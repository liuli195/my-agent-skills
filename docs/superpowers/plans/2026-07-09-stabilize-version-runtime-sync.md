---
change: stabilize-version-runtime-sync
design-doc: docs/superpowers/specs/2026-07-09-stabilize-version-runtime-sync-design.md
base-ref: cf1ae747b7678203cf3c522d7769f705797238d5
---

# Stabilize Version Runtime Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 锁住插件版本事实来源，并补齐 build-and-verify（构建与验证）runtime（运行时）同步闭环。

**Architecture:** 复用现有 Python（Python 语言）测试、Release Flow（发布流程）preflight（发布预检）入口、build-and-verify（构建与验证）runtime（运行时）提示逻辑和用户级 plugin-sync（插件同步）文档。普通测试只检查版本来源；发布阻塞放在 Release Flow（发布流程）；用户授权更新放在 plugin-sync（插件同步）。

**Tech Stack:** Python（Python 语言）标准库、pytest（测试框架）、PowerShell（命令行）、OpenSpec（规格流程）文档。

---

### Task 1: Version Source Tests

**Files:**
- Modify: `tests/test_build_and_verify_plugin.py`
- Modify: `tests/test_agent_guard_plugin_package.py` if existing manifest checks need the same pattern.
- Test: `tests/test_build_and_verify_plugin.py`

- [x] **Step 1: Add failing version literal guard test**

Add a test near existing plugin manifest tests:

```python
def test_tests_do_not_introduce_real_plugin_version_literals() -> None:
    allowed = {
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_verify_reports_newer_user_runtime_without_mutation",
    }
    pattern = re.compile(r"(?<!\d)0\.1\.\d+(?!\d)")
    violations: list[str] = []
    for path in sorted((REPO_ROOT / "tests").rglob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                identity = f"{path.relative_to(REPO_ROOT)}:{line_number}"
                if not any(identity.startswith(item.split("::", 1)[0]) for item in allowed):
                    violations.append(f"{identity}: {line.strip()}")
    assert violations == []
```

- [x] **Step 2: Run it and confirm it fails on current real literals**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_build_and_verify_plugin.py::test_tests_do_not_introduce_real_plugin_version_literals
```

Expected: FAIL if existing hard-coded real `0.1.x` literals are not covered by the final allowlist.

- [x] **Step 3: Make the guard precise**

Keep the guard in one test. Use a small explicit allowlist for true fixture cases only; do not allow ordinary assertions that duplicate current plugin versions.

- [x] **Step 4: Preserve dual manifest file comparison**

Confirm existing tests read both files and compare values directly:

```python
codex_manifest = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
claude_manifest = read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")
assert codex_manifest["version"] == claude_manifest["version"]
```

- [x] **Step 5: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_build_and_verify_plugin.py::test_build_and_verify_plugin_has_dual_manifests tests/test_build_and_verify_plugin.py::test_tests_do_not_introduce_real_plugin_version_literals
```

Expected: PASS.

### Task 2: Release Flow Runtime Preflight

**Files:**
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- Modify: `tests/test_release_flow_cli.py`
- Test: `tests/test_release_flow_cli.py`

- [x] **Step 1: Write failing preflight test**

Add a test that creates build-and-verify（构建与验证）manifests at the requested release version and `.build-and-verify/runtime/version.json` at an older version:

```python
def test_preflight_blocks_stale_build_and_verify_runtime(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_plugin_manifests(project, "build-and-verify", "0.1.37")
    write_json(project / ".build-and-verify" / "runtime" / "version.json", {"runtime_version": "0.1.36"})
    monkeypatch.setattr(load_release_flow_module(), "remote_release_errors", lambda _project, _tag: [])

    result = run("preflight", "--project", str(project), "--tag", "v0.1.37", "--version", "0.1.37", "--bump-plugins", "build-and-verify")

    assert result.returncode == 1
    assert "runtime_update_required" in result.stdout
    assert "repository=0.1.36" in result.stdout
    assert "requested=0.1.37" in result.stdout
    assert "update-runtime" in result.stdout
```

- [x] **Step 2: Run test and confirm failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_release_flow_cli.py::test_preflight_blocks_stale_build_and_verify_runtime
```

Expected: FAIL because runtime freshness is not implemented yet.

- [x] **Step 3: Implement minimal runtime check**

In `release_flow.py`, add helpers near existing manifest helpers:

```python
def build_and_verify_runtime_version(project: Path) -> str | None:
    path = project / ".build-and-verify" / "runtime" / "version.json"
    if not path.exists():
        return None
    data = read_json_mapping(path)
    value = data.get("runtime_version") or data.get("plugin_version")
    return value if isinstance(value, str) else None
```

In `preflight_errors`, only when `"build-and-verify" in bumped`, compare runtime version to `version` and append:

```python
errors.append(f"runtime_update_required: repository={runtime or 'missing'} requested={version}")
```

- [x] **Step 4: Add next action**

Extend `preflight_next_action`:

```python
if error.startswith("runtime_update_required: "):
    return "run build-and-verify update-runtime, commit the runtime snapshot through PR Flow, then rerun release-flow preflight"
```

- [x] **Step 5: Prove preflight is read-only**

In the same test, snapshot `version.json` bytes before/after and assert unchanged.

- [x] **Step 6: Run Release Flow tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_release_flow_cli.py::test_preflight_blocks_stale_build_and_verify_runtime tests/test_release_flow_cli.py::test_release_flow_local_e2e
```

Expected: PASS.

### Task 3: Build And Verify Stale Runtime Contract

**Files:**
- Modify: `tests/test_build_and_verify_plugin.py`
- Modify only if needed: `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py`
- Test: `tests/test_build_and_verify_plugin.py`

- [x] **Step 1: Add or tighten exit behavior assertion**

In the existing stale runtime tests, assert the command return code still reflects the underlying build/verify result, not the stale runtime hint:

```python
assert result.returncode == 0
assert "runtime_outdated:" in result.stdout
assert "update-runtime" in result.stdout
```

- [x] **Step 2: Assert runtime files do not change**

Use existing byte snapshots:

```python
before = runtime_file.read_bytes()
result = run_check(project, "verify", check_user_runtime=True)
assert runtime_file.read_bytes() == before
```

- [x] **Step 3: Run focused build-and-verify tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_build_and_verify_plugin.py::test_build_and_verify_verify_does_not_mutate_repository_runtime tests/test_build_and_verify_plugin.py::test_build_and_verify_verify_reports_newer_user_runtime_without_mutation
```

Expected: PASS.

### Task 4: Plugin Sync Runtime Contract

**Files:**
- Modify: `C:\Users\liuli\.agents\skills\plugin-sync\references\status-taxonomy.md`
- Modify: `C:\Users\liuli\.agents\skills\plugin-sync\references\update-build-and-verify-runtime.md`
- Modify if needed: `C:\Users\liuli\.agents\skills\plugin-sync\references\check.md`
- Modify: `tests/test_build_and_verify_plugin.py` or create `tests/test_plugin_sync_skill_contract.py`
- Test: plugin-sync（插件同步）document contract tests.

- [x] **Step 1: Write failing document contract test**

Create `tests/test_plugin_sync_skill_contract.py` with direct file checks:

```python
from pathlib import Path

PLUGIN_SYNC = Path.home() / ".agents" / "skills" / "plugin-sync"

def read(name: str) -> str:
    return (PLUGIN_SYNC / name).read_text(encoding="utf-8")

def test_plugin_sync_runtime_status_contract() -> None:
    taxonomy = read("references/status-taxonomy.md")
    update = read("references/update-build-and-verify-runtime.md")
    for status in [
        "runtime_not_configured",
        "runtime_source_missing",
        "runtime_current",
        "runtime_stale",
        "runtime_updated",
        "update_failed",
    ]:
        assert status in taxonomy
        assert status in update
    assert "`not_configured`" not in update
```

- [x] **Step 2: Run test and confirm failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_plugin_sync_skill_contract.py
```

Expected: FAIL because `update_failed` and `not_configured` are not aligned yet.

- [x] **Step 3: Update status taxonomy**

In `status-taxonomy.md`, add:

```text
- `update_failed`（更新失败）: authorized repository runtime（仓库运行时） update failed.
```

- [x] **Step 4: Split read-only and authorized update docs**

In `update-build-and-verify-runtime.md`, make two sections:

```markdown
## Read-Only Check（只读检查）
...
## Authorized Update（授权更新）
...
```

Ensure read-only output includes `runtime_not_configured`, `runtime_source_missing`, `runtime_current`, and `runtime_stale`.

- [x] **Step 5: Add reread and PR Flow condition**

Document:

```text
After authorized update, reread <repo>\.build-and-verify\runtime\version.json.
Report PR Flow（拉取请求流程） only when Git（版本管理） reports tracked changes under .build-and-verify/runtime/.
```

- [x] **Step 6: Run plugin-sync contract test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_plugin_sync_skill_contract.py
```

Expected: PASS.

### Task 5: End-To-End Regressions

**Files:**
- Modify: `tests/test_release_flow_cli.py`
- Modify: `tests/test_build_and_verify_plugin.py`
- Modify: `tests/test_plugin_sync_skill_contract.py`

- [x] **Step 1: Release Flow entrypoint regression**

Use the CLI-like `run("preflight", ...)` helper and assert stale runtime returns `runtime_update_required` from the user entrypoint.

- [x] **Step 2: Build/verify entrypoint regression**

Use existing `run_check(project, "verify", check_user_runtime=True)` helper and assert stale runtime output plus unchanged runtime file.

- [x] **Step 3: Plugin-sync read-only regression**

In document contract tests, assert the read-only section names `.build-and-verify/config.json`, `version.json`, `runtime_current`, and `runtime_stale`.

- [x] **Step 4: Plugin-sync authorized update regression**

In document contract tests, assert the authorized update section names `update-runtime`, reread `version.json`, `runtime_updated`, `update_failed`, and PR Flow（拉取请求流程） tracked changes condition.

- [x] **Step 5: Run focused regression set**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_release_flow_cli.py::test_preflight_blocks_stale_build_and_verify_runtime tests/test_build_and_verify_plugin.py::test_build_and_verify_verify_reports_newer_user_runtime_without_mutation tests/test_plugin_sync_skill_contract.py
```

Expected: PASS.

### Task 6: Final Verification

**Files:**
- Modify: `openspec/changes/stabilize-version-runtime-sync/tasks.md`

- [x] **Step 1: Run OpenSpec validation**

Run:

```powershell
openspec validate stabilize-version-runtime-sync --strict
```

Expected: `Change 'stabilize-version-runtime-sync' is valid`.

- [x] **Step 2: Run repository fast verification**

Run:

```powershell
.\.build-and-verify\runtime\build_and_verify.py verify --project . 
```

Expected: `status: passed`.

- [x] **Step 3: Mark tasks complete**

After the matching implementation and verification pass, mark each completed item in:

```text
openspec/changes/stabilize-version-runtime-sync/tasks.md
```

- [x] **Step 4: Commit**

Commit only after tests pass. The user-level plugin-sync（插件同步） files are outside this repository and cannot be staged in this repo commit; report them separately in the final summary.

```powershell
git add docs/superpowers/plans/2026-07-09-stabilize-version-runtime-sync.md docs/superpowers/specs/2026-07-09-stabilize-version-runtime-sync-design.md openspec/changes/stabilize-version-runtime-sync tests plugins
git commit -m "实现版本运行时同步闭环"
```
