import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

import { registerDirectAgentGuard, registerWorktreeDispatch } from "./dispatch.ts";

export default function register(pi: ExtensionAPI) {
  registerDirectAgentGuard(pi);
  registerWorktreeDispatch(pi, Type.Object({
    worktree_path: Type.String({ description: "Absolute path to the existing target worktree" }),
    expected_branch: Type.String({ description: "Exact branch expected in the target worktree" }),
    ticket_path: Type.String({ description: "Absolute path to exactly one published ticket in the target worktree" }),
  }));
}
