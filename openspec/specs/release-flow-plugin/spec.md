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

#### Scenario: 不声明本地发布记录目录

- **WHEN** 项目配置声明 release-flow（发布流程）设置
- **THEN** 配置 MUST NOT 声明本地 release record（发布记录）目录
- **THEN** 发布流程 MUST NOT 依赖 `.release-flow/releases/<tag>/` 持久目录

#### Scenario: 不声明 GitHub Rulesets 期望设置

- **WHEN** 项目配置声明 GitHub 仓库设置
- **THEN** 配置 MUST NOT 声明 GitHub Rulesets（GitHub 规则集）期望
- **THEN** preflight（发布前检查）MUST NOT 检查 GitHub Rulesets（GitHub 规则集）

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

系统 MUST 提供 project setup（项目启用）阶段，用于生成目标项目配置，并输出 GitHub Actions（GitHub 自动化任务）权限配置方案。首版 MUST NOT 在没有额外实现仓库上下文和认证回读前修改 GitHub 仓库设置。

#### Scenario: 生成目标项目配置

- **WHEN** 用户在目标项目启用 release-flow（发布流程）
- **THEN** 系统 MUST 生成 `.release-flow/config.yaml`（配置文件）
- **THEN** 系统 MUST 生成 `.release-flow/projection.yaml`（投影配置）
- **THEN** 系统 MUST 从插件模板生成目标项目的薄 GitHub Workflow（GitHub 工作流）入口
- **THEN** 系统 MUST NOT 生成只服务本地 release record（发布记录）的 `.release-flow/.gitignore`
- **THEN** 系统 MUST NOT 将插件内的发布脚本复制到目标项目仓库
- **THEN** 系统 MUST NOT 创建 `.release-flow/releases/<tag>/release-plan.json`（发布计划文件）

#### Scenario: 生成 GitHub 配置方案

- **WHEN** 项目启用阶段检查 GitHub 仓库
- **THEN** 系统 MUST 输出 Actions permissions（自动化任务权限）的期望配置方案
- **THEN** 系统 MUST NOT 输出 GitHub Rulesets（GitHub 规则集）的期望配置方案
- **THEN** 系统 MUST NOT 输出非敏感 marketplace identity（市场身份）的 GitHub Actions Variables（GitHub 变量）配置方案

#### Scenario: 授权后修改 GitHub 配置

- **WHEN** 用户明确授权自动配置 GitHub
- **THEN** 首版系统 MUST 报告自动写入 GitHub 暂不可用
- **THEN** 系统 MUST NOT 调用真实 GitHub 设置 API（接口）
- **THEN** 后续版本 MAY 使用 `gh`（GitHub 命令行）或 GitHub API（接口）修改仓库设置并回读验证结果

#### Scenario: 未授权时输出手动步骤

- **WHEN** 用户未授权自动配置 GitHub
- **THEN** 系统 MUST 输出用户可手动执行的 Actions permissions（自动化任务权限）配置步骤
- **THEN** 系统 MUST NOT 输出 GitHub Rulesets（GitHub 规则集）配置步骤
- **THEN** 系统 MUST NOT 修改 GitHub 仓库设置

### Requirement: 发布前检查

系统 MUST 提供 release-flow preflight（发布前检查）阶段，用于在发布前验证本地配置、发布输入、manifest（插件清单）、发布投影和远端发布冲突。

#### Scenario: 检查配置文件

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 验证 `.release-flow/config.yaml`（配置文件）存在且合法
- **THEN** 系统 MUST 验证 `.release-flow/projection.yaml`（投影配置）存在且合法

#### Scenario: 检查发布输入

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 验证 `tag`（标签）和 `version`（版本）一致
- **THEN** 系统 MUST 验证 `bumpPlugins`（提升插件列表）存在且只包含已注册插件

#### Scenario: 检查版本一致性

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 只要求 `bumpPlugins`（提升插件列表）声明的插件 manifest（插件清单）版本等于发布版本
- **THEN** 系统 MUST 拒绝未声明插件的 manifest（插件清单）版本不同于远端发布通道同路径版本

#### Scenario: 检查发布投影

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 验证 projection（投影）可以由单一 Plugin registry（插件注册表）生成
- **THEN** 系统 MUST 拒绝无法生成的发布投影
- **THEN** 系统 MUST NOT 要求用户在源码分支运行正式 marketplace（市场）projection（投影）

#### Scenario: 检查远端发布冲突

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST 检查远端 tag（标签）是否已存在
- **THEN** 系统 MUST 检查 GitHub Release（GitHub 发布）是否已存在
- **THEN** 任一已存在时 MUST 拒绝继续

#### Scenario: 不检查 GitHub Rulesets

- **WHEN** 执行 preflight（发布前检查）
- **THEN** 系统 MUST NOT 读取 GitHub Rulesets（GitHub 规则集）
- **THEN** 系统 MUST NOT 声称已验证 GitHub Rulesets（GitHub 规则集）

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

### Requirement: 插件发布清单单一注册表

系统 MUST 使用单一 Plugin registry（插件注册表）描述可发布插件，并从该注册表推导 projection（投影）校验、Codex marketplace（Codex 市场）生成和 manifest（插件清单）路径。

#### Scenario: 新增插件只需注册一次

- **WHEN** 维护者把插件加入发布范围
- **THEN** 系统 MUST 只要求在单一 Plugin registry（插件注册表）中声明该插件
- **THEN** projection（投影）校验、marketplace（市场）生成和 manifest（插件清单）版本检查 MUST 使用同一声明

#### Scenario: projection 插件未注册

- **WHEN** `.release-flow/projection.yaml`（投影配置）引用未注册插件
- **THEN** preflight（发布前检查）和 CI（持续集成）发布 MUST 拒绝继续
- **THEN** 错误 MUST 指出未注册插件名

### Requirement: 发布输入选择提升插件

系统 MUST 使用 `bumpPlugins`（提升插件列表）声明本次发布需要提升版本的插件。

版本漂移比较基准 MUST 是远端发布通道 `origin/<channelBranch>`（远端通道分支）中同路径 manifest（插件清单）的版本。

#### Scenario: 只提升部分插件

- **WHEN** `bumpPlugins`（提升插件列表）只包含部分插件
- **THEN** preflight（发布前检查）MUST 只要求这些插件的 manifest（插件清单）版本等于发布版本
- **THEN** 未声明插件的 manifest（插件清单）版本 MUST 等于远端发布通道同路径 manifest（插件清单）版本

#### Scenario: 不提升插件

- **WHEN** `bumpPlugins`（提升插件列表）为空列表
- **THEN** preflight（发布前检查）MUST 不要求任何插件 manifest（插件清单）版本等于发布版本
- **THEN** 任何 manifest（插件清单）版本与远端发布通道同路径 manifest（插件清单）版本不一致 MUST 被拒绝

#### Scenario: 未声明提升导致版本漂移

- **WHEN** 某个插件 manifest（插件清单）版本不同于远端发布通道同路径版本但不在 `bumpPlugins`（提升插件列表）中
- **THEN** preflight（发布前检查）MUST 拒绝继续
- **THEN** 错误 MUST 指出该插件需要加入 `bumpPlugins`（提升插件列表）或撤回版本变更

#### Scenario: 未声明新插件

- **WHEN** 某个插件在远端发布通道没有同路径 manifest（插件清单）且不在 `bumpPlugins`（提升插件列表）中
- **THEN** preflight（发布前检查）MUST 拒绝继续
- **THEN** 错误 MUST 指出该插件需要加入 `bumpPlugins`（提升插件列表）

### Requirement: 远端发布冲突检查

系统 MUST 在发布前检查和 CI（持续集成）发布前检查远端 tag（标签）和 GitHub Release（GitHub 发布）是否已存在。

#### Scenario: 远端 tag 已存在

- **WHEN** 远端已存在本次发布 tag（标签）
- **THEN** preflight（发布前检查）和 CI（持续集成）发布 MUST 拒绝继续
- **THEN** 输出 MUST 明确报告 release already exists（发布已存在）

#### Scenario: GitHub Release 已存在

- **WHEN** GitHub Release（GitHub 发布）已存在本次发布 tag（标签）
- **THEN** preflight（发布前检查）和 CI（持续集成）发布 MUST 拒绝继续
- **THEN** 输出 MUST 明确报告 release already exists（发布已存在）

### Requirement: 发布投影只在隔离发布环境执行

系统 MUST NOT 要求维护者在源码分支运行正式 marketplace（市场）projection（投影）。

#### Scenario: 本地源码分支保持 DEV 身份

- **WHEN** 维护者在源码分支执行发布前检查
- **THEN** preflight（发布前检查）MUST NOT 要求运行本地 `project`（投影）命令
- **THEN** 源码分支中的 DEV（开发）marketplace（市场）配置 MUST 保持不变

#### Scenario: CI 生成正式发布投影

- **WHEN** GitHub Workflow（GitHub 工作流）执行发布
- **THEN** CI（持续集成）MUST 在隔离发布树中应用正式 marketplace（市场）projection（投影）
- **THEN** 正式 marketplace（市场）身份 MUST 只写入发布通道产物

