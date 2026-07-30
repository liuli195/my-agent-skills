## ADDED Requirements

### Requirement: 跨 agent review 输入契约
系统 MUST 接收明确的 review input（审查输入），并以该输入作为所有 reviewer agent（审查代理）的共同上下文。首版实现 MAY 通过 CLI 文件参数表达输入，不要求创建独立 input package 文件。

#### Scenario: 输入完整
- **WHEN** 调用方提供 change id、base ref、head ref、diff、需求或规格上下文、设计上下文、任务上下文和已运行测试结果
- **THEN** review mechanism（审查机制）可以启动跨 agent review

#### Scenario: 输入缺少关键字段
- **WHEN** 调用方缺少 change id、head ref 或 diff
- **THEN** review mechanism（审查机制）拒绝启动，并报告缺失字段

#### Scenario: 输入文件缺失
- **WHEN** 调用方提供的 diff、规格、设计、任务或测试结果文件不存在
- **THEN** review mechanism（审查机制）拒绝启动，并报告缺失文件

### Requirement: review subject 绑定
系统 MUST 将 review subject（审查对象）绑定到 clean commit（干净提交），不得把未提交工作区作为可通过审查对象。

#### Scenario: 启动时工作区不干净
- **WHEN** review mechanism（审查机制）启动时 `git status --short` 非空
- **THEN** 它拒绝启动 reviewer，并不得生成 `review-pass.json`

#### Scenario: head ref 不匹配
- **WHEN** 调用方提供的 `head_ref` 不等于当前 `git rev-parse HEAD`
- **THEN** review mechanism（审查机制）拒绝启动 reviewer，并报告 head mismatch

#### Scenario: 派发前或生成 pass marker 前工作区变化
- **WHEN** reviewer 派发前或生成 pass marker 前工作区变为 dirty（未提交）
- **THEN** review mechanism（审查机制）拒绝继续，并不得生成 `review-pass.json`

#### Scenario: 修复后重新 review
- **WHEN** review 发现 blocking finding（阻塞发现）且实现被修复
- **THEN** 修复必须提交形成新的 `head_ref` 后，才可以重新运行 review 并生成新的 pass marker

### Requirement: reviewer 角色派发
系统 MUST 将一次 review（审查）拆分给多个明确角色的 reviewer agent（审查代理），并要求每个 reviewer 返回结构化发现。

#### Scenario: 默认角色
- **WHEN** review mechanism（审查机制）启动默认 review
- **THEN** 它派发 spec alignment（规格一致性）、implementation correctness（实现正确性）、tests and edge cases（测试和边界）、risk review（风险审查）四类 reviewer

#### Scenario: 可选风险审查关闭
- **WHEN** 调用方显式关闭 risk review（风险审查）
- **THEN** review report（审查报告）记录该角色被跳过及原因

#### Scenario: Claude Agent SDK 缺失
- **WHEN** 当前 Python、默认 Claude SDK venv 和显式 SDK Python 都不能导入 Claude Agent SDK
- **THEN** review mechanism（审查机制）拒绝启动 reviewer，并报告 SDK 不可用

#### Scenario: 只读 reviewer workspace
- **WHEN** review mechanism（审查机制）派发 reviewer
- **THEN** reviewer 可以读取 workspace（工作区）上下文
- **AND** reviewer 不得获得写入文件或修改 Git 状态的工具权限

### Requirement: review 报告和严重级别
系统 MUST 为每次 review（审查）生成人类可读报告，并使用统一严重级别汇总 findings（发现项）。

#### Scenario: 阻塞发现
- **WHEN** 任一 reviewer 返回 CRITICAL 或 IMPORTANT finding（发现项）
- **THEN** 汇总报告把该 finding 计入 `blocking_findings`

#### Scenario: 非阻塞发现
- **WHEN** reviewer 只返回 WARNING 或 SUGGESTION finding（发现项）
- **THEN** 汇总报告记录这些 finding，但不计入 `blocking_findings`

#### Scenario: reviewer 返回非法结果
- **WHEN** reviewer 超时或返回无法解析的结构化结果
- **THEN** 汇总报告把该 reviewer 计为 CRITICAL finding（发现项）

#### Scenario: findings 去重
- **WHEN** 多个 reviewer 返回相同 severity、location 和 summary 的 finding
- **THEN** review mechanism（审查机制）只计入一条去重后的 finding

### Requirement: review pass marker
系统 MUST 只在 blocking findings（阻塞发现）为 0 时生成机器可读 pass marker（通过标记）。

#### Scenario: review 通过
- **WHEN** review 完成且 `blocking_findings` 为 0
- **AND** 当前 worktree 仍然干净
- **AND** 当前 `HEAD` 仍等于 `head_ref`
- **THEN** 系统生成 `review-pass.json`，包含 `status: pass`、`change`、`base_ref`、`head_ref`、`blocking_findings`、`report` 和 `report_hash`

#### Scenario: review 不通过
- **WHEN** review 完成且 `blocking_findings` 大于 0
- **THEN** 系统生成 review report（审查报告），但不得生成 `review-pass.json`

#### Scenario: pass marker report hash
- **WHEN** 系统生成 `review-pass.json`
- **THEN** `report_hash` MUST 匹配同一输出目录内 `review-report.md` 的内容 hash

#### Scenario: 默认输出目录
- **WHEN** 调用方没有提供 output dir（输出目录）
- **THEN** 系统把 `review-report.md`、`review-results.json` 和可选的 `review-pass.json` 写入 `.local/cross-agent-review/<change>/<head_ref>/`

#### Scenario: output dir 覆盖
- **WHEN** 调用方显式提供 output dir（输出目录）
- **THEN** 系统把本次 review 输出写入该目录

### Requirement: Comet 边界
系统 MUST 让 cross-agent review（跨代理审查）保持为独立审查证据，不替代 Comet verify（Comet 验证）。

#### Scenario: 不运行构建或测试
- **WHEN** review mechanism（审查机制）执行 review
- **THEN** 它读取调用方提供的测试结果
- **AND** 它不得负责运行构建命令或测试命令

#### Scenario: 不推进 Comet phase
- **WHEN** review mechanism（审查机制）完成 review
- **THEN** 它不得修改 `.comet.yaml` 或推进 Comet phase（阶段）
