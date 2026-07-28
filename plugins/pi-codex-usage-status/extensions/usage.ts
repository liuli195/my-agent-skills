const DEFAULT_REFRESH_SECONDS = 15;
const SEVEN_DAYS_SECONDS = 7 * 24 * 60 * 60;

type JsonRecord = Record<string, unknown>;

export interface CodexUsage {
	remainingPercent: number;
	resetAtMs: number;
}

function isRecord(value: unknown): value is JsonRecord {
	return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function refreshMilliseconds(settings: unknown): number {
	const value = isRecord(settings)
		&& isRecord(settings.codexUsageStatus)
		? settings.codexUsageStatus.refreshSeconds
		: undefined;
	return typeof value === "number" && Number.isFinite(value) && value > 0
		? value * 1_000
		: DEFAULT_REFRESH_SECONDS * 1_000;
}

export function parseUsage(payload: unknown): CodexUsage | undefined {
	if (!isRecord(payload) || !isRecord(payload.rate_limit)) return undefined;
	const windows = [payload.rate_limit.primary_window, payload.rate_limit.secondary_window];
	for (const candidate of windows) {
		if (!isRecord(candidate) || candidate.limit_window_seconds !== SEVEN_DAYS_SECONDS) continue;
		const usedPercent = candidate.used_percent;
		const resetAt = candidate.reset_at;
		if (
			typeof usedPercent !== "number"
			|| !Number.isFinite(usedPercent)
			|| typeof resetAt !== "number"
			|| !Number.isFinite(resetAt)
		) return undefined;
		return {
			remainingPercent: Math.floor(Math.max(0, Math.min(100, 100 - usedPercent))),
			resetAtMs: resetAt * 1_000,
		};
	}
	return undefined;
}

export function formatUsage(usage: CodexUsage, now = Date.now()): string {
	const remainingMs = usage.resetAtMs - now;
	if (remainingMs <= 0) return "Codex：--%/0D0H";
	const totalHours = Math.floor(remainingMs / 3_600_000);
	if (totalHours === 0) {
		return `Codex：${Math.floor(usage.remainingPercent)}%/${Math.floor(remainingMs / 60_000)}M`;
	}
	const days = Math.floor(totalHours / 24);
	const hours = totalHours % 24;
	return `Codex：${Math.floor(usage.remainingPercent)}%/${days}D${hours}H`;
}
