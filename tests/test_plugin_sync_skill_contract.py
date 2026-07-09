from __future__ import annotations

import os
from pathlib import Path


PLUGIN_SYNC_ROOT = Path(
    os.environ.get(
        "PLUGIN_SYNC_SKILL_ROOT",
        Path(__file__).parent / "fixtures" / "plugin-sync",
    )
)


def reference_text(name: str) -> str:
    assert PLUGIN_SYNC_ROOT.exists(), f"plugin-sync skill not found: {PLUGIN_SYNC_ROOT}"
    return (PLUGIN_SYNC_ROOT / "references" / name).read_text(encoding="utf-8")


def test_plugin_sync_runtime_status_taxonomy_uses_canonical_names() -> None:
    text = reference_text("status-taxonomy.md")

    for status in [
        "runtime_not_configured",
        "runtime_source_missing",
        "runtime_current",
        "runtime_stale",
        "runtime_updated",
        "update_failed",
    ]:
        assert f"`{status}`" in text
    assert "`not_configured`" not in text


def test_plugin_sync_runtime_update_reference_closes_sync_loop() -> None:
    text = reference_text("update-build-and-verify-runtime.md")

    for required in [
        ".build-and-verify/config.json",
        ".build-and-verify/runtime/",
        "runtime_current",
        "runtime_stale",
        "runtime_not_configured",
        "runtime_source_missing",
        "runtime_updated",
        "update_failed",
        "update-runtime",
        "version.json",
        "PR Flow",
    ]:
        assert required in text
    assert "`not_configured`" not in text
    assert "read-only" in text.lower()
    assert "explicit user authorization" in text
