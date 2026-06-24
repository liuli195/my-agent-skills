import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_BUILD_SCRIPT = REPO_ROOT / "scripts" / "local_plugin_build.py"
BUILD_AND_VERIFY_RUNNER = (
    REPO_ROOT
    / "plugins"
    / "build-and-verify"
    / "skills"
    / "build-and-verify"
    / "scripts"
    / "build_and_verify_runner.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_check_module():
    return load_module(BUILD_AND_VERIFY_RUNNER, "build_and_verify_runner")


def load_local_build_module():
    return load_module(LOCAL_BUILD_SCRIPT, "repo_local_plugin_build")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_runner_config(
    root: Path,
    *,
    build_checks: list[dict[str, Any]] | None = None,
    verify_checks: list[dict[str, Any]] | None = None,
) -> None:
    write_json(
        root / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": build_checks or []},
            "verify": {"checks": verify_checks or []},
        },
    )


def make_completed(command, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(command, returncode, "", "")


def make_plugin(root: Path, name: str) -> Path:
    plugin = root / "plugins" / name
    write_json(
        plugin / ".claude-plugin" / "plugin.json",
        {
            "name": name,
            "version": "0.1.0",
            "description": f"{name} plugin",
            "skills": "./skills",
        },
    )
    write_json(
        plugin / ".codex-plugin" / "plugin.json",
        {
            "name": name,
            "version": "0.1.0",
            "description": f"{name} plugin",
            "skills": "./skills",
        },
    )
    (plugin / "skills" / name).mkdir(parents=True)
    (plugin / "skills" / name / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name}\n---\n",
        encoding="utf-8",
    )
    return plugin


def make_marketplace(root: Path, names: list[str]) -> None:
    write_json(
        root / ".claude-plugin" / "marketplace.json",
        {
            "name": "test-marketplace",
            "owner": {"name": "Test"},
            "plugins": [
                {
                    "name": name,
                    "source": f"./plugins/{name}",
                    "description": f"{name} plugin",
                }
                for name in names
            ],
        },
    )
    make_codex_dev_marketplace(root, names)


def make_codex_dev_marketplace(
    root: Path,
    names: list[str],
    *,
    marketplace_name: str = "test-marketplace-dev",
    display_name: str = "Test Marketplace DEV",
) -> None:
    write_json(
        root / ".agents" / "plugins" / "marketplace.json",
        {
            "name": marketplace_name,
            "interface": {"displayName": display_name},
            "plugins": [
                {
                    "name": name,
                    "source": {"source": "local", "path": f"./plugins/{name}"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Developer Tools",
                }
                for name in names
            ],
        },
    )


def make_projection(root: Path, names: list[str]) -> None:
    projection = "\n".join(
        [
            "version: 1",
            "",
            "generators:",
            "  - path: .agents/plugins/marketplace.json",
            "    type: codex-marketplace",
            "    identity: codex",
            "    plugins:",
            *[f"      - {name}" for name in names],
            "",
        ]
    )
    (root / ".release-flow").mkdir(parents=True)
    (root / ".release-flow" / "projection.yaml").write_text(projection, encoding="utf-8")


def test_runner_build_runs_configured_checks(tmp_path: Path, capsys) -> None:
    module = load_check_module()
    write_runner_config(
        tmp_path,
        build_checks=[
            {"id": "build.one", "command": "run-build-one"},
            {"id": "build.two", "command": "run-build-two"},
        ],
    )
    calls: list[tuple[str, Path, bool]] = []

    def fake_run(command, cwd, check, text, capture_output, shell=False, timeout=None):
        calls.append((command, cwd, shell))
        return make_completed(command)

    result = module.run_build(tmp_path, runner=fake_run)

    assert result == 0
    assert calls == [
        ("run-build-one", tmp_path, True),
        ("run-build-two", tmp_path, True),
    ]
    output = capsys.readouterr().out
    assert "checked: build.one, build.two" in output
    assert "status: passed" in output


def test_runner_build_reports_failed_check(tmp_path: Path, capsys) -> None:
    module = load_check_module()
    write_runner_config(
        tmp_path,
        build_checks=[
            {"id": "build.one", "command": "run-build-one"},
            {"id": "build.two", "command": "run-build-two"},
        ],
    )

    def fake_run(command, cwd, check, text, capture_output, shell=False, timeout=None):
        if command == "run-build-two":
            return subprocess.CompletedProcess(command, 9, "", "build.two failed\n")
        return make_completed(command)

    result = module.run_build(tmp_path, runner=fake_run)
    captured = capsys.readouterr()

    assert result == 1
    assert "checked: build.one, build.two" in captured.out
    assert "status: failed" in captured.out
    assert "build.two failed" in captured.err


def test_runner_default_verify_selects_changed_checks_and_uses_cache(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("unchanged\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        verify_checks=[
            {
                "id": "verify.src",
                "command": "run-verify-src",
                "paths": ["src/**"],
                "inputs": ["src/app.py"],
            },
            {
                "id": "verify.docs",
                "command": "run-verify-docs",
                "paths": ["docs/**"],
                "inputs": ["docs/guide.md"],
            },
        ],
    )
    monkeypatch.setattr(
        module, "_changed_files", lambda _root: ["src/app.py"], raising=False
    )
    calls: list[tuple[str, bool]] = []

    def fake_run(command, cwd, check, text, capture_output, shell=False, timeout=None):
        calls.append((command, shell))
        return make_completed(command)

    first = module.run_verify(tmp_path, runner=fake_run)
    second = module.run_verify(tmp_path, runner=fake_run)

    assert first == 0
    assert second == 0
    assert calls == [("run-verify-src", True)]
    output = capsys.readouterr().out
    assert "checked: verify.src" in output
    assert "full-not-run: true" in output
    assert "cache-hit: verify.src" in output
    assert "verify.docs" not in output


def test_runner_full_verify_runs_all_checks_without_cache(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("unchanged\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        verify_checks=[
            {
                "id": "verify.src",
                "command": "run-verify-src",
                "paths": ["src/**"],
                "inputs": ["src/app.py"],
            },
            {
                "id": "verify.docs",
                "command": "run-verify-docs",
                "paths": ["docs/**"],
                "inputs": ["docs/guide.md"],
            },
        ],
    )
    monkeypatch.setattr(
        module, "_changed_files", lambda _root: ["src/app.py"], raising=False
    )
    calls: list[str] = []

    def fake_run(command, cwd, check, text, capture_output, shell=False, timeout=None):
        calls.append(command)
        return make_completed(command)

    assert module.run_verify(tmp_path, runner=fake_run) == 0
    capsys.readouterr()
    calls.clear()

    result = module.run_verify(tmp_path, runner=fake_run, full=True)

    assert result == 0
    assert calls == ["run-verify-src", "run-verify-docs"]
    output = capsys.readouterr().out
    assert "checked: verify.src, verify.docs" in output
    assert "full-not-run: false" in output
    assert "cache-hit:" not in output


def test_runner_full_verify_refreshes_cache_for_default_verify(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        verify_checks=[
            {
                "id": "verify.src",
                "command": "run-verify-src",
                "paths": ["src/app.py"],
                "inputs": ["src/app.py"],
            }
        ],
    )
    monkeypatch.setattr(module, "_changed_files", lambda _root: ["src/app.py"], raising=False)
    calls: list[str] = []

    def fake_run(command, cwd, check, text, capture_output, shell=False, timeout=None):
        calls.append(command)
        return make_completed(command)

    full = module.run_verify(tmp_path, runner=fake_run, full=True)
    full_output = capsys.readouterr().out
    default = module.run_verify(tmp_path, runner=fake_run)
    default_output = capsys.readouterr().out

    assert full == 0
    assert default == 0
    assert calls == ["run-verify-src"]
    assert "cache-hit:" not in full_output
    assert "cache-hit: verify.src" in default_output


def test_runner_does_not_cache_failed_verify_results(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "fails.py").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        verify_checks=[
            {
                "id": "verify.fail-once",
                "command": "run-fail-once",
                "paths": ["src/fails.py"],
                "inputs": ["src/fails.py"],
            }
        ],
    )
    monkeypatch.setattr(module, "_changed_files", lambda _root: ["src/fails.py"], raising=False)
    returncodes = [7, 0]
    calls: list[str] = []

    def fake_run(command, cwd, check, text, capture_output, shell=False, timeout=None):
        calls.append(command)
        return make_completed(command, returncodes.pop(0))

    first = module.run_verify(tmp_path, runner=fake_run)
    second = module.run_verify(tmp_path, runner=fake_run)

    assert first == 1
    assert second == 0
    assert calls == ["run-fail-once", "run-fail-once"]
    output = capsys.readouterr().out
    assert "cache-hit: verify.fail-once" not in output


def test_runner_default_check_cache_key_tracks_dirty_file_contents(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    dirty_file = tmp_path / "dirty.txt"
    dirty_file.write_text("first\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        verify_checks=[
            {
                "id": "verify.default",
                "command": "run-default",
            }
        ],
    )
    monkeypatch.setattr(module, "_changed_files", lambda _root: ["dirty.txt"], raising=False)
    calls: list[str] = []

    def fake_run(command, cwd, check, text, capture_output, shell=False, timeout=None):
        calls.append(command)
        return make_completed(command)

    first = module.run_verify(tmp_path, runner=fake_run)
    dirty_file.write_text("second\n", encoding="utf-8")
    second = module.run_verify(tmp_path, runner=fake_run)

    assert first == 0
    assert second == 0
    assert calls == ["run-default", "run-default"]
    output = capsys.readouterr().out
    assert "cache-hit: verify.default" not in output


def test_runner_cache_key_changes_with_runtime_versions(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        verify_checks=[
            {
                "id": "versioned-cache",
                "command": "run-versioned-cache",
                "paths": ["src/**"],
                "inputs": ["src/app.py"],
            }
        ],
    )
    config = module._load_config(tmp_path)
    check = config["verify"]["checks"][0]
    base_key = module._cache_key(tmp_path, config, check, ["src/app.py"])

    monkeypatch.setattr(
        module, "FRAMEWORK_VERSION", "changed-framework", raising=False
    )
    framework_key = module._cache_key(tmp_path, config, check, ["src/app.py"])
    monkeypatch.setattr(module, "FRAMEWORK_VERSION", "0.1.0", raising=False)
    monkeypatch.setattr(module, "CACHE_VERSION", "changed-cache", raising=False)
    cache_key = module._cache_key(tmp_path, config, check, ["src/app.py"])

    assert framework_key != base_key
    assert cache_key != base_key


def test_runner_cache_store_writes_passed_status(tmp_path: Path) -> None:
    module = load_check_module()
    check = {"id": "cache-status", "command": "run-cache-status"}

    module._cache_store(tmp_path, "abc123", check)

    cache_files = list((tmp_path / ".build-and-verify" / "cache").glob("*.json"))
    assert len(cache_files) == 1
    data = json.loads(cache_files[0].read_text(encoding="utf-8"))
    assert data == {"status": "passed", "id": "cache-status"}


def test_runner_build_reports_missing_config_without_traceback(
    tmp_path: Path, capsys
) -> None:
    module = load_check_module()

    result = module.run_build(tmp_path)
    captured = capsys.readouterr()

    assert result == 1
    assert "missing_config: .build-and-verify/config.json" in captured.err
    assert "status: failed" in captured.out
    assert "Traceback" not in captured.out + captured.err


def test_runner_build_reports_invalid_config_without_traceback(
    tmp_path: Path, capsys
) -> None:
    module = load_check_module()
    config = tmp_path / ".build-and-verify" / "config.json"
    config.parent.mkdir()
    config.write_text("{not json\n", encoding="utf-8")

    result = module.run_build(tmp_path)
    captured = capsys.readouterr()

    assert result == 1
    assert "invalid_config: .build-and-verify/config.json" in captured.err
    assert "status: failed" in captured.out
    assert "Traceback" not in captured.out + captured.err


def test_runner_verify_reports_missing_config_without_traceback(
    tmp_path: Path, capsys
) -> None:
    module = load_check_module()

    result = module.run_verify(tmp_path)
    captured = capsys.readouterr()

    assert result == 1
    assert "missing_config: .build-and-verify/config.json" in captured.err
    assert "status: failed" in captured.out
    assert "Traceback" not in captured.out + captured.err


def test_runner_verify_reports_invalid_config_without_traceback(
    tmp_path: Path, capsys
) -> None:
    module = load_check_module()
    config = tmp_path / ".build-and-verify" / "config.json"
    config.parent.mkdir()
    config.write_text("{not json\n", encoding="utf-8")

    result = module.run_verify(tmp_path)
    captured = capsys.readouterr()

    assert result == 1
    assert "invalid_config: .build-and-verify/config.json" in captured.err
    assert "status: failed" in captured.out
    assert "Traceback" not in captured.out + captured.err


@pytest.mark.parametrize(
    ("config_data", "expected_error"),
    [
        ([], "root must be object"),
        ({"build": "bad", "verify": {"checks": []}}, "build must be object"),
        (
            {"build": {"checks": "bad"}, "verify": {"checks": []}},
            "build.checks must be list",
        ),
        (
            {"build": {"checks": ["bad"]}, "verify": {"checks": []}},
            "build.checks[0] must be object",
        ),
        (
            {
                "build": {"checks": [{"id": "bad", "command": 123}]},
                "verify": {"checks": []},
            },
            "build.checks[0].command must be non-empty string or list of non-empty strings",
        ),
        (
            {
                "build": {"checks": [{"id": "no-command"}]},
                "verify": {"checks": []},
            },
            "build.checks[0].command must be non-empty string or list of non-empty strings",
        ),
        (
            {
                "build": {"checks": [{"id": "bad", "command": ["ok", 123]}]},
                "verify": {"checks": []},
            },
            "build.checks[0].command must be non-empty string or list of non-empty strings",
        ),
        (
            {
                "build": {"checks": []},
                "verify": {"checks": [{"id": "bad", "command": "ok", "paths": "src/**"}]},
            },
            "verify.checks[0].paths must be list of non-empty strings",
        ),
        (
            {
                "build": {"checks": []},
                "verify": {"checks": [{"id": "bad", "command": "ok", "inputs": ["src", 123]}]},
            },
            "verify.checks[0].inputs must be list of non-empty strings",
        ),
        (
            {
                "build": {"checks": [{"id": "", "command": "ok"}]},
                "verify": {"checks": []},
            },
            "build.checks[0].id must be non-empty string",
        ),
        (
            {
                "build": {
                    "checks": [
                        {"id": "duplicate", "command": "ok"},
                        {"id": "duplicate", "command": "ok"},
                    ]
                },
                "verify": {"checks": []},
            },
            "build.checks[1].id must be unique",
        ),
        (
            {
                "build": {"checks": [{"id": "bad", "command": ""}]},
                "verify": {"checks": []},
            },
            "build.checks[0].command must be non-empty string or list of non-empty strings",
        ),
        (
            {
                "build": {"checks": []},
                "verify": {"checks": [{"id": "bad", "command": "ok", "paths": [""]}]},
            },
            "verify.checks[0].paths must be list of non-empty strings",
        ),
    ],
)
def test_runner_reports_invalid_config_structure_without_traceback(
    tmp_path: Path, capsys, config_data: Any, expected_error: str
) -> None:
    module = load_check_module()
    write_json(tmp_path / ".build-and-verify" / "config.json", config_data)

    result = module.run_build(tmp_path)
    captured = capsys.readouterr()

    assert result == 1
    assert "invalid_config: .build-and-verify/config.json" in captured.err
    assert expected_error in captured.err
    assert "status: failed" in captured.out
    assert "Traceback" not in captured.out + captured.err


def test_runner_selects_check_without_paths_for_any_change() -> None:
    module = load_check_module()
    default_check = {"id": "verify.default", "command": "run-default"}
    src_check = {"id": "verify.src", "command": "run-src", "paths": ["src/**"]}

    assert module._selected_checks([default_check, src_check], ["docs/guide.md"]) == [
        default_check
    ]
    assert module._selected_checks([default_check], []) == []


@pytest.mark.parametrize(
    ("pattern", "changed_file", "expected"),
    [
        ("src/[ab].py", "src/a.py", True),
        ("src/[ab].py", "src/c.py", False),
        ("src/**/*.py", "src/sub/deep.py", True),
        ("docs/", "docs", True),
        ("docs/", "docs/guide.md", True),
        ("/", "docs/guide.md", False),
    ],
)
def test_runner_path_matches_globs_and_trailing_slashes(
    pattern: str, changed_file: str, expected: bool
) -> None:
    module = load_check_module()

    assert module._path_matches(pattern, changed_file) is expected


def test_runner_no_check_returns_success_without_full_fallback(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        verify_checks=[
            {
                "id": "src-only",
                "command": "run-src-only",
                "paths": ["src/**"],
                "inputs": ["src"],
            }
        ],
    )
    monkeypatch.setattr(module, "_changed_files", lambda _root: ["docs/guide.md"], raising=False)
    calls: list[str] = []

    def fake_run(command, cwd, check, text, capture_output, shell=False, timeout=None):
        calls.append(command)
        return make_completed(command)

    result = module.run_verify(tmp_path, runner=fake_run)

    assert result == 0
    assert calls == []
    output = capsys.readouterr().out
    assert "checked:" in output
    assert "full-not-run: true" in output


def test_runner_default_verify_empty_checks_returns_success(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    write_runner_config(tmp_path, verify_checks=[])
    monkeypatch.setattr(module, "_changed_files", lambda _root: [], raising=False)

    result = module.run_verify(tmp_path)

    assert result == 0
    output = capsys.readouterr().out
    assert "checked:" in output
    assert "full-not-run: true" in output
    assert "status: passed" in output


@pytest.mark.parametrize("invalid_input", ["../outside.txt", "/outside.txt"])
def test_runner_rejects_inputs_outside_project(
    tmp_path: Path, monkeypatch, capsys, invalid_input: str
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        verify_checks=[
            {
                "id": "invalid-input",
                "command": "run-invalid",
                "paths": ["src/**"],
                "inputs": [invalid_input],
            }
        ],
    )
    monkeypatch.setattr(module, "_changed_files", lambda _root: ["src/app.py"], raising=False)

    def fake_run(*_args, **_kwargs):
        raise AssertionError("invalid input should stop before running checks")

    result = module.run_verify(tmp_path, runner=fake_run)

    assert result == 1
    assert f"invalid_input_path: {invalid_input}" in capsys.readouterr().err


@pytest.mark.parametrize("invalid_input", ["../outside.txt", "/outside.txt"])
def test_runner_full_verify_rejects_inputs_outside_project(
    tmp_path: Path, monkeypatch, capsys, invalid_input: str
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        verify_checks=[
            {
                "id": "invalid-input",
                "command": "run-invalid",
                "paths": ["src/**"],
                "inputs": [invalid_input],
            }
        ],
    )
    monkeypatch.setattr(module, "_changed_files", lambda _root: ["src/app.py"], raising=False)

    def fake_run(*_args, **_kwargs):
        raise AssertionError("invalid input should stop before running checks")

    result = module.run_verify(tmp_path, runner=fake_run, full=True)

    assert result == 1
    assert f"invalid_input_path: {invalid_input}" in capsys.readouterr().err


def test_runner_build_rejects_inputs_outside_project(
    tmp_path: Path, capsys
) -> None:
    module = load_check_module()
    write_runner_config(
        tmp_path,
        build_checks=[
            {
                "id": "invalid-build-input",
                "command": "run-invalid-build",
                "inputs": ["/outside.txt"],
            }
        ],
    )

    def fake_run(*_args, **_kwargs):
        raise AssertionError("invalid input should stop before running checks")

    result = module.run_build(tmp_path, runner=fake_run)

    assert result == 1
    assert "invalid_input_path: /outside.txt" in capsys.readouterr().err


def test_runner_reports_missing_list_command_without_traceback(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        verify_checks=[
            {
                "id": "missing-command",
                "command": ["missing-build-and-verify-executable"],
                "paths": ["src/**"],
                "inputs": ["src/app.py"],
            }
        ],
    )
    monkeypatch.setattr(module, "_changed_files", lambda _root: ["src/app.py"], raising=False)

    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("missing-build-and-verify-executable")

    result = module.run_verify(tmp_path, runner=fake_run)
    captured = capsys.readouterr()

    assert result == 1
    assert "command_not_found: missing-command: missing-build-and-verify-executable" in captured.err
    assert "Traceback" not in captured.out + captured.err


def test_runner_changed_files_combines_all_git_sources(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_check_module()
    responses = {
        ("diff", "--name-only", "--cached"): ["staged.py"],
        ("diff", "--name-only"): ["unstaged.py"],
        ("ls-files", "--others", "--exclude-standard"): ["untracked.py"],
    }

    def fake_git_names(_root: Path, *args: str) -> list[str]:
        return responses[args]

    monkeypatch.setattr(module, "_git_names", fake_git_names)

    assert module._changed_files(tmp_path) == [
        "staged.py",
        "unstaged.py",
        "untracked.py",
    ]


def test_runner_changed_files_falls_back_to_project_scan_when_git_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("app\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "noise").write_text("ignore\n", encoding="utf-8")
    (tmp_path / ".build-and-verify" / "cache").mkdir(parents=True)
    (tmp_path / ".build-and-verify" / "cache" / "hit.json").write_text(
        "ignore\n", encoding="utf-8"
    )
    monkeypatch.setattr(module, "_git_names", lambda _root, *_args: None)

    assert module._changed_files(tmp_path) == ["src/app.py"]


def test_build_runs_claude_validation_for_marketplace_and_each_plugin(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_plugin(tmp_path, "beta")
    make_marketplace(tmp_path, ["alpha", "beta"])
    make_projection(tmp_path, ["alpha", "beta"])

    calls: list[tuple[list[str], Path]] = []

    def fake_run(command, cwd, text, capture_output, check):
        calls.append((command, cwd))
        return subprocess.CompletedProcess(command, 0, "ok", "")

    errors = module.run_build(tmp_path, runner=fake_run)

    assert errors == []
    assert calls == [
        (["claude", "plugin", "validate", "."], tmp_path),
        (["claude", "plugin", "validate", str(tmp_path / "plugins" / "alpha")], tmp_path),
        (["claude", "plugin", "validate", str(tmp_path / "plugins" / "beta")], tmp_path),
    ]
    assert all(cwd == tmp_path for _command, cwd in calls)
    assert all("--strict" not in command for command, _cwd in calls)


def test_local_plugin_build_main_outputs_stable_status(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_local_build_module()
    calls: list[Path] = []
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    def fake_run_build(root=tmp_path):
        calls.append(root)
        return []

    monkeypatch.setattr(module, "run_build", fake_run_build)

    result = module.main([])

    assert result == 0
    assert calls == [tmp_path]
    assert "status: build checks passed" in capsys.readouterr().out


def test_local_plugin_build_main_uses_explicit_build_argv(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_local_build_module()
    calls: list[Path] = []
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    def fake_run_build(root=tmp_path):
        calls.append(root)
        return []

    monkeypatch.setattr(module, "run_build", fake_run_build)

    result = module.main(["build"])

    assert result == 0
    assert calls == [tmp_path]
    assert "status: build checks passed" in capsys.readouterr().out


def test_local_plugin_build_main_prefers_explicit_argv_over_sys_argv(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_local_build_module()
    calls: list[Path] = []
    monkeypatch.setattr(sys, "argv", ["local_plugin_build.py", "verify"])
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    def fake_run_build(root=tmp_path):
        calls.append(root)
        return []

    monkeypatch.setattr(module, "run_build", fake_run_build)

    result = module.main(["build"])

    assert result == 0
    assert calls == [tmp_path]
    assert "status: build checks passed" in capsys.readouterr().out


def test_local_plugin_build_main_rejects_verify_command(capsys) -> None:
    module = load_local_build_module()

    result = module.main(["verify"])
    captured = capsys.readouterr()

    assert result == 2
    assert "unknown command: verify" in captured.err


def test_build_rejects_marketplace_source_outside_repo(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_marketplace(tmp_path, ["escape"])
    data = json.loads((tmp_path / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    data["plugins"][0]["source"] = "../outside"
    write_json(tmp_path / ".claude-plugin" / "marketplace.json", data)

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("source_outside_repo" in error for error in errors)


def test_build_rejects_codex_dev_marketplace_without_dev_name(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha"])
    make_codex_dev_marketplace(tmp_path, ["alpha"], marketplace_name="test-marketplace", display_name="Test Marketplace")

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("codex_dev_marketplace_name_missing_dev" in error for error in errors)
    assert any("codex_dev_marketplace_display_name_missing_DEV" in error for error in errors)


def test_build_rejects_codex_dev_marketplace_source_outside_repo(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha"])
    data = json.loads((tmp_path / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    data["plugins"][0]["source"]["path"] = "../outside"
    write_json(tmp_path / ".agents" / "plugins" / "marketplace.json", data)

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("codex_dev_source_outside_repo" in error for error in errors)


def test_build_reports_missing_claude_command(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_projection(tmp_path, [])
    make_marketplace(tmp_path, [])

    def missing_claude(*args, **kwargs):
        raise FileNotFoundError("claude")

    errors = module.run_build(tmp_path, runner=missing_claude)

    assert any("missing_command: claude" in error for error in errors)


def test_build_reports_invalid_marketplace_entry(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_projection(tmp_path, [])
    write_json(
        tmp_path / ".claude-plugin" / "marketplace.json",
        {
            "name": "test-marketplace",
            "owner": {"name": "Test"},
            "plugins": ["not-a-plugin"],
        },
    )

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("invalid_marketplace_entry" in error for error in errors)


def test_build_reports_duplicate_marketplace_plugin_name(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha", "alpha"])
    make_projection(tmp_path, ["alpha"])

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("duplicate_marketplace_plugin: alpha" in error for error in errors)


def test_build_reports_missing_pyyaml_dependency(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_marketplace(tmp_path, [])
    make_projection(tmp_path, [])
    module.yaml = None

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("missing_dependency: PyYAML" in error for error in errors)


def test_build_reports_manifest_name_mismatch(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha"])
    write_json(
        tmp_path / "plugins" / "alpha" / ".claude-plugin" / "plugin.json",
        {
            "name": "wrong",
            "version": "0.1.0",
            "description": "wrong plugin",
            "skills": "./skills",
        },
    )

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("claude_manifest_name_mismatch" in error for error in errors)


def test_build_reports_missing_codex_manifest_path(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha"])
    codex_manifest = tmp_path / "plugins" / "alpha" / ".codex-plugin" / "plugin.json"
    data = json.loads(codex_manifest.read_text(encoding="utf-8"))
    data["hooks"] = "./missing-hooks"
    write_json(codex_manifest, data)

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("missing_manifest_path" in error for error in errors)


def test_build_reports_projection_plugin_mismatch(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha", "missing"])

    errors = module.run_build(tmp_path, runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""))

    assert any("projection_plugins_mismatch" in error for error in errors)


def test_build_reports_projection_missing_marketplace_plugin(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_plugin(tmp_path, "beta")
    make_marketplace(tmp_path, ["alpha", "beta"])
    make_projection(tmp_path, ["alpha"])

    errors = module.run_build(tmp_path, runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""))

    assert any("projection_plugins_mismatch" in error for error in errors)


def test_build_reports_duplicate_projection_plugin(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha", "alpha"])

    errors = module.run_build(tmp_path, runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""))

    assert any("duplicate_projection_plugin" in error for error in errors)


def guard_profile_template_dirs(root: Path) -> tuple[Path, Path]:
    left = root / "plugins" / "agent-guard" / "assets" / "templates" / "guard-profile"
    right = (
        root
        / "plugins"
        / "agent-guard"
        / "skills"
        / "agent-guard"
        / "assets"
        / "templates"
        / "guard-profile"
    )
    return left, right


def make_guard_profile_mirrors(root: Path, content: str = "schema_version: guard-profile/v1\n") -> None:
    left, right = guard_profile_template_dirs(root)
    template_files = [
        ".gitkeep",
        "confirmed-notes.yaml",
        "minimal/GUARD-MANIFEST.yaml",
        "minimal/activation-model.yaml",
        "minimal/artifacts.yaml",
        "minimal/brief-template.md",
        "minimal/execution-model.yaml",
        "minimal/global-command-guards.yaml",
        "minimal/guard-points.yaml",
        "minimal/observation-model.yaml",
        "minimal/state-machine.yaml",
        "minimal/target-model.yaml",
        "minimal/validation-plan.md",
        "comet-review-gate/GUARD-MANIFEST.yaml",
        "comet-review-gate/activation-model.yaml",
        "comet-review-gate/artifacts.yaml",
        "comet-review-gate/brief-template.md",
        "comet-review-gate/execution-model.yaml",
        "comet-review-gate/global-command-guards.yaml",
        "comet-review-gate/guard-points.yaml",
        "comet-review-gate/observation-model.yaml",
        "comet-review-gate/state-machine.yaml",
        "comet-review-gate/target-model.yaml",
        "comet-review-gate/validation-plan.md",
    ]
    for template_file in template_files:
        file_content = "" if template_file == ".gitkeep" else f"# {template_file}\n{content}"
        for base in (left, right):
            path = base / template_file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(file_content, encoding="utf-8")


def test_build_accepts_matching_guard_profile_mirrors(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_guard_profile_mirrors(tmp_path)

    errors = module.check_guard_profile_template_mirrors(tmp_path)

    assert errors == []


def test_build_reports_guard_profile_mirror_mismatch(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_guard_profile_mirrors(tmp_path)
    _left, right = guard_profile_template_dirs(tmp_path)
    right_file = right / "comet-review-gate" / "GUARD-MANIFEST.yaml"
    right_file.write_text("schema_version: changed\n", encoding="utf-8")

    errors = module.check_guard_profile_template_mirrors(tmp_path)

    assert any("guard_profile_template_mismatch" in error for error in errors)


def test_build_reports_guard_profile_mirror_file_set_mismatch(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_guard_profile_mirrors(tmp_path)
    _left, right = guard_profile_template_dirs(tmp_path)
    (right / "EXTRA.yaml").write_text("extra: true\n", encoding="utf-8")

    errors = module.check_guard_profile_template_mirrors(tmp_path)

    assert any("guard_profile_template_files_mismatch" in error for error in errors)


def test_run_build_reports_guard_profile_mirror_mismatch(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "agent-guard")
    make_marketplace(tmp_path, ["agent-guard"])
    make_projection(tmp_path, ["agent-guard"])
    make_guard_profile_mirrors(tmp_path)
    _left, right = guard_profile_template_dirs(tmp_path)
    (right / "comet-review-gate" / "GUARD-MANIFEST.yaml").write_text("schema_version: changed\n", encoding="utf-8")

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("guard_profile_template_mismatch" in error for error in errors)


def test_run_build_reports_guard_profile_mirror_file_set_mismatch(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "agent-guard")
    make_marketplace(tmp_path, ["agent-guard"])
    make_projection(tmp_path, ["agent-guard"])
    make_guard_profile_mirrors(tmp_path)
    _left, right = guard_profile_template_dirs(tmp_path)
    (right / "EXTRA.yaml").write_text("extra: true\n", encoding="utf-8")

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("guard_profile_template_files_mismatch" in error for error in errors)


def test_comet_config_does_not_duplicate_guard_commands() -> None:
    import yaml

    data = yaml.safe_load((REPO_ROOT / ".comet" / "config.yaml").read_text(encoding="utf-8"))

    assert "build_command" not in data
    assert "verify_command" not in data


def test_root_comet_yaml_points_to_check_commands_for_guard() -> None:
    import yaml

    data = yaml.safe_load((REPO_ROOT / ".comet.yaml").read_text(encoding="utf-8"))
    script = REPO_ROOT / "plugins" / "build-and-verify" / "skills" / "build-and-verify" / "scripts" / "build_and_verify.py"

    assert (
        data["build_command"]
        == "python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py build --project ."
    )
    assert (
        data["verify_command"]
        == "python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project ."
    )
    assert script.is_file()


def test_active_automation_does_not_reference_removed_check_entrypoint() -> None:
    active_files = [
        REPO_ROOT / ".github" / "workflows" / "release.yml",
        REPO_ROOT / ".comet.yaml",
        REPO_ROOT / ".comet" / "config.yaml",
        REPO_ROOT / ".build-and-verify" / "config.json",
    ]

    for path in active_files:
        text = path.read_text(encoding="utf-8").replace("\\", "/")
        assert "scripts/check.py" not in text


def test_root_verify_checks_are_split_by_repo_domains() -> None:
    data = json.loads((REPO_ROOT / ".build-and-verify" / "config.json").read_text(encoding="utf-8"))
    checks = data["verify"]["checks"]
    check_by_id = {check["id"]: check for check in checks}

    assert [check["id"] for check in checks] == [
        "verify.local-build-contract",
        "verify.agent-guard",
        "verify.release-flow",
        "verify.pr-flow",
        "verify.cross-agent-review",
        "verify.build-and-verify",
        "verify.openspec",
    ]
    assert "pytest.full" not in check_by_id

    local_build_contract = check_by_id["verify.local-build-contract"]
    assert ".comet/config.yaml" in local_build_contract["paths"]
    assert ".comet/config.yaml" in local_build_contract["inputs"]
    assert ".comet.yaml" in local_build_contract["paths"]
    assert ".comet.yaml" in local_build_contract["inputs"]
    assert "docs/agent-guard/**" in local_build_contract["paths"]
    assert "docs/agent-guard" in local_build_contract["inputs"]
    assert "." not in local_build_contract["inputs"]

    openspec = check_by_id["verify.openspec"]
    assert openspec["command"] == "openspec validate --all --strict --no-interactive"
    assert openspec["paths"] == ["openspec/**", "docs/superpowers/**"]
    assert openspec["inputs"] == ["openspec", "docs/superpowers"]
