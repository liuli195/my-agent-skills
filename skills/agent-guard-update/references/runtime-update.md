# Runtime Update（运行时更新）

Runtime update（运行时更新）只维护已初始化项目的 `.agents/guard-runtime/`。

## 命令

```powershell
python ../agent-guard/scripts/upgrade_guard_runtime.py --project <target-project>
```

默认 dry-run（试运行），只输出当前版本、目标版本和将更新的 Runtime（运行时）文件。只有用户明确授权时才加 `--authorize-upgrade`。

## 边界

- 只覆盖通用 Runtime（运行时）文件。
- 保留 Guard Profile（守卫画像）。
- 保留 Hook（钩子）安装状态。
- 保留 `.local/guard/*` 运行态、确认记录和人工覆盖记录。
- 不修改被守卫对象。

如果目标项目还没有 Runtime（运行时），返回 `status: not_initialized`，并提示先使用 `$agent-guard-init`。
