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
    repo_root = tmp_path / "repo-marketplace"
    return [
        "--plugin-source",
        str(PLUGIN_ROOT),
        "--codex-repo-marketplace",
        str(repo_root / ".agents" / "plugins" / "marketplace.json"),
        "--claude-repo-marketplace",
        str(repo_root / ".claude-plugin" / "marketplace.json"),
        "--codex-personal-marketplace",
        str(tmp_path / "codex-personal" / ".agents" / "plugins" / "marketplace.json"),
        "--claude-personal-marketplace",
        str(tmp_path / "claude-personal" / ".claude-plugin" / "marketplace.json"),
        "--release-ref",
        "marketplace",
    ]


def marketplace_entries(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["plugins"]


def marketplace_paths(tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path / "repo-marketplace"
    return {
        "codex_repo": repo_root / ".agents" / "plugins" / "marketplace.json",
        "claude_repo": repo_root / ".claude-plugin" / "marketplace.json",
        "codex_personal": tmp_path / "codex-personal" / ".agents" / "plugins" / "marketplace.json",
        "claude_personal": tmp_path / "claude-personal" / ".claude-plugin" / "marketplace.json",
    }


def agent_guard_entry(path: Path) -> dict:
    return next(entry for entry in marketplace_entries(path) if entry["name"] == "agent-guard")


def test_dry_run_lists_codex_and_claude_targets_without_writing(tmp_path: Path) -> None:
    result = run_installer(["dry-run", *common_args(tmp_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "target: all" in result.stdout
    assert "scope: all" in result.stdout
    assert "release_ref: marketplace" in result.stdout
    assert "codex_repo_marketplace:" in result.stdout
    assert "claude_repo_marketplace:" in result.stdout
    assert "codex_personal_marketplace:" in result.stdout
    assert "claude_personal_marketplace:" in result.stdout
    assert "safety: marketplace_catalog_only" in result.stdout
    assert not (tmp_path / "repo-marketplace").exists()
    assert not (tmp_path / "codex-personal").exists()
    assert not (tmp_path / "claude-personal").exists()


def test_install_requires_explicit_target_and_authorization(tmp_path: Path) -> None:
    missing_target = run_installer(["install", *common_args(tmp_path), "--scope", "all", "--authorize-install"])
    missing_scope = run_installer(["install", *common_args(tmp_path), "--target", "all", "--authorize-install"])
    missing_authorization = run_installer(["install", *common_args(tmp_path), "--target", "all", "--scope", "all"])

    assert missing_target.returncode == 2
    assert "install requires --target" in missing_target.stderr
    assert missing_scope.returncode == 2
    assert "install requires --scope" in missing_scope.stderr
    assert missing_authorization.returncode == 2
    assert "install requires --authorize-install" in missing_authorization.stderr


def test_authorized_install_is_repeatable_and_updates_marketplaces(tmp_path: Path) -> None:
    args = ["install", *common_args(tmp_path), "--target", "all", "--scope", "all", "--authorize-install"]

    first = run_installer(args)
    second = run_installer(args)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "status: installed" in second.stdout
    paths = marketplace_paths(tmp_path)
    for key in ("codex_repo", "codex_personal"):
        entry = agent_guard_entry(paths[key])
        assert entry["source"] == {"source": "local", "path": "./plugins/agent-guard"}
        assert "policy" in entry
    for key in ("claude_repo", "claude_personal"):
        entry = agent_guard_entry(paths[key])
        assert entry["source"] == "./plugins/agent-guard"


def test_verify_checks_package_and_marketplace_entries(tmp_path: Path) -> None:
    install = run_installer(["install", *common_args(tmp_path), "--target", "all", "--scope", "all", "--authorize-install"])
    assert install.returncode == 0, install.stdout + install.stderr

    verify = run_installer(["verify", *common_args(tmp_path), "--target", "all", "--scope", "all"])

    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "status: verified" in verify.stdout
    assert "source_package: complete" in verify.stdout
    assert "codex_repo_marketplace_entry: present" in verify.stdout
    assert "claude_repo_marketplace_entry: present" in verify.stdout
    assert "codex_personal_marketplace_entry: present" in verify.stdout
    assert "claude_personal_marketplace_entry: present" in verify.stdout


def test_verify_rejects_legacy_marketplace_entry(tmp_path: Path) -> None:
    path = marketplace_paths(tmp_path)["codex_repo"]
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "plugins": [
                    {
                        "name": "agent-guard",
                        "kind": "local",
                        "install_path": str(PLUGIN_ROOT),
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    verify = run_installer(["verify", *common_args(tmp_path), "--target", "codex", "--scope", "repo"])

    assert verify.returncode == 1
    assert "legacy_marketplace_entry" in verify.stdout


def test_installer_rejects_profile_argument(tmp_path: Path) -> None:
    result = run_installer(["dry-run", *common_args(tmp_path), "--profile", "pr-flow"])

    assert result.returncode == 2
    assert "profile" in result.stderr
