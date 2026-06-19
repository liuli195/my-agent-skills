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
    assert "status: ready" in result.stdout


def test_head_mismatch_rejects_before_dispatch(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(*review_args(tmp_path / "repo", "0" * 40, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 1
    assert "head_ref_mismatch" in result.stdout
    assert head != "0" * 40
