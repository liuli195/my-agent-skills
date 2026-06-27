## MODIFIED Requirements

### Requirement: Global command guard configuration layout
系统 MUST 让 Global Command Guard（全局命令守卫）通过 artifacts.yaml（产物注册文件）读取被守卫流程证据。

#### Scenario: Comet change review 通过产物注册读取项目产物
- **WHEN** Global Command Guard 用于守卫 Comet change build 完成命令
- **AND** 该守卫通过 `artifact` 或 `artifact_id` 引用 `artifacts.yaml` 中的 cross-agent-review pass marker（跨代理审查通过标记）
- **THEN** Runtime（运行时）MUST 按 `artifacts.yaml` 注册路径读取该 guard-defined evidence（守卫定义证据）
- **AND** 该产物 MUST 位于项目内 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`
- **AND** Runtime 不得从 `~/.agents/guard` 读取该 Comet change 的通过证据

### Requirement: Global Command Guard evidence uses dual path model
系统 MUST 为 Global Command Guard（全局命令守卫点）区分 guard-defined evidence（守卫定义证据）和 external artifact（外部产物）。当通过结论由主 agent（主代理）根据上游报告生成时，Agent Guard（代理守卫）MUST 定义默认 evidence（证据）目录；当被守卫流程本身已经生成稳定可检查产物时，Agent Guard（代理守卫）MUST 只登记并校验原始路径，不复制、不搬运、不接管目录。

#### Scenario: guard-defined evidence 使用默认目录
- **WHEN** Guard Profile（守卫画像）声明的 artifact（产物）属于 guard-defined evidence（守卫定义证据）
- **THEN** Runtime（运行时）MUST 从 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json` 读取证据

#### Scenario: guard-defined evidence 由调用方写入
- **WHEN** guard-defined evidence（守卫定义证据）需要写入 pass marker（通过标记）
- **THEN** 被守卫流程或主 agent（主代理）MUST 在 Guard（守卫）检查前写入该 marker（标记）
- **AND** Agent Guard（代理守卫）只负责读取和校验，不负责生成该 marker（标记）

#### Scenario: guard-defined evidence 使用标准字段
- **WHEN** guard-defined evidence（守卫定义证据）写入 pass marker（通过标记）
- **THEN** marker（标记）MUST 使用 `guard-evidence/v1` 字段契约

#### Scenario: cross-agent-review pass marker 使用 guard-defined evidence
- **WHEN** Global Command Guard（全局命令守卫点）校验 cross-agent-review（跨代理审查）的 pass marker（通过标记）
- **THEN** 该 artifact（产物）MUST 注册为 guard-defined evidence（守卫定义证据）
- **AND** 注册路径 MUST 使用 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`
- **AND** `{artifact_id}` MUST 为 `cross_agent_review_pass`
- **AND** `{subject_id}` MUST 来自命令捕获值，Comet change（变更）场景下等于 `change`
