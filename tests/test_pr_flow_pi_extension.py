from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "pr-flow"
EXTENSION = PLUGIN_ROOT / "extensions" / "pi-pr-flow.ts"
SKILL_NAMES = ["pr-flow", "pr-flow-complete", "pr-flow-cleanup", "pr-flow-hotfix", "pr-flow-tweak"]


def test_pi_extension_runs_the_packaged_pr_flow_script() -> None:
    source = EXTENSION.read_text(encoding="utf-8")

    assert 'name: "pr_flow"' in source
    assert "import.meta.url" in source
    assert "skills/pr-flow/scripts/pr_flow.py" in source
    assert "@gotgenes/pi-permission-system" not in source


def test_pr_flow_execution_skills_document_the_pi_tool_route() -> None:
    for skill_name in SKILL_NAMES:
        source = (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")

        assert "Pi（编码助手）" in source
        assert "pr_flow" in source
