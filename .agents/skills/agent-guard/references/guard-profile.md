# Guard Profile Contract（守卫画像契约）

Guard Profile（守卫画像）是守卫画像目录。它只描述被守卫对象和守卫规则，不修改被守卫对象，也不把具体业务规则写入 Runtime（运行时）。

按场景读取：

- 新建或校验画像目录：读“最小文件集合”和“必填字段”。
- 配置默认模式和实例策略：读“可选字段和默认值”。
- 编写 Guard Point（守卫点）：读“Guard Point（守卫点）字段”。
- 编写 Hook Binding（钩子绑定）：读“Hook Binding（钩子绑定）字段”。
- 排查校验错误：读“引用规则”和“错误输出”。

## 最小文件集合

一个最小可验证画像目录必须包含：

| 类别 | 文件 | 用途 |
| --- | --- | --- |
| manifest（清单） | `GUARD-MANIFEST.yaml` | 画像入口和文件索引 |
| target_model（目标模型） | `target-model.yaml` | 被守卫对象边界 |
| activation_model（激活模型） | `activation-model.yaml` | 显式激活和实例创建规则 |
| subject_resolver（主体解析器） | `subject-resolver.yaml` | Subject Key（主体键）计算和匹配规则 |
| execution_model（执行模型） | `execution-model.yaml` | agent（代理）可理解的节点、状态语义和下一步 |
| observation_model（观察模型） | `observation-model.yaml` | 可观察信号 |
| state_machine（状态机） | `state-machine.yaml` | Runtime（运行时）可执行的状态和转换 |
| guard_points（守卫点） | `guard-points.yaml` | 守卫点定义 |
| artifacts（产物） | `artifacts.yaml` | 产物定义 |
| hook_bindings（钩子绑定） | `hook-bindings.yaml` | Hook（钩子）或人工事件到转换的绑定 |
| brief_template（简报模板） | `brief-template.md` | Guard Brief（守卫简报）默认模板 |
| validation_plan（验证计划） | `validation-plan.md` | 本画像的验证计划 |

校验入口：

```powershell
python .agents\skills\agent-guard\scripts\validate_guard_profile.py <guard-profile-dir>
```

## 必填字段

`GUARD-MANIFEST.yaml`：

- `schema_version`
- `guard_profile_id`
- `name`
- `description`
- `mode`

`target-model.yaml`：

- `target.id`
- `target.type`
- `target.name`
- `target.source`
- `target.boundary`

`activation-model.yaml`：

- `activation.allowed_sources`
- `activation.required_profile_ref`
- `activation.scopes`
- `activation.on_existing_subject`
- `activation.on_missing_subject`
- `activation.initial_state`

`subject-resolver.yaml`：

- `subject.identity_fields`
- `subject.required_fields`
- `subject.context_sources`
- `subject.existing_match_policy`
- `subject.create_policy`
- `subject.ambiguous_policy`

其余文件：

- `execution-model.yaml` 必须有 `nodes` 和 `states`。
- `observation-model.yaml` 必须有 `signals`。
- `state-machine.yaml` 必须有 `initial_state`、`terminal_states`、`states` 和 `transitions`。
- `guard-points.yaml` 必须有 `guard_points`。
- `artifacts.yaml` 必须有 `artifacts`。
- `hook-bindings.yaml` 必须有 `hook_bindings`。

## 可选字段和默认值

- `mode` 建议显式写 `record`、`warn` 或 `block`。未成熟画像默认用 `warn`，不要默认启用阻断。
- 守卫点可以写自己的 `mode`。未写时后续 Runtime（运行时）可以继承 manifest（清单）的 `mode`。
- `subject.optional_fields` 可用于隔离 repo（仓库）、worktree（工作树）、branch（分支）、session（会话）或外部 ID。
- `activation.on_existing_subject` 建议默认 `reuse`。
- `activation.on_missing_subject` 只有显式激活时才建议 `create`。
- `subject.ambiguous_policy` 建议默认 `audit`，不要在歧义下阻断无关实例。

## Guard Point（守卫点）字段

`guard-points.yaml` 的单个守卫点建议使用这些字段：

- `id`：守卫点 ID，必须能被 `state-machine.yaml` 的转换引用。
- `description`：短说明，便于审计和错误输出。
- `trigger.events`：可选事件类型列表；不匹配时该守卫点跳过。
- `trigger.states`：可选当前状态列表；不匹配时该守卫点跳过。
- `mode`：`record`、`warn` 或 `block`。未写时继承 manifest（清单）模式。
- `inputs.artifacts`：该守卫点读取的产物 ID。
- `required_artifacts`：该守卫点要求存在的产物 ID。
- `checks`：按顺序执行的检查列表。
- `failure_reason`：默认失败原因。
- `fix_hint`：默认修复建议。
- `override_policy.allowed`：是否允许人工覆盖，默认必须视为 `false`。
- `override_policy.record_path`：可选覆盖记录路径模板。

支持的 `checks[].type`：

- `event_field`：检查标准事件 envelope（信封）字段，支持 `field`、`equals`、`in`、`contains` 和默认存在性检查。
- `state`：检查当前状态，支持 `current_state` 或 `allowed_states`。
- `artifact_exists`：检查事件 payload（载荷）或产物定义路径里是否存在产物。
- `artifact_freshness`：检查产物存在且 `updated_at`、`timestamp`、`created_at` 或文件 mtime（修改时间）不超过 `max_age_seconds`。
- `human_confirmation`：检查事件 payload 或 `.local/guard/confirmations/<profile>/<subject-key-hash>/<confirmation-id>.json` 中的人工确认记录。

人工覆盖记录默认路径：

```text
.local/guard/overrides/<guard-profile-id>/<subject-key-hash>/<guard-point-id>.json
```

有效记录必须包含：

- `guard_profile_id`
- `subject_key_hash`
- `guard_point_id`
- `expires_at`
- `reason`

## Hook Binding（钩子绑定）字段

`hook-bindings.yaml` 的单个绑定建议使用这些字段：

- `id`：绑定 ID，便于审计。
- `source`：事件来源，例如 `codex`、`git` 或 `manual`。
- `trigger_event` 或 `trigger.event`：外部 Hook（钩子）事件名，例如 `UserPromptSubmit`、`PreToolUse` 或 `pre-push`。
- `event_type`：转换后的标准事件类型，必须能被 `observation-model.yaml` 和 `state-machine.yaml` 引用。
- `target_profile`：目标 Guard Profile（守卫画像）ID；未写时表示当前画像。
- `blocking`：该入口是否可能阻断外部动作。
- `install.status`：安装状态，例如 `not_installed`、`dry_run` 或 `installed`。
- `install.target`：目标 Hook（钩子）文件，例如 `.codex/hooks.json` 或 `.githooks/pre-push`。
- `install.rollback`：回滚方式。
- `transitions`：该事件可能触发的状态转换 ID。
- `guard_points`：该事件入口会执行或关联的 Guard Point（守卫点）ID。

Hook Binding（钩子绑定）只描述映射和安装元数据，不承载业务判断。业务判断仍放在 `state-machine.yaml` 和 `guard-points.yaml`。安装行为见 `hook-contract.md`。

## 引用规则

校验入口会检查这些引用：

- `activation.initial_state` 必须引用 `state-machine.yaml` 中的 `states.id`。
- `state-machine.initial_state` 和 `terminal_states` 必须引用已有状态。
- 每个状态转换的 `from`、`to` 必须引用已有状态。
- 每个状态转换的 `guard_points` 必须引用 `guard-points.yaml`。
- 每个状态转换的 `required_artifacts` 必须引用 `artifacts.yaml`。
- 每个状态转换的 `on_event` 必须引用 `observation-model.yaml` 的 `signals.id`。
- 每个守卫点的 `required_artifacts`、`inputs.artifacts` 和 artifact check（产物检查）必须引用 `artifacts.yaml`。
- 每个 Hook Binding（钩子绑定）的 `transitions` 必须引用状态转换。
- 每个 Hook Binding（钩子绑定）的 `guard_points` 必须引用守卫点。
- `execution-model.yaml` 中节点的 `completion_signals` 必须引用观察信号。
- `execution-model.yaml` 中节点和状态提到的产物必须引用 `artifacts.yaml`。

## 错误输出

失败输出面向 agent（代理）使用，必须包含：

- 配置类别，例如 `state_machine`。
- 字段名，例如 `transitions.close.guard_points`。
- 出错原因。
- 修复方向。

示例：

```text
失败：Guard Profile（守卫画像）校验未通过
错误：category=state_machine field=transitions.close.guard_points 引用了 `missing`，但 `guard_points` 未定义它。
修复：定义该守卫点，或移除状态转换里的引用。
```

成功输出会列出已验证类别：

```text
通过：Guard Profile（守卫画像）校验
已检查：manifest
已检查：target_model
```

## 通用契约边界

通用契约不得写入任何具体业务流程规则。PR（拉取请求）流程、发布流程、审批流程等只能出现在具体 Guard Profile（守卫画像）中，不能进入 Runtime（运行时）、Hook（钩子）适配器或本通用契约。
