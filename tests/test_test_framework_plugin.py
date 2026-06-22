import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "test-framework"
CODEX_REPO_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
RELEASE_FLOW_PROJECTION = REPO_ROOT / ".release-flow" / "projection.yaml"
RELEASE_FLOW_SCRIPT = Path("plugins/release-flow/skills/release-flow/scripts/release_flow.py")

PLUGIN_NAME = "test-framework"
PLUGIN_VERSION = "0.1.8"
PLUGIN_DESCRIPTION = "Test Framework Plugin（测试框架插件）"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def plugin_names(catalog: dict) -> list[str]:
    return [plugin["name"] for plugin in catalog["plugins"]]


def plugin_after(names: list[str], left: str) -> str:
    return names[names.index(left) + 1]


def release_projection_plugins() -> list[str]:
    lines = RELEASE_FLOW_PROJECTION.read_text(encoding="utf-8").splitlines()
    in_codex_generator = False
    in_plugins = False
    plugins: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "- path: .agents/plugins/marketplace.json":
            in_codex_generator = True
            continue
        if in_codex_generator and stripped.startswith("- path: ") and plugins:
            break
        if in_codex_generator and stripped == "plugins:":
            in_plugins = True
            continue
        if in_plugins:
            if line.startswith("      - "):
                plugins.append(stripped.removeprefix("- "))
                continue
            if plugins:
                break

    return plugins


def test_test_framework_plugin_has_dual_manifests() -> None:
    expected_manifest = {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "skills": "./skills",
    }

    assert read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json") == expected_manifest
    assert read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json") == expected_manifest


def test_test_framework_plugin_has_single_skill_entrypoint() -> None:
    skill_root = PLUGIN_ROOT / "skills"
    skill_dirs = [path.name for path in skill_root.iterdir() if path.is_dir()]
    skill_text = (skill_root / PLUGIN_NAME / "SKILL.md").read_text(encoding="utf-8")
    front_matter = skill_text.split("---", 2)[1]

    assert skill_dirs == [PLUGIN_NAME]
    assert skill_text.startswith("---\n")
    assert f"name: {PLUGIN_NAME}" in front_matter
    assert "只初始化测试框架产物" in skill_text
    assert "不安装依赖" in skill_text
    assert "不写用户级配置" in skill_text
    assert "不配置 CI（持续集成）" in skill_text
    assert "不内置仓库业务逻辑" in skill_text
    assert "scripts/test_framework.py init" in skill_text


def test_test_framework_registered_in_marketplaces_and_projection() -> None:
    claude_catalog = read_json(CLAUDE_REPO_MARKETPLACE)
    codex_catalog = read_json(CODEX_REPO_MARKETPLACE)
    claude_names = plugin_names(claude_catalog)
    codex_names = plugin_names(codex_catalog)
    projection_plugins = release_projection_plugins()

    assert plugin_after(claude_names, "pr-flow") == PLUGIN_NAME
    assert claude_catalog["plugins"][claude_names.index(PLUGIN_NAME)] == {
        "name": PLUGIN_NAME,
        "source": "./plugins/test-framework",
        "description": PLUGIN_DESCRIPTION,
    }
    assert plugin_after(codex_names, "pr-flow") == PLUGIN_NAME
    assert codex_catalog["plugins"][codex_names.index(PLUGIN_NAME)] == {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": "./plugins/test-framework"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools",
    }
    assert plugin_after(projection_plugins, "pr-flow") == PLUGIN_NAME


def test_test_framework_release_projection_passes_real_validate() -> None:
    result = subprocess.run(
        ["python", str(RELEASE_FLOW_SCRIPT), "validate", "--project", "."],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
