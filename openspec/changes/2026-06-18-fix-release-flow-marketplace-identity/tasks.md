## 1. Tests First

- [x] 1.1 添加 release-flow 测试，覆盖 source branch 缺少 `.agents/plugins/marketplace.json` 时仍能生成发布分支 Codex marketplace。
- [x] 1.2 添加 release-flow 测试，覆盖缺失 `RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF` 时 preflight 输出清晰错误和手动配置步骤。
- [x] 1.3 添加 release-flow 测试，覆盖 marketplace identity 一致、旧名残留和 identity 漂移阻断。
- [x] 1.4 添加 Agent Guard installer 测试，覆盖 marketplace 默认值来自共享 identity，且本仓库 Codex repo marketplace 缺失不导致包验证失败。

## 2. Release-Flow Identity

- [x] 2.1 在 `.release-flow/projection.yaml` 中扩展 project projection 语义并声明 marketplace identity 字段，更新仓库 projection 与模板。
- [x] 2.2 让 GitHub workflow 模板、`github-plan` 和 `configure-github --dry-run` 从 projection identity 派生必需 GitHub Actions Variables。
- [x] 2.3 将 `RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF` 纳入模板、期望设置输出和 preflight required variable 校验。

## 3. Marketplace Generation

- [x] 3.1 为 Codex marketplace 增加从模板生成的发布路径，避免 release projection 依赖 main 分支持久保存 `.agents/plugins/marketplace.json`。
- [x] 3.2 更新 preflight expected channel tree 逻辑，校验生成 catalog 与 marketplace identity 一致，并拒绝未声明差异。
- [x] 3.3 从 main 分支移除 Codex repo-local marketplace 持久文件，同时保证 release workflow 仍生成正式 Codex marketplace。

## 4. Agent Guard Installer

- [x] 4.1 让 installer 的 Codex/Claude catalog root 和 expected marketplace entry 校验读取共享 identity。
- [x] 4.2 调整 package verification，区分本仓库 source branch 不需要 Codex repo-local marketplace 与目标项目 repo scope 安装。
- [x] 4.3 更新 installer 输出和错误信息，报告实际 identity、期望 identity 和修复路径。

## 5. Documentation And Verification

- [x] 5.1 更新 release-flow/Agent Guard 相关文档，说明 main 不保存 Codex repo-local marketplace，发布分支由 release-flow 生成。
- [x] 5.2 运行 OpenSpec strict validation，确认 delta spec 可归档。
- [x] 5.3 运行相关端到端回归：release-flow plugin/package/CLI、Agent Guard package/installer。
