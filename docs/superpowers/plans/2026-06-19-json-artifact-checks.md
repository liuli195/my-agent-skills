---
change: add-json-artifact-checks
design-doc: docs/superpowers/specs/2026-06-19-json-artifact-checks-design.md
base-ref: 73ade80fc55b6d6b03b346af124f9d481450406c
---

# JSON Artifact Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add generic Agent Guard `json_artifact` Guard Point checks with validator coverage, runtime evaluation, and audit detail.

**Architecture:** Keep `artifact_exists` unchanged and add `json_artifact` as a separate check type in the existing Guard Point evaluation path. Validator checks shape and references up front; Runtime resolves the artifact path, parses JSON, evaluates a small predicate set, and returns the existing `guard_failed` envelope with JSON-specific details.

**Tech Stack:** Python stdlib, pytest, existing Agent Guard Runtime and Guard Profile validator.

---

## File Structure

- Modify `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py`: validate `json_artifact` check type, predicate shape, and artifact references.
- Modify `plugins/agent-guard/scripts/guard_runtime/core.py`: add JSON artifact loading, dot-path lookup, predicate evaluation, and JSON check failure detail.
- Modify `tests/test_validate_guard_profile.py`: add profile validator tests for valid and invalid `json_artifact` declarations.
- Modify `tests/test_agent_guard_runtime_router.py`: add runtime state completion tests for passing and failing JSON artifact checks.
- Modify `openspec/changes/add-json-artifact-checks/tasks.md`: check off tasks only after implementation and verification pass.

### Task 1: Validator Contract

**Files:**
- Modify: `tests/test_validate_guard_profile.py`
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py`

- [x] **Step 1: Add failing validator tests**

Add tests to `tests/test_validate_guard_profile.py` after `test_guard_point_check_artifact_must_reference_defined_artifact`:

```python
def test_guard_point_json_artifact_check_can_reference_defined_artifact(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: review_pass_valid
    description: 校验 review pass JSON。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: equals
        value: pass
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "通过：Guard Profile（守卫画像）校验" in result.stdout


def test_guard_point_json_artifact_check_requires_artifact_reference(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: review_pass_valid
    description: 缺少 artifact 引用。
    checks:
      - id: status_pass
        type: json_artifact
        field: status
        predicate: equals
        value: pass
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=guard_points" in result.stdout
    assert "field=guard_points.review_pass_valid.checks.status_pass.artifact" in result.stdout


def test_guard_point_json_artifact_check_rejects_unknown_artifact(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: review_pass_valid
    description: 引用未知 artifact。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: missing_json
        field: status
        predicate: equals
        value: pass
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "field=guard_points.review_pass_valid.checks.status_pass.artifact" in result.stdout
    assert "引用了 `missing_json`" in result.stdout


def test_guard_point_json_artifact_check_requires_supported_predicate(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: review_pass_valid
    description: 使用未知 predicate。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: matches_regex
        value: pass
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "field=guard_points.review_pass_valid.checks.status_pass.predicate" in result.stdout
    assert "matches_regex" in result.stdout
```

- [x] **Step 2: Run validator tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_validate_guard_profile.py -q
```

Expected: new tests fail because `json_artifact` is not supported yet.

- [x] **Step 3: Implement validator support**

In `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py`, add helpers near `validate_references`:

```python
JSON_ARTIFACT_PREDICATES = {"exists", "equals", "not_equals", "number_lte", "number_gte", "array_none", "array_all"}
VALUE_PREDICATES = {"equals", "not_equals", "number_lte", "number_gte"}
FIELD_PREDICATES = JSON_ARTIFACT_PREDICATES


def validate_json_artifact_check(guard_point_id: str, check: dict[str, Any], check_id: str, artifact_ids: set[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    base = f"guard_points.{guard_point_id}.checks.{check_id}"
    artifact = check.get("artifact") or check.get("artifact_id")
    if not isinstance(artifact, str) or not artifact:
        issues.append(ValidationIssue("guard_points", f"{base}.artifact", "json_artifact check 必须引用 artifact。", "添加 `artifact: <artifact-id>`，并确保该 id 存在于 artifacts.yaml。"))
    elif artifact not in artifact_ids:
        issues.append(missing_reference("guard_points", f"{base}.artifact", artifact, "artifacts", "定义该 artifact，或更新 check 引用。"))

    predicate = check.get("predicate")
    if not isinstance(predicate, str) or not predicate:
        issues.append(ValidationIssue("guard_points", f"{base}.predicate", "json_artifact check 必须声明 predicate。", "使用 exists、equals、not_equals、number_lte、number_gte、array_none 或 array_all。"))
        return issues
    if predicate not in JSON_ARTIFACT_PREDICATES:
        issues.append(ValidationIssue("guard_points", f"{base}.predicate", f"不支持的 json_artifact predicate：`{predicate}`。", "使用受支持的 predicate，或新增 Runtime 能力后再声明。"))

    if predicate in FIELD_PREDICATES and not isinstance(check.get("field"), str):
        issues.append(ValidationIssue("guard_points", f"{base}.field", "json_artifact check 必须声明 field。", "添加点路径字段，例如 `status` 或 `security_review.tool`。"))
    if predicate in VALUE_PREDICATES and "value" not in check:
        issues.append(ValidationIssue("guard_points", f"{base}.value", f"`{predicate}` predicate 必须声明 value。", "添加用于比较的 `value`。"))
    if predicate in {"array_none", "array_all"} and not isinstance(check.get("where"), dict):
        issues.append(ValidationIssue("guard_points", f"{base}.where", f"`{predicate}` predicate 必须声明 where 子谓词。", "添加 `where`，包含 field、predicate 和 value。"))
    return issues
```

Then update the existing check loop in `validate_references` so `json_artifact` is allowed and delegated:

```python
            check_type = check.get("type")
            if check_type == "json_artifact":
                issues.extend(validate_json_artifact_check(str(guard_point_id), check, str(check.get("id", "<unknown>")), artifact_ids))
                continue
            if check_type not in {"artifact_exists", "artifact_freshness"}:
                ...
```

- [x] **Step 4: Run validator tests and confirm pass**

Run:

```powershell
python -m pytest tests/test_validate_guard_profile.py -q
```

Expected: all tests pass.

### Task 2: Runtime JSON Predicate Evaluation

**Files:**
- Modify: `tests/test_agent_guard_runtime_router.py`
- Modify: `plugins/agent-guard/scripts/guard_runtime/core.py`

- [ ] **Step 1: Add failing runtime tests**

Add tests after `test_state_completed_evaluates_guard_points_before_advancing` in `tests/test_agent_guard_runtime_router.py`:

```python
def test_state_completed_allows_json_artifact_check_when_predicate_passes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: review_pass_valid
    description: review pass marker 必须通过。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: equals
        value: pass
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    note = project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "completion-note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(json.dumps({"status": "pass"}, ensure_ascii=False), encoding="utf-8")
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_blocks_json_artifact_check_when_predicate_fails(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: review_pass_valid
    description: review pass marker 必须通过。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: equals
        value: pass
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    note = project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "completion-note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(json.dumps({"status": "fail"}, ensure_ascii=False), encoding="utf-8")
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "json_artifact_check_failed"
    assert payload["details"]["json_check"]["artifact"] == "completion_note"
    assert payload["details"]["json_check"]["field"] == "status"
    assert payload["details"]["json_check"]["expected"] == "pass"
    assert payload["details"]["json_check"]["actual"] == "fail"
```

- [ ] **Step 2: Run runtime tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py::test_state_completed_allows_json_artifact_check_when_predicate_passes tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_artifact_check_when_predicate_fails -q
```

Expected: fail with `unsupported_guard_point_check`.

- [ ] **Step 3: Add JSON artifact helpers**

In `plugins/agent-guard/scripts/guard_runtime/core.py`, add helpers near `artifact_exists`:

```python
MISSING = object()


def artifact_definition(project: Path, profile_id: str, artifact_id: str, user_home: Path | None = None, scope: str = "project") -> dict[str, Any] | None:
    artifacts = read_yaml(profile_dir(project, profile_id, user_home, scope) / "artifacts.yaml").get("artifacts", [])
    for artifact in artifacts if isinstance(artifacts, list) else []:
        if isinstance(artifact, dict) and artifact.get("id") == artifact_id:
            return artifact
    return None


def artifact_file_path(project: Path, profile_id: str, instance_id: str, state_version: int, artifact_id: str, user_home: Path | None = None, scope: str = "project") -> Path | None:
    artifact = artifact_definition(project, profile_id, artifact_id, user_home, scope)
    if artifact is None:
        return None
    template = artifact.get("path")
    if not isinstance(template, str):
        return None
    return artifact_path(project, user_home, scope, template, profile_id, instance_id, state_version)


def value_at_path(data: Any, field: str) -> Any:
    current = data
    for part in field.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return MISSING
    return current
```

Update `artifact_exists` to reuse `artifact_file_path`:

```python
def artifact_exists(...):
    path = artifact_file_path(project, profile_id, instance_id, state_version, artifact_id, user_home, scope)
    return path.exists() if path is not None else False
```

- [ ] **Step 4: Add predicate evaluation**

Add:

```python
def json_check_failure(check: dict[str, Any], artifact_id: str, field: str | None, predicate: str | None, expected: Any = None, actual: Any = None, reason: str = "json_artifact_check_failed") -> dict[str, Any]:
    return {
        "failure_reason": reason,
        "json_check": {
            "artifact": artifact_id,
            **({"field": field} if field else {}),
            **({"predicate": predicate} if predicate else {}),
            **({"expected": expected} if expected is not None else {}),
            **({"actual": actual} if actual is not MISSING else {}),
        },
    }


def evaluate_json_predicate(data: Any, check: dict[str, Any]) -> dict[str, Any] | None:
    artifact_id = str(check.get("artifact") or check.get("artifact_id") or "")
    field = check.get("field")
    predicate = check.get("predicate")
    value = value_at_path(data, field) if isinstance(field, str) else MISSING
    expected = check.get("value")
    if predicate == "exists":
        return None if value is not MISSING else json_check_failure(check, artifact_id, field, predicate, actual=MISSING)
    if predicate == "equals":
        return None if value == expected else json_check_failure(check, artifact_id, field, predicate, expected, value)
    if predicate == "not_equals":
        return None if value != expected else json_check_failure(check, artifact_id, field, predicate, expected, value)
    if predicate == "number_lte":
        return None if isinstance(value, (int, float)) and isinstance(expected, (int, float)) and value <= expected else json_check_failure(check, artifact_id, field, predicate, expected, value)
    if predicate == "number_gte":
        return None if isinstance(value, (int, float)) and isinstance(expected, (int, float)) and value >= expected else json_check_failure(check, artifact_id, field, predicate, expected, value)
    return json_check_failure(check, artifact_id, field if isinstance(field, str) else None, str(predicate), expected, value, "unsupported_json_artifact_predicate")
```

Then add array predicate support before the unsupported return:

```python
    if predicate in {"array_none", "array_all"}:
        if not isinstance(value, list):
            return json_check_failure(check, artifact_id, field, predicate, actual=value)
        where = check.get("where")
        if not isinstance(where, dict):
            return json_check_failure(check, artifact_id, field, predicate, actual=value)
        failures = [evaluate_json_predicate(item, {**where, "artifact": artifact_id}) for item in value]
        matches = [failure is None for failure in failures]
        if predicate == "array_none":
            return None if not any(matches) else json_check_failure(check, artifact_id, field, predicate, expected="no matching elements", actual=value)
        return None if all(matches) else json_check_failure(check, artifact_id, field, predicate, expected="all elements match", actual=value)
```

- [ ] **Step 5: Dispatch `json_artifact` checks**

In `evaluate_guard_point`, branch before unsupported check handling:

```python
        if check_type == "json_artifact":
            artifact_id = check.get("artifact") or check.get("artifact_id")
            path = artifact_file_path(project, profile_id, instance_id, state_version, str(artifact_id), user_home, scope) if isinstance(artifact_id, str) else None
            if path is None or not path.exists():
                ...
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                failure_extra = json_check_failure(check, str(artifact_id), check.get("field") if isinstance(check.get("field"), str) else None, check.get("predicate") if isinstance(check.get("predicate"), str) else None, reason="invalid_json_artifact")
                ...
            failure_extra = evaluate_json_predicate(data, check)
            if failure_extra is not None:
                failure = guard_point_failure(..., failure_extra["failure_reason"], ...)
                failure["json_check"] = failure_extra["json_check"]
                return failure
            continue
```

Use the existing `missing_artifacts`, `required_conditions`, `fix_hint`, and `profile_allow_override` patterns from the `artifact_exists` branch.

- [ ] **Step 6: Run focused runtime tests and confirm pass**

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py::test_state_completed_allows_json_artifact_check_when_predicate_passes tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_artifact_check_when_predicate_fails -q
```

Expected: both pass.

### Task 3: Complete Predicate and Audit Coverage

**Files:**
- Modify: `tests/test_agent_guard_runtime_router.py`
- Modify: `plugins/agent-guard/scripts/guard_runtime/core.py`

- [ ] **Step 1: Add full predicate tests**

Add tests for:

```python
def test_state_completed_supports_json_number_predicates(tmp_path: Path) -> None:
    ...

def test_state_completed_supports_json_array_none_predicate(tmp_path: Path) -> None:
    ...

def test_state_completed_supports_json_array_all_predicate(tmp_path: Path) -> None:
    ...

def test_state_completed_blocks_invalid_json_artifact(tmp_path: Path) -> None:
    ...
```

Use the same setup pattern as Task 2. Assert `payload["details"]["json_check"]` contains the failing predicate data and invalid JSON reports `failure_reason == "invalid_json_artifact"`.

- [ ] **Step 2: Run new tests and confirm failures**

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py -q
```

Expected: newly added tests fail until all predicates and audit details are complete.

- [ ] **Step 3: Finish predicate behavior and audit details**

Update `evaluate_json_predicate` and the `json_artifact` dispatch until all predicates pass. Ensure the final failure dict from `guard_failure_details` includes `json_check`; if needed, update `guard_failure_details`:

```python
        **({"json_check": failure.get("json_check")} if failure.get("json_check") else {}),
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/test_validate_guard_profile.py tests/test_agent_guard_runtime_router.py -q
```

Expected: pass.

### Task 4: Change Tracking and Full Verification

**Files:**
- Modify: `openspec/changes/add-json-artifact-checks/tasks.md`

- [ ] **Step 1: Mark completed OpenSpec tasks**

After implementation and focused tests pass, update `openspec/changes/add-json-artifact-checks/tasks.md` by changing completed items from `- [ ]` to `- [x]`.

- [ ] **Step 2: Validate OpenSpec change**

Run:

```powershell
openspec validate add-json-artifact-checks --strict
```

Expected: `Change 'add-json-artifact-checks' is valid`.

- [ ] **Step 3: Run full repository tests**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit the completed change**

Run:

```powershell
git add plugins/agent-guard/scripts/guard_runtime/core.py plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py tests/test_validate_guard_profile.py tests/test_agent_guard_runtime_router.py openspec/changes/add-json-artifact-checks docs/superpowers/specs/2026-06-19-json-artifact-checks-design.md docs/superpowers/plans/2026-06-19-json-artifact-checks.md
git commit -m "实现 JSON artifact 守卫检查"
```

Expected: commit succeeds on the feature branch or worktree selected for build execution.

## Self-Review

- Spec coverage: validator support, runtime JSON checks, predicate set, invalid JSON, audit detail, and regression coverage are mapped to tasks.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: check type is consistently `json_artifact`; predicate names match the Design Doc and delta spec.
