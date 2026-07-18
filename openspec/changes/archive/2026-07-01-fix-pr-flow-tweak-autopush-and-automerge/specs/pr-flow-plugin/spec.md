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
- **AND** PR checks（拉取请求检查） are no longer pending（等待中）
- **AND** GitHub CLI（GitHub 命令行） does not suggest `--auto`（自动合并）
- **THEN** complete（收尾） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** complete（收尾） MUST use `ruleset_merge_blocking` as reason（原因）
- **THEN** complete（收尾） MUST preserve the original GitHub（代码托管平台） error text for diagnosis（诊断）

#### Scenario: Rulesets block merge while checks are pending
- **WHEN** `gh pr merge`（合并拉取请求） fails with `ruleset_merge_blocking`（规则集阻塞）
- **AND** PR checks（拉取请求检查） are still pending（等待中）
- **THEN** complete（收尾） MUST reuse the configured checks wait behavior（检查等待行为）
- **THEN** complete（收尾） MUST return the checks wait stop state（检查等待停止状态） unchanged if checks（检查） fail or remain pending until timeout
- **THEN** complete（收尾） MUST retry merge（合并） only after checks（检查） are no longer pending（等待中） and no checks wait stop state（检查等待停止状态） is returned
- **THEN** complete（收尾） MUST keep using `ruleset_merge_blocking` as reason（原因） if merge（合并） remains blocked after waiting

#### Scenario: Rulesets suggest auto-merge
- **WHEN** `gh pr merge`（合并拉取请求） fails because the base branch policy（目标分支策略） prohibits the merge（合并）
- **AND** PR checks（拉取请求检查） are no longer pending（等待中）
- **AND** GitHub CLI（GitHub 命令行） suggests `--auto`（自动合并）
- **THEN** complete（收尾） MUST retry the existing merge（合并） command with `--auto`（自动合并）
- **THEN** complete（收尾） MUST preserve `--match-head-commit`（匹配头提交）
- **THEN** complete（收尾） MUST NOT suggest or use `--admin`（管理员绕过）

#### Scenario: Transient PR view failure is retried
- **WHEN** a read-only `gh pr view`（查看拉取请求） call fails with EOF（连接提前结束）
- **THEN** PR Flow（拉取请求流程） MUST retry the read-only query with a bounded retry count
- **THEN** retry attempts MUST NOT print repeated stop state（停止状态） lines
- **THEN** if retries are exhausted, PR Flow（拉取请求流程） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** if retries are exhausted, PR Flow（拉取请求流程） MUST use `gh_pr_view_transient_failed` as reason（原因）
- **THEN** if retries are exhausted, stop state（停止状态） details（详情） MUST record the transient（临时） category, retry count, and next command（下一步命令）

### Requirement: Tweak PR path
系统 MUST 提供 tweak（非 bug 小改动）路径，用于跳过 review gate 但保留 PR 流程。

#### Scenario: Tweak requires PR
- **WHEN** 用户运行 tweak
- **THEN** 系统 MUST 创建或同步 PR
- **THEN** 系统 MUST 等待 checks、合并 PR 并执行 cleanup
- **THEN** 系统 MUST 跳过 review gate

#### Scenario: Tweak reuses safe auto-push
- **WHEN** 用户在功能分支运行 tweak（小改）
- **AND** 本地工作区干净
- **AND** 当前分支不是 `defaults.baseBranch`（默认目标分支）
- **AND** GitHub（代码托管平台）远端确认当前分支没有 active rules（有效规则）
- **AND** 当前分支没有 upstream（上游分支）或本地提交尚未推送
- **THEN** tweak（小改） MUST reuse the same safe auto-push（安全自动推送） behavior as complete（收尾）
- **THEN** 推送成功后 MUST continue to create or sync PR（拉取请求）

#### Scenario: Tweak reason
- **WHEN** 用户运行 tweak
- **THEN** 用户 MUST 提供 reason（原因）
- **THEN** reason（原因） MUST only justify using the tweak（小改） path
- **THEN** 系统 MUST NOT 在 PR body（拉取请求正文）中写入独立的 tweak path（小改路径）正文或 reason（原因）
- **THEN** PR body（拉取请求正文） MUST use the same `Summary`、`Scope` and `Closing References` sections as `complete`（收尾）
