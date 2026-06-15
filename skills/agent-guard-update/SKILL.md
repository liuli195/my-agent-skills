---
name: agent-guard-update
description: 更新守卫：维护已经初始化的守卫，升级 Guard Runtime（守卫运行时）或同步已校验 Guard Profile（守卫画像）。Use when 用户要升级 Runtime、同步已校验画像到已初始化守卫，或维护已有守卫。
---

# agent-guard-update

用于维护已经初始化的守卫。

立即执行：在把更新后的 Guard Profile（守卫画像）同步到已初始化守卫前，运行 `validate_guard_profile.py <guard-profile-dir>`。禁止跳过此步骤。

## 边界

- 只处理已初始化的守卫。
- 未初始化时默认中止，并提示先使用 `$agent-guard-init`。
- 不重新调研，不改画像业务语义。
- 保留 `.local/guard/*`、Hook（钩子）安装状态、确认记录和覆盖记录。

## 流程

1. 判断用户要升级 Runtime（运行时）还是同步画像。
2. Runtime update（运行时更新）：读取 `references/runtime-update.md`，运行 `../agent-guard/scripts/upgrade_guard_runtime.py --project <target-project>`；默认 dry-run，用户明确授权后才加 `--authorize-upgrade`。
3. Profile sync（画像同步）：读取 `references/profile-sync.md`，先运行 `../agent-guard/scripts/validate_guard_profile.py <guard-profile-dir>`，再按 `../agent-guard/scripts/init_project_guard.py` 或 `../agent-guard/scripts/init_user_guard.py` 的 `--on-existing update` 模式同步。
4. 输出保留项、写入项和验证结果。
