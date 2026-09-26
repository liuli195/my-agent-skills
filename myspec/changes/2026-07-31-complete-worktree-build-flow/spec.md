# 完成工作树构建主流程

**Status:** ready-for-agent

## Problem Statement

开发者通过统一初始化入口准备主工作区和关联工作树后，仍无法从关联工作树运行完整 Build and Verify（构建与验证）`build`（构建检查）主流程。Windows CI（持续集成）已经证明 Node.js（运行时）共享依赖和 `pi-tool-display` 编译成功，但仓库本地插件包检查因运行环境与初始化环境脱节而失败：PyYAML（YAML 解析库）安装在关联工作树的 `.venv`（虚拟环境）中，构建步骤却使用系统 Python（脚本语言）；同时，本地插件包检查依赖未声明、未由初始化入口提供的 `claude plugin validate` 外部命令。

这使初始化入口的用户承诺不成立，也让构建结果取决于机器是否碰巧全局安装 Claude Code（代码代理）和 Python 开发依赖。当前 `projection_plugins_mismatch` 与 `codex_dev_projection_plugins_mismatch` 还是 PyYAML 缺失后的连带结果，并非真实投影不一致。

## Solution

让主工作区和关联工作树继续通过同一个工作树初始化入口准备环境。主工作区保存唯一的 `.venv` 和根级 Node.js 依赖实体；关联工作树通过目录链接共享两者，不重复安装大型依赖。运行 Build and Verify（构建与验证）前，调用方使用目标工作区链接到共享 `.venv` 的 Python 环境，使所有仓库配置检查在同一环境中执行。

移除本地插件包检查对 `claude plugin validate` 的外部调用，不安装 Claude Code（代码代理），并保留仓库已有的清单字段、插件名称、路径存在性、目录边界、市场登记和发布投影一致性检查。CI（持续集成）不得增加直接 npm（软件包管理器）构建或其他并列检查入口；完整主流程仍只从 Build and Verify（构建与验证）进入。

## User Stories

1. As a repository contributor, I want one initialization command for the main checkout and linked worktrees, so that I do not need separate environment procedures.
2. As a linked-worktree developer, I want initialization followed by the Build and Verify build command to succeed, so that the documented workflow is complete.
3. As a main-checkout developer, I want the same initialization contract to prepare the environment used by Build and Verify, so that behavior does not depend on global packages.
4. As a Windows developer, I want the initialized virtual environment to be used by repository checks, so that PyYAML installed during setup is actually available during the build.
5. As a developer using multiple worktrees, I want Node.js dependencies shared from the main checkout, so that each worktree does not duplicate hundreds of megabytes.
6. As a developer using multiple worktrees, I want each linked worktree to reuse the main checkout's Python environment, so that large Python dependencies are not installed repeatedly.
7. As a contributor without Claude Code installed, I want repository-owned package checks to run without that unrelated global command, so that local builds are reproducible.
8. As a maintainer, I want plugin manifests and marketplace registrations still checked, so that removing the external Claude command does not remove the repository's structural safeguards.
9. As a maintainer, I want release projection consistency still checked with the declared Python dependencies, so that genuine projection drift remains a build failure.
10. As a CI maintainer, I want Build and Verify to remain the only build and verification entry, so that direct npm or script checks cannot diverge from local behavior.
11. As a reviewer, I want the Windows linked-worktree regression to execute the complete user flow, so that a passing TypeScript compilation alone cannot hide a later build failure.
12. As a maintainer, I want failures to identify the true missing dependency or inconsistency, so that a YAML parser failure is not mistaken for four independent defects.
13. As a repository contributor, I want a fresh checkout to fail clearly when initialization has not been run, so that Build and Verify does not silently install dependencies or mutate the environment.
14. As a maintainer, I want no new dependency manager, wrapper command, or second build path, so that the fix remains small and supportable.

## Implementation Decisions

- Preserve `scripts/setup-worktree.ps1` as the single environment initialization entry for both the main checkout and linked worktrees.
- Use the same shared dependency model as the quantitative research repository: the main checkout owns the only `.venv` and root `node_modules` entities, while compatible linked worktrees use directory links to both.
- Record a Python dependency fingerprint in the shared `.venv`; linked worktrees must stop when the shared environment is missing, stale, or based on a different dependency manifest.
- Refuse to overwrite or delete an existing linked-worktree `.venv` or `node_modules` that does not point to the expected shared target.
- Treat initialization as a prerequisite for a fresh checkout. Build and Verify remains non-mutating and does not install dependencies.
- Run Build and Verify with the target checkout's initialized Python environment active so configured child commands resolve the same Python environment and declared packages.
- Keep Build and Verify as the only CI build and verification entry. Do not add direct npm, TypeScript, local package script, or equivalent parallel checks.
- Remove every `claude plugin validate` subprocess call from the repository-owned local plugin package build check.
- Do not add `@anthropic-ai/claude-code` or another Claude CLI package to repository dependencies. Its platform package would add roughly 266–275 MB and is unnecessary for the retained checks.
- Retain repository-owned validation of marketplace structure, plugin and manifest names, required manifest fields, referenced local paths, repository path boundaries, duplicate registrations, Codex development marketplace consistency, and release projection consistency.
- Keep PyYAML in the declared Python development dependencies and use the initialized environment rather than adding a second YAML parser or a handwritten parser.
- The Windows linked-worktree CI flow must initialize the main checkout, initialize the linked worktree, activate the linked worktree environment, and invoke Build and Verify `build` against that linked worktree.
- This decision intentionally changes the active `local-plugin-build-checks` specification, which currently requires Claude CLI validation. That requirement must be replaced by the repository-owned structural validation contract rather than silently ignored.
- This change completes the reopened GitHub Issue #230 acceptance criterion; it does not replace the already-delivered Node.js dependency sharing behavior.

## Testing Decisions

- The primary and highest test seam is the existing Windows linked-worktree CI flow. It exercises a fresh main checkout, public initialization entry, real Git linked worktree, shared Node.js dependency link, linked-worktree Python environment, and the complete Build and Verify `build` command.
- The end-to-end regression must assert success of the whole Build and Verify command, not only `tsc`, npm workspace compilation, or the repository-owned local package script.
- CI automation must contain only Build and Verify build and verification invocations as check entries; setup commands may prepare the environment but may not duplicate build assertions.
- Existing local plugin package subprocess tests provide prior art for command availability and manifest error behavior. Update them to prove the build no longer invokes or requires `claude` while retained malformed manifest, path, marketplace, and projection cases still fail.
- Existing setup script tests remain the focused seam for main-checkout initialization, linked-worktree junction creation, missing shared dependencies, mismatched manifests, idempotent reuse, and setup failure propagation.
- Add or update a contract check proving the Windows workflow uses the linked worktree's initialized Python environment before invoking Build and Verify.
- Preserve the original red-capable failure shape: without the fix, the complete linked-worktree build reports `missing_command: claude`, `missing_dependency: PyYAML`, and two projection mismatch messages after TypeScript compilation succeeds.
- Complete verification must use the repository Build and Verify entry and cover the packaged or published execution shape required by repository rules.
- Tests should assert exit status and public diagnostics, not private helper decomposition or exact internal subprocess counts beyond proving the removed external dependency is absent.

## Out of Scope

- Adding Claude Code or another large CLI dependency.
- Replacing PyYAML with a handwritten YAML parser.
- Making Build and Verify install or update dependencies.
- Creating or installing a separate Python virtual environment inside each linked worktree.
- Renaming or moving `.worktrees`.
- Changing the root Node.js workspace or dependency-link design already delivered for Issue #230.
- Adding a direct npm, TypeScript, or repository script check to CI alongside Build and Verify.
- Refactoring unrelated local plugin checks or Build and Verify runtime architecture.
- Installing plugins or changing user-level agent configuration.

## Further Notes

The reproduced fast failure command was `PATH="$(dirname "$(command -v python)"):/usr/bin" python -S scripts/local_plugin_build.py`, which produced the same four diagnostics as GitHub Actions run `30574529083`. The run also showed `pi-tool-display` TypeScript compilation passing before the overall Build and Verify command failed, isolating the remaining defect from Node.js dependency sharing.

The existing specification conflict is deliberate and must be resolved as part of this change: native Claude CLI validation is being removed because it is an undeclared, heavyweight, globally resolved prerequisite, while the repository-owned checks that protect package structure remain mandatory.
