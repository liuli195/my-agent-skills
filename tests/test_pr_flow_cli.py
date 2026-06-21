import json
import subprocess
import sys
from pathlib import Path

import yaml


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


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd or REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def test_init_creates_config_template_and_gitignore(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("init", "--project", str(project), "--base-branch", "main")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: initialized" in result.stdout
    assert "GitHub Rulesets suggestion" in result.stdout

    config = yaml.safe_load((project / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))
    assert config["defaults"]["baseBranch"] == "main"
    assert config["defaults"]["mergeStrategy"] == "merge"
    assert config["defaults"]["reviewGate"]["mode"] == "github"
    assert config["defaults"]["wait"] == {"timeoutSeconds": 600, "pollSeconds": 15}
    assert config["defaults"]["pr"]["bodyTemplatePath"] == ".pr-flow/pr-template.md"
    assert config["branches"]["main"]["remote"] == "origin"
    assert config["branches"]["main"]["allowHotfixPush"] is False

    template = (project / ".pr-flow" / "pr-template.md").read_text(encoding="utf-8")
    for section in ["Summary", "Scope", "Verification", "Risk", "Rollback"]:
        assert f"## {section}" in template

    assert (project / ".pr-flow" / ".gitignore").read_text(encoding="utf-8") == "/runs/\n/last-status.json\n"


def test_init_does_not_call_gh_api(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("init", "--project", str(project))

    assert result.returncode == 0
    assert "gh api" not in result.stdout
    assert "Rulesets written" not in result.stdout


def test_missing_config_reports_exception_required(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("diagnose", "--project", str(project))

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "missing_config" in result.stdout


def test_status_file_is_written_for_stop_state(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    init_result = run("init", "--project", str(project))

    assert init_result.returncode == 0, init_result.stdout + init_result.stderr
    result = run("diagnose", "--project", str(project))

    assert result.returncode == 1
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "diagnose"
    assert status["details"]["reason"] == "diagnose_not_implemented"
