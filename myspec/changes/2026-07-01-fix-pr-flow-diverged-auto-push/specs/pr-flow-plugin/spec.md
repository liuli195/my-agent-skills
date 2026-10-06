## ADDED Requirements

### Requirement: Auto-push refuses upstream divergence
PR Flow（拉取请求流程）MUST refuse safe auto-push（安全自动推送） when the current branch is behind its upstream（上游分支）.

#### Scenario: Complete stops before pushing a diverged branch
- **WHEN** 用户运行 complete（收尾）
- **AND** 当前分支已有 upstream（上游分支）
- **AND** 当前分支相对 upstream（上游分支）同时有 ahead（领先）提交和 behind（落后）提交
- **THEN** complete（收尾） MUST NOT run `git push`（推送）
- **THEN** complete（收尾） MUST output `EXCEPTION_REQUIRED`（需要人工处理）
- **THEN** stop-state details（停止状态详情） MUST include ahead（领先）和 behind（落后）提交数
- **THEN** stop-state details（停止状态详情） MUST include a recovery command（恢复命令） to sync the upstream（上游分支） before retrying

#### Scenario: Tweak stops before pushing a diverged branch
- **WHEN** 用户运行 tweak（小改）
- **AND** 当前分支已有 upstream（上游分支）
- **AND** 当前分支相对 upstream（上游分支）同时有 ahead（领先）提交和 behind（落后）提交
- **THEN** tweak（小改） MUST NOT run `git push`（推送）
- **THEN** tweak（小改） MUST output `EXCEPTION_REQUIRED`（需要人工处理）
- **THEN** stop-state details（停止状态详情） MUST include the command（命令） needed to rerun the same tweak（小改） operation after sync（同步）

#### Scenario: Behind-only branch stops before PR lifecycle
- **WHEN** complete（收尾） or tweak（小改） runs on a branch with upstream（上游分支）
- **AND** 当前分支 has no ahead（领先） commits
- **AND** 当前分支 is behind（落后） upstream（上游分支）
- **THEN** PR Flow（拉取请求流程） MUST stop before create、sync or merge PR（创建、同步或合并拉取请求）
- **THEN** PR Flow（拉取请求流程） MUST output `EXCEPTION_REQUIRED`（需要人工处理）
