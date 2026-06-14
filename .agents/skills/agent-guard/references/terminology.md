# Terminology（术语）

本文定义 `agent-guard` 使用的核心术语。不要把这些词替换成临时说法。

- Agent Guard（代理守卫）：旁路守卫系统。它观察、校验、记录 agent（代理）执行过程，必要时按 Guard Profile（守卫画像）拒绝不允许的操作。
- Guard Runtime（守卫运行时）：项目级或用户级运行时，只执行通用机制，例如事件标准化、实例解析、状态机、守卫点、审计和 Guard Brief（守卫简报）。
- Guard Profile（守卫画像）：描述被守卫对象、Subject Resolver（主体解析器）、状态机、守卫点、产物、Hook Binding（钩子绑定）和 Guard Brief（守卫简报）模板。
- Guard Instance（守卫实例）：某个 Guard Profile（守卫画像）在一个具体 Subject（主体）上的运行上下文。权限拒绝必须绑定到明确实例。
- Subject（主体）：一次被守卫的具体对象，例如某个任务、流程、分支、外部请求或会话。
- Subject Key（主体键）：由 Guard Profile（守卫画像）的 Subject Resolver（主体解析器）计算出的稳定身份键。Runtime（运行时）不替画像猜默认身份。
- subject-key-hash（主体键哈希）：Subject Key（主体键）的 hash（哈希），用于状态目录名，避免把完整身份塞进路径。
- Subject Resolver（主体解析器）：画像内的身份解析规则，声明身份字段、必需字段、匹配策略、创建策略和歧义策略。
- 标准事件：Hook（钩子）、command（命令）或人工输入被 adapter（适配器）转成的统一事件 envelope（信封）。画像只依赖标准事件字段。
- 状态机：画像内的状态和转换规则。Runtime（运行时）只按配置执行，不写业务状态。
- 守卫点：某个事件或转换上的校验。守卫点失败会阻止状态推进，但不定义额外模式。
- 产物：守卫读取或生成的文件、日志、快照、报告、人工确认或外部记录。
- Hook Binding（钩子绑定）：把 Codex Hook（Codex 钩子）、Git Hook（Git 钩子）、人工事件或其他来源映射到标准事件和转换。Hook（钩子）内不写业务规则。
- Guard Brief（守卫简报）：给 agent（代理）的短简报，说明当前状态、允许下一步、禁止下一步、缺失产物、最近拒绝原因、下一步建议和审计位置。
- Guard Injection（守卫注入）：把 latest Guard Brief（最新守卫简报）注入给 agent（代理）的机制。注入要按 `brief_hash` 去重。
- 运行审计：每次守卫运行的记录，包含事件、实例、状态、守卫点结果、产物引用和返回结果。
- 权限结果：当前状态权限评估的结果，只能是 `allow`、`ask` 或 `deny`。
- `allow`：允许当前操作继续。
- `ask`：要求主 agent（主代理）取得用户明确确认后重试同一操作。
- `deny`：拒绝当前操作继续。
- 人工覆盖：用户显式授权的临时放行记录，必须有范围和过期时间。
