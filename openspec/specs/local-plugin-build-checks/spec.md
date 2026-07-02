# local-plugin-build-checks Specification

## Purpose
TBD - created by archiving change add-local-plugin-build-checks. Update Purpose after archive.
## Requirements
### Requirement: Build command validates local plugin package shape
The repository SHALL（必须）provide a local build command through the initialized build-and-verify（构建与验证）Plugin（插件）contract. Repository-specific package-shape checks remain repository-owned configured checks, not plugin-owned framework logic.

#### Scenario: Build command runs repository-owned package checks
- **WHEN** a developer runs `python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py build --project .`
- **THEN** the command uses `.build-and-verify/config.json` `build.checks`
- **THEN** the configured build check runs `python scripts/local_plugin_build.py`
- **THEN** `scripts/local_plugin_build.py` remains a repository-owned check command, not the build-and-verify（构建与验证）Plugin（插件） entrypoint

#### Scenario: Removed check entrypoint is not active automation
- **WHEN** repository active automation and guard（守卫） command files are inspected
- **THEN** `.github/workflows/`, `.comet.yaml`, `.comet/config.yaml`, `.pr-flow/config.yaml`, and `.build-and-verify/config.json` MUST NOT reference `scripts/check.py`
- **THEN** they MUST NOT reference `plugins/test-framework/` or `.test-framework/`

#### Scenario: Root Python test configuration is not active automation
- **WHEN** repository active automation and build-and-verify（构建与验证） configuration are inspected
- **THEN** root `pyproject.toml` MUST NOT exist
- **THEN** pytest（Python 测试运行器） commands in `.build-and-verify/config.json` MUST explicitly provide required paths and command options

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

### Requirement: Verify command follows initialized build-and-verify contract
The repository SHALL（必须）provide a verify command initialized by the build-and-verify（构建与验证）Plugin（插件） contract.

#### Scenario: Verify command defaults to framework fast mode
- **WHEN** a developer runs `python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .`
- **THEN** the command uses `.build-and-verify/config.json` `verify.checks`
- **THEN** the command applies changed-files（变更文件） selection and passed-result cache（通过结果缓存）
- **THEN** the command does not bypass changed-files（变更文件） selection and passed-result cache（通过结果缓存） by unconditionally running every configured verify check

#### Scenario: Verify full mode runs all configured checks
- **WHEN** a developer runs `python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full`
- **THEN** the command runs all `.build-and-verify/config.json` `verify.checks`
- **THEN** the command does not use cache（缓存） hits to skip checks（检查项）
- **THEN** passed checks（已通过检查项） refresh passed-result cache（通过结果缓存）
- **THEN** failed checks（失败检查项） are not stored as passed-result cache（通过结果缓存）
- **THEN** the command does not rely on the default verify mode being full（完整验证）

#### Scenario: Comet config keeps guard-compatible command shim
- **WHEN** Comet（双星流程）reads root `.comet.yaml`
- **THEN** it defines `build_command: python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py build --project .`
- **THEN** it defines `verify_command: python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .`
- **THEN** those commands act as the project-level（项目级） guard（守卫） compatibility shim（兼容层） for the committed build-and-verify（构建与验证） runner（运行器） under `plugins/build-and-verify/`

### Requirement: Repository workflows avoid deprecated Node runtime references
The repository's active GitHub workflows MUST avoid Node.js 20 action/runtime references when a current replacement is available.

#### Scenario: Active workflow references are fully scanned
- **WHEN** repository workflow validation runs
- **THEN** it MUST inspect every active `.github/workflows/*.yml` file
- **THEN** it MUST inspect `uses:` action references and explicit Node runtime version declarations
- **THEN** every reference with an available current non-deprecated replacement MUST be upgraded or explicitly covered by an exception scenario

#### Scenario: Checkout actions use current major
- **WHEN** active `.github/workflows/*.yml` files are inspected
- **THEN** each `actions/checkout` reference MUST use `actions/checkout@v5`
- **THEN** no active workflow MUST reference `actions/checkout@v4`

#### Scenario: Full verify uses current setup actions and Node runtime
- **WHEN** `.github/workflows/full-verify.yml` is inspected
- **THEN** it MUST use `actions/setup-node@v6`
- **THEN** it MUST use `node-version: "24"`
- **THEN** it MUST use `actions/setup-python@v6`

#### Scenario: CodeQL action stays on current available major
- **WHEN** `.github/workflows/codeql.yml` is inspected
- **THEN** `github/codeql-action/init` and `github/codeql-action/analyze` MAY remain on `@v4` while no newer major is available

### Requirement: Plugin manifest version tests use manifest source of truth
Repository-owned local plugin package tests MUST NOT maintain a duplicate hard-coded plugin version source when validating dual Codex（代码助手） and Claude（代码助手） manifest（清单） files.

#### Scenario: Dual manifest version consistency is checked without duplicate constant
- **WHEN** a local plugin package test validates `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json`
- **THEN** the test MUST read version（版本） values from the manifest（清单） files
- **THEN** the test MUST assert the two manifest（清单） versions are equal
- **THEN** the test MUST NOT require a second hard-coded plugin version constant to be updated during release version bump（版本提升）

### Requirement: Repository tests enforce runtime boundary
Repository-owned tests MUST enforce a boundary between ordinary tests and explicit E2E（端到端测试） coverage across the whole `tests/` tree.

The boundary MUST apply to plugin test families for Build and Verify（构建与验证）, PR Flow（拉取请求流程）, Release Flow（发布流程）, Cross Agent Review（跨代理审查）, and Agent Guard（代理守卫）. Broad enforcement for those plugin tests is intentional scope for this change, not an overshoot outside the spec.

#### Scenario: Ordinary tests do not call real subprocess directly
- **WHEN** repository tests scan `tests/`
- **THEN** ordinary tests MUST NOT directly or through repository test helper（辅助函数）/ fixture（测试夹具） invoke real subprocess（子进程） execution
- **THEN** any allowed subprocess（子进程） usage MUST be listed by test function identity（测试函数身份） in an explicit E2E（端到端测试） allowlist

#### Scenario: Ordinary tests do not initialize temporary git repositories
- **WHEN** repository tests scan `tests/`
- **THEN** ordinary tests MUST NOT directly or through repository test helper（辅助函数）/ fixture（测试夹具） run temporary git（版本控制） repository initialization
- **THEN** any allowed temporary git（版本控制） initialization MUST be listed by test function identity（测试函数身份） in an explicit E2E（端到端测试） allowlist

#### Scenario: Ordinary tests do not run real CLI entrypoints
- **WHEN** repository tests scan `tests/`
- **THEN** ordinary tests MUST NOT run repository plugin CLI（命令行） entrypoints through real process execution directly or through repository test helper（辅助函数）/ fixture（测试夹具）
- **THEN** real CLI（命令行） entrypoint coverage MUST be limited to explicit E2E（端到端测试） allowlisted test function identities（测试函数身份）

#### Scenario: E2E allowlist is narrow
- **WHEN** a test needs real subprocess（子进程）, CLI（命令行）, temporary git（版本控制）, or broad cache（缓存） scanning
- **THEN** the test MUST be named by file path + qualified test function（文件路径加限定测试函数） and documented in the E2E（端到端测试） allowlist
- **THEN** the allowlist MUST NOT permit an entire file only because one test in that file is E2E（端到端测试）

#### Scenario: Plugin tests share the same boundary
- **WHEN** repository tests scan plugin-focused tests for Build and Verify（构建与验证）, PR Flow（拉取请求流程）, Release Flow（发布流程）, Cross Agent Review（跨代理审查）, or Agent Guard（代理守卫）
- **THEN** ordinary branch behavior in those plugin tests MUST use in-process（进程内） or fake runner（假执行器） execution
- **THEN** any real subprocess（子进程）, CLI（命令行）, temporary git（版本控制）, or broad cache（缓存） behavior in those plugin tests MUST be explicitly allowlisted by test function identity（测试函数身份） with a distinct E2E（端到端测试） reason

