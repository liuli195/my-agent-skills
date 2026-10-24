## Problem Statement

my-spec 在 add、review 和 audit 流程中要求冲突、删除及低可信候选逐项决定，但现有 Skill（技能）没有可靠落实原设计中的完整 `conflicts` 状态。Agent（代理）可能只保存第一项和总数，后续为取得下一项重新扫描，导致同一次运行的候选集合从 13 项变化为 8 项。用户无法确认后续问题仍来自最初的审查结果，也无法安全恢复被中断的逐项决定。

此外，my-spec-add 的文案把用户指定文档描述为必需输入，但实际命令允许无参数运行，Agent 也可以从会话、文档、代码或其他相关证据中形成规格。这造成设计、规格与实际可用行为不一致。

## Solution

恢复 my-spec 原始的简单状态机制：一次分析完成后，把全部待决定项保存到当前运行的 `conflicts` 列表，以 `currentConflict` 指向当前项目，并将用户选择写入 `decisions`。首次展示前必须保存完整列表；进入逐项决定后只能读取该列表，禁止重新扫描来取得下一项。

由 `spec_ops.py`（规格操作脚本）承担状态初始化、完整列表写入、当前项读取、决定记录、游标推进和状态报告等机械操作。Agent 继续负责语义分析、证据选择、推荐答案和 Delta（增量规格）生成，脚本不做相似度判断或语义推断。

add、review 和 audit 共用同一状态机制，同时保持各自范围：review 只审查主规格，audit 机械扫描 Git（版本管理）可见仓库范围，add 由 Agent 为当前请求自主选择相关证据，不要求必须指定文档，也不自动扩展为 audit。

## User Stories

1. As a my-spec-review 用户, I want the complete conflict list fixed before the first question, so that later questions come from the same review result.
2. As a my-spec-audit 用户, I want the complete deletion and low-confidence list preserved, so that repository audit decisions do not drift between turns.
3. As a my-spec-add 用户, I want to run the command without naming a document, so that requirements already established in the conversation can become specifications.
4. As a my-spec-add 用户, I want the Agent to select relevant conversation, document, code, or other evidence, so that the entry point fits the current task rather than one input format.
5. As a user answering conflicts, I want to see one item at a time, so that each semantic decision remains deliberate.
6. As a user answering conflicts, I want the reported total to remain stable, so that I can trust progress reporting.
7. As a user resuming a my-spec run, I want the same current conflict to be returned, so that interruption does not silently change the review.
8. As a user modifying an accepted candidate, I want the modified decision saved against the current item, so that the preview reflects exactly what I approved.
9. As a user deferring a candidate, I want it excluded from the preview, so that unresolved semantics do not enter the main specification.
10. As a user ignoring a candidate, I want the decision recorded only for the current run, so that it does not become a second long-term source of truth.
11. As a maintainer, I want incomplete conflict payloads rejected, so that an Agent cannot save only a count and first item.
12. As a maintainer, I want duplicate or out-of-order decisions rejected, so that decisions cannot be applied to the wrong candidate.
13. As a maintainer, I want state transitions enforced mechanically, so that unresolved conflicts cannot reach preview or application.
14. As a maintainer, I want add、review and audit to share one state contract, so that the same defect is not fixed three different ways.
15. As a maintainer, I want semantic discovery to remain Agent-owned, so that deterministic scripts do not pretend to understand requirement meaning.
16. As a maintainer, I want audit scope discovery to remain deterministic, so that Agent preference cannot silently omit Git-visible files.
17. As a maintainer, I want the current main-spec fingerprint checked before continuation and application, so that stale decisions cannot overwrite changed specifications.
18. As a maintainer, I want the regression exercised through the packaged CLI, so that tests cover the real state boundary rather than helper-only behavior.
19. As a maintainer, I want all three Skill contracts checked by tests, so that future wording changes cannot reintroduce rescanning.
20. As a repository contributor, I want `verify.my-spec` to run these regressions, so that the shared validation entry point catches failures.

## Implementation Decisions

- Keep the original run-state vocabulary: `ANALYZING`, `WAITING_DECISION` and `READY_TO_APPLY`.
- Keep the original state fields `conflicts`, `currentConflict` and `decisions`; do not introduce a separate Decision Queue subsystem.
- Treat `conflicts` as the umbrella list for semantic conflicts, deletion candidates, low-confidence candidates and semantic format decisions.
- Save the complete `conflicts` list before displaying the first item. A count without complete item bodies is invalid.
- Once the run reaches `WAITING_DECISION`, obtain every next item from saved state. Rescanning to obtain the next item is forbidden.
- Add deterministic CLI operations for state initialization, complete conflict-list storage, current-item retrieval, decision recording and status reporting.
- The state script validates legal transitions, cursor position, supported decision values and non-empty candidate evidence, then writes state atomically.
- Agent-owned semantic work remains outside the script: selecting evidence, identifying candidates, assessing confidence, explaining conflicts and generating Delta content.
- Exact duplicates and other deterministic items continue to be handled automatically; only conflicts, all removals and low-confidence candidates enter `conflicts`.
- Preserve the existing decisions: accept, ignore, accept after modification and defer. Deferred items do not enter preview.
- Preserve current-run-only decisions. Successful completion cleans the work state; no cross-run ignore ledger is introduced.
- my-spec-review reads only the main specification library.
- my-spec-audit derives its repository range from Git-visible files and retains its existing exclusions.
- my-spec-add allows the Agent to choose any relevant evidence available for the current request. A specified document is optional, and add does not imply a full-repository audit.
- Keep `inputFingerprint`. The Agent supplies it for the exact evidence used by add; review uses the main-spec fingerprint, and audit uses the deterministic repository input fingerprint.
- Update the original design, active main specification, shared entry contract and three specialized Skill references so they describe the same behavior.
- Do not create `CONTEXT.md` or an ADR（架构决策记录） for this change.

## Testing Decisions

- The primary test seam is the packaged `spec_ops.py` CLI. Tests invoke real commands in separate processes rather than only calling internal helpers.
- A regression writes 13 complete conflicts, reads the first, decides it, starts a new process and proves the second item and total still come from the original list.
- State tests cover initialization, legal transitions, atomic complete-list storage, current-item retrieval, all supported decisions, cursor advancement and status counts.
- Trust-boundary tests reject count-only payloads, missing evidence, duplicate identifiers, unsupported decisions, skipped items, repeated decisions and attempts to become ready while unresolved items remain.
- Skill contract tests verify that add、review and audit all save the complete list before the first display and prohibit rescanning during `WAITING_DECISION`.
- my-spec-add contract tests verify that a document is optional and that Agent-selected evidence can come from the current task context.
- Existing Delta validation, preview, complete diff, fingerprint recheck, atomic application and rollback tests remain unchanged and continue to pass.
- The repository's `verify.my-spec` check is the release-facing test entry and must execute the new regressions.
- Tests assert externally observable CLI output, exit status and persisted run behavior; they do not couple to internal helper decomposition.

## Out of Scope

- Building a semantic scanner in `spec_ops.py`.
- Introducing a new queue service, database, catalog or long-term decision ledger.
- Persisting conversation history or controlling Agent context.
- Changing how the Agent chooses which evidence to read for add.
- Changing MySpec main or Delta syntax.
- Changing final confirmation, full-diff display, atomic replacement or rollback semantics except where state gating enforces existing rules.
- Creating `CONTEXT.md` or an ADR.
- Installing or synchronizing the plugin into user environments.

## Further Notes

This change restores and enforces the original simple `state.json` mechanism rather than replacing it with a larger workflow system. The triggering failure was a review that reported 13 findings but persisted only the first item and count; a later rescan produced 8 findings. The regression must preserve that concrete failure shape.
