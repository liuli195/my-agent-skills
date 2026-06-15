# Guard Injection（守卫注入）

Guard Injection（守卫注入）把 latest Guard Brief（最新守卫简报）提供给 agent（代理）。它提高执行效率，但不替代 Hook（钩子）或 Git hook（Git 钩子）的权限拒绝。

按场景读取：

- 只要读取当前简报：看“读取入口”。
- 需要实现或排查注入：看“规则”和“写入文件”。

规则：

- Runtime（运行时）只在状态、缺失产物、最近拒绝原因或下一步要求变化后生成 latest brief（最新简报）。
- 注入内容只能来自 Runtime（运行时）生成的 latest Guard Brief（最新守卫简报）。
- 只有解析到唯一 Guard Instance（守卫实例）才允许注入。
- 注入前校验 `subject-key-hash`、`state_version` 和 `expires_at`。
- 同一 Codex session（Codex 会话）内按 `brief_hash` 去重，相同 brief（简报）不重复注入。
- Brief（简报）保持短格式；字段清单见“写入文件”和“字段映射”。

Guard Profile（守卫画像）可以提供状态语义和文案模板，但 Runtime（运行时）负责统一渲染，避免简报和状态机漂移。

## 写入文件

Runtime（运行时）写入：

- `.local/guard/latest/<guard-profile-id>/<subject-key-hash>/brief.json`
- `.local/guard/latest/<guard-profile-id>/<subject-key-hash>/brief.md`
- `.local/guard/runs/<guard-profile-id>/<run-id>/brief.json`
- `.local/guard/runs/<guard-profile-id>/<run-id>/brief.md`

`brief.json` 至少包含 `guard_profile_id`、`subject_key_hash`、`state`、`state_version`、`allowed_next`、`forbidden_next`、`missing_artifacts`、`recent_denial_reasons`、`next_step`、`audit_path`、`brief_hash`、`brief_text` 和 `expires_at`。如果当前状态声明了 `permissions`、`transition_conditions`，或存在从当前状态出发的转换，Runtime（运行时）应把它们渲染进 `brief_text`，并可在 JSON 中保留同名结构化字段。Brief（简报）可以暴露 `completable_state_id`。

Guard Brief（守卫简报）的状态推进指令只提示 `event_type: state_completed` 和当前 `completable_state_id`；状态推进规则见 `runtime-contract.md`。

终止状态下的 Guard Brief（守卫简报）不得暴露 `completable_state_id`，只提示流程已完成和审计位置。

Guard Brief（守卫简报）是导航信息，不是状态推进锁。提交 `state_completed` 前不要求重新读取 Brief，也不需要提交 `brief_hash`。

字段映射：

| 语义 | JSON 字段 | 模板变量 |
| --- | --- | --- |
| Guard Profile（守卫画像） | `guard_profile_id` | `{{ guard_profile_id }}` |
| Subject（主体） | `subject_key_hash` | `{{ subject_key_hash }}` |
| 当前状态 | `state` | `{{ state }}` |
| 允许下一步 | `allowed_next` | `{{ allowed_next }}` |
| 禁止下一步 | `forbidden_next` | `{{ forbidden_next }}` |
| 缺失产物 | `missing_artifacts` | `{{ missing_artifacts }}` |
| 最近拒绝原因 | `recent_denial_reasons` | `{{ recent_denial_reasons }}` |
| 下一步建议 | `next_step` | `{{ next_step }}` |
| 审计位置 | `audit_path` | `{{ audit_path }}` |
| 过期时间 | `expires_at` | 无 |

## 读取入口

Hook（钩子）或 agent（代理）读取简报时使用：

```powershell
python .agents\guard-runtime\guard_runner.py brief --profile <id> --subject <subject-key-hash> --session <session-id> --format json
```

第一次读取当前 `brief_hash` 返回 `injectable`，并把记录写入：

```text
.local/guard/injections/<guard-profile-id>/<subject-key-hash>/<session-hash>.json
```

同一 session（会话）内再次读取相同 `brief_hash` 返回 `already_injected`。
