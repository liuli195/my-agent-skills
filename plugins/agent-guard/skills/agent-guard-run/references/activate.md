# Activate（激活）

激活用于把当前 `source + session_id` 显式绑定到一个 Session Focus Instance（会话焦点实例）。

## 入口

Plugin Runtime（插件运行时）稳定入口：

```text
python <plugin>/scripts/guard_runtime/cli.py activate --source codex --session-id <session-id> --profile <id>
```

源码仓库辅助脚本：

```powershell
python ../agent-guard/scripts/activate_guard.py
```

## 规则

- 先确认 `SessionStart` Hook（会话启动钩子）已经写入 Session Observation（会话观察记录）。
- 先展示 Guarded Target（被守卫目标）表格和 active Guard Instance（活跃守卫实例）表格。
- 选择已有实例时使用 `--select-instance <instance-id>`。
- 创建新实例时必须显式传入 `--create`，并确认 `--title` 和 `--description`。
- 新实例 `instance_id` 必须是 opaque ID（不透明 ID），不带业务语义。
- 切换焦点只替换 Session Focus Binding（会话焦点绑定），旧实例不自动关闭。
- 成功绑定必须写 `session_focus_changed` 审计。
- Hook（钩子）事件和 `state_completed` 事件不得创建新实例。
