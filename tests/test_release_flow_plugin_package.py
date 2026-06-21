import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "release-flow"
CODEX_REPO_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
RELEASE_FLOW_PROJECTION = REPO_ROOT / ".release-flow" / "projection.yaml"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_release_flow_manifests_are_valid_json() -> None:
    codex_manifest = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    claude_manifest = read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")

    assert codex_manifest["name"] == "release-flow"
    assert claude_manifest["name"] == "release-flow"
    assert codex_manifest["version"] == claude_manifest["version"]
    assert codex_manifest["skills"] == "./skills"
    assert claude_manifest["skills"] == "./skills"
    assert codex_manifest["description"]
    assert claude_manifest["description"]


def test_release_flow_package_contains_skill_scripts_and_templates() -> None:
    skill_root = PLUGIN_ROOT / "skills" / "release-flow"

    required = [
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        "skills/release-flow/SKILL.md",
        "skills/release-flow/scripts/release_flow.py",
        "skills/release-flow/assets/templates/release-flow/config.yaml",
        "skills/release-flow/assets/templates/release-flow/projection.yaml",
        "skills/release-flow/assets/templates/release-flow/gitignore",
        "skills/release-flow/assets/templates/github/workflows/release.yml",
    ]
    for item in required:
        assert (PLUGIN_ROOT / item).exists(), item

    text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    assert "release-flow" in text
    assert "Lorem ipsum" not in text
    assert "sample text only" not in text
    assert "not yet written" not in text


def test_release_flow_workflow_template_installs_pyyaml() -> None:
    workflow = (
        PLUGIN_ROOT
        / "skills"
        / "release-flow"
        / "assets"
        / "templates"
        / "github"
        / "workflows"
        / "release.yml"
    ).read_text(encoding="utf-8")

    assert "Install release-flow dependencies" in workflow
    assert "python -m pip install PyYAML" in workflow


def test_codex_release_flow_entry_is_generated_by_release_projection() -> None:
    projection = RELEASE_FLOW_PROJECTION.read_text(encoding="utf-8")
    codex_catalog = read_json(CODEX_REPO_MARKETPLACE)

    assert codex_catalog["name"] == "my-agent-skills-marketplace-dev"
    assert codex_catalog["interface"]["displayName"] == "My Agent Skills Marketplace DEV"
    assert "path: .agents/plugins/marketplace.json" in projection
    assert "type: codex-marketplace" in projection
    assert "release-flow" in projection
    release_flow_entries = [plugin for plugin in codex_catalog["plugins"] if plugin.get("name") == "release-flow"]
    assert release_flow_entries == [
        {
            "name": "release-flow",
            "source": {"source": "local", "path": "./plugins/release-flow"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        }
    ]


def test_claude_repo_marketplace_catalog_includes_release_flow_local_entry() -> None:
    claude_catalog = read_json(CLAUDE_REPO_MARKETPLACE)

    claude_entries = [
        plugin for plugin in claude_catalog["plugins"] if plugin.get("name") == "release-flow"
    ]

    assert claude_entries == [
        {
            "name": "release-flow",
            "source": "./plugins/release-flow",
            "description": "Release flow plugin for Codex and Claude agents",
        }
    ]
