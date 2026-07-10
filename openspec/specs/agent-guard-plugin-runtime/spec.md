## Purpose

本 capability（能力）定义 Plugin-first（插件优先）Agent Guard Runtime（代理守卫运行时）的当前基线：插件发布、授权安装、固定 lifecycle hooks（生命周期钩子）、标准事件、Session Observation（会话观察记录）、Session Focus（会话焦点）、显式 Guard Instance（守卫实例）生命周期、路由、状态完成和 Runtime API（运行时接口）兼容性。
## Requirements
### Requirement: 插件优先发布运行时
系统 MUST 通过 Agent Guard Plugin（代理守卫插件）发布通用 Runtime code（运行时代码）、Hook Adapter（钩子适配器）、Hook Router（钩子路由器）、lifecycle hooks（生命周期钩子）和 Agent Guard Skill（代理守卫技能）入口，而不是把 Runtime code 复制到目标项目。

#### Scenario: 项目初始化
- **WHEN** project-level guard initialization（项目级守卫初始化）运行
- **THEN** 它只写入 Guard Profile（守卫画像）和运行态位置，不把 `scripts/guard_runtime` 复制到目标项目

#### Scenario: 插件安装
- **WHEN** Agent Guard Plugin（代理守卫插件）被安装或验证
- **THEN** plugin package（插件包）从插件根目录提供 runtime（运行时）、hooks（钩子）、manifests（清单）、assets（资源）和 Skill（技能）入口

### Requirement: 授权插件安装器
系统 MUST 让插件安装保持显式、目标明确、可验证，并以 dry-run（试运行）作为安全默认行为。

#### Scenario: 试运行
- **WHEN** installer（安装器）在没有 install authorization（安装授权）的情况下被调用
- **THEN** 它报告计划写入或验证的 Codex 和 Claude plugin package（插件包）位置、personal marketplace（个人市场）位置和 repo marketplace（仓库市场）位置，不修改 user-level plugin locations（用户级插件位置）或 marketplace files（市场文件）

#### Scenario: 授权安装
- **WHEN** installer（安装器）收到明确 target（目标）、scope（作用域）和 install authorization（安装授权）
- **THEN** 它安装或更新对应 plugin package（插件包）和 marketplace entry（市场条目），并可以验证 manifest（清单）、hook（钩子）、runtime（运行时）、Skill（技能）入口和 marketplace entry（市场条目）可用

#### Scenario: 产品目标校验
- **WHEN** installer（安装器）以 `target: codex`、`target: claude` 或 `target: all` 运行
- **THEN** 它分别校验 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 或两者，并且不把 Claude Junction（Claude 目录联接）作为兼容条件

#### Scenario: 作用域校验
- **WHEN** installer（安装器）以 `scope: personal`、`scope: repo` 或 `scope: all` 运行
- **THEN** 它分别验证 personal marketplace（个人市场）、repo marketplace（仓库市场）或两者，并且不写入 Guard Profile（守卫画像）、project hooks（项目钩子）或 git config（Git 配置）

### Requirement: 固定生命周期钩子集合
系统 MUST 在第一版 plugin-runtime baseline（插件运行时基线）中只注册 `SessionStart` 和 `PreToolUse` lifecycle hooks（生命周期钩子）。

#### Scenario: 校验钩子配置
- **WHEN** hook configuration（钩子配置）被校验
- **THEN** 它包含 `SessionStart` 和 `PreToolUse`，并排除 Git hooks（Git 钩子）、`UserPromptSubmit`、`PostToolUse`、subagent hooks（子代理钩子）和 Claude `PermissionRequest`

#### Scenario: Hook 保持画像无关
- **WHEN** lifecycle hook command（生命周期钩子命令）运行
- **THEN** 它不接收 profile（画像）参数，也不在 hook（钩子）层选择 Guard Profile（守卫画像）

#### Scenario: 平台 manifest 避免重复加载
- **WHEN** package verification（包验证）检查 Agent Guard manifest（清单）和标准 `hooks/hooks.json`
- **THEN** Codex manifest MUST 声明 `hooks: ./hooks/hooks.json`
- **THEN** Claude manifest MUST NOT 声明标准 `hooks/hooks.json`
- **THEN** 标准 `hooks/hooks.json` MUST 继续位于插件包内并只包含 `SessionStart` 和 `PreToolUse`

### Requirement: 标准生命周期事件信封
系统 MUST 把 Codex 和 Claude lifecycle payloads（生命周期载荷）转换成包含 source（来源）、event type（事件类型）、context（上下文）和 payload（载荷）的标准 envelope（信封），且不包含 profile（画像）或 instance（实例）标识。

#### Scenario: SessionStart 转换
- **WHEN** 收到 Codex 或 Claude `SessionStart` payload（载荷）
- **THEN** adapter（适配器）输出带 `source`、`session_id` 和 `cwd` context（上下文）的 `lifecycle.session_start`

#### Scenario: PreToolUse 转换
- **WHEN** 收到 Codex 或 Claude `PreToolUse` payload（载荷）
- **THEN** adapter（适配器）输出不含 `guard_profile_id`、`profile_id` 或 Hook Binding（钩子绑定）数据的 `lifecycle.pre_tool_use`

### Requirement: 会话观察与会话焦点
系统 MUST 把 Session Observation（会话观察记录）事实和当前 Session Focus Binding（会话焦点绑定）分开记录，并使用显式焦点绑定识别当前 Guard Instance（守卫实例）。

#### Scenario: 写入会话观察
- **WHEN** `SessionStart` 为带有 `source`、`session_id` 和 `cwd` 的会话运行
- **THEN** 系统写入 Session Observation（会话观察记录），供后续 activation（激活）查找

#### Scenario: 选择焦点绑定
- **WHEN** 用户为当前会话激活一个 Guard Instance（守卫实例）
- **THEN** 系统写入一个 Session Focus Binding（会话焦点绑定），包含 `source`、`session_id`、`scope`、`profile_id` 和 opaque `instance_id`（不透明实例 ID）

### Requirement: 显式守卫实例生命周期
系统 MUST 使用 opaque Guard Instance identifiers（不透明守卫实例标识），并且第一版只支持 `active` 和 `closed` 两种实例状态。

#### Scenario: 创建实例
- **WHEN** activation（激活）创建新的 Guard Instance（守卫实例）
- **THEN** 该实例获得 opaque `instance_id`（不透明实例 ID）、用户可见 title（标题）、description（说明）和 `active` 状态

#### Scenario: 已关闭实例
- **WHEN** focus binding（焦点绑定）指向一个 `closed` 实例
- **THEN** Runtime（运行时）行为把该会话视为没有 active focus（活跃焦点）可用于守卫执行

### Requirement: Runtime Router 焦点处理
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

### Requirement: 状态完成使用当前焦点
系统 MUST 只允许 `state_completed` 推进当前 Session Focus Instance（会话焦点实例），并拒绝调用方传入的 profile（画像）或 instance（实例）选择。

#### Scenario: 没有焦点时提交状态完成
- **WHEN** 调用方在没有当前 Session Focus Instance（会话焦点实例）时提交 `state_completed`
- **THEN** Runtime（运行时）中止，并提示调用方先 activate（激活）守卫

#### Scenario: 有焦点时提交状态完成
- **WHEN** 调用方为有效当前焦点提交 `state_completed`
- **THEN** Runtime（运行时）锁定 `profile_id + instance_id`，评估 guard points（守卫点）和 artifacts（产物），并且只在刚好一个 transition（转换）通过时推进该实例

### Requirement: Runtime API 兼容性
系统 MUST 要求 Guard Profile（守卫画像）声明 `runtime_api_version`，并且在画像与已安装 Runtime（运行时）不兼容时避免阻断用户工作。

#### Scenario: 兼容画像
- **WHEN** profile（画像）的 `runtime_api_version` 与 plugin Runtime（插件运行时）兼容
- **THEN** Runtime（运行时）可以评估该画像，用于 routing（路由）和 state transition（状态转换）

#### Scenario: 不兼容画像
- **WHEN** profile（画像）的 `runtime_api_version` 不兼容
- **THEN** Runtime（运行时）返回 allow-with-audit compatibility result（放行并审计的兼容性结果），而不是误读该画像并拒绝工作

### Requirement: Marketplace 订阅入口

系统 MUST 支持通过 marketplace subscription（市场订阅）发布和验证 Agent Guard Plugin（代理守卫插件），并覆盖 personal marketplace（个人市场）、repo marketplace（仓库市场）、fixed release（固定版本发布）和 latest channel（最新通道）。Agent Guard 的 fixed release 和 latest channel 规则 MUST 由 `release-flow` Plugin（发布流程插件）配置和验证。

#### Scenario: 个人市场条目

- **WHEN** installer（安装器）为 personal scope（个人作用域）执行 dry-run（试运行）、install（安装）或 verify（验证）
- **THEN** 它使用 personal marketplace（个人市场）位置，并把 `agent-guard` 条目解析为 personal plugin package（个人插件包）

#### Scenario: 仓库市场条目

- **WHEN** installer（安装器）为 repo scope（仓库作用域）执行 dry-run（试运行）、install（安装）或 verify（验证）
- **THEN** 它使用当前仓库的 Codex `.agents/plugins/marketplace.json` 和 Claude `.claude-plugin/marketplace.json`，并把 `agent-guard` 条目解析为 `./plugins/agent-guard`

#### Scenario: GitHub 固定版本订阅

- **WHEN** 生成或验证 fixed release（固定版本发布）的 marketplace subscription（市场订阅）说明
- **THEN** 订阅源 MUST 指向 GitHub repo（GitHub 仓库）的版本 tag（标签）
- **THEN** release-flow MUST 将该 tag 与 Agent Guard Codex/Claude manifest version（清单版本）关联验证

#### Scenario: GitHub latest 通道订阅

- **WHEN** 生成或验证 latest channel（最新通道）的 marketplace subscription（市场订阅）说明
- **THEN** 订阅源 MUST 指向 GitHub repo（GitHub 仓库）的 `marketplace` 分支，以保持现有 Codex/Claude 订阅链接不变并支持自动更新
- **THEN** release-flow MUST 将该分支声明为 Agent Guard latest channel

### Requirement: Marketplace 条目契约
系统 MUST 为 Agent Guard Plugin（代理守卫插件）生成和验证包含 `source`、`policy` 和 `category` 的 marketplace entry（市场条目）。

#### Scenario: 生成 Codex 本地条目
- **WHEN** installer（安装器）写入 marketplace entry（市场条目）
- **THEN** 条目包含 `name: agent-guard`、`source.source: local`、`source.path: ./plugins/agent-guard`、`policy.installation`、`policy.authentication` 和 `category`

#### Scenario: 生成 Claude 仓库目录
- **WHEN** installer（安装器）写入 Claude repo marketplace catalog（仓库市场目录）
- **THEN** `.claude-plugin/marketplace.json` 包含 `agent-guard` 插件条目，并把插件目录解析到 `plugins/agent-guard`

#### Scenario: 验证条目
- **WHEN** installer（安装器）验证 marketplace entry（市场条目）
- **THEN** 它拒绝缺少 `source` 对象、`policy.installation`、`policy.authentication` 或 `category` 的旧格式条目

### Requirement: 插件包自包含
系统 MUST 让 `plugins/agent-guard` 成为 Codex 和 Claude 都可安装的自包含 plugin package（插件包）。

#### Scenario: 自包含资源
- **WHEN** package verification（包验证）检查 Agent Guard Plugin（代理守卫插件）
- **THEN** skills（技能）、hooks（钩子）、runtime（运行时）、scripts（脚本）、assets（资源）以及 `.codex-plugin/plugin.json` 和 `.claude-plugin/plugin.json` 都位于 `plugins/agent-guard` 内

### Requirement: Agent Guard 发布分支边界

系统 MUST 将 Agent Guard 的 `marketplace` 分支作为由 `release-flow` Plugin 生成或更新的 latest channel，不得把它作为开发分支或规则真相。

#### Scenario: 发布分支由 main 和 projection 生成

- **WHEN** 更新 `marketplace` 分支用于发布 latest channel
- **THEN** 发布流程 MUST 从 `main` 的源码、manifest version 和 `.release-flow/projection.yaml` 生成发布内容
- **THEN** 发布流程 MUST 从 GitHub Actions Variables 读取 projection 所需变量值

#### Scenario: 禁止本地发布分支

- **WHEN** 发布 Agent Guard latest channel
- **THEN** 本地流程 MUST NOT 创建 `marketplace` 发布分支
- **THEN** 本地流程 MUST NOT 手工 push `marketplace`

#### Scenario: 禁止发布分支手工漂移

- **WHEN** 验证 `marketplace` 分支与 `main` 的差异
- **THEN** 校验 MUST 拒绝未被 `.release-flow/projection.yaml` 描述的差异

#### Scenario: tag 与 manifest 版本一致

- **WHEN** 创建或验证 fixed release（固定版本发布）
- **THEN** tag（标签）中的版本 MUST 与 Codex manifest 和 Claude manifest 的 version（版本）一致

### Requirement: Agent Guard 发布变量注册

系统 MUST 使用 `.release-flow/projection.yaml` 注册 Agent Guard marketplace catalog（市场目录）发布态变量，并禁止把变量值写入 Git。

#### Scenario: 注册 Codex marketplace 名称变量

- **WHEN** Agent Guard latest channel 需要生成 Codex marketplace catalog
- **THEN** projection MUST 注册用于 `.agents/plugins/marketplace.json` 的发布态变量
- **THEN** projection MUST 声明该变量注入到对应 JSON 字段

#### Scenario: 注册 Claude marketplace 名称变量

- **WHEN** Agent Guard latest channel 需要生成 Claude marketplace catalog
- **THEN** projection MUST 注册用于 `.claude-plugin/marketplace.json` 的发布态变量
- **THEN** projection MUST 声明该变量注入到对应 JSON 字段

### Requirement: Installer 使用共享 marketplace identity
Agent Guard installer（安装器）MUST 使用 release-flow 共享 marketplace identity（市场身份）生成和验证 marketplace catalog（市场目录），不得把正式 marketplace 名称只硬编码在 installer 内部。

#### Scenario: 默认 catalog root 读取 identity
- **WHEN** installer 生成 Codex 或 Claude marketplace catalog
- **THEN** Codex catalog name 和 display name MUST 来自共享 marketplace identity
- **THEN** Claude catalog name 和 owner name MUST 来自共享 marketplace identity

#### Scenario: 验证拒绝 identity 不一致
- **WHEN** installer 验证 marketplace catalog
- **THEN** 它 MUST 拒绝和共享 marketplace identity 不一致的 catalog name、display name 或 owner name
- **THEN** 错误输出 MUST 指出实际值和期望值

### Requirement: Source repo 与 repo scope marketplace 边界
系统 MUST 区分本仓库 source branch（源分支）的 marketplace 文件边界和 installer 的 repo scope（仓库作用域）安装行为。

#### Scenario: 本仓库 main 不需要 Codex repo marketplace
- **WHEN** Agent Guard Plugin 在本仓库 source branch 中开发
- **THEN** installer package verification（包验证）MUST NOT 要求 `.agents/plugins/marketplace.json` 作为持久源文件存在
- **THEN** Codex repo-local marketplace 缺失 MUST NOT 被视为插件包不完整

#### Scenario: 目标项目 repo scope 仍可显式写入
- **WHEN** 用户以 repo scope 对目标项目运行授权安装
- **THEN** installer MAY 写入用户显式传入的 Codex repo marketplace 路径
- **THEN** 该行为 MUST NOT 重新要求本仓库 main 分支保存 Codex repo-local marketplace 文件

### Requirement: Global command guard points

系统 MUST 支持 Global Command Guard（全局命令守卫点）在命令匹配后按声明式 skip condition（跳过条件）放行特定上下文，并且不得把具体业务 workflow（工作流）判断硬编码进 Runtime（运行时）。

#### Scenario: 声明式 YAML 条件命中时跳过守卫

- **WHEN** 命令匹配一个 Global Command Guard（全局命令守卫点）
- **AND** 该守卫声明 `skip_when`（跳过条件）读取相对 YAML（配置文件）路径、字段和允许值
- **AND** 该 YAML（配置文件）字段值是 string scalar（字符串标量）并命中允许值
- **THEN** Runtime（运行时）跳过该守卫的 evidence（证据）检查
- **AND** 该守卫不应造成 deny（拒绝）
- **AND** Runtime（运行时）在 audit（审计）中记录被跳过的守卫编号和跳过原因

#### Scenario: 跳过条件未命中时继续原有检查

- **WHEN** 命令匹配一个 Global Command Guard（全局命令守卫点）
- **AND** `skip_when`（跳过条件）缺失、目标文件缺失、字段缺失、字段值未命中、YAML（配置文件）不可读或路径模板不安全
- **THEN** Runtime（运行时）继续执行该守卫原有 evidence（证据）检查

### Requirement: Global command guard configuration layout
系统 MUST 让 Global Command Guard（全局命令守卫）通过 artifacts.yaml（产物注册文件）读取被守卫流程证据。

#### Scenario: Comet change review 通过产物注册读取项目产物
- **WHEN** Global Command Guard 用于守卫 Comet change build 完成命令
- **AND** 该守卫通过 `artifact` 或 `artifact_id` 引用 `artifacts.yaml` 中的 cross-agent-review pass marker（跨代理审查通过标记）
- **THEN** Runtime（运行时）MUST 按 `artifacts.yaml` 注册路径读取该 guard-defined evidence（守卫定义证据）
- **AND** 该产物 MUST 位于项目内 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`
- **AND** Runtime 不得从 `~/.agents/guard` 读取该 Comet change 的通过证据

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

#### Scenario: command extraction 识别一层 tool input containers
- **WHEN** PreToolUse payload（载荷）的 command（命令）位于 top-level（顶层）、`tool_input`、`input`、`parameters`、`params`、`args` 或 `arguments`
- **THEN** command extraction（命令提取）MUST 识别字符串 `command` 或 `cmd`
- **AND** unsupported nested values（不支持的嵌套值）MUST 被安全忽略

#### Scenario: 复用 JSON 谓词
- **WHEN** Global Command Guard 校验 JSON evidence（JSON 证据）
- **THEN** Runtime（运行时）MUST 复用 `json_artifact` check 的受限 predicate（谓词）语义
- **AND** 不得引入任意脚本或表达式执行

#### Scenario: 复用审计输出
- **WHEN** Global Command Guard allow（允许）或 deny（拒绝）一个命令
- **THEN** Runtime（运行时）MUST 写入 audit（审计），并记录 matched guard id、tool、command、captures 和失败检查详情

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

### Requirement: Global Command Guard built-in context values

Global Command Guard MUST expose generic built-in context values for template rendering and JSON `value_from` checks.

#### Scenario: Short Git HEAD is available

- **WHEN** Runtime evaluates a Global Command Guard inside a Git repository
- **THEN** `git_head` MUST contain the full current HEAD
- **AND** `git_head_short` MUST contain the first 12 characters of `git_head`
- **AND** `git_head_short` MUST be allowed in artifact path templates and JSON `value_from` checks

### Requirement: Global Command Guard evidence uses dual path model
系统 MUST 为 Global Command Guard（全局命令守卫点）区分 guard-defined evidence（守卫定义证据）和 external artifact（外部产物）。当通过结论由主 agent（主代理）根据上游报告作出时，Agent Guard（代理守卫） MUST 定义默认 evidence（证据）目录，并且只在主代理显式调用通用记录入口后机械写入；当被守卫流程本身已经生成稳定可检查产物时，Agent Guard（代理守卫） MUST 只登记并校验原始路径，不复制、不搬运、不接管目录。

#### Scenario: guard-defined evidence 使用默认目录
- **WHEN** Guard Profile（守卫画像）声明的 artifact（产物）属于 guard-defined evidence（守卫定义证据）
- **THEN** Runtime（运行时） MUST 从 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json` 读取证据

#### Scenario: guard-defined evidence 由主代理显式记录
- **WHEN** guard-defined evidence（守卫定义证据）需要写入 pass marker（通过标记）
- **THEN** 主 agent（主代理） MUST 在 Guard（守卫）检查前显式调用 `record-evidence`（记录证据）
- **AND** Runtime（运行时）只能机械校验并写入，不得自主生成业务结论

#### Scenario: guard-defined evidence 使用标准字段
- **WHEN** guard-defined evidence（守卫定义证据）写入 pass marker（通过标记）
- **THEN** marker（标记） MUST 使用 `guard-evidence/v1`（守卫证据第一版）字段契约

#### Scenario: external artifact 保持只读
- **WHEN** `artifacts.yaml`（产物注册文件）中的目标 artifact（产物）不属于 guard-defined evidence（守卫定义证据）
- **THEN** Agent Guard（代理守卫） MUST 只读取和校验该外部产物
- **AND** `record-evidence`（记录证据） MUST 拒绝覆盖该产物

#### Scenario: cross-agent-review pass marker 使用 guard-defined evidence
- **WHEN** Global Command Guard（全局命令守卫点）校验 Cross Agent Review（跨代理审查）的 pass marker（通过标记）
- **THEN** 该 artifact（产物） MUST 注册为 `type: json`（数据类型）且 `owner: agent-guard`（代理守卫拥有）的 guard-defined evidence（守卫定义证据）
- **AND** 注册路径 MUST 使用 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`
- **AND** `{artifact_id}` MUST 为该 Guard Profile（守卫画像）声明的 `cross_agent_review_pass`
- **AND** `{subject_id}` MUST 来自命令捕获值，Comet change（双星变更）场景下等于 `change`

### Requirement: 通用 record-evidence 入口
Agent Guard Runtime（代理守卫运行时） MUST 提供通用 `record-evidence`（记录证据）入口，供主代理在完成语义判断后显式记录任意 Guard Profile（守卫画像）声明的 guard-defined JSON evidence（守卫定义数据证据）。该入口 MUST 不硬编码业务 workflow（工作流）、审查技能、profile id（画像编号）、artifact id（产物编号）或证据业务字段。

#### Scenario: 显式选择画像来源
- **WHEN** 主代理调用 `record-evidence`（记录证据）
- **THEN** 调用 MUST 明确提供 project（项目）或 user（用户）profile source scope（画像来源范围）、`profile_id`（画像编号）和 `artifact_id`（产物编号）
- **AND** Runtime（运行时） MUST 只从所选来源的 `.agents/guards/<profile_id>/artifacts.yaml`（产物注册文件）解析产物
- **AND** Runtime（运行时） MUST NOT 在另一个来源范围中猜测或回退查找同名画像

#### Scenario: 只写守卫定义数据证据
- **WHEN** 目标 artifact（产物）存在于 `artifacts.yaml`（产物注册文件）
- **THEN** Runtime（运行时） MUST 要求该产物声明 `type: json`（数据类型）和 `owner: agent-guard`（代理守卫拥有）
- **AND** 任一条件不满足时，Runtime（运行时） MUST 拒绝写入并报告目标不是 guard-defined evidence（守卫定义证据）

#### Scenario: 从画像安全解析路径
- **WHEN** 目标产物通过所有权检查
- **THEN** Runtime（运行时） MUST 只使用该产物的 `path`（路径）模板
- **AND** Runtime（运行时） MUST 注入 `profile_id`、`artifact_id`、`subject_id`、当前 `git_head`（提交头）和当前 12 位 `git_head_short`（短提交头）
- **AND** Runtime（运行时） MUST 拒绝缺失模板值、绝对路径、Windows drive path（Windows 驱动器路径）和项目目录逃逸

#### Scenario: 当前仓库状态决定提交字段
- **WHEN** Runtime（运行时）准备记录证据
- **THEN** 它 MUST 从 `--project` 指向的 Git（版本控制）仓库读取当前完整 `HEAD`（提交头）
- **AND** 当前 worktree（工作区） MUST 干净
- **AND** 调用方 MUST NOT 覆盖 `head_ref` 或 `head_ref_short`

#### Scenario: 标准字段由 Runtime 注入
- **WHEN** 主代理提供 `producer`（生产方）、`subject_type`（对象类型）、`subject_id`（对象编号）和 JSON object（数据对象）业务字段
- **THEN** Runtime（运行时） MUST 注入 `schema_version: guard-evidence/v1`、`status: pass`、`producer`、`profile_id`、`artifact_id`、`subject_type`、`subject_id`、`head_ref`、`head_ref_short` 和 `created_at`
- **AND** Runtime（运行时） MUST 拒绝业务字段对象包含任一保留标准字段

#### Scenario: 原子写入证据
- **WHEN** 画像、产物、路径、仓库和业务字段均有效
- **THEN** Runtime（运行时） MUST 在目标目录创建同目录临时文件并通过 atomic replace（原子替换）写入 `pass.json`
- **AND** 命令输出 MUST 包含 `status: evidence_recorded`、当前完整提交头、12 位短提交头和可复制证据路径

#### Scenario: 写入失败不留下半文件
- **WHEN** JSON（数据）读取、目录创建、临时文件写入或原子替换失败
- **THEN** Runtime（运行时） MUST 返回失败状态
- **AND** Runtime（运行时） MUST NOT 把部分 JSON（数据）暴露为有效目标证据
