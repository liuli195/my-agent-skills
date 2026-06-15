# Events（事件）

标准事件用于让 Runtime（运行时）处理主 agent（主代理）主动提交的状态事件，或处理 Hook（钩子）提交的权限检查事件。

## 运行入口

```text
guard_runner.py run --event <event-file>
```

源码仓库辅助脚本：

```powershell
python ../agent-guard/scripts/run_guard_event.py
```

## 标准事件字段

事件文件至少包含：

- `guard_profile_id` 或 `profile_ref`
- `event_type`
- `context`

主 agent（主代理）主动推进状态时，`event_type` 必须是 `state_completed`，并且必须带 `completed_state_id`。

Runtime（运行时）必须按 Guard Profile（守卫画像）中的 `artifacts.yaml`、状态目录、审计记录和约定路径读取证据。主 agent（主代理）不得提交目标状态、转换 ID 或产物列表。`state_completed` 的 `payload.*` 不得作为转换条件、产物存在、产物新鲜度或人工确认的通过依据。

## 状态权限

如果当前状态声明了 `permissions`，Runtime（运行时）必须在工具调用类事件上按当前状态评估权限。

- `allow`：允许当前操作继续。
- `ask`：要求主 agent（主代理）取得用户明确确认后重试同一操作。
- `deny`：拒绝当前操作继续。

状态权限评估和状态转换是两条独立逻辑。权限检查不得推进状态。

## 状态推进

- 普通事件只匹配已有 Guard Instance（守卫实例），不会创建新实例。
- `state_completed` 事件也只匹配已有 Guard Instance（守卫实例），不会创建新实例。
- Hook（钩子）提交的事件只能用于权限评估、审计和提示，不得推进状态。
- 只有主 agent（主代理）主动提交且 `event_type=state_completed`、带 `completed_state_id` 的事件可以触发状态转换。
- 每个非终止状态完成后必须唯一匹配一条转换；无匹配或多匹配都是画像配置错误。

## 返回 envelope（信封）

Runtime（运行时）输出统一使用：

- `status`：机器结果，例如 `allow`、`ask`、`deny`、`error`、`no_subject_match`、`ambiguous_subject`、`activated`、`injectable` 或 `already_injected`。
- `decision`：执行判断，例如 `ignored`、`guard_passed`、`guard_failed`、`confirmation_required`、`unresolved`、`denied` 或 `failed`。
- `reason`：短原因码。
- `details`：状态文件、审计文件、失败守卫点、配置错误或修复建议等结构化信息。
