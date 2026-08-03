# Requirements（需求）

## MUST — Dependencies（依赖）

Before presenting Gate 1 output, read [output-template](output-template.md) and use its exact titles, four blocks, and order.

Before a new requirements discussion, read and use `codebase-design` in the current session to form an overall design proposal. Scale it to the Flow Level（流程等级）: for a lightweight change, state only the observable result, scope, and highest public test seam; identify Module（模块）, Interface（接口）, and Seam（接缝） only when the change has structural design.

After the user confirms the overall direction, and before discussing any detail, read `grill-with-docs` in the current session, then read and use `domain-modeling` as required by that Skill（技能）. MUST NOT substitute ordinary `grilling` for `grill-with-docs`.

Before invoking `to-spec` or `to-tickets`, read the exact Skill and confirm current-session tool-call evidence that `codebase-design`, `grill-with-docs`, and `domain-modeling` were read. Read `wayfinder` only when dependent decisions require its multi-session route. Do not replace this evidence with a self-reported flag or state file.

If a required Skill is missing, unreadable, fails to load, or is replaced by another entry, stop and report the blocker, preserved requirement artifacts, and Gate 1 — Complete Requirements（完成需求） as the resume point.

## MUST — Gate（门禁）

### Gate 1 — Complete Requirements（完成需求）

#### Usage Condition（使用条件）

Use this completion gate after the domain terms, highest public test seam, specification, and vertical tickets are drafted, and before publishing requirement artifacts.

#### Previous Gate（上一依赖门禁）

There is no previous formal gate. Development Flow（开发流程）starts with requirements discussion.

#### Checks（检查清单）

Confirm that:

- the domain terms are resolved;
- the highest public test seam is agreed;
- the specification and vertical tickets are agreed;
- every blocking edge is genuine;
- the proposed change name, branch, and worktree layout are clear;
- no requirement artifact has been published or committed without this confirmation.

If any check fails, preserve the drafts and stop at Gate 1 — Complete Requirements（完成需求）.

#### Confirmation Output（待用户确认内容清单）

Present the complete specification, test seam, ticket breakdown and blocking edges, proposed change name, branch, and worktree. Explicitly ask whether the user approves completing Requirements and publishing those artifacts. Approval of one detail or a request to continue investigation is not approval of Gate 1 — Complete Requirements（完成需求）.

Without explicit confirmation, report the preserved drafts and Gate 1 — Complete Requirements（完成需求） as the resume point.

#### Next Gate（下一步门禁）

Gate 2 — Enter Implementation（进入实施）. Gate 1 — Complete Requirements（完成需求） passes only after the approved requirement artifacts are published, committed, and the change worktree is clean.

## Flow Level（流程等级）

Recommend a level from observable risk, then let the user confirm it.

| Level | Use for | Minimum path |
| --- | --- | --- |
| Lightweight | Documentation, wording, formatting, or low-risk configuration with no changed runtime behavior | Short confirmation, relevant check, real smoke only when a user path changed, `pr-flow-tweak` |
| Standard | Features, bugs, and integrations | Requirements, isolated implementation, TDD, bounded overall review, user-entry smoke, `pr-flow-complete` |
| High risk | Security, data migration, release, machine state, or broad public contracts | Deep requirements, risk-specific checks, critical-ticket review, overall review, `pr-flow-complete` |

Security, data integrity, migration, release, and other protected work stays high risk. Missing information defaults to standard. The user may raise any level; lowering a protected level requires changing the scope rather than skipping its controls.

## Discussion route（讨论路径）

1. Present the overall design proposal before detail discussion. It states the observable result, scope, out-of-scope work, highest public test seam, and any applicable Module（模块）, Interface（接口）, and Seam（接缝）.
2. Let the user confirm or redirect that direction in normal conversation. Direction Confirmation（方向确认） is not a formal gate: it does not publish artifacts or authorize implementation or delivery.
3. After Direction Confirmation（方向确认）, use `grill-with-docs` and `domain-modeling` to discuss only unresolved details, one decision at a time. Do not re-ask a detail already answered and confirmed in the current conversation.
4. Return to the overall design proposal when an answer changes the scope, Module（模块）, Interface（接口）, Seam（接缝）, highest public test seam, or Flow Level（流程等级）; otherwise continue with the unresolved detail.

Choose the route after Direction Confirmation（方向确认）:

- Use `grill-with-docs` when the remaining decisions can be resolved in one session.
- Use `wayfinder` when dependent decisions, research, or prototypes require multiple sessions. Treat the confirmed direction as its destination; its individual discussion tickets only resolve remaining decisions.
- For an already precise lightweight change, use the minimal proposal and direction confirmation without manufacturing an interview.

During discussion, retain confirmed domain terms and decisions in the conversation. Publish the confirmed terms with the spec and tickets instead of editing the base checkout mid-discussion.

## Publish one change（发布单项变更）

1. Confirm the highest public test seam through `to-spec`.
2. Use `to-tickets` to draft tracer-bullet vertical slices. Every ticket has an independently observable result, runnable verification, and only genuine blockers.
3. After receiving the confirmation required by Gate 1 — Complete Requirements（完成需求）, create an ASCII-named change branch in `.worktrees/<change>/`, run the repository worktree initializer, and publish:
   - confirmed terms to the repository domain glossary;
   - the spec to `myspec/changes/<change>/spec.md`;
   - implementation tickets to `myspec/changes/<change>/issues/`.
4. Commit these requirement artifacts before presenting the implementation plan.

For multi-session wayfinding, keep the intermediate map at `myspec/changes/<change>/wayfinder.md` and its decision tickets under `decisions/`. Decision tickets guide the final spec; implementation tickets remain separate.

Completion requires a clean change worktree containing the committed, user-approved requirement artifacts. Stop before implementation authorization.
