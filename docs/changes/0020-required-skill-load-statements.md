# Issue #20: 强制加载必需辅助 Skill

GitHub Issue: https://github.com/liuli195/my-agent-skills/issues/20

## 已确认方案

第一阶段只在拆分后的入口正文中加入强制流程句，不修改 Guard Runtime（守卫运行时）和 Guard Profile（守卫画像）契约。

如果后续需要机器验证“必需辅助 Skill（技能）是否执行”，用 Agent Guard（代理守卫）自身守卫这些入口流程，而不是在本阶段引入新的 Runtime 证明模型。

## 强制流程句

- `$agent-guard-install`：立即执行：在调研、生成或更新任何 Guard Profile（守卫画像）前，使用 Skill 工具加载 `$grill-with-docs`。禁止跳过此步骤。
- `$agent-guard-init`：立即执行：在初始化任何项目级或用户级 Guard Profile（守卫画像）前，运行 `validate_guard_profile.py <guard-profile-dir>`。禁止跳过此步骤。
- `$agent-guard-update`：立即执行：在把更新后的 Guard Profile（守卫画像）同步到已初始化守卫前，运行 `validate_guard_profile.py <guard-profile-dir>`。禁止跳过此步骤。
- `$agent-guard-run`：立即执行：提交任何 `state_completed` 事件前，读取最新 Guard Brief（守卫简报）。禁止跳过此步骤。
- `$agent-guard-hooks`：立即执行：安装或验证 Hook（钩子）前，读取 `references/hook-install.md`。禁止跳过此步骤。

## 验收口径

- [ ] 5 个新入口都包含对应强制流程句。
- [ ] `$agent-guard-install` 明确要求先加载 `$grill-with-docs`。
- [ ] `$agent-guard-init` 和 `$agent-guard-update` 明确要求先校验画像。
- [ ] `$agent-guard-run` 明确要求提交 `state_completed` 前读取最新 Guard Brief（守卫简报）。
- [ ] `$agent-guard-hooks` 明确要求先读取 Hook 安装文档。
- [ ] 文档说明本阶段不做 Runtime 机器验证；后续可用 Agent Guard 自身守卫该流程。

## 不进入本 issue

- 不在 Guard Profile（守卫画像）中新增 `required_skill_commands`。
- 不让 Runtime（守卫运行时）记录或验证辅助 Skill 执行。
- 不改变状态推进、Hook（钩子）事件或 Guard Brief（守卫简报）契约。
