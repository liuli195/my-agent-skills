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
PLUGIN_ROOT = REPO_ROOT / "plugins" / "test-framework"
CODEX_REPO_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
RELEASE_FLOW_PROJECTION = REPO_ROOT / ".release-flow" / "projection.yaml"
RELEASE_FLOW_CONFIG = REPO_ROOT / ".release-flow" / "config.yaml"
RELEASE_FLOW_SCRIPT = REPO_ROOT / "plugins" / "release-flow" / "skills" / "release-flow" / "scripts" / "release_flow.py"
TEST_FRAMEWORK_SCRIPT = (
    PLUGIN_ROOT / "skills" / "test-framework" / "scripts" / "test_framework.py"
)

PLUGIN_NAME = "test-framework"
PLUGIN_VERSION = "0.1.11"
PLUGIN_DESCRIPTION = "Test Framework Plugin（测试框架插件）"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_test_framework(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TEST_FRAMEWORK_SCRIPT), *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def load_test_framework_module():
    spec = importlib.util.spec_from_file_location(
        "test_framework_entrypoint", TEST_FRAMEWORK_SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_check(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    module = load_test_framework_module()
    argv = [*args, "--project", str(project)]
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        returncode = int(module.main(argv))
    return subprocess.CompletedProcess(
        args=[str(TEST_FRAMEWORK_SCRIPT), *argv],
        returncode=returncode,
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
    )


def git(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )


def command_that_logs(label: str, log_name: str = "run.log") -> list[str]:
    code = (
        "from pathlib import Path\n"
        f"with Path({log_name!r}).open('a', encoding='utf-8') as file:\n"
        f"    file.write({label!r} + '\\n')\n"
    )
    return [sys.executable, "-c", code]


def test_test_framework_main_returns_error_without_command(capsys) -> None:
    module = load_test_framework_module()

    result = module.main([])
    captured = capsys.readouterr()

    assert result == 2
    assert "usage:" in captured.err


def command_that_fails_once(label: str) -> list[str]:
    code = (
        "from pathlib import Path\n"
        "marker = Path('fail-once.marker')\n"
        "Path('run.log').open('a', encoding='utf-8').write(" + repr(label) + " + '\\n')\n"
        "if marker.exists():\n"
        "    raise SystemExit(0)\n"
        "marker.write_text('failed', encoding='utf-8')\n"
        "raise SystemExit(7)\n"
    )
    return [sys.executable, "-c", code]


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


def write_release_projection_project(project: Path) -> Path:
    release_flow_dir = project / ".release-flow"
    release_flow_dir.mkdir(parents=True)
    (project / ".agents" / "plugins").mkdir(parents=True)
    (project / ".claude-plugin").mkdir(parents=True)

    (release_flow_dir / "config.yaml").write_text(
        RELEASE_FLOW_CONFIG.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (release_flow_dir / "projection.yaml").write_text(
        RELEASE_FLOW_PROJECTION.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (project / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "placeholder",
                "owner": {"name": "placeholder"},
                "plugins": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    vars_file = project / "release-vars.json"
    vars_file.write_text(
        json.dumps(
            {
                "CODEX_MARKETPLACE_CATALOG_NAME": "my-agent-skills-marketplace",
                "CODEX_MARKETPLACE_DISPLAY_NAME": "My Agent Skills Marketplace",
                "CLAUDE_MARKETPLACE_CATALOG_NAME": "my-agent-skills-marketplace",
                "CLAUDE_MARKETPLACE_OWNER_NAME": "My Agent Skills Marketplace",
                "RELEASE_FLOW_PLUGIN_REPOSITORY": "liuli/my-agent-skills",
                "RELEASE_FLOW_PLUGIN_REF": "main",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return vars_file


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
    script_path = skill_root / PLUGIN_NAME / "scripts" / "test_framework.py"
    skill_dirs = [path.name for path in skill_root.iterdir() if path.is_dir()]
    skill_text = (skill_root / PLUGIN_NAME / "SKILL.md").read_text(encoding="utf-8")
    front_matter = skill_text.split("---", 2)[1]

    assert skill_dirs == [PLUGIN_NAME]
    assert script_path.is_file()
    assert skill_text.startswith("---\n")
    assert f"name: {PLUGIN_NAME}" in front_matter
    assert "只初始化测试框架配置产物" in skill_text
    assert "不安装依赖" in skill_text
    assert "不写用户级配置" in skill_text
    assert "不配置 CI（持续集成）" in skill_text
    assert "不内置仓库业务逻辑" in skill_text
    assert "不向目标仓库复制 runner（运行器）" in skill_text
    assert "scripts/test_framework.py init" in skill_text
    assert "scripts/test_framework.py build" in skill_text
    assert "scripts/test_framework.py verify" in skill_text
    assert "timeoutSeconds" in skill_text
    assert "pytest-xdist" in skill_text


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
        [sys.executable, str(RELEASE_FLOW_SCRIPT), "validate", "--project", "."],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_test_framework_release_projection_projects_real_catalogs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    vars_file = write_release_projection_project(project)

    result = subprocess.run(
        [
            sys.executable,
            str(RELEASE_FLOW_SCRIPT),
            "project",
            "--project",
            str(project),
            "--vars-file",
            str(vars_file),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: projected" in result.stdout

    codex_catalog = read_json(project / ".agents" / "plugins" / "marketplace.json")
    codex_names = plugin_names(codex_catalog)
    assert plugin_after(codex_names, "pr-flow") == PLUGIN_NAME
    assert codex_catalog["plugins"][codex_names.index(PLUGIN_NAME)] == {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": "./plugins/test-framework"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools",
    }


def test_test_framework_init_writes_config_gitignore_and_cache(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run_test_framework("init", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: initialized" in result.stdout
    assert (project / ".test-framework" / "config.json").is_file()
    assert (project / ".test-framework" / ".gitignore").is_file()
    assert (project / ".test-framework" / "cache").is_dir()
    assert not (project / "scripts" / "check.py").exists()
    assert read_json(project / ".test-framework" / "config.json") == {
        "version": 1,
        "build": {"checks": []},
        "verify": {"checks": []},
    }
    assert (project / ".test-framework" / ".gitignore").read_text(encoding="utf-8") == "/cache/\n/runs/\n"


@pytest.mark.parametrize(
    "existing",
    [
        Path(".test-framework/config.json"),
        Path(".test-framework/.gitignore"),
    ],
)
def test_test_framework_init_refuses_existing_files_before_writes(
    tmp_path: Path, existing: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    existing_path = project / existing
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text("keep me\n", encoding="utf-8")

    result = run_test_framework("init", "--project", str(project))

    assert result.returncode != 0
    assert f"existing_file: {existing.as_posix()}" in result.stderr
    assert existing_path.read_text(encoding="utf-8") == "keep me\n"
    generated_files = [
        Path(".test-framework/config.json"),
        Path(".test-framework/.gitignore"),
    ]
    for relative in generated_files:
        path = project / relative
        if path != existing_path:
            assert not path.exists()
    assert not (project / ".test-framework" / "cache").exists()


def test_test_framework_runner_build_verify_and_full_verify(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "docs").mkdir()
    (project / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
    (project / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {
                "checks": [
                    {"id": "build-main", "command": command_that_logs("build-main")}
                ]
            },
            "verify": {
                "checks": [
                    {
                        "id": "verify-src",
                        "command": command_that_logs("verify-src"),
                        "paths": ["src/**"],
                        "inputs": ["src"],
                    },
                    {
                        "id": "verify-docs",
                        "command": command_that_logs("verify-docs"),
                        "paths": ["docs/**"],
                        "inputs": ["docs"],
                    },
                ]
            },
        },
    )

    build = run_check(project, "build")
    verify = run_check(project, "verify")
    full_verify = run_check(project, "verify", "--full")

    assert build.returncode == 0, build.stdout + build.stderr
    assert "checked: build-main" in build.stdout
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "checked: verify-src, verify-docs" in verify.stdout
    assert "full-not-run: true" in verify.stdout
    assert full_verify.returncode == 0, full_verify.stdout + full_verify.stderr
    assert "checked: verify-src, verify-docs" in full_verify.stdout
    assert "full-not-run: false" in full_verify.stdout
    assert "cache-hit" not in full_verify.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "build-main",
        "verify-src",
        "verify-docs",
        "verify-src",
        "verify-docs",
    ]


def test_test_framework_runner_full_verify_allows_empty_checks(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0

    result = run_check(project, "verify", "--full")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "checked:" in result.stdout
    assert "full-not-run: false" in result.stdout
    assert "status: passed" in result.stdout


def test_test_framework_runner_full_verify_runs_parallel_checks_concurrently(tmp_path: Path, capsys) -> None:
    import threading
    import time

    module = load_test_framework_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "parallel": True, "inputs": []},
                    {"id": "parallel-b", "command": ["parallel-b"], "parallel": True, "inputs": []},
                    {"id": "serial-c", "command": ["serial-c"], "parallel": False, "inputs": []},
                ]
            },
        },
    )
    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_runner(command, **_kwargs):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.2)
        with lock:
            active -= 1
        return subprocess.CompletedProcess(command, 0, stdout=f"{command[0]}\n", stderr="")

    result = module._runner().run_verify(project, runner=fake_runner, full=True)
    captured = capsys.readouterr()

    assert result == 0
    assert max_active > 1
    assert "serial-c" in captured.out
    assert "duration: parallel-a seconds=" in captured.out
    assert "duration: parallel-b seconds=" in captured.out
    assert "duration: serial-c seconds=" in captured.out
    assert "full-not-run: false" in captured.out


def test_test_framework_runner_full_verify_honors_max_parallel_checks(tmp_path: Path) -> None:
    import threading
    import time

    module = load_test_framework_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "maxParallel": 2,
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "parallel": True, "inputs": []},
                    {"id": "parallel-b", "command": ["parallel-b"], "parallel": True, "inputs": []},
                    {"id": "parallel-c", "command": ["parallel-c"], "parallel": True, "inputs": []},
                ],
            },
        },
    )
    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_runner(command, **_kwargs):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.1)
        with lock:
            active -= 1
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = module._runner().run_verify(project, runner=fake_runner, full=True)

    assert result == 0
    assert max_active == 2


def test_test_framework_runner_full_verify_zero_max_parallel_means_unlimited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    import time

    module = load_test_framework_module()
    monkeypatch.setattr(module._runner().os, "cpu_count", lambda: 2)
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "maxParallel": 0,
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "parallel": True, "inputs": []},
                    {"id": "parallel-b", "command": ["parallel-b"], "parallel": True, "inputs": []},
                    {"id": "parallel-c", "command": ["parallel-c"], "parallel": True, "inputs": []},
                ],
            },
        },
    )
    active = 0
    max_active = 0
    lock = threading.Lock()
    barrier = threading.Barrier(3)

    def fake_runner(command, **_kwargs):
        nonlocal active, max_active
        try:
            with lock:
                active += 1
                max_active = max(max_active, active)
            barrier.wait(timeout=2)
        finally:
            with lock:
                active -= 1
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = module._runner().run_verify(project, runner=fake_runner, full=True)

    assert result == 0
    assert max_active == 3


def test_test_framework_runner_rejects_negative_max_parallel(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "maxParallel": -1,
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "parallel": True, "inputs": []},
                ],
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 1
    assert "verify.maxParallel must be non-negative integer" in result.stderr
    assert "status: failed" in result.stdout


def test_test_framework_runner_reports_missing_xdist_before_running_pytest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    module = load_test_framework_module()
    runner = module._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "pytest-parallel",
                        "command": "python -m pytest -n 8 tests",
                        "parallel": False,
                        "inputs": [],
                    },
                ],
            },
        },
    )
    calls = []

    def fake_runner(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runner.importlib.util, "find_spec", lambda _name: None)

    result = runner.run_verify(project, runner=fake_runner, full=True)
    captured = capsys.readouterr()

    assert result == 1
    assert calls == []
    assert "missing_dependency: pytest-parallel: pytest-xdist is required" in captured.err
    assert "status: failed" in captured.out


def test_test_framework_runner_full_verify_aggregates_missing_xdist_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    module = load_test_framework_module()
    runner = module._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "pytest-a",
                        "command": "python -m pytest -n 8 tests/a",
                        "parallel": True,
                        "inputs": [],
                    },
                    {
                        "id": "pytest-b",
                        "command": [sys.executable, "-m", "pytest", "-n", "8", "tests/b"],
                        "parallel": True,
                        "inputs": [],
                    },
                ],
            },
        },
    )
    calls = []

    def fake_runner(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runner.importlib.util, "find_spec", lambda _name: None)

    result = runner.run_verify(project, runner=fake_runner, full=True)
    captured = capsys.readouterr()

    assert result == 1
    assert calls == []
    assert "missing_dependency: pytest-a: pytest-xdist is required" in captured.err
    assert "missing_dependency: pytest-b: pytest-xdist is required" in captured.err
    assert "failed: pytest-a, pytest-b" in captured.out
    assert "status: failed" in captured.out


@pytest.mark.parametrize("timeout_seconds", [0, -1, True])
def test_test_framework_runner_rejects_invalid_check_timeout_seconds(
    tmp_path: Path, timeout_seconds: object
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "invalid-timeout",
                        "command": command_that_logs("invalid-timeout"),
                        "timeoutSeconds": timeout_seconds,
                        "parallel": False,
                        "inputs": [],
                    },
                ],
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 1
    assert "invalid_timeoutSeconds: invalid-timeout" in result.stderr
    assert "status: failed" in result.stdout


def test_test_framework_runner_full_verify_reports_parallel_check_timeout(
    tmp_path: Path, capsys
) -> None:
    module = load_test_framework_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "timeoutSeconds": 1,
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "parallel": True, "inputs": []},
                ],
            },
        },
    )

    def fake_runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))

    result = module._runner().run_verify(project, runner=fake_runner, full=True)
    captured = capsys.readouterr()

    assert result == 1
    assert "check_timeout: parallel-a exceeded 1s" in captured.err
    assert "failed: parallel-a" in captured.out
    assert "status: failed" in captured.out


def test_test_framework_runner_full_verify_reports_parallel_check_exception(
    tmp_path: Path, capsys
) -> None:
    module = load_test_framework_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "parallel": True, "inputs": []},
                ],
            },
        },
    )

    def fake_runner(_command, **_kwargs):
        raise RuntimeError("boom")

    result = module._runner().run_verify(project, runner=fake_runner, full=True)
    captured = capsys.readouterr()

    assert result == 1
    assert "parallel_check_exception: parallel-a: RuntimeError: boom" in captured.err
    assert "failed: parallel-a" in captured.out
    assert "status: failed" in captured.out


def test_test_framework_runner_full_verify_reports_keyboard_interrupt_from_parallel_check(
    tmp_path: Path, capsys
) -> None:
    module = load_test_framework_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "parallel": True, "inputs": []},
                ],
            },
        },
    )

    def fake_runner(_command, **_kwargs):
        raise KeyboardInterrupt("worker interrupted")

    result = module._runner().run_verify(project, runner=fake_runner, full=True)
    captured = capsys.readouterr()

    assert result == 1
    assert "parallel_check_interrupted: parallel-a: KeyboardInterrupt: worker interrupted" in captured.err
    assert "failed: parallel-a" in captured.out
    assert "status: failed" in captured.out


def test_test_framework_runner_full_verify_skips_serial_checks_after_parallel_interrupt(
    tmp_path: Path, capsys
) -> None:
    module = load_test_framework_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "parallel": True, "inputs": []},
                    {"id": "serial-after-interrupt", "command": ["serial-after-interrupt"], "parallel": False, "inputs": []},
                ],
            },
        },
    )
    calls = []

    def fake_runner(command, **_kwargs):
        calls.append(command)
        if command == ["parallel-a"]:
            raise KeyboardInterrupt("worker interrupted")
        return subprocess.CompletedProcess(command, 0, stdout="serial ran\n", stderr="")

    result = module._runner().run_verify(project, runner=fake_runner, full=True)
    captured = capsys.readouterr()

    assert result == 1
    assert calls == [["parallel-a"]]
    assert "serial ran" not in captured.out
    assert "failed: parallel-a" in captured.out
    assert "checked: parallel-a, serial-after-interrupt" in captured.out
    assert "status: failed" in captured.out


def test_test_framework_runner_full_verify_reports_serial_failure_after_parallel_pass(
    tmp_path: Path, capsys
) -> None:
    module = load_test_framework_module()
    project = tmp_path / "project"
    project.mkdir()
    cache_dir = project / ".test-framework" / "cache"
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-pass", "command": ["parallel-pass"], "parallel": True, "inputs": []},
                    {"id": "serial-fail", "command": ["serial-fail"], "parallel": False, "inputs": []},
                ],
            },
        },
    )

    def fake_runner(command, **_kwargs):
        if command == ["serial-fail"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="serial failed\n")
        return subprocess.CompletedProcess(command, 0, stdout="parallel passed\n", stderr="")

    result = module._runner().run_verify(project, runner=fake_runner, full=True)
    captured = capsys.readouterr()
    cache_files = list(cache_dir.glob("*.json"))

    assert result == 1
    assert "parallel passed" in captured.out
    assert "serial failed" in captured.err
    assert "failed: serial-fail" in captured.out
    assert "checked: parallel-pass, serial-fail" in captured.out
    assert "status: failed" in captured.out
    assert len(cache_files) == 1
    assert read_json(cache_files[0]) == {"status": "passed", "id": "parallel-pass"}


def test_test_framework_cache_store_writes_temp_file_before_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_test_framework_module()
    runner = module._runner()
    project = tmp_path / "project"
    project.mkdir()
    cache_dir = project / ".test-framework" / "cache"
    path_type = type(project)
    original_write_text = path_type.write_text

    def tracking_write_text(self, *args, **kwargs):
        assert self.name != "cache-key.json"
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "write_text", tracking_write_text)

    runner._cache_store(project, "cache-key", {"id": "cache-check"})

    assert read_json(cache_dir / "cache-key.json") == {"status": "passed", "id": "cache-check"}


def test_test_framework_runner_reads_changed_files_with_single_git_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_test_framework_module()
    runner = module._runner()
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if command == ["git", "diff", "--name-only", "--cached"]:
            return subprocess.CompletedProcess(command, 0, stdout="staged.txt\n", stderr="")
        if command == ["git", "diff", "--name-only"]:
            return subprocess.CompletedProcess(command, 0, stdout="unstaged.txt\n", stderr="")
        if command == ["git", "ls-files", "--others", "--exclude-standard"]:
            return subprocess.CompletedProcess(command, 0, stdout="untracked.txt\n", stderr="")
        if command == ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="M  staged.txt\0 M unstaged.txt\0?? untracked.txt\0",
                stderr="",
            )
        raise AssertionError(command)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    changed = runner._changed_files(tmp_path)

    assert changed == ["staged.txt", "unstaged.txt", "untracked.txt"]
    assert calls == [["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]]


def test_test_framework_runner_reads_git_status_rename_and_copy_destinations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_test_framework_module()
    runner = module._runner()

    def fake_run(command, **_kwargs):
        if command == ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="R  renamed.txt\0old-name.txt\0C  copied.txt\0source.txt\0",
                stderr="",
            )
        raise AssertionError(command)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner._git_status_names(tmp_path) == ["renamed.txt", "copied.txt"]


def test_test_framework_user_level_skill_path_runs_verify_without_git(
    tmp_path: Path,
) -> None:
    user_skill = tmp_path / "user-skills" / "test-framework"
    shutil.copytree(PLUGIN_ROOT / "skills" / "test-framework", user_skill)
    script = user_skill / "scripts" / "test_framework.py"
    project = tmp_path / "project"
    project.mkdir()

    init = subprocess.run(
        [sys.executable, str(script), "init", "--project", str(project)],
        cwd=tmp_path,
        check=False,
        text=True,
        capture_output=True,
    )
    assert init.returncode == 0, init.stdout + init.stderr
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "verify-src",
                        "command": command_that_logs("verify-src"),
                        "paths": ["src/**"],
                        "inputs": ["src"],
                    }
                ]
            },
        },
    )

    verify = subprocess.run(
        [sys.executable, str(script), "verify", "--project", str(project)],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )

    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "checked: verify-src" in verify.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "verify-src"
    ]


def test_test_framework_non_git_project_uses_filesystem_scan(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "docs").mkdir()
    (project / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    (project / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "verify-src",
                        "command": command_that_logs("verify-src"),
                        "paths": ["src/**"],
                        "inputs": ["src"],
                    },
                    {
                        "id": "verify-docs",
                        "command": command_that_logs("verify-docs"),
                        "paths": ["docs/**"],
                        "inputs": ["docs"],
                    },
                ]
            },
        },
    )

    verify = run_check(project, "verify")

    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "checked: verify-src, verify-docs" in verify.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "verify-src",
        "verify-docs",
    ]


def test_test_framework_runner_uses_passed_result_cache(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "cached.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "cache-check",
                        "command": command_that_logs("cache-check"),
                        "paths": ["src/cached.py"],
                        "inputs": ["src/cached.py"],
                    }
                ]
            },
        },
    )

    first = run_check(project, "verify")
    cache_files = list((project / ".test-framework" / "cache").glob("*.json"))
    second = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert len(cache_files) == 1
    assert read_json(cache_files[0]) == {"status": "passed", "id": "cache-check"}
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: cache-check" in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "cache-check"
    ]


def test_test_framework_runner_full_verify_ignores_existing_default_cache(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "cached.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "full-ignores-fast-cache",
                        "command": command_that_logs("full-ignores-fast-cache"),
                        "paths": ["src/cached.py"],
                        "inputs": ["src/cached.py"],
                    }
                ]
            },
        },
    )

    default = run_check(project, "verify")
    cached_default = run_check(project, "verify")
    full = run_check(project, "verify", "--full")

    assert default.returncode == 0, default.stdout + default.stderr
    assert cached_default.returncode == 0, cached_default.stdout + cached_default.stderr
    assert full.returncode == 0, full.stdout + full.stderr
    assert "cache-hit: full-ignores-fast-cache" in cached_default.stdout
    assert "cache-hit:" not in full.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "full-ignores-fast-cache",
        "full-ignores-fast-cache",
    ]


def test_test_framework_runner_full_verify_refreshes_cache_for_default_verify(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "cached.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "full-primes-cache",
                        "command": command_that_logs("full-primes-cache"),
                        "paths": ["src/cached.py"],
                        "inputs": ["src/cached.py"],
                    }
                ]
            },
        },
    )

    full = run_check(project, "verify", "--full")
    default = run_check(project, "verify")

    assert full.returncode == 0, full.stdout + full.stderr
    assert default.returncode == 0, default.stdout + default.stderr
    assert "cache-hit:" not in full.stdout
    assert "cache-hit: full-primes-cache" in default.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "full-primes-cache"
    ]


def test_test_framework_runner_cache_misses_when_input_is_deleted(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    assert git(project, "init").returncode == 0
    assert git(project, "config", "user.email", "test@example.invalid").returncode == 0
    assert git(project, "config", "user.name", "Test User").returncode == 0
    (project / "src").mkdir()
    input_file = project / "src" / "input.txt"
    input_file.write_text("base\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "deleted-input",
                        "command": command_that_logs("deleted-input"),
                        "inputs": ["src/input.txt"],
                    }
                ]
            },
        },
    )
    assert git(project, "add", ".").returncode == 0
    assert git(project, "commit", "-m", "initial").returncode == 0

    input_file.write_text("changed\n", encoding="utf-8")
    first = run_check(project, "verify")
    input_file.unlink()
    second = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit:" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "deleted-input",
        "deleted-input",
    ]


def test_test_framework_runner_default_cache_key_tracks_glob_path_contents(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    assert git(project, "init").returncode == 0
    (project / "src").mkdir()
    app_path = project / "src" / "app.txt"
    app_path.write_text("first\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "glob-default-inputs",
                        "command": command_that_logs("glob-default-inputs"),
                        "paths": ["src/**"],
                    }
                ]
            },
        },
    )

    first = run_check(project, "verify")
    app_path.write_text("second\n", encoding="utf-8")
    second = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: glob-default-inputs" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "glob-default-inputs",
        "glob-default-inputs",
    ]


def test_test_framework_runner_default_check_cache_key_tracks_changed_files(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    assert git(project, "init").returncode == 0
    assert git(project, "config", "user.email", "test@example.invalid").returncode == 0
    assert git(project, "config", "user.name", "Test User").returncode == 0
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "default-check",
                        "command": command_that_logs("default-check"),
                    }
                ]
            },
        },
    )
    assert git(project, "add", ".").returncode == 0
    assert git(project, "commit", "-m", "initial").returncode == 0

    (project / "a.txt").write_text("a\n", encoding="utf-8")
    first = run_check(project, "verify")
    (project / "b.txt").write_text("b\n", encoding="utf-8")
    second = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: default-check" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "default-check",
        "default-check",
    ]


def test_test_framework_pathless_check_skips_clean_git_worktree(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    assert git(project, "init").returncode == 0
    assert git(project, "config", "user.email", "test@example.invalid").returncode == 0
    assert git(project, "config", "user.name", "Test User").returncode == 0
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "pathless",
                        "command": command_that_logs("pathless"),
                    }
                ]
            },
        },
    )
    assert git(project, "add", ".").returncode == 0
    assert git(project, "commit", "-m", "initial").returncode == 0

    verify = run_check(project, "verify")

    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "checked:" in verify.stdout
    assert "checked: pathless" not in verify.stdout
    assert not (project / "run.log").exists()


def test_test_framework_runner_default_check_cache_key_tracks_dirty_file_contents(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    assert git(project, "init").returncode == 0
    assert git(project, "config", "user.email", "test@example.invalid").returncode == 0
    assert git(project, "config", "user.name", "Test User").returncode == 0
    dirty_file = project / "dirty.txt"
    dirty_file.write_text("base\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "default-dirty-check",
                        "command": command_that_logs("default-dirty-check"),
                    }
                ]
            },
        },
    )
    assert git(project, "add", ".").returncode == 0
    assert git(project, "commit", "-m", "initial").returncode == 0

    dirty_file.write_text("first\n", encoding="utf-8")
    first = run_check(project, "verify")
    dirty_file.write_text("second\n", encoding="utf-8")
    second = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: default-dirty-check" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "default-dirty-check",
        "default-dirty-check",
    ]


def test_test_framework_runner_reports_missing_list_command_without_traceback(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "missing-command",
                        "command": ["missing-test-framework-executable"],
                        "paths": ["src/app.txt"],
                        "inputs": ["src/app.txt"],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify")
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "command_not_found: missing-command" in output
    assert "Traceback" not in output


def test_test_framework_runner_verify_reports_missing_config_without_traceback(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / ".test-framework" / "config.json").unlink()

    result = run_check(project, "verify")
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "missing_config: .test-framework/config.json" in output
    assert "status: failed" in result.stdout
    assert "Traceback" not in output


@pytest.mark.parametrize(
    "invalid_input",
    [
        "../outside.txt",
        "{outside}",
    ],
)
def test_test_framework_runner_rejects_inputs_outside_project(
    tmp_path: Path, invalid_input: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "invalid-input",
                        "command": command_that_logs("invalid-input"),
                        "paths": ["src/**"],
                        "inputs": [invalid_input.format(outside=outside)],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify")

    assert result.returncode != 0
    assert "invalid_input_path" in result.stderr
    assert not (project / "run.log").exists()


def test_test_framework_runner_full_verify_rejects_inputs_outside_project(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "invalid-input",
                        "command": command_that_logs("invalid-input"),
                        "paths": ["src/**"],
                        "inputs": ["../outside.txt"],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode != 0
    assert "invalid_input_path: ../outside.txt" in result.stderr
    assert not (project / "run.log").exists()


@pytest.mark.parametrize("mutation", ["check_id", "command", "inputs", "config"])
def test_test_framework_runner_cache_key_changes_with_check_contract(
    tmp_path: Path, mutation: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "inputs").mkdir()
    (project / "src" / "sample.py").write_text("changed\n", encoding="utf-8")
    (project / "inputs" / "v1.txt").write_text("v1\n", encoding="utf-8")
    (project / "inputs" / "v2.txt").write_text("v2\n", encoding="utf-8")

    def config(
        *,
        version: int = 1,
        check_id: str = "cache-contract",
        command: list[str] | None = None,
        inputs: list[str] | None = None,
    ) -> dict:
        return {
            "version": version,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": check_id,
                        "command": command or command_that_logs("base"),
                        "paths": ["src/**"],
                        "inputs": inputs or ["inputs/v1.txt"],
                    }
                ]
            },
        }

    write_json(project / ".test-framework" / "config.json", config())
    first = run_check(project, "verify")
    cached = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    cache_files = list((project / ".test-framework" / "cache").glob("*.json"))
    assert len(cache_files) == 1
    assert read_json(cache_files[0])["status"] == "passed"
    assert cached.returncode == 0, cached.stdout + cached.stderr
    assert "cache-hit: cache-contract" in cached.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == ["base"]

    changed_config = config()
    expected_checked = "cache-contract"
    expected_log = "base"
    if mutation == "check_id":
        changed_config = config(check_id="cache-contract-renamed")
        expected_checked = "cache-contract-renamed"
    elif mutation == "command":
        changed_config = config(command=command_that_logs("changed-command"))
        expected_log = "changed-command"
    elif mutation == "inputs":
        changed_config = config(inputs=["inputs/v2.txt"])
    elif mutation == "config":
        changed_config = config(version=2)
    else:
        raise AssertionError(f"unsupported mutation: {mutation}")

    write_json(project / ".test-framework" / "config.json", changed_config)
    changed = run_check(project, "verify")

    assert changed.returncode == 0, changed.stdout + changed.stderr
    assert "cache-hit:" not in changed.stdout
    assert f"checked: {expected_checked}" in changed.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "base",
        expected_log,
    ]


def test_test_framework_runner_cache_miss_does_not_fall_back_to_full(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "sample.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "verify.sample",
                        "command": command_that_logs(
                            "verify.sample", "sample-count.txt"
                        ),
                        "paths": ["src/**"],
                        "inputs": ["src/sample.txt"],
                    },
                    {
                        "id": "verify.full-only",
                        "command": command_that_logs(
                            "verify.full-only", "full-ran.txt"
                        ),
                        "paths": ["other/**"],
                        "inputs": ["other"],
                    },
                ]
            },
        },
    )

    result = run_check(project, "verify")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "cache-hit:" not in result.stdout
    assert "checked: verify.sample" in result.stdout
    assert "full-not-run: true" in result.stdout
    assert (project / "sample-count.txt").read_text(encoding="utf-8").splitlines() == [
        "verify.sample"
    ]
    assert not (project / "full-ran.txt").exists()


@pytest.mark.parametrize(
    "excluded_relative",
    [
        Path(".test-framework/cache/noise.txt"),
        Path(".git/noise.txt"),
        Path("src/__pycache__/noise.pyc"),
    ],
)
def test_test_framework_runner_directory_hash_ignores_generated_paths(
    tmp_path: Path, excluded_relative: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "sample.txt").write_text("changed\n", encoding="utf-8")
    run_log = project / ".test-framework" / "cache" / "directory-hash-runs.txt"
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "directory-hash",
                        "command": command_that_logs(
                            "directory-hash",
                            ".test-framework/cache/directory-hash-runs.txt",
                        ),
                        "paths": ["src/**"],
                        "inputs": ["."],
                    }
                ]
            },
        },
    )

    first = run_check(project, "verify")
    noise_path = project / excluded_relative
    noise_path.parent.mkdir(parents=True, exist_ok=True)
    noise_path.write_text("ignored\n", encoding="utf-8")
    second = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: directory-hash" in second.stdout
    assert run_log.read_text(encoding="utf-8").splitlines() == ["directory-hash"]


def test_test_framework_cache_key_covers_runtime_and_cache_versions() -> None:
    template = (
        PLUGIN_ROOT / "skills" / "test-framework" / "scripts" / "test_framework_runner.py"
    ).read_text(encoding="utf-8")

    assert '"cache_version": CACHE_VERSION' in template
    assert '"framework_version": FRAMEWORK_VERSION' in template
    assert '"python_version": platform.python_version()' in template


def test_test_framework_runner_does_not_cache_failed_results(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "fails.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "fail-once",
                        "command": command_that_fails_once("fail-once"),
                        "paths": ["src/fails.py"],
                        "inputs": ["src/fails.py"],
                    }
                ]
            },
        },
    )

    first = run_check(project, "verify")
    second = run_check(project, "verify")

    assert first.returncode != 0
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: fail-once" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "fail-once",
        "fail-once",
    ]


def test_test_framework_runner_no_check_does_not_fall_back_to_full(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "docs").mkdir()
    (project / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "src-only",
                        "command": command_that_logs("src-only"),
                        "paths": ["src/**"],
                        "inputs": ["src"],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "checked:" in result.stdout
    assert "full-not-run: true" in result.stdout
    assert not (project / "run.log").exists()


def test_test_framework_runner_reads_worktree_changed_files(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "staged-check",
                        "command": command_that_logs("staged-check"),
                        "paths": ["staged.txt"],
                        "inputs": ["staged.txt"],
                    },
                    {
                        "id": "unstaged-check",
                        "command": command_that_logs("unstaged-check"),
                        "paths": ["unstaged.txt"],
                        "inputs": ["unstaged.txt"],
                    },
                    {
                        "id": "untracked-check",
                        "command": command_that_logs("untracked-check"),
                        "paths": ["untracked.txt"],
                        "inputs": ["untracked.txt"],
                    },
                ]
            },
        },
    )
    (project / "staged.txt").write_text("base\n", encoding="utf-8")
    (project / "unstaged.txt").write_text("base\n", encoding="utf-8")
    assert git(project, "init").returncode == 0
    assert git(project, "config", "user.email", "test@example.com").returncode == 0
    assert git(project, "config", "user.name", "Test User").returncode == 0
    assert git(project, "add", ".").returncode == 0
    assert git(project, "commit", "-m", "initial").returncode == 0
    (project / "staged.txt").write_text("staged\n", encoding="utf-8")
    assert git(project, "add", "staged.txt").returncode == 0
    (project / "unstaged.txt").write_text("unstaged\n", encoding="utf-8")
    (project / "untracked.txt").write_text("untracked\n", encoding="utf-8")

    result = run_check(project, "verify")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "checked: staged-check, unstaged-check, untracked-check" in result.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "staged-check",
        "unstaged-check",
        "untracked-check",
    ]
