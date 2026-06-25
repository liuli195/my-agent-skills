---
change: add-comet-planning-review-gate
design-doc: docs/superpowers/specs/2026-06-25-add-comet-planning-review-gate-design.md
base-ref: 4b2b2889b1efaac7a8097bf26b94ed329a16e591
---

# Add Comet Planning Review Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove plugin-bundled Comet Guard Profile templates while keeping Agent Guard able to validate external Comet planning-review evidence before `design --apply`.

**Architecture:** Agent Guard Plugin keeps only generic Global Command Guard（全局命令守卫点）runtime and validation mechanisms. Comet-specific configuration moves out of bundled templates and is represented only in user-level or target-environment Guard Profile（守卫画像）fixtures in tests. Evidence paths follow a dual model: guard-defined evidence uses `.local/guard/evidence`, while upstream-owned artifacts such as cross-agent-review stay at their original paths.

**Tech Stack:** Python, pytest, YAML Guard Profile（守卫画像）files, Agent Guard runtime scripts, OpenSpec（规格流程）docs.

---

## File Map

- Modify: `tests/test_validate_guard_profile.py` to remove Comet template validation assumptions and add source-kind rejection coverage.
- Modify: `tests/test_agent_guard_plugin_package.py` to assert Comet templates are not package requirements.
- Modify: `tests/test_local_plugin_build_checks.py` to remove mirror expectations for `comet-review-gate`.
- Modify: `tests/test_agent_guard_runtime_router.py` to use temporary user-level Guard Profile（守卫画像）fixtures for planning-review and cross-agent-review evidence tests.
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py` to remove `built-in-comet-review-gate` from allowed built-in source kinds.
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py` to remove Comet template package items.
- Delete: `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/`.
- Delete: `plugins/agent-guard/assets/templates/guard-profile/comet-review-gate/`.
- Modify docs under `plugins/agent-guard/skills/agent-guard*/` only where they currently present Comet templates as bundled plugin assets.
- Update: `openspec/changes/add-comet-planning-review-gate/tasks.md` as each task completes.

## Task 1: Remove Bundled Comet Template Expectations

**Files:**
- Modify: `tests/test_validate_guard_profile.py`
- Modify: `tests/test_agent_guard_plugin_package.py`
- Modify: `tests/test_local_plugin_build_checks.py`

- [x] **Step 1: Replace template-positive validator tests with absence tests**

In `tests/test_validate_guard_profile.py`, remove constants that point at `comet-review-gate` template directories and replace the three Comet-template tests with:

```python
def test_comet_review_gate_templates_are_not_bundled() -> None:
    skill_template = PLUGIN_SKILL / "assets" / "templates" / "guard-profile" / "comet-review-gate"
    plugin_template = REPO_ROOT / "plugins" / "agent-guard" / "assets" / "templates" / "guard-profile" / "comet-review-gate"

    assert not skill_template.exists()
    assert not plugin_template.exists()
```

- [x] **Step 2: Add source-kind rejection test**

In `tests/test_validate_guard_profile.py`, add:

```python
def test_business_specific_builtin_comet_source_is_rejected(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    manifest = profile / "GUARD-MANIFEST.yaml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace("kind: built-in-minimal-sample", "kind: built-in-comet-review-gate")
    manifest.write_text(text, encoding="utf-8")

    result = run_validator(profile)

    assert result.returncode == 1
    assert "built-in-comet-review-gate" in result.stdout
```

- [x] **Step 3: Update package tests**

In `tests/test_agent_guard_plugin_package.py`, remove `assets/templates/guard-profile/comet-review-gate` and `assets/templates/guard-profile/comet-review-gate/GUARD-MANIFEST.yaml` from required package item expectations. Add:

```python
def test_plugin_package_does_not_bundle_comet_review_gate_template() -> None:
    assert not (PLUGIN_ROOT / "skills" / "agent-guard" / "assets" / "templates" / "guard-profile" / "comet-review-gate").exists()
    assert not (PLUGIN_ROOT / "assets" / "templates" / "guard-profile" / "comet-review-gate").exists()
```

- [x] **Step 4: Update local plugin build checks**

In `tests/test_local_plugin_build_checks.py`, remove `comet-review-gate/*` from mirrored-template expected paths and remove tests that intentionally mutate `comet-review-gate/GUARD-MANIFEST.yaml`. Add one check that the mirrored-template rule does not mention `comet-review-gate`.

- [x] **Step 5: Run focused failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_validate_guard_profile.py::test_comet_review_gate_templates_are_not_bundled tests/test_validate_guard_profile.py::test_business_specific_builtin_comet_source_is_rejected tests/test_agent_guard_plugin_package.py::test_plugin_package_does_not_bundle_comet_review_gate_template -q
```

Expected before implementation: failure because the Comet template still exists and the source kind is still allowed.

## Task 2: Remove Plugin Coupling

**Files:**
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py`
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py`
- Delete: `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/`
- Delete: `plugins/agent-guard/assets/templates/guard-profile/comet-review-gate/`

- [x] **Step 1: Remove built-in Comet source kind**

In `validate_guard_profile.py`, change:

```python
ALLOWED_PROFILE_SOURCE_KINDS = {
    "grill-with-docs-confirmed-notes",
    "built-in-minimal-sample",
    "built-in-comet-review-gate",
}
```

to:

```python
ALLOWED_PROFILE_SOURCE_KINDS = {
    "grill-with-docs-confirmed-notes",
    "built-in-minimal-sample",
}
```

- [x] **Step 2: Remove package item paths**

In `install_agent_guard_plugin.py`, remove:

```python
"skills/agent-guard/assets/templates/guard-profile/comet-review-gate",
"assets/templates/guard-profile/comet-review-gate",
```

from `PACKAGE_ITEMS`.

- [x] **Step 3: Delete bundled template directories**

Delete:

```text
plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/
plugins/agent-guard/assets/templates/guard-profile/comet-review-gate/
```

- [x] **Step 4: Run package and validator tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_validate_guard_profile.py tests/test_agent_guard_plugin_package.py tests/test_local_plugin_build_checks.py -q
```

Expected after implementation: PASS.

## Task 3: Add Planning-Review Runtime Fixtures

**Files:**
- Modify: `tests/test_agent_guard_runtime_router.py`

- [x] **Step 1: Add fixture writer helpers**

Add helpers near existing global command guard helpers:

```python
def write_planning_review_artifacts(profile: Path) -> None:
    profile.joinpath("artifacts.yaml").write_text(
        """
artifacts:
  - id: planning_review_pass
    type: json
    owner: agent-guard
    path: .local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json
    reuse_policy: deny
""".lstrip(),
        encoding="utf-8",
    )


def write_planning_review_guard(profile: Path) -> None:
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: comet_design_requires_planning_review
    tool: Bash
    match:
      command_patterns:
        - '(^|[\\s''"])(?:[^\\s''"]*/)?comet-guard\\.sh[''"]?\\s+(?P<change>[A-Za-z0-9._-]+)\\s+design\\s+--apply(?:\\s|$)'
        - '\\$COMET_GUARD[''"]?\\s+(?P<change>[A-Za-z0-9._-]+)\\s+design\\s+--apply(?:\\s|$)'
      required_captures:
        - change
    evidence:
      artifact: planning_review_pass
    checks:
      - field: schema_version
        predicate: equals
        value: guard-evidence/v1
      - field: status
        predicate: equals
        value: pass
      - field: producer
        predicate: equals
        value: planning-review
      - field: profile_id
        predicate: equals
        value: comet-review-gate
      - field: artifact_id
        predicate: equals
        value: planning_review_pass
      - field: subject_type
        predicate: equals
        value: comet-change
      - field: subject_id
        predicate: equals
        value_from: change
      - field: head_ref
        predicate: equals
        value_from: git_head
      - field: head_ref_short
        predicate: equals
        value_from: git_head_short
      - field: blocking_findings
        predicate: number_lte
        value: 0
      - field: scope
        predicate: exists
      - field: report_hash
        predicate: exists
      - field: created_at
        predicate: exists
    deny:
      reason: comet_planning_review_required
      next: produce_planning_review_pass_marker
      suggestion: 先运行 planning-review（规划审查），通过后由主 agent（代理）写入 pass.json。
""",
    )
```

- [x] **Step 2: Add pass marker writer helper**

Add:

```python
def write_planning_review_pass(project: Path, change: str, head: str, **overrides: object) -> Path:
    path = project / ".local" / "guard" / "evidence" / "comet-review-gate" / "planning_review_pass" / change / head[:12] / "pass.json"
    path.parent.mkdir(parents=True)
    payload = {
        "schema_version": "guard-evidence/v1",
        "status": "pass",
        "producer": "planning-review",
        "profile_id": "comet-review-gate",
        "artifact_id": "planning_review_pass",
        "subject_type": "comet-change",
        "subject_id": change,
        "head_ref": head,
        "head_ref_short": head[:12],
        "blocking_findings": 0,
        "scope": ["proposal.md", "design.md", "tasks.md", "specs/**/*.md"],
        "report_hash": "hash",
        "created_at": "2026-06-25T00:00:00+08:00",
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path
```

- [x] **Step 3: Add missing marker deny test**

Add a test that creates a user-level `comet-review-gate` profile with planning-review guard and no `pass.json`, then runs:

```python
result = pre_tool(project, user_home, "comet-guard.sh add-comet-planning-review-gate design --apply")
```

Assert return code `1`, reason `comet_planning_review_required`, and failing artifact contains `planning_review_pass`.

- [x] **Step 4: Add valid marker allow test**

Create a Git project, get `head = git rev-parse HEAD`, write a valid `pass.json`, then assert `pre_tool(... design --apply)` returns `0` and matched guard id includes:

```text
user:comet-review-gate:comet_design_requires_planning_review
```

- [x] **Step 5: Add stale marker deny test**

Write `pass.json` with `head_ref: "stale"` and `head_ref_short: "stale"`. Assert deny and failed check references `head_ref` or `head_ref_short`.

- [x] **Step 6: Add invalid marker table test**

Use `pytest.mark.parametrize` for these overrides:

```python
[
    {"status": "fail"},
    {"producer": "other"},
    {"artifact_id": "other"},
    {"subject_id": "other-change"},
    {"blocking_findings": 1},
    {"scope": None},
    {"report_hash": None},
]
```

For each, assert `design --apply` is denied.

- [x] **Step 7: Add command-pattern coverage test**

Run the same valid marker against four commands:

```python
[
    "comet-guard.sh add-comet-planning-review-gate design --apply",
    "/tmp/comet-guard.sh add-comet-planning-review-gate design --apply",
    "$COMET_GUARD add-comet-planning-review-gate design --apply",
    "\"$COMET_BASH\" \"$COMET_GUARD\" add-comet-planning-review-gate design --apply",
]
```

Assert all allow.

- [x] **Step 8: Run runtime tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_guard_runtime_router.py -q
```

Expected after implementation: PASS.

## Task 4: Preserve External Artifact Path Behavior

**Files:**
- Modify: `tests/test_agent_guard_runtime_router.py`
- Modify docs under `plugins/agent-guard/skills/agent-guard*/` as needed.

- [x] **Step 1: Add cross-agent-review original-path regression**

In `tests/test_agent_guard_runtime_router.py`, add or update a test that registers:

```yaml
artifacts:
  - id: cross_agent_review_pass
    type: json
    owner: external
    path: .local/cross-agent-review/{change}/{git_head_short}/review-pass.json
```

Write the marker only under `.local/cross-agent-review/.../review-pass.json`, do not create `.local/guard/evidence/...`, and assert `build --apply` allows.

- [x] **Step 2: Document dual evidence model**

Update the Agent Guard references that discuss Global Command Guard（全局命令守卫点） and artifacts（产物） with these rules:

```markdown
- guard-defined evidence（守卫定义证据）：原流程没有可检查产物时，使用 `.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json`。
- external artifact（外部产物）：原流程已有稳定产物时，只在 `artifacts.yaml` 登记原路径，不复制到 `.local/guard/evidence`。
- Agent Guard（代理守卫）定义路径和校验契约，但不自动生成 marker（标记）。
```

- [x] **Step 3: Run docs/package tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_guard_skill_entrypoints.py tests/test_agent_guard_plugin_package.py -q
```

Expected after implementation: PASS.

## Task 5: Sync OpenSpec Tasks And Verify

**Files:**
- Modify: `openspec/changes/add-comet-planning-review-gate/tasks.md`

- [x] **Step 1: Run focused test set**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_validate_guard_profile.py tests/test_agent_guard_plugin_package.py tests/test_local_plugin_build_checks.py tests/test_agent_guard_runtime_router.py tests/test_agent_guard_skill_entrypoints.py -q
```

Expected: PASS.

- [x] **Step 2: Run OpenSpec validation**

Run:

```powershell
openspec validate add-comet-planning-review-gate --strict
```

Expected: `Change 'add-comet-planning-review-gate' is valid`.

- [x] **Step 3: Update task checklist**

Mark completed items in `openspec/changes/add-comet-planning-review-gate/tasks.md` only after the matching tests pass.

- [x] **Step 4: Run repository regression required by repository rules**

Run:

```powershell
C:\Users\liuli\AppData\Local\Programs\Python\Python312\python.exe plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .
```

Expected: PASS.

- [x] **Step 5: Commit**

Commit after tests pass:

```powershell
git add tests plugins docs openspec
git commit -m "feat: 添加 Comet planning-review 门禁"
```

## Plan Self-Review

- Spec coverage: each added or modified requirement maps to at least one task.
- No plugin-bundled Comet config remains in the target design.
- planning-review（规划审查）marker writer is explicitly the calling主 agent（代理）, not Agent Guard（代理守卫） or planning-review（规划审查）Skill（技能）.
- guard-defined evidence（守卫定义证据） and external artifact（外部产物） are tested separately.
- Real user-level `~/.agents/guards/comet-review-gate` is updated only after explicit user confirmation.
