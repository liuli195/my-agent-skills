from __future__ import annotations

import os
import shutil
import stat
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


def remove_template(target: Path) -> None:
    def retry_readonly_file(operation, path, error_info):
        error = error_info[1]
        if os.name != "nt" or not isinstance(error, PermissionError) or operation not in (os.unlink, os.remove):
            raise error
        file = Path(path)
        mode = file.lstat().st_mode
        if not stat.S_ISREG(mode) or mode & stat.S_IWRITE:
            raise error
        file.chmod(mode | stat.S_IWRITE)
        operation(path)

    shutil.rmtree(target, onerror=retry_readonly_file)


def copy_template(source: Path, target: Path) -> Path:
    if target.exists():
        remove_template(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git/hooks"))
    return target
