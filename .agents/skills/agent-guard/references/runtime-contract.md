# Runtime Contract（运行时契约）

Guard Runtime（守卫运行时）是项目级或用户级通用运行时。它不能写入具体业务规则，也不能替 Guard Profile（守卫画像）猜 Subject Key（主体键）。

按场景读取：

- 初始化项目级 Runtime（运行时）：读“项目级初始化入口”。
- 激活 Guard Instance（守卫实例）：读“显式激活”。
- 处理 Hook（钩子）或人工事件：读“标准事件运行”。
- 读取 Guard Brief（守卫简报）：读“Guard Brief 入口”。
- 排查返回结果或并发：读“运行顺序和默认处理”。

## 项目级初始化入口

项目级初始化入口：

```powershell
python .agents\skills\agent-guard\scripts\init_project_guard.py --profile <guard-profile-dir> --project <target-project>
```

默认 dry-run（试运行），只输出将写入的配置目录和安全状态。只有显式加 `--authorize-init` 才会生成骨架和画像配置：

- `.agents/guard-runtime/`：项目级 Runtime（运行时）骨架，包含 `VERSION`、`RUNTIME-MANIFEST.yaml`、`requirements.txt`、`guard_runner.py` 和 README。
- `.agents/guards/<guard-profile-id>/`：从已校验草案复制出的项目级 Guard Profile（守卫画像）。

初始化阶段不得预建 `.local/guard/*` 运行态目录，不得安装 Hook（钩子）、不得默认启用 blocking mode（阻断模式）、不得修改被守卫对象。已有同名画像默认 `abort`（中止），只能通过 `--on-existing update` 或 `--on-existing overwrite` 明确处理。

`.local/guard/state/`、`.local/guard/runs/`、`.local/guard/overrides/`、`.local/guard/confirmations/`、`.local/guard/latest/` 和 `.local/guard/injections/` 是运行时路径，由激活、事件处理、人工确认或 brief 注入按需创建。

如需初始化为 blocking mode（阻断模式），必须同时提供 `--authorize-init --authorize-blocking --mode block`，或源画像为 `mode: block` 且提供 `--authorize-blocking`。没有阻断授权时，`block` 会降级为 `warn`。

## 用户级初始化入口

用户级 Guard Profile（守卫画像）初始化入口：

```powershell
python .agents\skills\agent-guard\scripts\init_user_guard.py --profile <guard-profile-dir> --user-guard-root <user-guard-root>
```

默认 dry-run（试运行）。只有显式加 `--authorize-init` 才会写入：

- `<user-guard-root>/<guard-profile-id>/`：用户级 Guard Profile（守卫画像）。
- `user-scope.md`：说明该画像属于用户级范围，不初始化目标项目、不安装 Hook（钩子）。

用户级初始化也遵守 blocking mode（阻断模式）授权规则：没有 `--authorize-blocking` 时，`block` 会降级为 `warn`。

稳定入口建议：

```text
guard_runner.py activate --profile <id> --scope current_context --source agent-guard-skill --context-json '{"session_id":"..."}'
guard_runner.py run --event <event-file>
guard_runner.py brief --profile <id> --subject <subject-key-hash> --format json
guard_runner.py brief --profile <id> --subject <subject-key-hash> --session <session-id> --format json
```

Hook adapter（钩子适配器）入口和事件字段见 `hook-contract.md`。Runtime（运行时）只消费标准事件 envelope（信封）。

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
- 缺少必填字段时返回 `no_subject_match` 并写审计。
- 多个候选实例匹配时返回 `ambiguous_subject` 并写审计。
- 阻断只能发生在已解析到唯一实例的后续守卫点上；`no_subject_match` 和 `ambiguous_subject` 默认不强阻断。

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

`run --event <event-file>` 入口读取单个 JSON envelope（JSON 信封），用于处理 hook adapter（钩子适配器）或人工命令输出的标准事件。

事件文件字段：

- `guard_profile_id` 或 `profile_ref`：要加载的 Guard Profile（守卫画像）。
- `event_id`：事件 ID；缺失时由 Runtime（运行时）补默认值。
- `event_type`：事件类型，用于匹配 `state-machine.yaml` 的 `transitions[].on_event`。
- `source`：事件来源；缺失时使用 `unknown`。
- `timestamp`：事件时间；缺失时使用当前 UTC 时间。
- `context`：Subject Resolver（主体解析器）可读取的上下文字段。
- `subject`：可选 Subject（主体）输入。
- `payload`：事件载荷；`payload.artifacts`、`payload.artifact_ids` 或同名 payload 字段可用于 required artifacts（必需产物）检查。
- `tool` 和 `action`：可选工具或动作信息。
- `raw_event_summary`：原始事件摘要，用于审计和 debug（调试）。

处理规则：

- Runtime（运行时）按 `guard_profile_id` 或 `profile_ref` 加载 Guard Profile（守卫画像）。
- Runtime（运行时）会规范化 `event.id`、`event.type`、`event.source` 和 `event.timestamp`，让 Subject Resolver（主体解析器）可以读取 `event.*` 字段。
- 普通事件只匹配已有 Guard Instance（守卫实例），不会创建新实例。
- 缺少必填 subject 字段或没有实例匹配时返回 `no_subject_match`，写审计，不强阻断。
- 多个实例匹配时返回 `ambiguous_subject`，写审计，不推进状态。
- 状态转换按当前状态、`event_type` 和可选 `conditions` 匹配。
- `conditions` 支持按 envelope（信封）字段做 `equals`、`in`、`contains` 和 `exists` 判断；未知或无效条件不得默默放行。
- 无匹配转换时返回 `status=allow`、`decision=ignored`、`reason=no_matching_transition`，不写审计，不推进状态。
- 多个转换同时匹配时返回 `ambiguous_transition`，写审计，不推进状态。
- 匹配到唯一转换后，Runtime（运行时）按转换引用顺序执行 Guard Point（守卫点）。
- Guard Point（守卫点）会执行 `required_artifacts` 和 `checks`，并记录每个检查的输入、证据、结果、失败原因和修复建议。
- 守卫点全部通过、只记录失败、警告失败，或失败守卫点都有有效人工覆盖时，推进 `current_state`，`state_version` 加一，写状态、审计和 latest Guard Brief（最新守卫简报）。
- 转换可显式配置 `advance_on_warn_failure: false`，让警告失败只写审计和 latest Guard Brief（最新守卫简报）但不推进状态。
- 阻断模式失败时不推进状态，但必须用当前状态、缺失产物、最近阻断原因和审计位置刷新 latest Guard Brief（最新守卫简报）。
- 每次写审计时必须在同一 run 目录写 `raw-event.json`，保存标准事件 envelope（信封），用于审计和 debug（调试）。

## Guard Brief 入口

Runtime（运行时）负责生成 latest Guard Brief（最新守卫简报）并暴露读取入口：

```text
guard_runner.py brief --profile <id> --subject <subject-key-hash> --format json
guard_runner.py brief --profile <id> --subject <subject-key-hash> --session <session-id> --format json
```

字段、写入路径和 `brief_hash` 去重规则见 `guard-injection.md`。无唯一 Guard Instance（守卫实例）时不生成可注入 brief，只写审计。

## 守卫点执行

Guard Point（守卫点）字段、检查类型和人工覆盖记录格式见 `guard-profile.md`。Runtime（运行时）只负责按状态转换引用顺序执行这些配置。

阻断结果必须包含：

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

- `status`：机器结果，例如 `allow`、`warn`、`block`、`error`、`no_subject_match`、`ambiguous_subject`、`ambiguous_transition`、`activated`、`injectable` 或 `already_injected`。
- `decision`：执行判断，例如 `ignored`、`guard_passed`、`guard_failed`、`guard_recorded`、`unresolved` 或 `blocked`。
- `reason`：短原因码，例如 `no_matching_transition`。
- `details`：状态文件、审计文件、失败守卫点、缺失条件或修复建议等结构化信息。

## 运行顺序和默认处理

运行顺序：

1. 读取标准事件或显式激活请求。
2. 加载 Guard Profile（守卫画像）。
3. 用 Subject Resolver（主体解析器）解析 Guard Instance（守卫实例）。
4. 读取当前状态。
5. 匹配状态转换。
6. 执行转换上的守卫点。
7. 根据结果推进状态或保持原状态；只有阻断失败、歧义或无法解析实例等结果保持原状态。
8. 写运行审计。
9. 状态或缺失产物变化时写 latest Guard Brief（最新守卫简报）。
10. 输出返回 envelope（信封）。

默认处理：

| 场景 | status | decision | reason |
| --- | --- | --- | --- |
| 无法解析实例 | `no_subject_match` | `unresolved` | 缺失或无法计算 Subject（主体） |
| 多实例匹配 | `ambiguous_subject` | `unresolved` | 多个候选实例 |
| 无匹配转换 | `allow` | `ignored` | `no_matching_transition` |
| 守卫点通过 | `allow` | `guard_passed` | 空或 `ok` |
| 记录模式失败 | `allow` | `guard_recorded` | 守卫点失败原因 |
| 警告模式失败 | `warn` | `guard_failed` | 守卫点失败原因 |
| 阻断模式失败 | `block` | `guard_failed` | 守卫点失败原因 |
| 同一实例内多转换匹配 | `ambiguous_transition` | `blocked` | `multiple_matching_transitions` |
| 同一 Subject（主体）写锁超时 | `lock_timeout` | `blocked` | `lock_timeout` |
| Runtime（运行时）自身错误 | `error` | `blocked` | 运行时错误码 |

状态写入必须按 `subject-key-hash` 加锁。同一 Subject（主体）串行写入，不同 Subject（主体）可以并发。锁超时必须写 `audit.json`，返回 `status=lock_timeout`，并且不得推进状态。
