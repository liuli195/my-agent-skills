# Hook Contract（钩子契约）

Hook（钩子）的职责是捕获事件、标准化事件、调用 Guard Runtime（守卫运行时）。Hook（钩子）不写业务规则，不直接判断流程是否合规。

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

该 adapter（适配器）支持：

- `codex`：读取 Codex lifecycle hook（Codex 生命周期钩子）payload（载荷），覆盖 `UserPromptSubmit`、`SubagentStart`、`SubagentStop`、`PreToolUse` 和 `PostToolUse`。
- `git-pre-push`：读取 Git pre-push（Git 推送前）标准输入，把 remote（远端）和 ref（引用）信息写入标准事件 envelope（信封）。

标准事件必填字段：

- `guard_profile_id`
- `event_id`
- `event_type`
- `source`
- `timestamp`
- `context`
- `payload`

标准事件可选字段：

- `tool`
- `action`
- `hook`
- `raw_event_summary`

adapter（适配器）只做格式转换和 Runtime（运行时）调用。具体业务判断必须由 Guard Profile（守卫画像）的 state machine（状态机）和 guard points（守卫点）完成。

adapter（适配器）会保留 payload（载荷）里的 `context` 扩展字段，例如 PR 编号、任务 ID 或外部对象 ID，供 Subject Resolver（主体解析器）读取。

adapter（适配器）默认用临时事件文件调用 Runtime（运行时），运行结束后删除该临时文件，避免 Hook（钩子）事件制造本地噪音。只有用户显式指定 `--out` 时，才会把标准事件 envelope（信封）持久化到指定路径。

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

`--authorize-install` 只授权安装 Hook（钩子）入口。默认安装为观察模式：即使 Runtime（运行时）返回 `block`，Hook（钩子）入口也返回 0，不阻断外部动作。

只有同时传入 `--authorize-blocking` 时，支持阻断的 Hook（钩子）入口才会返回 Runtime（运行时）的阻断码：

```powershell
python .agents\skills\agent-guard\scripts\install_hooks.py --project <target-project> --profile <guard-profile-id> --authorize-install --authorize-blocking
```

验证入口：

```powershell
python .agents\skills\agent-guard\scripts\install_hooks.py --project <target-project> --profile <guard-profile-id> --verify
```

安装 Hook（钩子）必须有用户明确授权。启用 blocking mode（阻断模式）也必须有用户明确授权。
