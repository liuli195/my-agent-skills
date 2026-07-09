# Brainstorm Summary

- Change: fix-flow-recovery-and-authorization-boundaries
- Date: 2026-07-09

## 确认的技术方案

采用最小方案：PR Flow（拉取请求流程）复用现有恢复动作表，补齐 PR（拉取请求）创建后查询失败的可恢复路径；Release Flow（发布流程）只增加 preflight（发布前检查）错误汇总输出，不推断版本号；远端治理配置和 authorization phrase（授权短语）只在 Skill（技能）入口增加禁止句。

## 关键取舍与风险

- 不新增依赖、不新增 GitHub connector fallback（连接器回退）、不新增远端配置写入能力。
- `gh_pr_view_transient_failed`（临时查看失败）复用于创建后查询短暂失败，仅限 PR（拉取请求）已成功创建后的上下文。
- Release Flow（发布流程）不替用户和 agent（代理）选择版本，只报告当前阻塞状态和 PR（拉取请求）路径。

## 测试策略

- PR Flow（拉取请求流程）增加失败测试覆盖创建 PR（拉取请求）后 `gh pr view`（查看拉取请求）失败。
- PR Flow（拉取请求流程）包级测试检查可恢复原因必须有恢复动作。
- Release Flow（发布流程）增加多错误汇总输出测试。
- 包级文本测试检查 Skill（技能）入口禁止规则。

## Spec Patch

已在 OpenSpec（开放规格）delta spec（增量规格）中补充 PR Flow（拉取请求流程）和 Release Flow（发布流程）验收场景。
