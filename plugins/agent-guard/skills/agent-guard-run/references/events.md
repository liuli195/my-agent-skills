# Events（事件）

标准事件用于让 Runtime（运行时）处理主 agent（主代理）主动提交的状态事件，或处理 Hook（钩子）提交的权限检查事件。

## 运行入口

```text
python <plugin>/scripts/guard_runtime/cli.py state-completed --source codex --session-id <session-id>
```

源码仓库辅助脚本：

```powershell
python ../agent-guard/scripts/run_guard_event.py
```

## 标准事件字段

`run_guard_event.py` 接收的事件文件至少包含：

- `event_type`
- `context`

`source` 可选，缺省为 `codex`。`payload` 可选，缺省为空对象。Hook Adapter（钩子适配器）输出的标准事件仍必须包含 `source/event_type/context/payload`。

主 agent（主代理）主动推进状态时，`event_type` 必须是 `state_completed`。Runtime（运行时）只能从当前 Session Focus Binding（会话焦点绑定）读取 `profile_id + instance_id`，调用方不得指定画像或实例。

Runtime（运行时）必须按 Guard Profile（守卫画像）中的 `artifacts.yaml`、状态目录、审计记录和约定路径读取证据。主 agent（主代理）不得提交目标状态、转换 ID 或产物列表。`state_completed` 的 `payload.*` 不得作为转换条件、产物存在、产物新鲜度或人工确认的通过依据。

提交 `state_completed` 前必须先通过 brief（简报）入口读取当前 Session Focus Instance（会话焦点实例）的最新 Guard Brief（守卫简报）。如果当前 `brief_hash` 未被读取，Runtime（运行时）返回 `brief_required`，不推进状态。

## 状态权限

如果当前状态声明了 `permissions`，Runtime（运行时）必须在工具调用类事件上按当前状态评估权限。

- `allow`：允许当前操作继续。
- `ask`：要求主 agent（主代理）取得用户明确确认后重试同一操作。
- `deny`：拒绝当前操作继续。

状态权限评估和状态转换是两条独立逻辑。权限检查不得推进状态。

## Global Command Guard（全局命令守卫）

run 阶段只处理 Runtime（运行时）对 `global-command-guards.yaml` 的评估结果。

- Runtime（运行时）按 `artifacts.yaml` 解析 artifact（产物）路径，再读取已注册 evidence（证据）。
- 缺少 artifact、证据不存在、JSON 失配或路径不安全时，返回拒绝结果和失败原因。
- `reason`、`next` 和 `suggestion` 可来自 Guard Profile（守卫画像）的 deny 配置；Runtime（运行时）只透传或渲染这些字段，不内置被守卫业务流程。
- 如果上游流程已有稳定 external artifact（外部产物），主 agent（主代理）不得通过复制 pass marker（通过标记）到 `.local/guard/evidence` 绕过原始路径。
- 如果上游流程没有稳定产物，主 agent（主代理）可以按 Agent Guard（代理守卫）定义的 guard-defined evidence（守卫定义证据）路径写入通过标记，默认形状为 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`。
- 主 agent（主代理）不得把 `verify --apply` 作为主拦截点；应让 Global Command Guard（全局命令守卫）检查上游真实证据。

troubleshoot（排障）：先看返回 envelope（信封）中的 `failure_reason`、`artifact_id`、`evidence_path` 和 `failed_checks`，再补真实证据或修正画像。

## 状态推进

- 普通事件只使用当前 Session Focus Instance（会话焦点实例），不会创建新实例。
- `state_completed` 事件也只使用当前 Session Focus Instance（会话焦点实例），不会创建新实例。
- Hook（钩子）提交的事件只能用于权限评估、审计和提示，不得推进状态。
- 只有主 agent（主代理）主动提交且 `event_type=state_completed` 的事件可以触发状态转换。
- 每个非终止状态完成后必须唯一匹配一条转换；无匹配或多匹配都是画像配置错误。

## 返回 envelope（信封）

Runtime（运行时）输出至少包含：

- `status`：机器结果，例如 `allow`、`ask`、`deny`、`error`、`brief_required`、`no_session_focus_instance`、`session_focus_bound`、`session_observation_missing` 或 `lock_timeout`。
- `reason`：短原因码。

部分结果会额外包含 `brief_hash`、`brief_text`、`audit_path`、`guard_point_id`、`failure_reason`、`details` 或 `candidate_transition_ids`。`decision` 只用于人工覆盖记录等局部结构，不是所有 Runtime（运行时）返回的必填字段。

- `details`：状态文件、审计文件、失败守卫点、配置错误或修复建议等结构化信息。
