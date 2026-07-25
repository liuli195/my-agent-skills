import { existsSync } from "node:fs";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn, spawnSync } from "node:child_process";

const npmRoot = spawnSync(
	process.platform === "win32" ? process.env.ComSpec : "npm",
	process.platform === "win32" ? ["/d", "/s", "/c", "npm root -g"] : ["root", "-g"],
	{ encoding: "utf8" },
).stdout.trim();
const piRoot = [join(process.cwd(), "node_modules"), npmRoot]
	.map((root) => join(root, "@earendil-works", "pi-coding-agent"))
	.find((root) => existsSync(join(root, "package.json")));
if (!piRoot) throw new Error("pi-coding-agent runtime not found");
const jitiPath = join(piRoot, "node_modules", "jiti", "lib", "jiti.cjs");

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
const boundaryUsage = { remainingPercent: 85, resetAtMs: now + 3_600_000 };
if (usage.formatUsage(boundaryUsage, now) !== "Codex：85%/0D1H") throw new Error("hour boundary mismatch");
if (usage.formatUsage({ ...boundaryUsage, resetAtMs: now + 45 * 60_000 + 59_000 }, now) !== "Codex：85%/45M") {
	throw new Error("minute format mismatch");
}
if (usage.formatUsage({ ...boundaryUsage, resetAtMs: now + 59_000 }, now) !== "Codex：85%/0M") {
	throw new Error("sub-minute format mismatch");
}
if (usage.formatUsage(parsed, parsed.resetAtMs) !== "Codex：--%/0D0H") throw new Error("expired format mismatch");
if (usage.refreshMilliseconds({}) !== 15_000) throw new Error("default interval mismatch");
if (usage.refreshMilliseconds({ codexUsageStatus: { refreshSeconds: 30 } }) !== 30_000) {
	throw new Error("custom interval mismatch");
}
if (usage.refreshMilliseconds({ codexUsageStatus: { refreshSeconds: 0 } }) !== 15_000) {
	throw new Error("invalid interval mismatch");
}

const helperSource = String.raw`
import { appendFileSync } from "node:fs";
import { ExtensionRunner } from "__PI_EXTENSION_RUNNER__";
const state = globalThis.__codexUsageLifecycle ??= { pending: [] };
if (!globalThis.__codexUsageRunnerPatch) {
	const createContext = ExtensionRunner.prototype.createContext;
	ExtensionRunner.prototype.createContext = function () {
		state.runner = this;
		return createContext.call(this);
	};
	globalThis.__codexUsageRunnerPatch = true;
}
const token = ["header", Buffer.from(JSON.stringify({
	"https://api.openai.com/auth": { chatgpt_account_id: "test-account" },
})).toString("base64url"), "signature"].join(".");
globalThis.fetch = (_url, options) => new Promise((resolve) => {
	if (process.env.PI_LIFECYCLE_REQUEST_LOG) {
		appendFileSync(process.env.PI_LIFECYCLE_REQUEST_LOG, "request\\n");
	}
	state.pending.push({ signal: options.signal, resolve: () => resolve({
		ok: true,
		json: async () => ({ rate_limit: { secondary_window: {
			used_percent: 25,
			reset_at: Date.now() / 1000 + 604800,
			limit_window_seconds: 604800,
		} } }),
	}) });
});
const waitForPending = async (count = 1) => {
	const deadline = Date.now() + 2000;
	while (state.pending.length < count && Date.now() < deadline) await new Promise((resolve) => setTimeout(resolve, 5));
	if (state.pending.length < count) throw new Error("usage request did not start");
};
const release = async (aborted) => {
	await waitForPending();
	const index = state.pending.findIndex((request) => request.signal.aborted === aborted);
	if (index < 0) throw new Error("no " + (aborted ? "aborted" : "active") + " usage request");
	state.pending.splice(index, 1)[0].resolve();
	await new Promise((resolve) => setTimeout(resolve, 25));
};
export default function (pi) {
	pi.on("session_start", (event, ctx) => {
		ctx.modelRegistry.getAll = () => [{ provider: "openai-codex" }];
		ctx.modelRegistry.getApiKeyAndHeaders = async () => ({ ok: true, apiKey: token });
		if (event.reason === "reload" && process.env.PI_LIFECYCLE_MARKER) {
			const setStatus = ctx.ui.setStatus.bind(ctx.ui);
			ctx.ui.setStatus = (key, text) => {
				setStatus(key, text);
				if (key === "mcp-codex" && text?.startsWith("Codex：75%/")) {
					appendFileSync(process.env.PI_LIFECYCLE_MARKER, "status-restored\\n");
				}
			};
			setTimeout(() => void release(false), 50);
		}
	});
	pi.registerCommand("test-reload", {
		handler: async (_args, ctx) => {
			await waitForPending();
			await ctx.reload();
			await release(true);
		},
	});
	pi.registerCommand("test-real-reload", {
		handler: async (_args, ctx) => {
			await waitForPending();
			await ctx.reload();
			await release(false);
			appendFileSync(process.env.PI_LIFECYCLE_MARKER, "reloaded\\n");
		},
	});
	pi.registerCommand("test-invalidate-reload", {
		handler: async (_args, ctx) => {
			await waitForPending();
			await ctx.reload();
			state.runner.invalidate();
			await release(false);
		},
	});
	pi.registerCommand("test-release", { handler: () => release(false) });
	pi.registerCommand("test-release-old", { handler: () => release(true) });
	pi.registerCommand("test-shutdown", { handler: (_args, ctx) => ctx.shutdown() });
}
`;

async function runLifecycleRegression({ faulty = false } = {}) {
	const root = await mkdtemp(join(tmpdir(), "pi-codex-usage-status-"));
	let child;
	try {
		const settingsDir = join(root, ".pi", "agent");
		await mkdir(settingsDir, { recursive: true });
		await writeFile(join(settingsDir, "settings.json"), JSON.stringify({
			codexUsageStatus: { refreshSeconds: 1 },
		}));
		const helper = join(root, "lifecycle-helper.ts");
		const requestLog = join(root, "requests.log");
		const runnerModule = join(piRoot, "dist", "core", "extensions", "runner.js").replaceAll("\\", "/");
		await writeFile(helper, helperSource.replace("__PI_EXTENSION_RUNNER__", runnerModule));
		const productionExtension = join(process.cwd(), "plugins", "pi-codex-usage-status", "extensions", "pi-codex-usage-status.ts");
		let extension = productionExtension;
		if (faulty) {
			extension = join(root, "faulty-pi-codex-usage-status.ts");
			const source = await readFile(productionExtension, "utf8");
			const usageModule = join(process.cwd(), "plugins", "pi-codex-usage-status", "extensions", "usage.ts").replaceAll("\\", "/");
			await writeFile(extension, source
				.replace('from "./usage.ts"', `from ${JSON.stringify(usageModule)}`)
				.replace(
					"if (!setStatus(statusUI, usage ? formatUsage(usage) : undefined)) stop(false);",
					"ctx.ui.setStatus(STATUS_KEY, usage ? formatUsage(usage) : undefined);",
				)
				.replace("void refresh().catch(() => stop(false));", "void refresh();"));
		}
		const cli = join(piRoot, "dist", "cli.js");
		child = spawn(process.execPath, [cli,
			"--mode", "rpc", "--no-session", "--offline", "--no-extensions", "--no-skills",
			"--no-prompt-templates", "--no-context-files", "-e", helper, "-e", extension,
		], {
			cwd: root,
			env: { ...process.env, HOME: root, USERPROFILE: root, PI_LIFECYCLE_REQUEST_LOG: requestLog },
			stdio: ["pipe", "pipe", "pipe"],
		});
		let stdout = "";
		let stderr = "";
		const events = [];
		child.stderr.setEncoding("utf8");
		child.stderr.on("data", (chunk) => { stderr += chunk; });
		child.stdout.setEncoding("utf8");
		child.stdout.on("data", (chunk) => {
			stdout += chunk;
			while (stdout.includes("\n")) {
				const newline = stdout.indexOf("\n");
				const line = stdout.slice(0, newline).replace(/\r$/, "");
				stdout = stdout.slice(newline + 1);
				if (line) events.push(JSON.parse(line));
			}
		});
		const send = (value) => child.stdin.write(`${JSON.stringify(value)}\n`);
		const staleError = () => events.find((event) =>
			event.type === "extension_error" && String(event.error).includes("This extension ctx is stale"));
		const assertHealthy = (stage) => {
			if (child.exitCode !== null) throw new Error(`Pi exited during ${stage}: ${child.exitCode}\n${stderr}`);
			if (staleError() || stderr.includes("This extension ctx is stale")) {
				throw new Error(`stale ctx during ${stage}\n${stderr}`);
			}
			if (stderr.includes("uncaughtException")) throw new Error(`uncaught exception during ${stage}\n${stderr}`);
		};
		const waitFor = async (predicate, message) => {
			const deadline = Date.now() + 4000;
			while (Date.now() < deadline) {
				const found = events.find(predicate);
				if (found) return found;
				if (child.exitCode !== null) break;
				await new Promise((resolve) => setTimeout(resolve, 10));
			}
			throw new Error(`${message}\nevents: ${JSON.stringify(events)}\nstderr: ${stderr}`);
		};

		send({ id: "initial", type: "prompt", message: "/test-release" });
		await waitFor((event) => event.id === "initial" && event.success === true, "initial request release failed");
		await waitFor((event) => event.method === "setStatus" && event.statusText?.startsWith("Codex：75%/"), "initial refresh did not publish status");
		events.length = 0;
		send({ id: "reload", type: "prompt", message: "/test-reload" });
		await waitFor((event) => event.id === "reload" && event.success === true, "reload command failed");
		assertHealthy("reload");

		events.length = 0;
		send({ id: "invalidate-reload", type: "prompt", message: "/test-invalidate-reload" });
		await waitFor((event) => event.id === "invalidate-reload" && event.success === true, "runtime invalidation reload failed");
		assertHealthy("runtime invalidation reload");
		const requestsAfterInvalidation = (await readFile(requestLog, "utf8")).trim().split("\n").length;
		await new Promise((resolve) => setTimeout(resolve, 1100));
		const requestsAfterInterval = (await readFile(requestLog, "utf8")).trim().split("\n").length;
		if (requestsAfterInterval !== requestsAfterInvalidation) {
			throw new Error(`stale timer made another request: ${requestsAfterInvalidation} -> ${requestsAfterInterval}`);
		}

		events.length = 0;
		send({ id: "new", type: "new_session" });
		await waitFor((event) => event.id === "new" && event.success === true, "new session failed");
		send({ id: "release-old", type: "prompt", message: "/test-release-old" });
		await waitFor((event) => event.id === "release-old" && event.success === true, "old-session request release failed");
		assertHealthy("new session");

		events.length = 0;
		send({ id: "release-current", type: "prompt", message: "/test-release" });
		await waitFor((event) => event.id === "release-current" && event.success === true, "current request release failed");
		await waitFor((event) => event.method === "setStatus" && event.statusText?.startsWith("Codex：75%/"), "current session did not publish usage");

		events.length = 0;
		await new Promise((resolve) => setTimeout(resolve, 1100));
		send({ id: "periodic", type: "prompt", message: "/test-release" });
		await waitFor((event) => event.id === "periodic" && event.success === true, "periodic request release failed");
		await waitFor((event) => event.method === "setStatus" && event.statusText?.startsWith("Codex：75%/"), "periodic refresh did not publish usage");
		assertHealthy("periodic refresh");

		events.length = 0;
		send({ id: "shutdown", type: "prompt", message: "/test-shutdown" });
		await waitFor((event) => event.method === "setStatus" && event.statusText === undefined, "shutdown did not clear status");
		await waitFor((event) => event.id === "shutdown" && event.success === true, "shutdown command failed");
		const exitCode = child.exitCode ?? await Promise.race([
			new Promise((resolve) => child.once("exit", resolve)),
			new Promise((_, reject) => setTimeout(() => reject(new Error("Pi did not shut down gracefully")), 4000)),
		]);
		if (exitCode !== 0) throw new Error(`unexpected Pi exit code: ${exitCode}\n${stderr}`);
		if (staleError() || stderr.includes("This extension ctx is stale") || stderr.includes("uncaughtException")) {
			throw new Error(`lifecycle error during shutdown\n${stderr}`);
		}
	} finally {
		if (child?.exitCode === null) {
			child.kill();
			await new Promise((resolve) => child.once("exit", resolve));
		}
		await rm(root, { recursive: true, force: true, maxRetries: 3, retryDelay: 20 });
	}
}

async function runRealReloadRegression() {
	const root = await mkdtemp(join(tmpdir(), "pi-codex-usage-status-reload-"));
	let child;
	try {
		const settingsDir = join(root, ".pi", "agent");
		await mkdir(settingsDir, { recursive: true });
		const plugin = join(process.cwd(), "plugins", "pi-codex-usage-status");
		await writeFile(join(settingsDir, "settings.json"), JSON.stringify({
			packages: [plugin],
			codexUsageStatus: { refreshSeconds: 1 },
		}));
		const helper = join(root, "lifecycle-helper.ts");
		const marker = join(root, "reloaded.txt");
		const runnerModule = join(piRoot, "dist", "core", "extensions", "runner.js").replaceAll("\\", "/");
		await writeFile(helper, helperSource.replace("__PI_EXTENSION_RUNNER__", runnerModule));
		const cli = join(piRoot, "dist", "cli.js");
		const piArgs = [process.execPath, cli,
			"--no-session", "--offline", "--approve", "--no-skills", "--no-prompt-templates",
			"--no-context-files", "-e", helper,
		];
		const script = "C:/msys64/usr/bin/script.exe";
		const quote = (value) => `'${value.replaceAll("\\", "/").replaceAll("'", "'\\''")}'`;
		const launcher = existsSync(script) ? script : process.execPath;
		const launcherArgs = existsSync(script)
			? ["-q", "-e", "-c", piArgs.map(quote).join(" "), "/dev/null"]
			: piArgs.slice(1);
		child = spawn(launcher, launcherArgs, {
			cwd: process.cwd(),
			env: { ...process.env, HOME: root, USERPROFILE: root, PI_LIFECYCLE_MARKER: marker },
			stdio: ["pipe", "pipe", "pipe"],
		});
		let stdout = "";
		let stderr = "";
		child.stdout.setEncoding("utf8");
		child.stdout.on("data", (chunk) => {
			stdout += chunk;
			if (chunk.includes("\x1b[6n")) child.stdin.write("\x1b[1;1R");
		});
		child.stderr.setEncoding("utf8");
		child.stderr.on("data", (chunk) => { stderr += chunk; });
		const startupDeadline = Date.now() + 4000;
		while (!stdout.includes("lifecycle-helper.ts") && child.exitCode === null && Date.now() < startupDeadline) {
			await new Promise((resolve) => setTimeout(resolve, 10));
		}
		if (!stdout.includes("lifecycle-helper.ts")) throw new Error(`Pi TUI did not start\nstdout: ${stdout}\nstderr: ${stderr}`);
		child.stdin.write("/reload\r");
		const deadline = Date.now() + 6000;
		while (!existsSync(marker) && child.exitCode === null && Date.now() < deadline) {
			await new Promise((resolve) => setTimeout(resolve, 10));
		}
		if (child.exitCode !== null || stderr.includes("This extension ctx is stale")) {
			throw new Error(`stale ctx after real reload\n${stderr}`);
		}
		if (!existsSync(marker)) throw new Error(`real reload did not restore status\nstdout: ${stdout}\nstderr: ${stderr}`);
		await new Promise((resolve) => setTimeout(resolve, 100));
		child.stdin.write("/test-shutdown\r");
		const exitCode = child.exitCode ?? await Promise.race([
			new Promise((resolve) => child.once("exit", resolve)),
			new Promise((_, reject) => setTimeout(() => reject(new Error("Pi did not shut down after real reload")), 4000)),
		]);
		if (exitCode !== 0) throw new Error(`unexpected Pi exit after real reload: ${exitCode}\n${stderr}`);
	} finally {
		if (child?.exitCode === null) {
			if (process.platform === "win32") {
				spawnSync("taskkill.exe", ["/PID", String(child.pid), "/T", "/F"]);
			} else {
				child.kill();
			}
			await new Promise((resolve) => child.once("exit", resolve));
		}
		await rm(root, { recursive: true, force: true, maxRetries: 3, retryDelay: 20 });
	}
}

if (process.argv.includes("--faulty")) {
	await runLifecycleRegression({ faulty: true });
} else {
	const red = spawnSync(process.execPath, [process.argv[1], "--faulty"], {
		cwd: process.cwd(),
		encoding: "utf8",
		timeout: 15_000,
	});
	if (red.status === 0) throw new Error("faulty lifecycle implementation did not reproduce stale ctx");
	if (!`${red.stdout}\n${red.stderr}`.includes("This extension ctx is stale")) {
		throw new Error(`faulty lifecycle failed for the wrong reason\n${red.stdout}\n${red.stderr}`);
	}
	await runLifecycleRegression();
	await runRealReloadRegression();
}
