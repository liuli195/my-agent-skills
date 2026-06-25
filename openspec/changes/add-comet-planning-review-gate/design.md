## Context

现有 `comet-agent-review-gate`（comet 审查门禁）已经通过 Agent Guard Global Command Guard（全局命令守卫点）保护 build（构建）完成进入 verify（验证）的边界，并校验 cross-agent-review（跨代理审查）生成的 `review-pass.json`。

这次变更补另一个更早的边界：design（设计）完成进入 build（构建）前，必须先通过 planning-review（规划审查）。这个边界适合检查 proposal（提案）、design（设计）、tasks（任务）和 delta spec（规格增量）之间是否有冲突、遗漏、范围漂移或不可验证计划。

## Goals / Non-Goals

**Goals:**

- 在 `comet-guard.sh <change> design --apply` 前增加 Global Command Guard（全局命令守卫点）规则。
- 通过 `artifacts.yaml`（产物注册文件）注册 `planning_review_pass`（规划审查通过标记）。
- 为 `planning_review_pass`（规划审查通过标记）使用 Agent Guard（代理守卫）定义的 guard-defined evidence（守卫定义证据）默认目录。
- 保持 cross-agent-review（跨代理审查）这类已有产物使用原始路径，只登记不搬运。
- 删除 Agent Guard Plugin（代理守卫插件）内置的 Comet review gate（comet 审查门禁）Guard Profile（守卫画像）模板，避免插件携带业务配置副本。
- 让外部用户级 Guard Profile（守卫画像）配置 deny（拒绝）提示，引导调用方运行 planning-review（规划审查）并生成通过标记。
- 保持 planning-review（规划审查）自身只读，不让 Agent Guard（代理守卫）代替它执行审查。

**Non-Goals:**

- 不新增 Comet phase（阶段）。
- 不新增 wrapper（包装命令）。
- 不改 planning-review（规划审查）Skill（技能）的只读审查规则。
- 不把 planning-review（规划审查）流程硬编码进 Agent Guard Runtime（代理守卫运行时）。
- 不在 Agent Guard Plugin（代理守卫插件）中继续保留 Comet（流程）业务 Guard Profile（守卫画像）模板。

## Decisions

### Decision 1: 删除插件内 Comet review gate 模板

删除 `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate` 和 `plugins/agent-guard/assets/templates/guard-profile/comet-review-gate`，并移除插件包验证中对这两套模板的要求。

原因：这些文件把 Comet（流程）业务配置作为 Agent Guard Plugin（代理守卫插件）内置资产发布，形成不必要耦合。Agent Guard（代理守卫）应提供通用 Global Command Guard（全局命令守卫点）机制，Comet（流程）相关配置应保留在用户级或目标环境自己的 Guard Profile（守卫画像）中。

备选方案：继续扩展插件模板。缺点是进一步加深插件与 Comet（流程）的耦合，和“实际配置不需要在插件中保留一套”的目标冲突。

### Decision 2: planning-review 通过结果用独立 artifact

外部用户级 Guard Profile（守卫画像）新增 `planning_review_pass`（规划审查通过标记）产物。该产物属于 guard-defined evidence（守卫定义证据）：原流程没有稳定可检查产物，需要 Agent Guard（代理守卫）定义默认 evidence（证据）目录，并由主 agent（代理）在 planning-review（规划审查）放行后写入。

默认路径为：

```text
.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json
```

本场景渲染为：

```text
.local/guard/evidence/comet-review-gate/planning_review_pass/{subject_id}/{git_head_short}/pass.json
```

这里 `{subject_id}` 在 Comet（流程）场景中取当前 change（变更）编号。

通过标记至少包含：

- `schema_version: guard-evidence/v1`
- `status: pass`
- `producer: planning-review`
- `profile_id`
- `artifact_id`
- `subject_type: comet-change`
- `subject_id`
- `head_ref`
- `head_ref_short`
- `blocking_findings: 0`
- `scope`
- `report_hash`
- `created_at`

原因：Global Command Guard（全局命令守卫点）已有 artifact（产物）引用和 JSON predicate（JSON 谓词）能力，外部配置即可复用；同时能绑定当前 change（变更）和当前 Git HEAD（代码版本），避免使用过期审查结论。

写入者是当前执行 Comet（流程）的主 agent（代理）。写入前必须完成 planning-review（规划审查），且没有 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）。满足这些条件时，主 agent（代理）MUST 写入 `pass.json`；存在阻断项时不得写入或复用旧 marker（标记）。planning-review（规划审查）Skill（技能）本身不写文件；Agent Guard Runtime（代理守卫运行时）也不生成 marker（标记）。

### Decision 3: 已有外部产物只登记原路径

cross-agent-review（跨代理审查）已经生成稳定产物：

```text
.local/cross-agent-review/{change}/{git_head_short}/review-pass.json
```

这类产物属于 external artifact（外部产物）。Agent Guard（代理守卫）只在 `artifacts.yaml`（产物注册文件）中登记原路径并校验，不复制、不搬运、不改目录。

### Decision 4: Agent Guard 只校验证据，不执行 planning-review

门禁拒绝时只返回 `reason`、`next`、`suggestion` 和失败 artifact（产物）详情。调用方看到拒绝后运行 planning-review（规划审查），并在审查放行后生成 pass marker（通过标记），再重试 design guard（设计守卫）命令。

原因：planning-review（规划审查）Skill（技能）要求只读，不运行脚本、不修改文件、不推进状态。Agent Guard（代理守卫）如果主动执行它，会破坏现有边界。

## Risks / Trade-offs

- [Risk] 没有现成 pass marker（通过标记）生成器时，流程可能停在门禁提示上。Mitigation: 在规格和用户级配置说明中明确 marker（标记）字段、路径和生成责任，测试用例覆盖有效与缺失 marker。
- [Risk] design（设计）阶段的 HEAD（代码版本）变化会让旧 marker（标记）过期。Mitigation: 使用 `{git_head_short}` 作为路径，并校验 marker 内的完整 `head_ref`。
- [Risk] 删除内置模板后，旧测试和文档仍可能要求插件包包含 Comet（流程）配置。Mitigation: 更新包验证、模板镜像测试和 Agent Guard（代理守卫）参考文档，明确 Comet（流程）配置不属于插件内置资产。
- [Risk] guard-defined evidence（守卫定义证据）和 external artifact（外部产物）边界不清会导致产物被重复复制。Mitigation: 规格中明确只有原流程没有产物时才使用 `.local/guard/evidence`，已有产物只登记原路径。

## Migration Plan

1. 删除插件内置 Comet review gate（comet 审查门禁）模板和镜像模板。
2. 移除插件包验证、模板镜像测试和 validator（校验器）中对 `built-in-comet-review-gate`（内置 comet 审查门禁）来源的依赖。
3. 增加 runtime（运行时）测试，用临时用户级 Guard Profile（守卫画像）覆盖 guard-defined `planning_review_pass`（规划审查通过标记）的缺失、过期和通过。
4. 更新 Agent Guard（代理守卫）文档，说明双轨 evidence（证据）模型和业务 Guard Profile（守卫画像）配置属于用户级或目标环境，不随插件发布。

## Open Questions

无。当前变更只定义和校验 pass marker（通过标记）契约，不改 planning-review（规划审查）Skill（技能）的内部流程。
