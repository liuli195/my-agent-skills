---
name: pi-development-flow
description: Orchestrate one Pi development change from design-first requirements discussion through isolated implementation, review, PR delivery, and cleanup. Use when starting or resuming repository development work that must follow the complete development flow.
---

# Pi Development Flow（Pi 开发流程）

Orchestrate one GitHub-hosted repository change by composing the repository's existing Skills（技能）. Keep each delegated Skill as the single source of truth for its own procedure.

## Run（运行）

1. **Choose the entry.** For an existing `myspec/changes/<change>/`, read [resume](references/resume.md) before acting. For a new change, continue to requirements. If the user explicitly requests repository initialization or a formal entry reports a missing prerequisite, read [initialization](references/initialization.md).
2. **Confirm requirements.** Read and complete [requirements](references/requirements.md): form and confirm the overall design before discussing only unresolved details. This phase is complete when the approved domain terms, spec, vertical tickets, and test seams are committed on the change branch.
3. **Request implementation authorization.** Present the concrete implementation plan as a table covering ticket order and parallel groups, branch and worktree layout, executor, red/green checks, smoke checks, review gates, integration points, cleanup timing, risks, and stop conditions. Wait for explicit authorization; creating the change is not authorization to implement it.
4. **Implement.** After authorization, read and complete [implementation](references/implementation.md). This phase is complete when every ticket is integrated, its behavior evidence is recorded, the risk-matched final verification and fast verification pass, and the bounded overall review has no blocking finding.
5. **Deliver.** Read and complete [delivery](references/delivery.md). The Development Flow（开发流程） is complete when the PR（拉取请求） is merged, the base branch is synchronized, and every safely removable branch and worktree is gone. Local installation, client synchronization, marketplace refresh, and Release Flow（发布流程） remain outside this flow unless the user explicitly requests the exact action.

## Gates（门禁）

Keep four numbered and named decisions distinct:

1. **Gate 1 — Complete Requirements（完成需求）.** Approve requirements, test seams, and tickets before publishing the change artifacts.
2. **Gate 2 — Enter Implementation（进入实施）.** Approve the concrete implementation plan before code or behavior changes.
3. **Gate 3 — Enter Delivery（进入交付）.** After implementation, review, and verification complete, use the final `my-spec-add`（新增自有规格） confirmation to approve the formal MySpec（自有规格） difference. Gate 3 passes only after that Skill（技能） applies and validates the difference, then enters Gate 4.
4. **Gate 4 — Authorize PR Delivery（授权 PR 交付）.** After the formal specification is valid, approve push, PR creation or update, merge, and final cleanup.

At any failed gate, preserve the current artifacts and report the exact resume entry.
