# 统一 MySpec CLI 与 Agent 环境

**Status:** ready-for-agent

## Problem Statement

MySpec（自有规格）的确定性操作目前由各 Skill（技能）直接引用包内 Python（脚本语言）路径。Pi、Claude 和 Codex 的本地目录、远端市场和缓存布局不同，导致命令能否执行依赖安装位置，路径选择还可能落到大模型，无法形成稳定、可复现的本地与 CI（持续集成）契约。

开发者还需要分别处理 CLI（命令行程序）、Pi Package（Pi 软件包）、Claude Plugin（插件）和 Codex Plugin（插件）的来源与版本。本地源码与发布版可能同时启用并暴露重复 Skill（技能），而独立更新 CLI（命令行程序）或插件又可能产生版本失配。现有发布模型如果继续为每个宿主维护单独资产、市场和缓存，将增加安装、更新、诊断、自举验证和故障恢复成本。

## Solution

将 MySpec（自有规格）发布为单一 npm（软件包管理器）包 `@liuli195/myspec`。该包同时提供稳定的 `myspec` CLI（命令行程序）、现有 Python 3.12（脚本语言）确定性核心、四个 Skill（技能），以及 Pi、Claude、Codex 所需的插件与自带市场清单。

Skill（技能）只调用 `myspec` 及现有业务子命令，不再寻找、解析或写死 Python（脚本语言）脚本路径。Node.js（运行时）启动器相对于已安装包定位唯一 Python（脚本语言）实现，按固定顺序选择 Python 3.12 或更高版本，并完整转发参数、输出和退出码。

所有 Agent（代理）始终登记同一个全局 npm 包稳定目录。发布模式通过 npm Install（npm 安装）提供固定发布包；开发模式通过 npm Link（npm 本地链接）让同一路径指向当前源码。`myspec init` 管理 Agent（代理）初始化和显式模式切换，`myspec doctor` 只读诊断真实安装状态，`myspec update` 仅在发布模式统一更新 CLI（命令行程序）与全部已安装插件。

本仓库的 PR CI（拉取请求持续集成）从当前检出提交生成 npm Tarball（npm 软件包），在隔离环境安装并测试真实 `myspec` 命令，从而解决“用旧发布版验证新源码”的自举问题。GitHub Release（发布版本）和 Git Tag（Git 标签）继续记录版本；npm（软件包管理器）承担包分发、固定版本、最新版解析、缓存和完整性校验。

## User Stories

1. As a MySpec user, I want to run one stable `myspec` command, so that I do not need to know where an Agent installed its scripts.
2. As a MySpec user, I want Skill instructions to avoid embedded script paths, so that the same workflow works in Pi, Claude, and Codex.
3. As a security-conscious user, I want path and runtime selection to be deterministic scripts, so that a language model never chooses executable locations.
4. As an existing MySpec user, I want current specification subcommands and arguments to remain unchanged, so that the CLI migration does not alter business behavior.
5. As a local developer, I want to enter development mode explicitly, so that my global MySpec command and all installed Agent plugins use the same local source.
6. As a local developer, I want source edits to take effect on the next command or Agent reload, so that I can verify changes without copying packages.
7. As a local developer, I want the current directory to be the default development source, so that normal setup stays concise.
8. As a local developer, I want to provide an explicit source directory when needed, so that setup remains deterministic outside the repository root.
9. As a local developer, I want invalid source directories to fail immediately, so that MySpec never searches parent directories or guesses another checkout.
10. As a local developer, I want development and release modes to be machine-wide, so that different Agents cannot silently invoke incompatible MySpec versions.
11. As a local developer, I want release restoration to recover the version that was active before development mode, so that switching modes does not unexpectedly upgrade me.
12. As a local developer, I want updating to be rejected in development mode, so that an update cannot silently replace my source checkout.
13. As a local developer, I want to switch explicitly to release mode before upgrading, so that mode changes remain visible and intentional.
14. As a Pi user, I want Pi to load MySpec from the stable global npm package directory, so that npm Link and npm Install naturally switch the active content.
15. As a Claude user, I want MySpec to provide a self-contained local plugin marketplace, so that Claude can load the same package used by the CLI.
16. As a Codex user, I want MySpec to provide a self-contained local plugin marketplace, so that Codex can load the same package used by the CLI.
17. As a multi-Agent user, I want one initialization command for Pi, Claude, and Codex, so that I do not maintain three installation procedures.
18. As a multi-Agent user, I want `--all` to mean exactly Pi, Claude, and Codex, so that its scope is stable and predictable.
19. As a multi-Agent user, I want unavailable Agents skipped during all-Agent initialization, so that one missing client does not block the clients I use.
20. As a multi-Agent user, I want explicit initialization of a missing Agent to fail, so that mistaken commands are visible.
21. As an existing plugin user, I want legacy MySpec sources disabled rather than deleted, so that migration avoids duplicate skills without destroying recoverable state.
22. As an existing plugin user, I want duplicate enabled sources reported, so that I can understand why multiple MySpec skills appear.
23. As a user diagnosing installation, I want a read-only doctor command, so that inspection never changes plugins, markets, state, or locks.
24. As a user diagnosing installation, I want doctor to query npm and the real Agent clients, so that stale state files cannot produce a false healthy result.
25. As a release-mode user, I want one update command to upgrade the CLI and every installed MySpec plugin together, so that versions remain aligned.
26. As a release-mode user, I want an interrupted update to be safely repeatable, so that partial external changes can converge without manual reconstruction.
27. As a user running concurrent tools, I want installation and update operations serialized, so that two processes cannot corrupt shared mode state.
28. As a user recovering from a crashed installer, I want stale locks removed only after the recorded process is proven absent, so that elapsed time alone never authorizes cleanup.
29. As a Windows user, I want the launcher to find a valid Python 3.12 installation through deterministic candidates, so that the same npm package works with standard Windows Python layouts.
30. As a Linux or macOS user, I want the launcher to recognize standard Python 3.12 command names, so that no platform-specific package is needed.
31. As an environment administrator, I want to override the Python executable explicitly, so that managed environments can choose an approved interpreter.
32. As a user without Python 3.12, I want a clear non-zero diagnostic, so that MySpec does not fail through an obscure child-process error.
33. As a third-party repository maintainer, I want to install the latest or a fixed npm version, so that I can choose convenience or reproducibility without custom GitHub download logic.
34. As a third-party repository maintainer, I want CI to invoke the same `myspec` interface as local development, so that validation behavior is portable.
35. As a CI maintainer, I want to pass specification and work directories explicitly, so that monorepo and multi-checkout jobs have no root-discovery ambiguity.
36. As a MySpec contributor, I want PR CI to test the package built from the PR checkout, so that unreleased source can pass the first CI round without depending on a previous release.
37. As a MySpec contributor, I want complete local verification to install the same package shape used by CI, so that packaging omissions fail before review.
38. As a release maintainer, I want npm publication, Git tags, and GitHub release records to share one version, so that there is no CLI-to-plugin compatibility matrix.
39. As a release maintainer, I want npm to own latest-version resolution, package caching, and integrity checks, so that MySpec does not duplicate package-manager behavior.
40. As a maintainer, I want the Python core to keep zero third-party runtime dependencies, so that npm distribution does not introduce a second dependency graph for specification logic.
41. As a maintainer, I want Plugin Sync to delegate MySpec operations to the CLI, so that installation policy exists in one implementation.
42. As an external repository maintainer, I want Build and Verify to remain only the unified build and verification entry, so that version-management policy does not leak into verification.
43. As a user with old marketplace subscriptions, I want those marketplaces preserved, so that adopting the unified package does not modify unrelated plugins.

## Implementation Decisions

- `@liuli195/myspec` is the single published unit for the CLI（命令行程序） and all Pi、Claude、Codex integration resources. The package is not Pi-specific and therefore does not use a `pi-` package prefix.
- The current Python（脚本语言） specification engine remains the sole implementation of deterministic specification behavior. It moves out of the Skill（技能） resource tree; the legacy direct script entry is removed rather than retained as a compatibility copy.
- A minimal Node.js（运行时） executable locates the adjacent Python（脚本语言） engine, forwards arguments and signals, preserves standard streams and returns the child exit code.
- Python（脚本语言） support is `>=3.12`. Interpreter candidates are checked in this order: `MYSPEC_PYTHON`, `python3.12`, `python3`, `python`, then Windows `py -3.12`. Candidates below 3.12 are rejected.
- Python（脚本语言） deterministic logic retains zero third-party runtime dependencies.
- Existing business commands remain named `state-init`, `state-set-conflicts`, `state-current`, `state-decide`, `state-status`, `validate-main`, `validate-delta`, `apply-delta`, and `diff`. Their explicit path arguments and observable behavior remain unchanged.
- Agent initialization is exposed as `myspec init --pi`, `--claude`, `--codex`, or `--all`. `--all` has a fixed three-client scope. Missing clients are skipped only for `--all`; explicitly requested missing clients fail.
- Environment switching is exposed as `myspec init --dev` and `myspec init --release`. Mode options cannot be combined with Agent selection options.
- Development mode defaults to the current directory and supports an explicit source override. The CLI validates required package and marketplace manifests and does not search parent directories.
- Development mode stores the active source directory, source Git commit, and previous release version, then uses npm Link（npm 本地链接） and restarts through the source CLI before refreshing installed Agents.
- Release mode restores the release version saved when development mode began. If no previous version is known, it fails instead of selecting the latest version.
- Environment mode is machine-wide because all three Agents resolve the same global CLI（命令行程序） and package directory.
- Pi registers the stable global npm package directory as its package source. Claude and Codex register self-contained single-plugin marketplaces shipped in that same directory.
- The stable package path remains registered across mode changes. npm Link（npm 本地链接） changes it to local source; fixed-version npm Install（npm 安装） restores released content.
- Migration enables the self-contained source before disabling legacy MySpec plugin sources. It never automatically removes plugins, marketplaces, source directories, or user files.
- `myspec doctor` is read-only and can target Pi, Claude, Codex, or all three. It reads actual npm and client state and reports runtime problems, current mode, source, version mismatch, duplicate enabled sources, lock state, and reload requirements.
- `myspec update` is valid only in release mode. It resolves npm's latest published version, preflights installed clients, updates the global package, re-executes the new CLI, refreshes every installed Agent integration, then runs doctor.
- Plugin Sync（插件同步） delegates MySpec initialization, diagnosis, mode switching, and updates to the CLI and does not duplicate MySpec path, marketplace, or version rules.
- Build and Verify（构建与验证） remains only the unified build and verification entry. It executes the repository's configured checks but does not own, infer, or synchronize the MySpec npm version.
- User-level state contains only mode, source identity, previous release version, and resumable operation progress. Agent installation truth is queried from the clients rather than persisted as a parallel inventory.
- A user-level installation lock serializes initialization and update. Locks record process identity, start time, and command; they are reclaimed only after the process is proven absent.
- Installation and update use preflight followed by recorded idempotent steps. Failures stop immediately and preserve original errors. Cross-client atomic rollback is not promised.
- npm（软件包管理器） is the installation and distribution authority. GitHub Release（发布版本） and Git Tag（Git 标签） remain version records but carry no Wheel（Python 安装包）、Pi ZIP（Pi 压缩包） or custom installation assets.
- The repository's release process publishes the npm package only after source tests and packaged end-to-end verification pass.
- External repositories do not receive a MySpec-specific version file. Reproducible CI pins the npm package version in its existing CI configuration; automated PR Flow（拉取请求流程） alignment is deferred from this change.

## Testing Decisions

- Tests observe external behavior: executable commands, standard streams, exit codes, resulting specification state, client invocations and final installation status. They do not assert private helper calls or internal class structure.
- The primary automated seam is a packed npm Tarball（npm 软件包） installed into an isolated npm prefix and user home. Tests invoke the installed `myspec` executable exactly as a user or CI job would.
- Controlled executable substitutes for npm、Pi、Claude and Codex expose the highest deterministic client boundary while allowing success, missing-client, stale-source, duplicate-source and interrupted-update scenarios to run in CI.
- The packaged black-box suite covers every existing business subcommand, Python（脚本语言） candidate ordering and version rejection, Agent initialization, global mode switching, legacy-source disabling, doctor read-only behavior, update restrictions, lock recovery and idempotent continuation.
- Prior art is the existing MySpec subprocess test suite, package-manifest contract tests, local plugin build checks, Plugin Sync contract tests and Build and Verify（构建与验证） command-stub patterns. These seams should be extended rather than replaced by new test frameworks.
- The real Agent（代理） end-to-end seam runs in a development machine with Pi、Claude and Codex installed. It starts from release mode, enters development mode, proves that all four skills and the CLI use observable local source changes, restores the saved release version, and proves that no duplicate skills remain enabled.
- Complete local verification and PR CI（拉取请求持续集成） both pack the current checkout, install the Tarball（npm 软件包） in isolation and run the complete business flow. PR CI must not resolve a published or machine-preinstalled MySpec version.
- Release verification installs the candidate npm package in a clean environment, runs the packaged end-to-end suite, publishes only after success, and confirms the published package exposes the same version and resources.

## Out of Scope

- Rewriting the Python（脚本语言） specification engine in JavaScript or TypeScript.
- Supporting Python versions below 3.12.
- Adding third-party Python runtime dependencies.
- Supporting Agent clients other than Pi、Claude and Codex.
- Installing Pi、Claude、Codex、Node.js or Python automatically.
- Inferring repository roots or replacing explicit business directory arguments.
- Publishing through PyPI（Python 软件仓库） or distributing Wheel（Python 安装包） files.
- Publishing separate Pi ZIP（Pi 压缩包） assets or maintaining a custom release download cache.
- Maintaining separate development and release plugin marketplaces.
- Automatically deleting legacy plugin installations, marketplace subscriptions or user files.
- Allowing different Agents on the same machine to use different MySpec modes.
- Letting `myspec update` implicitly exit development mode.
- Adding a repository-level MySpec version file to consuming repositories.
- Checking or synchronizing external-repository CI npm versions through PR Flow（拉取请求流程）; that integration is deferred to a later change.
- Guaranteeing atomic rollback across npm and three independent Agent clients.

## Further Notes

- Because Codex canonicalizes a local marketplace added through a linked path, its stable npm path must be registered in release mode before Codex can use later development-mode links.
- The existing remote `my-agent-skills-marketplace` remains useful for discovery and unrelated plugins. Unified MySpec initialization uses the package's self-contained source and disables only duplicate MySpec installations.
- Agent clients may require a reload, restart or new session after their plugin cache is refreshed. The CLI reports the requirement but does not conceal it.
- Local and CI reproducibility for external repositories currently depends on manually aligning the Git-visible CI npm pin with the local release-mode CLI. A later PR Flow（拉取请求流程） change may automate that alignment; Build and Verify（构建与验证） remains limited to running configured checks.
