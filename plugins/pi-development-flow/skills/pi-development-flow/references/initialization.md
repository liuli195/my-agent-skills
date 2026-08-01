# Initialization（初始化）

Read this file only for an explicit initialization request or after a formal entry reports a missing prerequisite.

## Readiness（就绪检查）

Inspect the bounded repository and confirm:

- it is a Git repository with an authenticated GitHub remote;
- the required planning, TDD（测试驱动开发）, review, MySpec（自有规格）, PR Flow（拉取请求流程）, Build and Verify（构建与验证）, and Pi Subagent Policy（Pi 子代理策略）Skills（技能） are available;
- issue-tracker, triage, and domain-document rules exist;
- MySpec, Build and Verify, and PR Flow expose their formal entry points;
- the repository has a worktree initialization entry and ignores its root `.worktrees/` directory.

## Missing prerequisites（缺失前置项）

Record the named gate whose formal entry reported the missing prerequisite. Before changing anything, read the exact formal entry responsible for each confirmed missing item. Present one structured initialization plan with the missing items, formal entries, change scope, verification, and the named gate to which the flow will return; then wait for explicit initialization authorization.

Initialization authorization is not a fifth formal gate and does not satisfy Gate 1 — Complete Requirements（完成需求）, Gate 2 — Enter Implementation（进入实施）, Gate 3 — Enter Delivery（进入交付）, or Gate 4 — Authorize PR Delivery（授权 PR 交付）. After successful initialization, return to the same gate that reported the missing prerequisite and recheck it.

Delegate only to an existing formal entry, such as:

- `setup-matt-pocock-skills` for engineering-skill repository documents;
- `build-and-verify-init` for Build and Verify configuration;
- `pr-flow-init` for PR Flow configuration;
- MySpec's own initialization command;
- `plugin-sync` for authorized Agent-side installation or synchronization.

When no formal initializer owns a missing CI（持续集成）workflow, worktree script, or other prerequisite, report the blocker and stop. Resume after the user supplies it.

A successful initialization is enough. Future runs rely on each formal entry's own validation and revisit readiness only after a prerequisite error or an explicit initialization request.
