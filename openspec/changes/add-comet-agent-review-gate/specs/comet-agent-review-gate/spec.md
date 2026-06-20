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
- **AND** deny（拒绝）输出包含失败原因、缺失产物、当前 change、当前 head ref 和来自 Guard Profile（守卫画像）配置的下一步提示

#### Scenario: deny 输出由画像配置承载
- **WHEN** Global Command Guard（全局命令守卫点）拒绝 `comet-guard.sh <change> build --apply`
- **THEN** deny（拒绝）输出 MUST 包含结构化 `reason`、`next`、`suggestion`、命令 captures（捕获值）和 failing guard（失败守卫）详情
- **AND** `reason`、`next` 和 `suggestion` MAY 使用 Guard Profile 中声明的场景化配置
- **AND** Runtime（运行时）只负责透传或渲染这些配置字段，调用方 MAY 根据这些字段选择后续动作
- **AND** 本系统 MUST NOT 在 Agent Guard 或 Comet 中实现 cross-agent-review 内部编排逻辑

#### Scenario: pass marker 过期
- **WHEN** `review-pass.json` 的 `head_ref` 不匹配当前 HEAD
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet build 阶段守卫收尾命令，并提示重新运行跨 agent review

### Requirement: review fail 表现为无有效 pass marker
系统 MUST 只通过 pass marker（通过标记）是否存在且有效来判断 Comet build 阶段守卫收尾命令能否继续。跨 agent review 的执行、修复和重新审查流程属于 cross-agent-review（跨代理审查）或调用方契约。

#### Scenario: 阻塞发现
- **WHEN** 跨 agent review 报告包含 CRITICAL 或 IMPORTANT findings（发现项）
- **THEN** cross-agent-review 不生成 pass marker（通过标记）
- **AND** Global Command Guard（全局命令守卫点）继续拒绝 Comet build 阶段守卫收尾命令
- **AND** Agent Guard 不解析 review report（审查报告）或决定修复流程

#### Scenario: 修复后重新审查
- **WHEN** 用户修复 blocking findings（阻塞发现）并更新 HEAD
- **THEN** cross-agent-review 或调用方负责重新审查并使用新 head ref 生成新的 `review-pass.json`
- **AND** Agent Guard 只校验新 pass marker 是否匹配当前命令和当前 HEAD
