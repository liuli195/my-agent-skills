import { randomUUID } from "node:crypto";
import { realpath } from "node:fs/promises";
import { dirname, isAbsolute, resolve } from "node:path";

import {
  isToolCallEventType,
  type ExtensionAPI,
} from "@earendil-works/pi-coding-agent";

type RpcReply<T> =
  | { success: true; data?: T }
  | { success: false; error: string };

type Completion = {
  id: string;
  status: string;
  result?: string;
  error?: string;
};

type AgentInput = Record<string, unknown>;

const DIRECT_READ_ONLY_ROLES = new Set(["explorer", "reviewer", "architect"]);

export function registerDirectAgentGuard(pi: ExtensionAPI) {
  pi.on("tool_call", (event) => {
    if (!isToolCallEventType<"Agent", AgentInput>("Agent", event)) return;

    const role = typeof event.input.subagent_type === "string"
      ? event.input.subagent_type.toLowerCase()
      : "";
    const hasResume = Object.prototype.hasOwnProperty.call(event.input, "resume");
    if (!hasResume && DIRECT_READ_ONLY_ROLES.has(role)) return;

    return {
      block: true,
      reason: "Direct Agent calls for writable, unknown, or resumed subagents are blocked. Use dispatch_implementer_in_worktree.",
    };
  });
}

function rpc<T>(
  pi: ExtensionAPI,
  channel: string,
  payload: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<T> {
  return new Promise((resolveReply, reject) => {
    const requestId = randomUUID();
    const replyChannel = `${channel}:reply:${requestId}`;
    const timer = setTimeout(() => finish(new Error(`${channel} timed out`)), 5_000);
    const unsubscribe = pi.events.on(replyChannel, (raw: unknown) => {
      const reply = raw as RpcReply<T>;
      finish(reply.success ? undefined : new Error(reply.error), reply.data);
    });
    const onAbort = () => finish(new Error("Subagent dispatch cancelled"));

    function finish(error?: Error, value?: T) {
      clearTimeout(timer);
      unsubscribe();
      signal?.removeEventListener("abort", onAbort);
      if (error) reject(error);
      else resolveReply(value as T);
    }

    signal?.addEventListener("abort", onAbort, { once: true });
    pi.events.emit(channel, { ...payload, requestId });
  });
}

function waitForCompletion(
  pi: ExtensionAPI,
  agentId: string,
  signal?: AbortSignal,
): Promise<Completion> {
  return new Promise((resolveCompletion, reject) => {
    const offCompleted = pi.events.on("subagents:completed", onCompleted);
    const offFailed = pi.events.on("subagents:failed", onFailed);
    const onAbort = () => fail(new Error("Subagent dispatch cancelled"), true);

    function cleanup() {
      offCompleted();
      offFailed();
      signal?.removeEventListener("abort", onAbort);
    }

    function fail(error: Error, stop = false) {
      cleanup();
      if (stop) void rpc(pi, "subagents:rpc:stop", { agentId }).catch(() => {});
      reject(error);
    }

    function onCompleted(raw: unknown) {
      const completion = raw as Completion;
      if (completion.id !== agentId) return;
      cleanup();
      resolveCompletion(completion);
    }

    function onFailed(raw: unknown) {
      const completion = raw as Completion;
      if (completion.id !== agentId) return;
      fail(new Error(completion.error || `Implementer ended with ${completion.status}`));
    }

    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

async function git(pi: ExtensionAPI, cwd: string, args: string[], signal?: AbortSignal) {
  const result = await pi.exec("git", ["-C", cwd, ...args], { signal, timeout: 5_000 });
  if (result.code !== 0) {
    throw new Error(result.stderr.trim() || `git ${args.join(" ")} failed`);
  }
  return result.stdout.trim();
}

async function verifyWorktree(
  pi: ExtensionAPI,
  path: string,
  expectedBranch: string,
  signal?: AbortSignal,
) {
  if (!isAbsolute(path)) throw new Error("worktree_path must be absolute");

  const worktree = await realpath(path);
  const topLevel = await realpath(await git(pi, worktree, ["rev-parse", "--show-toplevel"], signal));
  if (topLevel.toLowerCase() !== worktree.toLowerCase()) {
    throw new Error("worktree_path must be the worktree root");
  }

  const listed = await git(pi, worktree, ["worktree", "list", "--porcelain"], signal);
  const registered = listed
    .split(/\r?\n/)
    .filter((line) => line.startsWith("worktree "))
    .map((line) => resolve(line.slice("worktree ".length)).toLowerCase());
  if (!registered.includes(worktree.toLowerCase())) {
    throw new Error("worktree_path is not a registered Git worktree");
  }

  const commonDir = await realpath(
    await git(pi, worktree, ["rev-parse", "--path-format=absolute", "--git-common-dir"], signal),
  );
  if (dirname(commonDir).toLowerCase() === worktree.toLowerCase()) {
    throw new Error("Refusing to dispatch a writable subagent in the primary worktree");
  }

  const branch = await git(pi, worktree, ["branch", "--show-current"], signal);
  if (branch !== expectedBranch) {
    throw new Error(`Expected branch "${expectedBranch}", found "${branch || "detached HEAD"}"`);
  }

  return { worktree, branch };
}

export function registerWorktreeDispatch(
  pi: ExtensionAPI,
  parameters: object,
) {
  pi.registerTool({
    name: "dispatch_implementer_in_worktree",
    label: "Dispatch Implementer in Worktree",
    description: "Dispatch one Implementer with caller-provided prompt and description in an existing non-primary Git worktree.",
    promptSnippet: "Dispatch an Implementer with caller-provided instructions in a bound worktree",
    promptGuidelines: [
      "Provide a self-contained prompt and description; the tool preserves both values unchanged.",
    ],
    parameters: parameters as never,
    async execute(_toolCallId, params, signal) {
      const target = await verifyWorktree(
        pi,
        params.worktree_path,
        params.expected_branch,
        signal,
      );
      const ping = await rpc<{ version: number }>(pi, "subagents:rpc:ping", {}, signal);
      if (ping.version !== 2) {
        throw new Error(`Unsupported pi-subagents RPC protocol ${ping.version}`);
      }

      const spawned = await rpc<{ id: string }>(
        pi,
        "subagents:rpc:spawn",
        {
          type: "Implementer",
          prompt: params.prompt,
          options: { cwd: target.worktree, description: params.description },
        },
        signal,
      );
      const completion = await waitForCompletion(pi, spawned.id, signal);

      return {
        content: [{ type: "text", text: completion.result || "Implementer completed without a text result." }],
        details: {
          agentId: spawned.id,
          worktree: target.worktree,
          branch: target.branch,
          status: completion.status,
          result: completion.result,
        },
      };
    },
  });
}
