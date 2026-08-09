# Implementation（实施）

## MUST — Dependencies（依赖）

Before presenting Gate 2 output, read [output-template](output-template.md) and use its exact titles, four blocks, and order.

Before changing feature, bug, or integration behavior, read and apply `tdd`（测试驱动开发）. Before verification, read `build-and-verify`（构建与验证） and use its formal entry. Before review, read `code-review`（代码审查）.

Read `pi-subagent-policy`（Pi 子代理策略） only after deciding delegation is useful and before the first delegation. If a required Skill（技能） is missing, unreadable, fails to load, or is replaced by an informal entry, stop and report the current ticket, preserved evidence, and Gate 2 — Implementation and Verification（实施和验证） as the resume point. Do not replace Build and Verify with a new verification entry.

## MUST — Gate（门禁）

### Gate 2 — Implementation and Verification（实施和验证）

#### Usage Condition（使用条件）

Use this entry gate after Requirements（需求） is complete and before any code, behavior, user-level Skill（技能）, configuration, installation state, or external-client change in the confirmed plan.

#### Previous Gate（上一依赖门禁）

Gate 1 — Requirements Confirmation（需求确认）. The approved requirement artifacts must be published and committed in a clean change worktree.

#### Checks（检查清单）

Confirm that:

- Gate 1 — Requirements Confirmation（需求确认） passed with current-session evidence;
- the committed specification, test seam, and tickets match the approved drafts;
- the concrete implementation plan covers ticket order and parallel groups, branch and worktree layout, executor, red and green checks, smoke checks, review gates, integration points, cleanup timing, risks, and stop conditions;
- the user explicitly authorized that current plan after seeing it;
- no implementation change occurred before that authorization.

If any check fails, do not implement. Preserve the artifacts and stop at Gate 2 — Implementation and Verification（实施和验证）.

#### Confirmation Output（待用户确认内容清单）

When authorization is missing, present the complete implementation plan and explicitly ask whether the user authorizes entering Implementation. “Continue”, requirement approval, or draft approval is not implementation authorization and cannot retroactively authorize an earlier change.

Without explicit confirmation, state that implementation has not started and report the change path and Gate 2 — Implementation and Verification（实施和验证） as the resume point.

#### Next Gate（下一步门禁）

Gate 3 — Specification Archival and Delivery（规格存档并交付）. Gate 2 — Implementation and Verification（实施和验证） is complete only after every ticket is accepted, behavior evidence is recorded outside the immutable ticket, proportional and fixed-baseline fast verification pass, and the bounded overall review has no unresolved blocker.

## Gate 2 ownership（门禁二职责）

Gate 2 uses **Single Writer（单写者）**. The main Agent（代理） constructs the plan and prompts, dispatches work, reads actual evidence, runs formal verification, and decides whether the immutable Approved Ticket（已批准票据） is satisfied. The bound Implementer（实施者） is the only writer of Git-visible implementation changes, including implementation, tests, required integration edits, and review fixes. A Reviewer（审查者） only reports findings and never edits the worktree. The main Agent MUST NOT directly take over an Implementer change.

The Approved Ticket is immutable throughout Gate 2. Do not write implementation evidence, progress, or revisions back into it. If an answer changes the requirement, scope, public seam, or observable acceptance, stop and return to Gate 1 — Requirements Confirmation（需求确认） instead of silently changing the ticket.

A Gate Confirmation（门禁确认） is requested once for this gate. One confirmation covers execution and recovery; recovery does not request it again. If a later action fails, report the exact failed action and resume from that action after recovery. Request a new confirmation only for a separate dangerous action that was not covered by the original confirmation.

## Ordered Gate 2 states（门禁二有序状态）

These are orchestration states, not a new runtime state machine. Follow them in order for each ticket. Every state has a checkable completion condition.

### READY — 准备

1. Confirm the Gate 2 checks above, the current ticket's blockers, its fixed verification baseline, and the target branch and worktree. Choose one feature worktree for sequential tickets; create separate worktrees only for genuinely unblocked parallel tickets.
2. Before the first delegation, apply `pi-subagent-policy` and stop if the effective Implementer or Reviewer configuration does not match the policy. Use the controlled dispatch tool for every writable delegation.
3. Build one self-contained prompt from the short checklist below. It MUST describe one clear write goal, and a ticket implementation goal MUST correspond to exactly one published ticket. Do not ask the child to discover missing requirements from another ticket.

#### Self-contained prompt checklist（自包含提示词清单）

- the one observable result and the exact immutable acceptance criteria;
- the relevant source locations and direct context;
- the confirmed public seam and the red/green check, or the smallest relevant check for documentation-only work;
- the fixed verification baseline and required `build-and-verify` command;
- the real user-entry smoke and any affected failure, recovery, security, data-integrity, or migration path;
- the expected Git end state: focused commit, limited diff, clean assigned worktree, and no main-worktree change;
- stop conditions: requirement conflict, uncertain ownership, unverified worktree, missing evidence, or a finding that must return to requirements.

4. Call `dispatch_implementer_in_worktree` with exactly the caller-built `prompt`, `description`, absolute `worktree_path`, and `expected_branch`. The tool verifies and binds the existing non-primary worktree, starts the fixed Implementer role, and preserves the prompt and description; it does not interpret tickets, build prompts, or decide acceptance. Never rely on a prompt to change directories. If tool-enforced binding is unavailable or validation fails, stop before delegation and provide a handoff from the target worktree.

READY is complete only when the target and branch have passed tool validation, the prompt and description are self-contained for one goal, and the Implementer has been dispatched through the controlled entry.

### RETURNED — 已返回

1. Every Implementer invocation first enters `RETURNED`, regardless of its result text. A returned report is not acceptance.
2. The main Agent inspects actual Git and verification evidence in the bound worktree rather than trusting the report: the expected branch and worktree, the commit made after the fixed baseline, focused and limited diff, clean worktree, affected checks, fixed-baseline verification with `status: passed` and non-empty `checked`, required real smoke, and any required review result.
3. Confirm that the main worktree and unrelated paths have no Git-visible change from the dispatch. Preserve dirty, uncommitted, unowned, or unknown content; do not repair it directly.

RETURNED is complete only when this evidence inspection has produced an explicit decision: all evidence satisfies the Approved Ticket, evidence is repairable by another Implementer invocation, or safe ownership cannot be established.

### REWORK_REQUIRED — 需要返工

Enter `REWORK_REQUIRED` when evidence is missing or failing, the diff is not focused, the worktree is dirty, the fixed-baseline verification is invalid, the required smoke fails, or a Reviewer reports a blocking finding.

The main Agent constructs a **new self-contained prompt** containing only the missing evidence or one repair goal, the relevant source and review finding, the immutable acceptance, fixed baseline, checks, smoke, expected Git end state, and stop conditions. Dispatch that prompt and description through the same `dispatch_implementer_in_worktree` entry. The main Agent MUST NOT edit the implementation or take over the repair. MUST NOT rely on a prompt to change directories. After a repair returns, start again at `RETURNED`; after a Reviewer fix, run only the targeted review of the fix diff and affected behavior.

REWORK_REQUIRED is complete only when the new dispatch has returned and its evidence is ready for another `RETURNED` decision.

### ACCEPTED — 已验收

Enter `ACCEPTED` only when the actual evidence, not the Implementer's report, proves all of the following against the immutable Approved Ticket:

- the assigned worktree and exact branch are correct;
- a focused commit exists after the fixed baseline and the limited diff contains only the ticket's goal;
- the assigned worktree is clean and the main worktree has no dispatch change;
- the agreed red/green or smallest relevant check passes;
- fixed-baseline Build and Verify passes with `status: passed` and non-empty `checked`;
- the real main-path smoke and any required high-risk paths pass;
- the required bounded review has no unresolved blocking finding, with Reviewer output treated as report-only evidence.

Only after these checks pass may the flow accept this ticket and move to the next unblocked ticket. Do not write the evidence into the ticket; cite the actual commit, diff, worktree, check, smoke, and review outputs in the flow result.

### BLOCKED — 已阻塞

Enter `BLOCKED` when the target worktree or branch cannot be verified, the controlled entry is unavailable, a required Skill（技能） or formal verification entry cannot load, ownership or Git state is unknown, a requirement conflicts with the immutable ticket, or recovery would require an unapproved dangerous action. Do not start or resume a writable child, and do not make a direct main-Agent edit.

Report the exact blocker, preserved evidence, and recovery point. A requirement or acceptance conflict returns to Gate 1 — Requirements Confirmation（需求确认）. A missing implementation prerequisite remains at Gate 2 — Implementation and Verification（实施和验证）. A post-confirmation action failure resumes from that action without repeating Gate 2 confirmation.

## Verify proportionally（按风险验证）

| Point | Verification |
| --- | --- |
| Ticket | The smallest check at the agreed public seam that proves the ticket's observable result |
| Integration | After committed changes, run `build-and-verify verify --project <worktree> --base <fixed-baseline>`; require `status: passed` with non-empty `checked`, and rerun affected smoke only when conflict resolution or integration changed behavior |
| Lightweight final | Relevant check plus a real target-behavior smoke when a user path changed |
| Standard final | One real user-entry or published-form smoke through the changed main success path, plus fast verification |
| High-risk final | Main success-path smoke plus affected security, data-integrity, failure, migration, or recovery paths, plus fast verification |
| PR CI | The repository's full automated checks |

For committed changes, Pi Development Flow MUST use a fixed verification baseline rather than infer `HEAD^` or read another worktree. A fast result with `status: skipped` or an empty `checked` value is not valid pass evidence and MUST stop integration until a fixed-baseline verification selects at least one check. An external client or system adapter receives its own smallest real smoke immediately after completion. Repository rules, the spec, and explicit user requirements may demand stronger verification. Internal unit tests do not replace a required user-entry smoke.

## Review within the diff（在差异内审查）

Use `code-review` for its fixed-point, Standards（规范）, and Spec（规格） review method. `pi-subagent-policy` controls role selection, so both axes use Reviewer rather than a general-purpose role.

Add only these orchestration constraints:

1. Trigger ticket review for this public dispatch contract and for security, data, migration, release, machine state, hard-to-reproduce shared bugs, high integration conflict, or explicit user request.
2. Read direct callers and contracts only as context needed to judge the changed diff; context is not extra review scope.
3. Keep small patches within their actual diff and necessary context rather than expanding through an unchanged dependency tree.
4. After fixes, review only the fix diff and affected behavior. One full review and one targeted follow-up is the default; recurring basic failures return to requirements and tickets.
5. In the final review, focus on cross-ticket composition, missing acceptance, scope growth, integration edits, and post-ticket-review changes. Previously reviewed local code that did not change gets no second deep style review.

Documented rule violations, missing or wrong specified behavior, scope growth, security, data integrity, and missing main-path acceptance block integration. Treat code smells as judgement calls and fix them only when they create present maintenance risk. If a single ticket is the whole change, one final review satisfies both critical-ticket and overall review gates.

Completion requires all tickets accepted, final proportional verification passing, and the bounded overall review free of unresolved blockers.
