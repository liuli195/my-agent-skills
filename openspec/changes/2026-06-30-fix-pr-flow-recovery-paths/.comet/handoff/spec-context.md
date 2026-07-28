# Comet Spec Context

- Change: fix-pr-flow-recovery-paths
- Phase: design
- Mode: beta
- Context hash: 3fff697f05cd8e8e83663538814b133f1f28163691300571d7498cffb559acb6

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/fix-pr-flow-recovery-paths/proposal.md
- SHA256: 197d0398f07dbb71f46c19d2af3998285d7eabd42e1655417b3842668926f9d1
- Source: openspec/changes/fix-pr-flow-recovery-paths/design.md
- SHA256: 93c0f0e57dea6115e53144bd92c8e3c4f6f898fe424b2163eef84cf1b77b19ea
- Source: openspec/changes/fix-pr-flow-recovery-paths/tasks.md
- SHA256: b8a9652799b45ecd7b9f50a92f96ce28210853c9fc1ab4e79be05c19c6ae8811
- Source: openspec/changes/fix-pr-flow-recovery-paths/specs/pr-flow-plugin/spec.md
- SHA256: 13affa02f32b202a1605987584b82e31bfd7ec4dfeb04a8c73579e7dc1882e7b

## Acceptance Projection

## openspec/changes/fix-pr-flow-recovery-paths/specs/pr-flow-plugin/spec.md

- Source: openspec/changes/fix-pr-flow-recovery-paths/specs/pr-flow-plugin/spec.md
- Lines: 1-140
- SHA256: 13affa02f32b202a1605987584b82e31bfd7ec4dfeb04a8c73579e7dc1882e7b

```md
## MODIFIED Requirements

### Requirement: Complete PR lifecycle
系统 MUST 提供 complete（完整流程），从当前分支创建或同步 PR 到合并后清理。

#### Scenario: Safe auto-push before PR lifecycle
- **WHEN** 用户在功能分支运行 complete（收尾）
- **AND** 本地工作区干净
- **AND** 当前分支不是 `defaults.baseBranch`（默认目标分支）
- **AND** GitHub（代码托管平台）远端确认当前分支没有 active rules（有效规则）
- **AND** 当前分支没有 upstream（上游分支）或本地提交尚未推送
- **THEN** complete（收尾） MUST 执行普通 `git push`（推送）
- **THEN** 无 upstream（上游分支）时 MUST 使用 `git push -u <remote> <branch>`
- **THEN** 已有 upstream（上游分支）时 MUST 使用 `git push`
- **THEN** 推送成功后 MUST 继续创建或同步 PR（拉取请求）

#### Scenario: Auto-push refuses unsafe branch
- **WHEN** complete（收尾）准备自动推送当前分支
- **AND** 当前分支等于 `defaults.baseBranch`（默认目标分支）或 GitHub（代码托管平台）远端显示当前分支有 active rules（有效规则）
- **THEN** complete（收尾） MUST NOT push（推送）
- **THEN** complete（收尾） MUST output `EXCEPTION_REQUIRED`（需要人工处理）

#### Scenario: Auto-push fails closed on uncertainty
- **WHEN** complete（收尾）准备自动推送当前分支
- **AND** 本地工作区不干净、GitHub（代码托管平台）保护状态查询失败、保护状态无法解析或 `git push`（推送）失败
- **THEN** complete（收尾） MUST NOT continue to create, sync, or merge PR（拉取请求）
- **THEN** complete（收尾） MUST output `EXCEPTION_REQUIRED`（需要人工处理） for dirty or uncertain state
- **THEN** complete（收尾） MUST output `PUSH_REQUIRED`（需要推送） when `git push`（推送） itself fails

#### Scenario: Rulesets block merge
- **WHEN** `gh pr merge`（合并拉取请求） fails because the base branch policy（目标分支策略） prohibits the merge（合并）
- **AND** PR checks（拉取请求检查） are no longer pending（等待中）
- **THEN** complete（收尾） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** complete（收尾） MUST use `ruleset_merge_blocking` as reason（原因）
- **THEN** complete（收尾） MUST preserve the original GitHub（代码托管平台） error text for diagnosis（诊断）

#### Scenario: Rulesets block merge while checks are pending
- **WHEN** `gh pr merge`（合并拉取请求） fails with `ruleset_merge_blocking`（规则集阻塞）
- **AND** PR checks（拉取请求检查） are still pending（等待中）
- **THEN** complete（收尾） MUST reuse the configured checks wait behavior（检查等待行为）
- **THEN** complete（收尾） MUST return the checks wait stop state（检查等待停止状态） unchanged if checks（检查） fail or remain pending until timeout
- **THEN** complete（收尾） MUST retry merge（合并） only after checks（检查） are no longer pending（等待中） and no checks wait stop state（检查等待停止状态） is returned
- **THEN** complete（收尾） MUST keep using `ruleset_merge_blocking` as reason（原因） if merge（合并） remains blocked after waiting

#### Scenario: Transient PR view failure is retried
- **WHEN** a read-only `gh pr view`（查看拉取请求） call fails with EOF（连接提前结束）
- **THEN** PR Flow（拉取请求流程） MUST retry the read-only query with a bounded retry count
- **THEN** retry attempts MUST NOT print repeated stop state（停止状态） lines
- **THEN** if retries are exhausted, PR Flow（拉取请求流程） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** if retries are exhausted, PR Flow（拉取请求流程） MUST use `gh_pr_view_transient_failed` as reason（原因）
- **THEN** if retries are exhausted, stop state（停止状态） details（详情） MUST record the transient（临时） category, retry count, and next command（下一步命令）

### Requirement: Review gate modes
系统 MUST 只支持 GitHub（代码托管平台）和 skip（跳过）两种 review gate（审查门禁）模式。

#### Scenario: GitHub review gate
- **WHEN** `reviewGate.mode` 为 `github`
- **THEN** 系统 MUST 读取 PR（拉取请求）的 `reviewDecision`（审查结论）
- **THEN** 系统 MUST 在 `CHANGES_REQUESTED`（要求修改）或 `REVIEW_REQUIRED`（需要审查）时阻止合并

#### Scenario: Skipped review gate
- **WHEN** `reviewGate.mode` 为 `skip`
- **THEN** 系统 MUST 跳过 review gate（审查门禁）
- **THEN** 系统 MUST NOT 读取本地 review evidence（审查证据）

#### Scenario: Unsupported review gate modes
- **WHEN** `reviewGate.mode` 为 `local`、`dual` 或其他非支持值
- **THEN** validate（校验） MUST 报告 unsupported review gate mode（不支持的审查门禁模式）
- **THEN** complete（收尾） MUST NOT treat that mode as local review evidence（本地审查证据）

#### Scenario: Deprecated evidence path is reported
- **WHEN** `.pr-flow/config.yaml`（配置文件） contains `defaults.reviewGate.evidencePath`（审查证据路径）
- **THEN** validate（校验） MUST report a warning（警告） that the field is deprecated（已废弃） and not read
- **THEN** complete（收尾） MUST NOT treat `evidencePath`（审查证据路径） as local review evidence（本地审查证据）

### Requirement: PR body template and closing references
系统 MUST 让 PR Flow（拉取请求流程）在 `complete`（收尾）和 `tweak`（小改）路径中生成、校验并保留可审计的 PR body（拉取请求正文）。

#### Scenario: Init creates three-section PR body template
- **WHEN** `init`（初始化）写入 `.pr-flow/pr-template.md`（拉取请求正文模板）
- **THEN** 模板 MUST 包含 `Summary`、`Scope` 和 `Closing References` 三个章节
- **THEN** 模板 MUST 为每个章节提供注释形式的说明和填写指南
- **THEN** 默认配置 `defaults.pr.requiredSections` MUST 只包含 `Summary`、`Scope` 和 `Closing References`

#### Scenario: Complete requires explicit PR body inputs
- **WHEN** 用户运行 `complete`（收尾）
- **AND** `--summary` 或 `--scope` 缺失或为空
- **THEN** `complete`（收尾） MUST NOT 自动推送、创建、同步或合并 PR（拉取请求）
- **THEN** `complete`（收尾） MUST output `EXCEPTION_REQUIRED`（需要人工处理）
- **THEN** stop state（停止状态） details（详情） MUST include `reason: pr_body_required`、缺失参数和可执行 `nextCommand`（下一步命令）

#### Scenario: Tweak uses same PR body inputs
- **WHEN** 用户运行 `tweak`（小改）
- **AND** `--summary` 或 `--scope` 缺失或为空
- **THEN** `tweak`（小改） MUST NOT 创建、同步或合并 PR（拉取请求）
- **THEN** `tweak`（小改） MUST output `EXCEPTION_REQUIRED`（需要人工处理）
- **THEN** stop state（停止状态） details（详情） MUST include `reason: pr_body_required`、缺失参数和可执行 `nextCommand`（下一步命令）

#### Scenario: Closing references are rendered from explicit issue numbers
- **WHEN** `complete`（收尾）或 `tweak`（小改）收到一个或多个 `--fixes <number>` 参数
- **THEN** PR body（拉取请求正文） MUST 在 `Closing References`（关闭引用）章节写入 GitHub（代码托管平台）支持的 `Fixes #<number>` 引用
- **THEN** 系统 MUST NOT 从分支名、提交信息、历史 issue（问题单）或 PR（拉取请求）状态自动推测 issue（问题单）编号

#### Scenario: No closing references are explicit
- **WHEN** `complete`（收尾）或 `tweak`（小改）没有收到 `--fixes` 参数
- **THEN** PR body（拉取请求正文） MUST 在 `Closing References`（关闭引用）章节写入 `None`

#### Scenario: New PR uses generated body
- **WHEN** `complete`（收尾）或 `tweak`（小改）创建新的 PR（拉取请求）
- **THEN** 新建 PR（拉取请求） MUST 使用统一生成的 PR body（拉取请求正文）
- **THEN** 系统 MUST NOT 保留 `gh pr create --fill`（自动填充）生成的正文来替代统一正文
- **THEN** "不覆盖已有人工正文"规则 MUST only apply to PR（拉取请求）在当前命令开始前已经存在且正文非空的情况

#### Scenario: Empty or invalid template is rejected
- **WHEN** 配置要求 PR body template（拉取请求正文模板）或 requiredSections（必需章节）
- **AND** 模板缺失、模板为空或缺少 requiredSections（必需章节）
- **THEN** `complete`（收尾）和 `tweak`（小改） MUST output `EXCEPTION_REQUIRED`（需要人工处理）
- **THEN** stop state（停止状态） details（详情） MUST include `reason: pr_body_required`、`templatePath`、`missingSections` 和可执行修复提示
- **THEN** 流程 MUST NOT 创建、同步、合并或清理 PR（拉取请求）

#### Scenario: Existing human-authored body is not overwritten
- **WHEN** `complete`（收尾）或 `tweak`（小改）同步到已有 PR（拉取请求）
- **AND** PR body（拉取请求正文）在忽略空白和 HTML comment（HTML 注释）后非空
- **THEN** 系统 MUST NOT overwrite（覆盖）现有正文
- **AND** 如果调用方提供了 `--fixes`
- **THEN** 系统 MUST preserve（保留）已有正文并 only append（仅追加） missing closing references（缺失关闭引用）
- **THEN** 系统 MUST continue（继续） if all requested closing references（关闭引用） already exist
- **THEN** missing closing references（缺失关闭引用） MUST be appended under an existing `Closing References`（关闭引用） section, or in a minimal appended `Closing References`（关闭引用） section if none exists

#### Scenario: Existing empty PR body is filled before checks and merge
- **WHEN** `complete`（收尾）或 `tweak`（小改）同步到已有 PR（拉取请求）
- **AND** PR body（拉取请求正文）在忽略空白和 HTML comment（HTML 注释）后为空
- **THEN** 系统 MUST 在等待 checks（检查）和 merge（合并）前写入统一生成的 PR body（拉取请求正文）

#### Scenario: Diagnose reports body-aware next commands
- **WHEN** `diagnose`（诊断）在功能分支上发现缺少 PR（拉取请求）
- **THEN** stop state（停止状态） details（详情） MUST include 带 `--summary`、`--scope` 和可选 `--fixes` 的 `nextCommand`（下一步命令）
- **WHEN** `diagnose`（诊断）发现已有 PR（拉取请求）正文为空
- **THEN** `diagnose`（诊断） MUST output `EXCEPTION_REQUIRED`（需要人工处理）
- **THEN** stop state（停止状态） details（详情） MUST include `reason: pr_body_required` 和可执行 `nextCommand`（下一步命令）
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
