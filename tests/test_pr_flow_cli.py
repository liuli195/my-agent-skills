import hashlib
import importlib.util
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


def load_pr_flow_module():
    spec = importlib.util.spec_from_file_location("pr_flow_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    body_files_path = bin_dir / "body_files.json"
    responses_path.write_text(json.dumps(responses), encoding="utf-8")
    calls_path.write_text("[]", encoding="utf-8")
    body_files_path.write_text("[]", encoding="utf-8")
    fake_script = bin_dir / "gh_fake_sequence.py"
    fake_script.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "from pathlib import Path",
                f"responses_path = Path({str(responses_path)!r})",
                f"calls_path = Path({str(calls_path)!r})",
                f"body_files_path = Path({str(body_files_path)!r})",
                "responses = json.loads(responses_path.read_text(encoding='utf-8'))",
                "calls = json.loads(calls_path.read_text(encoding='utf-8'))",
                "body_files = json.loads(body_files_path.read_text(encoding='utf-8'))",
                "index = len(calls)",
                "calls.append(sys.argv[1:])",
                "calls_path.write_text(json.dumps(calls, indent=2), encoding='utf-8')",
                "if '--body-file' in sys.argv[1:]:",
                "    body_index = sys.argv.index('--body-file') + 1",
                "    body_path = Path(sys.argv[body_index])",
                "    body_files.append({'args': sys.argv[1:], 'body': body_path.read_text(encoding='utf-8')})",
                "    body_files_path.write_text(json.dumps(body_files, indent=2), encoding='utf-8')",
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


def pr_view_json(
    *,
    checks: list[dict],
    review_decision: str = "REVIEW_REQUIRED",
    head_oid: str | None = None,
    is_draft: bool = False,
) -> str:
    payload = {
        "number": 12,
        "state": "OPEN",
        "isDraft": is_draft,
        "mergeStateStatus": "BLOCKED",
        "reviewDecision": review_decision,
        "headRefName": "feature/example",
        "baseRefName": "main",
        "statusCheckRollup": checks,
    }
    if head_oid is not None:
        payload["headRefOid"] = head_oid
    return (
        json.dumps(payload)
        + "\n"
    )


def cleanup_pr_view_json(
    *,
    state: str = "MERGED",
    head_ref: str = "feature/example",
    base_ref: str = "main",
) -> str:
    return (
        json.dumps(
            {
                "number": 12,
                "state": state,
                "headRefName": head_ref,
                "baseRefName": base_ref,
                "headRepositoryOwner": {"login": "test-owner"},
            }
        )
        + "\n"
    )


def git_bare(remote: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "--git-dir", str(remote), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def git_bare_result(remote: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "--git-dir", str(remote), *args],
        check=False,
        text=True,
        capture_output=True,
    )


def init_cleanup_project(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    remote_init = subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert remote_init.returncode == 0, remote_init.stdout + remote_init.stderr

    project = tmp_path / "project"
    assert init_repo(project) == "main"
    init_result = run("init", "--project", str(project))
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr
    git(project, "add", ".pr-flow")
    git(project, "commit", "-m", "configure pr flow")
    git(project, "remote", "add", "origin", str(remote))
    git(project, "push", "-u", "origin", "main")

    git(project, "checkout", "-b", "feature/example")
    (project / "README.md").write_text("# Test Project\n\nFeature change\n", encoding="utf-8")
    git(project, "add", "README.md")
    git(project, "commit", "-m", "feature")
    git(project, "push", "-u", "origin", "feature/example")

    integrator = tmp_path / "integrator"
    clone_result = subprocess.run(
        ["git", "clone", str(remote), str(integrator)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert clone_result.returncode == 0, clone_result.stdout + clone_result.stderr
    git(integrator, "config", "user.email", "test@example.com")
    git(integrator, "config", "user.name", "Test User")
    git(integrator, "checkout", "-B", "main", "origin/main")
    git(integrator, "merge", "--ff-only", "origin/feature/example")
    git(integrator, "push", "origin", "main")

    git(project, "checkout", "feature/example")
    return project, remote


def init_complete_project(
    tmp_path: Path,
    *,
    review_mode: str = "github",
    merge_strategy: str = "merge",
    evidence_path: str | None = None,
) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    remote_init = subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert remote_init.returncode == 0, remote_init.stdout + remote_init.stderr

    project = tmp_path / "project"
    assert init_repo(project) == "main"
    configure_complete(
        project,
        review_mode=review_mode,
        merge_strategy=merge_strategy,
        evidence_path=evidence_path,
    )
    git(project, "add", ".pr-flow")
    git(project, "commit", "-m", "configure pr flow")
    git(project, "remote", "add", "origin", str(remote))
    git(project, "push", "-u", "origin", "main")

    git(project, "checkout", "-b", "feature/example")
    (project / "README.md").write_text("# Test Project\n\nFeature change\n", encoding="utf-8")
    git(project, "add", "README.md")
    git(project, "commit", "-m", "feature")
    git(project, "push", "-u", "origin", "feature/example")

    integrator = tmp_path / "integrator"
    clone_result = subprocess.run(
        ["git", "clone", str(remote), str(integrator)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert clone_result.returncode == 0, clone_result.stdout + clone_result.stderr
    git(integrator, "config", "user.email", "test@example.com")
    git(integrator, "config", "user.name", "Test User")
    git(integrator, "checkout", "-B", "main", "origin/main")
    git(integrator, "merge", "--ff-only", "origin/feature/example")
    git(integrator, "push", "origin", "main")

    git(project, "checkout", "feature/example")
    return project, remote


def passing_pr_view_json(project: Path, *, review_decision: str = "APPROVED") -> str:
    return pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision=review_decision,
        head_oid=git(project, "rev-parse", "HEAD"),
    )


def captured_body_files(fake_bin: Path) -> list[dict[str, str]]:
    return json.loads((fake_bin / "body_files.json").read_text(encoding="utf-8"))


def assert_cleanup_exception(project: Path, result: subprocess.CompletedProcess[str], reason: str) -> None:
    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "cleanup"
    assert status["details"]["reason"] == reason


def configure_complete(
    project: Path,
    *,
    review_mode: str,
    merge_strategy: str = "merge",
    evidence_path: str | None = None,
) -> None:
    assert run("init", "--project", str(project)).returncode == 0
    config_path = project / ".pr-flow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["defaults"]["wait"] = {"timeoutSeconds": 0, "pollSeconds": 0}
    config["defaults"]["mergeStrategy"] = merge_strategy
    config["defaults"]["reviewGate"] = {"mode": review_mode}
    if evidence_path is not None:
        config["defaults"]["reviewGate"]["evidencePath"] = evidence_path
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


HOTFIX_PHRASE = "ship-hotfix"


def configure_hotfix(
    project: Path,
    *,
    target: str = "main",
    allow_hotfix: bool = True,
    verify_command: str = "git rev-parse HEAD",
) -> None:
    assert run("init", "--project", str(project)).returncode == 0
    config_path = project / ".pr-flow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config.setdefault("authorization", {})
    config["authorization"]["phraseHashAlgorithm"] = "md5"
    config["authorization"]["phraseHash"] = hashlib.md5(HOTFIX_PHRASE.encode("utf-8")).hexdigest()
    config["defaults"]["remote"] = "origin"
    config["defaults"]["hotfix"] = {"verifyCommand": verify_command}
    config.setdefault("branches", {}).setdefault(target, {})
    config["branches"][target]["allowHotfixPush"] = allow_hotfix
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


def init_hotfix_project(
    tmp_path: Path,
    *,
    allow_hotfix: bool = True,
    verify_command: str = "git rev-parse HEAD",
) -> tuple[Path, Path, str]:
    remote = tmp_path / "remote.git"
    remote_init = subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert remote_init.returncode == 0, remote_init.stdout + remote_init.stderr

    project = tmp_path / "project"
    assert init_repo(project) == "main"
    configure_hotfix(project, allow_hotfix=allow_hotfix, verify_command=verify_command)
    git(project, "add", ".pr-flow")
    git(project, "commit", "-m", "configure pr flow")
    git(project, "remote", "add", "origin", str(remote))
    git(project, "push", "-u", "origin", "main")
    before_commit = git_bare(remote, "rev-parse", "refs/heads/main")

    git(project, "checkout", "-b", "hotfix/example", "origin/main")
    (project / "README.md").write_text("# Test Project\n\nHotfix change\n", encoding="utf-8")
    git(project, "add", "README.md")
    git(project, "commit", "-m", "hotfix")
    return project, remote, before_commit


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
    assert config["defaults"]["reviewGate"]["evidencePath"] == ".pr-flow/review-pass.json"
    assert config["defaults"]["hotfix"]["verifyCommand"] == ".\\.venv\\Scripts\\python.exe -m pytest"
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
    assert "push current branch before continuing" in result.stdout


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


def test_diagnose_on_base_branch_without_pr_reports_gh_pr_view_failed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    fake_bin = write_fake_gh(tmp_path / "bin", stderr="no pull requests found for branch\n", exit_code=1)
    assert init_repo(project) == "main"
    assert run("init", "--project", str(project)).returncode == 0

    result = run_with_path(fake_bin, "diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "gh_pr_view_failed" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["branch"] == "main"
    assert status["details"]["baseBranch"] == "main"
    assert status["details"]["reason"] == "gh_pr_view_failed"
    assert "no pull requests found" in status["details"]["stderr"]


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


def test_diagnose_outputs_ready_when_no_stop_state_remains(tmp_path: Path) -> None:
    project = tmp_path / "project"
    fake_bin = write_fake_gh(
        tmp_path / "bin",
        stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="",
        ),
    )
    assert init_repo(project) == "main"
    assert run("init", "--project", str(project)).returncode == 0

    result = run_with_path(fake_bin, "diagnose", "--project", str(project))

    assert result.returncode == 0
    assert "status: ready" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "ready"
    assert status["command"] == "diagnose"
    assert status["details"]["reason"] == "ready_to_complete"
    assert status["details"]["nextCommand"] == "complete"


def test_diagnose_outputs_dispatch_required_for_draft_pr(tmp_path: Path) -> None:
    project = tmp_path / "project"
    fake_bin = write_fake_gh(
        tmp_path / "bin",
        stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="",
            is_draft=True,
        ),
    )
    assert init_repo(project) == "main"
    assert run("init", "--project", str(project)).returncode == 0

    result = run_with_path(fake_bin, "diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    assert "pr_is_draft" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["reason"] == "pr_is_draft"
    assert status["details"]["nextCommand"] == "gh pr ready"


def test_complete_creates_pr_when_none_exists_then_merges_and_cleans_up(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path)
    head_oid = git(project, "rev-parse", "HEAD")
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stderr": "no pull requests found\n", "exit_code": 1},
            {"stdout": "https://github.example/test/repo/pull/12\n"},
            {"stdout": passing_pr_view_json(project)},
            {"stdout": passing_pr_view_json(project)},
            {"stdout": ""},
            {"stdout": cleanup_pr_view_json()},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls[0][:2] == ["pr", "view"]
    assert calls[1][:2] == ["pr", "create"]
    assert calls[4] == ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid]
    assert calls[5] == ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"]


def test_complete_merges_locked_head_then_runs_cleanup_in_order(tmp_path: Path) -> None:
    project, remote = init_complete_project(tmp_path)
    head_oid = git(project, "rev-parse", "HEAD")
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": passing_pr_view_json(project)},
            {"stdout": passing_pr_view_json(project)},
            {"stdout": ""},
            {"stdout": cleanup_pr_view_json()},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert git(project, "branch", "--show-current") == "main"
    assert git_bare_result(remote, "show-ref", "--verify", "refs/heads/feature/example").returncode != 0
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls == [
        [
            "pr",
            "view",
            "--json",
            "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid",
        ],
        [
            "pr",
            "view",
            "--json",
            "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid",
        ],
        ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid],
        ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"],
    ]
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "cleanup_complete"
    assert status["command"] == "cleanup"


def test_complete_returns_cleanup_stop_when_cleanup_fails_after_merge(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path)
    head_oid = git(project, "rev-parse", "HEAD")
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": passing_pr_view_json(project)},
            {"stdout": passing_pr_view_json(project)},
            {"stdout": ""},
            {"stdout": cleanup_pr_view_json(state="OPEN")},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 1
    assert "status: merge_complete" in result.stdout
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "pr_not_merged" in result.stdout
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls[2] == ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid]
    assert calls[3] == ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"]
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "cleanup"
    assert status["details"]["reason"] == "pr_not_merged"
    assert "pr-flow-cleanup" in status["details"]["recovery"]


def test_complete_stops_when_pr_sync_fails_instead_of_using_stale_pr(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path)
    fake_bin, _calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": passing_pr_view_json(project)},
            {"stderr": "rate limited\n", "exit_code": 1},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "gh_pr_view_failed" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "gh_pr_view_failed"
    assert "rate limited" in status["details"]["stderr"]


def test_complete_uses_configured_merge_strategy_flag(tmp_path: Path) -> None:
    for strategy, expected_flag in [("merge", "--merge"), ("squash", "--squash"), ("rebase", "--rebase")]:
        case_tmp = tmp_path / strategy
        case_tmp.mkdir()
        project, _remote = init_complete_project(case_tmp, merge_strategy=strategy)
        head_oid = git(project, "rev-parse", "HEAD")
        fake_bin, calls_path = write_fake_gh_sequence(
            case_tmp / "bin",
            [
                {"stdout": passing_pr_view_json(project)},
                {"stdout": passing_pr_view_json(project)},
                {"stdout": ""},
                {"stdout": cleanup_pr_view_json()},
            ],
        )

        result = run_with_path(fake_bin, "complete", "--project", str(project))

        assert result.returncode == 0, strategy + result.stdout + result.stderr
        calls = json.loads(calls_path.read_text(encoding="utf-8"))
        assert calls[2] == ["pr", "merge", "12", expected_flag, "--match-head-commit", head_oid]


def test_complete_rejects_when_head_moved_before_merge(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path)
    moved_head_oid = "0" * 40
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {
                "stdout": pr_view_json(
                    checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                    review_decision="APPROVED",
                    head_oid=moved_head_oid,
                )
            },
            {
                "stdout": pr_view_json(
                    checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                    review_decision="APPROVED",
                    head_oid=moved_head_oid,
                )
            },
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls == [
        [
            "pr",
            "view",
            "--json",
            "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid",
        ],
        [
            "pr",
            "view",
            "--json",
            "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid",
        ],
    ]
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "head_moved"


def test_complete_rejects_missing_head_ref_oid_without_merge(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path)
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {
                "stdout": pr_view_json(
                    checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                    review_decision="APPROVED",
                )
            },
            {
                "stdout": pr_view_json(
                    checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                    review_decision="APPROVED",
                )
            },
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls == [
        [
            "pr",
            "view",
            "--json",
            "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid",
        ],
        [
            "pr",
            "view",
            "--json",
            "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid",
        ],
    ]
    assert all(call[:3] != ["pr", "merge", "12"] for call in calls)
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "missing_head_ref_oid"


def test_complete_rejects_current_branch_that_does_not_match_pr_head(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path)
    git(project, "checkout", "-b", "feature/other")
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            { "stdout": passing_pr_view_json(project) },
            { "stdout": passing_pr_view_json(project) },
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "current_branch_mismatch" in result.stdout
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert all(call[:2] != ["pr", "merge"] for call in calls)
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "current_branch_mismatch"
    assert status["details"]["currentBranch"] == "feature/other"
    assert status["details"]["headRefName"] == "feature/example"


def test_complete_reports_exception_when_gh_pr_merge_fails(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path)
    head_oid = git(project, "rev-parse", "HEAD")
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": passing_pr_view_json(project)},
            {"stdout": passing_pr_view_json(project)},
            {"stderr": "merge failed\n", "exit_code": 1},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "gh_pr_merge_failed" in result.stdout
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls[2] == ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid]
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "gh_pr_merge_failed"
    assert status["details"]["stderr"] == "merge failed"


def test_complete_rejects_unknown_merge_strategy(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path, merge_strategy="octopus")
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": passing_pr_view_json(project)},
            {"stdout": passing_pr_view_json(project)},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert len(calls) == 2
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "unknown_merge_strategy"


def test_complete_skip_review_gate_ignores_github_changes_requested(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path, review_mode="skip")
    fake_bin, _calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": passing_pr_view_json(project, review_decision="CHANGES_REQUESTED")},
            {"stdout": passing_pr_view_json(project, review_decision="CHANGES_REQUESTED")},
            {"stdout": ""},
            {"stdout": cleanup_pr_view_json()},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout


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
    evidence_path = tmp_path / "review-pass.json"
    project, _remote = init_complete_project(tmp_path, review_mode="local", evidence_path=str(evidence_path))
    write_review_pass(project, str(evidence_path))
    fake_bin, _calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": passing_pr_view_json(project, review_decision="CHANGES_REQUESTED")},
            {"stdout": passing_pr_view_json(project, review_decision="CHANGES_REQUESTED")},
            {"stdout": ""},
            {"stdout": cleanup_pr_view_json()},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout


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
    evidence_path = tmp_path / "review-pass.json"
    project, _remote = init_complete_project(tmp_path, review_mode="dual", evidence_path=str(evidence_path))
    write_review_pass(project, str(evidence_path))
    fake_bin, _calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": passing_pr_view_json(project)},
            {"stdout": passing_pr_view_json(project)},
            {"stdout": ""},
            {"stdout": cleanup_pr_view_json()},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout


def test_complete_dual_review_gate_blocks_github_changes_requested_even_with_local_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "review-pass.json"
    project, _remote = init_complete_project(tmp_path, review_mode="dual", evidence_path=str(evidence_path))
    write_review_pass(project, str(evidence_path))
    fake_bin, _calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": passing_pr_view_json(project, review_decision="CHANGES_REQUESTED")},
            {"stdout": passing_pr_view_json(project, review_decision="CHANGES_REQUESTED")},
        ],
    )

    result = run_with_path(fake_bin, "complete", "--project", str(project))

    assert result.returncode == 1
    assert "status: REPLY_OR_FIX_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "REPLY_OR_FIX_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "review_gate_blocking"
    assert status["details"]["reviewGateMode"] == "dual"
    assert status["details"]["reviewDecision"] == "CHANGES_REQUESTED"


def test_tweak_requires_reason(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("tweak", "--project", str(project))

    assert result.returncode == 2
    assert "status: not_implemented" not in result.stdout
    assert "status: tweak_requires_reason" in result.stdout


def test_bare_tweak_requires_project() -> None:
    result = run("tweak")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "required:" in result.stderr
    assert "--project" in result.stderr


def test_tweak_creates_pr_when_none_exists_and_writes_body(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path)
    head_oid = git(project, "rev-parse", "HEAD")
    reason = "small docs polish"
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stderr": "no pull requests found\n", "exit_code": 1},
            {"stdout": "https://github.example/test/repo/pull/12\n"},
            {"stdout": passing_pr_view_json(project)},
            {"stdout": passing_pr_view_json(project)},
            {"stdout": ""},
            {"stdout": ""},
            {"stdout": cleanup_pr_view_json()},
        ],
    )

    result = run_with_path(fake_bin, "tweak", "--project", str(project), "--reason", reason)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls[0][:2] == ["pr", "view"]
    assert calls[1][:2] == ["pr", "create"]
    assert calls[3][:2] == ["pr", "view"]
    assert calls[4][:3] == ["pr", "edit", "12"]
    assert "--body-file" in calls[4]
    assert calls[5] == ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid]
    assert calls[6] == ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"]
    body_records = captured_body_files(fake_bin)
    assert len(body_records) == 1
    assert (
        "## Tweak Path\n\n"
        "Review gate skipped for non-bug small change.\n\n"
        f"Reason: {reason}\n"
    ) in body_records[0]["body"]


def test_tweak_skips_review_gate_for_changes_requested_then_merges_and_cleans_up(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path, review_mode="github")
    head_oid = git(project, "rev-parse", "HEAD")
    reason = "rename helper only"
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": passing_pr_view_json(project, review_decision="CHANGES_REQUESTED")},
            {"stdout": passing_pr_view_json(project, review_decision="CHANGES_REQUESTED")},
            {"stdout": ""},
            {"stdout": ""},
            {"stdout": cleanup_pr_view_json()},
        ],
    )

    result = run_with_path(fake_bin, "tweak", "--project", str(project), "--reason", reason)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert "REPLY_OR_FIX_REQUIRED" not in result.stdout
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls == [
        [
            "pr",
            "view",
            "--json",
            "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid",
        ],
        [
            "pr",
            "view",
            "--json",
            "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid",
        ],
        ["pr", "edit", "12", "--body-file", calls[2][4]],
        ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid],
        ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"],
    ]


def test_tweak_pending_checks_report_dispatch_required(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    configure_complete(project, review_mode="github")
    reason = "format-only cleanup"
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {
                "stdout": pr_view_json(
                    checks=[{"name": "ci", "status": "IN_PROGRESS", "conclusion": None}],
                    review_decision="CHANGES_REQUESTED",
                )
            },
            {
                "stdout": pr_view_json(
                    checks=[{"name": "ci", "status": "IN_PROGRESS", "conclusion": None}],
                    review_decision="CHANGES_REQUESTED",
                )
            },
            {"stdout": ""},
        ],
    )

    result = run_with_path(fake_bin, "tweak", "--project", str(project), "--reason", reason)

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls[2][:3] == ["pr", "edit", "12"]
    assert all(call[:2] != ["pr", "merge"] for call in calls)
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "tweak"
    assert status["details"]["reason"] == "checks_pending"
    body_records = captured_body_files(fake_bin)
    assert len(body_records) == 1
    assert f"Reason: {reason}\n" in body_records[0]["body"]


def test_hotfix_rejects_authorization_phrase_mismatch_without_leaking_phrase(tmp_path: Path) -> None:
    project, _remote, _before_commit = init_hotfix_project(tmp_path)
    wrong_phrase = "wrong-secret"

    result = run(
        "hotfix",
        "--project",
        str(project),
        "--target",
        "main",
        "--authorization-phrase",
        wrong_phrase,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "authorization_phrase_mismatch" in result.stdout
    assert wrong_phrase not in result.stdout
    assert wrong_phrase not in result.stderr
    status_text = (project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8")
    assert wrong_phrase not in status_text
    status = json.loads(status_text)
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "authorization_phrase_mismatch"


def test_hotfix_missing_authorization_config_does_not_run_verify_command(tmp_path: Path, monkeypatch) -> None:
    pr_flow = load_pr_flow_module()
    project, remote, before_commit = init_hotfix_project(tmp_path)
    config_path = project / ".pr-flow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config.pop("authorization")
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    git(project, "add", ".pr-flow/config.yaml")
    git(project, "commit", "-m", "remove authorization config")
    verify_calls = []

    def fake_verify(project_arg: Path, command: str) -> subprocess.CompletedProcess[str]:
        verify_calls.append((project_arg, command))
        return subprocess.CompletedProcess(command, 0, "verified", "")

    monkeypatch.setattr(pr_flow, "run_hotfix_verify_command", fake_verify)

    result = pr_flow.run_hotfix(
        pr_flow.argparse.Namespace(
            project=project,
            target="main",
            authorization_phrase=HOTFIX_PHRASE,
            command="hotfix",
        )
    )

    assert result == 1
    assert verify_calls == []
    assert git_bare(remote, "rev-parse", "refs/heads/main") == before_commit
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "authorization_phrase_missing"


def test_hotfix_runs_verify_command_before_authorization_phrase_check(tmp_path: Path) -> None:
    project, remote, before_commit = init_hotfix_project(
        tmp_path,
        verify_command="git rev-parse refs/heads/does-not-exist",
    )
    wrong_phrase = "wrong-secret"

    result = run(
        "hotfix",
        "--project",
        str(project),
        "--target",
        "main",
        "--authorization-phrase",
        wrong_phrase,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "authorization_phrase_mismatch" not in result.stdout
    assert git_bare(remote, "rev-parse", "refs/heads/main") == before_commit
    status_text = (project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8")
    assert wrong_phrase not in status_text
    status = json.loads(status_text)
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "hotfix_verify_failed"


def test_hotfix_verify_command_preserves_windows_backslash_executable_path(tmp_path: Path, monkeypatch) -> None:
    pr_flow = load_pr_flow_module()
    calls = []

    def fake_run(command_args, **kwargs):
        calls.append((command_args, kwargs))
        return subprocess.CompletedProcess(command_args, 0, "", "")

    monkeypatch.setattr(pr_flow.subprocess, "run", fake_run)

    result = pr_flow.run_hotfix_verify_command(tmp_path, r".venv\Scripts\python.exe -m pytest")

    assert result.returncode == 0
    assert calls == [
        (
            [r".venv\Scripts\python.exe", "-m", "pytest"],
            {
                "cwd": tmp_path,
                "check": False,
                "text": True,
                "capture_output": True,
                "shell": False,
            },
        )
    ]


def test_hotfix_verify_command_uses_shlex_on_non_windows(tmp_path: Path, monkeypatch) -> None:
    pr_flow = load_pr_flow_module()
    calls = []

    def fake_run(command_args, **kwargs):
        calls.append((command_args, kwargs))
        return subprocess.CompletedProcess(command_args, 0, "", "")

    monkeypatch.setattr(pr_flow.os, "name", "posix")
    monkeypatch.setattr(pr_flow.subprocess, "run", fake_run)

    result = pr_flow.run_hotfix_verify_command(tmp_path, "python -m pytest")

    assert result.returncode == 0
    assert calls[0][0] == ["python", "-m", "pytest"]
    assert calls[0][1]["shell"] is False


def test_hotfix_requires_target_for_bare_command() -> None:
    result = run("hotfix")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "required:" in result.stderr
    assert "--target" in result.stderr


def test_hotfix_requires_target_when_project_and_authorization_are_supplied(tmp_path: Path) -> None:
    project, _remote, _before_commit = init_hotfix_project(tmp_path)

    result = run(
        "hotfix",
        "--project",
        str(project),
        "--authorization-phrase",
        HOTFIX_PHRASE,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "required:" in result.stderr
    assert "--target" in result.stderr


def test_hotfix_rejects_target_branch_without_allow_hotfix_push(tmp_path: Path) -> None:
    project, _remote, _before_commit = init_hotfix_project(tmp_path, allow_hotfix=False)

    result = run(
        "hotfix",
        "--project",
        str(project),
        "--target",
        "main",
        "--authorization-phrase",
        HOTFIX_PHRASE,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "hotfix_push_not_allowed"


def test_hotfix_requires_explicit_target_branch_allow_hotfix_push(tmp_path: Path) -> None:
    project, remote, before_commit = init_hotfix_project(tmp_path)
    config_path = project / ".pr-flow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["defaults"]["allowHotfixPush"] = True
    config["branches"].pop("main")
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run(
        "hotfix",
        "--project",
        str(project),
        "--target",
        "main",
        "--authorization-phrase",
        HOTFIX_PHRASE,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert git_bare(remote, "rev-parse", "refs/heads/main") == before_commit
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "hotfix_push_not_allowed"


def test_hotfix_rejects_dirty_worktree_before_push(tmp_path: Path) -> None:
    project, remote, before_commit = init_hotfix_project(tmp_path)
    (project / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")

    result = run(
        "hotfix",
        "--project",
        str(project),
        "--target",
        "main",
        "--authorization-phrase",
        HOTFIX_PHRASE,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "dirty_worktree" in result.stdout
    assert git_bare(remote, "rev-parse", "refs/heads/main") == before_commit
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "dirty_worktree"
    assert "dirty.txt" in status["details"]["dirty"]


def test_hotfix_writes_audit_record_when_post_push_readback_mismatches(tmp_path: Path, monkeypatch) -> None:
    pr_flow = load_pr_flow_module()
    project, remote, before_commit = init_hotfix_project(tmp_path)
    head_commit = git(project, "rev-parse", "HEAD")
    remote_after = "0" * 40

    def fake_confirm(project_arg: Path, remote_arg: str, target_arg: str, expected_head: str) -> str:
        raise pr_flow.PrFlowError(
            "hotfix_readback_mismatch",
            {
                "reason": "hotfix_readback_mismatch",
                "targetBranch": target_arg,
                "remote": remote_arg,
                "currentHead": expected_head,
                "remoteAfter": remote_after,
            },
        )

    monkeypatch.setattr(pr_flow, "confirm_hotfix_remote_readback", fake_confirm)

    result = pr_flow.run_hotfix(
        pr_flow.argparse.Namespace(
            project=project,
            target="main",
            authorization_phrase=HOTFIX_PHRASE,
            command="hotfix",
        )
    )

    assert result == 1
    assert git_bare(remote, "rev-parse", "refs/heads/main") == head_commit
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "hotfix_readback_mismatch"
    audit_path = project / status["details"]["auditPath"]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["targetBranch"] == "main"
    assert audit["beforeCommit"] == before_commit
    assert audit["afterCommit"] == head_commit
    assert audit["readback"] == {
        "remote": "origin",
        "targetBranch": "main",
        "remoteAfter": remote_after,
        "matchedHead": False,
    }


def test_hotfix_missing_git_is_not_reported_as_missing_config(tmp_path: Path) -> None:
    project, _remote, _before_commit = init_hotfix_project(tmp_path)
    env = os.environ.copy()
    env["PATH"] = ""

    result = run(
        "hotfix",
        "--project",
        str(project),
        "--target",
        "main",
        "--authorization-phrase",
        HOTFIX_PHRASE,
        env=env,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "missing_config" not in result.stdout
    assert "git_fetch_target_failed" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "git_fetch_target_failed"


def test_hotfix_rejects_when_head_is_not_based_on_latest_remote_target(tmp_path: Path) -> None:
    project, remote, _before_commit = init_hotfix_project(tmp_path)
    integrator = tmp_path / "integrator"
    clone_result = subprocess.run(
        ["git", "clone", str(remote), str(integrator)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert clone_result.returncode == 0, clone_result.stdout + clone_result.stderr
    git(integrator, "config", "user.email", "test@example.com")
    git(integrator, "config", "user.name", "Test User")
    git(integrator, "checkout", "-B", "main", "origin/main")
    (integrator / "remote.txt").write_text("remote advance\n", encoding="utf-8")
    git(integrator, "add", "remote.txt")
    git(integrator, "commit", "-m", "advance target")
    git(integrator, "push", "origin", "main")
    remote_head = git_bare(remote, "rev-parse", "refs/heads/main")

    result = run(
        "hotfix",
        "--project",
        str(project),
        "--target",
        "main",
        "--authorization-phrase",
        HOTFIX_PHRASE,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert git_bare(remote, "rev-parse", "refs/heads/main") == remote_head
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "hotfix_base_mismatch"
    assert status["details"]["remoteHead"] == remote_head


def test_hotfix_rejects_when_verify_command_fails(tmp_path: Path) -> None:
    project, remote, before_commit = init_hotfix_project(
        tmp_path,
        verify_command="git rev-parse refs/heads/does-not-exist",
    )

    result = run(
        "hotfix",
        "--project",
        str(project),
        "--target",
        "main",
        "--authorization-phrase",
        HOTFIX_PHRASE,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert git_bare(remote, "rev-parse", "refs/heads/main") == before_commit
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "hotfix_verify_failed"
    assert status["details"]["returncode"] != 0


def test_hotfix_pushes_head_to_target_and_writes_audit_record(tmp_path: Path) -> None:
    project, remote, before_commit = init_hotfix_project(tmp_path)
    head_commit = git(project, "rev-parse", "HEAD")

    result = run(
        "hotfix",
        "--project",
        str(project),
        "--target",
        "main",
        "--authorization-phrase",
        HOTFIX_PHRASE,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: hotfix_complete" in result.stdout
    assert git_bare(remote, "rev-parse", "refs/heads/main") == head_commit

    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["remoteAfter"] == head_commit

    run_files = sorted((project / ".pr-flow" / "runs").glob("hotfix-*.json"))
    assert len(run_files) == 1
    audit = json.loads(run_files[0].read_text(encoding="utf-8"))
    assert audit["command"] == "hotfix"
    assert audit["targetBranch"] == "main"
    assert audit["beforeCommit"] == before_commit
    assert audit["afterCommit"] == head_commit
    assert audit["actor"]["name"] == "Test User"
    assert audit["actor"]["email"] == "test@example.com"
    assert audit["timestamp"]
    assert audit["verification"]["command"] == "git rev-parse HEAD"
    assert audit["verification"]["returncode"] == 0
    assert audit["verification"]["status"] == "passed"
    assert audit["readback"] == {
        "remote": "origin",
        "targetBranch": "main",
        "remoteAfter": head_commit,
        "matchedHead": True,
    }


def test_cleanup_merged_pr_checks_out_base_pulls_and_deletes_branches(tmp_path: Path) -> None:
    project, remote = init_cleanup_project(tmp_path)
    fake_bin, calls_path = write_fake_gh_sequence(tmp_path / "bin", [{"stdout": cleanup_pr_view_json()}])
    stale_local_base = git(project, "rev-parse", "main")
    remote_base_after_merge = git_bare(remote, "rev-parse", "refs/heads/main")
    assert stale_local_base != remote_base_after_merge
    assert git_bare_result(remote, "show-ref", "--verify", "refs/heads/feature/example").returncode == 0

    result = run_with_path(fake_bin, "cleanup", "--project", str(project), "--pr", "12")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert "branch: main" in result.stdout
    assert git(project, "branch", "--show-current") == "main"
    assert git(project, "rev-parse", "main") == remote_base_after_merge
    assert git_bare_result(remote, "show-ref", "--verify", "refs/heads/feature/example").returncode != 0
    local_branches = git(project, "branch", "--format", "%(refname:short)").splitlines()
    assert "feature/example" not in local_branches
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "cleanup_complete"
    assert status["command"] == "cleanup"
    assert status["details"]["pr"] == 12
    assert status["details"]["remote"] == "origin"
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls == [["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"]]


def test_cleanup_partial_remote_delete_failure_reports_recovery_state(tmp_path: Path) -> None:
    project, remote = init_cleanup_project(tmp_path)
    fake_bin = write_fake_gh(tmp_path / "bin", stdout=cleanup_pr_view_json(base_ref="missing-base"))

    result = run_with_path(fake_bin, "cleanup", "--project", str(project), "--pr", "12")

    assert_cleanup_exception(project, result, "git_checkout_base_failed")
    assert git_bare_result(remote, "show-ref", "--verify", "refs/heads/feature/example").returncode != 0
    assert git(project, "branch", "--show-current") == "feature/example"
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["completedCleanupSteps"] == ["remote_head_deleted", "remote_delete_confirmed"]
    assert "Remote head branch was already deleted" in status["details"]["recovery"]
    assert "do not rerun full `pr-flow-cleanup --project . --pr 12`" in status["details"]["recovery"]


def test_cleanup_pull_failure_after_base_checkout_reports_recovery_state(tmp_path: Path, monkeypatch) -> None:
    pr_flow = load_pr_flow_module()
    project, remote = init_cleanup_project(tmp_path)
    original_require_git_success = pr_flow.require_git_success

    monkeypatch.setattr(pr_flow, "view_pr_for_cleanup", lambda project_arg, pr_number: json.loads(cleanup_pr_view_json()))

    def fail_pull(project_arg: Path, reason: str, *args: str) -> subprocess.CompletedProcess[str]:
        if args == ("pull", "--ff-only", "origin", "main"):
            raise pr_flow.PrFlowError(
                reason,
                {
                    "reason": reason,
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "synthetic pull failure",
                },
            )
        return original_require_git_success(project_arg, reason, *args)

    monkeypatch.setattr(pr_flow, "require_git_success", fail_pull)

    result = pr_flow.run_cleanup(pr_flow.argparse.Namespace(project=project, pr="12", command="cleanup"))

    assert result == 1
    assert git_bare_result(remote, "show-ref", "--verify", "refs/heads/feature/example").returncode != 0
    assert git(project, "branch", "--show-current") == "main"
    local_branches = git(project, "branch", "--format", "%(refname:short)").splitlines()
    assert "feature/example" in local_branches
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "cleanup"
    assert status["details"]["reason"] == "git_pull_ff_only_failed"
    assert status["details"]["completedCleanupSteps"] == [
        "remote_head_deleted",
        "remote_delete_confirmed",
        "base_checked_out",
    ]
    assert "Remote head branch was already deleted" in status["details"]["recovery"]


def test_cleanup_rejects_pr_state_that_is_not_merged(tmp_path: Path) -> None:
    project, _remote = init_cleanup_project(tmp_path)
    fake_bin = write_fake_gh(tmp_path / "bin", stdout=cleanup_pr_view_json(state="OPEN"))

    result = run_with_path(fake_bin, "cleanup", "--project", str(project), "--pr", "12")

    assert_cleanup_exception(project, result, "pr_not_merged")


def test_cleanup_rejects_dirty_worktree(tmp_path: Path) -> None:
    project, _remote = init_cleanup_project(tmp_path)
    fake_bin = write_fake_gh(tmp_path / "bin", stdout=cleanup_pr_view_json())
    (project / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    result = run_with_path(fake_bin, "cleanup", "--project", str(project), "--pr", "12")

    assert_cleanup_exception(project, result, "dirty_worktree")


def test_cleanup_rejects_head_branch_equal_to_base_branch(tmp_path: Path) -> None:
    project, _remote = init_cleanup_project(tmp_path)
    fake_bin = write_fake_gh(tmp_path / "bin", stdout=cleanup_pr_view_json(head_ref="main", base_ref="main"))
    git(project, "checkout", "main")

    result = run_with_path(fake_bin, "cleanup", "--project", str(project), "--pr", "12")

    assert_cleanup_exception(project, result, "protected_base_branch")


def test_cleanup_rejects_current_branch_mismatch(tmp_path: Path) -> None:
    project, _remote = init_cleanup_project(tmp_path)
    fake_bin = write_fake_gh(tmp_path / "bin", stdout=cleanup_pr_view_json())
    git(project, "checkout", "main")

    result = run_with_path(fake_bin, "cleanup", "--project", str(project), "--pr", "12")

    assert_cleanup_exception(project, result, "current_branch_mismatch")
