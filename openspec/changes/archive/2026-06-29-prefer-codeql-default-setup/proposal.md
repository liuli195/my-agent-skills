## Why

PR Flow init（拉取请求流程初始化）现在把 CodeQL scan producer（CodeQL 扫描结果来源）说成“创建或启用”，并允许把 `Analyze Python` 放进 PR status checks（拉取请求状态检查）。这会把 GitHub CodeQL Default setup（GitHub CodeQL 默认配置）和 Advanced setup（高级配置）混在一起，导致 agent（代理）默认推荐本地 workflow（工作流）而不是远端默认配置。

## What Changes

- CodeQL security check（CodeQL 安全检查）开启时，GitHub setup guidance（GitHub 配置建议）默认要求启用 CodeQL Default setup（CodeQL 默认配置）。
- PR status checks（拉取请求状态检查）不得提供 `Analyze Python`、`Analyze (python)`、`Analyze (actions)` 或 `CodeQL` 这类 CodeQL（代码查询扫描）检查作为默认或高级选项。
- validate（校验）仍不确认远端状态；它只输出需要启用 Default setup（默认配置）和 Rulesets（规则集）code scanning（代码扫描）门禁的 remote tasks（远端待办）。
- 不删除现有 `.github/workflows/codeql.yml`，不自动修改 GitHub（代码托管平台）远端配置。

## Capabilities

### New Capabilities

### Modified Capabilities
- `pr-flow-plugin`: CodeQL security check（CodeQL 安全检查）默认扫描来源和 status checks（状态检查）选择规则。

## Impact

- Affected code（受影响代码）: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Affected guidance（受影响说明）: `plugins/pr-flow/skills/pr-flow-init/references/*.md`
- Affected tests（受影响测试）: `tests/test_pr_flow_cli.py`
- Affected spec（受影响规格）: `openspec/specs/pr-flow-plugin/spec.md`
