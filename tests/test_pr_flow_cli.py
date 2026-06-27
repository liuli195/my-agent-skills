import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml
import pytest

from tests.support.git_templates import copy_template


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


def template_cache_key(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(REPO_ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


TEMPLATE_CACHE_KEY = template_cache_key(Path(__file__), SCRIPT)
# The cache is content-keyed and intentionally left under the OS temp directory
# between runs; stale locks and incomplete templates are recovered in-place.
TEMPLATE_ROOT = Path(tempfile.gettempdir()) / f"pr-flow-test-templates-{TEMPLATE_CACHE_KEY}"
TEMPLATE_LOCK_TIMEOUT_SECONDS = 30
TEMPLATE_LOCK_STALE_SECONDS = 30


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


def test_command_stub_records_gh_calls() -> None:
    from tests.support.command_stubs import CommandStub

    stub = CommandStub()
    stub.add(["pr", "view"], stdout='{"number":1}\n', returncode=0)

    result = stub("gh", "pr", "view")

    assert result.returncode == 0
    assert result.stdout == '{"number":1}\n'
    assert stub.calls == [("gh", "pr", "view")]


def test_command_stub_closes_body_file(monkeypatch, tmp_path: Path) -> None:
    from tests.support.command_stubs import CommandStub

    body_file = tmp_path / "body.json"
    body_file.write_text('{"ok":true}\n', encoding="utf-8")

    class TrackingFile:
        closed = False

        def read(self) -> str:
            return body_file.read_text(encoding="utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.closed = True

    tracker = TrackingFile()

    def fake_open(path, *_, **__):
        assert Path(path) == body_file
        return tracker

    monkeypatch.setattr("builtins.open", fake_open)
    stub = CommandStub()
    stub.add(["api", "graphql", "--body-file", str(body_file)], stdout="ok\n")

    result = stub("gh", "api", "graphql", "--body-file", str(body_file))

    assert result.returncode == 0
    assert stub.body_files == [{"args": ("gh", "api", "graphql", "--body-file", str(body_file)), "body": '{"ok":true}\n'}]
    assert tracker.closed


def test_pr_flow_template_cache_key_includes_script_contents() -> None:
    assert TEMPLATE_CACHE_KEY == template_cache_key(Path(__file__), SCRIPT)


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["cleanup", "--project", "."], "--pr"),
        (["hotfix", "--project", "."], "--target"),
        (["complete", "--project", ".", "--not-a-real-option"], "--not-a-real-option"),
    ],
)
def test_pr_flow_cli_argparse_errors_cover_core_commands(args: list[str], expected: str) -> None:
    result = run(*args)

    assert result.returncode == 2
    assert expected in result.stderr


def test_command_stub_accepts_project_argument_for_pr_flow_helpers(tmp_path: Path) -> None:
    from tests.support.command_stubs import CommandStub

    stub = CommandStub()
    stub.add(["pr", "view"], stdout='{"number":1}\n', returncode=0)

    result = stub(tmp_path, "pr", "view")

    assert result.returncode == 0
    assert result.stdout == '{"number":1}\n'
    assert result.args == ["pr", "view"]
    assert stub.calls == [("pr", "view")]


def test_command_stub_can_consume_sequence_and_capture_body_file(tmp_path: Path) -> None:
    from tests.support.command_stubs import CommandStub

    body_path = tmp_path / "body.md"
    body_path.write_text("hello body\n", encoding="utf-8")
    stub = CommandStub(consume=True)
    stub.add(["pr", "view"], stderr="not found\n", returncode=1)
    stub.add(["pr", "view"], stdout='{"number":1}\n')
    stub.add(["pr", "edit", "1", "--body-file", str(body_path)])

    first = stub("gh", "pr", "view")
    second = stub("gh", "pr", "view")
    edit = stub("gh", "pr", "edit", "1", "--body-file", str(body_path))

    assert first.returncode == 1
    assert second.stdout == '{"number":1}\n'
    assert edit.returncode == 0
    assert stub.body_files == [
        {"args": ("gh", "pr", "edit", "1", "--body-file", str(body_path)), "body": "hello body\n"}
    ]


def test_command_stub_placeholder_matches_body_file_path(tmp_path: Path) -> None:
    from tests.support.command_stubs import CommandStub

    body_path = tmp_path / "body.md"
    body_path.write_text("hello body\n", encoding="utf-8")
    stub = CommandStub(consume=True)
    stub.add(["pr", "edit", "1", "--body-file", "__placeholder__"])

    result = stub("gh", "pr", "edit", "1", "--body-file", str(body_path))

    assert result.returncode == 0
    assert stub.responses == []
    assert stub.body_files == [
        {"args": ("gh", "pr", "edit", "1", "--body-file", str(body_path)), "body": "hello body\n"}
    ]


def test_pr_flow_in_process_invocation_captures_output(tmp_path: Path) -> None:
    from tests.support.pr_flow_invocation import invoke_pr_flow

    draft = tmp_path / "confirmed.yaml"
    draft.write_text(
        yaml.safe_dump(default_pr_flow_config_for_test(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    result = invoke_pr_flow(["init", "--project", str(tmp_path), "--config", str(draft)])

    assert result.returncode == 0
    assert "status: initialized" in result.stdout
    assert result.stderr == ""


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


def copy_project_remote_template(template_dir: Path, tmp_path: Path) -> tuple[Path, Path]:
    remote = copy_template(template_dir / "remote.git", tmp_path / "remote.git")
    project = copy_template(template_dir / "project", tmp_path / "project")
    git(project, "remote", "set-url", "origin", str(remote))
    return project, remote


def remove_template_lock(lock_dir: Path) -> None:
    for _ in range(5):
        shutil.rmtree(lock_dir, ignore_errors=True)
        if not lock_dir.exists():
            return
        time.sleep(0.05)


def ensure_project_remote_template(template_name: str, tmp_path: Path, creator) -> tuple[Path, Path]:
    template_dir = TEMPLATE_ROOT / template_name
    ready = template_dir / ".ready"
    lock_dir = TEMPLATE_ROOT / f"{template_name}.lock"
    if ready.exists():
        if lock_dir.exists():
            remove_template_lock(lock_dir)
        return copy_project_remote_template(template_dir, tmp_path)

    deadline = time.monotonic() + TEMPLATE_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock_dir.mkdir(parents=True)
            break
        except FileExistsError:
            try:
                lock_age = time.time() - lock_dir.stat().st_mtime
            except FileNotFoundError:
                continue
            if lock_age > TEMPLATE_LOCK_STALE_SECONDS:
                remove_template_lock(lock_dir)
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"template_lock_timeout: {lock_dir}")
            time.sleep(0.05)

    try:
        if not ready.exists():
            if template_dir.exists():
                shutil.rmtree(template_dir)
            template_dir.mkdir(parents=True, exist_ok=True)
            creator(template_dir)
            ready.write_text("ok\n", encoding="utf-8")
    finally:
        remove_template_lock(lock_dir)

    return copy_project_remote_template(template_dir, tmp_path)


def test_project_template_recovers_stale_lock(tmp_path: Path) -> None:
    template_name = f"stale-lock-{tmp_path.name}"
    lock_dir = TEMPLATE_ROOT / f"{template_name}.lock"
    lock_dir.mkdir(parents=True, exist_ok=True)
    stale_time = time.time() - TEMPLATE_LOCK_STALE_SECONDS - 1
    os.utime(lock_dir, (stale_time, stale_time))

    project, remote = ensure_project_remote_template(
        template_name,
        tmp_path,
        lambda template_dir: _create_cleanup_project(template_dir),
    )

    assert project.is_dir()
    assert remote.is_dir()
    assert not lock_dir.exists()


def test_project_template_recreates_incomplete_template_after_stale_lock(tmp_path: Path) -> None:
    template_name = f"incomplete-template-{os.getpid()}-{time.monotonic_ns()}"
    template_dir = TEMPLATE_ROOT / template_name
    lock_dir = TEMPLATE_ROOT / f"{template_name}.lock"
    template_dir.mkdir(parents=True)
    (template_dir / "partial.txt").write_text("partial\n", encoding="utf-8")
    lock_dir.mkdir(parents=True, exist_ok=True)
    stale_time = time.time() - TEMPLATE_LOCK_STALE_SECONDS - 1
    os.utime(lock_dir, (stale_time, stale_time))

    project, remote = ensure_project_remote_template(
        template_name,
        tmp_path,
        lambda template_dir: _create_cleanup_project(template_dir),
    )

    assert project.is_dir()
    assert remote.is_dir()
    assert (template_dir / ".ready").is_file()
    assert not (template_dir / "partial.txt").exists()
    assert not lock_dir.exists()


def init_cleanup_project(tmp_path: Path) -> tuple[Path, Path]:
    return ensure_project_remote_template("cleanup", tmp_path, _create_cleanup_project)


def _create_cleanup_project(tmp_path: Path) -> tuple[Path, Path]:
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
    write_confirmed_pr_flow_config(project)
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
    key = f"complete-{review_mode}-{merge_strategy}-{evidence_path or 'default'}".replace(os.sep, "_").replace(":", "_")
    return ensure_project_remote_template(
        key,
        tmp_path,
        lambda template_dir: _create_complete_project(
            template_dir,
            review_mode=review_mode,
            merge_strategy=merge_strategy,
            evidence_path=evidence_path,
        ),
    )


def _create_complete_project(
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


def write_minimal_pr_flow_config(project: Path) -> None:
    config_dir = project / ".pr-flow"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "defaults": {"baseBranch": "main"},
        "branches": {"main": {"remote": "origin"}},
    }
    (config_dir / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


def run_cleanup_in_process(
    tmp_path: Path,
    monkeypatch,
    *,
    pr_stdout: str,
    git_responses: list[tuple[list[str], str, int]] | None = None,
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_minimal_pr_flow_config(project)
    gh_stub = CommandStub()
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=pr_stdout)
    git_stub = CommandStub()
    for args, stdout, returncode in git_responses or []:
        git_stub.add(args, stdout=stdout, returncode=returncode)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)
    result = invoke_pr_flow(["cleanup", "--project", str(project), "--pr", "12"], module=module)
    return project, result


def write_hotfix_pr_flow_config(
    project: Path,
    *,
    allow_hotfix: bool = True,
    include_authorization: bool = True,
    include_branch: bool = True,
    verify_command: str = "git rev-parse HEAD",
) -> None:
    config_dir = project / ".pr-flow"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "defaults": {
            "baseBranch": "main",
            "remote": "origin",
            "hotfix": {"verifyCommand": verify_command},
        },
        "branches": {},
    }
    if include_authorization:
        config["authorization"] = {
            "phraseHashAlgorithm": "md5",
            "phraseHash": hashlib.md5(HOTFIX_PHRASE.encode("utf-8")).hexdigest(),
        }
    if include_branch:
        config["branches"]["main"] = {
            "remote": "origin",
            "allowHotfixPush": allow_hotfix,
        }
    (config_dir / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


def run_hotfix_in_process(
    tmp_path: Path,
    monkeypatch,
    *,
    authorization_phrase: str = "ship-hotfix",
    allow_hotfix: bool = True,
    include_authorization: bool = True,
    include_branch: bool = True,
    git_responses: list[tuple[list[str], str, int]] | None = None,
    verify_returncode: int = 0,
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_hotfix_pr_flow_config(
        project,
        allow_hotfix=allow_hotfix,
        include_authorization=include_authorization,
        include_branch=include_branch,
    )
    git_stub = CommandStub()
    default_responses = [
        (["fetch", "origin", "main"], "", 0),
        (["rev-parse", "origin/main"], "a" * 40 + "\n", 0),
        (["rev-parse", "HEAD"], "b" * 40 + "\n", 0),
        (["merge-base", "HEAD", "origin/main"], "a" * 40 + "\n", 0),
        (["status", "--short"], "", 0),
    ]
    for args, stdout, returncode in git_responses or default_responses:
        git_stub.add(args, stdout=stdout, returncode=returncode)

    def fake_verify(project_arg: Path, command: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.CompletedProcess([command], verify_returncode, "verified\n", "verify failed\n" if verify_returncode else "")
        if verify_returncode:
            details = module.command_failure_details("hotfix_verify_failed", result)
            details["command"] = command
            raise module.PrFlowError("hotfix_verify_failed", details)
        return result

    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "run_hotfix_verify_command", fake_verify)
    result = invoke_pr_flow(
        [
            "hotfix",
            "--project",
            str(project),
            "--target",
            "main",
            "--authorization-phrase",
            authorization_phrase,
        ],
        module=module,
    )
    return project, result


def write_complete_pr_flow_config(
    project: Path,
    *,
    review_mode: str = "github",
    merge_strategy: str = "merge",
    evidence_path: str = ".pr-flow/review-pass.json",
) -> None:
    config_dir = project / ".pr-flow"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "defaults": {
            "baseBranch": "main",
            "mergeStrategy": merge_strategy,
            "reviewGate": {"mode": review_mode, "evidencePath": evidence_path},
            "wait": {"timeoutSeconds": 0, "pollSeconds": 0},
        },
        "branches": {"main": {"remote": "origin"}},
    }
    (config_dir / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


def run_complete_in_process(
    tmp_path: Path,
    monkeypatch,
    *,
    pr_stdout: str | None = None,
    pr_responses: list[tuple[str, str, int]] | None = None,
    cleanup_stdout: str | None = None,
    merge_strategy: str = "merge",
    git_responses: list[tuple[list[str], str, int]] | None = None,
    merge_returncode: int = 0,
    merge_stderr: str = "",
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project, merge_strategy=merge_strategy)
    gh_stub = CommandStub(consume=pr_responses is not None)
    if pr_responses is None:
        assert pr_stdout is not None
        gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    else:
        for stdout, stderr, returncode in pr_responses:
            gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=stdout, stderr=stderr, returncode=returncode)
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", "b" * 40], stderr=merge_stderr, returncode=merge_returncode)
    if cleanup_stdout is not None:
        gh_stub.add(
            ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"],
            stdout=cleanup_stdout,
        )
    git_stub = CommandStub()
    for args, stdout, returncode in git_responses or []:
        git_stub.add(args, stdout=stdout, returncode=returncode)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)
    result = invoke_pr_flow(["complete", "--project", str(project)], module=module)
    return project, result


def run_tweak_in_process(
    tmp_path: Path,
    monkeypatch,
    *,
    reason: str,
    first_pr_returncode: int = 0,
    first_pr_stderr: str = "",
    review_decision: str = "APPROVED",
    checks: list[dict[str, object]] | None = None,
    forbid_full_verify: bool = False,
) -> tuple[Path, subprocess.CompletedProcess[str], object]:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    if forbid_full_verify:
        def fail_full_verify(*_args, **_kwargs):
            raise AssertionError("tweak must not run build-and-verify verify --full")

        monkeypatch.setattr(module, "run_hotfix_verify_command", fail_full_verify)
    head_oid = "b" * 40
    pr_stdout = pr_view_json(
        checks=checks or [{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision=review_decision,
        head_oid=head_oid,
    )
    gh_stub = CommandStub(consume=True)
    if first_pr_returncode:
        gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr=first_pr_stderr, returncode=first_pr_returncode)
        gh_stub.add(["pr", "create", "--base", "main", "--fill"], stdout="https://github.example/test/repo/pull/12\n")
        gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    else:
        gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "edit", "12", "--body-file", "__placeholder__"])
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())

    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "HEAD"], head_oid + "\n"),
        (["status", "--short"], ""),
        (["branch", "--show-current"], "feature/example\n"),
        (["push", "origin", "--delete", "feature/example"], ""),
        (["ls-remote", "--heads", "origin", "feature/example"], ""),
        (["checkout", "main"], ""),
        (["pull", "--ff-only", "origin", "main"], ""),
        (["branch", "-d", "feature/example"], ""),
        (["branch", "--show-current"], "main\n"),
    ]:
        git_stub.add(git_args, stdout=stdout)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)
    result = invoke_pr_flow(["tweak", "--project", str(project), "--reason", reason], module=module)
    return project, result, gh_stub


def run_diagnose_in_process(
    tmp_path: Path,
    monkeypatch,
    *,
    pr_stdout: str,
    pr_stderr: str = "",
    pr_returncode: int = 0,
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_minimal_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="main\n")
    git_stub.add(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], stdout="origin/main\n")
    git_stub.add(["status", "--short"], stdout="")
    gh_stub = CommandStub()
    gh_stub.add(
        ["pr", "view", "--json", "number,state,isDraft,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup"],
        stdout=pr_stdout,
        stderr=pr_stderr,
        returncode=pr_returncode,
    )
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)
    result = invoke_pr_flow(["diagnose", "--project", str(project)], module=module)
    return project, result


def review_gate_config_for_test(mode: str, evidence_path: str = ".pr-flow/review-pass.json") -> dict:
    return {"defaults": {"reviewGate": {"mode": mode, "evidencePath": evidence_path}}}


def passing_review_pr(review_decision: str = "APPROVED") -> dict:
    return json.loads(
        pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision=review_decision,
            head_oid="b" * 40,
        )
    )


def write_review_pass_file(project: Path, relative_path: str = ".pr-flow/review-pass.json") -> str:
    fingerprint = "sha256:" + "1" * 64
    evidence_path = project / relative_path
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(
            {
                "status": "pass",
                "base_ref": "main",
                "head_ref": "feature/example",
                "diff_fingerprint": fingerprint,
                "blocking_findings": 0,
            }
        ),
        encoding="utf-8",
    )
    return fingerprint


def default_pr_flow_config_for_test(base_branch: str = "main") -> dict:
    return load_pr_flow_module().default_config(base_branch)


def write_confirmed_pr_flow_config(project: Path, config: dict | None = None) -> None:
    draft = project.parent / f"{project.name}-confirmed-pr-flow.yaml"
    draft.write_text(
        yaml.safe_dump(config or default_pr_flow_config_for_test(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    result = run("init", "--project", str(project), "--config", str(draft))
    assert result.returncode == 0, result.stdout + result.stderr


def configure_complete(
    project: Path,
    *,
    review_mode: str,
    merge_strategy: str = "merge",
    evidence_path: str | None = None,
) -> None:
    write_confirmed_pr_flow_config(project)
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
    write_confirmed_pr_flow_config(project)
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
    key = f"hotfix-{allow_hotfix}-{verify_command}".replace(os.sep, "_").replace(":", "_").replace(" ", "_")
    project, remote = ensure_project_remote_template(
        key,
        tmp_path,
        lambda template_dir: _create_hotfix_project(
            template_dir,
            allow_hotfix=allow_hotfix,
            verify_command=verify_command,
        ),
    )
    before_commit = git_bare(remote, "rev-parse", "refs/heads/main")
    return project, remote, before_commit


def _create_hotfix_project(
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
    draft = tmp_path / "confirmed.yaml"
    draft.write_text(
        yaml.safe_dump(default_pr_flow_config_for_test("main"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    result = run("init", "--project", str(project), "--config", str(draft))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: initialized" in result.stdout
    assert "GitHub Rulesets suggestion" in result.stdout

    config = yaml.safe_load((project / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))
    assert config["defaults"]["baseBranch"] == "main"
    assert config["defaults"]["mergeStrategy"] == "merge"
    assert config["defaults"]["reviewGate"]["mode"] == "github"
    assert config["defaults"]["reviewGate"]["evidencePath"] == ".pr-flow/review-pass.json"
    assert (
        config["defaults"]["hotfix"]["verifyCommand"]
        == "python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full"
    )
    assert config["defaults"]["wait"] == {"timeoutSeconds": 600, "pollSeconds": 15}
    assert config["defaults"]["pr"]["bodyTemplatePath"] == ".pr-flow/pr-template.md"
    assert config["branches"]["main"]["remote"] == "origin"
    assert config["branches"]["main"]["allowHotfixPush"] is False

    template = (project / ".pr-flow" / "pr-template.md").read_text(encoding="utf-8")
    for section in ["Summary", "Scope", "Verification", "Risk", "Rollback"]:
        assert f"## {section}" in template

    assert (project / ".pr-flow" / ".gitignore").read_text(encoding="utf-8") == "/runs/\n/last-status.json\n"


def test_init_without_confirmed_config_does_not_write_defaults(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("init", "--project", str(project), "--base-branch", "main")

    assert result.returncode == 2
    assert "confirmed config required" in result.stdout
    assert not (project / ".pr-flow" / "config.yaml").exists()
    assert not (project / ".pr-flow" / "pr-template.md").exists()
    assert not (project / ".pr-flow" / ".gitignore").exists()


def test_init_validation_errors_block_all_writes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    draft = tmp_path / "invalid.yaml"
    draft.write_text(
        yaml.safe_dump({"defaults": {"reviewGate": {"mode": "local"}}}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    result = run("init", "--project", str(project), "--config", str(draft))

    assert result.returncode == 1
    assert "status: validation_failed" in result.stdout
    assert "error: defaults.baseBranch missing" in result.stdout
    assert not (project / ".pr-flow" / "config.yaml").exists()
    assert not (project / ".pr-flow" / "pr-template.md").exists()
    assert not (project / ".pr-flow" / ".gitignore").exists()


def test_current_repo_hotfix_verify_command_uses_BUILD_AND_VERIFY_full() -> None:
    config = yaml.safe_load((REPO_ROOT / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))

    assert (
        config["defaults"]["hotfix"]["verifyCommand"]
        == "python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full"
    )


def test_init_does_not_call_gh_api(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    draft = tmp_path / "confirmed.yaml"
    draft.write_text(
        yaml.safe_dump(default_pr_flow_config_for_test(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    result = run("init", "--project", str(project), "--config", str(draft))

    assert result.returncode == 0
    assert "gh api" not in result.stdout
    assert "Rulesets written" not in result.stdout


def test_pr_flow_init_skill_uses_progressive_disclosure_references() -> None:
    skill_path = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-init" / "SKILL.md"
    skill_text = skill_path.read_text(encoding="utf-8")

    for heading in ["## Hard Boundaries", "## Closed Loop", "## Required Flow", "## Output", "## References"]:
        assert heading in skill_text
    for reference in [
        "references/questionnaire.md",
        "references/config-draft.md",
        "references/validation.md",
    ]:
        assert reference in skill_text
        assert (skill_path.parent / reference).is_file()
    assert "用户沉默 MUST NOT 被视为确认" in skill_text
    assert "完整问答" not in skill_text


def test_pr_flow_init_content_is_organized_by_user_scenario() -> None:
    init_dir = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-init"
    combined = "\n".join(
        [
            (init_dir / "SKILL.md").read_text(encoding="utf-8"),
            (init_dir / "references" / "questionnaire.md").read_text(encoding="utf-8"),
            (init_dir / "references" / "config-draft.md").read_text(encoding="utf-8"),
            (init_dir / "references" / "validation.md").read_text(encoding="utf-8"),
        ]
    )

    for scenario in [
        "初次启用 PR Flow",
        "review gate",
        "hotfix",
        "cleanup",
        "GitHub setup suggestions",
        "最终写入确认",
    ]:
        assert scenario in combined
    for template_term in ["固定问题", "固定选项", "选择后果", "跳转规则"]:
        assert template_term in combined


def test_pr_flow_plugin_init_entrypoints_route_to_pr_flow_init() -> None:
    paths = [
        REPO_ROOT / "plugins" / "pr-flow" / ".codex-plugin" / "plugin.json",
        REPO_ROOT / "plugins" / "pr-flow" / ".claude-plugin" / "plugin.json",
        REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow" / "SKILL.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "pr-flow-init" in text
        assert "agent（代理）问答" in text
        assert "只读 validate（校验）" in text


def test_pr_flow_init_end_to_end_from_skill_to_confirmed_write(tmp_path: Path) -> None:
    skill_dir = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-init"
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    questionnaire = (skill_dir / "references" / "questionnaire.md").read_text(encoding="utf-8")
    config_draft = (skill_dir / "references" / "config-draft.md").read_text(encoding="utf-8")
    validation = (skill_dir / "references" / "validation.md").read_text(encoding="utf-8")

    assert "references/questionnaire.md" in skill_text
    assert "固定问题" in questionnaire
    assert "setup.github" in config_draft
    assert "error（错误）" in validation

    project = tmp_path / "project"
    project.mkdir()
    config = default_pr_flow_config_for_test("main")
    config["setup"] = {"github": {"requiredChecks": ["ci"], "requiredReview": True}}
    draft = tmp_path / "confirmed.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    validate_result = run("validate", "--project", str(project), "--config", str(draft))
    assert validate_result.returncode == 0, validate_result.stdout + validate_result.stderr
    assert "status: validation_passed" in validate_result.stdout

    init_result = run("init", "--project", str(project), "--config", str(draft))
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr

    written = yaml.safe_load((project / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))
    assert written["defaults"]["baseBranch"] == "main"
    assert written["setup"]["github"]["requiredChecks"] == ["ci"]
    assert (project / ".pr-flow" / "pr-template.md").is_file()
    assert (project / ".pr-flow" / ".gitignore").read_text(encoding="utf-8") == "/runs/\n/last-status.json\n"

    combined_output = validate_result.stdout + init_result.stdout
    for forbidden in ["status: ready", "status: merge_complete", "cleanup_complete", "hotfix_complete"]:
        assert forbidden not in combined_output


def test_validate_reads_only_provided_config_and_reports_suggestions(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    draft = tmp_path / "draft.yaml"
    draft.write_text(
        yaml.safe_dump(
            {
                "defaults": {
                    "baseBranch": "main",
                    "mergeStrategy": "merge",
                    "reviewGate": {"mode": "github", "evidencePath": ".pr-flow/review-pass.json"},
                    "hotfix": {"verifyCommand": "python -m pytest"},
                    "wait": {"timeoutSeconds": 600, "pollSeconds": 15},
                },
                "branches": {"main": {"remote": "origin", "allowHotfixPush": False}},
                "setup": {"github": {"requiredChecks": ["ci"]}},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = run("validate", "--project", str(project), "--config", str(draft))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: validation_passed" in result.stdout
    assert "setup suggestion: configure GitHub required review" in result.stdout
    assert "setup suggestion: configure GitHub Rulesets required checks" in result.stdout
    assert not (project / ".pr-flow" / "config.yaml").exists()


def test_validate_reports_errors_for_missing_core_shape(tmp_path: Path) -> None:
    draft = tmp_path / "draft.yaml"
    draft.write_text(
        yaml.safe_dump({"defaults": {"reviewGate": {"mode": "local"}}}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    result = run("validate", "--config", str(draft))

    assert result.returncode == 1
    assert "status: validation_failed" in result.stdout
    assert "error: defaults.baseBranch missing" in result.stdout
    assert "error: branches must contain at least one branch" in result.stdout
    assert "error: defaults.reviewGate.evidencePath missing" in result.stdout


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda config: config["branches"]["main"].update(
                {"allowHotfixPush": True, "remote": ""}
            ),
            "error: branches.main.remote missing",
        ),
        (
            lambda config: config["defaults"].update({"reviewGate": {"mode": "local"}}),
            "error: defaults.reviewGate.evidencePath missing",
        ),
        (
            lambda config: config["setup"]["github"].update({"autoDeleteHeadBranch": True}),
            "warning: GitHub auto-delete head branch overlaps PR Flow cleanup",
        ),
        (
            lambda config: config["setup"]["github"].update({"requiredReview": True}),
            "setup suggestion: tweak cannot bypass GitHub required review",
        ),
    ],
)
def test_validate_dependency_matrix(tmp_path: Path, mutate, expected: str) -> None:
    config = {
        "defaults": {
            "baseBranch": "main",
            "mergeStrategy": "merge",
            "reviewGate": {"mode": "github", "evidencePath": ".pr-flow/review-pass.json"},
            "hotfix": {"verifyCommand": "python -m pytest"},
            "wait": {"timeoutSeconds": 600, "pollSeconds": 15},
        },
        "branches": {"main": {"remote": "origin", "allowHotfixPush": False}},
        "authorization": {"phraseHashAlgorithm": "md5", "phraseHash": "abc"},
        "setup": {"github": {"requiredChecks": ["ci"]}},
    }
    mutate(config)
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("validate", "--config", str(draft))

    assert expected in result.stdout


def test_missing_config_reports_exception_required(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "missing_config" in result.stdout


def test_status_file_is_written_for_stop_state(tmp_path: Path) -> None:
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_confirmed_pr_flow_config(project)
    result = invoke_pr_flow(["diagnose", "--project", str(project)], module=module)

    assert result.returncode == 1
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["reason"] == "git_current_branch_failed"


def test_diagnose_outputs_push_required_without_upstream(tmp_path: Path) -> None:
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    assert init_repo(project) == "main"
    write_confirmed_pr_flow_config(project)
    git(project, "switch", "-c", "feature/no-upstream")

    result = invoke_pr_flow(["diagnose", "--project", str(project)], module=module)

    assert result.returncode == 1
    assert "status: PUSH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "PUSH_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["branch"] == "feature/no-upstream"
    assert status["details"]["reason"] == "missing_upstream"
    assert "push current branch before continuing" in result.stdout


def test_diagnose_outputs_exception_for_unknown_gh_failure(tmp_path: Path, monkeypatch) -> None:
    project, result = run_diagnose_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout="",
        pr_stderr="synthetic gh failure\n",
        pr_returncode=42,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "gh_pr_view_failed" in result.stdout
    assert "PUSH_REQUIRED" not in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["branch"] == "main"
    assert status["details"]["reason"] == "gh_pr_view_failed"


def test_diagnose_on_base_branch_without_pr_reports_gh_pr_view_failed(tmp_path: Path, monkeypatch) -> None:
    project, result = run_diagnose_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout="",
        pr_stderr="no pull requests found for branch\n",
        pr_returncode=1,
    )

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


@pytest.mark.parametrize(
    ("pr_stdout", "returncode", "expected_status", "expected_reason", "extra_detail"),
    [
        (
            pr_view_json(checks=[{"name": "ci", "status": "IN_PROGRESS", "conclusion": None}]),
            1,
            "DISPATCH_REQUIRED",
            "checks_pending",
            {},
        ),
        (
            pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "FAILURE"}]),
            1,
            "REPLY_OR_FIX_REQUIRED",
            "checks_or_review_blocking",
            {},
        ),
        (
            pr_view_json(
                checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                review_decision="CHANGES_REQUESTED",
            ),
            1,
            "REPLY_OR_FIX_REQUIRED",
            "checks_or_review_blocking",
            {},
        ),
        (
            pr_view_json(
                checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                review_decision="REVIEW_REQUIRED",
            ),
            1,
            "REPLY_OR_FIX_REQUIRED",
            "checks_or_review_blocking",
            {"reviewDecision": "REVIEW_REQUIRED"},
        ),
        (
            pr_view_json(
                checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                review_decision="",
            ),
            0,
            "ready",
            "ready_to_complete",
            {"nextCommand": "complete"},
        ),
        (
            pr_view_json(
                checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                review_decision="",
                is_draft=True,
            ),
            1,
            "DISPATCH_REQUIRED",
            "pr_is_draft",
            {"nextCommand": "gh pr ready"},
        ),
    ],
)
def test_diagnose_outputs_stop_state_matrix(
    tmp_path: Path,
    monkeypatch,
    pr_stdout: str,
    returncode: int,
    expected_status: str,
    expected_reason: str,
    extra_detail: dict[str, str],
) -> None:
    project, result = run_diagnose_in_process(tmp_path, monkeypatch, pr_stdout=pr_stdout)

    assert result.returncode == returncode
    assert f"status: {expected_status}" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == expected_status
    assert status["command"] == "diagnose"
    assert status["details"]["reason"] == expected_reason
    for key, value in extra_detail.items():
        assert status["details"][key] == value


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


def test_complete_full_flow_uses_configured_squash_strategy(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path, merge_strategy="squash")
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
    assert calls[4] == ["pr", "merge", "12", "--squash", "--match-head-commit", head_oid]


def test_complete_merges_locked_head_then_runs_cleanup_in_order(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    head_oid = "b" * 40
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="APPROVED", head_oid=head_oid))
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="APPROVED", head_oid=head_oid))
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "HEAD"], head_oid + "\n"),
        (["status", "--short"], ""),
        (["branch", "--show-current"], "feature/example\n"),
        (["push", "origin", "--delete", "feature/example"], ""),
        (["ls-remote", "--heads", "origin", "feature/example"], ""),
        (["checkout", "main"], ""),
        (["pull", "--ff-only", "origin", "main"], ""),
        (["branch", "-d", "feature/example"], ""),
        (["branch", "--show-current"], "main\n"),
    ]:
        git_stub.add(git_args, stdout=stdout)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(["complete", "--project", str(project)], module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    calls = [list(call) for call in gh_stub.calls]
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
        ["pr", "merge", "12", "--merge", "--match-head-commit", "b" * 40],
        ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"],
    ]
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "cleanup_complete"
    assert status["command"] == "cleanup"


def test_complete_does_not_run_build_and_verify_full_verify(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    head_oid = "b" * 40
    gh_stub = CommandStub(consume=True)
    for command in [
        ["pr", "view", "--json", module.PR_VIEW_FIELDS],
        ["pr", "view", "--json", module.PR_VIEW_FIELDS],
    ]:
        gh_stub.add(
            command,
            stdout=pr_view_json(
                checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                review_decision="APPROVED",
                head_oid=head_oid,
            ),
        )
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid])
    gh_stub.add(
        ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"],
        stdout=cleanup_pr_view_json(),
    )
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "HEAD"], head_oid + "\n"),
        (["status", "--short"], ""),
        (["branch", "--show-current"], "feature/example\n"),
        (["push", "origin", "--delete", "feature/example"], ""),
        (["ls-remote", "--heads", "origin", "feature/example"], ""),
        (["checkout", "main"], ""),
        (["pull", "--ff-only", "origin", "main"], ""),
        (["branch", "-d", "feature/example"], ""),
        (["branch", "--show-current"], "main\n"),
    ]:
        git_stub.add(git_args, stdout=stdout)

    def fail_full_verify(*_args, **_kwargs):
        raise AssertionError("complete must not run build-and-verify verify --full")

    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "run_hotfix_verify_command", fail_full_verify)

    result = invoke_pr_flow(["complete", "--project", str(project)], module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout


def test_complete_returns_cleanup_stop_when_cleanup_fails_after_merge(tmp_path: Path, monkeypatch) -> None:
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid="b" * 40,
        ),
        cleanup_stdout=cleanup_pr_view_json(state="OPEN"),
        git_responses=[
            (["branch", "--show-current"], "feature/example\n", 0),
            (["rev-parse", "HEAD"], "b" * 40 + "\n", 0),
        ],
    )

    assert result.returncode == 1
    assert "status: merge_complete" in result.stdout
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "pr_not_merged" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "cleanup"
    assert status["details"]["reason"] == "pr_not_merged"
    assert "pr-flow-cleanup" in status["details"]["recovery"]


def test_complete_stops_when_pr_sync_fails_instead_of_using_stale_pr(tmp_path: Path, monkeypatch) -> None:
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_responses=[
            (
                pr_view_json(
                    checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                    review_decision="APPROVED",
                    head_oid="b" * 40,
                ),
                "",
                0,
            ),
            ("", "rate limited\n", 1),
        ],
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "gh_pr_view_failed" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "gh_pr_view_failed"
    assert "rate limited" in status["details"]["stderr"]


def test_complete_uses_configured_merge_strategy_flag(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub

    module = load_pr_flow_module()
    for strategy, expected_flag in [("merge", "--merge"), ("squash", "--squash"), ("rebase", "--rebase")]:
        project = tmp_path / strategy
        project.mkdir()
        head_oid = f"{strategy:0<40}"[:40]
        git_stub = CommandStub()
        git_stub.add(["rev-parse", "HEAD"], stdout=f"{head_oid}\n")
        gh_stub = CommandStub()
        gh_stub.add(["pr", "merge", "12", expected_flag, "--match-head-commit", head_oid])
        monkeypatch.setattr(module, "git", git_stub)
        monkeypatch.setattr(module, "gh", gh_stub)

        result = module.merge_pr(
            project,
            {"defaults": {"mergeStrategy": strategy}},
            {"number": 12, "headRefOid": head_oid, "headRefName": "feature/example"},
        )

        assert result is None
        assert gh_stub.calls == [("pr", "merge", "12", expected_flag, "--match-head-commit", head_oid)]


def test_complete_rejects_when_head_moved_before_merge(tmp_path: Path, monkeypatch) -> None:
    moved_head_oid = "0" * 40
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid=moved_head_oid,
        ),
        git_responses=[
            (["branch", "--show-current"], "feature/example\n", 0),
            (["rev-parse", "HEAD"], "b" * 40 + "\n", 0),
        ],
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "head_moved"


def test_complete_rejects_missing_head_ref_oid_without_merge(tmp_path: Path, monkeypatch) -> None:
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
        ),
        git_responses=[(["branch", "--show-current"], "feature/example\n", 0)],
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "missing_head_ref_oid"


def test_complete_rejects_current_branch_that_does_not_match_pr_head(tmp_path: Path, monkeypatch) -> None:
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid="b" * 40,
        ),
        git_responses=[(["branch", "--show-current"], "feature/other\n", 0)],
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "current_branch_mismatch" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "current_branch_mismatch"
    assert status["details"]["currentBranch"] == "feature/other"
    assert status["details"]["headRefName"] == "feature/example"


def test_complete_reports_exception_when_gh_pr_merge_fails(tmp_path: Path, monkeypatch) -> None:
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid="b" * 40,
        ),
        git_responses=[
            (["branch", "--show-current"], "feature/example\n", 0),
            (["rev-parse", "HEAD"], "b" * 40 + "\n", 0),
        ],
        merge_returncode=1,
        merge_stderr="merge failed\n",
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "gh_pr_merge_failed" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "gh_pr_merge_failed"
    assert status["details"]["stderr"] == "merge failed"


def test_complete_rejects_unknown_merge_strategy(tmp_path: Path, monkeypatch) -> None:
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid="b" * 40,
        ),
        merge_strategy="octopus",
        git_responses=[(["branch", "--show-current"], "feature/example\n", 0)],
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "unknown_merge_strategy"


def test_complete_skip_review_gate_ignores_github_changes_requested(tmp_path: Path) -> None:
    module = load_pr_flow_module()

    result = module.check_review_gate(
        tmp_path,
        review_gate_config_for_test("skip"),
        passing_review_pr(review_decision="CHANGES_REQUESTED"),
    )

    assert result is None


def test_complete_github_review_gate_blocks_changes_requested(tmp_path: Path, monkeypatch) -> None:
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="CHANGES_REQUESTED",
            head_oid="b" * 40,
        ),
    )

    assert result.returncode == 1
    assert "status: REPLY_OR_FIX_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "REPLY_OR_FIX_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "review_gate_blocking"


def test_complete_wait_timeout_zero_reports_pending_checks_without_sleep(tmp_path: Path, monkeypatch) -> None:
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "IN_PROGRESS", "conclusion": None}],
            review_decision="APPROVED",
            head_oid="b" * 40,
        ),
    )

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "checks_pending"


def test_complete_local_review_gate_accepts_review_pass_evidence(tmp_path: Path, monkeypatch) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    fingerprint = write_review_pass_file(project)
    monkeypatch.setattr(module, "current_diff_fingerprint", lambda project_arg, pr: fingerprint)

    result = module.check_review_gate(project, review_gate_config_for_test("local"), passing_review_pr("CHANGES_REQUESTED"))

    assert result is None


def test_complete_local_review_gate_blocks_stale_diff_evidence(tmp_path: Path, monkeypatch) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    write_review_pass_file(project)
    monkeypatch.setattr(module, "current_diff_fingerprint", lambda project_arg, pr: "sha256:" + "0" * 64)

    result = module.check_review_gate(project, review_gate_config_for_test("local"), passing_review_pr("CHANGES_REQUESTED"))

    assert result is not None
    assert result["status"] == "REPLY_OR_FIX_REQUIRED"
    assert result["details"]["reason"] == "local_review_evidence_failed"


def test_complete_dual_review_gate_requires_github_and_local_evidence(tmp_path: Path, monkeypatch) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    fingerprint = write_review_pass_file(project)
    monkeypatch.setattr(module, "current_diff_fingerprint", lambda project_arg, pr: fingerprint)

    result = module.check_review_gate(project, review_gate_config_for_test("dual"), passing_review_pr())

    assert result is None


def test_complete_dual_review_gate_blocks_github_changes_requested_even_with_local_evidence(tmp_path: Path) -> None:
    module = load_pr_flow_module()
    write_review_pass_file(tmp_path)

    result = module.check_review_gate(
        tmp_path,
        review_gate_config_for_test("dual"),
        passing_review_pr(review_decision="CHANGES_REQUESTED"),
    )

    assert result is not None
    assert result["status"] == "REPLY_OR_FIX_REQUIRED"
    assert result["details"]["reason"] == "review_gate_blocking"
    assert result["details"]["reviewGateMode"] == "dual"
    assert result["details"]["reviewDecision"] == "CHANGES_REQUESTED"


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


def test_tweak_creates_pr_when_none_exists_and_writes_body(tmp_path: Path, monkeypatch) -> None:
    reason = "small docs polish"
    _project, result, gh_stub = run_tweak_in_process(
        tmp_path,
        monkeypatch,
        reason=reason,
        first_pr_returncode=1,
        first_pr_stderr="no pull requests found\n",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    calls = [list(call) for call in gh_stub.calls]
    assert calls[0][:2] == ["pr", "view"]
    assert calls[1][:2] == ["pr", "create"]
    assert calls[3][:2] == ["pr", "view"]
    assert calls[4][:3] == ["pr", "edit", "12"]
    assert "--body-file" in calls[4]
    assert calls[5] == ["pr", "merge", "12", "--merge", "--match-head-commit", "b" * 40]
    assert calls[6] == ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"]
    body_records = gh_stub.body_files
    assert len(body_records) == 1
    assert (
        "## Tweak Path\n\n"
        "Review gate skipped for non-bug small change.\n\n"
        f"Reason: {reason}\n"
    ) in body_records[0]["body"]


def test_tweak_skips_review_gate_for_changes_requested_then_merges_and_cleans_up(tmp_path: Path, monkeypatch) -> None:
    reason = "rename helper only"
    _project, result, gh_stub = run_tweak_in_process(
        tmp_path,
        monkeypatch,
        reason=reason,
        review_decision="CHANGES_REQUESTED",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert "REPLY_OR_FIX_REQUIRED" not in result.stdout
    calls = [list(call) for call in gh_stub.calls]
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
        ["pr", "merge", "12", "--merge", "--match-head-commit", "b" * 40],
        ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"],
    ]


def test_tweak_does_not_run_build_and_verify_full_verify(tmp_path: Path, monkeypatch) -> None:
    _project, result, _gh_stub = run_tweak_in_process(
        tmp_path,
        monkeypatch,
        reason="wording only",
        forbid_full_verify=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout


def test_tweak_pending_checks_report_dispatch_required(tmp_path: Path, monkeypatch) -> None:
    reason = "format-only cleanup"
    project, result, gh_stub = run_tweak_in_process(
        tmp_path,
        monkeypatch,
        reason=reason,
        review_decision="CHANGES_REQUESTED",
        checks=[{"name": "ci", "status": "IN_PROGRESS", "conclusion": None}],
    )

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    calls = [list(call) for call in gh_stub.calls]
    assert calls[2][:3] == ["pr", "edit", "12"]
    assert all(call[:2] != ["pr", "merge"] for call in calls)
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "tweak"
    assert status["details"]["reason"] == "checks_pending"
    body_records = gh_stub.body_files
    assert len(body_records) == 1
    assert f"Reason: {reason}\n" in body_records[0]["body"]


def test_hotfix_rejects_authorization_phrase_mismatch_without_leaking_phrase(tmp_path: Path, monkeypatch) -> None:
    wrong_phrase = "wrong-secret"

    project, result = run_hotfix_in_process(
        tmp_path,
        monkeypatch,
        authorization_phrase=wrong_phrase,
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
    project, result = run_hotfix_in_process(
        tmp_path,
        monkeypatch,
        include_authorization=False,
    )

    assert result.returncode == 1
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "authorization_phrase_missing"


def test_hotfix_runs_verify_command_before_authorization_phrase_check(tmp_path: Path, monkeypatch) -> None:
    project, result = run_hotfix_in_process(
        tmp_path,
        monkeypatch,
        authorization_phrase="wrong-secret",
        verify_returncode=1,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "authorization_phrase_mismatch" not in result.stdout
    status_text = (project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8")
    assert "wrong-secret" not in status_text
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
    project = tmp_path / "project"
    project.mkdir()

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


def test_hotfix_rejects_target_branch_without_allow_hotfix_push(tmp_path: Path, monkeypatch) -> None:
    project, result = run_hotfix_in_process(
        tmp_path,
        monkeypatch,
        allow_hotfix=False,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "hotfix_push_not_allowed"


def test_hotfix_requires_explicit_target_branch_allow_hotfix_push(tmp_path: Path, monkeypatch) -> None:
    project, result = run_hotfix_in_process(
        tmp_path,
        monkeypatch,
        include_branch=False,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "hotfix_push_not_allowed"


def test_hotfix_rejects_dirty_worktree_before_push(tmp_path: Path, monkeypatch) -> None:
    project, result = run_hotfix_in_process(
        tmp_path,
        monkeypatch,
        git_responses=[
            (["fetch", "origin", "main"], "", 0),
            (["rev-parse", "origin/main"], "a" * 40 + "\n", 0),
            (["rev-parse", "HEAD"], "b" * 40 + "\n", 0),
            (["merge-base", "HEAD", "origin/main"], "a" * 40 + "\n", 0),
            (["status", "--short"], "dirty.txt\n", 0),
        ],
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "dirty_worktree" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "dirty_worktree"
    assert "dirty.txt" in status["details"]["dirty"]


def test_hotfix_writes_audit_record_when_post_push_readback_mismatches(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    pr_flow = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_hotfix_pr_flow_config(project)
    before_commit = "a" * 40
    head_commit = "b" * 40
    remote_after = "0" * 40
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["fetch", "origin", "main"], ""),
        (["rev-parse", "origin/main"], before_commit + "\n"),
        (["rev-parse", "HEAD"], head_commit + "\n"),
        (["merge-base", "HEAD", "origin/main"], before_commit + "\n"),
        (["status", "--short"], ""),
        (["push", "origin", "HEAD:refs/heads/main"], ""),
        (["config", "--get", "user.name"], "Test User\n"),
        (["config", "--get", "user.email"], "test@example.com\n"),
    ]:
        git_stub.add(git_args, stdout=stdout)

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

    def fake_verify(project_arg: Path, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([command], 0, head_commit + "\n", "")

    monkeypatch.setattr(pr_flow, "git", git_stub)
    monkeypatch.setattr(pr_flow, "confirm_hotfix_remote_readback", fake_confirm)
    monkeypatch.setattr(pr_flow, "run_hotfix_verify_command", fake_verify)

    result = invoke_pr_flow(
        ["hotfix", "--project", str(project), "--target", "main", "--authorization-phrase", HOTFIX_PHRASE],
        module=pr_flow,
    )

    assert result.returncode == 1
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
    project = tmp_path / "project"
    project.mkdir()
    write_hotfix_pr_flow_config(project)
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


def test_hotfix_rejects_when_head_is_not_based_on_latest_remote_target(tmp_path: Path, monkeypatch) -> None:
    remote_head = "a" * 40
    project, result = run_hotfix_in_process(
        tmp_path,
        monkeypatch,
        git_responses=[
            (["fetch", "origin", "main"], "", 0),
            (["rev-parse", "origin/main"], remote_head + "\n", 0),
            (["rev-parse", "HEAD"], "b" * 40 + "\n", 0),
            (["merge-base", "HEAD", "origin/main"], "c" * 40 + "\n", 0),
        ],
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "hotfix"
    assert status["details"]["reason"] == "hotfix_base_mismatch"
    assert status["details"]["remoteHead"] == remote_head


def test_hotfix_rejects_when_verify_command_fails(tmp_path: Path, monkeypatch) -> None:
    project, result = run_hotfix_in_process(
        tmp_path,
        monkeypatch,
        verify_returncode=1,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
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
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": cleanup_pr_view_json()},
        ],
    )
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


def test_cleanup_partial_remote_delete_failure_reports_recovery_state(tmp_path: Path, monkeypatch) -> None:
    project, result = run_cleanup_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=cleanup_pr_view_json(base_ref="missing-base"),
        git_responses=[
            (["status", "--short"], "", 0),
            (["branch", "--show-current"], "feature/example\n", 0),
            (["push", "origin", "--delete", "feature/example"], "", 0),
            (["ls-remote", "--heads", "origin", "feature/example"], "", 0),
            (["checkout", "missing-base"], "", 1),
        ],
    )

    assert_cleanup_exception(project, result, "git_checkout_base_failed")
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["completedCleanupSteps"] == ["remote_head_deleted", "remote_delete_confirmed"]
    assert "Remote head branch was already deleted" in status["details"]["recovery"]
    assert "do not rerun full `pr-flow-cleanup --project . --pr 12`" in status["details"]["recovery"]


def test_cleanup_pull_failure_after_base_checkout_reports_recovery_state(tmp_path: Path, monkeypatch) -> None:
    project, result = run_cleanup_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=cleanup_pr_view_json(),
        git_responses=[
            (["status", "--short"], "", 0),
            (["branch", "--show-current"], "feature/example\n", 0),
            (["push", "origin", "--delete", "feature/example"], "", 0),
            (["ls-remote", "--heads", "origin", "feature/example"], "", 0),
            (["checkout", "main"], "", 0),
            (["pull", "--ff-only", "origin", "main"], "synthetic pull failure", 1),
        ],
    )

    assert result.returncode == 1
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["command"] == "cleanup"
    assert status["details"]["reason"] == "git_pull_ff_only_failed"
    assert status["details"]["completedCleanupSteps"] == [
        "remote_head_deleted",
        "remote_delete_confirmed",
        "base_checked_out",
    ]
    assert "Remote head branch was already deleted" in status["details"]["recovery"]


def test_cleanup_rejects_pr_state_that_is_not_merged(tmp_path: Path, monkeypatch) -> None:
    project, result = run_cleanup_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=cleanup_pr_view_json(state="OPEN"),
    )


    assert_cleanup_exception(project, result, "pr_not_merged")


def test_cleanup_rejects_dirty_worktree(tmp_path: Path, monkeypatch) -> None:
    project, result = run_cleanup_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=cleanup_pr_view_json(),
        git_responses=[(["status", "--short"], "dirty.txt\n", 0)],
    )

    assert_cleanup_exception(project, result, "dirty_worktree")


def test_cleanup_rejects_head_branch_equal_to_base_branch(tmp_path: Path, monkeypatch) -> None:
    project, result = run_cleanup_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=cleanup_pr_view_json(head_ref="main", base_ref="main"),
        git_responses=[
            (["status", "--short"], "", 0),
            (["branch", "--show-current"], "main\n", 0),
        ],
    )

    assert_cleanup_exception(project, result, "protected_base_branch")


def test_cleanup_rejects_current_branch_mismatch(tmp_path: Path, monkeypatch) -> None:
    project, result = run_cleanup_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=cleanup_pr_view_json(),
        git_responses=[
            (["status", "--short"], "", 0),
            (["branch", "--show-current"], "main\n", 0),
        ],
    )

    assert_cleanup_exception(project, result, "current_branch_mismatch")
