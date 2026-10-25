"""Read-only entrypoint and configuration contracts, not side-effect inference."""
from __future__ import annotations

import ast
import fnmatch
import json
import shlex
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ORDINARY_CHECKS = {
    "verify.local-build-contract", "verify.release-flow", "verify.pr-flow",
    "verify.my-spec", "verify.runtime-boundaries", "verify.build-and-verify",
    "verify.build-and-verify-cli", "verify.data-store", "verify.cloud-bootstrap",
}
REAL_SELECTORS = {
    "verify.real-my-spec": ("tests/integration/test_npm.py::TestMySpec", 2),
    "verify.real-build-and-verify": ("tests/integration/test_npm.py::TestBuildAndVerify", 2),
    "verify.real-pr-flow": ("tests/integration/test_git_workflows.py::TestPrFlow", 2),
    "verify.real-release-flow": ("tests/integration/test_git_workflows.py::TestReleaseFlow", 2),
    "verify.real-workspace": ("tests/integration/test_filesystem.py::TestWorkspace", 2),
    "verify.real-data-store": ("tests/integration/test_native_data.py::TestDataStore", 2),
    "verify.real-cloud-bootstrap": ("tests/integration/test_project_environment.py::TestBootstrap", 2),
}


def _config() -> dict:
    config = json.loads((REPO_ROOT / ".build-and-verify/config.json").read_text(encoding="utf-8"))
    assert config["version"] == 2, "repository test-role migration is not enabled"
    return config


def _test_arguments(check: dict) -> list[str]:
    command = check["command"]
    tokens = shlex.split(command) if isinstance(command, str) else command
    return [token.replace("\\", "/") for token in tokens
            if str(token).replace("\\", "/").startswith("tests/")
            and str(token).split("::", 1)[0].endswith((".py", ".test.mjs"))]


def _covers(check: dict, field: str, relative: str) -> bool:
    return any(
        relative == pattern or fnmatch.fnmatchcase(relative, pattern)
        or ((field == "inputs" or pattern.endswith("/"))
            and relative.startswith(pattern.rstrip("/") + "/"))
        for pattern in check.get(field, [])
    )


def test_config_explicitly_assigns_all_guarded_and_real_check_roles() -> None:
    config = _config()
    assert len(config["build"]["checks"]) == 2
    verify = config["verify"]
    checks = verify["checks"]
    ids = [check["id"] for check in checks]
    real_ids = verify["realChecks"]
    assert len(checks) == 17
    assert len(ids) == len(set(ids)) and all(ids)
    assert len(real_ids) == len(set(real_ids)) == 8
    assert set(real_ids) == {*REAL_SELECTORS, "verify.myspec"}
    assert set(ids) - set(real_ids) == ORDINARY_CHECKS
    assert all(ids.index(real) < ids.index(ordinary) for real in real_ids for ordinary in ORDINARY_CHECKS)
    assert (verify["maxParallel"], verify["timeoutSeconds"], verify["fullBudgetSeconds"]) == (8, 180, 60)
    assert verify.get("enforceLocalBudget", True) is True
    for check in checks:
        assert check.get("pr", True) is True
        if check["id"] in ORDINARY_CHECKS:
            assert check["pytestXdistWorkers"] == 2
            assert "--dist" not in check["command"]
        assert check["checkParallel"] is True
    by_id = {check["id"]: check for check in checks}
    assert by_id["verify.my-spec"]["timeoutSeconds"] == 420
    assert by_id["verify.real-my-spec"]["timeoutSeconds"] == 420
    assert by_id["verify.myspec"]["command"] == "node plugins/my-spec/bin/myspec.js validate-main myspec/specs"
    assert "pytestXdistWorkers" not in by_id["verify.myspec"]


def test_real_checks_select_existing_nonempty_classes() -> None:
    checks = {check["id"]: check for check in _config()["verify"]["checks"]}
    for check_id, (selector, workers) in REAL_SELECTORS.items():
        check = checks[check_id]
        assert _test_arguments(check) == [selector]
        assert check["pytestXdistWorkers"] == workers
        path, class_name = selector.split("::")
        tree = ast.parse((REPO_ROOT / path).read_text(encoding="utf-8"))
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name]
        assert len(classes) == 1, selector
        assert any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name.startswith("test_") for node in classes[0].body), selector


def test_explicit_test_entrypoints_cover_all_files_without_role_overlap() -> None:
    config = _config()
    arguments = [(check["id"], argument) for check in config["verify"]["checks"]
                 for argument in _test_arguments(check)]
    expected = {path.relative_to(REPO_ROOT).as_posix()
                for pattern in ("test_*.py", "*.test.mjs")
                for path in (REPO_ROOT / "tests").rglob(pattern)}
    assert {argument.split("::", 1)[0] for _, argument in arguments} == expected
    counts = Counter(argument for _, argument in arguments)
    assert all(count == 1 for count in counts.values()), counts
    for check_id, argument in arguments:
        assert ("/integration/" in argument) == (check_id in REAL_SELECTORS), (check_id, argument)
    assert not (REPO_ROOT / "pyproject.toml").exists()


def test_paths_and_inputs_cover_entrypoints_and_shared_preparation() -> None:
    checks = {check["id"]: check for check in _config()["verify"]["checks"]}
    for check in checks.values():
        files = {argument.split("::", 1)[0] for argument in _test_arguments(check)}
        if not files:
            continue
        files.add("tests/conftest.py")
        if check["id"] in REAL_SELECTORS:
            files.add("tests/integration/conftest.py")
        for field in ("paths", "inputs"):
            for relative in files:
                assert _covers(check, field, relative), (check["id"], field, relative)
    for check_id, plugin in (("verify.real-my-spec", "my-spec"),
                             ("verify.real-build-and-verify", "build-and-verify")):
        check = checks[check_id]
        other = "build-and-verify" if plugin == "my-spec" else "my-spec"
        for field in ("paths", "inputs"):
            for relative in (f"plugins/{plugin}/package.json", "plugins/tool-lifecycle/pack.py",
                             "plugins/tool-lifecycle/python/management.py", "tests/support/npm_candidates.py"):
                assert _covers(check, field, relative), (check_id, field, relative)
            assert not _covers(check, field, f"plugins/{other}/python/unrelated.py")
            assert not _covers(check, field, "tests/unrelated_future_test.py")
    for field in ("paths", "inputs"):
        assert _covers(checks["verify.runtime-boundaries"], field, "tests/future/test_new.py")
