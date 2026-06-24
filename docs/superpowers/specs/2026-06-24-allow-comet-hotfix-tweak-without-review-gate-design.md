---
comet_change: allow-comet-hotfix-tweak-without-review-gate
role: technical-design
canonical_spec: openspec
---

# Comet Hotfix/Tweak Review Gate Bypass Design

## 目标

当前 `comet-review-gate`（Comet 审查门禁）通过用户级 Global Command Guard（全局命令守卫）拦截 `comet-guard.sh <change> build --apply`，并要求存在 cross-agent-review（跨代理审查）通过标记。

本变更保留 full workflow（完整流程）的强制审查，同时让 hotfix（热修复）和 tweak（小改）workflow（流程）不再因为缺少 cross-agent-review（跨代理审查）通过标记而阻断。

## 方案

采用声明式 `skip_when`（跳过条件）机制：

```yaml
skip_when:
  - yaml:
      path: openspec/changes/{change}/.comet.yaml
      field: workflow
      in:
        - hotfix
        - tweak
```

Runtime（运行时）在命令匹配后、读取 evidence（证据）前评估该条件。条件命中时，当前 guard（守卫）不加入匹配结果，也不检查 cross-agent-review（跨代理审查）通过标记。条件缺失、文件缺失、字段缺失或字段值未命中时，继续走原有 evidence（证据）检查。

这个设计保持 Agent Guard（代理守卫）Runtime（运行时）通用：它只按配置读取 YAML（配置文件）字段，不内置 Comet（彗星流程）业务判断。

## 边界

`skip_when`（跳过条件）只负责“是否跳过当前全局命令守卫”。它不推进 Comet（彗星流程）phase（阶段），不修改 `.comet.yaml`（Comet 状态文件），不生成或删除 cross-agent-review（跨代理审查）产物。

路径必须复用现有相对路径解析，按当前 runtime scope（运行时作用域）解析到项目根或用户运行态根，避免读取边界外文件。

## 校验器

Guard Profile validator（守卫画像校验器）需要校验：

- `skip_when`（跳过条件）必须是 list（列表）。
- 每个 YAML（配置文件）条件必须包含非空 `path`、`field` 和 `in`。
- `path` 模板字段必须来自命令捕获或内置上下文值。

这样配置拼写错误会在初始化或同步前暴露，而不是在运行时静默失效。

## 测试策略

- Runtime（运行时）测试：`workflow: tweak` 命中 `skip_when`（跳过条件）时放行。
- 模板测试：full workflow（完整流程）缺少 pass marker（通过标记）仍拒绝。
- 模板测试：hotfix/tweak（热修复/小改）workflow（流程）缺少 pass marker（通过标记）放行。
- Validator（校验器）测试：合法 `skip_when`（跳过条件）配置通过。
- 用户级 Guard Profile（守卫画像）校验通过。
- 完整 pytest（测试）和 OpenSpec（开放规格）严格校验通过。

## 风险

主要风险是 `skip_when`（跳过条件）被误用于绕过关键守卫。当前设计把跳过条件留在 Guard Profile（守卫画像）配置层，由 profile owner（画像维护者）显式声明，并通过 delta spec（增量规格）限制本次内置模板只跳过 hotfix/tweak（热修复/小改）workflow（流程）。
