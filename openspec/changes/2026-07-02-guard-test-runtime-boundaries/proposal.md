## Why

慢测试反复回归的根因不是单个文件慢，而是普通测试可以随意启动真实 CLI（命令行）、subprocess（子进程）、临时 git（版本控制）仓库和大范围 cache（缓存）扫描。并行只能缓解耗时，不能阻止未来测试重新引入同类成本。

## What Changes

- 增加全仓库测试运行边界守门，扫描整个 `tests/`。
- 普通测试禁止直接执行真实 subprocess（子进程）、CLI（命令行）入口、临时 git（版本控制）初始化和大范围 cache（缓存）扫描。
- 真实 E2E（端到端测试）按测试函数名白名单登记，不按文件整体放行。
- 收缩重复 E2E（端到端测试），把分支逻辑改为 in-process（进程内）测试和 fake runner（假执行器）。
- 固定 `maxParallel=0`，Pytest（测试工具）worker（工作进程）使用 `auto`，runner（执行器）给并行检查中的 `auto` 设置稳定 worker（工作进程）上限，并把 Full（完整验证）整体时间压到 30 秒内。
- 按用户授权，同一提交包含 `stabilize-flow-recovery-actions` 和 `stabilize-version-runtime-sync` 两个 OpenSpec（开放规格）脚手架；它们只作为规划产物提交，不属于本变更实现验收。

## Capabilities

### New Capabilities

- None

### Modified Capabilities

- `local-plugin-build-checks`: 仓库测试必须守住普通测试与 E2E（端到端测试）的运行边界。
- `test-framework-plugin`: build-and-verify（构建与验证）相关测试保留必要真实入口，其余分支逻辑走进程内测试。

## Impact

- 影响测试组织和多个插件测试文件的重复真实运行路径。
- 同一提交含两个独立后续 change（变更）脚手架，后续实现仍按各自 change（变更）推进。
- 不新增性能测试框架。
- 不删除所有 E2E（端到端测试）。
- 不依赖继续提高并行度来解决慢测试。
