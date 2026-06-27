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


def review_args(
    project: Path,
    head: str,
    *,
    base: str | None = None,
    mode: str = "convergence",
    fake_reviewer_results: str | None = "[]",
) -> list[str]:
    args = [
        "run",
        "--input-file",
        str(write_review_input(project, base or head, head, mode=mode)),
    ]
    if fake_reviewer_results is not None:
        args.extend(["--fake-reviewer-results", fake_reviewer_results])
    return args


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


def test_convergence_pass_marker_records_mode_and_refs(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "two\n")
    write_file(project / "spec.md", "spec body\n")
    write_file(project / "design.md", "design body\n")
    write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    git(project, "add", "app.txt", "spec.md", "design.md", "docs/superpowers/plans/demo.md")
    git(project, "commit", "-m", "feature")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(project, base, head, mode="convergence")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    marker = json.loads((input_file.parent.parent / "review-pass.json").read_text(encoding="utf-8"))
    assert marker["mode"] == "convergence"
    assert marker["base_ref"] == base
    assert marker["head_ref"] == head


def test_endless_pass_marker_records_mode_and_refs(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "two\n")
    write_file(project / "spec.md", "spec body\n")
    write_file(project / "design.md", "design body\n")
    write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    git(project, "add", "app.txt", "spec.md", "design.md", "docs/superpowers/plans/demo.md")
    git(project, "commit", "-m", "feature")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(project, base, head, mode="endless")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    marker = json.loads((input_file.parent.parent / "review-pass.json").read_text(encoding="utf-8"))
    assert marker["mode"] == "endless"
    assert marker["base_ref"] == base
    assert marker["head_ref"] == head


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


def test_debug_timeout_writes_missing_raw_timeout_evidence(tmp_path: Path, monkeypatch) -> None:
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
        raw_path = raw_dir / f"{payload['roles'][0]}.txt"
        raw_path.write_text(
            json.dumps({"role": payload["roles"][0], "status": "completed", "findings": []}),
            encoding="utf-8",
        )
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    reviewers = module.run_sdk_dispatch_subprocess(review_input, sys.executable)

    raw_dir = input_file.parent.parent / "debug" / "raw"
    missing_raw = raw_dir / "implementation-correctness.txt"
    assert (raw_dir / "spec-alignment.txt").is_file()
    assert missing_raw.is_file()
    assert "sdk_dispatch_timeout" in missing_raw.read_text(encoding="utf-8")
    assert [reviewer["status"] for reviewer in reviewers] == ["completed", "failed"]


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


def test_output_dir_root_extra_file_rejects_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    write_file(output_dir / "notes.txt", "not a review runtime artifact\n")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

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

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

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

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

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
    output_dir = input_file.parent.parent
    debug_dir = output_dir / "debug"
    assert set(calls[0]) == {
        input_file.resolve(),
        (output_dir / "review-report.md").resolve(),
        (output_dir / "review-pass.json").resolve(),
        (debug_dir / "review-input.json").resolve(),
        (debug_dir / "prompts" / "spec-alignment.txt").resolve(),
        (debug_dir / "prompts" / "implementation-correctness.txt").resolve(),
        (debug_dir / "raw" / "spec-alignment.txt").resolve(),
        (debug_dir / "raw" / "implementation-correctness.txt").resolve(),
    }
    assert output_dir.resolve() not in calls[0]


def test_diff_file_argument_is_not_required(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)

    result = run(*review_args(project, head), cwd=project)

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
    assert f"git diff {base}...{head}" in prompt
    assert f"git log {base}..{head} --oneline" in prompt
    assert f"git diff --name-status --find-renames --find-copies-harder {base}...{head}" in prompt
    assert "Your entire final response MUST be exactly one JSON object." in prompt
    assert "The first character of the response MUST be `{`." in prompt
    assert "The last character of the response MUST be `}`." in prompt
    assert "Do not write any preface, explanation, summary, or conclusion outside the JSON object." in prompt
    assert "Do not wrap the JSON object in Markdown fences." in prompt
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
        "review_subject_commands",
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
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    write_file(project / "dirty.txt", "dirty\n")

    result = run(*review_args(project, head), cwd=project)

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (project / ".local" / "cross-agent-review" / "demo" / head[:12] / "review-pass.json").exists()


def test_input_files_in_space_directory_are_allowed(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    commit_review_context(project)
    input_dir = project / "review inputs"
    spec_file = write_file(input_dir / "spec file.md")
    design_file = write_file(input_dir / "design file.md")
    plan_file = write_file(input_dir / "plan file.md")
    git(project, "add", "review inputs")
    git(project, "commit", "-m", "add review inputs")
    head = git(project, "rev-parse", "HEAD")
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

    result = run(
        "run",
        "--input-file",
        str(input_file),
        "--fake-reviewer-results",
        "[]",
        cwd=project,
    )

    assert result.returncode == 0
    assert "status: pass" in result.stdout


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


def test_fake_reviewer_results_bypass_real_sdk_for_tests(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)

    result = run(*review_args(project, head), cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr


def test_default_run_does_not_archive_context_snapshots_or_git_manifest(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output_dir / "review-report.md").is_file()
    assert (output_dir / "review-pass.json").is_file()
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


def test_reviewer_prompt_does_not_reference_legacy_tests_file(tmp_path: Path) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert "tests_file" not in prompt
    assert "Tests file:" not in prompt


def test_prompt_contains_review_context(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output_dir / "review-report.md").is_file()
    assert (output_dir / "review-pass.json").is_file()


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
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None, fake_reviewer_results=None)
    )

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert "Role: spec-alignment" in prompt
    assert "Return only a single JSON object. Do not use Markdown." in prompt
    assert f"Read: {input_file}" in prompt
    assert "Review only base_ref...head_ref from the input file." in prompt
    assert "Use spec_file, design_file, and plan_file as requirements context." in prompt
    assert f"git diff {base}...{head}" in prompt
    assert f"git log {base}..{head} --oneline" in prompt
    assert f"git diff --name-status --find-renames --find-copies-harder {base}...{head}" in prompt
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
        assert f"Read: {review.input_file}" in prompt
        assert "Manifest file:" not in prompt
        assert "Return only a single JSON object" in prompt


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
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None, fake_reviewer_results=None)
    )

    prompt = module.reviewer_prompt(review, "implementation-correctness")

    assert f"Read: {input_file}" in prompt
    assert f"git diff {base}...{head}" in prompt
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
    assert "readonly_tools" not in captured_payload
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
    assert "readonly_tools" not in captured_payload
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
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)

    result = run(
        *review_args(project, head, fake_reviewer_results=json.dumps(["not a reviewer"])),
        cwd=project,
    )

    assert result.returncode == 1
    assert "invalid_fake_reviewer_results" in result.stdout


def test_fake_reviewer_results_reject_missing_required_fields(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)

    result = run(
        *review_args(
            project,
            head,
            fake_reviewer_results=json.dumps([{"role": "spec-alignment", "status": "completed"}]),
        ),
        cwd=project,
    )

    assert result.returncode == 1
    assert "invalid_fake_reviewer_results" in result.stdout


def test_fake_reviewer_results_generate_report_and_pass_marker_without_results_file(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    output_dir = project / ".local" / "cross-agent-review" / "demo" / head[:12]
    fake = json.dumps(
        [
            {"role": "spec-alignment", "status": "completed", "findings": []},
            {"role": "implementation-correctness", "status": "completed", "findings": []},
        ]
    )

    result = run(
        *review_args(project, head, fake_reviewer_results=fake),
        cwd=project,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output_dir / "review-report.md").is_file()
    assert (output_dir / "review-pass.json").is_file()


def test_sdk_dispatch_uses_default_sdk_tools(monkeypatch, capsys) -> None:
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
                    "prompts": {"spec-alignment": "prompt"},
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    capsys.readouterr()
    assert captured_options == [{"cwd": str(REPO_ROOT)}]


def test_sdk_dispatch_reports_reviewer_timeout(monkeypatch, capsys, tmp_path: Path) -> None:
    module = load_script_module()
    raw_dir = tmp_path / "raw"

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
                    "prompts": {"spec-alignment": "prompt"},
                    "raw_dir": str(raw_dir),
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
    raw_text = (raw_dir / "spec-alignment.txt").read_text(encoding="utf-8")
    assert "Reviewer timed out" in raw_text
    assert "Exceeded 480 seconds." in raw_text


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
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    output_dir = project / ".local" / "cross-agent-review" / "demo" / head[:12]
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
        *review_args(project, head, fake_reviewer_results=fake),
        cwd=project,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output_dir / "review-report.md").is_file()
    assert (output_dir / "review-pass.json").is_file()


def test_blocking_findings_do_not_generate_pass_marker(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    output_dir = project / ".local" / "cross-agent-review" / "demo" / head[:12]
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
        *review_args(project, head, fake_reviewer_results=fake),
        cwd=project,
    )

    assert result.returncode == 1
    assert (output_dir / "review-report.md").is_file()
    assert not (output_dir / "review-pass.json").exists()


def test_blocking_findings_remove_stale_pass_marker_from_reused_output_dir(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent

    clean_result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

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
        "run",
        "--input-file",
        str(input_file),
        "--fake-reviewer-results",
        blocking_fake,
        cwd=project,
    )

    assert blocking_result.returncode == 1
    assert not (output_dir / "review-pass.json").exists()


def test_report_hash_matches_report(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    head = commit_review_context(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    report = (output_dir / "review-report.md").read_bytes()
    marker = json.loads((output_dir / "review-pass.json").read_text(encoding="utf-8"))
    import hashlib

    assert marker["report_hash"] == hashlib.sha256(report).hexdigest()
    assert marker["head_ref"] == head


def test_duplicate_findings_are_counted_once(tmp_path: Path) -> None:
    module = load_script_module()
    finding = {
        "severity": "IMPORTANT",
        "location": "app.txt:1",
        "summary": "Duplicate",
        "evidence": "Evidence",
        "recommendation": "Fix",
    }
    summary = module.aggregate(
        [
            {"role": "spec-alignment", "status": "completed", "findings": [finding]},
            {"role": "implementation-correctness", "status": "completed", "findings": [finding]},
        ]
    )

    assert summary["blocking_findings"] == 1
    assert summary["findings"] == [finding]


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
        ]
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
        ]
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
        ]
    )

    assert summary["blocking_findings"] == 4
    assert [finding["severity"] for finding in summary["findings"]] == ["CRITICAL", "CRITICAL", "CRITICAL", "CRITICAL"]
    assert {finding["summary"] for finding in summary["findings"]} == {
        "Reviewer output used invalid severity: minor",
        "Reviewer output used invalid severity: medium",
        "Reviewer output used invalid severity: low",
        "Reviewer output used invalid severity: info",
    }
