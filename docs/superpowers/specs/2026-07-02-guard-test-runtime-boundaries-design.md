---
comet_change: guard-test-runtime-boundaries
role: technical-design
canonical_spec: openspec
archived-with: 2026-07-02-guard-test-runtime-boundaries
status: final
---

# Guard Test Runtime Boundaries Design

## 背景

当前慢测试的根因不是单个测试文件慢，而是普通测试可以直接启动 subprocess（子进程）、真实 CLI（命令行）、临时 git（版本控制）仓库和 broad cache（大范围缓存）扫描。只优化某个慢文件会留下回归入口。

本变更建立仓库级测试运行边界：普通测试默认走 in-process（进程内）路径，真实 E2E（端到端测试）只按 test function identity（测试函数身份）登记放行。

## 技术方案

新增一个仓库级 boundary guard（边界守门）测试，放在现有测试套件内，扫描整个 `tests/` 目录。

扫描使用 Python AST（Python 语法树），按 test function（测试函数）收集以下高成本行为：

- 直接调用 subprocess（子进程）执行。
- 直接或通过本仓库已有 helper（辅助函数）/ fixture（测试夹具）调用真实 CLI（命令行）入口。
- 直接或通过本仓库已有 helper（辅助函数）/ fixture（测试夹具）初始化临时 git（版本控制）仓库。
- 对 runtime cache（运行时缓存）做大范围扫描。

守门测试维护一个小型 E2E allowlist（端到端白名单）。allowlist（白名单）键使用 file path + qualified test function（文件路径加限定测试函数）格式，并写明原因；不允许按整个文件放行。参数化测试按同一个 test function（测试函数）登记理由。

build-and-verify（构建与验证）测试保持两类路径：

- 少量真实 E2E（端到端测试）证明 packaged entrypoint（发布形态入口）可运行：至少保留一个 init（初始化）入口和一个 verify（验证）入口；额外真实 E2E（端到端测试）只能用于不同 packaged entrypoint（发布形态入口）行为，并必须显式写入 allowlist（白名单）。
- 分支逻辑、cache（缓存）选择、命令规划、失败分类和 runtime（运行时）报告走已有 `run_check`（进程内检查入口）或 runner（执行器）函数，并使用 fake runner（假执行器）。

这里的 verify（验证）真实入口指默认 fast-verify（快速验证）入口；full verify（完整验证）分支行为由进程内 fake runner（假执行器）覆盖，避免重复真实子进程。

实现过程中目标升级为 Full（完整验证）整体 30 秒内。配置固定 `maxParallel=0`，Pytest（测试工具）使用 `auto`，不继续靠调高并行数解决问题。runner（执行器）在外部未设置 `PYTEST_XDIST_AUTO_NUM_WORKERS`（Pytest 自动工作进程数）时，为并行检查里的 `auto` 提供 4 个 worker（工作进程）的稳定上限，避免多个检查同时吃满 CPU（处理器）。重复真实运行路径从 build-and-verify（构建与验证）扩展到 PR Flow（拉取请求流程）、Release Flow（发布流程）、Cross Agent Review（跨代理审查）和 Agent Guard（代理守卫）测试；只保留能证明发布形态入口或关键真实边界的 E2E（端到端测试）。

同一提交还按用户授权包含 `stabilize-flow-recovery-actions` 和 `stabilize-version-runtime-sync` 两个后续 OpenSpec（开放规格）脚手架。它们是规划产物，不作为本变更实现验收范围。

## 关键取舍

采用 AST（语法树）扫描，而不是纯文本扫描。它仍然只用 Python（Python 语言）标准库，但可以按函数归属定位违规点，误报比字符串匹配少。

不做完整 static analysis（静态分析）框架。首版只覆盖本仓库已有测试形态、helper（辅助函数）和 fixture（测试夹具）命名；后续如果出现绕过形态，再扩展守门规则。

不删除所有 E2E（端到端测试）。真实入口仍保留，但必须证明发布形态行为，而不是重复覆盖普通分支逻辑。

## 错误处理

守门测试失败时输出违规 test function（测试函数）、文件路径、行为类别和建议处理方式：

- 分支逻辑测试改成 in-process（进程内）调用。
- 必要真实入口加入 E2E allowlist（端到端白名单）并写明理由。
- 重复 E2E（端到端测试）删除或收缩。

## 测试策略

先写守门测试，确认当前测试套件暴露真实 subprocess（子进程）、CLI（命令行）、temporary git（临时版本控制仓库）和 broad cache（大范围缓存）扫描，包括本仓库已有 helper（辅助函数）和 fixture（测试夹具）路径。

随后把 build-and-verify（构建与验证）重复分支测试迁到 in-process（进程内）入口和 fake runner（假执行器）。保留必要 E2E（端到端测试）后，增加 focused checks（聚焦检查）确认 init（初始化）和 verify（验证）各有一个真实入口。

运行时间验收记录同一命令的 before/after（前后对比），并记录 Full（完整验证）整体耗时。不引入性能测试框架。完成标准是 Full（完整验证）通过且整体时间小于等于 30 秒，并且没有新增重复真实 E2E（端到端测试）路径。

最终验证：

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py
python -m pytest -q tests/test_test_runtime_boundaries.py
python .build-and-verify/runtime/build_and_verify.py verify --project "D:\My Project\my-agent-skills"
python .build-and-verify/runtime/build_and_verify.py verify --project "D:\My Project\my-agent-skills" --full
```

## Spec Patch

已回写 OpenSpec（开放规格）design/spec/tasks（设计/规格/任务）：统一 Python AST（Python 语法树）扫描，明确 helper（辅助函数）/ fixture（测试夹具）边界，明确 E2E allowlist（端到端白名单）身份格式，加入 full verification（完整验证）和 before/after runtime（前后运行时间）记录。
