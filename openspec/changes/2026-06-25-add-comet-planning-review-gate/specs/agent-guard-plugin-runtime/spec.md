## ADDED Requirements

### Requirement: Global Command Guard evidence uses dual path model

系统 MUST 为 Global Command Guard（全局命令守卫点）区分 guard-defined evidence（守卫定义证据）和 external artifact（外部产物）。当被守卫流程没有稳定可检查产物时，Agent Guard（代理守卫）MUST 定义默认 evidence（证据）目录；当被守卫流程已经生成稳定产物时，Agent Guard（代理守卫）MUST 只登记并校验原始路径，不复制、不搬运、不接管目录。

#### Scenario: guard-defined evidence 使用默认目录

- **WHEN** Guard Profile（守卫画像）声明的 artifact（产物）属于 guard-defined evidence（守卫定义证据）
- **THEN** 相对路径 MUST 使用项目内 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`
- **AND** `{profile_id}` MUST 来自当前 Guard Profile（守卫画像）
- **AND** `{artifact_id}` MUST 来自当前 artifact（产物）编号
- **AND** `{subject_id}` MUST 来自命令捕获或声明式上下文，例如 Comet change（变更）名称
- **AND** `{git_head_short}` MUST 来自当前 Git HEAD（代码版本）的 12 位短值

#### Scenario: guard-defined evidence 由调用方写入

- **WHEN** guard-defined evidence（守卫定义证据）需要写入 pass marker（通过标记）
- **THEN** 写入者 MUST 是调用被守卫流程的主 agent（代理）或明确的调用方
- **AND** 当被守卫流程的审查结论满足 Guard Profile（守卫画像）声明的放行条件时，调用方 MUST 写入该 marker（标记）
- **AND** Agent Guard Runtime（代理守卫运行时）MUST NOT 自动生成该 marker（标记）
- **AND** 被检查的只读 Skill（技能）MUST NOT 因为门禁而改变自身只读边界

#### Scenario: guard-defined evidence 使用标准字段

- **WHEN** guard-defined evidence（守卫定义证据）写入 pass marker（通过标记）
- **THEN** JSON（数据对象）MUST 包含 `schema_version: guard-evidence/v1`
- **AND** JSON（数据对象）MUST 包含 `status: pass`
- **AND** JSON（数据对象）MUST 包含 `producer`
- **AND** JSON（数据对象）MUST 包含 `profile_id`
- **AND** JSON（数据对象）MUST 包含 `artifact_id`
- **AND** JSON（数据对象）MUST 包含 `subject_type`
- **AND** JSON（数据对象）MUST 包含 `subject_id`
- **AND** JSON（数据对象）MUST 包含 `head_ref`
- **AND** JSON（数据对象）MUST 包含 `head_ref_short`
- **AND** JSON（数据对象）MUST 包含 `blocking_findings`
- **AND** JSON（数据对象）MUST 包含 `scope`
- **AND** JSON（数据对象）MUST 包含 `report_hash`
- **AND** JSON（数据对象）MUST 包含 `created_at`

#### Scenario: external artifact 保留原路径

- **WHEN** 被守卫流程已经生成稳定可检查产物
- **THEN** Guard Profile（守卫画像）MUST 在 `artifacts.yaml`（产物注册文件）中登记该原始路径
- **AND** Agent Guard Runtime（代理守卫运行时）MUST 按登记路径读取和校验
- **AND** Runtime（运行时）MUST NOT 要求把该产物复制到 `.local/guard/evidence`
- **AND** Runtime（运行时）MUST NOT 修改该外部流程的输出目录

#### Scenario: cross-agent-review pass marker 是 external artifact

- **WHEN** Global Command Guard（全局命令守卫点）校验 cross-agent-review（跨代理审查）的 `review-pass.json`
- **THEN** 该 artifact（产物）MUST 注册为 external artifact（外部产物）
- **AND** 注册路径 MUST 保持 `.local/cross-agent-review/{change}/{git_head_short}/review-pass.json`
- **AND** Agent Guard（代理守卫）不得搬运或复制该 marker（标记）
