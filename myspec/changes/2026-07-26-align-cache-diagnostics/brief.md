# Outcome

让 `pi-cache-diagnostics` 的缓存未命中判定与 Pi 内部语义一致，同时保留插件面向大额未命中的详细归因能力。

# Scope

- 对齐“从未报告缓存时不把零缓存计为未命中”的保护。
- 在错误、终止或零用量响应后保留上一条有效请求基准，避免污染下一轮比较。
- 记录模型切换、会话标识摘要和大额未命中标记。
- 保留现有请求前缀、系统指令、工具及传输诊断。
- 添加覆盖对应主流程的最小验证。

# Non-goals

- 不修改 Pi 本体。
- 不改变当前 SSE 传输配置，不启用 WebSocket cached。
- 不计算账单成本。
- 不把 permission-system 引起的指令变化误归因为 Pi 版本切换。

# Acceptance examples

- 缓存从未出现过时，连续零缓存响应不产生 `missedTokens` 或大额告警。
- 已有缓存活动后，旧提示词未被缓存读取时按 `min(previous, current) - cacheRead` 计算未命中。
- 新增超过 20,000 token、但旧前缀全部命中时，不产生大额未命中。
- 错误、终止和零用量响应不替换上一条有效基准。
- 模型变化时日志明确记录 `modelChanged: true`。
- 每条请求和响应都带匿名化会话标识，可区分并发 Pi 会话。

# Constraints and invariants

- 只修改当前仓库中的插件及必要验证文件。
- 不直接导入 Pi 私有的 `dist/core/cache-stats.js`。
- 不记录原始会话标识、提示词正文或其他敏感数据。
- 20,000 token 仅作为大额告警阈值，不替代 Pi 的未命中定义。
- 压缩边界继续重置比较基准。

# Decisions

- 本地复用 Pi 的判定公式和状态语义，不依赖其私有模块。
- 用 `reportedCache` 跨轮记录当前会话是否曾报告缓存活动。
- 用 `largeMiss` 明确区分“检测到未命中”和“大额告警”。
- 使用会话标识的 SHA-256 摘要关联请求与响应。

# Open questions

无。

# Verification expectations

- 运行 build-and-verify（构建与验证）技能规定的 fast（快速）验证。
- 运行覆盖插件真实事件流的端到端回归，验证请求、响应、压缩边界和并发会话日志。
