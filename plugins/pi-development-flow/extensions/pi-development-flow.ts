import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

import { registerWorktreeDispatch } from "./dispatch.ts";

export default function register(pi: ExtensionAPI) {
  registerWorktreeDispatch(pi, Type.Object({
    worktree_path: Type.String({ description: "Absolute path to the existing target worktree" }),
    expected_branch: Type.String({ description: "Exact branch expected in the target worktree" }),
    ticket_path: Type.String({ description: "Absolute path to exactly one ready-for-agent ticket in the target worktree" }),
  }));
}
