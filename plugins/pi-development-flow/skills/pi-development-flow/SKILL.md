---
name: pi-development-flow
description: Orchestrate one Pi development change from requirements through isolated implementation, review, PR delivery, and cleanup. Use when starting or resuming repository development work that must follow the complete development flow.
---

# Pi Development Flow（Pi 开发流程）

Orchestrate one GitHub-hosted repository change by composing the repository's existing Skills（技能）. Keep each delegated Skill as the single source of truth for its own procedure.

## Run（运行）

1. **Choose the entry.** For an existing `myspec/changes/<change>/`, read [resume](references/resume.md) before acting. For a new change, continue to requirements. If the user explicitly requests repository initialization or a formal entry reports a missing prerequisite, read [initialization](references/initialization.md).
2. **Confirm requirements.** Read and complete [requirements](references/requirements.md). This phase is complete when the approved domain terms, spec, vertical tickets, and test seams are committed on the change branch.
3. **Request implementation authorization.** Present the concrete implementation plan as a table covering ticket order and parallel groups, branch and worktree layout, executor, red/green checks, smoke checks, review gates, integration points, cleanup timing, risks, and stop conditions. Wait for explicit authorization; creating the change is not authorization to implement it.
4. **Implement.** After authorization, read and complete [implementation](references/implementation.md). This phase is complete when every ticket is integrated, its behavior evidence is recorded, the risk-matched final verification and fast verification pass, and the bounded overall review has no blocking finding.
5. **Deliver.** Read and complete [delivery](references/delivery.md). The Development Flow（开发流程） is complete only when the PR（拉取请求） is merged, the base branch is synchronized, authorized local delivery is verified, and every safely removable branch and worktree is gone.

## Gates（门禁）

Keep four decisions distinct:

1. Approve requirements, test seams, and tickets before publishing the change artifacts.
2. Approve the concrete implementation plan before code or behavior changes.
3. Approve the formal MySpec（自有规格）difference through `my-spec-add` after review and verification.
4. Approve push, PR creation or update, merge, and final cleanup before PR delivery.

At any failed gate, preserve the current artifacts and report the exact resume entry.
