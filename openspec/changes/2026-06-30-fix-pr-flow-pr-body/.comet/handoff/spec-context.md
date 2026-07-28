# Comet Spec Context

- Change: fix-pr-flow-pr-body
- Phase: design
- Mode: beta
- Context hash: 565bd556bcbff774a35567cdfcd976fb0c971663860ceada6cb5ee94ca487f18

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/fix-pr-flow-pr-body/proposal.md
- SHA256: 924dd8cf23a03d69e7121ad978bf64d45ab36c23a0c90a70f45b2d7aadd26a7a
- Source: openspec/changes/fix-pr-flow-pr-body/design.md
- SHA256: e06b9b76bd24b406c7fb55d573d8a9d480a7326f87c261104b4aa26a8832f5f5
- Source: openspec/changes/fix-pr-flow-pr-body/tasks.md
- SHA256: eafcdd6aee620444673831f3bd21427b92c5a1c1ee1d041a7cf9d4d05759f3c9
- Source: openspec/changes/fix-pr-flow-pr-body/specs/pr-flow-plugin/spec.md
- SHA256: f052ef1e0f9ef600bf123df8c5389e4a6f92823b65d6d5c1872af0a064b03070

## Acceptance Projection

## openspec/changes/fix-pr-flow-pr-body/specs/pr-flow-plugin/spec.md

- Source: openspec/changes/fix-pr-flow-pr-body/specs/pr-flow-plugin/spec.md
- Lines: 1-84
- SHA256: f052ef1e0f9ef600bf123df8c5389e4a6f92823b65d6d5c1872af0a064b03070

```md
## ADDED Requirements

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
- **THEN** 系统 MUST output `EXCEPTION_REQUIRED`（需要人工处理）并提示人工补充 closing references（关闭引用）
- **THEN** stop state（停止状态） details（详情） MUST include PR（拉取请求）编号、冲突原因和明确的手工补充 `Fixes #<number>` 动作

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

## MODIFIED Requirements

### Requirement: Tweak PR path
系统 MUST 提供 tweak（非 bug 小改动）路径，用于跳过 review gate 但保留 PR 流程。

#### Scenario: Tweak requires PR
- **WHEN** 用户运行 tweak
- **THEN** 系统 MUST 创建或同步 PR
- **THEN** 系统 MUST 等待 checks、合并 PR 并执行 cleanup
- **THEN** 系统 MUST 跳过 review gate

#### Scenario: Tweak reason
- **WHEN** 用户运行 tweak
- **THEN** 用户 MUST 提供 reason（原因）
- **THEN** reason（原因） MUST only justify using the tweak（小改） path
- **THEN** 系统 MUST NOT 在 PR body（拉取请求正文）中写入独立的 tweak path（小改路径）正文或 reason（原因）
- **THEN** PR body（拉取请求正文） MUST use the same `Summary`、`Scope` and `Closing References` sections as `complete`（收尾）
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
