import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
INSTALLER = PLUGIN_ROOT / "skills" / "agent-guard" / "scripts" / "install_agent_guard_plugin.py"


def run_installer(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALLER), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def common_args(tmp_path: Path) -> list[str]:
    return [
        "--plugin-source",
        str(PLUGIN_ROOT),
        "--codex-home",
        str(tmp_path / "codex-home"),
        "--claude-home",
        str(tmp_path / "claude-home"),
        "--codex-marketplace",
        str(tmp_path / "codex-marketplace.json"),
        "--claude-marketplace",
        str(tmp_path / "claude-marketplace.json"),
    ]


def marketplace_entries(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["plugins"]


def test_dry_run_lists_codex_and_claude_targets_without_writing(tmp_path: Path) -> None:
    result = run_installer(["dry-run", *common_args(tmp_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "codex_plugin_target:" in result.stdout
    assert "claude_plugin_target:" in result.stdout
    assert "codex_marketplace:" in result.stdout
    assert "claude_marketplace:" in result.stdout
    assert "project_hooks: not_installed" in result.stdout
    assert "git_config: not_modified" in result.stdout
    assert not (tmp_path / "codex-home").exists()
    assert not (tmp_path / "claude-home").exists()


def test_install_requires_explicit_target_and_authorization(tmp_path: Path) -> None:
    missing_target = run_installer(["install", *common_args(tmp_path), "--authorize-install"])
    missing_authorization = run_installer(["install", *common_args(tmp_path), "--target", "codex"])

    assert missing_target.returncode == 2
    assert "install requires --target" in missing_target.stderr
    assert missing_authorization.returncode == 2
    assert "install requires --authorize-install" in missing_authorization.stderr


def test_authorized_install_is_repeatable_and_updates_marketplaces(tmp_path: Path) -> None:
    args = ["install", *common_args(tmp_path), "--target", "all", "--authorize-install"]

    first = run_installer(args)
    second = run_installer(args)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "status: installed" in second.stdout
    assert (tmp_path / "codex-home" / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json").exists()
    assert (tmp_path / "claude-home" / "plugins" / "agent-guard" / ".claude-plugin" / "plugin.json").exists()
    assert [entry["name"] for entry in marketplace_entries(tmp_path / "codex-marketplace.json")] == ["agent-guard"]
    assert [entry["name"] for entry in marketplace_entries(tmp_path / "claude-marketplace.json")] == ["agent-guard"]
    assert not (tmp_path / "target-project" / ".codex" / "hooks.json").exists()
    assert not (tmp_path / "target-project" / ".githooks").exists()
    assert not (tmp_path / "target-project" / ".git" / "config").exists()


def test_verify_checks_package_and_marketplace_entries(tmp_path: Path) -> None:
    install = run_installer(["install", *common_args(tmp_path), "--target", "all", "--authorize-install"])
    assert install.returncode == 0, install.stdout + install.stderr

    verify = run_installer(["verify", *common_args(tmp_path), "--target", "all"])

    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "status: verified" in verify.stdout
    assert "source_package: complete" in verify.stdout
    assert "codex_install: complete" in verify.stdout
    assert "claude_install: complete" in verify.stdout
    assert "codex_marketplace_entry: present" in verify.stdout
    assert "claude_marketplace_entry: present" in verify.stdout


def test_installer_rejects_profile_argument(tmp_path: Path) -> None:
    result = run_installer(["dry-run", *common_args(tmp_path), "--profile", "pr-flow"])

    assert result.returncode == 2
    assert "profile" in result.stderr
