# 本机验证预算硬截止（门禁一已确认）

状态：ready-for-human。第一道关卡授权范围的实现、真实入口检查及父端独立审查已完成；当前固定基线验证已通过，第二道关卡待用户批准。本文更新候选事项的真实状态，不应用正式规格。

## 问题说明

当前完整验证在所有检查完成后才比较总预算，超预算只警告。单项检查可以继续很久，后续检查仍会执行，用户无法用项目已有预算限制本机这一次验证的实际等待时间。快速验证目前不读取总预算；独立构建命令也没有总预算。

## 解决方案

提供缺省开启的本机预算强制开关。已证明在本机执行且开启时，一次命令共用一个按单调时钟计算的截止时间；到期仍有工作未完成即中断本次启动的进程及后代，停止启动后续检查，返回非零超时失败。关闭时超预算仅警告并继续，真实检查错误仍失败。云端、拉取请求及持续集成保留原行为。

临时诊断模式仅对本次运行取消总截止，不修改默认配置；保留单项防挂超时与断言失败，实时记录检查开始、结束、耗时和未完成情况。诊断结果明确不作为正式验证通过证据。测试用例耗时使用测试框架原有能力，不要求通用命令程序解析所有子测试。

## 用户故事

1. 作为本机用户，我希望省略开关仍启用硬截止，避免忘记开启限制。
2. 作为本机用户，我希望使用项目已有预算数值，避免插件写死某个项目的秒数。
3. 作为本机用户，我希望串行和并行检查共用一次运行的预算，避免每个检查重新获得全部时间。
4. 作为本机用户，我希望到期停止本次进程及其后代，避免后台测试继续消耗资源。
5. 作为本机用户，我希望用户其他进程继续工作，避免全局终止同名程序。
6. 作为本机用户，我希望看到实际耗时、预算、未完成和未启动检查，知道为什么失败。
7. 作为本机用户，我希望关闭强制开关后只收到预算警告，仍可完成验证。
8. 作为本机用户，我希望关闭开关也不会吞掉功能失败、单项超时或异常。
9. 作为云端及拉取请求用户，我希望本机开关不改变我的运行行为。
10. 作为使用云端模型操作本机的用户，我希望判断依据是执行地点，而非模型所在地点。
11. 作为维护者，我希望超时、取消和未启动检查不写成功缓存，避免后来误报通过。
12. 作为维护者，我希望预算前真实完成的检查仍能缓存，并保留原缓存行为覆盖。
13. 作为报告使用者，我希望文字输出、退出码、缓存和机器可读报告状态一致。
14. 作为诊断用户，我希望临时取消总截止后找到耗时检查，且诊断不会冒充正式通过。
15. 作为维护者，我希望短合成预算测试能证明硬截止，不故意等待项目实际的长预算。

## 实施决定

- 用户已确认仅覆盖每次快速及完整验证，独立构建不纳入，不跨命令调用累计预算。预算值复用现有可选正整数 `verify.fullBudgetSeconds`（完整验证预算秒数）；最新显式授权将本仓库预算从30秒调整为60秒，消费者既有60秒不变；插件实现不引入固定秒数。
- 本机强制开关 `verify.enforceLocalBudget`（本机预算强制开关）必须为布尔值，缺省视为开启。
- 显式区分执行地点与拉取请求场景。现有场景输出不能证明本机；操作系统也不能证明本机。现有实现未发现可复用的执行地点参数。
- 执行地点参数 `--execution-context local|cloud|ci`（执行地点：本机、云端、持续集成）为基本路径，可选继承 `BUILD_AND_VERIFY_EXECUTION_CONTEXT`（执行地点环境声明），参数优先。可靠持续集成标识和拉取请求场景优先豁免，未知不得伪报本机，也不得静默跳过默认强制限制；未知且配置预算、强制开启的正式验证在启动检查前明确失败。用户已获知该兼容性变化。无需宿主新增功能或机器级配置。本次已知本机环境中 `CODEX_CI=1`（宿主内部环境标记），因此该标记不能单独证明持续集成。
- 一次命令共用一条单调时钟截止时间，包括运行前准备、缓存选择、调度和实际检查；不得跨不同命令调用累计预算。
- 单项等待上限取单项超时与剩余总预算的较小值，并明确区分单项超时和总预算到期。
- 串并行共用取消状态，启动前原子核对截止与取消；到期不再启动排队检查。
- 进程管理只处理本次拥有的进程树；可移植系统使用独立进程组，Windows（视窗系统）使用可靠作业对象，回收等待有界，父进程退出后仍可回收后代。
- 报告保留已有计时字段，并以兼容方式补充状态、原因、未完成和未启动信息；超时不能写成功缓存或吞异常。
- 用户已确认采用一次性诊断参数，候选名称 `--diagnostic`（诊断模式）。第一版不新造检查项选择器，使用已有测试框架原生选择能力调试单项。

## 测试决定

- 目标产品：构建与验证插件；最高真实入口：已发布形态的命令行程序。现有仓库测试通过命令入口运行，沿用这个接缝。
- 红灯、绿灯、最终冒烟使用相同命令入口；最终正式验证另由统一构建与验证入口按固定提交基线执行，必须通过且检查项非空。
- 使用短合成预算，覆盖开关缺省、开启、关闭；快速与完整；本机、未知、云端、拉取请求、持续集成；串并行；剩余预算与单项超时；后代进程回收及无关进程存活；缓存与报告；诊断流式状态及真实错误。
- 保留核心真实入口代表及既有行为覆盖；按父端明确批准收缩低收益极端交叉案例，不声称等价100%覆盖。测试放统一测试目录；运行技能只保留最小运行内容。
- 本机真实冒烟可以核验视窗系统进程回收；其他操作系统需要相应平台证据，不能用本机通过冒充跨平台通过。

## 范围之外

- 不安装或全局更新插件，不发布，不推送，不合并主分支。
- 不修改其他仓库预算、消费者工具链记录、网络权限、钩子或并行数据任务。
- 不新增测试框架，不做全仓库重构，不提前修改正式规格或术语表。

## 待确认与流程证据

1. 用户已确认：“验证吧，先做验证好吧。60秒预算构建确实可以单独处理”。因此覆盖快速及完整验证，独立构建保持当前行为，既有项目预算不变。
2. 已确认命令级显式执行地点为基本路径，可选环境继承；未知且配置预算、强制开启的正式验证预检失败，不依赖宿主新增功能。
3. 用户已确认本次诊断保留单项超时及真实错误、实时逐检查耗时，结果不构成正式预算验收；第一版不新造检查项选择器。
4. 最高真实入口、两张串行票据、第一张后再第二张、全部完成后父端独立审查已获确认。其他仓库数据任务可并行；本插件内部两张票据仍串行。
5. 固定基线为 `1ee464d7a255d27ede3be29a1292ba98b9b5b737`；当前已登记同一工作树位于 `D:\My Project\my-agent-skills`，分支为主分支。
6. 起始状态仅发现未跟踪 `.claude/settings.local.json`；用户要求原样保留且不提交，该例外已在门禁一展示并获确认，不能称工作树干净。
7. 按进程回收涉及机器状态风险，采用完整开发流程。父端已实际读取本机转交的代码架构技能及参考，并报告基于云端源码调查应用该技能；本机仅消费结论，未自行架构或独立审查。
8. 本次已读取并使用带文档问答及其问答、领域建模技能：明确“执行地点”不等于“模型地点”，“总预算”不等于“单项超时”，“诊断完成”不等于“正式通过”；边界问题记录待确认，不擅自定案，不修改术语表。
9. 本次已使用转为规格和转为票据技能生成需求及票据。门禁一展示回执为 `Sentinel_37a744abf0e08191997327a71deccd53`；用户确认回执为 `Sentinel_abcbf241e2f88191a3e2964d70ed8db4`。批准分支为 `feat/local-verification-budget`，主实施模型与低思考强度由用户指定；准许本地提交，不准安装、发布、推送或合并。已有解释器受限时允许申请提权运行，不重装。
10. 最新预算变更授权回执为 `Sentinel_5767fb34fd0c8191b72c2c637ba76d35`，用户原文：“我授权你把那个技能仓库的验证预算调整到60秒”。此授权仅替代本仓库预算数值要求；先前30秒失败与诊断证据分别保留，不改写历史结果，其余门禁范围不变。

## 当前实施与第二道关卡准备状态（2026-10-03）

- 当前唯一工作区为 `D:\My Project\my-agent-skills\.local\worktrees\local-verification-budget`，功能分支 `feat/local-verification-budget`，固定基线仍为 `1ee464d7a255d27ede3be29a1292ba98b9b5b737`。早期主工作区登记及不准推送条款为当时历史状态，后续已明确批准隔离迁移和功能分支检查点提交推送；禁止修改原工作区或重新绑定全局工具继续有效。
- 两票按批准顺序串行完成实现。精确实现 `2ebf5efbc475199020a79c0f1922904b4909f3ab` 的完整无缓存正式验证通过：8组全部完成，外部54.8512462秒、报告54.7729244秒、退出0。证据提交 `2a3ec5471a28677eb5a20960c9c6979ce6f284cb` 已由父端远端双轴源码审查通过；本机不以自审替代。
- 01票短预算真实入口及恢复证据、02票诊断无总截止且保留真实失败/单项超时证据由统一测试覆盖；本轮正式构建验证216项及真实命令入口46项全部通过。此前红灯和失败记录保留，不改写历史。诊断证据不算正式验收。
- 父端释放重测资源后已单独运行固定基线快速验证：受测提交 `5d6f24a1621baac107ab85bae5b19dc73557cc3d`、基线 `1ee464d7a255d27ede3be29a1292ba98b9b5b737`，结果通过且已检查列表8项非空，全部有效缓存命中，无测试重跑；外部3.0349541秒、退出0。未清缓存，完整模式通过未替代此要求。
- 完整正式规格候选仅置于本工作区 `.local/spec-work/`。两项相关能力为构建验证插件契约及整库完整验证本地命令；既有警告模式改为仅关闭强制开关或豁免场景，增加本地总截止/上下文/诊断/兼容报告约定，整库正式命令明确本地地点。保持标题身份、既有无关要求和 narrower（更窄）性能目标，不删除规则或扩大其他领域。
- 已知限制：完整验证余量约5秒，30—40秒目标未达；无限输出阻塞及人为退出组合没有等价100%替代，正常模板锁等待未计时，跨平台行为仍需对应平台证据。第二道关卡前不新增产品或性能修改。
- 第二道关卡拟请求批准：仅应用展示的完整正式规格预览、执行配置规定的拉取请求检查和审查、通过后合并至主干并按准确授权范围安全清理；不安装、不发布、不改变机器级工具绑定。关联工作区保留或清理由父端明确交付动作后纳入展示，不在本机提前执行。
### 完整正式规格预览已准备，尚未应用

- 官方自有规格公开入口已生成并校验完整增量和预览，状态为待应用；待应用仅表示预览就绪，不表示用户批准。仅修改构建验证插件及整库完整运行两项能力，3项既有需求更新、2项新增预算/诊断需求，以及1项整库本机命令更新；不删除需求、不改无关能力或更窄性能目标。
- 完整文件级差异：本工作区 .local/spec-work/current/formal-spec.diff；完整预览：.local/spec-work/current/preview/；增量：.local/spec-work/current/delta/。完整差异文件校验编号为 SHA256（安全散列） a7869653d7a2618e942c5ac2ba24a90dad11c2004a0652cf012e9c06bc1ff029。初始候选证据快照保留于该运行的 evidence（证据）目录，输入及正式规格指纹保留，后续流程状态更新不更改候选行为。
- 当前运行使用既有机器级开发绑定提供自有规格实现，但公开诊断确认目标是本隔离工作树；未重新绑定、安装、写原工作区或正式规格。固定基线差异检查及未跟踪正式规格检查均成功、输出为空。
- 父端已释放机器并明确放行一次固定基线验证，该次已按有效缓存通过，原始日志与元数据保留。最终用户批准条款由父端完整展示，当前不提前执行任何交付动作。

## 第二道关卡最少完整确认条款草案

1. 批准且仅批准完整差异 `.local/spec-work/current/formal-spec.diff` 所展示的两项能力正式规格变更；应用前复核正式规格、增量、预览及实现身份，任何内容漂移先停止，不默默扩大范围。
2. 批准在本功能分支执行完成拉取请求流程：创建或同步至主干的拉取请求，运行并等待配置要求的检查和审查，通过后按配置合并；不得直写主干、强推、安装、发布或改变机器级工具绑定。
3. 交付后保留本独立工作区，不清理、不删除。原主工作区是否同步必须单独明确纳入本次展示后的授权；同步原主工作区会让绑定该处的全局开发入口生效，未获准确授权时不执行同步，不能把第二道关卡泛化为原工作区开发权限。
4. 接受已知证据限制：完整正式验证约54.85秒、仅约5秒余量，30—40秒目标未达到；固定基线验证全部为有效缓存命中而非再执行；已删除极端交叉覆盖不声称等价100%，正常模板锁等待未计时，其他平台需要各自验证。此次批准不授权继续产品或性能扩展。

上述仅为供父端完整展示的草案，尚无第二道关卡用户确认；未执行其后的动作。最后提交只更新候选状态及证据，不改受测实现、预算配置、检查清单或正式规格。
## 可从远端读取的完整正式规格差异

以下为已由官方自有规格入口校验的完整文件级差异原文，仅用于第二道关卡展示，**尚未应用正式规格，也尚未获得第二道关卡批准**。没有省略任何差异段落。

原始差异文件 SHA256（安全散列）：`a7869653d7a2618e942c5ac2ba24a90dad11c2004a0652cf012e9c06bc1ff029`。该编号对应 `.local/spec-work/current/formal-spec.diff` 原文件字节；下方代码块用于远端可访问展示，文件容器及换行格式不属于原始差异校验对象。

待父端展示的准确授权范围为：仅应用下方预览、创建拉取请求、运行配置要求的持续集成检查和审查、通过后合并至主干。是否同步原主工作区必须明确授权；该同步会让绑定原处的全局开发入口生效。本独立工作区保留且不清理，不安装、不发布、不改变全局绑定。本机此时只补展示材料，不请求或执行第二道关卡。

```diff
--- a/full-verification-runtime/spec.md
+++ b/full-verification-runtime/spec.md
@@ -74,11 +74,12 @@
 - **THEN** the runner（运行器） MUST treat missing pytest-xdist（Pytest 并行插件） as a failed check（检查项）
 - **THEN** `checkParallel`（检查项间并行） MUST NOT by itself imply pytest-xdist（Pytest 并行插件） usage
 ### Requirement: Full verification has a local runtime target
-Full repository end-to-end verification SHALL（必须）complete in under 60 seconds on the local development machine while preserving the existing behavior coverage. This repository-level target is distinct from any narrower plugin test-suite target. The current full verification command for this repository SHALL（必须）be `build-and-verify verify --project . --full` unless a later MySpec（自有规格）change explicitly replaces it.
+Full repository end-to-end verification SHALL（必须）complete in under 60 seconds on the local development machine while preserving the existing behavior coverage. This repository-level target is distinct from any narrower plugin test-suite target. The current full verification command for this repository SHALL（必须）be `build-and-verify verify --project . --full --execution-context local` unless a later MySpec（自有规格）change explicitly replaces it.
 
 #### Scenario: Full repository verification completes under target
 - **WHEN** a developer runs the full repository verification command
 - **THEN** the command MUST complete in under 60 seconds on the local development machine
+- **THEN** the execution context MUST explicitly identify local（本机）execution, and successful full verification MUST NOT be substituted for fixed-baseline verification（固定基线验证）required by the development workflow
 - **THEN** the command MUST run all configured verify checks（验证检查项） from `.build-and-verify/config.json`, including the repository's Python（Python 语言）test checks
 - **THEN** this repository-level target MUST NOT redefine a narrower target for the Build and Verify（构建与验证）plugin's own test suite
 
--- a/test-framework-plugin/spec.md
+++ b/test-framework-plugin/spec.md
@@ -50,91 +50,85 @@
 - **THEN** agent（代理） MUST 允许用户在存在依赖或环境问题时仍写入配置
 - **THEN** agent（代理） MUST 明确说明用户可以让 agent（代理）协助处理环境和外部依赖问题
 ### Requirement: Full verify provides non-blocking total performance warnings
-Build and Verify（构建与验证） MUST allow a target repository to declare an optional positive integer `verify.fullBudgetSeconds`（完整验证预算秒数） for full verification wall time, and the performance result MUST NOT replace or change functional verification status.
+Build and Verify（构建与验证） MUST 接受可选正整数 `verify.fullBudgetSeconds`（完整验证预算秒数）。明确本机执行时该值同时约束一次快速或完整验证；强制开关关闭，或云端、拉取请求及可靠持续集成场景时，预算告警 MUST NOT 替代真实功能结果。
 
 #### Scenario: Full verify finishes before budget
-- **WHEN** a user runs `verify --full`（完整验证） with a valid `verify.fullBudgetSeconds`
-- **AND** all configured checks finish within that budget
-- **THEN** the system MUST complete all configured checks
-- **THEN** the system MUST NOT output `performance-warning`（性能警告）
-- **THEN** the exit status MUST remain determined by functional verification results
+- **WHEN** 完整验证在配置预算内完成全部检查
+- **THEN** 系统 MUST NOT 输出 `performance-warning`（性能警告）
+- **THEN** 退出状态 MUST 由真实检查结果确定
 
 #### Scenario: Full verify exceeds budget
-- **WHEN** a user runs `verify --full`（完整验证） with a valid `verify.fullBudgetSeconds`
-- **AND** total full verification wall time exceeds that budget
-- **THEN** the system MUST complete all configured checks before evaluating the budget result
-- **THEN** the system MUST output `performance-warning`（性能警告） with total time, budget, exceeded time, and exceeded percentage
-- **THEN** the performance warning MUST NOT change the exit status determined by functional verification results
+- **WHEN** 本机强制开关关闭，或执行地点为云端、拉取请求或可靠持续集成
+- **AND** 完整验证超过配置预算
+- **THEN** 系统 MUST 完成配置检查后输出总耗时、预算和超出时长告警
+- **THEN** 告警 MUST NOT 改变功能检查确定的退出状态
+- **THEN** 云端、拉取请求及可靠持续集成 MUST 保留既有完整验证预算告警行为
 
 #### Scenario: Functional failure remains authoritative
-- **WHEN** one or more configured checks fail during full verification
-- **THEN** the system MUST report functional verification failure using its existing exit status
-- **THEN** an under-budget or over-budget result MUST NOT replace that functional result
+- **WHEN** 任一检查失败、异常或发生单项超时
+- **THEN** 系统 MUST 返回真实失败
+- **THEN** 开关关闭、预算内完成或仅有预算告警 MUST NOT 将真实失败变为通过
 
 #### Scenario: Invalid full budget is rejected
-- **WHEN** `.build-and-verify/config.json` declares `verify.fullBudgetSeconds`
-- **AND** the value is not a positive integer
-- **THEN** configuration validation MUST fail before configured checks run
-- **THEN** the system MUST report the invalid field
+- **WHEN** 配置预算不是正整数，或 `verify.enforceLocalBudget`（本机预算强制开关）不是布尔值
+- **THEN** 系统 MUST 在启动检查前明确拒绝并报告无效字段
 ### Requirement: Full verify records a fixed performance report on demand or over budget
-Build and Verify（构建与验证） MUST support `verify --full --performance-report`（完整验证性能报告） and MUST conditionally record one fixed-format report without coupling to repository business test output.
+Build and Verify（构建与验证） MUST 保留固定报告路径和既有核心计时字段，并兼容补充本机截止与诊断状态；报告 MUST NOT 依赖业务测试输出结构。
 
 #### Scenario: Explicit report is written within budget
-- **WHEN** a user runs `verify --full --performance-report`
-- **AND** full verification does not exceed its configured budget or has no configured budget
-- **THEN** the system MUST write `.build-and-verify/runs/performance-report.json`
-- **THEN** the exit status MUST remain determined by functional verification results
+- **WHEN** 用户运行 `verify --full --performance-report`（完整验证性能报告）
+- **THEN** 系统 MUST 写入 `.build-and-verify/runs/performance-report.json`（性能报告）
+- **THEN** 报告 MUST 与真实退出结果一致
 
 #### Scenario: Over-budget run writes report automatically
-- **WHEN** full verification exceeds `verify.fullBudgetSeconds`
-- **THEN** the system MUST write `.build-and-verify/runs/performance-report.json` whether or not `--performance-report` was provided
-- **THEN** the system MUST output the report path
+- **WHEN** 本机快速或完整验证超预算、发生总截止，或进入诊断模式
+- **THEN** 系统 MUST 自动记录报告并输出报告路径
+- **THEN** 总截止报告 MUST 包含失败原因、耗时、预算、未完成及未启动检查
+- **THEN** 未完成检查 MUST NOT 被报告为已通过
 
 #### Scenario: Unrequested under-budget run does not touch the fixed report
-- **WHEN** full verification does not exceed its configured budget or has no configured budget
-- **AND** `--performance-report` was not provided
-- **THEN** the system MUST NOT create or modify the fixed report for that run
+- **WHEN** 非诊断验证未超预算且未请求性能报告
+- **THEN** 系统 MUST NOT 创建、覆盖或删除已有固定报告
 
 #### Scenario: Report schema is stable
-- **WHEN** the system writes the performance report
-- **THEN** the report MUST contain exactly `schemaVersion`, `runtimeVersion`, `generatedAt`, `totalSeconds`, `budgetSeconds`, `overBudget`, `verificationStatus`, and `checks`
-- **THEN** `generatedAt` MUST use UTC（协调世界时）
-- **THEN** `budgetSeconds` and `overBudget` MUST be `null` when no budget is configured
-- **THEN** `checks` MUST record every configured check in configuration order with its id, status, and duration
+- **WHEN** 系统写入性能报告
+- **THEN** 报告 MUST 保留 `schemaVersion`（结构版本）、`runtimeVersion`（运行时版本）、`generatedAt`（生成时间）、`totalSeconds`（总秒数）、`budgetSeconds`（预算秒数）、`overBudget`（超预算状态）、`verificationStatus`（验证状态）和 `checks`（检查列表）核心字段
+- **THEN** 本机及诊断报告 MUST 兼容补充执行地点、诊断标记、原因、未完成及未启动信息
+- **THEN** 生成时间 MUST 使用协调世界时；无预算时预算及超预算字段 MUST 为 null（空值）
+- **THEN** 检查列表 MUST 按配置顺序记录检查编号、状态及耗时
 
 #### Scenario: Report failure does not block verification
-- **WHEN** the performance report cannot be written
-- **THEN** the system MUST output `performance-report-warning`（性能报告警告）
-- **THEN** the report failure MUST NOT change the exit status determined by functional verification results
+- **WHEN** 报告无法写入
+- **THEN** 系统 MUST 输出 `performance-report-warning`（性能报告警告）
+- **THEN** 报告错误 MUST NOT 将真实失败改为通过或取消本机总截止
 
 #### Scenario: Incomplete full verification does not produce performance output
-- **WHEN** full verification does not return a result for every selected check
-- **THEN** the system MUST NOT evaluate the performance budget or output `performance-warning`（性能警告）
-- **THEN** the system MUST NOT create or modify the fixed report
-- **THEN** the exit status MUST remain determined by the existing functional verification behavior
+- **WHEN** 豁免场景的既有完整验证未返回全部已选检查结果
+- **THEN** 系统 MUST 保留既有不计算完整预算及不覆盖固定报告的行为
+- **THEN** 本机总截止 MUST 仍记录未完成及未启动状态并返回失败
 
 #### Scenario: Fast verification does not touch performance reporting
-- **WHEN** a user runs verify（快速验证） without `--full`
-- **THEN** the system MUST NOT evaluate `verify.fullBudgetSeconds`
-- **THEN** the system MUST NOT output a performance warning or create, modify, or remove the fixed report
+- **WHEN** 非本机且非诊断的快速验证运行
+- **THEN** 系统 MUST 保留既有不评估完整预算、不改固定报告的行为
+- **THEN** 本机快速验证 MUST 使用相同总预算，超预算时 MUST 记录报告
 
 #### Scenario: Performance report requires full mode
-- **WHEN** a user provides `--performance-report` without `--full`
-- **THEN** argument validation MUST fail before configured checks run
-- **THEN** the system MUST explain that performance reporting requires full verification
+- **WHEN** 用户显式提供 `--performance-report`（性能报告参数）但未提供 `--full`（完整模式参数）
+- **THEN** 参数校验 MUST 在检查前失败并说明完整模式要求
+- **THEN** 此约束 MUST NOT 阻止本机截止或诊断自动记录报告
 ### Requirement: Guided initialization supports optional full verification budget
-Build and Verify Init（构建与验证初始化） MUST allow a user to opt into the generic full verification budget without supplying a repository-specific default.
+Build and Verify Init（构建与验证初始化） MUST 允许用户选择可选正整数预算，不替任何项目写死数值，且 MUST 准确说明本机强制开关缺省开启。
 
 #### Scenario: User enables full verification budget
-- **WHEN** a user chooses to configure a full verification budget during guided initialization
-- **THEN** the questionnaire MUST explain that exceeding the budget only warns and records a report
-- **THEN** the generated config MUST contain the user-confirmed positive integer `verify.fullBudgetSeconds`
-- **THEN** the final confirmation summary and post-write validation MUST show the configured value
+- **WHEN** 用户选择配置验证预算
+- **THEN** 问答及最终确认 MUST 展示用户确认数值，并说明该值用于本机单次快速与完整验证
+- **THEN** 问答 MUST 说明本机缺省到时终止并失败，关闭开关仅告警，豁免场景保留既有行为
+- **THEN** 生成配置 MUST 包含用户确认的预算数值，写后校验 MUST 检查预算与开关类型
 
 #### Scenario: User leaves full verification budget disabled
-- **WHEN** a user does not choose a full verification budget during guided initialization
-- **THEN** the generated config MUST omit `verify.fullBudgetSeconds`
-- **THEN** the plugin template MUST NOT impose a repository-specific performance target
+- **WHEN** 用户不选择配置预算
+- **THEN** 生成配置 MUST 省略预算字段
+- **THEN** 插件模板 MUST NOT 强加项目专属性能目标
 ### Requirement: Build and Verify tests minimize repeated real entrypoints
 Build and Verify（构建与验证） tests MUST keep real entrypoint coverage small and move repeated branch coverage to in-process（进程内） tests. Its 30-second target applies to the plugin's own test suite and is distinct from the repository-wide end-to-end full verification target.
 
@@ -561,3 +555,42 @@
 - **WHEN** initialization or configuration review handles existing checks
 - **THEN** it MUST preserve valid `pr` values and explain that omission means `true`
 - **THEN** it MUST identify non-boolean values as invalid and describe which checks run in each scene
+### Requirement: Local verification shares one enforced invocation budget
+Build and Verify（构建与验证） MUST 在明确本机且配置预算的正式验证中缺省强制一次命令的总截止，快速与完整模式共用既有预算字段；独立构建及不同命令调用 MUST NOT 被累计纳入。
+
+#### Scenario: Local verification reaches its deadline
+- **WHEN** 明确本机的正式验证开启强制限制且达到总截止
+- **THEN** 准备、缓存选择、串行或并行检查、排队、收尾及迁移 MUST 共用该次预算
+- **THEN** 系统 MUST 停止后续检查，终止本次拥有的进程及后代，并有界回收
+- **THEN** 系统 MUST NOT 终止无关用户进程
+- **THEN** 系统 MUST 返回非零总预算超时失败，且单项等待 MUST 受剩余总预算及单项超时中较小值约束
+
+#### Scenario: Execution context is explicit or inherited
+- **WHEN** 用户声明 `--execution-context local|cloud|ci`（执行地点：本机、云端、持续集成）或继承 `BUILD_AND_VERIFY_EXECUTION_CONTEXT`（执行地点环境声明）
+- **THEN** 命令参数 MUST 优先于环境继承
+- **THEN** 拉取请求及可靠持续集成标识 MUST 优先豁免本机强制规则
+- **THEN** 系统 MUST NOT 根据模型地点、操作系统或仅有 `CODEX_CI=1`（宿主内部标记）推断持续集成
+
+#### Scenario: Unknown strict context is rejected
+- **WHEN** 正式验证执行地点未知且配置预算、强制开启
+- **THEN** 系统 MUST 在启动检查前明确拒绝
+- **THEN** 系统 MUST NOT 静默豁免或伪报本机
+
+#### Scenario: Passed cache remains truthful
+- **WHEN** 本机验证复用或更新通过缓存
+- **THEN** 快速模式 MUST 仅复用输入、配置、命令和运行身份匹配的成功结果
+- **THEN** 完整模式 MUST NOT 读取成功缓存跳过检查
+- **THEN** 超时、取消和未启动 MUST NOT 写成功缓存；截止前真实完成的成功检查 MAY（可以）缓存
+### Requirement: One-shot diagnostic preserves real failures without formal acceptance
+Build and Verify（构建与验证） MUST 提供 `--diagnostic`（一次性诊断），仅取消本次总截止，不改变项目配置或正式验收语义。
+
+#### Scenario: Diagnostic runs beyond the total budget
+- **WHEN** 用户启用一次性诊断
+- **THEN** 系统 MUST 保留单项防挂超时、真实检查失败及异常
+- **THEN** 系统 MUST 实时输出检查开始、结束、耗时及未完成状态
+- **THEN** 系统 MUST 明确标记诊断结果不构成正式预算通过，且 MUST NOT 写入正式成功缓存
+
+#### Scenario: Diagnostic observes individual test costs
+- **WHEN** 用户定位单项测试或子测试耗时
+- **THEN** 插件文档 MUST 引导使用测试框架原生选择及计时能力
+- **THEN** 插件 MUST NOT 宣称拥有新增检查选择器或可解析所有业务子测试
```
