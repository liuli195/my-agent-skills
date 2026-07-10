import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "cross-agent-review"
SCRIPT = PLUGIN_ROOT / "skills" / "cross-agent-review" / "scripts" / "cross_agent_review.py"
_SCRIPT_MODULE = None


def script_module():
    global _SCRIPT_MODULE
    if _SCRIPT_MODULE is not None:
        return _SCRIPT_MODULE
    spec = importlib.util.spec_from_file_location("cross_agent_review_package_for_tests", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _SCRIPT_MODULE = module
    return module


def run_script(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.chdir(cwd or REPO_ROOT), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            returncode = int(script_module().main(args))
        except SystemExit as error:
            returncode = error.code if isinstance(error.code, int) else 1
    return subprocess.CompletedProcess(
        [sys.executable, str(SCRIPT), *args],
        returncode,
        stdout.getvalue(),
        stderr.getvalue(),
    )


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
    assert "retry" in text
    assert "revalidate" in text
    assert "不自动安装" in text


def test_cross_agent_review_package_has_no_agent_guard_evidence_knowledge() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PLUGIN_ROOT.rglob("*")
        if path.is_file() and path.suffix in {".py", ".md"}
    )

    for forbidden in [
        "mark-pass",
        "comet-review-gate",
        "cross_agent_review_pass",
        ".local/guard/evidence",
        "guard-evidence/v1",
    ]:
        assert forbidden not in text


def test_cross_agent_review_skill_documents_single_review_input_contract() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert ".local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json" in text
    assert "`<head_ref_short>`（短头引用）等于 `head_ref`（头引用）的前 12 个字符。" in text
    assert "--input-file" in text
    assert "plan_file" in text
    assert "tasks_file" not in text
    assert "--spec-file" not in text
    assert "--design-file" not in text
    assert "--tasks-file" not in text


def test_cross_agent_review_skill_documents_exact_optional_input_contract() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    payloads = [
        json.loads(block.split("```", 1)[0])
        for block in text.split("```json\n")[1:]
    ]
    review_input = next(payload for payload in payloads if "summary_only" in payload)

    assert review_input["summary_only"] == [
        {"path": "docs/process.md", "reason": "过程文档仅供按需核对"}
    ]
    assert review_input["revalidation_policy"] == [
        {"path": "docs/checklist.md", "validator": "checkbox-only"},
        {
            "path": "manifest.yaml",
            "validator": "mapping-fields-only",
            "format": "yaml",
            "fields": ["status", "evidence"],
        },
    ]
    for required in [
        "change",
        "mode",
        "base_ref",
        "head_ref",
        "spec_file",
        "design_file",
        "plan_file",
    ]:
        assert required in review_input


def test_cross_agent_review_skill_documents_revalidation_fallback() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    for reason in ["未声明文件", "重叠策略", "解析失败", "规格或设计变化"]:
        assert reason in text
    assert "改用 `run`（运行）执行真实审查" in text


def test_cross_agent_review_skill_documents_allowed_mode_values() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "`mode`（模式）只能是 `convergence`（收敛）或 `endless`（无尽）" in text


def test_cross_agent_review_skill_documents_default_mode_and_comet_baseline() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    for phrase in [
        "默认使用 `convergence`（收敛）模式",
        "Comet build completion（双星构建完成）或 PR Flow local review（拉取请求流程本地审查）：使用 `convergence`（收敛）模式",
        "用户显式调用 cross-agent-review（跨代理审查）且没有说明模式：使用 `convergence`（收敛）模式",
        "用户明确要求“无尽模式”“每轮完整复查”“不要收窄范围”或等价表达：使用 `endless`（无尽）模式",
        "优先使用 plan（计划）文件头的 implementation baseline（实施基准）",
        "只有缺少 implementation baseline（实施基准）时，才回退到 change init baseline（变更初始化基准）",
    ]:
        assert phrase in text


def test_cross_agent_review_skill_documents_review_range_refs() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "review（审查）范围由 `base_ref`（基准引用）和 `head_ref`（当前提交引用）控制" in text


def test_cross_agent_review_skill_documents_default_and_debug_outputs() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "review-report.md" in text
    assert "review-state.json" in text
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
    result = run_script(
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
        cwd=PLUGIN_ROOT / "skills" / "cross-agent-review",
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
