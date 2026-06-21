import hashlib
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


def diff_fingerprint(project: Path, base_ref: str = "main", head_ref: str = "feature/example") -> str:
    result = subprocess.run(
        ["git", "diff", "--binary", f"{base_ref}...{head_ref}"],
        cwd=project,
        check=False,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace")
    return f"sha256:{hashlib.sha256(result.stdout).hexdigest()}"


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


def init_feature_branch(project: Path) -> None:
    assert init_repo(project) == "main"
    git(project, "checkout", "-b", "feature/example")
    (project / "README.md").write_text("# Test Project\n\nFeature change\n", encoding="utf-8")
    git(project, "add", "README.md")
    git(project, "commit", "-m", "feature")


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


def write_fake_gh_sequence(bin_dir: Path, responses: list[dict[str, object]]) -> tuple[Path, Path]:
    bin_dir.mkdir()
    responses_path = bin_dir / "responses.json"
    calls_path = bin_dir / "calls.json"
    responses_path.write_text(json.dumps(responses), encoding="utf-8")
    calls_path.write_text("[]", encoding="utf-8")
    fake_script = bin_dir / "gh_fake_sequence.py"
    fake_script.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "from pathlib import Path",
                f"responses_path = Path({str(responses_path)!r})",
                f"calls_path = Path({str(calls_path)!r})",
                "responses = json.loads(responses_path.read_text(encoding='utf-8'))",
                "calls = json.loads(calls_path.read_text(encoding='utf-8'))",
                "index = len(calls)",
                "calls.append(sys.argv[1:])",
                "calls_path.write_text(json.dumps(calls, indent=2), encoding='utf-8')",
                "if index >= len(responses):",
                "    sys.stderr.write('unexpected gh call: ' + ' '.join(sys.argv[1:]) + '\\n')",
                "    raise SystemExit(99)",
                "response = responses[index]",
                "sys.stdout.write(str(response.get('stdout', '')))",
                "sys.stderr.write(str(response.get('stderr', '')))",
                "raise SystemExit(int(response.get('exit_code', 0)))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if os.name == "nt":
        launcher = bin_dir / "gh.cmd"
        launcher.write_text(
            f'@echo off\n"{sys.executable}" "%~dp0gh_fake_sequence.py" %*\nexit /b %ERRORLEVEL%\n',
            encoding="utf-8",
        )
    else:
        launcher = bin_dir / "gh"
        launcher.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/gh_fake_sequence.py" "$@"\n',
            encoding="utf-8",
        )
        launcher.chmod(0o755)
    return bin_dir, calls_path


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


def configure_complete(
    project: Path,
    *,
    review_mode: str,
    evidence_path: str | None = None,
) -> None:
    assert run("init", "--project", str(project)).returncode == 0
    config_path = project / ".pr-flow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["defaults"]["wait"] = {"timeoutSeconds": 0, "pollSeconds": 0}
    config["defaults"]["reviewGate"] = {"mode": review_mode}
    if evidence_path is not None:
        config["defaults"]["reviewGate"]["evidencePath"] = evidence_path
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_review_pass(
    project: Path,
    relative_path: str = ".pr-flow/review-pass.json",
    *,
    fingerprint: str | None = None,
) -> None:
    evidence_path = project / relative_path
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(
            {
                "status": "pass",
                "base_ref": "main",
                "head_ref": "feature/example",
                "diff_fingerprint": fingerprint or diff_fingerprint(project),
                "blocking_findings": 0,
            }
        ),
        encoding="utf-8",
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


def test_complete_creates_pr_when_none_exists(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    configure_complete(project, review_mode="github")
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stderr": "no pull requests found\n", "exit_code": 1},
            {"stdout": "https://github.example/test/repo/pull/12\n"},
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="APPROVED")},
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="APPROVED")},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: ready_to_merge" in result.stdout
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls[0][:2] == ["pr", "view"]
    assert calls[1][:2] == ["pr", "create"]


def test_complete_skip_review_gate_ignores_github_changes_requested(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    configure_complete(project, review_mode="skip")
    fake_bin, _calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="CHANGES_REQUESTED")},
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="CHANGES_REQUESTED")},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: ready_to_merge" in result.stdout


def test_complete_github_review_gate_blocks_changes_requested(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    configure_complete(project, review_mode="github")
    fake_bin, _calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="CHANGES_REQUESTED")},
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="CHANGES_REQUESTED")},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 1
    assert "status: REPLY_OR_FIX_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "REPLY_OR_FIX_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "review_gate_blocking"


def test_complete_wait_timeout_zero_reports_pending_checks_without_sleep(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    configure_complete(project, review_mode="skip")
    fake_bin, _calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "IN_PROGRESS", "conclusion": None}], review_decision="APPROVED")},
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "IN_PROGRESS", "conclusion": None}], review_decision="APPROVED")},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "checks_pending"


def test_complete_local_review_gate_accepts_review_pass_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    init_feature_branch(project)
    configure_complete(project, review_mode="local", evidence_path=".pr-flow/review-pass.json")
    write_review_pass(project)
    fake_bin, _calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="CHANGES_REQUESTED")},
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="CHANGES_REQUESTED")},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: ready_to_merge" in result.stdout


def test_complete_local_review_gate_blocks_stale_diff_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    init_feature_branch(project)
    configure_complete(project, review_mode="local", evidence_path=".pr-flow/review-pass.json")
    write_review_pass(project, fingerprint="sha256:" + "0" * 64)
    fake_bin, _calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="CHANGES_REQUESTED")},
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="CHANGES_REQUESTED")},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 1
    assert "status: REPLY_OR_FIX_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "REPLY_OR_FIX_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "local_review_evidence_failed"


def test_complete_dual_review_gate_requires_github_and_local_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    init_feature_branch(project)
    configure_complete(project, review_mode="dual", evidence_path=".pr-flow/review-pass.json")
    write_review_pass(project)
    fake_bin, _calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="APPROVED")},
            {"stdout": pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="APPROVED")},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: ready_to_merge" in result.stdout
