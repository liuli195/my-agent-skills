# cross-agent-review Specification Delta

## MODIFIED Requirements

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
系统 MUST 将 review subject（审查对象）绑定到 clean commit（干净提交），并使用 `review-input.json` 中的 `base_ref` 和 `head_ref` 定义审查范围。

#### Scenario: 启动时工作区不干净
- **WHEN** review mechanism（审查机制）启动时 `git status --short` 非空，且变化不属于本次 `review-input.json` 或本次输出目录
- **THEN** 它拒绝启动 reviewer，并不得生成 `review-pass.json`

#### Scenario: 运行时输入输出例外
- **WHEN** `git status --short` 只包含本次 `.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json` 或本次输出目录中的 review runtime artifacts（审查运行产物）
- **THEN** review mechanism（审查机制）MAY 继续运行
- **AND** 该例外 MUST NOT 放行其他 workspace（工作区）变更
- **AND** 该 allowlist（允许清单）MUST 同时适用于启动、派发前和生成 `review-pass.json` 前的所有 clean worktree（干净工作区）检查

#### Scenario: head ref 不匹配
- **WHEN** `review-input.json` 中的 `head_ref` 不等于当前 `git rev-parse HEAD`
- **THEN** review mechanism（审查机制）拒绝启动 reviewer，并报告 head mismatch（当前提交不匹配）

#### Scenario: base ref 无效
- **WHEN** `review-input.json` 中的 `base_ref` 不能解析为有效 Git ref（Git 引用）
- **THEN** review mechanism（审查机制）拒绝启动 reviewer，并报告 base mismatch（基准提交不匹配）

#### Scenario: 派发前或生成 pass marker 前工作区变化
- **WHEN** reviewer 派发前或生成 pass marker（通过标记）前工作区变为 dirty（未提交）
- **THEN** review mechanism（审查机制）拒绝继续，并不得生成 `review-pass.json`

#### Scenario: 修复后重新 review
- **WHEN** review（审查）发现 blocking finding（阻塞发现）且实现被修复
- **THEN** 修复必须提交形成新的 `head_ref` 后，才可以重新运行 review（审查）并生成新的 pass marker（通过标记）

### Requirement: reviewer 角色派发
系统 MUST 将一次 review（审查）拆分给两个明确角色的 reviewer agent（审查代理），并要求每个 reviewer 返回结构化发现。

#### Scenario: 默认角色
- **WHEN** review mechanism（审查机制）启动默认 review（审查）
- **THEN** 它只派发 `spec-alignment`（规格一致性）和 `implementation-correctness`（实现正确性）两个 reviewer agent（审查代理）
- **AND** 它 MUST NOT 派发 `tests-and-edge-cases`（测试和边界）或 `risk-review`（风险审查）

#### Scenario: Claude Agent SDK 缺失
- **WHEN** 当前 Python、默认 Claude SDK venv 和显式 SDK Python 都不能导入 Claude Agent SDK（Claude 代理开发包）
- **THEN** review mechanism（审查机制）拒绝启动 reviewer，并报告 SDK（开发包）不可用

#### Scenario: 只读 reviewer workspace
- **WHEN** review mechanism（审查机制）派发 reviewer
- **THEN** reviewer 可以读取 workspace（工作区）上下文
- **AND** reviewer 不得获得写入文件或修改 Git 状态的工具权限

### Requirement: review（审查）模式选择

系统 MUST 支持 `convergence`（收敛）和 `endless`（无尽）两种模式。模式 MUST 写入 `review-input.json`，并通过 `base_ref` / `head_ref` 控制 review（审查）范围。

#### Scenario: 默认收敛模式

- **WHEN** 调用方没有明确要求无尽模式
- **THEN** `review-input.json` 中的 `mode` MUST 为 `convergence`
- **AND** 首轮 review（审查）MUST 使用 implementation baseline（实施基准）作为 `base_ref`
- **AND** 首轮 review（审查）MUST 使用当前已提交 `HEAD` 作为 `head_ref`

#### Scenario: 收敛模式 rerun

- **WHEN** `convergence`（收敛）模式下修复 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）后重新 review（审查）
- **THEN** 调用方 MUST 使用上一轮失败 review（审查）的 `head_ref` 作为新的 `base_ref`
- **AND** 调用方 MUST 使用修复后的当前已提交 `HEAD` 作为新的 `head_ref`
- **AND** reviewer agent（审查代理）MUST 只审查 `base_ref...head_ref` 范围
- **AND** 只有证据显示相关风险超出当前修复范围时，reviewer agent（审查代理）MAY 扩大上下文读取范围

#### Scenario: 显式无尽模式

- **WHEN** 用户或调用方明确要求无尽模式、每轮完整复查、不要收窄范围或等价表达
- **THEN** `review-input.json` 中的 `mode` MUST 为 `endless`
- **AND** 每轮 review（审查）MUST 保持 `base_ref` 为 implementation baseline（实施基准）或调用方提供的完整 baseline（基准）
- **AND** 每轮 review（审查）MUST 使用当前已提交 `HEAD` 作为 `head_ref`
- **AND** 不得因为上一轮 findings（发现项）已被修复而收窄复审范围

#### Scenario: 模式不改变输出契约

- **WHEN** 调用方选择 `convergence`（收敛）或 `endless`（无尽）模式
- **THEN** review output（审查输出）契约 MUST 保持一致
- **AND** `review-pass.json` MUST 记录本次使用的 `mode`

### Requirement: review pass marker
系统 MUST 只在 blocking findings（阻塞发现）为 0 时生成机器可读 pass marker（通过标记）。默认输出 MUST 只包含人类可读报告和可选 pass marker（通过标记）。

#### Scenario: review 通过
- **WHEN** review（审查）完成且 `blocking_findings` 为 0
- **AND** 当前 worktree（工作区）仍然干净
- **AND** 当前 `HEAD` 仍等于 `head_ref`
- **THEN** 系统生成 `review-pass.json`，包含 `status: pass`、`change`、`mode`、`base_ref`、`head_ref`、`blocking_findings`、`report` 和 `report_hash`

#### Scenario: review 不通过
- **WHEN** review（审查）完成且 `blocking_findings` 大于 0
- **THEN** 系统生成 `review-report.md`
- **AND** 系统不得生成 `review-pass.json`

#### Scenario: pass marker report hash
- **WHEN** 系统生成 `review-pass.json`
- **THEN** `report_hash` MUST 匹配同一输出目录内 `review-report.md` 的内容 hash（哈希）

#### Scenario: 默认输出目录
- **WHEN** review mechanism（审查机制）完成一次 review（审查）
- **THEN** 系统 MUST 把 `review-report.md` 写入 `.local/cross-agent-review/<change>/<head_ref_short>/`
- **AND** blocking findings（阻塞发现）为 0 时，系统 MUST 把 `review-pass.json` 写入同一目录
- **AND** 系统 MUST NOT 默认写入 `review-results.json`、`inputs/manifest.json`、`prompts/<role>.txt` 或 `raw/<role>.txt`

### Requirement: review input snapshots
系统 MUST 使用 `review-input.json`（审查输入文件）中的文件引用和 `base_ref` / `head_ref` 定义 review subject（审查对象）。系统 MUST NOT 默认复制上下文文件快照，也不得默认写入 manifest（清单）或 reviewer debug（审查代理排障）产物。

#### Scenario: 不复制上下文快照
- **WHEN** cross-agent-review（跨代理审查）运行并接收 `review-input.json`
- **THEN** 系统 MUST 直接读取其中引用的 `spec_file`、`design_file` 和 `plan_file`
- **AND** 系统 MUST NOT 在输出目录的 `inputs/` 子目录写入 `spec.md`、`design.md`、`tasks.md`、`plan.md` 或 `manifest.json`

#### Scenario: review subject 使用三点 diff
- **WHEN** 系统生成 review subject（审查对象）
- **THEN** diff command（差异命令）MUST 使用 `git diff <base_ref>...<head_ref>`
- **AND** changed files command（变更文件命令）MUST 使用 `git diff --name-status --find-renames --find-copies-harder <base_ref>...<head_ref>`
- **AND** commit list command（提交列表命令）MUST 使用 `git log <base_ref>..<head_ref> --oneline`

#### Scenario: reviewer 使用轻量输入契约
- **WHEN** reviewer agent（审查代理）收到审查提示
- **THEN** 提示 MUST 引用 `prepared-inputs/review-input.json`
- **AND** 提示 MUST 指示 reviewer agent（审查代理）只读检查 repository（仓库）
- **AND** 提示 MUST 指示 reviewer agent（审查代理）只审查 `base_ref...head_ref` 范围
- **AND** 提示 MUST 指示 reviewer agent（审查代理）使用 `spec_file`、`design_file` 和 `plan_file` 作为需求上下文
- **AND** 提示 MUST NOT 内联完整 diff output（差异输出）、context file（上下文文件）正文、changed files（变更文件）清单或长命令块

#### Scenario: reviewer prompt 使用独立模板
- **WHEN** 系统生成 reviewer prompt（审查提示词）
- **THEN** prompt（提示词）正文结构 MUST 来自 cross-agent-review（跨代理审查）插件内的独立模板文件，便于修改和复用
- **AND** Python 脚本 MUST 作为调用方和渲染入口，负责提供模板变量、读取模板和渲染模板
- **AND** 模板变量 MUST 限制为 role（角色）、input file path（输入文件路径）、role focus（角色重点）、severity rubric（严重级别规则）和 output schema（输出结构）

#### Scenario: debug 排障产物
- **WHEN** 调用方通过 `--debug` 显式启用 debug mode（排障模式）
- **THEN** 系统 MUST 在输出目录写入 `debug/review-input.json`
- **AND** 系统 MUST 为每个 reviewer agent（审查代理）写入 `debug/prompts/<role>.txt` 和 `debug/raw/<role>.txt`
- **AND** 系统 MUST NOT 在 debug mode（排障模式）关闭时写入这些 debug artifacts（排障产物）

#### Scenario: 不保存 diff patch
- **WHEN** cross-agent-review（跨代理审查）准备 review input（审查输入）
- **THEN** 系统 MUST NOT 写入 `diff.patch`（差异补丁）快照
- **AND** 系统 MUST NOT 把 `diff.patch`（差异补丁）传给 reviewer agent（审查代理）
- **AND** review subject（审查对象）MUST 由 `review-input.json` 中的 `base_ref` 和 `head_ref` 定义
