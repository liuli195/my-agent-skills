from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
EXTENSION = PLUGIN_ROOT / "extensions" / "pi-agent-guard.ts"


def test_pi_extension_uses_native_events_and_existing_router_only() -> None:
    source = EXTENSION.read_text(encoding="utf-8")

    assert 'pi.on("session_start"' in source
    assert 'pi.on("tool_call"' in source
    assert "hook_router.py" in source
    assert "@gotgenes/pi-permission-system" not in source


def test_pi_extension_blocks_router_nonzero_exit_and_exposes_current_session_to_wrappers() -> None:
    source = EXTENSION.read_text(encoding="utf-8")

    assert 'child.on("close", (code)' in source
    assert "if (code !== 0)" in source
    assert 'process.env.AGENT_GUARD_SOURCE = "pi"' in source
    assert "process.env.AGENT_GUARD_SESSION_ID = sessionId" in source


def test_run_skill_documents_host_specific_session_context() -> None:
    references = PLUGIN_ROOT / "skills" / "agent-guard-run" / "references"

    for name in ["activate.md", "brief.md", "events.md"]:
        source = (references / name).read_text(encoding="utf-8")
        assert "--source codex" not in source
        assert "AGENT_GUARD_SOURCE" in source


def test_codex_and_claude_manifests_do_not_load_pi_extension() -> None:
    codex = (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    claude = (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")

    assert "extensions" not in codex
    assert "extensions" not in claude
