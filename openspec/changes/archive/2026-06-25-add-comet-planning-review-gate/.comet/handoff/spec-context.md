# Comet Spec Context

- Change: add-comet-planning-review-gate
- Phase: design
- Mode: beta
- Context hash: 8053c3f63c1e6c00a3c7131572ee3e5e7a9c0aea23135d31abe4048dc310f453

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/add-comet-planning-review-gate/proposal.md
- SHA256: e71433e65b74c92b0ec774bec84ab3102770393b1712c592699d09c06944922f
- Source: openspec/changes/add-comet-planning-review-gate/design.md
- SHA256: 2b383a8857e79a5147321a571b5c43d112f40e0504a3588105ebf880b8be724e
- Source: openspec/changes/add-comet-planning-review-gate/tasks.md
- SHA256: 40e85dceb4211f3553cca978299454c2aa386ed9b0dc0ada1c1d9a08c4c9a324
- Source: openspec/changes/add-comet-planning-review-gate/specs/agent-guard-core/spec.md
- SHA256: e3a07b4184d9217c3bccaee43b193b5d91c5cc03d6ac9aea41940508e02ece1e
- Source: openspec/changes/add-comet-planning-review-gate/specs/agent-guard-plugin-runtime/spec.md
- SHA256: b1c58d402b87a329cf61334cdf680d5515660ed1c7112787aca3260fb11ae256
- Source: openspec/changes/add-comet-planning-review-gate/specs/comet-agent-review-gate/spec.md
- SHA256: ade530547626fbb09436740589257cf5ec9bfb3d2cb6f701646eb35c1c72e392

## Acceptance Projection

## openspec/changes/add-comet-planning-review-gate/specs/agent-guard-core/spec.md

- Source: openspec/changes/add-comet-planning-review-gate/specs/agent-guard-core/spec.md
- Lines: 1-27
- SHA256: e3a07b4184d9217c3bccaee43b193b5d91c5cc03d6ac9aea41940508e02ece1e

```md
## MODIFIED Requirements

### Requirement: 守卫画像来源元数据

系统 MUST 在每个业务 Guard Profile（守卫画像）manifest（清单）中记录来源元数据，并要求 `grill-with-docs-confirmed-notes` 来源具备 confirmed（已确认）状态。系统 MAY 接受明确列入白名单的通用内置 Guard Profile（守卫画像）模板来源，但 MUST NOT 为具体业务 workflow（工作流）保留内置来源白名单。

#### Scenario: 已确认来源清单

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用 `source.kind: grill-with-docs-confirmed-notes`
- **THEN** 该 manifest（清单）同时包含 `source.status: confirmed`

#### Scenario: 通用内置模板来源

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用通用内置模板来源，例如 `built-in-minimal-sample`
- **THEN** Validator（校验器）MAY 接受该来源类型
- **AND** Validator（校验器）继续校验该 Guard Profile（守卫画像）的其他文件和引用

#### Scenario: 业务专用内置来源不再被接受

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用业务 workflow（工作流）专用来源，例如 `source.kind: built-in-comet-review-gate`
- **THEN** Validator（校验器）MUST 拒绝该来源类型
- **AND** Agent Guard Plugin（代理守卫插件）不得通过该来源类型表达 Comet（流程）业务配置

#### Scenario: 模板记录保持未确认

- **WHEN** 系统创建 `confirmed-notes.yaml` 模板
- **THEN** 模板状态保持为 `needs_confirmation`，直到调研流程明确确认它
```

## openspec/changes/add-comet-planning-review-gate/specs/agent-guard-plugin-runtime/spec.md

- Source: openspec/changes/add-comet-planning-review-gate/specs/agent-guard-plugin-runtime/spec.md
- Lines: 1-54
- SHA256: b1c58d402b87a329cf61334cdf680d5515660ed1c7112787aca3260fb11ae256

```md
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
```

## openspec/changes/add-comet-planning-review-gate/specs/comet-agent-review-gate/spec.md

- Source: openspec/changes/add-comet-planning-review-gate/specs/comet-agent-review-gate/spec.md
- Lines: 1-103
- SHA256: ade530547626fbb09436740589257cf5ec9bfb3d2cb6f701646eb35c1c72e392

```md
## ADDED Requirements

### Requirement: Comet planning-review gate protects design completion

系统 MUST 支持通过用户级 Global Command Guard（全局命令守卫点）在 Comet full workflow（完整工作流）从 design（设计）进入 build（构建）前校验 planning-review（规划审查）通过标记。该门禁 MUST 不新增 Comet phase（阶段），MUST 不新增 wrapper（包装命令），MUST 不让 Agent Guard（代理守卫）执行 planning-review（规划审查）内部流程。

#### Scenario: design 完成命令进入 planning-review 门禁

- **WHEN** Comet full workflow（完整工作流）完成 design（设计）阶段，主 agent（代理）准备执行 design 阶段守卫收尾命令
- **THEN** 系统在 `comet-guard.sh <change> design --apply` 执行前检查 planning-review（规划审查）的 pass marker（通过标记）
- **AND** 系统不得把 `comet-guard.sh <change> build --apply` 或 `comet-guard.sh <change> verify --apply` 作为 planning-review（规划审查）的主要匹配边界

#### Scenario: planning-review 命令模式覆盖实际调用形态

- **WHEN** 用户级 Global Command Guard（全局命令守卫点）配置 Comet planning-review gate（comet 规划审查门禁）
- **THEN** command patterns（命令模式）MUST 覆盖直接调用 `comet-guard.sh <change> design --apply`
- **AND** command patterns（命令模式）MUST 覆盖路径调用，例如 `<path>/comet-guard.sh <change> design --apply`
- **AND** command patterns（命令模式）MUST 覆盖环境变量脚本调用，例如 `"$COMET_BASH" "$COMET_GUARD" <change> design --apply`
- **AND** command patterns（命令模式）MUST 捕获 `change`

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
- **AND** 该产物路径 MUST 指向 Agent Guard（代理守卫）默认 evidence（证据）目录 `.local/guard/evidence/<profile_id>/planning_review_pass/<change>/<head_ref_short>/pass.json`
- **AND** `<change>` MUST 来自 Global Command Guard（全局命令守卫点）的命令捕获值
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
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
