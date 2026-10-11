## ADDED Requirements

### Requirement: Invalid fixes input is reported directly
系统 MUST 在 `complete`（收尾）和 `tweak`（小改）路径中把无效 `--fixes`（修复问题编号）参数作为独立输入错误报告，不得让用户误以为只是缺少 PR body（拉取请求正文）。

#### Scenario: Invalid fixes value is rejected with a copyable example
- **WHEN** 用户运行 `complete`（收尾）或 `tweak`（小改）
- **AND** `--fixes`（修复问题编号）包含逗号分隔值、带 `#` 前缀的值、非数字值或小于等于 0 的值
- **THEN** 系统 MUST stop（停止） before auto-push（自动推送）、PR create（创建拉取请求）、sync（同步） or merge（合并）
- **THEN** stop output（停止输出） MUST identify invalid `--fixes`（修复问题编号） input directly
- **THEN** stop state（停止状态） details（详情） MUST include `invalidFixes`
- **THEN** output（输出） MUST include a copyable example using repeated arguments, such as `--fixes 41 --fixes 43 --fixes 44`

#### Scenario: Valid repeated fixes values continue
- **WHEN** 用户运行 `complete`（收尾）或 `tweak`（小改）
- **AND** 每个 `--fixes`（修复问题编号）值都是大于 0 的数字
- **THEN** 系统 MUST accept repeated `--fixes`（修复问题编号） arguments
- **THEN** PR body（拉取请求正文） MUST render each value as a `Fixes #<number>` closing reference（关闭引用）

### Requirement: Post-create PR sync uses transient PR view retry
系统 MUST 让创建 PR（拉取请求）后的同步查看路径复用 bounded retry（有界重试）行为。

#### Scenario: Post-create sync retries EOF and succeeds
- **WHEN** `complete`（收尾） creates a PR（拉取请求）
- **AND** the immediate post-create `gh pr view`（查看拉取请求） sync fails once with EOF（连接提前结束）
- **AND** a retry succeeds
- **THEN** PR Flow（拉取请求流程） MUST continue the lifecycle without printing an intermediate stop state（停止状态）
