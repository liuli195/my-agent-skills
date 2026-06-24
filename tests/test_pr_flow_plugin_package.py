import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "pr-flow"
CODEX_REPO_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
RELEASE_FLOW_PROJECTION = REPO_ROOT / ".release-flow" / "projection.yaml"

PLUGIN_NAME = "pr-flow"
PLUGIN_VERSION = "0.1.11"
PLUGIN_DESCRIPTION = "PR Flow Plugin（拉取请求流程插件）"
ENTRYPOINT_COMMANDS = {
    "pr-flow": "diagnose",
    "pr-flow-init": "init",
    "pr-flow-complete": "complete",
    "pr-flow-cleanup": "cleanup",
    "pr-flow-hotfix": "hotfix",
    "pr-flow-tweak": "tweak",
}


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


def test_pr_flow_manifests_are_valid_json() -> None:
    expected_manifest = {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "skills": "./skills",
    }

    assert read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json") == expected_manifest
    assert read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json") == expected_manifest


def test_pr_flow_skill_entrypoints_call_shared_script() -> None:
    for skill_name, command in ENTRYPOINT_COMMANDS.items():
        skill_text = (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
        front_matter = skill_text.split("---", 2)[1]

        assert skill_text.startswith("---\n")
        assert f"name: {skill_name}" in front_matter
        assert "description:" in front_matter
        assert "## 边界" in skill_text
        assert "pr_flow.py" in skill_text
        assert f" {command}" in skill_text
        if skill_name == "pr-flow-cleanup":
            assert "--pr" in skill_text


def test_pr_flow_cli_command_help_includes_command_name() -> None:
    script = PLUGIN_ROOT / "skills" / "pr-flow" / "scripts" / "pr_flow.py"

    for command in ENTRYPOINT_COMMANDS.values():
        result = subprocess.run(
            [sys.executable, str(script), command, "--help"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )

        assert result.returncode == 0, result.stderr
        assert command in result.stdout


def test_pr_flow_bare_commands_report_stable_contract() -> None:
    script = PLUGIN_ROOT / "skills" / "pr-flow" / "scripts" / "pr_flow.py"

    for skill_name, command in ENTRYPOINT_COMMANDS.items():
        result = subprocess.run(
            [sys.executable, str(script), command],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        skill_text = (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")

        assert result.returncode == 2
        assert result.stdout == ""
        assert "required:" in result.stderr
        assert "骨架入口" not in skill_text
        assert "status: not_implemented" not in skill_text


def test_pr_flow_package_passes_repo_build_checks() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "plugins/test-framework/skills/test-framework/scripts/test_framework.py",
            "build",
            "--project",
            ".",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "status: build checks passed" in result.stdout


def test_claude_marketplace_appends_pr_flow_after_cross_agent_review() -> None:
    catalog = read_json(CLAUDE_REPO_MARKETPLACE)
    names = plugin_names(catalog)

    assert plugin_after(names, "cross-agent-review") == PLUGIN_NAME
    assert catalog["plugins"][names.index(PLUGIN_NAME)] == {
        "name": PLUGIN_NAME,
        "source": "./plugins/pr-flow",
        "description": PLUGIN_DESCRIPTION,
    }


def test_codex_dev_marketplace_appends_pr_flow_after_cross_agent_review() -> None:
    catalog = read_json(CODEX_REPO_MARKETPLACE)
    names = plugin_names(catalog)

    assert plugin_after(names, "cross-agent-review") == PLUGIN_NAME
    assert catalog["plugins"][names.index(PLUGIN_NAME)] == {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": "./plugins/pr-flow"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools",
    }


def test_release_projection_appends_pr_flow_after_cross_agent_review() -> None:
    plugins = release_projection_plugins()

    assert plugin_after(plugins, "cross-agent-review") == PLUGIN_NAME
