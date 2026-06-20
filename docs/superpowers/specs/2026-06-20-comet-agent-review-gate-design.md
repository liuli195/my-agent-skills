---
comet_change: add-comet-agent-review-gate
role: technical-design
canonical_spec: openspec
---

# Comet Agent Review Gate Design

## 目标

本变更把三个既有能力接到同一个流程边界：

- Comet build 完成、进入 verify 前的稳定命令边界。
- Agent Guard Global Command Guard（全局命令守卫点）。
- cross-agent-review（跨代理审查）生成的 `review-pass.json`。

最终效果是：当用户级全局守卫启用后，主 agent 执行 `comet-guard.sh <change> build --apply` 前必须先满足跨 agent review 通过证据。Comet 自身仍保持 `open -> design -> build -> verify -> archive`，不新增 phase，不新增 wrapper。

## 边界

必须保持三个插件边界清晰：

- Comet 只负责 phase、handoff、build/verify/archive 流程，不负责审查逻辑。
- cross-agent-review 只负责独立审查，默认输出仍是 `.local/cross-agent-review/<change>/<head_ref>/`，不推进 Comet phase。
- Agent Guard 只负责命令前置守卫和证据校验，不派发 reviewer agent。

本变更优先用配置解决。实现阶段先检查 Global Command Guard 是否已经能通过 `artifact` / `artifact_id` 引用 `artifacts.yaml`。如果不能，必须先停下来说明原因、影响面和最小修改点，再进入 runtime 修改。

## 守卫点

主拦截点固定为 build 阶段收尾命令：

```text
comet-guard.sh <change> build --apply
```

这个命令在 phase 从 build 进入 verify 之前执行，符合“进入 verify 前拦截”。`comet-guard.sh <change> verify --apply` 属于 verify 完成后的状态推进，不能作为主拦截点。

命令匹配必须覆盖三类形态：

- 直接脚本调用：`comet-guard.sh <change> build --apply`
- 路径脚本调用：`<path>/comet-guard.sh <change> build --apply`
- 环境变量调用：`"$COMET_BASH" "$COMET_GUARD" <change> build --apply`

匹配结果至少要捕获 `change`。`head_ref` 不从命令捕获，统一使用当前 Git HEAD。

## 配置模型

Comet review gate 使用用户级 Guard Profile：

```text
~/.agents/guards/<profile_id>/
  global-command-guards.yaml
  artifacts.yaml
```

`global-command-guards.yaml` 声明命令守卫，`artifacts.yaml` 注册外部产物：

```yaml
artifacts:
  - id: cross_agent_review_pass
    type: json
    owner: external
    path: .local/cross-agent-review/{change}/{git_head}/review-pass.json
    reuse_policy: deny
```

Global Command Guard 通过 `artifact` 或 `artifact_id` 引用该产物，并使用 JSON predicate 校验：

- `status == pass`
- `change == {change}`
- `head_ref == {git_head}`
- `blocking_findings == 0`
- `report` 存在
- `report_hash` 存在

即使 profile 位于用户级目录，项目命令的相对 artifact path 也按当前项目根目录解析。不得解析到用户 profile 目录，也不得要求复制到 `.local/guard/evidence`。

## Runtime 语义

Global Command Guard evidence evaluation 需要支持两种来源：

1. 新模型：`artifact` / `artifact_id` 引用 `artifacts.yaml`。
2. 旧模型：legacy `evidence.path`，只为既有配置兼容。

Comet review gate 必须使用新模型。旧模型不得用于该 gate。

artifact path 模板支持：

- 命令捕获值，例如 `{change}`
- 运行时上下文，例如 `{git_head}`、`{source_scope}`、`{profile_id}`、`{guard_id}`、`{effective_guard_id}`、`{runtime_scope}`

该路径不能强制依赖 Session Focus 专用字段，例如 `{instance_id}` 或 `{state_version}`。

## Agent 行为边界

当 Global Command Guard deny `build --apply` 时，Agent Guard 只负责返回结构化拒绝结果。deny 说明缺少或不满足通过证据，不代表 Agent Guard 拥有后续 review flow（审查流程）。`reason`、`next`、`suggestion` 这类场景化提示可以由 Guard Profile 配置，Runtime 只按通用机制透传或渲染。

deny 输出应包含：

- `reason`
- `next`
- `suggestion`
- captures（捕获值）
- failing guards（失败守卫）
- artifact / evidence（产物 / 证据）失败详情

后续如何执行 build readiness check、如何准备 cross-agent-review 输入、如何检查 clean worktree、如何运行 reviewer agent、如何生成 `review-pass.json`，属于调用方和 `cross-agent-review` Skill 的契约。Agent Guard 不实现、不派发、不复制这些流程。

## Agent Guard 文档设计

Agent Guard skill 入口和共享参考文档必须补 Global Command Guard，不得只依赖 Runtime README。

文档按 agent 使用场景组织：

- `$agent-guard`：识别全局命令守卫意图并路由。
- `$agent-guard-install`：生成用户级 profile 草案，包含 `global-command-guards.yaml` 和 `artifacts.yaml`。
- `$agent-guard-init`：初始化或启用已校验 profile。
- `$agent-guard-update`：同步和维护已初始化 profile。
- `$agent-guard-run`：解释 PreToolUse deny 的通用字段和排障入口，不承载被守卫业务流程的执行顺序。
- shared references/templates：放模板字段、排障矩阵和完整示例。

写法标准：

- 渐进式披露：入口只放当前场景立即需要的步骤和下一跳。
- 按 agent 使用场景组织，不按 runtime 文件或实现函数组织。
- 明确禁止项：不新增 wrapper、不改 cross-agent-review 输出、不复制 pass marker、不用 `verify --apply` 做主拦截点、不在 Agent Guard 中实现 cross-agent-review 内部流程。
- 语言简洁高效：短句、可执行步骤，避免重复背景。

## 错误处理

缺少 `review-pass.json`：

- deny build completion。
- 输出缺失 artifact、change、head ref、失败原因和 profile 声明的下一步提示。

`head_ref` 过期：

- deny build completion。
- 输出 head mismatch 失败详情；重新运行 cross-agent-review 的具体步骤由 cross-agent-review Skill 或调用方处理。

review 有 CRITICAL 或 IMPORTANT finding：

- cross-agent-review 不生成 `review-pass.json`。
- build completion 继续被拒绝。
- 调用方按 Guard Profile deny 提示和 cross-agent-review 自身规则处理后续动作。

artifact 引用无效：

- validator 报告未知 artifact id。
- runtime deny，并在失败详情中包含缺失 artifact id。

## 测试策略

校验器测试：

- `global-command-guards.yaml` 引用已注册 artifact 时通过。
- 引用未知 artifact 时失败。
- 命令模式覆盖直接、路径、环境变量三类调用。

Runtime 测试：

- 从用户级 profile 读取全局守卫。
- 对项目命令按项目根解析 `.local/cross-agent-review/{change}/{git_head}/review-pass.json`。
- 支持 `{change}` 和 `{git_head}` 模板渲染。
- 不要求 `{instance_id}` 或 `{state_version}`。
- missing pass marker、stale head、JSON predicate failure 均 deny。
- valid pass marker allow。
- legacy `evidence.path` 仍兼容，但 Comet gate 样例不使用它。

边界测试：

- Agent Guard deny 输出包含通用字段和 artifact/evidence 失败详情。
- `reason`、`next` 和 `suggestion` 可由 Guard Profile 场景化配置提供。
- review fail 对 Agent Guard 表现为没有有效 pass marker 或 JSON predicate 失败。
- review pass 对 Agent Guard 表现为 `review-pass.json` 校验通过并允许 build `--apply` 继续。
- Agent Guard 不运行 cross-agent-review，不准备其输入，不推进 Comet phase。

文档测试：

- Agent Guard skill entrypoints 提到 Global Command Guard。
- 入口文档按 install/init/update/run/troubleshoot 场景组织。
- 文档列出禁止项。
- 模板索引暴露 `global-command-guards.yaml` 与 `artifacts.yaml` 配合方式。
