import { SettingsManager, type ExtensionAPI, type ExtensionContext } from "@earendil-works/pi-coding-agent";
import { formatUsage, parseUsage, refreshMilliseconds, type CodexUsage } from "./usage.ts";

const STATUS_KEY = "mcp-codex";
const USAGE_URL = "https://chatgpt.com/backend-api/wham/usage";

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
	return value !== null && typeof value === "object" && !Array.isArray(value);
}

function accountIdFromToken(token: string): string | undefined {
	try {
		const encoded = token.split(".")[1];
		if (!encoded) return undefined;
		const payload = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8")) as unknown;
		if (!isRecord(payload)) return undefined;
		const auth = payload["https://api.openai.com/auth"];
		return isRecord(auth) && typeof auth.chatgpt_account_id === "string"
			? auth.chatgpt_account_id
			: undefined;
	} catch {
		return undefined;
	}
}

async function fetchUsage(ctx: ExtensionContext, signal: AbortSignal): Promise<CodexUsage | undefined> {
	const model = ctx.modelRegistry.getAll().find((candidate) => candidate.provider === "openai-codex");
	if (!model) return undefined;
	const auth = await ctx.modelRegistry.getApiKeyAndHeaders(model);
	if (!auth.ok || !auth.apiKey) return undefined;
	const accountId = accountIdFromToken(auth.apiKey);
	if (!accountId) return undefined;
	const response = await fetch(USAGE_URL, {
		headers: {
			Authorization: `Bearer ${auth.apiKey}`,
			"chatgpt-account-id": accountId,
			originator: "pi",
		},
		signal,
	});
	if (!response.ok) return undefined;
	return parseUsage(await response.json());
}

export default function (pi: ExtensionAPI): void {
	let timer: ReturnType<typeof setInterval> | undefined;
	let controller: AbortController | undefined;
	let usage: CodexUsage | undefined;
	let refreshing = false;
	let generation = 0;
	let statusUI: ExtensionContext["ui"] | undefined;

	const setStatus = (ui: ExtensionContext["ui"] | undefined, text: string | undefined): boolean => {
		if (!ui) return true;
		try {
			ui.setStatus(STATUS_KEY, text);
			return true;
		} catch {
			// Pi can invalidate a runtime before its shutdown reaches this extension instance.
			return false;
		}
	};

	const stop = (clearStatus = true): void => {
		generation += 1;
		if (timer) clearInterval(timer);
		timer = undefined;
		controller?.abort();
		controller = undefined;
		refreshing = false;
		const ui = statusUI;
		statusUI = undefined;
		if (clearStatus) setStatus(ui, undefined);
	};

	pi.on("session_start", (_event, ctx) => {
		stop();
		statusUI = ctx.ui;
		usage = undefined;
		const settings = SettingsManager.create(ctx.cwd).getGlobalSettings() as unknown;
		const interval = refreshMilliseconds(settings);
		const sessionGeneration = generation;

		const refresh = async (): Promise<void> => {
			if (refreshing || sessionGeneration !== generation) return;
			refreshing = true;
			const currentController = new AbortController();
			controller = currentController;
			try {
				const latest = await fetchUsage(ctx, currentController.signal);
				if (latest && sessionGeneration === generation) usage = latest;
			} catch {
				// Keep the last successful value on temporary API or network failures.
			} finally {
				if (controller === currentController) controller = undefined;
				if (sessionGeneration === generation) {
					refreshing = false;
					if (!setStatus(statusUI, usage ? formatUsage(usage) : undefined)) stop(false);
				}
			}
		};

		const runRefresh = (): void => {
			// Runtime invalidation can happen without another event reaching this extension instance.
			void refresh().catch(() => stop(false));
		};

		runRefresh();
		timer = setInterval(runRefresh, interval);
	});

	pi.on("session_shutdown", stop);
}
