# Comet Spec Context

- Change: refactor-cross-agent-review-input-contract
- Phase: design
- Mode: beta
- Context hash: 73cb750306b7577bf2524b0ad0fdb8bd5ba8e6879ee9a5fea9139217472d46a9

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/refactor-cross-agent-review-input-contract/proposal.md
- SHA256: d2b1a47c42274da014a1dfeb3afee281bff917a8363e00c7df58b6ad9f376e23
- Source: openspec/changes/refactor-cross-agent-review-input-contract/design.md
- SHA256: 8cbe44a52ea9509ef8db86a46e2e97f3b79634d59a11936bd685d7e1c4e0f710
- Source: openspec/changes/refactor-cross-agent-review-input-contract/tasks.md
- SHA256: e22905973f9b713bf0b8df824abd5d07bb000c489fe26b176763e6d5d70902f3
- Source: openspec/changes/refactor-cross-agent-review-input-contract/specs/cross-agent-review/spec.md
- SHA256: 5094e16db392c45fd5050baf89315c6b8db0b43cd61a7fe16466fe15a5716281

## Acceptance Projection

## openspec/changes/refactor-cross-agent-review-input-contract/specs/cross-agent-review/spec.md

- Source: openspec/changes/refactor-cross-agent-review-input-contract/specs/cross-agent-review/spec.md
- Lines: 1-64
- SHA256: 5094e16db392c45fd5050baf89315c6b8db0b43cd61a7fe16466fe15a5716281

```md
## MODIFIED Requirements

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
- **AND** changed files command（变更文件命令）MUST 使用 `git diff --name-status <base_ref>...<head_ref>`
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

## ADDED Requirements

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
```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.
