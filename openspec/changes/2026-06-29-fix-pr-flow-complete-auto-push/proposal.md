## Why

`pr-flow-complete`（完成流程）现在遇到未推送的功能分支时停在 `PUSH_REQUIRED`（需要推送），用户还要手动跑 `git push`（推送）。这让“完成流程”在最常见的功能分支收尾场景里断开。

根因是 `complete`（完成流程）只检测 missing upstream（缺少上游分支）并输出下一步命令，没有在安全前提满足时执行普通推送。

## What Changes

- `complete`（完成流程）在创建或同步 PR（拉取请求）前，允许自动执行普通 `push`（推送）。
- 自动推送前必须确认本地工作区干净。
- 自动推送前必须确认当前分支不是 `defaults.baseBranch`（默认目标分支）。
- 自动推送前必须通过 GitHub（代码托管平台）远端查询确认当前分支不受保护；查询失败或不确定时停止。
- 不做 `force push`（强制推送），不修改 `hotfix`（热修复）直推路径。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `pr-flow-plugin`: `complete`（完成流程）对未推送功能分支的处理从只提示改为安全自动普通推送。

## Impact

- 影响 `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`（流程脚本）。
- 影响 `tests/test_pr_flow_cli.py`（测试）。
- 不新增依赖，不改变公开命令参数。
