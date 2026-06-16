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
系统 MUST 只通过当前 Session Focus Binding（会话焦点绑定）路由 `PreToolUse` 检查，并且不得从 repository（仓库）、branch（分支）、PR、task（任务）、Subject Resolver（主体解析器）或 `subject_key_hash` 推断实例。

#### Scenario: 没有焦点绑定
- **WHEN** `PreToolUse` 事件没有 Session Focus Binding（会话焦点绑定）
- **THEN** Runtime（运行时）允许该工具事件，并审计 `no_session_focus_instance`

#### Scenario: 焦点绑定无效
- **WHEN** 唯一 focus binding（焦点绑定）损坏、缺少必需字段或和另一个绑定冲突
- **THEN** Runtime（运行时）返回 error result（错误结果），并审计焦点绑定问题，不使用 permission `deny`（权限拒绝）

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
系统 MUST 支持通过 marketplace subscription（市场订阅）发布和验证 Agent Guard Plugin（代理守卫插件），并覆盖 personal marketplace（个人市场）和 repo marketplace（仓库市场）。

#### Scenario: 个人市场条目
- **WHEN** installer（安装器）为 personal scope（个人作用域）执行 dry-run（试运行）、install（安装）或 verify（验证）
- **THEN** 它使用 personal marketplace（个人市场）位置，并把 `agent-guard` 条目解析为 personal plugin package（个人插件包）

#### Scenario: 仓库市场条目
- **WHEN** installer（安装器）为 repo scope（仓库作用域）执行 dry-run（试运行）、install（安装）或 verify（验证）
- **THEN** 它使用当前仓库的 Codex `.agents/plugins/marketplace.json` 和 Claude `.claude-plugin/marketplace.json`，并把 `agent-guard` 条目解析为 `./plugins/agent-guard`

#### Scenario: GitHub 发布分支订阅
- **WHEN** 生成或验证正式 marketplace subscription（市场订阅）说明
- **THEN** 订阅源指向 GitHub repo（GitHub 仓库）的 `marketplace` 发布分支，不使用 tag（标签）或 commit（提交）固定版本

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
