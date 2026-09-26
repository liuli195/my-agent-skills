## Why

`diagnose`（诊断）在功能分支已经推送但 PR（拉取请求）尚不存在时，会把 `gh pr view`（查看拉取请求）的未找到结果显示成 `gh_pr_view_failed`（查看失败）。这让用户无法区分“还没创建 PR”和真实 `gh`（GitHub 命令行）异常。

## What Changes

- 在 `diagnose`（诊断）中识别 `gh pr view`（查看拉取请求）的 no pull request（无拉取请求）结果。
- 对非目标分支输出 `DISPATCH_REQUIRED`（需要外部进展）和 `complete`（收尾）下一步。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。已有 stop state（停止状态）模型不变，只修复分类。

## Impact

- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- `tests/test_pr_flow_cli.py`
