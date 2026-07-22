## MODIFIED Requirements

### Requirement: Comet review gate 通过产物注册层校验 pass marker
系统 MUST 通过 Agent Guard artifacts.yaml（产物注册文件）注册 `cross_agent_review_pass`（跨代理审查通过标记），并使用 Global Command Guard（全局命令守卫点）的 JSON predicate（JSON 谓词）校验该 marker（标记）。`cross_agent_review_pass` 属于 guard-defined evidence（守卫定义证据），因为通过结论由主 agent（主代理）读取 review report（审查报告）后生成。系统 MUST NOT 在 Agent Guard（代理守卫）中实现 cross-agent-review（跨代理审查）内部流程。

#### Scenario: 注册 cross-agent-review pass marker
- **WHEN** 用户级 Guard Profile（守卫画像）配置 Comet review gate
- **THEN** `artifacts.yaml` 注册 `cross_agent_review_pass` 产物
- **AND** 该产物路径指向 Agent Guard（代理守卫）默认 evidence（证据）目录 `.local/guard/evidence/<profile_id>/cross_agent_review_pass/<subject_id>/<head_ref_short>/pass.json`
- **AND** `<subject_id>` 来自 Global Command Guard（全局命令守卫点）的命令捕获值，Comet（流程）场景下等于 `<change>`
- **AND** `<head_ref_short>` 来自当前 Git HEAD（代码版本）的 12 位短值
- **AND** Global Command Guard 通过 `artifact` 或 `artifact_id` 引用该注册产物，而不是直接声明独立 `evidence.path`

#### Scenario: pass marker 合法
- **WHEN** `pass.json` 存在于当前 change（变更）和当前短 HEAD（代码版本）对应目录
- **AND** `status` 为 `pass`、`schema_version` 为 `guard-evidence/v1`、`producer` 为 `cross-agent-review`、`artifact_id` 为 `cross_agent_review_pass`、`subject_id` 匹配当前 change、`head_ref` 匹配当前完整 HEAD、`head_ref_short` 匹配当前短 HEAD、`blocking_findings` 为 0、`report` 存在且 `report_hash` 存在
- **THEN** Global Command Guard（全局命令守卫点）允许 Comet build 阶段守卫收尾命令继续执行

#### Scenario: pass marker 缺失
- **WHEN** review report（审查报告）存在但 `cross_agent_review_pass` 的 `pass.json` 不存在
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet build 阶段守卫收尾命令
- **AND** deny（拒绝）输出包含失败原因、缺失产物、当前 change、当前 head ref 和来自 Guard Profile（守卫画像）配置的下一步提示

#### Scenario: pass marker 过期
- **WHEN** `pass.json` 的 `head_ref` 不匹配当前完整 HEAD
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet build 阶段守卫收尾命令，并提示重新运行跨 agent review

### Requirement: review fail 表现为无有效 pass marker
系统 MUST 只通过 pass marker（通过标记）是否存在且有效来判断 Comet build 阶段守卫收尾命令能否继续。跨 agent review 的执行、修复和重新审查流程属于 cross-agent-review（跨代理审查）或调用方契约。

#### Scenario: 阻塞发现
- **WHEN** 跨 agent review 报告包含 CRITICAL 或 IMPORTANT findings（发现项）
- **THEN** 主 agent（主代理）不得生成 pass marker（通过标记）
- **AND** Global Command Guard（全局命令守卫点）继续拒绝 Comet build 阶段守卫收尾命令
- **AND** Agent Guard 不解析 review report（审查报告）或决定修复流程

#### Scenario: 修复后重新审查
- **WHEN** 用户修复 blocking findings（阻塞发现）并更新 HEAD
- **THEN** 调用方负责重新审查，并由主 agent（主代理）在通过后使用新 head ref 生成新的 `pass.json`
- **AND** Agent Guard 只校验新 pass marker 是否匹配当前命令和当前 HEAD

### Requirement: Comet planning-review gate validates registered pass marker
系统 MUST 通过 Agent Guard artifacts.yaml（产物注册文件）注册 `planning_review_pass`（规划审查通过标记），并使用 Global Command Guard（全局命令守卫点）的 JSON predicate（JSON 谓词）校验该 marker（标记）。`planning_review_pass` 属于 guard-defined evidence（守卫定义证据），因为 planning-review（规划审查）原流程没有稳定可检查产物。系统 MUST NOT 要求 planning-review（规划审查）Skill（技能）修改自身只读审查边界。

#### Scenario: 注册 planning-review pass marker
- **WHEN** 用户级 Guard Profile（守卫画像）配置 Comet planning-review gate
- **THEN** `planning_review_pass` 和 `cross_agent_review_pass` MUST use the same guard-defined evidence（守卫定义证据）默认路径 shape（形状）
- **AND** `cross_agent_review_pass` MUST use `artifact_id`（产物编号）值 `cross_agent_review_pass`
