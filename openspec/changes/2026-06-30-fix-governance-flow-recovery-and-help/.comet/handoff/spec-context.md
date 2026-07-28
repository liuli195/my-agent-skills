# Comet Spec Context

- Change: fix-governance-flow-recovery-and-help
- Phase: design
- Mode: beta
- Context hash: 4128dbd416aafb8cd7e015bc78e8dfb0b9bf4931907b534211671dff144b53a5

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/fix-governance-flow-recovery-and-help/proposal.md
- SHA256: 55cf47d87f870d0e2ba62f23f7bd7966c5185b7e3160adf6cd5a27158acfc3cd
- Source: openspec/changes/fix-governance-flow-recovery-and-help/design.md
- SHA256: 2893b31322c415700e84fdb981cf99b4cdb9410b1dc475d2fc6d14fab4d85382
- Source: openspec/changes/fix-governance-flow-recovery-and-help/tasks.md
- SHA256: fbe236037e480e844d9400e6b475a8949156dcb5111783f414a55326e6e70b7c
- Source: openspec/changes/fix-governance-flow-recovery-and-help/specs/cross-agent-review/spec.md
- SHA256: 39d2601487c4785d7b27340cc0815541d9273300ed7862f23d6dae8a7033b4fd
- Source: openspec/changes/fix-governance-flow-recovery-and-help/specs/pr-flow-plugin/spec.md
- SHA256: 1e8d6676282fefa41585ca110e8f9016606831efc5cd48011fea4fac58fbc073
- Source: openspec/changes/fix-governance-flow-recovery-and-help/specs/release-flow-plugin/spec.md
- SHA256: 35994306632cca290458fdffa09a708d1a4fc86ca16c779881097ed89a17511b

## Acceptance Projection

## openspec/changes/fix-governance-flow-recovery-and-help/specs/cross-agent-review/spec.md

- Source: openspec/changes/fix-governance-flow-recovery-and-help/specs/cross-agent-review/spec.md
- Lines: 1-19
- SHA256: 39d2601487c4785d7b27340cc0815541d9273300ed7862f23d6dae8a7033b4fd

```md
## ADDED Requirements

### Requirement: head_ref_short path convention is explicit
系统 MUST 明确 `head_ref_short`（短头引用）等于 `head_ref`（头引用）的前 12 个字符，并在 cross-agent-review（跨代理审查）的用户可见路径中保持一致。

#### Scenario: Review input path uses first 12 characters
- **WHEN** 调用方准备 `review-input.json`（审查输入文件）
- **THEN** `<head_ref_short>`（短头引用） MUST equal the first 12 characters of `head_ref`（头引用）
- **THEN** the input path（输入路径） MUST be `.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json`

#### Scenario: Run output prints copyable review input path
- **WHEN** `cross-agent-review run`（跨代理审查运行） accepts an input file（输入文件）
- **THEN** output（输出） MUST include the copyable `review-input.json`（审查输入文件） path used for the run
- **THEN** output（输出） MUST expose the same 12-character `head_ref_short`（短头引用） value

#### Scenario: Mark-pass output uses the same short reference
- **WHEN** `mark-pass`（标记通过） writes pass marker（通过标记）
- **THEN** the evidence path（证据路径） MUST use the same 12-character `head_ref_short`（短头引用）
- **THEN** output（输出） MUST include the copyable evidence path（证据路径）
```

## openspec/changes/fix-governance-flow-recovery-and-help/specs/pr-flow-plugin/spec.md

- Source: openspec/changes/fix-governance-flow-recovery-and-help/specs/pr-flow-plugin/spec.md
- Lines: 1-27
- SHA256: 1e8d6676282fefa41585ca110e8f9016606831efc5cd48011fea4fac58fbc073

```md
## ADDED Requirements

### Requirement: Invalid fixes input is reported directly
系统 MUST 在 `complete`（收尾）和 `tweak`（小改）路径中把无效 `--fixes`（修复问题编号）参数作为独立输入错误报告，不得让用户误以为只是缺少 PR body（拉取请求正文）。

#### Scenario: Invalid fixes value is rejected with a copyable example
- **WHEN** 用户运行 `complete`（收尾）或 `tweak`（小改）
- **AND** `--fixes`（修复问题编号）包含逗号分隔值、带 `#` 前缀的值、非数字值或小于等于 0 的值
- **THEN** 系统 MUST stop（停止） before auto-push（自动推送）、PR create（创建拉取请求）、sync（同步） or merge（合并）
- **THEN** stop output（停止输出） MUST identify invalid `--fixes`（修复问题编号） input directly
- **THEN** stop state（停止状态） details（详情） MUST include `invalidFixes`
- **THEN** output（输出） MUST include a copyable example using repeated arguments, such as `--fixes 41 --fixes 43 --fixes 44`

#### Scenario: Valid repeated fixes values continue
- **WHEN** 用户运行 `complete`（收尾）或 `tweak`（小改）
- **AND** 每个 `--fixes`（修复问题编号）值都是大于 0 的数字
- **THEN** 系统 MUST accept repeated `--fixes`（修复问题编号） arguments
- **THEN** PR body（拉取请求正文） MUST render each value as a `Fixes #<number>` closing reference（关闭引用）

### Requirement: Post-create PR sync uses transient PR view retry
系统 MUST 让创建 PR（拉取请求）后的同步查看路径复用 bounded retry（有界重试）行为。

#### Scenario: Post-create sync retries EOF and succeeds
- **WHEN** `complete`（收尾） creates a PR（拉取请求）
- **AND** the immediate post-create `gh pr view`（查看拉取请求） sync fails once with EOF（连接提前结束）
- **AND** a retry succeeds
- **THEN** PR Flow（拉取请求流程） MUST continue the lifecycle without printing an intermediate stop state（停止状态）
```

## openspec/changes/fix-governance-flow-recovery-and-help/specs/release-flow-plugin/spec.md

- Source: openspec/changes/fix-governance-flow-recovery-and-help/specs/release-flow-plugin/spec.md
- Lines: 1-56
- SHA256: 35994306632cca290458fdffa09a708d1a4fc86ca16c779881097ed89a17511b

```md
## MODIFIED Requirements

### Requirement: 发布执行阶段

系统 MUST 提供 release-flow publish（发布）阶段，通过 GitHub Workflow（GitHub 工作流）执行发布，本地不得执行发布 Git（版本管理）写操作。

#### Scenario: 本地只触发 workflow

- **WHEN** 用户执行 publish（发布）
- **THEN** 本地系统 MUST 使用 `workflow_dispatch`（工作流触发）触发 GitHub Workflow（GitHub 工作流）
- **THEN** 本地系统 MUST 只传递 `tag`（标签）、`version`（版本）和 `bumpPlugins`（提升插件列表）
- **THEN** 本地系统 MUST NOT 创建发布分支
- **THEN** 本地系统 MUST NOT 创建 tag（标签）
- **THEN** 本地系统 MUST NOT push（推送）发布内容

#### Scenario: publish 不支持 dry-run

- **WHEN** 用户执行 `publish --dry-run`（发布试运行）
- **THEN** CLI（命令行接口） MUST reject（拒绝） the argument
- **THEN** 系统 MUST NOT print workflow dispatch（工作流触发） preview output（预览输出）

#### Scenario: publish workflow trigger retries EOF

- **WHEN** 用户执行 authorized publish（已授权发布）
- **AND** `gh workflow run`（触发工作流） fails with EOF（连接提前结束）
- **THEN** 本地系统 MUST retry（重试） the workflow trigger（工作流触发） with a bounded retry count
- **THEN** retry attempts（重试尝试） MUST NOT create local branches（本地分支）、tags（标签） or pushes（推送）
- **THEN** if a retry succeeds, publish（发布） MUST return success

#### Scenario: publish workflow trigger reports exhausted EOF retry

- **WHEN** 用户执行 authorized publish（已授权发布）
- **AND** every bounded retry of `gh workflow run`（触发工作流） fails with EOF（连接提前结束）
- **THEN** publish（发布） MUST return the final failure code
- **THEN** publish（发布） MUST preserve the final GitHub CLI（GitHub 命令行） output for diagnosis（诊断）
- **THEN** retry attempts（重试尝试） MUST NOT create local branches（本地分支）、tags（标签） or pushes（推送）

#### Scenario: GitHub Workflow 执行发布

- **WHEN** GitHub Workflow（GitHub 工作流）运行
- **THEN** workflow（工作流）MUST checkout（检出）配置指定的 source ref（源引用）
- **THEN** workflow（工作流）MUST 直接运行 source repo（源码仓库）内的 release-flow（发布流程）脚本
- **THEN** workflow（工作流）MUST 读取 source repo（源码仓库）内的 `.release-flow/projection.yaml`（投影配置）
- **THEN** workflow（工作流）MUST 在隔离发布树中应用 projection（投影）
- **THEN** workflow（工作流）MUST 创建或更新远端 `marketplace`（市场分支）
- **THEN** workflow（工作流）MUST 创建 tag（标签）
- **THEN** workflow（工作流）MUST 创建 GitHub Release（GitHub 发布）
- **THEN** `ci-publish`（持续集成发布）MUST NOT 提供 `--dry-run`（试运行）分支逻辑

#### Scenario: CI 输出发布追溯字段

- **WHEN** GitHub Workflow（GitHub 工作流）发布成功
- **THEN** 输出 MUST 包含 release URL（发布链接）
- **THEN** 输出 MUST 包含 marketplace commit（市场提交）
- **THEN** 输出 MUST 包含 tag commit（标签提交）
- **THEN** 输出 MUST 包含 workflow run URL（工作流运行链接）
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
