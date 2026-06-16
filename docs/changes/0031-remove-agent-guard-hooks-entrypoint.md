# Issue #31: MVP 删除独立 agent-guard-hooks 入口

GitHub Issue: https://github.com/liuli195/my-agent-skills/issues/31

## 背景

MVP 阶段不需要保留独立的 `$agent-guard-hooks` Skill（技能）入口。lifecycle Hook（生命周期钩子）已经由 Agent Guard Plugin（代理守卫插件）发布，并随插件安装注册。

## 已确认方案

删除独立 `$agent-guard-hooks` 入口。

保留底层能力：

- Plugin Installer（插件安装器）继续支持 dry-run、install、verify。
- `$agent-guard-update` 承载插件更新和插件验证入口。
- `$agent-guard-run activate` 在找不到 Session Observation（会话观察记录）时提示检查插件 Hook 是否已安装、已信任、已触发。

## 验收口径

- [x] `plugins/agent-guard/skills/agent-guard-hooks/` 不再作为发布 Skill 入口存在。
- [x] 薄路由 `$agent-guard` 不再路由到 `$agent-guard-hooks`。
- [x] 用户级 Skill 安装/验证脚本不再同步或要求 `agent-guard-hooks`。
- [x] Plugin Package（插件包）测试仍确认 `hooks/hooks.json` 只声明 `SessionStart` 和 `PreToolUse`。
- [x] Plugin Installer（插件安装器）测试仍覆盖 dry-run、install、verify。
- [x] 端到端回归通过：`python -m pytest tests/test_agent_guard_prd_full_e2e.py -q`。
- [x] 发布或提交前完整测试通过：`python -m pytest -q`。

## 不进入本 issue

- 不删除 Plugin Installer（插件安装器）。
- 不删除 `hooks/hooks.json`。
- 不删除 `SessionStart` / `PreToolUse` lifecycle Hook（生命周期钩子）。
- 不恢复项目级 Hook 或 Git Hook 安装。
