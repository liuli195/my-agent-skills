## Context

本次调查的本机证据：

- full verification（完整验证）baseline（基线）: 341 passed，约 214 秒；当前工作区的 canonical command（规范命令）为 `python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full`，实施前需要用该命令重跑并刷新证据。
- `python -m pytest --durations=40 -q`: 最慢项集中在 `tests/test_pr_flow_cli.py`。
- 按文件计时：`test_pr_flow_cli.py` 约 135 秒，占完整验证约六成。
- 按 PR Flow（拉取请求流程）分组：`complete/tweak` 约 77 秒，`cleanup` 约 32 秒，`hotfix` 约 28 秒，`diagnose` 约 10 秒。
- 初始环境没有 `pytest-xdist`（并行测试插件）；用户确认后，依赖安装到当前系统 `python`（Python 解释器）环境，并作为并行层接入。

慢因不是业务逻辑本身，而是测试结构反复支付重成本：每个相关测试创建真实 Git（版本管理）仓库、提交、push（推送）、clone（克隆），再通过 Python CLI（命令行程序）子进程调用脚本，并用 fake `gh`（GitHub 命令行工具）脚本文件记录调用。

## Goals / Non-Goals

**Goals:**
- 把 full（完整）验证从约 214 秒压到 60 秒以内。
- 保留 local build contract（本地构建契约）、PR Flow（拉取请求流程）、Release Flow（发布流程）、Agent Guard（代理守卫）、cross-agent-review（跨代理审查）和 Test Framework（测试框架）关键行为覆盖，并保留 `verify.openspec`（开放规格验证）覆盖和计时，不用删测试换速度。
- 第一层 repo-native（仓库内自带）测试优化对全仓库测试生效，优先优化 `test_pr_flow_cli.py`，因为它是最大耗时来源。
- 第二层并行执行由 Test Framework（测试框架）runner（运行器）统一协调，对所有 configured verify checks（已配置验证检查项）在安全时生效，不能只给单个文件开特殊路径。
- 用数据分阶段验证：每次重构后记录文件级和全量耗时。

**Non-Goals:**
- 不改变 PR Flow（拉取请求流程）生产行为。
- 不自动安装测试依赖；pytest-xdist（并行测试插件）必须先评估，只有在项目环境已可用或用户明确授权安装后才接入命令。本次用户已授权使用当前系统 `python`（Python 解释器）。
- 不把 full（完整）验证变成 partial（局部）验证。
- 不把第一个 change（变更）的 fast/full（快速/完整）入口拆分混进本 change（变更）。
- 不创建或修改 `docs/rules/` 下任何文件；测试写法规则先沉淀在 OpenSpec（规格流程）产物里。

## Decisions

1. 先做 repo-native（仓库内自带）测试结构优化，再做套件级并行。
   - 第一层减少单测试成本：共享 Git（版本管理）fixture（测试夹具）、fake CLI（模拟命令行工具）stub（替身）、in-process（进程内）调用和窄 test seam（测试接缝）。
   - 第二层由 Test Framework（测试框架）runner（运行器）调度所有 verify checks（验证检查项）的 parallel-safe（可并行）和 serial-only（只串行）分组。
   - pytest-xdist（并行测试插件）是并行层的加速器；不能在未安装且未获授权时把命令改成依赖 xdist（并行测试）worker（工作进程）参数。本次接入发生在用户授权安装之后。

2. 全仓库测试分层，PR Flow（拉取请求流程）先行。
   - 保留少量真实 CLI（命令行程序）+ Git（版本管理）端到端测试，覆盖 happy path（成功路径）和关键安全门。
   - 其余 stop state（停机状态）、配置分支、review gate（审查门禁）和错误分支改为进程内调用或更轻的 fixture（测试夹具）。
   - 如果需要，可以给脚本提取小的测试 seam（测试接缝），例如可注入的 `gh`/`git` runner（运行器），但不改变命令行外部行为。

3. 先处理最大耗时分组，再扩展到剩余瓶颈。
   - 第一轮目标：`complete/tweak` 分组从约 77 秒降到 25 秒以内。
   - 第二轮目标：`cleanup` + `hotfix` 从约 60 秒降到 20 秒以内。
   - 第三轮目标：Test Framework（测试框架）full verify（完整验证）支持并行调度和串行兜底。
   - 第四轮目标：复测全量，若仍超过 60 秒，再按最新 durations（耗时报告）优化 `agent_guard_runtime_router`、`cross_agent_review_cli`、`release_flow_cli` 或其它最大剩余项。

## Risks / Trade-offs

- [Risk] 进程内测试可能漏掉 CLI（命令行程序）参数解析或真实进程环境问题。Mitigation: 保留少量 CLI（命令行程序）端到端测试覆盖参数和真实执行路径。
- [Risk] 共享 fixture（测试夹具）可能导致测试间状态污染。Mitigation: fixture（测试夹具）只共享不可变基础仓库模板；每个测试复制或创建独立工作副本。
- [Risk] 小 seam（测试接缝）可能变成过度抽象。Mitigation: 只提取当前慢测试直接需要的 runner（运行器）或状态构造函数。
- [Risk] pytest-xdist（并行测试插件）不可用时提前改命令会破坏 full verification（完整验证）。Mitigation: 先检测可用性；不可用时只记录依赖和结论，不把 verify check（验证检查项）改成必须使用 xdist（并行测试）worker（工作进程）参数；本次已在用户授权安装后逐组验证再接入。
- [Risk] 并行运行会放大共享状态污染。Mitigation: 每个 check（检查项）声明 parallel（并行）策略；不安全的 check（检查项）仍在 full verification（完整验证）里串行运行。
- [Risk] 1 分钟目标受机器性能影响。Mitigation: 使用本机当前基线作为目标环境，并在报告中记录具体命令和耗时。
