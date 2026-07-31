# Delivery（交付）

## Formal specification（正式规格）

After the bounded overall review and its fixes pass proportional verification, run `my-spec-add` against the verified external behavior. Follow its conflict decisions, complete diff, validation, and final user-confirmation gates. Formal specifications are not part of the earlier code-review scope. Run the relevant fast validation after applying the approved specification difference.

## PR delivery（拉取请求交付）

Present the final diff, verification evidence, review result, and known risks. Wait for explicit delivery authorization.

- Use `pr-flow-tweak` only for a non-bug lightweight change that meets its contract.
- Use `pr-flow-complete` for standard and high-risk changes.
- Treat every PR Flow stop state as a resumable pause rather than completion.
- When a merge or rebase conflict exists, use `resolving-merge-conflicts`. Resolve from the spec, tickets, commits, and tests; rerun affected checks. Ask the user when the sources permit incompatible observable behaviors rather than choosing a new behavior.

## Cleanup and completion（清理与完成）

PR Flow owns merged head-branch cleanup and final worktree removal. Use only non-forced cleanup. Preserve dirty, unmerged, failed, or unknown content and report the blocker.

After merge, synchronize the local base branch.

By default, Development Flow excludes local installation, client synchronization, marketplace refresh, and Release Flow（发布流程）. The flow MUST NOT proactively list or ask about these actions. Perform one only when the user explicitly requests that exact action; a general instruction such as “continue the cleanup” does not authorize installation, synchronization, refresh, or release work.

Use the requested action's formal entry and verify its result. Never infer authorization for a required release when a requested synchronization depends on unpublished content; report that requested action separately. Unrequested or unavailable local delivery MUST NOT block completion or become a default follow-up task.

Declare the Development Flow（开发流程） complete only when:

- every acceptance criterion and required check passes;
- the formal specification is approved and valid;
- the PR is actually merged;
- the local base matches the current remote base;
- safely removable ticket, feature, and integration branches and worktrees are gone;
- no temporary artifact from the flow remains.
