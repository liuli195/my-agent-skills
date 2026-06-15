# 0002 Agent Guard Plugin Runtime 与会话焦点

状态：已接受

日期：2026-06-15

关联：

- GitHub Issue [#14](https://github.com/liuli195/my-agent-skills/issues/14)
- GitHub Issue [#17](https://github.com/liuli195/my-agent-skills/issues/17)
- GitHub Issue [#19](https://github.com/liuli195/my-agent-skills/issues/19)
- PRD：[Agent Guard Plugin Runtime 与会话焦点 PRD](../prd/0017-agent-guard-plugin-runtime-session-focus-prd.md)
- 技术方案：[Agent Guard Plugin Runtime 与会话焦点技术实现方案](../designs/0017-agent-guard-plugin-runtime-session-focus.md)

## 决策

Agent Guard（代理守卫）第一版采用 Plugin-first（插件优先）架构。通用 Runtime code（运行时代码）、Hook Adapter（钩子适配器）、lifecycle Hook（生命周期钩子）和入口 Skill（技能）由 Plugin（插件）发布；项目级和用户级只保存 Guard Profile（守卫画像）与运行态数据。

源码布局和安装布局分离。本仓库用 `plugins/` 维护 Plugin（插件）源码，最终安装目录必须符合 Codex / Claude 官方插件根目录约定。

第一版只保留有明确用途的带 `session_id` lifecycle Hook（生命周期钩子）：`SessionStart` 用于识别会话，`PreToolUse` 用于执行前检查。不安装 Git Hook（Git 钩子），不处理无 `session_id` 的 Hook（钩子），不接入 Claude `PermissionRequest`。

删除 Subject Resolver（主体解析器）和 `subject_key_hash` 身份模型。Guard Instance（守卫实例）使用 opaque `instance_id`（不透明实例 ID），并通过显式 Session Focus Binding（会话焦点绑定）绑定到当前会话。焦点查找采用 project-first（项目优先）。

激活流程通过 `SessionStart` Hook（会话启动钩子）记录的 Session Observation（会话观察记录）识别当前会话；交互选择仍由主 agent（主代理）在对话中完成。

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
- 新业务画像必须来自已确认的 `$grill-with-docs`（带文档拷问方法）调研记录。

## 原因

项目级复制 Runtime code（运行时代码）会带来升级和版本漂移成本。Plugin-first（插件优先）让通用机制集中发布，项目级只保留业务语义和运行态。

Subject Resolver（主体解析器）让实例匹配依赖隐式推断。显式会话焦点更小、更清楚，也能避免多个活跃实例互相影响。

Git Hook（Git 钩子）缺少稳定 `session_id`，会把第一版拖回 repo（仓库）、branch（分支）或 PR 等额外匹配模型。第一版先只处理 Codex 和 Claude 都能提供 `session_id` 的生命周期事件。

未确认用途的 Hook（钩子）不进入第一版，避免增加运行噪声和维护面。

## 后果

- 旧 PRD、Skill 入口、模板、校验器和测试中与旧契约强绑定的内容需要删除或重写。
- 初始化和升级逻辑不再向目标项目复制 Runtime code（运行时代码）。
- Runtime Router（运行时路由器）不做主体推断，只按 Session Focus Binding（会话焦点绑定）处理当前实例。
- 详细路径、错误码、测试矩阵和交互模板以 PRD 与技术方案为准。
