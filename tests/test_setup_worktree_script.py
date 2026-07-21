from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "setup-worktree.ps1"


def test_setup_worktree_script_prepares_only_local_python_dev_environment() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "$ErrorActionPreference = 'Stop'" in text
    assert "$projectRoot = Split-Path -Parent $PSScriptRoot" in text
    assert r"$python = Join-Path $projectRoot '.venv\Scripts\python.exe'" in text
    assert "py -3.12 -m venv .venv" in text
    assert "& $python -m pip install --upgrade pip" in text
    assert "& $python -m pip install -r requirements-dev.txt" in text
    assert "build_and_verify" not in text


def test_setup_worktree_script_propagates_each_setup_failure() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert text.count("if ($LASTEXITCODE) { exit $LASTEXITCODE }") == 3
