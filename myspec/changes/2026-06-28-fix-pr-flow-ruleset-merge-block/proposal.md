## Why

当 `gh pr merge`（合并拉取请求）被 GitHub Rulesets（GitHub 规则集）或 base branch policy（目标分支策略）阻止时，`complete`（收尾）现在只输出 `EXCEPTION_REQUIRED / gh_pr_merge_failed`，用户需要手工理解 GitHub（代码托管平台）错误。

## What Changes

- 识别 `base branch policy prohibits the merge`（目标分支策略禁止合并）这类可等待阻塞。
- 输出 `DISPATCH_REQUIRED`（需要外部进展）和 `ruleset_merge_blocking`（规则集阻塞合并）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。已有 `DISPATCH_REQUIRED`（需要外部进展）状态可表达外部规则等待。

## Impact

- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- `tests/test_pr_flow_cli.py`
