## Context

本次调查的本机证据：

- `python scripts/check.py verify`: 341 passed，约 214 秒。
- `python -m pytest --durations=40 -q`: 最慢项集中在 `tests/test_pr_flow_cli.py`。
- 按文件计时：`test_pr_flow_cli.py` 约 135 秒，占完整验证约六成。
- 按 PR Flow（拉取请求流程）分组：`complete/tweak` 约 77 秒，`cleanup` 约 32 秒，`hotfix` 约 28 秒，`diagnose` 约 10 秒。
- 当前没有 `pytest-xdist`（并行测试插件），不能把并行当作现成方案。

慢因不是业务逻辑本身，而是测试结构反复支付重成本：每个相关测试创建真实 Git（版本管理）仓库、提交、push（推送）、clone（克隆），再通过 Python CLI（命令行程序）子进程调用脚本，并用 fake `gh`（GitHub 命令行工具）脚本文件记录调用。

## Goals / Non-Goals

**Goals:**
- 把 full（完整）验证从约 214 秒压到 60 秒以内。
- 保留 PR Flow（拉取请求流程）关键行为覆盖，不用删测试换速度。
- 优先优化 `test_pr_flow_cli.py`，因为它是最大耗时来源。
- 用数据分阶段验证：每次重构后记录文件级和全量耗时。

**Non-Goals:**
- 不改变 PR Flow（拉取请求流程）生产行为。
- 不在未经设计确认的情况下新增测试依赖。
- 不把 full（完整）验证变成 partial（局部）验证。
- 不把第一个 change（变更）的 fast/full（快速/完整）入口拆分混进本 change（变更）。

## Decisions

1. 先优化测试结构，不先引入并行依赖。
   - 备选方案是安装 `pytest-xdist`（并行测试插件）后用并行跑测试，但当前环境未安装，而且真实 Git（版本管理）临时目录测试并行后可能引入隔离问题。
   - 先减少单测试成本更稳。

2. PR Flow（拉取请求流程）测试分层。
   - 保留少量真实 CLI（命令行程序）+ Git（版本管理）端到端测试，覆盖 happy path（成功路径）和关键安全门。
   - 其余 stop state（停机状态）、配置分支、review gate（审查门禁）和错误分支改为进程内调用或更轻的 fixture（测试夹具）。
   - 如果需要，可以给脚本提取小的测试 seam（测试接缝），例如可注入的 `gh`/`git` runner（运行器），但不改变命令行外部行为。

3. 先处理最大耗时分组。
   - 第一轮目标：`complete/tweak` 分组从约 77 秒降到 25 秒以内。
   - 第二轮目标：`cleanup` + `hotfix` 从约 60 秒降到 20 秒以内。
   - 第三轮目标：复测全量，若仍超过 60 秒，再看 `agent_guard_runtime_router`、`cross_agent_review_cli` 和 `release_flow_cli`。

## Risks / Trade-offs

- [Risk] 进程内测试可能漏掉 CLI（命令行程序）参数解析或真实进程环境问题。Mitigation: 保留少量 CLI（命令行程序）端到端测试覆盖参数和真实执行路径。
- [Risk] 共享 fixture（测试夹具）可能导致测试间状态污染。Mitigation: fixture（测试夹具）只共享不可变基础仓库模板；每个测试复制或创建独立工作副本。
- [Risk] 小 seam（测试接缝）可能变成过度抽象。Mitigation: 只提取当前慢测试直接需要的 runner（运行器）或状态构造函数。
- [Risk] 1 分钟目标受机器性能影响。Mitigation: 使用本机当前基线作为目标环境，并在报告中记录具体命令和耗时。

