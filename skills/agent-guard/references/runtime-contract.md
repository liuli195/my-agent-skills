# Runtime Contract（运行时契约）

Guard Runtime（守卫运行时）是项目级或用户级通用运行时。它不能写入具体业务规则，也不能替 Guard Profile（守卫画像）猜 Subject Key（主体键）。

按场景读取：

- 初始化项目级 Runtime（运行时）：读“项目级初始化入口”。
- 初始化用户级 Guard Profile（守卫画像）：读“用户级初始化入口”。
- 升级项目级 Runtime（运行时）：读“升级入口”。
- 激活 Guard Instance（守卫实例）：读“显式激活”。
- 处理主 agent（主代理）主动提交的状态事件：读“标准事件运行”。
- 处理 Hook（钩子）权限检查事件：读“状态权限运行”。
- 读取 Guard Brief（守卫简报）：读“Guard Brief 入口”。
- 排查返回结果或并发：读“运行顺序和默认处理”。

## 项目级初始化入口

项目级初始化入口：

```powershell
python skills\agent-guard\scripts\init_project_guard.py --profile <guard-profile-dir> --project <target-project>
```

默认 dry-run（试运行），只输出将写入的配置目录和安全状态。只有显式加 `--authorize-init` 才会生成骨架和画像配置：

- `.agents/guard-runtime/`：项目级 Runtime（运行时）骨架，包含 `VERSION`、`RUNTIME-MANIFEST.yaml`、`requirements.txt`、`guard_runner.py` 和 README。
- `.agents/guards/<guard-profile-id>/`：从已校验草案复制出的项目级 Guard Profile（守卫画像）。

初始化阶段不得预建 `.local/guard/*` 运行态目录，不得安装 Hook（钩子）、不得修改被守卫对象。已有同名画像默认 `abort`（中止），只能通过 `--on-existing update` 或 `--on-existing overwrite` 明确处理。

`.local/guard/state/`、`.local/guard/runs/`、`.local/guard/overrides/`、`.local/guard/confirmations/`、`.local/guard/latest/` 和 `.local/guard/injections/` 是运行时路径，由激活、事件处理、人工确认或 brief 注入按需创建。

## 用户级初始化入口

用户级 Guard Profile（守卫画像）初始化入口：

```powershell
python skills\agent-guard\scripts\init_user_guard.py --profile <guard-profile-dir> --user-guard-root <user-guard-root>
```

默认 dry-run（试运行）。只有显式加 `--authorize-init` 才会写入：

- `<user-guard-root>/<guard-profile-id>/`：用户级 Guard Profile（守卫画像）。
- `user-scope.md`：说明该画像属于用户级范围，不初始化目标项目、不安装 Hook（钩子）。

稳定入口建议：

```text
guard_runner.py activate --profile <id> --scope current_context --source agent-guard-skill --context-json '{"session_id":"..."}'
guard_runner.py run --event <event-file>
guard_runner.py brief --profile <id> --subject <subject-key-hash> --format json
guard_runner.py brief --profile <id> --subject <subject-key-hash> --session <session-id> --format json
```

Hook adapter（钩子适配器）入口和事件字段见 `hook-contract.md`。Runtime（运行时）只消费标准事件 envelope（信封）。

Guard Instance（守卫实例）必须由主 agent（主代理）或相关 Skill（技能）在流程开始时显式 activate（激活）。Hook（钩子）不负责发现缺失实例；缺失实例不被视为 Hook 违规。

## 升级入口

升级已初始化的项目级 Runtime（运行时）：

```powershell
python skills\agent-guard\scripts\upgrade_guard_runtime.py --project <target-project>
```

默认 dry-run（试运行），只输出当前版本、目标版本、将更新的 Runtime（运行时）文件，并声明 Guard Profile（守卫画像）和 Hook（钩子）配置会保留。只有显式加 `--authorize-upgrade` 才会覆盖项目级 Runtime（运行时）文件。

升级只处理 `.agents/guard-runtime/`。如果目标项目还没有 Runtime（运行时），返回 `status: not_initialized`，先执行项目级初始化。

## 显式激活

`activate` 入口接收显式激活请求。请求至少包含：

- `action: activate_guard`
- `guard_profile_id`
- `scope`
- `source`
- `context`
- 可选 `subject`

处理规则：

- 先校验 Guard Profile（守卫画像）存在。
- 校验 `activation.allowed_sources`、`activation.scopes` 和 `activation.required_profile_ref`。
- 按 `subject-resolver.yaml` 的 `identity_fields`、`required_fields`、`optional_fields` 和 `context_sources` 读取字段。
- Runtime（运行时）不得自行猜测 Subject Key（主体键）字段。
- 优先扫描 `.local/guard/state/<guard-profile-id>/*/state.json` 匹配已有 Guard Instance（守卫实例）。
- 没有匹配且 `subject.create_policy: explicit_activation_only`、`activation.on_missing_subject: create` 时，才创建新实例。
- 只有主 agent（主代理）显式 `activate` 可以创建 Guard Instance（守卫实例）。Hook（钩子）事件和 `state_completed` 事件不得创建新实例。
- 缺少必填字段时返回 `no_subject_match` 并写审计。
- 多个候选实例匹配时返回 `ambiguous_subject` 并写审计。
- 权限拒绝只能发生在已解析到唯一实例的状态权限检查上；`no_subject_match` 和 `ambiguous_subject` 默认不拒绝外部动作。

激活成功必须写入：

- `.local/guard/state/<guard-profile-id>/<subject-key-hash>/state.json`
- `.local/guard/runs/<guard-profile-id>/<run-id>/audit.json`
- `.local/guard/runs/<guard-profile-id>/<run-id>/raw-event.json`
- `.local/guard/runs/<guard-profile-id>/<run-id>/brief.json`
- `.local/guard/runs/<guard-profile-id>/<run-id>/brief.md`
- `.local/guard/latest/<guard-profile-id>/<subject-key-hash>/brief.json`
- `.local/guard/latest/<guard-profile-id>/<subject-key-hash>/brief.md`

激活输出必须包含 `subject_key_hash`、当前状态、状态文件、审计文件、`brief_path` 和 `brief_hash`。`brief-input.json` 可以作为兼容文件保留，但新调用应读取 `brief.json` 或 `brief.md`。

## 标准事件运行

`run --event <event-file>` 入口读取单个 JSON envelope（JSON 信封），用于处理主 agent（主代理）主动提交的标准事件，或 Hook（钩子）提交的权限检查事件。

事件文件字段：

- `guard_profile_id` 或 `profile_ref`：要加载的 Guard Profile（守卫画像）。
- `event_id`：事件 ID；缺失时由 Runtime（运行时）补默认值。
- `event_type`：事件类型。主 agent（主代理）主动推进状态时必须是 `state_completed`。
- `completed_state_id`：主 agent（主代理）声明已完成的状态 ID。Runtime（运行时）必须校验它和当前 Guard Instance（守卫实例）的当前状态一致。
- `source`：事件来源；缺失时使用 `unknown`。
- `timestamp`：事件时间；缺失时使用当前 UTC 时间。
- `context`：Subject Resolver（主体解析器）可读取的上下文字段。
- `subject`：可选 Subject（主体）输入。
- `payload`：事件载荷。`state_completed` 事件不得依赖 payload 选择证据；Runtime（运行时）必须按 Guard Profile（守卫画像）声明读取证据。
- `tool` 和 `action`：可选工具或动作信息。
- `raw_event_summary`：原始事件摘要，用于审计和 debug（调试）。

处理规则：

- Runtime（运行时）按 `guard_profile_id` 或 `profile_ref` 加载 Guard Profile（守卫画像）。
- Runtime（运行时）会规范化 `event.id`、`event.type`、`event.source` 和 `event.timestamp`，让 Subject Resolver（主体解析器）可以读取 `event.*` 字段。
- 普通事件只匹配已有 Guard Instance（守卫实例），不会创建新实例。
- `state_completed` 事件也只匹配已有 Guard Instance（守卫实例），不会创建新实例。
- 主 agent（主代理）事件缺少必填 subject 字段或没有实例匹配时返回 `no_subject_match`，写审计，不拒绝外部动作；Hook（钩子）事件无法匹配唯一实例时返回 `allow/ignored/no_guard_instance`，不写审计。
- 主 agent（主代理）事件匹配多个实例时返回 `ambiguous_subject`，写审计，不推进状态；Hook（钩子）事件匹配多个实例时返回 `allow/ignored/no_guard_instance`，不写审计。
- 只有主 agent（主代理）主动提交且 `event_type=state_completed`、带 `completed_state_id` 的事件可以触发状态转换。Hook（钩子）提交的事件只能用于权限评估、审计和提示，不得推进状态。
- Runtime（运行时）必须先校验 `completed_state_id` 等于当前状态，再查找所有 `from` 为当前状态且 `on_event=state_completed` 的候选转换。
- Runtime（运行时）按候选转换的 `conditions`、`required_artifacts` 和 Guard Point（守卫点）判断哪条转换成立，并由 Runtime（运行时）决定下一个状态。
- 主 agent（主代理）不得提交目标状态、转换 ID 或产物列表。
- 主 agent（主代理）提交 `state_completed` 时不得承担证据选择职责；Runtime（运行时）必须按 Guard Profile（守卫画像）中的 `artifacts.yaml`、状态目录、审计记录和约定路径自行读取证据。
- `state_completed` 的 `payload.*` 不得作为转换条件、产物存在、产物新鲜度或人工确认的通过依据。
- `conditions` 支持按 envelope（信封）字段做 `equals`、`in`、`contains` 和 `exists` 判断；未知或无效条件不得默默放行。
- 无候选转换、没有转换条件满足或多个转换同时满足，都表示 Guard Profile（守卫画像）的状态机配置错误，必须写审计，返回 `status=error`、`decision=failed`，不推进状态；多条转换同时满足时 `reason=ambiguous_transition`。
- `completed_state_id` 缺失或当前状态不匹配时，必须写审计并返回错误结果，不推进状态。事件类型不是 `state_completed` 时按非推进事件处理，返回 `allow/ignored/non_state_completed_event`，不得推进状态。
- Guard Profile（守卫画像）必须保证每个状态完成后能唯一确定下一条转换。Runtime（运行时）不负责在无法唯一匹配时给主 agent（主代理）设计补救流程。
- 当前状态是 `terminal_states` 中的终止状态时，不允许提交 `state_completed`。Runtime（运行时）必须写审计，返回 `status=error`、`decision=failed`、`reason=terminal_state_completed`，不修改状态。
- 主 agent（主代理）提交 `state_completed` 时不需要提交 `state_version`。Runtime（运行时）必须通过 Guard Instance（守卫实例）的当前状态、同一 Subject（主体）写锁、内部 `state_version` 和产物新鲜度校验保证一致性。
- 匹配到唯一转换后，Runtime（运行时）按转换引用顺序执行 Guard Point（守卫点）。
- Guard Point（守卫点）会执行 `required_artifacts` 和 `checks`，并记录每个检查的输入、证据、结果、失败原因和修复建议。
- 守卫点全部通过，或失败守卫点都有有效人工覆盖时，推进 `current_state`，`state_version` 加一，写状态、审计和 latest Guard Brief（最新守卫简报）。
- 守卫点失败且没有有效人工覆盖时不推进状态，必须用当前状态、失败原因和审计位置刷新 latest Guard Brief（最新守卫简报）。
- 每次写审计时必须在同一 run 目录写 `raw-event.json`，保存标准事件 envelope（信封），用于审计和 debug（调试）。

## 状态权限运行

如果当前状态声明了 `permissions`，Runtime（运行时）必须在工具调用类事件上按当前状态评估权限。未声明 `permissions` 的状态不做工具级权限检查。

状态权限评估和状态转换是两条独立逻辑。状态权限只回答“当前工具调用是否允许执行”，不得推进状态，也不得替状态机生成转换。状态推进只能由 `state-machine.yaml` 中匹配到的转换、转换条件和 Guard Point（守卫点）结果决定。

处理规则：

- Runtime（运行时）先把 `allow`、`ask`、`deny` 简写清单规范化为 `permissions.rules`。
- 按工具名、工具输入、命令、路径、参数字段和事件字段匹配规则。
- 多条规则命中时，最严格结果优先：`deny` 高于 `ask`，`ask` 高于 `allow`。
- 未命中规则时，使用 `permissions.default`。
- `allow` 表示该工具调用通过当前状态权限检查。
- `deny` 表示该工具调用违反当前状态权限；Runtime（运行时）必须拒绝该操作。
- `ask` 不直接放行；Runtime（运行时）必须返回 `status=ask`，要求主 agent（主代理）向用户请求明确确认。
- 状态权限评估完成后必须写审计；如果只是权限检查事件，不匹配状态转换，也不推进状态。

`ask` 返回结果必须包含：

- `status=ask`
- `decision=confirmation_required`
- `reason`
- `suggestion`
- `confirmation_id`
- `confirmation_path`
- `tool_input_hash`
- `audit_path`

`deny` 返回结果必须包含：

- `status=deny`
- `decision=denied`
- `reason`
- `suggestion`
- `state`
- `state_version`
- `audit_path`
- `details.permission.effect`
- `details.permission.default`
- `details.permission.tool`
- `details.permission.command`
- `details.permission.matched_rules`

人工确认记录写入：

```text
.local/guard/confirmations/<guard-profile-id>/<subject-key-hash>/<confirmation-id>.json
```

有效确认记录必须包含：

- `guard_profile_id`
- `subject_key_hash`
- `confirmation_id`
- `state`
- `tool`
- `tool_input_hash`
- `approved_by`
- `approved_at`
- `expires_at`
- `reason`

确认只对同一 Guard Instance（守卫实例）、同一状态、同一工具和同一工具输入 hash 有效。过期、状态变化、工具输入变化或 Subject（主体）变化都必须重新确认。确认通过后，主 agent（主代理）应重试同一工具调用；Runtime（运行时）校验确认记录后才放行。

工具调用成功后的状态变化不得由 Hook（钩子）自动触发。主 agent（主代理）完成对应状态后，按“标准事件运行”提交 `state_completed`。

## Guard Brief 入口

Runtime（运行时）负责生成 latest Guard Brief（最新守卫简报）并暴露读取入口：

```text
guard_runner.py brief --profile <id> --subject <subject-key-hash> --format json
guard_runner.py brief --profile <id> --subject <subject-key-hash> --session <session-id> --format json
```

字段、写入路径和 `brief_hash` 去重规则见 `guard-injection.md`。无唯一 Guard Instance（守卫实例）时不生成可注入 brief，只写审计。

## 守卫点执行

Guard Point（守卫点）字段、检查类型和人工覆盖记录格式见 `guard-profile.md`。Runtime（运行时）只负责按状态转换引用顺序执行这些配置。

Guard Point（守卫点）失败结果必须包含：

- `failed_guard_points`
- `current_state` 或 `state`
- `missing_conditions`
- `fix_suggestions`
- `override_allowed`
- `override_record_path`
- `audit_path`

人工覆盖默认关闭。只有 Guard Point（守卫点）允许覆盖且覆盖记录有效时，Runtime（运行时）才放行失败守卫点。

## 返回 envelope（信封）

Runtime（运行时）输出统一使用这些顶层字段：

- `status`：机器结果，例如 `allow`、`ask`、`deny`、`error`、`no_subject_match`、`ambiguous_subject`、`activated`、`injectable` 或 `already_injected`。
- `decision`：执行判断，例如 `ignored`、`guard_passed`、`guard_failed`、`confirmation_required`、`unresolved`、`denied` 或 `failed`。
- `reason`：短原因码，例如 `invalid_state_machine_transition`。
- `details`：状态文件、审计文件、失败守卫点、配置错误或修复建议等结构化信息。

`details` 是结构化信息的权威位置。为了兼容现有行式输出，Runtime（运行时）可以把 `details` 中的常用字段同时保留为顶层别名；新调用方应优先读取 `details`。

## 运行顺序和默认处理

运行顺序：

1. 读取标准事件或显式激活请求。
2. 加载 Guard Profile（守卫画像）。
3. 用 Subject Resolver（主体解析器）解析 Guard Instance（守卫实例）。
4. 读取当前状态。
5. 如果是工具调用类事件且当前状态声明了 `permissions`，先执行状态权限评估并返回 `allow`、`ask` 或 `deny`，不得推进状态。
6. 如果不是 `state_completed` 事件，返回 `allow/ignored/non_state_completed_event`，不得推进状态。
7. 如果是 `state_completed`，校验 `completed_state_id` 等于当前状态，且当前状态不是终止状态。
8. 收集当前状态的 `state_completed` 候选转换，并用转换条件、required artifacts（必需产物）和守卫点选出唯一通过的转换。
9. 如果没有转换通过或通过的转换不唯一，返回状态机错误。
10. 根据结果推进状态或保持原状态；守卫点失败、状态机错误、歧义或无法解析实例等结果保持原状态。
11. 对权限检查、状态推进、状态机错误、守卫点失败、锁超时和未解析的主 agent（主代理）事件写运行审计；被忽略的非推进事件不写状态推进审计。
12. 状态、缺失产物或最近拒绝原因变化时写 latest Guard Brief（最新守卫简报）。
13. 输出返回 envelope（信封）。

默认处理：

| 场景 | status | decision | reason |
| --- | --- | --- | --- |
| Hook 事件无法解析实例 | `allow` | `ignored` | `no_guard_instance` |
| 主 agent 事件无法解析实例 | `no_subject_match` | `unresolved` | 缺失或无法计算 Subject（主体） |
| 多实例匹配 | `ambiguous_subject` | `unresolved` | 多个候选实例 |
| 非推进事件 | `allow` | `ignored` | `non_state_completed_event` |
| 守卫点通过 | `allow` | `guard_passed` | 空或 `ok` |
| 状态权限允许 | `allow` | `guard_passed` | 空或 `ok` |
| 状态权限需要确认 | `ask` | `confirmation_required` | 命中 ask 规则或 default ask |
| 状态权限拒绝 | `deny` | `denied` | 命中 deny 规则或 default deny |
| 守卫点失败 | `error` | `guard_failed` | 守卫点失败原因 |
| 状态完成后无法匹配转换 | `error` | `failed` | `invalid_state_machine_transition` |
| 状态完成后匹配到多条转换 | `error` | `failed` | `ambiguous_transition` |
| 终止状态再次完成 | `error` | `failed` | `terminal_state_completed` |
| 同一 Subject（主体）写锁超时 | `lock_timeout` | `failed` | `lock_timeout` |
| Runtime（运行时）自身错误 | `error` | `failed` | 运行时错误码 |

状态写入必须按 `subject-key-hash` 加锁。同一 Subject（主体）串行写入，不同 Subject（主体）可以并发。锁超时必须写 `audit.json`，返回 `status=lock_timeout`，并且不得推进状态。

如果流程可能回到同名状态，Runtime（运行时）必须依靠内部 `state_version`、状态进入时间或等价元数据判断产物和确认记录是否属于当前状态轮次。主 agent（主代理）仍只提交 `completed_state_id`。

产物默认不得跨状态轮次复用。Runtime（运行时）检查转换条件、`required_artifacts` 或 Guard Point（守卫点）时，必须按 `artifacts.yaml` 的 `freshness.scope` 和 `reuse_policy` 判断产物是否属于当前状态轮次；未声明 `reuse_policy` 时按 `deny` 处理。
