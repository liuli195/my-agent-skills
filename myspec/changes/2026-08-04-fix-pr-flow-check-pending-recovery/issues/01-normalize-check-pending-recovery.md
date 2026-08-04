# 01 — 统一检查等待与失败恢复

**父问题：** #107

**What to build:** 让 PR Flow `complete`（收尾）和 `diagnose`（诊断）按检查实际状态区分等待、失败和取消，并在停止时直接提供恢复动作。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 检查仍运行且 GitHub CLI 返回特殊待处理退出状态、同时返回有效检查数据时，`complete` 进入现有有界等待，而不是返回 `checks_or_review_blocking`。
- [ ] 检查等待后通过时，`complete` 在同一次运行中继续合并；等待超时返回 `DISPATCH_REQUIRED / checks_pending`。
- [ ] 检查失败或取消时，返回 `REPLY_OR_FIX_REQUIRED / checks_or_review_blocking`，不继续等待或合并。
- [ ] `complete` 和 `diagnose` 的停止输出直接包含等待、修复或重试动作；停止状态详情保留可机器读取的恢复信息。
- [ ] 回归测试覆盖待处理特殊退出状态、等待后通过、超时、失败和取消场景，并先红后绿。
