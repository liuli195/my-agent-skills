import asyncio
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
    spec = importlib.util.spec_from_file_location("cross_agent_review", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def test_cross_agent_review_template_cache_key_includes_script_contents() -> None:
    assert TEMPLATE_CACHE_KEY == template_cache_key(Path(__file__), SCRIPT)


def test_missing_required_args_fail() -> None:
    result = run("run", "--change", "demo")

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


def commit_review_context(project: Path) -> str:
    write_file(project / "spec.md", "spec body\n")
    write_file(project / "design.md", "design body\n")
    write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    git(project, "add", "spec.md", "design.md", "docs/superpowers/plans/demo.md")
    git(project, "commit", "-m", "add review context")
    return git(project, "rev-parse", "HEAD")


def review_args(project: Path, head: str, *, mode: str = "convergence") -> list[str]:
    return [
        "run",
        "--input-file",
        str(write_review_input(project, head, head, mode=mode)),
        "--fake-reviewer-results",
        "[]",
    ]


def test_run_accepts_single_review_input_file(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)

    result = run(*review_args(project, head), cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: pass" in result.stdout
    assert (project / ".local" / "cross-agent-review" / "demo" / head[:12] / "review-report.md").is_file()


def test_default_outputs_are_report_and_pass_marker_only(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output_dir / "review-report.md").is_file()
    assert (output_dir / "review-pass.json").is_file()
    assert not (output_dir / "review-results.json").exists()
    assert not (output_dir / "inputs").exists()
    assert not (output_dir / "prompts").exists()
    assert not (output_dir / "raw").exists()
    assert not (output_dir / "debug").exists()


def test_blocking_findings_write_report_without_results_or_pass_marker(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
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

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", fake, cwd=project)

    assert result.returncode == 1
    assert (output_dir / "review-report.md").is_file()
    assert not (output_dir / "review-pass.json").exists()
    assert not (output_dir / "review-results.json").exists()
    assert not (output_dir / "inputs").exists()


def test_debug_writes_input_prompts_and_raw_under_debug(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    monkeypatch.chdir(project)
    review_input = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=True, sdk_python=None, fake_reviewer_results=None)
    )

    def fake_run(*args, **kwargs):
        payload = json.loads(kwargs["input"])
        raw_dir = Path(payload["raw_dir"])
        raw_dir.mkdir(parents=True, exist_ok=True)
        for role in payload["roles"]:
            (raw_dir / f"{role}.txt").write_text(
                json.dumps({"role": role, "status": "completed", "findings": []}),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=json.dumps([]), stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    module.run_sdk_dispatch_subprocess(review_input, sys.executable)

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


@pytest.mark.parametrize("removed_role", ["risk-review", "tests-and-edge-cases"])
def test_fake_reviewer_results_reject_removed_roles(tmp_path: Path, removed_role: str) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    fake = json.dumps([{"role": removed_role, "status": "completed", "findings": []}])

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", fake, cwd=project)

    assert result.returncode == 1
    assert "invalid_fake_reviewer_role" in result.stdout
    assert removed_role in result.stdout
    assert not (output_dir / "review-pass.json").exists()


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

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

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

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "missing_file" in result.stdout
    assert "missing.md" in result.stdout


def test_invalid_mode_fails(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head, mode="wide")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "invalid_mode: wide" in result.stdout


def test_prepared_inputs_rejects_extra_regular_file(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    write_file(input_file.parent / "plan.md", "old snapshot\n")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

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

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

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

    result = run("run", "--input-file", str(wrong_file), "--fake-reviewer-results", "[]", cwd=project)

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

    result = run("run", "--input-file", str(wrong_input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "invalid_input_file_location" in result.stdout
    assert not (project / "review-pass.json").exists()


def test_change_path_traversal_rejects_input_location(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head, change="../../escape")
    output_dir = input_file.parent.parent

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "invalid_input_file_location" in result.stdout
    assert not (output_dir / "review-pass.json").exists()


def test_invalid_base_ref_fails_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, "0" * 40, head)

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "base_ref_mismatch" in result.stdout


def test_dirty_worktree_outside_runtime_artifacts_rejects_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    write_file(project / "dirty.txt", "dirty\n")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (input_file.parent.parent / "review-pass.json").exists()


def test_renamed_tracked_file_into_runtime_artifacts_rejects_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    git(project, "mv", "app.txt", str(output_dir / "app.txt"))

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

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

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

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
            "--fake-reviewer-results",
            "[]",
        ]
    )
    calls = []

    def fake_ensure_clean_subject(cwd, head_ref, allowed_dirty_paths=()):
        calls.append([Path(path).resolve() for path in allowed_dirty_paths])

    monkeypatch.setattr(module, "ensure_clean_subject", fake_ensure_clean_subject)
    monkeypatch.chdir(project)

    assert module.run_review(parsed) == 0

    assert len(calls) == 3
    assert calls[0] == calls[1] == calls[2]
    assert input_file.resolve() in calls[0]
    assert input_file.parent.parent.resolve() in calls[0]


def test_diff_file_argument_is_not_required(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(*review_args(tmp_path / "repo", head, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 0, result.stdout + result.stderr


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
                fake_reviewer_results=None,
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
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None, fake_reviewer_results=None)
    )

    prompt = module.reviewer_prompt(review_input, "spec-alignment")

    assert f"Read: {input_file}" in prompt
    assert "Review only base_ref...head_ref from the input file." in prompt
    assert "Use spec_file, design_file, and plan_file as requirements context." in prompt
    assert "Manifest file:" not in prompt
    assert "Changed files:" not in prompt
    assert "Spec bytes:" not in prompt
    assert "Design file:" not in prompt
    assert "Tasks file:" not in prompt
    assert "git diff" not in prompt
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
        "schema_json",
        "severity_rubric",
        "role_focus",
    }
    assert captured_values["role"] == "implementation-correctness"
    assert captured_values["input_file_path"] == str(review_input.input_file)
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
    head = init_repo(tmp_path / "repo")
    write_file(tmp_path / "repo" / "dirty.txt", "dirty\n")

    result = run(*review_args(tmp_path / "repo", head, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (tmp_path / "out" / "review-pass.json").exists()


def test_untracked_input_files_in_space_directory_are_allowed(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_dir = project / "review inputs"

    result = run(
        "run",
        "--change",
        "demo",
        "--base-ref",
        head,
        "--head-ref",
        head,
        "--spec-file",
        str(write_file(input_dir / "spec file.md")),
        "--design-file",
        str(write_file(input_dir / "design file.md")),
        "--tasks-file",
        str(write_file(input_dir / "tasks file.md")),
        "--output-dir",
        str(tmp_path / "out"),
        "--fake-reviewer-results",
        "[]",
        cwd=project,
    )

    assert result.returncode == 0
    assert "status: pass" in result.stdout


def test_head_mismatch_rejects_before_dispatch(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(*review_args(tmp_path / "repo", "0" * 40, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 1
    assert "head_ref_mismatch" in result.stdout
    assert head != "0" * 40


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


def test_sdk_python_directory_reports_clear_error_without_traceback(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    sdk_dir = tmp_path / "not-python"
    sdk_dir.mkdir()

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--sdk-python",
        str(sdk_dir),
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert "sdk_unavailable" in result.stdout
    assert "Traceback" not in result.stderr


def test_sdk_python_invalid_file_reports_clear_error_without_traceback(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    invalid_python = write_file(tmp_path / "not-python.exe", "not a real executable\n")

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--sdk-python",
        str(invalid_python),
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert "sdk_unavailable" in result.stdout
    assert "Traceback" not in result.stderr


def test_fake_reviewer_results_bypass_real_sdk_for_tests(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(*review_args(tmp_path / "repo", head, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 0, result.stdout + result.stderr


def test_run_archives_context_snapshots_and_git_manifest_under_output_dir(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    write_file(project / "source.txt", "source body\n")
    git(project, "add", "source.txt")
    git(project, "commit", "-m", "add source")
    base = git(project, "rev-parse", "HEAD")
    write_file(project / "app.txt", "two\n")
    write_file(project / "new file.txt", "new\n")
    shutil.copyfile(project / "source.txt", project / "copy.txt")
    git(project, "add", "app.txt", "copy.txt", "new file.txt")
    git(project, "commit", "-m", "change app")
    head = git(project, "rev-parse", "HEAD")
    input_dir = project / "review inputs"
    output_dir = tmp_path / "out"
    spec_file = write_file(input_dir / "spec file.md", "spec body\n")
    design_file = write_file(input_dir / "design file.md", "design body\n")
    tasks_file = write_file(input_dir / "tasks file.md", "tasks body\n")

    result = run(
        "run",
        "--change",
        "demo",
        "--base-ref",
        base,
        "--head-ref",
        head,
        "--spec-file",
        str(spec_file),
        "--design-file",
        str(design_file),
        "--tasks-file",
        str(tasks_file),
        "--output-dir",
        str(output_dir),
        "--fake-reviewer-results",
        "[]",
        cwd=project,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    inputs_dir = output_dir / "inputs"
    assert {path.name for path in inputs_dir.iterdir()} == {
        "manifest.json",
        "spec.md",
        "design.md",
        "tasks.md",
    }
    assert not (inputs_dir / "diff.patch").exists()
    assert (inputs_dir / "spec.md").read_text(encoding="utf-8") == "spec body\n"
    assert (inputs_dir / "design.md").read_text(encoding="utf-8") == "design body\n"
    assert (inputs_dir / "tasks.md").read_text(encoding="utf-8") == "tasks body\n"
    manifest = json.loads((output_dir / "inputs" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["change"] == "demo"
    assert manifest["base_ref"] == base
    assert manifest["head_ref"] == head
    assert manifest["review_subject"] == {
        "diff_command": f"git diff {base}...{head}",
        "commit_list_command": f"git log {base}..{head} --oneline",
        "changed_files_command": (
            f"git diff --name-status --find-renames --find-copies-harder {base}...{head}"
        ),
        "path_diff_command_template": f"git diff {base}...{head} -- <path>",
        "merge_base": base,
    }
    assert manifest["commits"] == [{"sha": head[:7], "summary": "change app"}]
    assert manifest["changed_files"] == [
        {"path": "app.txt", "status": "modified"},
        {"path": "copy.txt", "status": "copied", "previous_path": "source.txt"},
        {"path": "new file.txt", "status": "added"},
    ]
    assert set(manifest["inputs"]) == {"spec", "design", "tasks"}
    assert set(manifest["inputs"]["spec"]) == {"path", "bytes", "sha256"}
    assert set(manifest["inputs"]["design"]) == {"path", "bytes", "sha256"}
    assert set(manifest["inputs"]["tasks"]) == {"path", "bytes", "sha256"}
    assert not (inputs_dir / "tests.txt").exists()


def test_changed_file_entries_from_git_reports_file_statuses(tmp_path: Path) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    init_repo(project)
    write_file(project / "source.txt", "copy body\n")
    write_file(project / "old.txt", "rename body\n")
    write_file(project / "path with space.txt", "before\n")
    write_file(project / "removed.txt", "delete me\n")
    git(project, "add", "source.txt", "old.txt", "path with space.txt", "removed.txt")
    git(project, "commit", "-m", "base files")
    base = git(project, "rev-parse", "HEAD")
    shutil.copyfile(project / "source.txt", project / "copy.txt")
    git(project, "mv", "old.txt", "new.txt")
    git(project, "rm", "removed.txt")
    write_file(project / "path with space.txt", "after\n")
    git(project, "add", "copy.txt", "path with space.txt")
    git(project, "commit", "-m", "change files")
    head = git(project, "rev-parse", "HEAD")

    assert module.changed_file_entries_from_git(project, base, head) == [
        {"path": "copy.txt", "status": "copied", "previous_path": "source.txt"},
        {"path": "new.txt", "status": "renamed", "previous_path": "old.txt"},
        {"path": "path with space.txt", "status": "modified"},
        {"path": "removed.txt", "status": "deleted"},
    ]


def test_run_accepts_legacy_tests_file_argument_without_snapshotting_it(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    legacy_tests_file = write_file(project / "legacy-tests.txt", "legacy tests\n")
    output_dir = tmp_path / "out"

    result = run(
        *review_args(project, head, output_dir),
        "--tests-file",
        str(legacy_tests_file),
        cwd=project,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (output_dir / "inputs" / "tests.txt").exists()
    module = load_script_module()
    review = module.ReviewInput(
        change="demo",
        mode="convergence",
        base_ref=head,
        head_ref=head,
        spec_file=output_dir / "inputs" / "spec.md",
        design_file=output_dir / "inputs" / "design.md",
        plan_file=output_dir / "inputs" / "plan.md",
        input_file=output_dir / "prepared-inputs" / "review-input.json",
        output_dir=output_dir,
        debug=False,
        sdk_python=None,
        fake_reviewer_results=None,
    )
    assert "legacy tests" not in module.reviewer_prompt(review, "spec-alignment")


def test_run_accepts_missing_legacy_tests_file_argument_without_snapshotting_it(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    output_dir = tmp_path / "out"

    result = run(
        *review_args(project, head, output_dir),
        "--tests-file",
        str(project / "missing-legacy-tests.txt"),
        cwd=project,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (output_dir / "inputs" / "tests.txt").exists()


def test_prompt_contains_review_context(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    args = review_args(tmp_path / "repo", head, tmp_path / "out")
    result = run(*args, "--fake-reviewer-results", "[]", cwd=tmp_path / "repo")

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path / "out" / "review-results.json").read_text(encoding="utf-8"))
    assert data["readonly_tools"]


def test_reviewer_prompt_includes_review_subject_commands_not_diff_file(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "two\n")
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "feature")
    head = git(project, "rev-parse", "HEAD")
    spec_file = write_file(project / "spec.md", "Spec body\n")
    design_file = write_file(project / "design.md", "Design body\n")
    tasks_file = write_file(project / "tasks.md", "Tasks body\n")
    review = module.ReviewInput(
        change="demo-change",
        mode="convergence",
        base_ref=base,
        head_ref=head,
        spec_file=spec_file,
        design_file=design_file,
        plan_file=tasks_file,
        input_file=tmp_path / "review-input.json",
        output_dir=tmp_path / "out",
        debug=False,
        sdk_python=None,
        fake_reviewer_results=None,
    )
    monkeypatch.chdir(project)

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert "Role: spec-alignment" in prompt
    assert "Return only a single JSON object. Do not use Markdown." in prompt
    assert "Change: demo-change" in prompt
    assert f"Base ref: {base}" in prompt
    assert f"Head ref: {head}" in prompt
    assert f"git diff {base}...{head}" in prompt
    assert f"git log {base}..{head} --oneline" in prompt
    assert f"git diff --name-status --find-renames --find-copies-harder {base}...{head}" in prompt
    assert f"git diff {base}...{head} -- <path>" in prompt
    assert "Changed files:" in prompt
    assert "- modified: app.txt" in prompt
    assert f"Spec file: {spec_file}" in prompt
    assert f"Design file: {design_file}" in prompt
    assert f"Tasks file: {tasks_file}" in prompt
    assert "Diff file:" not in prompt
    assert "diff.patch" not in prompt
    assert "Spec body" not in prompt
    assert "Tasks:" not in prompt


def test_reviewer_prompt_references_manifest_and_role_rubrics(tmp_path: Path) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)
    manifest_path = review.output_dir / "inputs" / "manifest.json"

    for role in module.REVIEWER_ROLES:
        prompt = module.reviewer_prompt(review, role)
        assert f"Focus for {role}:" in prompt
        assert "Severity rubric:" in prompt
        assert f"Manifest file: {manifest_path}" in prompt
        assert "Return only a single JSON object" in prompt


def test_reviewer_prompt_template_is_loaded_from_file(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)
    manifest_path = review.output_dir / "inputs" / "manifest.json"
    template = write_file(
        tmp_path / "reviewer-prompt.md",
        "Template marker: {{ role }} / {{ manifest_path }}\n",
    )
    monkeypatch.setattr(module, "REVIEWER_PROMPT_TEMPLATE", template, raising=False)

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert f"Template marker: spec-alignment / {manifest_path}" in prompt


def test_reviewer_prompt_does_not_inline_large_diff_or_context(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    base = init_repo(project)
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
    tasks_file = write_file(project / "tasks.md", large_tasks)
    review = module.ReviewInput(
        change="demo-change",
        mode="convergence",
        base_ref=base,
        head_ref=head,
        spec_file=spec_file,
        design_file=design_file,
        plan_file=tasks_file,
        input_file=tmp_path / "review-input.json",
        output_dir=tmp_path / "out",
        debug=False,
        sdk_python=None,
        fake_reviewer_results=None,
    )
    monkeypatch.chdir(project)

    prompt = module.reviewer_prompt(review, "implementation-correctness")

    assert f"Spec file: {spec_file}" in prompt
    assert f"Spec bytes: {len(spec_file.read_bytes())}" in prompt
    assert "Changed files:" in prompt
    assert "- modified: app.txt" in prompt
    assert repeated_diff_body * 5 not in prompt
    assert "Spec body" not in prompt
    assert "Design body" not in prompt
    assert "Tasks body" not in prompt
    assert "requirement" not in prompt
    assert "design detail" not in prompt
    assert "task detail" not in prompt
    assert "diff.patch" not in prompt
    assert len(prompt) < 5000


def test_sdk_dispatch_subprocess_writes_debug_prompt_artifacts(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path, debug=True)
    captured_payload = None

    def fake_run(*args, **kwargs):
        nonlocal captured_payload
        captured_payload = json.loads(kwargs["input"])
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps([{"role": "spec-alignment", "status": "completed", "findings": []}]),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.run_sdk_dispatch_subprocess(review, sys.executable) == [
        {"role": "spec-alignment", "status": "completed", "findings": []}
    ]

    prompts_dir = review.output_dir / "debug" / "prompts"
    assert {path.name for path in prompts_dir.iterdir()} == {
        "spec-alignment.txt",
        "implementation-correctness.txt",
    }
    assert captured_payload["raw_dir"] == str(review.output_dir / "debug" / "raw")
    assert captured_payload["force_exit"] is True
    assert "Role: spec-alignment" in (prompts_dir / "spec-alignment.txt").read_text(encoding="utf-8")


def test_sdk_dispatch_subprocess_uses_only_two_roles(tmp_path: Path, monkeypatch) -> None:
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
                    {"role": "spec-alignment", "status": "completed", "findings": []},
                    {"role": "implementation-correctness", "status": "completed", "findings": []},
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    results = module.run_sdk_dispatch_subprocess(review_input, sys.executable)

    assert [item["role"] for item in results] == ["spec-alignment", "implementation-correctness"]
    assert captured_payload["roles"] == ["spec-alignment", "implementation-correctness"]
    assert "raw_dir" not in captured_payload


def test_sdk_dispatch_subprocess_returns_role_failures_on_timeout(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path, debug=True)

    def fake_run(*args, **kwargs):
        payload = json.loads(kwargs["input"])
        raw_dir = Path(payload["raw_dir"])
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "implementation-correctness.txt").write_text(
            json.dumps({"role": "implementation-correctness", "status": "completed", "findings": []}),
            encoding="utf-8",
        )
        raise subprocess.TimeoutExpired(args[0], timeout=module.SDK_DISPATCH_TIMEOUT_SECONDS)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    results = module.run_sdk_dispatch_subprocess(review, sys.executable)

    by_role = {result["role"]: result for result in results}
    assert module.SDK_DISPATCH_TIMEOUT_SECONDS < 600
    assert by_role["implementation-correctness"]["status"] == "completed"
    assert by_role["spec-alignment"]["status"] == "failed"
    assert by_role["spec-alignment"]["findings"][0]["summary"] == "Reviewer dispatch timed out"
    assert by_role["spec-alignment"]["findings"][0]["severity"] == "CRITICAL"


def test_sdk_dispatch_writes_raw_reviewer_output(monkeypatch, tmp_path: Path) -> None:
    module = load_script_module()
    raw_dir = tmp_path / "raw"

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            pass

    async def fake_query(*, prompt, options):
        class Message:
            result = json.dumps({"role": "spec-alignment", "status": "completed", "findings": []})

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
                    "readonly_tools": ["Read", "Grep"],
                    "prompts": {"spec-alignment": "prompt"},
                    "raw_dir": str(raw_dir),
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    assert json.loads((raw_dir / "spec-alignment.txt").read_text(encoding="utf-8")) == {
        "role": "spec-alignment",
        "status": "completed",
        "findings": [],
    }


def test_reviewer_prompt_requires_strict_json_contract(tmp_path: Path) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert "Return only a single JSON object. Do not use Markdown." in prompt
    assert "Use only these severity values: CRITICAL, IMPORTANT, WARNING, SUGGESTION." in prompt
    assert 'If there are no issues, return "findings": []' in prompt
    assert "Do not put pass, aligned, ok, or informational observations in findings." in prompt
    assert "Do not use severity aliases such as high, medium, low, minor, or info." in prompt


def test_fake_reviewer_results_reject_non_dict_items(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        json.dumps(["not a reviewer"]),
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert "invalid_fake_reviewer_results" in result.stdout


def test_fake_reviewer_results_reject_missing_required_fields(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        json.dumps([{"role": "spec-alignment", "status": "completed"}]),
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert "invalid_fake_reviewer_results" in result.stdout


def test_reviewer_roles_are_recorded_in_results(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    fake = json.dumps(
        [
            {"role": "spec-alignment", "status": "completed", "findings": []},
            {"role": "implementation-correctness", "status": "completed", "findings": []},
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
    ]
    assert "Edit" not in data["readonly_tools"]
    assert "Write" not in data["readonly_tools"]


def test_sdk_dispatch_disallows_write_and_execution_tools(monkeypatch, capsys) -> None:
    module = load_script_module()
    captured_options = []

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            captured_options.append(kwargs)

    async def fake_query(*, prompt, options):
        class Message:
            result = json.dumps({"role": "spec-alignment", "status": "completed", "findings": []})

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
                    "readonly_tools": ["Read", "Grep"],
                    "prompts": {"spec-alignment": "prompt"},
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    capsys.readouterr()
    assert captured_options
    disallowed = set(captured_options[0]["disallowed_tools"])
    assert {"Edit", "Write", "NotebookEdit", "TodoWrite", "Bash"} <= disallowed


def test_sdk_dispatch_accepts_json_wrapped_in_markdown_fence(monkeypatch, capsys) -> None:
    module = load_script_module()

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            pass

    async def fake_query(*, prompt, options):
        class Message:
            result = (
                "```json\n"
                + json.dumps({"role": "spec-alignment", "status": "completed", "findings": []})
                + "\n```"
            )

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
                    "readonly_tools": ["Read", "Grep"],
                    "prompts": {"spec-alignment": "prompt"},
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    data = json.loads(capsys.readouterr().out)
    assert data == [{"role": "spec-alignment", "status": "completed", "findings": []}]


def test_sdk_dispatch_reports_reviewer_timeout(monkeypatch, capsys) -> None:
    module = load_script_module()

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            pass

    async def fake_query(*, prompt, options):
        class Message:
            result = json.dumps({"role": "spec-alignment", "status": "completed", "findings": []})

        yield Message()

    async def fake_wait_for(awaitable, timeout):
        assert timeout == 480
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise asyncio.TimeoutError

    fake_sdk = types.SimpleNamespace(ClaudeAgentOptions=FakeClaudeAgentOptions, query=fake_query)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "cwd": str(REPO_ROOT),
                    "roles": ["spec-alignment"],
                    "readonly_tools": ["Read", "Grep"],
                    "prompts": {"spec-alignment": "prompt"},
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    data = json.loads(capsys.readouterr().out)
    assert data == [
        {
            "role": "spec-alignment",
            "status": "failed",
            "findings": [
                {
                    "severity": "CRITICAL",
                    "location": "spec-alignment",
                    "summary": "Reviewer timed out",
                    "evidence": "Exceeded 480 seconds.",
                    "recommendation": "Rerun review after checking Claude Agent SDK availability.",
                }
            ],
        }
    ]


def test_sdk_dispatch_retries_transient_reviewer_exception(monkeypatch, capsys) -> None:
    module = load_script_module()
    calls = 0
    sleeps = []

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            pass

    async def fake_query(*, prompt, options):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient sdk failure")

        class Message:
            result = json.dumps({"role": "spec-alignment", "status": "completed", "findings": []})

        yield Message()

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    fake_sdk = types.SimpleNamespace(ClaudeAgentOptions=FakeClaudeAgentOptions, query=fake_query)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "cwd": str(REPO_ROOT),
                    "roles": ["spec-alignment"],
                    "readonly_tools": ["Read", "Grep"],
                    "prompts": {"spec-alignment": "prompt"},
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    data = json.loads(capsys.readouterr().out)
    assert data == [{"role": "spec-alignment", "status": "completed", "findings": []}]
    assert calls == 2
    assert sleeps == [1]


def test_sdk_dispatch_subprocess_timeout_reports_clear_error(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)
    captured_timeout = None

    def fake_run(*args, **kwargs):
        nonlocal captured_timeout
        captured_timeout = kwargs["timeout"]
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    results = module.run_sdk_dispatch_subprocess(review, sys.executable)

    assert captured_timeout == module.SDK_DISPATCH_TIMEOUT_SECONDS
    assert module.SDK_DISPATCH_TIMEOUT_SECONDS == 540
    assert {result["role"] for result in results} == set(module.REVIEWER_ROLES)
    assert all(result["status"] == "failed" for result in results)
    assert all(result["findings"][0]["summary"] == "Reviewer dispatch timed out" for result in results)


def test_sdk_dispatch_subprocess_invalid_stdout_reports_clear_error(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="not json", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    try:
        module.run_sdk_dispatch_subprocess(review, sys.executable)
    except ValueError as exc:
        assert "sdk_dispatch_invalid_output" in str(exc)
        assert "stdout was not valid JSON" in str(exc)
    else:
        raise AssertionError("expected sdk_dispatch_invalid_output")


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


def test_blocking_findings_remove_stale_pass_marker_from_reused_output_dir(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    output_dir = tmp_path / "out"
    head = init_repo(project)

    clean_result = run(*review_args(project, head, output_dir), cwd=project)

    assert clean_result.returncode == 0, clean_result.stdout + clean_result.stderr
    assert (output_dir / "review-pass.json").is_file()

    blocking_fake = json.dumps(
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

    blocking_result = run(
        *review_args(project, head, output_dir),
        "--fake-reviewer-results",
        blocking_fake,
        cwd=project,
    )

    assert blocking_result.returncode == 1
    assert not (output_dir / "review-pass.json").exists()


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


def test_aggregate_blocks_findings_without_severity() -> None:
    module = load_script_module()

    summary = module.aggregate(
        [
            {
                "role": "implementation-correctness",
                "status": "pass",
                "findings": [
                    {
                        "location": "app.txt:1",
                        "issue": None,
                        "detail": "Reviewed behavior matches the spec.",
                    }
                ],
            }
        ],
        [],
    )

    assert summary["blocking_findings"] == 1
    assert summary["findings"][0]["severity"] == "CRITICAL"
    assert summary["findings"][0]["summary"] == "Reviewer output missing severity"


def test_aggregate_blocks_aligned_records_inside_findings() -> None:
    module = load_script_module()

    summary = module.aggregate(
        [
            {
                "role": "spec-alignment",
                "status": "aligned",
                "findings": [
                    {
                        "requirement": "Plugin package",
                        "status": "aligned",
                        "evidence": "Manifest and skill entrypoints match the spec.",
                    }
                ],
            }
        ],
        [],
    )

    assert summary["blocking_findings"] == 1
    assert summary["findings"][0]["severity"] == "CRITICAL"
    assert summary["findings"][0]["summary"] == "Reviewer output missing severity"


def test_aggregate_blocks_severity_aliases() -> None:
    module = load_script_module()

    summary = module.aggregate(
        [
            {
                "role": "spec-alignment",
                "status": "pass-with-findings",
                "findings": [
                    {"severity": "minor", "area": "docs", "description": "Tiny wording note."},
                    {"severity": "medium", "area": "tests", "description": "Add an edge test.", "suggestion": "Cover the boundary."},
                    {"severity": "low", "area": "docs", "description": "Clarify wording.", "suggestion": "Tighten the text."},
                    {"severity": "info", "file": "app.py", "line": 3, "message": "No risk."},
                ],
            }
        ],
        [],
    )

    assert summary["blocking_findings"] == 4
    assert [finding["severity"] for finding in summary["findings"]] == ["CRITICAL", "CRITICAL", "CRITICAL", "CRITICAL"]
    assert {finding["summary"] for finding in summary["findings"]} == {
        "Reviewer output used invalid severity: minor",
        "Reviewer output used invalid severity: medium",
        "Reviewer output used invalid severity: low",
        "Reviewer output used invalid severity: info",
    }


def test_aggregate_treats_pass_dict_findings_with_no_issues_as_non_blocking() -> None:
    module = load_script_module()

    summary = module.aggregate(
        [
            {
                "role": "implementation-correctness",
                "status": "pass",
                "findings": {
                    "spec_compliance": {"verdict": "pass", "details": "Matches spec."},
                    "issues": [],
                },
            }
        ],
        [],
    )

    assert summary["blocking_findings"] == 0
    assert summary["findings"] == []


def test_aggregate_blocks_dict_gaps_with_severity_aliases() -> None:
    module = load_script_module()

    summary = module.aggregate(
        [
            {
                "role": "spec-alignment",
                "status": "pass_with_gaps",
                "findings": {
                    "summary": "Coverage is acceptable with gaps.",
                    "gaps": [
                        {
                            "severity": "medium",
                            "area": "manifest",
                            "detail": "Missing required-field tests.",
                            "recommendation": "Add one regression test.",
                        },
                        {
                            "severity": "low",
                            "area": "cli",
                            "detail": "Unknown command path is not covered.",
                        },
                    ],
                },
            }
        ],
        [],
    )

    assert summary["blocking_findings"] == 2
    assert [finding["severity"] for finding in summary["findings"]] == ["CRITICAL", "CRITICAL"]
    assert {finding["summary"] for finding in summary["findings"]} == {
        "Reviewer output used invalid severity: medium",
        "Reviewer output used invalid severity: low",
    }
