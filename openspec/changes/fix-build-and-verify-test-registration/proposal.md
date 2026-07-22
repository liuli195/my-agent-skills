## Why

工作树初始化脚本测试已新增，但 Build and Verify（构建与验证）配置的显式 pytest（Python 测试运行器）命令没有登记该测试。全量 pytest（Python 测试运行器）因此失败，且默认验证无法覆盖该测试。

## What Changes

- 将 `tests/test_setup_worktree_script.py`（工作树初始化脚本测试）登记到 `verify.build-and-verify`（构建与验证检查）的受影响路径、测试命令和缓存输入。
- 不改变 Build and Verify（构建与验证）配置结构或公开接口；补齐既有规格中 pytest（Python 测试运行器）测试路径完整性的验收场景。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `test-framework-plugin`：明确显式 pytest（Python 测试运行器）命令必须覆盖仓库全部 `tests/test_*.py`（Python 测试文件）。

## Impact

- 修改 `.build-and-verify/config.json`（构建与验证配置文件）。
- 恢复 `tests/test_build_and_verify_plugin.py`（构建与验证插件测试）的测试清单一致性。