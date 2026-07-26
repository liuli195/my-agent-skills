import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
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
const extension = createJiti(__filename)(${JSON.stringify(extensionPath)}).default;
const handlers = new Map();
const notifications = [];
const pi = {
	on(name, handler) { handlers.set(name, handler); },
	registerCommand() {},
};
const entries = [];
const sessionId = "private-session-id";
const ctx = {
	model: { provider: "openai-codex" },
	modelRegistry: { getModel: () => ({ cost: { cacheRead: 0 } }) },
	sessionManager: {
		getSessionId: () => sessionId,
		getEntries: () => entries,
	},
	ui: { notify: (...args) => notifications.push(args) },
};
async function request() {
	await handlers.get("before_provider_request")({ payload: {
		model: "gpt-5.6-sol", input: [], instructions: "stable", tools: [],
	}}, ctx);
	await handlers.get("before_provider_headers")({ headers: {
		authorization: "Bearer secret", "x-client-auth": "custom-secret", "x-request-id": "request-visible", "x-unrelated": "hidden",
	}}, ctx);
	await handlers.get("after_provider_response")({ status: 200, headers: {
		"set-cookie": "secret-cookie", "x-request-id": "response-visible",
	}}, ctx);
}
async function response(usage) {
	const message = {
		role: "assistant", provider: "openai-codex", model: "gpt-5.6-sol", usage,
		stopReason: "stop", timestamp: Date.now(), content: [],
	};
	await handlers.get("message_end")({ message }, ctx);
	entries.push({ type: "message", message });
}
(async () => {
	await extension(pi);
	await handlers.get("session_start")({ reason: "startup" }, ctx);
	await request(); await response({ input: 30000, cacheRead: 0, cacheWrite: 0, cost: { input: 0, cacheRead: 0, cacheWrite: 0 } });
	await request(); await response({ input: 1000, cacheRead: 29696, cacheWrite: 0, cost: { input: 0, cacheRead: 0, cacheWrite: 0 } });
	await request(); await response({ input: 31000, cacheRead: 0, cacheWrite: 0, cost: { input: 0, cacheRead: 0, cacheWrite: 0 } });
	await Promise.all([
		handlers.get("session_shutdown")({ reason: "reload" }, ctx),
		handlers.get("session_start")({ reason: "reload" }, ctx),
	]);
	await request(); await response({ input: 31000, cacheRead: 0, cacheWrite: 0, cost: { input: 0, cacheRead: 0, cacheWrite: 0 } });
	await handlers.get("session_tree")({ newLeafId: "older", oldLeafId: "newer" }, ctx);
	await request(); await response({ input: 31000, cacheRead: 0, cacheWrite: 0, cost: { input: 0, cacheRead: 0, cacheWrite: 0 } });
	entries.push({ type: "compaction" });
	await handlers.get("session_compact")({ reason: "manual", willRetry: false }, ctx);
	await request(); await response({ input: 31000, cacheRead: 0, cacheWrite: 0, cost: { input: 0, cacheRead: 0, cacheWrite: 0 } });
	await handlers.get("session_shutdown")({ reason: "quit" }, ctx);
	if (notifications.length) throw new Error("successful audit emitted a notification");
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

	const diagnostics = join(root, ".pi", "agent", "diagnostics", "pi-cache-diagnostics");
	const sessionDirs = await readdir(join(diagnostics, "misses"));
	if (sessionDirs.length !== 1 || sessionDirs[0] === "private-session-id") throw new Error("session id was not hashed");
	const evidenceFiles = (await readdir(join(diagnostics, "misses", sessionDirs[0]))).filter((name) => name.endsWith(".jsonl.gz"));
	if (evidenceFiles.length !== 3 || evidenceFiles.some((name) => !name.includes("miss-"))) {
		throw new Error(`expected three native miss evidence packages, got ${evidenceFiles}`);
	}
	const packages = await Promise.all(evidenceFiles.map(async (name) => gunzipSync(await readFile(join(diagnostics, "misses", sessionDirs[0], name)))
		.toString("utf8").trim().split("\n").map(JSON.parse)));
	const evidence = packages[0];
	if (packages.some((rows) => rows[0].type !== "evidence_manifest" || rows[0].schemaVersion !== 1)) throw new Error("manifest missing");
	if (packages.some((rows) => rows.at(-1).type !== "evidence_complete")) throw new Error("completion marker missing");
	if (packages.filter((rows) => rows[0].evidenceIncomplete).length !== 1) throw new Error("tree evidence boundary was not marked exactly once");
	if (!packages.some((rows) => rows.some((row) => row.type === "session_start_reason" && row.reason === "reload"))) throw new Error("reload checkpoint was not restored into evidence");
	const requestHeaders = evidence.find((row) => row.type === "provider_headers_observed").headers;
	if (!requestHeaders.authorization.excluded || requestHeaders.authorization.value) throw new Error("authorization leaked");
	if (!requestHeaders["x-client-auth"].excluded || requestHeaders["x-client-auth"].value) throw new Error("custom credential header leaked");
	if (requestHeaders["x-request-id"] !== "request-visible") throw new Error("allowlisted request id missing");
	if (!requestHeaders["x-unrelated"].excluded) throw new Error("unknown header leaked");
	const responseHeaders = evidence.find((row) => row.type === "provider_response_observed").headers;
	if (!responseHeaders["set-cookie"].excluded || responseHeaders["set-cookie"].value) throw new Error("cookie leaked");
	if (["Bearer secret", "custom-secret", "secret-cookie"].some((secret) => JSON.stringify(evidence).includes(secret))) throw new Error("credential value leaked");

	const oldLog = join(root, ".pi", "agent", "diagnostics", "openai-codex-cache.jsonl");
	if (existsSync(oldLog)) throw new Error("legacy log was modified");
} finally {
	await rm(root, { recursive: true, force: true });
}

console.log("pi-cache-diagnostics tests passed");
