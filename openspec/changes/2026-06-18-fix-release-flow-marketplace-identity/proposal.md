## Why

当前 marketplace identity（市场身份）分散在 repo-local marketplace 文件、release-flow projection（发布投影）、GitHub Actions Variables（仓库变量）、workflow 模板和 installer（安装器）默认值中。结果是 main 分支会被 Codex Desktop 识别成本地 marketplace，正式订阅又指向同名 marketplace，容易出现重复入口、旧名残留和发布时才暴露的变量缺失。

本变更把 identity 收敛为单一来源，并让 release-flow 在初始化、发布前检查和发布分支生成时显式校验它，避免 #38、#39、#40 这三个问题继续反复出现。

## What Changes

- 移除 main 分支对 repo-local Codex marketplace 持久文件的依赖；发布分支需要的 Codex marketplace catalog（市场目录）由 release workflow（发布工作流）从模板和 identity 生成。
- 扩展 `.release-flow/projection.yaml` 的语义，在 project projection（项目投影）中声明 marketplace identity，包括 Codex/Claude marketplace name（市场名）、display/owner name（显示名/所有者名）、release-flow plugin repository/ref（插件仓库/引用）等字段。
- 让 projection、workflow variables（工作流变量）、GitHub expected settings（期望设置）、`github-plan`、`configure-github --dry-run` 和 `preflight` 共享同一 projection identity 声明。
- 明确校验 `RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF`，缺失时输出变量含义和手动修复步骤。
- 让 Agent Guard installer 的 marketplace 默认值和校验逻辑读取同一 identity，避免硬编码旧 marketplace 名。
- 增加测试覆盖源分支无 repo-local Codex marketplace、发布分支生成 marketplace、变量缺失、identity 漂移和旧名残留阻断。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `release-flow-plugin`: 发布流程需要声明并校验单一 marketplace identity、发布插件来源变量，以及由模板生成发布分支 marketplace 的行为。
- `agent-guard-plugin-runtime`: installer 生成和验证 marketplace entry 时需要使用同一 identity，并区分本仓库 main 分支不保留 Codex repo-local marketplace 与目标项目 repo scope 安装行为。

## Impact

- 影响 release-flow CLI、projection 模板、GitHub workflow 模板、preflight 和发布分支生成逻辑。
- 影响 Agent Guard installer 的 marketplace catalog 默认值、repo/personal scope 校验和相关说明。
- 影响本仓库 `.release-flow/` 配置、marketplace catalog 文件布局、OpenSpec specs、release-flow/agent-guard 测试。
