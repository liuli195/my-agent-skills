## Purpose

本 capability（能力）定义 Agent Guard（代理守卫）核心行为的当前基线契约：确认调研门禁、Guard Profile（守卫画像）来源元数据、被守卫对象解耦、Runtime（运行时）通用边界、状态权限、守卫点推进和初始化前画像校验。
## Requirements
### Requirement: 确认调研门禁
系统 MUST 在生成、更新或初始化任何业务 Guard Profile（守卫画像）前，要求先完成已确认的 `$grill-with-docs`（带文档拷问方法）调研。

#### Scenario: 缺少已确认调研记录
- **WHEN** 用户或 agent（代理）尝试在没有 `grill_with_docs.status: confirmed` 的情况下生成、更新或初始化业务 Guard Profile（守卫画像）
- **THEN** 系统返回 needs-confirmation（需要确认）结果，并且不创建或初始化该画像

#### Scenario: 接受已确认调研记录
- **WHEN** 输入记录包含 `grill_with_docs.status: confirmed`
- **THEN** 系统可以从这些记录生成 Guard Profile（守卫画像）草案，并继续进入校验

### Requirement: 守卫画像来源元数据

系统 MUST 在每个业务 Guard Profile（守卫画像）manifest（清单）中记录来源元数据，并要求 `grill-with-docs-confirmed-notes` 来源具备 confirmed（已确认）状态。系统 MAY 接受明确列入白名单的通用内置 Guard Profile（守卫画像）模板来源，但 MUST NOT 为具体业务 workflow（工作流）保留内置来源白名单。

#### Scenario: 已确认来源清单

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用 `source.kind: grill-with-docs-confirmed-notes`
- **THEN** 该 manifest（清单）同时包含 `source.status: confirmed`

#### Scenario: 通用内置模板来源

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用通用内置模板来源，例如 `built-in-minimal-sample`
- **THEN** Validator（校验器）MAY 接受该来源类型
- **AND** Validator（校验器）继续校验该 Guard Profile（守卫画像）的其他文件和引用

#### Scenario: 目标环境配置来源

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用 `source.kind: target-environment-config`
- **THEN** Validator（校验器）MAY 接受该来源类型
- **AND** Validator（校验器）继续校验该 Guard Profile（守卫画像）的其他文件和引用

#### Scenario: 业务专用内置来源不再被接受

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用业务 workflow（工作流）专用来源，例如 `source.kind: built-in-comet-review-gate`
- **THEN** Validator（校验器）MUST 拒绝该来源类型
- **AND** Agent Guard Plugin（代理守卫插件）不得通过该来源类型表达 Comet（流程）业务配置

#### Scenario: 模板记录保持未确认

- **WHEN** 系统创建 `confirmed-notes.yaml` 模板
- **THEN** 模板状态保持为 `needs_confirmation`，直到调研流程明确确认它

### Requirement: 被守卫对象解耦
系统 MUST 把 Agent Guard（代理守卫）行为保留在被守卫对象外部，并且不得要求修改被守卫的 Skill（技能）、workflow（工作流）、node（节点）、command（命令）、artifact lifecycle（产物生命周期）、session behavior（会话行为）或临时任务。

#### Scenario: 守卫既有 Skill
- **WHEN** 用户为既有 Skill（技能）创建 Guard Profile（守卫画像）
- **THEN** 系统把守卫规则保存在 Guard Profile（守卫画像）中，不重写目标 Skill 入口

#### Scenario: 守卫非 Skill 工作流
- **WHEN** 用户为 workflow（工作流）或临时任务创建 Guard Profile（守卫画像）
- **THEN** 系统把该目标建模为被守卫对象，并且不假设它一定是 Skill（技能）

### Requirement: 画像拥有业务规则
系统 MUST 把具体业务守卫规则保存在 Guard Profile（守卫画像）配置中，同时保持 Runtime（运行时）和 Agent Guard Skill（代理守卫技能）入口逻辑通用。Agent Guard MUST NOT contain business workflow orchestration（业务流程编排） or hard-coded business logic（硬编码业务逻辑） for any guarded target.

#### Scenario: Runtime 处理守卫事件
- **WHEN** Runtime（运行时）收到标准化守卫事件
- **THEN** Runtime 加载当前 Guard Profile（守卫画像），并评估画像定义的 state machine（状态机）、permissions（权限）、guard checks（守卫检查）、artifacts（产物）和 brief（简报）语义

#### Scenario: Runtime 保持通用
- **WHEN** 新增一个被守卫的业务流程
- **THEN** Runtime（运行时）不为该具体流程新增硬编码规则
- **AND** Runtime 只执行通用机制，例如命令匹配、上下文提取、artifact（产物）解析、JSON predicate（JSON 谓词）校验、allow/deny（允许/拒绝）结果和 audit（审计）记录

#### Scenario: Skill 入口不承载业务编排
- **WHEN** Agent Guard Skill（代理守卫技能）文档说明某个 Global Command Guard（全局命令守卫点）的 deny（拒绝）结果
- **THEN** 文档可以解释通用返回字段，例如 reason、next、suggestion、captures、failing guards 和 artifact/evidence 信息
- **AND** 这些字段的场景化内容 MAY 来自 Guard Profile（守卫画像）中的 deny 配置
- **AND** Runtime（运行时）只负责按通用机制透传或渲染这些配置字段
- **AND** 文档不得实现或复写被守卫业务流程的下一步执行顺序

#### Scenario: 外部 Skill 拥有自身流程
- **WHEN** 守卫点依赖另一个 Skill（技能）或 workflow（工作流）生成外部 evidence（证据）
- **THEN** Agent Guard 只能校验该 evidence 是否满足 Guard Profile 声明
- **AND** Guard Profile MAY 配置 deny reason、next 和 suggestion 来提示调用方后续处理方向
- **AND** Agent Guard 不得把这些提示升级为内置流程，也不得实现、派发或复制该外部 Skill 的内部流程
- **AND** 该外部流程的输入准备、执行步骤、工作区约束、测试约束和结果生成规则 MUST 保留在对应 Skill 或调用方契约中

#### Scenario: Comet review gate 不侵入 cross-agent-review
- **WHEN** Global Command Guard（全局命令守卫点）用于守卫 Comet build completion（构建完成）命令
- **THEN** Agent Guard 可以匹配命令、读取 `cross_agent_review_pass` artifact（产物）并校验 `review-pass.json`
- **AND** Comet review gate 的 Guard Profile MAY 配置指向生成 pass marker（通过标记）的 deny 提示
- **AND** Agent Guard 不得准备 cross-agent-review 输入、检查 cross-agent-review 的工作区前置条件、派发 reviewer agent（审查代理）或推进 Comet phase（阶段）

### Requirement: 显式状态权限
系统 MUST 把 Guard Profile（守卫画像）中的 `states[].permissions` 作为动态 `allow`、`ask` 和 `deny` 决策的权威来源。

#### Scenario: 配置 deny 规则
- **WHEN** 当前状态声明了匹配的 `deny` permission（权限）
- **THEN** Runtime（运行时）返回绑定到当前明确 Guard Instance（守卫实例）的 deny（拒绝）结果

#### Scenario: 初始化不创建 deny 规则
- **WHEN** project（项目级）、user（用户级）或 plugin（插件）初始化运行
- **THEN** 初始化不会隐式创建、修改或授权 `deny` 规则

### Requirement: 守卫点状态推进
系统 MUST 只在当前状态转换存在唯一匹配候选，且所有必需 guard checks（守卫检查）和 artifacts（产物）通过或具备有效显式 override（覆盖）时推进状态。

#### Scenario: 守卫点失败
- **WHEN** 必需 guard point（守卫点）失败且没有有效 override（覆盖）
- **THEN** Runtime（运行时）保持当前状态不变，并报告失败的 guard point（守卫点）

#### Scenario: 转换歧义
- **WHEN** 一个 state completion event（状态完成事件）匹配多个 transition（转换）
- **THEN** Runtime（运行时）把该画像视为对当前事件无效，并且不推进状态

### Requirement: 画像校验边界
系统 MUST 在初始化或同步前校验 Guard Profile（守卫画像）的完整性，并拒绝未确认来源或过时画像契约。

#### Scenario: 拒绝未确认画像
- **WHEN** 校验发现业务画像来源是 `grill-with-docs-confirmed-notes`，但 source status（来源状态）不是 `confirmed`
- **THEN** 校验在 project-level（项目级）或 user-level（用户级）初始化前失败

#### Scenario: 拒绝过时契约
- **WHEN** 校验发现 accepted plugin-runtime contract（已接受插件运行时契约）已删除的过时必需文件或字段
- **THEN** 校验报告该过时契约，而不是静默接受

### Requirement: JSON artifact 内容守卫检查
系统 MUST 支持 Guard Point（守卫点）声明通用 `json_artifact` check，用于读取 profile-owned JSON artifact（画像拥有的 JSON 产物）并校验其内容。

#### Scenario: JSON 内容检查通过
- **WHEN** Guard Point 声明 `json_artifact` check，目标 artifact 存在、JSON 可解析，且所有声明谓词均通过
- **THEN** Runtime（运行时）把该 check 视为通过，并继续评估同一 Guard Point 的后续检查

#### Scenario: JSON 内容检查失败
- **WHEN** Guard Point 声明 `json_artifact` check，目标 artifact 存在且 JSON 可解析，但字段值不满足声明谓词
- **THEN** Runtime（运行时）保持当前 Guard Instance（守卫实例）状态不变，并返回 `guard_failed`
- **THEN** audit（审计）记录失败的 artifact id、field path（字段路径）、predicate（谓词）、expected（期望值）和 actual（实际值）

#### Scenario: JSON 文件无法解析
- **WHEN** Guard Point 声明 `json_artifact` check，目标 artifact 存在但不是合法 JSON
- **THEN** Runtime（运行时）返回 `guard_failed`
- **THEN** audit（审计）记录 `invalid_json_artifact` 和目标 artifact id

### Requirement: JSON artifact 谓词集合
系统 MUST 为 `json_artifact` check 支持受限、声明式、可验证的谓词集合，并拒绝执行任意脚本或表达式。

#### Scenario: 字段存在检查
- **WHEN** check 声明 `predicate: exists` 和 `field`
- **THEN** Runtime（运行时）要求该字段路径在 JSON 对象中存在

#### Scenario: 字段等值检查
- **WHEN** check 声明 `predicate: equals` 和 `value`
- **THEN** Runtime（运行时）要求字段路径的实际值等于声明值

#### Scenario: 数字比较检查
- **WHEN** check 声明 `predicate: number_lte` 或 `predicate: number_gte`
- **THEN** Runtime（运行时）要求字段路径的实际值和声明值均为数字，并按对应比较规则判断

#### Scenario: 数组元素检查
- **WHEN** check 声明 `predicate: array_none` 或 `predicate: array_all`
- **THEN** Runtime（运行时）要求目标字段是数组，并按元素子谓词判断每个数组元素

### Requirement: JSON artifact check 声明校验
系统 MUST 在 Guard Profile（守卫画像）校验阶段拒绝无效或不支持的 `json_artifact` check 声明。

#### Scenario: 未知谓词
- **WHEN** Guard Profile（守卫画像）包含 `json_artifact` check 且 `predicate` 不在支持列表内
- **THEN** validator（校验器）报告清晰错误，并拒绝该画像作为可初始化画像

#### Scenario: 缺少 artifact 引用
- **WHEN** Guard Profile（守卫画像）包含 `json_artifact` check 但未声明 `artifact` 或 `artifact_id`
- **THEN** validator（校验器）报告缺少 artifact 引用

#### Scenario: 引用不存在的 artifact
- **WHEN** Guard Profile（守卫画像）包含 `json_artifact` check 且引用的 artifact id 不存在于 `artifacts.yaml`
- **THEN** validator（校验器）报告该引用无效

