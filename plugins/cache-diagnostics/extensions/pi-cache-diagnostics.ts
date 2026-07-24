import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { getAgentDir, getPackageDir, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

type JsonRecord = Record<string, unknown>;

interface OpenAICodexWebSocketDebugStats {
	requests: number;
	connectionsCreated: number;
	connectionsReused: number;
	cachedContextRequests: number;
	storeTrueRequests: number;
	fullContextRequests: number;
	deltaRequests: number;
	lastInputItems: number;
	lastDeltaInputItems?: number;
	lastPreviousResponseId?: string;
	websocketFailures: number;
	sseFallbacks: number;
	websocketFallbackActive?: boolean;
	lastWebSocketError?: string;
}

interface RequestSnapshot {
	sequence: number;
	statsBefore?: OpenAICodexWebSocketDebugStats;
}

const LOG_PATH = join(getAgentDir(), "diagnostics", "openai-codex-cache.jsonl");
const STAT_KEYS = [
	"requests",
	"connectionsCreated",
	"connectionsReused",
	"cachedContextRequests",
	"storeTrueRequests",
	"fullContextRequests",
	"deltaRequests",
	"websocketFailures",
	"sseFallbacks",
] as const;

function isRecord(value: unknown): value is JsonRecord {
	return value !== null && typeof value === "object" && !Array.isArray(value);
}

function serialized(value: unknown): string {
	return JSON.stringify(value) ?? "undefined";
}

function hash(value: unknown): string {
	return createHash("sha256").update(serialized(value)).digest("hex");
}

function localTimestamp(): string {
	const date = new Date();
	const offsetMinutes = -date.getTimezoneOffset();
	const local = new Date(date.getTime() + offsetMinutes * 60_000).toISOString().slice(0, -1);
	const sign = offsetMinutes >= 0 ? "+" : "-";
	const absoluteOffset = Math.abs(offsetMinutes);
	const hours = String(Math.floor(absoluteOffset / 60)).padStart(2, "0");
	const minutes = String(absoluteOffset % 60).padStart(2, "0");
	return `${local}${sign}${hours}:${minutes}`;
}

function stringDifference(previous: string, current: string): JsonRecord | undefined {
	if (previous === current) return undefined;

	let commonPrefixChars = 0;
	while (
		commonPrefixChars < previous.length
		&& commonPrefixChars < current.length
		&& previous[commonPrefixChars] === current[commonPrefixChars]
	) {
		commonPrefixChars += 1;
	}

	let commonSuffixChars = 0;
	while (
		commonSuffixChars < previous.length - commonPrefixChars
		&& commonSuffixChars < current.length - commonPrefixChars
		&& previous[previous.length - commonSuffixChars - 1] === current[current.length - commonSuffixChars - 1]
	) {
		commonSuffixChars += 1;
	}

	const oldChangedEnd = previous.length - commonSuffixChars;
	const newChangedEnd = current.length - commonSuffixChars;
	const oldChanged = previous.slice(commonPrefixChars, oldChangedEnd);
	const newChanged = current.slice(commonPrefixChars, newChangedEnd);
	const snippetStart = Math.max(0, commonPrefixChars - 100);
	const oldSnippetEnd = Math.min(previous.length, snippetStart + 200);
	const newSnippetEnd = Math.min(current.length, snippetStart + 200);
	const beforeDifference = current.slice(0, commonPrefixChars);
	const lastNewline = beforeDifference.lastIndexOf("\n");
	const headings = current.slice(0, commonPrefixChars + 1).match(/^#{1,6}\s+.*$/gm);

	return {
		line: (beforeDifference.match(/\n/g)?.length ?? 0) + 1,
		column: commonPrefixChars - lastNewline,
		section: headings?.at(-1),
		commonPrefixChars,
		commonSuffixChars,
		oldLength: previous.length,
		newLength: current.length,
		oldChangedChars: oldChanged.length,
		newChangedChars: newChanged.length,
		oldChangedHash: hash(oldChanged),
		newChangedHash: hash(newChanged),
		oldSnippetStart: snippetStart,
		newSnippetStart: snippetStart,
		oldSnippet: previous.slice(snippetStart, oldSnippetEnd),
		newSnippet: current.slice(snippetStart, newSnippetEnd),
		oldChangedTruncated: oldChangedEnd > oldSnippetEnd,
		newChangedTruncated: newChangedEnd > newSnippetEnd,
	};
}

function firstDifference(left: unknown, right: unknown, path = "$"): string | undefined {
	if (serialized(left) === serialized(right)) return undefined;
	if (Array.isArray(left) && Array.isArray(right)) {
		const length = Math.min(left.length, right.length);
		for (let index = 0; index < length; index++) {
			const difference = firstDifference(left[index], right[index], `${path}[${index}]`);
			if (difference) return difference;
		}
		return `${path}.length`;
	}
	if (isRecord(left) && isRecord(right)) {
		const leftKeys = Object.keys(left);
		const rightKeys = Object.keys(right);
		if (serialized(leftKeys) !== serialized(rightKeys)) return `${path}.[[key-order]]`;
		for (const key of leftKeys) {
			const difference = firstDifference(left[key], right[key], `${path}.${key}`);
			if (difference) return difference;
		}
	}
	return path;
}

function compareInputPrefix(previous: unknown[], current: unknown[]): {
	matches: boolean;
	firstDifference?: string;
} {
	if (current.length < previous.length) {
		return { matches: false, firstDifference: "$.input.length" };
	}
	for (let index = 0; index < previous.length; index++) {
		const difference = firstDifference(previous[index], current[index], `$.input[${index}]`);
		if (difference) return { matches: false, firstDifference: difference };
	}
	return { matches: true };
}

function statsDelta(
	before: OpenAICodexWebSocketDebugStats | undefined,
	after: OpenAICodexWebSocketDebugStats | undefined,
): Partial<Record<(typeof STAT_KEYS)[number], number>> | undefined {
	if (!before || !after) return undefined;
	return Object.fromEntries(STAT_KEYS.map((key) => [key, after[key] - before[key]]));
}

function append(entry: JsonRecord): void {
	mkdirSync(join(getAgentDir(), "diagnostics"), { recursive: true });
	appendFileSync(LOG_PATH, `${JSON.stringify(entry)}\n`, "utf8");
}

export default async function (pi: ExtensionAPI): Promise<void> {
	const providerModulePath = join(
		getPackageDir(),
		"node_modules",
		"@earendil-works",
		"pi-ai",
		"dist",
		"api",
		"openai-codex-responses.js",
	);
	const { getOpenAICodexWebSocketDebugStats } = await import(pathToFileURL(providerModulePath).href) as {
		getOpenAICodexWebSocketDebugStats(sessionId: string): OpenAICodexWebSocketDebugStats | undefined;
	};

	let sequence = 0;
	let previousInput: unknown[] | undefined;
	let previousInstructions: string | undefined;
	let previousWithoutInput: JsonRecord | undefined;
	let pending: RequestSnapshot | undefined;
	let previousPromptTokens: number | undefined;

	pi.on("session_start", (_event, ctx) => {
		sequence = 0;
		previousInput = undefined;
		previousInstructions = undefined;
		previousWithoutInput = undefined;
		pending = undefined;
		previousPromptTokens = undefined;
		append({
			type: "session_start",
			timestamp: localTimestamp(),
			sessionIdHash: hash(ctx.sessionManager.getSessionId()),
		});
	});

	pi.on("before_provider_request", (event, ctx) => {
		if (ctx.model?.provider !== "openai-codex" || !isRecord(event.payload)) return;

		const payload = event.payload;
		const input = Array.isArray(payload.input) ? payload.input : [];
		const instructions = typeof payload.instructions === "string" ? payload.instructions : undefined;
		const { input: _input, previous_response_id: _previousResponseId, ...withoutInput } = payload;
		const prefix = previousInput ? compareInputPrefix(previousInput, input) : undefined;
		const instructionsDifference = previousInstructions && instructions
			? stringDifference(previousInstructions, instructions)
			: undefined;
		const firstWithoutInputDifference = previousWithoutInput
			? firstDifference(previousWithoutInput, withoutInput)
			: undefined;
		const sessionId = ctx.sessionManager.getSessionId();
		const statsBefore = getOpenAICodexWebSocketDebugStats(sessionId);
		sequence += 1;
		pending = { sequence, statsBefore };

		append({
			type: "request",
			timestamp: localTimestamp(),
			sequence,
			model: payload.model,
			inputItems: input.length,
			inputHash: hash(input),
			instructionsLength: instructions?.length,
			instructionsHash: hash(payload.instructions),
			instructionsDifference,
			toolsCount: Array.isArray(payload.tools) ? payload.tools.length : 0,
			toolsHash: hash(payload.tools),
			withoutInputHash: hash(withoutInput),
			firstWithoutInputDifference,
			previousInputPrefixMatches: prefix?.matches,
			firstPrefixDifference: prefix?.firstDifference,
			statsAvailable: statsBefore !== undefined,
		});
		previousInput = input;
		previousInstructions = instructions;
		previousWithoutInput = withoutInput;
	});

	pi.on("message_end", (event, ctx) => {
		const message = event.message;
		if (message.role !== "assistant" || message.provider !== "openai-codex") return;

		const usage = message.usage;
		const promptTokens = usage.input + usage.cacheRead + usage.cacheWrite;
		const hasPromptUsage = promptTokens > 0;
		const missedTokens = !hasPromptUsage || previousPromptTokens === undefined
			? undefined
			: Math.max(0, Math.min(previousPromptTokens, promptTokens) - usage.cacheRead);
		const statsAfter = getOpenAICodexWebSocketDebugStats(ctx.sessionManager.getSessionId());
		const delta = statsDelta(pending?.statsBefore, statsAfter);

		append({
			type: "response",
			timestamp: localTimestamp(),
			sequence: pending?.sequence,
			stopReason: message.stopReason,
			promptTokens,
			inputTokens: usage.input,
			cacheReadTokens: usage.cacheRead,
			cacheWriteTokens: usage.cacheWrite,
			missedTokens,
			statsDelta: delta,
			lastInputItems: statsAfter?.lastInputItems,
			lastDeltaInputItems: statsAfter?.lastDeltaInputItems,
			previousResponseIdSent: statsAfter?.lastPreviousResponseId !== undefined,
			websocketFallbackActive: statsAfter?.websocketFallbackActive,
			lastWebSocketError: statsAfter?.lastWebSocketError,
			diagnostics: message.diagnostics?.map((diagnostic) => diagnostic.type),
		});

		if (missedTokens !== undefined && missedTokens >= 20_000) {
			ctx.ui.notify(`Cache diagnostics captured request #${pending?.sequence ?? "?"}`, "warning");
		}
		if (hasPromptUsage) previousPromptTokens = promptTokens;
		pending = undefined;
	});

	pi.on("session_compact", () => {
		append({ type: "session_compact", timestamp: localTimestamp() });
		previousInput = undefined;
		previousWithoutInput = undefined;
		previousPromptTokens = undefined;
	});

	pi.registerCommand("cache-diagnostics", {
		description: "Show OpenAI Codex cache diagnostic status",
		handler: async (_args, ctx) => {
			const stats = getOpenAICodexWebSocketDebugStats(ctx.sessionManager.getSessionId());
			ctx.ui.notify(
				stats
					? `Cache diagnostics active • ${stats.deltaRequests} delta / ${stats.fullContextRequests} full • ${LOG_PATH}`
					: `Cache diagnostics active • waiting for first OpenAI Codex request • ${LOG_PATH}`,
				"info",
			);
		},
	});
}
