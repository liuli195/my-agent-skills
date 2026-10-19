## ADDED Requirements

### Requirement: Pi 最小自动生命周期适配
系统 MUST 在 Agent Guard Plugin（代理守卫插件）内提供仅限 Pi（编码助手）的适配层，将 Pi（编码助手）会话启动和工具调用转换为既有 Runtime Router（运行时路由器）可处理的标准生命周期事件。该适配层 MUST 复用既有 Guard Profile（守卫画像）、Session Observation（会话观察记录）、Session Focus（会话焦点）、Global Command Guard（全局命令守卫点）和审计语义，不得改变 Codex（编码助手）或 Claude（克劳德）的 Hook（钩子）配置和行为。

#### Scenario: Pi 会话启动记录观察
- **WHEN** Pi（编码助手）开始一个加载 Agent Guard（代理守卫）的会话
- **THEN** 适配层 MUST 以 `source=pi`、会话标识和当前项目目录调用既有生命周期入口
- **THEN** Runtime（运行时）MUST 按既有 SessionStart（会话启动）语义记录 Session Observation（会话观察记录）

#### Scenario: Pi 工具调用复用守卫判定
- **WHEN** Pi（编码助手）在受 Guard Profile（守卫画像）约束的会话中发起工具调用
- **THEN** 适配层 MUST 将工具名称和可用输入映射为既有 PreToolUse（工具调用前）判定所需的标准事件
- **THEN** Runtime（运行时）MUST 按既有 Global Command Guard（全局命令守卫点）和 Session Focus permission（会话焦点权限）顺序产生 allow（允许）或 deny（拒绝）结果
- **THEN** Pi（编码助手）适配 MUST 将该既有判定结果直接映射为当前工具调用的继续或阻断结果，不得额外执行第二次 Agent Guard（代理守卫）判定

#### Scenario: Pi 适配不改变既有架构和宿主
- **WHEN** Pi（编码助手）适配层被加载或执行
- **THEN** 它 MUST NOT 修改 Guard Profile（守卫画像）格式、Runtime API（运行时接口）、权限规则或 Session Focus（会话焦点）生命周期
- **THEN** 它 MUST NOT 导入、配置、调用或修改其他 Pi（编码助手）插件
- **THEN** Codex（编码助手）和 Claude（克劳德）MUST 继续通过现有 `hooks/hooks.json`（钩子配置）和 Hook Router（钩子路由器）运行，不加载 Pi（编码助手）适配层

#### Scenario: Pi 适配不要求目标仓库配置
- **WHEN** Pi（编码助手）从已安装的 Agent Guard Plugin（代理守卫插件）运行
- **THEN** 自动生命周期适配 MUST NOT 要求目标仓库新增 `.pi`（Pi 配置）文件、全局记忆或子代理框架
