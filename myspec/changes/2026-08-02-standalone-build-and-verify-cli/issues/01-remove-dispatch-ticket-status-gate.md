# 01 — 移除派发票据状态门禁

**What to build（构建内容）：** Pi Development Flow（Pi 开发流程）派发器只根据目标非主工作树、预期分支和单一已发布票据路径绑定 Implementer（实施者）；不再解析票据正文的 `ready-for-agent`（可派发）状态。

**Blocked by（前置项）：** None — can start immediately（无，可立即开始）。

**Status:** ready-for-agent

- [ ] 已指定且位于目标工作树发布票据目录中的票据，无论正文是否含状态标记，均可被精确派发。
- [ ] 错误分支、主工作树和目录外路径继续被拒绝。
- [ ] 派发器参数说明与 Development Flow（开发流程）实施说明不再声称状态是派发门禁。
- [ ] 受控派发器测试通过，仓库快速验证通过。
