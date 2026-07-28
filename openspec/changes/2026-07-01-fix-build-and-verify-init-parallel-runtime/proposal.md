## Why

`build-and-verify-init`（构建与验证初始化）当前会写入 `.build-and-verify/config.json`（配置文件），但不会复制仓库内 runtime（运行时），与初始化规格不一致。并行配置也把 check（检查项）之间并行和 pytest（Python 测试框架）内部并行混在一起，导致用户误解 `parallel: true`（并行）语义。

## What Changes

- **BREAKING**: 删除旧 `parallel`（并行）配置字段，改为 `checkParallel`（检查项间并行）。
- 新增 `pytestXdistWorkers`（Pytest 工作进程数）配置字段，用于显式开启 pytest（Python 测试框架）内部并行。
- 让默认 `verify`（快速验证）和 `verify --full`（完整验证）都复用 check（检查项）间并行调度。
- 扩展 `build_and_verify.py init`（初始化命令），支持接收已确认配置、覆盖备份、合并 `.gitignore`（忽略规则）并复制 runtime（运行时）。
- 更新 `build-and-verify-init`（构建与验证初始化）问答和校验流程，使最终写入通过初始化命令完成。
- 不在本流程覆盖初始化 `D:\My Project\Quant-Research-Lab`。

## Capabilities

### New Capabilities

### Modified Capabilities
- `test-framework-plugin`: 修改初始化、配置字段、pytest-xdist（Pytest 并行插件）显式配置和依赖校验要求。
- `full-verification-runtime`: 修改 check（检查项）间并行在快速验证和完整验证中的调度要求。

## Impact

- `plugins/build-and-verify/skills/build-and-verify/scripts/`
- `plugins/build-and-verify/skills/build-and-verify-init/`
- `.build-and-verify/config.json`
- `.build-and-verify/runtime/`
- `tests/test_build_and_verify_plugin.py`
- `openspec/specs/test-framework-plugin/`
- `openspec/specs/full-verification-runtime/`
