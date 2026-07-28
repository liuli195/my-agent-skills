## Why

`complete`（收尾）在当前功能分支尚未推送时，会继续调用 `gh pr create`（创建拉取请求）并把底层错误显示为 `gh_pr_create_failed`。同一状态下 `diagnose`（诊断）已经能返回 `PUSH_REQUIRED`（需要推送），两条入口表现不一致。

## What Changes

- 让 `complete`（收尾）在创建 PR（拉取请求）前检查当前非目标分支是否缺少 `upstream`（上游分支）。
- 缺少时直接输出 `PUSH_REQUIRED`（需要推送）和可执行的 `git push -u` 命令。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。已有规格已经要求缺少远端 head branch（功能分支）时输出 `PUSH_REQUIRED`，本次只是让 `complete`（收尾）遵守同一意图。

## Impact

- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- `tests/test_pr_flow_cli.py`
