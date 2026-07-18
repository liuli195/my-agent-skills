# Brainstorm Summary

- Change: simplify-pr-flow-review-gate
- Date: 2026-06-30

## 确认的技术方案

删除 PR Flow（拉取请求流程）的 `local`（本地）和 `dual`（双重）review gate（审查门禁）运行分支，只保留 `github`（GitHub 审查）和 `skip`（跳过）。

## 关键取舍与风险

不修复本地 evidence（证据）路径，因为当前需求是保留可用门禁并删除坏分支。已使用 `local`（本地）或 `dual`（双重）的仓库需要迁移到 `github`（GitHub 审查）或 `skip`（跳过）。

## 测试策略

覆盖 validate（校验）接受/拒绝模式、complete（收尾）门禁行为、init（初始化）问答文档派生规则。

## Spec Patch

已创建 delta spec（增量规格），要求只支持 `github`（GitHub 审查）和 `skip`（跳过），并删除 cross-agent-review（跨代理审查）为 PR Flow（拉取请求流程）生成本地 evidence（证据）的要求。
