import argparse
import asyncio
import contextlib
import hashlib
import json
import io
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

import pytest

from tests.support.git_templates import copy_template


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
_SCRIPT_MODULE = None


def template_cache_key(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(REPO_ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


TEMPLATE_CACHE_KEY = template_cache_key(Path(__file__), SCRIPT)
TEMPLATE_ROOT = Path(tempfile.gettempdir()) / f"cross-agent-review-test-templates-{TEMPLATE_CACHE_KEY}"


def load_script_module():
    global _SCRIPT_MODULE
    if _SCRIPT_MODULE is not None:
        return _SCRIPT_MODULE
    spec = importlib.util.spec_from_file_location("cross_agent_review", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _SCRIPT_MODULE = module
    return module


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    module = load_script_module()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.chdir(cwd or REPO_ROOT), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            returncode = int(module.main(args))
        except SystemExit as error:
            returncode = error.code if isinstance(error.code, int) else 1
    return subprocess.CompletedProcess(
        [sys.executable, str(SCRIPT), *args],
        returncode,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def write_file(path: Path, text: str = "content\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def copy_template_overlay(source: Path, target: Path) -> Path:
    if not target.exists():
        return copy_template(source, target)
    for source_path in source.rglob("*"):
        relative = source_path.relative_to(source)
        if len(relative.parts) >= 2 and relative.parts[:2] == (".git", "hooks"):
            continue
        target_path = target / relative
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists() and len(relative.parts) >= 3 and relative.parts[:2] == (".git", "objects"):
            continue
        shutil.copy2(source_path, target_path)
    return target


def test_cross_agent_review_template_cache_key_includes_script_contents() -> None:
    assert TEMPLATE_CACHE_KEY == template_cache_key(Path(__file__), SCRIPT)


def test_missing_required_args_fail() -> None:
    result = run("run")

    assert result.returncode == 2
    assert "error:" in result.stderr


def git(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def ensure_repo_template(project: Path) -> None:
    template = TEMPLATE_ROOT / "basic-repo"
    ready = TEMPLATE_ROOT / "basic-repo.ready"
    if ready.exists():
        copy_template(template, project)
        return

    lock_dir = TEMPLATE_ROOT / "basic-repo.lock"
    deadline = time.monotonic() + 120
    while True:
        try:
            lock_dir.mkdir(parents=True)
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise TimeoutError(f"template_lock_timeout: {lock_dir}")
            time.sleep(0.05)

    try:
        if not ready.exists():
            if template.exists():
                shutil.rmtree(template)
            template.mkdir(parents=True, exist_ok=True)
            create_repo(template)
            ready.write_text("ok\n", encoding="utf-8")
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)

    copy_template(template, project)


def create_repo(project: Path) -> str:
    project.mkdir(exist_ok=True)
    git(project, "init")
    git(project, "config", "user.email", "test@example.invalid")
    git(project, "config", "user.name", "Test User")
    write_file(project / "app.txt", "one\n")
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "initial")
    return git(project, "rev-parse", "HEAD")


def init_repo(project: Path) -> str:
    ensure_repo_template(project)
    return git(project, "rev-parse", "HEAD")


def ensure_review_context_template(project: Path) -> None:
    template = TEMPLATE_ROOT / "review-context-repo"
    ready = TEMPLATE_ROOT / "review-context-repo.ready"
    if ready.exists():
        copy_template_overlay(template, project)
        return

    lock_dir = TEMPLATE_ROOT / "review-context-repo.lock"
    deadline = time.monotonic() + 120
    while True:
        try:
            lock_dir.mkdir(parents=True)
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise TimeoutError(f"template_lock_timeout: {lock_dir}")
            time.sleep(0.05)

    try:
        if not ready.exists():
            if template.exists():
                shutil.rmtree(template)
            ensure_repo_template(template)
            create_review_context_commit(template)
            ready.write_text("ok\n", encoding="utf-8")
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)

    copy_template_overlay(template, project)


def write_review_input(
    project: Path,
    base: str,
    head: str,
    *,
    mode: str = "convergence",
    change: str = "demo",
    payload_overrides: dict | None = None,
) -> Path:
    output_dir = project / ".local" / "cross-agent-review" / change / head[:12]
    prepared_dir = output_dir / "prepared-inputs"
    spec_file = write_file(project / "spec.md", "spec body\n")
    design_file = write_file(project / "design.md", "design body\n")
    plan_file = write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    payload = {
        "change": change,
        "mode": mode,
        "base_ref": base,
        "head_ref": head,
        "spec_file": str(spec_file.relative_to(project)),
        "design_file": str(design_file.relative_to(project)),
        "plan_file": str(plan_file.relative_to(project)),
    }
    if payload_overrides:
        payload.update(payload_overrides)
    input_file = prepared_dir / "review-input.json"
    write_file(input_file, json.dumps(payload, ensure_ascii=False) + "\n")
    return input_file


def test_review_input_classifies_context_summary_and_default_full(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    base = git(project, "rev-parse", "HEAD")
    write_file(project / "spec.md", "spec body\n")
    write_file(project / "design.md", "design body\n")
    write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    write_file(project / "src" / "app.py", "print('ok')\n")
    write_file(project / "docs" / "process.md", "generated plan\n")
    git(project, "add", ".")
    git(project, "commit", "-m", "review subject")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(
        project,
        base,
        head,
        payload_overrides={
            "summary_only": [
                {"path": "docs/process.md", "reason": "过程文档仅供按需核对"}
            ]
        },
    )

    module = load_script_module()
    with contextlib.chdir(project):
        review_input = module.load_review_input(
            argparse.Namespace(input_file=input_file, debug=False, sdk_python=None)
        )
        state = module.initial_review_state(review_input)

    by_path = {item["path"]: item for item in state["files"]}
    assert by_path["spec.md"]["classification"] == "authoritative_context"
    assert by_path["spec.md"]["reason"] is None
    assert by_path["src/app.py"]["classification"] == "full_review"
    assert by_path["docs/process.md"]["classification"] == "summary_only"
    assert by_path["docs/process.md"]["reason"] == "过程文档仅供按需核对"
    assert "spec.md" in state["roles"]["spec-alignment"]["scope"]["authoritative_context"]


def committed_review_subject(tmp_path: Path) -> tuple[Path, str, str, Path]:
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "spec.md", "spec body\n")
    write_file(project / "design.md", "design body\n")
    write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    write_file(project / "src" / "app.py", "print('ok')\n")
    git(project, "add", ".")
    git(project, "commit", "-m", "review subject")
    head = git(project, "rev-parse", "HEAD")
    return project, base, head, write_review_input(project, base, head)


def review_subject_with_full_and_summary_files(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "spec.md", "spec body\n")
    write_file(project / "design.md", "design body\n")
    write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    write_file(project / "src" / "app.py", "print('behavior')\n")
    write_file(project / "docs" / "process.md", "generated process body\n")
    git(project, "add", ".")
    git(project, "commit", "-m", "review subject")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(
        project,
        base,
        head,
        payload_overrides={
            "summary_only": [
                {"path": "docs/process.md", "reason": "过程文档仅供按需核对"}
            ]
        },
    )
    module = load_script_module()
    with contextlib.chdir(project):
        review_input = module.load_review_input(
            argparse.Namespace(input_file=input_file, debug=False, sdk_python=None)
        )
        module.atomic_write_json(
            review_input.output_dir / "review-state.json",
            module.initial_review_state(review_input),
        )
    return project, input_file


def committed_review_input(tmp_path: Path) -> tuple[Path, Path]:
    project, _, _, input_file = committed_review_subject(tmp_path)
    return project, input_file


def review_args_from_input(input_file: Path) -> list[str]:
    return ["run", "--input-file", str(input_file)]


def test_changed_file_entries_preserves_rename_and_copy_sources(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "spec.md", "spec body\n")
    write_file(project / "design.md", "design body\n")
    write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    git(project, "mv", "app.txt", "renamed.txt")
    shutil.copyfile(project / "renamed.txt", project / "copied.txt")
    git(project, "add", ".")
    git(project, "commit", "-m", "rename and copy")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(project, base, head)

    module = load_script_module()
    with contextlib.chdir(project):
        review_input = module.load_review_input(
            argparse.Namespace(input_file=input_file, debug=False, sdk_python=None)
        )
        entries = module.changed_file_entries(review_input)

    by_path = {entry["path"]: entry for entry in entries}
    assert by_path["renamed.txt"]["status"].startswith("R")
    assert by_path["renamed.txt"]["old_path"] == "app.txt"
    assert by_path["copied.txt"]["status"].startswith("C")
    assert by_path["copied.txt"]["old_path"] == "app.txt"


@pytest.mark.parametrize(
    "output",
    [
        b"Q\0src/app.py\0",
        b"R100\0old.py\0",
        b"M\0src/app.py\0extra\0",
        b"R\0old.py\0new.py\0",
        b"C101\0old.py\0new.py\0",
        b"M100\0src/app.py\0",
    ],
)
def test_changed_file_entries_rejects_malformed_name_status(
    tmp_path: Path, monkeypatch, output: bytes
) -> None:
    project, _, _, input_file = committed_review_subject(tmp_path)
    module = load_script_module()
    with contextlib.chdir(project):
        review_input = module.load_review_input(
            argparse.Namespace(input_file=input_file, debug=False, sdk_python=None)
        )
        monkeypatch.setattr(module, "git_output_bytes", lambda *_: output)
        with pytest.raises(ValueError) as exc_info:
            module.changed_file_entries(review_input)

    assert str(exc_info.value) == "invalid_changed_file_entries"


def test_initial_state_records_subject_context_hashes_and_role_scopes(tmp_path: Path) -> None:
    project, base, head, input_file = committed_review_subject(tmp_path)
    module = load_script_module()
    with contextlib.chdir(project):
        review_input = module.load_review_input(
            argparse.Namespace(input_file=input_file, debug=False, sdk_python=None)
        )
        state = module.initial_review_state(review_input)
        module.atomic_write_json(review_input.output_dir / "review-state.json", state)
        allowed_paths = module.runtime_allowed_paths(review_input)
    saved = json.loads((review_input.output_dir / "review-state.json").read_text(encoding="utf-8"))

    assert saved["schema_version"] == "cross-agent-review-state/v1"
    assert saved["subject"]["change"] == "demo"
    assert saved["subject"]["base_ref"] == base
    assert saved["subject"]["head_ref"] == head
    assert saved["subject"]["head_ref_short"] == head[:12]
    assert saved["subject"]["input_file"] == input_file.relative_to(project).as_posix()
    assert saved["subject"]["input_hash"].startswith("sha256:")
    assert set(saved["subject"]["contexts"]) == {"spec", "design", "plan"}
    assert all(
        context["hash"].startswith("sha256:")
        for context in saved["subject"]["contexts"].values()
    )
    assert saved["roles"]["spec-alignment"]["attempts"] == []
    assert "status" not in saved["roles"]["spec-alignment"]
    assert review_input.output_dir / "review-state.json" in allowed_paths


def test_role_input_contains_only_full_review_diff_and_summary_stats(
    tmp_path: Path, capsys
) -> None:
    project, input_file = review_subject_with_full_and_summary_files(tmp_path)
    module = load_script_module()
    state_file = input_file.parent.parent / "review-state.json"

    with contextlib.chdir(project):
        assert (
            module.main(
                [
                    "_role-input",
                    "--input-file",
                    str(input_file),
                    "--state-file",
                    str(state_file),
                    "--role",
                    "implementation-correctness",
                ]
            )
            == 0
        )

    output = capsys.readouterr().out
    assert "+print('behavior')" in output
    assert "generated process body" not in output
    assert "docs/process.md" in output
    assert "过程文档仅供按需核对" in output
    assert "- docs/process.md: 过程文档仅供按需核对 (status: A)" in output
    assert "1\t0\tdocs/process.md" in output


@pytest.mark.parametrize(
    ("summary_only", "error"),
    [
        (
            [
                {"path": "src/app.py", "reason": "first"},
                {"path": "src/app.py", "reason": "second"},
            ],
            "invalid_summary_only: duplicate_path=src/app.py",
        ),
        ([{"path": "src/app.py", "reason": ""}], "invalid_summary_only: empty_reason=src/app.py"),
        ([{"path": "C:\\outside.txt", "reason": "outside"}], "path_outside_project"),
        ([{"path": "../src/app.py", "reason": "traversal"}], "path_outside_project"),
        ([{"path": "src/../src/app.py", "reason": "traversal"}], "path_outside_project"),
        ([{"path": "src/./app.py", "reason": "dot segment"}], "path_outside_project"),
        ([{"path": "src//app.py", "reason": "empty segment"}], "path_outside_project"),
        ([{"path": "src\\app.py", "reason": "backslash"}], "path_outside_project"),
        (
            [{"path": "not-changed.md", "reason": "not changed"}],
            "invalid_summary_only: not_changed=not-changed.md",
        ),
        ([{"path": "spec.md", "reason": "overlap"}], "classification_overlap"),
    ],
)
def test_summary_only_rejects_invalid_entries(
    tmp_path: Path, summary_only: list[dict[str, str]], error: str
) -> None:
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "spec.md", "spec body\n")
    write_file(project / "design.md", "design body\n")
    write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    write_file(project / "src" / "app.py", "print('ok')\n")
    git(project, "add", ".")
    git(project, "commit", "-m", "review subject")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(
        project,
        base,
        head,
        payload_overrides={"summary_only": summary_only},
    )

    module = load_script_module()
    with contextlib.chdir(project), pytest.raises(ValueError, match=error):
        review_input = module.load_review_input(
            argparse.Namespace(input_file=input_file, debug=False, sdk_python=None)
        )
        module.initial_review_state(review_input)


def test_summary_only_reports_sorted_classification_overlap_paths(tmp_path: Path) -> None:
    project, base, head, _ = committed_review_subject(tmp_path)
    input_file = write_review_input(
        project,
        base,
        head,
        payload_overrides={
            "summary_only": [
                {"path": "spec.md", "reason": "overlap"},
                {"path": "design.md", "reason": "overlap"},
            ]
        },
    )
    module = load_script_module()

    with contextlib.chdir(project), pytest.raises(ValueError) as exc_info:
        review_input = module.load_review_input(
            argparse.Namespace(input_file=input_file, debug=False, sdk_python=None)
        )
        module.initial_review_state(review_input)

    assert str(exc_info.value) == "classification_overlap: paths=design.md,spec.md"


def test_review_input_parses_revalidation_policy(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    input_file = write_review_input(
        project,
        "base",
        "head",
        payload_overrides={
            "revalidation_policy": [
                {"path": "checks.md", "validator": "checkbox-only"},
                {
                    "path": "manifest.yaml",
                    "validator": "mapping-fields-only",
                    "format": "yaml",
                    "fields": ["status", "evidence"],
                },
            ]
        },
    )

    module = load_script_module()
    with contextlib.chdir(project):
        review_input = module.load_review_input(
            argparse.Namespace(input_file=input_file, debug=False, sdk_python=None)
        )

    assert review_input.revalidation_policy == (
        module.RevalidationPolicy(path="checks.md", validator="checkbox-only"),
        module.RevalidationPolicy(
            path="manifest.yaml",
            validator="mapping-fields-only",
            format="yaml",
            fields=("status", "evidence"),
        ),
    )


@pytest.mark.parametrize(
    ("policy", "error"),
    [
        ({}, "expected_array"),
        (
            [
                {"path": "checks.md", "validator": "checkbox-only"},
                {"path": "checks.md", "validator": "checkbox-only"},
            ],
            "duplicate_path=checks.md",
        ),
        ([{"path": "../checks.md", "validator": "checkbox-only"}], "path_outside_project"),
        ([{"path": "checks.md", "validator": "unknown"}], "invalid_validator"),
        ([{"path": "checks.md", "validator": []}], "invalid_validator"),
        (
            [{"path": "manifest.json", "validator": "mapping-fields-only", "fields": ["status"]}],
            "invalid_format",
        ),
        (
            [
                {
                    "path": "manifest.json",
                    "validator": "mapping-fields-only",
                    "format": [],
                    "fields": ["status"],
                }
            ],
            "invalid_format",
        ),
        (
            [
                {
                    "path": "manifest.json",
                    "validator": "mapping-fields-only",
                    "format": "json",
                    "fields": [],
                }
            ],
            "invalid_fields",
        ),
        (
            [
                {
                    "path": "manifest.json",
                    "validator": "mapping-fields-only",
                    "format": "json",
                    "fields": ["status", "status"],
                }
            ],
            "duplicate_field=status",
        ),
    ],
)
def test_revalidation_policy_rejects_invalid_entries(
    tmp_path: Path, policy: object, error: str
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    input_file = write_review_input(
        project,
        "base",
        "head",
        payload_overrides={"revalidation_policy": policy},
    )

    module = load_script_module()
    with contextlib.chdir(project), pytest.raises(ValueError, match=error):
        module.load_review_input(
            argparse.Namespace(input_file=input_file, debug=False, sdk_python=None)
        )


def create_review_context_commit(project: Path) -> str:
    write_file(project / "spec.md", "spec body\n")
    write_file(project / "design.md", "design body\n")
    write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    git(project, "add", "spec.md", "design.md", "docs/superpowers/plans/demo.md")
    git(project, "commit", "-m", "add review context")
    return git(project, "rev-parse", "HEAD")


def commit_review_context(project: Path) -> str:
    ensure_review_context_template(project)
    return git(project, "rev-parse", "HEAD")


NO_BLOCKING_REVIEW = """# Review Result
## Findings
No findings.
"""

BLOCKING_REVIEW = """# Review Result
## Findings
- Severity: IMPORTANT
  Location: app.txt:1
  Summary: Wrong behavior
  Evidence: Evidence
  Recommendation: Fix behavior
"""


def review_args(
    project: Path,
    head: str,
    *,
    base: str | None = None,
    mode: str = "convergence",
) -> list[str]:
    return [
        "run",
        "--input-file",
        str(write_review_input(project, base or head, head, mode=mode)),
    ]


def reviewer_state(module, review_input, text: str = NO_BLOCKING_REVIEW) -> dict:
    state = {
        "subject": {
            "change": review_input.change,
            "base_ref": review_input.base_ref,
            "head_ref": review_input.head_ref,
        },
        "roles": {role: {"attempts": []} for role in module.REVIEWER_ROLES},
    }
    for role in module.REVIEWER_ROLES:
        module.record_role_result(state, role, "completed", text)
    return state


def run_review_in_process(module, monkeypatch, project: Path, *args: str, reviewer_text: str = NO_BLOCKING_REVIEW) -> int:
    monkeypatch.chdir(project)
    monkeypatch.setattr(module, "resolve_sdk_python", lambda explicit, require_real_sdk: "fake-sdk")
    monkeypatch.setattr(
        module,
        "run_sdk_role_subprocess",
        lambda review_args, sdk_python, role: ("completed", reviewer_text),
    )
    return module.main(list(args))


def guard_pass_path(
    project: Path,
    head: str,
    *,
    change: str = "demo",
    profile_id: str = "comet-review-gate",
    artifact_id: str = "cross_agent_review_pass",
) -> Path:
    return (
        project
        / ".local"
        / "guard"
        / "evidence"
        / profile_id
        / artifact_id
        / change
        / head[:12]
        / "pass.json"
    )


def test_run_accepts_single_review_input_file(tmp_path: Path, monkeypatch, capsys) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)

    status = run_review_in_process(module, monkeypatch, project, *review_args(project, head))
    captured = capsys.readouterr()

    assert status == 0
    assert "status: review_ready" in captured.out
    assert (project / ".local" / "cross-agent-review" / "demo" / head[:12] / "review-report.md").is_file()


def test_default_outputs_are_report_only(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent

    status = run_review_in_process(module, monkeypatch, project, "run", "--input-file", str(input_file))

    assert status == 0
    assert (output_dir / "review-report.md").is_file()
    assert not (output_dir / "review-pass.json").exists()
    assert not guard_pass_path(project, head).exists()
    assert not (output_dir / "review-results.json").exists()
    assert not (output_dir / "inputs").exists()
    assert not (output_dir / "prompts").exists()
    assert not (output_dir / "raw").exists()
    assert not (output_dir / "debug").exists()


def test_mark_pass_writes_guard_evidence_default_path(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    base = init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, base, head, mode="convergence")
    report_path = input_file.parent.parent / "review-report.md"
    write_file(report_path, NO_BLOCKING_REVIEW)

    result = run("mark-pass", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    marker_path = guard_pass_path(project, head)
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    assert f"head_ref_short: {head[:12]}" in result.stdout
    assert f"path: {marker_path.relative_to(project)}" in result.stdout
    assert marker_path.is_file()
    assert marker["schema_version"] == "guard-evidence/v1"
    assert marker["producer"] == "cross-agent-review"
    assert marker["profile_id"] == "comet-review-gate"
    assert marker["artifact_id"] == "cross_agent_review_pass"
    assert marker["subject_type"] == "comet-change"
    assert marker["subject_id"] == "demo"
    assert marker["head_ref_short"] == head[:12]
    assert marker["blocking_findings"] == 0
    assert marker["mode"] == "convergence"
    assert marker["base_ref"] == base
    assert marker["head_ref"] == head
    assert marker["report"] == str((input_file.parent.parent / "review-report.md").relative_to(project))
    assert marker["report_hash"].startswith("sha256:")


def test_mark_pass_records_endless_mode_and_refs(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    base = init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, base, head, mode="endless")
    write_file(input_file.parent.parent / "review-report.md", NO_BLOCKING_REVIEW)

    result = run("mark-pass", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    marker = json.loads(guard_pass_path(project, head).read_text(encoding="utf-8"))
    assert marker["mode"] == "endless"
    assert marker["base_ref"] == base
    assert marker["head_ref"] == head


def test_blocking_findings_write_report_without_pass_marker(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    project.mkdir()
    head = "1234567890abcdef"
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    monkeypatch.chdir(project)
    review_input = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None)
    )

    status = module.write_outputs(
        review_input, reviewer_state(module, review_input, BLOCKING_REVIEW)
    )

    assert status == 0
    assert (output_dir / "review-report.md").is_file()
    assert not (output_dir / "review-pass.json").exists()
    assert not guard_pass_path(project, head).exists()
    assert not (output_dir / "inputs").exists()


def test_debug_writes_input_prompts_and_raw_under_debug(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    monkeypatch.chdir(project)
    review_input = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=True, sdk_python=None)
    )

    def fake_role(_review_input, _sdk_python, role):
        raw_dir = review_input.output_dir / "debug" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{role}.txt").write_text(NO_BLOCKING_REVIEW, encoding="utf-8")
        return "completed", NO_BLOCKING_REVIEW

    monkeypatch.setattr(module, "run_sdk_role_subprocess", fake_role)
    state = {"roles": {role: {"attempts": []} for role in module.REVIEWER_ROLES}}
    module.dispatch_roles(review_input, sys.executable, state, module.REVIEWER_ROLES)

    debug_dir = input_file.parent.parent / "debug"
    assert json.loads((debug_dir / "review-input.json").read_text(encoding="utf-8"))["mode"] == "convergence"
    assert {path.name for path in (debug_dir / "prompts").iterdir()} == {
        "spec-alignment.txt",
        "implementation-correctness.txt",
    }
    assert {path.name for path in (debug_dir / "raw").iterdir()} == {
        "spec-alignment.txt",
        "implementation-correctness.txt",
    }


def test_sdk_role_subprocess_uses_plugin_owned_timeout(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    monkeypatch.chdir(project)
    review_input = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=True, sdk_python=None)
    )
    def fake_run(*args, **kwargs):
        assert kwargs["timeout"] == module.SDK_DISPATCH_TIMEOUT_SECONDS
        payload = json.loads(kwargs["input"])
        assert payload["roles"] == ["spec-alignment"]
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    status, output = module.run_sdk_role_subprocess(
        review_input, sys.executable, "spec-alignment"
    )

    assert status == "timed_out"
    assert "Reviewer dispatch timed out" in output


def test_missing_input_file_fails(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)

    result = run("run", "--input-file", str(project / ".local" / "missing" / "review-input.json"), cwd=project)

    assert result.returncode == 1
    assert "missing_file" in result.stdout


def test_missing_required_review_input_field_fails(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head, payload_overrides={"plan_file": None})
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    del payload["plan_file"]
    input_file.write_text(json.dumps(payload), encoding="utf-8")

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "missing_field: plan_file" in result.stdout


def test_missing_referenced_plan_file_fails(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(
        project,
        head,
        head,
        payload_overrides={"plan_file": "docs/superpowers/plans/missing.md"},
    )

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "missing_file" in result.stdout
    assert "missing.md" in result.stdout


def test_invalid_mode_fails(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head, mode="wide")

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "invalid_mode: wide" in result.stdout


def test_prepared_inputs_rejects_extra_regular_file(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    write_file(input_file.parent / "plan.md", "old snapshot\n")

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "unexpected_prepared_input" in result.stdout
    assert "plan.md" in result.stdout


def test_prepared_inputs_rejects_extra_directory(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    write_file(input_file.parent / "extra" / "junk.txt", "junk\n")
    output_dir = input_file.parent.parent

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "unexpected_prepared_input" in result.stdout
    assert "extra" in result.stdout
    assert not (output_dir / "review-pass.json").exists()


def test_input_file_must_be_named_review_input_json_under_prepared_inputs(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    wrong_file = input_file.parent / "input.json"
    wrong_file.write_text(input_file.read_text(encoding="utf-8"), encoding="utf-8")
    input_file.unlink()

    result = run("run", "--input-file", str(wrong_file), cwd=project)

    assert result.returncode == 1
    assert "invalid_input_file_location" in result.stdout


def test_input_file_must_be_under_change_and_head_runtime_dir(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    valid_input_file = write_review_input(project, head, head)
    wrong_input_file = project / "prepared-inputs" / "review-input.json"
    write_file(wrong_input_file, valid_input_file.read_text(encoding="utf-8"))
    write_file(wrong_input_file.parent / "dirty.txt", "dirty\n")

    result = run("run", "--input-file", str(wrong_input_file), cwd=project)

    assert result.returncode == 1
    assert "invalid_input_file_location" in result.stdout
    assert not (project / "review-pass.json").exists()


def test_change_path_traversal_rejects_input_location(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head, change="../../escape")
    output_dir = input_file.parent.parent

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "invalid_input_file_location" in result.stdout
    assert not (output_dir / "review-pass.json").exists()


def test_invalid_base_ref_fails_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, "0" * 40, head)

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "base_ref_mismatch" in result.stdout


def test_dirty_worktree_outside_runtime_artifacts_rejects_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    write_file(project / "dirty.txt", "dirty\n")

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (input_file.parent.parent / "review-pass.json").exists()


def test_output_dir_root_extra_file_rejects_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    write_file(output_dir / "notes.txt", "not a review runtime artifact\n")

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (output_dir / "review-pass.json").exists()


@pytest.mark.parametrize("debug_child", ["prompts", "raw"])
def test_debug_extra_file_rejects_before_dispatch(tmp_path: Path, debug_child: str) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    write_file(output_dir / "debug" / debug_child / "extra.txt", "not a runtime artifact\n")

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (output_dir / "review-pass.json").exists()


@pytest.mark.parametrize(
    "artifact_child",
    [
        Path("review-report.md") / "extra.txt",
        Path("debug") / "raw" / "spec-alignment.txt" / "extra.txt",
    ],
)
def test_runtime_artifact_file_path_directory_children_reject_before_dispatch(
    tmp_path: Path, artifact_child: Path
) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    write_file(output_dir / artifact_child, "not a runtime artifact\n")

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (output_dir / "review-pass.json").exists()


def test_renamed_tracked_file_into_runtime_artifacts_rejects_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    git(project, "mv", "app.txt", str(output_dir / "app.txt"))

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (output_dir / "review-pass.json").exists()


def test_copied_tracked_file_into_runtime_artifacts_rejects_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    shutil.copyfile(project / "app.txt", output_dir / "app.txt")
    git(project, "add", str(output_dir / "app.txt"))

    result = run("run", "--input-file", str(input_file), cwd=project)

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (output_dir / "review-pass.json").exists()


def test_clean_worktree_checks_reuse_runtime_allowlist(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    parsed = module.build_parser().parse_args(
        [
            "run",
            "--input-file",
            str(input_file),
        ]
    )
    calls = []

    def fake_ensure_clean_subject(cwd, head_ref, allowed_dirty_paths=()):
        calls.append([Path(path).resolve() for path in allowed_dirty_paths])

    monkeypatch.setattr(module, "ensure_clean_subject", fake_ensure_clean_subject)
    monkeypatch.setattr(module, "resolve_sdk_python", lambda explicit, require_real_sdk: "fake-sdk")
    monkeypatch.setattr(
        module,
        "run_sdk_role_subprocess",
        lambda review_args, sdk_python, role: ("completed", NO_BLOCKING_REVIEW),
    )
    monkeypatch.chdir(project)

    assert module.run_review(parsed) == 0

    assert len(calls) == 2
    assert calls[0] == calls[1]
    output_dir = input_file.parent.parent
    debug_dir = output_dir / "debug"
    assert set(calls[0]) == {
        input_file.resolve(),
        (output_dir / "review-report.md").resolve(),
        (output_dir / "review-pass.json").resolve(),
        (output_dir / "review-state.json").resolve(),
        (debug_dir / "review-input.json").resolve(),
        (debug_dir / "prompts" / "spec-alignment.txt").resolve(),
        (debug_dir / "prompts" / "implementation-correctness.txt").resolve(),
        (debug_dir / "raw" / "spec-alignment.txt").resolve(),
        (debug_dir / "raw" / "implementation-correctness.txt").resolve(),
    }
    assert output_dir.resolve() not in calls[0]


def test_diff_file_argument_is_not_required(tmp_path: Path, monkeypatch, capsys) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)

    status = run_review_in_process(module, monkeypatch, project, *review_args(project, head))
    captured = capsys.readouterr()

    assert status == 0
    assert "status: review_ready" in captured.out


def make_review_input_for_module(module, tmp_path: Path, *, debug: bool = False):
    input_file = write_review_input(tmp_path, "base", "head")
    cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        return module.load_review_input(
            types.SimpleNamespace(
                input_file=input_file,
                debug=debug,
                sdk_python=None,
            )
        )
    finally:
        os.chdir(cwd)


def make_review_args_for_module(module, tmp_path: Path, *, debug: bool = False):
    return make_review_input_for_module(module, tmp_path, debug=debug)


def test_reviewer_roles_are_two_default_roles(tmp_path: Path) -> None:
    module = load_script_module()

    assert module.REVIEWER_ROLES == ["spec-alignment", "implementation-correctness"]
    assert set(module.ROLE_FOCUS) == {"spec-alignment", "implementation-correctness"}


def test_reviewer_prompt_references_review_input_file_only(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "two\n")
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "feature")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(project, base, head)
    monkeypatch.chdir(project)
    review_input = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None)
    )

    prompt = module.reviewer_prompt(review_input, "spec-alignment")
    state_file = input_file.parent.parent / "review-state.json"

    assert str(input_file) in prompt
    assert str(state_file) in prompt
    assert "_role-input" in prompt
    assert f"git diff {base}...{head}" not in prompt
    assert f"git log {base}..{head} --oneline" not in prompt
    assert f"git diff --name-status --find-renames --find-copies-harder {base}...{head}" not in prompt
    assert "Return only the lightweight Markdown format below." in prompt
    assert "Do not use JSON." in prompt
    assert "# Review Result:" in prompt
    assert "Do not wrap the response in Markdown fences." in prompt
    assert "Manifest file:" not in prompt
    assert "Changed files:" not in prompt
    assert "Spec bytes:" not in prompt
    assert "Design file:" not in prompt
    assert "Tasks file:" not in prompt
    assert "spec body" not in prompt
    assert "plan body" not in prompt


def test_reviewer_prompt_template_uses_limited_variables(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review_input = make_review_input_for_module(module, tmp_path)
    captured_values = {}

    def capture_render_template(path: Path, values: dict[str, str]) -> str:
        captured_values.update(values)
        return "rendered prompt"

    monkeypatch.setattr(module, "render_template", capture_render_template)

    prompt = module.reviewer_prompt(review_input, "implementation-correctness")

    assert prompt == "rendered prompt"
    assert set(captured_values) == {
        "role",
        "input_file_path",
        "state_file_path",
        "role_input_command",
        "severity_rubric",
        "role_focus",
    }
    assert captured_values["role"] == "implementation-correctness"
    assert captured_values["input_file_path"] == str(review_input.input_file)
    assert captured_values["state_file_path"] == str(
        review_input.output_dir / "review-state.json"
    )
    assert "_role-input" in captured_values["role_input_command"]
    for legacy_key in ["change", "manifest_path", "changed_files", "context_files", "tasks_file"]:
        assert legacy_key not in captured_values


def test_spec_alignment_role_focus_uses_plan_contract_not_tasks(tmp_path: Path) -> None:
    module = load_script_module()
    review_input = make_review_input_for_module(module, tmp_path)

    prompt = module.reviewer_prompt(review_input, "spec-alignment")
    role_focus = module.ROLE_FOCUS["spec-alignment"]

    assert "plan" in role_focus
    assert "tasks_file" not in role_focus
    assert "tasks" not in role_focus.lower()
    assert "tasks_file" not in prompt
    assert "tasks" not in prompt.lower()


def test_dirty_worktree_rejects_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    write_file(project / "dirty.txt", "dirty\n")

    result = run(*review_args(project, head), cwd=project)

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (project / ".local" / "cross-agent-review" / "demo" / head[:12] / "review-pass.json").exists()


def test_input_files_in_space_directory_are_allowed(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    project.mkdir()
    input_dir = project / "review inputs"
    spec_file = write_file(input_dir / "spec file.md")
    design_file = write_file(input_dir / "design file.md")
    plan_file = write_file(input_dir / "plan file.md")
    head = "1234567890abcdef"
    input_file = write_review_input(
        project,
        head,
        head,
        payload_overrides={
            "spec_file": str(spec_file.relative_to(project)),
            "design_file": str(design_file.relative_to(project)),
            "plan_file": str(plan_file.relative_to(project)),
        },
    )
    monkeypatch.chdir(project)

    review_input = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None)
    )

    assert review_input.spec_file == spec_file
    assert review_input.design_file == design_file
    assert review_input.plan_file == plan_file


def test_head_mismatch_rejects_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)

    result = run(*review_args(project, "0" * 40, base=head), cwd=project)

    assert result.returncode == 1
    assert "head_ref_mismatch" in result.stdout
    assert head != "0" * 40


def test_sdk_missing_reports_clear_error(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    missing_python = tmp_path / "missing-python.exe"

    result = run(
        *review_args(project, head),
        "--sdk-python",
        str(missing_python),
        cwd=project,
    )

    assert result.returncode == 1
    assert "sdk_unavailable" in result.stdout


def test_sdk_python_directory_reports_clear_error_without_traceback(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    sdk_dir = tmp_path / "not-python"
    sdk_dir.mkdir()

    result = run(
        *review_args(project, head),
        "--sdk-python",
        str(sdk_dir),
        cwd=project,
    )

    assert result.returncode == 1
    assert "sdk_unavailable" in result.stdout
    assert "Traceback" not in result.stderr


def test_sdk_python_invalid_file_reports_clear_error_without_traceback(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    invalid_python = write_file(tmp_path / "not-python.exe", "not a real executable\n")

    result = run(
        *review_args(project, head),
        "--sdk-python",
        str(invalid_python),
        cwd=project,
    )

    assert result.returncode == 1
    assert "sdk_unavailable" in result.stdout
    assert "Traceback" not in result.stderr


def test_run_can_be_exercised_with_internal_dispatch_injection(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)

    status = run_review_in_process(module, monkeypatch, project, *review_args(project, head))

    assert status == 0


def test_default_run_does_not_archive_context_snapshots_or_git_manifest(tmp_path: Path, monkeypatch, capsys) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent

    status = run_review_in_process(module, monkeypatch, project, "run", "--input-file", str(input_file))
    captured = capsys.readouterr()

    assert status == 0
    assert f"head_ref_short: {head[:12]}" in captured.out
    assert f"input_file: {input_file.relative_to(project)}" in captured.out
    assert (output_dir / "review-report.md").is_file()
    assert not (output_dir / "review-pass.json").exists()
    assert not (output_dir / "inputs").exists()
    assert not (output_dir / "prompts").exists()
    assert not (output_dir / "raw").exists()


def test_run_rejects_legacy_tests_file_argument(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    legacy_tests_file = write_file(project / "legacy-tests.txt", "legacy tests\n")
    output_dir = project / ".local" / "cross-agent-review" / "demo" / head[:12]

    result = run(
        *review_args(project, head),
        "--tests-file",
        str(legacy_tests_file),
        cwd=project,
    )

    assert result.returncode == 2
    assert "unrecognized arguments: --tests-file" in result.stderr
    assert not (output_dir / "review-report.md").exists()


def test_run_rejects_fake_reviewer_results_argument(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent

    result = run(
        "run",
        "--input-file",
        str(input_file),
        "--fake-reviewer-results",
        "[]",
        cwd=project,
    )

    assert result.returncode == 2
    assert "unrecognized arguments: --fake-reviewer-results" in result.stderr
    assert not (output_dir / "review-report.md").exists()


def test_reviewer_prompt_does_not_reference_legacy_tests_file(tmp_path: Path) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert "tests_file" not in prompt
    assert "Tests file:" not in prompt


def test_prompt_contains_review_context(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    status = run_review_in_process(module, monkeypatch, project, "run", "--input-file", str(input_file))

    assert status == 0
    assert (output_dir / "review-report.md").is_file()
    assert not (output_dir / "review-pass.json").exists()


def test_reviewer_prompt_references_review_input_not_diff_file(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    base = commit_review_context(project)
    write_file(project / "app.txt", "two\n")
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "feature")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(project, base, head)
    monkeypatch.chdir(project)
    review = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None)
    )

    prompt = module.reviewer_prompt(review, "spec-alignment")
    state_file = input_file.parent.parent / "review-state.json"

    assert "Role: spec-alignment" in prompt
    assert "Return only the lightweight Markdown format below." in prompt
    assert str(input_file) in prompt
    assert str(state_file) in prompt
    assert "_role-input" in prompt
    assert f"git diff {base}...{head}" not in prompt
    assert f"git log {base}..{head} --oneline" not in prompt
    assert f"git diff --name-status --find-renames --find-copies-harder {base}...{head}" not in prompt
    assert "Change: demo-change" not in prompt
    assert f"Base ref: {base}" not in prompt
    assert f"Head ref: {head}" not in prompt
    assert "Changed files:" not in prompt
    assert "Diff file:" not in prompt
    assert "diff.patch" not in prompt
    assert "spec body" not in prompt
    assert "plan body" not in prompt


def test_reviewer_prompt_references_input_file_and_role_rubrics(tmp_path: Path) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)

    for role in module.REVIEWER_ROLES:
        prompt = module.reviewer_prompt(review, role)
        assert f"Focus for {role}:" in prompt
        assert "Severity rubric:" in prompt
        assert str(review.input_file) in prompt
        assert str(review.output_dir / "review-state.json") in prompt
        assert "_role-input" in prompt
        assert "Manifest file:" not in prompt
        assert "# Review Result:" in prompt


def test_reviewer_prompt_template_is_loaded_from_file(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)
    template = write_file(
        tmp_path / "reviewer-prompt.md",
        "Template marker: {{ role }} / {{ input_file_path }}\n",
    )
    monkeypatch.setattr(module, "REVIEWER_PROMPT_TEMPLATE", template, raising=False)

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert f"Template marker: spec-alignment / {review.input_file}" in prompt


def test_reviewer_prompt_does_not_inline_large_diff_or_context(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    base = commit_review_context(project)
    repeated_diff_body = "large diff body marker\n"
    write_file(project / "app.txt", repeated_diff_body * 1000)
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "large feature")
    head = git(project, "rev-parse", "HEAD")
    large_spec = "Spec body\n" + ("requirement\n" * 2000)
    large_design = "Design body\n" + ("design detail\n" * 2000)
    large_tasks = "Tasks body\n" + ("task detail\n" * 2000)
    spec_file = write_file(project / "spec.md", large_spec)
    design_file = write_file(project / "design.md", large_design)
    plan_file = write_file(project / "docs" / "superpowers" / "plans" / "demo.md", large_tasks)
    git(project, "add", "spec.md", "design.md", "docs/superpowers/plans/demo.md")
    git(project, "commit", "-m", "large context")
    head = git(project, "rev-parse", "HEAD")
    input_file = project / ".local" / "cross-agent-review" / "demo" / head[:12] / "prepared-inputs" / "review-input.json"
    write_file(
        input_file,
        json.dumps(
            {
                "change": "demo",
                "mode": "convergence",
                "base_ref": base,
                "head_ref": head,
                "spec_file": str(spec_file.relative_to(project)),
                "design_file": str(design_file.relative_to(project)),
                "plan_file": str(plan_file.relative_to(project)),
            }
        )
        + "\n",
    )
    monkeypatch.chdir(project)
    review = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None)
    )

    prompt = module.reviewer_prompt(review, "implementation-correctness")

    assert str(input_file) in prompt
    assert str(review.output_dir / "review-state.json") in prompt
    assert "_role-input" in prompt
    assert f"git diff {base}...{head}" not in prompt
    assert f"Spec file: {spec_file}" not in prompt
    assert f"Design file: {design_file}" not in prompt
    assert f"Plan file: {plan_file}" not in prompt
    assert "Changed files:" not in prompt
    assert repeated_diff_body * 5 not in prompt
    assert "Spec body" not in prompt
    assert "Design body" not in prompt
    assert "Tasks body" not in prompt
    assert "requirement\n" * 5 not in prompt
    assert "design detail" not in prompt
    assert "task detail" not in prompt
    assert "diff.patch" not in prompt
    assert len(prompt) < 5000


def test_sdk_role_subprocess_payload_contains_only_requested_role(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_script_module()
    review_input = make_review_input_for_module(module, tmp_path)
    captured_payload = None

    def fake_run(*args, **kwargs):
        nonlocal captured_payload
        captured_payload = json.loads(kwargs["input"])
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "role": "spec-alignment",
                        "execution_status": "completed",
                        "text": NO_BLOCKING_REVIEW,
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    status, output = module.run_sdk_role_subprocess(
        review_input, sys.executable, "spec-alignment"
    )

    assert (status, output) == ("completed", NO_BLOCKING_REVIEW)
    assert captured_payload["roles"] == ["spec-alignment"]
    assert set(captured_payload["prompts"]) == {"spec-alignment"}
    assert "readonly_tools" not in captured_payload
    assert "raw_dir" not in captured_payload


def test_sdk_role_subprocess_whitespace_result_is_failed(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_script_module()
    review_input = make_review_input_for_module(module, tmp_path)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "role": "spec-alignment",
                        "execution_status": "completed",
                        "text": " \n\t",
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    status, output = module.run_sdk_role_subprocess(
        review_input, sys.executable, "spec-alignment"
    )

    assert status == "failed"
    assert "Severity: CRITICAL" in output
    assert "invalid role result" in output


def test_sdk_dispatch_writes_raw_reviewer_output(monkeypatch, tmp_path: Path) -> None:
    module = load_script_module()
    raw_dir = tmp_path / "raw"

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            pass

    async def fake_query(*, prompt, options):
        class Message:
            result = NO_BLOCKING_REVIEW

        yield Message()

    fake_sdk = types.SimpleNamespace(ClaudeAgentOptions=FakeClaudeAgentOptions, query=fake_query)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "cwd": str(REPO_ROOT),
                    "roles": ["spec-alignment"],
                    "prompts": {"spec-alignment": "prompt"},
                    "raw_dir": str(raw_dir),
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    assert (raw_dir / "spec-alignment.txt").read_text(encoding="utf-8") == NO_BLOCKING_REVIEW


def invoke_task2_sdk_dispatch(module, monkeypatch, capsys, query) -> dict:
    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setitem(
        sys.modules,
        "claude_agent_sdk",
        types.SimpleNamespace(ClaudeAgentOptions=FakeClaudeAgentOptions, query=query),
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "cwd": str(REPO_ROOT),
                    "roles": ["spec-alignment"],
                    "prompts": {"spec-alignment": "prompt"},
                }
            )
        ),
    )
    assert module.run_sdk_dispatch() == 0
    return json.loads(capsys.readouterr().out)[0]


def test_task2_sdk_dispatch_nonempty_result_is_completed(monkeypatch, capsys) -> None:
    module = load_script_module()

    async def fake_query(*, prompt, options):
        yield types.SimpleNamespace(result=BLOCKING_REVIEW)

    result = invoke_task2_sdk_dispatch(module, monkeypatch, capsys, fake_query)

    assert result["execution_status"] == "completed"
    assert result["text"] == BLOCKING_REVIEW


def test_task2_sdk_dispatch_empty_result_is_failed(monkeypatch, capsys) -> None:
    module = load_script_module()

    async def fake_query(*, prompt, options):
        if False:
            yield

    result = invoke_task2_sdk_dispatch(module, monkeypatch, capsys, fake_query)

    assert result["execution_status"] == "failed"
    assert "Reviewer returned empty output" in result["text"]


def test_task2_sdk_dispatch_whitespace_result_is_failed(monkeypatch, capsys) -> None:
    module = load_script_module()

    async def fake_query(*, prompt, options):
        yield types.SimpleNamespace(result=" \n\t")

    result = invoke_task2_sdk_dispatch(module, monkeypatch, capsys, fake_query)

    assert result["execution_status"] == "failed"
    assert "Severity: CRITICAL" in result["text"]
    assert "Reviewer returned empty output" in result["text"]


def test_task2_sdk_dispatch_query_exception_is_failed(monkeypatch, capsys) -> None:
    module = load_script_module()

    async def fake_query(*, prompt, options):
        raise RuntimeError("query broke")
        yield

    result = invoke_task2_sdk_dispatch(module, monkeypatch, capsys, fake_query)

    assert result["execution_status"] == "failed"
    assert "RuntimeError: query broke" in result["text"]


def test_task2_sdk_dispatch_wait_timeout_is_timed_out(monkeypatch, capsys) -> None:
    module = load_script_module()

    async def fake_query(*, prompt, options):
        yield types.SimpleNamespace(result=NO_BLOCKING_REVIEW)

    async def fake_wait_for(awaitable, timeout):
        assert timeout == module.SDK_REVIEWER_TIMEOUT_SECONDS
        awaitable.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
    result = invoke_task2_sdk_dispatch(module, monkeypatch, capsys, fake_query)

    assert result["execution_status"] == "timed_out"
    assert "Reviewer timed out" in result["text"]


def test_completed_role_is_saved_before_sibling_timeout(tmp_path: Path, monkeypatch) -> None:
    project, input_file = committed_review_input(tmp_path)
    module = load_script_module()
    state_path = input_file.parent.parent / "review-state.json"

    def fake_role(_review_input, _python, role):
        if role == "spec-alignment":
            return "completed", "# Review Result\n## Findings\nNone\n"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if state_path.exists():
                saved = json.loads(state_path.read_text(encoding="utf-8"))
                if saved["roles"]["spec-alignment"].get("status") == "completed":
                    break
            time.sleep(0.01)
        else:
            raise AssertionError("completed sibling was not persisted immediately")
        failure = module.reviewer_failure(
            role,
            "Reviewer timed out",
            "Exceeded 480 seconds.",
            "Retry",
        )
        return "timed_out", failure["text"]

    monkeypatch.setattr(
        module,
        "resolve_sdk_python",
        lambda explicit, require_real_sdk: "fake-sdk",
    )
    monkeypatch.setattr(module, "run_sdk_role_subprocess", fake_role, raising=False)

    result = run(*review_args_from_input(input_file), cwd=project)
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stdout + result.stderr
    assert state["roles"]["spec-alignment"]["status"] == "completed"
    assert state["roles"]["implementation-correctness"]["status"] == "timed_out"
    for role in module.REVIEWER_ROLES:
        output = state["roles"][role]["output"]
        assert state["roles"][role]["output_hash"] == module.sha256_bytes(output.encode("utf-8"))


def test_parent_future_exception_is_saved_as_failed_markdown(tmp_path: Path, monkeypatch) -> None:
    project, input_file = committed_review_input(tmp_path)
    module = load_script_module()

    def fake_role(_review_input, _python, role):
        if role == "implementation-correctness":
            raise RuntimeError("worker broke")
        return "completed", NO_BLOCKING_REVIEW

    monkeypatch.setattr(module, "run_sdk_role_subprocess", fake_role, raising=False)
    with contextlib.chdir(project):
        review_input = module.load_review_input(
            argparse.Namespace(input_file=input_file, debug=False, sdk_python=None)
        )
        state = module.initial_review_state(review_input)
        module.atomic_write_json(review_input.output_dir / "review-state.json", state)
        module.dispatch_roles(review_input, "fake-sdk", state, module.REVIEWER_ROLES)

    role_state = state["roles"]["implementation-correctness"]
    assert role_state["status"] == "failed"
    assert isinstance(role_state["output"], str)
    assert "RuntimeError: worker broke" in role_state["output"]
    assert role_state["output_hash"] == module.sha256_bytes(role_state["output"].encode("utf-8"))


def test_record_role_result_rejects_whitespace_completed_output() -> None:
    module = load_script_module()
    state = {"roles": {"spec-alignment": {"attempts": []}}}

    module.record_role_result(state, "spec-alignment", "completed", " \n\t")

    role_state = state["roles"]["spec-alignment"]
    assert role_state["status"] == "failed"
    assert role_state["output"].strip()
    assert "Severity: CRITICAL" in role_state["output"]
    assert role_state["output_hash"] == module.sha256_bytes(
        role_state["output"].encode("utf-8")
    )


def test_dispatch_records_numbered_attempt_timestamps_at_boundaries(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_script_module()
    review_input = make_review_input_for_module(module, tmp_path)
    role = "spec-alignment"
    state = {"roles": {role: {"attempts": []}}}
    events = []
    real_datetime = module.datetime
    timestamps = iter(
        [
            real_datetime(2026, 7, 10, 1, 2, 3, tzinfo=module.UTC),
            real_datetime(2026, 7, 10, 1, 2, 4, tzinfo=module.UTC),
            real_datetime(2026, 7, 10, 1, 2, 5, tzinfo=module.UTC),
            real_datetime(2026, 7, 10, 1, 2, 6, tzinfo=module.UTC),
        ]
    )

    class FakeDateTime:
        @classmethod
        def now(cls, timezone):
            assert timezone is module.UTC
            value = next(timestamps)
            events.append(value.isoformat(timespec="microseconds").replace("+00:00", "Z"))
            return value

    def fake_role(*_args):
        events.append("worker")
        return "completed", NO_BLOCKING_REVIEW

    monkeypatch.setattr(module, "datetime", FakeDateTime)
    monkeypatch.setattr(module, "run_sdk_role_subprocess", fake_role)

    module.dispatch_roles(review_input, "fake-sdk", state, [role])
    module.dispatch_roles(review_input, "fake-sdk", state, [role])

    role_state = state["roles"][role]
    assert events == [
        "2026-07-10T01:02:03.000000Z",
        "worker",
        "2026-07-10T01:02:04.000000Z",
        "2026-07-10T01:02:05.000000Z",
        "worker",
        "2026-07-10T01:02:06.000000Z",
    ]
    assert [attempt["number"] for attempt in role_state["attempts"]] == [1, 2]
    assert role_state["attempts"][0] == {
        "number": 1,
        "started_at": "2026-07-10T01:02:03.000000Z",
        "finished_at": "2026-07-10T01:02:04.000000Z",
        "status": "completed",
        "output": NO_BLOCKING_REVIEW,
        "output_hash": module.sha256_bytes(NO_BLOCKING_REVIEW.encode("utf-8")),
    }
    assert role_state["attempts"][1]["started_at"] == "2026-07-10T01:02:05.000000Z"
    assert role_state["attempts"][1]["finished_at"] == "2026-07-10T01:02:06.000000Z"
    assert role_state["status"] == "completed"
    assert role_state["output"] == NO_BLOCKING_REVIEW
    assert role_state["output_hash"] == module.sha256_bytes(
        NO_BLOCKING_REVIEW.encode("utf-8")
    )
    assert "number" not in role_state
    assert "started_at" not in role_state
    assert "finished_at" not in role_state


def test_report_is_rebuilt_only_from_state_and_top_level_hash_is_saved(
    tmp_path: Path,
) -> None:
    project, input_file = committed_review_input(tmp_path)
    module = load_script_module()

    with contextlib.chdir(project):
        review_input = module.load_review_input(
            argparse.Namespace(input_file=input_file, debug=False, sdk_python=None)
        )
        state = module.initial_review_state(review_input)
        module.record_role_result(
            state,
            "spec-alignment",
            "completed",
            "# Review Result: spec-alignment\n## Findings\nSpec state output\n",
        )
        module.record_role_result(
            state,
            "implementation-correctness",
            "failed",
            "# Review Result: implementation-correctness\n## Findings\nImplementation state output\n",
        )
        state["subject"].update(
            {
                "change": "state-only-change",
                "base_ref": "state-only-base",
                "head_ref": "state-only-head",
            }
        )
        before = json.loads(json.dumps(state))
        report_text = module.render_report(state)
        with pytest.raises(TypeError):
            module.render_report(review_input, state)
        module.atomic_write_json(review_input.output_dir / "review-state.json", state)
        assert module.write_outputs(review_input, state) == 0

    report_path = review_input.output_dir / "review-report.md"
    report = report_path.read_text(encoding="utf-8")
    saved = json.loads((review_input.output_dir / "review-state.json").read_text(encoding="utf-8"))
    assert report == report_text
    assert "# Cross-Agent Review: state-only-change" in report
    assert "- Base ref: `state-only-base`" in report
    assert "- Head ref: `state-only-head`" in report
    assert "Spec state output" in report
    assert "Implementation state output" in report
    assert saved["report_hash"] == module.sha256_bytes(report_path.read_bytes())
    assert "report" not in saved
    assert set(saved) == {*before, "report_hash"}
    for key, value in before.items():
        assert saved[key] == value


def test_reviewer_prompt_requires_lightweight_markdown_contract(tmp_path: Path) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert "Return only the lightweight Markdown format below." in prompt
    assert "Do not use JSON." in prompt
    assert "# Review Result:" in prompt
    assert "Use only these severity values: CRITICAL, IMPORTANT, WARNING, SUGGESTION." in prompt
    assert "If there are no issues, write exactly:" in prompt
    assert "Do not put pass, aligned, ok, or informational observations in findings." in prompt
    assert "Do not use severity aliases such as high, medium, low, minor, or info." in prompt


def test_internal_dispatch_injection_generates_report_without_results_file(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    output_dir = project / ".local" / "cross-agent-review" / "demo" / head[:12]

    status = run_review_in_process(module, monkeypatch, project, *review_args(project, head))

    assert status == 0
    assert (output_dir / "review-report.md").is_file()
    assert not (output_dir / "review-pass.json").exists()


def test_sdk_dispatch_uses_default_sdk_tools(monkeypatch, capsys) -> None:
    module = load_script_module()
    captured_options = []

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            captured_options.append(kwargs)

    async def fake_query(*, prompt, options):
        class Message:
            result = NO_BLOCKING_REVIEW

        yield Message()

    fake_sdk = types.SimpleNamespace(ClaudeAgentOptions=FakeClaudeAgentOptions, query=fake_query)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "cwd": str(REPO_ROOT),
                    "roles": ["spec-alignment"],
                    "prompts": {"spec-alignment": "prompt"},
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    capsys.readouterr()
    assert captured_options == [{"cwd": str(REPO_ROOT)}]


def test_sdk_dispatch_uses_plugin_owned_reviewer_timeout(monkeypatch, capsys, tmp_path: Path) -> None:
    module = load_script_module()
    raw_dir = tmp_path / "raw"

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            pass

    async def fake_query(*, prompt, options):
        class Message:
            result = NO_BLOCKING_REVIEW

        yield Message()

    fake_sdk = types.SimpleNamespace(ClaudeAgentOptions=FakeClaudeAgentOptions, query=fake_query)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)
    async def fake_wait_for(awaitable, timeout):
        assert timeout == 480
        return await awaitable

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "cwd": str(REPO_ROOT),
                    "roles": ["spec-alignment"],
                    "prompts": {"spec-alignment": "prompt"},
                    "raw_dir": str(raw_dir),
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    data = json.loads(capsys.readouterr().out)
    assert data[0]["role"] == "spec-alignment"
    assert "No findings." in data[0]["text"]
    assert (raw_dir / "spec-alignment.txt").read_text(encoding="utf-8") == NO_BLOCKING_REVIEW


def test_sdk_role_subprocess_invalid_stdout_is_failed(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="not json", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    status, output = module.run_sdk_role_subprocess(
        review, sys.executable, "spec-alignment"
    )

    assert status == "failed"
    assert "sdk_dispatch_invalid_output" in output
    assert "stdout was not valid JSON" in output


def test_non_blocking_findings_generate_report_without_pass_marker(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    project.mkdir()
    head = "1234567890abcdef"
    input_file = write_review_input(project, head, head)
    output_dir = project / ".local" / "cross-agent-review" / "demo" / head[:12]
    review_text = """# Review Result
## Findings
- Severity: WARNING
  Location: app.txt:1
  Summary: Minor issue
  Evidence: Evidence
  Recommendation: Recommendation
"""
    monkeypatch.chdir(project)
    review_input = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None)
    )

    status = module.write_outputs(
        review_input, reviewer_state(module, review_input, review_text)
    )

    assert status == 0
    assert (output_dir / "review-report.md").is_file()
    assert not (output_dir / "review-pass.json").exists()


def test_blocking_findings_do_not_generate_pass_marker(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    project.mkdir()
    head = "1234567890abcdef"
    input_file = write_review_input(project, head, head)
    output_dir = project / ".local" / "cross-agent-review" / "demo" / head[:12]
    monkeypatch.chdir(project)
    review_input = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None)
    )

    status = module.write_outputs(
        review_input, reviewer_state(module, review_input, BLOCKING_REVIEW)
    )

    assert status == 0
    assert (output_dir / "review-report.md").is_file()
    assert not (output_dir / "review-pass.json").exists()


def test_run_removes_stale_legacy_pass_marker_from_reused_output_dir(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent

    clean_status = run_review_in_process(module, monkeypatch, project, "run", "--input-file", str(input_file))

    assert clean_status == 0
    (output_dir / "review-pass.json").write_text("stale\n", encoding="utf-8")

    blocking_status = run_review_in_process(
        module,
        monkeypatch,
        project,
        "run",
        "--input-file",
        str(input_file),
        reviewer_text=BLOCKING_REVIEW,
    )

    assert blocking_status == 0
    assert not (output_dir / "review-pass.json").exists()


def test_mark_pass_report_hash_matches_report(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    write_file(output_dir / "review-report.md", NO_BLOCKING_REVIEW)
    mark_result = run("mark-pass", "--input-file", str(input_file), cwd=project)

    assert mark_result.returncode == 0, mark_result.stdout + mark_result.stderr
    report = (output_dir / "review-report.md").read_bytes()
    marker = json.loads(guard_pass_path(project, head).read_text(encoding="utf-8"))
    import hashlib

    assert marker["report_hash"] == "sha256:" + hashlib.sha256(report).hexdigest()
    assert marker["head_ref"] == head


def test_reviewer_state_preserves_reviewer_text_without_parsing() -> None:
    module = load_script_module()
    review_input = types.SimpleNamespace(change="demo", base_ref="base", head_ref="head")

    state = reviewer_state(module, review_input, NO_BLOCKING_REVIEW)
    module.record_role_result(
        state,
        "implementation-correctness",
        "completed",
        BLOCKING_REVIEW,
    )

    assert state["roles"]["spec-alignment"]["output"] == NO_BLOCKING_REVIEW
    assert state["roles"]["implementation-correctness"]["output"] == BLOCKING_REVIEW
