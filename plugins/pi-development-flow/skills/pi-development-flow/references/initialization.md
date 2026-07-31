# Initialization

Read this file only for an explicit initialization request or after a formal entry reports a missing prerequisite.

## Readiness

Inspect the bounded repository and confirm:

- it is a Git repository with an authenticated GitHub remote;
- the required planning, TDD（测试驱动开发）, review, MySpec（自有规格）, PR Flow（拉取请求流程）, Build and Verify（构建与验证）, and Pi Subagent Policy（Pi 子代理策略）Skills（技能） are available;
- issue-tracker, triage, and domain-document rules exist;
- MySpec, Build and Verify, and PR Flow expose their formal entry points;
- the repository has a worktree initialization entry and ignores its root `.worktrees/` directory.

## Missing prerequisites

Present one structured initialization plan and wait for authorization. Delegate only to an existing formal entry, such as:

- `setup-matt-pocock-skills` for engineering-skill repository documents;
- `build-and-verify-init` for Build and Verify configuration;
- `pr-flow-init` for PR Flow configuration;
- MySpec's own initialization command;
- `plugin-sync` for authorized Agent-side installation or synchronization.

When no formal initializer owns a missing CI（持续集成）workflow, worktree script, or other prerequisite, report the blocker and stop. Resume after the user supplies it.

A successful initialization is enough. Future runs rely on each formal entry's own validation and revisit readiness only after a prerequisite error or an explicit initialization request.
