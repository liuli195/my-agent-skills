## ADDED Requirements

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
- **THEN** 文档 MUST 明确禁止新增 reviewed wrapper（审查包装入口）、修改 cross-agent-review 默认输出目录、复制 pass marker 到 `.local/guard/evidence`、把 `verify --apply` 作为主拦截点、以及在 Agent Guard 中实现 cross-agent-review 内部流程

#### Scenario: 文档语言简洁高效
- **WHEN** 更新 Skill 入口说明、共享参考文档或模板索引
- **THEN** 文档 MUST 使用短句和可执行步骤
- **AND** 文档 MUST 避免重复解释、营销式描述、长篇背景和只服务实现细节的术语堆叠
