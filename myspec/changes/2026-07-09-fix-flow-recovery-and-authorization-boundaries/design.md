## Context

当前代码已有一些轻量恢复能力：PR Flow（拉取请求流程）用 `RECOVERABLE_NEXT_ACTIONS`（可恢复动作表）和 `error_status`（错误状态映射）区分部分可恢复原因；Release Flow（发布流程）用 `preflight_next_action`（发布前下一步动作）为单条错误输出提示。

缺口是两处没有收敛：PR（拉取请求）创建成功后的查询失败没有结合上下文转成可恢复状态；Release Flow（发布流程）同时出现多条 preflight（发布前检查）错误时仍逐条输出，用户需要自行串联。

## Goals / Non-Goals

**Goals:**

- 复用现有恢复动作表和状态映射，不新增复杂状态机。
- 让所有已知可恢复原因都有非 `EXCEPTION_REQUIRED`（需要异常处理）状态和恢复动作，并由同一清单测试保护。
- Release Flow（发布流程）多错误时只输出底层错误明细和一条当前状态处理路径，不推断版本号。
- 用 Skill（技能）入口禁止句约束高风险授权边界。

**Non-Goals:**

- 不新增依赖。
- 不新增 GitHub connector fallback（连接器回退）。
- 不让 Release Flow（发布流程）创建或合并 PR（拉取请求）。
- 不实现 GitHub（代码托管平台）远端治理配置写入。
- 不让脚本读取 memory（记忆）或判断 authorization phrase（授权短语）的来源。

## Decisions

- PR Flow（拉取请求流程）恢复矩阵继续使用现有恢复动作表和轻量状态映射。当前必须登记的可恢复原因是 `gh_auth_required`（GitHub 授权缺失）、`gh_pr_view_transient_failed`（临时查看失败）、`checks_pending`（检查等待中）、`ruleset_merge_blocking`（规则集阻塞合并）、`checks_or_review_blocking`（检查或审查阻塞）、`invalid_fixes`（修复参数无效）、`pr_missing`（缺少拉取请求）和 `missing_upstream`（缺少上游分支）。测试必须遍历这个清单，断言状态不是 `EXCEPTION_REQUIRED`（需要异常处理），且详情包含 `nextAction`（下一步动作）或 `nextCommand`（下一步命令）。
- PR（拉取请求）创建成功后的 `gh pr view`（查看拉取请求）失败复用 `gh_pr_view_transient_failed`（临时查看失败）和 `DISPATCH_REQUIRED`（需要外部进展），并记录 `transientCategory: post_create_view`（创建后查看）。
- Release Flow（发布流程）增加输出层汇总函数，只根据已有错误字符串生成摘要，不改变 preflight（发布前检查）的判定逻辑。多错误且全部属于 release（发布）冲突、manifest（清单）版本不匹配、source ref（源引用）未合入版本提升或 plugin（插件）需要一并提升版本时，保留每条 `error:`（错误）明细，但只输出一条汇总 `nextAction:`（下一步动作）；混入未跟踪错误时继续保留逐条 nextAction（下一步动作），避免隐藏更精确的恢复提示。release（发布）冲突的处理路径是由用户和 agent（代理）确定 release version（发布版本）后重跑 preflight（发布前检查），脚本不得推断或建议具体版本号。
- 远端治理和 authorization phrase（授权短语）边界只写在 Skill（技能）入口，并用包级文本测试防回退。

## Risks / Trade-offs

- `gh_pr_view_transient_failed`（临时查看失败）会覆盖 EOF（连接提前结束）以外的创建后查询短暂失败。缓解：只在 `gh pr create`（创建拉取请求）已经成功的上下文使用。
- Release Flow（发布流程）汇总输出仍不替用户选择版本。缓解：这是用户确认的边界，脚本只报告现状。
