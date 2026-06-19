## ADDED Requirements

### Requirement: 跨 agent review 输入契约
系统 MUST 接收明确的 review input package（审查输入包），并以该输入作为所有 reviewer agent（审查代理）的共同上下文。

#### Scenario: 输入包完整
- **WHEN** 调用方提供 change id、base ref、head ref、diff、需求或规格上下文、设计上下文、任务上下文和已运行测试结果
- **THEN** review mechanism（审查机制）可以启动跨 agent review

#### Scenario: 输入包缺少关键字段
- **WHEN** 调用方缺少 change id、head ref 或 diff
- **THEN** review mechanism（审查机制）拒绝启动，并报告缺失字段

### Requirement: reviewer 角色派发
系统 MUST 将一次 review（审查）拆分给多个明确角色的 reviewer agent（审查代理），并要求每个 reviewer 返回结构化发现。

#### Scenario: 默认角色
- **WHEN** review mechanism（审查机制）启动默认 review
- **THEN** 它派发 spec alignment（规格一致性）、implementation correctness（实现正确性）、tests and edge cases（测试和边界）、risk review（风险审查）四类 reviewer

#### Scenario: 可选风险审查关闭
- **WHEN** 调用方显式关闭 risk review（风险审查）
- **THEN** review report（审查报告）记录该角色被跳过及原因

### Requirement: review 报告和严重级别
系统 MUST 为每次 review（审查）生成人类可读报告，并使用统一严重级别汇总 findings（发现项）。

#### Scenario: 阻塞发现
- **WHEN** 任一 reviewer 返回 CRITICAL 或 IMPORTANT finding（发现项）
- **THEN** 汇总报告把该 finding 计入 `blocking_findings`

#### Scenario: 非阻塞发现
- **WHEN** reviewer 只返回 WARNING 或 SUGGESTION finding（发现项）
- **THEN** 汇总报告记录这些 finding，但不计入 `blocking_findings`

### Requirement: review pass marker
系统 MUST 只在 blocking findings（阻塞发现）为 0 时生成机器可读 pass marker（通过标记）。

#### Scenario: review 通过
- **WHEN** review 完成且 `blocking_findings` 为 0
- **THEN** 系统生成 `review-pass.json`，包含 `status: pass`、`change`、`base_ref`、`head_ref`、`blocking_findings`、`report` 和 `report_hash`

#### Scenario: review 不通过
- **WHEN** review 完成且 `blocking_findings` 大于 0
- **THEN** 系统生成 review report（审查报告），但不得生成 `review-pass.json`
