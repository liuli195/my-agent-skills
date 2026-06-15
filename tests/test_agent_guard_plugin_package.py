import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"


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


def test_plugin_manifests_are_valid_json() -> None:
    codex_manifest = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    claude_manifest = read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")

    assert codex_manifest["name"] == "agent-guard"
    assert claude_manifest["name"] == "agent-guard"
    assert codex_manifest["hooks"] == "hooks/hooks.json"
    assert claude_manifest["hooks"] == "hooks/hooks.json"


def test_plugin_hooks_only_use_session_start_and_pre_tool_use() -> None:
    hooks = read_json(PLUGIN_ROOT / "hooks" / "hooks.json")

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


def test_plugin_package_contains_runtime_placeholder_skills_and_templates() -> None:
    assert (PLUGIN_ROOT / "scripts" / "hook_router.py").exists()
    assert (PLUGIN_ROOT / "scripts" / "guard_runtime").is_dir()
    assert (PLUGIN_ROOT / "scripts" / "guard_runtime" / "README.md").exists()
    assert (PLUGIN_ROOT / "skills" / "agent-guard" / "SKILL.md").exists()
    assert (PLUGIN_ROOT / "assets" / "templates").is_dir()
