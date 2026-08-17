# 01 — 新增 Orca ntfy 会话状态通知插件

**What to build:** 为 Orca（代理运行平台）提供一个可直接加载的个人插件：订阅代理状态变化，在 `blocked`、`waiting`、`done` 状态发生变化时向公共 ntfy 发送一条简短会话通知，并具备状态去重、令牌私密读取、网络重试和敏感信息保护。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [x] 提供使用 `pluginApi: 1` 的 `orca-plugin.json`，主入口订阅 `agent.status.changed`，并声明 `events:subscribe` 与 `secrets` 能力。
- [x] 只处理 `blocked`、`waiting`、`done`；使用 `worktreeId + paneKey` 去重，状态变化才发送。
- [x] 未知 Agent 类型时标题固定为 `orca agent`；正文分别为“会话阻塞，等待处理”“会话已完成，等待回复”“会话已经彻底完成”。
- [x] `blocked` 和 `waiting` 使用高优先级，`done` 使用普通优先级，并发送对应标签。
- [x] 固定向公共 `https://ntfy.sh` 发送 HTTPS POST；令牌和随机主题只从 Orca `secrets` 读取，源码、清单和日志不出现私密值。
- [x] 网络失败按 1 秒、5 秒、30 秒至少重试三次；重复事件和最终失败行为符合规格。
- [x] 不发送完整路径、代理输出、分支或原始事件；文档说明无正式 `net:fetch`、无事件回放、未接入状态钩子的终端限制。
- [x] 添加清单检查、事件入口测试、去重测试、重试测试、私密值保护测试和最小真实入口冒烟测试，不新增运行时依赖。
