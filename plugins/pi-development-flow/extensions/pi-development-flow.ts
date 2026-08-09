import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

import { registerDirectAgentGuard, registerWorktreeDispatch } from "./dispatch.ts";

export default function register(pi: ExtensionAPI) {
  registerDirectAgentGuard(pi);
  registerWorktreeDispatch(pi, Type.Object({
    prompt: Type.String({ description: "Prompt passed to Implementer unchanged" }),
    description: Type.String({ description: "Description passed to Implementer unchanged" }),
    worktree_path: Type.String({ description: "Absolute path to the verified existing non-primary Git worktree" }),
    expected_branch: Type.String({ description: "Exact branch expected in the verified worktree" }),
  }));
}
