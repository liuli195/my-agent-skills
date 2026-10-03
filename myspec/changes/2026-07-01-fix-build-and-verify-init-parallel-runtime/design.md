## Context

`build-and-verify-init`（构建与验证初始化）目前由 agent（代理）直接写 `.build-and-verify/config.json`（配置文件），没有通过 `build_and_verify.py init`（初始化命令）统一落盘，因此可能漏掉 runtime（运行时）复制。并行配置也只有 `parallel`（并行）字段，实际表达 check（检查项）之间并行，但容易被理解为 pytest（Python 测试框架）内部并行。

## Goals / Non-Goals

**Goals:**
- 初始化写入统一经过 `build_and_verify.py init`（初始化命令）。
- 用 `checkParallel`（检查项间并行）替换旧 `parallel`（并行）字段。
- 用 `pytestXdistWorkers`（Pytest 工作进程数）显式表达 pytest-xdist（Pytest 并行插件）并行。
- 默认 `verify`（快速验证）和 `verify --full`（完整验证）都支持 check（检查项）间并行。

**Non-Goals:**
- 不兼容旧 `parallel`（并行）字段。
- 不自动安装依赖。
- 不覆盖初始化 `D:\My Project\Quant-Research-Lab`。

## Decisions

1. `init`（初始化命令）成为唯一落盘入口。
   - `--config` 接收已确认配置文件。
   - `--overwrite` 允许覆盖已有配置，并在写入前备份。
   - runtime（运行时）每次初始化都刷新。

2. 并行配置拆成两个字段。
   - `checkParallel` 控制 check（检查项）之间能否并行调度。
   - `pytestXdistWorkers` 控制 pytest（Python 测试框架）内部 worker（工作进程）数量。

3. 快速验证复用完整验证调度器。
   - 快速验证先按 changed files（变更文件）和 cache（缓存）筛出要执行的 check（检查项）。
   - 筛出的 check（检查项）再按 `checkParallel` 调度。

## Risks / Trade-offs

- [Risk] 旧配置会失败。Mitigation: 用户已确认不保留兼容，通过重新初始化覆盖配置。
- [Risk] `pytestXdistWorkers` 自动拼接命令可能误改非 pytest（Python 测试框架）命令。Mitigation: 仅当命令明确是 pytest（Python 测试框架）入口时生效，否则配置无效。
- [Risk] 并行会放大共享状态污染。Mitigation: 用户必须显式选择 `checkParallel`，未声明默认串行。
