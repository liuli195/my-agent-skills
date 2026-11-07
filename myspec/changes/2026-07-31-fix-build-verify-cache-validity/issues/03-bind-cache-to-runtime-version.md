# 03 缓存绑定运行时版本

**Status:** completed
**Prerequisites:** none
**Source:** GitHub Issue #240

## 用户结果

用户运行 `update-runtime`（更新运行时）得到新版本后，fast verify（快速验证）不会复用旧运行时生成的通过缓存。

## 验收标准

- 相同运行时版本和相同输入仍可命中缓存。
- 运行时版本变化后，旧缓存不能命中。
- fast verify（快速验证）和 full verify（完整验证）缓存都包含当前固定运行时版本。
- 运行时版本不存在时，两种验证模式在运行检查或读写缓存前报错。
- `build`（构建检查）在运行时版本不存在时仍可运行。
- 不增加执行文件摘要后备，不删除旧缓存文件。
- canonical runtime（规范运行时）与仓库 runtime snapshot（运行时快照）一致。

## 红灯与验证

1. 使用现有 fake runner（假执行器）增加失败检查：版本变化后旧缓存当前仍会命中。
2. 覆盖相同版本命中、完整验证写缓存、缺失版本失败和构建检查不受影响。
3. 用同一组检查转绿。
4. 通过 Build and Verify（构建与验证）运行定向检查，并用更新后的仓库 runtime（运行时）执行更新前后缓存最小真实冒烟。

## TDD（测试驱动开发）证据

- [x] 先新增 `test_runner_binds_cache_to_runtime_version_and_requires_version`；`python .build-and-verify/runtime/build_and_verify.py verify --project .` 红灯：版本从 `1.0.0` 变为 `2.0.0` 后仍错误命中旧缓存。
- [x] 最小修复后，同一检查覆盖相同版本命中、版本变化失效、full verify（完整验证）写入后供 fast verify（快速验证）命中，以及缺失版本在调度或缓存读写前失败；`build`（构建检查）仍可运行。
- [x] 审查修复红灯：新增 `test_repository_runtime_requires_runtime_version_before_verify_runs_or_caches`；仓库 runtime（运行时）的 `version.json` 只含 `plugin_version`（插件版本）时，旧实现仍执行检查并返回成功，而预期在运行检查或缓存读写前以 `missing_runtime_version`（缺失运行时版本）失败。

## 验证证据

- [x] 绿灯：`python .build-and-verify/runtime/build_and_verify.py verify --project .`，`verify.local-build-contract` 66 项通过，`verify.build-and-verify` 221 项通过；未使用 `--full`（完整）。
- [x] 最小真实入口冒烟：`python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py update-runtime --project .` 后，`python .build-and-verify/runtime/build_and_verify.py verify --project .` 两项检查均缓存命中并通过。
- [x] canonical runtime（规范运行时）与仓库 runtime snapshot（运行时快照）的 `build_and_verify.py` 和 `build_and_verify_runner.py` 字节一致。
- [x] 审查修复绿灯：`python .build-and-verify/runtime/build_and_verify.py verify --project .` 通过，`verify.local-build-contract` 66 项和 `verify.build-and-verify` 222 项通过；随后同一真实 fast verify（快速验证）入口两项均 `cache-hit`（缓存命中）并通过。未使用 `--full`（完整）。
