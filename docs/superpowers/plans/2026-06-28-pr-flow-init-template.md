---
change: optimize-pr-flow-init-template
design-doc: docs/superpowers/specs/2026-06-28-pr-flow-init-template-design.md
base-ref: a4bd6df12207defb355693fbfab7b77abcb6f8d6
archived-with: 2026-06-28-optimize-pr-flow-init-template
---

# PR Flow Init Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `pr-flow-init`（拉取请求流程初始化）模板 to use the latest user-confirmed flow and lock it with focused documentation contract tests.

**Architecture:** Keep the existing Skill（技能）entrypoint and three reference files. Update only tests and reference Markdown（标记文档） unless an existing entrypoint route conflicts with the new init（初始化）contract.

**Tech Stack:** Python（Python 语言）pytest（测试框架）, Markdown（标记文档）, OpenSpec（开放规格）, Comet（彗星流程）.

archived-with: 2026-06-28-optimize-pr-flow-init-template
---

## File Map

- Modify: `tests/test_pr_flow_cli.py`
  - Update old scenario assertions.
  - Add focused contract assertions for the new flow.
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`
  - Replace old review-gate-driven questionnaire with automatic inspection and latest six-question flow.
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`
  - Require user-readable summary before YAML（配置格式） details.
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/validation.md`
  - Require structured error（错误）, warning（警告）, and remote tasks（远端待办） output.
- Preserve: `plugins/pr-flow/skills/pr-flow-init/SKILL.md`
  - Keep the existing constraint that old config and branch state cannot replace user answers.
- Preserve unless tests prove conflict: `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, `plugins/pr-flow/skills/pr-flow/SKILL.md`.

## Task 1: Update Contract Tests First

**Files:**
- Modify: `tests/test_pr_flow_cli.py`

- [x] **Step 1: Replace old scenario expectations**

In `test_pr_flow_init_content_is_organized_by_user_scenario`, replace old required scenarios:

```python
for scenario in [
    "automatic inspection",
    "default PR target branch",
    "branch protection",
    "PR status checks",
    "CodeQL security check",
    "hotfix",
    "merge methods",
    "GitHub 推荐配置",
    "最终写入确认",
]:
    assert scenario in combined
```

- [x] **Step 2: Add latest-flow assertions**

Add assertions in the same test or a new focused test:

```python
questionnaire = (init_dir / "references" / "questionnaire.md").read_text(encoding="utf-8")
assert questionnaire.index("automatic inspection") < questionnaire.index("default PR target branch")
assert "GitHub Rulesets" in questionnaire
assert "Require a pull request before merging" in questionnaire
assert "required_approving_review_count: 0" in questionnaire
assert "PR status checks" in questionnaire
assert "Require status checks to pass before merging" in questionnaire
assert "CodeQL security check" in questionnaire
assert "Require code scanning results" in questionnaire
assert "CodeQL" in questionnaire
assert "reuse existing authorization phrase" in questionnaire
assert "create new authorization phrase" in questionnaire
assert "merge methods" in questionnaire
assert "PR Flow（拉取请求流程）合并前使用哪种审查门禁" not in questionnaire
```

- [x] **Step 3: Add draft and validation assertions**

Add checks:

```python
config_draft = (init_dir / "references" / "config-draft.md").read_text(encoding="utf-8")
validation = (init_dir / "references" / "validation.md").read_text(encoding="utf-8")

assert config_draft.index("用户可读摘要") < config_draft.index("YAML")
for heading in ["本地将写入", "GitHub 当前状态", "GitHub 推荐配置", "validation results"]:
    assert heading in config_draft

for heading in ["error（错误）", "warning（警告）", "remote tasks（远端待办）"]:
    assert heading in validation
assert "not inspected" in validation
assert "no access" in validation
```

- [x] **Step 4: Run focused tests and confirm RED（失败）**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "pr_flow_init" -q
```

Expected: fail on the newly added contract assertions before reference files are updated.

## Task 2: Update Reference Templates

**Files:**
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/validation.md`

- [x] **Step 1: Update questionnaire**

Replace the old question sequence with sections for:

```text
automatic inspection
default PR target branch
branch protection through GitHub Rulesets
PR status checks
CodeQL security check
hotfix direct push
authorization phrase
merge methods
GitHub 推荐配置
final write confirmation
```

Include the exact rule names:

```text
Require a pull request before merging
required_approving_review_count: 0
Require status checks to pass before merging
Require code scanning results
CodeQL
```

Keep fixed labels:

```text
固定问题
固定选项
选择后果
跳转规则
```

- [x] **Step 2: Update config draft**

Require this order before any YAML（配置格式） appendix:

```text
用户可读摘要
本地将写入
GitHub 当前状态
GitHub 推荐配置
validation results
YAML 附录
```

Make clear that GitHub（代码托管平台） setup is not applied by init（初始化）.

- [x] **Step 3: Update validation**

Require structured groups:

```text
error（错误）
warning（警告）
remote tasks（远端待办）
```

Add the no-access case:

```text
GitHub access（GitHub 访问权限）、gh CLI（GitHub 命令行工具）或 network（网络）不可用时，GitHub 当前状态必须显示 not inspected（未检查）或 no access（无权限）。
```

- [x] **Step 4: Run focused tests and confirm GREEN（通过）**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "pr_flow_init" -q
```

Expected: pass.

## Task 3: Verify and Close Build Tasks

**Files:**
- Modify: `openspec/changes/optimize-pr-flow-init-template/tasks.md`

- [x] **Step 1: Run OpenSpec strict validation**

Run:

```powershell
openspec validate optimize-pr-flow-init-template --strict
```

Expected: `Change 'optimize-pr-flow-init-template' is valid`.

- [x] **Step 2: Review diff boundaries**

Run:

```powershell
git diff -- plugins/pr-flow/skills/pr-flow-init tests/test_pr_flow_cli.py openspec/changes/optimize-pr-flow-init-template docs/superpowers
```

Confirm no runtime script semantics changed beyond the validate（校验）output terminology sync in `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`.

- [x] **Step 3: Mark OpenSpec tasks complete**

After tests and validation pass, check off all tasks in:

```text
openspec/changes/optimize-pr-flow-init-template/tasks.md
```

Do not mark tasks complete before verification passes.
