# Comet Spec Context

- Change: add-comet-agent-review-gate
- Phase: design
- Mode: beta
- Context hash: ca828f2b0e2198214d1cbf557404082da90f87100394416c35e102894897d115

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/add-comet-agent-review-gate/proposal.md
- SHA256: e29e23072aaa48d1de5f952002132bdc2014a0aa8637d13d3d6fd009fb3d7bd2
- Source: openspec/changes/add-comet-agent-review-gate/design.md
- SHA256: 1d5e43eb1a6830742b9b424ae1dfb031b4d0acb8b757d7a6d24b7a37406a4eb7
- Source: openspec/changes/add-comet-agent-review-gate/tasks.md
- SHA256: 60f5e3ecd724605b4f1d2d2bbc2c1b41604ceea530cb5e91f4b90ea93f3ee509
- Source: openspec/changes/add-comet-agent-review-gate/specs/agent-guard-plugin-runtime/spec.md
- SHA256: 9b00943ce18057ac1262357d9b867c849119fa318fcf79a9784bd329140ea6d2
- Source: openspec/changes/add-comet-agent-review-gate/specs/agent-guard-skill-entrypoints/spec.md
- SHA256: 32f6b96482662a1b3d891556862a013a2eb3b91fb49c15eeb1f495ea3d734c2d
- Source: openspec/changes/add-comet-agent-review-gate/specs/comet-agent-review-gate/spec.md
- SHA256: 941d97bf2859b159e016ed247a05de3e2480bf183ca8d7145aec3de708d1c4bd

## Acceptance Projection

## openspec/changes/add-comet-agent-review-gate/specs/agent-guard-plugin-runtime/spec.md

- Source: openspec/changes/add-comet-agent-review-gate/specs/agent-guard-plugin-runtime/spec.md
- Lines: 1-106
- SHA256: 9b00943ce18057ac1262357d9b867c849119fa318fcf79a9784bd329140ea6d2

```md
## MODIFIED Requirements

### Requirement: Global command guard configuration layout
系统 MUST 支持在 Guard Profile（守卫画像）目录中声明 `global-command-guards.yaml`，用于存放静态的 Global Command Guard（全局命令守卫点）配置。系统 MUST 区分静态配置作用域、运行态数据作用域和外部产物所在位置。

#### Scenario: 项目级静态配置
- **WHEN** 项目级 Guard Profile 声明全局命令守卫点
- **THEN** 配置文件 MUST 位于 `.agents/guards/<profile_id>/global-command-guards.yaml`

#### Scenario: 用户级静态配置
- **WHEN** 用户级 Guard Profile 声明全局命令守卫点
- **THEN** 配置文件 MUST 位于 `~/.agents/guards/<profile_id>/global-command-guards.yaml`

#### Scenario: 有效守卫 ID
- **WHEN** Runtime（运行时）加载任意 Global Command Guard
- **THEN** Runtime MUST 为该规则生成 effective guard id（有效守卫 ID）
- **AND** effective guard id MUST 使用 `<source_scope>:<profile_id>:<guard_id>`

#### Scenario: 同名守卫 ID 不跨来源冲突
- **WHEN** 两个不同 Guard Profile 或不同 source scope（来源作用域）声明相同 `guard_id`
- **THEN** Runtime（运行时）MUST 通过 effective guard id 区分它们
- **AND** Validator（校验器）不得要求跨 profile 全局唯一

#### Scenario: 同一文件内守卫 ID 必须唯一
- **WHEN** 同一个 `global-command-guards.yaml` 中出现重复 `guard_id`
- **THEN** Validator（校验器）MUST 报错

#### Scenario: 动态文件使用运行时目录
- **WHEN** Global Command Guard 读取或写入运行时动态材料
- **THEN** Runtime（运行时）MUST 使用 `.local/guard` 或用户级等价目录 `~/.agents/guard`
- **AND** Runtime 不得把全局命令守卫点的动态材料写入静态 Guard Profile 目录

#### Scenario: 项目上下文使用项目级运行目录
- **WHEN** Global Command Guard 守卫的命令作用于当前项目
- **THEN** Runtime（运行时）MUST 使用 `.local/guard` 记录该守卫的 audit（审计）和自身运行态材料
- **AND** 即使 Global Command Guard 的静态配置来自用户级 Guard Profile，Runtime 也不得默认把该项目命令的运行态材料写入 `~/.agents/guard`

#### Scenario: 用户作用域使用用户级运行目录
- **WHEN** Runtime 处理显式 user scope（用户作用域）的会话焦点实例、用户全局命令，或配置显式声明用户级运行态
- **THEN** Runtime（运行时）MUST 使用 `~/.agents/guard`

#### Scenario: Comet change review 通过产物注册读取项目产物
- **WHEN** Global Command Guard 用于守卫 Comet change build 完成命令
- **AND** 该守卫通过 `artifact` 或 `artifact_id` 引用 `artifacts.yaml` 中的 cross-agent-review pass marker（跨代理审查通过标记）
- **THEN** Runtime（运行时）MUST 按 `artifacts.yaml` 注册路径读取该外部产物
- **AND** 该产物 MAY 位于项目内 `.local/cross-agent-review/<change>/<head_ref>/review-pass.json`
- **AND** Runtime 不得要求 cross-agent-review 把该产物复制到 `.local/guard/evidence`
- **AND** Runtime 不得从 `~/.agents/guard` 读取该 Comet change 的通过证据

#### Scenario: 用户级安装不等于用户级运行态
- **WHEN** Agent Guard Plugin（代理守卫插件）安装在用户级
- **AND** 主 agent 在项目内触发 hook 或执行项目命令
- **THEN** Runtime（运行时）MUST 把该项目上下文的审计和自身运行态材料写入 `.local/guard`

### Requirement: Evidence checks
系统 MUST 支持 Global Command Guard 用 artifact reference（产物引用）或 legacy evidence path template（旧证据路径模板）读取 JSON evidence（JSON 证据），并使用命令上下文和运行时上下文执行检查。新集成 SHOULD 优先使用 `artifacts.yaml` 产物注册层。

#### Scenario: evidence 通过 artifact reference 读取
- **WHEN** Global Command Guard 匹配命令
- **AND** 配置的 evidence（证据）声明 `artifact` 或 `artifact_id`
- **THEN** Runtime（运行时）MUST 从同一 Guard Profile 的 `artifacts.yaml` 查找该 artifact id
- **AND** Runtime MUST 渲染该 artifact 的 `path`
- **AND** 目标 JSON 存在且所有配置的 JSON checks（JSON 检查）均通过时，Runtime 允许该命令继续进入后续 Session Focus permission（会话焦点权限）检查

#### Scenario: artifact path 使用命令和运行时上下文
- **WHEN** Global Command Guard 通过 `artifacts.yaml` 渲染 artifact path
- **THEN** Runtime（运行时）MUST 支持命令捕获值，例如 `{change}`
- **AND** Runtime MUST 支持全局守卫运行时上下文，例如 `{git_head}`、`{source_scope}`、`{profile_id}`、`{guard_id}`、`{effective_guard_id}` 和 `{runtime_scope}`
- **AND** Global Command Guard artifact path 不得强制要求 Session Focus 专用上下文，例如 `{instance_id}` 或 `{state_version}`

#### Scenario: 用户级 profile 的 artifact path 按项目命令解析
- **WHEN** 用户级 Guard Profile 的 `artifacts.yaml` 为项目命令声明相对路径 artifact
- **THEN** Runtime（运行时）MUST 按当前项目根目录解析该相对路径
- **AND** Runtime 不得把该相对路径解析到用户级 Guard Profile 目录或 `~/.agents/guard`

#### Scenario: evidence 通过 legacy path 读取
- **WHEN** Global Command Guard 匹配命令
- **AND** 配置只声明 legacy `evidence.path`
- **AND** evidence JSON 存在
- **AND** 所有配置的 JSON checks（JSON 检查）均通过
- **THEN** Runtime（运行时）允许该命令继续进入后续 Session Focus permission 检查

#### Scenario: evidence 缺失
- **WHEN** Global Command Guard 匹配命令
- **AND** 目标 evidence JSON 不存在
- **THEN** Runtime（运行时）返回 `deny`
- **AND** reason（原因）为该守卫声明的 deny reason，或 `global_command_guard_required`

#### Scenario: evidence 使用上下文值
- **WHEN** JSON check 声明 `value_from`
- **THEN** Runtime（运行时）从 command context 或 runtime context（运行时上下文）读取对应值参与谓词比较

#### Scenario: evidence 路径使用有效守卫上下文
- **WHEN** legacy evidence path template（旧证据路径模板）包含 `source_scope`、`profile_id`、`guard_id`、`effective_guard_id` 或 `runtime_scope`
- **THEN** Runtime（运行时）MUST 从当前匹配规则的上下文中解析这些值
- **AND** Runtime MUST 避免不同 profile 中同名 guard id 写入同一 evidence 路径

#### Scenario: legacy evidence path 兼容但不用于 Comet review gate
- **WHEN** Global Command Guard 配置只声明 legacy `evidence.path`
- **THEN** Runtime（运行时）MAY 继续按既有 `.local/guard/evidence` 或用户级等价 evidence 目录解析该路径
- **AND** 新的 Comet review gate 配置不得使用该 legacy path 模型表达 cross-agent-review pass marker

#### Scenario: artifact 引用无效
- **WHEN** Global Command Guard 配置声明的 `artifact` 或 `artifact_id` 不存在于同一 Guard Profile 的 `artifacts.yaml`
- **THEN** Validator（校验器）MUST 报告该引用无效
- **AND** Runtime（运行时）MUST deny（拒绝）匹配命令，并在失败详情中包含缺失的 artifact id
```

## openspec/changes/add-comet-agent-review-gate/specs/agent-guard-skill-entrypoints/spec.md

- Source: openspec/changes/add-comet-agent-review-gate/specs/agent-guard-skill-entrypoints/spec.md
- Lines: 1-48
- SHA256: 32f6b96482662a1b3d891556862a013a2eb3b91fb49c15eeb1f495ea3d734c2d

```md
## ADDED Requirements

### Requirement: Agent Guard Skill 入口覆盖 Global Command Guard
系统 MUST 让 Agent Guard（代理守卫）所有相关 Skill（技能）入口和共享参考文档覆盖 Global Command Guard（全局命令守卫点）的配置、初始化、同步、运行反馈和排障语义。Global Command Guard 不得只存在于 Runtime（运行时）实现或内部 README 中。相关文档 MUST 采用 progressive disclosure（渐进式披露），按 agent 使用场景组织，明确禁止项，并保持语言简洁高效。

#### Scenario: 路由入口识别全局命令守卫意图
- **WHEN** 用户要求安装、配置、同步或排查 Global Command Guard（全局命令守卫点）
- **THEN** `$agent-guard` router（路由入口）把该意图路由到合适的 `$agent-guard-install`、`$agent-guard-init`、`$agent-guard-update` 或 `$agent-guard-run` 场景入口

#### Scenario: 安装入口生成全局命令守卫画像
- **WHEN** `$agent-guard-install` 为用户级 Global Command Guard（全局命令守卫点）生成 Guard Profile（守卫画像）草案
- **THEN** 入口说明和参考文档指导 agent 同时生成或更新 `global-command-guards.yaml` 和相关 `artifacts.yaml` 注册
- **AND** 文档说明静态规则可位于 `~/.agents/guards/<profile_id>/global-command-guards.yaml`
- **AND** 文档说明 Global Command Guard 可通过 `artifact` 或 `artifact_id` 引用 `artifacts.yaml` 中的注册产物

#### Scenario: 初始化和更新入口同步全局命令守卫画像
- **WHEN** `$agent-guard-init` 或 `$agent-guard-update` 初始化或同步包含 Global Command Guard（全局命令守卫点）的 Guard Profile（守卫画像）
- **THEN** 入口说明要求先运行 `validate_guard_profile.py <guard-profile-dir>`
- **AND** 文档说明该校验覆盖 `global-command-guards.yaml`、命令模式、产物引用和 JSON predicate（JSON 谓词）

#### Scenario: 运行入口解释全局命令守卫拒绝
- **WHEN** PreToolUse（工具使用前）因 Global Command Guard（全局命令守卫点）拒绝命令
- **THEN** `$agent-guard-run` 或共享运行参考文档说明该拒绝不依赖 Session Focus Instance（会话焦点实例）
- **AND** 文档指导 agent 根据 deny（拒绝）输出中的 reason、next、suggestion、captures、failing guards（失败守卫）和 artifact/evidence 信息执行下一步
- **AND** 文档说明对 Comet review gate（审查门禁）应先执行 build readiness check（构建就绪检查），再按 deny 指引准备并运行 cross-agent-review（跨代理审查）

#### Scenario: 模板索引暴露全局命令守卫资源
- **WHEN** agent 查阅 Agent Guard 共享模板或参考索引
- **THEN** 文档列出 `global-command-guards.yaml` 模板、`artifacts.yaml` 配合方式、用户级静态配置位置和项目级运行态边界

#### Scenario: 文档按渐进式披露组织
- **WHEN** 更新 Agent Guard Skill 入口或共享参考文档
- **THEN** 入口文档 MUST 只放当前场景 agent 立即需要的步骤、判断标准和下一跳链接
- **AND** 细节、模板字段和排障矩阵 MUST 放入对应 reference（参考文档）或 template（模板）文件

#### Scenario: 文档按 agent 使用场景组织
- **WHEN** 文档说明 Global Command Guard（全局命令守卫点）
- **THEN** 内容 MUST 按 agent 使用场景组织，例如 install（安装/生成草案）、init（初始化/启用）、update（同步/维护）、run（运行/处理拒绝）、troubleshoot（排障）
- **AND** 文档不得只按内部模块、runtime 文件或实现函数组织

#### Scenario: 文档明确禁止项
- **WHEN** 文档说明 Comet review gate（审查门禁）或 Global Command Guard
- **THEN** 文档 MUST 明确禁止新增 reviewed wrapper（审查包装入口）、修改 cross-agent-review 默认输出目录、复制 pass marker 到 `.local/guard/evidence`、把 `verify --apply` 作为主拦截点、以及绕过 build readiness check（构建就绪检查）直接 review

#### Scenario: 文档语言简洁高效
- **WHEN** 更新 Skill 入口说明、共享参考文档或模板索引
- **THEN** 文档 MUST 使用短句和可执行步骤
- **AND** 文档 MUST 避免重复解释、营销式描述、长篇背景和只服务实现细节的术语堆叠
```

## openspec/changes/add-comet-agent-review-gate/specs/comet-agent-review-gate/spec.md

- Source: openspec/changes/add-comet-agent-review-gate/specs/comet-agent-review-gate/spec.md
- Lines: 1-85
- SHA256: 941d97bf2859b159e016ed247a05de3e2480bf183ca8d7145aec3de708d1c4bd

```md
## ADDED Requirements

### Requirement: Comet review gate 不改变阶段链
系统 MUST 在不新增 Comet phase（阶段）的前提下支持 build 到 verify 之间的 agent review gate（代理审查门禁）。

#### Scenario: 原始 Comet 阶段链保持不变
- **WHEN** 用户运行原始 Comet 流程
- **THEN** 系统仍按 `open -> design -> build -> verify -> archive` 阶段链推进
- **AND** review gate（审查门禁）只由已安装并启用的 Global Command Guard（全局命令守卫点）触发
- **AND** 未安装、未启用或未匹配该用户级全局守卫时，Comet 原始命令行为保持不变

#### Scenario: build 完成命令进入门禁
- **WHEN** Comet build 阶段完成，主 agent 准备执行 build 阶段守卫收尾命令
- **THEN** 系统在 `comet-guard.sh <change> build --apply` 执行前检查跨 agent review 的 pass marker（通过标记）
- **AND** 系统不得把 `comet-guard.sh <change> verify --apply` 作为主要拦截点，因为该命令用于 verify 完成后的状态推进

#### Scenario: 命令模式覆盖实际调用形态
- **WHEN** 用户级 Global Command Guard（全局命令守卫点）配置 Comet review gate
- **THEN** command patterns（命令模式）MUST 覆盖直接调用 `comet-guard.sh <change> build --apply`
- **AND** command patterns MUST 覆盖路径调用，例如 `<path>/comet-guard.sh <change> build --apply`
- **AND** command patterns MUST 覆盖环境变量脚本调用，例如 `"$COMET_BASH" "$COMET_GUARD" <change> build --apply`
- **AND** command patterns MUST NOT 以 `comet-guard.sh <change> verify --apply` 作为主要匹配边界

### Requirement: Comet review gate 使用用户级 Global Command Guard
系统 MUST 使用用户级 Global Command Guard（全局命令守卫点）表达 Comet verify 前的 review gate（审查门禁），不得新增 Comet phase（阶段）、不得新增 reviewed wrapper（带审查包装入口），也不得使用 Session Focus Binding（会话焦点绑定）表达该命令边界。

#### Scenario: 用户级全局守卫拦截 build 完成
- **WHEN** 主 agent 尝试执行 Comet build 阶段守卫收尾命令
- **THEN** Agent Guard 从用户级 Guard Profile（守卫画像）的 `global-command-guards.yaml` 匹配该命令
- **AND** 该匹配不依赖当前 Session Focus Instance（会话焦点实例）

#### Scenario: 项目命令使用项目运行态
- **WHEN** 用户级 Global Command Guard（全局命令守卫点）拦截项目内 Comet build 阶段守卫收尾命令
- **THEN** audit（审计）和 evidence resolution（证据解析）按项目运行态执行
- **AND** 系统不得把该项目命令的运行态材料写入 `~/.agents/guard`

### Requirement: Comet review gate 通过产物注册层校验 pass marker
系统 MUST 通过 Agent Guard artifacts.yaml 产物注册层引用 cross-agent-review（跨代理审查）默认输出的 `review-pass.json`，并使用 Global Command Guard（全局命令守卫点）的 JSON predicate（JSON 谓词）校验该 pass marker（通过标记）。系统 MUST NOT 要求 cross-agent-review 修改默认输出目录、复制 pass marker 到另一套 evidence 目录，或改变 cross-agent-review 的边界行为。

#### Scenario: 注册 cross-agent-review pass marker
- **WHEN** 用户级 Guard Profile（守卫画像）配置 Comet review gate
- **THEN** `artifacts.yaml` 注册 `cross_agent_review_pass` 产物
- **AND** 该产物路径指向项目内 `.local/cross-agent-review/<change>/<head_ref>/review-pass.json`
- **AND** `<change>` 来自 Global Command Guard（全局命令守卫点）的命令捕获值
- **AND** `<head_ref>` 来自当前 Git HEAD
- **AND** Global Command Guard 通过 `artifact` 或 `artifact_id` 引用该注册产物，而不是直接声明独立 `evidence.path`

#### Scenario: pass marker 合法
- **WHEN** `review-pass.json` 存在，且 `status` 为 `pass`、`change` 匹配当前 change、`head_ref` 匹配当前 HEAD、`blocking_findings` 为 0、`report` 存在且 `report_hash` 存在
- **THEN** Global Command Guard（全局命令守卫点）允许 Comet build 阶段守卫收尾命令继续执行

#### Scenario: pass marker 缺失
- **WHEN** review report（审查报告）存在但 `review-pass.json` 不存在
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet build 阶段守卫收尾命令
- **AND** deny（拒绝）输出包含失败原因、缺失产物、当前 change、当前 head ref 和下一步运行 cross-agent-review 的提示

#### Scenario: deny 后先确认 build 已可收尾
- **WHEN** Global Command Guard（全局命令守卫点）拒绝 `comet-guard.sh <change> build --apply`
- **THEN** agent MUST 先运行非变更的 build readiness check（构建就绪检查），例如 `comet-guard.sh <change> build`
- **AND** 只有该检查通过时，agent 才准备 cross-agent-review 输入并启动审查
- **AND** 如果 build readiness check 不通过，agent MUST 先回 build 修复该失败，而不是提前运行 cross-agent-review

#### Scenario: deny 后准备 cross-agent-review 输入
- **WHEN** build readiness check（构建就绪检查）通过且缺少有效 pass marker（通过标记）
- **THEN** agent MUST 准备 `cross-agent-review` 所需输入：`--change`、`--base-ref`、`--head-ref`、`--diff-file`、`--spec-file`、`--design-file`、`--tasks-file` 和 `--tests-file`
- **AND** `--head-ref` MUST 等于当前 `git rev-parse HEAD`
- **AND** worktree MUST 为 clean（干净）
- **AND** `--tests-file` MUST 指向调用方已经运行并保存的测试结果
- **AND** agent MUST NOT 要求 cross-agent-review 运行构建或测试

#### Scenario: pass marker 过期
- **WHEN** `review-pass.json` 的 `head_ref` 不匹配当前 HEAD
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet build 阶段守卫收尾命令，并提示重新运行跨 agent review

### Requirement: review fail 回到 build 修复
系统 MUST 在跨 agent review 不通过时停在 verify 前，并让用户回 build 修复或重新 review。

#### Scenario: 阻塞发现
- **WHEN** 跨 agent review 报告包含 CRITICAL 或 IMPORTANT findings（发现项）
- **THEN** cross-agent-review 不生成 pass marker（通过标记）
- **AND** Global Command Guard（全局命令守卫点）继续拒绝 Comet build 阶段守卫收尾命令，并提示回 build 修复

#### Scenario: 修复后重新审查
- **WHEN** 用户修复 blocking findings（阻塞发现）并更新 HEAD
- **THEN** agent 必须重新运行 cross-agent-review，并使用新 head ref 生成新的 `review-pass.json`
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
