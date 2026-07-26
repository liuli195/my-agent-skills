import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const npmRoot = spawnSync(
	process.platform === "win32" ? process.env.ComSpec : "npm",
	process.platform === "win32" ? ["/d", "/s", "/c", "npm root -g"] : ["root", "-g"],
	{ encoding: "utf8" },
).stdout.trim();
const piRoot = [join(process.cwd(), "node_modules"), npmRoot]
	.map((root) => join(root, "@earendil-works", "pi-coding-agent"))
	.find((root) => existsSync(join(root, "package.json")));
if (!piRoot) throw new Error("pi-coding-agent runtime not found");

const extensionPath = join(process.cwd(), "plugins", "pi-cache-diagnostics", "extensions", "pi-cache-diagnostics.ts");

const root = await mkdtemp(join(tmpdir(), "pi-cache-diagnostics-"));
try {
	const helper = join(root, "e2e.cjs");
	const stubPackage = join(root, "node_modules", "@earendil-works", "pi-coding-agent");
	await mkdir(stubPackage, { recursive: true });
	await writeFile(join(stubPackage, "package.json"), JSON.stringify({ main: "index.cjs" }));
	await writeFile(join(stubPackage, "index.cjs"), `module.exports = {
		getAgentDir: () => process.env.PI_CODING_AGENT_DIR,
		getPackageDir: () => ${JSON.stringify(piRoot)},
	};\n`);
	await writeFile(helper, String.raw`
const { createJiti } = require(${JSON.stringify(join(piRoot, "node_modules", "jiti", "lib", "jiti.cjs"))});
const loaded = createJiti(__filename)(${JSON.stringify(extensionPath)});
const extension = loaded.default;
const noMiss = loaded.detectMissedTokens(undefined, false, { input: 30000, cacheRead: 0, cacheWrite: 0 });
if (noMiss !== undefined) throw new Error("first uncached request was counted as a miss");
const newTail = loaded.detectMissedTokens(30000, true, { input: 25000, cacheRead: 30000, cacheWrite: 0 });
if (newTail !== undefined) throw new Error("fully cached old prefix plus a large new tail was counted as a miss");
const realMiss = loaded.detectMissedTokens(55000, true, { input: 55000, cacheRead: 0, cacheWrite: 0 });
if (realMiss !== 55000) throw new Error("real miss mismatch: " + realMiss);
const handlers = new Map();
const notifications = [];
const pi = {
	on(name, handler) { handlers.set(name, handler); },
	registerCommand() {},
};
let sessionId = "private-session-id";
const ctx = {
	model: { provider: "openai-codex" },
	sessionManager: { getSessionId: () => sessionId },
	ui: { notify: (...args) => notifications.push(args) },
};
const request = (model = "gpt-5.6-sol") => handlers.get("before_provider_request")({ payload: {
	model, input: [], instructions: "stable", tools: [],
}}, ctx);
const response = (usage, stopReason = "stop", model = "gpt-5.6-sol") => handlers.get("message_end")({ message: {
	role: "assistant", provider: "openai-codex", model, usage,
	stopReason, diagnostics: [],
}}, ctx);
(async () => {
	await extension(pi);
	handlers.get("session_start")({}, ctx);
	request(); response({ input: 30000, cacheRead: 0, cacheWrite: 0 });
	request(); response({ input: 25000, cacheRead: 30000, cacheWrite: 0 });
	request(); response({ input: 55000, cacheRead: 0, cacheWrite: 0 });
	request(); response({ input: 70000, cacheRead: 0, cacheWrite: 0 }, "error");
	request(); response({ input: 80000, cacheRead: 0, cacheWrite: 0 }, "aborted");
	request(); response({ input: 0, cacheRead: 0, cacheWrite: 0 });
	request(); response({ input: 30000, cacheRead: 30000, cacheWrite: 0 });
	request("gpt-5.6-terra"); response({ input: 1000, cacheRead: 60000, cacheWrite: 0 }, "stop", "gpt-5.6-terra");
	handlers.get("session_compact")();
	request("gpt-5.6-terra"); response({ input: 61000, cacheRead: 0, cacheWrite: 0 }, "stop", "gpt-5.6-terra");
	sessionId = "second-private-session-id";
	handlers.get("session_start")({}, ctx);
	request(); response({ input: 30000, cacheRead: 0, cacheWrite: 0 });
	if (notifications.length !== 2) throw new Error("large-miss notification mismatch: " + notifications.length);
})().catch((error) => { console.error(error); process.exitCode = 1; });
`);
	const run = spawnSync(process.execPath, [helper], {
		cwd: root,
		env: {
			...process.env,
			HOME: root,
			USERPROFILE: root,
			PI_CODING_AGENT_DIR: join(root, ".pi", "agent"),
			NODE_PATH: [join(root, "node_modules"), npmRoot, process.env.NODE_PATH]
				.filter(Boolean).join(process.platform === "win32" ? ";" : ":"),
		},
		encoding: "utf8",
	});
	if (run.status !== 0) throw new Error(`extension flow failed:\n${run.stdout}\n${run.stderr}`);
	const rows = (await readFile(join(root, ".pi", "agent", "diagnostics", "openai-codex-cache.jsonl"), "utf8"))
		.trim().split("\n").map(JSON.parse);
	const responses = rows.filter((row) => row.type === "response");
	if (responses[0].missedTokens !== undefined) throw new Error("cold request miss was logged");
	if (responses[1].missedTokens !== undefined || responses[1].largeMiss) throw new Error("new tail was logged as a miss");
	if (responses[2].missedTokens !== 55_000 || !responses[2].largeMiss) throw new Error("large miss was not logged");
	if (responses[3].missedTokens !== undefined) throw new Error("error response was counted as a miss");
	if (responses[4].missedTokens !== undefined) throw new Error("aborted response was counted as a miss");
	if (responses[5].missedTokens !== undefined) throw new Error("zero-usage response was counted as a miss");
	if (responses[6].missedTokens !== 25_000) throw new Error("invalid responses replaced the prior baseline");
	if (!responses[7].modelChanged) throw new Error("model switch was not logged");
	if (responses[8].missedTokens !== undefined) throw new Error("compaction did not reset the miss baseline");
	if (responses[9].missedTokens !== undefined) throw new Error("new session did not reset the miss baseline");
	const firstSessionHash = responses[0].sessionIdHash;
	const secondSessionHash = responses[9].sessionIdHash;
	if (!firstSessionHash || !secondSessionHash || firstSessionHash === secondSessionHash) {
		throw new Error("sessions were not separated by anonymous hashes");
	}
	if (responses.some((row) => ["private-session-id", "second-private-session-id"].includes(row.sessionIdHash))) {
		throw new Error("raw session id leaked into diagnostics");
	}
} finally {
	await rm(root, { recursive: true, force: true });
}

console.log("pi-cache-diagnostics tests passed");
