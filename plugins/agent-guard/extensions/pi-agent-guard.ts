import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

type RouterResult = {
	status?: string;
	reason?: string;
	suggestion?: string;
};

function routerPath(): string {
	return fileURLToPath(new URL("../scripts/hook_router.py", import.meta.url));
}

function runRouter(event: "SessionStart" | "PreToolUse", payload: Record<string, unknown>, cwd: string): Promise<RouterResult> {
	return new Promise((resolve, reject) => {
		const child = spawn("python", [routerPath(), "--source", "pi", "--event", event, "--project", cwd], {
			cwd,
			stdio: ["pipe", "pipe", "pipe"],
		});
		let stdout = "";
		let stderr = "";

		child.stdout.on("data", (chunk) => {
			stdout += chunk;
		});
		child.stderr.on("data", (chunk) => {
			stderr += chunk;
		});
		child.on("error", reject);
		child.on("close", (code) => {
			if (code !== 0) {
				reject(new Error(stderr.trim() || `router exited with code ${code}`));
				return;
			}
			try {
				const line = stdout.trim().split(/\r?\n/).at(-1);
				if (!line) throw new Error(stderr || "router returned no JSON output");
				resolve(JSON.parse(line) as RouterResult);
			} catch (error) {
				reject(error);
			}
		});
		child.stdin.end(JSON.stringify(payload));
	});
}

function blockReason(result: RouterResult): string {
	return [result.reason || "agent_guard_blocked", result.suggestion].filter(Boolean).join("\n");
}

export default function (pi: ExtensionAPI): void {
	pi.on("session_start", async (_event, ctx) => {
		const sessionId = ctx.sessionManager.getSessionId();
		process.env.AGENT_GUARD_SOURCE = "pi";
		process.env.AGENT_GUARD_SESSION_ID = sessionId;
		try {
			await runRouter("SessionStart", { session_id: sessionId, cwd: ctx.cwd }, ctx.cwd);
		} catch (error) {
			ctx.ui.notify(`Agent Guard session observation failed: ${String(error)}`, "error");
		}
	});

	pi.on("tool_call", async (event, ctx) => {
		let result: RouterResult;
		try {
			result = await runRouter(
				"PreToolUse",
				{
					session_id: ctx.sessionManager.getSessionId(),
					cwd: ctx.cwd,
					tool_name: event.toolName,
					tool_input: event.input,
				},
				ctx.cwd,
			);
		} catch (error) {
			return { block: true, reason: `agent_guard_router_failed: ${String(error)}` };
		}

		if (result.status === "allow") return undefined;
		return { block: true, reason: blockReason(result) };
	});
}
