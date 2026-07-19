import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
INSTALLER = PLUGIN_ROOT / "skills" / "agent-guard" / "scripts" / "install_agent_guard_plugin.py"
_INSTALLER_MODULE = None


def installer_module():
    global _INSTALLER_MODULE
    if _INSTALLER_MODULE is not None:
        return _INSTALLER_MODULE
    spec = importlib.util.spec_from_file_location("install_agent_guard_plugin_for_tests", INSTALLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _INSTALLER_MODULE = module
    return module


def run_installer(args: list[str]) -> subprocess.CompletedProcess[str]:
    module = installer_module()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.chdir(REPO_ROOT), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            returncode = int(module.main(args))
        except SystemExit as error:
            returncode = error.code if isinstance(error.code, int) else 1
    return subprocess.CompletedProcess(
        [sys.executable, str(INSTALLER), *args],
        returncode,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def common_args(tmp_path: Path, plugin_source: Path = PLUGIN_ROOT) -> list[str]:
    repo_root = tmp_path / "repo-marketplace"
    return [
        "--plugin-source",
        str(plugin_source),
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


def plugin_entries(data: dict) -> list[dict]:
    return [entry for entry in data["plugins"] if entry["name"] == "agent-guard"]


def agent_guard_entries(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return plugin_entries(data)


def marketplace_paths(tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path / "repo-marketplace"
    return {
        "codex_repo": repo_root / ".agents" / "plugins" / "marketplace.json",
        "claude_repo": repo_root / ".claude-plugin" / "marketplace.json",
        "codex_personal": tmp_path / "codex-personal" / ".agents" / "plugins" / "marketplace.json",
        "claude_personal": tmp_path / "claude-personal" / ".claude-plugin" / "marketplace.json",
    }


def agent_guard_entry(path: Path) -> dict:
    return agent_guard_entries(path)[0]


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
    paths = marketplace_paths(tmp_path)
    assert str(paths["codex_repo"]) in result.stdout
    assert str(paths["claude_repo"]) in result.stdout
    assert str(paths["codex_personal"]) in result.stdout
    assert str(paths["claude_personal"]) in result.stdout
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
    entries = {key: agent_guard_entries(path) for key, path in paths.items()}
    for key in ("codex_repo", "claude_repo", "codex_personal", "claude_personal"):
        assert len(entries[key]) == 1
    for key in ("codex_repo", "codex_personal"):
        entry = entries[key][0]
        assert entry["source"] == {"source": "local", "path": "./plugins/agent-guard"}
        assert entry["policy"]["installation"] == "AVAILABLE"
        assert entry["policy"]["authentication"] == "ON_INSTALL"
        assert entry["category"] == "Productivity"
    for key in ("claude_repo", "claude_personal"):
        entry = entries[key][0]
        assert entry["source"] == "./plugins/agent-guard"


def test_verify_checks_package_and_marketplace_entries(tmp_path: Path) -> None:
    install = run_installer(["install", *common_args(tmp_path), "--target", "all", "--scope", "all", "--authorize-install"])
    assert install.returncode == 0, install.stdout + install.stderr

    verify = run_installer(["verify", *common_args(tmp_path), "--target", "all", "--scope", "all"])

    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "status: verified" in verify.stdout
    assert "shared_identity: loaded" in verify.stdout
    assert "source_package: complete" in verify.stdout
    assert "codex_repo_marketplace_entry: present" in verify.stdout
    assert "claude_repo_marketplace_entry: present" in verify.stdout
    assert "codex_personal_marketplace_entry: present" in verify.stdout
    assert "claude_personal_marketplace_entry: present" in verify.stdout


def test_verify_default_scope_does_not_require_repo_marketplace(tmp_path: Path) -> None:
    install = run_installer(
        [
            "install",
            *common_args(tmp_path),
            "--target",
            "codex",
            "--scope",
            "personal",
            "--authorize-install",
        ]
    )
    assert install.returncode == 0, install.stdout + install.stderr

    verify = run_installer(["verify", *common_args(tmp_path), "--target", "codex"])

    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "codex_personal_marketplace_entry: present" in verify.stdout
    assert "codex_repo_marketplace_entry" not in verify.stdout


def test_verify_target_codex_only_requires_codex_manifest(tmp_path: Path) -> None:
    install = run_installer(
        ["install", *common_args(tmp_path), "--target", "codex", "--scope", "repo", "--authorize-install"]
    )
    assert install.returncode == 0, install.stdout + install.stderr
    plugin_source = tmp_path / "agent-guard-source"
    shutil.copytree(PLUGIN_ROOT, plugin_source)
    (plugin_source / ".claude-plugin" / "plugin.json").unlink()

    codex_verify = run_installer(["verify", *common_args(tmp_path, plugin_source), "--target", "codex", "--scope", "repo"])
    all_verify = run_installer(["verify", *common_args(tmp_path, plugin_source), "--target", "all", "--scope", "repo"])

    assert codex_verify.returncode == 0, codex_verify.stdout + codex_verify.stderr
    assert "status: verified" in codex_verify.stdout
    assert all_verify.returncode == 1
    assert ".claude-plugin/plugin.json" in all_verify.stdout


def test_verify_rejects_legacy_hook_config_shape(tmp_path: Path) -> None:
    install = run_installer(["install", *common_args(tmp_path), "--target", "all", "--scope", "all", "--authorize-install"])
    assert install.returncode == 0, install.stdout + install.stderr
    plugin_source = tmp_path / "agent-guard-source"
    shutil.copytree(PLUGIN_ROOT, plugin_source)
    legacy_hooks = {
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python -c \"import os; print(os.environ.get('PLUGIN_ROOT') or os.environ.get('CLAUDE_PLUGIN_ROOT')); print('hook_router.py')\" --event SessionStart",
                    }
                ]
            }
        ],
        "PreToolUse": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python -c \"import os; print(os.environ.get('PLUGIN_ROOT') or os.environ.get('CLAUDE_PLUGIN_ROOT')); print('hook_router.py')\" --event PreToolUse",
                    }
                ]
            }
        ],
    }
    (plugin_source / "hooks" / "hooks.json").write_text(
        json.dumps(legacy_hooks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    verify = run_installer(["verify", *common_args(tmp_path, plugin_source), "--target", "all", "--scope", "all"])

    assert verify.returncode == 1
    assert "invalid_hooks: expected top-level hooks object" in verify.stdout


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


def test_verify_rejects_marketplace_catalog_identity_mismatch(tmp_path: Path) -> None:
    install = run_installer(
        [
            "install",
            *common_args(tmp_path),
            "--target",
            "codex",
            "--scope",
            "repo",
            "--authorize-install",
        ]
    )
    assert install.returncode == 0, install.stdout + install.stderr
    path = marketplace_paths(tmp_path)["codex_repo"]
    data = json.loads(path.read_text(encoding="utf-8"))
    data["name"] = "old-agent-guard-marketplace"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    verify = run_installer(["verify", *common_args(tmp_path), "--target", "codex", "--scope", "repo"])

    assert verify.returncode == 1
    assert "invalid_marketplace_identity" in verify.stdout
    assert "old-agent-guard-marketplace" in verify.stdout


def test_verify_reports_invalid_marketplace_plugins_shape(tmp_path: Path) -> None:
    path = marketplace_paths(tmp_path)["codex_repo"]
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"plugins": "bad"}, ensure_ascii=False, indent=2), encoding="utf-8")

    verify = run_installer(["verify", *common_args(tmp_path), "--target", "codex", "--scope", "repo"])

    assert verify.returncode == 1
    assert "invalid_marketplace_plugins" in verify.stdout


def test_verify_reports_invalid_marketplace_plugin_entry(tmp_path: Path) -> None:
    path = marketplace_paths(tmp_path)["codex_repo"]
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"plugins": [None]}, ensure_ascii=False, indent=2), encoding="utf-8")

    verify = run_installer(["verify", *common_args(tmp_path), "--target", "codex", "--scope", "repo"])

    assert verify.returncode == 1
    assert "invalid_marketplace_plugins" in verify.stdout


def test_install_rejects_invalid_marketplace_plugins_without_overwriting(tmp_path: Path) -> None:
    path = marketplace_paths(tmp_path)["codex_repo"]
    path.parent.mkdir(parents=True)
    original = json.dumps({"plugins": "bad"}, ensure_ascii=False, indent=2)
    path.write_text(original, encoding="utf-8")

    install = run_installer(["install", *common_args(tmp_path), "--target", "codex", "--scope", "repo", "--authorize-install"])

    assert install.returncode == 1
    assert "invalid_marketplace_plugins" in install.stdout
    assert path.read_text(encoding="utf-8") == original


def test_installer_rejects_profile_argument(tmp_path: Path) -> None:
    result = run_installer(["dry-run", *common_args(tmp_path), "--profile", "pr-flow"])

    assert result.returncode == 2
    assert "profile" in result.stderr
