import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "pr-flow"
CODEX_REPO_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
RELEASE_FLOW_PROJECTION = REPO_ROOT / ".release-flow" / "projection.yaml"
LOCAL_PLUGIN_BUILD = REPO_ROOT / "scripts" / "local_plugin_build.py"

PLUGIN_NAME = "pr-flow"
PLUGIN_DESCRIPTION = (
    "PR Flow Plugin（拉取请求流程插件）。pr-flow-init 初始化 PR Flow（拉取请求流程）配置："
    "agent（代理）问答、配置草案、只读 validate（校验）和用户确认后本地写入。"
)
PR_FLOW_SCRIPT = PLUGIN_ROOT / "skills" / "pr-flow" / "scripts" / "pr_flow.py"
_PR_FLOW_MODULE = None
_LOCAL_PLUGIN_BUILD_MODULE = None
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


def pr_flow_module():
    global _PR_FLOW_MODULE
    if _PR_FLOW_MODULE is not None:
        return _PR_FLOW_MODULE
    spec = importlib.util.spec_from_file_location("pr_flow_package_for_tests", PR_FLOW_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _PR_FLOW_MODULE = module
    return module


def run_pr_flow(*args: str) -> subprocess.CompletedProcess[str]:
    module = pr_flow_module()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.chdir(REPO_ROOT), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            returncode = int(module.main(args))
        except SystemExit as error:
            returncode = error.code if isinstance(error.code, int) else 1
    return subprocess.CompletedProcess(
        [sys.executable, str(PR_FLOW_SCRIPT), *args],
        returncode,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def local_plugin_build_module():
    global _LOCAL_PLUGIN_BUILD_MODULE
    if _LOCAL_PLUGIN_BUILD_MODULE is not None:
        return _LOCAL_PLUGIN_BUILD_MODULE
    spec = importlib.util.spec_from_file_location("local_plugin_build_for_pr_flow_tests", LOCAL_PLUGIN_BUILD)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _LOCAL_PLUGIN_BUILD_MODULE = module
    return module


def run_local_plugin_build() -> subprocess.CompletedProcess[str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.chdir(REPO_ROOT), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            returncode = int(local_plugin_build_module().main(["build"]))
        except SystemExit as error:
            returncode = error.code if isinstance(error.code, int) else 1
    return subprocess.CompletedProcess(
        [sys.executable, str(LOCAL_PLUGIN_BUILD), "build"],
        returncode,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def test_pr_flow_manifests_are_valid_json() -> None:
    codex_manifest = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    claude_manifest = read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")

    assert codex_manifest["name"] == PLUGIN_NAME
    assert claude_manifest["name"] == PLUGIN_NAME
    assert codex_manifest["version"] == claude_manifest["version"]
    assert codex_manifest["description"] == PLUGIN_DESCRIPTION
    assert claude_manifest["description"] == PLUGIN_DESCRIPTION
    assert codex_manifest["skills"] == "./skills"
    assert claude_manifest["skills"] == "./skills"


def test_pr_flow_skill_entrypoints_call_shared_script() -> None:
    for skill_name, command in ENTRYPOINT_COMMANDS.items():
        skill_text = (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
        front_matter = skill_text.split("---", 2)[1]

        assert skill_text.startswith("---\n")
        assert f"name: {skill_name}" in front_matter
        assert "description:" in front_matter
        if skill_name == "pr-flow-init":
            assert "## Hard Boundaries" in skill_text
            assert "references/questionnaire.md" in skill_text
            assert "validate --config <path>" in skill_text
            assert "init --project <repo> --config <path>" in skill_text
            continue
        assert "## 边界" in skill_text
        assert "pr_flow.py" in skill_text
        assert f" {command}" in skill_text
        if skill_name == "pr-flow-cleanup":
            assert "--pr" in skill_text


def test_pr_flow_cli_command_help_includes_command_name() -> None:
    for command in ENTRYPOINT_COMMANDS.values():
        result = run_pr_flow(command, "--help")

        assert result.returncode == 0, result.stderr
        assert command in result.stdout


def test_pr_flow_bare_commands_report_stable_contract() -> None:
    for skill_name, command in ENTRYPOINT_COMMANDS.items():
        result = run_pr_flow(command)
        skill_text = (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")

        assert result.returncode == 2
        assert result.stdout == ""
        assert "required:" in result.stderr
        assert "骨架入口" not in skill_text
        assert "status: not_implemented" not in skill_text


def test_pr_flow_package_passes_repo_build_checks() -> None:
    if shutil.which("claude") is None:
        pytest.skip("claude CLI is required for package validation")

    result = run_local_plugin_build()

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
