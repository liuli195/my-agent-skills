# 01 — 修正 Orca ntfy 公共匿名通知

**What to build:** 将 `orca-ntfy`（Orca 通知插件）从“主题加令牌”纠正为公共 `ntfy.sh` 匿名主题发布，并让源码、清单、说明、正式规格和验证保持一致。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 插件版本升级为 `1.0.1`，继续声明 `pluginApi: 1`、目标事件、`events:subscribe` 和 `secrets` 能力。
- [ ] 插件只读取 `ntfy-topic`，不读取 `ntfy-token`，所有请求都不包含 `Authorization` 请求头。
- [ ] 保留三个状态、固定通知内容、优先级、标签、按 `worktreeId + paneKey` 去重及 1 秒、5 秒、30 秒重试。
- [ ] 缺少主题或发送失败时不泄露主题、事件载荷、响应正文或其他敏感信息，也不回退到认证发送。
- [ ] 更新插件说明、正式规格和官方资料调研说明，删除令牌、自建推送密钥及账户认证对本方案的误导。
- [ ] 通过真实插件入口验证匿名请求、仅主题读取、无授权请求头、状态映射、去重、重试和隐私边界。
- [ ] 使用 build-and-verify（构建与验证）执行匹配的静态检查、单元测试和最小真实入口冒烟测试，并记录未验证项。
