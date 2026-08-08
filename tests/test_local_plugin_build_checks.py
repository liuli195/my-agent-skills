import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_BUILD_SCRIPT = REPO_ROOT / "scripts" / "local_plugin_build.py"
BUILD_AND_VERIFY_RUNNER = (
    REPO_ROOT / "plugins" / "build-and-verify" / "python" / "build_and_verify_runner.py"
)


@pytest.fixture
def worktree_local_tmp_path() -> Iterator[Path]:
    local_root = REPO_ROOT / ".local"
    local_root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="nested-xdist-", dir=local_root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_node_cli_launchers_are_forced_to_lf() -> None:
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()

    assert "plugins/build-and-verify/bin/*.js text eol=lf" in attributes
    assert "plugins/my-spec/bin/*.js text eol=lf" in attributes


def test_my_spec_candidate_setup_accepts_tests_directory_invocation() -> None:
    module = load_module(REPO_ROOT / "tests" / "conftest.py", "test_my_spec_conftest")

    config = type("Config", (), {"args": ["tests"]})()

    assert module._runs_my_spec(config)


def test_my_spec_candidate_setup_reuses_supplied_tarball(tmp_path: Path, monkeypatch) -> None:
    module = load_module(REPO_ROOT / "tests" / "conftest.py", "test_my_spec_conftest_ci")
    candidate = tmp_path / "candidate.tgz"
    candidate.write_bytes(b"candidate")
    monkeypatch.setenv(module.MYSPEC_TEST_TARBALL, str(candidate))

    def unexpected_pack(*args, **kwargs):
        raise AssertionError(f"unexpected pack: {args} {kwargs}")

    monkeypatch.setattr(module.subprocess, "run", unexpected_pack)
    config = type("Config", (), {"args": ["tests/test_my_spec.py"]})()

    module.pytest_configure(config)
    module.pytest_sessionfinish(type("Session", (), {"config": config})(), 0)


def test_my_spec_candidate_setup_restores_external_tarball_value(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module(REPO_ROOT / "tests" / "conftest.py", "test_my_spec_conftest_restore")
    candidate = tmp_path / "candidate.tgz"
    candidate.write_bytes(b"candidate")
    original = str(candidate).replace("\\", "/")
    monkeypatch.setenv(module.MYSPEC_TEST_TARBALL, original)
    monkeypatch.setenv(module.MYSPEC_TEST_IN_PROCESS, "outer")
    config = type("Config", (), {"args": ["tests/test_my_spec.py"]})()

    module.pytest_configure(config)
    assert os.environ[module.MYSPEC_TEST_TARBALL] == str(candidate.resolve())
    module.pytest_sessionfinish(type("Session", (), {"config": config})(), 0)

    assert os.environ[module.MYSPEC_TEST_TARBALL] == original
    assert os.environ[module.MYSPEC_TEST_IN_PROCESS] == "outer"


def test_my_spec_candidate_setup_cleans_up_when_pack_cannot_start(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module(REPO_ROOT / "tests" / "conftest.py", "test_my_spec_conftest_failure")
    candidate_directory = tmp_path / "candidate"
    candidate_directory.mkdir()
    monkeypatch.setattr(module.tempfile, "mkdtemp", lambda **_: str(candidate_directory))
    monkeypatch.delenv(module.MYSPEC_TEST_TARBALL, raising=False)

    def pack_unavailable(*args, **kwargs):
        raise OSError("pack unavailable")

    monkeypatch.setattr(module.subprocess, "run", pack_unavailable)
    config = type("Config", (), {"args": ["tests/test_my_spec.py"]})()

    with pytest.raises(pytest.UsageError, match="failed to prepare MySpec test Tarball"):
        module.pytest_configure(config)

    assert module._candidate_directory is None
    assert not candidate_directory.exists()


def test_my_spec_candidate_install_keeps_real_installs_isolated(tmp_path: Path, monkeypatch) -> None:
    module = load_module(REPO_ROOT / "tests" / "test_my_spec.py", "test_my_spec_real_install")
    candidate = tmp_path / "candidate.tgz"
    candidate.write_bytes(b"candidate")
    monkeypatch.setenv("MYSPEC_TEST_TARBALL", str(candidate))
    calls: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        return "npm" if name == "npm" else None

    def fake_run(command, **kwargs):
        del kwargs
        calls.append(command)
        prefix = Path(command[command.index("--prefix") + 1])
        root = prefix / ("node_modules" if os.name == "nt" else "lib/node_modules")
        package = root / "@liuli195" / "myspec"
        package.mkdir(parents=True, exist_ok=True)
        (package / "package.json").write_text("{}", encoding="utf-8")
        executable = prefix / ("myspec.cmd" if os.name == "nt" else "bin/myspec")
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("#!/bin/sh\n", encoding="utf-8")
        if command[1] == "root":
            return subprocess.CompletedProcess(command, 0, f"{root}\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(module.shutil, "which", fake_which)
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    _, first_package = module.install_packed_myspec(first)
    _, second_package = module.install_packed_myspec(second)

    assert first_package != second_package
    assert len([command for command in calls if command[1] == "install"]) == 2


def test_my_spec_in_process_install_reuses_shared_lightweight_package(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module(REPO_ROOT / "tests" / "test_my_spec.py", "test_my_spec_lightweight_install")
    candidate = tmp_path / "candidate.tgz"
    candidate.write_bytes(b"candidate")
    monkeypatch.setenv("MYSPEC_TEST_TARBALL", str(candidate))
    monkeypatch.setenv("MYSPEC_TEST_IN_PROCESS", "1")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail(f"unexpected subprocess: {args} {kwargs}"),
    )
    copy_calls = []
    copytree = module.shutil.copytree

    def track_copytree(*args, **kwargs):
        if Path(args[1]).name == "myspec":
            copy_calls.append(args[1])
        return copytree(*args, **kwargs)

    monkeypatch.setattr(module.shutil, "copytree", track_copytree)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    first_executable, first_package = module.install_packed_myspec(first)
    second_executable, second_package = module.install_packed_myspec(second)

    assert first_executable.is_file()
    assert second_executable.is_file()
    assert first_package == second_package
    assert module.npm_prefix_for(first_package) == module.npm_prefix_for(second_package)
    assert len(copy_calls) == 1
    assert (first_package / "python" / "spec_ops.py").is_file()
    assert (first_package / "python" / "management.py").read_bytes() == (
        REPO_ROOT / "plugins" / "tool-lifecycle" / "python" / "management.py"
    ).read_bytes()


def test_my_spec_in_process_shared_template_uses_worktree_local_and_cleans_up(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module(REPO_ROOT / "tests" / "test_my_spec.py", "test_my_spec_local_template")
    candidate = tmp_path / "candidate.tgz"
    candidate.write_bytes(b"candidate")
    monkeypatch.setenv("MYSPEC_TEST_TARBALL", str(candidate))
    monkeypatch.setenv("MYSPEC_TEST_IN_PROCESS", "1")

    executable, package = module.install_packed_myspec(tmp_path / "first")
    template_root = next(
        path for path in executable.parents if path.name.startswith("myspec-lightweight-")
    )
    assert package.is_dir()
    module._cleanup_lightweight_install()

    assert template_root.parent.resolve() == (REPO_ROOT / ".local").resolve()
    assert not template_root.exists()


def test_my_spec_in_process_fakes_reject_unhandled_commands() -> None:
    module = load_module(REPO_ROOT / "tests" / "test_my_spec.py", "test_my_spec_fake_command_boundaries")

    git_result = module._run_in_process_git(["git", "unsupported"], ["unsupported"])
    npm_result = module._run_in_process_npm(
        ["npm", "unsupported"], ["unsupported"], {"MYSPEC_PACKAGE_VERSION": "0.0.0"}
    )

    assert git_result.returncode != 0
    assert npm_result.returncode != 0


def test_my_spec_in_process_runner_uses_the_passed_installed_cli(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module(REPO_ROOT / "tests" / "test_my_spec.py", "test_my_spec_installed_cli")
    prefix = tmp_path / "prefix"
    package = prefix / ("node_modules" if os.name == "nt" else "lib/node_modules") / "@liuli195" / "myspec"
    (package / "python").mkdir(parents=True)
    (package / "package.json").write_text(
        (REPO_ROOT / "plugins" / "my-spec" / "package.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    shutil.copy2(
        REPO_ROOT / "plugins" / "my-spec" / "python" / "lifecycle_profile.json",
        package / "python" / "lifecycle_profile.json",
    )
    shutil.copy2(
        REPO_ROOT / "plugins" / "tool-lifecycle" / "python" / "management.py",
        package / "python" / "management.py",
    )
    (package / "python" / "spec_ops.py").write_text(
        "def main(args):\n    print('installed-cli')\n    return 0\n",
        encoding="utf-8",
    )
    executable = prefix / ("myspec.cmd" if os.name == "nt" else "bin/myspec")
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("", encoding="utf-8")
    monkeypatch.setenv("MYSPEC_TEST_IN_PROCESS", "1")

    result = module.run_cli(executable, "--help")

    assert result.returncode == 0
    assert result.stdout == "installed-cli\n"


def test_my_spec_in_process_runner_handles_spec_ops_without_subprocess(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module(REPO_ROOT / "tests" / "test_my_spec.py", "test_my_spec_in_process")
    specs = tmp_path / "specs" / "accounts" / "spec.md"
    specs.parent.mkdir(parents=True)
    specs.write_text(
        "# Accounts\n\n## Purpose\n\n描述账户行为。\n\n## Requirements\n\n"
        "### Requirement: 登录\n\n系统 MUST 允许登录。\n\n#### Scenario: 正常\n\n"
        "- **WHEN** 用户登录\n- **THEN** 系统创建会话\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MYSPEC_TEST_IN_PROCESS", "1")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail(f"unexpected subprocess: {args} {kwargs}"),
    )

    result = module.run_python(module.SPEC_OPS, "validate-main", specs.parent.parent)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


def test_my_spec_in_process_runner_restores_subprocess_after_failure(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module(REPO_ROOT / "tests" / "test_my_spec.py", "test_my_spec_in_process_restore")
    script = tmp_path / "spec_ops.py"
    script.write_text("", encoding="utf-8")
    original_run = module.subprocess.run

    class BrokenSpecOps:
        @staticmethod
        def main(_args):
            raise RuntimeError("simulated runner failure")

    monkeypatch.setattr(module, "_load_in_process_spec_ops", lambda _path: BrokenSpecOps)

    result = module._run_in_process(script)

    assert result.returncode == 1
    assert module.subprocess.run is original_run


def test_my_spec_in_process_management_avoids_fake_client_subprocess(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module(REPO_ROOT / "tests" / "test_my_spec.py", "test_my_spec_in_process_management")
    candidate = tmp_path / "candidate.tgz"
    candidate.write_bytes(b"candidate")
    monkeypatch.setenv("MYSPEC_TEST_TARBALL", str(candidate))
    monkeypatch.setenv("MYSPEC_TEST_IN_PROCESS", "1")

    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = module.install_packed_myspec(installed)
    client_bin, log = module.install_fake_pi(tmp_path / "fake-pi")
    env = module.isolated_myspec_env(tmp_path, module.npm_prefix_for(installed_package), client_bin)
    env["MYSPEC_PI_LOG"] = str(log)
    module.write(
        Path(env["PI_CODING_AGENT_DIR"]) / "settings.json",
        json.dumps({"packages": [str(installed_package)]}),
    )
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail(f"unexpected subprocess: {args} {kwargs}"),
    )

    result = module.run_cli(executable, "doctor", "--pi", env=env)

    assert result.returncode == 0, result.stderr


def test_my_spec_in_process_shared_package_rebuilds_after_mutation(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module(REPO_ROOT / "tests" / "test_my_spec.py", "test_my_spec_lightweight_integrity")
    candidate = tmp_path / "candidate.tgz"
    candidate.write_bytes(b"candidate")
    monkeypatch.setenv("MYSPEC_TEST_TARBALL", str(candidate))
    monkeypatch.setenv("MYSPEC_TEST_IN_PROCESS", "1")
    first_executable, first_package = module.install_packed_myspec(tmp_path / "first")
    del first_executable
    lifecycle_root = first_package.parents[1] / "plugins" / "tool-lifecycle"
    _private_executable, private_package = module._copy_lightweight_myspec(tmp_path / "private")
    del _private_executable
    private_lifecycle_root = private_package.parents[1] / "plugins" / "tool-lifecycle"
    for root in (lifecycle_root, private_lifecycle_root):
        assert (root / "python" / "management.py").read_bytes() == (
            module.SHARED_MANAGEMENT
        ).read_bytes()
        assert (root / "pack.py").read_bytes() == module.PACK.read_bytes()
    changed = lifecycle_root / "pack.py"
    original = changed.read_bytes()
    changed.write_bytes(original + b"\n")

    _second_executable, second_package = module.install_packed_myspec(tmp_path / "second")

    assert second_package != first_package
    assert second_package.joinpath("package.json").read_bytes() == (
        module.PLUGIN_ROOT / "package.json"
    ).read_bytes()
    assert (
        second_package.parents[1] / "plugins" / "tool-lifecycle" / "pack.py"
    ).read_bytes() == module.PACK.read_bytes()
    changed = second_package / "package.json"
    original = changed.read_bytes()
    changed.write_bytes(original + b"\n")

    _third_executable, third_package = module.install_packed_myspec(tmp_path / "third")

    assert third_package != second_package
    assert third_package.joinpath("package.json").read_bytes() == original


def test_my_spec_candidate_setup_packs_once_before_workers(monkeypatch) -> None:
    module = load_module(REPO_ROOT / "tests" / "conftest.py", "test_my_spec_conftest_once")
    calls: list[list[str]] = []

    def pack_once(command, **kwargs):
        del kwargs
        calls.append(command)
        output = Path(command[-1]) / "candidate.tgz"
        output.write_bytes(b"candidate")
        return subprocess.CompletedProcess(command, 0, f"{output}\n", "")

    monkeypatch.delenv(module.MYSPEC_TEST_TARBALL, raising=False)
    monkeypatch.setattr(module.subprocess, "run", pack_once)
    config = type("Config", (), {"args": ["tests/test_my_spec.py"]})()
    module.pytest_configure(config)
    module.pytest_configure(config)
    controller_candidate = Path(os.environ[module.MYSPEC_TEST_TARBALL])
    assert controller_candidate.is_absolute()

    assert len(calls) == 1
    assert calls[0][0:3] == [sys.executable, str(module.MYSPEC_PACK), "myspec"]
    module.pytest_sessionfinish(type("Session", (), {"config": config})(), 0)
    assert module._candidate_directory is None


def test_my_spec_candidate_path_reaches_real_xdist_workers(
    worktree_local_tmp_path: Path,
) -> None:
    report_dir = worktree_local_tmp_path / "worker-reports"
    report_dir.mkdir()
    worker_temp_root = worktree_local_tmp_path / "worker-temp"
    worker_temp_root.mkdir()
    probe = worktree_local_tmp_path / "test_my_spec.py"
    probe.write_text(
        """import json
import os
from pathlib import Path

import tests.test_my_spec as myspec


def test_candidate_is_inherited_and_installed_once(tmp_path):
    worker = os.environ["PYTEST_XDIST_WORKER"]
    candidate = Path(os.environ["MYSPEC_TEST_TARBALL"]).resolve()
    assert candidate.is_file()
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, package = myspec.install_packed_myspec(installed)
    prefix = myspec.npm_prefix_for(package)
    client_bin, log = myspec.install_fake_pi(tmp_path / "fake-pi")
    env = myspec.isolated_myspec_env(tmp_path, prefix, client_bin)
    env["MYSPEC_PI_LOG"] = str(log)
    state_root = Path(env["HOME"]) / ".myspec"
    state_root.mkdir()
    myspec.write(
        Path(env["PI_CODING_AGENT_DIR"]) / "settings.json",
        json.dumps({"packages": []}),
    )
    result = myspec.run_cli(executable, "doctor", "--pi", env=env)
    assert result.returncode == 0, result.stderr
    report = {
        "candidate": str(candidate),
        "home": str(Path(env["HOME"]).resolve()),
        "logRoot": str(log.parent.resolve()),
        "stateRoot": str(state_root.resolve()),
        "prefix": str(prefix.resolve()),
        "package": str(package.resolve()),
        "packageExistsBeforeWorkerCleanup": package.is_dir(),
    }
    (Path(os.environ["MYSPEC_WORKER_REPORT_DIR"]) / f"{worker}.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.pop("MYSPEC_TEST_TARBALL", None)
    env["MYSPEC_WORKER_REPORT_DIR"] = str(report_dir)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "tests.conftest",
            "-n",
            "4",
            "--dist=each",
            "--rootdir",
            str(REPO_ROOT),
            "--basetemp",
            str(worker_temp_root),
            str(probe),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    reports = sorted(report_dir.glob("gw*.json"))
    assert [report.stem for report in reports] == ["gw0", "gw1", "gw2", "gw3"]
    payloads = [json.loads(report.read_text(encoding="utf-8")) for report in reports]
    candidates = {Path(payload["candidate"]).resolve() for payload in payloads}
    assert len(candidates) == 1
    candidate = next(iter(candidates))
    assert candidate.is_absolute()
    for field in ("home", "logRoot", "stateRoot", "prefix"):
        values = {Path(payload[field]).resolve() for payload in payloads}
        assert len(values) == 4, field
    assert all(payload["packageExistsBeforeWorkerCleanup"] for payload in payloads)
    assert all(Path(payload["logRoot"]).is_dir() for payload in payloads)
    assert all(Path(payload["stateRoot"]).is_dir() for payload in payloads)
    assert not list(worker_temp_root.glob("myspec-install-template-*"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_check_module():
    module = load_module(BUILD_AND_VERIFY_RUNNER, "build_and_verify_runner")
    run_verify = module.run_verify

    def run_verify_with_test_runtime(*args, **kwargs):
        kwargs.setdefault("runtime_version", "test-runtime")
        return run_verify(*args, **kwargs)

    module.run_verify = run_verify_with_test_runtime
    return module


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
            "version": "9.9.0",
            "description": f"{name} plugin",
            "skills": "./skills",
        },
    )
    write_json(
        plugin / ".codex-plugin" / "plugin.json",
        {
            "name": name,
            "version": "9.9.0",
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

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
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

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
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

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
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


def test_runner_config_change_selects_all_checks_once(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    write_runner_config(
        tmp_path,
        verify_checks=[
            {"id": "verify.src", "command": "run-verify-src", "paths": ["src/**"]},
            {"id": "verify.docs", "command": "run-verify-docs", "paths": ["docs/**"]},
        ],
    )
    monkeypatch.setattr(
        module,
        "_changed_files",
        lambda _root: [".build-and-verify/config.json"],
        raising=False,
    )
    calls: list[str] = []

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
        calls.append(command)
        return make_completed(command)

    assert module.run_verify(tmp_path, runner=fake_run) == 0

    output = capsys.readouterr().out
    assert calls == ["run-verify-src", "run-verify-docs"]
    assert output.count("selection-reason: config-changed") == 1


def test_runner_config_change_invalidates_old_cache_and_reuses_current_cache(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("app\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("guide\n", encoding="utf-8")
    checks = [
        {"id": "verify.src", "command": "run-verify-src", "paths": ["src/**"], "inputs": ["src/app.py"]},
        {"id": "verify.docs", "command": "run-verify-docs", "paths": ["docs/**"], "inputs": ["docs/guide.md"]},
    ]
    write_runner_config(tmp_path, verify_checks=checks)
    old_config = module._load_config(tmp_path)
    for check in checks:
        module._cache_store(
            tmp_path,
            module._cache_key(
                tmp_path,
                old_config,
                check,
                [".build-and-verify/config.json"],
                runtime_identity="test-runtime",
            ),
            check,
        )
    monkeypatch.setattr(
        module,
        "_changed_files",
        lambda _root: [".build-and-verify/config.json"],
        raising=False,
    )
    calls: list[str] = []

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
        calls.append(command)
        return make_completed(command)

    assert module.run_verify(tmp_path, runner=fake_run) == 0
    current_output = capsys.readouterr().out
    assert calls == []
    assert "cache-hit: verify.src" in current_output
    assert "cache-hit: verify.docs" in current_output

    write_json(
        tmp_path / ".build-and-verify" / "config.json",
        {"version": 2, "build": {"checks": []}, "verify": {"checks": checks}},
    )
    assert module.run_verify(tmp_path, runner=fake_run) == 0
    changed_output = capsys.readouterr().out
    assert calls == ["run-verify-src", "run-verify-docs"]
    assert "cache-hit:" not in changed_output

    assert module.run_verify(tmp_path, runner=fake_run) == 0
    reused_output = capsys.readouterr().out
    assert calls == ["run-verify-src", "run-verify-docs"]
    assert "cache-hit: verify.src" in reused_output
    assert "cache-hit: verify.docs" in reused_output


def test_runner_invalid_config_stops_before_scheduling_verify_checks(
    tmp_path: Path, capsys
) -> None:
    module = load_check_module()
    write_json(
        tmp_path / ".build-and-verify" / "config.json",
        {"version": 1, "build": {"checks": []}, "verify": {"checks": [{"id": "bad", "command": "run", "paths": "src/**"}]}},
    )

    def fake_run(*_args, **_kwargs):
        raise AssertionError("invalid config must stop before scheduling")

    assert module.run_verify(tmp_path, runner=fake_run) == 1
    captured = capsys.readouterr()
    assert "verify.checks[0].paths must be list of non-empty strings" in captured.err


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

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
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

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
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

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
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

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
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


def test_runner_binds_cache_to_runtime_version_and_requires_version(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        build_checks=[{"id": "build", "command": "run-build"}],
        verify_checks=[
            {
                "id": "versioned-cache",
                "command": "run-versioned-cache",
                "paths": ["src/**"],
                "inputs": ["src/app.py"],
            }
        ],
    )
    monkeypatch.setattr(module, "_changed_files", lambda _root: ["src/app.py"])
    calls: list[str] = []

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
        calls.append(command)
        return make_completed(command)

    assert module.run_verify(tmp_path, runner=fake_run, runtime_version="1.0.0") == 0
    assert module.run_verify(tmp_path, runner=fake_run, runtime_version="1.0.0") == 0
    assert module.run_verify(tmp_path, runner=fake_run, runtime_version="2.0.0") == 0
    assert module.run_verify(tmp_path, runner=fake_run, full=True, runtime_version="3.0.0") == 0
    assert module.run_verify(tmp_path, runner=fake_run, runtime_version="3.0.0") == 0
    assert calls == ["run-versioned-cache", "run-versioned-cache", "run-versioned-cache"]
    assert capsys.readouterr().out.count("cache-hit: versioned-cache") == 2

    cache_files = list((tmp_path / ".build-and-verify" / "cache").glob("*.json"))
    assert len(cache_files) == 3
    calls.clear()
    assert module.run_verify(tmp_path, runner=fake_run, runtime_version="") == 1
    assert module.run_verify(tmp_path, runner=fake_run, full=True, runtime_version="") == 1
    assert calls == []
    assert len(list((tmp_path / ".build-and-verify" / "cache").glob("*.json"))) == 3
    assert module.run_build(tmp_path, runner=fake_run) == 0
    assert calls == ["run-build"]
    assert capsys.readouterr().err.count("missing_runtime_version") == 2


def test_runner_binds_cache_to_implementation_identity(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        tmp_path,
        verify_checks=[
            {
                "id": "implementation-cache",
                "command": "run-implementation-cache",
                "paths": ["src/**"],
                "inputs": ["src/app.py"],
            }
        ],
    )
    monkeypatch.setattr(module, "_changed_files", lambda _root: ["src/app.py"])
    calls: list[str] = []

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
        calls.append(command)
        return make_completed(command)

    assert module.run_verify(
        tmp_path,
        runner=fake_run,
        runtime_version="test-runtime",
        implementation_identity="implementation-a",
    ) == 0
    assert module.run_verify(
        tmp_path,
        runner=fake_run,
        runtime_version="test-runtime",
        implementation_identity="implementation-a",
    ) == 0
    assert module.run_verify(
        tmp_path,
        runner=fake_run,
        runtime_version="test-runtime",
        implementation_identity="implementation-b",
    ) == 0
    assert calls == ["run-implementation-cache", "run-implementation-cache"]
    assert capsys.readouterr().out.count("cache-hit: implementation-cache") == 1


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
    base_framework_version = module.FRAMEWORK_VERSION
    base_cache_version = module.CACHE_VERSION
    base_key = module._cache_key(tmp_path, config, check, ["src/app.py"])

    monkeypatch.setattr(
        module, "FRAMEWORK_VERSION", "changed-framework", raising=False
    )
    framework_key = module._cache_key(tmp_path, config, check, ["src/app.py"])
    monkeypatch.setattr(
        module, "FRAMEWORK_VERSION", base_framework_version, raising=False
    )
    monkeypatch.setattr(module, "CACHE_VERSION", "changed-cache", raising=False)
    cache_key = module._cache_key(tmp_path, config, check, ["src/app.py"])
    monkeypatch.setattr(module, "CACHE_VERSION", base_cache_version, raising=False)
    monkeypatch.setattr(
        module.platform, "python_version", lambda: "changed-python", raising=False
    )
    python_key = module._cache_key(tmp_path, config, check, ["src/app.py"])

    assert framework_key != base_key
    assert cache_key != base_key
    assert python_key != base_key


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

    def fake_run(command, cwd, check, text, encoding, errors, capture_output, shell=False, timeout=None):
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
    assert "status: skipped" in output
    assert "reason: no_changed_files" in output


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


def test_build_validates_plugins_without_claude_command(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha"])
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    assert module.main(["build"]) == 0
    assert "status: build checks passed" in capsys.readouterr().out


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

    errors = module.run_build(tmp_path)

    assert any("source_outside_repo" in error for error in errors)


def test_build_rejects_codex_dev_marketplace_without_dev_name(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha"])
    make_codex_dev_marketplace(tmp_path, ["alpha"], marketplace_name="test-marketplace", display_name="Test Marketplace")

    errors = module.run_build(tmp_path)

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

    errors = module.run_build(tmp_path)

    assert any("codex_dev_source_outside_repo" in error for error in errors)


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

    errors = module.run_build(tmp_path)

    assert any("invalid_marketplace_entry" in error for error in errors)


def test_build_reports_duplicate_marketplace_plugin_name(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha", "alpha"])
    make_projection(tmp_path, ["alpha"])

    errors = module.run_build(tmp_path)

    assert any("duplicate_marketplace_plugin: alpha" in error for error in errors)


def test_build_reports_missing_pyyaml_dependency(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_marketplace(tmp_path, [])
    make_projection(tmp_path, [])
    module.yaml = None

    errors = module.run_build(tmp_path)

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
            "version": "9.9.0",
            "description": "wrong plugin",
            "skills": "./skills",
        },
    )

    errors = module.run_build(tmp_path)

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

    errors = module.run_build(tmp_path)

    assert any("missing_manifest_path" in error for error in errors)


def test_build_reports_projection_plugin_mismatch(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha", "missing"])

    errors = module.run_build(tmp_path)

    assert any("projection_plugins_mismatch" in error for error in errors)


def test_build_reports_projection_missing_marketplace_plugin(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_plugin(tmp_path, "beta")
    make_marketplace(tmp_path, ["alpha", "beta"])
    make_projection(tmp_path, ["alpha"])

    errors = module.run_build(tmp_path)

    assert any("projection_plugins_mismatch" in error for error in errors)


def test_build_reports_duplicate_projection_plugin(tmp_path: Path) -> None:
    module = load_local_build_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha", "alpha"])

    errors = module.run_build(tmp_path)

    assert any("duplicate_projection_plugin" in error for error in errors)


def test_active_automation_does_not_reference_removed_check_entrypoint() -> None:
    active_files = [
        REPO_ROOT / ".github" / "workflows" / "release.yml",
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
        "verify.pi-tool-display",
        "verify.local-build-contract",
        "verify.release-flow",
        "verify.pr-flow",
        "verify.myspec",
        "verify.my-spec",
        "verify.runtime-boundaries",
        "verify.build-and-verify",
    ]
    assert "pytest.full" not in check_by_id

    runtime_boundaries = check_by_id["verify.runtime-boundaries"]
    assert runtime_boundaries["paths"] == ["requirements-dev.txt", "tests/**"]
    assert runtime_boundaries["inputs"] == ["requirements-dev.txt", "tests"]
    assert runtime_boundaries["command"] == (
        "python -m pytest -q -p no:cacheprovider tests/test_test_runtime_boundaries.py"
    )
    assert runtime_boundaries["checkParallel"] is True
    assert "pytestXdistWorkers" not in runtime_boundaries
    assert "tests/test_test_runtime_boundaries.py" not in check_by_id[
        "verify.build-and-verify"
    ]["command"]
    selected = {
        check["id"]
        for check in load_check_module()._selected_checks(
            checks, ["tests/test_my_spec.py"]
        )
    }
    assert "verify.runtime-boundaries" in selected
    assert "verify.build-and-verify" not in selected

    myspec = check_by_id["verify.myspec"]
    assert myspec["paths"] == [
        "myspec/specs/**",
        "plugins/my-spec/bin/myspec.js",
        "plugins/my-spec/python/spec_ops.py",
    ]
    assert myspec["inputs"] == [
        "myspec/specs",
        "plugins/my-spec/bin/myspec.js",
        "plugins/my-spec/python/spec_ops.py",
    ]
    assert myspec["command"] == (
        "node plugins/my-spec/bin/myspec.js validate-main myspec/specs"
    )

    my_spec = check_by_id["verify.my-spec"]
    assert my_spec["paths"] == [
        ".agents/plugins/marketplace.json",
        ".claude-plugin/marketplace.json",
        ".release-flow/projection.yaml",
        ".build-and-verify/config.json",
        ".gitattributes",
        ".gitignore",
        "myspec/specs/my-spec/spec.md",
        "plugins/my-spec/**",
        "plugins/tool-lifecycle/**",
        "tests/conftest.py",
        "tests/test_my_spec.py",
        "tests/fixtures/myspec_source_cases.json",
    ]
    assert my_spec["timeoutSeconds"] == 420
    assert my_spec["checkParallel"] is False
    assert my_spec["pytestXdistWorkers"] == 4
    assert my_spec["inputs"] == [
        ".agents/plugins/marketplace.json",
        ".claude-plugin/marketplace.json",
        ".release-flow/projection.yaml",
        ".build-and-verify/config.json",
        ".gitattributes",
        ".gitignore",
        "myspec/specs/my-spec/spec.md",
        "plugins/my-spec",
        "plugins/tool-lifecycle",
        "tests/conftest.py",
        "tests/test_my_spec.py",
        "tests/fixtures/myspec_source_cases.json",
    ]

    local_build_contract = check_by_id["verify.local-build-contract"]
    assert ".comet/config.yaml" in local_build_contract["paths"]
    assert ".comet/config.yaml" in local_build_contract["inputs"]
    assert ".comet.yaml" not in local_build_contract["paths"]
    assert ".comet.yaml" not in local_build_contract["inputs"]
    assert "." not in local_build_contract["inputs"]
    for check in checks:
        assert "docs/agent-guard/**" not in check.get("paths", [])
        assert "docs/agent-guard" not in check.get("inputs", [])


def test_runtime_boundaries_cache_tracks_test_directory(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_check_module()
    test_file = tmp_path / "tests" / "test_sample.py"
    test_file.parent.mkdir()
    test_file.write_text("first\n", encoding="utf-8")
    root_config = json.loads(
        (REPO_ROOT / ".build-and-verify" / "config.json").read_text(encoding="utf-8")
    )
    runtime_boundaries = dict(
        next(
            check
            for check in root_config["verify"]["checks"]
            if check["id"] == "verify.runtime-boundaries"
        )
    )
    runtime_boundaries["command"] = "runtime-boundaries"
    write_runner_config(tmp_path, verify_checks=[runtime_boundaries])
    monkeypatch.setattr(
        module, "_changed_files", lambda _root: ["tests/test_sample.py"]
    )
    calls: list[str] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return make_completed(command)

    assert module.run_verify(tmp_path, runner=fake_run) == 0
    first_output = capsys.readouterr().out
    assert module.run_verify(tmp_path, runner=fake_run) == 0
    second_output = capsys.readouterr().out
    test_file.write_text("second\n", encoding="utf-8")
    assert module.run_verify(tmp_path, runner=fake_run) == 0
    third_output = capsys.readouterr().out

    assert "cache-hit: verify.runtime-boundaries" not in first_output
    assert "cache-hit: verify.runtime-boundaries" in second_output
    assert "cache-hit: verify.runtime-boundaries" not in third_output
    assert calls == ["runtime-boundaries", "runtime-boundaries"]

