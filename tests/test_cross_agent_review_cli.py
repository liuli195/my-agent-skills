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
        "--diff-file",
        str(write_file(input_dir / "change diff.patch")),
        "--spec-file",
        str(write_file(input_dir / "spec file.md")),
        "--design-file",
        str(write_file(input_dir / "design file.md")),
        "--tasks-file",
        str(write_file(input_dir / "tasks file.md")),
        "--tests-file",
        str(write_file(input_dir / "tests file.txt")),
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
