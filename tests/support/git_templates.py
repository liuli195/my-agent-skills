from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def run_git(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def init_user(project: Path) -> None:
    run_git(project, "config", "user.email", "test@example.com")
    run_git(project, "config", "user.name", "Test User")


def copy_template(source: Path, target: Path) -> Path:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git/hooks"))
    return target
