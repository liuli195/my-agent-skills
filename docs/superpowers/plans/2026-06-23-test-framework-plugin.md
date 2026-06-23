---
change: split-fast-full-verification
design-doc: docs/superpowers/specs/2026-06-23-test-framework-plugin-design.md
base-ref: b58fde2cf4ddcc91316737670271c938bc83714f
---

# Test Framework Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **2026-06-23 update:** Latest decision supersedes earlier steps that mention copying or maintaining a target-repository runner（运行器） script. The generic runner now lives only inside the `test-framework` Plugin（测试框架插件） as `scripts/test_framework_runner.py`, and the unified command entrypoint is `scripts/test_framework.py build|verify --project <repo>`. Target repositories still own repository-specific check commands such as `scripts/local_plugin_build.py`, referenced from `.test-framework/config.json`.

**Goal:** Build a lightweight `test-framework` Plugin（测试框架插件） that initializes one reusable build（构建检查） / default cached verify（快速验证） / explicit full verify（全量验证） framework.

**Architecture:** The plugin ships the real framework runner（运行器） and command entrypoint. Target repositories define checks in `.test-framework/config.json`; the plugin entrypoint executes configured checks, selects affected checks for default verify（验证）, and caches only passed（已通过） results in `.test-framework/cache/`. The command path is the currently installed Skill（技能） script path: project-level（项目级） installs can call the repository plugin path, and user-level（用户级） installs call the user Skill path. The target repository does not persist either plugin path.

**Tech Stack:** Python（Python 语言） standard library only for initialized target repositories: `argparse`, `fnmatch`, `hashlib`, `json`, `pathlib`, `shlex`, `subprocess`, and `sys`. Tests use pytest（Python 测试框架） in this repository.

---

## File Structure

- Create `plugins/test-framework/.codex-plugin/plugin.json`: Codex（Codex 版本） manifest（清单）.
- Create `plugins/test-framework/.claude-plugin/plugin.json`: Claude（Claude 版本） manifest（清单）.
- Create `plugins/test-framework/skills/test-framework/SKILL.md`: single Skill（技能） entrypoint.
- Create `plugins/test-framework/skills/test-framework/scripts/test_framework.py`: deterministic init（初始化） and command entrypoint script.
- Create `plugins/test-framework/skills/test-framework/scripts/test_framework_runner.py`: complete reusable runner（运行器） implementation.
- Create `plugins/test-framework/skills/test-framework/assets/templates/test-framework/config.json`: minimal JSON（数据格式） config template.
- Create `plugins/test-framework/skills/test-framework/assets/templates/test-framework/gitignore`: ignores `/cache/` and `/runs/`.
- Modify `.claude-plugin/marketplace.json`: register `test-framework`.
- Modify `.agents/plugins/marketplace.json`: register `test-framework`.
- Modify `.release-flow/projection.yaml`: register `test-framework`.
- Modify `plugins/release-flow/skills/release-flow/scripts/release_flow.py`: register `test-framework` in release projection（发布投影） metadata validation/generation only.
- Keep `scripts/local_plugin_build.py`: repository-owned package-shape check command referenced by `build.checks`; it is not a plugin output.
- Create `.test-framework/config.json`: this repository's configured checks.
- Create `.test-framework/.gitignore`: ignores framework local state.
- Modify `tests/test_test_framework_plugin.py`: package, init, conflict, and E2E（端到端） tests.
- Modify `tests/test_local_plugin_build_checks.py`: local runner behavior tests.

This plan does not modify PR Flow（拉取请求流程）, Release Flow（发布流程） behavior, CI（持续集成）, `.pr-flow/config.yaml`, or `plugins/pr-flow/**`. Release Flow（发布流程） changes are limited to `test-framework` package metadata validation/generation for release projection（发布投影）.

## Commit Policy

Repository rules require explicit user authorization before commit（提交）. Tasks below have verification checkpoints only. Do not run `git commit` unless the user explicitly authorizes it later.

### Task 1: Package the Dual-Surface Plugin

**Files:**
- Create: `plugins/test-framework/.codex-plugin/plugin.json`
- Create: `plugins/test-framework/.claude-plugin/plugin.json`
- Create: `plugins/test-framework/skills/test-framework/SKILL.md`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `.agents/plugins/marketplace.json`
- Modify: `.release-flow/projection.yaml`
- Create: `tests/test_test_framework_plugin.py`

- [x] **Step 1: Write package tests**

Create `tests/test_test_framework_plugin.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = REPO_ROOT / "plugins" / "test-framework"
SCRIPT = PLUGIN / "skills" / "test-framework" / "scripts" / "test_framework.py"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_test_framework_plugin_has_dual_manifests() -> None:
    codex = read_json(PLUGIN / ".codex-plugin" / "plugin.json")
    claude = read_json(PLUGIN / ".claude-plugin" / "plugin.json")

    for manifest in (codex, claude):
        assert manifest["name"] == "test-framework"
        assert manifest["version"] == "0.1.8"
        assert "测试框架" in manifest["description"]
        assert manifest["skills"] == "./skills"


def test_test_framework_plugin_has_single_skill_entrypoint() -> None:
    skill = PLUGIN / "skills" / "test-framework" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "name: test-framework" in text
    assert "test_framework.py init" in text


def test_test_framework_registered_in_marketplaces_and_projection() -> None:
    claude_marketplace = read_json(REPO_ROOT / ".claude-plugin" / "marketplace.json")
    codex_marketplace = read_json(REPO_ROOT / ".agents" / "plugins" / "marketplace.json")
    projection_text = (REPO_ROOT / ".release-flow" / "projection.yaml").read_text(encoding="utf-8")

    assert any(plugin["name"] == "test-framework" for plugin in claude_marketplace["plugins"])
    assert any(plugin["name"] == "test-framework" for plugin in codex_marketplace["plugins"])
    assert "      - test-framework" in projection_text
```

- [x] **Step 2: Run package tests and see them fail**

Run: `python -m pytest tests/test_test_framework_plugin.py -q`

Expected: FAIL because the plugin package does not exist.

- [x] **Step 3: Add plugin manifests and skill**

Create both manifests with:

```json
{
  "name": "test-framework",
  "version": "0.1.8",
  "description": "Test Framework Plugin（测试框架插件）",
  "skills": "./skills"
}
```

Create `plugins/test-framework/skills/test-framework/SKILL.md`:

```markdown
---
name: test-framework
description: "初始化轻量测试框架：标准产物结构、快速缓存验证、统一配置和统一命令入口。Use when 需要给仓库启用 build/verify/verify --full 测试框架。"
---

# Test Framework

## 边界

只初始化测试框架产物，不安装依赖、不写用户级配置、不配置 CI（持续集成）、不内置仓库业务逻辑。

## 命令

```bash
python scripts/test_framework.py init --project .
```

初始化目标仓库的 `.test-framework/config.json`、`.test-framework/.gitignore` 和 `.test-framework/cache/`；不复制 runner（运行器）到目标仓库。
```

- [x] **Step 4: Register plugin metadata**

Add `test-framework` to `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`, and `.release-flow/projection.yaml` using the same shape as existing plugin entries.

- [x] **Step 5: Run package tests**

Run: `python -m pytest tests/test_test_framework_plugin.py -q`

Expected: PASS for package tests that do not need init yet.

### Task 2: Implement Init Script and Complete Runner Template

**Files:**
- Create: `plugins/test-framework/skills/test-framework/scripts/test_framework.py`
- Create: `plugins/test-framework/skills/test-framework/scripts/test_framework_runner.py`
- Create: `plugins/test-framework/skills/test-framework/assets/templates/test-framework/config.json`
- Create: `plugins/test-framework/skills/test-framework/assets/templates/test-framework/gitignore`
- Modify: `tests/test_test_framework_plugin.py`

- [x] **Step 1: Add init and conflict tests**

Append to `tests/test_test_framework_plugin.py`:

```python
def run_init(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "init", "--project", str(project)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_init_creates_standard_artifacts(tmp_path: Path) -> None:
    result = run_init(tmp_path)

    assert result.returncode == 0
    assert (tmp_path / ".test-framework" / "config.json").is_file()
    assert (tmp_path / ".test-framework" / ".gitignore").read_text(encoding="utf-8") == "/cache/\n/runs/\n"
    assert (tmp_path / ".test-framework" / "cache").is_dir()
    assert not (tmp_path / "scripts" / "check.py").exists()


def test_init_refuses_existing_config_conflict(tmp_path: Path) -> None:
    config = tmp_path / ".test-framework" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text("{}\n", encoding="utf-8")

    result = run_init(tmp_path)

    assert result.returncode == 1
    assert "existing_file" in result.stderr
    assert ".test-framework/config.json" in result.stderr.replace("\\", "/")


def test_init_conflict_does_not_leave_partial_files(tmp_path: Path) -> None:
    config = tmp_path / ".test-framework" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text("{}\n", encoding="utf-8")

    result = run_init(tmp_path)

    assert result.returncode == 1
    assert "existing_file" in result.stderr
    assert not (tmp_path / ".test-framework" / "cache").exists()
```

- [x] **Step 2: Add E2E test for initialized target repository**

Append:

```python
def test_initialized_repository_runs_build_verify_full_and_cache(tmp_path: Path) -> None:
    result = run_init(tmp_path)
    assert result.returncode == 0

    config = {
        "version": 1,
        "build": {
            "checks": [
                {
                    "id": "build.echo",
                    "command": f"{sys.executable} -c \"print('build ok')\""
                }
            ]
        },
        "verify": {
            "checks": [
                {
                    "id": "verify.sample",
                    "paths": ["src/**"],
                    "command": f"{sys.executable} -c \"from pathlib import Path; p=Path('verify-count.txt'); n=int(p.read_text()) if p.exists() else 0; p.write_text(str(n+1)); print('verify ok')\"",
                    "inputs": ["src"]
                }
            ]
        }
    }
    (tmp_path / ".test-framework" / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "sample.txt").write_text("changed\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, text=True, capture_output=True, check=False)

    build = subprocess.run([sys.executable, str(SCRIPT), "build", "--project", str(tmp_path)], cwd=tmp_path, text=True, capture_output=True, check=False)
    fast = subprocess.run([sys.executable, str(SCRIPT), "verify", "--project", str(tmp_path)], cwd=tmp_path, text=True, capture_output=True, check=False)
    cached = subprocess.run([sys.executable, str(SCRIPT), "verify", "--project", str(tmp_path)], cwd=tmp_path, text=True, capture_output=True, check=False)
    full = subprocess.run([sys.executable, str(SCRIPT), "verify", "--project", str(tmp_path), "--full"], cwd=tmp_path, text=True, capture_output=True, check=False)

    assert build.returncode == 0
    assert fast.returncode == 0
    assert "full-not-run: true" in fast.stdout
    assert cached.returncode == 0
    assert "cache-hit: true" in cached.stdout
    assert full.returncode == 0
    assert "full-not-run: false" in full.stdout
    assert (tmp_path / "verify-count.txt").read_text(encoding="utf-8") == "2"


def test_initialized_repository_does_not_cache_failed_results_or_run_full_on_miss(tmp_path: Path) -> None:
    result = run_init(tmp_path)
    assert result.returncode == 0
    config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {
            "checks": [
                {
                    "id": "verify.fail-once",
                    "paths": ["src/**"],
                    "command": f"{sys.executable} -c \"from pathlib import Path; p=Path('attempt.txt'); n=int(p.read_text()) if p.exists() else 0; p.write_text(str(n+1)); raise SystemExit(1 if n == 0 else 0)\"",
                    "inputs": ["src"]
                },
                {
                    "id": "verify.full-only",
                    "paths": ["other/**"],
                    "command": f"{sys.executable} -c \"from pathlib import Path; Path('full-ran.txt').write_text('yes')\"",
                    "inputs": ["other"]
                }
            ]
        }
    }
    (tmp_path / ".test-framework" / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "sample.txt").write_text("changed\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, text=True, capture_output=True, check=False)

    first = subprocess.run([sys.executable, str(SCRIPT), "verify", "--project", str(tmp_path)], cwd=tmp_path, text=True, capture_output=True, check=False)
    second = subprocess.run([sys.executable, str(SCRIPT), "verify", "--project", str(tmp_path)], cwd=tmp_path, text=True, capture_output=True, check=False)

    assert first.returncode == 1
    assert second.returncode == 0
    assert (tmp_path / "attempt.txt").read_text(encoding="utf-8") == "2"
    assert not (tmp_path / "full-ran.txt").exists()


def test_initialized_repository_no_check_does_not_run_full(tmp_path: Path) -> None:
    result = run_init(tmp_path)
    assert result.returncode == 0
    config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {
            "checks": [
                {
                    "id": "verify.sample",
                    "paths": ["src/**"],
                    "command": f"{sys.executable} -c \"from pathlib import Path; Path('verify-ran.txt').write_text('yes')\"",
                    "inputs": ["src"]
                }
            ]
        }
    }
    (tmp_path / ".test-framework" / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, text=True, capture_output=True, check=False)
    (tmp_path / "README.md").write_text("docs only\n", encoding="utf-8")

    fast = subprocess.run([sys.executable, str(SCRIPT), "verify", "--project", str(tmp_path)], cwd=tmp_path, text=True, capture_output=True, check=False)

    assert fast.returncode == 0
    assert "checked:" in fast.stdout
    assert "full-not-run: true" in fast.stdout
    assert not (tmp_path / "verify-ran.txt").exists()


def test_initialized_repository_default_verify_collects_all_worktree_change_kinds(tmp_path: Path) -> None:
    result = run_init(tmp_path)
    assert result.returncode == 0
    config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {
            "checks": [
                {
                    "id": "verify.sample",
                    "paths": ["src/**"],
                    "command": f"{sys.executable} -c \"from pathlib import Path; p=Path('count.txt'); n=int(p.read_text()) if p.exists() else 0; p.write_text(str(n+1))\"",
                    "inputs": ["src"]
                }
            ]
        }
    }
    (tmp_path / ".test-framework" / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, text=True, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, text=True, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, text=True, capture_output=True, check=False)
    (tmp_path / "src").mkdir()
    tracked = tmp_path / "src" / "tracked.txt"
    tracked.write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/tracked.txt"], cwd=tmp_path, text=True, capture_output=True, check=False)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, text=True, capture_output=True, check=False)

    tracked.write_text("unstaged\n", encoding="utf-8")
    unstaged = subprocess.run([sys.executable, str(SCRIPT), "verify", "--project", str(tmp_path)], cwd=tmp_path, text=True, capture_output=True, check=False)
    assert unstaged.returncode == 0

    tracked.write_text("staged\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/tracked.txt"], cwd=tmp_path, text=True, capture_output=True, check=False)
    staged = subprocess.run([sys.executable, str(SCRIPT), "verify", "--project", str(tmp_path)], cwd=tmp_path, text=True, capture_output=True, check=False)
    assert staged.returncode == 0

    (tmp_path / "src" / "new.txt").write_text("untracked\n", encoding="utf-8")
    untracked = subprocess.run([sys.executable, str(SCRIPT), "verify", "--project", str(tmp_path)], cwd=tmp_path, text=True, capture_output=True, check=False)
    assert untracked.returncode == 0

    assert int((tmp_path / "count.txt").read_text(encoding="utf-8")) >= 3
```

- [x] **Step 3: Run init tests and see them fail**

Run: `python -m pytest tests/test_test_framework_plugin.py -q`

Expected: FAIL because init script and templates are not implemented.

- [x] **Step 4: Implement init script**

Create `plugins/test-framework/skills/test-framework/scripts/test_framework.py`:

```python
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"


def planned_copies(root: Path) -> tuple[tuple[Path, Path], ...]:
    return (
        (TEMPLATE_ROOT / "test-framework" / "config.json", root / ".test-framework" / "config.json"),
        (TEMPLATE_ROOT / "test-framework" / "gitignore", root / ".test-framework" / ".gitignore"),
    )


def preflight(copies: tuple[tuple[Path, Path], ...], root: Path) -> int:
    for _source, target in copies:
        if target.exists():
            print(f"existing_file: {target.relative_to(root).as_posix()}", file=sys.stderr)
            return 1
    return 0


def copy_template(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def run_init(project: Path) -> int:
    root = project.expanduser().resolve()
    copies = planned_copies(root)
    result = preflight(copies, root)
    if result != 0:
        return result
    for source, target in copies:
        copy_template(source, target)
    (root / ".test-framework" / "cache").mkdir(parents=True, exist_ok=True)
    print("status: initialized")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize Test Framework（测试框架） artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init")
    init.add_argument("--project", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        return run_init(args.project)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 5: Add minimal config and gitignore templates**

Create `assets/templates/test-framework/config.json`:

```json
{
  "version": 1,
  "build": {
    "checks": []
  },
  "verify": {
    "checks": []
  }
}
```

Create `assets/templates/test-framework/gitignore`:

```gitignore
/cache/
/runs/
```

- [x] **Step 6: Add complete plugin runner implementation**

Create `plugins/test-framework/skills/test-framework/scripts/test_framework_runner.py` as the canonical runner（运行器）. It must implement:

- JSON（数据格式） config loading from `.test-framework/config.json`.
- `build` running all `build.checks`.
- `verify` selecting `verify.checks` by changed files and using passed-result cache（通过结果缓存）.
- `verify --full` running all `verify.checks`.
- cache directory `.test-framework/cache/`.
- input directory hashing（目录哈希） excluding `.test-framework/cache/`, `.git/`, and `__pycache__/`.
- no-check output with `full-not-run: true`.

The implementation should expose stable helper names for tests and future maintenance: `_load_config`, `_changed_files`, `_selected_checks`, `_cache_key`, `_cache_load`, `_cache_store`, `_run_check`, `run_build`, and `run_verify`.

Default `_changed_files` behavior must use worktree（工作区） changes: `git diff --name-only --cached` for staged tracked changes（已暂存已跟踪变更）, `git diff --name-only` for unstaged tracked changes（未暂存已跟踪变更）, and `git ls-files --others --exclude-standard` for untracked non-ignored files（未跟踪且未忽略文件）. The only supported verify flag in A is `--full`.

- [x] **Step 7: Run init and E2E tests**

Tests must cover both path models: project-level（项目级） invocation through the repository plugin script and user-level（用户级） invocation through a copied Skill（技能） directory outside the target project.

Run: `python -m pytest tests/test_test_framework_plugin.py -q`

Expected: PASS.

### Task 3: Connect This Repository to the Framework

**Files:**
- Modify: `plugins/test-framework/skills/test-framework/scripts/test_framework.py`
- Create: `plugins/test-framework/skills/test-framework/scripts/test_framework_runner.py`
- Create: `.test-framework/config.json`
- Create: `.test-framework/.gitignore`
- Keep/modify: `scripts/local_plugin_build.py`
- Delete: target-repository generic runner script
- Modify: `tests/test_local_plugin_build_checks.py`

- [x] **Step 1: Write local runner tests**

Update `tests/test_local_plugin_build_checks.py` so build and verify tests use JSON（数据格式） config and assert:

- `run_build(root, runner=fake_run)` executes configured `build.checks`.
- default `run_verify(root, runner=fake_run)` selects only checks matching changed files.
- `run_verify(root, runner=fake_run, full=True)` runs all configured checks.
- passed（已通过） cache hit skips the runner.
- failed（失败） results are not cached.
- no selected checks return success and print `full-not-run: true`.

Move existing package-shape tests to import `scripts/local_plugin_build.py` for the repository-specific checks. Keep test-framework runner（测试框架运行器） tests focused on the plugin-owned generic runner contract.

- [x] **Step 2: Run local tests and see failures**

Run: `python -m pytest tests/test_local_plugin_build_checks.py -q`

Expected: FAIL until the plugin runner follows the framework contract.

- [x] **Step 3: Connect repository to plugin runner**

Modify the plugin command entrypoint and repository command wiring to use the plugin-owned framework runner:

- Make `build` execute `.test-framework/config.json` `build.checks`.
- Make `verify` execute the default cached mode.
- Make `verify --full` execute all configured verify checks.

Keep `scripts/local_plugin_build.py` as this repository's package-shape check command. It should expose `main()` for subprocess execution, return `0` when package-shape checks pass, and print the same error strings when they fail. This helper is a configured check command, not a human-facing framework entrypoint and not a plugin-owned artifact.

- [x] **Step 4: Add this repository config**

Create `.test-framework/config.json`:

```json
{
  "version": 1,
  "build": {
    "checks": [
      {
        "id": "build.local-plugin-package",
        "command": "python scripts/local_plugin_build.py",
        "inputs": [
          ".claude-plugin/marketplace.json",
          ".agents/plugins/marketplace.json",
          ".release-flow/projection.yaml",
          "plugins",
          "scripts/local_plugin_build.py"
        ]
      }
    ]
  },
  "verify": {
    "checks": [
      {
        "id": "pytest.full",
        "paths": [
          ".agents/**",
          ".claude-plugin/**",
          ".comet.yaml",
          ".release-flow/**",
          "pyproject.toml",
          "scripts/local_plugin_build.py",
          ".test-framework/**",
          ".github/**",
          "plugins/**",
          "tests/**",
          "openspec/**",
          "docs/superpowers/**"
        ],
        "command": "python -m pytest",
        "inputs": [
          ".agents",
          ".claude-plugin",
          ".comet.yaml",
          ".release-flow",
          "pyproject.toml",
          "scripts/local_plugin_build.py",
          ".test-framework/config.json",
          ".github",
          "plugins",
          "openspec",
          "docs/superpowers",
          "tests"
        ]
      }
    ]
  }
}
```

This config intentionally has one canonical full pytest（Python 测试框架） check. Its `paths` cover repository areas that can affect the full pytest（Python 测试框架） suite, so default `verify` applies changed-files（变更文件） selection and cache（缓存） to the same canonical check that `verify --full` runs unconditionally.

Create `.test-framework/.gitignore`:

```gitignore
/cache/
/runs/
```

- [x] **Step 5: Run local runner tests**

Run: `python -m pytest tests/test_local_plugin_build_checks.py tests/test_test_framework_plugin.py -q`

Expected: PASS.

### Task 4: Scope Guard and Validation

**Files:**
- Modify: `openspec/changes/split-fast-full-verification/tasks.md`

- [x] **Step 1: Confirm no out-of-scope files are changed**

Run:

```bash
git status --short
```

Expected: no changes to `.pr-flow/config.yaml`, `plugins/pr-flow/**`, Release Flow（发布流程） behavior, or CI（持续集成） workflow files for this A change.

- [x] **Step 2: Run focused tests**

Run:

```bash
python -m pytest tests/test_test_framework_plugin.py tests/test_local_plugin_build_checks.py -q
```

Expected: PASS.

- [x] **Step 3: Run initialized repository commands**

Run:

```bash
python plugins/test-framework/skills/test-framework/scripts/test_framework.py build --project .
python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project .
python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full
```

Expected: all PASS. Default `verify` prints `full-not-run: true`; `verify --full` prints `full-not-run: false`.

- [x] **Step 4: Validate OpenSpec（开放规格）**

Run:

```bash
openspec validate split-fast-full-verification --strict
```

Expected: PASS.

- [x] **Step 5: Mark tasks complete after evidence exists**

Only after the commands above pass, check the corresponding boxes in `openspec/changes/split-fast-full-verification/tasks.md`.

## Self-Review

- Spec coverage: tasks cover standard artifacts, fast cache verification, unified config and entrypoint, and dual Claude/Codex surfaces.
- Scope guard: PR Flow（拉取请求流程）, Release Flow（发布流程） behavior, CI（持续集成）, and full-suite runtime optimization are out of scope.
- Dependency guard: initialized repositories use JSON（数据格式） and Python（运行器） standard library only.
- Cache guard: cache lives under `.test-framework/cache/`, which `.test-framework/.gitignore` can actually ignore.
- Verification guard: includes E2E（端到端） init test and root command validation.

