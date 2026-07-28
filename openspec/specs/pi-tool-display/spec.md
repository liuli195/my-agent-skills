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
