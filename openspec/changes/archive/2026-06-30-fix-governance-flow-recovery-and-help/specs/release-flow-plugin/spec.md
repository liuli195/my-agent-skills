## MODIFIED Requirements

### Requirement: 发布执行阶段

系统 MUST 提供 release-flow publish（发布）阶段，通过 GitHub Workflow（GitHub 工作流）执行发布，本地不得执行发布 Git（版本管理）写操作。

#### Scenario: 本地只触发 workflow

- **WHEN** 用户执行 publish（发布）
- **THEN** 本地系统 MUST 使用 `workflow_dispatch`（工作流触发）触发 GitHub Workflow（GitHub 工作流）
- **THEN** 本地系统 MUST 只传递 `tag`（标签）、`version`（版本）和 `bumpPlugins`（提升插件列表）
- **THEN** 本地系统 MUST NOT 创建发布分支
- **THEN** 本地系统 MUST NOT 创建 tag（标签）
- **THEN** 本地系统 MUST NOT push（推送）发布内容

#### Scenario: publish 不支持 dry-run

- **WHEN** 用户执行 `publish --dry-run`（发布试运行）
- **THEN** CLI（命令行接口） MUST reject（拒绝） the argument
- **THEN** 系统 MUST NOT print workflow dispatch（工作流触发） preview output（预览输出）

#### Scenario: publish workflow trigger retries EOF

- **WHEN** 用户执行 authorized publish（已授权发布）
- **AND** `gh workflow run`（触发工作流） fails with EOF（连接提前结束）
- **THEN** 本地系统 MUST retry（重试） the workflow trigger（工作流触发） with a bounded retry count
- **THEN** retry attempts（重试尝试） MUST NOT create local branches（本地分支）、tags（标签） or pushes（推送）
- **THEN** if a retry succeeds, publish（发布） MUST return success

#### Scenario: publish workflow trigger reports exhausted EOF retry

- **WHEN** 用户执行 authorized publish（已授权发布）
- **AND** every bounded retry of `gh workflow run`（触发工作流） fails with EOF（连接提前结束）
- **THEN** publish（发布） MUST return the final failure code
- **THEN** publish（发布） MUST preserve the final GitHub CLI（GitHub 命令行） output for diagnosis（诊断）
- **THEN** retry attempts（重试尝试） MUST NOT create local branches（本地分支）、tags（标签） or pushes（推送）

#### Scenario: GitHub Workflow 执行发布

- **WHEN** GitHub Workflow（GitHub 工作流）运行
- **THEN** workflow（工作流）MUST checkout（检出）配置指定的 source ref（源引用）
- **THEN** workflow（工作流）MUST 直接运行 source repo（源码仓库）内的 release-flow（发布流程）脚本
- **THEN** workflow（工作流）MUST 读取 source repo（源码仓库）内的 `.release-flow/projection.yaml`（投影配置）
- **THEN** workflow（工作流）MUST 在隔离发布树中应用 projection（投影）
- **THEN** workflow（工作流）MUST 创建或更新远端 `marketplace`（市场分支）
- **THEN** workflow（工作流）MUST 创建 tag（标签）
- **THEN** workflow（工作流）MUST 创建 GitHub Release（GitHub 发布）
- **THEN** `ci-publish`（持续集成发布）MUST NOT 提供 `--dry-run`（试运行）分支逻辑

#### Scenario: CI 输出发布追溯字段

- **WHEN** GitHub Workflow（GitHub 工作流）发布成功
- **THEN** 输出 MUST 包含 release URL（发布链接）
- **THEN** 输出 MUST 包含 marketplace commit（市场提交）
- **THEN** 输出 MUST 包含 tag commit（标签提交）
- **THEN** 输出 MUST 包含 workflow run URL（工作流运行链接）
