---
name: pi-development-flow
description: Orchestrate one Pi development change from design-first requirements discussion through worktree-bound implementation, review, PR delivery, and cleanup. Use when starting or resuming repository development work that must follow the complete development flow.
---

# Pi Development Flow（Pi 开发流程）

Orchestrate one GitHub-hosted repository change by composing the repository's existing Skills（技能）. Keep each delegated Skill as the single source of truth for its own procedure.

## Run（运行）

1. **Choose the entry.** For an existing `myspec/changes/<change>/`, read [resume](references/resume.md) before acting. For a new change, continue to requirements. If the user explicitly requests repository initialization or a formal entry reports a missing prerequisite, read [initialization](references/initialization.md).
2. **Confirm requirements.** Read and complete [requirements](references/requirements.md): form and confirm the overall design before discussing only unresolved details. This phase is complete when the approved domain terms, spec, vertical tickets, and test seams are committed on the change branch.
3. **Request implementation and verification authorization.** Present the concrete implementation plan as a table covering ticket order and parallel groups, branch and worktree layout, executor, red/green checks, smoke checks, review gates, integration points, cleanup timing, risks, and stop conditions. Wait for explicit authorization; creating the change is not authorization to implement it.
4. **Implement and verify.** After authorization, read and complete [implementation](references/implementation.md). This phase is complete when every ticket is integrated, its behavior evidence is recorded, the risk-matched final verification and fast verification pass, and the bounded overall review has no blocking finding.
5. **Archive the specification and deliver.** Read and complete [delivery](references/delivery.md), then run its Completion Check（完成检查）. The Development Flow（开发流程） is complete only when that check reports final completion. Local installation, client synchronization, marketplace refresh, and Release Flow（发布流程） remain outside this flow unless the user explicitly requests the exact action.

## Output Contract（输出契约）

Every gate and completion result MUST use the fixed titles and exact four-block format in [output-template](references/output-template.md). Read that reference before presenting the result. Do not rename, reorder, merge, split, or add output blocks; put only the current gate's essential points in the summary and use citations for long content.

## Gates（门禁）

Keep three numbered and named decisions distinct:

1. **Gate 1 — Requirements Confirmation（需求确认）.** Approve requirements, test seams, and tickets before publishing the change artifacts.
2. **Gate 2 — Implementation and Verification（实施和验证）.** Approve the concrete implementation plan before code or behavior changes.
3. **Gate 3 — Specification Archival and Delivery（规格存档并交付）.** After implementation, review, and verification complete, present the complete formal specification difference and exact PR delivery actions together, obtain one user confirmation, then apply and validate the specification and execute the authorized delivery automatically.
After Gate 3 delivery, run **Completion Check — 完成检查**: report whether final completion is proven, report cleanup residue, and request explicit force-cleanup authorization when needed. This is not a fourth numbered or authorization gate.

At any failed gate or completion check, preserve the current artifacts and report the exact resume entry.
