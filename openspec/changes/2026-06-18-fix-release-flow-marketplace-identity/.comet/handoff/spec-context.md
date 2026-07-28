# Comet Spec Context

- Change: fix-release-flow-marketplace-identity
- Phase: design
- Mode: beta
- Context hash: 7ec9a922ecaa4184f6db400a8bf980558a9b0976ce45bb73dd157d05869ebc52

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/fix-release-flow-marketplace-identity/proposal.md
- SHA256: 276f644871f5cadc2154742b6efc37a51632e9ff363f623bc98c2564e8ec3c21
- Source: openspec/changes/fix-release-flow-marketplace-identity/design.md
- SHA256: 25b901f8b2ff3a8a07ce28640e7be9a5613670659b55a6ae0456b030bf24af24
- Source: openspec/changes/fix-release-flow-marketplace-identity/tasks.md
- SHA256: e584c709a0870c0585233573823798ea13df1d3061ce371e1e340f7c0c6b1951
- Source: openspec/changes/fix-release-flow-marketplace-identity/specs/agent-guard-plugin-runtime/spec.md
- SHA256: 10d3b9ef49717b749b2c98bee1a1ad126454ad3848b47bb0181cd0da3f96db50
- Source: openspec/changes/fix-release-flow-marketplace-identity/specs/release-flow-plugin/spec.md
- SHA256: c30b81eec1927464ce1fbaa81e996d0887bf7ce6e046dd9daf0c34465c6399f3

## Acceptance Projection

## openspec/changes/fix-release-flow-marketplace-identity/specs/agent-guard-plugin-runtime/spec.md

- Source: openspec/changes/fix-release-flow-marketplace-identity/specs/agent-guard-plugin-runtime/spec.md
- Lines: 1-27
- SHA256: 10d3b9ef49717b749b2c98bee1a1ad126454ad3848b47bb0181cd0da3f96db50

```md
## ADDED Requirements

### Requirement: Installer 使用共享 marketplace identity
Agent Guard installer（安装器）MUST 使用 release-flow 共享 marketplace identity（市场身份）生成和验证 marketplace catalog（市场目录），不得把正式 marketplace 名称只硬编码在 installer 内部。

#### Scenario: 默认 catalog root 读取 identity
- **WHEN** installer 生成 Codex 或 Claude marketplace catalog
- **THEN** Codex catalog name 和 display name MUST 来自共享 marketplace identity
- **THEN** Claude catalog name 和 owner name MUST 来自共享 marketplace identity

#### Scenario: 验证拒绝 identity 不一致
- **WHEN** installer 验证 marketplace catalog
- **THEN** 它 MUST 拒绝和共享 marketplace identity 不一致的 catalog name、display name 或 owner name
- **THEN** 错误输出 MUST 指出实际值和期望值

### Requirement: Source repo 与 repo scope marketplace 边界
系统 MUST 区分本仓库 source branch（源分支）的 marketplace 文件边界和 installer 的 repo scope（仓库作用域）安装行为。

#### Scenario: 本仓库 main 不需要 Codex repo marketplace
- **WHEN** Agent Guard Plugin 在本仓库 source branch 中开发
- **THEN** installer package verification（包验证）MUST NOT 要求 `.agents/plugins/marketplace.json` 作为持久源文件存在
- **THEN** Codex repo-local marketplace 缺失 MUST NOT 被视为插件包不完整

#### Scenario: 目标项目 repo scope 仍可显式写入
- **WHEN** 用户以 repo scope 对目标项目运行授权安装
- **THEN** installer MAY 写入用户显式传入的 Codex repo marketplace 路径
- **THEN** 该行为 MUST NOT 重新要求本仓库 main 分支保存 Codex repo-local marketplace 文件
```

## openspec/changes/fix-release-flow-marketplace-identity/specs/release-flow-plugin/spec.md

- Source: openspec/changes/fix-release-flow-marketplace-identity/specs/release-flow-plugin/spec.md
- Lines: 1-63
- SHA256: c30b81eec1927464ce1fbaa81e996d0887bf7ce6e046dd9daf0c34465c6399f3

```md
## ADDED Requirements

### Requirement: Marketplace identity 注册
系统 MUST 在 `.release-flow/projection.yaml` 的 project projection（项目投影）语义中声明单一 marketplace identity（市场身份），并让 release-flow 的模板、配置方案和发布检查共同读取该 identity。

#### Scenario: 声明正式 marketplace identity
- **WHEN** 项目启用 release-flow
- **THEN** 系统 MUST 声明 Codex marketplace catalog name（目录名）和 display name（显示名）
- **THEN** 系统 MUST 声明 Claude marketplace catalog name（目录名）和 owner name（所有者名）
- **THEN** 系统 MUST 声明 release-flow plugin repository（插件仓库）和 ref（引用）
- **THEN** 这些 identity 字段 MUST 位于 `.release-flow/projection.yaml`，而不是 `.release-flow/config.yaml`

#### Scenario: 模板共享 identity
- **WHEN** release-flow 生成 projection（发布投影）或 GitHub workflow（工作流）模板
- **THEN** 生成内容 MUST 引用同一 marketplace identity
- **THEN** 生成内容 MUST NOT 硬编码和 identity 不一致的旧 marketplace 名称

### Requirement: 发布插件来源变量声明
系统 MUST 显式声明并校验 release-flow workflow 使用的 release-flow plugin source variables（插件来源变量）。

#### Scenario: 初始化模板声明插件来源变量
- **WHEN** 生成 release-flow 初始化模板
- **THEN** projection 模板 MUST 声明 `RELEASE_FLOW_PLUGIN_REPOSITORY`
- **THEN** projection 模板 MUST 声明 `RELEASE_FLOW_PLUGIN_REF`
- **THEN** 两个变量 MUST 标记为 required GitHub Actions Variables（必需仓库变量）

#### Scenario: GitHub 配置方案展示插件来源变量
- **WHEN** 用户运行 `github-plan` 或 `configure-github --dry-run`
- **THEN** 输出 MUST 包含 `RELEASE_FLOW_PLUGIN_REPOSITORY`
- **THEN** 输出 MUST 包含 `RELEASE_FLOW_PLUGIN_REF`
- **THEN** 输出 MUST 说明这些变量用于 checkout release-flow plugin

#### Scenario: 发布前检查拒绝缺失插件来源变量
- **WHEN** 执行 `preflight` 且 GitHub Actions Variables 快照缺少 `RELEASE_FLOW_PLUGIN_REPOSITORY` 或 `RELEASE_FLOW_PLUGIN_REF`
- **THEN** 系统 MUST 拒绝发布前检查
- **THEN** 错误输出 MUST 包含缺失变量名、变量含义和手动设置步骤

### Requirement: Codex marketplace 由发布流程生成
系统 MUST 允许 source branch（源分支）不持久保存 Codex repo-local marketplace（仓库本地市场）文件，并在 release channel（发布通道）生成正式 Codex marketplace catalog。

#### Scenario: main 分支不保存 Codex repo-local marketplace
- **WHEN** 仓库处于开发 source branch
- **THEN** 仓库 MUST NOT 依赖 `.agents/plugins/marketplace.json` 作为持久 repo-local marketplace 文件
- **THEN** Codex Desktop MUST NOT 因打开本仓库而额外发现一个同名本地 marketplace

#### Scenario: 发布分支生成 Codex marketplace
- **WHEN** release workflow 从 source branch 生成 `marketplace` 分支
- **THEN** 系统 MUST 能在 source branch 缺少 `.agents/plugins/marketplace.json` 时生成该文件
- **THEN** 生成的 catalog MUST 使用 marketplace identity 中的 Codex name 和 display name
- **THEN** 生成的 catalog MUST 包含发布插件条目

### Requirement: Marketplace identity 漂移检查
系统 MUST 在发布前检查和发布投影中发现 marketplace identity 与生成产物不一致的漂移。

#### Scenario: 拒绝旧名残留
- **WHEN** 生成产物或 channel tree（通道树）中存在和 marketplace identity 不一致的旧 marketplace name
- **THEN** `preflight` MUST 拒绝继续
- **THEN** 错误输出 MUST 指出不一致字段和期望 identity 值

#### Scenario: 拒绝未声明 marketplace 差异
- **WHEN** `marketplace` 分支中的 marketplace catalog 与 source branch 加 projection 生成的 expected tree（期望树）不一致
- **THEN** `preflight` MUST 拒绝未被 projection 或 identity 声明的差异
- **THEN** 系统 MUST 保持不调用真实 GitHub Settings API 的首版边界
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
