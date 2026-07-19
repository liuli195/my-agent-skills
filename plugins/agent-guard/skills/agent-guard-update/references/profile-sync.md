# Profile Sync（画像同步）

Profile sync（画像同步）把已校验 Guard Profile（守卫画像）同步到已经初始化的守卫。

## 前置校验

```powershell
python ../agent-guard/scripts/validate_guard_profile.py <guard-profile-dir>
```

校验未通过时不得同步。

## 同步命令

项目级：

```powershell
python ../agent-guard/scripts/init_project_guard.py --profile <guard-profile-dir> --project <target-project> --on-existing update
```

用户级：

```powershell
python ../agent-guard/scripts/init_user_guard.py --profile <guard-profile-dir> --user-guard-root <user-guard-root> --on-existing update
```

默认 dry-run（试运行）。只有用户明确授权时才加 `--authorize-init`。

## 边界

- 只同步已校验画像。
- 不重新调研。
- 不修改画像业务语义。
- 不安装 Hook（钩子）。
- 不清理 `.local/guard/*`。
- 不删除确认记录或人工覆盖记录。

如果目标尚未初始化，默认中止，并提示先使用 `$agent-guard-init`。

## Global Command Guard（全局命令守卫）

update 阶段同步已校验的 `global-command-guards.yaml` 和 `artifacts.yaml`，不清理运行态证据。

- 可以更新 artifact（产物）声明和外部证据检查条件。
- 禁止新增 reviewed wrapper。
- 对真正已有的 external artifact（外部产物），禁止复制 pass marker（通过标记）到 `.local/guard/evidence` 绕过原始路径。
- 禁止把 `verify --apply` 作为主拦截点。

troubleshoot（排障）：同步后仍被拒绝时，先查看 Runtime（运行时）返回的 artifact 缺失或 JSON 检查失败原因，再决定是否重新生成上游证据。
