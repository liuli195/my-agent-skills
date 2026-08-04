# 02 — 有界刷新规则集阻塞并保留真实终态

**父问题：** #107

**What to build:** 当 GitHub 合并策略拒绝发生在检查完成传播窗口时，PR Flow 复核检查并进行一次有界刷新重试；确认仍被规则集阻塞后，保留准确的停止状态和平台错误。

**Blocked by:** 01 — 统一检查等待与失败恢复

**Status:** completed

- [x] 首次合并被策略拒绝且检查仍等待时，复用票据 01 的等待行为；检查失败或超时则原样返回检查停止状态。
- [x] 检查完成后，流程在保持源提交和目标提交不变的前提下进行一次有界刷新，并最多重试一次合并。
- [x] 刷新后仍被策略拒绝时，返回 `DISPATCH_REQUIRED / ruleset_merge_blocking`，保留原始平台错误，不误报为检查等待。
- [x] 不因该恢复路径创建空提交、使用管理员绕过或无限重试；既有匹配头提交和明确 `--auto` 建议的行为保持不变。
- [x] 回归测试覆盖检查等待后重试成功、刷新竞争和持续真实规则集阻塞。

## Behavior evidence

- Red: 新增持续规则集阻塞回归在实现前错误保留刷新后的平台错误，而不是首次合并错误。
- Green: PR Flow 定向测试 `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py tests/test_pr_flow_pi_extension.py`，结果 `266 passed`。
- Green: `build-and-verify verify --project .`，结果 `status: passed`。
- Note: 未执行真实 GitHub 远端 PR 冒烟；本次回归通过公开 `complete` 命令入口和命令替身覆盖停止状态。
