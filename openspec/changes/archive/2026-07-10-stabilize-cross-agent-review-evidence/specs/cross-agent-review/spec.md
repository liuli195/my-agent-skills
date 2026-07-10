## MODIFIED Requirements

### Requirement: 跨 agent review 输入契约
系统 MUST 只接收一个 caller-prepared `review-input.json`（调用方准备的审查输入文件）作为 Cross Agent Review（跨代理审查）的启动输入。该文件 MUST 位于同一次 review（审查）的 `prepared-inputs`（预备输入目录）下，并包含审查对象、模式和权威上下文文件引用；调用方 MAY 在同一文件中声明仅摘要路径和跨提交重新校验策略。

#### Scenario: 输入完整
- **WHEN** 调用方提供 `--input-file`，且该文件路径为 `.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json`
- **AND** `review-input.json` 包含 `change`、`mode`、`base_ref`、`head_ref`、`spec_file`、`design_file` 和 `plan_file`
- **THEN** review mechanism（审查机制）可以启动 Cross Agent Review（跨代理审查）

#### Scenario: 输入缺少关键字段
- **WHEN** `review-input.json` 缺少 `change`、`mode`、`base_ref`、`head_ref`、`spec_file`、`design_file` 或 `plan_file` 任一字段
- **THEN** review mechanism（审查机制）拒绝启动，并报告缺失字段

#### Scenario: 输入文件缺失
- **WHEN** `review-input.json` 引用的 `spec_file`、`design_file` 或 `plan_file` 不存在
- **THEN** review mechanism（审查机制）拒绝启动，并报告缺失文件

#### Scenario: prepared inputs 边界
- **WHEN** 调用方准备 review input（审查输入）
- **THEN** 调用方 MUST 把 `review-input.json` 写入同一次 review（审查）的 `prepared-inputs`（预备输入目录）
- **AND** review mechanism（审查机制）MUST NOT 从分散的 `spec_file`、`design_file` 或 `tasks_file` CLI（命令行接口）参数启动

#### Scenario: prepared inputs 只包含一个输入文件
- **WHEN** review mechanism（审查机制）读取 `prepared-inputs`（预备输入目录）
- **THEN** 该目录作为 review input（审查输入）MUST 只包含 `review-input.json` 一个普通文件
- **AND** 如果该目录包含 `spec.md`、`design.md`、`tasks.md`、`plan.md`、`manifest.json` 或其他普通文件，review mechanism（审查机制）MUST 拒绝启动并报告 unexpected prepared input（意外预备输入）

#### Scenario: plan file 取代 tasks file
- **WHEN** 调用方准备 review input（审查输入）
- **THEN** `review-input.json` MUST 使用 `plan_file` 引用 `docs/superpowers/plans/` 下的 Superpowers plan（超级能力计划）
- **AND** review mechanism（审查机制）MUST NOT 要求或读取 `tasks_file`

#### Scenario: 调用方声明 summary only
- **WHEN** 调用方认为某个已变更文件只需作为摘要信息进入主要审查
- **THEN** 调用方 MAY 在 `summary_only` 中声明该文件的精确项目相对路径和非空 `reason`
- **AND** `summary_only` MUST NOT 使用扩展名、目录、glob（通配模式）、文件大小或 Comet（双星工作流）名称作为隐式排除规则

#### Scenario: 调用方声明 revalidation policy
- **WHEN** 调用方准备允许后续跨提交机械重新校验
- **THEN** 调用方 MAY 在 `revalidation_policy` 中按精确项目相对路径声明受支持校验器及其参数
- **AND** 该声明 MUST NOT 改变首次真实审查的文件范围

### Requirement: reviewer 角色派发
系统 MUST 将一次 review（审查）拆分给两个明确角色的 reviewer agent（审查代理），为每个角色建立独立输入范围和独立运行结果，并要求每个 reviewer（审查代理）返回轻量 Markdown（标记文本）审查结果。

#### Scenario: 默认角色
- **WHEN** review mechanism（审查机制）启动默认 review（审查）
- **THEN** 系统 MUST 派发 `spec-alignment`（规格对齐）和 `implementation-correctness`（实施正确性）两个 reviewer（审查代理）

#### Scenario: spec alignment 角色范围
- **WHEN** 系统派发 `spec-alignment`（规格对齐）角色
- **THEN** 该角色 MUST 取得当前 `spec_file`、`design_file` 和 `plan_file` 权威上下文、`full_review`（完整审查）差异以及 `summary_only`（仅摘要）清单和理由
- **AND** 该角色 MAY 按需读取 `summary_only`（仅摘要）文件的原文或差异

#### Scenario: implementation correctness 角色范围
- **WHEN** 系统派发 `implementation-correctness`（实施正确性）角色
- **THEN** 该角色 MUST 以 `full_review`（完整审查）中的实现、测试和配置差异作为主要输入
- **AND** 该角色 MAY 按需读取权威上下文和 `summary_only`（仅摘要）文件，但 MUST NOT 把计划或流程文档作为默认主要差异

### Requirement: review（审查）模式选择
系统 MUST 支持 convergence（收敛）和 endless（无尽）两种 review（审查）模式，且输出契约保持一致。

#### Scenario: 模式写入审查状态
- **WHEN** 调用方选择 `convergence`（收敛）或 `endless`（无尽）模式
- **THEN** `review-state.json`（审查状态文件）的 `subject.mode` MUST 记录本次使用的 `mode`
- **AND** report（报告）与 retry（重试）MUST 继续绑定该模式

### Requirement: review input snapshots
系统 MUST 让 reviewer prompt（审查代理提示词）引用 `review-input.json`（审查输入文件）、`review-state.json`（审查状态文件）和由插件执行的短 role-input command（角色输入命令），不内联大 diff（差异）内容或变更文件清单。

#### Scenario: reviewer prompt 内容
- **WHEN** 系统生成 reviewer prompt（审查提示词）
- **THEN** prompt（提示词）MUST 指示 reviewer agent（审查代理）返回固定 Markdown（标记文本）格式，并为每个 finding（发现项）包含 `Severity`
- **AND** prompt（提示词）MUST NOT 内联完整 diff output（差异输出）、context file（上下文文件）正文、changed files（变更文件）清单或长命令块
- **AND** prompt（提示词）MUST NOT 提供无路径范围的完整 `git diff`

#### Scenario: role input command 强制路径范围
- **WHEN** reviewer（审查代理）运行 prompt（提示词）提供的 role-input command（角色输入命令）
- **THEN** 插件 MUST 从 `review-state.json`（审查状态文件）读取该角色的精确文件范围
- **AND** 插件 MUST 通过参数数组执行 path-scoped Git diff（路径限定版本差异），不得依赖 reviewer（审查代理）自行拼接文件路径

#### Scenario: reviewer prompt 使用独立模板
- **WHEN** 系统生成 reviewer prompt（审查提示词）
- **THEN** Python（脚本语言）脚本 MUST 作为调用方和渲染入口，负责提供模板变量、读取模板和渲染模板
- **AND** 模板变量 MUST 限制为 role（角色）、input file path（输入文件路径）、state file path（状态文件路径）、role input command（角色输入命令）、role focus（角色重点）和 severity rubric（严重级别规则）

### Requirement: head_ref_short path convention is explicit
系统 MUST 明确 `head_ref_short`（短头引用）等于 `head_ref`（头引用）的前 12 个字符，并在 Cross Agent Review（跨代理审查）的用户可见路径中保持一致。

#### Scenario: Review input path uses first 12 characters
- **WHEN** 调用方准备 `review-input.json`（审查输入文件）
- **THEN** `<head_ref_short>`（短头引用） MUST equal the first 12 characters of `head_ref`（头引用）
- **AND** the input path（输入路径） MUST be `.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json`

#### Scenario: Run output prints copyable review input path
- **WHEN** `cross-agent-review run`（跨代理审查运行） accepts an input file（输入文件）
- **THEN** output（输出） MUST include the copyable `review-input.json`（审查输入文件） path used for the run
- **AND** output（输出） MUST expose the same 12-character `head_ref_short`（短头引用） value

#### Scenario: Report and state use the same short reference
- **WHEN** `run`（运行）、`retry`（重试）或 `revalidate`（重新校验）写入当前提交的报告和状态
- **THEN** 输出目录 MUST 使用同一个 12 位 `head_ref_short`（短头引用）
- **AND** 命令输出 MUST 包含可复制的报告和状态路径

## ADDED Requirements

### Requirement: 角色化文件投影
系统 MUST 从 Git（版本控制）审查范围生成单一文件清单，并让每个文件恰好属于 `authoritative_context`（权威上下文）、`summary_only`（仅摘要）或 `full_review`（完整审查）之一；分类 MUST 写入 `review-state.json`（审查状态文件）。

#### Scenario: 权威上下文使用精确路径
- **WHEN** 已变更文件的项目相对路径精确等于 `spec_file`、`design_file` 或 `plan_file`
- **THEN** 系统 MUST 把该文件分类为 `authoritative_context`（权威上下文）
- **AND** 系统 MUST NOT 通过目录或扩展名推导其他权威上下文

#### Scenario: summary only 需要显式理由
- **WHEN** 已变更文件的精确路径只在 `summary_only` 中出现一次，且声明包含非空理由
- **THEN** 系统 MUST 把该文件分类为 `summary_only`（仅摘要）并记录理由
- **AND** 该分类 MUST NOT 禁止 reviewer（审查代理）按需读取文件

#### Scenario: 未分类文件默认完整审查
- **WHEN** 已变更文件既不是精确权威上下文，也没有有效 `summary_only` 声明
- **THEN** 系统 MUST 把该文件分类为 `full_review`（完整审查）

#### Scenario: 分类声明歧义
- **WHEN** 同一路径被重复声明、同时落入多个调用方分类、位于项目外或不是审查范围内的变更文件
- **THEN** 系统 MUST 拒绝启动真实 reviewer（审查代理）并报告具体路径和原因

### Requirement: 可恢复审查状态
系统 MUST 在 `.local/cross-agent-review/<change>/<head_ref_short>/review-state.json`（审查状态文件）记录审查对象、输入哈希、文件分类、角色范围、尝试记录、角色终态、原始输出和输出哈希，并在每个角色返回后原子更新。

#### Scenario: 角色成功立即持久化
- **WHEN** 一个 reviewer（审查代理）在另一个 reviewer（审查代理）结束前成功返回非空结果
- **THEN** 系统 MUST 把该角色状态记录为 `completed`（完成）
- **AND** 系统 MUST 在等待另一个角色期间保存其尝试、原始输出和输出哈希

#### Scenario: 角色运行失败
- **WHEN** reviewer（审查代理）派发失败或返回非法结果
- **THEN** 系统 MUST 把该角色状态记录为 `failed`（失败）
- **AND** 系统 MUST 为该角色保存带 CRITICAL（严重阻断）finding（发现项）的 Markdown（标记文本）结果

#### Scenario: 角色超时
- **WHEN** reviewer（审查代理）超过插件声明的 timeout（超时）
- **THEN** 系统 MUST 把该角色状态记录为 `timed_out`（超时）
- **AND** 系统 MUST 保留已经 `completed`（完成）的另一个角色，不得把两个角色都改写为失败

#### Scenario: 默认输出
- **WHEN** 一次真实 review（审查）达到两个角色终态
- **THEN** 系统 MUST 在当前短提交目录写入 `review-report.md`（审查报告）和 `review-state.json`（审查状态文件）
- **AND** 系统 MUST NOT 写入 Agent Guard（代理守卫）通过证据
- **AND** 系统 MUST NOT 默认写入 `review-pass.json`、`review-results.json`、`inputs/manifest.json`、`prompts/<role>.txt` 或 `raw/<role>.txt`

### Requirement: 只重试失败角色
系统 MUST 提供 `retry`（重试）入口，只重新派发当前状态为 `failed`（失败）或 `timed_out`（超时）的角色，并保留其他角色的成功结果。

#### Scenario: 一个角色失败
- **WHEN** `review-state.json`（审查状态文件）中一个角色为 `completed`（完成），另一个角色为 `failed`（失败）或 `timed_out`（超时）
- **THEN** `retry`（重试） MUST 只派发失败或超时角色
- **AND** 成功角色的尝试、输出和输出哈希 MUST 保持不变

#### Scenario: 重试范围不扩大
- **WHEN** `retry`（重试）派发一个失败或超时角色
- **THEN** 该角色输入范围 MUST 等于或小于首次运行中记录的该角色范围
- **AND** `retry`（重试） MUST NOT 引入原文件清单之外的路径

#### Scenario: 没有可重试角色
- **WHEN** 两个角色都为 `completed`（完成）或 `reused`（复用）
- **THEN** `retry`（重试） MUST 不派发 reviewer（审查代理）并报告 `no_retryable_roles`

### Requirement: 机械变化跨提交重新校验
系统 MUST 提供 `revalidate`（重新校验）入口，只在上一提交审查事实完整、所有提交间变化都恰好匹配声明式机械策略时复用结果；该入口 MUST 保持当前提交头绑定，且 MUST NOT 调用 reviewer SDK（审查代理开发包）或自动写入通过证据。

#### Scenario: checkbox only 变化通过
- **WHEN** 一个已变更精确路径声明 `checkbox-only`（仅复选框）
- **AND** 两个提交中的行数、顺序和除 Markdown task checkbox（标记任务复选框）状态外的全部内容相同
- **THEN** 该文件通过机械重新校验

#### Scenario: mapping fields only 变化通过
- **WHEN** 一个已变更精确路径声明 `mapping-fields-only`（仅映射字段）、`json` 或 `yaml` 格式及非空顶层字段列表
- **AND** 文件是可解析的 JSON（数据文件）或 YAML（配置文件）顶层映射
- **AND** 删除声明字段后两个提交的解析结构完全相同
- **THEN** 该文件通过机械重新校验

#### Scenario: 全部变化可证明
- **WHEN** 上一状态绑定的输入、报告和角色输出哈希均匹配
- **AND** 上一状态的两个角色都为 `completed`（完成）
- **AND** 上一提交到当前提交的每个变化文件都恰好通过一条声明策略
- **AND** 当前 worktree（工作区）干净且当前完整 `HEAD`（提交头）匹配新输入
- **THEN** 系统 MUST 不调用 reviewer SDK（审查代理开发包）
- **AND** 系统 MUST 为当前短提交目录生成新 `review-report.md`（审查报告）和 `review-state.json`（审查状态文件）
- **AND** 两个角色状态 MUST 为 `reused`（复用），并记录来源提交、来源状态和已验证变化

#### Scenario: 重新校验拒绝不明确变化
- **WHEN** 存在未声明文件、重叠策略、rename（重命名）、copy（复制）、规格变化、设计变化、解析失败、脏工作区、提交头不匹配、输入哈希不匹配、报告哈希不匹配或角色输出哈希不匹配
- **THEN** 系统 MUST 拒绝复用并报告具体原因
- **AND** 系统 MUST 不调用 reviewer SDK（审查代理开发包）、不生成伪造审查结果且不写入通过证据

#### Scenario: 禁止链式复用
- **WHEN** 上一状态任一角色为 `reused`（复用）而不是 `completed`（完成）
- **THEN** 系统 MUST 拒绝再次 `revalidate`（重新校验）
- **AND** 调用方 MUST 运行真实 review（审查）建立新的语义基线

## REMOVED Requirements

### Requirement: review pass marker
**Reason**: `mark-pass`（标记通过）把 Agent Guard（代理守卫）的画像、产物、路径和证据字段耦合进 Cross Agent Review（跨代理审查），违反“审查方只产出事实、主代理决定、守卫拥有证据契约”的职责边界。

**Migration**: 主代理读取 `review-report.md`（审查报告）和 `review-state.json`（审查状态文件）并确认没有未处理的 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）finding（发现项）后，显式调用 Agent Guard（代理守卫）的通用 `record-evidence`（记录证据）入口。Cross Agent Review（跨代理审查）不再提供 `mark-pass`（标记通过）命令，也不再包含任何 Guard Profile（守卫画像）、artifact id（产物编号）、证据路径或 `guard-evidence/v1`（守卫证据第一版）字段知识。
