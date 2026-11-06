from pathlib import Path


PLUGIN_SYNC_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "plugin-sync" / "skills" / "plugin-sync"


def test_plugin_sync_delegates_build_and_verify_lifecycle() -> None:
    text = (PLUGIN_SYNC_ROOT / "references/update-build-and-verify-runtime.md").read_text(encoding="utf-8")
    for command in ["build-and-verify doctor", "build-and-verify init", "build-and-verify update"]:
        assert command in text
    assert "explicit user authorization" in text
    for forbidden in ["update-runtime", "runtime_current", "runtime_stale", "PR Flow"]:
        assert forbidden not in text


def test_plugin_sync_has_no_cloud_account_delivery_script() -> None:
    assert not (PLUGIN_SYNC_ROOT / "scripts/plugin_sync.py").exists()
