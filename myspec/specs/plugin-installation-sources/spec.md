# Plugin Installation Sources

## Purpose

让两种代理客户端按插件能力选择共享市场或既有命令包，并明确区分开发和正式来源。

## Requirements

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
### Requirement: Shared marketplaces provide nine owned plugins while preserving command tool distribution

系统 MUST 在 Codex 和 Claude Code 的共享开发与正式市场中提供 release-flow、pr-flow、dev-flow、subagent-policy、plugin-sync、retro-to-issues、data-store、my-spec、build-and-verify 九项插件。MySpec 和 Build and Verify MUST 保留既有 npm 命令、包内单插件市场兼容入口、构建发布与自举检查；共享市场成员身份不得成为误卸载有效安装的理由。

#### Scenario: 用户通过任一客户端选择共享市场插件

- **WHEN** 用户浏览共享市场或安装九项自有插件
- **THEN** 两端 MUST 提供相同九项，目标技能、脚本和资源可发现；每项仅启用所选完整来源，两项 npm 命令仍可用。
