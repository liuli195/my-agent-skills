import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "pr-flow"
    / "skills"
    / "pr-flow"
    / "scripts"
    / "pr_flow.py"
)


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd or REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )


def run_with_path(path: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = str(path) + os.pathsep + env.get("PATH", "")
    return run(*args, cwd=cwd, env=env)


def git(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def init_repo(project: Path) -> str:
    project.mkdir()
    git(project, "init")
    git(project, "branch", "-M", "main")
    git(project, "config", "user.email", "test@example.com")
    git(project, "config", "user.name", "Test User")
    (project / "README.md").write_text("# Test Project\n", encoding="utf-8")
    git(project, "add", "README.md")
    git(project, "commit", "-m", "init")
    return git(project, "branch", "--show-current")


def write_fake_gh(bin_dir: Path, *, stdout: str = "", stderr: str = "", exit_code: int = 0) -> Path:
    bin_dir.mkdir()
    fake_script = bin_dir / "gh_fake.py"
    fake_script.write_text(
        "\n".join(
            [
                "import sys",
                f"sys.stdout.write({stdout!r})",
                f"sys.stderr.write({stderr!r})",
                f"raise SystemExit({exit_code})",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if os.name == "nt":
        launcher = bin_dir / "gh.cmd"
        launcher.write_text(
            f'@echo off\n"{sys.executable}" "%~dp0gh_fake.py" %*\nexit /b %ERRORLEVEL%\n',
            encoding="utf-8",
        )
    else:
        launcher = bin_dir / "gh"
        launcher.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/gh_fake.py" "$@"\n',
            encoding="utf-8",
        )
        launcher.chmod(0o755)
    return bin_dir


def pr_view_json(*, checks: list[dict], review_decision: str = "REVIEW_REQUIRED") -> str:
    return (
        json.dumps(
            {
                "number": 12,
                "state": "OPEN",
                "mergeStateStatus": "BLOCKED",
                "reviewDecision": review_decision,
                "headRefName": "feature/example",
                "baseRefName": "main",
                "statusCheckRollup": checks,
            }
        )
        + "\n"
    )


def test_init_creates_config_template_and_gitignore(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("init", "--project", str(project), "--base-branch", "main")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: initialized" in result.stdout
    assert "GitHub Rulesets suggestion" in result.stdout

    config = yaml.safe_load((project / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))
    assert config["defaults"]["baseBranch"] == "main"
    assert config["defaults"]["mergeStrategy"] == "merge"
    assert config["defaults"]["reviewGate"]["mode"] == "github"
    assert config["defaults"]["wait"] == {"timeoutSeconds": 600, "pollSeconds": 15}
    assert config["defaults"]["pr"]["bodyTemplatePath"] == ".pr-flow/pr-template.md"
    assert config["branches"]["main"]["remote"] == "origin"
    assert config["branches"]["main"]["allowHotfixPush"] is False

    template = (project / ".pr-flow" / "pr-template.md").read_text(encoding="utf-8")
    for section in ["Summary", "Scope", "Verification", "Risk", "Rollback"]:
        assert f"## {section}" in template

    assert (project / ".pr-flow" / ".gitignore").read_text(encoding="utf-8") == "/runs/\n/last-status.json\n"


def test_init_does_not_call_gh_api(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("init", "--project", str(project))

    assert result.returncode == 0
    assert "gh api" not in result.stdout
    assert "Rulesets written" not in result.stdout


def test_missing_config_reports_exception_required(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "missing_config" in result.stdout


def test_status_file_is_written_for_stop_state(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    init_result = run("init", "--project", str(project))

    assert init_result.returncode == 0, init_result.stdout + init_result.stderr
    result = run("diagnose", "--project", str(project))

    assert result.returncode == 1
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["reason"] == "git_current_branch_failed"


def test_diagnose_outputs_push_required_without_upstream(tmp_path: Path) -> None:
    project = tmp_path / "project"
    assert init_repo(project) == "main"
    assert run("init", "--project", str(project)).returncode == 0
    git(project, "switch", "-c", "feature/no-upstream")

    result = run("diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: PUSH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "PUSH_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["branch"] == "feature/no-upstream"
    assert status["details"]["reason"] == "missing_upstream"


def test_diagnose_outputs_exception_for_unknown_gh_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    fake_bin = write_fake_gh(tmp_path / "bin", stderr="synthetic gh failure\n", exit_code=42)
    assert init_repo(project) == "main"
    assert run("init", "--project", str(project)).returncode == 0

    result = run_with_path(fake_bin, "diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "gh_pr_view_failed" in result.stdout
    assert "PUSH_REQUIRED" not in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["branch"] == "main"
    assert status["details"]["reason"] == "gh_pr_view_failed"


def test_diagnose_outputs_dispatch_required_for_pending_checks(tmp_path: Path) -> None:
    project = tmp_path / "project"
    fake_bin = write_fake_gh(
        tmp_path / "bin",
        stdout=pr_view_json(checks=[{"name": "ci", "status": "IN_PROGRESS", "conclusion": None}]),
    )
    assert init_repo(project) == "main"
    assert run("init", "--project", str(project)).returncode == 0

    result = run_with_path(fake_bin, "diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["reason"] == "checks_pending"


def test_diagnose_outputs_reply_or_fix_required_for_failing_checks(tmp_path: Path) -> None:
    project = tmp_path / "project"
    fake_bin = write_fake_gh(
        tmp_path / "bin",
        stdout=pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "FAILURE"}]),
    )
    assert init_repo(project) == "main"
    assert run("init", "--project", str(project)).returncode == 0

    result = run_with_path(fake_bin, "diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: REPLY_OR_FIX_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "REPLY_OR_FIX_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["reason"] == "checks_or_review_blocking"


def test_diagnose_outputs_reply_or_fix_required_for_changes_requested(tmp_path: Path) -> None:
    project = tmp_path / "project"
    fake_bin = write_fake_gh(
        tmp_path / "bin",
        stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="CHANGES_REQUESTED",
        ),
    )
    assert init_repo(project) == "main"
    assert run("init", "--project", str(project)).returncode == 0

    result = run_with_path(fake_bin, "diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: REPLY_OR_FIX_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "REPLY_OR_FIX_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["reason"] == "checks_or_review_blocking"


def test_diagnose_outputs_reply_or_fix_required_for_review_required(tmp_path: Path) -> None:
    project = tmp_path / "project"
    fake_bin = write_fake_gh(
        tmp_path / "bin",
        stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="REVIEW_REQUIRED",
        ),
    )
    assert init_repo(project) == "main"
    assert run("init", "--project", str(project)).returncode == 0

    result = run_with_path(fake_bin, "diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: REPLY_OR_FIX_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "REPLY_OR_FIX_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["reason"] == "checks_or_review_blocking"
    assert status["details"]["reviewDecision"] == "REVIEW_REQUIRED"
