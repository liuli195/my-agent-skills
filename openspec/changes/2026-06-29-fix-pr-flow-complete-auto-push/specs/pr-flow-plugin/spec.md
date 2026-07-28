## MODIFIED Requirements

### Requirement: Complete PR lifecycle
系统 MUST 提供 complete（完整流程），从当前分支创建或同步 PR 到合并后清理。

#### Scenario: Safe auto-push before PR lifecycle
- **WHEN** 用户在功能分支运行 complete（收尾）
- **AND** 本地工作区干净
- **AND** 当前分支不是 `defaults.baseBranch`（默认目标分支）
- **AND** GitHub（代码托管平台）远端确认当前分支没有 active rules（有效规则）
- **AND** 当前分支没有 upstream（上游分支）或本地提交尚未推送
- **THEN** complete（收尾） MUST 执行普通 `git push`（推送）
- **THEN** 无 upstream（上游分支）时 MUST 使用 `git push -u <remote> <branch>`
- **THEN** 已有 upstream（上游分支）时 MUST 使用 `git push`
- **THEN** 推送成功后 MUST 继续创建或同步 PR（拉取请求）

#### Scenario: Auto-push refuses unsafe branch
- **WHEN** complete（收尾）准备自动推送当前分支
- **AND** 当前分支等于 `defaults.baseBranch`（默认目标分支）或 GitHub（代码托管平台）远端显示当前分支有 active rules（有效规则）
- **THEN** complete（收尾） MUST NOT push（推送）
- **THEN** complete（收尾） MUST output `EXCEPTION_REQUIRED`（需要人工处理）

#### Scenario: Auto-push fails closed on uncertainty
- **WHEN** complete（收尾）准备自动推送当前分支
- **AND** 本地工作区不干净、GitHub（代码托管平台）保护状态查询失败、保护状态无法解析或 `git push`（推送）失败
- **THEN** complete（收尾） MUST NOT continue to create, sync, or merge PR（拉取请求）
- **THEN** complete（收尾） MUST output `EXCEPTION_REQUIRED`（需要人工处理） for dirty or uncertain state
- **THEN** complete（收尾） MUST output `PUSH_REQUIRED`（需要推送） when `git push`（推送） itself fails

#### Scenario: Rulesets block merge
- **WHEN** `gh pr merge`（合并拉取请求） fails because the base branch policy（目标分支策略） prohibits the merge（合并）
- **THEN** complete（收尾） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** complete（收尾） MUST use `ruleset_merge_blocking` as reason（原因）
- **THEN** complete（收尾） MUST preserve the original GitHub（代码托管平台） error text for diagnosis（诊断）
