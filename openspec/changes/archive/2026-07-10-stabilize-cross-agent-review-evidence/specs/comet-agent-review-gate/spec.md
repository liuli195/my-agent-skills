## MODIFIED Requirements

### Requirement: Comet review gate 通过产物注册层校验 pass marker
系统 MUST 通过 Agent Guard `artifacts.yaml`（代理守卫产物注册文件）注册 `cross_agent_review_pass`（跨代理审查通过标记），并使用 Global Command Guard（全局命令守卫点）的 JSON predicate（数据谓词）校验该 marker（标记）。`cross_agent_review_pass` 属于 guard-defined evidence（守卫定义证据），因为通过结论由主 agent（主代理）读取 review report（审查报告）和 review state（审查状态）后作出；主代理 MUST 通过 Agent Guard（代理守卫）的通用 `record-evidence`（记录证据）入口写入。系统 MUST NOT 在 Agent Guard（代理守卫）中实现 Cross Agent Review（跨代理审查）内部流程。

#### Scenario: 注册 cross-agent-review pass marker
- **WHEN** 用户级 Guard Profile（守卫画像）配置 Comet review gate（双星审查门禁）
- **THEN** `artifacts.yaml`（产物注册文件） MUST 把 `cross_agent_review_pass` 注册为 `type: json`（数据类型）、`owner: agent-guard`（代理守卫拥有）的产物
- **AND** 该产物路径 MUST 指向 Agent Guard（代理守卫）默认 evidence（证据）目录 `.local/guard/evidence/<profile_id>/cross_agent_review_pass/<subject_id>/<head_ref_short>/pass.json`
- **AND** `<subject_id>` MUST 来自 Global Command Guard（全局命令守卫点）的命令捕获值，Comet（双星流程）场景下等于 `<change>`
- **AND** `<head_ref_short>` MUST 来自当前 Git HEAD（代码版本）的 12 位短值
- **AND** Global Command Guard（全局命令守卫点） MUST 通过 `artifact` 或 `artifact_id` 引用该注册产物，而不是直接声明独立 `evidence.path`

#### Scenario: 主代理记录 cross-agent-review 通过证据
- **WHEN** 主代理读取当前提交的 `review-report.md`（审查报告）和 `review-state.json`（审查状态文件）
- **AND** 主代理确认两个角色结果有效且没有未处理的 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）finding（发现项）
- **THEN** 主代理 MUST 显式调用 Agent Guard（代理守卫）`record-evidence`（记录证据）并提供现有门禁所需业务字段
- **AND** Cross Agent Review（跨代理审查） MUST NOT 写入该证据

#### Scenario: pass marker 合法
- **WHEN** `pass.json` 存在于当前 change（变更）和当前短 HEAD（代码版本）对应目录
- **AND** `status` 为 `pass`、`schema_version` 为 `guard-evidence/v1`、`producer` 为 `cross-agent-review`、`artifact_id` 为 `cross_agent_review_pass`、`subject_id` 匹配当前 change、`head_ref` 匹配当前完整 HEAD、`head_ref_short` 匹配当前短 HEAD、`blocking_findings` 为 0、`report` 存在且 `report_hash` 存在
- **THEN** Global Command Guard（全局命令守卫点）允许 Comet build（双星构建）阶段守卫收尾命令继续执行

#### Scenario: pass marker 缺失
- **WHEN** review report（审查报告）存在但 `cross_agent_review_pass` 的 `pass.json` 不存在
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet build（双星构建）阶段守卫收尾命令
- **AND** deny（拒绝）输出包含失败原因、缺失产物、当前 change（变更）、当前 head ref（提交头）和来自 Guard Profile（守卫画像）配置的下一步提示

#### Scenario: pass marker 过期
- **WHEN** `pass.json` 的 `head_ref` 不匹配当前完整 HEAD（提交头）
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet build（双星构建）阶段守卫收尾命令，并提示运行当前提交的真实审查或受限 `revalidate`（重新校验）

### Requirement: review fail 表现为无有效 pass marker
系统 MUST 只通过 pass marker（通过标记）是否存在且有效来判断 Comet build（双星构建）阶段守卫收尾命令能否继续。Cross Agent Review（跨代理审查）的执行、修复、重试和重新校验流程属于 Cross Agent Review（跨代理审查）或调用方契约。

#### Scenario: 阻塞发现
- **WHEN** Cross Agent Review（跨代理审查）报告包含未处理的 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）finding（发现项）
- **THEN** 主 agent（主代理） MUST NOT 调用 `record-evidence`（记录证据）生成 pass marker（通过标记）
- **AND** Global Command Guard（全局命令守卫点）继续拒绝 Comet build（双星构建）阶段守卫收尾命令
- **AND** Agent Guard（代理守卫） MUST NOT 解析 review report（审查报告）或决定修复流程

#### Scenario: 修复后重新审查
- **WHEN** 用户修复 blocking findings（阻塞发现）并更新 HEAD（提交头）
- **THEN** 调用方负责运行真实 review（审查），或在全部变化满足声明式机械策略时运行 `revalidate`（重新校验）
- **AND** 主 agent（主代理）只在读取当前提交的新报告和状态并作出通过结论后调用 `record-evidence`（记录证据）
- **AND** Agent Guard（代理守卫）只校验新 pass marker（通过标记）是否匹配当前命令和当前 HEAD（提交头）

### Requirement: Comet planning-review gate validates registered pass marker
系统 MUST 通过 Agent Guard `artifacts.yaml`（代理守卫产物注册文件）注册 `planning_review_pass`（规划审查通过标记），并使用 Global Command Guard（全局命令守卫点）的 JSON predicate（数据谓词）校验该 marker（标记）。`planning_review_pass` 属于 guard-defined evidence（守卫定义证据），因为 Planning Review（规划审查）原流程保持只读；主代理 MUST 根据其五字段结果作出结论并通过通用 `record-evidence`（记录证据）入口写入。

#### Scenario: 注册 planning-review pass marker
- **WHEN** 用户级 Guard Profile（守卫画像）配置 Comet planning-review gate（双星规划审查门禁）
- **THEN** `planning_review_pass` 和 `cross_agent_review_pass` MUST 使用相同的 guard-defined evidence（守卫定义证据）默认路径形状
- **AND** `planning_review_pass` MUST 注册为 `type: json`（数据类型）和 `owner: agent-guard`（代理守卫拥有）
- **AND** `planning_review_pass` MUST 使用 `artifact_id`（产物编号）值 `planning_review_pass`
- **AND** `cross_agent_review_pass` MUST 使用 `artifact_id`（产物编号）值 `cross_agent_review_pass`

#### Scenario: 主代理构造 planning review 证据
- **WHEN** Planning Review（规划审查）按只读契约输出 `mode`（模式）、`scope`（范围）、`blocking`（阻断项）、`findings`（发现项）和 `decision`（结论）五个字段
- **AND** 主代理确认 `decision` 为 `PASS`（放行）且没有未处理阻断项
- **THEN** 主代理 MUST 把该五字段 JSON object（数据对象）作为业务字段 `review`（审查结果）传给 `record-evidence`（记录证据）
- **AND** 主代理 MUST 同时提供现有门禁检查使用的平面字段 `blocking_findings`、`scope`、`report` 和 `report_hash`
- **AND** `report` MUST 为 `inline:review`
- **AND** 规范 JSON（数据对象）字节串 MUST 使用 UTF-8（统一编码）、按键排序、紧凑分隔符、保留非 ASCII（非英文字符）且没有尾随换行
- **AND** `report_hash` MUST 使用 `sha256:<lowercase hex>`（安全哈希小写十六进制）格式，并等于该规范字节串的 SHA-256（安全哈希）

#### Scenario: planning review 技能保持只读
- **WHEN** Planning Review（规划审查）完成审查
- **THEN** Planning Review（规划审查）技能 MUST NOT 写入 Agent Guard（代理守卫）证据或调用 `record-evidence`（记录证据）
- **AND** 只有主代理 MAY 在语义通过后显式调用通用入口

#### Scenario: planning review pass marker 合法
- **WHEN** 当前 change（变更）和当前 HEAD（提交头）的 `planning_review_pass` 存在
- **AND** marker（标记）的现有平面字段满足 Guard Profile（守卫画像）声明的所有 JSON predicate（数据谓词）
- **THEN** Global Command Guard（全局命令守卫点）允许 Comet design（双星设计）阶段守卫收尾命令继续执行
