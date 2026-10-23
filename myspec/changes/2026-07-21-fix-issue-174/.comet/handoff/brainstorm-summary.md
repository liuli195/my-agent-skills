# Brainstorm Summary

- Change: fix-issue-174
- Date: 2026-07-21

## 确认的技术方案

- Agent Guard（代理守卫）在插件根目录增加 Pi（编码助手）专属 extension（扩展）。它使用 Pi（编码助手）原生 `session_start`（会话启动）和 `tool_call`（工具调用）事件，并从自身模块位置定位既有 Python（派森）Hook Router（钩子路由器）。
- Pi（编码助手）会话启动通过 `source=pi` 记录既有 Session Observation（会话观察记录）；每个工具调用都将会话标识、项目目录、工具名称和完整输入映射为既有 `PreToolUse`（工具调用前）事件。Router（路由器）返回 allow（允许）时继续执行，deny（拒绝）或 ask（询问）时阻断当前调用。
- 适配层逐调用启动 Router（路由器）子进程，不复制或重写 Guard Runtime（守卫运行时），不新增状态、规则、配置或其他 Pi（编码助手）插件依赖。共享改动仅将现有 source（来源）白名单扩展为 `pi`。
- PR Flow（拉取请求流程）在插件根目录增加 Pi（编码助手）专属 extension（扩展）工具。它从自身模块位置定位 `pr_flow.py`（PR Flow 脚本），并以当前项目目录执行；共享技能在 Pi（编码助手）可用该工具时路由至它。
- PR Flow（拉取请求流程）恢复命令使用 `pr_flow.py`（PR Flow 脚本）自身的绝对路径及当前 Python（派森）解释器；Windows（视窗）和非 Windows（视窗）分别使用标准库安全引用规则。

## 关键取舍与风险

- 每次工具调用启动一个 Python（派森）进程会增加少量延迟，但避免常驻进程、进程间状态、退出清理和第二套运行时，符合最小适配范围。
- Pi（编码助手）适配将所有工具输入原样交给既有 Router（路由器）；Router（路由器）仅按既有规则处理可识别命令，不为新宿主添加推测性解析。
- Router（路由器）无法启动、输出无效或返回非预期错误时，Pi（编码助手）适配阻断当前工具调用并返回明确错误，避免静默绕过 Guard（守卫）。
- Pi（编码助手）extension（扩展）目录仅由 Pi（编码助手）发现；Codex（编码助手）与 Claude（克劳德）继续按现有 manifest（清单）和 Hook（钩子）运行。

## 测试策略

- 覆盖 Pi（编码助手）会话启动、所有工具调用的 allow（允许）/deny（拒绝）/ask（询问）映射、`source=pi` 会话隔离、Router（路由器）异常阻断以及现有 Codex（编码助手）/Claude（克劳德）回归。
- 覆盖 Pi（编码助手）PR Flow（拉取请求流程）入口在无源码插件路径的外部仓库执行，及 Windows（视窗）和非 Windows（视窗）恢复命令引用。
- 在两个目标仓库从 Pi（编码助手）技能入口运行完整主流程，并运行仓库完整构建和端到端回归。

## Spec Patch

无。
