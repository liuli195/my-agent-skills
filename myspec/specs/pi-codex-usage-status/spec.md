# Pi Codex Usage Status

## Purpose

本 capability（能力）定义 `pi-codex-usage-status` Pi（编码代理）扩展在状态栏显示 Codex（代码代理）订阅 7 天额度剩余比例和重置倒计时的行为。

## Requirements

### Requirement: Pi 状态栏显示 Codex 7 天额度

系统 MUST 通过名为 `pi-codex-usage-status` 的 Pi（编码代理）扩展，在状态栏显示 Codex（代码代理）订阅的 7 天额度剩余比例和重置倒计时。

#### Scenario: 显示可用额度

- **WHEN** 已取得 7 天额度窗口数据，已使用比例为 15%，距离重置还有 6 天 21 小时
- **THEN** 状态栏 MUST 显示 `Codex：85%/6D21H`

#### Scenario: 不足一小时显示分钟

- **WHEN** 已取得 7 天额度窗口数据，额度剩余 85%，距离重置还有 45 分 59 秒
- **THEN** 状态栏 MUST 显示 `Codex：85%/45M`
- **THEN** 状态栏 MUST NOT 显示天数或小时数

#### Scenario: 不足一分钟显示零分钟

- **WHEN** 已取得 7 天额度窗口数据，额度剩余 85%，距离重置还有 59 秒
- **THEN** 状态栏 MUST 显示 `Codex：85%/0M`

#### Scenario: 一小时格式边界

- **WHEN** 已取得 7 天额度窗口数据，额度剩余 85%，距离重置恰好还有 1 小时
- **THEN** 状态栏 MUST 显示 `Codex：85%/0D1H`

#### Scenario: 状态项顺序

- **WHEN** MCP（模型上下文协议）、Codex（代码代理）额度和 yolo（免确认模式）状态项同时可见
- **THEN** 状态栏 MUST 按 MCP（模型上下文协议）→ Codex（代码代理）→ yolo（免确认模式）的顺序显示这些状态项

#### Scenario: 数值取整

- **WHEN** 额度剩余百分比或重置倒计时包含非整数单位
- **THEN** 状态栏 MUST 将百分比、天数、小时数或分钟数分别向下取整

#### Scenario: 默认周期刷新

- **WHEN** 扩展正在运行且用户未配置刷新间隔
- **THEN** 扩展 MUST 每 15 秒通过 Codex API（应用程序接口）重新获取 7 天额度剩余比例与重置倒计时
- **THEN** 状态栏 MUST 同时更新百分比和倒计时两个显示值

#### Scenario: 自定义刷新间隔

- **WHEN** Pi（编码代理）全局 `settings.json`（设置文件）中的 `codexUsageStatus.refreshSeconds` 为有效刷新间隔
- **THEN** 扩展 MUST 按该间隔重新获取并更新两个显示值

#### Scenario: 无效刷新间隔

- **WHEN** `codexUsageStatus.refreshSeconds` 缺失或无效
- **THEN** 扩展 MUST 静默使用 15 秒刷新间隔

#### Scenario: 倒计时推进

- **WHEN** 已取得的重置时间尚未到达且刷新发生
- **THEN** 状态栏 MUST 更新为当前剩余的完整天数和完整小时数，或在不足 1 小时时更新为完整分钟数

#### Scenario: 数据不可用

- **WHEN** 尚未取得 7 天额度数据或读取失败
- **THEN** 状态栏 MUST 隐藏 Codex（代码代理）额度状态项

#### Scenario: 已知窗口已经重置

- **WHEN** 已知的重置时间已经到达且尚未取得新窗口数据
- **THEN** 状态栏 MUST 显示 `Codex：--%/0D0H`

#### Scenario: 切换到非 Codex 模型

- **WHEN** 已取得有效额度数据且当前模型切换为非 Codex（代码代理）模型
- **THEN** 状态栏 MUST 继续显示 Codex（代码代理）订阅状态

#### Scenario: 临时刷新失败

- **WHEN** 已取得有效额度数据且后续刷新临时失败
- **THEN** 状态栏 MUST 继续显示上次取得的剩余百分比
- **THEN** 重置倒计时 MUST 继续推进
- **THEN** 到达重置时间后 MUST 显示 `Codex：--%/0D0H`
### Requirement: 扩展保护认证信息

系统 MUST NOT 在状态栏、日志或错误提示中暴露 Codex（代码代理）认证信息。

#### Scenario: 认证请求失败

- **WHEN** Codex（代码代理）认证请求失败或返回错误
- **THEN** 状态栏、日志和错误提示 MUST NOT 包含认证令牌或其他认证信息
