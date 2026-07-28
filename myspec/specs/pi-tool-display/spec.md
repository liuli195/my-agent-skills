# Pi Tool Display

## Purpose

本 capability（能力）定义 `pi-tool-display`（Pi 工具显示扩展）在不改变工具执行语义的前提下控制内置及第三方工具显示、配置、重新加载和诊断日志的用户可见行为。

## Requirements

### Requirement: 工具显示扩展不得改变执行语义

扩展 MUST 只改变工具行显示，不得修改工具定义、Schema（结构定义）、所有权、激活状态、执行、模型上下文、消息或会话；不兼容宿主形状或渲染失败时必须保留 Pi（编码代理）原生行为。

#### Scenario: 显示扩展无法渲染工具

- **WHEN** 宿主形状不兼容或自定义渲染失败
- **THEN** 工具继续执行并使用 Pi（编码代理）原生渲染
### Requirement: 工具显示策略支持预设和显式控制

扩展 MUST 支持 `opencode`、`balanced`、`verbose` 预设，以及 `/tool-display show`、`reset` 和 `preset` 命令；关闭单个内置工具显示时必须保留 Pi（编码代理）原生渲染。

#### Scenario: 用户修改显示策略

- **WHEN** 用户选择预设、重置配置或关闭单个内置工具显示
- **THEN** 系统更新显示策略，且被关闭的自定义显示回退为原生渲染
### Requirement: 第三方工具显示必须显式选择

扩展 MUST 仅对精确配置的 `customToolOverrides` 或显式 Adapter（适配器）启用第三方或 MCP（模型上下文协议）工具显示，不得自动探测或拦截未配置工具。

#### Scenario: 第三方工具未配置显示覆盖

- **WHEN** 第三方工具没有精确配置覆盖或 Adapter（适配器）
- **THEN** 系统保留该工具的原生渲染

#### Scenario: 第三方工具已配置显示覆盖

- **WHEN** 第三方工具配置了精确覆盖
- **THEN** 系统按 hidden、summary 或 preview 模式显示该工具
### Requirement: Diff 与写入摘要只使用可信输入

扩展 MUST 仅根据工具提供的显式 patch（补丁）或 before/after（前后）数据渲染 Diff（差异），不得读取工作区重建旧内容或推断创建、覆盖语义。

#### Scenario: 编辑工具缺少可信差异数据

- **WHEN** edit 或 write 工具没有提供显式 patch 或 before/after 数据
- **THEN** 系统显示中性写入摘要而不是伪造 Diff（差异）
### Requirement: 项目配置必须受信且写入全局配置

扩展 MUST 只在项目受信时读取项目配置并将其作为全局配置覆盖层；`/tool-display` 的写入必须保存到全局配置。

#### Scenario: 项目不受信

- **WHEN** 当前项目存在本地显示配置但未被信任
- **THEN** 系统不加载该项目配置

#### Scenario: 用户通过命令修改配置

- **WHEN** 用户通过 `/tool-display` 保存显示设置
- **THEN** 系统写入全局配置且不修改项目配置文件
### Requirement: 扩展重新加载必须可恢复

扩展 MUST 支持 `/reload`，并清理旧显示补丁、计时器和 Adapter（适配器）注册，不得堆叠包装器或留下过期注册。

#### Scenario: 用户重新加载扩展

- **WHEN** 用户执行 `/reload`
- **THEN** 新显示策略生效，旧生命周期资源不重复残留
### Requirement: 装饰性界面与能力检测保持一致

扩展 MUST 支持原生用户消息框、工具行分隔线及主题颜色配置，并且只在 RTK（终端工具包）可用时显示 RTK 控件。

#### Scenario: 用户打开显示设置

- **WHEN** 用户打开显示设置
- **THEN** 系统只展示当前环境支持的控件，并按配置渲染消息框和分隔线
### Requirement: 诊断日志默认关闭且不泄露敏感值

扩展 MUST 默认不创建调试产物或向终端输出调试日志；启用后必须写入脱敏的调试文件，且日志写入失败不得阻断扩展。

#### Scenario: 调试日志未启用

- **WHEN** 用户未启用调试日志
- **THEN** 扩展不创建调试产物且不向终端输出调试日志

#### Scenario: 调试日志已启用

- **WHEN** 用户启用调试日志
- **THEN** 扩展写入脱敏后的文件日志，且写入失败不影响工具显示与执行
### Requirement: 内置工具输出必须遵循各自显示模式

扩展 MUST 按配置为 read、search、Bash 命令及 Bash 结果提供文档声明的隐藏、摘要、预览或完整显示行为，并在失败的 Bash 调用中始终保留可见的失败标题。

#### Scenario: 用户选择紧凑输出模式

- **WHEN** 用户为内置工具选择 hidden、summary、count、preview、opencode 或 full 中该工具支持的模式
- **THEN** 系统按该模式限制可见输出，并允许用户通过 Pi（编码代理）的展开操作查看可展开内容
### Requirement: Diff 展示必须适应布局并保留可信行标识

扩展 MUST 支持 split、unified 和按宽度自动选择的 Diff（差异）布局，必须在窄面板中限制宽度，并在带 `LINE#HASH` 锚点的内容实际渲染时保留该行标识；折叠限制必须按逻辑 Diff 内容行计算。

#### Scenario: 用户在不同宽度查看带锚点的差异

- **WHEN** 可信 Diff 输入包含 `LINE#HASH` 锚点且终端宽度发生变化
- **THEN** 系统选择或使用已配置的布局，在可用宽度内显示差异，并在对应内容实际渲染时保留锚点行标识
### Requirement: 显示 Adapter 注册必须可释放且不依赖加载顺序

扩展 MUST 为直接依赖方提供 display-only Adapter（仅显示适配器）注册，注册必须不依赖扩展加载顺序，返回的 disposer（释放函数）必须在待处理注册被接管前后保持幂等，并且不得暴露或修改可执行工具定义。

#### Scenario: 生产者先于显示扩展注册 Adapter

- **WHEN** 第三方扩展在 `pi-tool-display` 加载前注册显示 Adapter（适配器）并保留 disposer（释放函数）
- **THEN** 注册在显示扩展加载后生效，且同一 disposer（释放函数）可安全取消待处理或已生效的注册
### Requirement: 稳定版 Pi 兼容范围必须从 0.81.1 开始

扩展 MUST 支持 `0.81.1` 及以上稳定版 Pi（编码代理），不得将预发布版本或更低版本声明为受支持；不受支持的宿主必须保留原生显示与执行。

#### Scenario: 扩展运行在不受支持的 Pi 版本

- **WHEN** Pi（编码代理）版本低于 `0.81.1` 或版本字符串为预发布版本
- **THEN** 扩展不接管不兼容的显示路径，并保留 Pi（编码代理）原生显示与执行
