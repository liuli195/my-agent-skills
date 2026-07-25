import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const roots = [
	process.env.APPDATA && join(process.env.APPDATA, "npm", "node_modules"),
	process.env.ProgramFiles && join(process.env.ProgramFiles, "nodejs", "node_modules"),
	"/usr/local/lib/node_modules",
	"/usr/lib/node_modules",
].filter(Boolean);
const jitiPath = roots
	.map((root) => join(root, "@earendil-works", "pi-coding-agent", "node_modules", "jiti", "lib", "jiti.cjs"))
	.find(existsSync);
if (!jitiPath) throw new Error("pi-coding-agent jiti runtime not found");

const { createJiti } = createRequire(import.meta.url)(jitiPath);
const usage = createJiti(import.meta.url)(
	join(process.cwd(), "plugins", "pi-codex-usage-status", "extensions", "usage.ts"),
);
const now = Date.UTC(2026, 0, 1, 3);
const parsed = usage.parseUsage({
	rate_limit: {
		primary_window: { used_percent: 1, reset_at: 0, limit_window_seconds: 18_000 },
		secondary_window: {
			used_percent: 14.2,
			reset_at: (now + 6 * 86_400_000 + 21 * 3_600_000 + 3_599_000) / 1_000,
			limit_window_seconds: 604_800,
		},
	},
});
if (!parsed) throw new Error("seven-day window not parsed");
if (usage.formatUsage(parsed, now) !== "Codex：85%/6D21H") throw new Error("active format mismatch");
if (usage.formatUsage(parsed, parsed.resetAtMs) !== "Codex：--%/0D0H") throw new Error("expired format mismatch");
if (usage.refreshMilliseconds({}) !== 15_000) throw new Error("default interval mismatch");
if (usage.refreshMilliseconds({ codexUsageStatus: { refreshSeconds: 30 } }) !== 30_000) {
	throw new Error("custom interval mismatch");
}
if (usage.refreshMilliseconds({ codexUsageStatus: { refreshSeconds: 0 } }) !== 15_000) {
	throw new Error("invalid interval mismatch");
}
