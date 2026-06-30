# Brainstorm Summary

- Change: allow-comet-hotfix-tweak-without-review-gate
- Date: 2026-06-24

## 确认的技术方案

已确认采用方案 A：为 Global Command Guard（全局命令守卫）增加声明式 `skip_when`（跳过条件）。命令匹配后读取相对 YAML（配置文件）路径、字段和值列表，字段值命中时跳过该守卫的 evidence（证据）检查。`comet-review-gate`（Comet 审查门禁）通过该机制读取 `.comet.yaml`（Comet 状态文件）中的 `workflow`（流程类型），让 `hotfix`（热修复）和 `tweak`（小改）跳过 cross-agent-review（跨代理审查）要求。

## 关键取舍与风险

方案 A 保持 Runtime（运行时）通用，不把 Comet（彗星流程）业务规则硬编码进 Agent Guard（代理守卫）。方案 B 只改命令匹配，无法可靠判断 workflow（流程类型）。方案 C 写专用逻辑，短期简单但违反通用 Runtime（运行时）边界。

风险主要在配置拼写和路径解析：通过 validator（校验器）检查 `skip_when`（跳过条件）结构，并复用现有相对路径解析，避免读取项目边界外文件。

## 测试策略

- 覆盖 full（完整流程）缺少 pass marker（通过标记）仍被拒绝。
- 覆盖 hotfix/tweak（热修复/小改）缺少 pass marker（通过标记）被放行。
- 覆盖 `skip_when`（跳过条件）配置校验。
- 校验用户级 Guard Profile（守卫画像）。
- 运行完整 pytest（测试）和 OpenSpec（开放规格）严格校验。

## Spec Patch

已补充 delta spec（增量规格）：

- `agent-guard-plugin-runtime`: 声明 Global Command Guard（全局命令守卫）支持声明式跳过条件。
- `comet-agent-review-gate`: 声明 full（完整流程）继续要求 cross-agent-review（跨代理审查），hotfix/tweak（热修复/小改）不要求。
