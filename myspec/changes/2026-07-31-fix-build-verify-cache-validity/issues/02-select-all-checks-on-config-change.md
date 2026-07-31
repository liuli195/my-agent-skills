# 02 配置变化时选择全部检查

**Status:** completed
**Prerequisites:** none  
**Source:** GitHub Issue #239

## 用户结果

用户修改 `.build-and-verify/config.json`（配置文件）后运行 fast verify（快速验证），全部当前验证检查都会进入选择范围，并能看到一次明确原因说明。

## 验收标准

- 配置文件是唯一 changed file（变更文件）时，选择全部当前 `verify.checks`（验证检查项）。
- 输出只包含一条整体选择原因。
- 配置结构错误在任何检查调度前失败。
- 旧配置生成的缓存不能命中；当前配置已生成的缓存可以复用。
- 配置变化扩大选择范围但不强制重跑缓存命中的检查。
- 普通源码变化继续按现有 `paths`（受影响路径）选择检查。
- canonical runtime（规范运行时）与仓库 runtime snapshot（运行时快照）一致。

## 红灯与验证

1. 使用现有 fake runner（假执行器）增加失败检查：唯一变更为配置文件时，全部当前检查应被选择。
2. 覆盖整体原因输出、无效配置、当前配置缓存复用和普通路径选择。
3. 用同一组检查转绿。
4. 通过 Build and Verify（构建与验证）运行定向检查，并从仓库 runtime（运行时）的 fast verify（快速验证）命令执行最小真实冒烟。

## TDD（测试驱动开发）证据

- [x] 先新增 `test_runner_config_change_selects_all_checks_once`；仓库 runtime（运行时）`verify`（验证）入口红灯，配置文件为唯一变更时未调度任何检查。
- [x] 最小修复后，同一入口转绿；runner integration seam（运行器集成接缝）覆盖一次整体原因、全部选择、旧配置缓存失效、当前配置缓存复用、缓存命中不强制重跑、无效配置调度前失败和普通源码路径选择。
- [x] 审查修复：先让同一配置的预写缓存应命中，现有测试因 `_cache_key`（缓存键）默认 `runtime_version="unknown"` 与包装器注入的 `"test-runtime"` 不同而红灯；随后预写缓存同样使用 `"test-runtime"`，再验证配置变更后未命中、当前配置后续复用。

## 验证证据

- [x] 红灯：`python .build-and-verify/runtime/build_and_verify.py verify --project .`，`test_runner_config_change_selects_all_checks_once` 失败（0 次调度，期望 2 次）。
- [x] 绿灯与最小真实入口冒烟：`python .build-and-verify/runtime/build_and_verify.py verify --project .`，`verify.local-build-contract` 65 项通过，`verify.build-and-verify` 221 项通过；未使用 `--full`（完整）。
- [x] canonical runtime（规范运行时）与仓库 runtime snapshot（运行时快照）的 `build_and_verify.py` 和 `build_and_verify_runner.py` 字节一致。
- [x] 审查修复红灯：`python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .`，`test_runner_config_change_invalidates_old_cache_and_reuses_current_cache` 失败：预写同配置缓存仍调度 2 次。
- [x] 审查修复绿灯：同一 Build and Verify（构建与验证）fast（快速）入口 66 项通过，`verify.local-build-contract` 通过；未使用 `--full`（完整）。
