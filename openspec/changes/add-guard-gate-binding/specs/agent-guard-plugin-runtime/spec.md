## ADDED Requirements

### Requirement: Global command guard points
系统 MUST 支持 Global Command Guard（全局命令守卫点），用于在 PreToolUse（工具使用前）阶段拦截匹配的 shell command（命令），即使当前没有 Session Focus Binding（会话焦点绑定）。

#### Scenario: 无会话焦点时仍执行全局命令守卫点
- **WHEN** 主 agent 尝试执行一个匹配 Global Command Guard（全局命令守卫点）的命令
- **AND** 当前会话没有 Session Focus Instance（会话焦点实例）
- **THEN** Runtime（运行时）仍必须评估该 Global Command Guard

#### Scenario: 守卫任意配置命令点
- **WHEN** Guard Profile（守卫画像）声明一个 Global Command Guard，并配置 command pattern（命令模式）
- **THEN** Runtime（运行时）按该配置匹配命令，而不是只识别某个内置 workflow（工作流）

#### Scenario: 多个守卫画像同时贡献全局命令守卫点
- **WHEN** 多个 Guard Profile 都包含 `global-command-guards.yaml`
- **THEN** Runtime（运行时）MUST 收集所有这些配置
- **AND** Runtime MUST 形成 Effective Global Command Guard Set（有效全局命令守卫集）
- **AND** Runtime 不得只读取当前 Session Focus（会话焦点）对应的 Guard Profile

#### Scenario: 用户级和项目级全局命令守卫点同时存在
- **WHEN** 项目级 `.agents/guards/*/global-command-guards.yaml` 和用户级 `~/.agents/guards/*/global-command-guards.yaml` 同时存在
- **THEN** Runtime（运行时）MUST 同时收集两类来源
- **AND** Runtime MUST 对当前命令统一评估所有匹配的 Global Command Guard

#### Scenario: 未匹配全局命令守卫点时保持现有行为
- **WHEN** 主 agent 执行的命令不匹配任何 Global Command Guard
- **THEN** Runtime（运行时）继续使用现有 Session Focus permission（会话焦点权限）逻辑

#### Scenario: 全局命令守卫点拒绝命令
- **WHEN** 主 agent 执行的命令匹配 Global Command Guard
- **AND** 该守卫声明的 evidence（证据）检查不通过
- **THEN** Runtime（运行时）返回 `deny`
- **AND** 响应包含机器可读的 `reason`、`next`、`suggestion`、matched guard ids（匹配的有效守卫 ID 列表）、failing guards（失败守卫列表）、captures（捕获值）和 audit path（审计路径）

#### Scenario: 多个匹配守卫点必须全部通过
- **WHEN** 一个命令同时匹配多个 Global Command Guard
- **THEN** Runtime（运行时）MUST 评估所有匹配规则
- **AND** 只有所有匹配规则都通过时，命令才允许继续
- **AND** 任意一个匹配规则返回 deny 时，最终结果 MUST 为 deny

### Requirement: Global command guard configuration layout
系统 MUST 支持在 Guard Profile（守卫画像）目录中声明 `global-command-guards.yaml`，用于存放静态的 Global Command Guard（全局命令守卫点）配置。系统 MUST 区分静态配置作用域和运行态数据作用域。

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
- **THEN** Runtime（运行时）MUST 使用 `.local/guard`
- **AND** 即使 Global Command Guard 的静态配置来自用户级 Guard Profile，Runtime 也不得默认把该项目命令的动态文件写入 `~/.agents/guard`

#### Scenario: 用户作用域使用用户级运行目录
- **WHEN** Runtime 处理显式 user scope（用户作用域）的会话焦点实例、用户全局命令，或配置显式声明用户级运行态
- **THEN** Runtime（运行时）MUST 使用 `~/.agents/guard`

#### Scenario: Comet change review 使用项目级运行目录
- **WHEN** Global Command Guard 用于守卫 Comet change verify（Comet 变更验证）
- **THEN** review evidence（review 证据）MUST 位于项目级 `.local/guard`
- **AND** Runtime 不得从 `~/.agents/guard` 读取该 change 的通过证据

#### Scenario: 用户级安装不等于用户级运行态
- **WHEN** Agent Guard Plugin（代理守卫插件）安装在用户级
- **AND** 主 agent 在项目内触发 hook 或执行项目命令
- **THEN** Runtime（运行时）MUST 把该项目上下文的审计和证据写入 `.local/guard`

### Requirement: Command context extraction
系统 MUST 支持从配置声明的 command patterns（命令模式）中提取 named captures（命名捕获），用于后续 evidence path（证据路径）和 JSON predicate（JSON 谓词）校验。

#### Scenario: 提取命名捕获
- **WHEN** command pattern 匹配受保护命令，并包含 named capture
- **THEN** Runtime（运行时）把捕获值写入 command context（命令上下文）

#### Scenario: 解析 PowerShell 包装的 Git Bash 命令
- **WHEN** shell command 是 PowerShell 调用 Git Bash，并在 `-lc` 字符串中执行受保护命令
- **THEN** Runtime（运行时）仍能识别内层命令并提取 configured captures（配置捕获值）

#### Scenario: 缺少必需捕获
- **WHEN** command 明确匹配受保护边界
- **AND** Runtime（运行时）无法提取该守卫声明的 required capture（必需捕获）
- **THEN** Runtime（运行时）返回 `deny`
- **AND** reason（原因）为该守卫声明的缺省原因，或 `required_capture_missing`

### Requirement: Shared guard check evaluator
系统 MUST 将可复用检查能力从 Session Focus（会话焦点）和 Guard Instance（守卫实例）专用路径中抽象出来，使 Global Command Guard（全局命令守卫点）和现有 Guard Point（守卫点）可以共享。

#### Scenario: 复用命令提取与匹配
- **WHEN** Runtime（运行时）处理 PreToolUse
- **THEN** Session Focus permission（会话焦点权限）和 Global Command Guard MUST 使用同一套 command extraction（命令提取）基础能力

#### Scenario: 复用 JSON 谓词
- **WHEN** Global Command Guard 校验 JSON evidence（JSON 证据）
- **THEN** Runtime（运行时）MUST 复用 `json_artifact` check 的受限 predicate（谓词）语义
- **AND** 不得引入任意脚本或表达式执行

#### Scenario: 复用审计输出
- **WHEN** Global Command Guard allow（允许）或 deny（拒绝）一个命令
- **THEN** Runtime（运行时）MUST 写入 audit（审计），并记录 matched guard id、tool、command、captures 和失败检查详情

### Requirement: Evidence checks
系统 MUST 支持 Global Command Guard 用 evidence path template（证据路径模板）读取 JSON evidence，并使用命令上下文和运行时上下文执行检查。

#### Scenario: evidence 通过
- **WHEN** Global Command Guard 匹配命令
- **AND** evidence JSON 存在
- **AND** 所有配置的 JSON checks（JSON 检查）均通过
- **THEN** Runtime（运行时）允许该命令继续进入后续 Session Focus permission 检查

#### Scenario: evidence 缺失
- **WHEN** Global Command Guard 匹配命令
- **AND** evidence JSON 不存在
- **THEN** Runtime（运行时）返回 `deny`
- **AND** reason（原因）为该守卫声明的 deny reason，或 `global_command_guard_required`

#### Scenario: evidence 使用上下文值
- **WHEN** JSON check 声明 `value_from`
- **THEN** Runtime（运行时）从 command context 或 runtime context（运行时上下文）读取对应值参与谓词比较

#### Scenario: evidence 路径使用有效守卫上下文
- **WHEN** evidence path template（证据路径模板）包含 `source_scope`、`profile_id`、`guard_id`、`effective_guard_id` 或 `runtime_scope`
- **THEN** Runtime（运行时）MUST 从当前匹配规则的上下文中解析这些值
- **AND** Runtime MUST 避免不同 profile 中同名 guard id 写入同一 evidence 路径

## MODIFIED Requirements

### Requirement: PreToolUse 使用当前焦点
系统 MUST 保持现有 Session Focus permission（会话焦点权限）语义不变；Global Command Guard（全局命令守卫点）只在 PreToolUse 入口增加独立的前置检查。

#### Scenario: 全局命令守卫点先于会话焦点权限执行
- **WHEN** 一个命令同时匹配 Global Command Guard 和 Session Focus permission rule（会话焦点权限规则）
- **THEN** Runtime（运行时）先评估 Global Command Guard
- **AND** 任一检查返回 deny 时命令不得执行

#### Scenario: 全局命令守卫点允许后继续检查会话焦点
- **WHEN** Global Command Guard 允许一个命令
- **AND** 当前存在 Session Focus permission rule
- **THEN** Runtime（运行时）继续执行现有 Session Focus permission 检查

#### Scenario: 会话焦点不被全局命令守卫点修改
- **WHEN** Global Command Guard 允许或拒绝一个命令
- **THEN** Runtime（运行时）不得写入、替换或删除 Session Focus Binding（会话焦点绑定）
