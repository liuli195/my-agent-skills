# Init Flow（初始化流程）

初始化只发布已校验 Guard Profile（守卫画像）草案，并创建项目级或用户级运行位置。

## 前置校验

```powershell
python ../agent-guard/scripts/validate_guard_profile.py <guard-profile-dir>
```

校验未通过时不得初始化。

## 项目级初始化

```powershell
python ../agent-guard/scripts/init_project_guard.py --profile <guard-profile-dir> --project <target-project>
```

默认 dry-run（试运行）。只有用户明确授权时才加 `--authorize-init`。

授权后写入：

- `.agents/guard-runtime/`：项目级 Runtime（运行时）骨架。
- `.agents/guards/<guard-profile-id>/`：已校验 Guard Profile（守卫画像）。

Runtime（运行时）骨架来自 `../agent-guard/assets/templates/guard-runtime/`。

## 用户级初始化

```powershell
python ../agent-guard/scripts/init_user_guard.py --profile <guard-profile-dir> --user-guard-root <user-guard-root>
```

默认 dry-run（试运行）。只有用户明确授权时才加 `--authorize-init`。

授权后写入：

- `<user-guard-root>/<guard-profile-id>/`：用户级 Guard Profile（守卫画像）。
- `user-scope.md`：说明该画像属于用户级范围。

如果画像包含 `deny` 状态权限，必须额外取得用户明确授权后才加 `--authorize-deny-permissions`。
