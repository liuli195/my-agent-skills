## Why

`release-flow` 发布流程把非敏感发布身份同时放在 `.release-flow/projection.yaml` 和 GitHub Variables 里，导致自发布时需要重复维护同一批信息。最近多次发布已经复现：远端变量存在，但本地 `preflight` 仍要求手工导出变量文件，流程复杂且容易误判。

## What Changes

- **BREAKING**: 移除 `release-flow preflight --github-vars-file` 变量快照入口。
- **BREAKING**: 移除 `release-flow ci-publish --vars-file` 变量文件入口。
- **BREAKING**: 移除 `release-flow project --vars-file` 变量文件入口。
- **BREAKING**: `CODEX_MARKETPLACE_CATALOG_NAME`、`CODEX_MARKETPLACE_DISPLAY_NAME`、`CLAUDE_MARKETPLACE_CATALOG_NAME`、`CLAUDE_MARKETPLACE_OWNER_NAME`、`RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF` 不再声明为 release-flow GitHub Variables。
- `project`、`preflight` 和 `ci-publish` 直接从 `.release-flow/projection.yaml` 的 `identity` 读取非敏感 marketplace 身份。
- `github-plan` 和 `configure-github --dry-run` 不再输出这些非敏感 marketplace GitHub Variables。
- GitHub workflow 直接运行 source repo 内的 `release-flow` 脚本，不再 checkout 外部 release-flow 插件仓库。
- release-flow 初始化模板、当前仓库配置、规格和测试同步删除旧变量文件路径。

## Capabilities

### New Capabilities

### Modified Capabilities
- `release-flow-plugin`: project、发布前检查、CI 发布和 GitHub 配置方案不再依赖非敏感 GitHub Variables 或变量文件，改用 projection identity 作为唯一来源。

## Impact

- 影响 `plugins/release-flow/skills/release-flow/scripts/release_flow.py`。
- 影响 release-flow 的 GitHub workflow 模板和当前仓库 `.github/workflows/release.yml`。
- 影响 `.release-flow/projection.yaml` 及 release-flow projection 模板。
- 影响 `openspec/specs/release-flow-plugin/spec.md`。
- 影响 `tests/test_release_flow_cli.py`。
- 不新增依赖，不新增环境变量配置，不处理 Secrets。
