from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.support.git_templates import init_user, run_git


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
