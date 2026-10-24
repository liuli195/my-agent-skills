from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.support.npm_candidates import NpmCandidate


NPM_MODULE = Path(__file__).with_name("test_npm.py").resolve()
NPM_CLASSES = {"TestMySpec": "myspec", "TestBuildAndVerify": "build-and-verify"}


def _selected_npm_packages(config: pytest.Config) -> set[str]:
    packages = set()
    for argument in config.args:
        raw, *selectors = str(argument).split("::")
        path = Path(raw)
        if not path.is_absolute():
            path = Path(config.invocation_params.dir) / path
        path = path.resolve()
        if path == NPM_MODULE:
            if not selectors:
                packages.update(NPM_CLASSES.values())
            elif selectors[0] in NPM_CLASSES:
                packages.add(NPM_CLASSES[selectors[0]])
        elif not selectors and NPM_MODULE.is_relative_to(path):
            packages.update(NPM_CLASSES.values())
    return packages


def pytest_configure(config: pytest.Config) -> None:
    selected = _selected_npm_packages(config)
    if not selected:
        return
    from tests.support.npm_candidates import (
        CANDIDATES_ENV, TARBALL_ENV, candidate_environment, candidate_for,
        prepare_candidate, remove_owned_candidate,
    )
    if hasattr(config, "workerinput"):
        for name in selected:
            candidate_for(name)
        return

    candidates = {}
    if os.environ.get(CANDIDATES_ENV):
        # A nested framework invocation may read its parent's complete baseline.
        for name in selected:
            candidates[name] = candidate_for(name)
        return

    root = Path(tempfile.mkdtemp(prefix="own-skills-npm-check-"))
    config.add_cleanup(lambda: remove_owned_candidate(root))
    try:
        for name in sorted(selected):
            supplied = os.environ.get(TARBALL_ENV[name])
            candidates[name] = prepare_candidate(name, root / name, tarball=Path(supplied) if supplied else None)
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        raise pytest.UsageError(f"failed_to_prepare_npm_candidate: {error}") from error

    def restore_environment() -> None:
        os.environ.pop(CANDIDATES_ENV, None)

    config.add_cleanup(restore_environment)
    # Publish only after every selected candidate is complete, before workers start.
    os.environ[CANDIDATES_ENV] = candidate_environment(candidates)


@pytest.fixture(scope="class")
def npm_candidate(request: pytest.FixtureRequest) -> NpmCandidate:
    if request.cls is None or request.cls.__name__ not in NPM_CLASSES:
        raise pytest.UsageError("npm_candidate_requires_selected_npm_class")
    from tests.support.npm_candidates import candidate_for

    return candidate_for(NPM_CLASSES[request.cls.__name__])


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
    from tests.support.git_templates import init_user, run_git

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
