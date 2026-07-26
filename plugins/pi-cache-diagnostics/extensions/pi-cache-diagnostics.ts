import { createHash, randomUUID } from "node:crypto";
import { gzip, gunzip } from "node:zlib";
import { promisify } from "node:util";
import { mkdir, readFile, readdir, rename, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { getAgentDir, getPackageDir, type ExtensionAPI, type ExtensionContext } from "@earendil-works/pi-coding-agent";

// ponytail: OpenAI Codex only; add provider evidence adapters when another provider needs auditing.
const PROVIDER = "openai-codex";
const SCHEMA_VERSION = 1;
const ROOT = join(getAgentDir(), "diagnostics", "pi-cache-diagnostics");
const ACTIVE_DIR = join(ROOT, "active");
const CHECKPOINT_DIR = join(ROOT, "checkpoints");
const MISSES_DIR = join(ROOT, "misses");
const gzipAsync = promisify(gzip);
const gunzipAsync = promisify(gunzip);

type JsonRecord = Record<string, unknown>;
type CacheMiss = { missedTokens: number; missedCost: number; idleMs: number; modelChanged: boolean };
type DebugStats = Record<string, unknown>;
type CapturedEvent = JsonRecord & {
	type: string;
	eventSequence: number;
	timestampMs: number;
	timestampUtc: string;
	timestampLocal: string;
};

interface SessionState {
	sessionIdHash: string;
	eventSequence: number;
	baseline: CapturedEvent[];
	window: CapturedEvent[];
	currentRequestStart?: number;
	providerRequestId?: string;
	evidenceIncomplete: boolean;
	activePath: string;
	checkpointPath: string;
}

function hash(value: string): string {
	return createHash("sha256").update(value).digest("hex");
}

function localTimestamp(date: Date): string {
	const offsetMinutes = -date.getTimezoneOffset();
	const local = new Date(date.getTime() + offsetMinutes * 60_000).toISOString().slice(0, -1);
	const sign = offsetMinutes >= 0 ? "+" : "-";
	const offset = Math.abs(offsetMinutes);
	return `${local}${sign}${String(Math.floor(offset / 60)).padStart(2, "0")}:${String(offset % 60).padStart(2, "0")}`;
}

function jsonSafe(value: unknown): unknown {
	const seen = new WeakSet<object>();
	const encoded = JSON.stringify(value, (_key, item: unknown) => {
		if (typeof item === "bigint") return { $type: "bigint", value: item.toString() };
		if (typeof item === "function") return { $type: "function", name: item.name };
		if (typeof item === "symbol") return { $type: "symbol", value: String(item) };
		if (item && typeof item === "object") {
			if (seen.has(item)) return { $type: "circular" };
			seen.add(item);
		}
		return item;
	});
	return encoded === undefined ? { $type: "undefined" } : JSON.parse(encoded);
}

function timestampFields(now = new Date()): Pick<CapturedEvent, "timestampMs" | "timestampUtc" | "timestampLocal"> {
	return { timestampMs: now.getTime(), timestampUtc: now.toISOString(), timestampLocal: localTimestamp(now) };
}

function filterHeaders(headers: Record<string, unknown>): JsonRecord {
	const sensitive = /authorization|auth|cookie|token|secret|credential|session|signature|password|api[-_]?key/i;
	const allowed = /^(date|retry-after|traceparent|tracestate|request-id|x-request-id|x-trace-id|x-correlation-id|x-cache|x-cache-status|cf-cache-status|x-ratelimit-[a-z0-9-]+|ratelimit-[a-z0-9-]+|openai-processing-ms|openai-version|x-openai-version|x-model|x-client-version|user-agent)$/i;
	return Object.fromEntries(Object.entries(headers).map(([name, value]) => [
		name,
		sensitive.test(name)
			? { excluded: true, reason: "credential" }
			: allowed.test(name) ? jsonSafe(value) : { excluded: true, reason: "not-allowlisted" },
	]));
}

function lines(events: CapturedEvent[]): string {
	return `${events.map((event) => JSON.stringify(event)).join("\n")}\n`;
}

function safeFilename(value: string): string {
	return value.replace(/[^a-zA-Z0-9._-]/g, "-");
}

async function ensureDirectories(): Promise<void> {
	await Promise.all([mkdir(ACTIVE_DIR, { recursive: true }), mkdir(CHECKPOINT_DIR, { recursive: true }), mkdir(MISSES_DIR, { recursive: true })]);
}

export default async function (pi: ExtensionAPI): Promise<void> {
	const packageDir = getPackageDir();
	const cacheStatsPath = join(packageDir, "dist", "core", "cache-stats.js");
	const providerPath = join(packageDir, "node_modules", "@earendil-works", "pi-ai", "dist", "api", "openai-codex-responses.js");
	const [{ detectCacheMiss }, { getOpenAICodexWebSocketDebugStats }] = await Promise.all([
		import(pathToFileURL(cacheStatsPath).href) as Promise<{
			detectCacheMiss(entries: unknown[], message: unknown, models: unknown): CacheMiss | undefined;
		}>,
		import(pathToFileURL(providerPath).href) as Promise<{
			getOpenAICodexWebSocketDebugStats(sessionId: string): DebugStats | undefined;
		}>,
	]);

	let state: SessionState | undefined;
	let lastEvidence: string | undefined;
	let lastError: string | undefined;
	let fileQueue = Promise.resolve();
	let lifecycleQueue = Promise.resolve();
	const notifiedErrors = new Set<string>();

	function serializeFileOperation<T>(operation: () => Promise<T>): Promise<T> {
		const result = fileQueue.then(operation, operation);
		fileQueue = result.then(() => undefined, () => undefined);
		return result;
	}

	function serializeLifecycle(operation: () => Promise<void>): Promise<void> {
		const result = lifecycleQueue.then(operation, operation);
		lifecycleQueue = result.then(() => undefined, () => undefined);
		return result;
	}

	async function reportFailure(kind: string, error: unknown, ctx?: ExtensionContext): Promise<void> {
		lastError = `${kind}: ${error instanceof Error ? error.message : String(error)}`;
		if (state) {
			state.evidenceIncomplete = true;
			capture("audit_failure", { operation: kind, error: lastError });
		}
		if (ctx && !notifiedErrors.has(kind)) {
			notifiedErrors.add(kind);
			try {
				ctx.ui.notify(`Cache diagnostics ${kind} failed; model request was not interrupted`, "warning");
			} catch {
				// A reload can invalidate the UI context before background I/O reports its failure.
			}
		}
	}

	function capture(type: string, data: JsonRecord = {}): CapturedEvent | undefined {
		if (!state) return undefined;
		state.eventSequence += 1;
		const safeData = jsonSafe(data) as JsonRecord;
		const source = safeData.event as JsonRecord | undefined;
		const message = safeData.message as JsonRecord | undefined;
		const sourceTimestamp = source?.timestamp ?? message?.timestamp;
		const event = {
			type,
			eventSequence: state.eventSequence,
			...timestampFields(),
			...(typeof sourceTimestamp === "number" ? { sourceTimestampMs: sourceTimestamp } : {}),
			...safeData,
		} satisfies CapturedEvent;
		state.window.push(event);
		return event;
	}

	async function persistActive(ctx?: ExtensionContext, target = state): Promise<boolean> {
		if (!target) return false;
		const content = lines([...target.baseline, ...target.window]);
		const temporaryPath = `${target.activePath}.${randomUUID()}.tmp`;
		try {
			await serializeFileOperation(async () => {
				await ensureDirectories();
				await writeFile(temporaryPath, content, "utf8");
				await rename(temporaryPath, target.activePath);
			});
			return true;
		} catch (error) {
			await rm(temporaryPath, { force: true }).catch(() => undefined);
			await reportFailure("write", error, ctx);
			return false;
		}
	}

	function isMissing(error: unknown): boolean {
		return (error as NodeJS.ErrnoException | undefined)?.code === "ENOENT";
	}

	async function restore(sessionId: string, ctx: ExtensionContext): Promise<void> {
		const sessionIdHash = hash(sessionId);
		const originalActivePath = join(ACTIVE_DIR, `${sessionIdHash}.jsonl`);
		const checkpointPath = join(CHECKPOINT_DIR, `${sessionIdHash}.jsonl.gz`);
		let activePath = originalActivePath;
		let restored: CapturedEvent[] = [];
		let restoreError: unknown;
		try {
			await ensureDirectories();
			try {
				restored = readEvents(await readFile(originalActivePath));
			} catch (activeError) {
				if (!isMissing(activeError)) throw activeError;
				try {
					restored = readEvents(await gunzipAsync(await readFile(checkpointPath)));
				} catch (checkpointError) {
					if (!isMissing(checkpointError)) throw checkpointError;
				}
			}
		} catch (error) {
			restoreError = error;
			activePath = join(ACTIVE_DIR, `${sessionIdHash}.recovery-${randomUUID()}.jsonl`);
		}
		state = {
			sessionIdHash,
			eventSequence: restored.at(-1)?.eventSequence ?? 0,
			baseline: restored,
			window: [],
			evidenceIncomplete: restoreError !== undefined,
			activePath,
			checkpointPath,
		};
		if (restoreError) await reportFailure("restore", restoreError, ctx);
		capture("session_start", { sessionIdHash });
		await persistActive(ctx);
	}

	function readEvents(buffer: Buffer): CapturedEvent[] {
		return buffer.toString("utf8").split("\n").filter(Boolean).map((line) => JSON.parse(line) as CapturedEvent);
	}

	async function checkpoint(ctx?: ExtensionContext, target = state): Promise<void> {
		if (!target) return;
		if (!await persistActive(ctx, target)) {
			await persistActive(ctx, target);
			return;
		}
		const temporaryPath = `${target.checkpointPath}.${randomUUID()}.tmp`;
		try {
			await serializeFileOperation(async () => {
				const compressed = await gzipAsync(await readFile(target.activePath));
				await writeFile(temporaryPath, compressed);
				await rename(temporaryPath, target.checkpointPath);
				await rm(target.activePath, { force: true });
			});
		} catch (error) {
			await rm(temporaryPath, { force: true }).catch(() => undefined);
			await reportFailure("checkpoint", error, ctx);
			await persistActive(ctx, target);
		}
	}

	async function finalizeMiss(miss: CacheMiss, message: JsonRecord, ctx: ExtensionContext): Promise<void> {
		if (!state) return;
		const complete = capture("evidence_complete", { providerRequestId: state.providerRequestId });
		if (!complete) return;
		const bodyEvents = [...state.baseline, ...state.window];
		const manifest: CapturedEvent = {
			type: "evidence_manifest",
			eventSequence: 0,
			...timestampFields(),
			schemaVersion: SCHEMA_VERSION,
			sessionIdHash: state.sessionIdHash,
			provider: message.provider,
			model: message.model,
			providerRequestId: state.providerRequestId,
			missedTokens: miss.missedTokens,
			miss: jsonSafe(miss),
			evidenceIncomplete: state.evidenceIncomplete || state.baseline.length === 0,
			eventCount: bodyEvents.length,
			startTimestampMs: bodyEvents.at(0)?.timestampMs,
			endTimestampMs: bodyEvents.at(-1)?.timestampMs,
		};
		const stamp = new Date().toISOString().replace(/[:.]/g, "-");
		const requestId = safeFilename(state.providerRequestId ?? "unobserved");
		const sessionDir = join(MISSES_DIR, state.sessionIdHash);
		const base = `${stamp}-${state.eventSequence}-miss-${miss.missedTokens}-${requestId}`;
		const jsonlPath = join(sessionDir, `${base}.jsonl`);
		const gzipTmpPath = join(sessionDir, `${base}.jsonl.gz.tmp`);
		const gzipPath = join(sessionDir, `${base}.jsonl.gz`);
		try {
			await serializeFileOperation(async () => {
				await mkdir(sessionDir, { recursive: true });
				await writeFile(jsonlPath, lines([manifest, ...bodyEvents]), "utf8");
				try {
					await writeFile(gzipTmpPath, await gzipAsync(await readFile(jsonlPath)));
					await rename(gzipTmpPath, gzipPath);
					await rm(jsonlPath, { force: true });
					lastEvidence = gzipPath;
				} catch (error) {
					const failedPath = `${jsonlPath}.failed`;
					const message = error instanceof Error ? error.message : String(error);
					const failedManifest = { ...manifest, evidenceIncomplete: true, storageStatus: "compression_failed", storageError: message };
					const failureEvent: CapturedEvent = {
						type: "evidence_storage_failure",
						eventSequence: complete.eventSequence + 1,
						...timestampFields(),
						operation: "compression",
						error: message,
					};
					await writeFile(failedPath, lines([failedManifest, ...bodyEvents, failureEvent]), "utf8");
					await Promise.all([rm(jsonlPath, { force: true }), rm(gzipTmpPath, { force: true })]);
					lastEvidence = failedPath;
					await reportFailure("compression", error, ctx);
				}
			});
		} catch (error) {
			await reportFailure("evidence", error, ctx);
		}
	}

	function finishAssistant(message: JsonRecord, ctx: ExtensionContext): void {
		if (!state) return;
		const miss = detectCacheMiss(ctx.sessionManager.getEntries(), message, ctx.modelRegistry);
		capture("message_end", {
			providerRequestId: state.providerRequestId,
			message,
			transportStatsAfter: getOpenAICodexWebSocketDebugStats(ctx.sessionManager.getSessionId()),
			cacheMiss: miss,
		});
		if (miss) void finalizeMiss(miss, message, ctx);

		const usage = message.usage as JsonRecord | undefined;
		const promptTokens = Number(usage?.input ?? 0) + Number(usage?.cacheRead ?? 0) + Number(usage?.cacheWrite ?? 0);
		if (promptTokens > 0) {
			const start = state.currentRequestStart ?? Math.max(0, state.window.length - 1);
			state.baseline = state.window.slice(start);
			state.window = [];
			state.currentRequestStart = undefined;
			state.providerRequestId = undefined;
			state.evidenceIncomplete = false;
		}
		void persistActive(ctx);
	}

	pi.on("session_start", (event, ctx) => serializeLifecycle(async () => {
		await restore(ctx.sessionManager.getSessionId(), ctx);
		capture("session_start_reason", { reason: event.reason, previousSessionFile: event.previousSessionFile });
		await persistActive(ctx);
	}));
	pi.on("session_shutdown", (event, ctx) => serializeLifecycle(async () => {
		const closingState = state;
		capture("session_shutdown", { event });
		await checkpoint(ctx, closingState);
		if (state === closingState) state = undefined;
	}));
	pi.on("session_compact", async (event, ctx) => {
		capture("session_compact", { event });
		if (state) {
			state.baseline = [];
			state.evidenceIncomplete = false;
		}
		await persistActive(ctx);
	});
	pi.on("session_tree", async (event, ctx) => {
		capture("session_tree", { event });
		if (state) {
			state.baseline = [];
			state.evidenceIncomplete = true;
		}
		await persistActive(ctx);
	});

	for (const eventName of [
		"input", "before_agent_start", "agent_start", "agent_end", "turn_start", "turn_end", "context",
		"tool_execution_start", "tool_execution_end", "model_select", "thinking_level_select",
	] as const) {
		pi.on(eventName, (event, ctx) => {
			capture(eventName, { event });
			void persistActive(ctx);
		});
	}

	pi.on("before_provider_request", (event, ctx) => {
		if (ctx.model?.provider !== PROVIDER || !state) return;
		state.providerRequestId = randomUUID();
		state.currentRequestStart = state.window.length;
		capture("provider_request_observed", {
			providerRequestId: state.providerRequestId,
			observedProviderPayload: event.payload,
			transportStatsBefore: getOpenAICodexWebSocketDebugStats(ctx.sessionManager.getSessionId()),
		});
		void persistActive(ctx);
	});
	pi.on("before_provider_headers", (event, ctx) => {
		if (ctx.model?.provider !== PROVIDER) return;
		capture("provider_headers_observed", { providerRequestId: state?.providerRequestId, headers: filterHeaders(event.headers) });
		void persistActive(ctx);
	});
	pi.on("after_provider_response", (event, ctx) => {
		if (ctx.model?.provider !== PROVIDER) return;
		capture("provider_response_observed", {
			providerRequestId: state?.providerRequestId,
			status: event.status,
			headers: filterHeaders(event.headers),
		});
		void persistActive(ctx);
	});
	pi.on("message_end", (event, ctx) => {
		const message = event.message as unknown as JsonRecord;
		if (message.role === "assistant" && message.provider === PROVIDER) finishAssistant(message, ctx);
	});

	pi.registerCommand("cache-diagnostics", {
		description: "Show OpenAI Codex cache evidence status",
		handler: async (_args, ctx) => {
			let count = 0;
			try {
				for (const session of await readdir(MISSES_DIR, { withFileTypes: true })) {
					if (!session.isDirectory()) continue;
					count += (await readdir(join(MISSES_DIR, session.name))).filter((name) => name.endsWith(".jsonl.gz") || name.endsWith(".jsonl.failed")).length;
				}
			} catch {
				// No evidence directory yet.
			}
			ctx.ui.notify(
				`Cache diagnostics active • ${count} evidence package${count === 1 ? "" : "s"} • ${lastError ?? "healthy"} • ${lastEvidence ?? ROOT}`,
				lastError ? "warning" : "info",
			);
		},
	});
}
