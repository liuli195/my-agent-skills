# Brief（简报）

Guard Brief（守卫简报）把当前状态、允许下一步、禁止下一步、缺失产物、最近拒绝原因和审计位置提供给主 agent（主代理）。

## 读取入口

```text
guard_runner.py brief --profile <id> --subject <subject-key-hash> --session <session-id> --format json
```

源码仓库辅助脚本：

```powershell
python ../agent-guard/scripts/render_guard_brief.py
```

提交任何 `state_completed` 事件前，必须读取最新 Guard Brief（守卫简报）。

## 写入路径

Runtime（运行时）写入：

- `.local/guard/latest/<guard-profile-id>/<subject-key-hash>/brief.json`
- `.local/guard/latest/<guard-profile-id>/<subject-key-hash>/brief.md`
- `.local/guard/runs/<guard-profile-id>/<run-id>/brief.json`
- `.local/guard/runs/<guard-profile-id>/<run-id>/brief.md`

Brief（简报）字段和默认文案模板以 `../agent-guard/assets/templates/guard-profile/minimal/brief-template.md` 为准。

## 注入规则

- 只有解析到唯一 Guard Instance（守卫实例）才允许注入。
- 注入前校验 `subject-key-hash`、`state_version` 和 `expires_at`。
- 同一 Codex session（Codex 会话）内按 `brief_hash` 去重。
- 终止状态下不得暴露 `completable_state_id`，只提示流程已完成和审计位置。
- Guard Brief（守卫简报）是导航信息，不替代 Runtime（运行时）的状态推进判断。
