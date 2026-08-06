import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "setup-worktree.ps1"
_ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|[@-Z\\-_])")


def normalize_powershell_output(result: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    plain = _ANSI_ESCAPE.sub("", output)
    return " ".join(re.sub(r"(?m)^[ \t]{4,}\|[ \t]?", "", plain).split())


def test_normalize_powershell_output_removes_host_ansi_and_whitespace() -> None:
    result = subprocess.CompletedProcess(
        ["powershell", "-File", str(SCRIPT)],
        1,
        "\x1b[31mShared Node.js dependencies are\n",
        "\x1b[0m     | missing. Run scripts\\setup-worktree.ps1\n",
    )

    assert normalize_powershell_output(result) == (
        "Shared Node.js dependencies are missing. Run scripts\\setup-worktree.ps1"
    )
    literal = subprocess.CompletedProcess(["powershell"], 1, "| literal message\n", "")
    assert normalize_powershell_output(literal) == "| literal message"


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


def test_windows_worktree_build_uses_initialized_environment_and_unified_entry() -> None:
    workflow = (REPO_ROOT / ".github/workflows/full-verify.yml").read_text(encoding="utf-8")
    build_step = workflow.split("- name: Build from linked worktree", 1)[1]

    assert ".worktrees/smoke/.venv/Scripts/Activate.ps1" in build_step
    assert "build-and-verify build --project .worktrees/smoke" in build_step
    assert build_step.index("Activate.ps1") < build_step.index("build-and-verify build")
    assert "build_and_verify.py" not in build_step
    assert ".build-and-verify/runtime/" not in build_step
    assert "npm run build" not in build_step


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
@pytest.mark.parametrize("shell_name", ["powershell", "pwsh"])
def test_setup_worktree_script_links_shared_node_dependencies(
    tmp_path: Path, shell_name: str
) -> None:
    shell = shutil.which(shell_name)
    if not shell:
        pytest.skip(f"{shell_name} executable is required")

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
    shared_venv = project / ".venv"
    shared_python = shared_venv / "Scripts/python.exe"
    requirements = (project / "requirements-dev.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
    fingerprint = hashlib.sha256(requirements.encode()).hexdigest().upper()

    npm_marker = project / "npm-called"
    py_marker = project / "py-called"
    fake_bin = project / "fake-bin"
    fake_bin.mkdir()
    (fake_bin / "npm.cmd").write_text(
        f'@echo called>>"{npm_marker}"\n@exit /b 99\n', encoding="utf-8"
    )
    (fake_bin / "py.cmd").write_text(
        f'@echo called>>"{py_marker}"\n@exit /b 99\n', encoding="utf-8"
    )
    env = os.environ | {"PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}
    command = [shell, "-NoProfile", "-File", str(worktree / "scripts/setup-worktree.ps1")]

    def setup(*, check: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=worktree,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=check,
        )

    missing = setup()
    assert missing.returncode != 0
    assert not npm_marker.exists()
    assert not py_marker.exists()
    assert "Shared Node.js dependencies are missing" in normalize_powershell_output(missing)

    shared_node_modules.mkdir()
    stale_node = setup()
    assert stale_node.returncode != 0
    assert not npm_marker.exists()
    assert not py_marker.exists()
    assert "Shared Node.js dependencies are stale" in normalize_powershell_output(stale_node)

    node_fingerprint = "\n".join(
        f"{hashlib.sha256((project / manifest).read_text(encoding='utf-8').replace(chr(13) + chr(10), chr(10)).encode()).hexdigest().upper()} {manifest}"
        for manifest in ("package.json", "package-lock.json", "plugins\\pi-tool-display\\package.json")
    )
    (shared_node_modules / ".package-lock.sha256").write_text(node_fingerprint + "\n", encoding="ascii")
    missing_python = setup()
    assert missing_python.returncode != 0
    assert not npm_marker.exists()
    assert not py_marker.exists()
    assert "Shared Python environment is missing" in normalize_powershell_output(missing_python)

    shared_python.parent.mkdir(parents=True)
    shared_python.touch()
    stale_python = setup()
    assert stale_python.returncode != 0
    assert not npm_marker.exists()
    assert not py_marker.exists()
    assert "Shared Python environment is stale" in normalize_powershell_output(stale_python)

    (shared_venv / ".requirements.sha256").write_text(
        f"{fingerprint} requirements-dev.txt\n", encoding="ascii"
    )
    setup(check=True)
    setup(check=True)

    link = worktree / "node_modules"
    assert link.is_junction()
    assert link.resolve() == shared_node_modules.resolve()
    venv_link = worktree / ".venv"
    assert venv_link.is_junction()
    assert venv_link.resolve() == shared_venv.resolve()
    assert not py_marker.exists()

    (worktree / "package.json").write_text("{}", encoding="utf-8")
    result = setup()
    assert result.returncode != 0
    assert not npm_marker.exists()
    assert not py_marker.exists()
    assert "do not match 'package.json'" in normalize_powershell_output(result)

    shutil.copy2(project / "package.json", worktree / "package.json")
    venv_link.rmdir()
    venv_link.mkdir()
    existing = setup()
    assert existing.returncode != 0
    assert not npm_marker.exists()
    assert not py_marker.exists()
    assert venv_link.is_dir() and not venv_link.is_junction()
    assert "already exists and does not link" in normalize_powershell_output(existing)
