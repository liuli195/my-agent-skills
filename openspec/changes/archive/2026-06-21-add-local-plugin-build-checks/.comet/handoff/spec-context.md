# Comet Spec Context

- Change: add-local-plugin-build-checks
- Phase: design
- Mode: beta
- Context hash: 7969939d124ae18d633a3bb5c8cc2d24f4aacc512266fa0cb33feac527987e46

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/add-local-plugin-build-checks/proposal.md
- SHA256: 295e92ce8e8cf518f8bfda086f29a67eafc313ef999cb0ffdd8fee1b222ba831
- Source: openspec/changes/add-local-plugin-build-checks/design.md
- SHA256: 6ab425b240669afd921b0e00321b51178de2593c7721c90c08267052ea7ea8e0
- Source: openspec/changes/add-local-plugin-build-checks/tasks.md
- SHA256: 98a05ff61f405c57e0885a2fa87a11669466eeaf54127292f98089c138fdfb4c
- Source: openspec/changes/add-local-plugin-build-checks/specs/local-plugin-build-checks/spec.md
- SHA256: d135f99a1f95da2180087f4fe68e65a5062d9959ce740ebaccd8ca0c9e22294c

## Acceptance Projection

## openspec/changes/add-local-plugin-build-checks/specs/local-plugin-build-checks/spec.md

- Source: openspec/changes/add-local-plugin-build-checks/specs/local-plugin-build-checks/spec.md
- Lines: 1-71
- SHA256: d135f99a1f95da2180087f4fe68e65a5062d9959ce740ebaccd8ca0c9e22294c

```md
## ADDED Requirements

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

#### Scenario: Comet uses repository command entrypoints
- **WHEN** Comet（双星流程）reads `.comet/config.yaml`
- **THEN** `build_command` points to `python scripts/check.py build` and `verify_command` points to `python scripts/check.py verify`
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
