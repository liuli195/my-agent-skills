# Implementation（实施）

## Shape the work（组织工作）

Use one feature branch and one `.worktrees/<change>/` worktree when all tickets are sequential. Create an integration branch only when at least two unblocked tickets can safely run in parallel. In that case, give each parallel ticket one ASCII-named branch, one `.worktrees/<change>-<ticket>/` worktree, and one Implementer（实施者）. Run the repository worktree initializer in every new worktree.

The main Agent（代理） decides whether delegation helps and how many parallel tickets the repository and machine can support. Before the first delegation, apply `pi-subagent-policy`; a policy mismatch stops delegation. Use Explorer（探索者） for independent investigation, Implementer for confirmed changes, and Reviewer（审查者） for review. Verify every delegated result before accepting it.

## Implement tickets（实施票据）

The main Agent MAY implement sequential tickets directly in the feature worktree; sequential work does not require delegation. Whether work is direct or delegated, the current ticket must be implemented, verified, and accepted before the next sequential ticket begins.

When the main Agent delegates, each Implementer invocation MUST bind exactly one published ticket and MUST NOT combine multiple published tickets. If a ticket cannot be implemented and verified independently, return to ticket design instead of widening the invocation. Sequential delegated tickets may reuse the feature worktree, but each gets a separate invocation after the previous ticket is accepted.

For writable delegation into an existing feature or ticket worktree, use `dispatch_implementer_in_worktree` with the absolute worktree path, expected branch, and exactly one published `ready-for-agent` ticket path from that worktree. The tool constructs the Implementer prompt; it does not accept a free-form multi-ticket prompt. The flow MUST NOT rely on a prompt to change directories. If tool-enforced binding is unavailable or validation fails, stop before delegation and provide a handoff from the target worktree.

- Apply `tdd` to feature, bug, and integration behavior: one confirmed public seam, one failing check, the minimum passing implementation, then the next slice.
- Documentation, formatting, and behavior-neutral configuration use the smallest relevant check without a ceremonial red/green loop.
- Each delegated Implementer commits focused, verified work on its assigned branch. The main Agent verifies the diff and evidence before integration.
- Integrate only tickets whose blockers are complete. Conflicting core-file work runs sequentially rather than pretending to be parallel.
- After integration passes its checks, the main Agent non-forcibly removes the integrated ticket worktree and branch without another user prompt. Preserve anything unmerged, dirty, failed, or of unknown origin.

Record only behavior evidence in the ticket: checked acceptance criteria, red/green result, user-entry smoke result, required review conclusion, and unresolved risk. Derive commits, branches, worktrees, and PR state from Git（版本管理） rather than copying them into the ticket.

## Verify proportionally（按风险验证）

| Point | Verification |
| --- | --- |
| Ticket | The smallest check at the agreed public seam that proves the ticket's observable result |
| Integration | Build and Verify fast mode; rerun affected smoke only when conflict resolution or integration changed behavior |
| Lightweight final | Relevant check plus a real target-behavior smoke when a user path changed |
| Standard final | One real user-entry or published-form smoke through the changed main success path, plus fast verification |
| High-risk final | Main success-path smoke plus affected security, data-integrity, failure, migration, or recovery paths, plus fast verification |
| PR CI | The repository's full automated checks |

An external client or system adapter receives its own smallest real smoke immediately after completion. Repository rules, the spec, and explicit user requirements may demand stronger verification. Internal unit tests do not replace a required user-entry smoke.

## Review within the diff（在差异内审查）

Use `code-review` for its fixed-point, Standards（规范）, and Spec（规格） review method. `pi-subagent-policy` controls role selection, so both axes use Reviewer rather than a general-purpose role.

Add only these orchestration constraints:

1. Trigger ticket review only for public contracts, shared behavior that blocks later tickets, security, data, migration, release, machine state, hard-to-reproduce shared bugs, high integration conflict, or explicit user request.
2. Read direct callers and contracts only as context needed to judge the changed diff; context is not extra review scope.
3. Keep small patches within their actual diff and necessary context rather than expanding through an unchanged dependency tree.
4. After fixes, review only the fix diff and affected behavior. One full review and one targeted follow-up is the default; recurring basic failures return to requirements and tickets.
5. In the final review, focus on cross-ticket composition, missing acceptance, scope growth, integration edits, and post-ticket-review changes. Previously reviewed local code that did not change gets no second deep style review.

Documented rule violations, missing or wrong specified behavior, scope growth, security, data integrity, and missing main-path acceptance block integration. Treat code smells as judgement calls and fix them only when they create present maintenance risk. If a single ticket is the whole change, one final review satisfies both critical-ticket and overall review gates.

Completion requires all tickets integrated, final proportional verification passing, and the bounded overall review free of unresolved blockers.
