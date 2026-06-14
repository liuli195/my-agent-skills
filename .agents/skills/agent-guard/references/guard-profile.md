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
- `source.kind`

`source.kind` 必须说明画像来源。当前允许：

- `grill-with-docs-confirmed-notes`：由本轮已确认调研记录提取生成。
- `built-in-minimal-sample`：仓库内置最小样例。

新 Guard Profile（守卫画像）不得在 `GUARD-MANIFEST.yaml` 中声明 `mode`。旧画像如包含 `mode`，校验器必须提示迁移到 `states[].permissions`，不得继续按 `record`、`warn` 或 `block` 解释。

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

- `subject.optional_fields` 可用于隔离 repo（仓库）、worktree（工作树）、branch（分支）、session（会话）或外部 ID。
- `activation.on_existing_subject` 建议默认 `reuse`。
- `activation.on_missing_subject` 只有显式激活时才建议 `create`。
- `subject.ambiguous_policy` 建议默认 `audit`，不要在歧义下拒绝无关实例。

## State（状态）字段

`state-machine.yaml` 的单个状态建议使用这些字段：

- `id`：状态 ID。
- `description`：短说明，便于 Guard Brief（守卫简报）和审计显示。
- `permissions.default`：当前状态下未命中规则时的处理，必须用 `deny`、`ask` 或 `allow`。
- `permissions.rules`：当前状态下的工具权限规则。规则只描述工具名、输入范围和处理结果，不写流程判断，也不触发状态推进。
- `allowed_next`：给 agent（代理）看的下一步摘要。
- `forbidden_next`：给 agent（代理）看的禁止动作摘要。
- `transition_conditions`：离开当前状态需要满足的条件摘要。

`permissions.rules` 的单条规则建议使用这些字段：

- `effect`：`allow`、`ask` 或 `deny`。多条规则命中时，最严格结果优先：`deny` 高于 `ask`，`ask` 高于 `allow`。
- `tool`：工具名，例如 `Bash`、`apply_patch` 或 MCP tool（MCP 工具）名。
- `match`：按工具输入匹配，支持命令前缀、路径、参数字段和事件字段。
- `reason`：拒绝或询问的原因。
- `suggestion`：建议 agent（代理）改做什么。

规则应尽量匹配工具和参数，而不是只匹配工具名。例如 `Bash(git status *)` 和 `Bash(git push *)` 必须能分开表达。Hook（钩子）只能把可见工具调用提交给 Runtime（运行时）判断，不能承诺拦截所有工具路径。

未声明 `permissions` 的状态不启用工具级权限检查。只要状态声明了 `permissions`，就必须显式声明 `permissions.default`，不能隐式决定默认处理。

状态权限采用权限模型，不再叠加额外开关。`deny` 就是拒绝当前操作，`ask` 就是要求人工确认，`allow` 就是允许。

`permissions` 和 `transitions` 是同一状态下的两类独立配置：`permissions` 控制当前状态允许哪些操作发生，`transitions` 控制主 agent（主代理）声明当前状态完成后，Runtime（运行时）如何判断下一状态。权限规则命中 `allow` 不代表状态推进，权限规则命中 `deny` 或 `ask` 也不修改状态。

状态转换的证据来源必须由 Guard Profile（守卫画像）声明。主 agent（主代理）只声明 `completed_state_id`，不得选择目标状态、转换 ID 或产物列表。Runtime（运行时）按 `artifacts.yaml`、状态目录、审计记录和约定路径读取证据；缺失证据时返回缺失产物和修复建议。

`state_completed` 事件不能用 `payload.*` 作为完成证据。状态推进转换的 `conditions` 不得引用 `payload.*`，被状态推进转换引用的 Guard Point（守卫点）也不得用 `event_field` 检查 `payload.*`。agent（代理）必须先按 `artifacts.yaml` 声明的位置写入产物，再提交 `state_completed`。

Guard Profile（守卫画像）必须保证每个非终止状态在完成后可以唯一匹配一条转换。没有转换满足或多条转换同时满足都属于状态机配置错误，不属于主 agent（主代理）需要补救的普通流程分支。

`permissions.rules` 可以采用接近 Codex（Codex 代理）命令规则或 Claude（Claude 代理）权限清单的表达方式，便于迁移和人工阅读。但 Guard Profile（守卫画像）不要求生成或同步工具原生的静态权限配置；当前状态仍是 Runtime（运行时）判断动态流程权限的唯一依据。

结构化 `permissions.rules` 是权威格式：

```yaml
states:
  - id: review_required
    permissions:
      default: deny
      rules:
        - effect: allow
          tool: Bash
          match:
            command_prefix: ["python", "scripts/review"]
          reason: "当前状态允许运行 review"
        - effect: deny
          tool: Bash
          match:
            command_prefix: ["git", "push"]
          reason: "完成 review 前禁止 push"
          suggestion: "先生成 review 产物并完成状态转换"
```

允许使用字符串清单作为简写输入：

```yaml
states:
  - id: review_required
    permissions:
      default: deny
      allow:
        - "Bash(python scripts/review *)"
        - "Read(docs/**)"
      deny:
        - "Bash(git push *)"
```

校验器或 Runtime（运行时）必须先把 `allow`、`ask`、`deny` 简写清单规范化为 `permissions.rules`，再执行引用校验、权限评估和审计输出。简写规则不能表达 `reason` 或 `suggestion` 时，Runtime（运行时）应使用状态或默认文案生成提示。

`ask` 规则表示需要用户明确确认，不表示自动放行。Runtime（运行时）必须生成 `confirmation_id`，并要求主 agent（主代理）取得人工确认记录后重试同一工具调用。确认记录格式和有效范围见 `runtime-contract.md`。

## Artifact（产物）字段

`artifacts.yaml` 的单个产物建议使用这些字段：

- `id`：产物 ID，必须能被状态转换和 Guard Point（守卫点）引用。
- `description`：短说明。
- `path`：Runtime（运行时）读取产物的路径或路径模板。
- `freshness.scope`：产物新鲜度范围，建议使用 `current_state_entry`。
- `reuse_policy`：是否允许跨状态轮次复用，必须是 `deny` 或 `allow`，默认 `deny`。

默认情况下，产物不得跨状态轮次复用。Runtime（运行时）必须确认产物属于当前状态进入后的轮次；只有产物显式声明 `reuse_policy: allow` 时，才可以复用旧产物。

`path` 可以使用这些模板变量：

- `{guard_profile_id}`。
- `{subject_key_hash}`。
- `{current_state}`。
- `{state_version}`。
- `{event_id}`。

示例：

```yaml
artifacts:
  - id: cross_review_report
    description: "交叉 review 报告"
    path: ".local/guard/artifacts/{guard_profile_id}/{subject_key_hash}/{state_version}/cross-review-report.json"
    freshness:
      scope: current_state_entry
    reuse_policy: deny
```

## Guard Point（守卫点）字段

`guard-points.yaml` 的单个守卫点建议使用这些字段：

- `id`：守卫点 ID，必须能被 `state-machine.yaml` 的转换引用。
- `description`：短说明，便于审计和错误输出。
- `trigger.events`：可选事件类型列表；不匹配时该守卫点跳过。
- `trigger.states`：可选当前状态列表；不匹配时该守卫点跳过。
- `inputs.artifacts`：该守卫点读取的产物 ID。
- `required_artifacts`：该守卫点要求存在的产物 ID。
- `checks`：按顺序执行的检查列表。
- `failure_reason`：默认失败原因。
- `fix_hint`：默认修复建议。
- `override_policy.allowed`：是否允许人工覆盖，默认必须视为 `false`。
- `override_policy.record_path`：可选覆盖记录路径模板。

支持的 `checks[].type`：

- `event_field`：检查标准事件 envelope（信封）字段，支持 `field`、`equals`、`in`、`contains` 和默认存在性检查；被 `state_completed` 转换引用时不得检查 `payload.*`。
- `state`：检查当前状态，支持 `current_state` 或 `allowed_states`。
- `artifact_exists`：检查产物定义路径里是否存在产物；非 `state_completed` 观察事件可以读取 payload（载荷）中的产物线索。
- `artifact_freshness`：检查产物存在且 `updated_at`、`timestamp`、`created_at` 或文件 mtime（修改时间）不超过 `max_age_seconds`。
- `human_confirmation`：检查 `.local/guard/confirmations/<profile>/<subject-key-hash>/<confirmation-id>.json` 中的人工确认记录；非 `state_completed` 观察事件可以读取 payload（载荷）中的确认线索。

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
- `GUARD-MANIFEST.yaml` 不得包含 `mode`。
- 每个状态转换的 `from`、`to` 必须引用已有状态。
- 每个状态转换必须有唯一 `id`，用于审计和错误输出。主 agent（主代理）不得通过转换 ID 选择下一状态。
- 每个状态转换不得包含旧字段 `advance_on_warn_failure`。
- 声明了 `permissions` 的状态必须声明 `permissions.default`。
- 每个 `permissions.default` 必须是 `allow`、`ask` 或 `deny`。
- 每个状态权限规则的 `effect` 必须是 `allow`、`ask` 或 `deny`。
- 状态权限的 `allow`、`ask`、`deny` 简写清单必须能规范化为 `permissions.rules`。
- 每个状态转换的 `guard_points` 必须引用 `guard-points.yaml`。
- 每个状态转换的 `required_artifacts` 必须引用 `artifacts.yaml`。
- 每个状态转换条件中引用的 artifact（产物）必须定义在 `artifacts.yaml`。
- 每个 `state_completed` 状态转换的 `conditions` 不得引用 `payload.*`。
- 每个 artifact（产物）的 `reuse_policy` 必须是 `deny` 或 `allow`；未写时按 `deny` 处理。
- 每个非终止状态完成后的转换条件必须设计为唯一匹配；校验器应尽量发现明显的无出口或重复无条件转换。
- 每个状态推进转换的 `on_event` 必须是 `state_completed`，并且 `observation-model.yaml` 必须定义该 signal（信号）。
- 每个守卫点的 `required_artifacts`、`inputs.artifacts` 和 artifact check（产物检查）必须引用 `artifacts.yaml`。
- 被 `state_completed` 状态转换引用的守卫点不得用 `event_field` 检查 `payload.*`。
- 每个守卫点不得包含旧字段 `mode`、`on_fail` 或 `on_error`。
- 每个 Hook Binding（钩子绑定）的 `transitions` 必须引用状态转换。
- 每个 Hook Binding（钩子绑定）的 `guard_points` 必须引用守卫点。
- 每个 Hook Binding（钩子绑定）不得包含旧字段 `blocking`。
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
