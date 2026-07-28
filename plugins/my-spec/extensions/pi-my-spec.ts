import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const commands = {
	"my-spec": "my-spec",
	"my-spec-add": "my-spec-add",
	"my-spec-review": "my-spec-review",
	"my-spec-audit": "my-spec-audit",
} as const;

export default function (pi: ExtensionAPI): void {
	for (const [command, skill] of Object.entries(commands)) {
		pi.registerCommand(command, {
			description: `Run the ${skill} skill`,
			handler: async (args, ctx) => {
				if (!ctx.isIdle()) {
					ctx.ui.notify(`/${command} requires an idle agent`, "warning");
					return;
				}
				pi.sendUserMessage(`Use the ${skill} skill.${args.trim() ? `\n\nUser request: ${args.trim()}` : ""}`);
			},
		});
	}
}
