## Why

PR Flow（拉取请求流程）当前 `complete`（收尾）创建 PR（拉取请求）时依赖 `gh pr create --fill`，没有消费 `.pr-flow/pr-template.md`（拉取请求正文模板），也不会写入 GitHub（代码托管平台）closing references（关闭引用）。这导致 PR（拉取请求）合并发布后缺少可审计正文，相关 issue（问题单）也不会自动关闭。

## What Changes

- `complete`（收尾）和 `tweak`（小改）统一使用同一套 PR body（拉取请求正文）逻辑。
- PR body template（拉取请求正文模板）收敛为 `Summary`、`Scope`、`Closing References` 三节，并保留注释形式的说明和填写指南。
- `complete`（收尾）和 `tweak`（小改）都要求调用方显式提供 `--summary` 和 `--scope`，可选重复提供 `--fixes <number>`。
- `--fixes` 统一渲染为 `Fixes #<number>`；未提供时 `Closing References` 写 `None`。
- 缺少正文必填参数、模板缺失、模板章节缺失或已有 PR（拉取请求）正文需要人工处理时，流程输出现有 stop state（停止状态）并停止。
- `diagnose`（诊断）输出兼容新的 PR body（拉取请求正文）要求，给出可执行的下一步命令提示。
- 不自动猜 issue（问题单）编号，不覆盖已有人工正文，不新增依赖。

## Capabilities

### New Capabilities

### Modified Capabilities

- `pr-flow-plugin`: 修改 complete（收尾）、tweak（小改）、diagnose（诊断）和 init（初始化）对 PR body（拉取请求正文）模板、必填正文参数和 closing references（关闭引用）的要求。

## Impact

- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- `plugins/pr-flow/skills/pr-flow-complete/SKILL.md`
- `plugins/pr-flow/skills/pr-flow-tweak/SKILL.md`
- `plugins/pr-flow/skills/pr-flow-init/` 相关说明
- `openspec/specs/pr-flow-plugin/spec.md` 的 delta spec（规格增量）
- `tests/test_pr_flow_cli.py`
