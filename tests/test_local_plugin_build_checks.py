from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_BUILD_SCRIPT = REPO_ROOT / "scripts" / "local_plugin_build.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def build_case(monkeypatch):
    module = load_module(LOCAL_BUILD_SCRIPT, "repo_local_plugin_build")
    manifest = {"name": "alpha", "version": "9.9.0", "description": "alpha plugin", "skills": "./skills"}
    documents = {
        ".claude-plugin/marketplace.json": {"name": "test-marketplace", "plugins": [{"name": "alpha", "source": "./plugins/alpha"}]},
        ".agents/plugins/marketplace.json": {"name": "test-marketplace-dev", "interface": {"displayName": "Test Marketplace DEV"},
            "plugins": [{"name": "alpha", "source": {"source": "local", "path": "./plugins/alpha"}}]},
        "plugins/alpha/.claude-plugin/plugin.json": dict(manifest),
        "plugins/alpha/.codex-plugin/plugin.json": dict(manifest),
        ".release-flow/projection.yaml": {"generators": [{"type": "codex-marketplace", "plugins": ["alpha"]}]},
    }
    exists = {"plugins/alpha/skills": True, "plugins/alpha/missing-hooks": False}
    def read_text(path):
        relative = path.relative_to(REPO_ROOT).as_posix()
        assert relative in documents, f"unexpected build input: {relative}"
        value = documents[relative]
        if isinstance(value, BaseException):
            raise value
        return value if isinstance(value, str) else json.dumps(value)
    def path_exists(path):
        relative = path.relative_to(REPO_ROOT).as_posix()
        assert relative in exists, f"unexpected existence query: {relative}"
        return exists[relative]
    monkeypatch.setattr(module, "_read_text", read_text)
    monkeypatch.setattr(module, "_path_exists", path_exists)
    return module, documents


@pytest.mark.parametrize("argv", [[], ["build"]])
def test_local_plugin_build_main_outputs_stable_status(build_case, argv, capsys):
    module, _ = build_case
    assert module.main(argv) == 0
    assert capsys.readouterr().out == "status: build checks passed\n"


def test_local_plugin_build_main_prefers_explicit_argv_over_sys_argv(build_case, monkeypatch, capsys):
    module, _ = build_case
    monkeypatch.setattr(sys, "argv", ["local_plugin_build.py", "verify"])
    assert module.main(["build"]) == 0
    assert "status: build checks passed" in capsys.readouterr().out


def test_local_plugin_build_main_rejects_verify_command(build_case, capsys):
    module, _ = build_case
    assert module.main(["verify"]) == 2
    assert "unknown command: verify" in capsys.readouterr().err


@pytest.mark.parametrize("case,expected", [
    ("claude-source-outside", "source_outside_repo"),
    ("codex-name", "codex_dev_marketplace_name_missing_dev"),
    ("codex-source-outside", "codex_dev_source_outside_repo"),
    ("invalid-entry", "invalid_marketplace_entry"),
    ("duplicate-marketplace", "duplicate_marketplace_plugin: alpha"),
    ("missing-yaml", "missing_dependency: PyYAML"),
    ("manifest-name", "claude_manifest_name_mismatch"),
    ("missing-hooks", "missing_manifest_path"),
    ("projection-extra", "projection_plugins_mismatch"),
    ("projection-missing", "projection_plugins_mismatch"),
    ("projection-duplicate", "duplicate_projection_plugin"),
])
def test_local_build_error_matrix_keeps_real_main(build_case, case, expected, capsys):
    module, docs = build_case
    claude = docs[".claude-plugin/marketplace.json"]
    codex = docs[".agents/plugins/marketplace.json"]
    projection = docs[".release-flow/projection.yaml"]["generators"][0]["plugins"]
    if case == "claude-source-outside": claude["plugins"][0]["source"] = "../outside"
    elif case == "codex-name": codex.update(name="test-marketplace", interface={"displayName": "Test Marketplace"})
    elif case == "codex-source-outside": codex["plugins"][0]["source"]["path"] = "../outside"
    elif case == "invalid-entry": claude["plugins"] = ["not-a-plugin"]
    elif case == "duplicate-marketplace": claude["plugins"] *= 2
    elif case == "missing-yaml": module.yaml = None
    elif case == "manifest-name": docs["plugins/alpha/.claude-plugin/plugin.json"]["name"] = "wrong"
    elif case == "missing-hooks": docs["plugins/alpha/.codex-plugin/plugin.json"]["hooks"] = "./missing-hooks"
    elif case == "projection-extra": projection.append("missing")
    elif case == "projection-missing": projection.clear()
    elif case == "projection-duplicate": projection.append("alpha")
    assert module.main(["build"]) == 1
    output = capsys.readouterr()
    assert expected in output.err and "status: build checks passed" not in output.out
    if case == "codex-name": assert "codex_dev_marketplace_display_name_missing_DEV" in output.err


@pytest.mark.parametrize("value,expected", [
    (FileNotFoundError("missing"), "missing_file"),
    ("not-json", "invalid_json"),
    ("[]", "invalid_json_object"),
])
def test_local_build_json_read_errors_are_reported(build_case, value, expected, capsys):
    module, docs = build_case
    docs[".claude-plugin/marketplace.json"] = value
    assert module.main(["build"]) == 1
    assert expected in capsys.readouterr().err


@pytest.mark.parametrize("argument,expected", [
    ("tests/test_my_spec.py", set()),
    ("tests/integration/test_npm.py::TestMySpec", {"myspec"}),
    ("tests/integration/test_npm.py::TestBuildAndVerify", {"build-and-verify"}),
    ("tests/integration/test_npm.py", {"myspec", "build-and-verify"}),
    ("tests", {"myspec", "build-and-verify"}),
])
def test_npm_candidates_are_selected_only_by_integration_scope(argument, expected):
    module = load_module(REPO_ROOT / "tests/integration/conftest.py", "candidate_selection_contract")
    config = SimpleNamespace(args=[argument], invocation_params=SimpleNamespace(dir=REPO_ROOT))
    assert module._selected_npm_packages(config) == expected

def test_shared_marketplaces_offer_seven_skills_without_npm_tools() -> None:
    expected = {"release-flow", "pr-flow", "dev-flow", "subagent-policy", "plugin-sync", "retro-to-issues", "data-store"}
    for relative in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
        catalog = json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))
        assert catalog["name"] == "my-agent-skills-marketplace-dev"
        assert {entry["name"] for entry in catalog["plugins"]} == expected


def test_node_cli_launchers_are_forced_to_lf() -> None:
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()

    assert "plugins/build-and-verify/bin/*.js text eol=lf" in attributes
    assert "plugins/my-spec/bin/*.js text eol=lf" in attributes


def test_active_automation_does_not_reference_removed_check_entrypoint() -> None:
    active_files = [
        REPO_ROOT / ".github" / "workflows" / "release.yml",
        REPO_ROOT / ".build-and-verify" / "config.json",
    ]

    for path in active_files:
        text = path.read_text(encoding="utf-8").replace("\\", "/")
        assert "scripts/check.py" not in text
