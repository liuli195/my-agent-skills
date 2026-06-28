import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "cross-agent-review"
SCRIPT = PLUGIN_ROOT / "skills" / "cross-agent-review" / "scripts" / "cross_agent_review.py"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_cross_agent_review_manifests_are_valid() -> None:
    codex_manifest = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    claude_manifest = read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")

    assert codex_manifest["name"] == "cross-agent-review"
    assert claude_manifest["name"] == "cross-agent-review"
    assert codex_manifest["version"] == claude_manifest["version"]
    assert codex_manifest["skills"] == "./skills"
    assert claude_manifest["skills"] == "./skills"
    assert codex_manifest["description"]
    assert claude_manifest["description"]


def test_cross_agent_review_skill_and_script_are_packaged() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    prompt_template = PLUGIN_ROOT / "skills" / "cross-agent-review" / "assets" / "templates" / "reviewer-prompt.md"

    assert skill.is_file()
    assert SCRIPT.is_file()
    assert prompt_template.is_file()
    text = skill.read_text(encoding="utf-8")
    assert "Claude Agent SDK" in text
    assert "mark-pass" in text
    assert "不自动安装" in text


def test_cross_agent_review_skill_documents_single_review_input_contract() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert ".local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json" in text
    assert "--input-file" in text
    assert "plan_file" in text
    assert "tasks_file" not in text
    assert "--spec-file" not in text
    assert "--design-file" not in text
    assert "--tasks-file" not in text


def test_cross_agent_review_skill_documents_allowed_mode_values() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "`mode`（模式）只能是 `convergence`（收敛）或 `endless`（无尽）" in text


def test_cross_agent_review_skill_documents_review_range_refs() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "review（审查）范围由 `base_ref`（基准引用）和 `head_ref`（当前提交引用）控制" in text


def test_cross_agent_review_skill_documents_default_and_debug_outputs() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "review-report.md" in text
    assert "pass.json" in text
    assert "cross_agent_review_pass" in text
    assert "review-results.json" not in text
    assert "inputs/manifest.json" not in text
    assert "inputs/spec.md" not in text
    assert "inputs/design.md" not in text
    assert "inputs/tasks.md" not in text
    assert "debug/review-input.json" in text
    assert "debug/prompts/<role>.txt" in text
    assert "debug/raw/<role>.txt" in text


def test_cross_agent_review_skill_documents_two_reviewers_only() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "spec-alignment" in text
    assert "implementation-correctness" in text
    assert "tests-and-edge-cases" not in text
    assert "risk-review" not in text


def test_cross_agent_review_skill_documents_input_staging_under_run_dir() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert ".local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/" in text
    assert ".local/cross-agent-review-inputs" not in text
    assert "debug/prompts/" in text
    assert "debug/raw/" in text


def test_cross_agent_review_skill_documents_manifest_diff_commands_and_timeout_boundary() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "--diff-file" not in text
    assert "inputs/diff.patch" not in text
    assert "git diff --name-status --find-renames --find-copies-harder <base-ref>...<head-ref>" in text
    assert "git diff <base-ref>...<head-ref> -- <path>" in text
    assert "外层" in text
    assert "480 秒" in text
    assert "540 秒" in text
    assert "timeout/watchdog" in text


def test_cross_agent_review_skill_documents_strict_finding_schema() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    for severity in ["CRITICAL", "IMPORTANT", "WARNING", "SUGGESTION"]:
        assert severity in text
    assert "severity aliases" in text
    assert "缺少 `Severity:`" in text


def test_cross_agent_review_skill_documents_mandatory_invocation_boundary() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    boundary = text.index("## 调用边界（强制）")
    prerequisites = text.index("## 前置条件")
    assert boundary < prerequisites

    boundary_text = text[boundary:prerequisites]
    assert "ONLY ALLOWED:" in boundary_text
    assert "STRICTLY FORBIDDEN:" in boundary_text
    assert "Comet build completion" in boundary_text
    assert "PR Flow" in boundary_text
    assert "local review" in boundary_text
    assert "用户显式调用" in boundary_text
    assert "Comet verify" in boundary_text
    assert "通用 code review" in boundary_text


def test_cross_agent_review_skill_does_not_require_test_evidence() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "测试结果文件默认生成" not in text
    assert "--tests-file" not in text
    assert "tests.txt" not in text
    assert "调用方已运行测试" not in text


def test_cross_agent_review_spec_documents_lightweight_review_input_contract() -> None:
    spec = REPO_ROOT / "openspec" / "specs" / "cross-agent-review" / "spec.md"
    text = spec.read_text(encoding="utf-8")

    assert "prepared-inputs/review-input.json" in text
    assert "spec_file" in text
    assert "design_file" in text
    assert "plan_file" in text
    assert "inputs/manifest.json" in text
    assert "提示中的 diff、spec、design 和 tasks 内容 MUST" not in text


def test_cross_agent_review_rejects_removed_cli_options(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "run",
            "--input-file",
            str(tmp_path / "review-input.json"),
            "--spec-file",
            str(tmp_path / "spec.md"),
            "--design-file",
            str(tmp_path / "design.md"),
            "--tasks-file",
            str(tmp_path / "tasks.md"),
            "--disable-risk-review",
        ],
        cwd=PLUGIN_ROOT / "skills" / "cross-agent-review",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_claude_repo_marketplace_includes_cross_agent_review() -> None:
    catalog = read_json(REPO_ROOT / ".claude-plugin" / "marketplace.json")
    entries = [plugin for plugin in catalog["plugins"] if plugin.get("name") == "cross-agent-review"]

    assert entries == [
        {
            "name": "cross-agent-review",
            "source": "./plugins/cross-agent-review",
            "description": "Cross-agent review plugin for Codex and Claude agents",
        }
    ]


def test_release_projection_includes_cross_agent_review() -> None:
    text = (REPO_ROOT / ".release-flow" / "projection.yaml").read_text(encoding="utf-8")
    assert "      - cross-agent-review" in text
