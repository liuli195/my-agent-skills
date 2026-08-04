# Initialization（初始化）

Read this file only for an explicit initialization request or after a formal entry reports a missing prerequisite.

## Readiness（就绪检查）

Inspect the bounded repository and confirm:

- it is a Git repository with an authenticated GitHub remote;
- the required Requirements（需求）Skills（技能）—`codebase-design`, `grill-with-docs`, its required `grilling` and `domain-modeling`, `to-spec`, and `to-tickets`—plus TDD（测试驱动开发）, review, MySpec（自有规格）, PR Flow（拉取请求流程）, Build and Verify（构建与验证）, and Pi Subagent Policy（Pi 子代理策略）are available; `wayfinder` is required only when the selected route needs its multi-session planning;
- issue-tracker, triage, and domain-document rules exist;
- MySpec, Build and Verify, and PR Flow expose their formal entry points;
- the repository has a worktree initialization entry and ignores its root `.worktrees/` directory.

## Missing prerequisites（缺失前置项）

Record the named gate whose formal entry reported the missing prerequisite. Before changing anything, read the exact formal entry responsible for each confirmed missing item. Present one structured initialization plan with the missing items, formal entries, change scope, verification, and the named gate to which the flow will return; then wait for explicit initialization authorization.

Initialization authorization is not a fourth formal gate and does not satisfy Gate 1 — Requirements Confirmation（需求确认）, Gate 2 — Implementation and Verification（实施和验证）, or Gate 3 — Specification Archival and Delivery（规格存档并交付）. After successful initialization, return to the same gate that reported the missing prerequisite and recheck it.

Delegate only to an existing formal entry, such as:

- `setup-matt-pocock-skills` for engineering-skill repository documents;
- `build-and-verify-init` for Build and Verify configuration;
- `pr-flow-init` for PR Flow configuration;
- MySpec's own initialization command;
- `plugin-sync` for authorized Agent-side installation or synchronization.

When no formal initializer owns a missing CI（持续集成）workflow, worktree script, or other prerequisite, report the blocker and stop. Resume after the user supplies it.

A successful initialization is enough. Future runs rely on each formal entry's own validation and revisit readiness only after a prerequisite error or an explicit initialization request.
