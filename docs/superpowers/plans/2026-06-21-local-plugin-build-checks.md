---
change: add-local-plugin-build-checks
design-doc: docs/superpowers/specs/2026-06-21-local-plugin-build-checks-design.md
base-ref: c6efd0f55f0dfabe5857ba66a96c48cdb64cd554
---

# Local Plugin Build Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add repository-local build and verify commands that validate plugin package shape before Comet（双星流程）verification.

**Architecture:** Add one Python（Python 语言）entrypoint at `scripts/check.py` with focused helper functions for marketplace discovery, Claude（Claude 编码工具）validation, manifest checks, projection checks, template mirror checks, and verify delegation. Keep `build` local and side-effect free; keep full test execution in `verify`.

**Tech Stack:** Python standard library, PyYAML（YAML 解析库）for `.release-flow/projection.yaml`, pytest（Python 测试框架）, Claude CLI（Claude 命令行工具）for `claude plugin validate`.

---

## File Structure

- Create `scripts/check.py`: command entrypoint and all local check helpers.
- Create `tests/test_local_plugin_build_checks.py`: focused tests for `scripts/check.py`.
- Create `pyproject.toml`: pytest discovery defaults.
- Modify `.comet/config.yaml`: add `build_command` and `verify_command`.
- Delete `.comet/build-check.sh`: only after checking no references remain.
- Modify `openspec/changes/add-local-plugin-build-checks/tasks.md`: mark tasks complete as implementation progresses.

## Task 1: Test Build Command Behavior

**Files:**
- Create: `tests/test_local_plugin_build_checks.py`
- Read: `.claude-plugin/marketplace.json`
- Read: `.release-flow/projection.yaml`

- [x] **Step 1: Write failing tests for marketplace loading and Claude validation command dispatch**

Add this initial test file:

```python
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check.py"


def load_check_module():
    spec = importlib.util.spec_from_file_location("repo_check", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_plugin(root: Path, name: str) -> Path:
    plugin = root / "plugins" / name
    write_json(
        plugin / ".claude-plugin" / "plugin.json",
        {
            "name": name,
            "version": "0.1.0",
            "description": f"{name} plugin",
            "skills": "./skills",
        },
    )
    write_json(
        plugin / ".codex-plugin" / "plugin.json",
        {
            "name": name,
            "version": "0.1.0",
            "description": f"{name} plugin",
            "skills": "./skills",
        },
    )
    (plugin / "skills" / name).mkdir(parents=True)
    (plugin / "skills" / name / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name}\n---\n",
        encoding="utf-8",
    )
    return plugin


def make_marketplace(root: Path, names: list[str]) -> None:
    write_json(
        root / ".claude-plugin" / "marketplace.json",
        {
            "name": "test-marketplace",
            "owner": {"name": "Test"},
            "plugins": [
                {
                    "name": name,
                    "source": f"./plugins/{name}",
                    "description": f"{name} plugin",
                }
                for name in names
            ],
        },
    )


def make_projection(root: Path, names: list[str]) -> None:
    projection = "\n".join(
        [
            "version: 1",
            "",
            "generators:",
            "  - path: .agents/plugins/marketplace.json",
            "    type: codex-marketplace",
            "    identity: codex",
            "    plugins:",
            *[f"      - {name}" for name in names],
            "",
        ]
    )
    (root / ".release-flow").mkdir(parents=True)
    (root / ".release-flow" / "projection.yaml").write_text(projection, encoding="utf-8")


def test_build_runs_claude_validation_for_marketplace_and_each_plugin(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_plugin(tmp_path, "beta")
    make_marketplace(tmp_path, ["alpha", "beta"])
    make_projection(tmp_path, ["alpha", "beta"])

    calls: list[list[str]] = []

    def fake_run(command, cwd, text, capture_output, check):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    errors = module.run_build(tmp_path, runner=fake_run)

    assert errors == []
    assert calls == [
        ["claude", "plugin", "validate", "."],
        ["claude", "plugin", "validate", str(tmp_path / "plugins" / "alpha")],
        ["claude", "plugin", "validate", str(tmp_path / "plugins" / "beta")],
    ]
    assert all("--strict" not in command for command in calls)
```

- [x] **Step 2: Run the new focused test and confirm it fails because `scripts/check.py` does not exist**

Run:

```bash
python -m pytest tests/test_local_plugin_build_checks.py::test_build_runs_claude_validation_for_marketplace_and_each_plugin -q
```

Expected: FAIL with a missing file or import error for `scripts/check.py`.

- [x] **Step 3: Add failing tests for marketplace source and manifest errors**

Append:

```python
def test_build_rejects_marketplace_source_outside_repo(tmp_path: Path) -> None:
    module = load_check_module()
    make_marketplace(tmp_path, ["escape"])
    data = json.loads((tmp_path / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    data["plugins"][0]["source"] = "../outside"
    write_json(tmp_path / ".claude-plugin" / "marketplace.json", data)

    errors = module.run_build(tmp_path, runner=lambda *args, **kwargs: None)

    assert any("source_outside_repo" in error for error in errors)


def test_build_reports_manifest_name_mismatch(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha"])
    write_json(
        tmp_path / "plugins" / "alpha" / ".claude-plugin" / "plugin.json",
        {
            "name": "wrong",
            "version": "0.1.0",
            "description": "wrong plugin",
            "skills": "./skills",
        },
    )

    errors = module.run_build(tmp_path, runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""))

    assert any("claude_manifest_name_mismatch" in error for error in errors)


def test_build_reports_missing_codex_manifest_path(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha"])
    (tmp_path / "plugins" / "alpha" / "skills").rename(tmp_path / "plugins" / "alpha" / "missing-skills")

    errors = module.run_build(tmp_path, runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""))

    assert any("missing_manifest_path" in error for error in errors)
```

- [x] **Step 4: Run these tests and confirm they fail for missing implementation**

Run:

```bash
python -m pytest tests/test_local_plugin_build_checks.py -q
```

Expected: FAIL because `run_build` and related checks are not implemented.

## Task 2: Test Projection And Template Mirror Checks

**Files:**
- Modify: `tests/test_local_plugin_build_checks.py`

- [ ] **Step 1: Add failing tests for projection registration consistency**

Append:

```python
def test_build_reports_projection_plugin_mismatch(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha", "missing"])

    errors = module.run_build(tmp_path, runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""))

    assert any("projection_plugins_mismatch" in error for error in errors)


def test_build_reports_duplicate_projection_plugin(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha", "alpha"])

    errors = module.run_build(tmp_path, runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""))

    assert any("duplicate_projection_plugin" in error for error in errors)
```

- [ ] **Step 2: Add failing tests for Guard Profile template mirror consistency**

Append:

```python
def make_guard_profile_mirrors(root: Path, content: str = "schema_version: guard-profile/v1\n") -> None:
    left = root / "plugins" / "agent-guard" / "assets" / "templates" / "guard-profile" / "minimal"
    right = (
        root
        / "plugins"
        / "agent-guard"
        / "skills"
        / "agent-guard"
        / "assets"
        / "templates"
        / "guard-profile"
        / "minimal"
    )
    left.mkdir(parents=True)
    right.mkdir(parents=True)
    (left / "GUARD-MANIFEST.yaml").write_text(content, encoding="utf-8")
    (right / "GUARD-MANIFEST.yaml").write_text(content, encoding="utf-8")


def test_build_accepts_matching_guard_profile_mirrors(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha"])
    make_guard_profile_mirrors(tmp_path)

    errors = module.check_guard_profile_template_mirrors(tmp_path)

    assert errors == []


def test_build_reports_guard_profile_mirror_mismatch(tmp_path: Path) -> None:
    module = load_check_module()
    make_guard_profile_mirrors(tmp_path)
    right_file = (
        tmp_path
        / "plugins"
        / "agent-guard"
        / "skills"
        / "agent-guard"
        / "assets"
        / "templates"
        / "guard-profile"
        / "minimal"
        / "GUARD-MANIFEST.yaml"
    )
    right_file.write_text("schema_version: changed\n", encoding="utf-8")

    errors = module.check_guard_profile_template_mirrors(tmp_path)

    assert any("guard_profile_template_mismatch" in error for error in errors)
```

- [ ] **Step 3: Run projection and mirror tests and confirm they fail for missing implementation**

Run:

```bash
python -m pytest tests/test_local_plugin_build_checks.py -q
```

Expected: FAIL for missing projection and mirror check functions.

## Task 3: Implement `scripts/check.py`

**Files:**
- Create: `scripts/check.py`
- Modify: `tests/test_local_plugin_build_checks.py` only if assertions need to match clearer error strings

- [ ] **Step 1: Create script skeleton with CLI and error collection**

Create `scripts/check.py`:

```python
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    import yaml
except ImportError:
    yaml = None


REPO_ROOT = Path(__file__).resolve().parents[1]
Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class MarketplacePlugin:
    name: str
    source: str
    path: Path


def read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing_json: {path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid_json: {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"invalid_json_object: {path}"
    return data, None


def resolve_repo_relative(root: Path, value: str, label: str) -> tuple[Path | None, str | None]:
    source = Path(value)
    if source.is_absolute():
        return None, f"{label}_absolute_path: {value}"
    resolved = (root / source).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        return None, f"{label}_outside_repo: {value}"
    return resolved, None
```

- [ ] **Step 2: Implement marketplace discovery**

Add:

```python
def marketplace_plugins(root: Path) -> tuple[list[MarketplacePlugin], list[str]]:
    data, error = read_json(root / ".claude-plugin" / "marketplace.json")
    if error:
        return [], [error]
    plugins = data.get("plugins") if data else None
    if not isinstance(plugins, list):
        return [], [f"invalid_marketplace_plugins: {root / '.claude-plugin' / 'marketplace.json'}"]

    result: list[MarketplacePlugin] = []
    errors: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(plugins):
        if not isinstance(entry, dict):
            errors.append(f"invalid_marketplace_entry: plugins[{index}]")
            continue
        name = entry.get("name")
        source = entry.get("source")
        if not isinstance(name, str) or not name:
            errors.append(f"missing_marketplace_name: plugins[{index}]")
            continue
        if name in seen:
            errors.append(f"duplicate_marketplace_plugin: {name}")
        seen.add(name)
        if not isinstance(source, str) or not source:
            errors.append(f"missing_marketplace_source: {name}")
            continue
        path, path_error = resolve_repo_relative(root, source, "source")
        if path_error:
            errors.append(path_error)
            continue
        if path is not None and not path.exists():
            errors.append(f"missing_marketplace_source_path: {name}: {source}")
            continue
        result.append(MarketplacePlugin(name=name, source=source, path=path))
    return result, errors
```

- [ ] **Step 3: Implement Claude validation dispatch**

Add:

```python
def run_command(command: list[str], root: Path, runner: Runner) -> str | None:
    try:
        result = runner(command, cwd=root, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return f"missing_command: {command[0]}"
    if result.returncode != 0:
        output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
        return f"command_failed: {' '.join(command)}\n{output}"
    return None


def check_claude_validation(root: Path, plugins: Iterable[MarketplacePlugin], runner: Runner) -> list[str]:
    errors: list[str] = []
    marketplace_error = run_command(["claude", "plugin", "validate", "."], root, runner)
    if marketplace_error:
        errors.append(marketplace_error)
    for plugin in plugins:
        plugin_error = run_command(["claude", "plugin", "validate", str(plugin.path)], root, runner)
        if plugin_error:
            errors.append(plugin_error)
    return errors
```

- [ ] **Step 4: Implement manifest checks**

Add:

```python
def manifest_path_errors(plugin_root: Path, manifest: dict[str, Any], fields: list[str]) -> list[str]:
    errors: list[str] = []
    for field in fields:
        value = manifest.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value:
            errors.append(f"invalid_manifest_path: {plugin_root}: {field}")
            continue
        path, path_error = resolve_repo_relative(plugin_root, value, f"manifest_{field}")
        if path_error:
            errors.append(path_error)
            continue
        if path is not None and not path.exists():
            errors.append(f"missing_manifest_path: {plugin_root}: {field}: {value}")
    return errors


def check_plugin_manifests(root: Path, plugins: Iterable[MarketplacePlugin]) -> list[str]:
    errors: list[str] = []
    required = ["name", "version", "description", "skills"]
    for plugin in plugins:
        claude_path = plugin.path / ".claude-plugin" / "plugin.json"
        codex_path = plugin.path / ".codex-plugin" / "plugin.json"
        claude, claude_error = read_json(claude_path)
        codex, codex_error = read_json(codex_path)
        if claude_error:
            errors.append(claude_error)
            continue
        if codex_error:
            errors.append(codex_error)
            continue
        assert claude is not None
        assert codex is not None
        if claude.get("name") != plugin.name:
            errors.append(f"claude_manifest_name_mismatch: {plugin.name}: {claude.get('name')}")
        if codex.get("name") != plugin.name:
            errors.append(f"codex_manifest_name_mismatch: {plugin.name}: {codex.get('name')}")
        for manifest_name, manifest in [("claude", claude), ("codex", codex)]:
            for field in required:
                if not isinstance(manifest.get(field), str) or not manifest.get(field):
                    errors.append(f"missing_manifest_field: {manifest_name}: {plugin.name}: {field}")
        errors.extend(manifest_path_errors(plugin.path, claude, ["skills"]))
        errors.extend(manifest_path_errors(plugin.path, codex, ["skills", "hooks", "assets"]))
    return errors
```

- [ ] **Step 5: Implement projection checks**

Add:

```python
def projection_plugin_lists(root: Path) -> tuple[list[list[str]], list[str]]:
    if yaml is None:
        return [], ["missing_dependency: PyYAML"]
    path = root / ".release-flow" / "projection.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], [f"missing_yaml: {path}"]
    except yaml.YAMLError as exc:
        return [], [f"invalid_yaml: {path}: {exc}"]
    if not isinstance(data, dict):
        return [], [f"invalid_yaml_mapping: {path}"]
    generators = data.get("generators")
    if not isinstance(generators, list):
        return [], [f"missing_projection_generators: {path}"]
    lists: list[list[str]] = []
    errors: list[str] = []
    for index, generator in enumerate(generators):
        if not isinstance(generator, dict):
            continue
        if generator.get("type") != "codex-marketplace":
            continue
        plugins = generator.get("plugins")
        if not isinstance(plugins, list) or not all(isinstance(item, str) and item for item in plugins):
            errors.append(f"invalid_projection_plugins: generators[{index}]")
            continue
        lists.append(plugins)
    return lists, errors


def check_projection(root: Path, plugins: Iterable[MarketplacePlugin]) -> list[str]:
    plugin_names = {plugin.name for plugin in plugins}
    lists, errors = projection_plugin_lists(root)
    for plugins_list in lists:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for name in plugins_list:
            if name in seen:
                duplicates.add(name)
            seen.add(name)
        for duplicate in sorted(duplicates):
            errors.append(f"duplicate_projection_plugin: {duplicate}")
        if set(plugins_list) != plugin_names:
            errors.append(
                "projection_plugins_mismatch: "
                f"projection={sorted(set(plugins_list))} marketplace={sorted(plugin_names)}"
            )
    return errors
```

- [ ] **Step 6: Implement Guard Profile mirror checks and command handlers**

Add:

```python
def relative_files(root: Path) -> dict[str, Path]:
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)).replace("\\", "/"): path
        for path in root.rglob("*")
        if path.is_file()
    }


def check_guard_profile_template_mirrors(root: Path) -> list[str]:
    left = root / "plugins" / "agent-guard" / "assets" / "templates" / "guard-profile"
    right = (
        root
        / "plugins"
        / "agent-guard"
        / "skills"
        / "agent-guard"
        / "assets"
        / "templates"
        / "guard-profile"
    )
    left_files = relative_files(left)
    right_files = relative_files(right)
    errors: list[str] = []
    if set(left_files) != set(right_files):
        errors.append(
            "guard_profile_template_files_mismatch: "
            f"root={sorted(left_files)} skill={sorted(right_files)}"
        )
        return errors
    for name in sorted(left_files):
        if left_files[name].read_bytes() != right_files[name].read_bytes():
            errors.append(f"guard_profile_template_mismatch: {name}")
    return errors


def run_build(root: Path = REPO_ROOT, runner: Runner = subprocess.run) -> list[str]:
    plugins, errors = marketplace_plugins(root)
    errors.extend(check_claude_validation(root, plugins, runner))
    errors.extend(check_plugin_manifests(root, plugins))
    errors.extend(check_projection(root, plugins))
    errors.extend(check_guard_profile_template_mirrors(root))
    return errors


def run_verify(root: Path = REPO_ROOT, runner: Runner = subprocess.run) -> int:
    result = runner([sys.executable, "-m", "pytest"], cwd=root, text=True, capture_output=False, check=False)
    return result.returncode


def print_errors(errors: list[str]) -> None:
    for error in errors:
        print(f"error: {error}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build")
    subparsers.add_parser("verify")
    args = parser.parse_args(argv)
    if args.command == "build":
        errors = run_build()
        if errors:
            print_errors(errors)
            return 1
        print("status: build checks passed")
        return 0
    if args.command == "verify":
        return run_verify()
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run focused tests until they pass**

Run:

```bash
python -m pytest tests/test_local_plugin_build_checks.py -q
```

Expected: all tests in `tests/test_local_plugin_build_checks.py` pass.

- [ ] **Step 8: Commit the script and focused tests**

Run:

```bash
git add scripts/check.py tests/test_local_plugin_build_checks.py
git commit -m "feat: add local plugin build checks"
```

## Task 4: Add Verify Command Test And Pytest Configuration

**Files:**
- Modify: `tests/test_local_plugin_build_checks.py`
- Create: `pyproject.toml`

- [ ] **Step 1: Add failing verify delegation test**

Append:

```python
def test_verify_delegates_to_pytest(tmp_path: Path) -> None:
    module = load_check_module()
    calls: list[list[str]] = []

    def fake_run(command, cwd, text, capture_output, check):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    result = module.run_verify(tmp_path, runner=fake_run)

    assert result == 0
    assert calls == [[sys.executable, "-m", "pytest"]]
```

- [ ] **Step 2: Run the verify test and confirm it passes with existing implementation**

Run:

```bash
python -m pytest tests/test_local_plugin_build_checks.py::test_verify_delegates_to_pytest -q
```

Expected: PASS.

- [ ] **Step 3: Add pytest configuration**

Create `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-q"
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_local_plugin_build_checks.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit verify test and pytest configuration**

Run:

```bash
git add pyproject.toml tests/test_local_plugin_build_checks.py
git commit -m "test: cover verify command delegation"
```

## Task 5: Configure Comet And Remove Old Build Script

**Files:**
- Modify: `.comet/config.yaml`
- Delete: `.comet/build-check.sh`
- Modify: `tests/test_local_plugin_build_checks.py`

- [ ] **Step 1: Add failing Comet config test**

Append:

```python
def test_comet_config_points_to_check_commands() -> None:
    import yaml

    data = yaml.safe_load((REPO_ROOT / ".comet" / "config.yaml").read_text(encoding="utf-8"))

    assert data["build_command"] == "python scripts/check.py build"
    assert data["verify_command"] == "python scripts/check.py verify"
```

- [ ] **Step 2: Run config test and confirm it fails**

Run:

```bash
python -m pytest tests/test_local_plugin_build_checks.py::test_comet_config_points_to_check_commands -q
```

Expected: FAIL because `.comet/config.yaml` does not yet declare the commands.

- [ ] **Step 3: Update `.comet/config.yaml`**

Add:

```yaml
# 构建与验证命令
# build: 本地插件包成型检查；verify: 完整 Python 测试
build_command: python scripts/check.py build
verify_command: python scripts/check.py verify
```

- [ ] **Step 4: Confirm `.comet/build-check.sh` is unreferenced**

Run:

```bash
rg "\\.comet/build-check\\.sh|build-check\\.sh"
```

Expected: only the file path itself appears, or no references outside historical artifacts. If active config or docs still reference it, replace those references with `python scripts/check.py build` before deleting.

- [ ] **Step 5: Delete `.comet/build-check.sh`**

Delete the file after Step 4 confirms no active references remain.

- [ ] **Step 6: Run config test and focused tests**

Run:

```bash
python -m pytest tests/test_local_plugin_build_checks.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Comet config and old script removal**

Run:

```bash
git add .comet/config.yaml tests/test_local_plugin_build_checks.py .comet/build-check.sh
git commit -m "chore: configure comet build and verify commands"
```

## Task 6: Final Verification And OpenSpec Task Updates

**Files:**
- Modify: `openspec/changes/add-local-plugin-build-checks/tasks.md`

- [ ] **Step 1: Run build command**

Run:

```bash
python scripts/check.py build
```

Expected: exit code 0 and `status: build checks passed`.

- [ ] **Step 2: Run verify command**

Run:

```bash
python scripts/check.py verify
```

Expected: exit code 0 and full pytest suite passes.

- [ ] **Step 3: Confirm Comet source files were not modified**

Run:

```bash
git status --short
git diff --name-only
```

Expected: changed files are limited to this repository's OpenSpec artifacts, design/plan docs, local check script, tests, pytest config, `.comet/config.yaml`, and removal of `.comet/build-check.sh`. No files under `C:\Users\liuli\.codex\skills\comet` are modified.

- [ ] **Step 4: Mark OpenSpec tasks complete**

Update `openspec/changes/add-local-plugin-build-checks/tasks.md` by changing completed `- [ ]` entries to `- [x]` only after the corresponding evidence exists.

- [ ] **Step 5: Commit task updates**

Run:

```bash
git add openspec/changes/add-local-plugin-build-checks/tasks.md
git commit -m "chore: complete local build checks tasks"
```

## Self-Review

Spec coverage:
- Build command local package checks are covered by Tasks 1, 2, 3, and 5.
- Claude validation is covered by Tasks 1 and 3.
- Marketplace and manifest consistency is covered by Tasks 1 and 3.
- Release projection consistency is covered by Tasks 2 and 3.
- Guard Profile template mirrors are covered by Tasks 2 and 3.
- Verify command and pytest defaults are covered by Task 4.
- Comet command entrypoints are covered by Task 5.

Placeholder scan:
- No task uses placeholder markers.
- Every code-changing task has explicit paths, commands, and expected outcomes.

Type consistency:
- Planned function names are consistent across tests and implementation: `run_build`, `run_verify`, and `check_guard_profile_template_mirrors`.
