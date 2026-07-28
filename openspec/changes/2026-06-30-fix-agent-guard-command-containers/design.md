## Context

`command_from_envelope` 是 Session Focus permission（会话焦点权限）和 Global Command Guard（全局命令守卫）的共享命令提取入口。

当前函数只检查 `payload.tool_input.command` 和 `payload.command`。`adapt_lifecycle_event` 已经会把 `input`、`parameters` 归一到 `tool_input`，但直接 Runtime envelope（运行时信封）或未来 hook adapter（钩子适配器）保留 `parameters`、`params`、`args`、`arguments` 时，共享提取入口会漏掉命令。

## Goals / Non-Goals

**Goals:**

- 固定读取一层容器里的 `command` / `cmd` 字符串。
- 保留 `tool_input` 和顶层 `payload` 的现有优先级。
- 让 Global Command Guard（全局命令守卫）audit（审计）记录识别到的真实 command（命令）。

**Non-Goals:**

- 不做任意深层递归扫描。
- 不支持非字符串命令。
- 不新增依赖或新配置。

## Decisions

1. 在 `command_from_envelope` 内使用固定容器列表。

   这是共享入口，改这里同时覆盖 Session Focus permission（会话焦点权限）和 Global Command Guard（全局命令守卫），比在调用方补丁更小。

2. 只支持一层容器。

   支持范围限定为 `tool_input`、顶层 `payload`、`input`、`parameters`、`params`、`args`、`arguments`。这覆盖现有载荷形状，不引入模糊扫描。

## Risks / Trade-offs

- 如果未来出现更深层载荷，需要另加明确容器；当前不提前泛化。
- `cmd` 作为 `command` 的别名会被识别，但非字符串仍安全忽略。
