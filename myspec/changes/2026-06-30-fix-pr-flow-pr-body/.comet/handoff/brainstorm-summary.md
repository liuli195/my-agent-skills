# Brainstorm Summary

- Change: fix-pr-flow-pr-body
- Date: 2026-06-30

## 确认的技术方案

采用共享 helper（辅助函数）加最小参数扩展。`complete`（收尾）和 `tweak`（小改）完全复用同一套 PR body（拉取请求正文）逻辑：模板读取、必填参数校验、HTML comment（HTML 注释）剥离、closing references（关闭引用）渲染、空正文补写和非空正文不覆盖。

PR body template（拉取请求正文模板）只保留 `Summary`、`Scope`、`Closing References` 三节；模板说明和填写指南保留在 HTML comment（HTML 注释）中。`--summary` 和 `--scope` 由主 agent（主代理）显式提供，script（脚本）不推测。`--fixes` 可重复，统一渲染为 `Fixes #<number>`；未传则写 `None`。`diagnose`（诊断）输出兼容新正文参数的 `nextCommand`（下一步命令）。

新建 PR（拉取请求）必须直接使用统一生成的三节正文；即使继续用 `gh pr create --fill`（自动填充）辅助标题，也必须用生成正文替代自动正文。旧五节模板或缺少三节 requiredSections（必需章节）不做兼容转换，按 `pr_body_required`（正文必需）停止，并输出模板路径、缺失章节和可执行修复提示。已有非空人工正文加 `--fixes` 时也停止，提示人工补充 `Fixes #<number>`（关闭引用）。

## 测试策略

- `init`（初始化）：默认模板和 requiredSections（必需章节）为三节。
- `complete`（收尾）：缺正文参数时不 auto-push（自动推送）也不创建 PR（拉取请求）；新建 PR（拉取请求）必须使用生成正文；带参数时生成正文；`--fixes` 渲染关闭引用。
- `tweak`（小改）：要求同样的 `--summary`、`--scope`、`--fixes`，不再用单独模板。
- 已有 PR（拉取请求）：空正文补写；非空正文不覆盖；非空正文加 `--fixes` 时停止。
- 停止状态：缺正文参数、旧模板/缺章节、人工正文冲突都必须输出可执行 details（详情）。
- `diagnose`（诊断）：无 PR（拉取请求）时提示完整命令；已有空正文时输出 `pr_body_required`。

## Spec Patch

暂无新增 Spec Patch 候选；当前 delta spec（规格增量）已覆盖确认方案。
