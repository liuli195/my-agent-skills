## 1. 回归证据

- [x] 1.1 运行 `test_build_and_verify_explicit_pytest_paths_cover_removed_pyproject_testpaths`（显式测试路径覆盖检查），确认新工作树初始化脚本测试尚未登记时失败。

## 2. 配置修复

- [ ] 2.1 在 `verify.build-and-verify`（构建与验证检查）的 `paths`（受影响路径）、`command`（执行命令）和 `inputs`（缓存输入）中登记 `tests/test_setup_worktree_script.py`（工作树初始化脚本测试）。

## 3. 验证

- [ ] 3.1 运行定向回归测试、完整 pytest（Python 测试运行器）套件、OpenSpec（开放规格）严格校验及 Build and Verify（构建与验证）的 build（构建检查）和默认 verify（快速验证）。