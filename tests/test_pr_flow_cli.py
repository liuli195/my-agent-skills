import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

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
_PR_FLOW_MODULE = None


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
    global _PR_FLOW_MODULE
    if _PR_FLOW_MODULE is not None:
        return _PR_FLOW_MODULE
    spec = importlib.util.spec_from_file_location("pr_flow_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _PR_FLOW_MODULE = module
    return module


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    module = load_pr_flow_module()
    stdout = io.StringIO()
    stderr = io.StringIO()
    previous_env = os.environ.copy()
    if env is not None:
        os.environ.clear()
        os.environ.update(env)
    try:
        with contextlib.chdir(cwd or REPO_ROOT), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                returncode = int(module.main(args))
            except SystemExit as error:
                returncode = error.code if isinstance(error.code, int) else 1
    finally:
        if env is not None:
            os.environ.clear()
            os.environ.update(previous_env)
    return subprocess.CompletedProcess(
        [sys.executable, str(SCRIPT), *args],
        returncode,
        stdout.getvalue(),
        stderr.getvalue(),
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


def test_write_status_keeps_compatibility_file_and_branch_run(tmp_path: Path) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    init_repo(project)

    module.write_status(project, "complete", "ready", {"sourceBranch": "feature/one"})

    latest = json.loads((project / ".pr-flow/last-status.json").read_text(encoding="utf-8"))
    runs = list((project / ".pr-flow/runs").glob("*.json"))
    assert len(runs) == 1
    assert json.loads(runs[0].read_text(encoding="utf-8")) == latest
    assert latest["details"]["sourceBranch"] == "feature/one"
    assert Path(latest["details"]["worktreePath"]) == project.resolve()
    assert latest["details"]["commonGitDir"]


def test_competing_mutation_reports_lock_without_rewriting_status(tmp_path: Path, capsys) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    init_repo(project)
    module.write_status(project, "complete", "ready", {"sourceBranch": "feature/one"})
    before = (project / ".pr-flow/last-status.json").read_bytes()

    with module.operation_lock(project, "complete", argparse.Namespace(project=project)):
        result = module.main(["cleanup", "--project", str(project), "--pr", "12"])

    assert result == 1
    assert "flow_locked" in capsys.readouterr().out
    assert (project / ".pr-flow/last-status.json").read_bytes() == before


def test_diagnose_reports_active_lock_without_writing_status(tmp_path: Path, capsys) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    init_repo(project)

    with module.operation_lock(project, "complete", argparse.Namespace(project=project)):
        assert module.main(["diagnose", "--project", str(project)]) == 1

    output = capsys.readouterr().out
    assert "flow_locked" in output
    assert "actor" in output
    assert "nextCommand" in output
    assert not (project / ".pr-flow/last-status.json").exists()


def test_require_current_base_fetches_remote_and_rejects_stale_source(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    git_stub = CommandStub(consume=True)
    git_stub.add(["fetch", "origin", "main"])
    git_stub.add(["rev-parse", "origin/main"], stdout="base-after\n")
    git_stub.add(["merge-base", "--is-ancestor", "base-after", "feature-head"], returncode=1)
    monkeypatch.setattr(module, "git", git_stub)

    with pytest.raises(module.PrFlowError) as error:
        module.require_current_base(
            project,
            module.default_config("main"),
            "main",
            "feature-head",
            "pr-flow-complete --project .",
        )

    assert error.value.reason == "base_outdated"
    assert error.value.details["baseCommit"] == "base-after"
    assert error.value.details["sourceCommit"] == "feature-head"
    assert git_stub.calls == [
        ("fetch", "origin", "main"),
        ("rev-parse", "origin/main"),
        ("merge-base", "--is-ancestor", "base-after", "feature-head"),
    ]


def test_pr_view_fields_include_base_commit() -> None:
    assert "baseRefOid" in load_pr_flow_module().PR_VIEW_FIELDS.split(",")


def allow_current_base(git_stub, source_oid: str) -> None:
    git_stub.add(["fetch", "origin", "main"])
    git_stub.add(["rev-parse", "origin/main"], stdout="a" * 40 + "\n")
    git_stub.add(["merge-base", "--is-ancestor", "a" * 40, source_oid])


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
    base_oid: str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    is_draft: bool = False,
    body: str | None = "Existing body",
) -> str:
    payload = {
        "number": 12,
        "state": "OPEN",
        "isDraft": is_draft,
        "mergeStateStatus": "BLOCKED",
        "reviewDecision": review_decision,
        "headRefName": "feature/example",
        "baseRefName": "main",
        "baseRefOid": base_oid,
        "statusCheckRollup": checks,
    }
    if head_oid is not None:
        payload["headRefOid"] = head_oid
    if body is not None:
        payload["body"] = body
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


def _create_minimal_project_remote_template(tmp_path: Path) -> tuple[Path, Path]:
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
    git(project, "remote", "add", "origin", str(remote))
    git(project, "push", "-u", "origin", "main")
    return project, remote


def fake_project_remote_template(template_dir: Path) -> None:
    (template_dir / "project").mkdir()
    (template_dir / "remote.git").mkdir()


def fake_copy_project_remote_template(template_dir: Path, tmp_path: Path) -> tuple[Path, Path]:
    remote = copy_template(template_dir / "remote.git", tmp_path / "remote.git")
    project = copy_template(template_dir / "project", tmp_path / "project")
    return project, remote


def test_project_template_recovers_stale_lock(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        sys.modules[__name__],
        "copy_project_remote_template",
        fake_copy_project_remote_template,
    )
    template_name = f"stale-lock-{tmp_path.name}"
    lock_dir = TEMPLATE_ROOT / f"{template_name}.lock"
    lock_dir.mkdir(parents=True, exist_ok=True)
    stale_time = time.time() - TEMPLATE_LOCK_STALE_SECONDS - 1
    os.utime(lock_dir, (stale_time, stale_time))

    project, remote = ensure_project_remote_template(
        template_name,
        tmp_path,
        fake_project_remote_template,
    )

    assert project.is_dir()
    assert remote.is_dir()
    assert not lock_dir.exists()


def test_project_template_recreates_incomplete_template_after_stale_lock(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        sys.modules[__name__],
        "copy_project_remote_template",
        fake_copy_project_remote_template,
    )
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
        fake_project_remote_template,
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
    evidence_path: str | None = None,
) -> None:
    config_dir = project / ".pr-flow"
    config_dir.mkdir(parents=True, exist_ok=True)
    review_gate = {"mode": review_mode}
    if evidence_path is not None:
        review_gate["evidencePath"] = evidence_path
    config = {
        "defaults": {
            "baseBranch": "main",
            "mergeStrategy": merge_strategy,
            "reviewGate": review_gate,
            "wait": {"timeoutSeconds": 0, "pollSeconds": 0},
            "pr": {
                "bodyTemplatePath": ".pr-flow/pr-template.md",
                "requiredSections": ["Summary", "Scope", "Closing References"],
            },
        },
        "branches": {"main": {"remote": "origin"}},
    }
    (config_dir / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (config_dir / "pr-template.md").write_text(
        "## Summary\n\n<!-- summary guide -->\n\n"
        "## Scope\n\n<!-- scope guide -->\n\n"
        "## Closing References\n\n<!-- closing guide -->\n",
        encoding="utf-8",
    )


def complete_args(project: Path, *, fixes: tuple[str, ...] = ()) -> list[str]:
    args = [
        "complete",
        "--project",
        str(project),
        "--summary",
        "修复 PR Flow 创建空正文 PR",
        "--scope",
        "更新 complete、tweak、diagnose 和测试",
    ]
    for issue in fixes:
        args.extend(["--fixes", issue])
    return args


def tweak_args(project: Path, *, reason: str, fixes: tuple[str, ...] = ()) -> list[str]:
    args = [
        "tweak",
        "--project",
        str(project),
        "--reason",
        reason,
        "--summary",
        "修复 PR Flow 创建空正文 PR",
        "--scope",
        "更新 complete、tweak、diagnose 和测试",
    ]
    for issue in fixes:
        args.extend(["--fixes", issue])
    return args


def expected_pr_body(
    summary: str = "修复 PR Flow 创建空正文 PR",
    scope: str = "更新 complete、tweak、diagnose 和测试",
    fixes: tuple[str, ...] = ("98",),
) -> str:
    references = "\n".join(f"Fixes #{issue}" for issue in fixes) if fixes else "None"
    return f"## Summary\n\n{summary}\n\n## Scope\n\n{scope}\n\n## Closing References\n\n{references}\n"


def run_complete_in_process(
    tmp_path: Path,
    monkeypatch,
    *,
    pr_stdout: str | None = None,
    pr_responses: list[tuple[str, str, int]] | None = None,
    cleanup_stdout: str | None = None,
    review_mode: str = "github",
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
    write_complete_pr_flow_config(project, review_mode=review_mode, merge_strategy=merge_strategy)
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
    git_stub.add(["branch", "--show-current"], stdout="feature/example\n")
    git_stub.add(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], stdout="origin/feature/example\n")
    git_stub.add(["rev-list", "--count", "@{u}..HEAD"], stdout="0\n")
    git_stub.add(["rev-list", "--count", "HEAD..@{u}"], stdout="0\n")
    git_stub.add(["fetch", "origin", "main"])
    git_stub.add(["rev-parse", "origin/main"], stdout="a" * 40 + "\n")
    git_stub.add(["merge-base", "--is-ancestor", "a" * 40, "b" * 40])
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)
    result = invoke_pr_flow(complete_args(project), module=module)
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
        gh_stub.add(["pr", "create", "--base", "main", "--fill", "--body-file", "__placeholder__"], stdout="https://github.example/test/repo/pull/12\n")
        gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    else:
        gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())

    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], "origin/feature/example\n"),
        (["rev-list", "--count", "@{u}..HEAD"], "0\n"),
        (["rev-list", "--count", "HEAD..@{u}"], "0\n"),
        (["rev-parse", "HEAD"], head_oid + "\n"),
        (["fetch", "origin", "main"], ""),
        (["rev-parse", "origin/main"], "a" * 40 + "\n"),
        (["merge-base", "--is-ancestor", "a" * 40, head_oid], ""),
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "HEAD"], head_oid + "\n"),
        (["status", "--short"], ""),
        (["branch", "--show-current"], "feature/example\n"),
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
    result = invoke_pr_flow(tweak_args(project, reason=reason), module=module)
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
    git_stub.add(["rev-parse", "HEAD"], stdout="b" * 40 + "\n")
    allow_current_base(git_stub, "b" * 40)
    git_stub.add(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], stdout="origin/main\n")
    git_stub.add(["status", "--short"], stdout="")
    gh_stub = CommandStub()
    gh_stub.add(
        ["pr", "view", "--json", module.PR_VIEW_FIELDS],
        stdout=pr_stdout,
        stderr=pr_stderr,
        returncode=pr_returncode,
    )
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)
    result = invoke_pr_flow(["diagnose", "--project", str(project)], module=module)
    return project, result


def review_gate_config_for_test(mode: Any, evidence_path: str | None = None) -> dict:
    review_gate = {"mode": mode}
    if evidence_path is not None:
        review_gate["evidencePath"] = evidence_path
    return {"defaults": {"reviewGate": review_gate}}


def passing_review_pr(review_decision: str = "APPROVED") -> dict:
    return json.loads(
        pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision=review_decision,
            head_oid="b" * 40,
        )
    )


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
    assert "GitHub remote task: configure GitHub required review" in result.stdout
    assert "GitHub Rulesets suggestion" not in result.stdout

    config = yaml.safe_load((project / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))
    assert config["defaults"]["baseBranch"] == "main"
    assert config["defaults"]["mergeStrategy"] == "merge"
    assert config["defaults"]["reviewGate"]["mode"] == "github"
    assert "evidencePath" not in config["defaults"]["reviewGate"]
    assert (
        config["defaults"]["hotfix"]["verifyCommand"]
        == "python .build-and-verify/runtime/build_and_verify.py verify --project . --full"
    )
    assert config["defaults"]["wait"] == {"timeoutSeconds": 600, "pollSeconds": 15}
    assert config["defaults"]["pr"]["bodyTemplatePath"] == ".pr-flow/pr-template.md"
    assert config["defaults"]["pr"]["requiredSections"] == ["Summary", "Scope", "Closing References"]
    assert config["branches"]["main"]["remote"] == "origin"
    assert config["branches"]["main"]["allowHotfixPush"] is False

    template = (project / ".pr-flow" / "pr-template.md").read_text(encoding="utf-8")
    assert "## Summary" in template
    assert "## Scope" in template
    assert "## Closing References" in template
    assert "## Verification" not in template
    assert "## Risk" not in template
    assert "## Rollback" not in template
    assert "<!--" in template

    assert (project / ".pr-flow" / ".gitignore").read_text(encoding="utf-8") == "/runs/\n/last-status.json\n"


def test_complete_requires_summary_scope_before_auto_push_or_pr_create(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    gh_stub = CommandStub()
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(["complete", "--project", str(project)], module=module)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert not any(call and call[0] in {"push", "fetch"} for call in git_stub.calls)
    assert gh_stub.calls == []
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "pr_body_required"
    assert status["details"]["missingArgs"] == ["--summary", "--scope"]
    assert "--summary" in status["details"]["nextCommand"]
    assert "--scope" in status["details"]["nextCommand"]


def test_complete_reports_dispatch_when_pr_create_requires_gh_auth(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="main\n")
    git_stub.add(["rev-parse", "HEAD"], stdout="b" * 40 + "\n")
    allow_current_base(git_stub, "b" * 40)
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr="no pull request found\n", returncode=1)
    gh_stub.add(
        ["pr", "create", "--base", "main", "--fill", "--body-file", "__placeholder__"],
        stderr="gh: To get started with GitHub CLI, please run: gh auth login\n",
        returncode=4,
    )
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "gh_auth_required"
    assert status["details"]["nextCommand"] == "gh auth status"


def test_complete_reports_dispatch_when_created_pr_view_temporarily_fails(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="main\n")
    git_stub.add(["rev-parse", "HEAD"], stdout="b" * 40 + "\n")
    allow_current_base(git_stub, "b" * 40)
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr="no pull request found\n", returncode=1)
    gh_stub.add(
        ["pr", "create", "--base", "main", "--fill", "--body-file", "__placeholder__"],
        stdout="https://github.example/test/repo/pull/12\n",
    )
    gh_stub.add(
        ["pr", "view", "--json", module.PR_VIEW_FIELDS],
        stderr="GraphQL: Could not resolve to a PullRequest\n",
        returncode=1,
    )
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "gh_pr_view_transient_failed"
    assert status["details"]["transientCategory"] == "post_create_view"
    assert "complete" in status["details"]["nextCommand"]
    assert str(project) in status["details"]["nextCommand"]


def test_tweak_reports_dispatch_when_remote_branch_rules_lookup_requires_gh_auth(
    tmp_path: Path, monkeypatch
) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="feature/example\n")
    git_stub.add(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], returncode=1)
    git_stub.add(["status", "--porcelain"], stdout="")
    gh_stub = CommandStub()
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr="no pull request found\n", returncode=1)
    gh_stub.add(
        ["api", "repos/{owner}/{repo}/rules/branches/feature%2Fexample", "--jq", "length"],
        stderr="gh: To get started with GitHub CLI, please run: gh auth login\n",
        returncode=4,
    )
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(tweak_args(project, reason="small docs polish"), module=module)

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "tweak"
    assert status["details"]["reason"] == "gh_auth_required"
    assert status["details"]["nextCommand"] == "gh auth status"


def test_complete_reports_dispatch_when_pr_merge_requires_gh_auth(tmp_path: Path, monkeypatch) -> None:
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid="b" * 40,
        ),
        cleanup_stdout=cleanup_pr_view_json(),
        git_responses=[(["rev-parse", "HEAD"], "b" * 40 + "\n", 0)],
        merge_returncode=4,
        merge_stderr="gh: To get started with GitHub CLI, please run: gh auth login\n",
    )

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "gh_auth_required"
    assert status["details"]["nextCommand"] == "gh auth status"


@pytest.mark.parametrize("bad_fix", ["41,43", "#98", "abc", "0", "-1"])
@pytest.mark.parametrize(
    ("command_args", "command"),
    [
        (lambda project, fixes: complete_args(project, fixes=fixes), "complete"),
        (lambda project, fixes: tweak_args(project, reason="small docs polish", fixes=fixes), "tweak"),
    ],
)
def test_pr_body_commands_reject_invalid_fixes_before_git_or_gh_calls(
    tmp_path: Path, monkeypatch, bad_fix: str, command_args, command: str
) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    gh_stub = CommandStub()
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(command_args(project, (bad_fix,)), module=module)

    assert result.returncode == 1
    assert "status: REPLY_OR_FIX_REQUIRED" in result.stdout
    assert not any(call and call[0] in {"fetch", "push", "checkout"} for call in git_stub.calls)
    assert gh_stub.calls == []
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "REPLY_OR_FIX_REQUIRED"
    assert status["command"] == command
    assert status["details"]["reason"] == "invalid_fixes"
    assert status["details"]["invalidFixes"] == [bad_fix]
    assert status["details"]["nextAction"] == (
        "Pass each issue number separately, for example --fixes 41 --fixes 43 --fixes 44."
    )


@pytest.mark.parametrize(
    ("command_args", "command"),
    [
        (lambda project: complete_args(project, fixes=("None",)), "complete"),
        (lambda project: tweak_args(project, reason="small docs polish", fixes=("None",)), "tweak"),
    ],
)
def test_pr_body_commands_reject_none_fixes_with_remove_guidance(
    tmp_path: Path, monkeypatch, command_args, command: str
) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    gh_stub = CommandStub()
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(command_args(project), module=module)

    assert result.returncode == 1
    assert "status: REPLY_OR_FIX_REQUIRED" in result.stdout
    assert not any(call and call[0] in {"fetch", "push", "checkout"} for call in git_stub.calls)
    assert gh_stub.calls == []
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "REPLY_OR_FIX_REQUIRED"
    assert status["command"] == command
    assert status["details"]["reason"] == "invalid_fixes"
    assert status["details"]["invalidFixes"] == ["None"]
    assert status["details"]["nextAction"] == "Remove --fixes when there is no issue to close."


def test_tweak_requires_summary_scope_before_pr_sync(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    gh_stub = CommandStub()
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(["tweak", "--project", str(project), "--reason", "small docs polish"], module=module)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert not any(call and call[0] in {"fetch", "push", "checkout"} for call in git_stub.calls)
    assert gh_stub.calls == []
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "tweak"
    assert status["details"]["reason"] == "pr_body_required"
    assert status["details"]["missingArgs"] == ["--summary", "--scope"]


def test_complete_stops_when_body_template_is_missing_required_section(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    (project / ".pr-flow" / "pr-template.md").write_text("## Summary\n\n## Scope\n", encoding="utf-8")
    git_stub = CommandStub()
    gh_stub = CommandStub()
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert not any(call and call[0] in {"fetch", "push", "checkout"} for call in git_stub.calls)
    assert gh_stub.calls == []
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "pr_body_required"
    assert status["details"]["templatePath"].replace("\\", "/").endswith(".pr-flow/pr-template.md")
    assert status["details"]["missingSections"] == ["Closing References"]
    assert "Closing References" in status["details"]["nextAction"]


def test_complete_and_tweak_share_three_section_body_renderer(tmp_path: Path) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    config = yaml.safe_load((project / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))

    complete_body = module.render_pr_body(project, config, "修复 PR Flow 创建空正文 PR", "更新 complete、tweak、diagnose 和测试", ["98"])
    tweak_body = module.render_pr_body(project, config, "修复 PR Flow 创建空正文 PR", "更新 complete、tweak、diagnose 和测试", ["98"])

    assert complete_body == expected_pr_body()
    assert tweak_body == expected_pr_body()


def test_create_pr_uses_generated_body_file(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    body = expected_pr_body()
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "create", "--base", "main", "--fill", "--body-file", "__placeholder__"], stdout="https://github.example/test/repo/pull/12\n")
    gh_stub.add(
        ["pr", "view", "--json", module.PR_VIEW_FIELDS],
        stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid="b" * 40,
            body=body,
        ),
    )
    monkeypatch.setattr(module, "gh", gh_stub)

    pr = module.create_pr(project, {"defaults": {"baseBranch": "main"}}, body)

    assert pr["number"] == 12
    assert gh_stub.body_files[0]["args"][:-1] == ("pr", "create", "--base", "main", "--fill", "--body-file")
    assert gh_stub.body_files[0]["body"] == body


def test_create_pr_retries_transient_eof_when_syncing_created_pr(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    body = expected_pr_body()
    monkeypatch.setenv("PR_FLOW_GH_PR_VIEW_RETRIES", "1")
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "create", "--base", "main", "--fill", "--body-file", "__placeholder__"], stdout="created\n")
    gh_stub.add(
        ["pr", "view", "--json", module.PR_VIEW_FIELDS],
        stderr='Post "https://api.github.com/graphql": EOF\n',
        returncode=1,
    )
    gh_stub.add(
        ["pr", "view", "--json", module.PR_VIEW_FIELDS],
        stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid="b" * 40,
            body=body,
        ),
    )
    monkeypatch.setattr(module, "gh", gh_stub)

    pr = module.create_pr(project, {"defaults": {"baseBranch": "main"}}, body)

    assert pr["number"] == 12
    assert len(gh_stub.calls) == 3
    assert gh_stub.body_files[0]["body"] == body


def test_create_pr_missing_after_success_does_not_report_create_output_as_view_failure(
    tmp_path: Path, monkeypatch
) -> None:
    from tests.support.command_stubs import CommandStub

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    body = expected_pr_body()
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "create", "--base", "main", "--fill", "--body-file", "__placeholder__"], stdout="created\n")
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr="no pull request found\n", returncode=1)
    monkeypatch.setattr(module, "gh", gh_stub)

    with pytest.raises(module.PrFlowError) as error:
        module.create_pr(project, {"defaults": {"baseBranch": "main"}}, body, "python pr_flow.py complete --project .")

    assert error.value.reason == "gh_pr_view_transient_failed"
    assert error.value.details["transientCategory"] == "post_create_view"
    assert "nextCommand" in error.value.details
    assert "returncode" not in error.value.details
    assert "stdout" not in error.value.details
    assert "stderr" not in error.value.details


def test_complete_fills_existing_empty_body_before_checks(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    head_oid = "b" * 40
    pr_stdout = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid=head_oid,
        body="<!-- template comment -->",
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "edit", "12", "--body-file", "__placeholder__"])
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], "origin/feature/example\n"),
        (["rev-list", "--count", "@{u}..HEAD"], "0\n"),
        (["rev-list", "--count", "HEAD..@{u}"], "0\n"),
        (["rev-parse", "HEAD"], head_oid + "\n"),
        (["status", "--short"], ""),
        (["branch", "--show-current"], "feature/example\n"),
        (["branch", "--show-current"], "feature/example\n"),
        (["push", "origin", "--delete", "feature/example"], ""),
        (["ls-remote", "--heads", "origin", "feature/example"], ""),
        (["checkout", "main"], ""),
        (["pull", "--ff-only", "origin", "main"], ""),
        (["branch", "-d", "feature/example"], ""),
        (["branch", "--show-current"], "main\n"),
    ]:
        git_stub.add(git_args, stdout=stdout)
    allow_current_base(git_stub, head_oid)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert gh_stub.calls[2][:3] == ("pr", "edit", "12")
    assert gh_stub.calls[4][:2] == ("pr", "merge")
    assert gh_stub.body_files[0]["body"] == expected_pr_body(fixes=())


def test_complete_appends_repeated_fixes_to_existing_human_body(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    head_oid = "b" * 40
    pr_stdout = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid=head_oid,
        body="Human body",
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "edit", "12", "--body-file", "__placeholder__"])
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], "origin/feature/example\n"),
        (["rev-list", "--count", "@{u}..HEAD"], "0\n"),
        (["rev-list", "--count", "HEAD..@{u}"], "0\n"),
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
    allow_current_base(git_stub, head_oid)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(complete_args(project, fixes=("98", "99")), module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "cleanup_complete"
    assert len(gh_stub.body_files) == 1
    assert gh_stub.body_files[0]["body"] == "Human body\n\n## Closing References\n\nFixes #98\nFixes #99\n"


def test_complete_continues_when_existing_human_body_already_has_fixes(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    head_oid = "b" * 40
    pr_stdout = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid=head_oid,
        body="Human body\n\n## Closing References\n\nFixes #98\n",
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], "origin/feature/example\n"),
        (["rev-list", "--count", "@{u}..HEAD"], "0\n"),
        (["rev-list", "--count", "HEAD..@{u}"], "0\n"),
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
    allow_current_base(git_stub, head_oid)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(complete_args(project, fixes=("98",)), module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert all(call[:2] != ("pr", "edit") for call in gh_stub.calls)


def test_closing_reference_match_does_not_treat_prefix_issue_as_present() -> None:
    module = load_pr_flow_module()

    assert module.has_closing_reference("Human body\n\nFixes #980\n", "98") is False
    assert module.has_closing_reference("Human body\n\nFixes #98\n", "98") is True


def test_complete_keeps_existing_human_body_without_fixes(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    pr_stdout = pr_view_json(
        checks=[{"name": "ci", "status": "QUEUED", "conclusion": None}],
        review_decision="APPROVED",
        head_oid="b" * 40,
        body="Human body",
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    git_stub = CommandStub(consume=True)
    git_stub.add(["branch", "--show-current"], stdout="feature/example\n")
    git_stub.add(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], stdout="origin/feature/example\n")
    git_stub.add(["rev-list", "--count", "@{u}..HEAD"], stdout="0\n")
    git_stub.add(["rev-list", "--count", "HEAD..@{u}"], stdout="0\n")
    allow_current_base(git_stub, "b" * 40)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(complete_args(project, fixes=()), module=module)

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    assert all(call[:2] != ("pr", "edit") for call in gh_stub.calls)
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "checks_pending"


def test_init_without_confirmed_config_does_not_write_defaults(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("init", "--project", str(project), "--base-branch", "main")

    assert result.returncode == 2
    assert "confirmed config required" in result.stdout
    assert "--base-branch no longer generates defaults" in result.stdout
    assert "defaults and branches" in result.stdout
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
        == "python .build-and-verify/runtime/build_and_verify.py verify --project . --full"
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
    assert "即使仓库已存在 `.pr-flow/config.yaml`" in skill_text
    assert "不能代替用户回答或确认" in skill_text
    assert "完整问答" not in skill_text


def test_pr_flow_complete_and_tweak_skills_show_body_args() -> None:
    complete = (REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-complete" / "SKILL.md").read_text(encoding="utf-8")
    tweak = (REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-tweak" / "SKILL.md").read_text(encoding="utf-8")

    for text in (complete, tweak):
        assert "--summary" in text
        assert "--scope" in text
        assert "--fixes" in text
    assert "--reason" in tweak


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
        "automatic inspection",
        "default PR target branch",
        "branch protection",
        "PR status checks",
        "CodeQL security check",
        "hotfix",
        "merge methods",
        "GitHub 推荐配置",
        "最终写入确认",
    ]:
        assert scenario in combined
    for template_term in ["固定问题", "固定选项", "选择后果", "跳转规则"]:
        assert template_term in combined
    assert "每次只提出一个问题" in combined


def test_pr_flow_init_questionnaire_uses_latest_flow() -> None:
    init_dir = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-init"
    questionnaire = (init_dir / "references" / "questionnaire.md").read_text(encoding="utf-8")

    ordered_sections = [
        "## 场景：automatic inspection",
        "## 场景：default PR target branch",
        "## 场景：branch protection",
        "## 场景：CodeQL security check",
        "## 场景：PR status checks",
        "## 场景：hotfix",
        "## 场景：authorization phrase",
        "## 场景：merge methods",
        "## 场景：GitHub 推荐配置",
        "## 场景：最终写入确认",
    ]
    positions = [questionnaire.index(section) for section in ordered_sections]
    assert positions == sorted(positions)
    assert "GitHub Rulesets" in questionnaire
    assert "每次只提出一个问题" in questionnaire
    assert "Require a pull request before merging" in questionnaire
    assert "required_approving_review_count: 0" in questionnaire
    assert "PR status checks" in questionnaire
    assert "Require status checks to pass before merging" in questionnaire
    assert "CodeQL security check" in questionnaire
    assert "开启" in questionnaire
    assert "不开启" in questionnaire
    assert "Require code scanning results" in questionnaire
    assert "CodeQL" in questionnaire
    assert "GitHub 默认阈值" in questionnaire
    assert "CodeQL Default setup（CodeQL 默认配置）" in questionnaire
    codeql_section = questionnaire.split("## 场景：CodeQL security check", 1)[1].split("## 场景：PR status checks", 1)[0]
    codeql_options_block = codeql_section.split("固定选项：", 1)[1].split("选择后果：", 1)[0]
    codeql_options = [line for line in codeql_options_block.splitlines() if line.startswith("- ")]
    assert codeql_options == [
        "- 开启：启用 CodeQL Default setup（CodeQL 默认配置）；在 GitHub Rulesets（GitHub 规则集）中配置 `Require code scanning results`（要求代码扫描结果），选择 `CodeQL` 作为 code scanning tool（代码扫描工具），阈值采用 GitHub 默认阈值。",
        "- 不开启：不生成 CodeQL（代码扫描工具）远端待办。",
    ]
    assert "开启：继续 PR status checks（拉取请求状态检查）场景；后续只展示非安全扫描 check name（检查名称）" in codeql_section
    assert "CodeQL scan producer（CodeQL 扫描结果来源）" not in codeql_section
    assert "reuse existing authorization phrase" in questionnaire
    assert "create new authorization phrase" in questionnaire
    assert "authorization.phraseHashAlgorithm: md5" in questionnaire
    assert "authorization.phraseHash" in questionnaire
    assert "merge methods" in questionnaire
    assert "not inspected" in questionnaire
    assert "no access" in questionnaire
    assert "不能声明远端状态已确认" in questionnaire
    assert "PR Flow（拉取请求流程）合并前使用哪种审查门禁" not in questionnaire
    branch_protection_section = questionnaire.split("## 场景：branch protection", 1)[1].split("## 场景：CodeQL security check", 1)[0]
    assert "defaults.reviewGate.mode: github" in branch_protection_section
    assert "defaults.reviewGate.mode: skip" in branch_protection_section
    assert "暂不配置远端保护" in branch_protection_section
    assert "保持现有或默认 `reviewGate.mode` 不变" not in branch_protection_section
    assert "不得派生 `defaults.reviewGate.mode: github`" not in branch_protection_section
    assert "从 automatic inspection（自动检查）得到的 remote branches（远端分支）逐项列出" in branch_protection_section
    assert "Restrict deletions" in branch_protection_section
    assert "限制删除" in branch_protection_section
    assert "Block force pushes" in branch_protection_section
    assert "阻止强制推送" in branch_protection_section
    assert "发布分支" not in branch_protection_section
    pr_status_section = questionnaire.split("## 场景：PR status checks", 1)[1].split("## 场景：hotfix", 1)[0]
    assert "每个 check name（检查名称）必须附带用途说明" in pr_status_section
    assert "来源 workflow/job（工作流/任务）" in pr_status_section
    assert "验证内容" in pr_status_section
    assert "失败影响" in pr_status_section
    assert "非安全扫描 check name（检查名称）" in pr_status_section
    for forbidden_check in [
        "`Analyze Python`",
        "Analyze Python",
        "`Analyze (python)`",
        "Analyze (python)",
        "`Analyze (actions)`",
        "Analyze (actions)",
        "`CodeQL` status check",
    ]:
        assert forbidden_check not in pr_status_section
    final_write_section = questionnaire.split("## 场景：最终写入确认", 1)[1].split("## 禁止重复问题", 1)[0]
    final_options_block = final_write_section.split("固定选项：", 1)[1].split("选择后果：", 1)[0]
    final_options = [line for line in final_options_block.splitlines() if line.startswith("- ")]
    assert final_options == [
        "- 不写入，放弃本次配置。",
        "- 只写入本地配置。",
        "- 按 remote tasks（远端待办）完成 GitHub（代码托管平台）配置，然后再写入本地配置。",
    ]
    assert "GitHub（代码托管平台）配置由 agent（代理）执行" in final_write_section
    assert "插件不提供 GitHub（代码托管平台）配置脚本能力" in final_write_section


def test_pr_flow_init_draft_and_validation_are_user_readable() -> None:
    init_dir = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-init"
    config_draft = (init_dir / "references" / "config-draft.md").read_text(encoding="utf-8")
    validation = (init_dir / "references" / "validation.md").read_text(encoding="utf-8")

    for heading in ["本地将写入", "GitHub 当前状态", "GitHub 推荐配置", "validation results"]:
        assert heading in config_draft
    assert "禁止展示完整 YAML" in config_draft
    assert "```yaml" not in config_draft
    assert "仅当 `allowHotfixPush: true`" in config_draft
    assert "defaults.reviewGate.mode" in config_draft
    assert "不单独提问" in config_draft
    assert "选择暂不配置远端保护时派生为 `skip`" in config_draft
    assert "选择暂不配置远端保护时保持现有或默认值不变" not in config_draft
    assert "not inspected" in config_draft
    assert "no access" in config_draft
    assert "不代表 init（初始化）已经写入远端" in config_draft
    assert "新增或识别 PR status checks" in config_draft
    assert "authorization must stay top-level" in config_draft

    for heading in ["error（错误）", "warning（警告）", "remote tasks（远端待办）"]:
        assert heading in validation
    assert "not inspected" in validation
    assert "no access" in validation
    assert "不能声明远端状态已确认" in validation
    for text in [config_draft, validation]:
        assert "启用 CodeQL Default setup（CodeQL 默认配置）" in text
        assert "Require code scanning results" in text
        assert "CodeQL" in text
        assert "GitHub 默认阈值" in text
        assert "CodeQL scan producer" not in text
        assert "defaultSetup" not in text
        assert "default_setup" not in text


def test_pr_flow_init_skill_uses_remote_tasks_not_setup_suggestions() -> None:
    skill_path = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-init" / "SKILL.md"
    skill_text = skill_path.read_text(encoding="utf-8")

    assert "remote tasks（远端待办）" in skill_text
    assert "warning（警告）或 setup suggestion（配置建议）" not in skill_text


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


def test_pr_flow_skill_shows_source_repo_diagnose_entrypoint() -> None:
    skill_path = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow" / "SKILL.md"
    skill_text = skill_path.read_text(encoding="utf-8")

    assert "python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py diagnose --project ." in skill_text
    assert "python scripts/pr_flow.py diagnose --project ." not in skill_text


@pytest.mark.parametrize(
    ("skill_name", "command"),
    [
        ("pr-flow-complete", 'complete --project . --summary "修复 PR Flow 创建空正文 PR" --scope "更新 complete、tweak、diagnose 和测试" --fixes 98'),
        ("pr-flow-cleanup", "cleanup --project . --pr <number>"),
        ("pr-flow-hotfix", "hotfix --project . --target main --authorization-phrase <phrase>"),
        ("pr-flow-tweak", 'tweak --project . --reason "small docs polish" --summary "更新 PR Flow 文档措辞" --scope "只修改 PR Flow 文档" --fixes 98'),
    ],
)
def test_pr_flow_command_skills_show_source_repo_script_entrypoint(skill_name: str, command: str) -> None:
    skill_path = REPO_ROOT / "plugins" / "pr-flow" / "skills" / skill_name / "SKILL.md"
    skill_text = skill_path.read_text(encoding="utf-8")

    assert f"python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py {command}" in skill_text
    assert "python ../pr-flow/scripts/pr_flow.py" not in skill_text


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
    config["setup"] = {
        "github": {
            "requiredChecks": ["ci"],
            "requiredReview": True,
            "codeScanning": {"tool": "CodeQL"},
        }
    }
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
    assert written["setup"]["github"]["codeScanning"] == {"tool": "CodeQL"}
    serialized_written = json.dumps(written, sort_keys=True)
    for forbidden_field in ["defaultSetup", "default_setup", "codeqlDefaultSetup", "codeql_default_setup"]:
        assert forbidden_field not in serialized_written
    assert (project / ".pr-flow" / "pr-template.md").is_file()
    assert (project / ".pr-flow" / ".gitignore").read_text(encoding="utf-8") == "/runs/\n/last-status.json\n"

    combined_output = validate_result.stdout + init_result.stdout
    assert "remote task: enable CodeQL Default setup" in validate_result.stdout
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
                    "reviewGate": {"mode": "github"},
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
    assert "remote task: configure GitHub required review" in result.stdout
    assert "remote task: configure GitHub Rulesets required checks" in result.stdout
    assert not (project / ".pr-flow" / "config.yaml").exists()


def test_validate_reports_codeql_default_setup_tasks(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = default_pr_flow_config_for_test()
    config["setup"] = {"github": {"codeScanning": {"tool": "CodeQL"}}}
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("validate", "--project", str(project), "--config", str(draft))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "remote task: enable CodeQL Default setup" in result.stdout
    assert "remote task: configure GitHub Rulesets CodeQL code scanning" in result.stdout
    assert "CodeQL scan producer" not in result.stdout


def test_validate_reports_codeql_default_setup_even_with_existing_codeql_workflow(tmp_path: Path) -> None:
    project = tmp_path / "project"
    workflow = project / ".github" / "workflows" / "codeql.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("uses: github/codeql-action/analyze@v4\n", encoding="utf-8")
    config = default_pr_flow_config_for_test()
    config["setup"] = {"github": {"codeScanning": {"tool": "CodeQL"}}}
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("validate", "--project", str(project), "--config", str(draft))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "remote task: enable CodeQL Default setup" in result.stdout
    assert "remote task: configure GitHub Rulesets CodeQL code scanning" in result.stdout
    assert "CodeQL scan producer" not in result.stdout


def test_validate_does_not_call_gh_cli_or_github_api(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    project = tmp_path / "project"
    project.mkdir()
    config = default_pr_flow_config_for_test()
    config["setup"] = {"github": {"codeScanning": {"tool": "CodeQL"}}}
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    module = load_pr_flow_module()
    gh_stub = CommandStub()
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(["validate", "--project", str(project), "--config", str(draft)], module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "remote task: enable CodeQL Default setup" in result.stdout
    assert gh_stub.calls == []


@pytest.mark.parametrize("review_mode", ["github", "skip"])
def test_validate_accepts_supported_review_gate_modes(tmp_path: Path, review_mode: str) -> None:
    config = default_pr_flow_config_for_test()
    config["defaults"]["reviewGate"] = {"mode": review_mode}
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("validate", "--config", str(draft))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: validation_passed" in result.stdout
    assert "defaults.reviewGate.evidencePath" not in result.stdout
    assert "review-pass.json" not in result.stdout


def test_validate_warns_when_supported_review_gate_keeps_deprecated_evidencePath(tmp_path: Path) -> None:
    config = default_pr_flow_config_for_test()
    config["defaults"]["reviewGate"] = {"mode": "github", "evidencePath": ".pr-flow/review-pass.json"}
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("validate", "--config", str(draft))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: validation_passed" in result.stdout
    assert "warning: defaults.reviewGate.evidencePath is deprecated and is not read" in result.stdout


@pytest.mark.parametrize("review_mode", ["local", "dual"])
def test_validate_rejects_removed_review_gate_modes(tmp_path: Path, review_mode: str) -> None:
    config = default_pr_flow_config_for_test()
    config["defaults"]["reviewGate"] = {"mode": review_mode, "evidencePath": ".pr-flow/review-pass.json"}
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("validate", "--config", str(draft))

    assert result.returncode == 1
    assert "status: validation_failed" in result.stdout
    assert f"error: defaults.reviewGate.mode unsupported: {review_mode}" in result.stdout
    assert "remote task: document review-pass.json evidence contract" not in result.stdout
    assert "defaults.reviewGate.evidencePath missing" not in result.stdout


@pytest.mark.parametrize("review_mode", [[], {}, None, 1, ""])
def test_validate_rejects_invalid_review_gate_mode_values(tmp_path: Path, review_mode) -> None:
    config = default_pr_flow_config_for_test()
    config["defaults"]["reviewGate"] = {"mode": review_mode}
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("validate", "--config", str(draft))

    assert result.returncode == 1
    assert "status: validation_failed" in result.stdout
    assert "error: defaults.reviewGate.mode unsupported:" in result.stdout
    assert "remote task: configure GitHub required review" not in result.stdout


def test_init_rejects_removed_review_gate_modes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = default_pr_flow_config_for_test()
    config["defaults"]["reviewGate"] = {"mode": "local", "evidencePath": ".pr-flow/review-pass.json"}
    draft = tmp_path / "confirmed.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("init", "--project", str(project), "--config", str(draft))

    assert result.returncode == 1
    assert "status: validation_failed" in result.stdout
    assert "error: defaults.reviewGate.mode unsupported: local" in result.stdout


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
    assert "error: defaults.reviewGate.mode unsupported: local" in result.stdout


def test_validate_reports_errors_for_invalid_wait_shape(tmp_path: Path) -> None:
    config = default_pr_flow_config_for_test()
    config["defaults"]["wait"] = "nope"
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("validate", "--config", str(draft))

    assert result.returncode == 1
    assert "error: defaults.wait must be a mapping" in result.stdout


def test_validate_reports_errors_for_invalid_wait_values(tmp_path: Path) -> None:
    config = default_pr_flow_config_for_test()
    config["defaults"]["wait"] = {"timeoutSeconds": "slow", "pollSeconds": 0}
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run("validate", "--config", str(draft))

    assert result.returncode == 1
    assert "error: defaults.wait.timeoutSeconds must be a positive integer" in result.stdout
    assert "error: defaults.wait.pollSeconds must be a positive integer" in result.stdout


def test_validate_reports_bad_yaml_as_structured_error(tmp_path: Path) -> None:
    draft = tmp_path / "draft.yaml"
    draft.write_text("defaults: [\n", encoding="utf-8")

    result = run("validate", "--config", str(draft))

    assert result.returncode == 1
    assert "status: validation_failed" in result.stdout
    assert "error: config YAML parse failed" in result.stdout
    assert "Traceback" not in result.stderr


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
            "error: defaults.reviewGate.mode unsupported: local",
        ),
        (
            lambda config: config["setup"]["github"].update({"autoDeleteHeadBranch": True}),
            "warning: GitHub auto-delete head branch overlaps with pr-flow cleanup",
        ),
        (
            lambda config: config["setup"]["github"].update({"requiredReviews": True}),
            "remote task: tweak cannot bypass GitHub required review",
        ),
        (
            lambda config: config["defaults"].update({"mergeStrategy": "fast-forward"}),
            "error: defaults.mergeStrategy unsupported: fast-forward",
        ),
    ],
)
def test_validate_dependency_matrix(tmp_path: Path, mutate, expected: str) -> None:
    config = {
        "defaults": {
            "baseBranch": "main",
            "mergeStrategy": "merge",
            "reviewGate": {"mode": "github"},
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


def test_diagnose_outputs_dispatch_required_without_upstream(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_minimal_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="feature/no-upstream\n")
    git_stub.add(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        stderr="fatal: no upstream configured\n",
        returncode=128,
    )
    git_stub.add(["status", "--short"], stdout="")
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", CommandStub())

    result = invoke_pr_flow(["diagnose", "--project", str(project)], module=module)

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["branch"] == "feature/no-upstream"
    assert status["details"]["baseBranch"] == "main"
    assert status["details"]["reason"] == "missing_upstream"
    assert " complete " in f" {status['details']['nextCommand']} "
    assert "--summary" in status["details"]["nextCommand"]
    assert "--scope" in status["details"]["nextCommand"]


def test_complete_auto_pushes_clean_unprotected_branch_without_upstream(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="feature/no-upstream\n")
    git_stub.add(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        stderr="fatal: no upstream configured\n",
        returncode=128,
    )
    git_stub.add(["status", "--porcelain"], stdout="")
    git_stub.add(["push", "-u", "origin", "feature/no-upstream"])
    git_stub.add(["rev-parse", "HEAD"], stdout="a" * 40 + "\n")
    allow_current_base(git_stub, "a" * 40)
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr="no pull requests found for branch\n", returncode=1)
    gh_stub.add(["api", "repos/{owner}/{repo}/rules/branches/feature%2Fno-upstream", "--jq", "length"], stdout="0\n")
    gh_stub.add(["pr", "create", "--base", "main", "--fill", "--body-file", "__placeholder__"], stdout="https://github.example/test/repo/pull/12\n")
    pending_pr = pr_view_json(checks=[{"name": "ci", "status": "QUEUED"}], head_oid="a" * 40)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pending_pr)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pending_pr)
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    assert ("push", "-u", "origin", "feature/no-upstream") in git_stub.calls
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "checks_pending"


def test_complete_auto_pushes_existing_pr_when_local_branch_is_ahead(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    pending_pr = pr_view_json(checks=[{"name": "ci", "status": "QUEUED"}], head_oid="a" * 40)
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pending_pr)
    gh_stub.add(["api", "repos/{owner}/{repo}/rules/branches/feature%2Fexample", "--jq", "length"], stdout="0\n")
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pending_pr)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="feature/example\n")
    git_stub.add(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], stdout="origin/feature/example\n")
    git_stub.add(["rev-list", "--count", "@{u}..HEAD"], stdout="1\n")
    git_stub.add(["rev-list", "--count", "HEAD..@{u}"], stdout="0\n")
    git_stub.add(["status", "--porcelain"], stdout="")
    git_stub.add(["push"])
    allow_current_base(git_stub, "a" * 40)
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    assert ("push",) in git_stub.calls
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "checks_pending"


@pytest.mark.parametrize(
    ("args_factory", "command"),
    [
        (complete_args, "complete"),
        (lambda project: tweak_args(project, reason="small docs polish"), "tweak"),
    ],
)
def test_lifecycle_refuses_auto_push_when_upstream_has_new_commits(
    tmp_path: Path,
    monkeypatch,
    args_factory,
    command: str,
) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    pending_pr = pr_view_json(checks=[{"name": "ci", "status": "QUEUED"}], head_oid="a" * 40)
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pending_pr)
    gh_stub.add(["api", "repos/{owner}/{repo}/rules/branches/feature%2Fexample", "--jq", "length"], stdout="0\n")
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="feature/example\n")
    git_stub.add(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], stdout="origin/feature/example\n")
    git_stub.add(["rev-list", "--count", "@{u}..HEAD"], stdout="1\n")
    git_stub.add(["rev-list", "--count", "HEAD..@{u}"], stdout="1\n")
    git_stub.add(["status", "--porcelain"], stdout="")
    git_stub.add(["push"])
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(args_factory(project), module=module)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert not any(call and call[0] == "push" for call in git_stub.calls)
    assert not any(call and call[0] == "api" for call in gh_stub.calls)
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == command
    assert status["details"]["reason"] == "upstream_branch_diverged"
    assert status["details"]["aheadCount"] == 1
    assert status["details"]["behindCount"] == 1
    assert status["details"]["syncCommand"] == "git pull --rebase"
    assert command in status["details"]["nextCommand"]


def test_complete_refuses_auto_push_when_worktree_dirty(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="feature/no-upstream\n")
    git_stub.add(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        stderr="fatal: no upstream configured\n",
        returncode=128,
    )
    git_stub.add(["status", "--porcelain"], stdout=" M README.md\n")
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr="no pull requests found for branch\n", returncode=1)
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert not any(call and call[0] == "push" for call in git_stub.calls)
    assert not any(call and call[0] == "api" for call in gh_stub.calls)
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "worktree_dirty"
    assert status["details"]["dirtyFiles"] == [" M README.md"]


def test_complete_refuses_auto_push_when_remote_branch_has_active_rules(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="feature/no-upstream\n")
    git_stub.add(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        stderr="fatal: no upstream configured\n",
        returncode=128,
    )
    git_stub.add(["status", "--porcelain"], stdout="")
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr="no pull requests found for branch\n", returncode=1)
    gh_stub.add(["api", "repos/{owner}/{repo}/rules/branches/feature%2Fno-upstream", "--jq", "length"], stdout="1\n")
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert not any(call and call[0] == "push" for call in git_stub.calls)
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "protected_branch_auto_push_blocked"
    assert status["details"]["branch"] == "feature/no-upstream"


def test_complete_refuses_auto_push_when_remote_rules_lookup_fails(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="feature/no-upstream\n")
    git_stub.add(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        stderr="fatal: no upstream configured\n",
        returncode=128,
    )
    git_stub.add(["status", "--porcelain"], stdout="")
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr="no pull requests found for branch\n", returncode=1)
    gh_stub.add(
        ["api", "repos/{owner}/{repo}/rules/branches/feature%2Fno-upstream", "--jq", "length"],
        stderr="api failed\n",
        returncode=1,
    )
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert not any(call and call[0] == "push" for call in git_stub.calls)
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "remote_branch_rules_lookup_failed"


def test_complete_outputs_push_required_when_auto_push_fails(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="feature/no-upstream\n")
    git_stub.add(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        stderr="fatal: no upstream configured\n",
        returncode=128,
    )
    git_stub.add(["status", "--porcelain"], stdout="")
    git_stub.add(["push", "-u", "origin", "feature/no-upstream"], stderr="push failed\n", returncode=1)
    git_stub.add(["rev-parse", "HEAD"], stdout="a" * 40 + "\n")
    allow_current_base(git_stub, "a" * 40)
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr="no pull requests found for branch\n", returncode=1)
    gh_stub.add(["api", "repos/{owner}/{repo}/rules/branches/feature%2Fno-upstream", "--jq", "length"], stdout="0\n")
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 1
    assert "status: PUSH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "git_push_failed"
    assert status["details"]["nextCommand"] == "git push -u origin feature/no-upstream"


def test_tweak_auto_pushes_clean_unprotected_branch_without_upstream(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="feature/no-upstream\n")
    git_stub.add(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        stderr="fatal: no upstream configured\n",
        returncode=128,
    )
    git_stub.add(["status", "--porcelain"], stdout="")
    git_stub.add(["push", "-u", "origin", "feature/no-upstream"])
    git_stub.add(["rev-parse", "HEAD"], stdout="a" * 40 + "\n")
    allow_current_base(git_stub, "a" * 40)
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr="no pull requests found for branch\n", returncode=1)
    gh_stub.add(["api", "repos/{owner}/{repo}/rules/branches/feature%2Fno-upstream", "--jq", "length"], stdout="0\n")
    gh_stub.add(["pr", "create", "--base", "main", "--fill", "--body-file", "__placeholder__"], stdout="https://github.example/test/repo/pull/12\n")
    pending_pr = pr_view_json(checks=[{"name": "ci", "status": "QUEUED"}], head_oid="a" * 40)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pending_pr)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pending_pr)
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(tweak_args(project, reason="small docs polish"), module=module)

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    assert ("push", "-u", "origin", "feature/no-upstream") in git_stub.calls
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "tweak"
    assert status["details"]["reason"] == "checks_pending"
    action = status["details"].get("nextAction") or status["details"].get("nextCommand")
    assert action is not None
    assert "checks" in action


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


def test_diagnose_retries_transient_eof_without_repeated_stop_output(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    monkeypatch.setenv("PR_FLOW_GH_PR_VIEW_RETRIES", "1")
    pr_stdout = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid="b" * 40,
        body="Human body",
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr='Post "https://api.github.com/graphql": EOF\n', returncode=1)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    git_stub = CommandStub(consume=True)
    git_stub.add(["branch", "--show-current"], stdout="feature/example\n")
    git_stub.add(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], stdout="origin/feature/example\n")
    git_stub.add(["status", "--short"], stdout="")
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(["diagnose", "--project", str(project)], module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("status:") == 1
    assert "status: ready" in result.stdout
    assert gh_stub.calls.count(("pr", "view", "--json", module.PR_VIEW_FIELDS)) == 2


def test_diagnose_reports_dispatch_when_transient_eof_retries_are_exhausted(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    monkeypatch.setenv("PR_FLOW_GH_PR_VIEW_RETRIES", "1")
    gh_stub = CommandStub(consume=True)
    for _ in range(2):
        gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr='Post "https://api.github.com/graphql": EOF\n', returncode=1)
    git_stub = CommandStub(consume=True)
    git_stub.add(["branch", "--show-current"], stdout="feature/example\n")
    git_stub.add(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], stdout="origin/feature/example\n")
    git_stub.add(["status", "--short"], stdout="")
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(["diagnose", "--project", str(project)], module=module)

    assert result.returncode == 1
    assert result.stdout.count("status:") == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    assert "gh_pr_view_transient_failed" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["details"]["reason"] == "gh_pr_view_transient_failed"
    assert status["details"]["transientCategory"] == "eof"
    assert status["details"]["retryAttempts"] == 1
    assert "diagnose" in status["details"]["nextCommand"]
    assert "diagnose --project" in status["details"]["nextCommand"]
    assert str(project) in status["details"]["nextCommand"]


def test_diagnose_reports_dispatch_for_gh_auth_failure(tmp_path: Path, monkeypatch) -> None:
    project, result = run_diagnose_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout="",
        pr_stderr="gh: To get started with GitHub CLI, please run: gh auth login\n",
        pr_returncode=4,
    )

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    assert "gh_auth_required" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["details"]["reason"] == "gh_auth_required"
    assert status["details"]["nextCommand"] == "gh auth status"


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


def test_diagnose_on_feature_branch_without_pr_reports_dispatch_required(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_minimal_pr_flow_config(project)
    git_stub = CommandStub()
    git_stub.add(["branch", "--show-current"], stdout="feature/ready\n")
    git_stub.add(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], stdout="origin/feature/ready\n")
    git_stub.add(["status", "--short"], stdout="")
    gh_stub = CommandStub()
    gh_stub.add(
        ["pr", "view", "--json", module.PR_VIEW_FIELDS],
        stderr="no pull requests found for branch\n",
        returncode=1,
    )
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(["diagnose", "--project", str(project)], module=module)

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    assert "pr_missing" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["branch"] == "feature/ready"
    assert status["details"]["reason"] == "pr_missing"
    assert "--summary" in status["details"]["nextCommand"]
    assert "--scope" in status["details"]["nextCommand"]
    assert status["details"]["optionalFixesArg"] == "--fixes 98"


def test_diagnose_existing_empty_body_reports_pr_body_required(tmp_path: Path, monkeypatch) -> None:
    project, result = run_diagnose_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid="b" * 40,
            body="<!-- template comment -->",
        ),
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "pr_body_required"
    assert status["details"]["pr"] == 12
    assert "--summary" in status["details"]["nextCommand"]
    assert "--scope" in status["details"]["nextCommand"]
    assert status["details"]["optionalFixesArg"] == "--fixes 98"


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
            {"nextCommandContains": "--summary"},
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
        if key == "nextCommandContains":
            assert value in status["details"]["nextCommand"]
        else:
            assert status["details"][key] == value


def test_complete_creates_pr_when_none_exists_then_merges_and_cleans_up(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    head_oid = "b" * 40
    completed_pr = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid=head_oid,
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr="no pull requests found\n", returncode=1)
    gh_stub.add(["pr", "create", "--base", "main", "--fill", "--body-file", "__placeholder__"], stdout="https://github.example/test/repo/pull/12\n")
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], "origin/feature/example\n"),
        (["rev-list", "--count", "@{u}..HEAD"], "0\n"),
            (["rev-list", "--count", "HEAD..@{u}"], "0\n"),
            (["rev-parse", "HEAD"], head_oid + "\n"),
            (["fetch", "origin", "main"], ""),
            (["rev-parse", "origin/main"], "a" * 40 + "\n"),
            (["merge-base", "--is-ancestor", "a" * 40, head_oid], ""),
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

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    calls = [list(call) for call in gh_stub.calls]
    assert calls[0][:2] == ["pr", "view"]
    assert calls[1][:2] == ["pr", "create"]
    assert calls[5] == ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid]
    assert calls[6] == ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"]
    assert gh_stub.body_files[0]["body"] == expected_pr_body(fixes=())


def test_complete_full_flow_uses_configured_squash_strategy(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project, merge_strategy="squash")
    head_oid = "b" * 40
    completed_pr = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid=head_oid,
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(["pr", "merge", "12", "--squash", "--match-head-commit", head_oid])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], "origin/feature/example\n"),
        (["rev-list", "--count", "@{u}..HEAD"], "0\n"),
        (["rev-list", "--count", "HEAD..@{u}"], "0\n"),
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
    allow_current_base(git_stub, head_oid)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert ("pr", "merge", "12", "--squash", "--match-head-commit", head_oid) in gh_stub.calls


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
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}], review_decision="APPROVED", head_oid=head_oid))
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], "origin/feature/example\n"),
        (["rev-list", "--count", "@{u}..HEAD"], "0\n"),
            (["rev-list", "--count", "HEAD..@{u}"], "0\n"),
            (["fetch", "origin", "main"], ""),
            (["rev-parse", "origin/main"], "a" * 40 + "\n"),
            (["merge-base", "--is-ancestor", "a" * 40, head_oid], ""),
        (["rev-parse", "HEAD"], head_oid + "\n"),
        (["status", "--short"], ""),
        (["branch", "--show-current"], "feature/example\n"),
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

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    calls = [list(call) for call in gh_stub.calls]
    assert [call[:2] for call in calls[:3]] == [["pr", "view"]] * 3
    assert calls[3] == ["pr", "merge", "12", "--merge", "--match-head-commit", "b" * 40]
    assert calls[4] == ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"]
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
        (["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], "origin/feature/example\n"),
        (["rev-list", "--count", "@{u}..HEAD"], "0\n"),
        (["rev-list", "--count", "HEAD..@{u}"], "0\n"),
        (["rev-parse", "HEAD"], head_oid + "\n"),
        (["status", "--short"], ""),
        (["branch", "--show-current"], "feature/example\n"),
        (["branch", "--show-current"], "feature/example\n"),
        (["push", "origin", "--delete", "feature/example"], ""),
        (["ls-remote", "--heads", "origin", "feature/example"], ""),
        (["checkout", "main"], ""),
        (["pull", "--ff-only", "origin", "main"], ""),
        (["branch", "-d", "feature/example"], ""),
        (["branch", "--show-current"], "main\n"),
    ]:
        git_stub.add(git_args, stdout=stdout)
    allow_current_base(git_stub, head_oid)
    gh_stub.add(
        ["pr", "view", "--json", module.PR_VIEW_FIELDS],
        stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid=head_oid,
        ),
    )

    def fail_full_verify(*_args, **_kwargs):
        raise AssertionError("complete must not run build-and-verify verify --full")

    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "run_hotfix_verify_command", fail_full_verify)

    result = invoke_pr_flow(complete_args(project), module=module)

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
            (["merge-base", "--is-ancestor", "a" * 40, moved_head_oid], "", 0),
        ],
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "head_moved"


def test_complete_rejects_when_base_moves_after_checks(tmp_path: Path, monkeypatch) -> None:
    head_oid = "b" * 40
    before = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid=head_oid,
        base_oid="a" * 40,
    )
    after = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid=head_oid,
        base_oid="c" * 40,
    )
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_responses=[(before, "", 0), (before, "", 0), (after, "", 0)],
    )

    assert result.returncode == 1
    status = json.loads((project / ".pr-flow/last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "base_outdated"


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


def test_complete_reports_dispatch_when_ruleset_blocks_merge(tmp_path: Path, monkeypatch) -> None:
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
        merge_stderr=(
            "X Pull request owner/repo#90 is not mergeable: the base branch policy prohibits the merge.\n"
            "To use administrator privileges to immediately merge the pull request, add the --admin flag.\n"
        ),
    )

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    assert "ruleset_merge_blocking" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "ruleset_merge_blocking"
    assert status["details"]["pr"] == 12
    action = status["details"].get("nextAction") or status["details"].get("nextCommand")
    assert action is not None
    assert "ruleset" in action


def test_complete_uses_auto_merge_when_ruleset_suggests_auto(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    head_oid = "b" * 40
    completed_pr = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid=head_oid,
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(
        ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid],
        stderr=(
            "X Pull request owner/repo#90 is not mergeable: the base branch policy prohibits the merge.\n"
            "To have the pull request merged after all the requirements have been met, add the --auto flag.\n"
        ),
        returncode=1,
    )
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid, "--auto"])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], "origin/feature/example\n"),
        (["rev-list", "--count", "@{u}..HEAD"], "0\n"),
        (["rev-list", "--count", "HEAD..@{u}"], "0\n"),
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "HEAD"], head_oid + "\n"),
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
    allow_current_base(git_stub, head_oid)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert ("pr", "merge", "12", "--merge", "--match-head-commit", head_oid, "--auto") in gh_stub.calls


def test_complete_returns_checks_pending_when_ruleset_recovery_wait_times_out(tmp_path: Path, monkeypatch) -> None:
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
            (
                pr_view_json(
                    checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                    review_decision="APPROVED",
                    head_oid="b" * 40,
                ),
                "",
                0,
            ),
                (
                    pr_view_json(
                        checks=[{"name": "ci", "status": "QUEUED", "conclusion": None}],
                    review_decision="APPROVED",
                    head_oid="b" * 40,
                ),
                    "",
                    0,
                ),
                (
                    pr_view_json(
                        checks=[{"name": "ci", "status": "QUEUED", "conclusion": None}],
                        review_decision="APPROVED",
                        head_oid="b" * 40,
                    ),
                    "",
                    0,
                ),
            ],
        git_responses=[
            (["branch", "--show-current"], "feature/example\n", 0),
            (["rev-parse", "HEAD"], "b" * 40 + "\n", 0),
        ],
        merge_returncode=1,
        merge_stderr="X Pull request owner/repo#90 is not mergeable: the base branch policy prohibits the merge.\n",
    )

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "checks_pending"
    action = status["details"].get("nextAction") or status["details"].get("nextCommand")
    assert action is not None
    assert "checks" in action


def test_complete_waits_for_checks_after_ruleset_block_then_retries_merge(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    config_path = project / ".pr-flow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["defaults"]["wait"] = {"timeoutSeconds": 30, "pollSeconds": 15}
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    head_oid = "b" * 40
    completed_pr = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid=head_oid,
    )
    pending_pr = pr_view_json(
        checks=[{"name": "ci", "status": "QUEUED", "conclusion": None}],
        review_decision="APPROVED",
        head_oid=head_oid,
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(
        ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid],
        stderr="X Pull request owner/repo#90 is not mergeable: the base branch policy prohibits the merge.\n",
        returncode=1,
    )
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pending_pr)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], "origin/feature/example\n"),
        (["rev-list", "--count", "@{u}..HEAD"], "0\n"),
        (["rev-list", "--count", "HEAD..@{u}"], "0\n"),
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "HEAD"], head_oid + "\n"),
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
    allow_current_base(git_stub, head_oid)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert gh_stub.calls.count(("pr", "merge", "12", "--merge", "--match-head-commit", head_oid)) == 2


def test_complete_uses_auto_merge_when_ruleset_suggests_auto_after_wait(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    config_path = project / ".pr-flow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["defaults"]["wait"] = {"timeoutSeconds": 30, "pollSeconds": 15}
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    head_oid = "b" * 40
    completed_pr = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid=head_oid,
    )
    pending_pr = pr_view_json(
        checks=[{"name": "ci", "status": "QUEUED", "conclusion": None}],
        review_decision="APPROVED",
        head_oid=head_oid,
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(
        ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid],
        stderr="X Pull request owner/repo#90 is not mergeable: the base branch policy prohibits the merge.\n",
        returncode=1,
    )
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pending_pr)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    gh_stub.add(
        ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid],
        stderr=(
            "X Pull request owner/repo#90 is not mergeable: the base branch policy prohibits the merge.\n"
            "To have the pull request merged after all the requirements have been met, add the --auto flag.\n"
        ),
        returncode=1,
    )
    gh_stub.add(["pr", "merge", "12", "--merge", "--match-head-commit", head_oid, "--auto"])
    gh_stub.add(["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"], stdout=cleanup_pr_view_json())
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], "origin/feature/example\n"),
        (["rev-list", "--count", "@{u}..HEAD"], "0\n"),
        (["rev-list", "--count", "HEAD..@{u}"], "0\n"),
        (["branch", "--show-current"], "feature/example\n"),
        (["rev-parse", "HEAD"], head_oid + "\n"),
        (["rev-parse", "HEAD"], head_oid + "\n"),
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
    allow_current_base(git_stub, head_oid)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=completed_pr)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert ("pr", "merge", "12", "--merge", "--match-head-commit", head_oid, "--auto") in gh_stub.calls


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


@pytest.mark.parametrize("review_mode", ["local", "dual"])
def test_complete_rejects_removed_review_gate_modes(tmp_path: Path, review_mode: str) -> None:
    module = load_pr_flow_module()

    result = module.check_review_gate(tmp_path, review_gate_config_for_test(review_mode), passing_review_pr())

    assert result is not None
    assert result["status"] == "EXCEPTION_REQUIRED"
    assert result["details"]["reason"] == "unknown_review_gate_mode"
    assert result["details"]["reviewGateMode"] == review_mode


@pytest.mark.parametrize("review_mode", [[], {}, None, 1, ""])
def test_complete_rejects_invalid_review_gate_mode_values(tmp_path: Path, review_mode) -> None:
    module = load_pr_flow_module()

    result = module.check_review_gate(tmp_path, review_gate_config_for_test(review_mode), passing_review_pr())

    assert result is not None
    assert result["status"] == "EXCEPTION_REQUIRED"
    assert result["details"]["reason"] == "unknown_review_gate_mode"
    assert result["details"]["reviewGateMode"] == review_mode


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
    assert "--body-file" in calls[1]
    assert calls[3][:2] == ["pr", "view"]
    assert calls[5] == ["pr", "merge", "12", "--merge", "--match-head-commit", "b" * 40]
    assert calls[6] == ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"]
    body_records = gh_stub.body_files
    assert len(body_records) == 1
    assert body_records[0]["body"] == expected_pr_body(fixes=())


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
    assert [call[:2] for call in calls[:3]] == [["pr", "view"]] * 3
    assert calls[3] == ["pr", "merge", "12", "--merge", "--match-head-commit", "b" * 40]
    assert calls[4] == ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"]


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
    assert all(call[:2] != ["pr", "edit"] for call in calls)
    assert all(call[:2] != ["pr", "merge"] for call in calls)
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["command"] == "tweak"
    assert status["details"]["reason"] == "checks_pending"
    assert gh_stub.body_files == []


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


def test_hotfix_pushes_head_to_target_and_writes_audit_record(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    pr_flow = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_hotfix_pr_flow_config(project)
    before_commit = "a" * 40
    head_commit = "b" * 40
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
        (["fetch", "origin", "main"], ""),
        (["rev-parse", "origin/main"], before_commit + "\n"),
        (["rev-parse", "HEAD"], head_commit + "\n"),
        (["merge-base", "HEAD", "origin/main"], before_commit + "\n"),
        (["status", "--short"], ""),
        (["push", "origin", "HEAD:refs/heads/main"], ""),
        (["fetch", "origin", "main"], ""),
        (["rev-parse", "origin/main"], head_commit + "\n"),
        (["config", "--get", "user.name"], "Test User\n"),
        (["config", "--get", "user.email"], "test@example.com\n"),
    ]:
        git_stub.add(git_args, stdout=stdout)

    def fake_verify(project_arg: Path, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([command], 0, head_commit + "\n", "")

    monkeypatch.setattr(pr_flow, "git", git_stub)
    monkeypatch.setattr(pr_flow, "run_hotfix_verify_command", fake_verify)

    result = invoke_pr_flow(
        ["hotfix", "--project", str(project), "--target", "main", "--authorization-phrase", HOTFIX_PHRASE],
        module=pr_flow,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: hotfix_complete" in result.stdout
    assert ("push", "origin", "HEAD:refs/heads/main") in git_stub.calls

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


def test_cleanup_merged_pr_checks_out_base_pulls_and_deletes_branches(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_minimal_pr_flow_config(project)
    gh_stub = CommandStub()
    gh_stub.add(
        ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"],
        stdout=cleanup_pr_view_json(),
    )
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
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

    result = invoke_pr_flow(["cleanup", "--project", str(project), "--pr", "12"], module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert "branch: main" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "cleanup_complete"
    assert status["command"] == "cleanup"
    assert status["details"]["pr"] == 12
    assert status["details"]["remote"] == "origin"
    assert gh_stub.calls == [("pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner")]
    expected_git_calls = [
        ("status", "--short"),
        ("branch", "--show-current"),
        ("push", "origin", "--delete", "feature/example"),
        ("ls-remote", "--heads", "origin", "feature/example"),
        ("checkout", "main"),
        ("pull", "--ff-only", "origin", "main"),
        ("branch", "-d", "feature/example"),
        ("branch", "--show-current"),
    ]
    assert all(call in git_stub.calls for call in expected_git_calls)


def test_cleanup_retries_transient_eof_pr_view_before_cleanup(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_minimal_pr_flow_config(project)
    monkeypatch.setenv("PR_FLOW_GH_PR_VIEW_RETRIES", "1")
    gh_stub = CommandStub(consume=True)
    gh_stub.add(
        ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"],
        stderr='Post "https://api.github.com/graphql": EOF\n',
        returncode=1,
    )
    gh_stub.add(
        ["pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner"],
        stdout=cleanup_pr_view_json(),
    )
    git_stub = CommandStub(consume=True)
    for git_args, stdout in [
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

    result = invoke_pr_flow(["cleanup", "--project", str(project), "--pr", "12"], module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout
    assert gh_stub.calls.count(("pr", "view", "12", "--json", "number,state,headRefName,baseRefName,headRepositoryOwner")) == 2


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
