---
comet_change: fix-build-and-verify-init-parallel-runtime
role: technical-design
canonical_spec: openspec
---

# Build and Verify Init Parallel Runtime Design

## Context

`build-and-verify-init`（构建与验证初始化）当前由 agent（代理）按参考文档直接写 `.build-and-verify/config.json`（配置文件）。这绕过了 `build_and_verify.py init`（初始化命令），所以会漏掉仓库内 runtime（运行时）复制。并行配置也只有 `parallel`（并行）字段；源码实际把它解释为 check（检查项）之间并行，但用户容易理解为 pytest（Python 测试框架）内部并行。

## Design

`build_and_verify.py init`（初始化命令）成为唯一落盘入口。默认 `init --project <repo>` 继续创建空模板；`init --project <repo> --config <file> --overwrite` 使用已确认配置覆盖初始化，负责在旧配置存在时备份、合并 `.gitignore`（忽略规则）、复制 runtime（运行时）和创建 cache（缓存）。首次初始化没有旧配置时直接写入已确认配置。

配置字段拆成两个明确含义：

- `checkParallel`（检查项间并行）：check（检查项）之间可并行调度。
- `pytestXdistWorkers`（Pytest 工作进程数）：pytest（Python 测试框架）内部 worker（工作进程）数量，值为 `"auto"` 或正整数。

旧 `parallel`（并行）字段不再支持。默认 `verify`（快速验证）先按 changed files（变更文件）和 cache（缓存）筛选需要执行的 check（检查项），再复用完整验证的调度器；`verify --full`（完整验证）直接调度全部 check（检查项），不因 cache（缓存）跳过。`pytestXdistWorkers`（Pytest 工作进程数）只允许声明在 pytest（Python 测试框架）命令上，非 pytest（Python 测试框架）命令声明该字段属于配置错误。

`build-and-verify-init`（构建与验证初始化）在最终写入前检查草案中的运行参数。草案包含 `pytestXdistWorkers`（Pytest 工作进程数）时，先检查目标环境是否可用 `pytest-xdist`（Pytest 并行插件），并列出影响和建议；该检查不自动安装依赖，也不阻止用户确认写入。

## Risks

旧配置会失败；用户已确认通过重新初始化覆盖配置迁移。`pytestXdistWorkers`（Pytest 工作进程数）只对明确 pytest（Python 测试框架）命令生效，避免误改其他命令。

## Tests

测试覆盖：

- `init --config --overwrite` 备份、写配置、合并 `.gitignore`（忽略规则）并复制 runtime（运行时）。
- `parallel`（并行）被拒绝，`checkParallel`（检查项间并行）被接受。
- fast/full（快速/完整）验证都按 `checkParallel`（检查项间并行）并行调度。
- `pytestXdistWorkers`（Pytest 工作进程数）添加 pytest-xdist（Pytest 并行插件）参数，并在缺失依赖时报错。
- 使用临时目标仓库跑端到端初始化回归，检查 `init --config --overwrite`（初始化覆盖命令）、runtime（运行时）复制、cache（缓存）创建、可选备份、fast（快速）验证和 full（完整）验证。
