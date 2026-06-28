# release-flow-plugin Specification

## Purpose
TBD - created by archiving change standardize-agent-guard-release-flow. Update Purpose after archive.
## Requirements
### Requirement: 双端兼容发布流程插件

系统 MUST 提供 `release-flow` Plugin（发布流程插件），用于在多个项目中复用一致的 release flow（发布流程），并同时兼容 Codex 和 Claude。

#### Scenario: Codex 插件结构

- **WHEN** 发布 `release-flow` Plugin
- **THEN** 插件包 MUST 包含 `.codex-plugin/plugin.json`
- **THEN** Codex manifest（清单）MUST 声明稳定 kebab-case（短横线命名）的插件 `name`、`version`、`description` 和 `skills`

#### Scenario: Claude 插件结构

- **WHEN** 发布 `release-flow` Plugin
- **THEN** 插件包 MUST 包含 `.claude-plugin/plugin.json`
- **THEN** Claude manifest（清单）MUST 声明插件 `name`、`version` 和 `description`

#### Scenario: 共享技能脚本和模板

- **WHEN** 发布 `release-flow` Plugin
- **THEN** 插件包 MUST 包含 `skills/release-flow/SKILL.md`
- **THEN** 插件包 MUST 包含 `skills/release-flow/scripts/` 中的确定性脚本
- **THEN** 插件包 MUST 包含 `skills/release-flow/assets/templates/` 中的配置和 GitHub Workflow（工作流）模板

#### Scenario: 跨项目复用

- **WHEN** 一个项目安装或启用 `release-flow` Plugin
- **THEN** 插件 MUST 通过该项目的 `.release-flow/config.yaml` 和 `.release-flow/projection.yaml` 解析发布模型
- **THEN** 插件 MUST NOT 依赖 Agent Guard 专用路径或硬编码仓库名称

### Requirement: 发布流程配置

系统 MUST 使用 `.release-flow/config.yaml` 保存项目级发布流程配置，并将该文件纳入 Git 版本管理。

#### Scenario: 声明发布通道

- **WHEN** 项目配置声明 release（发布）信息
- **THEN** 配置 MUST 声明 source ref（源引用）、channel branch（通道分支）和 branch mode（分支模式）
- **THEN** branch mode MUST 支持 `remote-only`，表示本地不创建发布分支

#### Scenario: 声明 workflow 触发方式

- **WHEN** 项目配置声明 workflow（工作流）
- **THEN** 配置 MUST 声明 GitHub Workflow 文件路径
- **THEN** 配置 MUST 声明触发方式为 `workflow_dispatch`

#### Scenario: 声明本地发布记录目录

- **WHEN** 项目配置声明 records（记录）
- **THEN** 配置 MUST 声明 `.release-flow/releases` 为本地发布记录目录
- **THEN** 发布记录目录 MUST NOT 纳入 Git 版本管理

#### Scenario: 声明 GitHub 期望设置

- **WHEN** 项目配置声明 GitHub 仓库设置
- **THEN** 配置 MUST 支持声明 Actions 权限、Rulesets（规则集）、release channel（发布通道）写入规则和 tag（标签）规则
- **THEN** 首版 MUST 使用 Rulesets 模型
- **THEN** 首版 MUST NOT 要求 Branch Protection（分支保护）兜底

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
- **THEN** transform MUST 使用 JSON Pointer（JSON 指针）声明字段路径到变量名的映射

#### Scenario: 变量值托管到 GitHub

- **WHEN** 发布流程需要变量值
- **THEN** 变量值 MUST 从 GitHub Actions Variables 读取
- **THEN** release-flow init/preflight MUST 检查 required 变量在 GitHub Actions Variables 中存在

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
- **THEN** 系统 MUST 输出 Actions 权限、Rulesets 和 Actions Variables 的期望配置方案

#### Scenario: 授权后修改 GitHub 配置

- **WHEN** 用户明确授权自动配置 GitHub
- **THEN** 首版系统 MUST 报告自动写入 GitHub 暂不可用
- **THEN** 系统 MUST NOT 调用真实 GitHub 设置 API
- **THEN** 后续版本 MAY 使用 `gh` 或 GitHub API 修改仓库设置并回读验证结果

#### Scenario: 未授权时输出手动步骤

- **WHEN** 用户未授权自动配置 GitHub
- **THEN** 系统 MUST 输出用户可手动执行的配置步骤
- **THEN** 系统 MUST NOT 修改 GitHub 仓库设置

### Requirement: 单次发布初始化阶段

系统 MUST 提供 release init（单次发布初始化）阶段，用于在每次发布前创建本地 release-plan（发布计划）。

#### Scenario: 创建本次发布计划

- **WHEN** 用户准备发布某个 tag
- **THEN** 系统 MUST 创建 `.release-flow/releases/<tag>/release-plan.json`
- **THEN** release-plan MUST 包含 version、tag、sourceRef、channelBranch、workflow file 和 projection registry
- **THEN** 发布目录名 MUST 使用 tag
- **THEN** 系统 MUST NOT 创建本地发布分支
- **THEN** 系统 MUST NOT 创建 tag
- **THEN** 系统 MUST NOT push 发布内容

#### Scenario: 不提供发布初始化试运行

- **WHEN** 用户准备发布某个 tag
- **THEN** `release-init` MUST NOT 提供 `--dry-run` 分支逻辑
- **THEN** 预览发布命令 MUST 使用 `publish --dry-run`

### Requirement: 发布前检查

系统 MUST 提供 release-flow preflight（发布前检查）阶段，用于在发布前验证本地配置、变量输入、版本、manifest（清单）和发布投影。首版 GitHub 仓库设置 MUST 由 `github-plan` 和 `configure-github --dry-run` 输出方案与手动步骤；认证远端回读验证 MAY 在后续版本加入。

#### Scenario: 检查配置文件

- **WHEN** 执行 preflight
- **THEN** 系统 MUST 验证 `.release-flow/config.yaml` 存在且合法
- **THEN** 系统 MUST 验证 `.release-flow/projection.yaml` 存在且合法

#### Scenario: 检查变量

- **WHEN** 执行 preflight
- **THEN** 系统 MUST 验证 projection 中 required 变量存在于传入的 GitHub Actions Variables 快照
- **THEN** 系统 MUST 拒绝缺失变量

#### Scenario: GitHub 仓库设置首版边界

- **WHEN** 执行 preflight
- **THEN** 系统 MUST NOT 调用真实 GitHub API
- **THEN** 系统 MUST NOT 声称已回读验证 GitHub Rulesets 或 workflow permissions
- **THEN** 系统 MUST 依赖 `github-plan` 和 `configure-github --dry-run` 输出 Actions 权限、Rulesets 和 Actions Variables 的手动配置步骤

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
- **THEN** workflow MUST 读取 `.release-flow/projection.yaml`
- **THEN** workflow MUST 从 GitHub Actions Variables 读取变量值
- **THEN** workflow MUST 应用 `json-env` transforms
- **THEN** workflow MUST 创建或更新远端 `marketplace` 分支
- **THEN** workflow MUST 创建 tag
- **THEN** workflow MUST 创建 GitHub Release
- **THEN** `ci-publish` MUST NOT 提供 `--dry-run` 分支逻辑

### Requirement: 发布记录与总结

系统 MUST 在本地 `.release-flow/releases/<tag>/` 保存每次发布的本地审计记录，并确保该目录不进入 Git。

#### Scenario: 读取发布计划

- **WHEN** publish 读取本次发布信息
- **THEN** 系统 MUST 读取 `.release-flow/releases/<tag>/release-plan.json`
- **THEN** 系统 MUST 拒绝缺失 release-plan 的 publish

#### Scenario: 保存发布前检查结果

- **WHEN** preflight 完成
- **THEN** 系统 MUST 写入 `.release-flow/releases/<tag>/preflight-report.json`

#### Scenario: 保存 workflow 结果

- **WHEN** publish 触发 workflow
- **THEN** 系统 MUST 写入 `.release-flow/releases/<tag>/workflow-run.json`

#### Scenario: 输出发布总结

- **WHEN** 发布流程结束
- **THEN** 系统 MUST 写入 `.release-flow/releases/<tag>/release-summary.md`
- **THEN** 总结 MUST 包含 tag、GitHub Release URL、`marketplace` commit、变量检查结果和发布结论

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

- **WHEN** 生成产物中存在和 marketplace identity 不一致的旧 marketplace name
- **THEN** `preflight` MUST 拒绝继续
- **THEN** 错误输出 MUST 指出不一致字段和期望 identity 值
