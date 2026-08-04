# 01 — 统一检查等待与失败恢复

**父问题：** #107

**What to build:** 让 PR Flow `complete`（收尾）和 `diagnose`（诊断）按检查实际状态区分等待、失败和取消，并在停止时直接提供恢复动作。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [x] 检查仍运行且 GitHub CLI 返回特殊待处理退出状态、同时返回有效检查数据时，`complete` 进入现有有界等待，而不是返回 `checks_or_review_blocking`。
- [x] 检查等待后通过时，`complete` 在同一次运行中继续合并；等待超时返回 `DISPATCH_REQUIRED / checks_pending`。
- [x] 检查失败或取消时，返回 `REPLY_OR_FIX_REQUIRED / checks_or_review_blocking`，不继续等待或合并。
- [x] `complete` 和 `diagnose` 的停止输出直接包含等待、修复或重试动作；停止状态详情保留可机器读取的恢复信息。
- [x] 回归测试覆盖待处理特殊退出状态、等待后通过、超时、失败和取消场景，并先红后绿。

## Behavior evidence

- Red: 在基线 `cdc36fa8` 上模拟有效 pending（等待中）检查数据和 GitHub CLI 退出码 `8`，`required_checks()` 返回 `checks_or_review_blocking`。
- Green: 同一探针在本票据实现上返回有效检查数据；定向测试 `16 passed, 236 deselected`。
- Green: PR Flow 受影响测试 `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py tests/test_pr_flow_pi_extension.py`，结果 `265 passed`。
- Green: `build-and-verify verify --project .`，结果 `status: passed`。
