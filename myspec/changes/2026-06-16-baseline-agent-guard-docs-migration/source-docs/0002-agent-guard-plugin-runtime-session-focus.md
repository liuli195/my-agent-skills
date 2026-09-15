# 0002 Agent Guard Plugin Runtime 与会话焦点

状态：已接受

日期：2026-06-15

关联：

- GitHub Issue [#14](https://github.com/liuli195/my-agent-skills/issues/14)
- GitHub Issue [#17](https://github.com/liuli195/my-agent-skills/issues/17)
- GitHub Issue [#19](https://github.com/liuli195/my-agent-skills/issues/19)
- GitHub Issue [#21](https://github.com/liuli195/my-agent-skills/issues/21)
- PRD：[Agent Guard Plugin Runtime 与会话焦点 PRD](../prd/0017-agent-guard-plugin-runtime-session-focus-prd.md)
- PRD：[Agent Guard Guard Brief 与注入流程 PRD](../prd/0030-agent-guard-brief-injection-flow-prd.md)
- 技术方案：[Agent Guard Plugin Runtime 与会话焦点技术实现方案](../designs/0017-agent-guard-plugin-runtime-session-focus.md)
- 技术方案：[Agent Guard Guard Brief 与注入流程技术方案](../designs/0030-agent-guard-brief-injection-flow.md)

## 决策

Agent Guard（代理守卫）第一版采用 Plugin-first（插件优先）架构。通用 Runtime code（运行时代码）、Hook Adapter（钩子适配器）、lifecycle Hook（生命周期钩子）和入口 Skill（技能）由 Plugin（插件）发布；项目级和用户级只保存 Guard Profile（守卫画像）与运行态数据。

源码布局和安装布局分离。本仓库用 `plugins/` 维护 Plugin（插件）源码，最终安装目录必须符合 Codex / Claude 官方插件根目录约定。

第一版只保留有明确用途的带 `session_id` lifecycle Hook（生命周期钩子）：`SessionStart` 用于识别会话，`PreToolUse` 用于执行前检查。不安装 Git Hook（Git 钩子），不处理无 `session_id` 的 Hook（钩子），不接入 Claude `PermissionRequest`。

删除 Subject Resolver（主体解析器）和 `subject_key_hash` 身份模型。Guard Instance（守卫实例）使用 opaque `instance_id`（不透明实例 ID），并通过显式 Session Focus Binding（会话焦点绑定）绑定到当前会话。焦点查找采用 project-first（项目优先）。

激活流程通过 `SessionStart` Hook（会话启动钩子）记录的 Session Observation（会话观察记录）识别当前会话；交互选择仍由主 agent（主代理）在对话中完成。

Guard Brief（守卫简报）和 Guard Injection（守卫注入）是状态推进的核心机制，必须保留。删除的是基于 Subject Resolver（主体解析器）和 `subject_key_hash` 的旧身份路径，不是删除简报或注入能力。新实现必须通过当前 Session Focus Binding（会话焦点绑定）解析 `profile_id + instance_id`，再生成、读取和注入当前实例的 Guard Brief（守卫简报）。

激活、状态推进、权限拒绝、守卫点失败和状态变化后，Runtime（运行时）必须刷新当前实例的 latest Guard Brief（最新守卫简报）。主 agent（主代理）提交 `state_completed` 前必须读取当前 Session Focus Instance（会话焦点实例）的最新 Guard Brief（守卫简报），不得只依赖焦点绑定存在本身。

Guard Brief（守卫简报）路径必须改为以 `profile_id + instance_id` 为粒度，例如 `.local/guard/latest/<profile_id>/<instance_id>/brief.json`。Guard Injection（守卫注入）去重仍使用 `brief_hash`，但记录粒度改为 `source + session_id + profile_id + instance_id`，不再使用 `subject_key_hash`。

Runtime（运行时）执行 `state_completed` 前必须确认当前 `brief_hash` 已经通过 brief（简报）入口读取并记录。未读取时返回 `brief_required`，不得推进状态。

本次实现不提供旧契约迁移或兼容层。旧状态只作为人工归档资料，不进入新 Runtime（运行时）读取路径。

本 ADR 替代 ADR 0001 中以下旧决策：

- 生成后的项目级 Runtime code（运行时代码）必须独立复制并运行。
- Git Hook（Git 钩子）作为第一版通用兜底。
- Guard Instance（守卫实例）由 Subject Resolver（主体解析器）和 Subject Key（主体键）匹配。

ADR 0001 中以下决策继续保留：

- 业务规则写入 Guard Profile（守卫画像）。
- Runtime（运行时）只执行通用机制，不写具体业务规则。
- Hook（钩子）只捕获和标准化事件，不推进状态。
- 权限拒绝必须来自明确 Guard Instance（守卫实例）。
- Guard Brief（守卫简报）仍是主 agent（主代理）理解当前状态、允许动作、禁止动作、缺失产物和下一步建议的权威读取面。
- 新业务画像必须来自已确认的 `$grill-with-docs`（带文档拷问方法）调研记录。

## 原因

项目级复制 Runtime code（运行时代码）会带来升级和版本漂移成本。Plugin-first（插件优先）让通用机制集中发布，项目级只保留业务语义和运行态。

Subject Resolver（主体解析器）让实例匹配依赖隐式推断。显式会话焦点更小、更清楚，也能避免多个活跃实例互相影响。

Guard Brief（守卫简报）不是旧 Subject Resolver（主体解析器）模型的一部分，而是状态推进的人机接口。Session Focus Binding（会话焦点绑定）只解决“当前会话指向哪个实例”，不能替代简报对当前状态、缺失产物、权限和下一步动作的表达。

Git Hook（Git 钩子）缺少稳定 `session_id`，会把第一版拖回 repo（仓库）、branch（分支）或 PR 等额外匹配模型。第一版先只处理 Codex 和 Claude 都能提供 `session_id` 的生命周期事件。

未确认用途的 Hook（钩子）不进入第一版，避免增加运行噪声和维护面。

## 后果

- 旧 PRD、Skill 入口、模板、校验器和测试中与旧契约强绑定的内容需要删除或重写。
- 初始化和升级逻辑不再向目标项目复制 Runtime code（运行时代码）。
- Runtime Router（运行时路由器）不做主体推断，只按 Session Focus Binding（会话焦点绑定）处理当前实例。
- 简报生成、latest brief（最新简报）、注入去重和相关测试需要从 `subject_key_hash` 迁移到 `instance_id`，不得删除。
- `$agent-guard-run` 入口必须保留“状态推进前读取最新 Guard Brief（守卫简报）”的执行要求。
- 详细路径、错误码、测试矩阵和交互模板以 PRD 与技术方案为准。
