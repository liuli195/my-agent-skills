# comet-agent-review-gate Specification

## Purpose
TBD - created by archiving change add-comet-agent-review-gate. Update Purpose after archive.
## Requirements
### Requirement: Comet review gate 不改变阶段链
系统 MUST 在不新增 Comet phase（阶段）的前提下支持 build 到 verify 之间的 agent review gate（代理审查门禁）。

#### Scenario: 原始 Comet 阶段链保持不变
- **WHEN** 用户运行原始 Comet 流程
- **THEN** 系统仍按 `open -> design -> build -> verify -> archive` 阶段链推进
- **AND** review gate（审查门禁）只由已安装并启用的 Global Command Guard（全局命令守卫点）触发
- **AND** 未安装、未启用或未匹配该用户级全局守卫时，Comet 原始命令行为保持不变

#### Scenario: build 完成命令进入门禁
- **WHEN** Comet build 阶段完成，主 agent 准备执行 build 阶段守卫收尾命令
- **THEN** 系统在 `comet-guard.sh <change> build --apply` 执行前检查跨 agent review 的 pass marker（通过标记）
- **AND** 系统不得把 `comet-guard.sh <change> verify --apply` 作为主要拦截点，因为该命令用于 verify 完成后的状态推进

#### Scenario: 命令模式覆盖实际调用形态
- **WHEN** 用户级 Global Command Guard（全局命令守卫点）配置 Comet review gate
- **THEN** command patterns（命令模式）MUST 覆盖直接调用 `comet-guard.sh <change> build --apply`
- **AND** command patterns MUST 覆盖路径调用，例如 `<path>/comet-guard.sh <change> build --apply`
- **AND** command patterns MUST 覆盖环境变量脚本调用，例如 `"$COMET_BASH" "$COMET_GUARD" <change> build --apply`
- **AND** command patterns MUST NOT 以 `comet-guard.sh <change> verify --apply` 作为主要匹配边界

### Requirement: Comet review gate 使用用户级 Global Command Guard

系统 MUST 使用用户级 Global Command Guard（全局命令守卫点）表达 Comet verify（验证）前的 review gate（审查门禁），但 hotfix（热修复）和 tweak（小改）workflow（工作流）不需要 cross-agent-review（跨代理审查）通过标记。

#### Scenario: full workflow 继续要求 cross-agent-review

- **WHEN** Comet full（完整）workflow（工作流）完成 build（构建）阶段并准备执行 `comet-guard.sh <change> build --apply`
- **AND** 当前 change（变更）和当前 HEAD（提交头）没有有效 cross-agent-review（跨代理审查）pass marker（通过标记）
- **THEN** Global Command Guard（全局命令守卫点）拒绝该命令

#### Scenario: hotfix workflow 不触发 cross-agent-review 门禁

- **WHEN** Comet hotfix（热修复）workflow（工作流）完成 build（构建）阶段并准备执行 `comet-guard.sh <change> build --apply`
- **THEN** Global Command Guard（全局命令守卫点）不得因为缺少 cross-agent-review（跨代理审查）pass marker（通过标记）拒绝该命令

#### Scenario: tweak workflow 不触发 cross-agent-review 门禁

- **WHEN** Comet tweak（小改）workflow（工作流）完成 build（构建）阶段并准备执行 `comet-guard.sh <change> build --apply`
- **THEN** Global Command Guard（全局命令守卫点）不得因为缺少 cross-agent-review（跨代理审查）pass marker（通过标记）拒绝该命令

### Requirement: Comet review gate 通过产物注册层校验 pass marker

系统 MUST 通过 Agent Guard artifacts.yaml 产物注册层引用 cross-agent-review（跨代理审查）默认输出的 `review-pass.json`，并使用 Global Command Guard（全局命令守卫点）的 JSON predicate（JSON 谓词）校验该 pass marker（通过标记）。系统 MUST NOT 要求 cross-agent-review 修改默认输出目录、复制 pass marker 到另一套 evidence 目录，或改变 cross-agent-review 的边界行为。

#### Scenario: 注册 cross-agent-review pass marker

- **WHEN** 用户级 Guard Profile（守卫画像）配置 Comet review gate
- **THEN** `artifacts.yaml` 注册 `cross_agent_review_pass` 产物
- **AND** 该产物路径指向项目内 `.local/cross-agent-review/<change>/<head_ref_short>/review-pass.json`
- **AND** `<change>` 来自 Global Command Guard（全局命令守卫点）的命令捕获值
- **AND** `<head_ref_short>` 来自当前 Git HEAD 的 12 位短值
- **AND** Global Command Guard 通过 `artifact` 或 `artifact_id` 引用该注册产物，而不是直接声明独立 `evidence.path`

#### Scenario: pass marker 合法

- **WHEN** `review-pass.json` 存在于当前 change 和当前短 HEAD 对应目录
- **AND** `status` 为 `pass`、`change` 匹配当前 change、`head_ref` 匹配当前完整 HEAD、`blocking_findings` 为 0、`report` 存在且 `report_hash` 存在
- **THEN** Global Command Guard（全局命令守卫点）允许 Comet build 阶段守卫收尾命令继续执行

#### Scenario: pass marker 缺失

- **WHEN** review report（审查报告）存在但 `review-pass.json` 不存在
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet build 阶段守卫收尾命令
- **AND** deny（拒绝）输出包含失败原因、缺失产物、当前 change、当前 head ref 和来自 Guard Profile（守卫画像）配置的下一步提示

#### Scenario: deny 输出由画像配置承载

- **WHEN** Global Command Guard（全局命令守卫点）拒绝 `comet-guard.sh <change> build --apply`
- **THEN** deny（拒绝）输出 MUST 包含结构化 `reason`、`next`、`suggestion`、命令 captures（捕获值）和 failing guard（失败守卫）详情
- **AND** `reason`、`next` 和 `suggestion` MAY 使用 Guard Profile 中声明的场景化配置
- **AND** Runtime（运行时）只负责透传或渲染这些配置字段，调用方 MAY 根据这些字段选择后续动作
- **AND** 本系统 MUST NOT 在 Agent Guard 或 Comet 中实现 cross-agent-review 内部编排逻辑

#### Scenario: pass marker 过期

- **WHEN** `review-pass.json` 的 `head_ref` 不匹配当前完整 HEAD
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet build 阶段守卫收尾命令，并提示重新运行跨 agent review

### Requirement: review fail 表现为无有效 pass marker
系统 MUST 只通过 pass marker（通过标记）是否存在且有效来判断 Comet build 阶段守卫收尾命令能否继续。跨 agent review 的执行、修复和重新审查流程属于 cross-agent-review（跨代理审查）或调用方契约。

#### Scenario: 阻塞发现
- **WHEN** 跨 agent review 报告包含 CRITICAL 或 IMPORTANT findings（发现项）
- **THEN** cross-agent-review 不生成 pass marker（通过标记）
- **AND** Global Command Guard（全局命令守卫点）继续拒绝 Comet build 阶段守卫收尾命令
- **AND** Agent Guard 不解析 review report（审查报告）或决定修复流程

#### Scenario: 修复后重新审查
- **WHEN** 用户修复 blocking findings（阻塞发现）并更新 HEAD
- **THEN** cross-agent-review 或调用方负责重新审查并使用新 head ref 生成新的 `review-pass.json`
- **AND** Agent Guard 只校验新 pass marker 是否匹配当前命令和当前 HEAD

### Requirement: Comet planning-review gate protects design completion

系统 MUST 支持通过用户级 Global Command Guard（全局命令守卫点）在 Comet full workflow（完整工作流）从 design（设计）进入 build（构建）前校验 planning-review（规划审查）通过标记。该门禁 MUST 不新增 Comet phase（阶段），MUST 不新增 wrapper（包装命令），MUST 不让 Agent Guard（代理守卫）执行 planning-review（规划审查）内部流程。

#### Scenario: design 完成命令进入 planning-review 门禁

- **WHEN** Comet full workflow（完整工作流）完成 design（设计）阶段，主 agent（代理）准备执行 design 阶段守卫收尾命令
- **THEN** 系统在 `comet-guard.sh <change> design --apply` 执行前检查 planning-review（规划审查）的 pass marker（通过标记）
- **AND** 系统不得把 `comet-guard.sh <change> build --apply` 或 `comet-guard.sh <change> verify --apply` 作为 planning-review（规划审查）的主要匹配边界

#### Scenario: planning-review 命令模式覆盖实际调用形态

- **WHEN** 用户级 Global Command Guard（全局命令守卫点）配置 Comet planning-review gate（comet 规划审查门禁）
- **THEN** command patterns（命令模式）MUST 覆盖直接调用 `comet-guard.sh <change> design --apply`
- **AND** command patterns（命令模式）MUST 覆盖 POSIX path（POSIX 路径）调用，例如 `<path>/comet-guard.sh <change> design --apply`
- **AND** command patterns（命令模式）MUST 覆盖 Windows path（Windows 路径）调用，例如 `<path>\comet-guard.sh <change> design --apply`
- **AND** command patterns（命令模式）MUST 覆盖环境变量脚本调用，例如 `"$COMET_BASH" "$COMET_GUARD" <change> design --apply`
- **AND** command patterns（命令模式）MUST 捕获 `subject_id`
- **AND** `subject_id` 的值 MUST 是当前 Comet change（变更）编号

### Requirement: Comet gate configuration stays outside Agent Guard plugin

系统 MUST NOT 在 Agent Guard Plugin（代理守卫插件）中发布 Comet-specific（Comet 专用）Guard Profile（守卫画像）配置模板。Comet planning-review gate（comet 规划审查门禁）和 Comet cross-agent-review gate（comet 跨代理审查门禁）MUST 由用户级或目标环境自己的 Guard Profile（守卫画像）配置表达。

#### Scenario: 插件包不包含 Comet review gate 模板

- **WHEN** Agent Guard Plugin（代理守卫插件）被打包或验证
- **THEN** 插件包 MUST NOT 要求存在 `skills/agent-guard/assets/templates/guard-profile/comet-review-gate`
- **AND** 插件包 MUST NOT 要求存在 `assets/templates/guard-profile/comet-review-gate`
- **AND** 插件包 MUST NOT 发布这些 Comet-specific（Comet 专用）Guard Profile（守卫画像）模板目录

#### Scenario: 运行时仍接受外部用户级配置

- **WHEN** 用户级或目标环境 Guard Profile（守卫画像）声明 Global Command Guard（全局命令守卫点）来保护 `comet-guard.sh <change> design --apply`
- **THEN** Agent Guard Runtime（代理守卫运行时）MUST 按通用 Global Command Guard（全局命令守卫点）机制评估该配置
- **AND** Runtime（运行时）不得要求该配置来自 Agent Guard Plugin（代理守卫插件）内置模板

### Requirement: Comet planning-review gate validates registered pass marker

系统 MUST 通过 Agent Guard artifacts.yaml（产物注册文件）注册 `planning_review_pass`（规划审查通过标记），并使用 Global Command Guard（全局命令守卫点）的 JSON predicate（JSON 谓词）校验该 marker（标记）。`planning_review_pass` 属于 guard-defined evidence（守卫定义证据），因为 planning-review（规划审查）原流程没有稳定可检查产物。系统 MUST NOT 要求 planning-review（规划审查）Skill（技能）修改自身只读审查边界。

#### Scenario: 注册 planning-review pass marker

- **WHEN** 用户级 Guard Profile（守卫画像）配置 Comet planning-review gate（comet 规划审查门禁）
- **THEN** `artifacts.yaml` MUST 注册 `planning_review_pass` 产物
- **AND** 该产物路径 MUST 指向 Agent Guard（代理守卫）默认 evidence（证据）目录 `.local/guard/evidence/<profile_id>/<artifact_id>/<subject_id>/<head_ref_short>/pass.json`
- **AND** `<artifact_id>` MUST 为 `planning_review_pass`
- **AND** `<subject_id>` MUST 来自 Global Command Guard（全局命令守卫点）捕获的 `subject_id`
- **AND** `<head_ref_short>` MUST 来自当前 Git HEAD（代码版本）的 12 位短值
- **AND** Global Command Guard（全局命令守卫点）MUST 通过 `artifact` 或 `artifact_id` 引用该注册产物，而不是直接声明独立 `evidence.path`
- **AND** `cross_agent_review_pass` MUST continue to register the existing cross-agent-review（跨代理审查）path `.local/cross-agent-review/<change>/<head_ref_short>/review-pass.json` without copying that artifact into `.local/guard/evidence`

#### Scenario: planning-review pass marker 合法

- **WHEN** `pass.json` 存在于当前 change（变更）和当前短 HEAD（代码版本）对应目录
- **AND** `status` 为 `pass`
- **AND** `schema_version` 为 `guard-evidence/v1`
- **AND** `producer` 为 `planning-review`
- **AND** `profile_id` 匹配当前 Guard Profile（守卫画像）
- **AND** `artifact_id` 为 `planning_review_pass`
- **AND** `subject_type` 为 `comet-change`
- **AND** `subject_id` 匹配当前 change（变更）
- **AND** `head_ref` 匹配当前完整 HEAD（代码版本）
- **AND** `head_ref_short` 匹配当前 12 位短 HEAD（代码版本）
- **AND** `blocking_findings` 为 0
- **AND** `scope` 存在
- **AND** `report_hash` 存在
- **AND** `created_at` 存在
- **THEN** Global Command Guard（全局命令守卫点）允许 Comet design 阶段守卫收尾命令继续执行

#### Scenario: 主 agent 写入 planning-review pass marker

- **WHEN** 主 agent（代理）完成 planning-review（规划审查）
- **AND** 审查结论没有 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）
- **THEN** 主 agent（代理）MUST 写入 `planning_review_pass` 通过标记
- **AND** 该写入 MUST 使用 Agent Guard（代理守卫）定义的 guard-defined evidence（守卫定义证据）路径和 `guard-evidence/v1` 字段契约
- **AND** planning-review（规划审查）Skill（技能）本身不得写入该 marker（标记）
- **AND** Agent Guard Runtime（代理守卫运行时）不得生成该 marker（标记）

#### Scenario: planning-review pass marker 字段无效

- **WHEN** `pass.json` 存在
- **AND** 其中 `schema_version`、`status`、`producer`、`profile_id`、`artifact_id`、`subject_type`、`subject_id`、`head_ref`、`head_ref_short`、`blocking_findings`、`scope`、`report_hash` 或 `created_at` 任一字段缺失或不匹配当前上下文
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet design 阶段守卫收尾命令
- **AND** deny（拒绝）输出 MUST 包含失败字段详情

#### Scenario: planning-review pass marker 缺失

- **WHEN** 当前 change（变更）和当前 HEAD（代码版本）没有有效 `planning_review_pass` 产物
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet design 阶段守卫收尾命令
- **AND** deny（拒绝）输出 MUST 包含失败原因、缺失产物、当前 change（变更）、当前 head ref（代码版本）和来自 Guard Profile（守卫画像）配置的下一步提示

#### Scenario: planning-review pass marker 过期

- **WHEN** `pass.json` 的 `head_ref` 不匹配当前完整 HEAD（代码版本）
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet design 阶段守卫收尾命令，并提示重新运行 planning-review（规划审查）

#### Scenario: planning-review 有阻断发现

- **WHEN** planning-review（规划审查）报告包含 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）
- **THEN** 调用方不得生成 `planning_review_pass` 通过标记
- **AND** 调用方不得复用旧的 `planning_review_pass` 通过标记
- **AND** Global Command Guard（全局命令守卫点）继续拒绝 Comet design 阶段守卫收尾命令
- **AND** Agent Guard（代理守卫）不解析 planning-review（规划审查）报告或决定修复流程

