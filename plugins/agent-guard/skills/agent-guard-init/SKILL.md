---
name: agent-guard-init
description: 初始化守卫：第一次创建项目级或用户级 Guard Profile（守卫画像）和运行态约定。Use when 用户要初始化、启用、落地或创建一个尚未初始化的守卫。
---

# agent-guard-init

用于第一次初始化项目级或用户级守卫。

立即执行：在初始化任何项目级或用户级 Guard Profile（守卫画像）前，运行 `validate_guard_profile.py <guard-profile-dir>`。禁止跳过此步骤。

## 边界

- 只接收已校验的 Guard Profile（守卫画像）。
- 第一次创建运行位置。
- 已存在同名守卫时默认中止，不升级、不覆盖。
- 不安装 Hook（钩子）。
- 不修改被守卫对象。

## 流程

1. 读取 `references/init-flow.md`，运行 `../agent-guard/scripts/validate_guard_profile.py <guard-profile-dir>`。
2. 读取 `references/init-boundaries.md`，选择 `../agent-guard/scripts/init_project_guard.py` 或 `../agent-guard/scripts/init_user_guard.py`。
3. 默认 dry-run（试运行）初始化命令。
4. 只有用户明确授权时才加 `--authorize-init`。
5. 如果画像包含 `deny` 状态权限，必须额外取得用户明确授权后才加 `--authorize-deny-permissions`。
6. 如果画像包含 Global Command Guard（全局命令守卫），按 `references/init-flow.md` 确认 `global-command-guards.yaml` 和 `artifacts.yaml` 一起发布。
7. 输出写入位置、授权状态和安全声明。
