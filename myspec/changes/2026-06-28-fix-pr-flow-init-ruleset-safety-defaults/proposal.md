## Why

`pr-flow-init`（拉取请求流程初始化）在用户选择 GitHub Rulesets（GitHub 规则集）做 branch protection（分支保护）时，remote tasks（远端待办）没有默认列出限制删除和阻止强制推送。
这会让 agent（代理）执行远端配置时漏掉受保护分支最基础的破坏性操作限制。

## What Changes

- 在 branch protection（分支保护）问答模板中，明确 GitHub Rulesets（GitHub 规则集）remote tasks（远端待办）默认启用 `Restrict deletions`（限制删除）。
- 在同一 remote tasks（远端待办）中默认启用 `Block force pushes`（阻止强制推送）。
- 不新增 GitHub API（接口）写入能力，仍由 agent（代理）按 remote tasks（远端待办）执行远端配置。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `pr-flow-plugin`: PR Flow init（拉取请求流程初始化）问答模板的 GitHub Rulesets（GitHub 规则集）远端待办规则。

## Impact

- 影响 `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`（问答模板）。
- 影响 `tests/test_pr_flow_cli.py`（初始化问卷验收测试）。
