# Brainstorm Summary

- Change: guard-test-runtime-boundaries
- Date: 2026-07-02

## 确认的技术方案

采用方案 2：新增一个仓库级测试边界守门测试，使用 Python AST（Python 语法树）扫描 `tests/` 中的 test function identity（测试函数身份），并通过一个按 file path + qualified test function（文件路径加限定测试函数）登记的 E2E（端到端测试） allowlist（白名单）放行必要真实入口。

build-and-verify（构建与验证）重复分支测试优先改用已有 `run_check`（进程内检查入口）和 runner（执行器）的 fake runner（假执行器）。真实 E2E（端到端测试）只保留能证明 packaged entrypoint（发布形态入口）可运行的 init（初始化）和 verify（验证）路径。

## 关键取舍与风险

- 取舍：用 stdlib AST（标准库语法树）而不是纯文本扫描，代码仍少，但误报更少。
- 风险：真实 E2E（端到端测试）白名单太宽会削弱边界；因此只按 test function（测试函数）登记，不按文件放行。
- 风险：扫描 helper（辅助函数）/ fixture（测试夹具）调用链可能误报；先覆盖本仓库已有 helper（辅助函数）和 fixture（测试夹具）形态，不做完整 static analysis（静态分析）框架。

## 测试策略

- 新守门测试先红后绿，覆盖 subprocess（子进程）、CLI（命令行）、temporary git（临时版本控制仓库）和 broad cache（大范围缓存）扫描边界。
- 聚焦运行 build-and-verify（构建与验证）相关测试，确认保留一个 init（初始化）真实 E2E（端到端测试）和一个 verify（验证）真实 E2E（端到端测试）。
- 记录 `python -m pytest -q tests/test_build_and_verify_plugin.py` 的 before/after runtime（前后运行时间）。
- 最后运行 fast verification（快速验证）和 full verification（完整验证）。

## Spec Patch

回写 OpenSpec（开放规格）design/spec/tasks（设计/规格/任务）：统一 Python AST（Python 语法树）扫描，明确 helper（辅助函数）/ fixture（测试夹具）边界，明确 E2E allowlist（端到端白名单）身份格式，加入 full verification（完整验证）和 before/after runtime（前后运行时间）记录。
