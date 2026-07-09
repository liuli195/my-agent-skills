---
comet_change: fix-flow-recovery-and-authorization-boundaries
role: technical-design
canonical_spec: openspec
---

# Fix Flow Recovery And Authorization Boundaries Design

## Context

PR Flow（拉取请求流程）和 Release Flow（发布流程）已有部分恢复输出，但仍有两个缺口：PR（拉取请求）创建后查询短暂失败会暴露成 `EXCEPTION_REQUIRED`（需要异常处理）；Release Flow（发布流程）preflight（发布前检查）多错误同时出现时只逐条提示，缺少汇总路径。

另一个缺口是授权边界：GitHub（代码托管平台）远端治理配置和 authorization phrase（授权短语）的禁止规则需要直接出现在 Skill（技能）入口，避免 agent（代理）从历史上下文或 memory（记忆）里复用授权。

## Decisions

1. PR Flow（拉取请求流程）继续使用现有 `RECOVERABLE_NEXT_ACTIONS`（可恢复动作表）和轻量状态映射。当前必须登记的可恢复原因是 `gh_auth_required`（GitHub 授权缺失）、`gh_pr_view_transient_failed`（临时查看失败）、`checks_pending`（检查等待中）、`ruleset_merge_blocking`（规则集阻塞合并）、`checks_or_review_blocking`（检查或审查阻塞）、`invalid_fixes`（修复参数无效）、`pr_missing`（缺少拉取请求）和 `missing_upstream`（缺少上游分支）。测试必须遍历这个清单，避免遗漏状态或恢复动作。
2. `gh pr create`（创建拉取请求）成功后，如果随后的 `gh pr view`（查看拉取请求）失败，转换为 `DISPATCH_REQUIRED`（需要外部进展）和 `gh_pr_view_transient_failed`（临时查看失败），记录 `transientCategory: post_create_view`（创建后查看），并给出重跑当前 `complete`（收尾）的 `nextCommand`（下一步命令）。
3. Release Flow（发布流程）增加输出层汇总函数。多错误且全部属于本轮跟踪的 release（发布）、manifest（清单）、source ref（源引用）和 plugin（插件）版本问题时，保留每条 `error:`（错误）明细，但只输出一条汇总 `nextAction:`（下一步动作）。混入未跟踪错误时继续保留逐条 nextAction（下一步动作）。汇总描述当前阻塞状态和处理路径：release（发布）冲突由用户和 agent（代理）确定 release version（发布版本）后重跑 preflight（发布前检查）；manifest（清单）、source ref（源引用）和 plugin（插件）版本问题走 PR（拉取请求）路径。脚本不推断最新版本或下一版本。
4. 远端治理和 authorization phrase（授权短语）只加入口禁止句，并用包级测试固定。

## Tests

- `tests/test_pr_flow_cli.py` 覆盖 PR（拉取请求）创建后查看失败的恢复状态。
- `tests/test_pr_flow_plugin_package.py` 覆盖恢复动作矩阵和 authorization phrase（授权短语）入口边界。
- `tests/test_release_flow_cli.py` 覆盖 preflight（发布前检查）多错误汇总输出，断言底层 error（错误）仍逐条输出且只有一条汇总 nextAction（下一步动作）。
- `tests/test_release_flow_plugin_package.py` 覆盖 Release Flow（发布流程）远端治理入口边界。

## Non-Goals

- 不增加依赖。
- 不增加 GitHub API（接口）远端配置写入。
- 不让 Release Flow（发布流程）创建 PR（拉取请求）。
- 不让脚本读取 memory（记忆）或判定 authorization phrase（授权短语）来源。
