# Hook Contract（钩子契约）

Hook（钩子）的职责是捕获事件、标准化事件、调用 Guard Runtime（守卫运行时）。Hook（钩子）不写业务规则，不直接判断流程是否合规，也不维护每个流程的专用权限表。第一版 Hook（钩子）不检查主 agent（主代理）是否读取过 Guard Brief（守卫简报）。

按场景读取：

- 写 Hook Binding（钩子绑定）字段：读 `guard-profile.md`。
- 理解 adapter（适配器）输入输出：读“Hook Adapter（钩子适配器）”。
- 安装或验证 Hook（钩子）：读“安装入口”。

支持来源：

- Codex Lifecycle Hook（Codex 生命周期钩子）：观察用户输入、工具调用和子 agent（子代理）启停。
- Git Hook（Git 钩子）：在提交或推送前做兜底调用。
- manual source（人工来源）：用于样例、人工确认或调试。

## Hook Adapter（钩子适配器）

项目级安装后会复制：

```text
.agents/guard-runtime/hook_event_adapter.py
```

第一版 adapter（适配器）支持：

- `codex`：读取 Codex lifecycle hook（Codex 生命周期钩子）payload（载荷），覆盖 `UserPromptSubmit`、`SubagentStart`、`SubagentStop`、`PreToolUse` 和 `PostToolUse`。
- `git-pre-push`：读取 Git pre-push（Git 推送前）标准输入，把 remote（远端）和 ref（引用）信息写入标准事件 envelope（信封）。

后续扩展保留 `SessionStart`、`PreCompact`、`Stop` 和 Git `pre-commit`。这些事件不属于第一版安装入口，避免过早扩大 Hook（钩子）行为面。

标准事件必填字段：

- `guard_profile_id`
- `event_id`
- `event_type`
- `source`
- `timestamp`
- `context`
- `subject`
- `payload`

标准事件可选字段：

- `tool`
- `action`
- `hook`
- `raw_event_summary`

adapter（适配器）只做格式转换和 Runtime（运行时）调用。具体业务判断必须由 Guard Profile（守卫画像）的 state machine（状态机）和 guard points（守卫点）完成。工具调用类事件必须保留工具名、工具输入、命令、路径和原始摘要，让 Runtime（运行时）可以按当前状态的 `permissions` 字段判断。

Hook（钩子）事件只用于权限评估、审计和提示，不推进状态。Hook（钩子）不得把“权限允许”解释成“状态已完成”，也不得在 Hook 内推进状态。状态推进只能由主 agent（主代理）主动调用 Runtime（运行时）提交标准事件完成。

Hook（钩子）无法解析到唯一 Guard Instance（守卫实例）时，必须忽略该事件：不拒绝、不提示、不写审计。Hook（钩子）不得自行猜 Subject（主体）、创建实例或负责检查实例是否存在。Guard Instance（守卫实例）只能由主 agent（主代理）显式 activate（激活）创建。

adapter（适配器）会保留 payload（载荷）里的 `context` 扩展字段，例如 PR 编号、任务 ID 或外部对象 ID，供 Subject Resolver（主体解析器）读取。

adapter（适配器）默认用临时事件文件调用 Runtime（运行时），运行结束后删除该临时文件，避免 Hook（钩子）事件制造本地噪音。只有用户显式指定 `--out` 时，才会把标准事件 envelope（信封）持久化到指定路径。

Hook（钩子）返回是否拒绝由 Runtime（运行时）结果决定。当前状态权限返回 `deny` 时，支持拒绝的 Hook（钩子）必须拒绝外部动作。不存在额外开关。

## 安装入口

安装入口：

```powershell
python .agents\skills\agent-guard\scripts\install_hooks.py --project <target-project> --profile <guard-profile-id>
```

默认 dry-run（试运行），只输出：

- 将创建或修改的文件。
- Runtime（运行时）调用命令。
- Hook Binding（钩子绑定）摘要。
- 回滚说明。
- 风险提示。

只有显式传入 `--authorize-install` 时才会写入：

- `.agents/guard-runtime/hook_event_adapter.py`
- `.codex/hooks.json`
- `.githooks/pre-push`
- Git 仓库的 `core.hooksPath=.githooks`
- `.agents/guards/<guard-profile-id>/hook-install-plan.md`

`--authorize-install` 授权安装 Hook（钩子）入口，也授权已安装 Hook（钩子）按 Runtime（运行时）返回的 `deny` 拒绝外部动作。安装后，Hook（钩子）会把可见工具调用交给 Runtime（运行时）评估；Runtime（运行时）返回 `deny` 时，支持拒绝的 Hook（钩子）应返回拒绝码。

验证入口：

```powershell
python .agents\skills\agent-guard\scripts\install_hooks.py --project <target-project> --profile <guard-profile-id> --verify
```

安装 Hook（钩子）必须有用户明确授权。权限拒绝由当前状态的 `permissions` 决定，没有额外开关。
