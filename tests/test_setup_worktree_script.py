import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "setup-worktree.ps1"


def test_repository_owns_shared_node_dependencies() -> None:
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))

    assert package["private"] is True
    assert package["workspaces"] == ["plugins/pi-tool-display"]
    assert (REPO_ROOT / "package-lock.json").is_file()
    assert not (REPO_ROOT / "plugins/pi-tool-display/package-lock.json").exists()


def test_setup_worktree_script_prepares_python_and_shared_node_dependencies() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "$ErrorActionPreference = 'Stop'" in text
    assert "$projectRoot = Split-Path -Parent $PSScriptRoot" in text
    assert r"$python = Join-Path $projectRoot '.venv\Scripts\python.exe'" in text
    assert "py -3.12 -m venv .venv" in text
    assert "& $python -m pip install --upgrade pip" in text
    assert "& $python -m pip install -r requirements-dev.txt" in text
    assert "git rev-parse --path-format=absolute --git-common-dir" in text
    assert "npm ci" in text
    assert "New-Item -ItemType Junction" in text
    assert "SHA256" in text
    assert "build_and_verify" not in text


def test_setup_worktree_script_propagates_each_setup_failure() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert text.count("if ($LASTEXITCODE) { exit $LASTEXITCODE }") >= 4


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
@pytest.mark.parametrize("shell_name", ["powershell", "pwsh"])
def test_setup_worktree_script_links_shared_node_dependencies(
    tmp_path: Path, shell_name: str
) -> None:
    shell = shutil.which(shell_name)
    true = shutil.which("true")
    if not shell or not true:
        pytest.skip(f"{shell_name} and true executables are required")

    project = tmp_path / "project"
    project.mkdir()
    shutil.copytree(REPO_ROOT / "scripts", project / "scripts")
    shutil.copytree(REPO_ROOT / "plugins/pi-tool-display", project / "plugins/pi-tool-display")
    shutil.copy2(REPO_ROOT / "package.json", project / "package.json")
    shutil.copy2(REPO_ROOT / "package-lock.json", project / "package-lock.json")
    shutil.copy2(REPO_ROOT / "requirements-dev.txt", project / "requirements-dev.txt")

    def run(*args: str, cwd: Path = project) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)

    run("git", "init")
    run("git", "config", "user.email", "test@example.invalid")
    run("git", "config", "user.name", "Test")
    run("git", "add", ".")
    run("git", "commit", "-m", "fixture")

    shared_node_modules = project / "node_modules"
    worktree = project / ".worktrees/test"
    run("git", "worktree", "add", "--detach", str(worktree), "HEAD")
    python = worktree / ".venv/Scripts/python.exe"
    python.parent.mkdir(parents=True)
    shutil.copy2(true, python)

    npm_marker = project / "npm-called"
    fake_bin = project / "fake-bin"
    fake_bin.mkdir()
    (fake_bin / "npm.cmd").write_text(
        f'@echo called>>"{npm_marker}"\n@exit /b 99\n', encoding="utf-8"
    )
    env = os.environ | {"PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}
    command = [shell, "-NoProfile", "-File", str(worktree / "scripts/setup-worktree.ps1")]

    missing = subprocess.run(
        command,
        cwd=worktree,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    assert missing.returncode != 0
    assert "Shared Node.js dependencies are missing" in missing.stdout + missing.stderr
    assert not npm_marker.exists()

    shared_node_modules.mkdir()
    subprocess.run(command, cwd=worktree, env=env, check=True)
    subprocess.run(command, cwd=worktree, env=env, check=True)

    link = worktree / "node_modules"
    assert link.is_junction()
    assert link.resolve() == shared_node_modules.resolve()

    (worktree / "package.json").write_text("{}", encoding="utf-8")
    result = subprocess.run(
        command,
        cwd=worktree,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    assert result.returncode != 0
    assert "do not match 'package.json'" in result.stdout + result.stderr
    assert not npm_marker.exists()
