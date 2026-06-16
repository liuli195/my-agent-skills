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

#### Scenario: 插件包与市场验证
- **WHEN** Agent Guard Plugin（代理守卫插件）package / marketplace verification（插件包 / 市场验证）运行
- **THEN** 它检查核心共享资源、四个场景化入口、插件 manifest（清单）和 marketplace subscription（市场订阅）入口
