# Brainstorm Summary

- Change: add-guard-gate-binding
- Date: 2026-06-20

## 确认的技术方案

本变更从 Gate Binding（门禁绑定）调整为 Global Command Guard（全局命令守卫点）。目标不是为 Comet 新增专用守卫逻辑，而是在 Agent Guard（代理守卫）里增加通用的命令边界拦截能力。

全局命令守卫点由 PreToolUse（工具使用前）hook 执行。主 agent 准备执行 shell 命令时，代理守卫先提取工具名和命令文本，再收集所有项目级和用户级 Guard Profile（守卫画像）贡献的 `global-command-guards.yaml`，形成 Effective Global Command Guard Set（有效全局命令守卫集）。

运行时为每条规则生成 effective guard id（有效守卫 ID）：`<source_scope>:<profile_id>:<guard_id>`。命令匹配所有规则后，运行时对所有匹配规则提取 named capture（命名捕获），解析 evidence path template（证据路径模板），读取 JSON evidence（JSON 证据），并使用复用的 JSON predicate（JSON 谓词）检查证据。所有匹配规则都通过才允许继续；任意规则失败返回 `deny`。检查通过后继续进入现有 Session Focus permission（会话焦点权限）逻辑。

Comet review-before-verify 是配置实例，不是运行时特例。Comet 命令不用修改，也不用主动调用 Agent Guard；命令边界由代理守卫 hook 自动拦截。

## 关键取舍与风险

- 保留 Session Focus（会话焦点）和 Guard Instance（守卫实例）的流程型能力，只把可复用的命令提取、命令匹配、JSON 检查、审计和校验器能力抽象出来。
- 新增 `global-command-guards.yaml`，作为每个 Guard Profile 对全局命令守卫系统贡献的静态规则文件，避免把静态命令边界规则塞进守卫实例状态或流程型 Guard Point。
- 多个 Guard Profile 可以同时贡献全局命令守卫点；同一文件内 guard id 必须唯一，不同 profile 或不同 source scope 中允许同名 guard id。
- 全局命令守卫点采用叠加约束：一个命令匹配多个规则时，所有规则都必须通过；不存在项目级覆盖用户级或后加载覆盖先加载。
- 运行态目录按事件或命令的目标作用域决定，不按插件安装范围或静态 Guard Profile 所在目录简单决定。
- 项目相关运行时动态文件继续使用 `.local/guard`；用户级运行目录 `~/.agents/guard` 只在显式用户作用域运行态使用。
- 用户级安装或用户级静态 Guard Profile 在项目内触发项目相关 hook 时，日志在 `.local/guard` 是合理现象。
- Comet change review 属于项目和 Git HEAD 相关证据，必须使用项目级 `.local/guard`，不得从用户级运行目录读取通过证据。
- 全局命令守卫点证据使用运行目录下的 `evidence/<source_scope>/<profile_id>/<guard_id>/...`，避免多个画像或用户级/项目级同名规则互相覆盖，不得污染静态 Guard Profile。
- 命令解析第一版只覆盖配置模式和测试覆盖的命令形态，包括 Windows PowerShell 包装 Git Bash。
- 如果命令明确命中受保护边界但缺少必需捕获值，必须拒绝，不能静默放行。

## 测试策略

- 校验器测试：有效配置、缺少命令模式、缺少证据路径、不支持 JSON 谓词、非法 `value_from`、缺少必需捕获值。
- 命令匹配测试：普通命令、Comet 风格命令 fixture、PowerShell 包装 Git Bash。
- 多来源测试：多个项目级 profile、用户级 + 项目级 profile 同时贡献规则、跨来源同名 `guard_id` 不冲突。
- 运行时测试：无会话焦点仍执行全局命令守卫点、证据缺失、证据过期、证据通过、审计字段完整、多个匹配规则任一失败则拒绝。
- 回归测试：未命中全局命令守卫点时现有会话焦点权限不变；全局命令守卫点允许后，会话焦点仍可拒绝。

## Spec Patch

已回写 OpenSpec delta：

- `proposal.md`：目标改为通用全局命令守卫点。
- `design.md`：补充最终方案、多来源收集、叠加评估、复用/抽象边界、完整目录设计。
- `tasks.md`：改为全局命令守卫点实施任务，加入多来源和同名规则测试。
- `specs/agent-guard-plugin-runtime/spec.md`：新增配置目录、多来源收集、作用域运行目录、命令上下文、共享检查器、证据检查等要求。
