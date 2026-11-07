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
