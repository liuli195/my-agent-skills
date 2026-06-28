---
comet_change: remove-release-flow-github-vars
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-28-remove-release-flow-github-vars
status: final
---

# Remove Release-Flow GitHub Variables Design

## Context

`release-flow` 目前把非敏感发布身份同时放在 `.release-flow/projection.yaml` 和 GitHub Variables 里。自发布时，本地 `preflight` 还要求用户手工导出变量文件；workflow 也会 checkout 外部 release-flow 插件，导致发布新版 release-flow 时可能仍运行旧脚本。

本次修复不使用本地环境变量，不保留旧变量文件兼容，不考虑 Secrets 配置。

## Goals

- `.release-flow/projection.yaml` 的 `identity` 是非敏感发布身份唯一来源。
- 删除 `project --vars-file`、`preflight --github-vars-file` 和 `ci-publish --vars-file`。
- workflow 直接运行 source repo 内的 release-flow 脚本。
- 删除 `RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF` 必需变量。
- 删除 Codex/Claude marketplace name/display/owner 的 GitHub Variables 声明。

## Decisions

### 1. Projection Identity 是唯一来源

复用现有 `projection.identity` 和 `projection_identity_value()`。`CODEX_MARKETPLACE_CATALOG_NAME`、`CODEX_MARKETPLACE_DISPLAY_NAME`、`CLAUDE_MARKETPLACE_CATALOG_NAME`、`CLAUDE_MARKETPLACE_OWNER_NAME`、`RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF` 都不再声明为 GitHub Variables。`transforms.set` 的值从变量名改成 identity 引用，例如：

```yaml
transforms:
  - path: .agents/plugins/marketplace.json
    type: json-env
    set:
      /name: identity.codex.marketplaceName
      /interface/displayName: identity.codex.displayName
```

保留 `json-env` 这个 transform type 名称，只改变取值来源。这样改动小，避免把本次修复扩大成配置格式重命名。

### 2. 删除变量文件入口

删除三个旧入口：

- `release-flow project --vars-file`
- `release-flow preflight --github-vars-file`
- `release-flow ci-publish --vars-file`

旧参数让 `argparse` 直接拒绝，不做兼容 shim。

### 3. Workflow 运行 Source 内脚本

workflow 已经 checkout source 到 `source/`。发布命令直接运行：

```text
source/plugins/release-flow/skills/release-flow/scripts/release_flow.py
```

同时删除外部 release-flow 插件 checkout 和 release vars 临时文件。

### 4. GitHub 配置方案不再输出非敏感变量

`github-plan` 和 `configure-github --dry-run` 仍输出 Actions 权限和 Rulesets 手动步骤，但不再输出非敏感 marketplace GitHub Variables。`validate` 和 `release-init` 也不能因为这些变量缺失而失败。

## Risks / Trade-offs

- 旧项目仍传变量文件会失败。  
  缓解：这是本次确认的破坏性清理，测试覆盖旧参数被拒绝。

- `json-env` 名称仍带 env。  
  缓解：暂不重命名，避免额外配置迁移；它只是旧 transform type 名称。

- workflow 依赖 source 内固定路径。  
  缓解：release-flow 插件路径已是仓库内固定结构，自发布正需要这个路径。

## Testing

- CLI 测试覆盖 `project` 无变量文件应用 projection。
- CLI 测试覆盖 `preflight` 无变量文件写报告。
- CLI 测试覆盖 `ci-publish` 无变量文件发布 marketplace。
- CLI 测试覆盖 `validate`、`release-init`、`github-plan` 和 `configure-github --dry-run` 不要求或输出非敏感 GitHub Variables。
- CLI 测试覆盖 projection 模板和当前 projection 不声明这些非敏感 GitHub Variables。
- CLI 测试覆盖旧变量参数被拒绝。
- workflow 模板测试覆盖不再 checkout 外部 release-flow 插件、不再写 `release-vars.json`。
