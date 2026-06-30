---
change: fix-pr-flow-recovery-paths
design-doc: docs/superpowers/specs/2026-06-30-fix-pr-flow-recovery-paths-design.md
base-ref: a38f21b519c4d7ab0d694f9c6ae6293abe3ea315
archived-with: 2026-06-30-fix-pr-flow-recovery-paths
---

# Fix PR Flow Recovery Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PR Flow（拉取请求流程）recover cleanly from EOF（连接提前结束）、pending checks（等待中的检查）、deprecated `evidencePath`（已废弃证据路径） and repeat `--fixes`（关闭引用参数） cases.

**Architecture:** Keep the change in `pr_flow.py`（拉取请求流程脚本） and existing CLI（命令行） tests. Reuse `wait_for_checks`（等待检查）, `update_pr_body`（更新正文） and existing stop state（停止状态） writing.

**Tech Stack:** Python（解释器） standard library（标准库）, pytest（测试工具）, OpenSpec（开放规格）。

archived-with: 2026-06-30-fix-pr-flow-recovery-paths
---

### Task 1: Recovery Behavior Tests

**Files:**
- Modify: `tests/test_pr_flow_cli.py`

- [x] **Step 1: Add failing tests**

Add tests for:
- EOF（连接提前结束） in `gh pr view` retries without repeated stop output.
- `ruleset_merge_blocking`（规则集阻塞） reuses `wait_for_checks`（等待检查） and stops unchanged on timeout/failure.
- `defaults.reviewGate.evidencePath`（审查证据路径） emits warning（警告）。
- Existing PR body（拉取请求正文） appends missing `Fixes #...`（关闭引用） and continues when already present.

- [x] **Step 2: Run focused tests and verify RED（失败）**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py -k "transient or ruleset or evidencePath or existing_human_body" -q
```

Expected: new tests fail for missing behavior.

### Task 2: Minimal Implementation

**Files:**
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Modify: `tests/test_pr_flow_cli.py`

- [x] **Step 1: Implement minimal code**

Implement only:
- bounded EOF（连接提前结束） retry for read-only `gh pr view`（查看拉取请求）。
- rule-blocked merge（合并） recovery using existing checks wait（检查等待）。
- closing reference（关闭引用） append for existing PR body（拉取请求正文）。
- deprecated `evidencePath`（证据路径） warning（警告）。

- [x] **Step 2: Run focused tests and verify GREEN（通过）**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py -k "transient or ruleset or evidencePath or existing_human_body" -q
```

Expected: PASS（通过）。

### Task 3: Validation

**Files:**
- Modify: `openspec/changes/fix-pr-flow-recovery-paths/tasks.md`

- [x] **Step 1: Run full PR Flow CLI（命令行） tests**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py -q
```

- [x] **Step 2: Run OpenSpec（开放规格） validation**

Run:

```bash
openspec validate fix-pr-flow-recovery-paths --strict
```

- [x] **Step 3: Mark OpenSpec（开放规格） tasks complete**

Update `openspec/changes/fix-pr-flow-recovery-paths/tasks.md` after tests and validation pass.
