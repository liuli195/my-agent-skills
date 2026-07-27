## Why

PR Flow（拉取请求流程）在已有 upstream（上游分支）的分支上只检查本地 ahead（领先）提交数，不检查 remote（远端）behind（落后）提交数。已创建 PR（拉取请求）后本地 amend（改写提交）会形成 ahead/behind（领先/落后）分叉，当前流程会误判为可普通 push（推送）。

## What Changes

- complete（收尾）和 tweak（小改）共享的 safe auto-push（安全自动推送）逻辑改为同时检查 ahead（领先）和 behind（落后）。
- 当当前分支 behind（落后） upstream（上游分支）时，流程停止并给出明确恢复命令，不再尝试普通 push（推送）。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-flow-plugin`: safe auto-push（安全自动推送）需要拒绝 ahead/behind（领先/落后）分叉分支，并提示 rebase（变基）或 fast-forward（快进）恢复后重跑原命令。

## Impact

- Affected code（受影响代码）: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Affected tests（受影响测试）: `tests/test_pr_flow_cli.py`
- Affected spec（受影响规格）: `openspec/specs/pr-flow-plugin/spec.md`
- No new dependency（新依赖）.
