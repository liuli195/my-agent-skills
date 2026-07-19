---
change: sync-build-verify-runtime
design-doc: docs/superpowers/specs/2026-07-01-sync-build-verify-runtime-design.md
base-ref: b96a29134761e08bb9a71d917e9fcc8a1c6296c9
archived-with: 2026-07-01-sync-build-verify-runtime
---

# Sync Build And Verify Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `build-and-verify`（构建与验证） a stable repository runtime（运行时） entrypoint and explicit runtime（运行时） sync command.

**Architecture:** Keep one Python（Python 语言） entrypoint. Copy the executing runtime（运行时） files into `.build-and-verify/runtime/`; never let `build/verify`（构建/验证） mutate repository files. Version lookup is best-effort（尽力而为） and only prints guidance.

**Tech Stack:** Python（Python 语言） standard library, existing pytest（Python 测试运行器） tests, existing OpenSpec（开放规格） docs.

archived-with: 2026-07-01-sync-build-verify-runtime
---

## File Structure

- Modify: `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py`
  - Add `update-runtime`（更新运行时） command.
  - Add runtime（运行时） copy helpers.
  - Add best-effort（尽力而为） version提示 before `build/verify`（构建/验证）.
- Modify: `plugins/build-and-verify/skills/build-and-verify/SKILL.md`
  - Replace “不复制 runner（运行器）” with repository runtime（运行时） snapshot semantics.
  - Document stable `.build-and-verify/runtime/build_and_verify.py` entrypoint.
- Modify: `tests/test_build_and_verify_plugin.py`
  - Update old “not copy runner（运行器）” assertions.
  - Add tests for `init`（初始化）, `update-runtime`（更新运行时）, version提示, and no mutation from `build/verify`（构建/验证）.
- Modify: `.github/workflows/full-verify.yml`, `.comet.yaml`, `.pr-flow/config.yaml`, `.build-and-verify/config.json`
  - Use `.build-and-verify/runtime/build_and_verify.py` where a repository-stable entrypoint is required.
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
  - Keep newly initialized PR Flow（拉取请求流程） hotfix verification on the stable repository runtime（运行时） path.
- Add generated runtime snapshot: `.build-and-verify/runtime/build_and_verify.py`, `.build-and-verify/runtime/build_and_verify_runner.py`, `.build-and-verify/runtime/version.json`
  - Produced by the updated command, not hand-crafted.

## Task 1: Tests For Runtime Snapshot Semantics

**Files:**
- Modify: `tests/test_build_and_verify_plugin.py`
- Modify: `openspec/changes/sync-build-verify-runtime/tasks.md`

- [x] **Step 1: Add failing tests for init runtime copy**

Add tests near the existing init tests:

```python
def test_build_and_verify_init_copies_repository_runtime(tmp_path: Path) -> None:
    project = tmp_path / "project"

    result = run_build_and_verify("init", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    runtime = project / ".build-and-verify" / "runtime"
    assert (runtime / "build_and_verify.py").is_file()
    assert (runtime / "build_and_verify_runner.py").is_file()
    assert (runtime / "version.json").is_file()
```

- [x] **Step 2: Add failing tests for explicit update-runtime**

```python
def test_build_and_verify_update_runtime_refreshes_runtime_without_config(tmp_path: Path) -> None:
    project = tmp_path / "project"
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    config_before = (project / ".build-and-verify" / "config.json").read_text(encoding="utf-8")
    (project / ".build-and-verify" / "runtime" / "build_and_verify.py").write_text("stale\n", encoding="utf-8")

    result = run_build_and_verify("update-runtime", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "stale" not in (project / ".build-and-verify" / "runtime" / "build_and_verify.py").read_text(encoding="utf-8")
    assert (project / ".build-and-verify" / "config.json").read_text(encoding="utf-8") == config_before
```

- [x] **Step 3: Add failing tests for non-mutating build/verify**

Use a tiny config command that always passes. Hash or read runtime（运行时） files before and after `verify`（验证）:

```python
def test_build_and_verify_verify_does_not_mutate_repository_runtime(tmp_path: Path) -> None:
    project = tmp_path / "project"
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    write_json(project / ".build-and-verify" / "config.json", {"version": 1, "build": {"checks": []}, "verify": {"checks": []}})
    runtime_file = project / ".build-and-verify" / "runtime" / "build_and_verify.py"
    before = runtime_file.read_bytes()

    result = run_check(project, "verify")

    assert result.returncode == 0, result.stdout + result.stderr
    assert runtime_file.read_bytes() == before
```

- [x] **Step 4: Run the new tests and confirm they fail**

Run:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py -k "runtime or update_runtime"
```

Expected: the new tests fail because runtime（运行时） copy/update does not exist yet.

## Task 2: Minimal Runtime Copy Implementation

**Files:**
- Modify: `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py`

- [x] **Step 1: Add constants and metadata helpers**

Add only standard library helpers:

```python
RUNTIME_FILES = ("build_and_verify.py", "build_and_verify_runner.py")
VERSION_FILE = "version.json"
PLUGIN_VERSION = "0.1.32"
```

Add helpers:

```python
def _runtime_root() -> Path:
    return Path(__file__).resolve().parent


def _runtime_target(project: Path) -> Path:
    return project / ".build-and-verify" / "runtime"
```

- [x] **Step 2: Implement copy from executing runtime**

```python
def _write_version(target: Path) -> None:
    payload = {
        "plugin": "build-and-verify",
        "plugin_version": PLUGIN_VERSION,
        "runtime_version": PLUGIN_VERSION,
    }
    (target / VERSION_FILE).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```

Copy only `RUNTIME_FILES` from `_runtime_root()` to `_runtime_target(project)`.

- [x] **Step 3: Add `update-runtime` parser and command branch**

Add:

```python
update_parser = subparsers.add_parser("update-runtime")
update_parser.add_argument("--project", required=True)
```

Branch:

```python
if args.command == "update-runtime":
    return _update_runtime(Path(args.project).resolve())
```

- [x] **Step 4: Make init preflight include runtime directory**

`init`（初始化） must refuse existing `.build-and-verify/runtime/` before creating anything.

- [x] **Step 5: Run targeted tests**

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py -k "runtime or update_runtime"
```

Expected: runtime copy/update tests pass.

## Task 3: Version Prompt, Text, And Repository Entrypoints

**Files:**
- Modify: `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py`
- Modify: `plugins/build-and-verify/skills/build-and-verify/SKILL.md`
- Modify: `.github/workflows/full-verify.yml`
- Modify: `.comet.yaml`
- Modify: `.pr-flow/config.yaml`
- Modify: `.build-and-verify/config.json`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Modify: `tests/test_build_and_verify_plugin.py`

- [x] **Step 1: Add best-effort version discovery**

Implement a small function that reads `version.json` from current runtime（运行时） and scans known user-level roots for newer `build-and-verify` runtime（运行时） files. If none are found, return `None`.

- [x] **Step 2: Print version hint before build/verify**

Before `run_build` and `run_verify`, call the version check. If newer script is found, print:

```text
runtime_outdated: repository=<version> installed=<version>
run: python <newer-script> update-runtime --project <repo>
```

Do not change the command return code.

- [x] **Step 3: Update Skill（技能）文案**

Replace the old boundary that says runtime（运行时） is not copied. Document:

```text
init（初始化）和 update-runtime（更新运行时）复制同一套 runtime（运行时）到 .build-and-verify/runtime/。
build/verify（构建/验证）只提示版本落后，不自动更新。
```

- [x] **Step 4: Update stable repository commands**

Replace repository-owned CI（持续集成） and automation commands with:

```powershell
python .build-and-verify/runtime/build_and_verify.py verify --project . --full
```

Use `build` or fast `verify` variants where existing config currently needs them.

- [x] **Step 5: Run contract tests**

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py
```

Expected: all `build-and-verify`（构建与验证） tests pass.

## Task 4: End-To-End Regression And Task Closure

**Files:**
- Modify: `openspec/changes/sync-build-verify-runtime/tasks.md`
- Generated: `.build-and-verify/runtime/*`

- [x] **Step 1: Generate repository runtime snapshot**

Run:

```powershell
python plugins\build-and-verify\skills\build-and-verify\scripts\build_and_verify.py update-runtime --project .
```

Expected: `.build-and-verify/runtime/` exists and contains the three runtime（运行时） files.

- [x] **Step 2: Run end-to-end regression in a temporary target repository**

Create a temp directory, run `init`（初始化）, then run from the copied runtime（运行时）:

```powershell
python .build-and-verify/runtime/build_and_verify.py update-runtime --project .
python .build-and-verify/runtime/build_and_verify.py build --project .
python .build-and-verify/runtime/build_and_verify.py verify --project .
```

Expected: all commands exit 0 and `build/verify`（构建/验证） do not mutate `.build-and-verify/runtime/`.

- [x] **Step 3: Run repository stable entrypoint**

```powershell
python .build-and-verify\runtime\build_and_verify.py verify --project .
```

Expected: fast verify（快速验证） exits 0.

- [x] **Step 4: Mark OpenSpec tasks complete**

After implementation and verification, update `openspec/changes/sync-build-verify-runtime/tasks.md` checkboxes to complete.

- [x] **Step 5: Commit implementation**

Only after tests pass:

```powershell
git add .build-and-verify plugins/build-and-verify tests .github .comet.yaml .pr-flow/config.yaml docs/superpowers/specs docs/superpowers/plans openspec/changes/sync-build-verify-runtime
git commit -m "feat: 同步 build-and-verify 仓库运行时"
```

## Self-Review

- Spec coverage: runtime（运行时） copy, `update-runtime`（更新运行时）, version提示, no mutation, Skill（技能） text, stable CI（持续集成） entrypoint, and end-to-end（端到端） verification are covered.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: all planned commands use existing Python（Python 语言） script names and existing test file paths.
