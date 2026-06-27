# cross-agent-review Specification

## Purpose
Define the independent cross-agent review workflow, reviewer roles, report contract, and guard pass marker handoff.
## Requirements
### Requirement: 跨 agent review 输入契约
系统 MUST 只接收一个 caller-prepared `review-input.json`（审查输入文件）作为 cross-agent-review（跨代理审查）的启动输入。该文件 MUST 位于同一次 review（审查）的 `prepared-inputs`（预备输入目录）下，并包含 review subject（审查对象）、模式和上下文文件引用。

#### Scenario: 输入完整
- **WHEN** 调用方提供 `--input-file`，且该文件路径为 `.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json`
- **AND** `review-input.json` 包含 `change`、`mode`、`base_ref`、`head_ref`、`spec_file`、`design_file` 和 `plan_file`
- **THEN** review mechanism（审查机制）可以启动跨 agent review（跨代理审查）

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

### Requirement: review subject 绑定
系统 MUST 把 review（审查）绑定到 caller-prepared `review-input.json`（审查输入文件）声明的 `base_ref`、`head_ref` 和上下文文件。

#### Scenario: 启动时工作区不干净
- **WHEN** review mechanism（审查机制）启动时 `git status --short` 非空，且变化不属于本次 `review-input.json` 或本次输出目录
- **THEN** 它拒绝启动 reviewer，并不得生成 `review-report.md`

#### Scenario: 运行时输入输出例外
- **WHEN** `git status --short` 只包含本次 `.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json` 或本次输出目录中的 review runtime artifacts（审查运行产物）
- **THEN** review mechanism（审查机制）MAY 继续运行
- **AND** 该例外 MUST NOT 放行其他 workspace（工作区）变更
- **AND** 该 allowlist（允许清单）MUST 同时适用于启动和派发前的所有 clean worktree（干净工作区）检查

#### Scenario: 派发前工作区变化
- **WHEN** reviewer 派发前工作区变为 dirty（未提交）
- **THEN** review mechanism（审查机制）拒绝继续，并不得生成 `review-report.md`

### Requirement: reviewer 角色派发
系统 MUST 将一次 review（审查）拆分给两个明确角色的 reviewer agent（审查代理），并要求每个 reviewer 返回轻量 Markdown（标记文本）审查结果。

#### Scenario: 默认角色
- **WHEN** review mechanism（审查机制）启动默认 review（审查）
- **THEN** 系统 MUST 派发 `spec-alignment` 和 `implementation-correctness` 两个 reviewer（审查代理）

### Requirement: review（审查）模式选择
系统 MUST 支持 convergence（收敛）和 endless（无尽）两种 review（审查）模式，且输出契约保持一致。

#### Scenario: 模式写入 pass marker
- **WHEN** 调用方选择 `convergence`（收敛）或 `endless`（无尽）模式
- **THEN** `mark-pass`（标记通过）写入的 pass marker（通过标记）MUST 记录本次使用的 `mode`

### Requirement: review 报告和严重级别
系统 MUST 为每次 review（审查）生成人类可读报告，并保留 reviewer（审查代理）原始 Markdown（标记文本）输出。review mechanism（审查机制）MUST NOT 解析 finding（发现项）、去重、计数或判断是否通过。

#### Scenario: 阻塞发现
- **WHEN** 任一 reviewer（审查代理）输出 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）finding（发现项）
- **THEN** 汇总报告保留该 reviewer（审查代理）的原始 Markdown（标记文本）
- **AND** 主 agent（主代理）负责判断该 finding（发现项）是否阻断 pass marker（通过标记）

#### Scenario: 非阻塞发现
- **WHEN** reviewer（审查代理）只输出 WARNING（警告）或 SUGGESTION（建议）finding（发现项）
- **THEN** 汇总报告保留该 reviewer（审查代理）的原始 Markdown（标记文本）
- **AND** 主 agent（主代理）负责把它们作为 residual risk（残留风险）或建议处理

#### Scenario: reviewer 返回非法结果
- **WHEN** reviewer 超时、SDK dispatch（开发包派发）失败或 reviewer 返回空结果
- **THEN** review mechanism（审查机制）把该运行态失败写成 CRITICAL（严重阻断）Markdown（标记文本）finding（发现项）

### Requirement: review pass marker
系统 MUST 将 review report（审查报告）和 pass marker（通过标记）分离。`run`（运行）只写人类可读报告；`mark-pass`（标记通过）只在主 agent（主代理）完成语义判断后写入 Agent Guard（代理守卫）默认 guard-defined evidence（守卫定义证据）目录。

#### Scenario: review 完成
- **WHEN** review（审查）完成
- **THEN** 系统生成 `review-report.md`
- **AND** 系统不得在 `.local/cross-agent-review/<change>/<head_ref_short>/` 生成 `review-pass.json`

#### Scenario: 主 agent 写入 pass marker
- **WHEN** 主 agent（主代理）读取 `review-report.md`
- **AND** 主 agent（主代理）确认没有未处理的 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）finding（发现项）
- **AND** 当前 worktree（工作区）仍然干净
- **AND** 当前 `HEAD` 仍等于 `head_ref`
- **THEN** `mark-pass`（标记通过）写入 `.local/guard/evidence/<profile_id>/cross_agent_review_pass/<change>/<head_ref_short>/pass.json`
- **AND** pass marker（通过标记）包含 `schema_version: guard-evidence/v1`、`status: pass`、`producer: cross-agent-review`、`profile_id`、`artifact_id: cross_agent_review_pass`、`subject_id`、`head_ref`、`head_ref_short`、`blocking_findings: 0`、`scope`、`report`、`report_hash` 和 `created_at`

#### Scenario: 主 agent 不写 pass marker
- **WHEN** 主 agent（主代理）判断仍有未处理的 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）finding（发现项）
- **THEN** 主 agent（主代理）不得运行 `mark-pass`（标记通过）

#### Scenario: pass marker report hash
- **WHEN** `mark-pass`（标记通过）写入 pass marker（通过标记）
- **THEN** `report_hash` MUST 匹配同一次 review（审查）生成的 `review-report.md` 内容 hash（哈希）

#### Scenario: 默认输出目录
- **WHEN** review mechanism（审查机制）完成一次 review（审查）
- **THEN** 系统 MUST 把 `review-report.md` 写入 `.local/cross-agent-review/<change>/<head_ref_short>/`
- **AND** 系统 MUST NOT 默认写入 `review-pass.json`、`review-results.json`、`inputs/manifest.json`、`prompts/<role>.txt` 或 `raw/<role>.txt`

### Requirement: Comet 边界
系统 MUST 让 cross-agent review（跨代理审查）保持为独立审查证据，不替代 Comet verify（Comet 验证）。

#### Scenario: 不运行构建或测试
- **WHEN** review mechanism（审查机制）执行 review
- **THEN** 它不得要求调用方预先运行测试或提供测试结果文件
- **AND** 它不得负责运行构建命令或测试命令

#### Scenario: 不推进 Comet phase
- **WHEN** review mechanism（审查机制）完成 review
- **THEN** 它不得修改 `.comet.yaml` 或推进 Comet phase（阶段）

### Requirement: review input snapshots
系统 MUST 让 reviewer prompt（审查代理提示词）引用 `review-input.json`（审查输入文件）和短审查命令，不内联大 diff（差异）内容。

#### Scenario: reviewer prompt 内容
- **WHEN** 系统生成 reviewer prompt（审查提示词）
- **THEN** prompt（提示词）MUST 指示 reviewer agent（审查代理）返回固定 Markdown（标记文本）格式，并为每个 finding（发现项）包含 `Severity`
- **AND** prompt（提示词）MUST NOT 内联完整 diff output（差异输出）、context file（上下文文件）正文、changed files（变更文件）清单或长命令块

#### Scenario: reviewer prompt 使用独立模板
- **WHEN** 系统生成 reviewer prompt（审查提示词）
- **THEN** Python 脚本 MUST 作为调用方和渲染入口，负责提供模板变量、读取模板和渲染模板
- **AND** 模板变量 MUST 限制为 role（角色）、input file path（输入文件路径）、review subject commands（审查对象命令）、role focus（角色重点）和 severity rubric（严重级别规则）

### Requirement: Skill invocation boundary

系统 MUST 限制 `cross-agent-review`（跨代理审查）Skill（技能）的自动调用场景，避免在验证或通用审查阶段重复运行。

#### Scenario: 允许的调用场景

- **WHEN** 当前流程处于 Comet build completion（构建完成）阶段、PR Flow local review（本地审查）阶段，或用户显式调用 `cross-agent-review`
- **THEN** agent（代理）MAY 调用 `cross-agent-review` Skill

#### Scenario: 禁止的自动调用场景

- **WHEN** 当前流程处于 Comet verify（验证）阶段或通用 code review（代码审查）阶段
- **THEN** agent（代理）MUST NOT 自动调用 `cross-agent-review` Skill

### Requirement: review timeout ownership
系统 MUST 由 cross-agent-review（跨代理审查）插件脚本管理 reviewer dispatch（审查代理派发）超时。调用方 MUST NOT 在插件命令外层包装短于插件内部上限的 timeout/watchdog（超时/看门等待）。

#### Scenario: 插件内部管理超时
- **WHEN** cross-agent-review（跨代理审查）真实派发 reviewer agent（审查代理）
- **THEN** 单个 reviewer agent（审查代理）的内部 timeout（超时）MUST 为 480 秒
- **AND** 整体 SDK dispatch（开发包派发）的内部 timeout（超时）MUST 为 540 秒
- **AND** timeout（超时）结果 MUST 由插件脚本转换为带 CRITICAL（严重阻断）finding（发现项）的 Markdown（标记文本）审查结果

#### Scenario: 主 agent 调用插件
- **WHEN** 主 agent（代理）调用 cross-agent-review（跨代理审查）插件命令
- **THEN** 主 agent（代理）MUST 直接等待插件脚本返回
- **AND** 主 agent（代理）MUST NOT 在外层添加小于 540 秒的 timeout（超时）、watchdog（看门等待）或等价提前终止包装

#### Scenario: 外层短 timeout 会造成错误失败
- **WHEN** 调用方在外层设置的等待时间短于插件内部 480 秒或 540 秒上限
- **THEN** 该调用契约 MUST 被视为无效
- **AND** 调用说明 MUST 指示移除外层短 timeout（超时），而不是调低插件内部 timeout（超时）
