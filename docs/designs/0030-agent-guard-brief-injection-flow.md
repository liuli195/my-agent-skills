# Agent Guard Guard Brief 与注入流程技术方案

状态：草案

来源：

- PRD：[Agent Guard Guard Brief 与注入流程 PRD](../prd/0030-agent-guard-brief-injection-flow-prd.md)
- ADR：[0002 Agent Guard Plugin Runtime 与会话焦点](../adr/0002-agent-guard-plugin-runtime-session-focus.md)
- 关联设计：[Agent Guard Plugin Runtime 与会话焦点技术实现方案](0017-agent-guard-plugin-runtime-session-focus.md)

更新时间：2026-06-16

## 目标

把 Guard Brief（守卫简报）和 Guard Injection（守卫注入）在 Session Focus（会话焦点）架构下的业务流程、技术接口、发版验收和测试点固定下来。

本方案确认：

- Guard Brief（守卫简报）必须保留。
- Guard Brief（守卫简报）不再使用 `subject_key_hash`。
- Runtime（运行时）维护 latest brief（最新简报）。
- agent 主动读取 latest brief，读取动作触发注入去重记录。
- Runtime（运行时）按 `brief_hash` 判断是否需要重新注入。

## 业务流程

### 1. 激活守卫

1. `SessionStart` Hook（会话启动钩子）记录 Session Observation（会话观察记录）。
2. 用户运行 `$agent-guard-run activate`。
3. Runtime（运行时）读取当前 `source + session_id` 的 observation（观察记录）。
4. 用户选择或创建 Guard Instance（守卫实例）。
5. Runtime（运行时）写 Session Focus Binding（会话焦点绑定）。
6. Runtime（运行时）立即生成 latest Guard Brief（最新守卫简报）。

激活完成后，当前会话已经有明确焦点和最新简报。

### 2. 进入守卫流程

1. 主 agent（主代理）读取 `$agent-guard-run`。
2. 主 agent（主代理）读取 `references/brief.md`。
3. 主 agent（主代理）运行 `render_guard_brief.py` 或 Runtime `brief` 命令。
4. Runtime（运行时）解析当前 Session Focus Instance（会话焦点实例）。
5. Runtime（运行时）返回 latest brief payload（最新简报载荷）。
6. Runtime（运行时）写入或更新 injection record（注入记录）。

### 3. 执行任务

1. agent 按简报中的当前状态、允许下一步、禁止下一步和缺失产物执行任务。
2. `PreToolUse` Hook（工具使用前钩子）触发时，Runtime Router（运行时路由器）按当前焦点实例评估权限。
3. 如果返回 `deny` 或 `ask`，Runtime（运行时）写审计并刷新 latest brief，把拒绝原因写入 `recent_denial_reasons`。

### 4. 推进状态

1. agent 准备提交 `state_completed`。
2. agent 必须先读取当前 Session Focus Instance（会话焦点实例）的 latest Guard Brief（最新守卫简报）。
3. 读取失败时，不得继续提交 `state_completed`。
4. 读取成功后，agent 提交 `state_completed`。
5. Runtime（运行时）持有 `profile_id + instance_id` 锁后校验完成条件。
6. 推进成功时写新状态、审计和 latest brief。
7. 推进失败时保持原状态，写审计和 latest brief，说明缺失产物或失败原因。

## 当前注入模式

当前版本是 pull-to-inject（读取触发注入）：

- 守卫不后台主动推送简报到 Codex / Claude 会话上下文。
- Runtime（运行时）负责生成 latest brief（最新简报）。
- agent 主动调用 brief（简报）入口。
- brief（简报）入口返回可注入 payload（载荷）。
- Runtime（运行时）记录该 session（会话）已经注入过哪些 `brief_hash`。

返回状态：

- `injectable`：当前 `brief_hash` 尚未在该会话和实例下注入过。
- `already_injected`：当前 `brief_hash` 已注入过，本次不需要重复注入。
- `brief_required`：调用方尝试推进状态，但当前 `brief_hash` 尚未通过 brief（简报）入口读取；Runtime（运行时）不推进状态。

## 身份与路径

### 身份粒度

- 会话：`source + session_id`
- 实例：`profile_id + instance_id`
- 注入记录：`source + session_id + profile_id + instance_id`

禁止使用：

- `subject_key_hash`
- Subject Resolver（主体解析器）输出
- Hook Binding（钩子绑定）输出

### 写入路径

latest JSON（最新 JSON）：

```text
.local/guard/latest/<profile_id>/<instance_id>/brief.json
```

latest Markdown（最新 Markdown）：

```text
.local/guard/latest/<profile_id>/<instance_id>/brief.md
```

注入记录：

```text
.local/guard/injections/<source>/<session_id-hash>/<profile_id>/<instance_id>.json
```

`session_id-hash` 使用稳定 hash（哈希），避免把原始 session id（会话 ID）直接暴露在深层路径中。

## Runtime 接口

### 激活

命令：

```powershell
python <plugin>/scripts/guard_runtime/cli.py activate --source codex --session-id <session-id> --profile <profile-id>
```

职责：

- 读取 Session Observation（会话观察记录）。
- 创建或选择 Guard Instance（守卫实例）。
- 写 Session Focus Binding（会话焦点绑定）。
- 写 `session_focus_changed` 审计。
- 写 latest Guard Brief（最新守卫简报）。

成功返回至少包含：

- `profile_id`
- `instance_id`
- `binding_path`
- `audit_path`
- `brief_path`
- `brief_hash`

### 读取简报

命令：

```powershell
python <plugin>/scripts/guard_runtime/cli.py brief --source codex --session-id <session-id>
```

职责：

- 解析当前 Session Focus Binding（会话焦点绑定）。
- 加载或刷新 latest Guard Brief（最新守卫简报）。
- 写 injection record（注入记录）。
- 返回 `injectable` 或 `already_injected`。

调用方不得传入 `profile_id` 或 `instance_id`。

### Skill 包装入口

命令：

```powershell
python skills/agent-guard/scripts/render_guard_brief.py --source codex --session-id <session-id>
```

职责：

- 作为 `$agent-guard-run` 的稳定辅助入口。
- 委托 Plugin Runtime（插件运行时）的 `brief` 命令。
- 支持从 `--context-json` 读取 `session_id`。

### 状态推进

命令：

```powershell
python skills/agent-guard/scripts/run_guard_event.py --event <event.json>
```

当事件为 `state_completed` 时：

1. 调用 Runtime `state-completed` 命令。
2. Runtime（运行时）先检查当前 `brief_hash` 是否已经通过 brief（简报）入口读取并记录。
3. 未读取时返回 `brief_required`，包含当前 latest brief payload（最新简报载荷），并且不推进状态。
4. agent（代理）读取简报后再次提交 `state_completed`。
5. Runtime（运行时）推进成功或失败后刷新 latest brief（最新简报）。

## Brief Payload

latest brief JSON（最新简报 JSON）至少包含：

- `profile_id`
- `guard_profile_id`
- `instance_id`
- `state`
- `state_version`
- `generated_at`
- `source`
- `allowed_next`
- `forbidden_next`
- `missing_artifacts`
- `next_step`
- `recent_denial_reasons`
- `permissions`
- `transition_conditions`
- `state_completion_instruction`
- `audit_path`
- `brief_hash`
- `brief_text`
- `brief_path`
- `brief_text_path`

`brief_hash` 只覆盖会影响注入更新的业务字段：

- `profile_id`
- `instance_id`
- `state`
- `state_version`
- `allowed_next`
- `forbidden_next`
- `missing_artifacts`
- `recent_denial_reasons`
- `transition_conditions`

不把 `generated_at` 放入 hash（哈希），避免无意义重复注入。

## 刷新规则

必须刷新 latest brief（最新简报）的时机：

- activation（激活）成功。
- `state_completed` 推进成功。
- `state_completed` 因缺失产物失败。
- `PreToolUse` 返回 `deny`。
- `PreToolUse` 返回 `ask`。
- latest brief 文件不存在、损坏或状态版本落后。

不强制刷新的时机：

- `PreToolUse` 返回 `allow`。
- 简报读取且 latest brief 与当前 state（状态）一致。

## 失败行为

### 无焦点

读取 brief（简报）时，如果没有 Session Focus Instance（会话焦点实例）：

- 返回 `no_session_focus_instance`。
- 提示先 activate（激活）。
- 不写注入记录。

### 多焦点

如果 project（项目级）和 user（用户级）同时存在焦点绑定：

- 返回 `deny` 或对应错误状态。
- 审计 `multiple_session_focus_bindings`。
- 不写注入记录。

### 坏焦点

如果焦点 JSON（JSON 数据）损坏或缺字段：

- 返回 `deny` 或对应错误状态。
- 审计 `invalid_session_focus_binding`。
- 不写注入记录。

### 实例不可用

如果绑定指向的实例不存在或已 closed（关闭）：

- 按无焦点处理。
- 不读取其他实例。

## 发版验收

发版前必须确认：

- ADR（架构决策记录）明确 Guard Brief（守卫简报）和 Guard Injection（守卫注入）必须保留。
- PRD（产品需求文档）明确当前版本是 pull-to-inject（读取触发注入）。
- 技术方案明确 latest brief 路径和 injection record（注入记录）路径。
- `$agent-guard-run` 明确要求提交 `state_completed` 前读取 latest Guard Brief。
- `render_guard_brief.py` 不再返回 `brief_not_available`。
- `render_guard_brief.py` 不使用 `--subject` 或 `subject_key_hash`。
- Runtime `brief` 命令不允许调用方指定 `profile_id` 或 `instance_id`。
- Runtime `state-completed` 命令在当前 `brief_hash` 未读取时必须返回 `brief_required`，不得推进状态。
- active docs（活跃文档）中没有把 Guard Brief（守卫简报）描述成已删除能力。
- 全量测试通过。

## 测试矩阵

| 场景 | 期望 |
| --- | --- |
| 激活新实例 | 写 Session Focus Binding，并写 latest `brief.json` 与 `brief.md` |
| 第一次读取 brief | 返回 `injectable`，写 injection record |
| 第二次读取相同 brief | 返回 `already_injected`，不重复追加 hash |
| 未读 brief 直接推进状态 | 返回 `brief_required`，状态不变，不写 state transition 审计 |
| 状态推进成功 | 状态版本增加，latest brief 刷新，`brief_hash` 改变 |
| 缺失产物导致推进失败 | 状态不变，latest brief 写入失败原因 |
| 权限 deny | 写审计，latest brief 写入拒绝原因 |
| 权限 ask | 写审计，latest brief 写入 ask 原因 |
| 无焦点读取 brief | 返回 `no_session_focus_instance`，不写注入记录 |
| 多焦点读取 brief | 返回错误并审计冲突，不写注入记录 |
| 坏焦点读取 brief | 返回错误并审计损坏，不写注入记录 |
| 终止状态简报 | 不提示继续推进，只提示流程完成和审计位置 |
| 文档残留扫描 | active docs 不再使用旧 `subject_key_hash` 简报路径 |

## 回归命令

局部回归：

```powershell
python -m pytest tests/test_agent_guard_runtime_brief.py tests/test_user_skill_install.py -q
```

全量回归：

```powershell
python -m pytest -q
```

旧路径残留扫描：

```powershell
rg -n -e "subject_key_hash.*brief" -e "brief_not_available" docs skills plugins tests -S
```

## 后续扩展

如果后续要做后台主动注入，需要新增独立方案，至少回答：

- Codex / Claude 是否提供稳定的会话上下文注入 API。
- 注入失败是否阻断状态推进。
- 后台注入和 agent 主动读取冲突时谁优先。
- 如何避免没有用户授权时修改会话上下文。
