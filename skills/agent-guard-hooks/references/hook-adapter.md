# Hook Adapter（钩子适配器）

Hook Adapter（钩子适配器）只做格式转换和 Runtime（运行时）调用。具体业务判断放在 Guard Profile（守卫画像）的 state machine（状态机）、permissions（权限规则）和 guard points（守卫点）。

## 支持来源

第一版 adapter（适配器）支持：

- `codex`：读取 Codex lifecycle hook（Codex 生命周期钩子）payload（载荷），只覆盖 `SessionStart` 和 `PreToolUse`。
- `claude`：读取 Claude lifecycle hook（Claude 生命周期钩子）payload（载荷），只覆盖 `SessionStart` 和 `PreToolUse`。

其他 Hook（钩子）不属于第一版安装入口，避免过早扩大 Hook（钩子）行为面。

## 标准事件

标准事件必填字段：

- `source`
- `event_type`
- `context`
- `payload`

标准事件可选字段：

- `tool`
- `action`
- `hook`
- `raw_event_summary`

工具调用类事件必须保留工具名、工具输入、命令、路径和原始摘要，供 Runtime（运行时）按当前状态 `permissions` 判断。

Hook（钩子）事件只用于会话观察、权限评估、审计和提示，不推进状态。adapter（适配器）不得把 Codex 或 Claude Hook（钩子）直接映射成 `state_completed`。
