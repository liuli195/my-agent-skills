## Context

`.build-and-verify/config.json`（构建与验证配置文件）的 `verify.build-and-verify`（构建与验证检查）显式列出 pytest（Python 测试运行器）文件。新增 `tests/test_setup_worktree_script.py`（工作树初始化脚本测试）后，配置未同步，导致测试清单一致性检查失败。

## Goals / Non-Goals

**Goals:**

- 让该测试成为 `verify.build-and-verify`（构建与验证检查）的受影响路径、执行命令和缓存输入。
- 恢复所有 `tests/test_*.py`（Python 测试文件）均被显式 pytest（Python 测试运行器）命令覆盖的契约。

**Non-Goals:**

- 不改变检查标识、并行参数、超时或验证模式。
- 不新增依赖、测试框架或配置字段。

## Decisions

1. 只修改 `verify.build-and-verify`（构建与验证检查）。
   - 该检查已负责 `tests/test_build_and_verify_plugin.py`（构建与验证插件测试）及相邻 Build and Verify（构建与验证）测试。
   - 将新测试同时加入 `paths`（受影响路径）、`command`（执行命令）和 `inputs`（缓存输入），使快速选择、实际执行和缓存键一致。

2. 以现有失败测试作为回归证据。
   - `test_build_and_verify_explicit_pytest_paths_cover_removed_pyproject_testpaths`（显式测试路径覆盖检查）已经精确暴露遗漏，无需新增测试逻辑。

## Risks / Trade-offs

- [只更新执行命令] → 同时更新受影响路径和缓存输入，避免快速验证漏选或缓存失效。
- [测试清单再次遗漏] → 现有一致性测试持续比对配置与 `tests/test_*.py`（Python 测试文件）。

## Migration Plan

修改配置后运行定向测试和完整 pytest（Python 测试运行器）套件；回滚只需移除该测试路径的三处登记。