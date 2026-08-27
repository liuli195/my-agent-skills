from __future__ import annotations

from pathlib import Path


PLUGIN_SYNC_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "plugin-sync" / "skills" / "plugin-sync"


def reference_text(name: str) -> str:
    assert PLUGIN_SYNC_ROOT.exists(), f"plugin-sync skill not found: {PLUGIN_SYNC_ROOT}"
    return (PLUGIN_SYNC_ROOT / "references" / name).read_text(encoding="utf-8")


def test_plugin_sync_delegates_build_and_verify_lifecycle() -> None:
    text = reference_text("update-build-and-verify-runtime.md")

    for command in ["build-and-verify doctor", "build-and-verify init", "build-and-verify update"]:
        assert command in text
    assert "explicit user authorization" in text
    for forbidden in ["update-runtime", "runtime_current", "runtime_stale", "PR Flow"]:
        assert forbidden not in text
