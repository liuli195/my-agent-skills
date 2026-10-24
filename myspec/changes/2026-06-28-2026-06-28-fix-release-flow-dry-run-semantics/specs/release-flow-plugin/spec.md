## MODIFIED Requirements

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

### Requirement: Marketplace identity 漂移检查

系统 MUST 在发布前检查和发布投影中发现 marketplace identity 与生成产物不一致的漂移。

#### Scenario: 拒绝旧名残留

- **WHEN** 生成产物中存在和 marketplace identity 不一致的旧 marketplace name
- **THEN** `preflight` MUST 拒绝继续
- **THEN** 错误输出 MUST 指出不一致字段和期望 identity 值
