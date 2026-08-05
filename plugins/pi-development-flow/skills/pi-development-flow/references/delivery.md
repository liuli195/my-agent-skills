# Delivery（交付）

## MUST — Dependencies（依赖）

Before presenting Gate 3 or Completion Check output, read [output-template](output-template.md) and use its exact titles, four blocks, and order.

Before preparing or applying the formal specification difference, read `my-spec-add`（新增自有规格）. Before PR（拉取请求） delivery, read `pr-flow-tweak`（小改流程） only for a qualifying non-bug Lightweight（轻量） change; read `pr-flow-complete`（完整拉取请求流程） for Standard（标准） and High risk（高风险） changes. If a merge or rebase conflict exists, read `resolving-merge-conflicts`（解决合并冲突） before resolving it.

If an exact required Skill（技能） is missing, unreadable, fails to load, or is replaced by an informal entry, stop and report the preserved artifacts and the current named gate as the resume point. Do not bypass a formal entry with ordinary Git（版本管理） commands.

## MUST — Gate（门禁）

### Gate 3 — Specification Archival and Delivery（规格存档并交付）

#### Usage Condition（使用条件）

Use this gate after implementation, proportional verification, fast verification, and the bounded overall review are complete, and when the complete formal specification preview difference and exact delivery actions are ready to be presented in Gate 3's own four-block result for one Gate 3 confirmation, before any specification application or delivery action.

#### Previous Gate（上一依赖门禁）

Gate 2 — Implementation and Verification（实施和验证）. Its authorized plan must be complete, every ticket integrated, behavior evidence recorded, required checks passing, and the bounded overall review free of unresolved blockers.

#### Checks（检查清单）

Confirm that:

- Gate 2 — Implementation and Verification was explicitly authorized before implementation started, and its completion conditions are now satisfied;
- every acceptance criterion and ticket is complete;
- proportional and fast verification pass;
- the bounded overall review has no unresolved blocker;
- the complete formal specification preview difference is ready;
- no specification application or delivery action has started;
- the exact delivery actions and expected results are identified.

If an implementation check fails, preserve the artifacts and return to Implementation and Verification. If formal specification preparation stops or requires a decision, preserve its artifacts and continue from its reported recovery point.

#### Confirmation Output（待用户确认内容清单）

The Gate 3 result uses [output-template](output-template.md) and presents a concise formal specification content summary, requirement-change counts (additions and removals, plus modifications or renames when present), verification evidence, known risks, exact delivery actions, and expected results within Gate 3's own four blocks. It MUST NOT expand the complete formal specification difference; preserve that difference in the MySpec preview and provide it through citations. Gate 3's result MUST NOT be combined with another gate or with Completion Check.

Gate 3 requests exactly one confirmation. That confirmation, requested in the Gate 3 result, authorizes both the formal specification application and the exact delivery actions. After that confirmation, recheck the specification state, apply and validate the approved specification difference, and automatically execute the authorized delivery without asking for a second confirmation.

Gate 3 passes only after the approved formal specification difference is applied and validated and the authorized delivery finishes successfully. A delivery stop state leaves Gate 3 incomplete and is not final completion.

#### Next Gate（下一步门禁）

Completion Check — 完成检查. Gate 3 includes the single confirmation, formal specification application, and delivery; it does not prove final completion.

### Completion Check — 完成检查

#### Usage Condition（使用条件）

Use this check after the authorized PR delivery has finished and the PR is merged, the local base is synchronized, and the selected cleanup action has returned a result.

#### Previous Gate（上一依赖门禁）

Gate 3 — Specification Archival and Delivery（规格存档并交付）. Its approved specification must be valid and its authorized delivery must have finished successfully. A PR Flow stop state remains a Gate 3 recovery state and does not enter Completion Check.

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

Use [output-template](output-template.md) exactly. If cleanup residue exists, ask whether the user grants explicit authorization for force cleanup of that exact residue. Do not force-delete automatically. A refusal preserves the residue and reports the recovery position; an authorization permits only the separately scoped cleanup action, after which this check runs again. This is not a fourth formal authorization gate.

#### Next Gate（下一步门禁）

There is no next gate. Report `最终完成` only after all checks pass; otherwise preserve the evidence and report the recovery position.

## Formal specification（正式规格）

After the bounded overall review and its fixes pass proportional verification, prepare the complete formal specification difference against the verified external behavior. Formal specification preparation owns its conflict decisions, complete difference, validation, application, and recovery. Its final confirmation is the single confirmation requested in the Gate 3 — Specification Archival and Delivery（规格存档并交付） result, which also authorizes the exact delivery actions. Formal specifications are not part of the earlier code-review scope. Run the relevant fast validation after the approved specification difference is applied and validated.

## PR delivery（拉取请求交付）

After the single confirmation requested in the Gate 3 — Specification Archival and Delivery（规格存档并交付） result succeeds and the specification is applied and validated, call the selected PR Flow（拉取请求流程） entry automatically; Gate 3 remains incomplete until that delivery finishes successfully.

- Use `pr-flow-tweak` only for a non-bug lightweight change that meets its contract.
- Use `pr-flow-complete` for standard and high-risk changes.
- Treat every PR Flow stop state as a resumable pause rather than completion; preserve it as the current incomplete Gate 3 delivery state without requesting another Gate 3 confirmation.
- When a merge or rebase conflict exists, use `resolving-merge-conflicts`. Resolve from the spec, tickets, commits, and tests; rerun affected checks. Ask the user when the sources permit incompatible observable behaviors rather than choosing a new behavior.

## Cleanup and completion（清理与完成）

PR Flow owns merged head-branch cleanup and final worktree removal. Use only non-forced cleanup. Preserve dirty, unmerged, failed, or unknown content and report the blocker.

After merge, synchronize the local base branch.

By default, Development Flow excludes local installation, client synchronization, marketplace refresh, and Release Flow（发布流程）. The flow MUST NOT proactively list or ask about these actions. Perform one only when the user explicitly requests that exact action; a general instruction such as “continue the cleanup” does not authorize installation, synchronization, refresh, or release work.

Use the requested action's formal entry and verify its result. Never infer authorization for a required release when a requested synchronization depends on unpublished content; report that requested action separately. Unrequested or unavailable local delivery MUST NOT block completion or become a default follow-up task.

Completion Check（完成检查） owns the final completion conclusion. Do not declare the Development Flow（开发流程） complete from a successful Gate 3 confirmation or a partial cleanup result.
