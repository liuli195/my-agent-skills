# Brainstorm Summary

- Change: add-comet-planning-review-gate
- Date: 2026-06-25

## 确认的技术方案

删除 Agent Guard Plugin（代理守卫插件）内置 `comet-review-gate`（comet 审查门禁）模板，移除 `built-in-comet-review-gate`（内置 comet 审查门禁）来源白名单。Comet（流程）相关 Global Command Guard（全局命令守卫点）配置改由外部用户级或目标环境 Guard Profile（守卫画像）表达。

新增双轨 evidence（证据）模型：

- guard-defined evidence（守卫定义证据）：原流程没有可检查产物时，使用 Agent Guard（代理守卫）默认目录 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`，由主 agent（代理）写入，Runtime（运行时）校验。
- external artifact（外部产物）：原流程已有稳定产物时，Agent Guard（代理守卫）只在 `artifacts.yaml`（产物注册文件）登记原路径并校验，不搬运、不复制、不改目录。

本次 `planning_review_pass`（规划审查通过标记）使用 guard-defined evidence（守卫定义证据）；`cross_agent_review_pass`（跨代理审查通过标记）继续使用 external artifact（外部产物）原路径。

## 候选方案

1. 已采用：删除 Agent Guard Plugin（代理守卫插件）内置 `comet-review-gate`（comet 审查门禁）模板，移除 `built-in-comet-review-gate`（内置 comet 审查门禁）来源白名单，运行时测试用临时用户级 Guard Profile（守卫画像）夹具覆盖 planning-review（规划审查）门禁。
2. 已否决：删除插件发布资产，但在仓库文档或测试资源中保留示例配置。风险是仍可能形成第二份配置真相。
3. 已否决：同时修改用户级 `~/.agents/guards/comet-review-gate` 配置。风险是越过本仓库边界，需要单独授权，且不属于插件去耦合本身。

## 关键取舍与风险

- 删除插件内模板可以消除 Agent Guard Plugin（代理守卫插件）与 Comet（流程）业务配置耦合。
- 测试仍需要覆盖外部配置路径，因此使用临时用户级 Guard Profile（守卫画像）夹具，而不是读取插件模板。
- 不触碰真实用户级配置，除非用户另行明确授权。
- guard-defined evidence（守卫定义证据）只适用于原流程没有产物的情况；已有产物如 cross-agent-review（跨代理审查）必须保留原路径。

## 测试策略

- 包验证测试确认插件不再要求或发布 `comet-review-gate`（comet 审查门禁）模板。
- validator（校验器）测试确认 `built-in-comet-review-gate`（内置 comet 审查门禁）来源不再接受。
- runtime（运行时）测试用临时用户级 Guard Profile（守卫画像）覆盖 `design --apply` 缺失、过期、通过三种 planning-review（规划审查）标记。
- evidence（证据）路径测试确认 `planning_review_pass`（规划审查通过标记）使用 `.local/guard/evidence`，`cross_agent_review_pass`（跨代理审查通过标记）继续登记原路径。

## Spec Patch

已补 `agent-guard-core`（代理守卫核心）、`agent-guard-plugin-runtime`（代理守卫运行时）和 `comet-agent-review-gate`（comet 审查门禁）delta spec（规格增量）。
