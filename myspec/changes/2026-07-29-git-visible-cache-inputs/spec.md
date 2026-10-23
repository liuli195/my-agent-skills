# Git 可见缓存输入

**Status:** ready-for-agent

## Problem Statement

Build and Verify（构建与验证）在为目录型缓存输入计算缓存键时，会递归读取目录中的所有文件，却不遵循 Git（版本管理）的忽略规则。依赖目录和构建产物即使已被 `.gitignore`（忽略配置）隐藏，仍可能被逐文件读取和计算摘要。

这会让原本可以并行完成的完整验证被缓存键计算阻塞。实际案例中，一个包含约 38,000 个依赖文件的目录使单项缓存键计算耗时超过 50 秒，而该检查的实际测试只需约 16 秒。

## Solution

目录型缓存输入应以 Git 可见文件为边界：包含已跟踪文件，以及未跟踪但未被忽略的文件。被 Git 忽略的未跟踪文件不参与缓存键。

显式指定的单个文件保持现有语义，即使该文件被忽略也参与缓存键。Git 不可用、命令失败或目标不是 Git 仓库时，直接回退现有目录遍历行为。

## User Stories

1. As a developer, I want ignored dependency files excluded from directory cache inputs, so that verification does not spend time hashing installed dependencies.
2. As a developer, I want ignored build artifacts excluded from directory cache inputs, so that generated output does not slow verification or cause irrelevant cache misses.
3. As a repository maintainer, I want each repository's Git ignore rules to define generated content, so that the runtime does not maintain an incomplete hard-coded exclusion list.
4. As a developer, I want tracked files included even when later ignore rules match them, so that source changes always invalidate the relevant cache.
5. As a developer, I want untracked but non-ignored files included, so that newly created source files affect verification before they are committed.
6. As a repository maintainer, I want explicitly named files to retain their current behavior, so that an intentionally cached ignored configuration or artifact remains supported.
7. As a user of a non-Git repository, I want verification to continue using directory traversal, so that Git does not become a mandatory runtime dependency.
8. As a user encountering a Git command failure, I want verification to fall back safely, so that cache-key calculation remains available rather than failing the check.
9. As a maintainer, I want the change limited to cache-input enumeration, so that command execution, parallel scheduling, and configuration semantics remain unchanged.
10. As a maintainer, I want repository runtime snapshots synchronized with the canonical implementation, so that checked-in projects execute the fixed behavior.

## Implementation Decisions

- A directory cache input is defined as a collection of Git visible files when the project is a usable Git repository.
- Git visible files consist of cached tracked files and untracked files that survive standard ignore rules.
- File enumeration uses a null-delimited Git result so paths containing whitespace or unusual characters remain unambiguous.
- Explicit single-file inputs bypass directory enumeration and retain existing behavior.
- A Git enumeration failure falls back directly to the existing directory walker.
- The fallback does not add fixed exclusions for dependency directories, virtual environments, coverage output, or build artifacts.
- No new configuration field, ignore syntax, shared file-list cache, or parallel scheduling behavior is introduced.
- The canonical runtime implementation and repository runtime snapshot remain identical.

## Testing Decisions

- Test at the existing runner integration seam using a temporary Git repository rather than testing a new helper in isolation.
- The regression scenario must contain a tracked file, an untracked visible file, and an ignored file under one directory input.
- Changing tracked or visible untracked content must change the cache result; changing ignored content must not change it.
- An explicitly configured ignored file must still affect its cache result.
- A non-Git project or failed Git enumeration must demonstrate the existing directory traversal fallback.
- Existing cache, verification, and runtime synchronization tests remain the prior art and should be extended rather than introducing another test entry point.
- Complete verification must pass after the runtime snapshot is synchronized.

## Out of Scope

- Hard-coded exclusions such as `node_modules`, `.venv`, `dist`, `build`, or `coverage`.
- A configurable ignore list or an override to force an ignored directory into directory enumeration.
- Caching one Git file inventory across multiple checks.
- Changing cache-key schema beyond the file set naturally represented in the existing payload.
- Changing check-level parallelism, Pytest worker counts, command execution, timeout behavior, or performance budgets.
- Optimizing individual test suites.

## Further Notes

The repository-level workaround that narrows broad cache inputs remains valid, but it should no longer be required solely to avoid Git-ignored dependencies after this runtime change. The observed runtime snapshot version matches the canonical plugin implementation, so this is a behavior change rather than a stale-runtime update.
