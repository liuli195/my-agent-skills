# Orca ntfy Notifications

## Purpose

在 Orca（代理运行平台）手机端连接不可用时，通过个人插件直接向公共 ntfy（通知服务）发送简短、去重且不泄露敏感信息的代理状态通知。

## Requirements

### Requirement: Orca 受支持状态通知

系统 MUST 仅在同一 `worktreeId + paneKey`（工作区和终端标识）进入新的 `blocked`（阻塞）、`waiting`（等待输入）或 `done`（完成）状态时发送通知，并忽略其他状态。

#### Scenario: 受支持状态发生变化

- **WHEN** 同一工作区和终端进入与已记录状态不同的受支持状态
- **THEN** 系统 SHALL 发送一条对应状态通知

#### Scenario: 重复状态事件

- **WHEN** 同一工作区和终端重复报告已经记录的受支持状态
- **THEN** 系统 SHALL NOT 再次发送通知

#### Scenario: 不受支持状态

- **WHEN** 代理报告 `blocked`、`waiting`、`done` 之外的状态
- **THEN** 系统 SHALL NOT 读取通知私密值或发起网络请求
### Requirement: Orca ntfy 通知格式

系统 MUST 向公共 `https://ntfy.sh` 发送带 Bearer（令牌）认证的 HTTPS POST（安全网页发布请求），标题固定为 `orca agent`，并按状态使用固定正文、优先级和标签。

#### Scenario: 等待输入通知

- **WHEN** 代理进入 `waiting` 状态
- **THEN** 系统 SHALL 发送正文“会话已完成，等待回复”、高优先级和 `waiting` 标签

#### Scenario: 阻塞通知

- **WHEN** 代理进入 `blocked` 状态
- **THEN** 系统 SHALL 发送正文“会话阻塞，等待处理”、高优先级和 `blocked` 标签

#### Scenario: 完成通知

- **WHEN** 代理进入 `done` 状态
- **THEN** 系统 SHALL 发送正文“会话已经彻底完成”、普通优先级和 `done` 标签
### Requirement: Orca ntfy 私密信息保护

系统 MUST 从 Orca `secrets`（私密存储）读取随机 ntfy 主题和专用令牌，不得将私密值写入源码、插件清单或日志，也不得在通知中包含完整工作区路径、终端标识、代理输出或其他敏感信息。

#### Scenario: 私密值已配置

- **WHEN** 插件处理新的受支持状态
- **THEN** 系统 SHALL 只通过 Orca 私密存储取得主题和令牌，并只发送固定通知内容

#### Scenario: 私密值缺失或发送失败

- **WHEN** 主题、令牌缺失或网络请求失败
- **THEN** 系统 SHALL NOT 在日志中输出主题、令牌、事件载荷或响应正文
### Requirement: Orca ntfy 网络失败恢复

系统 MUST 对网络异常以及 HTTP 408、429 和 5xx 响应执行初次请求加最多三次重试，重试间隔依次为 1 秒、5 秒和 30 秒；最终失败后 MUST 保留已记录状态以抑制同一状态的重复发送。

#### Scenario: 可重试网络失败后成功

- **WHEN** 初次请求或后续请求发生可重试失败，并在重试次数耗尽前恢复
- **THEN** 系统 SHALL 按规定间隔重试并在成功后停止重试

#### Scenario: 重试全部失败

- **WHEN** 初次请求和三次重试全部失败
- **THEN** 系统 SHALL 停止请求，并在相同状态再次到达时继续抑制发送

#### Scenario: 不可重试的客户端错误

- **WHEN** ntfy 返回 408 和 429 之外的 4xx 响应
- **THEN** 系统 SHALL NOT 重试该请求
### Requirement: Orca ntfy 个人插件边界

系统 MUST 将该能力限定为使用 Node.js（运行环境）直接网络请求的个人插件，并明确说明 Orca 尚无正式 `net:fetch`（网络请求能力）、只提供已接入状态钩子的代理事件且没有事件回放。

#### Scenario: 用户阅读插件限制

- **WHEN** 用户查看插件说明
- **THEN** 系统 SHALL 明确说明不支持自建 ntfy、本地中继、Orca 核心或 `app.asar`（应用资源包）修改，也不保证插件停机期间或未接入状态钩子的终端通知
