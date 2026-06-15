# Issues #21-#29: Agent Guard Plugin Runtime 与会话焦点

GitHub Issues:

- https://github.com/liuli195/my-agent-skills/issues/21
- https://github.com/liuli195/my-agent-skills/issues/22
- https://github.com/liuli195/my-agent-skills/issues/23
- https://github.com/liuli195/my-agent-skills/issues/24
- https://github.com/liuli195/my-agent-skills/issues/25
- https://github.com/liuli195/my-agent-skills/issues/26
- https://github.com/liuli195/my-agent-skills/issues/27
- https://github.com/liuli195/my-agent-skills/issues/28
- https://github.com/liuli195/my-agent-skills/issues/29

关联 PRD: [Agent Guard Plugin Runtime 与会话焦点 PRD](../prd/0017-agent-guard-plugin-runtime-session-focus-prd.md)

关联 ADR: [0002 Agent Guard Plugin Runtime 与会话焦点](../adr/0002-agent-guard-plugin-runtime-session-focus.md)

## 已实现方案

- 新增 `plugins/agent-guard/` 作为 Agent Guard Plugin（代理守卫插件）源码包，包含 Codex / Claude manifest（清单）、`SessionStart` / `PreToolUse` Hook（钩子）、Hook Router（钩子路由器）、Runtime code（运行时代码）和 Skill（技能）入口。
- 新增 Plugin Installer（插件安装器），支持 `dry-run`、`install`、`verify`，安装必须带明确 target（目标）和 `--authorize-install`。
- Hook Adapter（钩子适配器）把 Codex / Claude lifecycle payload（生命周期载荷）转换为标准 envelope（信封），不输出画像或实例字段。
- `SessionStart` 写 Session Observation（会话观察记录）。
- Activation（激活）通过 Session Observation（会话观察记录）显式创建、选择、切换 Session Focus Instance（会话焦点实例）。
- Runtime Router（运行时路由器）只通过 Session Focus Binding（会话焦点绑定）判断当前实例。
- `state_completed` 只能推进当前 Session Focus Instance（会话焦点实例），并使用 `profile_id + instance_id` 粒度锁。
- Guard Brief（守卫简报）和 Guard Injection（守卫注入）保留为状态推进核心机制，路径从 `subject_key_hash` 迁移为 `profile_id + instance_id`。
- Runtime（运行时）会在 `state_completed` 前检查当前 `brief_hash` 是否已通过 brief（简报）入口读取；未读取时返回 `brief_required`，不推进状态。
- `state_completed` 会评估 Guard Point（守卫点），并要求通过的 transition（转换）唯一；Guard Point 失败或多 transition 匹配时不推进状态。
- Session Focus Binding（会话焦点绑定）损坏或冲突时返回错误状态并审计，不使用权限 `deny`。
- Guard Profile（守卫画像）契约要求 `runtime_api_version`，不再要求 Subject Resolver（主体解析器）或 Hook Binding（钩子绑定）。
- 项目初始化只写 Guard Profile（守卫画像），不再复制 Runtime code（运行时代码）。

## 清理范围

- 删除项目级 Runtime（运行时）模板。
- 删除旧 Codex Hook（Codex 钩子）和 Git Hook（Git 钩子）模板。
- 删除旧 Subject Resolver（主体解析器）和 Hook Binding（钩子绑定）模板。
- 删除旧 `install_hooks.py` 和 `upgrade_guard_runtime.py` 兼容入口；Hook（钩子）和 Runtime code（运行时代码）统一由 Plugin（插件）安装器管理。

## 验证

- 全量测试：`python -m pytest`
- 结果：`72 passed`

旧 contract token（契约标记）只保留在 validator（校验器）的拒绝列表和负向测试中。
