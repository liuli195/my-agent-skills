# Init Flow（初始化流程）

初始化只发布已校验 Guard Profile（守卫画像）草案，并记录项目级或用户级运行态约定。

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

- `.agents/guards/<guard-profile-id>/`：已校验 Guard Profile（守卫画像）。

Runtime code（运行时代码）由 Agent Guard Plugin（代理守卫插件）提供，不复制到目标项目。

## 用户级初始化

```powershell
python ../agent-guard/scripts/init_user_guard.py --profile <guard-profile-dir> --user-guard-root <user-guard-root>
```

默认 dry-run（试运行）。只有用户明确授权时才加 `--authorize-init`。

授权后写入：

- `<user-guard-root>/<guard-profile-id>/`：用户级 Guard Profile（守卫画像）。
- `user-scope.md`：说明该画像属于用户级范围。

如果画像包含 `deny` 状态权限，必须额外取得用户明确授权后才加 `--authorize-deny-permissions`。

## Global Command Guard（全局命令守卫）

init 阶段只发布已校验配置，不现场改写场景规则。

- `global-command-guards.yaml` 和 `artifacts.yaml` 必须随同 Guard Profile（守卫画像）一起发布。
- artifact（产物）路径保持画像内声明，不复制 pass marker 到 `.local/guard/evidence`。
- 外部证据类拦截只在 Runtime（运行时）读取到对应 artifact 证据后放行。

troubleshoot（排障）：初始化后命令没有被拦截时，先确认发布位置中存在 `global-command-guards.yaml`，再确认 `artifacts.yaml` 中的 artifact ID 与守卫配置引用一致。
