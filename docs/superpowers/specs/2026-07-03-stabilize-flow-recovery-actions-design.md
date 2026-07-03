---
comet_change: stabilize-flow-recovery-actions
role: technical-design
canonical_spec: openspec
archived-with: 2026-07-03-stabilize-flow-recovery-actions
status: final
---

# Stabilize Flow Recovery Actions Design

## Context

PR Flow（拉取请求流程）已经有局部恢复路径，但恢复动作分散在不同出口。`gh`（GitHub 命令行）鉴权失败、只读 PR（拉取请求）查询临时失败、checks（检查）等待、ruleset（规则集）阻塞和无效 `--fixes None`（修复问题编号为空）都应该告诉用户下一步怎么恢复，而不是落到普通 `EXCEPTION_REQUIRED`（需要人工处理）。

Release Flow（发布流程）preflight（发布预检）已经能发现版本、manifest（清单）和远端发布冲突，但输出只列错误，缺少有序下一步。

## Confirmed Design

采用最小补全方案：

- PR Flow（拉取请求流程）复用现有 `stop_state`（停止状态）和错误详情字典，只在已知可恢复原因上补 `nextAction`（下一步动作）或 `nextCommand`（下一条命令）。
- `gh pr view`（查看拉取请求）临时失败继续使用现有 `gh_pr_view_transient_failed`（临时查看失败）和 retry（重试）证据，并保留重跑同一 PR Flow（拉取请求流程）命令。
- checks（检查）等待和 ruleset（规则集）阻塞只补恢复动作，不改变等待或合并判定。
- `--fixes None`（修复问题编号为空）继续在 PR body（拉取请求正文）生成前失败，并提示没有 issue（问题单）时删除 `--fixes`（修复问题编号）。
- Release Flow（发布流程）只在 preflight（发布预检）输出层把本 change（变更）列出的三类已知错误翻译为 `nextAction`（下一步动作）；`preflight_errors`（预检错误）仍只负责检查。
- 仓库级测试检查已知可恢复 stop state（停止状态）必须带 `nextAction`（下一步动作）或 `nextCommand`（下一条命令）。

## Non-Goals

- 不新增状态机。
- 不新增依赖。
- 不改变 PR（拉取请求）创建、合并、同步或发布权限。
- 不自动修复 manifest（清单）或重新发布。

## Trade-offs

小型映射表比统一错误框架更少改动，也更符合当前脚本结构。代价是新增可恢复 reason（原因）时需要同步补恢复动作；仓库级测试负责兜底。

Release Flow（发布流程）只在输出层补提示，避免把用户指导语混入 preflight（发布预检）检查逻辑。

## Test Strategy

复用现有 Python（Python 语言）CLI（命令行）测试，不新增测试框架：

- PR Flow（拉取请求流程）测试覆盖 GitHub（代码托管平台）鉴权失败、临时 PR（拉取请求）查询失败、checks（检查）等待、ruleset（规则集）阻塞和无效 `--fixes None`（修复问题编号为空）。
- Release Flow（发布流程）测试覆盖 sourceRef（源引用）缺版本提升、manifest（清单）版本不匹配和 release already exists（发布已存在）。
- 仓库级检查覆盖已知可恢复原因不能只输出普通 `EXCEPTION_REQUIRED`（需要人工处理），且必须带恢复动作。
- 端到端回归从用户入口覆盖 PR Flow（拉取请求流程）恢复输出，并覆盖 Release Flow（发布流程）preflight（发布预检）和 publish dry-run（发布试运行）发布形态。

## Spec Patch

补充 GitHub（代码托管平台）鉴权失败的稳定 reason（原因）为 `gh_auth_required`。
