# Brief（简报）

Guard Brief（守卫简报）把当前 Session Focus Instance（会话焦点实例）的状态、允许下一步、禁止下一步、缺失产物、最近拒绝原因和审计位置提供给主 agent（主代理）。

## 读取入口

源码仓库辅助脚本：

```powershell
python ../agent-guard/scripts/render_guard_brief.py --source <source> --session-id <session-id>
```

Plugin Runtime（插件运行时）入口：

```powershell
python <plugin>/scripts/guard_runtime/cli.py brief --source <source> --session-id <session-id>
```

Pi（编码助手）extension（扩展）会在 `session_start`（会话启动）中设置 `AGENT_GUARD_SOURCE=pi` 和 `AGENT_GUARD_SESSION_ID`。Pi 中调用源码仓库辅助脚本时可省略这两个参数；直接调用稳定 Runtime（运行时）入口时传入这两个环境变量的值。其他宿主必须传入其自身的 `source + session_id`。

提交任何 `state_completed` 事件前，必须读取当前 Session Focus Instance（会话焦点实例）的最新 Guard Brief（守卫简报）。

## 写入路径

Runtime（运行时）写入：

- `.local/guard/latest/<profile_id>/<instance_id>/brief.json`
- `.local/guard/latest/<profile_id>/<instance_id>/brief.md`
- `.local/guard/injections/<source>/<session_id-hash>/<profile_id>/<instance_id>.json`

路径使用 `profile_id + instance_id`，不使用 `subject_key_hash`。

## 注入规则

- 只有解析到唯一 Session Focus Instance（会话焦点实例）才允许注入。
- 注入内容只能来自 Runtime（运行时）生成的 latest brief（最新简报）。
- 同一 `source + session_id + profile_id + instance_id` 内按 `brief_hash` 去重。
- 相同 `brief_hash` 不重复注入。
- 终止状态下不得提示继续推进，只提示流程已完成和审计位置。
- Guard Brief（守卫简报）是状态推进前的权威读取面，但不替代 Runtime（运行时）的状态推进判断。
