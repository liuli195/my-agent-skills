---
name: agent-guard-update
description: 更新守卫：维护已经初始化的守卫，更新 Agent Guard Plugin（代理守卫插件）或同步已校验 Guard Profile（守卫画像）。Use when 用户要更新 Plugin、同步已校验画像到已初始化守卫，或维护已有守卫。
---

# agent-guard-update

用于维护已经初始化的守卫。

立即执行：在把更新后的 Guard Profile（守卫画像）同步到已初始化守卫前，运行 `validate_guard_profile.py <guard-profile-dir>`。禁止跳过此步骤。

## 边界

- 只处理已初始化的守卫。
- 未初始化时默认中止，并提示先使用 `$agent-guard-init`。
- 不重新调研，不改画像业务语义。
- 保留 `.local/guard/*`、Session Focus Binding（会话焦点绑定）、确认记录和覆盖记录。

## 流程

1. 判断用户要更新 Plugin（插件）还是同步画像。
2. Plugin update（插件更新）：读取 `references/runtime-update.md`，先用 marketplace subscription（市场订阅）参数运行 `../agent-guard/scripts/install_agent_guard_plugin.py dry-run --target <codex|claude|all> --scope <personal|repo|all>`；用户明确授权后才运行 `install --target <codex|claude|all> --scope <personal|repo|all> --authorize-install`。
3. Profile sync（画像同步）：读取 `references/profile-sync.md`，先运行 `../agent-guard/scripts/validate_guard_profile.py <guard-profile-dir>`，再按 `../agent-guard/scripts/init_project_guard.py` 或 `../agent-guard/scripts/init_user_guard.py` 的 `--on-existing update` 模式同步。
4. 如果同步 Global Command Guard（全局命令守卫），按 `references/profile-sync.md` 保留运行态证据并更新场景配置。
5. 输出保留项、写入项和验证结果。
