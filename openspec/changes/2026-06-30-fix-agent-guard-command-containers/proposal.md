## Why

Issue #16 暴露了 Agent Guard Runtime（代理守卫运行时）的 command extraction（命令提取）不一致：`parameters.command` 等价载荷容器里的命令不能被 `command_prefix` 规则识别。

这会让同一条工具命令因为 JSON 容器不同而从 allow（允许）变成 default deny（默认拒绝），并让 audit（审计）缺少真实 command（命令）。

## What Changes

- 让共享 `command_from_envelope` 覆盖 Runtime（运行时）保留的一层 tool input containers（工具输入容器）。
- 保持现有 top-level（顶层）和 `tool_input` 优先级。
- 不引入递归字段扫描、新依赖或新抽象。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-guard-plugin-runtime`: command extraction（命令提取）必须一致识别 Runtime（运行时）支持的一层命令容器。

## Impact

- Affected code: `plugins/agent-guard/scripts/guard_runtime/command_context.py`.
- Affected tests: `tests/test_agent_guard_runtime_router.py`.
- Dependencies: none added.
