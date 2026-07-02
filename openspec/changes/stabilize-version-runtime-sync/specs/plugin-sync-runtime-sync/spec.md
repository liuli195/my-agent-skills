## ADDED Requirements

### Requirement: Plugin Sync closes build-and-verify runtime synchronization
Plugin Sync（插件同步） MUST detect and optionally update build-and-verify（构建与验证） runtime（运行时） snapshots for configured target repositories.

#### Scenario: Configured repository runtime is current
- **WHEN** Plugin Sync（插件同步） checks a repository containing `.build-and-verify/config.json`
- **AND** `.build-and-verify/runtime/version.json` matches the newest installed build-and-verify（构建与验证） runtime（运行时）
- **THEN** Plugin Sync（插件同步） MUST report `runtime_current`

#### Scenario: Configured repository runtime is stale
- **WHEN** Plugin Sync（插件同步） checks a repository containing `.build-and-verify/config.json`
- **AND** `.build-and-verify/runtime/version.json` is older than the newest installed build-and-verify（构建与验证） runtime（运行时）
- **THEN** Plugin Sync（插件同步） MUST report `runtime_stale`
- **THEN** output（输出） MUST include repository runtime（运行时） version（版本）, installed runtime（运行时） version（版本）, and the update-runtime（更新运行时） command

#### Scenario: Runtime update requires authorization
- **WHEN** Plugin Sync（插件同步） detects `runtime_stale`
- **THEN** Plugin Sync（插件同步） MUST NOT run update-runtime（更新运行时） without explicit user authorization
- **WHEN** the user authorizes update-runtime（更新运行时）
- **THEN** Plugin Sync（插件同步） MUST run the existing build-and-verify（构建与验证） update-runtime（更新运行时） command
- **THEN** Plugin Sync（插件同步） MUST reread `.build-and-verify/runtime/version.json`

#### Scenario: Runtime update reports PR Flow next step
- **WHEN** Plugin Sync（插件同步） updates `.build-and-verify/runtime/`
- **AND** Git（版本管理） reports tracked changes under `.build-and-verify/runtime/`
- **THEN** Plugin Sync（插件同步） MUST report that the repository should use PR Flow（拉取请求流程） for the change
- **THEN** Plugin Sync（插件同步） MUST NOT commit, push（推送）, or open PR（拉取请求）
