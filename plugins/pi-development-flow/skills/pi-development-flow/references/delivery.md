# Delivery（交付）

## MUST — Dependencies（依赖）

Before presenting Gate 3, Gate 4, or Completion Check output, read [output-template](output-template.md) and use its exact titles, four blocks, and order.

Before preparing or applying the formal specification difference, read `my-spec-add`（新增自有规格）. Before PR（拉取请求） delivery, read `pr-flow-tweak`（小改流程） only for a qualifying non-bug Lightweight（轻量） change; read `pr-flow-complete`（完整拉取请求流程） for Standard（标准） and High risk（高风险） changes. If a merge or rebase conflict exists, read `resolving-merge-conflicts`（解决合并冲突） before resolving it.

If an exact required Skill（技能） is missing, unreadable, fails to load, or is replaced by an informal entry, stop and report the preserved artifacts and the current named gate as the resume point. Do not bypass a formal entry with ordinary Git（版本管理） commands.

## MUST — Gate（门禁）

### Gate 3 — Enter Delivery（进入交付）

#### Usage Condition（使用条件）

Use this gate after implementation, proportional verification, fast verification, and the bounded overall review are complete, and when `my-spec-add`（新增自有规格） has generated and validated the complete formal MySpec（自有规格） preview difference and is waiting for its final confirmation.

#### Previous Gate（上一依赖门禁）

Gate 2 — Enter Implementation（进入实施）. Its authorized plan must be complete, every ticket integrated, behavior evidence recorded, required checks passing, and the bounded overall review free of unresolved blockers.

#### Checks（检查清单）

Confirm that:

- Gate 2 — Enter Implementation passed before any implementation change;
- every acceptance criterion and ticket is complete;
- proportional and fast verification pass;
- the bounded overall review has no unresolved blocker;
- `my-spec-add` has presented the complete preview difference and reached its final confirmation;
- no PR（拉取请求） delivery action has started.

If an implementation check fails, preserve the artifacts and return to Implementation. If `my-spec-add` stops or requires a decision, preserve its artifacts and continue from that Skill（技能）'s reported recovery point.

#### Confirmation Output（待用户确认内容清单）

Gate 3's Development Flow summary uses [output-template](output-template.md), while the detailed final confirmation required by `my-spec-add`（新增自有规格） remains that Skill（技能）'s exact output. Cite it without rewriting or wrapping it, and do not add a second confirmation, exception, or recovery procedure. Implementation authorization or passing checks is not confirmation of Gate 3 — Enter Delivery.

Without that confirmation, do not apply the formal specification difference; report the `my-spec-add` recovery point and Gate 3 — Enter Delivery as the resume point.

#### Next Gate（下一步门禁）

Gate 4 — Authorize PR Delivery（授权 PR 交付）. Gate 3 passes only after `my-spec-add`（新增自有规格） atomically applies and validates the approved formal specification difference successfully.

### Gate 4 — Authorize PR Delivery（授权 PR 交付）

#### Usage Condition（使用条件）

Use this gate after the formal specification is approved and valid, and before push, PR creation or update, merge, or final cleanup.

#### Previous Gate（上一依赖门禁）

Gate 3 — Enter Delivery（进入交付）. Its approved formal specification difference must be applied and valid.

#### Checks（检查清单）

Confirm that:

- Gate 3 — Enter Delivery passed;
- the formal specification is valid;
- the final diff, verification evidence, review result, and known risks are complete;
- the exact push, PR creation or update, merge, and cleanup actions are identified;
- none of those delivery actions occurred without this authorization.

If any check fails, preserve the artifacts and stop at Gate 4 — Authorize PR Delivery.

#### Confirmation Output（待用户确认内容清单）

Present the final diff, verification evidence, review result, known risks, and the exact push, PR creation or update, merge, and final cleanup actions. Explicitly ask whether the user authorizes those PR delivery actions. “Continue”, implementation authorization, or formal specification approval is not authorization of Gate 4 — Authorize PR Delivery.

Without explicit confirmation, do not perform any listed delivery action and report Gate 4 — Authorize PR Delivery as the resume point.

#### Next Gate（下一步门禁）

Completion Check — 完成检查. Gate 4 only authorizes delivery; it does not prove final completion.

### Completion Check — 完成检查

#### Usage Condition（使用条件）

Use this check after the authorized PR delivery has finished and the PR is merged, the local base is synchronized, and the selected cleanup action has returned a result.

#### Previous Gate（上一依赖门禁）

Gate 4 — Authorize PR Delivery（授权 PR 交付）. Its authorized delivery actions must be complete or have a preserved stop state.

#### Checks（检查清单）

Confirm that:

- every acceptance criterion and required check passes;
- the formal specification is approved and valid;
- the PR is actually merged;
- the local base matches the current remote base;
- safely removable branches and worktrees are gone;
- no temporary artifact remains;
- unrequested local installation, client synchronization, marketplace refresh, and release work are not completion blockers.

If Git（版本管理） registration and branch cleanup are complete but a physical worktree directory（实体工作树目录） remains as Cleanup Residue（清理残留）, report `未完成`, the exact path, the cleanup reason, and citation evidence. Do not treat that state as `最终完成`.

#### Confirmation Output（待用户确认内容清单）

Use [output-template](output-template.md) exactly. If cleanup residue exists, ask whether the user grants explicit authorization for force cleanup of that exact residue. Do not force-delete automatically. A refusal preserves the residue and reports the recovery position; an authorization permits only the separately scoped cleanup action, after which this check runs again. This is not a fifth formal authorization gate.

#### Next Gate（下一步门禁）

There is no next gate. Report `最终完成` only after all checks pass; otherwise preserve the evidence and report the recovery position.

## Formal specification（正式规格）

After the bounded overall review and its fixes pass proportional verification, run `my-spec-add`（新增自有规格） against the verified external behavior. Let that Skill（技能） own its conflict decisions, complete difference, validation, final confirmation, application, and recovery. Its final confirmation is Gate 3 — Enter Delivery（进入交付）. Formal specifications are not part of the earlier code-review scope. Run the relevant fast validation after the approved specification difference is applied and validated.

## PR delivery（拉取请求交付）

Complete Gate 4 — Authorize PR Delivery（授权 PR 交付） before calling the selected PR Flow（拉取请求流程） entry.

- Use `pr-flow-tweak` only for a non-bug lightweight change that meets its contract.
- Use `pr-flow-complete` for standard and high-risk changes.
- Treat every PR Flow stop state as a resumable pause rather than completion.
- When a merge or rebase conflict exists, use `resolving-merge-conflicts`. Resolve from the spec, tickets, commits, and tests; rerun affected checks. Ask the user when the sources permit incompatible observable behaviors rather than choosing a new behavior.

## Cleanup and completion（清理与完成）

PR Flow owns merged head-branch cleanup and final worktree removal. Use only non-forced cleanup. Preserve dirty, unmerged, failed, or unknown content and report the blocker.

After merge, synchronize the local base branch.

By default, Development Flow excludes local installation, client synchronization, marketplace refresh, and Release Flow（发布流程）. The flow MUST NOT proactively list or ask about these actions. Perform one only when the user explicitly requests that exact action; a general instruction such as “continue the cleanup” does not authorize installation, synchronization, refresh, or release work.

Use the requested action's formal entry and verify its result. Never infer authorization for a required release when a requested synchronization depends on unpublished content; report that requested action separately. Unrequested or unavailable local delivery MUST NOT block completion or become a default follow-up task.

Completion Check（完成检查） owns the final completion conclusion. Do not declare the Development Flow（开发流程） complete from a successful Gate 4 authorization or a partial cleanup result.
