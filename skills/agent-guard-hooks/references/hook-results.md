# Hook Results（钩子结果）

Hook（钩子）返回是否拒绝由 Runtime（运行时）结果决定。

## 结果处理

- Runtime（运行时）返回 `allow` 时，Hook（钩子）允许外部动作继续。
- Runtime（运行时）返回 `ask` 时，Hook（钩子）提示需要用户确认；具体交互由主 agent（主代理）处理。
- Runtime（运行时）返回 `deny` 时，支持拒绝的 Hook（钩子）必须拒绝外部动作。
- Runtime（运行时）返回 `no_session_focus_instance` 时，Hook（钩子）允许外部动作继续，并保留审计。
- Runtime（运行时）返回 `missing_session_id` 时，Hook（钩子）按 `error` 处理，不进入 Session Focus Binding（会话焦点绑定）判断。

Hook（钩子）没有额外 blocking（阻塞）开关。是否拒绝只由当前状态的 `permissions` 和 Runtime（运行时）返回结果决定。

## 禁止行为

- Hook（钩子）不写业务规则。
- Hook（钩子）不维护每个流程的专用权限表。
- Hook（钩子）不创建 Guard Instance（守卫实例）。
- Hook（钩子）不推进状态。
- Hook（钩子）不负责发现缺失实例；缺失实例不被视为 Hook（钩子）违规。
