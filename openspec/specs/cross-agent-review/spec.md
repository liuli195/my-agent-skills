# cross-agent-review Specification

## Purpose
Define the independent cross-agent review workflow, reviewer roles, report contract, and pass marker used as reusable review evidence.
## Requirements
### Requirement: 跨 agent review 输入契约
系统 MUST 接收明确的 review input（审查输入），并以该输入作为所有 reviewer agent（审查代理）的共同上下文。首版实现 MAY 通过 CLI 文件参数表达输入，不要求创建独立 input package 文件。

#### Scenario: 输入完整
- **WHEN** 调用方提供 change id、base ref、head ref、diff、需求或规格上下文、设计上下文和任务上下文
- **THEN** review mechanism（审查机制）可以启动跨 agent review

#### Scenario: 输入缺少关键字段
- **WHEN** 调用方缺少 change id、head ref 或 diff
- **THEN** review mechanism（审查机制）拒绝启动，并报告缺失字段

#### Scenario: 输入文件缺失
- **WHEN** 调用方提供的 diff、规格、设计或任务文件不存在
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

### Requirement: review（审查）模式选择

系统 MUST 支持默认收敛模式和显式无尽模式。模式只影响调用方准备输入和 reviewer prompt（审查提示词）的复审范围，不得改变 CLI（命令行接口）参数、输出目录、pass marker（通过标记）或脚本行为。

#### Scenario: 默认收敛模式

- **WHEN** 调用方没有明确要求无尽模式
- **THEN** cross-agent-review（跨代理审查）MUST 使用收敛模式
- **AND** 首轮 review（审查）MUST 覆盖完整 review subject（审查对象）
- **AND** 修复 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）后重新 review（审查）时，调用方 MAY 将范围收窄到上一轮阻断问题、对应修复、变更路径和直接受影响上下文
- **AND** 只有证据显示相关风险超出当前范围时，调用方 MUST 扩大到完整 review subject（审查对象）

#### Scenario: 显式无尽模式

- **WHEN** 用户或调用方明确要求无尽模式、每轮完整复查、不要收窄范围或等价表达
- **THEN** cross-agent-review（跨代理审查）MUST 使用无尽模式
- **AND** 每轮 review（审查）MUST 覆盖完整 review subject（审查对象）和必要上下文
- **AND** 不得因为上一轮 findings（发现项）已被修复而收窄复审范围

#### Scenario: 模式不改变脚本契约

- **WHEN** 调用方选择收敛模式或无尽模式
- **THEN** CLI（命令行接口）参数和 review output（审查输出）契约 MUST 保持不变
- **AND** 模式选择 MUST 通过调用方准备的上下文和 reviewer prompt（审查提示词）表达

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
- **THEN** 它不得要求调用方预先运行测试或提供测试结果文件
- **AND** 它不得负责运行构建命令或测试命令

#### Scenario: 不推进 Comet phase
- **WHEN** review mechanism（审查机制）完成 review
- **THEN** 它不得修改 `.comet.yaml` 或推进 Comet phase（阶段）

### Requirement: review input snapshots
系统 MUST 在 review output（审查输出）目录中保存本次 review（审查）使用的上下文文件快照，方便复现和排障。系统 MUST 使用 `base_ref`（基线引用）和 `head_ref`（头引用）定义 review subject（审查对象），并在 `manifest.json`（清单）中记录可复现的 git diff command（差异命令）、commit list command（提交列表命令）和 changed files command（变更文件命令）。系统 MUST 使用轻量 reviewer prompt（审查提示词）作为 reviewer agent（审查代理）的初始上下文；该 prompt（提示词）MUST 引用 `manifest.json`（清单）、上下文文件路径和 path-scoped diff（按路径限定差异）命令模板，MUST NOT 内联完整 `diff`（差异）、`spec`（规格）、`design`（设计）或 `tasks`（任务）正文。

#### Scenario: 上下文快照写入输出目录
- **WHEN** cross-agent-review（跨代理审查）运行并接收 spec、design 和 tasks 输入文件
- **THEN** 系统 MUST 在输出目录的 `inputs/` 子目录写入 `spec.md`、`design.md`、`tasks.md` 和 `manifest.json`

#### Scenario: 输入清单
- **WHEN** 系统写入 review input snapshots（审查输入快照）
- **THEN** `inputs/manifest.json` MUST 记录 change id、base ref、head ref、merge base（合并基点）、diff command（差异命令）、commit list command（提交列表命令）、changed files command（变更文件命令）、path diff command template（按路径差异命令模板）、commit list（提交列表）、changed files（变更文件）清单、上下文文件路径、上下文文件 bytes（字节数）和上下文文件 sha256（哈希）
- **AND** changed files（变更文件）条目 MUST 至少包含 path（路径）和 status（状态）；重命名或复制时 MAY 包含 previous_path（原路径）

#### Scenario: review subject 使用三点 diff
- **WHEN** 系统生成 review subject（审查对象）
- **THEN** diff command（差异命令）MUST 使用 `git diff <base_ref>...<head_ref>`
- **AND** changed files command（变更文件命令）MUST 使用 `git diff --name-status --find-renames --find-copies-harder <base_ref>...<head_ref>`
- **AND** commit list command（提交列表命令）MUST 使用 `git log <base_ref>..<head_ref> --oneline`

#### Scenario: reviewer 使用轻量输入契约
- **WHEN** reviewer agent（审查代理）收到审查提示
- **THEN** 提示 MUST 引用输出目录中的 `inputs/manifest.json`、spec、design 和 tasks 快照路径
- **AND** 提示 MUST 包含 changed files（变更文件）清单或等价的路径范围提示
- **AND** 提示 MUST 包含 `git diff <base_ref>...<head_ref> -- <path>` 等价的 path-scoped diff（按路径限定差异）命令模板
- **AND** 提示 MUST 指示 reviewer agent（审查代理）按需读取相关输入片段
- **AND** 提示 MUST NOT 内联完整 diff output（差异输出）、`spec.md`、`design.md` 或 `tasks.md` 内容

#### Scenario: reviewer prompt 使用独立模板
- **WHEN** 系统生成 reviewer prompt（审查提示词）
- **THEN** prompt（提示词）正文结构 MUST 来自 cross-agent-review（跨代理审查）插件内的独立模板文件，便于修改和复用
- **AND** Python 脚本 MUST 作为调用方和渲染入口，负责提供模板变量、读取模板和渲染模板
- **AND** 模板变量 MUST 包含 role（角色）、schema（输出结构）、severity rubric（严重级别规则）、role focus（角色重点）、review subject（审查对象）、manifest path（清单路径）、commands（命令）、changed files（变更文件）和 context files（上下文文件）

#### Scenario: 不保存 diff patch
- **WHEN** cross-agent-review（跨代理审查）准备 review input snapshots（审查输入快照）
- **THEN** 系统 MUST NOT 写入 `diff.patch`（差异补丁）快照
- **AND** 系统 MUST NOT 把 `diff.patch`（差异补丁）传给 reviewer agent（审查代理）
- **AND** review subject（审查对象）MUST 由 manifest（清单）中的 git commands（命令）定义

#### Scenario: reviewer 排障产物
- **WHEN** 系统真实派发 reviewer agent（审查代理）
- **THEN** 系统 MUST 在输出目录写入 `prompts/<role>.txt` 和 `raw/<role>.txt`，用于复现 reviewer prompt（审查提示词）和原始输出

### Requirement: Skill invocation boundary

系统 MUST 限制 `cross-agent-review`（跨代理审查）Skill（技能）的自动调用场景，避免在验证或通用审查阶段重复运行。

#### Scenario: 允许的调用场景

- **WHEN** 当前流程处于 Comet build completion（构建完成）阶段、PR Flow local review（本地审查）阶段，或用户显式调用 `cross-agent-review`
- **THEN** agent（代理）MAY 调用 `cross-agent-review` Skill

#### Scenario: 禁止的自动调用场景

- **WHEN** 当前流程处于 Comet verify（验证）阶段或通用 code review（代码审查）阶段
- **THEN** agent（代理）MUST NOT 自动调用 `cross-agent-review` Skill

### Requirement: review timeout ownership
系统 MUST 由 cross-agent-review（跨代理审查）插件脚本管理 reviewer dispatch（审查代理派发）超时。调用方 MUST NOT 在插件命令外层包装短于插件内部上限的 timeout（超时）等待。

#### Scenario: 插件内部管理超时
- **WHEN** cross-agent-review（跨代理审查）真实派发 reviewer agent（审查代理）
- **THEN** 单个 reviewer agent（审查代理）的内部 timeout（超时）MUST 为 480 秒
- **AND** 整体 SDK dispatch（开发包派发）的内部 timeout（超时）MUST 为 540 秒
- **AND** 超时结果 MUST 由插件脚本转换为结构化 CRITICAL finding（严重发现项）

#### Scenario: 主 agent 调用插件
- **WHEN** 主 agent（代理）调用 cross-agent-review（跨代理审查）插件命令
- **THEN** 主 agent（代理）MUST 直接等待插件脚本返回
- **AND** 主 agent（代理）MUST NOT 在外层添加小于 540 秒的 timeout（超时）、watchdog（看门等待）或等价提前终止包装

#### Scenario: 外层短超时会造成错误失败
- **WHEN** 调用方在外层设置的等待时间短于插件内部 480 秒或 540 秒上限
- **THEN** 该调用契约 MUST 被视为无效
- **AND** 调用说明 MUST 指示移除外层短 timeout（超时），而不是调低插件内部超时

