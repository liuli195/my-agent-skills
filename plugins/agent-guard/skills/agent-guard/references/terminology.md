# Terminology（术语）

本文定义 `agent-guard` 使用的核心术语。不要把这些词替换成临时说法。

- Agent Guard（代理守卫）：旁路守卫系统。它观察、校验、记录 agent（代理）执行过程，必要时按 Guard Profile（守卫画像）拒绝不允许的操作。
- Agent Guard Plugin（代理守卫插件）：发布通用 Runtime code（运行时代码）、Hook Router（钩子路由器）、Hook Adapter（钩子适配器）、lifecycle Hook（生命周期钩子）和入口 Skill（技能）的插件包。
- Guard Runtime（守卫运行时）：由 Plugin（插件）发布的通用机制，例如事件标准化、Session Focus Binding（会话焦点绑定）、状态机、守卫点、权限判断和审计。
- Guard Profile（守卫画像）：描述 Guarded Target（被守卫目标）、状态机、权限规则、守卫点、产物、模板和 `runtime_api_version`（运行时接口版本）。
- Guarded Target（被守卫目标）：稳定的被守卫对象，例如一个 Skill（技能）或 workflow（工作流），不应是一条具体 Issue（问题）或一次性上下文。
- Guard Instance（守卫实例）：某个 Guard Profile（守卫画像）下的一次明确运行上下文，使用 opaque `instance_id`（不透明实例 ID），状态只允许 `active` 或 `closed`。
- Session Observation（会话观察记录）：`SessionStart` Hook（会话启动钩子）写入的事实记录，用于识别当前 `source + session_id + cwd`。
- Session Focus Binding（会话焦点绑定）：当前会话显式绑定的唯一 `profile_id + instance_id` 引用。
- 标准事件：Hook（钩子）、command（命令）或人工输入被 adapter（适配器）转成的统一事件 envelope（信封）。画像只依赖标准事件字段。
- 状态机：画像内的状态和转换规则。Runtime（运行时）只按配置执行，不写业务状态。
- 守卫点：某个事件或转换上的校验。守卫点失败会阻止状态推进，但不定义额外模式。
- 产物：守卫读取或生成的文件、日志、快照、报告、人工确认或外部记录。
- 运行审计：每次守卫运行的记录，包含事件、实例、状态、守卫点结果、产物引用和返回结果。
- 权限结果：当前状态权限评估的结果，只能是 `allow`、`ask` 或 `deny`。
- `allow`：允许当前操作继续。
- `ask`：要求主 agent（主代理）取得用户明确确认后重试同一操作。
- `deny`：拒绝当前操作继续。
- 人工覆盖：用户显式授权的临时放行记录，必须有范围和过期时间。
