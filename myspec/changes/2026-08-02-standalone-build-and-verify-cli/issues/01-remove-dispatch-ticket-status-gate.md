# 01 — 移除派发票据状态门禁

**What to build（构建内容）：** Pi Development Flow（Pi 开发流程）派发器只根据目标非主工作树、预期分支和单一已发布票据路径绑定 Implementer（实施者）；不再解析票据正文的 `ready-for-agent`（可派发）状态。

**Blocked by（前置项）：** None — can start immediately（无，可立即开始）。

**Status:** completed

- [x] 已指定且位于目标工作树发布票据目录中的票据，无论正文是否含状态标记，均可被精确派发。
- [x] 错误分支、主工作树和目录外路径继续被拒绝。
- [x] 派发器参数说明与 Development Flow（开发流程）实施说明不再声称状态是派发门禁。
- [x] 受控派发器测试通过，仓库快速验证通过。

## 行为证据

- 红灯：不含状态标记的票据被派发器拒绝，测试报 `ticket_path must have ready-for-agent status`。
- 绿灯：`node --test tests/pi_development_flow.test.mjs` 通过 8 项；无状态标记票据被精确绑定，错误分支、主工作树和目录外路径继续失败。
- 快速验证：Build and Verify（构建与验证）快速验证通过。
- 审查：规范与需求双轴审查无代码阻断；修复已通过 PR #261 合并到 `main`。
