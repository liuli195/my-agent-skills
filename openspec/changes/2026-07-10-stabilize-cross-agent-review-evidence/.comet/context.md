# Comet Spec Context

- Change: stabilize-cross-agent-review-evidence
- Phase: design
- Mode: beta
- Context hash: 1bb6c91e11dafd23dd510e8468062472cdd24bf26afefbc1c0d8d827400a2804

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/stabilize-cross-agent-review-evidence/proposal.md
- SHA256: 49c297d1ea0b60f015937a61eef3a78e322574a06744a13de1f5ba94a567a014
- Source: openspec/changes/stabilize-cross-agent-review-evidence/design.md
- SHA256: 15d882827a8013214bc77ee17bac42eca7b49f3833451ce6736574d2427fb6fb
- Source: openspec/changes/stabilize-cross-agent-review-evidence/tasks.md
- SHA256: c97704e97739bc3986b3f39fd673b115ecdaec783273194fe5d3b56448b1c1dd
- Source: openspec/changes/stabilize-cross-agent-review-evidence/specs/agent-guard-core/spec.md
- SHA256: beff08abdd32ea85eede600f28aaef1b56a1a60f00087ee9a2ed8a9e113019ae
- Source: openspec/changes/stabilize-cross-agent-review-evidence/specs/agent-guard-plugin-runtime/spec.md
- SHA256: 63f5ea4729b7dcd0e4678ed63440721670c9b07332ab788c461a47ea649f9c9c
- Source: openspec/changes/stabilize-cross-agent-review-evidence/specs/comet-agent-review-gate/spec.md
- SHA256: a7a3aed4f0511e0dbfabe03d9b3bff8a3a91e347ebbfe92456f62db656accdb1
- Source: openspec/changes/stabilize-cross-agent-review-evidence/specs/cross-agent-review/spec.md
- SHA256: 22e58ab1d16ae88d11ea09e87fb432a4c30c9dff1bdecb6f9114448f41045c94

## Acceptance Projection

## openspec/changes/stabilize-cross-agent-review-evidence/specs/agent-guard-core/spec.md

- Source: openspec/changes/stabilize-cross-agent-review-evidence/specs/agent-guard-core/spec.md
- Lines: 1-19
- SHA256: beff08abdd32ea85eede600f28aaef1b56a1a60f00087ee9a2ed8a9e113019ae

```md
## MODIFIED Requirements

### Requirement: 画像拥有业务规则
系统 MUST 让 Guard Profile（守卫画像）拥有被守卫业务规则。Agent Guard（代理守卫）核心只执行通用匹配、读取、校验，以及由主代理显式请求且不包含业务判断的 guard-defined evidence（守卫定义证据）机械写入；核心 MUST NOT 自主作出业务通过结论。

#### Scenario: Comet review gate 不侵入 cross-agent-review
- **WHEN** Global Command Guard（全局命令守卫点）用于守卫 Comet build completion（构建完成）命令
- **THEN** Agent Guard（代理守卫）可以匹配命令、读取 `cross_agent_review_pass` artifact（跨代理审查通过产物）并校验 guard-defined evidence（守卫定义证据）`pass.json`
- **AND** Comet review gate（双星审查门禁）的 Guard Profile（守卫画像） MAY 配置指向生成 pass marker（通过标记）的 deny（拒绝）提示
- **AND** Agent Guard（代理守卫）不得准备 Cross Agent Review（跨代理审查）输入、检查其工作区前置条件、派发 reviewer agent（审查代理）、解析审查发现项或推进 Comet phase（阶段）

#### Scenario: 主代理显式记录守卫定义证据
- **WHEN** 主代理已经根据上游流程产物作出通过结论，并显式调用通用 `record-evidence`（记录证据）入口
- **THEN** Agent Guard（代理守卫） MAY 按 Guard Profile（守卫画像）的产物契约校验并机械写入 guard-defined evidence（守卫定义证据）
- **AND** 该写入 MUST NOT 推导、补充或改变主代理的业务结论

#### Scenario: 守卫不得自主生成通过证据
- **WHEN** 主代理没有显式调用 `record-evidence`（记录证据），或上游只存在报告但没有主代理通过结论
- **THEN** Agent Guard（代理守卫） MUST NOT 自主读取报告并生成 pass marker（通过标记）

```

## openspec/changes/stabilize-cross-agent-review-evidence/specs/agent-guard-plugin-runtime/spec.md

- Source: openspec/changes/stabilize-cross-agent-review-evidence/specs/agent-guard-plugin-runtime/spec.md
- Lines: 1-72
- SHA256: 63f5ea4729b7dcd0e4678ed63440721670c9b07332ab788c461a47ea649f9c9c

```md
## MODIFIED Requirements

### Requirement: Global Command Guard evidence uses dual path model
系统 MUST 为 Global Command Guard（全局命令守卫点）区分 guard-defined evidence（守卫定义证据）和 external artifact（外部产物）。当通过结论由主 agent（主代理）根据上游报告作出时，Agent Guard（代理守卫） MUST 定义默认 evidence（证据）目录，并且只在主代理显式调用通用记录入口后机械写入；当被守卫流程本身已经生成稳定可检查产物时，Agent Guard（代理守卫） MUST 只登记并校验原始路径，不复制、不搬运、不接管目录。

#### Scenario: guard-defined evidence 使用默认目录
- **WHEN** Guard Profile（守卫画像）声明的 artifact（产物）属于 guard-defined evidence（守卫定义证据）
- **THEN** Runtime（运行时） MUST 从 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json` 读取证据

#### Scenario: guard-defined evidence 由主代理显式记录
- **WHEN** guard-defined evidence（守卫定义证据）需要写入 pass marker（通过标记）
- **THEN** 主 agent（主代理） MUST 在 Guard（守卫）检查前显式调用 `record-evidence`（记录证据）
- **AND** Runtime（运行时）只能机械校验并写入，不得自主生成业务结论

#### Scenario: guard-defined evidence 使用标准字段
- **WHEN** guard-defined evidence（守卫定义证据）写入 pass marker（通过标记）
- **THEN** marker（标记） MUST 使用 `guard-evidence/v1`（守卫证据第一版）字段契约

#### Scenario: external artifact 保持只读
- **WHEN** `artifacts.yaml`（产物注册文件）中的目标 artifact（产物）不属于 guard-defined evidence（守卫定义证据）
- **THEN** Agent Guard（代理守卫） MUST 只读取和校验该外部产物
- **AND** `record-evidence`（记录证据） MUST 拒绝覆盖该产物

#### Scenario: cross-agent-review pass marker 使用 guard-defined evidence
- **WHEN** Global Command Guard（全局命令守卫点）校验 Cross Agent Review（跨代理审查）的 pass marker（通过标记）
- **THEN** 该 artifact（产物） MUST 注册为 `type: json`（数据类型）且 `owner: agent-guard`（代理守卫拥有）的 guard-defined evidence（守卫定义证据）
- **AND** 注册路径 MUST 使用 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`
- **AND** `{artifact_id}` MUST 为该 Guard Profile（守卫画像）声明的 `cross_agent_review_pass`
- **AND** `{subject_id}` MUST 来自命令捕获值，Comet change（双星变更）场景下等于 `change`

## ADDED Requirements

### Requirement: 通用 record-evidence 入口
Agent Guard Runtime（代理守卫运行时） MUST 提供通用 `record-evidence`（记录证据）入口，供主代理在完成语义判断后显式记录任意 Guard Profile（守卫画像）声明的 guard-defined JSON evidence（守卫定义数据证据）。该入口 MUST 不硬编码业务 workflow（工作流）、审查技能、profile id（画像编号）、artifact id（产物编号）或证据业务字段。

#### Scenario: 显式选择画像来源
- **WHEN** 主代理调用 `record-evidence`（记录证据）
- **THEN** 调用 MUST 明确提供 project（项目）或 user（用户）profile source scope（画像来源范围）、`profile_id`（画像编号）和 `artifact_id`（产物编号）
- **AND** Runtime（运行时） MUST 只从所选来源的 `.agents/guards/<profile_id>/artifacts.yaml`（产物注册文件）解析产物
- **AND** Runtime（运行时） MUST NOT 在另一个来源范围中猜测或回退查找同名画像

#### Scenario: 只写守卫定义数据证据
- **WHEN** 目标 artifact（产物）存在于 `artifacts.yaml`（产物注册文件）
- **THEN** Runtime（运行时） MUST 要求该产物声明 `type: json`（数据类型）和 `owner: agent-guard`（代理守卫拥有）
- **AND** 任一条件不满足时，Runtime（运行时） MUST 拒绝写入并报告目标不是 guard-defined evidence（守卫定义证据）

#### Scenario: 从画像安全解析路径
- **WHEN** 目标产物通过所有权检查
- **THEN** Runtime（运行时） MUST 只使用该产物的 `path`（路径）模板
- **AND** Runtime（运行时） MUST 注入 `profile_id`、`artifact_id`、`subject_id`、当前 `git_head`（提交头）和当前 12 位 `git_head_short`（短提交头）
- **AND** Runtime（运行时） MUST 拒绝缺失模板值、绝对路径、Windows drive path（Windows 驱动器路径）和项目目录逃逸

#### Scenario: 当前仓库状态决定提交字段
- **WHEN** Runtime（运行时）准备记录证据
- **THEN** 它 MUST 从 `--project` 指向的 Git（版本控制）仓库读取当前完整 `HEAD`（提交头）
- **AND** 当前 worktree（工作区） MUST 干净
- **AND** 调用方 MUST NOT 覆盖 `head_ref` 或 `head_ref_short`

#### Scenario: 标准字段由 Runtime 注入
- **WHEN** 主代理提供 `producer`（生产方）、`subject_type`（对象类型）、`subject_id`（对象编号）和 JSON object（数据对象）业务字段
- **THEN** Runtime（运行时） MUST 注入 `schema_version: guard-evidence/v1`、`status: pass`、`producer`、`profile_id`、`artifact_id`、`subject_type`、`subject_id`、`head_ref`、`head_ref_short` 和 `created_at`
- **AND** Runtime（运行时） MUST 拒绝业务字段对象包含任一保留标准字段

#### Scenario: 原子写入证据
- **WHEN** 画像、产物、路径、仓库和业务字段均有效
- **THEN** Runtime（运行时） MUST 在目标目录创建同目录临时文件并通过 atomic replace（原子替换）写入 `pass.json`
- **AND** 命令输出 MUST 包含 `status: evidence_recorded`、当前完整提交头、12 位短提交头和可复制证据路径

#### Scenario: 写入失败不留下半文件
- **WHEN** JSON（数据）读取、目录创建、临时文件写入或原子替换失败
- **THEN** Runtime（运行时） MUST 返回失败状态
- **AND** Runtime（运行时） MUST NOT 把部分 JSON（数据）暴露为有效目标证据

```

## openspec/changes/stabilize-cross-agent-review-evidence/specs/comet-agent-review-gate/spec.md

- Source: openspec/changes/stabilize-cross-agent-review-evidence/specs/comet-agent-review-gate/spec.md
- Lines: 1-76
- SHA256: a7a3aed4f0511e0dbfabe03d9b3bff8a3a91e347ebbfe92456f62db656accdb1

```md
## MODIFIED Requirements

### Requirement: Comet review gate 通过产物注册层校验 pass marker
系统 MUST 通过 Agent Guard `artifacts.yaml`（代理守卫产物注册文件）注册 `cross_agent_review_pass`（跨代理审查通过标记），并使用 Global Command Guard（全局命令守卫点）的 JSON predicate（数据谓词）校验该 marker（标记）。`cross_agent_review_pass` 属于 guard-defined evidence（守卫定义证据），因为通过结论由主 agent（主代理）读取 review report（审查报告）和 review state（审查状态）后作出；主代理 MUST 通过 Agent Guard（代理守卫）的通用 `record-evidence`（记录证据）入口写入。系统 MUST NOT 在 Agent Guard（代理守卫）中实现 Cross Agent Review（跨代理审查）内部流程。

#### Scenario: 注册 cross-agent-review pass marker
- **WHEN** 用户级 Guard Profile（守卫画像）配置 Comet review gate（双星审查门禁）
- **THEN** `artifacts.yaml`（产物注册文件） MUST 把 `cross_agent_review_pass` 注册为 `type: json`（数据类型）、`owner: agent-guard`（代理守卫拥有）的产物
- **AND** 该产物路径 MUST 指向 Agent Guard（代理守卫）默认 evidence（证据）目录 `.local/guard/evidence/<profile_id>/cross_agent_review_pass/<subject_id>/<head_ref_short>/pass.json`
- **AND** `<subject_id>` MUST 来自 Global Command Guard（全局命令守卫点）的命令捕获值，Comet（双星流程）场景下等于 `<change>`
- **AND** `<head_ref_short>` MUST 来自当前 Git HEAD（代码版本）的 12 位短值
- **AND** Global Command Guard（全局命令守卫点） MUST 通过 `artifact` 或 `artifact_id` 引用该注册产物，而不是直接声明独立 `evidence.path`

#### Scenario: 主代理记录 cross-agent-review 通过证据
- **WHEN** 主代理读取当前提交的 `review-report.md`（审查报告）和 `review-state.json`（审查状态文件）
- **AND** 主代理确认两个角色结果有效且没有未处理的 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）finding（发现项）
- **THEN** 主代理 MUST 显式调用 Agent Guard（代理守卫）`record-evidence`（记录证据）并提供现有门禁所需业务字段
- **AND** Cross Agent Review（跨代理审查） MUST NOT 写入该证据

#### Scenario: pass marker 合法
- **WHEN** `pass.json` 存在于当前 change（变更）和当前短 HEAD（代码版本）对应目录
- **AND** `status` 为 `pass`、`schema_version` 为 `guard-evidence/v1`、`producer` 为 `cross-agent-review`、`artifact_id` 为 `cross_agent_review_pass`、`subject_id` 匹配当前 change、`head_ref` 匹配当前完整 HEAD、`head_ref_short` 匹配当前短 HEAD、`blocking_findings` 为 0、`report` 存在且 `report_hash` 存在
- **THEN** Global Command Guard（全局命令守卫点）允许 Comet build（双星构建）阶段守卫收尾命令继续执行

#### Scenario: pass marker 缺失
- **WHEN** review report（审查报告）存在但 `cross_agent_review_pass` 的 `pass.json` 不存在
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet build（双星构建）阶段守卫收尾命令
- **AND** deny（拒绝）输出包含失败原因、缺失产物、当前 change（变更）、当前 head ref（提交头）和来自 Guard Profile（守卫画像）配置的下一步提示

#### Scenario: pass marker 过期
- **WHEN** `pass.json` 的 `head_ref` 不匹配当前完整 HEAD（提交头）
- **THEN** Global Command Guard（全局命令守卫点）拒绝 Comet build（双星构建）阶段守卫收尾命令，并提示运行当前提交的真实审查或受限 `revalidate`（重新校验）

### Requirement: review fail 表现为无有效 pass marker
系统 MUST 只通过 pass marker（通过标记）是否存在且有效来判断 Comet build（双星构建）阶段守卫收尾命令能否继续。Cross Agent Review（跨代理审查）的执行、修复、重试和重新校验流程属于 Cross Agent Review（跨代理审查）或调用方契约。

#### Scenario: 阻塞发现
- **WHEN** Cross Agent Review（跨代理审查）报告包含未处理的 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）finding（发现项）
- **THEN** 主 agent（主代理） MUST NOT 调用 `record-evidence`（记录证据）生成 pass marker（通过标记）
- **AND** Global Command Guard（全局命令守卫点）继续拒绝 Comet build（双星构建）阶段守卫收尾命令
- **AND** Agent Guard（代理守卫） MUST NOT 解析 review report（审查报告）或决定修复流程

#### Scenario: 修复后重新审查
- **WHEN** 用户修复 blocking findings（阻塞发现）并更新 HEAD（提交头）
- **THEN** 调用方负责运行真实 review（审查），或在全部变化满足声明式机械策略时运行 `revalidate`（重新校验）
- **AND** 主 agent（主代理）只在读取当前提交的新报告和状态并作出通过结论后调用 `record-evidence`（记录证据）
- **AND** Agent Guard（代理守卫）只校验新 pass marker（通过标记）是否匹配当前命令和当前 HEAD（提交头）

### Requirement: Comet planning-review gate validates registered pass marker
系统 MUST 通过 Agent Guard `artifacts.yaml`（代理守卫产物注册文件）注册 `planning_review_pass`（规划审查通过标记），并使用 Global Command Guard（全局命令守卫点）的 JSON predicate（数据谓词）校验该 marker（标记）。`planning_review_pass` 属于 guard-defined evidence（守卫定义证据），因为 Planning Review（规划审查）原流程保持只读；主代理 MUST 根据其五字段结果作出结论并通过通用 `record-evidence`（记录证据）入口写入。

#### Scenario: 注册 planning-review pass marker
- **WHEN** 用户级 Guard Profile（守卫画像）配置 Comet planning-review gate（双星规划审查门禁）
- **THEN** `planning_review_pass` 和 `cross_agent_review_pass` MUST 使用相同的 guard-defined evidence（守卫定义证据）默认路径形状
- **AND** `planning_review_pass` MUST 注册为 `type: json`（数据类型）和 `owner: agent-guard`（代理守卫拥有）
- **AND** `planning_review_pass` MUST 使用 `artifact_id`（产物编号）值 `planning_review_pass`
- **AND** `cross_agent_review_pass` MUST 使用 `artifact_id`（产物编号）值 `cross_agent_review_pass`

#### Scenario: 主代理构造 planning review 证据
- **WHEN** Planning Review（规划审查）按只读契约输出 `mode`（模式）、`scope`（范围）、`blocking`（阻断项）、`findings`（发现项）和 `decision`（结论）五个字段
- **AND** 主代理确认 `decision` 为 `PASS`（放行）且没有未处理阻断项
- **THEN** 主代理 MUST 把该五字段 JSON object（数据对象）作为业务字段 `review`（审查结果）传给 `record-evidence`（记录证据）
- **AND** 主代理 MUST 同时提供现有门禁检查使用的平面字段 `blocking_findings`、`scope`、`report` 和 `report_hash`
- **AND** `report` MUST 为 `inline:review`
- **AND** 规范 JSON（数据对象）字节串 MUST 使用 UTF-8（统一编码）、按键排序、紧凑分隔符、保留非 ASCII（非英文字符）且没有尾随换行
- **AND** `report_hash` MUST 使用 `sha256:<lowercase hex>`（安全哈希小写十六进制）格式，并等于该规范字节串的 SHA-256（安全哈希）

#### Scenario: planning review 技能保持只读
- **WHEN** Planning Review（规划审查）完成审查
- **THEN** Planning Review（规划审查）技能 MUST NOT 写入 Agent Guard（代理守卫）证据或调用 `record-evidence`（记录证据）
- **AND** 只有主代理 MAY 在语义通过后显式调用通用入口

#### Scenario: planning review pass marker 合法
- **WHEN** 当前 change（变更）和当前 HEAD（提交头）的 `planning_review_pass` 存在
- **AND** marker（标记）的现有平面字段满足 Guard Profile（守卫画像）声明的所有 JSON predicate（数据谓词）
- **THEN** Global Command Guard（全局命令守卫点）允许 Comet design（双星设计）阶段守卫收尾命令继续执行

```

## openspec/changes/stabilize-cross-agent-review-evidence/specs/cross-agent-review/spec.md

- Source: openspec/changes/stabilize-cross-agent-review-evidence/specs/cross-agent-review/spec.md
- Lines: 1-208
- SHA256: 22e58ab1d16ae88d11ea09e87fb432a4c30c9dff1bdecb6f9114448f41045c94

```md
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

```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.