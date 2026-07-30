from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXTENSION = REPO_ROOT / "plugins" / "pi-codex-usage-status" / "extensions" / "pi-codex-usage-status.ts"


def test_extension_uses_pi_auth_api_and_ordered_status_lifecycle() -> None:
    source = EXTENSION.read_text(encoding="utf-8")

    assert 'const STATUS_KEY = "mcp-codex"' in source
    assert 'const USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"' in source
    assert "getApiKeyAndHeaders" in source
    assert '"chatgpt-account-id"' in source
    assert 'originator: "pi"' in source
    assert 'SettingsManager.create(ctx.cwd).getGlobalSettings()' in source
    assert 'pi.on("session_start"' in source
    assert 'pi.on("session_shutdown"' in source
    assert "clearInterval(timer)" in source
    assert "controller?.abort()" in source
    assert "Authorization" in source
    assert "console." not in source
