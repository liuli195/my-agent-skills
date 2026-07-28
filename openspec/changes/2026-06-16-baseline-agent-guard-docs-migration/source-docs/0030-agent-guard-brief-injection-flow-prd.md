# Agent Guard Guard Brief 与注入流程 PRD

状态：草案

来源：

- GitHub Issue [#21](https://github.com/liuli195/my-agent-skills/issues/21)
- 本地对话确认：Guard Brief（守卫简报）是状态推进核心机制，不能因删除 `subject_key_hash` 旧身份路径而删除。
- ADR：[0002 Agent Guard Plugin Runtime 与会话焦点](../adr/0002-agent-guard-plugin-runtime-session-focus.md)
- 技术方案：[Agent Guard Guard Brief 与注入流程技术方案](../designs/0030-agent-guard-brief-injection-flow.md)

## Problem Statement

用户需要 Agent Guard（代理守卫）在 Plugin-first（插件优先）和 Session Focus（会话焦点）架构下继续保留 Guard Brief（守卫简报）能力。

Guard Brief（守卫简报）不是旧 Subject Resolver（主体解析器）模型的一部分，而是状态推进的人机接口。它告诉主 agent（主代理）当前状态、下一步推荐、禁止事项、缺失产物、最近拒绝原因和审计位置。如果删除 `subject_key_hash` 时误删简报机制，agent 就只能依赖会话记忆或焦点绑定推进状态，容易跳过完成条件、错过拒绝原因或误推进实例。

当前需求是把最新简报流程、注入语义、发版验收和测试点单独落文档，方便后续 review（审查）和测试。

## Solution

Guard Brief（守卫简报）保留为状态推进前的权威读取面，但身份定位从 `subject_key_hash` 迁移为 Session Focus Instance（会话焦点实例）。

业务流程采用 pull-to-inject（读取触发注入）：

1. Runtime（运行时）在激活、状态推进成功、状态推进失败、权限拒绝或 ask（请求确认）后刷新 latest Guard Brief（最新守卫简报）。
2. 主 agent（主代理）进入守卫流程或提交 `state_completed` 前，主动读取当前 Session Focus Instance（会话焦点实例）的 latest Guard Brief。
3. Runtime（运行时）解析 `source + session_id` 对应的 Session Focus Binding（会话焦点绑定），找到唯一 `profile_id + instance_id`。
4. Runtime（运行时）返回可注入的简报 payload（载荷），并按 `brief_hash` 记录注入去重。
5. 同一 `source + session_id + profile_id + instance_id` 内，如果 `brief_hash` 没变，返回 `already_injected`，不重复注入。
6. 如果状态、缺失产物、拒绝原因或完成条件变化，`brief_hash` 变化，下一次读取返回新的 `injectable` 简报。

第一版不做后台主动推送。守卫维护最新简报，agent 主动读取，Runtime 负责生成、校验来源和去重记录。

## User Stories

1. 作为用户，我希望删除 `subject_key_hash` 后仍保留 Guard Brief（守卫简报），以便状态推进仍有清楚的当前状态说明。
2. 作为用户，我希望激活守卫后立即生成最新简报，以便 agent 开始工作前知道当前状态和下一步。
3. 作为用户，我希望状态推进前必须读取最新简报，以便 agent 不依赖过期会话记忆推进状态。
4. 作为用户，我希望状态推进成功后刷新简报，以便下一步推荐跟随新状态变化。
5. 作为用户，我希望状态推进失败后刷新简报，以便知道缺少哪些产物或为什么不能过。
6. 作为用户，我希望权限拒绝或 ask 后刷新简报，以便拒绝原因能进入下一次状态推荐。
7. 作为用户，我希望简报只针对当前 Session Focus Instance（会话焦点实例），以便多个活跃实例不会互相污染。
8. 作为用户，我希望简报路径使用 `profile_id + instance_id`，以便不再依赖旧主体解析模型。
9. 作为用户，我希望同一会话中相同简报不重复注入，以便节省上下文并避免噪声。
10. 作为用户，我希望简报变化后能重新注入，以便 agent 收到最新状态推荐。
11. 作为用户，我希望终止状态下的简报不提示继续推进，以便完成后的流程不会误导 agent。
12. 作为用户，我希望简报内容只能来自 Runtime（运行时）生成的 latest brief（最新简报），以便避免手写简报和状态机漂移。
13. 作为用户，我希望没有会话焦点时读取简报失败并提示先激活，以便不会误读其他实例。
14. 作为用户，我希望多个焦点绑定冲突时读取简报失败，以便暴露运行态异常。
15. 作为用户，我希望 `$agent-guard-run` 明确写入“提交 `state_completed` 前读取简报”，以便执行入口不能绕过核心机制。
16. 作为维护者，我希望技术方案列出路径、命令、payload 字段和错误状态，以便 review 时能逐项核对。
17. 作为维护者，我希望测试覆盖激活生成、主动读取、注入去重和状态推进刷新，以便防止后续误删简报机制。
18. 作为维护者，我希望文档明确当前不是后台主动推送，以便后续讨论 hook 注入时有清楚边界。

## Implementation Decisions

- Guard Brief（守卫简报）和 Guard Injection（守卫注入）是状态推进核心机制，必须保留。
- 删除范围只包含 Subject Resolver（主体解析器）、`subject_key_hash` 身份路径和旧简报路径，不包含简报机制本身。
- 简报身份粒度为 `profile_id + instance_id`。
- 会话粒度为 `source + session_id`。
- 注入去重粒度为 `source + session_id + profile_id + instance_id`。
- 去重依据为 `brief_hash`。
- latest brief（最新简报）由 Runtime（运行时）生成和刷新。
- 主 agent（主代理）通过 `$agent-guard-run` 或辅助脚本主动读取 latest brief。
- Runtime（运行时）读取简报时必须先解析 Session Focus Binding（会话焦点绑定），不得由调用方指定 `profile_id` 或 `instance_id` 绕过焦点。
- `state_completed` 前读取 latest brief 是硬规则。
- Runtime（运行时）执行 `state_completed` 前必须确认当前 `brief_hash` 已经通过 brief（简报）入口读取并记录；未读取时返回 `brief_required`，不得推进状态。
- 终止状态下的简报只提示流程已完成和审计位置，不提示继续提交 `state_completed`。
- 当前版本不实现后台主动注入当前 Codex / Claude 会话上下文。

## Testing Decisions

- 测试只验证外部行为，不绑定内部函数实现细节。
- Activation Service（激活服务）测试必须覆盖激活后写入 latest brief。
- Brief CLI（简报命令）测试必须覆盖读取当前 Session Focus Instance（会话焦点实例）。
- Skill wrapper（技能包装脚本）测试必须覆盖 `render_guard_brief.py` 委托 Plugin Runtime（插件运行时）。
- Injection Store（注入记录）测试必须覆盖同一 session（会话）相同 `brief_hash` 返回 `already_injected`。
- State Transition Service（状态推进服务）测试必须覆盖未读取当前 `brief_hash` 时返回 `brief_required` 且不推进状态。
- State Transition Service（状态推进服务）测试必须覆盖推进成功后 latest brief 的状态和 `brief_hash` 变化。
- 失败路径测试必须覆盖无焦点、多焦点、坏焦点、缺失产物和权限拒绝刷新简报。
- 文档 review（审查）必须确认 active docs（活跃文档）没有把 Guard Brief（守卫简报）描述成已删除能力。

## Out of Scope

- 后台主动推送 Guard Brief（守卫简报）到当前会话上下文。
- 无 `session_id` 的 Hook（钩子）简报注入。
- Git Hook（Git 钩子）注入。
- 旧 `subject_key_hash` 简报路径兼容读取。
- 旧运行态迁移。
- 多实例自动合并简报。
- 让 Hook（钩子）推进状态。

## Further Notes

- 当前流程是 pull-to-inject（读取触发注入），不是 push injection（主动推送注入）。
- Session Focus Binding（会话焦点绑定）只回答“当前会话指向哪个实例”；Guard Brief（守卫简报）回答“这个实例当前该做什么、缺什么、能不能推进”。
- 后续如果要做后台主动注入，需要单独 PRD，并明确 Codex / Claude 是否提供稳定的会话上下文注入入口。
