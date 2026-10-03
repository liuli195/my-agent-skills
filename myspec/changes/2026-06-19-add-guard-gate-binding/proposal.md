## Why

代理守卫（Agent Guard）当前主要通过会话焦点实例（Session Focus Instance）执行命令权限约束。这适合“某个会话正在推进某个流程实例”的场景，但不适合表达静态的项目级命令边界：

> 只要主 agent 尝试执行某个受保护命令点，就必须先通过配置的证据或检查；这个判断不依赖当前是否存在会话焦点，也不依赖有多少守卫实例正在运行。

Comet 验证前必须完成 review 是第一个具体用例，但能力不能写死为 Comet 专用。相同机制应能守卫任意配置的命令点，例如发布、部署、归档、清理、审批后执行等。

## What Changes

- 将本变更目标从 Gate Binding（门禁绑定，已废弃方向）调整为 Global Command Guard（全局命令守卫点）。
- 新增项目级或用户级 Guard Profile（守卫画像）贡献的配置文件：`global-command-guards.yaml`。
- 在 PreToolUse（工具使用前）阶段，收集所有项目级和用户级 `global-command-guards.yaml`，形成 Effective Global Command Guard Set（有效全局命令守卫集），先评估该集合，再进入现有会话焦点权限逻辑。
- 支持多个 Guard Profile 同时贡献全局命令守卫点；同名守卫 ID 通过 `<source_scope>:<profile_id>:<guard_id>` 区分。
- 当一个命令匹配多个全局命令守卫点时，必须所有匹配规则都通过；任意规则拒绝则命令拒绝。
- 支持通过 command pattern（命令模式）匹配受保护命令，并用 named capture（命名捕获）提取 `change`、`tag`、`environment` 等上下文变量。
- 支持 evidence path template（证据路径模板）读取 JSON evidence（JSON 证据），并复用已有 `json_artifact` 的 JSON predicate（JSON 谓词）语义。
- 抽象并复用当前散落在会话焦点 / 守卫实例路径里的通用能力：
  - 命令提取；
  - 命令匹配；
  - JSON 字段读取和谓词评估；
  - 运行时路径解析；
  - 审计输出；
  - 校验器问题格式。
- 当受保护命令缺少有效证据时，返回机器可读的 `deny` 输出，包含原因、下一步建议、匹配的有效守卫 ID、失败守卫列表、捕获值和审计路径。
- 保持会话焦点、守卫实例状态推进、守卫简报注入等现有语义不变。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `agent-guard-plugin-runtime`：运行时在会话焦点权限检查之外，支持全局命令守卫点。

## Impact

- Runtime（运行时）：影响 `plugins/agent-guard/scripts/guard_runtime/core.py`，并可能拆出命令上下文、命令匹配、JSON 检查、全局命令守卫等共享模块。
- Validator（校验器）：需要校验 `global-command-guards.yaml` 的配置结构、命令模式、证据路径、JSON 谓词和上下文引用。
- Templates（模板）：Guard Profile 模板需要增加可选的 `global-command-guards.yaml`。
- Tests（测试）：覆盖 PreToolUse 路由、命令解析、PowerShell 包装 Git Bash、JSON evidence 检查、审计输出、会话焦点回归。
- 现有会话焦点行为必须保持兼容。
