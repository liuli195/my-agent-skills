# Comet Spec Context

- Change: standardize-agent-guard-release-flow
- Phase: design
- Mode: beta
- Context hash: 64710d634e90c8dd9351e5acf1da74d66196b0ead4200a049628afaf5c82a854

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/standardize-agent-guard-release-flow/proposal.md
- SHA256: 5a3c9201ea983c8707748ea321172b034e5224874fdb9e7b64c1559a9263a53b
- Source: openspec/changes/standardize-agent-guard-release-flow/design.md
- SHA256: 44a180bb812d928286c178c16b426e97eb6ef852a977ce7a847ebb3a69809e19
- Source: openspec/changes/standardize-agent-guard-release-flow/tasks.md
- SHA256: 312b5bb437da7552b5aed97e69226d2b4aba34e15e7df3f88a909c44fc914d8d
- Source: openspec/changes/standardize-agent-guard-release-flow/specs/agent-guard-plugin-runtime/spec.md
- SHA256: 51e902834998f6fe2f3c1f0ba925efdb86174e1a119a34765e5197845f012c31
- Source: openspec/changes/standardize-agent-guard-release-flow/specs/release-flow-plugin/spec.md
- SHA256: 15c85716d7d3e40ed312dc2d28b539c3ffa5ff3afa5c00fcdc1efdf7abbca4f7

## Acceptance Projection

## openspec/changes/standardize-agent-guard-release-flow/specs/agent-guard-plugin-runtime/spec.md

- Source: openspec/changes/standardize-agent-guard-release-flow/specs/agent-guard-plugin-runtime/spec.md
- Lines: 1-71
- SHA256: 51e902834998f6fe2f3c1f0ba925efdb86174e1a119a34765e5197845f012c31

```md
## MODIFIED Requirements

### Requirement: Marketplace 订阅入口

系统 MUST 支持通过 marketplace subscription（市场订阅）发布和验证 Agent Guard Plugin（代理守卫插件），并覆盖 personal marketplace（个人市场）、repo marketplace（仓库市场）、fixed release（固定版本发布）和 latest channel（最新通道）。Agent Guard 的 fixed release 和 latest channel 规则 MUST 由 `release-flow` Plugin（发布流程插件）配置和验证。

#### Scenario: 个人市场条目

- **WHEN** installer（安装器）为 personal scope（个人作用域）执行 dry-run（试运行）、install（安装）或 verify（验证）
- **THEN** 它使用 personal marketplace（个人市场）位置，并把 `agent-guard` 条目解析为 personal plugin package（个人插件包）

#### Scenario: 仓库市场条目

- **WHEN** installer（安装器）为 repo scope（仓库作用域）执行 dry-run（试运行）、install（安装）或 verify（验证）
- **THEN** 它使用当前仓库的 Codex `.agents/plugins/marketplace.json` 和 Claude `.claude-plugin/marketplace.json`，并把 `agent-guard` 条目解析为 `./plugins/agent-guard`

#### Scenario: GitHub 固定版本订阅

- **WHEN** 生成或验证 fixed release（固定版本发布）的 marketplace subscription（市场订阅）说明
- **THEN** 订阅源 MUST 指向 GitHub repo（GitHub 仓库）的版本 tag（标签）
- **THEN** release-flow MUST 将该 tag 与 Agent Guard Codex/Claude manifest version（清单版本）关联验证

#### Scenario: GitHub latest 通道订阅

- **WHEN** 生成或验证 latest channel（最新通道）的 marketplace subscription（市场订阅）说明
- **THEN** 订阅源 MUST 指向 GitHub repo（GitHub 仓库）的 `marketplace` 分支，以保持现有 Codex/Claude 订阅链接不变并支持自动更新
- **THEN** release-flow MUST 将该分支声明为 Agent Guard latest channel

## ADDED Requirements

### Requirement: Agent Guard 发布分支边界

系统 MUST 将 Agent Guard 的 `marketplace` 分支作为由 `release-flow` Plugin 生成或更新的 latest channel，不得把它作为开发分支或规则真相。

#### Scenario: 发布分支由 main 和 projection 生成

- **WHEN** 更新 `marketplace` 分支用于发布 latest channel
- **THEN** 发布流程 MUST 从 `main` 的源码、manifest version 和 `.release-flow/projection.yaml` 生成发布内容
- **THEN** 发布流程 MUST 从 GitHub Actions Variables 读取 projection 所需变量值

#### Scenario: 禁止本地发布分支

- **WHEN** 发布 Agent Guard latest channel
- **THEN** 本地流程 MUST NOT 创建 `marketplace` 发布分支
- **THEN** 本地流程 MUST NOT 手工 push `marketplace`

#### Scenario: 禁止发布分支手工漂移

- **WHEN** 验证 `marketplace` 分支与 `main` 的差异
- **THEN** 校验 MUST 拒绝未被 `.release-flow/projection.yaml` 描述的差异

#### Scenario: tag 与 manifest 版本一致

- **WHEN** 创建或验证 fixed release（固定版本发布）
- **THEN** tag（标签）中的版本 MUST 与 Codex manifest 和 Claude manifest 的 version（版本）一致

### Requirement: Agent Guard 发布变量注册

系统 MUST 使用 `.release-flow/projection.yaml` 注册 Agent Guard marketplace catalog（市场目录）发布态变量，并禁止把变量值写入 Git。

#### Scenario: 注册 Codex marketplace 名称变量

- **WHEN** Agent Guard latest channel 需要生成 Codex marketplace catalog
- **THEN** projection MUST 注册用于 `.agents/plugins/marketplace.json` 的发布态变量
- **THEN** projection MUST 声明该变量注入到对应 JSON 字段

#### Scenario: 注册 Claude marketplace 名称变量

- **WHEN** Agent Guard latest channel 需要生成 Claude marketplace catalog
- **THEN** projection MUST 注册用于 `.claude-plugin/marketplace.json` 的发布态变量
- **THEN** projection MUST 声明该变量注入到对应 JSON 字段
```

## openspec/changes/standardize-agent-guard-release-flow/specs/release-flow-plugin/spec.md

- Source: openspec/changes/standardize-agent-guard-release-flow/specs/release-flow-plugin/spec.md
- Lines: 1-209
- SHA256: 15c85716d7d3e40ed312dc2d28b539c3ffa5ff3afa5c00fcdc1efdf7abbca4f7

```md
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

系统 MUST 提供 project setup（项目启用）阶段，用于调研仓库、生成目标项目配置、输出 GitHub 配置方案，并在用户授权后修改 GitHub 仓库设置。

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
- **THEN** 系统 MAY 使用 `gh` 或 GitHub API 修改仓库设置
- **THEN** 系统 MUST 回读配置并验证结果

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

系统 MUST 提供 release-flow preflight（发布前检查）阶段，用于在发布前验证配置、变量、GitHub 仓库设置、版本和发布投影。

#### Scenario: 检查配置文件

- **WHEN** 执行 preflight
- **THEN** 系统 MUST 验证 `.release-flow/config.yaml` 存在且合法
- **THEN** 系统 MUST 验证 `.release-flow/projection.yaml` 存在且合法

#### Scenario: 检查变量

- **WHEN** 执行 preflight
- **THEN** 系统 MUST 验证 projection 中 required 变量存在于 GitHub Actions Variables
- **THEN** 系统 MUST 拒绝缺失变量

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
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
