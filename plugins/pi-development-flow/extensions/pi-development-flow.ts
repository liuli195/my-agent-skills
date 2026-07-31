import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

import { registerWorktreeDispatch } from "./dispatch.ts";

export default function register(pi: ExtensionAPI) {
  registerWorktreeDispatch(pi, Type.Object({
    worktree_path: Type.String({ description: "Absolute path to the existing target worktree" }),
    expected_branch: Type.String({ description: "Exact branch expected in the target worktree" }),
    prompt: Type.String({ description: "Self-contained instructions for exactly one published ticket" }),
  }));
}
