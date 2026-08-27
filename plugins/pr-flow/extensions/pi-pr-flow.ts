import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

function scriptPath(): string {
	return fileURLToPath(new URL("../skills/pr-flow/scripts/pr_flow.py", import.meta.url));
}

function runPrFlow(args: string[], cwd: string): Promise<{ exitCode: number; stdout: string; stderr: string }> {
	return new Promise((resolve, reject) => {
		const child = spawn("python", [scriptPath(), ...args], { cwd, stdio: ["ignore", "pipe", "pipe"] });
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
			resolve({ exitCode: code ?? 1, stdout, stderr });
		});
	});
}

const prFlowTool = defineTool({
	name: "pr_flow",
	label: "PR Flow",
	description: "Run the packaged PR Flow script in the current project.",
	parameters: Type.Object({
		argv: Type.Array(Type.String({ description: "One PR Flow command or argument." })),
	}),

	async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
		const result = await runPrFlow(params.argv, ctx.cwd);
		const output = [result.stdout.trim(), result.stderr.trim(), `exitCode: ${result.exitCode}`].filter(Boolean).join("\n");
		return {
			content: [{ type: "text", text: output }],
			details: result,
		};
	},
});

export default function (pi: ExtensionAPI): void {
	pi.registerTool(prFlowTool);
}
