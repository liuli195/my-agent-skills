from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tests.support.git_templates import init_user, run_git


REPO_ROOT = Path(__file__).resolve().parents[1]
MYSPEC_PACK = REPO_ROOT / "plugins" / "tool-lifecycle" / "pack.py"
MYSPEC_TEST_TARBALL = "MYSPEC_TEST_TARBALL"
MYSPEC_TEST_IN_PROCESS = "MYSPEC_TEST_IN_PROCESS"
_candidate_directory: Path | None = None
_previous_candidate: str | None = None
_previous_in_process: str | None = None
_candidate_environment_managed = False


def _runs_my_spec(config: pytest.Config) -> bool:
    for argument in config.args:
        raw = str(argument).split("::", 1)[0].replace("\\", "/")
        if Path(raw).name == "test_my_spec.py":
            return True
        if raw.startswith("-"):
            continue
        selected = Path(raw)
        if not selected.is_absolute():
            selected = REPO_ROOT / selected
        if selected.resolve() in {REPO_ROOT, REPO_ROOT / "tests"}:
            return (REPO_ROOT / "tests" / "test_my_spec.py").is_file()
    return False


def _cleanup_candidate_directory() -> None:
    global _candidate_directory
    if _candidate_directory is not None:
        shutil.rmtree(_candidate_directory, ignore_errors=True)
        _candidate_directory = None


def _restore_in_process_environment() -> None:
    global _previous_in_process
    if _previous_in_process is None:
        os.environ.pop(MYSPEC_TEST_IN_PROCESS, None)
    else:
        os.environ[MYSPEC_TEST_IN_PROCESS] = _previous_in_process
    _previous_in_process = None


def _restore_candidate_environment() -> None:
    global _previous_candidate, _candidate_environment_managed
    if not _candidate_environment_managed:
        return
    if _previous_candidate is None:
        os.environ.pop(MYSPEC_TEST_TARBALL, None)
    else:
        os.environ[MYSPEC_TEST_TARBALL] = _previous_candidate
    _previous_candidate = None
    _candidate_environment_managed = False


def _prepare_my_spec_test_tarball() -> None:
    global _candidate_directory, _previous_candidate, _previous_in_process
    global _candidate_environment_managed
    if _candidate_environment_managed:
        return
    _previous_candidate = os.environ.get(MYSPEC_TEST_TARBALL)
    _previous_in_process = os.environ.get(MYSPEC_TEST_IN_PROCESS)
    _candidate_environment_managed = True
    os.environ[MYSPEC_TEST_IN_PROCESS] = "1"
    try:
        supplied = _previous_candidate
        if supplied:
            candidate = Path(supplied).expanduser().resolve()
            if not candidate.is_file():
                raise pytest.UsageError(
                    f"{MYSPEC_TEST_TARBALL} must point to an existing Tarball: {candidate}"
                )
            os.environ[MYSPEC_TEST_TARBALL] = str(candidate)
            return

        _previous_candidate = supplied
        _candidate_directory = Path(tempfile.mkdtemp(prefix="myspec-test-tarball-"))
        try:
            packed = subprocess.run(
                [sys.executable, str(MYSPEC_PACK), "myspec", str(_candidate_directory)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as error:
            _cleanup_candidate_directory()
            raise pytest.UsageError(f"failed to prepare MySpec test Tarball: {error}") from error
        if packed.returncode != 0:
            detail = packed.stderr.strip() or f"exit code {packed.returncode}"
            _cleanup_candidate_directory()
            raise pytest.UsageError(f"failed to prepare MySpec test Tarball: {detail}")

        candidate = Path(packed.stdout.strip()).resolve()
        if not candidate.is_file():
            _cleanup_candidate_directory()
            raise pytest.UsageError(
                f"MySpec pack Interface returned a missing Tarball: {candidate}"
            )
        os.environ[MYSPEC_TEST_TARBALL] = str(candidate)
    except BaseException:
        _cleanup_candidate_directory()
        _restore_candidate_environment()
        _restore_in_process_environment()
        raise


def pytest_configure(config: pytest.Config) -> None:
    if not hasattr(config, "workerinput") and _runs_my_spec(config):
        _prepare_my_spec_test_tarball()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    del exitstatus
    if not hasattr(session.config, "workerinput"):
        _cleanup_candidate_directory()
        _restore_candidate_environment()
        _restore_in_process_environment()


@pytest.fixture(scope="session")
def bare_remote_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    remote = tmp_path_factory.mktemp("git-template") / "remote.git"
    result = subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return remote


@pytest.fixture
def git_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    result = subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        result = subprocess.run(
            ["git", "init"],
            cwd=project,
            check=False,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        run_git(project, "checkout", "-b", "main")
    init_user(project)
    (project / "README.md").write_text("# Test Project\n", encoding="utf-8")
    run_git(project, "add", "README.md")
    run_git(project, "commit", "-m", "initial")
    return project
