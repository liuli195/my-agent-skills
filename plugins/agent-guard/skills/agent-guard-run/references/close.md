# Close（关闭）

关闭用于把一个 Guard Instance（守卫实例）标记为 `closed`，让它不再参与当前 Hook（钩子）权限判断或状态推进。

## 入口

Plugin Runtime（插件运行时）稳定入口：

```text
python <plugin>/scripts/guard_runtime/cli.py close-instance --profile <id> --instance-id <instance-id>
```

## 规则

- 关闭实例只把实例状态改为 `closed`，不删除历史运行态。
- 关闭实例不删除 Session Focus Binding（会话焦点绑定）。
- 关闭后的实例在 Hook（钩子）判断中按 `no_session_focus_instance` 处理。
- 关闭实例不是状态机里的 `state_completed`，不得绕过 Guard Point（守卫点）推进状态。
- 关闭前必须确认 `profile_id` 和 `instance_id` 来自当前表格或 Runtime（运行时）输出，不得凭记忆猜测。

## 输出

成功时 Runtime（运行时）返回：

- `status: instance_closed`
- `profile_id`
- `instance_id`
