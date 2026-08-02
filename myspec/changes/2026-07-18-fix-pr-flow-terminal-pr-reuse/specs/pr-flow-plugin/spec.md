## MODIFIED Requirements

### Requirement: Complete PR lifecycle
系统 MUST 提供 complete（完整流程），从当前分支创建或同步活动 PR（拉取请求）到合并后清理。仅 `OPEN`（未合并）状态的同名 PR（拉取请求）可作为当前活动 PR（拉取请求）。

#### Scenario: Recoverable PR view failure after creation
- **WHEN** `complete`（收尾）成功创建 PR（拉取请求）
- **AND** 随后的 `gh pr view`（查看拉取请求）暂时无法读取同一个 PR（拉取请求）
- **THEN** complete（收尾） MUST NOT output `EXCEPTION_REQUIRED`（需要异常处理）
- **THEN** complete（收尾） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** stop-state details（停止状态详情） MUST use `gh_pr_view_transient_failed` as reason（原因）
- **THEN** stop-state details（停止状态详情） MUST include `transientCategory: post_create_view`（创建后查看分类）
- **THEN** stop-state details（停止状态详情） MUST include a command（命令） to retry the same `complete`（收尾） operation

#### Scenario: Terminal same-name PR starts a new batch
- **WHEN** `complete`（收尾）在当前分支查询到状态为 `MERGED`（已合并）或 `CLOSED`（已关闭）的同名 PR（拉取请求）
- **THEN** 系统 MUST NOT 使用该 PR（拉取请求）的 `headRefOid`（源提交）进行基线校验
- **THEN** 系统 MUST 使用当前 `HEAD`（当前提交）校验最新远端目标分支
- **THEN** 系统 MUST 推送当前批次并创建新的 PR（拉取请求）

### Requirement: Tweak PR path
系统 MUST 提供 tweak（非 bug 小改动）路径，用于跳过 review gate（审查门禁）但保留 PR（拉取请求）流程。

#### Scenario: Tweak requires PR
- **WHEN** 用户运行 tweak
- **THEN** 系统 MUST 创建或同步活动 PR
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

#### Scenario: Terminal same-name PR starts a new batch
- **WHEN** `tweak`（小改）在当前分支查询到状态为 `MERGED`（已合并）或 `CLOSED`（已关闭）的同名 PR（拉取请求）
- **THEN** 系统 MUST NOT 使用该 PR（拉取请求）的 `headRefOid`（源提交）进行基线校验
- **THEN** 系统 MUST 使用当前 `HEAD`（当前提交）校验最新远端目标分支
- **THEN** 系统 MUST 推送当前批次并创建新的 PR（拉取请求）
