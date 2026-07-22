# Brainstorm Summary

- Change: stabilize-flow-recovery-actions
- Date: 2026-07-03

## 确认的技术方案

采用最小补全方案。PR Flow（拉取请求流程）在现有 `stop_state`（停止状态）和错误详情上补齐 `nextAction`（下一步动作）或 `nextCommand`（下一条命令）；Release Flow（发布流程）只在 preflight（发布预检）输出层把已知错误翻译为下一步提示。

## 关键取舍与风险

不新增状态机，不新增依赖，不改变 PR（拉取请求）创建、合并或发布权限。风险是漏掉新增可恢复 reason（原因），用仓库级检查兜底。

## 测试策略

复用现有 Python（Python 语言）CLI（命令行）测试；新增聚焦测试覆盖 GitHub（代码托管平台）鉴权、临时 PR（拉取请求）查询失败、检查等待、ruleset（规则集）阻塞、无效 `--fixes None`（修复问题编号为空）和 Release Flow（发布流程）preflight（发布预检）下一步输出。端到端回归从用户入口覆盖 PR Flow（拉取请求流程）恢复输出，并覆盖 Release Flow（发布流程）preflight（发布预检）和 publish dry-run（发布试运行）发布形态。

## Spec Patch

补充 GitHub（代码托管平台）鉴权失败的稳定 reason（原因）为 `gh_auth_required`；Release Flow（发布流程）范围明确收窄到本 change（变更）列出的三类 preflight（发布预检）错误。
