# local-plugin-build-checks Specification

## Purpose

TBD - created by archiving change add-local-plugin-build-checks. Update Purpose after archive.

## Requirements

### Requirement: Build command does not require external plugin validators
The build command SHALL（必须）validate repository-owned plugin package structure without requiring Claude Code（Claude 编码工具）or another globally installed plugin validator.

#### Scenario: Build runs without Claude Code
- **WHEN** the build command runs on a correctly initialized checkout without a `claude` command
- **THEN** repository-owned plugin package checks MUST still run
- **THEN** the absence of `claude` MUST NOT fail the build

#### Scenario: Repository-owned structural validation remains
- **WHEN** `.claude-plugin/marketplace.json` lists local plugin sources
- **THEN** the build command MUST validate those sources through the repository-owned marketplace and manifest consistency checks
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
### Requirement: Repository checks enforce recoverable stop action contract
Repository-owned checks（仓库检查） MUST guard the recoverable stop-state contract for local plugin scripts.

#### Scenario: Recoverable stop states include recovery details
- **WHEN** repository tests inspect local plugin scripts or their reason（原因） tables
- **THEN** every known recoverable `DISPATCH_REQUIRED`（需要外部进展）, `PUSH_REQUIRED`（需要推送） or `REPLY_OR_FIX_REQUIRED`（需要回复或修复） stop state MUST include `nextAction`（下一步动作） or `nextCommand`（下一条命令）

#### Scenario: Known recoverable reasons do not become generic exceptions
- **WHEN** repository tests cover known recoverable reasons（原因） such as GitHub authentication, transient PR view failure, pending checks, ruleset blocking, and invalid user input
- **THEN** those reasons（原因） MUST NOT be reported only as generic `EXCEPTION_REQUIRED`（需要人工处理）
### Requirement: Plugin manifest version tests use manifest source of truth
Repository-owned local plugin package tests MUST prevent duplicate real plugin version facts while allowing normal release intermediate states when validating dual Codex（代码助手） and Claude（代码助手） manifest（清单） files.

#### Scenario: Dual manifest versions are compared from files
- **WHEN** repository tests validate a local plugin package
- **THEN** tests MUST read Codex（编码助手） and Claude（编码助手） version（版本） values from their manifest（清单） files
- **THEN** tests MUST assert the manifest（清单） versions are equal
- **THEN** tests MUST NOT require a second hard-coded real plugin version constant

#### Scenario: Real release version literals are rejected in tests
- **WHEN** repository tests scan `tests/`
- **THEN** tests MUST fail if a new real plugin release version literal such as `0.1.x` is introduced outside an explicit allowlist
- **THEN** the allowlist MUST NOT include ordinary assertions that duplicate current plugin release versions

#### Scenario: Runtime manifest mismatch is not a generic test failure
- **WHEN** build-and-verify（构建与验证）runtime（运行时） version（版本） temporarily differs from the build-and-verify plugin manifest（插件清单） during a release preparation state
- **THEN** ordinary repository tests MUST NOT fail solely because of that mismatch
- **THEN** release readiness MUST be checked by the Release Flow preflight（发布预检） runtime（运行时） synchronization rule
### Requirement: Build command validates local plugin package shape
The repository SHALL（必须）provide a local build command through the initialized build-and-verify（构建与验证）Plugin（插件）contract. Repository-specific package-shape checks remain repository-owned configured checks, not plugin-owned framework logic.

#### Scenario: Build command runs repository-owned package checks
- **WHEN** a developer runs `build-and-verify build --project .`
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
### Requirement: Verify command follows initialized build-and-verify contract

The repository SHALL（必须）provide a verify command initialized by the build-and-verify（构建与验证）Plugin（插件） contract. Build and verify check execution MUST preserve each child process exit status even when captured output contains bytes that are not valid UTF-8（字符编码）.

#### Scenario: Verify command defaults to framework fast mode

- **WHEN** a developer runs `build-and-verify verify --project .`
- **THEN** the command uses `.build-and-verify/config.json` `verify.checks`
- **THEN** the command applies changed-files（变更文件） selection and passed-result cache（通过结果缓存）
- **THEN** the command does not bypass changed-files（变更文件） selection and passed-result cache（通过结果缓存） by unconditionally running every configured verify check

#### Scenario: Verify full mode runs all configured checks

- **WHEN** a developer runs `build-and-verify verify --project . --full`
- **THEN** the command runs all `.build-and-verify/config.json` `verify.checks`
- **THEN** the command does not use cache（缓存） hits to skip checks（检查项）
- **THEN** passed checks（已通过检查项） refresh passed-result cache（通过结果缓存）
- **THEN** failed checks（失败检查项） are not stored as passed-result cache（通过结果缓存）
- **THEN** the command does not rely on the default verify mode being full（完整验证）

#### Scenario: Comet config keeps guard-compatible command shim

- **WHEN** Comet（双星流程）reads root `.comet.yaml`
- **THEN** it defines `build_command: build-and-verify build --project .`
- **THEN** it defines `verify_command: build-and-verify verify --project .`
- **THEN** those commands invoke the installed build-and-verify（构建与验证） CLI（命令行程序）

#### Scenario: 检查输出包含非法 UTF-8 字节

- **WHEN** build（构建检查）或 verify（验证）的子进程输出包含非法 UTF-8 字节并以非零状态退出
- **THEN** 运行器 MUST 继续报告该检查的非零退出状态
- **THEN** 运行器 MUST NOT 以 `UnicodeDecodeError`（解码异常）替代原检查结果
### Requirement: Full Verify required check aggregates platform verification
The repository's required `Full Verify`（完整验证）GitHub status check SHALL（必须）report success only when every required platform verification job in the Full Verify workflow succeeds.

#### Scenario: All required platform jobs succeed
- **WHEN** the Linux and Windows platform verification jobs for the current pull request commit both complete successfully
- **THEN** the required `Full Verify` check MUST succeed

#### Scenario: A required platform job does not succeed
- **WHEN** either required platform verification job fails, is cancelled, or is skipped
- **THEN** the required `Full Verify` check MUST fail or remain blocking
### Requirement: Repository workflow artifact uploads use current action runtime

The repository's active GitHub workflows MUST use a current artifact upload action runtime whenever they upload release candidates.

#### Scenario: Active release candidate upload uses the current action

- **WHEN** an active repository workflow uploads release candidates
- **THEN** each `actions/upload-artifact` reference MUST use `actions/upload-artifact@v6`
- **THEN** no active workflow MUST reference `actions/upload-artifact@v4` or `actions/upload-artifact@v5`
### Requirement: Windows（视窗系统）PR（拉取请求）验证使用固定基线

本仓库的 Windows 平台验证任务 MUST 在 PR 事件中通过 Build and Verify（构建与验证）对固定目标提交运行受影响检查，并在手动触发时保留当前检出的完整验证入口；现有工作树构建和跨平台汇总门禁 MUST 保持有效。

#### Scenario: PR 运行受影响的 Windows 验证

- **WHEN** `Full Verify`（完整验证）工作流为 PR 当前提交运行
- **THEN** Windows 平台任务 MUST 检出足以解析该 PR 固定目标提交的 Git（版本管理）历史
- **THEN** Windows 平台任务 MUST 通过 Build and Verify 使用该固定提交作为快速验证基线
- **THEN** 只有验证命令成功、`checked`（已检查）非空且最终状态为 `passed`（通过）时，该步骤才能成功
- **THEN** 现有链接工作树初始化、环境激活和构建主路径 MUST 继续运行

#### Scenario: 手动触发 Windows 完整验证

- **WHEN** 维护者手动触发 `Full Verify` 工作流
- **THEN** Windows 平台任务 MUST 通过当前检出的 Build and Verify 入口运行完整验证
- **THEN** 完整验证返回非零结果时，Windows 平台任务 MUST 失败
- **THEN** 最终 `Full Verify` 跨平台汇总任务 MUST 继续要求 Linux（操作系统）与 Windows 平台任务全部成功
### Requirement: Build command validates NPM release metadata
The repository build command MUST run the Release Flow（发布流程）project validation as a configured repository-owned check so every registered NPM（软件包管理器）package is checked before release work begins.

#### Scenario: Build checks all registered NPM packages
- **WHEN** a developer runs `build-and-verify build --project .`
- **THEN** the command MUST run the configured release metadata check
- **THEN** the check MUST validate every registered and existing NPM package
- **THEN** the build MUST fail when any checked package cannot satisfy the provenance repository metadata contract

#### Scenario: Fast verification selects release metadata coverage
- **WHEN** either NPM package manifest, the Release Flow implementation, or the active release workflow changes
- **THEN** `build-and-verify verify --project .` MUST select the Release Flow verification check
- **THEN** successful verification MUST report a non-empty `checked` result containing that check
