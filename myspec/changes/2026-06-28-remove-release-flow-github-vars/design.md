## Context

当前 release-flow 把 marketplace identity 同时表达在两个地方：

- `.release-flow/projection.yaml` 的 `identity`
- GitHub Actions Variables 和本地导出的变量文件

这让自发布流程出现重复事实源。远端变量即使已经存在，本地 `preflight` 也无法直接读取，只能依赖用户手工导出 JSON 文件。本次修复不使用本地环境变量、不保留旧变量兼容、不考虑 Secrets。

## Goals / Non-Goals

**Goals:**

- 让 `.release-flow/projection.yaml` 的 `identity` 成为非敏感发布身份唯一来源。
- 删除 `project --vars-file`、`preflight --github-vars-file` 和 `ci-publish --vars-file`。
- 让 GitHub workflow 直接运行 source repo 内的 release-flow 脚本。
- 删除 `RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF` 必需变量。
- 删除 Codex/Claude marketplace name/display/owner 的 GitHub Variables 声明。

**Non-Goals:**

- 不从 GitHub API 回读 Variables。
- 不读取本地环境变量。
- 不保留旧变量文件兼容。
- 不改 Secrets 或凭据配置。

## Decisions

1. **直接使用 projection identity**

   release-flow 已经有 `projection.identity`，并且 generator 已用它生成 Codex marketplace。继续复用它，删除变量文件路径。`CODEX_MARKETPLACE_CATALOG_NAME`、`CODEX_MARKETPLACE_DISPLAY_NAME`、`CLAUDE_MARKETPLACE_CATALOG_NAME`、`CLAUDE_MARKETPLACE_OWNER_NAME`、`RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF` 都不再声明为 GitHub Variables。这样不新增配置层，也不引入依赖。

2. **把 transform 从变量名映射改成 identity 引用**

   现有 `transforms.set` 的值是变量名。改为指向 identity 引用，例如 `identity.codex.marketplaceName`。`apply_projection` 用现有 `projection_identity_value()` 解析引用并写入 JSON。保留 `json-env` 这个 transform type 名称，避免把本次修复扩大成配置格式重命名。

3. **workflow 运行 source 内脚本**

   workflow 已 checkout source 到 `source/`。发布命令改为运行 `source/plugins/release-flow/skills/release-flow/scripts/release_flow.py`，删除外部 release-flow plugin checkout。自发布时新版发布逻辑随 source 一起生效。

4. **GitHub 配置方案不再输出非敏感变量**

   `github-plan` 和 `configure-github --dry-run` 仍输出 Actions 权限和 Rulesets 手动步骤，但不再输出非敏感 marketplace GitHub Variables。`validate` 和 `release-init` 也不能因为这些变量缺失而失败。

5. **破坏旧入口，不做兼容层**

   `project --vars-file`、`preflight --github-vars-file` 和 `ci-publish --vars-file` 被移除。旧参数进入 argparse 错误即可，不增加迁移 shim。

## Risks / Trade-offs

- 旧项目仍依赖变量文件会失败 → 本次明确不保留兼容，失败是预期迁移信号。
- 旧 projection 仍使用变量名 transform 会失败 → 更新模板和当前仓库 projection，并由测试覆盖。
- workflow 依赖 source 内脚本路径 → release-flow 插件路径已经是仓库内固定结构，最小修复直接使用现有路径。
