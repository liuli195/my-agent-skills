# local-plugin-build-checks Specification

## Purpose
TBD - created by archiving change add-local-plugin-build-checks. Update Purpose after archive.
## Requirements
### Requirement: Build command validates local plugin package shape
The repository SHALL（必须）provide a local build command that validates plugin package shape without publishing, installing, writing user configuration, or contacting GitHub（代码托管平台）remote state.

#### Scenario: Build command runs local package checks
- **WHEN** a developer runs `python scripts/check.py build`
- **THEN** the command completes only after local plugin package checks have passed

#### Scenario: Build command avoids external side effects
- **WHEN** the build command runs
- **THEN** it does not install plugins, publish releases, write user-level configuration, or query GitHub remote state

### Requirement: Build command runs Claude plugin validation
The build command SHALL（必须）run Claude（Claude 编码工具）plugin validation for the repository marketplace and every local plugin listed in `.claude-plugin/marketplace.json`.

#### Scenario: Marketplace is validated
- **WHEN** the build command runs
- **THEN** it runs `claude plugin validate .`

#### Scenario: Local plugin sources are validated
- **WHEN** `.claude-plugin/marketplace.json` lists local plugin sources
- **THEN** the build command runs `claude plugin validate <source>` for each local source

#### Scenario: Strict validation is not required
- **WHEN** the build command runs Claude plugin validation
- **THEN** it does not require `--strict` mode to pass

### Requirement: Build command validates marketplace and manifest consistency
The build command SHALL（必须）validate that marketplace entries and plugin manifests are structurally consistent for Claude（Claude 编码工具）and Codex（OpenAI 编码代理）plugin surfaces.

#### Scenario: Marketplace source stays inside repository
- **WHEN** `.claude-plugin/marketplace.json` contains a plugin source
- **THEN** the source resolves to an existing path inside the repository

#### Scenario: Marketplace name matches plugin manifest
- **WHEN** a marketplace plugin entry points to a local plugin
- **THEN** the entry `name` matches that plugin's `.claude-plugin/plugin.json` `name`

#### Scenario: Plugin manifests declare required fields
- **WHEN** a local plugin is checked
- **THEN** its `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` declare required fields and reference existing local paths

### Requirement: Build command validates release projection registration
The build command SHALL（必须）validate that `.release-flow/projection.yaml` registration agrees with local plugin marketplace entries.

#### Scenario: Projection plugins match marketplace plugins
- **WHEN** `.release-flow/projection.yaml` declares a codex-marketplace（Codex 插件市场）generator
- **THEN** its plugin list matches the local plugin names in `.claude-plugin/marketplace.json`

#### Scenario: Projection plugin names are unique
- **WHEN** projection plugin lists are checked
- **THEN** duplicate plugin names are reported as build errors

### Requirement: Build command validates Guard Profile template mirrors
The build command SHALL（必须）validate that mirrored Guard Profile（守卫画像）template directories stay byte-for-byte consistent.

#### Scenario: Mirrored template files match
- **WHEN** the build command compares `plugins/agent-guard/assets/templates/guard-profile/` with `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/`
- **THEN** every mirrored file exists on both sides and has identical content

### Requirement: Verify command runs the full Python test suite
The repository SHALL（必须）provide a verify command that runs the full Python（Python 语言）test suite through the standard pytest（Python 测试框架）entrypoint.

#### Scenario: Verify command uses pytest defaults
- **WHEN** a developer runs `python scripts/check.py verify`
- **THEN** the command runs `python -m pytest` and uses repository pytest configuration for default test discovery

#### Scenario: Comet config avoids duplicate command wiring
- **WHEN** Comet（双星流程）reads `.comet/config.yaml`
- **THEN** it does not define `build_command` or `verify_command`

