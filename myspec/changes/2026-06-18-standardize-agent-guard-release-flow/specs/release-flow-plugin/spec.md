## ADDED Requirements

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
- **THEN** release-plan MUST 包含 version、tag、sourceRef、channelBranch、workflow file、projection registry 和 dryRun 标记
- **THEN** 发布目录名 MUST 使用 tag
- **THEN** 系统 MUST NOT 创建本地发布分支
- **THEN** 系统 MUST NOT 创建 tag
- **THEN** 系统 MUST NOT push 发布内容

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

#### Scenario: 检查发布投影差异

- **WHEN** 执行 preflight
- **THEN** 系统 MUST 从 `main` 和 projection 生成 expected marketplace tree（期望市场分支树）
- **THEN** 系统 MUST 拒绝未被 projection 描述的 `main` 与 `marketplace` 差异

### Requirement: 发布执行阶段

系统 MUST 提供 release-flow publish（发布）阶段，通过 GitHub Workflow 执行发布，本地不得执行发布 Git 写操作。

#### Scenario: 本地只触发 workflow

- **WHEN** 用户执行 publish
- **THEN** 本地系统 MUST 使用 `workflow_dispatch` 触发 GitHub Workflow
- **THEN** 本地系统 MUST NOT 创建发布分支
- **THEN** 本地系统 MUST NOT 创建 tag
- **THEN** 本地系统 MUST NOT push 发布内容

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
