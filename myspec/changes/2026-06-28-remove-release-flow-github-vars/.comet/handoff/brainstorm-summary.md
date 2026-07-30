# Brainstorm Summary

- Change: remove-release-flow-github-vars
- Date: 2026-06-29

## 已确认事实

- 不使用本地环境变量。
- 不保留旧 GitHub Variables 和变量文件兼容路径。
- 不考虑 Secrets 配置。
- 非敏感发布身份只来自 `.release-flow/projection.yaml` 的 `identity`。
- 自发布 workflow 直接运行 source repo 内的 release-flow 脚本。
- `release-flow project --vars-file` 也纳入本次破坏性删除范围。
- `CODEX_MARKETPLACE_CATALOG_NAME`、`CODEX_MARKETPLACE_DISPLAY_NAME`、`CLAUDE_MARKETPLACE_CATALOG_NAME`、`CLAUDE_MARKETPLACE_OWNER_NAME`、`RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF` 都不再声明为 GitHub Variables。

## 候选技术方案

- 推荐方案：删除所有变量文件入口，让 projection transform 直接解析 identity 引用。
- 备选方案：只删除 preflight 和 ci-publish 变量文件入口，保留 `project --vars-file`。该方案会留下旧变量模型，不符合“不保留兼容”的要求。
- 备选方案：保留旧参数但忽略。该方案会形成假兼容，增加歧义。

## 确认的技术方案

- 删除 `project --vars-file`、`preflight --github-vars-file` 和 `ci-publish --vars-file`。
- 让 `projection transform` 直接解析 `identity.*` 引用。
- workflow 直接运行 source repo 内的 release-flow 脚本。
- `github-plan` 和 `configure-github --dry-run` 只保留 Actions 权限和 Rulesets 输出，不再输出非敏感 marketplace GitHub Variables。
- 保留 `json-env` transform type 名称，避免无关配置格式重命名。

## 测试策略候选

- CLI 测试覆盖 preflight 无变量文件通过。
- CLI 测试覆盖 ci-publish 无变量文件生成 marketplace。
- CLI 测试覆盖旧变量参数被 argparse 拒绝。
- workflow 模板测试覆盖不再 checkout 外部 release-flow 插件。

## Spec Patch

- 补充 `project` 命令不再接收变量文件的验收场景。
- 补充项目启用和 GitHub 配置方案不再输出非敏感 marketplace GitHub Variables 的验收场景。
- 补充 Marketplace identity 不再声明 release-flow plugin repository/ref 的验收场景。
