# Brainstorm Summary

- Change: fix-build-and-verify-init-parallel-runtime
- Date: 2026-07-02

## 确认的技术方案

使用 `checkParallel`（检查项间并行）替换旧 `parallel`（并行）字段，不保留兼容逻辑。新增 `pytestXdistWorkers`（Pytest 工作进程数）显式表示 pytest（Python 测试框架）内部并行。`build_and_verify.py init`（初始化命令）扩展为 `init --config <file> --overwrite`，由命令统一执行备份、写配置、合并 `.gitignore`（忽略规则）、复制 runtime（运行时）和创建 cache（缓存）。

## 关键取舍与风险

- 不保留旧 `parallel`（并行）兼容，接受通过重新初始化覆盖配置完成迁移。
- `checkParallel`（检查项间并行）不触发依赖安装；只有 `pytestXdistWorkers`（Pytest 工作进程数）需要检查 pytest-xdist（Pytest 并行插件）。
- 不覆盖初始化 `D:\My Project\Quant-Research-Lab`，本 change（变更）只改当前仓库。

## 测试策略

新增 focused regression（聚焦回归）覆盖 init（初始化）覆盖写入、runtime（运行时）复制、`checkParallel`（检查项间并行）在 fast/full（快速/完整）验证中调度、`pytestXdistWorkers`（Pytest 工作进程数）命令应用和缺依赖失败。

## Spec Patch

已回写 delta spec（规格差异）：`test-framework-plugin`（测试框架插件）和 `full-verification-runtime`（完整验证运行时）。
