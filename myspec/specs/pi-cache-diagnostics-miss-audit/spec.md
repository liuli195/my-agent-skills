# Pi Cache Diagnostics Miss Audit

## Purpose

本 capability（能力）定义 `pi-cache-diagnostics`（Pi 缓存诊断插件）捕获 Pi（编码代理）原生缓存 Miss（未命中）事件并保存客户端可观测证据链的行为；大模型差异分析和根因归因不属于插件职责。

## Requirements

### Requirement: 原生缓存未命中判定

插件 MUST 直接使用 Pi（编码代理）内部 `detectCacheMiss`（缓存未命中检测）的结果判定 Miss（未命中），不得复制检测算法、维护容差或另设大型 Miss 分类。

#### Scenario: Pi 报告缓存未命中

- **WHEN** Pi（编码代理）原生 `detectCacheMiss` 返回 Miss（未命中）结果
- **THEN** 插件按统一证据流程记录该事件，并继承模型切换、压缩、分支摘要和会话恢复等原生语义
### Requirement: OpenAI Codex 审计范围

插件 MUST 只审计 `openai-codex`（OpenAI Codex 模型服务）；未来支持其他模型服务时仍须复用 Pi（编码代理）原生检测并适配对应证据格式。

#### Scenario: 使用其他模型服务

- **WHEN** 当前请求不属于 `openai-codex`
- **THEN** 插件不为该请求执行缓存 Miss（未命中）证据审计
### Requirement: 滚动请求证据窗口

插件 MUST 为当前会话维护从上一次有效请求及响应开始、经过后续关键完成态事件到当前最终助手消息结束的滚动证据窗口。

#### Scenario: 未触发缓存未命中

- **WHEN** 当前有效请求未触发 Miss（未命中）
- **THEN** 插件只保留当前有效请求及响应作为下一窗口的基准

#### Scenario: 触发缓存未命中

- **WHEN** 当前有效请求触发 Miss（未命中）
- **THEN** 插件将当前窗口固化为永久证据包，并以当前有效请求及响应建立下一窗口
### Requirement: 请求检查点与证据边界

插件 MUST 为每个会话保留一个最新请求检查点，并在无法恢复历史分支目标的完整模型服务载荷时明确标记证据边界。

#### Scenario: 有效请求完成

- **WHEN** 新的有效请求完成
- **THEN** 插件用该请求检查点覆盖旧检查点，而不累计保存全部正常请求

#### Scenario: 历史分支载荷无法恢复

- **WHEN** 历史分支跳转后无法恢复目标节点当时的完整模型服务载荷
- **THEN** 插件将此后第一次相关证据标记为 `evidenceIncomplete: true`，且不得声称证据完整
### Requirement: 关键完成态事件证据

插件 MUST 记录会话、用户输入、代理轮次、完整系统上下文、工具执行、模型设置、可观测模型请求、过滤后的网络元数据、最终助手消息、服务端用量、原生 Miss 结果、传输统计及审计完整性事件，并且不得记录消息流式片段或工具局部更新。

#### Scenario: 工具执行完成

- **WHEN** 一次工具执行开始并结束
- **THEN** 证据窗口记录工具名称、调用标识、参数、结果和错误状态

#### Scenario: 模型响应完成

- **WHEN** 当前最终助手消息完成
- **THEN** 证据窗口记录最终消息、服务端用量、Pi 原生 Miss（未命中）结果及可用传输统计快照
### Requirement: 客户端可观测边界

插件 MUST 将 `before_provider_request`（发送前请求）处理器捕获的载荷称为 `observedProviderPayload`（观测到的模型服务载荷），不得把它宣称为最终网络请求或伪造不可观测的内部传输关联。

#### Scenario: 模型服务请求即将发送

- **WHEN** 插件在 `before_provider_request` 事件观察到请求载荷
- **THEN** 插件生成一个 `providerRequestId`，保存观测载荷以及请求前、响应后的原始传输统计快照，并保留后续扩展仍可能修改载荷的边界说明

#### Scenario: 模型服务内部重试不可观测

- **WHEN** OpenAI Codex 内部执行插件无法逐次观测的 WebSocket（网络长连接）重试或 SSE（服务端事件流）回退
- **THEN** 插件不得伪造每次内部传输尝试的标识或关联
### Requirement: 证据中的敏感信息保护

插件 MUST 仅保存允许清单中的诊断请求头和响应头值；认证、Cookie（会话数据）及其他凭据只保存字段名与已排除标记，未列入允许清单的头只保存字段名。

#### Scenario: 网络头包含凭据

- **WHEN** 请求头或响应头包含认证、Cookie 或其他凭据字段
- **THEN** 永久证据不保存字段值，只记录字段名和已排除标记
### Requirement: 事件顺序与时间

插件 MUST 为每个会话使用严格递增的 `eventSequence`（事件序号），并为每个事件保存 Unix 毫秒、UTC ISO 8601 和带本机时区偏移的时间。

#### Scenario: 来源事件自带时间戳

- **WHEN** Pi（编码代理）源事件包含自己的时间戳
- **THEN** 插件将其另存为 `sourceTimestampMs`，不得覆盖采集时间
### Requirement: 自包含永久证据包

插件 MUST 在 Pi（编码代理）诊断目录的 `pi-cache-diagnostics/` 子目录中，为每次 Miss（未命中）生成按会话哈希分组、自包含且不自动删除的 `.jsonl.gz` 永久证据包。

#### Scenario: 缓存未命中证据固化

- **WHEN** 一个 Miss（未命中）窗口需要永久保存
- **THEN** 证据包依次包含证据清单、上一有效请求及响应、后续关键事件、本轮请求与响应、触发 Miss 的最终消息与检测结果，以及 `evidence_complete`（证据完成）事件

#### Scenario: 证据文件命名

- **WHEN** 插件生成永久证据文件名
- **THEN** 文件名包含时间、事件序号、未命中令牌数和 `providerRequestId`，且不得包含敏感内容
### Requirement: 证据格式版本

证据清单 MUST 包含 `schemaVersion: 1`、Miss（未命中）事实、模型、会话哈希、时间范围、事件数量和证据完整性状态；兼容新增字段不得提升版本，破坏性格式变化必须提升版本。

#### Scenario: 新增兼容字段

- **WHEN** 新版插件只向现有证据格式增加兼容字段
- **THEN** `schemaVersion` 保持不变

#### Scenario: 证据格式发生破坏性变化

- **WHEN** 新版插件改变现有消费者无法兼容的证据格式
- **THEN** 插件提升 `schemaVersion`
### Requirement: 原子固化与故障保全

插件 MUST 先完成临时 JSONL（逐行 JSON 格式）文件，再压缩到临时 Gzip（压缩格式）文件并原子改名；写入、压缩或恢复失败不得阻塞或取消模型请求。

#### Scenario: 压缩成功

- **WHEN** 临时 JSONL 文件已包含完成事件且 Gzip 完整性检查成功
- **THEN** 插件将临时压缩文件原子改名为最终 `.jsonl.gz`

#### Scenario: 压缩失败

- **WHEN** 证据压缩失败
- **THEN** 插件保留完整未压缩文件并改名为 `.jsonl.failed`，记录原因、通知用户并将对应窗口标记为不完整

#### Scenario: 同类审计错误持续发生

- **WHEN** 同类写入、压缩或恢复错误连续出现
- **THEN** 插件只主动通知一次，并在后续请求继续尝试恢复
### Requirement: 缓存诊断用户界面

插件 MUST 静默固化正常 Miss（未命中），只主动通知审计故障；`/cache-diagnostics`（缓存诊断命令）只显示采集状态，不执行分析或归因。

#### Scenario: 用户查看缓存诊断状态

- **WHEN** 用户运行 `/cache-diagnostics`
- **THEN** 命令显示采集状态、永久证据数量、最近证据时间、证据目录和当前错误状态，且不调用大模型或输出差异分析
### Requirement: 旧缓存日志保持只读

插件 MUST 保持现有 `openai-codex-cache.jsonl` 日志只读，不迁移、不删除、不修改，也不把它计入新证据包。

#### Scenario: 新证据系统开始记录

- **WHEN** 插件启用新的 Miss（未命中）证据格式
- **THEN** 新证据从独立目录开始记录，旧日志保持原状
