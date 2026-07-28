# Comet Design Handoff

- Change: simplify-cross-agent-review-contract
- Phase: design
- Mode: compact
- Context hash: 743e420b747b56fd790e55f294364d001f2d320ff735d0ccbe954c767dd7a1c8

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/simplify-cross-agent-review-contract/proposal.md

- Source: openspec/changes/simplify-cross-agent-review-contract/proposal.md
- Lines: 1-36
- SHA256: b09cdfa4743ef27b735b24c457638f42106fdab24fba8cac9276bc7955f0dcbb

```md
# Change: simplify-cross-agent-review-contract

## Why

Current `cross-agent-review` has too much ceremony for a low-frequency review gate:

- The input contract still mixes old `diff` / `tasks_file` assumptions with newer prepared-inputs behavior.
- Four reviewer agents create duplicated findings and slow each run.
- Default outputs include prompt, raw response, manifest, result JSON, and copied input snapshots, which makes normal review output noisy.
- `convergence mode` exists in wording, but the current contract does not make base/head narrowing the actual control surface.

This change keeps the useful hard boundary, `prepared-inputs`, while reducing the run contract to one input file and two reviewer agents.

## What Changes

- **BREAKING**: Replace multi-file CLI input with one `--input-file` pointing to `prepared-inputs/review-input.json`.
- Keep `prepared-inputs` as the required caller-prepared directory, but store only file references and review scope there.
- Replace `tasks_file` with `plan_file`, pointing to a Superpowers plan under `docs/superpowers/plans/`.
- Make `mode`, `base_ref`, and `head_ref` explicit fields in `review-input.json`.
- Make `convergence mode` effective by narrowing reruns through `base_ref` and `head_ref`.
- Keep both modes: `convergence` and `endless`.
- Remove the `tests-and-edge-cases` and `risk-review` reviewer roles.
- Keep only `spec-alignment` and `implementation-correctness` reviewers by default.
- Simplify default outputs to `review-report.md` and, on pass only, `review-pass.json`.
- Move prompt/raw/input debug artifacts behind an explicit debug mode.
- Stop copying input snapshots into the output directory.

## Capabilities

- Modified capability: `cross-agent-review`

## Impact

- Update `cross-agent-review` Skill docs, prompt template, CLI script, and tests.
- Update callers that still pass separate `spec_file`, `design_file`, or `tasks_file` arguments.
- Existing consumers of `review-results.json`, `inputs/manifest.json`, `prompts/`, or `raw/` must switch to debug mode or the pass/report outputs.
```

## openspec/changes/simplify-cross-agent-review-contract/design.md

- Source: openspec/changes/simplify-cross-agent-review-contract/design.md
- Lines: 1-125
- SHA256: 3434ca55b85e86023a337ca451be9efa408cbe1a61b874c4806a53feaef59456

[TRUNCATED]

```md
# Design: simplify cross-agent-review contract

## Context

The current workflow has two useful parts:

- A hard caller boundary through `prepared-inputs`.
- Independent reviewer agents that produce structured findings.

The inefficient parts are mostly accidental:

- Review input is split across several command arguments and copied snapshots.
- `tasks_file` points to OpenSpec tasks, but the actual implementation guidance is better represented by a Superpowers plan.
- `convergence mode` is described as prompt/context behavior instead of a concrete range contract.
- Four roles overlap, especially `tests-and-edge-cases` and `risk-review`, so reruns cost more while producing repeated findings.
- Normal output writes debugging material that is only useful when the review infrastructure itself fails.

## Goals

- Keep `prepared-inputs` as a strict contract.
- Make one `review-input.json` the only run input.
- Make `convergence mode` work through explicit `base_ref` / `head_ref` narrowing.
- Reduce default reviewer count from four to two.
- Reduce default output to the artifacts needed by callers.
- Keep enough debug information available when explicitly requested.

## Non-Goals

- Do not add test execution to `cross-agent-review`.
- Do not make `cross-agent-review` replace Comet verify.
- Do not preserve copied input snapshots for reproducibility.
- Do not keep a compatibility layer for the old multi-argument input style unless a concrete caller still requires a short migration window.

## Decisions

### Single Input File

The caller writes:

```json
{
  "change": "add-build-and-verify-init-skill",
  "mode": "convergence",
  "base_ref": "d6a1ca3c11e7648678a68186fe76f4ada92a1342",
  "head_ref": "8a2ccd24234d...",
  "spec_file": "openspec/changes/<change>/specs/<capability>/spec.md",
  "design_file": "docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md",
  "plan_file": "docs/superpowers/plans/YYYY-MM-DD-<topic>.md"
}
```

The script runs as:

```powershell
python scripts/cross_agent_review.py run --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

The file location is part of the contract:

```text
.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

### No Snapshot Copy

The script reads the referenced files directly. It does not copy `spec`, `design`, or `plan` into `inputs/`, and it does not write `inputs/manifest.json` by default.

This intentionally trades low-frequency reproducibility for a smaller and more readable contract.

### Plan File Replaces Tasks File

`plan_file` points to the Superpowers implementation plan. OpenSpec `tasks.md` remains the planning artifact for this change workflow, but it is no longer part of the review input contract.

### Mode Semantics

`convergence` and `endless` remain separate modes.

In `convergence` mode:

- First run uses the implementation baseline as `base_ref` and current committed `HEAD` as `head_ref`.
```

Full source: openspec/changes/simplify-cross-agent-review-contract/design.md

## openspec/changes/simplify-cross-agent-review-contract/tasks.md

- Source: openspec/changes/simplify-cross-agent-review-contract/tasks.md
- Lines: 1-34
- SHA256: 0dd1ac2666ae67dffa19f072bd33cc81986c9ecfa770a828b72519ec12ca1bf2

```md
# Tasks

## 1. Spec and Skill Contract

- [ ] Update `cross-agent-review` Skill docs to describe `prepared-inputs/review-input.json` as the only startup input.
- [ ] Replace `tasks_file` wording with `plan_file` and require Superpowers plan references.
- [ ] Document `convergence` and `endless` mode through `base_ref` / `head_ref`.

## 2. CLI and Input Loading

- [ ] Replace the old required `--spec-file`, `--design-file`, and `--tasks-file` startup path with `--input-file`.
- [ ] Validate required `review-input.json` fields and referenced files.
- [ ] Validate clean worktree, `head_ref`, and valid `base_ref` before reviewer dispatch.

## 3. Reviewer Dispatch

- [ ] Reduce default reviewers to `spec-alignment` and `implementation-correctness`.
- [ ] Remove `tests-and-edge-cases`, `risk-review`, and `--disable-risk-review` behavior.
- [ ] Keep reviewer workspaces read-only.

## 4. Prompt and Output

- [ ] Simplify reviewer prompt template so it references `review-input.json` instead of inlining large context.
- [ ] Stop writing copied input snapshots and `inputs/manifest.json`.
- [ ] Stop writing `review-results.json` by default.
- [ ] Write `review-report.md` by default and `review-pass.json` only on pass.
- [ ] Add explicit debug output for `debug/review-input.json`, `debug/prompts/<role>.txt`, and `debug/raw/<role>.txt`.

## 5. Tests and Verification

- [ ] Update CLI tests for the single input file contract.
- [ ] Update role and prompt tests for two reviewers.
- [ ] Update output tests for simplified default artifacts and debug artifacts.
- [ ] Run the repository verification path that covers the cross-agent-review plugin.
```

## openspec/changes/simplify-cross-agent-review-contract/specs/cross-agent-review/spec.md

- Source: openspec/changes/simplify-cross-agent-review-contract/specs/cross-agent-review/spec.md
- Lines: 1-165
- SHA256: 88bcc63f5ab6082232a839e1ffcbc9cd87639a8a31cfabefbf0972fcb7f7ee4c

[TRUNCATED]

```md
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

#### Scenario: plan file 取代 tasks file
- **WHEN** 调用方准备 review input（审查输入）
- **THEN** `review-input.json` MUST 使用 `plan_file` 引用 `docs/superpowers/plans/` 下的 Superpowers plan（超级能力计划）
- **AND** review mechanism（审查机制）MUST NOT 要求或读取 `tasks_file`

### Requirement: review subject 绑定
系统 MUST 将 review subject（审查对象）绑定到 clean commit（干净提交），并使用 `review-input.json` 中的 `base_ref` 和 `head_ref` 定义审查范围。

#### Scenario: 启动时工作区不干净
- **WHEN** review mechanism（审查机制）启动时 `git status --short` 非空
- **THEN** 它拒绝启动 reviewer，并不得生成 `review-pass.json`

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
```

Full source: openspec/changes/simplify-cross-agent-review-contract/specs/cross-agent-review/spec.md

