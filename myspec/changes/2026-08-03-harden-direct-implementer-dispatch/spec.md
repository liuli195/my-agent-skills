# 修复直接可写 Implementer 派发并恢复受控 TDD

## Problem Statement

Issue #246 已经通过受控派发入口把 Implementer（实施者）的工作目录绑定到已有 Git worktree（Git 工作树），但主 Agent（代理）仍可绕过该入口直接调用 `Agent` 工具。直接调用路径没有工具级 `cwd`（工作目录）约束，可能把可写实施和验证产物落到主工作区。

同时，现有受控入口使用 `isolated:true`，虽然避免了扩展和 MCP（模型上下文协议）资源阻止外层 Pi（编码代理）退出，却也禁用了 Implementer 所需的 Skill（技能）。恢复资源时若重新加载全部扩展，会重新引入已确认的生命周期风险。

## Solution

为 `pi-development-flow` 增加直接 `Agent` 调用拦截：只允许 Explorer（探索者）、Reviewer（审查者）和 Architect（架构师）等只读角色直接调用；Implementer、未知角色、空角色以及所有带 `resume`（恢复）的直接调用必须停止，并指向 `dispatch_implementer_in_worktree`。

受控 Implementer 派发仍由工具验证非主工作树、分支和票据路径，并通过 RPC（远程调用）传入目标工作目录；仅将资源模式改为非 isolated。Implementer 的持久化角色配置明确关闭扩展、预加载 `tdd`（测试驱动开发）技能，并固定使用 `openai-codex/gpt-5.6-luna` 与 `max` 思考强度。

## User Stories

1. 作为开发流程使用者，我希望直接调用可写 Implementer 时立即得到阻断，以免绕过工作树绑定。
2. 作为开发流程使用者，我希望直接调用只读角色仍然可用，不扩大可写入口限制。
3. 作为开发流程使用者，我希望未知角色和恢复调用不能绕过可写派发边界。
4. 作为开发流程使用者，我希望受控 Implementer 继续只写入已验证的目标工作树。
5. 作为 Implementer，我希望在不加载扩展和 MCP 的情况下使用预加载的 TDD 技能。
6. 作为开发流程使用者，我希望 Implementer 使用固定的 Luna Max 配置，不静默继承主 Agent 模型。
7. 作为开发流程使用者，我希望 Implementer 按 TDD 的红灯、绿灯顺序实施功能、缺陷和集成行为。
8. 作为仓库维护者，我希望子代理完成后外层 Pi 进程正常退出，且主工作区没有缓存或运行产物副作用。
9. 作为维护者，我希望策略 Skill、角色配置、测试和正式规格使用同一组角色和模型契约。

## Implementation Decisions

- 直接调用拦截位于 `pi-development-flow` 扩展的 `tool_call` 接缝，不修改 Pi 本体或 `@tintinweb/pi-subagents`。
- 允许角色集合按角色名大小写不敏感匹配，仅包含 Explorer、Reviewer、Architect。
- `resume` 存在时优先阻断，无论其角色名是否属于只读集合。
- `dispatch_implementer_in_worktree` 仍是唯一受控可写派发接口；其 RPC 路径不触发直接 `Agent` 拦截。
- 受控派发使用 `isolated:false`，角色配置使用 `extensions:false` 和 `skills:tdd`，只恢复明确需要的 TDD 技能，不恢复其他扩展或 MCP。
- Implementer 角色固定使用 `openai-codex/gpt-5.6-luna`、`max`，并在提示词中要求使用 `/skill:tdd`；Pi 当前正式技能命令为 `/skill:tdd`，不创建 `/tdd` 别名。
- 更新 `pi-subagent-policy`（Pi 子代理策略）对四个持久化角色的模型和提示词契约，保持模型注册表和实际角色配置一致。
- 用户级 Implementer 配置属于本次明确请求的机器状态变更；修改前保存原文件，修改后逐项比较无关配置，并通过新 Pi 进程验证实际生效值。
- 已完成的 `2026-08-01-harden-pi-development-flow` 和 `2026-07-31-add-pi-subagent-policy` 变更不被改写；本变更作为后续规格覆盖其受影响的资源模式和 Implementer 契约。

## Testing Decisions

- 最高测试接缝是新 Pi 进程的真实 `Agent` 和 `dispatch_implementer_in_worktree` 用户入口；测试观察阻断结果、实际工作树、模型、技能、进程退出和副作用。
- 先在同一检查中写出直接 Implementer、未知角色、空角色和 `resume` 的失败检查，再加入拦截实现使其通过。
- 同一回归覆盖三个只读角色放行和 RPC 受控派发不被误拦截。
- 真实临时 Git 仓库同时建立主工作区和已有功能工作树；受控子代理写入标记、执行验证并产生已知运行产物，主工作区前后保持不变。
- 真实子代理必须报告或证实预加载 TDD，使用 Luna Max，并在完成后于限定时间内退出。
- 用户级配置修改前后保存并比较文件；不能证明恢复或无关字段保持不变时停止，不宣告完成。
- 使用仓库已有 Build and Verify（构建与验证）入口执行快速验证；高风险主路径另执行真实 Pi 冒烟和受影响的失败/恢复路径。

## Out of Scope

- 不修改 Pi 本体、Pi 安装目录或 `@tintinweb/pi-subagents` 源码。
- 不把权限插件改造成角色级路由器。
- 不提供通用可写子代理沙箱或新的工作树创建器。
- 不允许直接 Implementer 通过 `isolation:worktree` 或其他参数绕过本变更的拦截。
- 不执行本地插件安装、客户端同步、市场刷新、发布或 PR（拉取请求）交付。
- 不新增 `/tdd` 技能别名。
- 不改变 Explorer、Reviewer、Architect 的模型和能力契约。

## Further Notes

本变更属于 High risk（高风险）流程，因为它修改可写子代理的安全接缝、资源生命周期和用户级角色配置。现有旧验证曾证明默认扩展/MCP 的非 isolated 子会话可能阻止外层 Pi 退出；本变更的验收必须证明 `isolated:false` 与 `extensions:false`、`skills:tdd` 组合不会重现该问题。
