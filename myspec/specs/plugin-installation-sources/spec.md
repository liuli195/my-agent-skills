# Plugin Installation Sources

## Purpose

让两种代理客户端按插件能力选择共享市场或既有命令包，并明确区分开发和正式来源。

## Requirements

### Requirement: Shared marketplaces provide seven skills while command tools keep package distribution

系统 MUST 在 Codex（代码代理）和 Claude Code（代码助手）的共享市场中提供 release-flow（发布流程）、pr-flow（拉取请求流程）、dev-flow（开发流程）、subagent-policy（子代理策略）、plugin-sync（插件同步）、retro-to-issues（复盘转任务）、data-store（数据中心）七项插件。MySpec（自有规格）及 Build and Verify（构建与验证）MUST 保留既有 NPM（软件包管理器）命令、包内单插件市场和自举检查，退出两个共享市场但不失去发布资格。

#### Scenario: A user installs skills through either client

- **WHEN** 用户在任一客户端浏览共享市场或安装七项技能
- **THEN** 两端提供相同七项，安装后技能正文与随包资源可发现
- **THEN** 两项命令工具通过自身软件包使用，不出现共享市场重复版本
### Requirement: Shared development and release marketplaces remain independently visible

系统 MUST 同时保留正式市场 my-agent-skills-marketplace 与开发市场 my-agent-skills-marketplace-dev；开发显示名称明确含 DEV（开发）。插件名保持一致，用户能选择单个插件来源，其他插件保持原选择。

#### Scenario: A user chooses a development plugin

- **WHEN** 用户让某一个插件使用开发市场
- **THEN** 正式与开发市场仍可浏览，其他插件和第三方市场不变
- **THEN** 目标插件的实际版本、启用状态与来源可核对，不同时启用两来源
### Requirement: Command tool source checks remain independent of shared catalog membership

两项既有命令工具 MUST 在未出现在共享市场时仍能完成开发与正式模式切换，保留包内自身登记、官方源码身份、版本、干净状态和远端可复现来源校验；不能因共享市场去重而放宽安全校验或遗漏发布输入与版本提升要求。

#### Scenario: Shared catalogs omit command tools

- **WHEN** 用户通过工具自身入口切换有效开发源码或恢复已保存正式版本
- **THEN** 工具不要求共享市场包含自身，并继续检查包内单一来源与有效源码
- **THEN** 无效来源仍明确拒绝，发布前仍检查两项工具及共享实现变更
