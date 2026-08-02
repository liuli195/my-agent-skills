# Agent Guard Plugin Runtime 与会话焦点 PRD

状态：草案

关联 Issue：

- GitHub Issue [#14](https://github.com/liuli195/my-agent-skills/issues/14)：支持 Guard Instance 在 Subject Key 升级时继承状态
- GitHub Issue [#17](https://github.com/liuli195/my-agent-skills/issues/17)：支持 Claude Code 生命周期 hook
- GitHub Issue [#19](https://github.com/liuli195/my-agent-skills/issues/19)：把 Agent Guard 技能打包为 Claude 和 Codex 插件

关联决策：

- ADR [0002 Agent Guard Plugin Runtime 与会话焦点](../adr/0002-agent-guard-plugin-runtime-session-focus.md)

## Problem Statement

用户希望 Agent Guard（代理守卫）升级为 Plugin-first（插件优先）架构，让通用 Runtime code（运行时代码）和 lifecycle Hook（生命周期钩子）随 Plugin（插件）安装，避免每个项目重复复制和维护没有业务语义的运行时代码。

现有实现把 Runtime（运行时）、Hook（钩子）、Guard Profile（守卫画像）、Subject Resolver（主体解析器）和 Git Hook（Git 钩子）混在同一套安装与匹配模型里，导致以下问题：

- Hook（钩子）安装需要知道具体 Guard Profile（守卫画像）。
- Subject Resolver（主体解析器）把实例匹配做成隐式推断，容易产生歧义。
- 多个活跃 Guard Instance（守卫实例）可能互相影响。
- Git Hook（Git 钩子）没有稳定 `session_id`，会把本次目标拖入额外匹配模型。
- Codex 和 Claude 的 Plugin（插件）启用状态、Hook（钩子）能力和 Runtime（运行时）行为需要一致表达。

第一版目标是更小、更清楚：只处理带 `session_id` 的 lifecycle Hook（生命周期钩子），只判断当前会话显式绑定的一个 Guard Instance（守卫实例）。

## Solution

Agent Guard（代理守卫）改为 Plugin-first（插件优先）方案：

- Plugin（插件）发布通用 Runtime code（运行时代码）、Hook Adapter（钩子适配器）、Hook Router（钩子路由器）和入口 Skill（技能）。
- Plugin Installer（插件安装器）负责把仓库内 Plugin（插件）源码安装或链接到 Codex / Claude 可加载位置，并验证插件清单、Skill（技能）、Hook（钩子）和 Runtime（运行时）入口可用。
- 项目级和用户级只保存 Guard Profile（守卫画像）与运行态数据，不再复制 Runtime code（运行时代码）。
- Codex 和 Claude 第一版只安装 `SessionStart` 和 `PreToolUse` lifecycle Hook（生命周期钩子）。
- `SessionStart` 写 Session Observation（会话观察记录），用于识别当前 `source + session_id + cwd`。
- `PreToolUse` 通过 Session Focus Binding（会话焦点绑定）找到当前 Guard Instance（守卫实例），并执行当前状态下的规则。
- 激活时用户显式选择 Guarded Target（被守卫目标）和 Guard Instance（守卫实例），再写 Session Focus Binding（会话焦点绑定）。
- 删除 Subject Resolver（主体解析器）、Hook Binding（钩子绑定）、`subject_key_hash` 身份模型和 Git Hook（Git 钩子）。
- Guard Point（守卫点）不绑定 Hook（钩子）；它由当前 Guard Instance（守卫实例）的状态触发评估。

## User Stories

1. 作为用户，我希望安装 Plugin（插件）后自动拥有通用 Runtime（运行时），以便不在每个仓库复制无业务语义的运行时代码。
2. 作为用户，我希望 Plugin（插件）只安装第一版真正需要的 lifecycle Hook（生命周期钩子），以便安装行为简单可预测。
3. 作为用户，我希望不再安装 Git Hook（Git 钩子），以便避免无 `session_id` 的复杂匹配。
4. 作为用户，我希望 Hook（钩子）安装不绑定 Guard Profile（守卫画像），以便一次安装后能服务多个画像。
5. 作为用户，我希望 Plugin（插件）安装默认先展示 dry-run（试运行）计划，以便明确会写入或链接哪些用户级插件位置。
6. 作为用户，我希望安装 Codex 和 Claude Plugin（插件）需要明确授权，以便不会意外修改用户环境。
7. 作为用户，我希望插件安装后能验证 `SessionStart` 和 `PreToolUse` 已注册，以便知道 Hook（钩子）能力可用。
8. 作为用户，我希望 Guard Profile（守卫画像）继续由调研生成，以便业务语义仍然来自明确确认。
9. 作为用户，我希望业务规则只写在 Guard Profile（守卫画像），以便 Runtime（运行时）和 Hook（钩子）保持通用。
10. 作为用户，我希望激活守卫时先选择 Guarded Target（被守卫目标），以便清楚知道当前要守卫什么。
11. 作为用户，我希望 Guarded Target（被守卫目标）是稳定对象，以便不把具体 Issue 当成目标。
12. 作为用户，我希望具体上下文写入 Guard Instance（守卫实例）说明，以便区分同一目标下的多次运行。
13. 作为用户，我希望可以从已有 active Guard Instance（活跃守卫实例）中选择继续，以便恢复之前的流程。
14. 作为用户，我希望可以创建新 Guard Instance（守卫实例），以便开启新的独立流程。
15. 作为用户，我希望新实例标题和说明由主 agent（主代理）生成草稿并让我确认，以便减少输入负担又保留控制权。
16. 作为用户，我希望激活选择用表格展示，以便清楚比较目标和实例。
17. 作为用户，我希望一个会话只能绑定一个 Session Focus Instance（会话焦点实例），以便避免多个流程互相干扰。
18. 作为用户，我希望中途可以切换 Session Focus Instance（会话焦点实例），以便当前对话转向另一个流程。
19. 作为用户，我希望切换焦点时旧实例不自动关闭，以便之后还能继续该流程。
20. 作为用户，我希望可以关闭 Guard Instance（守卫实例），以便旧流程自然退出 Hook（钩子）判断。
21. 作为用户，我希望实例只区分 active（活跃）和 closed（关闭），以便生命周期模型保持简单。
22. 作为用户，我希望实例 ID 不带业务语义，以便不依赖隐式主体匹配。
23. 作为用户，我希望删除 Subject Resolver（主体解析器），以便实例选择完全显式。
24. 作为用户，我希望不存在 Session Focus Binding（会话焦点绑定）时 Hook（钩子）放行并审计，以便未激活守卫不会误阻断。
25. 作为用户，我希望绑定损坏时 Hook（钩子）拒绝并审计，以便运行态损坏不会被忽略。
26. 作为用户，我希望多个焦点绑定冲突时 Hook（钩子）拒绝并审计，以便同一会话焦点冲突能被发现。
27. 作为用户，我希望绑定指向 closed（关闭）实例时按无焦点处理，以便关闭实例自然失效。
28. 作为用户，我希望 Codex 和 Claude 在 `SessionStart`、`PreToolUse` 上使用同一标准事件，以便第一版两端行为一致。
29. 作为用户，我希望 Hook Adapter（钩子适配器）统一提取 `session_id`，以便 Runtime Router（运行时路由器）不关心平台 payload（载荷）差异。
30. 作为用户，我希望 `state_completed`（状态完成）必须有会话焦点实例，以便状态推进不会误改其他实例。
31. 作为用户，我希望 `state_completed`（状态完成）不允许指定画像或实例，以便只能推进当前会话焦点。
32. 作为用户，我希望 Runtime（运行时）和 Guard Profile（守卫画像）通过接口版本兼容，以便 Plugin（插件）升级不误解释旧画像。
33. 作为维护者，我希望源码布局和安装布局分离，以便仓库可以维护多个 Plugin（插件）源码。
34. 作为维护者，我希望 Hook Router（钩子路由器）不接收画像参数，以便彻底删除 Hook Binding（钩子绑定）。
35. 作为维护者，我希望测试覆盖 Codex 和 Claude 的 `SessionStart`、`PreToolUse` payload（载荷）转换，以便证明 `session_id` 可用。
36. 作为维护者，我希望测试覆盖无绑定、坏绑定、多绑定、closed 实例等边界，以便会话焦点行为稳定。

## Implementation Decisions

- Plugin（插件）成为 Runtime code（运行时代码）和 lifecycle Hook（生命周期钩子）的发布单元。
- 源码布局和安装布局分离：仓库内维护 Plugin（插件）源码目录，安装后目录必须符合 Codex / Claude 官方插件根目录约定。
- Plugin Installer（插件安装器）负责 dry-run（试运行）、授权安装、更新和验证 Codex / Claude 本地插件，不负责生成 Guard Profile（守卫画像）。
- Plugin Installer（插件安装器）不得写目标项目 Hook（钩子）或目标项目 Git 配置。
- Guard Profile（守卫画像）和运行态数据仍存放在用户级或项目级位置；Runtime code（运行时代码）不再复制到目标项目。
- 第一版 lifecycle Hook（生命周期钩子）固定为 `SessionStart` 和 `PreToolUse`。
- Hook Router（钩子路由器）必须 profile-agnostic（画像无关）：不接收画像参数，不读取 Hook Binding（钩子绑定），不在 Hook（钩子）层选择 Guard Profile（守卫画像）。
- Guard Instance（守卫实例）使用 opaque ID（不透明 ID），状态只允许 active（活跃）和 closed（关闭）。
- Session Observation（会话观察记录）由 `SessionStart` 写入，用于激活流程识别当前会话；它是事实记录，不是焦点绑定。
- Session Focus Binding（会话焦点绑定）只保存当前会话焦点引用，不复制实例标题和说明。
- Session Focus Binding（会话焦点绑定）查找顺序为 project-first（项目优先）；只有焦点绑定多处存在才算冲突。
- 激活流程分两步：先选择 Guarded Target（被守卫目标），再选择或创建 Guard Instance（守卫实例）。
- 用户可见激活输出必须使用表格模板，目标列表按 project（项目级）优先展示。
- Runtime Router（运行时路由器）只通过 Session Focus Binding（会话焦点绑定）找实例，不做主体推断。
- `state_completed`（状态完成）入口由 `$agent-guard-run` 提供，只能推进当前 Session Focus Instance（会话焦点实例）。
- Guard Point（守卫点）不绑定 Hook（钩子），只由当前 Guard Instance（守卫实例）的状态触发评估。
- 本次实现不提供旧契约迁移或兼容层。
- `runtime_api_version`（运行时接口版本）进入 Guard Profile（守卫画像）兼容检查；不兼容时不能误阻断。
- 同一 Guard Instance（守卫实例）的状态推进必须加锁，避免并发写坏状态。

## Testing Decisions

- 测试只验证外部行为，不测试内部函数实现细节。
- Plugin Installer（插件安装器）测试覆盖 dry-run（试运行）、授权安装、验证、重复安装和不写目标项目 Hook（钩子）。
- Hook Adapter（钩子适配器）测试覆盖 Codex 和 Claude 的 `SessionStart`、`PreToolUse` payload（载荷）到标准事件的转换。
- Session Observation Store（会话观察存储）测试覆盖记录写入、project-first（项目优先）读取和无记录中止。
- Session Focus Store（会话焦点存储）测试覆盖无绑定、单个有效绑定、多绑定、损坏绑定、缺字段、实例不存在和 closed 实例。
- Activation Service（激活服务）测试覆盖表格输出、选择已有实例、创建新实例、切换焦点和关闭实例。
- Runtime Router（运行时路由器）测试覆盖无焦点放行、绑定损坏拒绝、多绑定拒绝、有效焦点按状态判断。
- State Transition Service（状态推进服务）测试覆盖无焦点中止、禁止指定画像或实例、有效焦点推进和并发锁。
- Profile Validator（画像校验器）测试覆盖 Subject Resolver（主体解析器）和 Hook Binding（钩子绑定）删除后的新契约。
- Plugin 安装验证测试覆盖只安装 `SessionStart`、`PreToolUse`，不写 Git Hook（Git 钩子），不复制项目级 Runtime code（运行时代码）。
- 旧 `subject_key_hash`、`subject-resolver.yaml`、Git Hook（Git 钩子）安装强绑定的测试需要重写或删除，不新增旧输出兼容测试。

## Out of Scope

- Git Hook（Git 钩子）安装与执行。
- `pre-commit` 和 `pre-push`。
- 无 `session_id` 的 Hook（钩子）。
- `UserPromptSubmit`、`PostToolUse`、`SubagentStart`、`SubagentStop`。
- Subject Resolver（主体解析器）。
- Hook Binding（钩子绑定）。
- 通过 repo（仓库）、branch（分支）、PR 或 task id（任务 ID）自动匹配实例。
- Claude `PermissionRequest`。
- 长期仓库级守卫。
- 发布到外部 marketplace（市场）。
- 旧 `subject_key_hash` 状态迁移。
- 旧脚本输出兼容层。

## Further Notes

- 本 PRD（产品需求文档）同时覆盖 Issue #14、#17 和 #19，优先服务“先把 Plugin Runtime（插件运行时）、lifecycle Hook（生命周期钩子）和 Session Focus Instance（会话焦点实例）跑通”。
- 当前方案由 ADR [0002 Agent Guard Plugin Runtime 与会话焦点](../adr/0002-agent-guard-plugin-runtime-session-focus.md) 记录替代决策。
- 既有 `agent-guard` 大 PRD 中 Subject Resolver（主体解析器）、Git Hook（Git 钩子）和项目级 Runtime code（运行时代码）复制策略后续只做删除或重写，不做兼容迁移。
- 技术调研结论：Codex 和 Claude Code lifecycle Hook（生命周期钩子）payload（载荷）都包含 `session_id`，可作为本方案的会话绑定依据。
