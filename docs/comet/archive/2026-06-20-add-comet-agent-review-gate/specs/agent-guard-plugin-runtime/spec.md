## MODIFIED Requirements

### Requirement: Global command guard configuration layout
系统 MUST 支持在 Guard Profile（守卫画像）目录中声明 `global-command-guards.yaml`，用于存放静态的 Global Command Guard（全局命令守卫点）配置。系统 MUST 区分静态配置作用域、运行态数据作用域和外部产物所在位置。

#### Scenario: 项目级静态配置
- **WHEN** 项目级 Guard Profile 声明全局命令守卫点
- **THEN** 配置文件 MUST 位于 `.agents/guards/<profile_id>/global-command-guards.yaml`

#### Scenario: 用户级静态配置
- **WHEN** 用户级 Guard Profile 声明全局命令守卫点
- **THEN** 配置文件 MUST 位于 `~/.agents/guards/<profile_id>/global-command-guards.yaml`

#### Scenario: 有效守卫 ID
- **WHEN** Runtime（运行时）加载任意 Global Command Guard
- **THEN** Runtime MUST 为该规则生成 effective guard id（有效守卫 ID）
- **AND** effective guard id MUST 使用 `<source_scope>:<profile_id>:<guard_id>`

#### Scenario: 同名守卫 ID 不跨来源冲突
- **WHEN** 两个不同 Guard Profile 或不同 source scope（来源作用域）声明相同 `guard_id`
- **THEN** Runtime（运行时）MUST 通过 effective guard id 区分它们
- **AND** Validator（校验器）不得要求跨 profile 全局唯一

#### Scenario: 同一文件内守卫 ID 必须唯一
- **WHEN** 同一个 `global-command-guards.yaml` 中出现重复 `guard_id`
- **THEN** Validator（校验器）MUST 报错

#### Scenario: 动态文件使用运行时目录
- **WHEN** Global Command Guard 读取或写入运行时动态材料
- **THEN** Runtime（运行时）MUST 使用 `.local/guard` 或用户级等价目录 `~/.agents/guard`
- **AND** Runtime 不得把全局命令守卫点的动态材料写入静态 Guard Profile 目录

#### Scenario: 项目上下文使用项目级运行目录
- **WHEN** Global Command Guard 守卫的命令作用于当前项目
- **THEN** Runtime（运行时）MUST 使用 `.local/guard` 记录该守卫的 audit（审计）和自身运行态材料
- **AND** 即使 Global Command Guard 的静态配置来自用户级 Guard Profile，Runtime 也不得默认把该项目命令的运行态材料写入 `~/.agents/guard`

#### Scenario: 用户作用域使用用户级运行目录
- **WHEN** Runtime 处理显式 user scope（用户作用域）的会话焦点实例、用户全局命令，或配置显式声明用户级运行态
- **THEN** Runtime（运行时）MUST 使用 `~/.agents/guard`

#### Scenario: Comet change review 通过产物注册读取项目产物
- **WHEN** Global Command Guard 用于守卫 Comet change build 完成命令
- **AND** 该守卫通过 `artifact` 或 `artifact_id` 引用 `artifacts.yaml` 中的 cross-agent-review pass marker（跨代理审查通过标记）
- **THEN** Runtime（运行时）MUST 按 `artifacts.yaml` 注册路径读取该外部产物
- **AND** 该产物 MAY 位于项目内 `.local/cross-agent-review/<change>/<head_ref>/review-pass.json`
- **AND** Runtime 不得要求 cross-agent-review 把该产物复制到 `.local/guard/evidence`
- **AND** Runtime 不得从 `~/.agents/guard` 读取该 Comet change 的通过证据

#### Scenario: 用户级安装不等于用户级运行态
- **WHEN** Agent Guard Plugin（代理守卫插件）安装在用户级
- **AND** 主 agent 在项目内触发 hook 或执行项目命令
- **THEN** Runtime（运行时）MUST 把该项目上下文的审计和自身运行态材料写入 `.local/guard`

### Requirement: Evidence checks
系统 MUST 支持 Global Command Guard 用 artifact reference（产物引用）或 legacy evidence path template（旧证据路径模板）读取 JSON evidence（JSON 证据），并使用命令上下文和运行时上下文执行检查。新集成 SHOULD 优先使用 `artifacts.yaml` 产物注册层。

#### Scenario: evidence 通过 artifact reference 读取
- **WHEN** Global Command Guard 匹配命令
- **AND** 配置的 evidence（证据）声明 `artifact` 或 `artifact_id`
- **THEN** Runtime（运行时）MUST 从同一 Guard Profile 的 `artifacts.yaml` 查找该 artifact id
- **AND** Runtime MUST 渲染该 artifact 的 `path`
- **AND** 目标 JSON 存在且所有配置的 JSON checks（JSON 检查）均通过时，Runtime 允许该命令继续进入后续 Session Focus permission（会话焦点权限）检查

#### Scenario: artifact path 使用命令和运行时上下文
- **WHEN** Global Command Guard 通过 `artifacts.yaml` 渲染 artifact path
- **THEN** Runtime（运行时）MUST 支持命令捕获值，例如 `{change}`
- **AND** Runtime MUST 支持全局守卫运行时上下文，例如 `{git_head}`、`{source_scope}`、`{profile_id}`、`{guard_id}`、`{effective_guard_id}` 和 `{runtime_scope}`
- **AND** Global Command Guard artifact path 不得强制要求 Session Focus 专用上下文，例如 `{instance_id}` 或 `{state_version}`

#### Scenario: 用户级 profile 的 artifact path 按项目命令解析
- **WHEN** 用户级 Guard Profile 的 `artifacts.yaml` 为项目命令声明相对路径 artifact
- **THEN** Runtime（运行时）MUST 按当前项目根目录解析该相对路径
- **AND** Runtime 不得把该相对路径解析到用户级 Guard Profile 目录或 `~/.agents/guard`

#### Scenario: evidence 通过 legacy path 读取
- **WHEN** Global Command Guard 匹配命令
- **AND** 配置只声明 legacy `evidence.path`
- **AND** evidence JSON 存在
- **AND** 所有配置的 JSON checks（JSON 检查）均通过
- **THEN** Runtime（运行时）允许该命令继续进入后续 Session Focus permission 检查

#### Scenario: evidence 缺失
- **WHEN** Global Command Guard 匹配命令
- **AND** 目标 evidence JSON 不存在
- **THEN** Runtime（运行时）返回 `deny`
- **AND** reason（原因）为该守卫声明的 deny reason，或 `global_command_guard_required`

#### Scenario: evidence 使用上下文值
- **WHEN** JSON check 声明 `value_from`
- **THEN** Runtime（运行时）从 command context 或 runtime context（运行时上下文）读取对应值参与谓词比较

#### Scenario: evidence 路径使用有效守卫上下文
- **WHEN** legacy evidence path template（旧证据路径模板）包含 `source_scope`、`profile_id`、`guard_id`、`effective_guard_id` 或 `runtime_scope`
- **THEN** Runtime（运行时）MUST 从当前匹配规则的上下文中解析这些值
- **AND** Runtime MUST 避免不同 profile 中同名 guard id 写入同一 evidence 路径

#### Scenario: legacy evidence path 兼容但不用于 Comet review gate
- **WHEN** Global Command Guard 配置只声明 legacy `evidence.path`
- **THEN** Runtime（运行时）MAY 继续按既有 `.local/guard/evidence` 或用户级等价 evidence 目录解析该路径
- **AND** 新的 Comet review gate 配置不得使用该 legacy path 模型表达 cross-agent-review pass marker

#### Scenario: artifact 引用无效
- **WHEN** Global Command Guard 配置声明的 `artifact` 或 `artifact_id` 不存在于同一 Guard Profile 的 `artifacts.yaml`
- **THEN** Validator（校验器）MUST 报告该引用无效
- **AND** Runtime（运行时）MUST deny（拒绝）匹配命令，并在失败详情中包含缺失的 artifact id
