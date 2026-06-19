# guard_runtime

本目录发布 Agent Guard Plugin（代理守卫插件）的 Runtime code（运行时代码）。

当前实现包含 Hook Adapter（钩子适配器）、Session Observation（会话观察记录）、Session Focus Binding（会话焦点绑定）、Guard Instance（守卫实例）、状态推进、Guard Brief（守卫简报）和 Guard Injection（守卫注入）相关入口。

## Global Command Guard（全局命令守卫点）

Runtime（运行时）在 PreToolUse（工具使用前）阶段收集 Global Command Guard（全局命令守卫点）规则：

- `.agents/guards/*/global-command-guards.yaml`
- `~/.agents/guards/*/global-command-guards.yaml`

每条规则会生成 effective guard id（有效守卫 ID）：

```text
<source_scope>:<profile_id>:<guard_id>
```

其中 `source_scope` 表示规则来源范围，例如 `project` 或 `user`；`profile_id` 来自 Guard Profile（守卫画像）目录名；`guard_id` 来自 `global-command-guards.yaml` 内的规则 `id`。

一个命令可以同时匹配多个规则。匹配到的所有规则都必须通过 evidence（证据）检查；任意规则失败，Runtime 都会 deny（拒绝）该命令，并在输出中包含匹配到的守卫 ID 和失败规则信息。

项目命令的 evidence（证据）和 audit（审计）默认写入项目 `.local/guard`，即使命中的规则来自用户级 Guard Profile（守卫画像）。这样可以保证项目命令的运行态证据留在项目边界内，便于审计和复现。

Global Command Guard（全局命令守卫点）和 Session Focus Guard（会话焦点守卫）的职责不同：

- Global Command Guard 在 PreToolUse 阶段按命令文本和证据文件判断是否允许执行，未激活 Session Focus（会话焦点）时也会生效。
- Session Focus Guard 依赖当前会话已激活的焦点实例，按 Guard Profile 的状态机和当前状态推进规则控制会话行为。
- Global Command Guard 通过后不会绕过 Session Focus Guard；如果后续会话焦点规则拒绝，命令仍会被拒绝。

相关数据范围也不同：

- Plugin install scope（插件安装范围）：插件代码和 Runtime 入口安装在用户授权的插件位置，负责提供可执行能力。
- Static profile scope（静态画像范围）：Guard Profile、`global-command-guards.yaml` 等静态规则可以来自项目 `.agents/guards/*` 或用户 `~/.agents/guards/*`。
- Runtime data scope（运行态数据范围）：项目命令产生的 evidence、audit、session state（会话状态）默认写入项目 `.local/guard`；用户级运行态只用于非项目范围的用户级命令或用户级上下文。
