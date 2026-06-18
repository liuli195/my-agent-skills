import json
import importlib.util
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
CODEX_REPO_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
ENTRYPOINT_SKILLS = [
    "agent-guard-install",
    "agent-guard-init",
    "agent-guard-update",
    "agent-guard-run",
]
ENTRYPOINT_REFERENCES = {
    "agent-guard-install": ["research-and-extract.md", "profile-draft.md"],
    "agent-guard-init": ["init-flow.md", "init-boundaries.md"],
    "agent-guard-update": ["runtime-update.md", "profile-sync.md"],
    "agent-guard-run": ["activate.md", "brief.md", "events.md", "close.md"],
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hook_commands(hooks: dict) -> list[str]:
    commands: list[str] = []
    for entries in hooks.values():
        for entry in entries:
            if "command" in entry:
                commands.append(entry["command"])
            for hook in entry.get("hooks", []):
                if "command" in hook:
                    commands.append(hook["command"])
    return commands


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def test_plugin_manifests_are_valid_json() -> None:
    codex_manifest = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    claude_manifest = read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")

    assert codex_manifest["name"] == "agent-guard"
    assert claude_manifest["name"] == "agent-guard"
    assert codex_manifest["hooks"] == "./hooks/hooks.json"
    assert claude_manifest["hooks"] == "./hooks/hooks.json"


def test_repo_marketplace_catalogs_point_to_agent_guard_plugin() -> None:
    codex_catalog = read_json(CODEX_REPO_MARKETPLACE)
    claude_catalog = read_json(CLAUDE_REPO_MARKETPLACE)

    assert codex_catalog["name"] == "my-agent-skills-marketplace"
    assert codex_catalog["interface"]["displayName"] == "My Agent Skills Marketplace"
    codex_entries = [
        plugin
        for plugin in codex_catalog["plugins"]
        if plugin.get("name") == "agent-guard"
    ]
    assert len(codex_entries) == 1, codex_entries
    codex_entry = codex_entries[0]
    assert codex_entry["source"] == {
        "source": "local",
        "path": "./plugins/agent-guard",
    }
    assert codex_entry["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert codex_entry["category"] == "Productivity"

    assert claude_catalog["name"] == "my-agent-skills-marketplace"
    assert claude_catalog["owner"]["name"] == "My Agent Skills Marketplace"
    claude_entries = [
        plugin
        for plugin in claude_catalog["plugins"]
        if plugin.get("name") == "agent-guard"
    ]
    assert len(claude_entries) == 1, claude_entries
    claude_entry = claude_entries[0]
    assert claude_entry["source"] == "./plugins/agent-guard"
    assert claude_entry["description"]


def test_plugin_package_does_not_depend_on_legacy_install_scripts() -> None:
    legacy_scripts = [
        REPO_ROOT / "scripts" / "install" / "install_user_skill.ps1",
        REPO_ROOT / "scripts" / "install" / "sync_claude_junction.ps1",
        REPO_ROOT / "scripts" / "install" / "verify_install.py",
    ]

    assert [path for path in legacy_scripts if path.exists()] == []


def test_plugin_hooks_only_use_session_start_and_pre_tool_use() -> None:
    config = read_json(PLUGIN_ROOT / "hooks" / "hooks.json")
    assert set(config) == {"hooks"}
    hooks = config["hooks"]

    assert set(hooks) == {"SessionStart", "PreToolUse"}
    for event, entries in hooks.items():
        commands = hook_commands({event: entries})
        assert len(commands) == 1
        command = commands[0]
        assert "hook_router.py" in command
        assert "PLUGIN_ROOT" in command
        assert "CLAUDE_PLUGIN_ROOT" in command
        assert "--event" in command
        assert event in command
        assert "--source codex" not in command
        assert "--source claude" not in command
        assert "--profile" not in command
        assert not re.search(r"[A-Za-z]:[\\/]", command)


def test_plugin_package_contains_runtime_skills_and_templates() -> None:
    assert (PLUGIN_ROOT / "scripts" / "hook_router.py").exists()
    assert (PLUGIN_ROOT / "scripts" / "guard_runtime").is_dir()
    assert (PLUGIN_ROOT / "scripts" / "guard_runtime" / "README.md").exists()
    assert (PLUGIN_ROOT / "assets" / "templates").is_dir()
    assert (PLUGIN_ROOT / "assets" / "templates" / "guard-profile" / "minimal" / "GUARD-MANIFEST.yaml").exists()

    core_skill = PLUGIN_ROOT / "skills" / "agent-guard"
    for required in [
        "SKILL.md",
        "references/architecture.md",
        "references/template-index.md",
        "references/terminology.md",
        "scripts/activate_guard.py",
        "scripts/render_guard_brief.py",
        "scripts/run_guard_event.py",
        "scripts/validate_guard_profile.py",
        "assets/templates/guard-profile/minimal/GUARD-MANIFEST.yaml",
    ]:
        assert (core_skill / required).exists()

    for entrypoint in ENTRYPOINT_SKILLS:
        skill_dir = PLUGIN_ROOT / "skills" / entrypoint
        assert (skill_dir / "SKILL.md").exists()
        for reference in ENTRYPOINT_REFERENCES[entrypoint]:
            assert (skill_dir / "references" / reference).exists()
        assert not (skill_dir / "scripts").exists()
        assert not (skill_dir / "assets").exists()

    assert not (PLUGIN_ROOT / "skills" / "agent-guard-hooks").exists()


def test_legacy_root_agent_guard_skills_are_removed() -> None:
    legacy_root = REPO_ROOT / "skills"
    if not legacy_root.exists():
        return

    legacy_agent_guard_skills = sorted(path.name for path in legacy_root.glob("agent-guard*"))
    assert legacy_agent_guard_skills == []


def test_plugin_skills_are_not_placeholder_text() -> None:
    text = (PLUGIN_ROOT / "skills" / "agent-guard" / "SKILL.md").read_text(encoding="utf-8")
    runtime_readme = (PLUGIN_ROOT / "scripts" / "guard_runtime" / "README.md").read_text(encoding="utf-8")
    templates_readme = (PLUGIN_ROOT / "assets" / "templates" / "README.md").read_text(encoding="utf-8")

    for value in [text, runtime_readme, templates_readme]:
        assert "占位" not in value
        assert "入口骨架" not in value
        assert "后续模块提供" not in value


def test_plugin_skill_wrappers_resolve_plugin_runtime() -> None:
    core_scripts = PLUGIN_ROOT / "skills" / "agent-guard" / "scripts"
    activate_guard = load_module(core_scripts / "activate_guard.py", "plugin_activate_guard")
    render_guard_brief = load_module(core_scripts / "render_guard_brief.py", "plugin_render_guard_brief")
    run_guard_event = load_module(core_scripts / "run_guard_event.py", "plugin_run_guard_event")

    assert activate_guard.runtime_cli() == PLUGIN_ROOT / "scripts" / "guard_runtime" / "cli.py"
    assert render_guard_brief.runtime_cli() == PLUGIN_ROOT / "scripts" / "guard_runtime" / "cli.py"
    assert run_guard_event.runtime_cli() == PLUGIN_ROOT / "scripts" / "guard_runtime" / "cli.py"
    assert run_guard_event.hook_router() == PLUGIN_ROOT / "scripts" / "hook_router.py"
