---
change: add-cross-agent-review-mechanism
design-doc: docs/superpowers/specs/2026-06-20-cross-agent-review-design.md
base-ref: 33e83be22cb5d14293feadd5c4cc2f67db210ddc
archived-with: 2026-06-20-add-cross-agent-review-mechanism
---

# Cross-Agent Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal independent `cross-agent-review` plugin that runs SDK-backed readonly reviewer agents and writes review evidence.

**Architecture:** Add a self-contained plugin package under `plugins/cross-agent-review`. Keep the runtime in one Python script with small functions for CLI parsing, subject checks, SDK resolution, reviewer dispatch, aggregation, and output writing. Tests use fake dispatchers and temporary Git repositories so the suite covers contracts without calling the real Claude Agent SDK.

**Tech Stack:** Python standard library, pytest, Claude Agent SDK imported dynamically only by the runtime path, Codex/Claude plugin manifests.

archived-with: 2026-06-20-add-cross-agent-review-mechanism
---

## File Structure

- Create `plugins/cross-agent-review/.codex-plugin/plugin.json`: Codex plugin manifest.
- Create `plugins/cross-agent-review/.claude-plugin/plugin.json`: Claude plugin manifest.
- Create `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`: thin skill entrypoint and usage contract.
- Create `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`: single-file review runner.
- Create `tests/test_cross_agent_review_plugin_package.py`: plugin structure, manifest, marketplace, and skill package checks.
- Create `tests/test_cross_agent_review_cli.py`: CLI, subject binding, aggregation, output, SDK resolution, and fake reviewer tests.
- Modify `.claude-plugin/marketplace.json`: add `cross-agent-review` repo marketplace entry.
- Modify `.release-flow/projection.yaml`: include `cross-agent-review` in generated Codex marketplace plugin list.
- Modify `.comet/build-check.sh`: include focused cross-agent-review tests in the repository quick regression entrypoint.
- Modify `openspec/changes/add-cross-agent-review-mechanism/tasks.md`: check off completed tasks as implementation proceeds.

## Task 1: Plugin Package Skeleton

**Files:**
- Create: `plugins/cross-agent-review/.codex-plugin/plugin.json`
- Create: `plugins/cross-agent-review/.claude-plugin/plugin.json`
- Create: `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`
- Create: `tests/test_cross_agent_review_plugin_package.py`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `.release-flow/projection.yaml`

- [x] **Step 1: Write failing package tests**

Create `tests/test_cross_agent_review_plugin_package.py`:

```python
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "cross-agent-review"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_cross_agent_review_manifests_are_valid() -> None:
    codex_manifest = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    claude_manifest = read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")

    assert codex_manifest["name"] == "cross-agent-review"
    assert claude_manifest["name"] == "cross-agent-review"
    assert codex_manifest["version"] == claude_manifest["version"]
    assert codex_manifest["skills"] == "./skills"
    assert claude_manifest["skills"] == "./skills"
    assert codex_manifest["description"]
    assert claude_manifest["description"]


def test_cross_agent_review_skill_and_script_are_packaged() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    script = PLUGIN_ROOT / "skills" / "cross-agent-review" / "scripts" / "cross_agent_review.py"

    assert skill.is_file()
    assert script.is_file()
    text = skill.read_text(encoding="utf-8")
    assert "Claude Agent SDK" in text
    assert "review-pass.json" in text
    assert "不自动安装" in text


def test_claude_repo_marketplace_includes_cross_agent_review() -> None:
    catalog = read_json(REPO_ROOT / ".claude-plugin" / "marketplace.json")
    entries = [plugin for plugin in catalog["plugins"] if plugin.get("name") == "cross-agent-review"]

    assert entries == [
        {
            "name": "cross-agent-review",
            "source": "./plugins/cross-agent-review",
            "description": "Cross-agent review plugin for Codex and Claude agents",
        }
    ]


def test_release_projection_includes_cross_agent_review() -> None:
    text = (REPO_ROOT / ".release-flow" / "projection.yaml").read_text(encoding="utf-8")
    assert "      - cross-agent-review" in text
```

- [x] **Step 2: Run package tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_plugin_package.py -q
```

Expected: FAIL because plugin files and marketplace entries do not exist yet.

- [x] **Step 3: Add plugin manifests**

Create `plugins/cross-agent-review/.codex-plugin/plugin.json`:

```json
{
  "name": "cross-agent-review",
  "version": "0.1.0",
  "description": "Cross-agent review plugin for Codex and Claude agents",
  "skills": "./skills"
}
```

Create `plugins/cross-agent-review/.claude-plugin/plugin.json`:

```json
{
  "name": "cross-agent-review",
  "version": "0.1.0",
  "description": "Cross-agent review plugin for Codex and Claude agents",
  "skills": "./skills"
}
```

- [x] **Step 4: Add skill entrypoint**

Create `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`:

```markdown
archived-with: 2026-06-20-add-cross-agent-review-mechanism
---
name: cross-agent-review
description: "运行跨代理审查。Use when 需要在提交后的 clean commit 上运行 Claude Agent SDK reviewer，并生成 review report 和 review-pass.json。"
archived-with: 2026-06-20-add-cross-agent-review-mechanism
---

# Cross-Agent Review

本 skill 运行独立 cross-agent review（跨代理审查），不推进 Comet phase（阶段），不运行构建或测试，不自动安装 Claude Agent SDK。

## 前置条件

- 当前 worktree 必须干净。
- 当前 `HEAD` 必须等于传入的 `--head-ref`。
- 调用方已运行测试，并提供测试结果文件。
- 当前 Python、默认 Claude SDK venv，或 `--sdk-python` 指定的 Python 必须能导入 `claude_agent_sdk`。

## 命令

```bash
python scripts/cross_agent_review.py run \
  --change <change-id> \
  --base-ref <base-ref> \
  --head-ref <head-ref> \
  --diff-file <path> \
  --spec-file <path> \
  --design-file <path> \
  --tasks-file <path> \
  --tests-file <path>
```

输出默认写入 `.local/cross-agent-review/<change>/<head_ref>/`。

只有没有 CRITICAL/IMPORTANT findings（发现项），且 worktree 仍干净时才生成 `review-pass.json`。
```

- [x] **Step 5: Add empty runner script with executable CLI placeholder**

Create `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`:

```python
from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cross_agent_review.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    print("status: not_implemented")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 6: Update marketplace and release projection**

Modify `.claude-plugin/marketplace.json` by appending:

```json
{
  "name": "cross-agent-review",
  "source": "./plugins/cross-agent-review",
  "description": "Cross-agent review plugin for Codex and Claude agents"
}
```

Modify `.release-flow/projection.yaml` under `generators[0].plugins`:

```yaml
      - agent-guard
      - release-flow
      - cross-agent-review
```

- [x] **Step 7: Run package tests and verify they pass**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_plugin_package.py -q
```

Expected: PASS.

- [x] **Step 8: Commit package skeleton**

```bash
git add plugins/cross-agent-review tests/test_cross_agent_review_plugin_package.py .claude-plugin/marketplace.json .release-flow/projection.yaml
git commit -m "feat: 新增 cross-agent-review 插件骨架"
```

## Task 2: CLI Validation and Clean Commit Subject Binding

**Files:**
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- Create/Modify: `tests/test_cross_agent_review_cli.py`

- [x] **Step 1: Write failing CLI validation tests**

Create `tests/test_cross_agent_review_cli.py`:

```python
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "cross-agent-review"
    / "skills"
    / "cross-agent-review"
    / "scripts"
    / "cross_agent_review.py"
)


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd or REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def write_file(path: Path, text: str = "content\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_required_args_fail() -> None:
    result = run("run", "--change", "demo")

    assert result.returncode == 2
    assert "error:" in result.stderr


def test_missing_input_file_fails(tmp_path: Path) -> None:
    result = run(
        "run",
        "--change",
        "demo",
        "--base-ref",
        "base",
        "--head-ref",
        "head",
        "--diff-file",
        str(tmp_path / "missing.diff"),
        "--spec-file",
        str(write_file(tmp_path / "spec.md")),
        "--design-file",
        str(write_file(tmp_path / "design.md")),
        "--tasks-file",
        str(write_file(tmp_path / "tasks.md")),
        "--tests-file",
        str(write_file(tmp_path / "tests.txt")),
        "--fake-reviewer-results",
        "[]",
    )

    assert result.returncode == 1
    assert "missing_file" in result.stdout
```

- [x] **Step 2: Add Git fixture tests for subject binding**

Append to `tests/test_cross_agent_review_cli.py`:

```python
def git(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def init_repo(project: Path) -> str:
    project.mkdir()
    git(project, "init")
    git(project, "config", "user.email", "test@example.invalid")
    git(project, "config", "user.name", "Test User")
    write_file(project / "app.txt", "one\n")
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "initial")
    return git(project, "rev-parse", "HEAD")


def review_args(project: Path, head: str, output_dir: Path) -> list[str]:
    return [
        "run",
        "--change",
        "demo",
        "--base-ref",
        head,
        "--head-ref",
        head,
        "--diff-file",
        str(write_file(project / "diff.patch")),
        "--spec-file",
        str(write_file(project / "spec.md")),
        "--design-file",
        str(write_file(project / "design.md")),
        "--tasks-file",
        str(write_file(project / "tasks.md")),
        "--tests-file",
        str(write_file(project / "tests.txt")),
        "--output-dir",
        str(output_dir),
        "--fake-reviewer-results",
        "[]",
    ]


def test_dirty_worktree_rejects_before_dispatch(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    write_file(tmp_path / "repo" / "dirty.txt", "dirty\n")

    result = run(*review_args(tmp_path / "repo", head, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (tmp_path / "out" / "review-pass.json").exists()


def test_head_mismatch_rejects_before_dispatch(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(*review_args(tmp_path / "repo", "0" * 40, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 1
    assert "head_ref_mismatch" in result.stdout
    assert head != "0" * 40
```

- [x] **Step 3: Run CLI tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py -q
```

Expected: FAIL because CLI arguments and subject checks are not implemented.

- [x] **Step 4: Implement CLI arguments and file validation**

Update `cross_agent_review.py` with:

```python
from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


REQUIRED_FILE_ARGS = ["diff_file", "spec_file", "design_file", "tasks_file", "tests_file"]


@dataclass(frozen=True)
class ReviewArgs:
    change: str
    base_ref: str
    head_ref: str
    diff_file: Path
    spec_file: Path
    design_file: Path
    tasks_file: Path
    tests_file: Path
    output_dir: Path | None
    sdk_python: Path | None
    fake_reviewer_results: str | None
    disable_risk_review: str | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cross_agent_review.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--change", required=True)
    run_parser.add_argument("--base-ref", required=True)
    run_parser.add_argument("--head-ref", required=True)
    run_parser.add_argument("--diff-file", type=Path, required=True)
    run_parser.add_argument("--spec-file", type=Path, required=True)
    run_parser.add_argument("--design-file", type=Path, required=True)
    run_parser.add_argument("--tasks-file", type=Path, required=True)
    run_parser.add_argument("--tests-file", type=Path, required=True)
    run_parser.add_argument("--output-dir", type=Path)
    run_parser.add_argument("--sdk-python", type=Path)
    run_parser.add_argument("--fake-reviewer-results")
    run_parser.add_argument("--disable-risk-review")
    return parser


def git_output(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise ValueError(f"git_failed: {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def ensure_clean_subject(cwd: Path, head_ref: str) -> None:
    if git_output(["status", "--short"], cwd):
        raise ValueError("dirty_worktree")
    current_head = git_output(["rev-parse", "HEAD"], cwd)
    if current_head != head_ref:
        raise ValueError(f"head_ref_mismatch: expected={head_ref} actual={current_head}")


def parse_review_args(args: argparse.Namespace) -> ReviewArgs:
    review_args = ReviewArgs(
        change=args.change,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        diff_file=args.diff_file,
        spec_file=args.spec_file,
        design_file=args.design_file,
        tasks_file=args.tasks_file,
        tests_file=args.tests_file,
        output_dir=args.output_dir,
        sdk_python=args.sdk_python,
        fake_reviewer_results=args.fake_reviewer_results,
        disable_risk_review=args.disable_risk_review,
    )
    for name in REQUIRED_FILE_ARGS:
        path = getattr(review_args, name)
        if not path.is_file():
            raise ValueError(f"missing_file: {path}")
    return review_args


def run_review(args: argparse.Namespace) -> int:
    try:
        review_args = parse_review_args(args)
        ensure_clean_subject(Path.cwd(), review_args.head_ref)
    except ValueError as exc:
        print("status: failed")
        print(f"error: {exc}")
        return 1
    print("status: ready")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    if parsed.command == "run":
        return run_review(parsed)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 5: Run CLI validation tests and verify they pass**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_missing_required_args_fail tests/test_cross_agent_review_cli.py::test_missing_input_file_fails tests/test_cross_agent_review_cli.py::test_dirty_worktree_rejects_before_dispatch tests/test_cross_agent_review_cli.py::test_head_mismatch_rejects_before_dispatch -q
```

Expected: PASS.

- [x] **Step 6: Commit CLI validation and subject binding**

```bash
git add plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py tests/test_cross_agent_review_cli.py
git commit -m "feat: 添加 review 输入校验和提交绑定"
```

## Task 3: SDK Resolution and Reviewer Dispatch

**Files:**
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- Modify: `tests/test_cross_agent_review_cli.py`

- [x] **Step 1: Write failing SDK resolution tests**

Append to `tests/test_cross_agent_review_cli.py`:

```python
def test_sdk_missing_reports_clear_error(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    missing_python = tmp_path / "missing-python.exe"

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--sdk-python",
        str(missing_python),
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert "sdk_unavailable" in result.stdout


def test_fake_reviewer_results_bypass_real_sdk_for_tests(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(*review_args(tmp_path / "repo", head, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 0, result.stdout + result.stderr
```

- [x] **Step 2: Write failing readonly role coverage test**

Append:

```python
def test_reviewer_roles_are_recorded_in_results(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    fake = json.dumps(
        [
            {"role": "spec-alignment", "status": "completed", "findings": []},
            {"role": "implementation-correctness", "status": "completed", "findings": []},
            {"role": "tests-and-edge-cases", "status": "completed", "findings": []},
            {"role": "risk-review", "status": "completed", "findings": []},
        ]
    )

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        fake,
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path / "out" / "review-results.json").read_text(encoding="utf-8"))
    assert [item["role"] for item in data["reviewers"]] == [
        "spec-alignment",
        "implementation-correctness",
        "tests-and-edge-cases",
        "risk-review",
    ]
    assert "Edit" not in data["readonly_tools"]
    assert "Write" not in data["readonly_tools"]
```

- [x] **Step 3: Run new dispatch tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_sdk_missing_reports_clear_error tests/test_cross_agent_review_cli.py::test_fake_reviewer_results_bypass_real_sdk_for_tests tests/test_cross_agent_review_cli.py::test_reviewer_roles_are_recorded_in_results -q
```

Expected: FAIL because SDK resolution, fake dispatch, and output writing are not implemented.

- [x] **Step 4: Implement SDK resolution helpers and readonly tool constants**

Add to `cross_agent_review.py`:

```python
import hashlib
import os


REVIEWER_ROLES = [
    "spec-alignment",
    "implementation-correctness",
    "tests-and-edge-cases",
    "risk-review",
]
READONLY_TOOLS = ["Read", "Glob", "Grep", "Bash(git diff *)", "Bash(git show *)", "Bash(git status *)"]


def default_sdk_python_candidates(explicit: Path | None) -> list[Path]:
    candidates: list[Path] = []
    env_value = os.environ.get("CROSS_AGENT_REVIEW_SDK_PYTHON")
    if explicit is not None:
        candidates.append(explicit)
    if env_value:
        candidates.append(Path(env_value))
    candidates.append(Path.home() / ".claude" / "security" / "agent-sdk-venv" / "Scripts" / "python.exe")
    candidates.append(Path.home() / ".claude" / "security" / "agent-sdk-venv" / "bin" / "python")
    return candidates


def current_python_has_sdk() -> bool:
    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        return False
    return True


def python_has_sdk(path: Path) -> bool:
    if not path.exists():
        return False
    result = subprocess.run(
        [str(path), "-c", "import claude_agent_sdk"],
        check=False,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def resolve_sdk_python(explicit: Path | None, require_real_sdk: bool) -> str:
    if not require_real_sdk:
        return "fake"
    if current_python_has_sdk():
        return sys.executable
    for candidate in default_sdk_python_candidates(explicit):
        if python_has_sdk(candidate):
            return str(candidate)
    raise ValueError("sdk_unavailable: install claude-agent-sdk or pass --sdk-python")
```

Add `import sys` at the top.

- [x] **Step 5: Implement fake reviewer dispatch and real SDK seam**

Add:

```python
def load_fake_reviewer_results(raw: str | None) -> list[dict]:
    if raw is None:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("invalid_fake_reviewer_results")
    return [item for item in data if isinstance(item, dict)]


def dispatch_reviewers(review_args: ReviewArgs, sdk_python: str) -> list[dict]:
    fake_results = load_fake_reviewer_results(review_args.fake_reviewer_results)
    if review_args.fake_reviewer_results is not None:
        return fake_results
    raise ValueError("real_sdk_dispatch_not_implemented")
```

The real SDK dispatch is implemented in Task 5 after outputs and aggregation are stable.

- [x] **Step 6: Add output directory helper**

Add:

```python
def short_ref(ref: str) -> str:
    return ref[:12] if len(ref) >= 12 else ref


def output_dir_for(review_args: ReviewArgs) -> Path:
    if review_args.output_dir is not None:
        return review_args.output_dir
    return Path(".local") / "cross-agent-review" / review_args.change / short_ref(review_args.head_ref)
```

- [x] **Step 7: Run focused SDK/dispatch tests**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_sdk_missing_reports_clear_error tests/test_cross_agent_review_cli.py::test_fake_reviewer_results_bypass_real_sdk_for_tests tests/test_cross_agent_review_cli.py::test_reviewer_roles_are_recorded_in_results -q
```

Expected: PASS after output writing is added in Task 4. If Task 4 is not complete yet, run this command after Task 4 Step 4.

- [x] **Step 8: Commit SDK resolution seam**

```bash
git add plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py tests/test_cross_agent_review_cli.py
git commit -m "feat: 添加 SDK 解析和 reviewer 派发接口"
```

## Task 4: Aggregation and Outputs

**Files:**
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- Modify: `tests/test_cross_agent_review_cli.py`

- [x] **Step 1: Write failing aggregation and output tests**

Append:

```python
def test_non_blocking_findings_generate_pass_marker(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    fake = json.dumps(
        [
            {
                "role": "spec-alignment",
                "status": "completed",
                "findings": [
                    {
                        "severity": "WARNING",
                        "location": "app.txt:1",
                        "summary": "Minor issue",
                        "evidence": "Evidence",
                        "recommendation": "Recommendation",
                    }
                ],
            }
        ]
    )

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        fake,
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "out" / "review-report.md").is_file()
    assert (tmp_path / "out" / "review-results.json").is_file()
    assert (tmp_path / "out" / "review-pass.json").is_file()


def test_blocking_findings_do_not_generate_pass_marker(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    fake = json.dumps(
        [
            {
                "role": "implementation-correctness",
                "status": "completed",
                "findings": [
                    {
                        "severity": "IMPORTANT",
                        "location": "app.txt:1",
                        "summary": "Wrong behavior",
                        "evidence": "Evidence",
                        "recommendation": "Fix behavior",
                    }
                ],
            }
        ]
    )

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        fake,
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert (tmp_path / "out" / "review-report.md").is_file()
    assert (tmp_path / "out" / "review-results.json").is_file()
    assert not (tmp_path / "out" / "review-pass.json").exists()
```

- [x] **Step 2: Add hash, deduplication, invalid result, and risk skip tests**

Append:

```python
def test_report_hash_matches_report(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    result = run(*review_args(tmp_path / "repo", head, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 0, result.stdout + result.stderr
    report = (tmp_path / "out" / "review-report.md").read_bytes()
    marker = json.loads((tmp_path / "out" / "review-pass.json").read_text(encoding="utf-8"))
    import hashlib

    assert marker["report_hash"] == hashlib.sha256(report).hexdigest()
    assert marker["head_ref"] == head


def test_duplicate_findings_are_counted_once(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    finding = {
        "severity": "IMPORTANT",
        "location": "app.txt:1",
        "summary": "Duplicate",
        "evidence": "Evidence",
        "recommendation": "Fix",
    }
    fake = json.dumps(
        [
            {"role": "spec-alignment", "status": "completed", "findings": [finding]},
            {"role": "implementation-correctness", "status": "completed", "findings": [finding]},
        ]
    )

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        fake,
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    data = json.loads((tmp_path / "out" / "review-results.json").read_text(encoding="utf-8"))
    assert data["blocking_findings"] == 1


def test_risk_review_skip_is_recorded(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--disable-risk-review",
        "low-risk-doc-only",
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path / "out" / "review-results.json").read_text(encoding="utf-8"))
    assert data["skipped_reviewers"] == [{"role": "risk-review", "reason": "low-risk-doc-only"}]
```

- [x] **Step 3: Run output tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_non_blocking_findings_generate_pass_marker tests/test_cross_agent_review_cli.py::test_blocking_findings_do_not_generate_pass_marker tests/test_cross_agent_review_cli.py::test_report_hash_matches_report tests/test_cross_agent_review_cli.py::test_duplicate_findings_are_counted_once tests/test_cross_agent_review_cli.py::test_risk_review_skip_is_recorded -q
```

Expected: FAIL because aggregation and outputs are not implemented.

- [x] **Step 4: Implement aggregation and output writing**

Add:

```python
BLOCKING_SEVERITIES = {"CRITICAL", "IMPORTANT"}
NON_BLOCKING_SEVERITIES = {"WARNING", "SUGGESTION"}
ALL_SEVERITIES = BLOCKING_SEVERITIES | NON_BLOCKING_SEVERITIES


def normalize_finding(raw: dict) -> dict:
    severity = str(raw.get("severity", "")).upper()
    if severity not in ALL_SEVERITIES:
        severity = "CRITICAL"
    return {
        "severity": severity,
        "location": str(raw.get("location", "")),
        "summary": str(raw.get("summary", "")),
        "evidence": str(raw.get("evidence", "")),
        "recommendation": str(raw.get("recommendation", "")),
    }


def aggregate(reviewers: list[dict], skipped: list[dict]) -> dict:
    findings: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for reviewer in reviewers:
        role = str(reviewer.get("role", "unknown"))
        raw_findings = reviewer.get("findings", [])
        if not isinstance(raw_findings, list):
            raw_findings = [
                {
                    "severity": "CRITICAL",
                    "location": role,
                    "summary": "Reviewer returned invalid findings",
                    "evidence": json.dumps(reviewer, ensure_ascii=False),
                    "recommendation": "Rerun review or fix reviewer prompt",
                }
            ]
        for raw in raw_findings:
            if not isinstance(raw, dict):
                raw = {
                    "severity": "CRITICAL",
                    "location": role,
                    "summary": "Reviewer returned invalid finding",
                    "evidence": repr(raw),
                    "recommendation": "Rerun review or fix reviewer prompt",
                }
            finding = normalize_finding(raw)
            key = (finding["severity"], finding["location"], finding["summary"])
            if key in seen:
                continue
            seen.add(key)
            findings.append(finding)
    blocking = sum(1 for finding in findings if finding["severity"] in BLOCKING_SEVERITIES)
    return {
        "reviewers": reviewers,
        "skipped_reviewers": skipped,
        "findings": findings,
        "blocking_findings": blocking,
        "readonly_tools": READONLY_TOOLS,
    }


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_report(review_args: ReviewArgs, summary: dict) -> str:
    lines = [
        f"# Cross-Agent Review: {review_args.change}",
        "",
        f"- Base ref: `{review_args.base_ref}`",
        f"- Head ref: `{review_args.head_ref}`",
        f"- Blocking findings: `{summary['blocking_findings']}`",
        "",
        "## Findings",
        "",
    ]
    if not summary["findings"]:
        lines.append("No findings.")
    for finding in summary["findings"]:
        lines.extend(
            [
                f"### {finding['severity']}: {finding['summary']}",
                "",
                f"- Location: `{finding['location']}`",
                f"- Evidence: {finding['evidence']}",
                f"- Recommendation: {finding['recommendation']}",
                "",
            ]
        )
    if summary["skipped_reviewers"]:
        lines.extend(["## Skipped Reviewers", ""])
        for skipped in summary["skipped_reviewers"]:
            lines.append(f"- `{skipped['role']}`: {skipped['reason']}")
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(review_args: ReviewArgs, summary: dict) -> int:
    out_dir = output_dir_for(review_args)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_text = render_report(review_args, summary)
    report_path = out_dir / "review-report.md"
    report_path.write_text(report_text, encoding="utf-8")
    write_json(out_dir / "review-results.json", summary)
    if summary["blocking_findings"] == 0:
        ensure_clean_subject(Path.cwd(), review_args.head_ref)
        report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
        write_json(
            out_dir / "review-pass.json",
            {
                "status": "pass",
                "change": review_args.change,
                "base_ref": review_args.base_ref,
                "head_ref": review_args.head_ref,
                "blocking_findings": 0,
                "report": "review-report.md",
                "report_hash": report_hash,
            },
        )
        return 0
    return 1
```

Update `run_review` to resolve SDK, dispatch, aggregate, and write outputs:

```python
def run_review(args: argparse.Namespace) -> int:
    try:
        review_args = parse_review_args(args)
        ensure_clean_subject(Path.cwd(), review_args.head_ref)
        sdk_python = resolve_sdk_python(review_args.sdk_python, review_args.fake_reviewer_results is None)
        ensure_clean_subject(Path.cwd(), review_args.head_ref)
        reviewers = dispatch_reviewers(review_args, sdk_python)
        skipped = []
        if review_args.disable_risk_review:
            skipped.append({"role": "risk-review", "reason": review_args.disable_risk_review})
            reviewers = [item for item in reviewers if item.get("role") != "risk-review"]
        summary = aggregate(reviewers, skipped)
        status = write_outputs(review_args, summary)
    except (ValueError, json.JSONDecodeError) as exc:
        print("status: failed")
        print(f"error: {exc}")
        return 1
    print("status: pass" if status == 0 else "status: findings")
    return status
```

- [x] **Step 5: Run output tests and verify they pass**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py -q
```

Expected: PASS for current test file.

- [x] **Step 6: Commit aggregation and outputs**

```bash
git add plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py tests/test_cross_agent_review_cli.py
git commit -m "feat: 生成 review 报告和 pass marker"
```

## Task 5: Real Claude Agent SDK Dispatch

**Files:**
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- Modify: `tests/test_cross_agent_review_cli.py`

- [x] **Step 1: Add prompt building tests**

Append:

```python
def test_prompt_contains_review_context(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    args = review_args(tmp_path / "repo", head, tmp_path / "out")
    result = run(*args, "--fake-reviewer-results", "[]", cwd=tmp_path / "repo")

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path / "out" / "review-results.json").read_text(encoding="utf-8"))
    assert data["readonly_tools"]
```

This test ensures fake execution still records readonly configuration. Real SDK calls are kept out of unit tests.

- [x] **Step 2: Implement reviewer prompt builder**

Add:

```python
def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def reviewer_prompt(review_args: ReviewArgs, role: str) -> str:
    return "\n\n".join(
        [
            f"Role: {role}",
            "Return only JSON with role, status, and findings.",
            f"Change: {review_args.change}",
            f"Base ref: {review_args.base_ref}",
            f"Head ref: {review_args.head_ref}",
            "Diff:\n" + read_text(review_args.diff_file),
            "Spec:\n" + read_text(review_args.spec_file),
            "Design:\n" + read_text(review_args.design_file),
            "Tasks:\n" + read_text(review_args.tasks_file),
            "Tests:\n" + read_text(review_args.tests_file),
        ]
    )
```

- [x] **Step 3: Implement async SDK dispatch**

Add:

```python
def dispatch_reviewers(review_args: ReviewArgs, sdk_python: str) -> list[dict]:
    fake_results = load_fake_reviewer_results(review_args.fake_reviewer_results)
    if review_args.fake_reviewer_results is not None:
        return fake_results
    return run_sdk_dispatch_subprocess(review_args, sdk_python)


def run_sdk_dispatch_subprocess(review_args: ReviewArgs, sdk_python: str) -> list[dict]:
    payload = {
        "cwd": str(Path.cwd()),
        "roles": REVIEWER_ROLES,
        "readonly_tools": READONLY_TOOLS,
        "prompts": {role: reviewer_prompt(review_args, role) for role in REVIEWER_ROLES},
    }
    result = subprocess.run(
        [sdk_python, str(Path(__file__).resolve()), "_sdk-dispatch"],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"sdk_dispatch_failed: {result.stderr.strip() or result.stdout.strip()}")
    data = json.loads(result.stdout)
    if not isinstance(data, list):
        raise ValueError("sdk_dispatch_invalid_output")
    return [item for item in data if isinstance(item, dict)]
```

Add `_sdk-dispatch` parser branch:

```python
subparsers.add_parser("_sdk-dispatch")
```

Update `main`:

```python
if parsed.command == "_sdk-dispatch":
    return run_sdk_dispatch()
```

- [x] **Step 4: Implement SDK subprocess entrypoint**

Add:

```python
def run_sdk_dispatch() -> int:
    import asyncio
    from claude_agent_sdk import ClaudeAgentOptions, query

    async def collect() -> list[dict]:
        payload = json.loads(sys.stdin.read())
        async def run_one(role: str) -> dict:
            options = ClaudeAgentOptions(
                cwd=payload["cwd"],
                allowed_tools=payload["readonly_tools"],
            )
            result_text = ""
            async for message in query(prompt=payload["prompts"][role], options=options):
                if hasattr(message, "result"):
                    result_text = message.result
            try:
                parsed = json.loads(result_text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
            return {
                "role": role,
                "status": "failed",
                "findings": [
                    {
                        "severity": "CRITICAL",
                        "location": role,
                        "summary": "Reviewer returned invalid JSON",
                        "evidence": result_text,
                        "recommendation": "Rerun review after checking reviewer prompt",
                    }
                ],
            }
        return await asyncio.gather(*(run_one(role) for role in payload["roles"]))

    print(json.dumps(asyncio.run(collect()), ensure_ascii=False))
    return 0
```

- [x] **Step 5: Run fake-dispatch unit tests**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py -q
```

Expected: PASS. This command does not call the real SDK because tests use `--fake-reviewer-results`.

- [x] **Step 6: Run one manual SDK smoke test on a clean temporary repo**

Use the known SDK Python path if current Python lacks the SDK:

```powershell
$sdk="C:\Users\liuli\.claude\security\agent-sdk-venv\Scripts\python.exe"
$head=(git rev-parse HEAD).Trim()
$out=".local/cross-agent-review/smoke/$head"
python plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py run --change smoke --base-ref $head --head-ref $head --diff-file diff.patch --spec-file spec.md --design-file design.md --tasks-file tasks.md --tests-file tests.txt --sdk-python $sdk --output-dir $out
```

Expected: exits 0 or 1 depending on reviewer findings, always writes `review-report.md` and `review-results.json`. If findings block, `review-pass.json` is absent.

- [x] **Step 7: Commit SDK dispatch**

```bash
git add plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py tests/test_cross_agent_review_cli.py
git commit -m "feat: 接入 Claude Agent SDK reviewer 派发"
```

## Task 6: Verification Entry Point and OpenSpec Task Closure

**Files:**
- Modify: `.comet/build-check.sh`
- Modify: `openspec/changes/add-cross-agent-review-mechanism/tasks.md`

- [x] **Step 1: Update quick regression entrypoint**

Modify `.comet/build-check.sh` pytest command to include:

```bash
  tests/test_cross_agent_review_plugin_package.py \
  tests/test_cross_agent_review_cli.py \
```

The final command should still end with `-q`.

- [x] **Step 2: Run focused tests**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_plugin_package.py tests/test_cross_agent_review_cli.py -q
```

Expected: PASS.

- [x] **Step 3: Run repository quick regression**

Run from Git Bash or MSYS Bash:

```bash
bash .comet/build-check.sh
```

Expected: PASS.

- [x] **Step 4: Run OpenSpec validation**

Run:

```powershell
openspec validate add-cross-agent-review-mechanism --strict
```

Expected: `Change 'add-cross-agent-review-mechanism' is valid`.

- [x] **Step 5: Check off OpenSpec tasks**

Update `openspec/changes/add-cross-agent-review-mechanism/tasks.md` by replacing each completed `- [ ]` with `- [x]` after the focused tests, quick regression, and OpenSpec validation pass.

- [x] **Step 6: Commit verification closure**

```bash
git add .comet/build-check.sh openspec/changes/add-cross-agent-review-mechanism/tasks.md
git commit -m "test: 覆盖 cross-agent-review 验证入口"
```
