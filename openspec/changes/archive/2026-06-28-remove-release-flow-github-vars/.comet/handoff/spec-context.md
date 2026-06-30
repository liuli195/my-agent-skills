# Comet Spec Context

- Change: remove-release-flow-github-vars
- Phase: design
- Mode: beta
- Context hash: c8557bdbdb223a076b6c83f05ee78e8d612ce0748aec954c4eeca9a52d7ab38f

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/remove-release-flow-github-vars/proposal.md
- SHA256: d59b5c01e854f70ca57cf6386106ca8a8ff9a5f6624d499c3a8f062ff9adc3c8
- Source: openspec/changes/remove-release-flow-github-vars/design.md
- SHA256: c04540004e5b7514dcf62c5bffcdf0a3f7b5f84efb9d084b53f93ea8945ee266
- Source: openspec/changes/remove-release-flow-github-vars/tasks.md
- SHA256: e6dc0dfe703e682da7f80d45493f8b10d9c96dabff85e30b016aaaccf0dfa478
- Source: openspec/changes/remove-release-flow-github-vars/specs/release-flow-plugin/spec.md
- SHA256: 71a9533ba8b228c001535bae9f4f4fdc6f5e24525794a97adaec809298e38667

## Acceptance Projection

## openspec/changes/remove-release-flow-github-vars/specs/release-flow-plugin/spec.md

- Source: openspec/changes/remove-release-flow-github-vars/specs/release-flow-plugin/spec.md
- Lines: 1-186
- SHA256: 71a9533ba8b228c001535bae9f4f4fdc6f5e24525794a97adaec809298e38667

```md
## MODIFIED Requirements

### Requirement: 发布投影变量注册表

系统 MUST 使用 `.release-flow/projection.yaml` 保存从 `main` 生成 latest channel（最新通道）的轻量发布投影规则，并将该文件纳入 Git 版本管理。

#### Scenario: 注册变量

- **WHEN** projection（发布投影）声明变量
- **THEN** 每个变量 MUST 声明 source（来源）、required（是否必填）、sensitive（是否敏感）和 description（说明）
- **THEN** source MUST 支持 `github-actions-variable`

#### Scenario: 禁止保存变量值

- **WHEN** projection 声明变量
- **THEN** projection MUST NOT 保存变量值
- **THEN** projection MAY 保存 `example` 或 `description` 这类非敏感说明字段

#### Scenario: 声明 JSON 注入规则

- **WHEN** projection 声明 transforms（转换）
- **THEN** transform MUST 声明目标文件路径
- **THEN** transform type MUST 支持 `json-env`
- **THEN** transform MUST 使用 JSON Pointer（JSON 指针）声明字段路径到 projection identity（投影身份）引用的映射

#### Scenario: 非敏感发布身份来自 projection

- **WHEN** 发布流程需要 marketplace identity（市场身份）这类非敏感发布身份
- **THEN** 变量值 MUST 从 `.release-flow/projection.yaml` 的 identity（身份）读取
- **THEN** release-flow init/preflight MUST NOT 要求这些非敏感身份存在于 GitHub Actions Variables
- **THEN** release-flow MUST NOT 要求用户为这些非敏感身份准备本地环境变量或变量文件
- **THEN** projection MUST NOT 将 `CODEX_MARKETPLACE_CATALOG_NAME`、`CODEX_MARKETPLACE_DISPLAY_NAME`、`CLAUDE_MARKETPLACE_CATALOG_NAME`、`CLAUDE_MARKETPLACE_OWNER_NAME`、`RELEASE_FLOW_PLUGIN_REPOSITORY` 或 `RELEASE_FLOW_PLUGIN_REF` 声明为 GitHub Actions Variables

#### Scenario: 应用投影不接收变量文件

- **WHEN** 用户运行 `project`
- **THEN** 系统 MUST NOT 接收 `--vars-file`
- **THEN** 系统 MUST 直接从 `.release-flow/projection.yaml` 的 identity 读取非敏感发布身份

### Requirement: 项目启用阶段

系统 MUST 提供 project setup（项目启用）阶段，用于调研仓库、生成目标项目配置，并输出 GitHub 配置方案。首版 MUST NOT 在没有额外实现仓库上下文和认证回读前修改 GitHub 仓库设置。

#### Scenario: 生成目标项目配置

- **WHEN** 用户在目标项目启用 release-flow
- **THEN** 系统 MUST 生成 `.release-flow/config.yaml`
- **THEN** 系统 MUST 生成 `.release-flow/projection.yaml`
- **THEN** 系统 MUST 生成 `.release-flow/.gitignore` 并忽略 `/releases/`
- **THEN** 系统 MUST 从插件模板生成目标项目的薄 GitHub Workflow 入口
- **THEN** 系统 MUST NOT 将插件内的发布脚本复制到目标项目仓库
- **THEN** 系统 MUST NOT 创建 `.release-flow/releases/<tag>/release-plan.json`

#### Scenario: 生成 GitHub 配置方案

- **WHEN** 项目启用阶段检查 GitHub 仓库
- **THEN** 系统 MUST 输出 Actions 权限和 Rulesets 的期望配置方案
- **THEN** 系统 MUST NOT 输出非敏感 marketplace identity 的 GitHub Actions Variables 配置方案

#### Scenario: 授权后修改 GitHub 配置

- **WHEN** 用户明确授权自动配置 GitHub
- **THEN** 首版系统 MUST 报告自动写入 GitHub 暂不可用
- **THEN** 系统 MUST NOT 调用真实 GitHub 设置 API
- **THEN** 后续版本 MAY 使用 `gh` 或 GitHub API 修改仓库设置并回读验证结果

#### Scenario: 未授权时输出手动步骤

- **WHEN** 用户未授权自动配置 GitHub
- **THEN** 系统 MUST 输出用户可手动执行的配置步骤
- **THEN** 系统 MUST NOT 修改 GitHub 仓库设置

### Requirement: 发布前检查

系统 MUST 提供 release-flow preflight（发布前检查）阶段，用于在发布前验证本地配置、版本、manifest（清单）和发布投影。GitHub 仓库设置 MUST 由 `github-plan` 和 `configure-github --dry-run` 输出方案与手动步骤；认证远端回读验证 MAY 在后续版本加入。

#### Scenario: 检查配置文件

- **WHEN** 执行 preflight
- **THEN** 系统 MUST 验证 `.release-flow/config.yaml` 存在且合法
- **THEN** 系统 MUST 验证 `.release-flow/projection.yaml` 存在且合法

#### Scenario: 不接收变量快照

- **WHEN** 执行 preflight
- **THEN** 系统 MUST NOT 接收 `--github-vars-file`
- **THEN** 系统 MUST NOT 要求 GitHub Actions Variables 快照
- **THEN** 系统 MUST 从 `.release-flow/projection.yaml` 的 identity 读取非敏感发布身份

#### Scenario: GitHub 仓库设置首版边界

- **WHEN** 执行 preflight
- **THEN** 系统 MUST NOT 调用真实 GitHub API
- **THEN** 系统 MUST NOT 声称已回读验证 GitHub Rulesets 或 workflow permissions
- **THEN** 系统 MUST 依赖 `github-plan` 和 `configure-github --dry-run` 输出 Actions 权限与 Rulesets 的手动配置步骤

#### Scenario: 检查版本一致性

- **WHEN** 执行 preflight
- **THEN** 系统 MUST 验证 release-plan tag（发布计划标签）与 manifest version（清单版本）一致

#### Scenario: 检查发布投影

- **WHEN** 执行 preflight
- **THEN** 系统 MUST 在临时目录中从 source branch（源分支）和 projection（发布投影）生成 expected marketplace tree（期望市场分支树）
- **THEN** 系统 MUST 拒绝无法生成的发布投影
- **THEN** 系统 MUST NOT 要求旧 `marketplace` 分支已经等于待发布投影
- **THEN** `preflight` MUST NOT 接收 `--channel-tree`

### Requirement: 发布执行阶段

系统 MUST 提供 release-flow publish（发布）阶段，通过 GitHub Workflow 执行发布，本地不得执行发布 Git 写操作。

#### Scenario: 本地只触发 workflow

- **WHEN** 用户执行 publish
- **THEN** 本地系统 MUST 使用 `workflow_dispatch` 触发 GitHub Workflow
- **THEN** 本地系统 MUST NOT 创建发布分支
- **THEN** 本地系统 MUST NOT 创建 tag
- **THEN** 本地系统 MUST NOT push 发布内容

#### Scenario: 发布试运行输出明确字段

- **WHEN** 用户执行 `publish --dry-run`
- **THEN** 输出 MUST 包含 `release_tag` 表示 release tag（发布标签）
- **THEN** 输出 MUST 包含 `git_tag_created: false`
- **THEN** 输出 MUST 包含 `local_branch_created: false`
- **THEN** 输出 MUST 包含 `push_run: false`
- **THEN** 输出 MUST NOT 包含重复的 `tag` 字段

#### Scenario: GitHub Workflow 执行发布

- **WHEN** GitHub Workflow 运行
- **THEN** workflow MUST checkout 配置指定的 source ref
- **THEN** workflow MUST 安装 release-flow 脚本依赖
- **THEN** workflow MUST 直接运行 source repo 内的 release-flow 脚本
- **THEN** workflow MUST 读取 source repo 内的 `.release-flow/projection.yaml`
- **THEN** workflow MUST 从 projection identity 读取非敏感 marketplace identity
- **THEN** workflow MUST 应用 projection transforms
- **THEN** workflow MUST 创建或更新远端 `marketplace` 分支
- **THEN** workflow MUST 创建 tag
- **THEN** workflow MUST 创建 GitHub Release
- **THEN** `ci-publish` MUST NOT 提供 `--dry-run` 分支逻辑
- **THEN** `ci-publish` MUST NOT 接收 `--vars-file`

### Requirement: Marketplace identity 注册
系统 MUST 在 `.release-flow/projection.yaml` 的 project projection（项目投影）语义中声明单一 marketplace identity（市场身份），并让 release-flow 的模板、配置方案和发布检查共同读取该 identity。

#### Scenario: 声明正式 marketplace identity
- **WHEN** 项目启用 release-flow
- **THEN** 系统 MUST 声明 Codex marketplace catalog name（目录名）和 display name（显示名）
- **THEN** 系统 MUST 声明 Claude marketplace catalog name（目录名）和 owner name（所有者名）
- **THEN** 系统 MUST NOT 声明 release-flow plugin repository（插件仓库）或 ref（引用）作为 marketplace identity 字段
- **THEN** 这些 identity 字段 MUST 位于 `.release-flow/projection.yaml`，而不是 `.release-flow/config.yaml`

#### Scenario: 模板共享 identity
- **WHEN** release-flow 生成 projection（发布投影）或 GitHub workflow（工作流）模板
- **THEN** 生成内容 MUST 引用同一 marketplace identity
- **THEN** 生成内容 MUST NOT 硬编码和 identity 不一致的旧 marketplace 名称

### Requirement: 发布插件来源变量声明

系统 MUST 不再要求 release-flow workflow 使用 GitHub Variables 声明 release-flow plugin source（插件来源）。

#### Scenario: 初始化模板不声明插件来源变量

- **WHEN** 生成 release-flow 初始化模板
- **THEN** projection 模板 MUST NOT 声明 `RELEASE_FLOW_PLUGIN_REPOSITORY`
- **THEN** projection 模板 MUST NOT 声明 `RELEASE_FLOW_PLUGIN_REF`
- **THEN** 两个变量 MUST NOT 声明为 GitHub Actions Variables（仓库变量）

#### Scenario: GitHub 配置方案不展示插件来源变量

- **WHEN** 用户运行 `github-plan` 或 `configure-github --dry-run`
- **THEN** 输出 MUST NOT 包含 `RELEASE_FLOW_PLUGIN_REPOSITORY`
- **THEN** 输出 MUST NOT 包含 `RELEASE_FLOW_PLUGIN_REF`
- **THEN** 输出 MUST NOT 包含 `CODEX_MARKETPLACE_CATALOG_NAME`
- **THEN** 输出 MUST NOT 包含 `CODEX_MARKETPLACE_DISPLAY_NAME`
- **THEN** 输出 MUST NOT 包含 `CLAUDE_MARKETPLACE_CATALOG_NAME`
- **THEN** 输出 MUST NOT 包含 `CLAUDE_MARKETPLACE_OWNER_NAME`

#### Scenario: 发布前检查不检查插件来源变量

- **WHEN** 执行 `preflight`
- **THEN** 系统 MUST NOT 检查 `RELEASE_FLOW_PLUGIN_REPOSITORY`
- **THEN** 系统 MUST NOT 检查 `RELEASE_FLOW_PLUGIN_REF`
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
