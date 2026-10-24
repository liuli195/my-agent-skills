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
    assert not package.get("devDependencies")
    lock = json.loads((REPO_ROOT / "package-lock.json").read_text(encoding="utf-8"))
    assert set(lock["packages"]) == {""}
    assert "overrides" not in package
    assert (REPO_ROOT / "package-lock.json").is_file()


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
    assert "New-Item -ItemType Directory -Path (Join-Path $projectRoot 'node_modules') -Force" in text
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
