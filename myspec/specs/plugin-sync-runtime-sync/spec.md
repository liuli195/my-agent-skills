# plugin-sync-runtime-sync Specification

## Purpose

TBD - created by archiving change stabilize-version-runtime-sync. Update Purpose after archive.

## Requirements

### Requirement: Plugin Sync closes build-and-verify runtime synchronization
Plugin Sync（插件同步） skill instructions（技能说明） MUST define how to detect and optionally update build-and-verify（构建与验证） runtime（运行时） snapshots for configured target repositories.

#### Scenario: Repository runtime is not configured
- **WHEN** the skill（技能） checks a repository without `.build-and-verify/config.json`
- **THEN** the instructions（说明） MUST require reporting `runtime_not_configured`
- **THEN** the instructions（说明） MUST forbid running update-runtime（更新运行时）

#### Scenario: Installed runtime source is missing
- **WHEN** the skill（技能） checks a repository containing `.build-and-verify/config.json`
- **AND** the newest installed build-and-verify（构建与验证） runtime（运行时） cannot be found
- **THEN** the instructions（说明） MUST require reporting `runtime_source_missing`
- **THEN** the instructions（说明） MUST forbid running update-runtime（更新运行时）

#### Scenario: Configured repository runtime is current
- **WHEN** the skill（技能） checks a repository containing `.build-and-verify/config.json`
- **AND** `.build-and-verify/runtime/version.json` matches the newest installed build-and-verify（构建与验证） runtime（运行时）
- **THEN** the instructions（说明） MUST require reporting `runtime_current`

#### Scenario: Configured repository runtime is stale
- **WHEN** the skill（技能） checks a repository containing `.build-and-verify/config.json`
- **AND** `.build-and-verify/runtime/version.json` is older than the newest installed build-and-verify（构建与验证） runtime（运行时）
- **THEN** the instructions（说明） MUST require reporting `runtime_stale`
- **THEN** output（输出） instructions（说明） MUST include repository runtime（运行时） version（版本）, installed runtime（运行时） version（版本）, and the update-runtime（更新运行时） command

#### Scenario: Runtime update requires authorization
- **WHEN** Plugin Sync（插件同步） detects `runtime_stale`
- **THEN** the instructions（说明） MUST forbid running update-runtime（更新运行时） without explicit user authorization
- **WHEN** the user authorizes update-runtime（更新运行时）
- **THEN** the instructions（说明） MUST require running the existing build-and-verify（构建与验证） update-runtime（更新运行时） command
- **THEN** the instructions（说明） MUST require rereading `.build-and-verify/runtime/version.json`
- **THEN** the instructions（说明） MUST require reporting `runtime_updated` when the reread runtime（运行时） version（版本） matches the installed runtime（运行时） version（版本）

#### Scenario: Runtime update fails
- **WHEN** the user authorizes update-runtime（更新运行时）
- **AND** the existing build-and-verify（构建与验证） update-runtime（更新运行时） command fails
- **THEN** the instructions（说明） MUST require reporting `update_failed`
- **THEN** the instructions（说明） MUST forbid reporting PR Flow（拉取请求流程） as the next step

#### Scenario: Runtime update reports PR Flow next step
- **WHEN** Plugin Sync（插件同步） updates `.build-and-verify/runtime/`
- **AND** Git（版本管理） reports tracked changes under `.build-and-verify/runtime/`
- **THEN** the instructions（说明） MUST require reporting that the repository should use PR Flow（拉取请求流程） for the change
- **THEN** the instructions（说明） MUST forbid commit, push（推送）, or open PR（拉取请求）
### Requirement: Plugin Sync delegates MySpec lifecycle management

Plugin Sync（插件同步）MUST 将 MySpec（自有规格）的初始化、诊断、机器级模式切换和更新委托给 `myspec` CLI（命令行程序），不得复制 MySpec 的路径、市场、模式或版本规则。

#### Scenario: 用户通过 Plugin Sync 管理 MySpec

- **WHEN** 用户要求 Plugin Sync 检查、初始化、切换或更新 MySpec
- **THEN** Plugin Sync MUST 调用适用的 `myspec init`、`myspec doctor` 或 `myspec update`
- **THEN** Plugin Sync MUST NOT 自行推断 MySpec 的包路径、客户端市场、模式或目标版本
