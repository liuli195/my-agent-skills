# Comet Spec Context

- Change: fix-issue-174
- Phase: design
- Mode: beta
- Context hash: d7dc3df44c0427ceb1ac8e65f0de51e98ba2bdcb29dea0ddc6338be7a2989b52

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/fix-issue-174/proposal.md
- SHA256: 3fd8ddf3c22e6b604e43730c850c7400e3d2bd93b50e2bf0f255569bece373e0
- Source: openspec/changes/fix-issue-174/design.md
- SHA256: 9a53a783529a938e64704112050b6879d7d784ee960a4a1bfffe03aea259b77d
- Source: openspec/changes/fix-issue-174/tasks.md
- SHA256: ad7d0b85819786551cdf54baadd7e7a8df910e076b03a782e7529bcf339826f3
- Source: openspec/changes/fix-issue-174/specs/agent-guard-plugin-runtime/spec.md
- SHA256: 52ae923fb21f0c50115794c057a13f9ddc0ce9a4bb0eb9b34fe7f5d5d2f5787e
- Source: openspec/changes/fix-issue-174/specs/pr-flow-plugin/spec.md
- SHA256: 5748b51086fad6e01e9f76dba4325a4082e83001c1694c41bf07b947c02e9ab5

## Acceptance Projection

## openspec/changes/fix-issue-174/specs/agent-guard-plugin-runtime/spec.md

- Source: openspec/changes/fix-issue-174/specs/agent-guard-plugin-runtime/spec.md
- Lines: 1-25
- SHA256: 52ae923fb21f0c50115794c057a13f9ddc0ce9a4bb0eb9b34fe7f5d5d2f5787e

```md
## ADDED Requirements

### Requirement: Pi 最小自动生命周期适配
系统 MUST 在 Agent Guard Plugin（代理守卫插件）内提供仅限 Pi（编码助手）的适配层，将 Pi（编码助手）会话启动和工具调用转换为既有 Runtime Router（运行时路由器）可处理的标准生命周期事件。该适配层 MUST 复用既有 Guard Profile（守卫画像）、Session Observation（会话观察记录）、Session Focus（会话焦点）、Global Command Guard（全局命令守卫点）和审计语义，不得改变 Codex（编码助手）或 Claude（克劳德）的 Hook（钩子）配置和行为。

#### Scenario: Pi 会话启动记录观察
- **WHEN** Pi（编码助手）开始一个加载 Agent Guard（代理守卫）的会话
- **THEN** 适配层 MUST 以 `source=pi`、会话标识和当前项目目录调用既有生命周期入口
- **THEN** Runtime（运行时）MUST 按既有 SessionStart（会话启动）语义记录 Session Observation（会话观察记录）

#### Scenario: Pi 工具调用复用守卫判定
- **WHEN** Pi（编码助手）在受 Guard Profile（守卫画像）约束的会话中发起工具调用
- **THEN** 适配层 MUST 将工具名称和可用输入映射为既有 PreToolUse（工具调用前）判定所需的标准事件
- **THEN** Runtime（运行时）MUST 按既有 Global Command Guard（全局命令守卫点）和 Session Focus permission（会话焦点权限）顺序产生 allow（允许）或 deny（拒绝）结果
- **THEN** Pi（编码助手）适配 MUST 将该既有判定结果直接映射为当前工具调用的继续或阻断结果，不得额外执行第二次 Agent Guard（代理守卫）判定

#### Scenario: Pi 适配不改变既有架构和宿主
- **WHEN** Pi（编码助手）适配层被加载或执行
- **THEN** 它 MUST NOT 修改 Guard Profile（守卫画像）格式、Runtime API（运行时接口）、权限规则或 Session Focus（会话焦点）生命周期
- **THEN** 它 MUST NOT 导入、配置、调用或修改其他 Pi（编码助手）插件
- **THEN** Codex（编码助手）和 Claude（克劳德）MUST 继续通过现有 `hooks/hooks.json`（钩子配置）和 Hook Router（钩子路由器）运行，不加载 Pi（编码助手）适配层

#### Scenario: Pi 适配不要求目标仓库配置
- **WHEN** Pi（编码助手）从已安装的 Agent Guard Plugin（代理守卫插件）运行
- **THEN** 自动生命周期适配 MUST NOT 要求目标仓库新增 `.pi`（Pi 配置）文件、全局记忆或子代理框架

```

## openspec/changes/fix-issue-174/specs/pr-flow-plugin/spec.md

- Source: openspec/changes/fix-issue-174/specs/pr-flow-plugin/spec.md
- Lines: 1-19
- SHA256: 5748b51086fad6e01e9f76dba4325a4082e83001c1694c41bf07b947c02e9ab5

```md
## ADDED Requirements

### Requirement: 已安装插件从自身位置执行 PR Flow
PR Flow Plugin（拉取请求流程插件）MUST 为 Pi（编码助手）提供从已安装插件自身位置解析 `pr_flow.py`（PR Flow 脚本）的执行入口。脚本位置 MUST 与目标项目目录分离；目标项目仍由 `--project`（项目参数）解析。

#### Scenario: Pi 在外部目标仓库运行
- **WHEN** Pi（编码助手）在不包含 `plugins/pr-flow`（拉取请求流程源码路径）的目标仓库中从 PR Flow Skill（拉取请求流程技能）入口执行命令
- **THEN** 入口 MUST 调用已安装插件内的 `pr_flow.py`（PR Flow 脚本）
- **THEN** `--project .`（项目参数）MUST 继续指向目标仓库，而不是插件目录

#### Scenario: 恢复命令不依赖源码仓库布局
- **WHEN** PR Flow（拉取请求流程）输出包含 `nextCommand`（下一命令）的可恢复停止状态
- **THEN** 该命令中的脚本位置 MUST 由执行中的 `pr_flow.py`（PR Flow 脚本）自身解析
- **THEN** 用户在目标仓库执行该命令时 MUST NOT 需要存在 `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`（源码仓库脚本路径）

#### Scenario: Codex 与 Claude 保持兼容
- **WHEN** Codex（编码助手）或 Claude（克劳德）从其插件缓存运行 PR Flow（拉取请求流程）
- **THEN** 入口和恢复命令 MUST 指向该已安装版本的脚本
- **THEN** 源码仓库中的文档仍 MAY 展示维护者专用的源码路径示例，且不得要求目标仓库复制该路径

```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.