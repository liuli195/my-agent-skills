# 04: 按实测结果改造并应用补丁

**What to build:** 首轮实测完成后，删除已经由上游解决或语义失效的旧补丁，只为稳定失败且成本收益合理的问题适配并应用 `0.3.2` 最小补丁。

**Blocked by:** 03: 在干净版本上逐项运行行为实测。

**Status:** completed

- [x] 每个应用的补丁都有补丁前红灯和补丁后同入口绿灯。
- [x] 未稳定复现的问题没有被应用补丁。
- [x] 补丁脚本只包含有失败证据、版本保护和唯一锚点的项目。
- [x] 修复后已复跑连接器、长消息、配置和引导词真实入口。

## 真实入口证据

- Quick question（快速问答）红灯：任务 `issue-351-v032-quick-red` 按 `0.3.2` 原模板发送
  `Quick question ... no [C2C] message needed`，真实 `awehitch_send_state` 返回
  `INVALID_MESSAGE: Control messages must start with [C2C].`
- 同入口绿灯：补入 `[C2C] / STATE: QUICK_QUESTION` 并重渲染现有 Codex（代码代理）技能后，
  任务 `issue-351-v032-quick-green` 的真实 `awehitch_send_state` 返回 `ok: true, sent: true`。
