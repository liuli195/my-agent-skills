---
comet_change: fix-pr-flow-pr-body
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-30-fix-pr-flow-pr-body
status: final
---

# PR Flow PR Body Design

## Context

`PR Flow`（拉取请求流程）已经在配置里声明 `defaults.pr.bodyTemplatePath`（正文模板路径）和 `requiredSections`（必需章节），`init`（初始化）也会写 `.pr-flow/pr-template.md`（拉取请求正文模板）。但 `complete`（收尾）创建 PR（拉取请求）时只调用 `gh pr create --fill`，没有使用模板，也不会写 GitHub（代码托管平台）closing references（关闭引用）。

`tweak`（小改）当前有独立正文模板，只写 tweak（小改）原因。这让 `complete`（收尾）和 `tweak`（小改）正文规则分叉，也无法统一处理 `Fixes #...`（关闭引用）。

## Goals

- `complete`（收尾）和 `tweak`（小改）共用同一套 PR body（拉取请求正文）生成、校验和写入保护。
- 默认 PR body template（拉取请求正文模板）收敛为 `Summary`、`Scope`、`Closing References` 三节。
- `--summary` 和 `--scope` 由主 agent（主代理）显式提供。
- `--fixes` 只从调用参数生成 `Fixes #<number>`；未提供时写 `None`。
- `diagnose`（诊断）输出带正文参数的可执行 `nextCommand`（下一步命令）。

## Non-Goals

- 不从提交、分支名、issue（问题单）历史或 PR（拉取请求）状态推断正文。
- 不新增依赖。
- 不引入模板变量系统。
- 不覆盖已有人工正文。
- 不改变 `hotfix`（热修复）和 `cleanup`（清理）行为。

## Design

新增一个小型共享 helper（辅助函数），由 `complete`（收尾）和 `tweak`（小改）共同调用。它负责：

- 读取并校验 `defaults.pr.bodyTemplatePath`（正文模板路径）。
- 校验 `requiredSections`（必需章节）包含 `Summary`、`Scope`、`Closing References`。
- 剥离 HTML comment（HTML 注释）和空白后判断正文是否为空。
- 使用 `--summary`、`--scope`、`--fixes` 生成最终正文。
- 保护已有非空 PR body（拉取请求正文），避免覆盖人工编辑内容。
- 为停止状态写入明确 details（详情），包括模板路径、缺失章节、PR（拉取请求）编号、冲突原因和下一步动作。

`complete`（收尾）必须在 auto-push（自动推送）之前校验正文参数和模板。新建 PR（拉取请求）时，脚本必须直接使用统一生成的正文；可以继续使用 `--fill`（自动填充）辅助标题，但必须用 `--body-file`（正文文件）覆盖自动正文。已有 PR（拉取请求）时，先读取 `body`（正文）：空正文则在 checks（检查）和 merge（合并）前补写；非空正文则不覆盖。若已有正文非空且调用方传入 `--fixes`，流程停止并提示人工补 closing references（关闭引用）。

`tweak`（小改）保留 `--reason` 作为选择 tweak path（小改路径）的理由，但不再用它生成另一套正文。它也要求 `--summary`、`--scope`，并复用同一套 `--fixes` 逻辑。

旧五节模板或旧 `requiredSections`（必需章节）不做兼容转换。已有仓库如果模板没有 `Summary`、`Scope`、`Closing References` 三节，`complete`（收尾）和 `tweak`（小改）必须按 `pr_body_required`（正文必需）停止，并在 details（详情）里给出模板路径、缺失章节和修复动作。

## CLI Contract

`complete`（收尾）示例：

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py complete --project . --summary "修复 PR Flow 创建空正文 PR" --scope "更新 complete、tweak、diagnose 和测试" --fixes 98
```

`tweak`（小改）示例：

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tweak --project . --reason "small docs polish" --summary "更新 PR Flow 文档措辞" --scope "只修改 PR Flow 文档" --fixes 98
```

缺少 `--summary` 或 `--scope` 时，输出 `EXCEPTION_REQUIRED`（需要人工处理）和 `reason: pr_body_required`，并在 details（详情）里给出缺失参数和可执行 `nextCommand`（下一步命令）。

## Tests

- `init`（初始化）生成三节模板和三项 `requiredSections`（必需章节）。
- `complete`（收尾）缺正文参数时不 auto-push（自动推送）也不创建 PR（拉取请求）。
- 新建 PR（拉取请求）直接使用统一生成的正文，不保留 `--fill`（自动填充）生成的正文。
- `complete`（收尾）和 `tweak`（小改）渲染同样的三节正文和 `Fixes #...`（关闭引用）。
- 已有 PR（拉取请求）空正文会补写；非空正文不会覆盖；非空正文加 `--fixes` 会停止。
- 模板缺失、缺少章节和人工正文冲突的停止详情足够明确。
- `diagnose`（诊断）无 PR（拉取请求）时提示完整命令；已有空正文时输出 `pr_body_required`。

## Risks

- 旧的裸 `complete --project .` 会停止。通过更新 `Skill`（技能）示例和 `diagnose`（诊断）输出降低误用。
- 旧五节模板会停止，而不是自动兼容。这样保持三节正文唯一规则，避免 `complete`（收尾）和 `tweak`（小改）再次分叉。
- 已有正文但缺 closing references（关闭引用）不会自动补。最小修复优先保护人工正文，提示人工处理。
