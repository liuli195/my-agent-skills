## Why

`pr-flow-init`（拉取请求流程初始化）的固定问答模板把本地运行配置、GitHub（代码托管平台）远端规则建议和用户可执行待办混在一起，导致初始化时容易误解默认 PR target branch（拉取请求目标分支）、branch protection（分支保护）、PR review（拉取请求代码审查）和 PR status checks（拉取请求状态检查）的边界。

本变更把初始化交互收敛为先自动检查、再少量单问题决策、最后用用户可读摘要展示本地写入和远端待办，避免 agent（代理）临场自由发挥。

## What Changes

- 更新 `pr-flow-init`（拉取请求流程初始化）问答模板，采用最新 6 问流程。
- 明确初始化问答必须每次只问一个问题。
- 明确 branch protection（分支保护）使用 GitHub Rulesets（GitHub 规则集）实现，并启用 `Require a pull request before merging`（合并前要求拉取请求）。
- branch protection（分支保护）候选分支必须来自自动检查得到的 remote branches（远端分支），不得固定写死。
- 将 PR status checks（拉取请求状态检查）作为独立问题，不再和 PR review（拉取请求代码审查）混问。
- PR status checks（拉取请求状态检查）候选项必须解释用途后再让用户选择。
- 在 PR status checks（拉取请求状态检查）后新增 CodeQL security check（CodeQL 安全检查）问题；开启时远端待办要求 `Require code scanning results`（要求代码扫描结果）、选择 `CodeQL`，并采用 GitHub 默认阈值。
- 将草案展示改为用户可读摘要，禁止展示完整 YAML（配置格式）草案。
- 将 validation（校验）摘要和 setup suggestion（配置建议）改为结构化、可执行的远端待办。
- 保留现有本地 `validate`（校验）和 `init`（初始化）脚本边界，不自动写 GitHub（代码托管平台）远端配置。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `pr-flow-plugin`: 修改 PR Flow init（拉取请求流程初始化）问答、草案展示和 GitHub（代码托管平台）远端建议契约。

## Impact

- 影响 `plugins/pr-flow/skills/pr-flow-init/SKILL.md`（初始化技能说明）。
- 影响 `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`（问答模板）。
- 影响 `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`（配置草案规则）。
- 影响 `plugins/pr-flow/skills/pr-flow-init/references/validation.md`（校验规则）。
- 影响 `tests/test_pr_flow_cli.py`（PR Flow 命令行测试）。
- `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 和 `skills/pr-flow/SKILL.md`（总入口）保留在验收范围内；只有 init（初始化）路由文案与新契约冲突时才修改。
- 影响 `openspec/specs/pr-flow-plugin/spec.md`（PR Flow 插件规格）的初始化契约。
