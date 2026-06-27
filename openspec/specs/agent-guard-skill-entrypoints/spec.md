## Purpose

本 capability（能力）定义 Agent Guard Skill（代理守卫技能）入口基线：install（安装）、init（初始化）、update（更新）、run（运行）四个场景入口；薄路由入口；必需首要动作；删除独立 hooks（钩子）入口；以及共享核心资源处理。
## Requirements
### Requirement: 场景化 Skill 入口
系统 MUST 为 install（安装）、init（初始化）、update（更新）和 run（运行）工作流暴露四个场景化 Agent Guard Skill（代理守卫技能）入口。

#### Scenario: 发布入口
- **WHEN** Agent Guard Plugin（代理守卫插件）发布 Skill（技能）入口
- **THEN** 它包含 `$agent-guard-install`、`$agent-guard-init`、`$agent-guard-update` 和 `$agent-guard-run`

#### Scenario: 入口描述
- **WHEN** agent（代理）读取场景化 Skill（技能）描述
- **THEN** 该描述只触发该入口对应的目标工作流

### Requirement: 薄 Agent Guard 路由器
系统 MUST 保留 `$agent-guard` 作为 thin router（薄路由器），用于把用户意图映射到场景化入口，并在意图模糊时先询问。

#### Scenario: 明确安装意图
- **WHEN** 用户明确要求安装或准备 Guard Profile（守卫画像）草案
- **THEN** `$agent-guard` 路由到 `$agent-guard-install`

#### Scenario: 意图模糊
- **WHEN** 用户请求无法清晰匹配 install（安装）、init（初始化）、update（更新）或 run（运行）
- **THEN** `$agent-guard` 先询问澄清，而不是直接运行完整流程

### Requirement: 安装入口调研门禁
系统 MUST 要求 `$agent-guard-install` 在调研、生成或更新任何 Guard Profile（守卫画像）草案前加载 `$grill-with-docs`。

#### Scenario: 安装流程开始
- **WHEN** `$agent-guard-install` 开始 research（调研）、generation（生成）或 draft update（草案更新）流程
- **THEN** 它先加载 `$grill-with-docs`，并且不跳过该步骤

### Requirement: 初始化和更新校验门禁
系统 MUST 要求 `$agent-guard-init` 和 `$agent-guard-update` 在把 Guard Profile（守卫画像）写入已初始化守卫位置前校验该画像。

#### Scenario: 初始化开始
- **WHEN** `$agent-guard-init` 准备初始化 project-level（项目级）或 user-level（用户级）Guard Profile（守卫画像）
- **THEN** 它先运行 `validate_guard_profile.py <guard-profile-dir>`

#### Scenario: 更新开始
- **WHEN** `$agent-guard-update` 准备把更新后的 Guard Profile（守卫画像）同步到已初始化守卫
- **THEN** 它先运行 `validate_guard_profile.py <guard-profile-dir>`

### Requirement: 运行入口简报门禁
系统 MUST 要求 `$agent-guard-run` 在提交任何 `state_completed` 事件前读取 latest Guard Brief（最新守卫简报）。

#### Scenario: 请求状态完成
- **WHEN** `$agent-guard-run` 即将提交 `state_completed`
- **THEN** 它先读取当前 latest Guard Brief（最新守卫简报）

#### Scenario: 简报读取失败
- **WHEN** 当前 latest Guard Brief（最新守卫简报）读取失败
- **THEN** `$agent-guard-run` 不提交 `state_completed`

### Requirement: 删除 hooks 入口
系统 MUST 在 MVP baseline（最小可行基线）中不发布也不路由到独立 `$agent-guard-hooks` Skill（技能）入口。

#### Scenario: 扫描已发布 Skill
- **WHEN** 检查已发布的 Agent Guard Skill（代理守卫技能）入口
- **THEN** `agent-guard-hooks` 不作为已发布 Skill（技能）入口存在

#### Scenario: 扫描路由表
- **WHEN** 检查 `$agent-guard` router（路由器）条目
- **THEN** 没有 route（路由）指向 `$agent-guard-hooks`

### Requirement: 共享核心资源
系统 MUST 把共享 scripts（脚本）、assets（资源）和 common references（通用参考资料）保留在核心 `agent-guard` Skill（技能）区域，同时让场景化入口引用这些共享资源而不是复制它们。

#### Scenario: 场景入口使用共享脚本
- **WHEN** 场景化入口需要共享 script（脚本）或 template（模板）
- **THEN** 它通过相对路径引用共享核心资源，而不是复制资源目录

#### Scenario: 插件包验证
- **WHEN** Agent Guard Plugin package verification（插件包验证）运行
- **THEN** 它检查核心共享资源、四个场景化入口、产品 manifest（清单）和 marketplace subscription（市场订阅）契约，而不是检查 user-level Skill installation（用户级技能安装）

### Requirement: 用户级 Skill 安装兼容层移除
系统 MUST 不再把 user-level Skill installation（用户级技能安装）、Claude Junction（Claude 目录联接）或旧 install scripts（安装脚本）作为 Agent Guard Plugin（代理守卫插件）的发布、订阅或验证契约。

#### Scenario: 扫描旧安装脚本
- **WHEN** 检查仓库发布入口
- **THEN** `scripts/install/install_user_skill.ps1`、`scripts/install/sync_claude_junction.ps1` 和 `scripts/install/verify_install.py` 不作为 Agent Guard 安装入口存在

#### Scenario: 验证发布契约
- **WHEN** Agent Guard Plugin（代理守卫插件）发布契约被验证
- **THEN** 验证只依赖 plugin package（插件包）、marketplace entry（市场条目）、manifest（清单）、hooks（钩子）、runtime（运行时）和 Skill（技能）入口，不依赖 `.agents/skills/agent-guard` 或 `.claude/skills/agent-guard` Junction（目录联接）

### Requirement: Agent Guard Skill 入口覆盖 Global Command Guard
系统 MUST 让 Agent Guard（代理守卫）所有相关 Skill（技能）入口和共享参考文档覆盖 Global Command Guard（全局命令守卫点）的配置、初始化、同步、运行反馈和排障语义。Global Command Guard 不得只存在于 Runtime（运行时）实现或内部 README 中。相关文档 MUST 采用 progressive disclosure（渐进式披露），按 agent 使用场景组织，明确禁止项，并保持语言简洁高效。

#### Scenario: 路由入口识别全局命令守卫意图
- **WHEN** 用户要求安装、配置、同步或排查 Global Command Guard（全局命令守卫点）
- **THEN** `$agent-guard` router（路由入口）把该意图路由到合适的 `$agent-guard-install`、`$agent-guard-init`、`$agent-guard-update` 或 `$agent-guard-run` 场景入口

#### Scenario: 安装入口生成全局命令守卫画像
- **WHEN** `$agent-guard-install` 为用户级 Global Command Guard（全局命令守卫点）生成 Guard Profile（守卫画像）草案
- **THEN** 入口说明和参考文档指导 agent 同时生成或更新 `global-command-guards.yaml` 和相关 `artifacts.yaml` 注册
- **AND** 文档说明静态规则可位于 `~/.agents/guards/<profile_id>/global-command-guards.yaml`
- **AND** 文档说明 Global Command Guard 可通过 `artifact` 或 `artifact_id` 引用 `artifacts.yaml` 中的注册产物

#### Scenario: 初始化和更新入口同步全局命令守卫画像
- **WHEN** `$agent-guard-init` 或 `$agent-guard-update` 初始化或同步包含 Global Command Guard（全局命令守卫点）的 Guard Profile（守卫画像）
- **THEN** 入口说明要求先运行 `validate_guard_profile.py <guard-profile-dir>`
- **AND** 文档说明该校验覆盖 `global-command-guards.yaml`、命令模式、产物引用和 JSON predicate（JSON 谓词）

#### Scenario: 运行入口解释全局命令守卫拒绝
- **WHEN** PreToolUse（工具使用前）因 Global Command Guard（全局命令守卫点）拒绝命令
- **THEN** `$agent-guard-run` 或共享运行参考文档说明该拒绝不依赖 Session Focus Instance（会话焦点实例）
- **AND** 文档指导 agent 根据 deny（拒绝）输出中的 reason、next、suggestion、captures、failing guards（失败守卫）和 artifact/evidence 信息执行下一步
- **AND** 文档不得复写 Comet 或 cross-agent-review（跨代理审查）的内部执行流程

#### Scenario: 模板索引暴露全局命令守卫资源
- **WHEN** agent 查阅 Agent Guard 共享模板或参考索引
- **THEN** 文档列出 `global-command-guards.yaml` 模板、`artifacts.yaml` 配合方式、用户级静态配置位置和项目级运行态边界

#### Scenario: 文档按渐进式披露组织
- **WHEN** 更新 Agent Guard Skill 入口或共享参考文档
- **THEN** 入口文档 MUST 只放当前场景 agent 立即需要的步骤、判断标准和下一跳链接
- **AND** 细节、模板字段和排障矩阵 MUST 放入对应 reference（参考文档）或 template（模板）文件

#### Scenario: 文档按 agent 使用场景组织
- **WHEN** 文档说明 Global Command Guard（全局命令守卫点）
- **THEN** 内容 MUST 按 agent 使用场景组织，例如 install（安装/生成草案）、init（初始化/启用）、update（同步/维护）、run（运行/处理拒绝）、troubleshoot（排障）
- **AND** 文档不得只按内部模块、runtime 文件或实现函数组织

#### Scenario: 文档明确禁止项
- **WHEN** 文档说明 Comet review gate（审查门禁）或 Global Command Guard
- **THEN** 文档 MUST 明确禁止新增 reviewed wrapper（审查包装入口）、在 Agent Guard（代理守卫）中实现 cross-agent-review（跨代理审查）内部流程、把 `verify --apply` 作为主拦截点、以及复制真正的 external artifact（外部产物）来绕过原始产物路径

#### Scenario: 文档语言简洁高效
- **WHEN** 更新 Skill 入口说明、共享参考文档或模板索引
- **THEN** 文档 MUST 使用短句和可执行步骤
- **AND** 文档 MUST 避免重复解释、营销式描述、长篇背景和只服务实现细节的术语堆叠
