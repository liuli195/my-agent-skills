---
comet_change: add-comet-planning-review-gate
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-25-add-comet-planning-review-gate
status: final
---

# Comet Planning Review Gate Design

## Context

现有 Comet review gate（comet 审查门禁）围绕 build（构建）完成进入 verify（验证）的边界，通过 Agent Guard Global Command Guard（全局命令守卫点）校验 cross-agent-review（跨代理审查）的 `review-pass.json`。

本变更增加更早的 design（设计）进入 build（构建）边界：在主 agent（代理）执行 `comet-guard.sh <change> design --apply` 前，必须已有 planning-review（规划审查）的通过证据。这个门禁用于防止 proposal（提案）、design（设计）、tasks（任务）和 delta spec（规格增量）存在冲突、遗漏或不可验证计划时过早进入实现。

同时，Agent Guard Plugin（代理守卫插件）不再发布 Comet-specific（Comet 专用）Guard Profile（守卫画像）模板。Comet（流程）业务配置应属于用户级或目标环境自己的 Guard Profile（守卫画像），插件只保留通用 Runtime（运行时）能力。

## Goals

- 删除插件内置 `comet-review-gate`（comet 审查门禁）模板和镜像模板。
- 移除 `built-in-comet-review-gate`（内置 comet 审查门禁）来源白名单。
- 定义双轨 evidence（证据）模型。
- 为 `planning_review_pass`（规划审查通过标记）使用 guard-defined evidence（守卫定义证据）默认目录。
- 保持 `cross_agent_review_pass`（跨代理审查通过标记）作为 external artifact（外部产物）登记原路径。
- 用临时用户级 Guard Profile（守卫画像）测试 design -> build planning-review（规划审查）门禁。

## Non-Goals

- 只有在用户明确确认时，才更新真实用户目录 `~/.agents/guards/comet-review-gate`。
- 不新增 Comet phase（流程阶段）。
- 不新增 wrapper（包装命令）。
- 不让 Agent Guard（代理守卫）执行 planning-review（规划审查）。
- 不迁移 cross-agent-review（跨代理审查）已有输出目录。

## Decisions

### 删除插件内 Comet 模板

删除以下目录：

```text
plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate
plugins/agent-guard/assets/templates/guard-profile/comet-review-gate
```

相关包验证、模板镜像测试和文档引用必须同步删除或改写。Agent Guard Plugin（代理守卫插件）不再携带 Comet（流程）业务配置副本。

### 双轨 evidence 模型

guard-defined evidence（守卫定义证据）适用于原流程没有可检查产物的场景。Agent Guard（代理守卫）定义默认路径：

```text
.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json
```

external artifact（外部产物）适用于原流程已有稳定产物的场景。Agent Guard（代理守卫）只在 `artifacts.yaml`（产物注册文件）登记原始路径并校验，不复制、不搬运、不改目录。

### planning-review pass marker

`planning_review_pass`（规划审查通过标记）属于 guard-defined evidence（守卫定义证据）。本场景路径为：

```text
.local/guard/evidence/comet-review-gate/planning_review_pass/{subject_id}/{git_head_short}/pass.json
```

这里 `{subject_id}` 在 Comet（流程）场景中取当前 change（变更）编号。

写入者是当前执行 Comet（流程）的主 agent（代理）。写入前必须完成 planning-review（规划审查），且没有 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）。满足这些条件时，主 agent（代理）MUST 写入 `pass.json`；存在阻断项时不得写入或复用旧 marker（标记）。planning-review（规划审查）Skill（技能）本身不写文件；Agent Guard Runtime（代理守卫运行时）也不生成 marker（标记）。

JSON（数据对象）字段契约：

```json
{
  "schema_version": "guard-evidence/v1",
  "status": "pass",
  "producer": "planning-review",
  "profile_id": "comet-review-gate",
  "artifact_id": "planning_review_pass",
  "subject_type": "comet-change",
  "subject_id": "<change>",
  "head_ref": "<full git head>",
  "head_ref_short": "<12-char head>",
  "blocking_findings": 0,
  "scope": ["proposal.md", "design.md", "tasks.md", "specs/**/*.md"],
  "report_hash": "<sha256>",
  "created_at": "<iso timestamp>"
}
```

### cross-agent-review stays external

`cross_agent_review_pass`（跨代理审查通过标记）已有原流程产物：

```text
.local/cross-agent-review/{change}/{git_head_short}/review-pass.json
```

它继续作为 external artifact（外部产物）登记并校验，不迁移到 `.local/guard/evidence`。

## Error Handling

- 缺少 `planning_review_pass`：deny（拒绝）`design --apply`，返回缺失 artifact（产物）详情。
- `head_ref` 不匹配当前 HEAD（代码版本）：deny（拒绝），提示重新运行 planning-review（规划审查）。
- planning-review（规划审查）存在阻断项：主 agent（代理）不得写入或复用 pass marker（通过标记）。
- `pass.json` 字段缺失或不匹配当前上下文：deny（拒绝），返回失败字段详情。
- 外部产物已有路径：不得复制到 `.local/guard/evidence`，否则视为边界错误。

## Test Strategy

- package（插件包）测试：确认不再要求或发布 `comet-review-gate`（comet 审查门禁）模板。
- validator（校验器）测试：确认 `built-in-comet-review-gate`（内置 comet 审查门禁）被拒绝。
- runtime（运行时）测试：临时用户级 Guard Profile（守卫画像）覆盖 `design --apply` 的缺失、过期、通过三种 marker（标记）。
- invalid marker（无效标记）测试：错误 `status`、错误 `producer`、错误 `artifact_id`、错误 `subject_id`、`blocking_findings` 大于 0、缺少 `scope`、缺少 `report_hash` 时必须拒绝。
- evidence（证据）路径测试：`planning_review_pass` 使用 `.local/guard/evidence`，`cross_agent_review_pass` 保持 `.local/cross-agent-review` 原路径。
- user config（用户配置）验证：用户确认后校验真实用户级 `comet-review-gate` Guard Profile（守卫画像），并通过真实 Hook（钩子）路径确认 design（设计）出口命令会被拦截。
