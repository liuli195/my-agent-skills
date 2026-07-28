## ADDED Requirements

### Requirement: 确认调研门禁
系统 MUST 在生成、更新或初始化任何业务 Guard Profile（守卫画像）前，要求先完成已确认的 `$grill-with-docs`（带文档拷问方法）调研。

#### Scenario: 缺少已确认调研记录
- **WHEN** 用户或 agent（代理）尝试在没有 `grill_with_docs.status: confirmed` 的情况下生成、更新或初始化业务 Guard Profile（守卫画像）
- **THEN** 系统返回 needs-confirmation（需要确认）结果，并且不创建或初始化该画像

#### Scenario: 接受已确认调研记录
- **WHEN** 输入记录包含 `grill_with_docs.status: confirmed`
- **THEN** 系统可以从这些记录生成 Guard Profile（守卫画像）草案，并继续进入校验

### Requirement: 守卫画像来源元数据
系统 MUST 在每个业务 Guard Profile（守卫画像）manifest（清单）中记录来源元数据，并要求 `grill-with-docs-confirmed-notes` 来源具备 confirmed（已确认）状态。

#### Scenario: 已确认来源清单
- **WHEN** Guard Profile（守卫画像）manifest（清单）使用 `source.kind: grill-with-docs-confirmed-notes`
- **THEN** 该 manifest（清单）同时包含 `source.status: confirmed`

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
系统 MUST 把具体业务守卫规则保存在 Guard Profile（守卫画像）配置中，同时保持 Runtime（运行时）逻辑通用。

#### Scenario: Runtime 处理守卫事件
- **WHEN** Runtime（运行时）收到标准化守卫事件
- **THEN** Runtime 加载当前 Guard Profile（守卫画像），并评估画像定义的 state machine（状态机）、permissions（权限）、guard checks（守卫检查）、artifacts（产物）和 brief（简报）语义

#### Scenario: Runtime 保持通用
- **WHEN** 新增一个被守卫的业务流程
- **THEN** Runtime（运行时）不为该具体流程新增硬编码规则

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
