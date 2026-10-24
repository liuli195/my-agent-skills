from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import shlex
import signal
import subprocess
import sys
import tempfile
import tarfile
import time
import traceback
from pathlib import Path
from typing import Any, Callable

import yaml
import pytest

from tests.support.npm_candidates import candidate_for, copy_install

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "plugins" / "build-and-verify"
PACK = REPO_ROOT / "plugins" / "tool-lifecycle" / "pack.py"


def _package_version() -> str:
    return json.loads((PACKAGE_ROOT / "package.json").read_text(encoding="utf-8"))["version"]


def _installed_build_and_verify(tmp_path: Path) -> tuple[str, Path, Path]:
    candidate = candidate_for("build-and-verify")
    prefix = tmp_path / "prefix"
    executable, _ = copy_install(candidate, prefix)
    return candidate.npm, prefix, executable

def _budget_run(tmp_path: Path, *, settings: dict | None = None,
                context: str | None = "local", extra: tuple[str, ...] = (),
                full: bool = True, checks: list[dict] | None = None,
                before_run=None) -> tuple[subprocess.CompletedProcess, Path]:
    project = tmp_path / "project"
    (project / ".build-and-verify").mkdir(parents=True)
    budget = (settings or {}).get("fullBudgetSeconds", 3)
    config = {"version": 1, "verify": {"fullBudgetSeconds": budget, "checks": checks or [
        {"id": "slow", "command": [sys.executable, "-c", f"import time; time.sleep({budget + 0.2})"], "inputs": []},
        {"id": "later", "command": [sys.executable, "-c", "print('LATER_STARTED')"], "inputs": []},
    ], **(settings or {})}}
    (project / ".build-and-verify" / "config.json").write_text(json.dumps(config), encoding="utf-8")
    initialized = subprocess.run(["git", "init", str(project)], capture_output=True)
    assert initialized.returncode == 0
    if before_run is not None:
        before_run(project)
    env = {**os.environ, "BUILD_AND_VERIFY_PYTHON": sys.executable,
           "GITHUB_ACTIONS": "false", "CI": "false", "CODEX_CI": "1"}
    env.pop("BUILD_AND_VERIFY_EXECUTION_CONTEXT", None)
    if context is not None:
        env["BUILD_AND_VERIFY_EXECUTION_CONTEXT"] = context
    package_root = candidate_for("build-and-verify").installed_package
    public_started = time.monotonic()
    result = subprocess.run([shutil.which("node"), str(package_root / "bin" / "build-and-verify.js"),
        "verify", "--project", str(project), *(('--full',) if full else ()), *extra],
        env=env, capture_output=True, text=True, timeout=8)
    result.public_elapsed_seconds = time.monotonic() - public_started
    return result, project


def _assert_pid_terminated(pid: int) -> None:
    if sys.platform == "win32":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            assert ctypes.get_last_error() == 87, "cannot prove owned descendant terminated"
            return
        code = ctypes.c_ulong()
        try:
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
            assert code.value != 259, f"owned descendant {pid} is still running"
        finally:
            kernel.CloseHandle(handle)
    else:
        # Linux may retain a terminated orphan as a zombie until init reaps it.
        stat = Path(f"/proc/{pid}/stat")
        if sys.platform.startswith("linux") and stat.exists():
            try:
                if stat.read_text().rsplit(")", 1)[1].split()[0] == "Z":
                    return
            except FileNotFoundError:
                return
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def _tree_snapshot() -> dict[str, bytes]:
    roots = ("plugins/build-and-verify", "plugins/tool-lifecycle")
    return {
        path.relative_to(REPO_ROOT).as_posix(): path.read_bytes()
        for root in roots
        for path in (REPO_ROOT / root).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def _isolated_env(tmp_path: Path, prefix: Path) -> dict[str, str]:
    home = tmp_path / "home"
    for path in (home, home / "AppData" / "Roaming", home / ".config", home / ".pi" / "agent", home / ".codex", home / ".claude"):
        path.mkdir(parents=True, exist_ok=True)
    return {
        **os.environ,
        "NPM_CONFIG_PREFIX": str(prefix),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "PI_CODING_AGENT_DIR": str(home / ".pi" / "agent"),
        "CODEX_HOME": str(home / ".codex"),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
    }


def _controlled_dev_source(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    for name in (".gitattributes", ".gitignore"):
        shutil.copy2(REPO_ROOT / name, source / name)
    for relative in (".agents", ".claude-plugin", "plugins/build-and-verify", "plugins/tool-lifecycle"):
        shutil.copytree(
            REPO_ROOT / relative,
            source / relative,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    launcher = source / "plugins" / "build-and-verify" / "bin" / "build-and-verify.js"
    launcher.chmod(launcher.stat().st_mode | 0o111)
    initialized = subprocess.run(["git", "init"], cwd=source, text=True, capture_output=True, check=False)
    assert initialized.returncode == 0, initialized.stderr
    # The isolated HOME must not lose Windows long-path support for this fixture.
    configured = _git(source, "config", "core.longpaths", "true")
    assert configured.returncode == 0, configured.stderr
    committed = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "add", "."],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr
    executable = subprocess.run(
        ["git", "update-index", "--chmod=+x", str(launcher.relative_to(source))],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert executable.returncode == 0, executable.stderr
    committed = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "source"],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr
    published = tmp_path / "published.git"
    initialized = subprocess.run(["git", "init", "--bare", published], text=True, capture_output=True, check=False)
    assert initialized.returncode == 0, initialized.stderr
    remote = subprocess.run(["git", "remote", "add", "published", published.as_uri()], cwd=source, text=True, capture_output=True, check=False)
    assert remote.returncode == 0, remote.stderr
    pushed = subprocess.run(["git", "push", "published", "HEAD:main"], cwd=source, text=True, capture_output=True, check=False)
    assert pushed.returncode == 0, pushed.stderr
    removed = subprocess.run(["git", "remote", "remove", "published"], cwd=source, text=True, capture_output=True, check=False)
    assert removed.returncode == 0, removed.stderr
    remote = subprocess.run(["git", "remote", "add", "origin", "git@github.com:liuli195/my-agent-skills.git"], cwd=source, text=True, capture_output=True, check=False)
    assert remote.returncode == 0, remote.stderr
    ssh = tmp_path / "ssh.py"
    ssh.write_text(
        "import subprocess\nimport sys\n"
        f"raise SystemExit(subprocess.run(['git', 'upload-pack', {str(published)!r}]).returncode)\n",
        encoding="utf-8",
    )
    return source, ssh


def _git(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=project, text=True, capture_output=True, check=False)


def _legacy_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    runtime = project / ".build-and-verify" / "runtime"
    runtime.mkdir(parents=True)
    (project / ".build-and-verify" / "config.json").write_text(
        json.dumps({"version": 1, "build": {"checks": []}, "verify": {"checks": []}}),
        encoding="utf-8",
    )
    (runtime / "build_and_verify.py").write_text("legacy", encoding="utf-8")
    (runtime / "build_and_verify_runner.py").write_text("legacy", encoding="utf-8")
    (runtime / "version.json").write_text(
        json.dumps({"plugin": "build-and-verify", "plugin_version": _package_version(), "runtime_version": _package_version()}),
        encoding="utf-8",
    )
    assert _git(project, "init").returncode == 0
    assert _git(project, "config", "user.name", "test").returncode == 0
    assert _git(project, "config", "user.email", "test@example.invalid").returncode == 0
    assert _git(project, "add", ".").returncode == 0
    committed = _git(project, "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "initial")
    assert committed.returncode == 0, committed.stderr
    return project



def _run_installed_bav(*args: str) -> subprocess.CompletedProcess[str]:
    candidate = candidate_for("build-and-verify")
    return subprocess.run([str(candidate.executable), *args], text=True, capture_output=True,
        check=False, env={**os.environ, "BUILD_AND_VERIFY_PYTHON": sys.executable})


class TestBuildAndVerify:
    def test_build_and_verify_package_excludes_legacy_skill_runtime(self, npm_candidate) -> None:
        # Inspect the official candidate prepared once by this check's controller.
        with tarfile.open(npm_candidate.tarball, "r:gz") as archive:
            files = {name.removeprefix("package/") for name in archive.getnames()}
        assert "python/build_and_verify.py" in files
        assert "python/build_and_verify_runner.py" in files
        assert not any(path.startswith("skills/build-and-verify/scripts/") for path in files)

    @pytest.mark.parametrize("full", [False, True])
    def test_public_verify_budget_applies_to_fast_and_full(self, tmp_path: Path, full: bool) -> None:
        checks = [
            {"id": "slow", "command": [sys.executable, "-c", "import time; time.sleep(6)"], "inputs": []},
            {"id": "later", "command": [sys.executable, "-c", "print('LATER_STARTED')"], "inputs": []},
        ]
        result, project = _budget_run(tmp_path, full=full, checks=checks,
            context="local" if full else "cloud",
            extra=() if full else ("--execution-context=local",))
        assert result.public_elapsed_seconds < 5
        assert result.returncode == 1, result.stdout + result.stderr
        assert "total_budget_timeout" in result.stdout
        assert "LATER_STARTED" not in result.stdout
        assert "not-started: later" in result.stdout
        report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
        assert report["verificationStatus"] == "failed"
        assert report["reason"] == "total_budget_timeout"
        assert report["overBudget"] is True
        assert report["notStarted"] == ["later"]
        assert report["checks"][0]["status"] == "timed_out"
        assert not list((project / ".build-and-verify/cache").glob("*.json"))


    def test_public_verify_budget_reaps_descendants_and_preserves_other_processes(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "descendant.pid"
        child_code = "import time; time.sleep(10)"
        parent_code = ("import subprocess,sys,time,pathlib; "
            f"child=subprocess.Popen([sys.executable,'-S','-c',{child_code!r}]); "
            f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid)); time.sleep(10)")
        unrelated = subprocess.Popen([sys.executable, "-S", "-c", child_code])
        try:
            result, _ = _budget_run(tmp_path, checks=[
                {"id": "tree", "command": [sys.executable, "-S", "-c", parent_code], "inputs": []}])
            assert result.returncode == 1, result.stdout + result.stderr
            assert result.public_elapsed_seconds < 5
            assert pid_file.exists(), result.stdout + result.stderr
            assert unrelated.poll() is None
            _assert_pid_terminated(int(pid_file.read_text()))
        finally:
            unrelated.terminate()
            unrelated.wait(timeout=2)


    def test_public_verify_budget_interrupts_blocked_preparation_and_its_descendants(self, tmp_path: Path) -> None:
        # A real Git filesystem monitor models a blocked external preparation read.
        # This is confined to the synthetic repository, never the user's hooks.
        pids = tmp_path / "preparation-pids.json"
        monitor = tmp_path / "monitor.py"
        monitor.write_text(
            "import json,os,subprocess,sys,time\nfrom pathlib import Path\n"
            "child=subprocess.Popen([sys.executable,'-S','-c','import time; time.sleep(10)'])\n"
            f"Path({str(pids)!r}).write_text(json.dumps([os.getpid(),child.pid]))\n"
            "time.sleep(10)\n", encoding="utf-8")
        hook = tmp_path / "monitor with space.sh"
        hook.write_text(f"#!/bin/sh\nexec {shlex.quote(Path(sys.executable).as_posix())} -S -B {shlex.quote(monitor.as_posix())}\n", encoding="utf-8", newline="\n")
        hook.chmod(0o755)

        def prepare(project: Path) -> None:
            (project / "probe.txt").write_text("tracked", encoding="utf-8")
            assert _git(project, "add", "probe.txt").returncode == 0
            assert _git(project, "config", "core.fsmonitor", shlex.quote(hook.as_posix())).returncode == 0

        started = time.monotonic()
        result, project = _budget_run(tmp_path, before_run=prepare)
        assert result.returncode != 0, result.stdout + result.stderr
        assert "bounded-cleanup-fallback" in result.stdout + result.stderr
        assert "total_budget_timeout:" in result.stderr
        assert "not-started: slow, later" in result.stderr
        assert "check-start:" not in result.stdout
        assert time.monotonic() - started < 6
        assert result.public_elapsed_seconds < 5
        assert pids.exists(), result.stdout + result.stderr
        for pid in json.loads(pids.read_text()):
            _assert_pid_terminated(pid)
        report_path = project / ".build-and-verify/runs/performance-report.json"
        if not report_path.exists():
            # Bounded fallback report I/O is best effort, never silent on failure.
            assert "performance-report-warning:" in result.stderr, result.stdout + result.stderr
            return
        report = json.loads(report_path.read_text())
        assert report["verificationStatus"] == "failed"
        assert report["reason"] == "total_budget_timeout"
        assert report["notStarted"] == ["slow", "later"]


    @pytest.mark.parametrize("phase", ["entry", "probe"])
    def test_review_python_startup_and_probe_are_inside_total_budget(self, tmp_path: Path, monkeypatch, phase: str) -> None:
        startup = tmp_path / "startup"
        startup.mkdir()
        condition = "sys.argv[0] == '-c'" if phase == "probe" else "sys.argv[0].endswith('build_and_verify.py')"
        (startup / "sitecustomize.py").write_text(
            f"import sys,time\nif {condition}: time.sleep(2)\n", encoding="utf-8")
        monkeypatch.setenv("PYTHONPATH", str(startup))
        result, _ = _budget_run(tmp_path, settings={"fullBudgetSeconds": 1}, checks=[
            {"id": "quick", "command": [sys.executable, "-c", "print('QUICK_STARTED')"], "inputs": []}])
        elapsed = result.public_elapsed_seconds
        assert result.returncode == 1, f"elapsed={elapsed:.2f}\n{result.stdout}\n{result.stderr}"
        assert "total_budget_timeout" in result.stdout + result.stderr
        assert "status: passed" not in result.stdout
        assert "QUICK_STARTED" not in result.stdout


    @pytest.mark.skipif(sys.platform != "win32", reason="Windows suspended-process ownership")
    def test_review_expired_windows_launch_is_never_resumed(self, tmp_path: Path, monkeypatch) -> None:
        import importlib.util
        package_root = candidate_for("build-and-verify").installed_package
        spec = importlib.util.spec_from_file_location("review_budget_runner", package_root / "python/build_and_verify_runner.py")
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        real_popen, real_job = subprocess.Popen, module._windows_job

        def delayed_popen(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            time.sleep(0.15)
            return process

        def observed_job(*args, **kwargs):
            job = real_job(*args, **kwargs)
            time.sleep(0.15)  # If resumed, the real process has time to expose the bug.
            return job

        monkeypatch.setattr(module.subprocess, "Popen", delayed_popen)
        monkeypatch.setattr(module, "_windows_job", observed_job)
        marker = tmp_path / "resumed.txt"
        control = module.RunControl(time.monotonic() + 0.05)
        with pytest.raises(module.TotalBudgetTimeout):
            module._managed_run([sys.executable, "-c",
                f"from pathlib import Path; Path({str(marker)!r}).write_text('started')"], control,
                text=True, timeout=3)
        assert not marker.exists(), "expired suspended process was resumed"


    @pytest.mark.parametrize("phase", ["probe", "entry"])
    def test_review_startup_reaps_descendants_after_parent_exits(self, tmp_path: Path, monkeypatch, phase: str) -> None:
        budget = 3
        descendant_sleep = 10
        wall_limit = 5
        startup = tmp_path / "startup"
        startup.mkdir()
        pids = tmp_path / "startup-pids.txt"
        condition = "sys.argv[0] == '-c'" if phase == "probe" else "sys.argv[0].endswith('build_and_verify.py')"
        (startup / "sitecustomize.py").write_text(
            "import subprocess,sys\nfrom pathlib import Path\n"
            f"if {condition}:\n"
            f"    child=subprocess.Popen([sys.executable,'-S','-c','import time; time.sleep({descendant_sleep})'])\n"
            f"    with Path({str(pids)!r}).open('a') as stream: stream.write(str(child.pid)+'\\n')\n"
            + ("    raise SystemExit(1)\n" if phase == "entry" else ""), encoding="utf-8")
        monkeypatch.setenv("PYTHONPATH", str(startup))
        result, _ = _budget_run(tmp_path, settings={"fullBudgetSeconds": budget}, checks=[
            {"id": "quick", "command": [sys.executable, "-c", "print('DONE')"], "inputs": []}])
        elapsed = result.public_elapsed_seconds
        assert result.returncode == 1, result.stdout + result.stderr
        assert elapsed < wall_limit, f"startup descendant held the public entry open for {elapsed:.2f}s"
        assert pids.exists(), result.stdout + result.stderr
        owned_pids = [int(pid) for pid in pids.read_text().splitlines()]
        try:
            for pid in owned_pids:
                _assert_pid_terminated(pid)
        finally:
            # Red runs let these known synthetic children finish naturally; never
            # terminate a PID after its owning parent has exited and released it.
            for pid in owned_pids:
                until = time.monotonic() + descendant_sleep + 1
                while time.monotonic() < until:
                    try:
                        _assert_pid_terminated(pid)
                        break
                    except AssertionError:
                        time.sleep(0.02)


    @pytest.mark.skipif(sys.platform != "win32", reason="Windows background-process compatibility")
    def test_review_budget_off_preserves_background_dependency(self, tmp_path: Path) -> None:
        pids = tmp_path / "background.pid"
        first = ("import subprocess,sys,time; from pathlib import Path; time.sleep(1.1); "
            "child=subprocess.Popen([sys.executable,'-S','-c','import time; time.sleep(.7)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
            f"Path({str(pids)!r}).write_text(str(child.pid))")
        second = ("import ctypes; from pathlib import Path\n"
            f"pid=int(Path({str(pids)!r}).read_text())\n"
            "kernel=ctypes.WinDLL('kernel32',use_last_error=True)\n"
            "kernel.OpenProcess.restype=ctypes.c_void_p\n"
            "kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]\n"
            "kernel.CloseHandle.argtypes=[ctypes.c_void_p]\n"
            "handle=kernel.OpenProcess(0x1000,False,pid)\n"
            "assert handle,'background dependency was terminated'\n"
            "code=ctypes.c_ulong()\n"
            "assert kernel.GetExitCodeProcess(handle,ctypes.byref(code))\n"
            "kernel.CloseHandle(handle)\n"
            "assert code.value==259,'background dependency was terminated'\n")
        result, _ = _budget_run(tmp_path, settings={"fullBudgetSeconds": 1, "enforceLocalBudget": False}, checks=[
            {"id": "start", "command": [sys.executable, "-c", first], "inputs": []},
            {"id": "use", "command": [sys.executable, "-c", second], "inputs": []}])
        try:
            assert result.returncode == 0, result.stdout + result.stderr
            assert "performance-warning:" in result.stdout
        finally:
            if pids.exists():
                until = time.monotonic() + 2
                while time.monotonic() < until:
                    try:
                        _assert_pid_terminated(int(pids.read_text()))
                        break
                    except AssertionError:
                        time.sleep(0.02)


    def test_packed_runtime_guard_initialization_and_explicit_migration(self, tmp_path: Path) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        env = _isolated_env(tmp_path, prefix)
        project = tmp_path / "project"
        initialized = subprocess.run([executable, "init", "--project", str(project)],
            env=env, text=True, capture_output=True, check=False)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        config_path = project / ".build-and-verify/config.json"
        assert json.loads(config_path.read_text()) == {
            "version": 2, "build": {"checks": []},
            "verify": {"realChecks": [], "checks": []}}
        config_path.write_text(json.dumps({"version": 2, "build": {"checks": [
            {"id": "build.memory", "command": [sys.executable, "-c", "print('PACKED_BUILD_OK')"], "inputs": []}]},
            "verify": {"realChecks": [], "checks": []}}))
        built = subprocess.run([executable, "build", "--project", str(project)],
            env=env, text=True, capture_output=True, check=False)
        assert built.returncode == 0, built.stdout + built.stderr
        assert "checked: build.memory" in built.stdout and "PACKED_BUILD_OK" in built.stdout
        legacy = {"version": 1, "verify": {"checks": [
            {"id": "ordinary", "command": [sys.executable, "ordinary.py"], "inputs": ["ordinary.py"]}]}}
        config_path.write_text(json.dumps(legacy))
        (project / "ordinary.py").write_text("from pathlib import Path\nPath('effect').write_text('legacy')\n")
        def verify():
            return subprocess.run([executable, "verify", "--project", str(project),
                "--execution-context", "cloud"], env=env, text=True, capture_output=True, check=False)
        old = verify()
        assert old.returncode == 0, old.stdout + old.stderr
        assert "legacy-unprotected" in old.stdout
        assert (project / "effect").read_text() == "legacy"
        (project / "effect").unlink()
        confirmed = tmp_path / "confirmed.json"
        confirmed.write_text(json.dumps({**legacy, "version": 2,
            "verify": {**legacy["verify"], "realChecks": []}}))
        migrated = subprocess.run([executable, "init", "--project", str(project),
            "--config", str(confirmed), "--overwrite"], env=env, text=True, capture_output=True, check=False)
        assert migrated.returncode == 0, migrated.stdout + migrated.stderr
        backups = list((project / ".build-and-verify/backups").glob("config-*.json"))
        assert len(backups) == 1 and json.loads(backups[0].read_text()) == legacy
        blocked = verify()
        assert blocked.returncode != 0, blocked.stdout + blocked.stderr
        assert "runtime_guard_violation" in blocked.stderr
        assert not (project / "effect").exists()
        # The same unprotected real success must never become ordinary evidence.
        real_config = json.loads(confirmed.read_text())
        real_config["verify"]["realChecks"] = ["ordinary"]
        config_path.write_text(json.dumps(real_config))
        real = verify()
        assert real.returncode == 0, real.stdout + real.stderr
        assert (project / "effect").read_text() == "legacy"
        (project / "effect").unlink()
        config_path.write_text(confirmed.read_text())
        protected_again = verify()
        assert protected_again.returncode == 1
        assert "cache-hit:" not in protected_again.stdout
        assert not (project / "effect").exists()
        restored = subprocess.run([executable, "init", "--project", str(project),
            "--config", str(backups[0]), "--overwrite"], env=env, text=True, capture_output=True, check=False)
        assert restored.returncode == 0, restored.stdout + restored.stderr
        assert json.loads(config_path.read_text()) == legacy
        assert json.loads(backups[0].read_text()) == legacy
        reverted = verify()
        assert reverted.returncode == 0, reverted.stdout + reverted.stderr
        assert "legacy-unprotected" in reverted.stdout
        (project / "ordinary.py").write_text(
            "import importlib\n"
            "try:\n"
            " db=importlib.import_module('duckdb')\n"
            " assert db.connect(':memory:').execute('select 42').fetchone() == (42,)\n"
            "except ImportError: pass\n")
        config_path.write_text(confirmed.read_text())
        unsupported_native = verify()
        assert unsupported_native.returncode == 1, unsupported_native.stdout + unsupported_native.stderr
        assert "runtime_guard_uncovered_native" in unsupported_native.stderr
        (project / "ordinary.py").write_text(
            "import duckdb\n"
            "connection=duckdb.connect(':memory:')\n"
            "assert connection.execute('select 42').fetchone() == (42,)\n"
            "connection.close()\n"
            "print('DUCKDB_QUERY_OK')\n")
        config_path.write_text(json.dumps(real_config))
        native_real = verify()
        assert native_real.returncode == 0, native_real.stdout + native_real.stderr
        assert "real-unprotected" in native_real.stdout
        assert "DUCKDB_QUERY_OK" in native_real.stdout
        (project / "ordinary.py").write_text(
            "import sqlite3\n"
            "class Custom(sqlite3.Connection): pass\n"
            "c=sqlite3.connect(':memory:', factory=Custom)\n"
            "seen=[]\n"
            "def authorize(action, *args):\n"
            " seen.append(action)\n"
            " return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_SELECT else sqlite3.SQLITE_OK\n"
            "c.set_authorizer(authorize)\n"
            "try: c.execute('select 1')\n"
            "except sqlite3.DatabaseError: pass\n"
            "else: raise AssertionError('business authorizer was lost')\n"
            "assert sqlite3.SQLITE_SELECT in seen\n"
            "c.set_authorizer(None)\n"
            "assert c.execute('select 42').fetchone() == (42,)\n"
            "assert c.execute('pragma temp_store').fetchone() == (2,)\n"
            "for sql in [\"ATTACH DATABASE 'sqlite-effect' AS bad\", \"VACUUM INTO 'sqlite-vacuum'\", 'PRAGMA temp_store=FILE']:\n"
            " try: c.execute(sql)\n"
            " except sqlite3.DatabaseError: pass\n"
            "print('SQLITE_CALLBACKS_OK')\n")
        config_path.write_text(confirmed.read_text())
        sqlite = verify()
        assert sqlite.returncode == 1, sqlite.stdout + sqlite.stderr
        assert "SQLITE_CALLBACKS_OK" in sqlite.stdout
        assert "sqlite3.authorizer" in sqlite.stderr
        assert not (project / "sqlite-effect").exists()
        assert not (project / "sqlite-vacuum").exists()
        import sqlite3
        with sqlite3.connect(str(project / "readonly.db")) as fixture:
            fixture.execute("create table values_for_reading(value)")
            fixture.execute("insert into values_for_reading values (42)")
        (project / "ordinary.py").write_text(
            "import sqlite3\n"
            "c=sqlite3.connect('file:readonly.db?mode=ro', uri=True)\n"
            "assert c.execute('select value from values_for_reading').fetchall() == [(42,)]\n"
            "assert c.execute('pragma table_info(values_for_reading)').fetchone()[1] == 'value'\n"
            "try: c.execute('insert into values_for_reading values (99)')\n"
            "except sqlite3.DatabaseError: pass\n"
            "print('SQLITE_READONLY_OK')\n")
        readonly = verify()
        assert readonly.returncode == 1, readonly.stdout + readonly.stderr
        assert "SQLITE_READONLY_OK" in readonly.stdout
        assert "sqlite3.authorizer" in readonly.stderr
        with sqlite3.connect(str(project / "readonly.db")) as fixture:
            assert fixture.execute("select value from values_for_reading").fetchall() == [(42,)]
        (project / "app.py").write_text("def answer(): return 42\n")
        (project / "tests").mkdir()
        (project / "tests/test_app.py").write_text(
            "import os\nfrom app import answer\n"
            "def test_app():\n"
            " assert answer() == 42\n"
            " with open(os.devnull, 'w') as sink: sink.write('discarded')\n"
            " if os.name == 'nt':\n"
            "  with open(r'\\\\.\\NuL', 'w') as sink: sink.write('discarded')\n")
        config_path.write_text(json.dumps({"version": 2, "verify": {"realChecks": [], "checks": [
            {"id": "app", "command": [sys.executable, "-m", "pytest", "-q", "tests/test_app.py"],
             "inputs": ["app.py", "tests/test_app.py"]}]}}))
        app = verify()
        assert app.returncode == 0, app.stdout + app.stderr
        assert "1 passed" in app.stdout
        # Cross-platform event contract only, not a real Windows application launch.
        (project / "ordinary.py").write_text(
            "import os, sys\n"
            "for event, args in [('os.startfile', ('never-open', 'open')), ('os.startfile/2', ('never-open', 'open', None, None, 1))]:\n"
            " try: sys.audit(event, *args)\n"
            " except PermissionError: pass\n"
            "for path in [r'\\\\.\\nul-other', r'\\\\.\\nul\\effect', r'\\\\.\\C:', r'\\\\?\\nul']:\n"
            " try: sys.audit('open', path, 'w', os.O_WRONLY | os.O_CREAT)\n"
            " except PermissionError: pass\n"
            " else: raise AssertionError('device path was allowed: ' + path)\n"
            "print('WINDOWS_EVENTS_HANDLED')\n")
        config_path.write_text(confirmed.read_text())
        windows_events = verify()
        assert windows_events.returncode == 1, windows_events.stdout + windows_events.stderr
        assert "WINDOWS_EVENTS_HANDLED" in windows_events.stdout
        assert "os.startfile " in windows_events.stderr and "os.startfile/2 " in windows_events.stderr
        if sys.platform == "linux":
            (project / "ordinary.py").write_text(
                "import os\n"
                "for name in ('mkfifo', 'mknod'):\n"
                " try: getattr(os, name)(name + '-effect')\n"
                " except PermissionError: pass\n"
                "print('UNIX_CREATION_HANDLED')\n")
            unix_creation = verify()
            assert unix_creation.returncode == 1, unix_creation.stdout + unix_creation.stderr
            assert "UNIX_CREATION_HANDLED" in unix_creation.stdout
            for name in ("mkfifo", "mknod"):
                assert "os." + name in unix_creation.stderr
                assert not (project / (name + "-effect")).exists()
        (project / "mixed.py").write_text(
            "import json, sys, time\nfrom pathlib import Path\n"
            "role=sys.argv[1]; started=time.monotonic(); time.sleep(0.4)\n"
            "try: Path(role + '-effect').write_text(role)\n"
            "except PermissionError: pass\n"
            "time.sleep(0.2)\n"
            "print('MIXED:' + json.dumps({'role': role, 'started': started, 'finished': time.monotonic()}))\n")
        config_path.write_text(json.dumps({"version": 2, "verify": {"realChecks": ["real"], "maxParallel": 2,
            "checks": [{"id": role, "command": [sys.executable, "mixed.py", role],
                        "checkParallel": True, "inputs": ["mixed.py"]} for role in ("real", "ordinary")]}}))
        mixed = verify()
        assert mixed.returncode == 1, mixed.stdout + mixed.stderr
        assert (project / "real-effect").read_text() == "real"
        assert not (project / "ordinary-effect").exists()
        assert "runtime_guard_violation" in mixed.stderr
        intervals = [json.loads(line.removeprefix("MIXED:")) for line in mixed.stdout.splitlines() if line.startswith("MIXED:")]
        assert {interval["role"] for interval in intervals} == {"real", "ordinary"}
        assert max(interval["started"] for interval in intervals) < min(interval["finished"] for interval in intervals)


    def test_packed_runtime_guard_preserves_pytest_workers_and_control_hooks(self, tmp_path: Path) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        env = {**_isolated_env(tmp_path, prefix), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTEST_ADDOPTS": "-n 2"}
        project = tmp_path / "project"
        (project / ".build-and-verify").mkdir(parents=True)
        (project / "test_memory.py").write_text(
            "import sqlite3, unittest, time\n"
            "class Memory(unittest.TestCase):\n"
            " def test_read_and_memory(self):\n"
            "  time.sleep(0.6)\n"
            "  self.assertEqual(open('data.txt').read(), 'READABLE')\n"
            "  self.assertEqual(sqlite3.connect(':memory:').execute('select 42').fetchone(), (42,))\n"
            "def test_second():\n time.sleep(0.6)\n assert sum([1, 2, 3]) == 6\n")
        (project / "conftest.py").write_text(
            "import os, time, pytest\nintervals=[]\n"
            "@pytest.hookimpl(hookwrapper=True)\n"
            "def pytest_runtest_call(item):\n"
            " start=time.monotonic(); yield\n"
            " item.user_properties.append(('execution', (os.getpid(), start, time.monotonic())))\n"
            "def pytest_runtest_logreport(report):\n"
            " if report.when == 'call': intervals.extend(v for k,v in report.user_properties if k == 'execution')\n"
            "def pytest_sessionfinish(session):\n"
            " if not hasattr(session.config, 'workerinput'):\n"
            "  assert len({x[0] for x in intervals}) == 2\n"
            "  assert max(x[1] for x in intervals) < min(x[2] for x in intervals)\n")
        (project / "data.txt").write_text("READABLE")
        config = {"version": 2, "verify": {"realChecks": [], "maxParallel": 2, "checks": [
            {"id": name, "command": [sys.executable, "-m", "pytest", "-q", "-p", "xdist.plugin", "test_memory.py"],
             "checkParallel": True, "inputs": ["test_memory.py", "data.txt", "conftest.py"]}
            for name in ("memory-a", "memory-b")]}}
        config_path = project / ".build-and-verify/config.json"
        config_path.write_text(json.dumps(config))
        def verify():
            return subprocess.run([executable, "verify", "--project", str(project), "--execution-context", "cloud"],
                env=env, text=True, capture_output=True, check=False, timeout=25)
        allowed = verify()
        assert allowed.returncode == 0, allowed.stdout + allowed.stderr
        assert allowed.stdout.count("2 passed") == 2
        proofs = [json.loads(line.removeprefix("runtime-guard: ")) for line in allowed.stdout.splitlines()
                  if line.startswith("runtime-guard: ")]
        assert len(proofs) == 2 and all(proof["workers"] == 2 for proof in proofs)
        assert max(proof["started"] for proof in proofs) < min(proof["finished"] for proof in proofs)
        (project / "conftest.py").write_text(
            "import os, subprocess, sys, threading, execnet\n"
            "def attempt():\n"
            " try: subprocess.run([sys.executable, '-c', 'print(123)'])\n"
            " except PermissionError: pass\n"
            "def pytest_configure(config):\n"
            " if not hasattr(config, 'workerinput'):\n"
            "  t=threading.Thread(target=attempt); t.start(); t.join()\n"
            "  try:\n"
            "   group=execnet.Group(); group.makegateway('popen'); group.terminate()\n"
            "  except PermissionError: pass\n")
        blocked = verify()
        assert blocked.returncode != 0, blocked.stdout + blocked.stderr
        assert "runtime_guard_violation:" in blocked.stderr and "subprocess.Popen" in blocked.stderr
        assert "runtime_guard_uncovered_worker" in blocked.stderr
        assert "cache-hit:" not in blocked.stdout
        (project / "conftest.py").write_text("")
        (project / "test_memory.py").write_text(
            "from pathlib import Path\nimport pytest, socket, subprocess, sys, threading\n"
            "def denied(action):\n"
            " try: action()\n"
            " except PermissionError: return\n"
            " raise AssertionError('effect was not rejected')\n"
            "def write(phase): denied(lambda: Path(phase).write_text('forbidden'))\n"
            "write('import-effect')\n"
            "@pytest.fixture(autouse=True)\n"
            "def effects():\n"
            " write('setup-effect'); denied(socket.socket)\n"
            " yield\n"
            " write('teardown-effect'); denied(lambda: subprocess.Popen([sys.executable, '-c', 'pass']))\n"
            "def test_effects():\n"
            " write('body-effect')\n"
            " t=threading.Thread(target=lambda: write('thread-effect')); t.start(); t.join()\n")
        effects = verify()
        assert effects.returncode == 1, effects.stdout + effects.stderr
        for phase in ("import", "setup", "body", "teardown", "thread"):
            assert phase + "-effect" in effects.stderr
            assert not (project / (phase + "-effect")).exists()
        assert "socket.__new__" in effects.stderr
        assert "subprocess.Popen" in effects.stderr
        (project / "conftest.py").write_text(
            "import os\nfrom pathlib import Path\n"
            "if os.environ.get('PYTEST_XDIST_WORKER') not in (None, 'gw0', 'gw1'):\n"
            " try: Path('restart-effect').write_text('forbidden')\n"
            " except PermissionError: pass\n")
        (project / "test_memory.py").write_text(
            "import os\n"
            "def run():\n"
            " if os.environ.get('PYTEST_XDIST_WORKER') == 'gw0': os._exit(0)\n"
            "def test_first(): run()\n"
            "def test_second(): run()\n")
        restarted = verify()
        assert restarted.returncode == 1, restarted.stdout + restarted.stderr
        assert "runtime_guard_evidence_incomplete" in restarted.stderr
        assert "restart-effect" in restarted.stderr
        assert not (project / "restart-effect").exists()


    def test_packed_node_runtime_guard_direct_script(self, tmp_path: Path) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        localized_prefix = tmp_path / "中文 安装目录"
        shutil.copytree(prefix, localized_prefix, symlinks=True)
        prefix = localized_prefix
        executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")
        env = _isolated_env(tmp_path, prefix)
        project = tmp_path / "project"
        (project / ".build-and-verify").mkdir(parents=True)
        script = project / "direct.cjs"
        config = {"version": 2, "verify": {"realChecks": [], "checks": [
            {"id": "node-memory", "command": [shutil.which("node"), "direct.cjs"], "inputs": ["direct.cjs"]}]}}
        (project / ".build-and-verify/config.json").write_text(json.dumps(config))
        script.write_text("const fs = require('node:fs');\n"
            "try { fs.writeFileSync('node-effect', 'forbidden'); } catch {}\n"
            "console.log('CAUGHT_AND_RETURNED_SUCCESS');\n")
        blocked = subprocess.run([executable, "verify", "--project", str(project), "--execution-context", "cloud"],
            env=env, text=True, capture_output=True, check=False, timeout=20)
        assert blocked.returncode == 1, blocked.stdout + blocked.stderr
        assert "CAUGHT_AND_RETURNED_SUCCESS" in blocked.stdout
        assert "runtime_guard_violation" in blocked.stderr
        assert not (project / "node-effect").exists()
        assert not list((project / ".build-and-verify/cache").glob("*.json"))
        config["verify"]["realChecks"] = ["node-memory"]
        (project / ".build-and-verify/config.json").write_text(json.dumps(config))
        real = subprocess.run([executable, "verify", "--project", str(project), "--execution-context", "cloud"],
            env=env, text=True, capture_output=True, check=False, timeout=20)
        assert real.returncode == 0, real.stdout + real.stderr
        assert "real-unprotected" in real.stdout and (project / "node-effect").read_text() == "forbidden"
        (project / "node-effect").unlink()
        config["verify"]["realChecks"] = []
        (project / ".build-and-verify/config.json").write_text(json.dumps(config))
        (project / "data.txt").write_text("READABLE")
        script.write_text("const assert = require('node:assert/strict');\n"
            "const fs = require('node:fs'); const cp = require('node:child_process');\n"
            "const net = require('node:net'); const {Worker} = require('node:worker_threads');\n"
            "function denied(fn) { assert.throws(fn, {code:'ERR_TEST_RUNTIME_GUARD'}); }\n"
            "assert.equal(fs.readFileSync('data.txt', 'utf8'), 'READABLE');\n"
            "assert.equal([1,2,3].reduce((a,b)=>a+b), 6);\n"
            "denied(() => cp.spawnSync(process.execPath, ['-e','0']));\n"
            "denied(() => new cp.ChildProcess().spawn({file:process.execPath,args:[process.execPath,'-e','0']}));\n"
            "denied(() => net.connect(9, '127.0.0.1'));\n"
            "denied(() => fs.openSync('open-effect', 'w'));\n"
            "denied(() => fs.mkdirSync('directory-effect'));\n"
            "denied(() => fs.renameSync('data.txt', 'renamed-effect'));\n"
            "(async () => {\n"
            " await assert.rejects(async () => fs.promises.writeFile('promise-effect', 'bad'), {code:'ERR_TEST_RUNTIME_GUARD'});\n"
            " const worker = new Worker(`const {parentPort}=require('node:worker_threads');\n"
            " const fs=require('node:fs'); try { fs.writeFileSync('thread-effect','bad'); } catch {}\n"
            " const db=new (require('node:sqlite').DatabaseSync)(':memory:');\n"
            " require('node:assert/strict').equal(db.prepare('select 42 as v').get().v,42);\n"
            " parentPort.postMessage(fs.readFileSync('data.txt','utf8'));`, {eval:true,execArgv:[],env:{}});\n"
            " worker.on('message', (value) => assert.equal(value, 'READABLE'));\n"
            " await new Promise((resolve,reject) => { worker.on('exit',resolve);worker.on('error',reject); });\n"
            " console.log('DIRECT_READ_MEMORY_THREAD_OK');\n"
            "})().catch(e => { console.error(e); process.exitCode=1; });\n")
        effects = subprocess.run([executable, "verify", "--project", str(project), "--execution-context", "cloud"],
            env=env, text=True, capture_output=True, check=False, timeout=20)
        assert effects.returncode == 1, effects.stdout + effects.stderr
        assert "DIRECT_READ_MEMORY_THREAD_OK" in effects.stdout, effects.stdout + effects.stderr
        for operation in ("spawnSync", "ChildProcess", "net.connect", "fs.openSync", "fs.mkdirSync", "fs.renameSync", "fs.promises.writeFile"):
            assert operation in effects.stderr
        assert "thread-effect" in effects.stderr
        for effect in ("open-effect", "directory-effect", "renamed-effect", "promise-effect", "thread-effect"):
            assert not (project / effect).exists()
        script.write_text("process.on('exit',()=>{\n"
            " try {require('node:fs').writeFileSync('exit-effect','bad');}catch {}\n"
            " console.log('EXIT_CLEANUP_CAUGHT');\n});\n")
        cleanup = subprocess.run([executable, "verify", "--project", str(project), "--execution-context", "cloud"],
            env=env, text=True, capture_output=True, check=False, timeout=20)
        assert cleanup.returncode == 1, cleanup.stdout + cleanup.stderr
        assert "EXIT_CLEANUP_CAUGHT" in cleanup.stdout
        assert "exit-effect" in cleanup.stderr
        assert not (project / "exit-effect").exists()


    def test_packed_node_runtime_guard_native_parallel_and_control(self, tmp_path: Path) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        env = _isolated_env(tmp_path, prefix)
        project = tmp_path / "project"
        (project / ".build-and-verify").mkdir(parents=True)
        (project / "data.txt").write_text("READABLE")
        for name in ("first", "second"):
            (project / f"{name}.test.mjs").write_text(
                "import test from 'node:test'; import assert from 'node:assert/strict';\n"
                "import {readFileSync} from 'node:fs';\n"
                "import {DatabaseSync} from 'node:sqlite';\n"
                "test('memory', async () => {\n"
                " const started=Number(process.hrtime.bigint())/1e9;\n"
                " assert.equal(readFileSync('data.txt','utf8'), 'READABLE');\n"
                " assert.equal(new DatabaseSync(':memory:').prepare('select 42 as v').get().v,42);\n"
                " await new Promise(resolve=>setTimeout(resolve, 600));\n"
                " console.log('NODE_INTERVAL:' + JSON.stringify({pid:process.pid,started,finished:Number(process.hrtime.bigint())/1e9}));\n"
                "});\n")
        (project / "memory-control.cjs").write_text(
            "const {Worker,isMainThread}=require('node:worker_threads');\n"
            "if(isMainThread && !process.env.NODE_TEST_CONTEXT) {\n"
            " new Worker(`require('node:worker_threads').parentPort.postMessage(42)`,{eval:true,env:{}})\n"
            " .on('message',value=>{require('node:assert/strict').equal(value,42);console.log('CONTROL_THREAD_OK');});}\n")
        config = {"version": 2, "verify": {"realChecks": [], "maxParallel": 2, "checks": [
            {"id": name, "command": [shutil.which("node"), "--test", "--test-concurrency=2", "--test-reporter=tap", "--require", "./memory-control.cjs",
                "first.test.mjs", "second.test.mjs"], "checkParallel": True,
             "inputs": ["first.test.mjs", "second.test.mjs", "data.txt", "memory-control.cjs"]} for name in ("node-a", "node-b")]}}
        config_path = project / ".build-and-verify/config.json"
        config_path.write_text(json.dumps(config))
        def verify():
            return subprocess.run([executable, "verify", "--project", str(project), "--execution-context", "cloud"],
                env=env, text=True, capture_output=True, check=False, timeout=25)
        allowed = verify()
        assert allowed.returncode == 0, allowed.stdout + allowed.stderr
        assert allowed.stdout.count("CONTROL_THREAD_OK") == 2
        intervals = [json.loads(line.split("NODE_INTERVAL:", 1)[1]) for line in allowed.stdout.splitlines()
                     if "NODE_INTERVAL:" in line]
        assert len(intervals) == 4 and len({item["pid"] for item in intervals}) == 4
        assert max(item["started"] for item in intervals) < min(item["finished"] for item in intervals)
        proofs = [json.loads(line.removeprefix("runtime-guard: ")) for line in allowed.stdout.splitlines()
                  if line.startswith("runtime-guard: ")]
        assert len(proofs) == 2 and all(proof["workers"] == 3 for proof in proofs)
        (project / "control.cjs").write_text(
            "const assert=require('node:assert/strict'); const cp=require('node:child_process');\n"
            "const fs=require('node:fs');\n"
            "assert.throws(()=>cp.spawn(process.execPath,['-e','0']),{code:'ERR_TEST_RUNTIME_GUARD'});\n"
            "try {fs.writeFileSync('control-effect','bad');} catch {}\n"
            "console.log('CONTROL_CALLBACK_PROTECTED');\n")
        config["verify"]["checks"] = [{"id": "node-control", "command": [shutil.which("node"), "--test",
            "--require", "./control.cjs", "first.test.mjs"],
            "inputs": ["control.cjs", "first.test.mjs"]}]
        config_path.write_text(json.dumps(config))
        blocked = verify()
        assert blocked.returncode == 1, blocked.stdout + blocked.stderr
        assert "CONTROL_CALLBACK_PROTECTED" in blocked.stdout
        assert "child_process.spawn" in blocked.stderr and "control-effect" in blocked.stderr
        assert not (project / "control-effect").exists()
        (project / "control.cjs").write_text(
            "const test=require('node:test');\n"
            "try { test.run({files:['first.test.mjs']}); } catch {}\n"
            "console.log('FRAMEWORK_CHANNEL_ATTEMPTED');\n")
        escaped = verify()
        assert escaped.returncode == 1, escaped.stdout + escaped.stderr
        assert "FRAMEWORK_CHANNEL_ATTEMPTED" in escaped.stdout
        assert "runtime_guard_uncovered_worker" in escaped.stderr
        (project / "effects.cjs").write_text(
            "const fs=require('node:fs');module.exports=(phase)=>{try {fs.writeFileSync(phase+'-effect','bad');}catch {}};\n"
            "module.exports('import');\n")
        (project / "first.test.mjs").write_text(
            "import test,{beforeEach,afterEach} from 'node:test';import effect from './effects.cjs';\n"
            "beforeEach(()=>effect('setup'));afterEach(()=>effect('teardown'));\n"
            "test('effect handling',()=>{effect('body');console.log('ALL_PHASES_CAUGHT');});\n")
        config["verify"]["checks"] = [{"id": "phases", "command": [shutil.which("node"), "--test", "first.test.mjs"],
            "inputs": ["first.test.mjs", "effects.cjs"]}]
        config_path.write_text(json.dumps(config))
        phases = verify()
        assert phases.returncode == 1, phases.stdout + phases.stderr
        assert "ALL_PHASES_CAUGHT" in phases.stdout
        for phase in ("import", "setup", "body", "teardown"):
            assert phase + "-effect" in phases.stderr
            assert not (project / (phase + "-effect")).exists()


    def test_packed_node_runtime_guard_mixed_commands_and_restarts(self, tmp_path: Path) -> None:
        import threading
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        env = _isolated_env(tmp_path, prefix)
        project = tmp_path / "project with space"
        (project / ".build-and-verify").mkdir(parents=True)
        (project / "logic.py").write_text("import os,sys\nassert os.environ['MIXED_VALUE']=='two words'\n"
            "assert sys.argv[1:] == ['argument with space']\nprint('PYTHON_SEGMENT_OK')\n")
        (project / "direct script.mjs").write_text("import assert from 'node:assert/strict';\n"
            "assert.equal(process.env.MIXED_VALUE, 'two words');\n"
            "assert.deepEqual(process.argv.slice(2), ['argument with space']);console.log('NODE_SEGMENT_OK');\n")
        assignment = 'set MIXED_VALUE=two words&&' if os.name == 'nt' else 'MIXED_VALUE="two words" '
        python = f'{assignment}"{sys.executable}" logic.py "argument with space"'
        node = f'{assignment}"{shutil.which("node")}" "direct script.mjs" "argument with space"'
        config = {"version": 2, "verify": {"realChecks": [], "checks": [
            {"id": "mixed", "command": python + '&&' + node, "inputs": ["logic.py", "direct script.mjs"]}]}}
        path = project / ".build-and-verify/config.json"
        path.write_text(json.dumps(config))
        def verify():
            return subprocess.run([executable, "verify", "--project", str(project), "--execution-context", "cloud"],
                env=env, text=True, capture_output=True, check=False, timeout=15)
        allowed = verify()
        assert allowed.returncode == 0, allowed.stdout + allowed.stderr
        assert "PYTHON_SEGMENT_OK" in allowed.stdout and "NODE_SEGMENT_OK" in allowed.stdout
        (project / "logic.py").write_text("from pathlib import Path\n"
            "try: Path('mixed-effect').write_text('bad')\nexcept PermissionError: pass\nprint('FIRST_SEGMENT_CAUGHT')\n")
        denied_first = verify()
        assert denied_first.returncode == 1, denied_first.stdout + denied_first.stderr
        assert "FIRST_SEGMENT_CAUGHT" in denied_first.stdout
        assert "NODE_SEGMENT_OK" not in denied_first.stdout
        assert not (project / "mixed-effect").exists()
        (project / "logic.py").write_text("raise SystemExit(7)\n")
        stopped = verify()
        assert stopped.returncode == 1, stopped.stdout + stopped.stderr
        assert "NODE_SEGMENT_OK" not in stopped.stdout
        assert "runtime_guard_evidence_incomplete" in stopped.stderr
        # Native watch restarts are driven externally, never by allowing test writes.
        watched = project / "restart.test.cjs"
        (project / "watch-control.cjs").write_text("console.log('WATCH_PID:'+process.pid);\n")
        watched.write_text("require('node:test')('before restart',()=>{});\n")
        config["verify"]["checks"] = [{"id": "restart", "command": [shutil.which("node"), "--test", "--watch", "--require", "./watch-control.cjs",
            "--test-reporter=tap", "restart.test.cjs"], "timeoutSeconds": 3, "inputs": ["restart.test.cjs"]}]
        path.write_text(json.dumps(config))
        watch_temp = tmp_path / "watch-temp"
        watch_temp.mkdir()
        env.update({key: str(watch_temp) for key in ("TMPDIR", "TMP", "TEMP")})
        finished = threading.Event()
        changed = threading.Event()
        def change_watched_file():
            # The runner buffers test output. Observe its existing read-only evidence
            # instead of racing startup or allowing ordinary tests a ready-file write.
            while not finished.wait(0.01):
                for evidence in watch_temp.glob("build-and-verify-guard-*/events.jsonl"):
                    try:
                        records = [json.loads(line) for line in evidence.read_text().splitlines()]
                    except (FileNotFoundError, json.JSONDecodeError):
                        continue  # Concurrent append or cleanup, never a ready signal.
                    workers = {item['unit'] for item in records if item['event'] == 'start' and item.get('role') == 'worker'}
                    if any(item['event'] == 'finish' and item['unit'] in workers for item in records):
                        watched.write_text("const fs=require('node:fs');try {fs.writeFileSync('restart-effect','bad');}catch {}\n"
                            "console.log('RESTART_IMPORT_PROTECTED');require('node:test')('after restart',()=>{});\n")
                        changed.set()
                        return
        updater = threading.Thread(target=change_watched_file)
        updater.start()
        try:
            restarted = verify()
        finally:
            finished.set()
            updater.join()
        assert restarted.returncode == 1, restarted.stdout + restarted.stderr
        assert changed.is_set(), restarted.stdout + restarted.stderr
        assert "before restart" in restarted.stdout, restarted.stdout + restarted.stderr
        assert "RESTART_IMPORT_PROTECTED" in restarted.stdout, restarted.stdout + restarted.stderr
        assert "check_timeout" in restarted.stderr
        assert not (project / "restart-effect").exists()
        owned = {int(line.split('WATCH_PID:', 1)[1]) for line in restarted.stdout.splitlines() if 'WATCH_PID:' in line}
        assert len(owned) >= 3, restarted.stdout
        for pid in owned:
            _assert_pid_terminated(pid)
        assert not any(json.loads(item.read_text())["id"] == "restart" for item in (project / ".build-and-verify/cache").glob("*.json"))


    def test_packed_runtime_guard_sqlite_native_file_boundaries(self, tmp_path: Path) -> None:
        import sqlite3
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        env = _isolated_env(tmp_path, prefix)
        project = tmp_path / "project"
        (project / ".build-and-verify").mkdir(parents=True)
        with sqlite3.connect(project / "readonly.db") as fixture:
            fixture.execute("create table values_for_reading(value)")
            fixture.execute("insert into values_for_reading values (42)")
        script = project / "sqlite.mjs"
        config = {"version": 2, "verify": {"realChecks": [], "checks": [
            {"id": "sqlite-node", "command": [shutil.which("node"), "sqlite.mjs"],
             "inputs": ["sqlite.mjs", "readonly.db"]}]}}
        path = project / ".build-and-verify/config.json"
        path.write_text(json.dumps(config))
        def verify():
            return subprocess.run([executable, "verify", "--project", str(project), "--execution-context", "cloud"],
                env=env, text=True, capture_output=True, check=False, timeout=20)
        script.write_text("import sqlite,{DatabaseSync} from 'node:sqlite';import assert from 'node:assert/strict';\n"
            "assert.equal(sqlite.DatabaseSync,DatabaseSync);\n"
            "const db=new DatabaseSync(':memory:',{open:false});db.open();\n"
            "db.exec('create table t(value);insert into t values (42)');\n"
            "let seen=0;db.setAuthorizer((action)=>{seen++;return action===sqlite.constants.SQLITE_SELECT?sqlite.constants.SQLITE_DENY:sqlite.constants.SQLITE_OK;});\n"
            "assert.throws(()=>db.prepare('select value from t'));assert.ok(seen>0);db.setAuthorizer(null);\n"
            "assert.equal(db.prepare('select value from t').get().value,42);\n"
            "const bytes=db.serialize();const clone=new DatabaseSync(':memory:');\n"
            "clone.setAuthorizer(action=>action===sqlite.constants.SQLITE_SELECT?sqlite.constants.SQLITE_DENY:sqlite.constants.SQLITE_OK);\n"
            "clone.deserialize(bytes);assert.throws(()=>clone.prepare('select value from t'));clone.setAuthorizer(null);\n"
            "assert.equal(clone.prepare('select value from t').get().value,42);\n"
            "assert.equal(clone.prepare('pragma temp_store').get().temp_store,2);\n"
            "db.close();db.open();assert.equal(db.prepare('select 7 as v').get().v,7);\n"
            "const reader=new DatabaseSync('readonly.db',{readOnly:true,open:false});reader.open();\n"
            "assert.equal(reader.prepare('select value from values_for_reading').get().value,42);reader.close();\n"
            "console.log('NODE_SQLITE_MEMORY_CALLBACK_REOPEN_READ_OK');\n")
        allowed = verify()
        assert allowed.returncode == 0, allowed.stdout + allowed.stderr
        assert "NODE_SQLITE_MEMORY_CALLBACK_REOPEN_READ_OK" in allowed.stdout
        script.write_text("import sqlite from 'node:sqlite';\n"
            "const db=new sqlite.DatabaseSync(':memory:',{open:false});db.open();\n"
            "db.exec('create table t(value)');const clone=new sqlite.DatabaseSync(':memory:');clone.deserialize(db.serialize());\n"
            "try{clone.exec(\"ATTACH DATABASE 'x' AS after_deserialize\")}catch{}\n"
            "for(const sql of [\"ATTACH DATABASE 'attach-effect' AS bad\",\"VACUUM INTO 'vacuum-effect'\",'PRAGMA temp_store=FILE']){try{db.exec(sql)}catch{}}\n"
            "try{new sqlite.DatabaseSync('constructor-effect')}catch{}\n"
            "const options={open:false};const lazy=new sqlite.DatabaseSync('lazy-effect',options);options.readOnly=true;try{lazy.open()}catch{}\n"
            "try{db.loadExtension('extension-effect')}catch{}\n"
            "try{await sqlite.backup(db,'backup-effect')}catch{}\n"
            "db.setAuthorizer(null);try{db.exec(\"ATTACH DATABASE 'callback-effect' AS bad2\")}catch{}\n"
            "db.close();db.open();try{db.exec(\"VACUUM INTO 'reopen-effect'\")}catch{}\n"
            "const reader=new sqlite.DatabaseSync('readonly.db',{readOnly:true});try{reader.exec('insert into values_for_reading values (99)')}catch{}\n"
            "console.log('NODE_SQLITE_CAUGHT_NATIVE_EFFECTS');\n")
        blocked = verify()
        assert blocked.returncode == 1, blocked.stdout + blocked.stderr
        assert "NODE_SQLITE_CAUGHT_NATIVE_EFFECTS" in blocked.stdout
        assert "sqlite.authorizer x" in blocked.stderr
        assert not (project / "x").exists()
        for name in ("attach", "vacuum", "constructor", "lazy", "extension", "backup", "callback", "reopen"):
            assert not (project / (name + "-effect")).exists()
        # A read-only WAL connection may create native -wal/-shm files. Ordinary
        # checks reject it before native open; an explicit real role still runs it.
        for language in ("python", "node"):
            database = project / f"wal {language}.db"
            fixture = sqlite3.connect(database)
            fixture.execute("pragma journal_mode=wal")
            fixture.execute("create table t(value)")
            fixture.execute("insert into t values (42)")
            fixture.commit()
            fixture.close()
            before = database.read_bytes()
            assert not Path(str(database) + "-wal").exists()
            assert not Path(str(database) + "-shm").exists()
            if language == "python":
                wal_script = project / "wal.py"
                wal_script.write_text("import sqlite3\n"
                    "try:\n c=sqlite3.connect('file:wal%20python.db?mode=ro',uri=True)\n"
                    "except PermissionError: print('WAL_OPEN_CAUGHT')\n"
                    "else:\n assert c.execute('select value from t').fetchone()==(42,)\n c.close()\n print('WAL_READ_OK')\n")
                command = [sys.executable, "wal.py"]
            else:
                wal_script = project / "wal.cjs"
                wal_script.write_text("const {DatabaseSync}=require('node:sqlite');let c;\n"
                    "try{c=new DatabaseSync('wal node.db',{readOnly:true});}catch{console.log('WAL_OPEN_CAUGHT');}\n"
                    "if(c){require('node:assert/strict').equal(c.prepare('select value from t').get().value,42);c.close();console.log('WAL_READ_OK');}\n")
                command = [shutil.which("node"), "wal.cjs"]
            check_id = "wal-" + language
            config["verify"] = {"realChecks": [], "checks": [{"id": check_id, "command": command,
                "inputs": [wal_script.name, database.name]}]}
            path.write_text(json.dumps(config))
            ordinary = verify()
            assert ordinary.returncode == 1, ordinary.stdout + ordinary.stderr
            assert "runtime_guard_uncovered_native" in ordinary.stderr and "WAL" in ordinary.stderr
            assert "WAL_OPEN_CAUGHT" in ordinary.stdout and "WAL_READ_OK" not in ordinary.stdout
            assert database.read_bytes() == before
            assert not Path(str(database) + "-wal").exists()
            assert not Path(str(database) + "-shm").exists()
            config["verify"]["realChecks"] = [check_id]
            path.write_text(json.dumps(config))
            real = verify()
            assert real.returncode == 0, real.stdout + real.stderr
            assert "real-unprotected" in real.stdout and "WAL_READ_OK" in real.stdout


    def test_controlled_pack_rejects_unknown_package(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(PACK), "unknown", str(tmp_path)],
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode != 0
        assert "invalid choice" in result.stderr


    def test_controlled_pack_rejects_repository_output(self, ) -> None:
        result = subprocess.run(
            [sys.executable, str(PACK), "build-and-verify", str(REPO_ROOT / ".temporary-pack")],
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode != 0
        assert "output_inside_repository" in result.stderr
        assert not (REPO_ROOT / ".temporary-pack").exists()


    def test_packed_build_and_verify_rejects_untrusted_dev_source(self, tmp_path: Path) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        source = tmp_path / "source"
        for relative in (".agents", ".claude-plugin", "plugins/build-and-verify", "plugins/tool-lifecycle"):
            shutil.copytree(REPO_ROOT / relative, source / relative)
        initialized = subprocess.run(["git", "init"], cwd=source, text=True, capture_output=True, check=False)
        assert initialized.returncode == 0, initialized.stderr
        committed = subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "add", "."],
            cwd=source,
            text=True,
            capture_output=True,
            check=False,
        )
        assert committed.returncode == 0, committed.stderr
        committed = subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "source"],
            cwd=source,
            text=True,
            capture_output=True,
            check=False,
        )
        assert committed.returncode == 0, committed.stderr
        env = _isolated_env(tmp_path, prefix)

        rejected = subprocess.run([executable, "init", "--dev", "--source", source], text=True, capture_output=True, check=False, env=env)

        assert rejected.returncode == 1
        assert "error: invalid_dev_source: official_remote" in rejected.stderr
        assert not (tmp_path / "home" / ".build-and-verify" / "state.json").exists()


    def test_packed_build_and_verify_doctor_reports_machine_readable_release_identity(self, tmp_path: Path) -> None:
        npm = shutil.which("npm")
        assert npm is not None
        before = _tree_snapshot()
        packed = subprocess.run(
            [sys.executable, str(PACK), "build-and-verify", str(tmp_path)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert packed.returncode == 0, packed.stderr
        assert _tree_snapshot() == before
        tarball = Path(packed.stdout.strip())
        prefix = tmp_path / "prefix"
        installed = subprocess.run(
            [npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", str(tarball)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert installed.returncode == 0, installed.stderr
        executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")
        env = _isolated_env(tmp_path, prefix)
        diagnosed = subprocess.run(
            [executable, "doctor"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

        assert diagnosed.returncode == 0, diagnosed.stderr
        report = json.loads(diagnosed.stdout)
        assert report["toolchain"] == {
            "mode": "release",
            "packageName": "@liuli195/build-and-verify",
            "packageVersion": _package_version(),
        }


    def test_packed_build_and_verify_update_blocks_legacy_codex_before_writes(self, tmp_path: Path) -> None:
        npm, prefix, executable = _installed_build_and_verify(tmp_path)
        node = shutil.which("node")
        assert node is not None
        latest = _package_version()
        fake_bin = tmp_path / "fake-bin"
        fake_bin.mkdir()
        npm_log = tmp_path / "npm.log"
        npm_log.touch()
        codex_log = tmp_path / "codex.log"
        codex_state = tmp_path / "codex-state.json"
        codex_failure_marker = tmp_path / "codex-failure-marker"
        codex_home = tmp_path / "codex-home"
        codex_home.mkdir()
        package_root = subprocess.run(
            [npm, "root", "--global", "--prefix", str(prefix)],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        stable = Path(package_root) / "@liuli195" / "build-and-verify"
        legacy = tmp_path / "legacy-source"
        write = lambda path, value: path.write_text(value, encoding="utf-8")
        write(
            codex_state,
            json.dumps(
                {
                    "marketplaces": [
                        {"name": "build-and-verify", "root": str(stable)},
                        {"name": "my-agent-skills-marketplace", "root": str(legacy)},
                    ],
                    "installed": [
                        {
                            "pluginId": "build-and-verify@build-and-verify",
                            "installed": True,
                        },
                        {
                            "pluginId": "build-and-verify@my-agent-skills-marketplace",
                            "installed": True,
                        },
                    ],
                    "available": [],
                },
                indent=2,
            ),
        )
        codex_config = codex_home / "config.toml"
        write(
            codex_config,
            '[plugins."build-and-verify@build-and-verify"]\nenabled = true\n'
            '[plugins."build-and-verify@my-agent-skills-marketplace"]\nenabled = true\n',
        )
        codex_before = codex_state.read_bytes(), codex_config.read_bytes()
        write(
            fake_bin / "fake-npm.py",
            "import json, os, subprocess, sys\n"
            "args = sys.argv[1:]\n"
            "with open(os.environ['BUILD_NPM_LOG'], 'a', encoding='utf-8') as log:\n"
            "    log.write(json.dumps(args) + '\\n')\n"
            "if args == ['view', '@liuli195/build-and-verify', 'version', '--json']:\n"
            "    print(json.dumps(os.environ['BUILD_NPM_LATEST']))\n"
            "    raise SystemExit(0)\n"
            "if args[:2] == ['install', '--global']:\n"
            "    raise SystemExit(77)\n"
            "real = os.environ['BUILD_REAL_NPM']\n"
            "command = [real, *args]\n"
            "result = subprocess.run(subprocess.list2cmdline(command) if os.name == 'nt' else command, shell=os.name == 'nt')\n"
            "raise SystemExit(result.returncode)\n",
        )
        write(
            fake_bin / "fake-codex.py",
            "import json, os, re, sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "state_path = Path(os.environ['BUILD_CODEX_STATE'])\n"
            "state = json.loads(state_path.read_text(encoding='utf-8'))\n"
            "with Path(os.environ['BUILD_CODEX_LOG']).open('a', encoding='utf-8') as log:\n"
            "    log.write(json.dumps(args) + '\\n')\n"
            "def save():\n"
            "    state_path.write_text(json.dumps(state), encoding='utf-8')\n"
            "if args == ['plugin', 'marketplace', 'list', '--json']:\n"
            "    print(json.dumps({'marketplaces': state['marketplaces']}))\n"
            "elif args == ['plugin', 'list', '--json']:\n"
            "    text = Path(os.environ['CODEX_HOME']) / 'config.toml'\n"
            "    config = text.read_text(encoding='utf-8') if text.exists() else ''\n"
            "    installed = []\n"
            "    for item in state['installed']:\n"
            "        current = dict(item)\n"
            "        identifier = re.escape(item['pluginId'])\n"
            "        current['enabled'] = bool(re.search(rf'(?ms)^\\[plugins\\.\"{identifier}\"\\]\\s*\\n.*?^enabled\\s*=\\s*true\\s*$', config))\n"
            "        installed.append(current)\n"
            "    print(json.dumps({'installed': installed, 'available': state['available']}))\n"
            "elif args[:2] == ['plugin', 'remove']:\n"
            "    identifier = args[2]\n"
            "    if identifier == 'build-and-verify@my-agent-skills-marketplace' and not Path(os.environ['BUILD_CODEX_FAIL_MARKER']).exists():\n"
            "        Path(os.environ['BUILD_CODEX_FAIL_MARKER']).write_text('failed', encoding='utf-8')\n"
            "        raise SystemExit(77)\n"
            "    state['installed'] = [item for item in state['installed'] if item['pluginId'] != identifier]\n"
            "    save()\n"
            "elif args == ['plugin', 'add', 'build-and-verify@build-and-verify', '--json']:\n"
            "    state['installed'] = [item for item in state['installed'] if item['pluginId'] != 'build-and-verify@build-and-verify']\n"
            "    state['installed'].append({'pluginId': 'build-and-verify@build-and-verify', 'installed': True, 'version': os.environ['BUILD_PACKAGE_VERSION'], 'source': {'source': 'local', 'path': os.environ['BUILD_STABLE']}})\n"
            "    config_path = Path(os.environ['CODEX_HOME']) / 'config.toml'\n"
            "    config = config_path.read_text(encoding='utf-8') if config_path.exists() else ''\n"
            "    if '[plugins.\"build-and-verify@build-and-verify\"]' not in config:\n"
            "        config_path.write_text(config.rstrip() + '\\n[plugins.\"build-and-verify@build-and-verify\"]\\nenabled = true\\n', encoding='utf-8')\n"
            "    save()\n"
            "else:\n"
            "    raise SystemExit(2)\n",
        )
        for name in ("npm", "codex"):
            script = fake_bin / f"fake-{name}.py"
            launcher = fake_bin / (f"{name}.cmd" if sys.platform == "win32" else name)
            if sys.platform == "win32":
                write(launcher, f'@"{sys.executable}" "{script}" %*\n')
            else:
                write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
                launcher.chmod(0o755)
        env = {
            **os.environ,
            "BUILD_AND_VERIFY_PYTHON": sys.executable,
            "NPM_CONFIG_PREFIX": str(prefix),
            "HOME": str(tmp_path / "home"),
            "USERPROFILE": str(tmp_path / "home"),
            "CODEX_HOME": str(codex_home),
            "BUILD_NPM_LOG": str(npm_log),
            "BUILD_REAL_NPM": str(npm),
            "BUILD_NPM_LATEST": latest,
            "BUILD_CODEX_LOG": str(codex_log),
            "BUILD_CODEX_STATE": str(codex_state),
            "BUILD_CODEX_FAIL_MARKER": str(codex_failure_marker),
            "BUILD_PACKAGE_VERSION": _package_version(),
            "BUILD_STABLE": str(stable),
            "PATH": os.pathsep.join(
                [str(fake_bin), str(Path(sys.executable).parent), str(Path(node).parent)]
            ),
        }
        blocked = subprocess.run(
            [executable, "update"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

        assert blocked.returncode == 1
        assert "error: legacy_source_migration_required" in blocked.stderr
        assert "build-and-verify init --codex" in blocked.stderr
        assert "build-and-verify init --pi" not in blocked.stderr
        assert "build-and-verify init --claude" not in blocked.stderr
        assert not any(json.loads(line)[:2] == ["install", "--global"] for line in npm_log.read_text(encoding="utf-8").splitlines())
        assert not (Path(env["HOME"]) / ".build-and-verify" / "state.json").exists()
        assert "plugin remove" not in codex_log.read_text(encoding="utf-8")
        assert (codex_state.read_bytes(), codex_config.read_bytes()) == codex_before

        failed_migration = subprocess.run(
            [executable, "init", "--codex"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        assert failed_migration.returncode == 1
        assert "error: codex_plugin_remove_failed:" in failed_migration.stderr

        migrated = subprocess.run(
            [executable, "init", "--codex"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        assert migrated.returncode == 0, migrated.stderr
        assert not any(
            item["pluginId"] == "build-and-verify@my-agent-skills-marketplace"
            for item in json.loads(codex_state.read_text(encoding="utf-8"))["installed"]
        )

        updated = subprocess.run(
            [executable, "update"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        assert updated.returncode == 0, updated.stderr
        assert json.loads(updated.stdout)["version"] == _package_version()


    def test_packed_build_and_verify_migrates_recognized_runtime_after_fast_verify(self, tmp_path: Path) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        project = _legacy_project(tmp_path)

        migrated = subprocess.run(
            [executable, "verify", "--project", str(project)],
            cwd=project,
            text=True,
            capture_output=True,
            check=False,
            env=_isolated_env(tmp_path, prefix),
        )

        assert migrated.returncode == 0, migrated.stderr
        assert not (project / ".build-and-verify" / "runtime").exists()
        assert _git(project, "status", "--porcelain").stdout == ""
        assert _git(project, "show", "--name-only", "--format=").stdout.splitlines() == [
            ".build-and-verify/runtime/build_and_verify.py",
            ".build-and-verify/runtime/build_and_verify_runner.py",
            ".build-and-verify/runtime/version.json",
        ]


    def test_packed_build_and_verify_preserves_legacy_runtime_when_verify_fails(self, tmp_path: Path) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        project = _legacy_project(tmp_path)
        (project / ".build-and-verify" / "config.json").write_text(
            json.dumps({"version": 1, "build": {"checks": []}, "verify": {"checks": [{"id": "fail", "command": [sys.executable, "-c", "raise SystemExit(1)"], "paths": [".build-and-verify/runtime/"]}]}}),
            encoding="utf-8",
        )
        assert _git(project, "add", ".").returncode == 0
        assert _git(project, "commit", "-m", "failing verify").returncode == 0

        verified = subprocess.run([executable, "verify", "--project", str(project)], cwd=project, text=True, capture_output=True, check=False, env=_isolated_env(tmp_path, prefix))

        assert verified.returncode == 1
        assert (project / ".build-and-verify" / "runtime").is_dir()
        assert _git(project, "status", "--porcelain").stdout == ""


    def test_packed_build_and_verify_rejects_unrecognized_legacy_runtime(self, tmp_path: Path) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        project = _legacy_project(tmp_path)
        (project / ".build-and-verify" / "runtime" / "unexpected.py").write_text("not legacy", encoding="utf-8")
        assert _git(project, "add", ".").returncode == 0
        assert _git(project, "commit", "-m", "unrecognized runtime").returncode == 0

        verified = subprocess.run([executable, "verify", "--project", str(project)], cwd=project, text=True, capture_output=True, check=False, env=_isolated_env(tmp_path, prefix))

        assert verified.returncode == 1
        assert "unrecognized_runtime" in verified.stderr
        assert (project / ".build-and-verify" / "runtime" / "unexpected.py").is_file()
        assert _git(project, "status", "--porcelain").stdout == ""


    def test_packed_build_and_verify_preserves_runtime_when_fast_verify_stages_external_file(self, tmp_path: Path) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        project = _legacy_project(tmp_path)
        write_and_stage = "from pathlib import Path; import subprocess; Path('external.txt').write_text('keep'); subprocess.check_call(['git', 'add', 'external.txt'])"
        (project / ".build-and-verify" / "config.json").write_text(
            json.dumps({"version": 1, "build": {"checks": []}, "verify": {"checks": [{"id": "stages-external", "command": [sys.executable, "-c", write_and_stage], "paths": [".build-and-verify/runtime/"]}]}}),
            encoding="utf-8",
        )
        assert _git(project, "add", ".").returncode == 0
        assert _git(project, "commit", "-m", "staging verify").returncode == 0

        verified = subprocess.run([executable, "verify", "--project", str(project)], cwd=project, text=True, capture_output=True, check=False, env=_isolated_env(tmp_path, prefix))

        assert verified.returncode == 1
        assert "git_worktree_not_clean" in verified.stderr
        assert (project / ".build-and-verify" / "runtime").is_dir()
        assert _git(project, "diff", "--cached", "--name-only").stdout == "external.txt\n"


    def test_packed_build_and_verify_restores_runtime_when_migration_commit_fails(self, tmp_path: Path) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        project = _legacy_project(tmp_path)
        hook = project / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)

        verified = subprocess.run([executable, "verify", "--project", str(project)], cwd=project, text=True, capture_output=True, check=False, env=_isolated_env(tmp_path, prefix))

        assert verified.returncode == 1
        assert "commit_failed" in verified.stderr
        assert (project / ".build-and-verify" / "runtime").is_dir()
        assert _git(project, "status", "--porcelain").stdout == ""


    def test_packed_build_and_verify_codex_doctor_resolves_orca_and_explicit_homes(self,
        tmp_path: Path,
    ) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        fake_bin = tmp_path / "fake-codex" / "bin"
        fake_bin.mkdir(parents=True)
        env_log = tmp_path / "codex-env.log"
        probe = fake_bin.parent / "codex_probe.py"
        probe.write_text(
            "import json\n"
            "import os\n"
            "import sys\n"
            "from pathlib import Path\n"
            "Path(os.environ['CODEX_ENV_LOG']).open('a', encoding='utf-8').write(os.environ['CODEX_HOME'] + '\\n')\n"
            "if sys.argv[1:] == ['plugin', 'marketplace', 'list', '--json']:\n"
            "    print(json.dumps({'marketplaces': []}))\n"
            "elif sys.argv[1:] == ['plugin', 'list', '--json']:\n"
            "    print(json.dumps({'installed': [], 'available': []}))\n"
            "else:\n"
            "    raise SystemExit(2)\n",
            encoding="utf-8",
        )
        if sys.platform == "win32":
            (fake_bin / "codex.cmd").write_text(
                f'@"{sys.executable}" "{probe}" %*\n',
                encoding="utf-8",
            )
        else:
            launcher = fake_bin / "codex"
            launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{probe}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
        env = _isolated_env(tmp_path, prefix)
        user_home = Path(env["USERPROFILE"]) / ".codex"
        orca_home = tmp_path / "orca-user-data" / "codex-runtime-home" / "home"
        orca_home.mkdir(parents=True)
        env.update(
            {
                "PATH": os.pathsep.join([str(fake_bin), env["PATH"]]),
                "CODEX_HOME": str(orca_home),
                "ORCA_USER_DATA_PATH": str(tmp_path / "orca-user-data"),
                "CODEX_ENV_LOG": str(env_log),
            }
        )

        inherited = subprocess.run(
            [executable, "doctor", "--codex"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

        assert inherited.returncode == 0, inherited.stderr
        report = json.loads(inherited.stdout)["codex"]
        assert report["codexHome"] == str(user_home)
        assert report["codexHomeSource"] == "orca-user-default"
        assert env_log.read_text(encoding="utf-8").splitlines() == [str(user_home), str(user_home)]

        explicit_home = tmp_path / "custom-codex-home"
        explicit_home.mkdir()
        env_log.write_text("", encoding="utf-8")
        explicit = subprocess.run(
            [executable, "doctor", "--codex", "--codex-home", explicit_home],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

        assert explicit.returncode == 0, explicit.stderr
        report = json.loads(explicit.stdout)["codex"]
        assert report["codexHome"] == str(explicit_home)
        assert report["codexHomeSource"] == "explicit"
        assert env_log.read_text(encoding="utf-8").splitlines() == [str(explicit_home), str(explicit_home)]
        assert env["CODEX_HOME"] == str(orca_home)

        unavailable_home = tmp_path / "not-a-directory"
        unavailable_home.write_text("not a directory", encoding="utf-8")
        env_log.write_text("", encoding="utf-8")
        unavailable = subprocess.run(
            [executable, "doctor", "--codex", "--codex-home", unavailable_home],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

        assert unavailable.returncode == 1
        assert f"error: codex_home_unavailable: {unavailable_home}: not a directory" in unavailable.stderr
        assert env_log.read_text(encoding="utf-8") == ""
        assert env["CODEX_HOME"] == str(orca_home)

        missing_home = tmp_path / "missing-codex-home"
        missing = subprocess.run(
            [executable, "doctor", "--codex", "--codex-home", missing_home],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

        assert missing.returncode == 1
        assert f"error: codex_home_unavailable: {missing_home}: directory does not exist" in missing.stderr


    def test_packed_build_and_verify_rejects_dirty_legacy_migration(self, tmp_path: Path) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        project = _legacy_project(tmp_path)
        (project / "unrelated.txt").write_text("keep", encoding="utf-8")

        migrated = subprocess.run([executable, "verify", "--project", str(project)], cwd=project, text=True, capture_output=True, check=False, env=_isolated_env(tmp_path, prefix))

        assert migrated.returncode == 1
        assert "git_worktree_not_clean" in migrated.stderr
        assert (project / ".build-and-verify" / "runtime").is_dir()
        assert _git(project, "status", "--porcelain").stdout == "?? unrelated.txt\n"


    def test_packed_build_and_verify_dev_identity_controls_public_verify_cache(self,
        tmp_path: Path,
    ) -> None:
        _, prefix, executable = _installed_build_and_verify(tmp_path)
        source, ssh = _controlled_dev_source(tmp_path)
        env = _isolated_env(tmp_path, prefix)
        env["GIT_SSH_COMMAND"] = f'"{sys.executable}" "{ssh}"'
        entered = subprocess.run(
            [executable, "init", "--dev", "--source", source],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        assert entered.returncode == 0, entered.stderr
        report = json.loads(entered.stdout)
        assert report["mode"] == "dev"
        assert report["source"] == str(source)
        assert _git(source, "status", "--porcelain").stdout == ""

        diagnosed = subprocess.run(
            [executable, "doctor"],
            cwd=source,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        assert diagnosed.returncode == 0, diagnosed.stderr
        toolchain = json.loads(diagnosed.stdout)["toolchain"]
        assert toolchain["sourceCommit"] == _git(source, "rev-parse", "HEAD").stdout.strip()
        first_identity = toolchain["implementationIdentity"]

        project = tmp_path / "project"
        project.mkdir()
        (project / "src").mkdir()
        (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
        command = [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('run.log').open('a', encoding='utf-8').write('ran\\n')",
        ]
        config = {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "public-cache",
                        "command": command,
                        "paths": ["src/app.txt"],
                        "inputs": ["src/app.txt"],
                    }
                ]
            },
        }
        config_path = project / ".build-and-verify" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

        def verify() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [executable, "verify", "--project", project],
                cwd=project,
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )

        first = verify()
        second = verify()
        assert first.returncode == 0, first.stderr
        assert second.returncode == 0, second.stderr
        assert "cache-hit: public-cache" in second.stdout
        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == ["ran"]
        # Full-cache refresh and config mutations use the runner's focused cache tests.

        (source / "plugins" / "my-spec").mkdir()
        (source / "plugins" / "my-spec" / "unrelated.txt").write_text("not Build and Verify\n", encoding="utf-8")
        unrelated = subprocess.run(
            [executable, "doctor"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        assert unrelated.returncode == 0, unrelated.stderr
        assert json.loads(unrelated.stdout)["toolchain"]["implementationIdentity"] == first_identity
        unchanged = verify()
        assert unchanged.returncode == 0, unchanged.stderr
        assert "cache-hit: public-cache" in unchanged.stdout

        implementation = source / "plugins" / "build-and-verify" / "python" / "build_and_verify_runner.py"
        implementation.write_text(
            implementation.read_text(encoding="utf-8") + "\n# implementation identity change\n",
            encoding="utf-8",
        )
        changed = subprocess.run(
            [executable, "doctor"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        assert changed.returncode == 0, changed.stderr
        assert json.loads(changed.stdout)["toolchain"]["implementationIdentity"] != first_identity
        invalidated = verify()
        assert invalidated.returncode == 0, invalidated.stderr
        assert "cache-hit: public-cache" not in invalidated.stdout
        implementation_identity = json.loads(changed.stdout)["toolchain"]["implementationIdentity"]

        packer = source / "plugins" / "tool-lifecycle" / "pack.py"
        packer.write_text(packer.read_text(encoding="utf-8") + "\n# shared packaging change\n", encoding="utf-8")
        shared_changed = subprocess.run(
            [executable, "doctor"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        assert shared_changed.returncode == 0, shared_changed.stderr
        shared_identity = json.loads(shared_changed.stdout)["toolchain"]["implementationIdentity"]
        assert shared_identity != implementation_identity
        shared_invalidated = verify()
        assert shared_invalidated.returncode == 0, shared_invalidated.stderr
        assert "cache-hit: public-cache" not in shared_invalidated.stdout

        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
            "ran",
            "ran",
            "ran",
        ]


    def test_packed_tools_bare_doctor_reports_only_package(self, tmp_path: Path) -> None:
        tool = "build-and-verify"

        _, prefix, executable = _installed_build_and_verify(tmp_path)
        pi_bin, pi_log = _myspec_install_removed_pi_command(tmp_path / "removed-pi")
        claude_bin, claude_log, claude_state = _myspec_install_fake_claude(tmp_path / "fake-claude")
        codex_bin, codex_log, codex_state = _myspec_install_fake_codex(tmp_path / "fake-codex")
        env = _myspec_isolated_myspec_env(tmp_path, prefix, pi_bin, claude_bin, codex_bin)
        invalid_home = tmp_path / "invalid-codex-home"
        invalid_home.write_text("not a directory", encoding="utf-8")
        env.update(CODEX_HOME=str(invalid_home), MYSPEC_PI_LOG=str(pi_log),
                   MYSPEC_CLAUDE_LOG=str(claude_log), MYSPEC_CLAUDE_STATE=str(claude_state),
                   MYSPEC_CODEX_LOG=str(codex_log), MYSPEC_CODEX_STATE=str(codex_state))
        env["BUILD_AND_VERIFY_PYTHON"] = sys.executable
        diagnosed = subprocess.run([str(executable), "doctor"], env=env, text=True, capture_output=True, check=False)
        assert diagnosed.returncode == 0, diagnosed.stderr
        report = json.loads(diagnosed.stdout)
        assert report["toolchain"]["mode"] == "release"
        assert report["npm"]["versionMismatch"] is False
        assert report["installation"]["pendingOperation"] is None
        assert not {"pi", "claude", "codex"}.intersection(report)
        assert not any(log.exists() for log in (pi_log, claude_log, codex_log))
        installed_package = prefix / ("node_modules" if os.name == "nt" else "lib/node_modules") / "@liuli195" / tool
        manifest = json.loads((installed_package / "package.json").read_text())
        assert "pi" not in manifest and "pi-package" not in manifest.get("keywords", [])


    def test_packed_tools_all_and_removed_pi_options(self, tmp_path: Path) -> None:
        tool = "build-and-verify"

        _, prefix, executable = _installed_build_and_verify(tmp_path)
        env = _myspec_isolated_myspec_env(tmp_path, prefix)
        env["BUILD_AND_VERIFY_PYTHON"] = sys.executable
        for command in ("doctor", "init"):
            removed = subprocess.run([str(executable), command, "--pi"], env=env, text=True, capture_output=True, check=False)
            assert removed.returncode == 2, removed.stdout + removed.stderr
            assert "error:" in removed.stderr
            selected = subprocess.run([str(executable), command, "--all"], env=env, text=True, capture_output=True, check=False)
            assert selected.returncode == 0, selected.stderr
            report = json.loads(selected.stdout)
            assert "pi" not in report
            assert {"claude", "codex"}.issubset(report)


    def test_packed_tools_reject_legacy_pi_pending_before_writes(self, tmp_path: Path) -> None:
        tool = "build-and-verify"

        _, prefix, executable = _installed_build_and_verify(tmp_path)
        package = prefix / ("node_modules" if os.name == "nt" else "lib/node_modules") / "@liuli195" / tool
        release_tarball = next((candidate_for("build-and-verify").tarball.parent).glob("*.tgz"))
        npm_bin, npm_log = _myspec_install_fake_npm(tmp_path / "fake-npm", release_tarball)
        env = _myspec_isolated_myspec_env(tmp_path, prefix, npm_bin)
        env.update(BUILD_AND_VERIFY_PYTHON=sys.executable, MYSPEC_NPM_LOG=str(npm_log),
                   MYSPEC_NPM_FAIL_INSTALL="1", MYSPEC_RELEASE_TARBALL=str(release_tarball))
        pending = {"command": "update", "targetVersion": "99.0.0", "integrations": ["pi", "claude"],
                   "completed": ["preflight"], "enabled": {"pi": True, "claude": False}, "scopes": {}}
        state_path = Path(env["HOME"]) / f".{tool}" / "state.json"
        pi_settings = Path(env["HOME"]) / ".pi" / "agent" / "settings.json"
        _myspec_write(state_path, json.dumps({"mode": "release", "pendingOperation": pending}, indent=2))
        _myspec_write(pi_settings, '{"packages": ["old-pi-source"], "other": "keep"}')
        before = (state_path.read_bytes(), pi_settings.read_bytes(), (package / "package.json").read_bytes())
        diagnosed = subprocess.run([str(executable), "doctor"], env=env, text=True, capture_output=True, check=False)
        assert diagnosed.returncode == 0, diagnosed.stderr
        assert json.loads(diagnosed.stdout)["installation"]["pendingOperation"]["integrations"] == ["pi", "claude"]
        rejected = subprocess.run([str(executable), "update"], env=env, text=True, capture_output=True, check=False)
        assert rejected.returncode == 1
        assert "error: invalid_update_state" in rejected.stderr
        assert (state_path.read_bytes(), pi_settings.read_bytes(), (package / "package.json").read_bytes()) == before
        assert not npm_log.exists() or npm_log.read_text() == ""


    def test_packed_tools_supported_clients_initialize_and_resume_update(self, tmp_path: Path) -> None:
        tool = "build-and-verify"

        _, prefix, executable = _installed_build_and_verify(tmp_path)
        package = prefix / ("node_modules" if os.name == "nt" else "lib/node_modules") / "@liuli195" / tool
        version = json.loads((package / "package.json").read_text())["version"]
        claude_bin, claude_log, claude_state = _myspec_install_fake_claude(tmp_path / "fake-claude")
        codex_bin, codex_log, codex_state = _myspec_install_fake_codex(tmp_path / "fake-codex")
        pi_bin, pi_log = _myspec_install_removed_pi_command(tmp_path / "removed-pi")
        env = _myspec_isolated_myspec_env(tmp_path, prefix, claude_bin, codex_bin, pi_bin)
        codex_home = Path(env["HOME"]) / ".codex"
        codex_home.mkdir()
        env.update(BUILD_AND_VERIFY_PYTHON=sys.executable, MYSPEC_CLAUDE_LOG=str(claude_log),
                   MYSPEC_CLAUDE_STATE=str(claude_state), MYSPEC_CLAUDE_HOME=str(Path(env["HOME"]) / ".claude"),
                   MYSPEC_CODEX_LOG=str(codex_log), MYSPEC_CODEX_STATE=str(codex_state),
                   CODEX_HOME=str(codex_home), MYSPEC_PI_LOG=str(pi_log))
        _myspec_write(claude_state, '{"marketplaces": [], "plugins": []}')
        _myspec_write(codex_state, '{"marketplaces": [], "installed": [], "available": []}')
        initialized = subprocess.run([str(executable), "init", "--all"], env=env, text=True, capture_output=True, check=False)
        assert initialized.returncode == 0, initialized.stderr
        assert set(json.loads(initialized.stdout)) == {"claude", "codex"}
        diagnosed = subprocess.run([str(executable), "doctor", "--all"], env=env, text=True, capture_output=True, check=False)
        assert diagnosed.returncode == 0, diagnosed.stderr
        report = json.loads(diagnosed.stdout)
        for client in ("claude", "codex"):
            assert report[client]["version"] == version
            assert report[client]["skills"]
            assert report[client]["sources"][0]["effective"] is True
        state_path = Path(env["HOME"]) / f".{tool}" / "state.json"
        _myspec_write(state_path, json.dumps({"mode": "release", "pendingOperation": {
            "command": "update", "targetVersion": version, "integrations": ["claude", "codex"],
            "completed": ["preflight", "npm"], "enabled": {"claude": False, "codex": False}, "scopes": {"claude": "user"}}}))
        updated = subprocess.run([str(executable), "update"], env=env, text=True, capture_output=True, check=False)
        assert updated.returncode == 0, updated.stderr
        result = json.loads(updated.stdout)
        assert result["claude"] == result["codex"] == "refreshed"
        assert "pi" not in result and "pi" not in result["doctor"]
        assert result["doctor"]["claude"]["enabled"] is False
        assert result["doctor"]["codex"]["enabled"] is False
        assert "pendingOperation" not in json.loads(state_path.read_text())
        assert not pi_log.exists()



    def test_public_verify_parallel_active_checks_share_cancellation(self, tmp_path: Path) -> None:
        checks = [{"id": name, "command": [sys.executable, "-c", "import time; time.sleep(6)"],
                   "inputs": [], "checkParallel": True} for name in ("first", "second")]
        result, project = _budget_run(tmp_path, settings={"maxParallel": 2}, checks=checks)
        assert result.returncode == 1
        report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
        assert report["unfinished"] == ["first", "second"]
        assert all(check["status"] == "timed_out" for check in report["checks"])


    def test_build_and_verify_init_writes_config_gitignore_and_cache(self, tmp_path: Path) -> None:
        from tests.test_build_and_verify_plugin import read_json
        project = tmp_path / "project"
        project.mkdir()

        result = _run_installed_bav("init", "--project", str(project))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "status: initialized" in result.stdout
        assert (project / ".build-and-verify" / "config.json").is_file()
        assert (project / ".build-and-verify" / ".gitignore").is_file()
        assert (project / ".build-and-verify" / "cache").is_dir()
        assert not (project / "scripts" / "check.py").exists()
        assert read_json(project / ".build-and-verify" / "config.json") == {
            "version": 2,
            "build": {"checks": []},
            "verify": {"realChecks": [], "checks": []},
        }
        assert (project / ".build-and-verify" / ".gitignore").read_text(
            encoding="utf-8"
        ) == "/cache/\n/runs/\n/backups/\n"
        assert "build-and-verify-init" not in result.stdout
        assert "questionnaire" not in result.stdout.lower()
        assert "questionnaire" not in result.stderr.lower()
        assert not (project / ".build-and-verify" / "backups").exists()
        assert read_json(project / ".build-and-verify" / "config.json")["build"]["checks"] == []
        assert read_json(project / ".build-and-verify" / "config.json")["verify"]["checks"] == []


    def test_runtime_guard_invalid_migration_keeps_existing_configuration(self, tmp_path: Path) -> None:
        from tests.test_build_and_verify_plugin import write_json, write_runner_config
        project = tmp_path / "project"
        write_runner_config(project)
        path = project / ".build-and-verify/config.json"
        before = path.read_bytes()
        draft = tmp_path / "draft.json"
        write_json(draft, {"version": 2, "verify": {"checks": []}})
        result = _run_installed_bav("init", "--project", str(project), "--config", str(draft), "--overwrite")
        assert result.returncode == 1
        assert "verify.realChecks" in result.stderr
        assert path.read_bytes() == before
        assert not (project / ".build-and-verify/backups").exists()


    def test_build_and_verify_init_writes_confirmed_config_with_overwrite(self,
        tmp_path: Path,
    ) -> None:
        from tests.test_build_and_verify_plugin import command_that_logs, read_json, write_json
        project = tmp_path / "project"
        project.mkdir()
        build_dir = project / ".build-and-verify"
        build_dir.mkdir()
        old_config = {"version": 1, "build": {"checks": []}, "verify": {"checks": []}}
        confirmed_config = {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "verify.confirmed",
                        "command": command_that_logs("confirmed"),
                        "inputs": [],
                    }
                ]
            },
        }
        write_json(build_dir / "config.json", old_config)
        (build_dir / ".gitignore").write_text("/custom/\n/cache/\n", encoding="utf-8")
        confirmed = tmp_path / "confirmed.json"
        write_json(confirmed, confirmed_config)

        result = _run_installed_bav(
            "init",
            "--project",
            str(project),
            "--config",
            str(confirmed),
            "--overwrite",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert read_json(build_dir / "config.json") == confirmed_config
        backups = list((build_dir / "backups").glob("config-*.json"))
        assert len(backups) == 1
        assert read_json(backups[0]) == old_config
        assert set((build_dir / ".gitignore").read_text(encoding="utf-8").splitlines()) == {
            "/custom/",
            "/cache/",
            "/runs/",
            "/backups/",
        }
        assert not (build_dir / "runtime").exists()
        assert (build_dir / "cache").is_dir()


    @pytest.mark.parametrize(
        "existing",
        [
            Path(".build-and-verify/config.json"),
            Path(".build-and-verify/.gitignore"),
        ],
    )
    def test_build_and_verify_init_refuses_existing_files_before_writes(self,
        tmp_path: Path, existing: Path
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        existing_path = project / existing
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        if existing.suffix:
            existing_path.write_text("keep me\n", encoding="utf-8")
        else:
            existing_path.mkdir()

        result = _run_installed_bav("init", "--project", str(project))

        assert result.returncode != 0
        assert f"existing_file: {existing.as_posix()}" in result.stderr
        if existing.suffix:
            assert existing_path.read_text(encoding="utf-8") == "keep me\n"
        else:
            assert existing_path.is_dir()
        generated_files = [
            Path(".build-and-verify/config.json"),
            Path(".build-and-verify/.gitignore"),
        ]
        for relative in generated_files:
            path = project / relative
            if path != existing_path:
                assert not path.exists()
        assert not (project / ".build-and-verify" / "cache").exists()


    @pytest.mark.parametrize(
        ("action", "failure_report"),
        [
            ("build", "checked: invalid-output"),
            ("verify", "failed: invalid-output"),
        ],
    )
    def test_build_and_verify_runner_reports_failed_check_with_invalid_utf8_output(self,
        tmp_path: Path, action: str, failure_report: str
    ) -> None:
        from tests.test_build_and_verify_plugin import write_runner_config
        project = tmp_path / "project"
        project.mkdir()
        check = {
            "id": "invalid-output",
            "command": [
                sys.executable,
                "-c",
                "import os; os.write(2, b'invalid: \\xff\\n'); raise SystemExit(7)",
            ],
            "inputs": [],
        }
        write_runner_config(
            project,
            build_checks=[check] if action == "build" else None,
            verify_checks=[check] if action == "verify" else None,
        )

        result = _run_installed_bav(action, "--project", str(project), *( ("--full",) if action == "verify" else ()))

        assert result.returncode == 1
        assert "invalid: \ufffd" in result.stderr
        assert failure_report in result.stdout
        assert "status: failed" in result.stdout
        assert "UnicodeDecodeError" not in result.stderr


# MySpec package scenarios. Product-specific helpers load only for selected MySpec cases.
_MYSPEC_REPO_ROOT = Path(__file__).resolve().parents[2]
_MYSPEC_PLUGIN_ROOT = _MYSPEC_REPO_ROOT / "plugins" / "my-spec"
_MYSPEC_SPEC_OPS = _MYSPEC_PLUGIN_ROOT / "python" / "spec_ops.py"
_MYSPEC_PACK = _MYSPEC_REPO_ROOT / "plugins" / "tool-lifecycle" / "pack.py"
_MYSPEC_SKILL_NAMES = ("my-spec", "my-spec-add", "my-spec-review", "my-spec-audit")
_MYSPEC_SHARED_MANAGEMENT = _MYSPEC_REPO_ROOT / "plugins" / "tool-lifecycle" / "python" / "management.py"
_MYSPEC_in_process_spec_ops: dict[Path, object] = {}


def _myspec_load_in_process_spec_ops(spec_ops_path: Path):
    spec_ops_path = spec_ops_path.resolve()
    cached = _MYSPEC_in_process_spec_ops.get(spec_ops_path)
    if cached is not None:
        return cached

    module_id = hashlib.sha256(str(spec_ops_path).encode()).hexdigest()[:16]
    management_name = "management"
    previous_management = sys.modules.get(management_name)
    try:
        management_spec = importlib.util.spec_from_file_location(
            f"myspec_management_{module_id}", spec_ops_path.with_name("management.py")
        )
        assert management_spec is not None and management_spec.loader is not None
        management = importlib.util.module_from_spec(management_spec)
        sys.modules[management_spec.name] = management
        sys.modules[management_name] = management
        management_spec.loader.exec_module(management)

        spec_ops_spec = importlib.util.spec_from_file_location(
            f"myspec_spec_ops_{module_id}", spec_ops_path
        )
        assert spec_ops_spec is not None and spec_ops_spec.loader is not None
        module = importlib.util.module_from_spec(spec_ops_spec)
        sys.modules[spec_ops_spec.name] = module
        spec_ops_spec.loader.exec_module(module)
    finally:
        if previous_management is None:
            sys.modules.pop(management_name, None)
        else:
            sys.modules[management_name] = previous_management
    _MYSPEC_in_process_spec_ops[spec_ops_path] = module
    return module



def _myspec_load_management_module():
    path = _MYSPEC_PLUGIN_ROOT / "python" / "management.py"
    spec = importlib.util.spec_from_file_location("myspec_management_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module



def _myspec_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")



def _myspec_controlled_git_script(git: str, remote: Path) -> str:
    return (
        "import subprocess\nimport sys\n"
        f"git = {git!r}\n"
        "def run_git(*args):\n"
        "    command = [git, *args]\n"
        "    shell = git.lower().endswith('.cmd')\n"
        "    if shell:\n"
        "        command = subprocess.list2cmdline(command)\n"
        "    return subprocess.run(command, shell=shell)\n"
        "args = sys.argv[1:]\n"
        "if args == ['remote', 'get-url', 'origin']:\n"
        "    print('https://github.com/liuli195/my-agent-skills')\n"
        "    raise SystemExit()\n"
        "if args == ['ls-remote', 'origin']:\n"
        f"    raise SystemExit(run_git('ls-remote', {remote.as_uri()!r}).returncode)\n"
        "raise SystemExit(run_git(*args).returncode)"
    )



def _myspec_real_controlled_dev_source(tmp_path: Path, marker: str | None = None) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    for name in (".gitattributes", ".gitignore"):
        shutil.copy2(_MYSPEC_REPO_ROOT / name, source / name)
    for relative in (".agents", ".claude-plugin", "plugins/my-spec", "plugins/tool-lifecycle"):
        shutil.copytree(
            _MYSPEC_REPO_ROOT / relative,
            source / relative,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    if marker is not None:
        _myspec_write(source / "plugins" / "my-spec" / "skills" / "my-spec" / "dev-marker.txt", marker)
    launcher = source / "plugins" / "my-spec" / "bin" / "myspec.js"
    launcher.chmod(launcher.stat().st_mode | 0o111)
    remote = tmp_path / "origin.git"
    for command in (
        ["git", "init", "--bare", remote],
        ["git", "init", source],
        ["git", "-C", source, "add", "."],
        ["git", "-C", source, "-c", "user.name=MySpec Test", "-c", "user.email=myspec@example.invalid", "commit", "-m", "development source"],
        ["git", "-C", source, "checkout-index", "--force", "--", "plugins/my-spec/bin/myspec.js"],
        # Seed before registering origin so Git cannot create a tracking ref.
        ["git", "-C", source, "push", remote.as_uri(), "HEAD:refs/heads/main"],
        ["git", "-C", source, "remote", "add", "origin", "https://github.com/liuli195/my-agent-skills"],
        ["git", "-C", source, "config", f"url.{remote.as_uri()}.insteadOf", "https://github.com/liuli195/my-agent-skills"],
    ):
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stderr
    git = shutil.which("git")
    assert git is not None
    bin_dir = tmp_path / "controlled-git"
    bin_dir.mkdir()
    if os.name == "nt":
        script = bin_dir / "git.py"
        _myspec_write(script, _myspec_controlled_git_script(git, remote))
        _myspec_write(bin_dir / "git.cmd", f'@"{sys.executable}" "{script}" %*')
    else:
        wrapper = bin_dir / "git"
        _myspec_write(wrapper, f'#!/bin/sh\nif [ "$1" = remote ] && [ "$2" = get-url ] && [ "$3" = origin ]; then echo https://github.com/liuli195/my-agent-skills; exit; fi\nif [ "$1" = ls-remote ] && [ "$2" = origin ]; then exec "{git}" ls-remote "{remote.as_uri()}"; fi\nexec "{git}" "$@"')
        wrapper.chmod(0o755)
    return source



def _myspec_controlled_dev_env(env: dict[str, str], source: Path) -> dict[str, str]:
    path_entries = [str(source.parent / "controlled-git"), env["PATH"]]
    if os.name == "nt":
        # Git for Windows' mingw executable launches its bundled shell.
        git_shell = shutil.which("sh")
        if git_shell is not None:
            path_entries.append(str(Path(git_shell).parent))
    return {**env, "PATH": os.pathsep.join(dict.fromkeys(path_entries))}



def _myspec_ready_state(cli: Path, root: Path, command: str = "add") -> Path:
    work = root / ".local" / "spec-work"
    conflicts = root / "no-conflicts.json"
    _myspec_write(conflicts, "[]")
    initialized = _myspec_run_python(
        cli, "state-init", work, command, "specs-fingerprint", "input-fingerprint"
    )
    assert initialized.returncode == 0, initialized.stderr
    stored = _myspec_run_python(
        cli,
        "state-set-conflicts",
        work,
        conflicts,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert stored.returncode == 0, stored.stderr
    return work



def _myspec_apply_ready(
    cli: Path,
    specs: Path,
    delta: Path,
    output: Path,
    work: Path,
) -> subprocess.CompletedProcess[str]:
    return _myspec_run_python(
        cli,
        "apply-delta",
        specs,
        delta,
        output,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )



def _myspec_pack_myspec_version(tmp_path: Path, version: str, marker: Path | None = None) -> Path:
    source = tmp_path / f"myspec-{version}"
    shutil.copytree(_MYSPEC_PLUGIN_ROOT, source)
    for relative in ("package.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        path = source / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        value["version"] = version
        _myspec_write(path, json.dumps(value, indent=2))
    if marker is not None:
        launcher = source / "bin" / "myspec.js"
        text = launcher.read_text(encoding="utf-8")
        text = text.replace(
            'const path = require("node:path");',
            'const path = require("node:path");\n'
            'require("node:fs").appendFileSync(process.env.MYSPEC_REEXEC_MARKER, `${process.pid}\\n`);',
        )
        _myspec_write(launcher, text)
    management = (_MYSPEC_REPO_ROOT / "plugins" / "tool-lifecycle" / "python" / "management.py").read_text(encoding="utf-8")
    _myspec_write(source / "python" / "management.py", management)
    package_dir = tmp_path / f"package-{version}"
    package_dir.mkdir()
    packed = subprocess.run(
        [shutil.which("npm") or "npm", "pack", "--ignore-scripts", "--json", "--pack-destination", str(package_dir)],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert packed.returncode == 0, packed.stderr
    return package_dir / json.loads(packed.stdout)[0]["filename"]



def _myspec_install_removed_pi_command(root: Path) -> tuple[Path, Path]:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    script = root / "fake_pi.py"
    log = root / "pi.log"
    _myspec_write(script, "import os, sys\nfrom pathlib import Path\n"
          'Path(os.environ["MYSPEC_PI_LOG"]).write_text("unexpected Pi invocation", encoding="utf-8")\n'
          "raise SystemExit(99)")
    launcher = bin_dir / ("pi.cmd" if os.name == "nt" else "pi")
    _myspec_write(launcher, f'@"{sys.executable}" "{script}" %*' if os.name == "nt"
          else f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
    if os.name != "nt":
        launcher.chmod(0o755)
    return bin_dir, log



def _myspec_install_fake_claude(root: Path) -> tuple[Path, Path, Path]:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    script = root / "fake_claude.py"
    log = root / "claude.log"
    state = root / "claude-state.json"
    _myspec_write(
        script,
        """import json
import os
import shutil
import sys
from pathlib import Path

arguments = sys.argv[1:]
state_path = Path(os.environ["MYSPEC_CLAUDE_STATE"])
state = json.loads(state_path.read_text(encoding="utf-8"))
with Path(os.environ["MYSPEC_CLAUDE_LOG"]).open("a", encoding="utf-8") as log:
    log.write(json.dumps(arguments) + "\\n")

def save():
    state_path.write_text(json.dumps(state, indent=2) + "\\n", encoding="utf-8")

def marketplace(name):
    return next((item for item in state["marketplaces"] if item["name"] == name), None)

def plugin(identifier):
    return next((item for item in state["plugins"] if item["id"] == identifier), None)

def refresh(identifier):
    name, market_name = identifier.split("@", 1)
    market = marketplace(market_name)
    if market is None or market.get("source") != "directory":
        print("missing local marketplace", file=sys.stderr)
        raise SystemExit(1)
    source = Path(market["path"])
    manifest = json.loads((source / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    target = Path(os.environ["MYSPEC_CLAUDE_HOME"]) / "plugins" / "cache" / market_name / name / manifest["version"]
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    current = plugin(identifier)
    record = {
        "id": identifier,
        "version": os.environ.get("MYSPEC_CLAUDE_REPORTED_VERSION", manifest["version"]),
        "scope": "user",
        "enabled": current["enabled"] if current else True,
        "installPath": str(target),
    }
    if current:
        state["plugins"][state["plugins"].index(current)] = record
    else:
        state["plugins"].append(record)
    save()

if arguments == ["plugin", "marketplace", "list", "--json"]:
    print(json.dumps(state["marketplaces"]))
elif arguments == ["plugin", "list", "--json"]:
    print(json.dumps(state["plugins"]))
elif arguments[:3] == ["plugin", "marketplace", "add"] and len(arguments) == 4:
    source = Path(arguments[3])
    manifest = json.loads((source / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    if marketplace(manifest["name"]) is None:
        state["marketplaces"].append({
            "name": manifest["name"],
            "source": "directory",
            "path": str(source),
            "installLocation": str(source),
        })
        save()
elif arguments[:2] == ["plugin", "install"] and arguments[3:] == ["--scope", "user"]:
    if os.environ.get("MYSPEC_CLAUDE_FAIL_INSTALL") == "1":
        print("simulated install failure", file=sys.stderr)
        raise SystemExit(1)
    refresh(arguments[2])
    if os.environ.get("MYSPEC_CLAUDE_FAIL_AFTER_INSTALL") == "1":
        print("simulated interruption after install", file=sys.stderr)
        raise SystemExit(1)
elif arguments[:2] == ["plugin", "update"] and arguments[3:] == ["--scope", "user"]:
    current = plugin(arguments[2])
    name, market_name = arguments[2].split("@", 1)
    source = Path(marketplace(market_name)["path"])
    version = json.loads((source / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    if current is None or current["version"] != version:
        refresh(arguments[2])
elif arguments[:2] == ["plugin", "uninstall"] and arguments[3:] == ["--scope", "user", "--keep-data"]:
    current = plugin(arguments[2])
    if current is None:
        print("missing plugin", file=sys.stderr)
        raise SystemExit(1)
    if os.environ.get("MYSPEC_CLAUDE_UNINSTALL_NOOP") != "1":
        state["plugins"].remove(current)
        save()
    if os.environ.get("MYSPEC_CLAUDE_FAIL_AFTER_UNINSTALL") == "1":
        print("simulated interruption after uninstall", file=sys.stderr)
        raise SystemExit(1)
elif arguments[:2] in (["plugin", "enable"], ["plugin", "disable"]) and arguments[3:] == ["--scope", "user"]:
    current = plugin(arguments[2])
    if current is None:
        print("missing plugin", file=sys.stderr)
        raise SystemExit(1)
    current["enabled"] = arguments[1] == "enable"
    save()
    if os.environ.get("MYSPEC_CLAUDE_FAIL_AFTER_ENABLED") == str(current["enabled"]).lower():
        print("simulated interruption after enabled state", file=sys.stderr)
        raise SystemExit(1)
elif arguments[:3] == ["plugin", "marketplace", "update"] and len(arguments) == 4:
    if marketplace(arguments[3]) is None:
        raise SystemExit(1)
else:
    raise SystemExit(2)
""",
    )
    if sys.platform == "win32":
        launcher = bin_dir / "claude.cmd"
        _myspec_write(launcher, f'@"{sys.executable}" "{script}" %*')
    else:
        launcher = bin_dir / "claude"
        _myspec_write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
        launcher.chmod(0o755)
    return bin_dir, log, state



def _myspec_install_fake_codex(root: Path) -> tuple[Path, Path, Path]:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    script = root / "fake_codex.py"
    log = root / "codex.log"
    state = root / "codex-state.json"
    _myspec_write(
        script,
        '''import json
import os
import re
import shutil
import sys
from pathlib import Path

arguments = sys.argv[1:]
state_path = Path(os.environ["MYSPEC_CODEX_STATE"])
state = json.loads(state_path.read_text(encoding="utf-8"))
config_path = Path(os.environ["CODEX_HOME"]) / "config.toml"
with Path(os.environ["MYSPEC_CODEX_LOG"]).open("a", encoding="utf-8") as log:
    log.write(json.dumps(arguments) + "\\n")
environment_log = os.environ.get("MYSPEC_CODEX_ENV_LOG")
if environment_log:
    with Path(environment_log).open("a", encoding="utf-8") as log:
        log.write(os.environ.get("CODEX_HOME", "") + "\\n")

def save():
    state_path.write_text(json.dumps(state, indent=2) + "\\n", encoding="utf-8")

def marketplace(name):
    return next((item for item in state["marketplaces"] if item["name"] == name), None)

def plugin(identifier):
    return next((item for item in state["installed"] if item["pluginId"] == identifier), None)

def set_enabled(identifier, enabled):
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    header = f'[plugins."{identifier}"]'
    pattern = re.compile(rf'(?ms)^\\[plugins\\."{re.escape(identifier)}"\\]\\s*\\n(?P<body>.*?)(?=^\\[|\\Z)')
    match = pattern.search(text)
    body = f"enabled = {'true' if enabled else 'false'}\\n"
    if match:
        current = match.group("body")
        current = re.sub(r"(?m)^enabled\\s*=.*$", body.rstrip(), current, count=1) if re.search(r"(?m)^enabled\\s*=", current) else body + current
        text = text[:match.start("body")] + current + text[match.end("body"):]
    else:
        text = text.rstrip() + ("\\n\\n" if text.strip() else "") + header + "\\n" + body
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(text, encoding="utf-8")

def remove_config(identifier):
    if not config_path.exists():
        return
    text = config_path.read_text(encoding="utf-8")
    pattern = re.compile(rf'(?ms)^\\[plugins\\."{re.escape(identifier)}"\\]\\s*\\n.*?(?=^\\[|\\Z)')
    config_path.write_text(pattern.sub("", text), encoding="utf-8")

def configured_enabled(identifier):
    if not config_path.exists():
        return False
    text = config_path.read_text(encoding="utf-8")
    pattern = re.compile(rf'(?ms)^\\[plugins\\."{re.escape(identifier)}"\\]\\s*\\n(?P<body>.*?)(?=^\\[|\\Z)')
    match = pattern.search(text)
    return bool(match and re.search(r"(?m)^enabled\\s*=\\s*true\\s*$", match.group("body")))

def install(identifier):
    name, market_name = identifier.split("@", 1)
    market = marketplace(market_name)
    if market is None:
        print("missing marketplace", file=sys.stderr)
        raise SystemExit(1)
    root = Path(market["root"])
    catalog = json.loads((root / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    entry = next((item for item in catalog["plugins"] if item["name"] == name), None)
    if entry is None:
        print("missing plugin", file=sys.stderr)
        raise SystemExit(1)
    relative = entry["source"]["path"]
    source = (root / relative).resolve()
    manifest = json.loads((source / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    target = Path(os.environ["CODEX_HOME"]) / "plugins" / "cache" / market_name / name / manifest["version"]
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    current = plugin(identifier)
    record = {
        "pluginId": identifier,
        "name": name,
        "marketplaceName": market_name,
        "version": os.environ.get("MYSPEC_CODEX_REPORTED_VERSION", manifest["version"]),
        "installed": True,
        "source": {"source": "local", "path": str(source)},
        "marketplaceSource": market.get("marketplaceSource"),
        "installPolicy": "AVAILABLE",
        "authPolicy": "ON_INSTALL",
    }
    if current:
        state["installed"][state["installed"].index(current)] = record
    else:
        state["installed"].append(record)
    set_enabled(identifier, True)
    save()

if arguments == ["plugin", "marketplace", "list", "--json"]:
    print(json.dumps({"marketplaces": state["marketplaces"]}))
elif arguments == ["plugin", "list", "--json"]:
    installed = [{**item, "enabled": configured_enabled(item["pluginId"])} for item in state["installed"]]
    print(json.dumps({"installed": installed, "available": state["available"]}))
elif arguments[:3] == ["plugin", "marketplace", "add"] and arguments[-1:] == ["--json"]:
    requested = Path(arguments[3])
    source = requested.resolve()
    catalog = json.loads((source / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    if marketplace(catalog["name"]) is None:
        state["marketplaces"].append({
            "name": catalog["name"],
            "root": str(source),
            "marketplaceSource": {"sourceType": "local", "source": str(source)},
        })
        save()
    print(json.dumps({"name": catalog["name"], "root": str(source)}))
elif arguments[:2] == ["plugin", "add"] and arguments[-1:] == ["--json"]:
    install(arguments[2])
    if os.environ.get("MYSPEC_CODEX_FAIL_AFTER_ADD") == "1":
        print("simulated interruption after add", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({"pluginId": arguments[2]}))
elif arguments[:2] == ["plugin", "remove"] and arguments[-1:] == ["--json"]:
    current = plugin(arguments[2])
    if current is None:
        print("missing plugin", file=sys.stderr)
        raise SystemExit(1)
    if os.environ.get("MYSPEC_CODEX_REMOVE_NOOP") != "1":
        target = Path(os.environ["CODEX_HOME"]) / "plugins" / "cache" / current["marketplaceName"] / current["name"] / current["version"]
        if target.exists():
            shutil.rmtree(target)
        state["installed"].remove(current)
        remove_config(arguments[2])
        save()
    if os.environ.get("MYSPEC_CODEX_FAIL_AFTER_REMOVE") == "1":
        print("simulated interruption after remove", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({"pluginId": arguments[2]}))
else:
    raise SystemExit(2)
''',
    )
    if sys.platform == "win32":
        launcher = bin_dir / "codex.cmd"
        _myspec_write(launcher, f'@"{sys.executable}" "{script}" %*')
    else:
        launcher = bin_dir / "codex"
        _myspec_write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
        launcher.chmod(0o755)
    return bin_dir, log, state



def _myspec_install_fake_npm(root: Path, release_tarball: Path) -> tuple[Path, Path]:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    script = root / "fake_npm.py"
    log = root / "npm.log"
    log.touch()
    npm = shutil.which("npm")
    assert npm is not None
    _myspec_write(
        script,
        """import json
import os
import subprocess
import sys
from pathlib import Path

arguments = sys.argv[1:]
with Path(os.environ["MYSPEC_NPM_LOG"]).open("a", encoding="utf-8") as log:
    log.write(json.dumps(arguments) + "\\n")
if arguments == ["view", "@liuli195/myspec", "version", "--json"]:
    print(json.dumps(os.environ.get("MYSPEC_NPM_LATEST", os.environ["MYSPEC_PACKAGE_VERSION"])))
    raise SystemExit(0)
if arguments == ["root", "--global"] and os.environ.get("MYSPEC_NPM_FAIL_ROOT") == "1":
    print("simulated npm root failure", file=sys.stderr)
    raise SystemExit(1)
if arguments[:2] == ["install", "--global"]:
    if os.environ.get("MYSPEC_NPM_FAIL_INSTALL") == "1":
        print("simulated install failure", file=sys.stderr)
        raise SystemExit(1)
    arguments[-1] = os.environ["MYSPEC_RELEASE_TARBALL"]
allowed = arguments in (["root", "--global"], ["prefix", "--global"], ["link"]) or (
    arguments[:2] == ["install", "--global"] and len(arguments) == 6
    and arguments[2:5] == ["--ignore-scripts", "--no-audit", "--no-fund"]
)
if not allowed:
    print("unsupported fake npm command", file=sys.stderr)
    raise SystemExit(127)
command = [os.environ["MYSPEC_REAL_NPM"], *arguments]
if os.name == "nt":
    result = subprocess.run(subprocess.list2cmdline(command), shell=True)
else:
    result = subprocess.run(command)
if arguments[:2] == ["install", "--global"] and result.returncode == 0 and os.environ.get("MYSPEC_NPM_FAIL_AFTER_INSTALL") == "1":
    print("simulated interruption after npm install", file=sys.stderr)
    raise SystemExit(1)
raise SystemExit(result.returncode)
""",
    )
    if sys.platform == "win32":
        launcher = bin_dir / "npm.cmd"
        _myspec_write(launcher, f'@"{sys.executable}" "{script}" %*')
    else:
        launcher = bin_dir / "npm"
        _myspec_write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
        launcher.chmod(0o755)
    return bin_dir, log



def _myspec_isolated_myspec_env(
    tmp_path: Path,
    prefix: Path,
    *extra_paths: Path,
) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    package_bin = prefix if os.name == "nt" else prefix / "bin"
    path_entries = [str(package_bin), *(str(path) for path in extra_paths)]
    command_paths = [shutil.which(command) for command in ("node", "npm", "git")]
    if os.name == "nt":
        path_entries.extend(
            str(Path(path).parent) for path in command_paths if path is not None
        )
        path_entries.append(str(Path(sys.executable).parent))
    else:
        command_bin = tmp_path / "system-commands"
        command_bin.mkdir(exist_ok=True)
        for path in command_paths:
            assert path is not None
            link = command_bin / Path(path).name
            if not link.exists():
                link.symlink_to(Path(path).resolve())
        path_entries.append(str(command_bin))
    return {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PI_CODING_AGENT_DIR": str(home / ".pi" / "agent"),
        "NPM_CONFIG_PREFIX": str(prefix),
        "MYSPEC_PYTHON": sys.executable,
        "MYSPEC_PACKAGE_VERSION": os.environ.get("MYSPEC_PACKAGE_VERSION", ""),
        "PATH": os.pathsep.join(path_entries),
    }



def _myspec_windows_py_launcher() -> Path:
    base_executable = Path(getattr(sys, "_base_executable", sys.executable))
    candidates = (
        base_executable.parent.parent / "Launcher" / "py.exe",
        Path(os.environ.get("SystemRoot", "C:/Windows")) / "py.exe",
        Path(shutil.which("py") or ""),
    )
    launcher = next(
        (path for path in candidates if path.is_file() and "WindowsApps" not in path.parts),
        None,
    )
    assert launcher is not None
    return launcher



def _myspec_run_launcher_selection(
    executable: Path,
    root: Path,
    versions: dict[str, str],
    override_version: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[Path], dict[str, Path]]:
    candidates = root / "candidates"
    candidates.mkdir(parents=True)
    python_source = Path(
        getattr(sys, "_base_executable", sys.executable)
        if sys.platform == "win32"
        else sys.executable
    )
    launcher = _myspec_windows_py_launcher() if "py" in versions else None
    paths: dict[str, Path] = {}
    reported_versions: dict[str, str] = {}
    for name, version in versions.items():
        if name == "py":
            # Native Windows launchers are location-sensitive; do not copy them.
            paths[name] = launcher.resolve()
            continue
        source = python_source
        path = candidates / (f"{name}.exe" if sys.platform == "win32" else name)
        shutil.copy2(source, path)
        paths[name] = path.resolve()
        if version == "3.11":
            reported_versions[os.path.normcase(str(paths[name]))] = version

    path_entries = [str(candidates)]
    if launcher is not None:
        path_entries.append(str(launcher.parent))
    path_entries.extend(
        (
            str(Path(shutil.which("node") or "").parent),
            str(python_source.parent),
        )
    )
    env = {
        **os.environ,
        "PATH": os.pathsep.join(path_entries),
        "PYTHONPATH": str(root),
        "PYTHONHOME": sys.base_prefix,
        "MYSPEC_TEST_MARKER": str(root / "selected.txt"),
    }
    env.pop("MYSPEC_PYTHON", None)
    if override_version is not None:
        override = root / ("override.exe" if sys.platform == "win32" else "override")
        shutil.copy2(python_source, override)
        env["MYSPEC_PYTHON"] = str(override)
        paths["MYSPEC_PYTHON"] = override.resolve()
        if override_version == "3.11":
            reported_versions[os.path.normcase(str(paths["MYSPEC_PYTHON"]))] = override_version
    if sys.platform == "win32" and versions.get("py") == "3.11":
        reported_versions[os.path.normcase(str(python_source.resolve()))] = "3.11"
    env["MYSPEC_TEST_VERSIONS"] = json.dumps(reported_versions)
    _myspec_write(
        root / "sitecustomize.py",
        """import json
import os
import sys
from pathlib import Path

executable = Path(sys.executable).resolve()
with Path(os.environ["MYSPEC_TEST_MARKER"]).open("a", encoding="utf-8") as marker:
    marker.write(str(executable) + "\\n")
version = json.loads(os.environ["MYSPEC_TEST_VERSIONS"]).get(os.path.normcase(str(executable)))
if version:
    major, minor = map(int, version.split("."))
    sys.version_info = type("VersionInfo", (), {"major": major, "minor": minor})()
""",
    )
    result = _myspec_run_cli(executable, "--help", env=env)
    marker = Path(env["MYSPEC_TEST_MARKER"])
    observed = (
        [Path(line) for line in marker.read_text(encoding="utf-8").splitlines()]
        if marker.exists()
        else []
    )
    return result, observed, paths



@pytest.fixture(scope="session")
def _myspec_recovery_package(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    # Recovery cases only mutate their own consumer data, not the installed package.
    return _myspec_install_packed_myspec(tmp_path_factory.mktemp("recovery-package"))



@pytest.fixture
def _myspec_recovery_cli(tmp_path: Path, _myspec_recovery_package: tuple[Path, Path]):
    executable, package = _myspec_recovery_package
    environment = tmp_path / "recovery-environment"
    environment.mkdir()
    env = _myspec_isolated_myspec_env(environment, npm_prefix_for(package))
    assert Path(shutil.which("myspec", path=env["PATH"])).resolve() == executable.resolve()

    def bare(*args: object, extra_env: dict[str, str] | None = None):
        return subprocess.run(
            ["myspec", *(str(arg) for arg in args)],
            cwd=tmp_path,
            env={**env, **(extra_env or {})},
            text=True,
            capture_output=True,
            check=False,
            shell=os.name == "nt",
        )

    return bare



@pytest.fixture(scope="session")
def _myspec_recovery_git_seed() -> dict[str, Path]:
    return {}



@pytest.fixture
def _myspec_recovery_git_project(tmp_path: Path, tmp_path_factory: pytest.TempPathFactory,
                         request: pytest.FixtureRequest, _myspec_recovery_git_seed: dict[str, Path]) -> Path:
    from tests.support.git_templates import copy_template
    if "path" not in _myspec_recovery_git_seed:
        project = request.getfixturevalue("git_project")
        seed = tmp_path_factory.mktemp("recovery-git-seed") / "project"
        copy_template(project, seed)
        # Publish only a complete, pristine repository, before recovery state exists.
        _myspec_recovery_git_seed["path"] = seed
        return project
    return copy_template(_myspec_recovery_git_seed["path"], tmp_path / "project")



@pytest.fixture
def _myspec_recovery_session(_myspec_recovery_git_project: Path, _myspec_recovery_cli):
    git_project = _myspec_recovery_git_project
    work = git_project / ".local" / "spec-work"
    specs = git_project / "myspec" / "specs"
    delta = work / "current" / "delta"
    preview = work / "current" / "preview"
    _myspec_write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
    initialized = _myspec_recovery_cli("state-init", work, "add", "specs", "input")
    assert initialized.returncode == 0, initialized.stderr
    _myspec_write(delta / "accounts" / "spec.md", "## MODIFIED Requirements\n\n" + requirement("登录", "允许密码登录"))
    conflicts = git_project / "conflicts.json"
    _myspec_write(conflicts, json.dumps([{
        "id": "login", "candidate": "密码登录", "evidence": ["request"],
        "reason": "需要确认", "recommendation": "accept",
    }]))
    for result in (
        _myspec_recovery_cli("state-set-conflicts", work, conflicts, "specs", "input"),
        _myspec_recovery_cli("state-decide", work, "login", "accept", "specs", "input"),
        _myspec_recovery_cli("apply-delta", specs, delta, preview, work, "specs", "input"),
    ):
        assert result.returncode == 0, result.stderr
    return git_project, work, specs, delta, preview



def _myspec_abort_arguments(session, cli) -> list[object]:
    target, work, specs, delta, preview = session
    digest = hashlib.sha256((work / "current" / "state.json").read_bytes()).hexdigest()
    state = json.loads((work / "current" / "state.json").read_text(encoding="utf-8"))
    inspected = cli("state-status", work, state["specsFingerprint"], state["inputFingerprint"], "--abort-identity")
    lock_identity = json.loads(inspected.stdout)["abortIdentity"]["lockIdentitySha256"] if inspected.returncode == 0 else "0" * 64
    return ["state-abort", work, target, specs, delta, preview, digest, "add", "--lock-identity", lock_identity, "--confirm-no-active-session"]



def _myspec_controlled_dev_source(tmp_path: Path, marker: str | None = None) -> Path:
    return _myspec_real_controlled_dev_source(tmp_path, marker)


def _myspec_install_packed_myspec(tmp_path: Path) -> tuple[Path, Path]:
    candidate = candidate_for("myspec")
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    shutil.copy2(candidate.tarball, package_dir / candidate.tarball.name)
    return copy_install(candidate, tmp_path / "npm-prefix")


def _myspec_run_python(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(script), *(str(arg) for arg in args)],
                          cwd=_MYSPEC_REPO_ROOT, text=True, capture_output=True, check=False)


def _myspec_run_cli(executable: Path, *args: object, env=None, cwd=None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(executable), *(str(arg) for arg in args)],
                          cwd=cwd, env=env, text=True, capture_output=True, check=False)


def _myspec_run_public_spec_cli(*args: object) -> subprocess.CompletedProcess[str]:
    return _myspec_run_cli(candidate_for("myspec").executable, *args)


def _myspec_run_in_process(script: Path, *args: object, env=None, cwd=None) -> subprocess.CompletedProcess[str]:
    # Only the unknown-process-status case needs a controlled OS-status leaf.
    # The installed command still runs its actual main and physical lock I/O.
    stdout, stderr = io.StringIO(), io.StringIO()
    previous_cwd = Path.cwd()
    previous_environment = os.environ.copy()
    try:
        if env is not None:
            os.environ.clear()
            os.environ.update(env)
        os.chdir(cwd or _MYSPEC_REPO_ROOT)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = _myspec_load_in_process_spec_ops(script).main([str(arg) for arg in args])
    finally:
        os.chdir(previous_cwd)
        os.environ.clear()
        os.environ.update(previous_environment)
    return subprocess.CompletedProcess([str(script), *map(str, args)], code, stdout.getvalue(), stderr.getvalue())


def _myspec_memory_migration_ready_state(cli, root, command="add"):
    work = root / ".local" / "spec-work"
    conflicts = root / "no-conflicts.json"
    _myspec_write(conflicts, "[]")
    for args in (("state-init", work, command, "specs-fingerprint", "input-fingerprint"),
                 ("state-set-conflicts", work, conflicts, "specs-fingerprint", "input-fingerprint")):
        result = _myspec_run_in_process(cli, *args)
        assert result.returncode == 0, result.stderr
    return work


def _myspec_memory_migration_apply_ready(cli, specs, delta, output, work):
    return _myspec_run_in_process(cli, "apply-delta", specs, delta, output, work,
                                  "specs-fingerprint", "input-fingerprint")


def _myspec_memory_migration_confirmed_workflow(
    cli: Path,
    specs: Path,
    delta: Path,
    preview: Path,
    *expected_diff: str,
) -> str:
    work = _myspec_memory_migration_ready_state(cli, preview.parent)
    validated = _myspec_run_in_process(cli, "validate-delta", delta, specs)
    assert validated.returncode == 0, validated.stderr
    generated = _myspec_run_in_process(
        cli,
        "apply-delta",
        specs,
        delta,
        preview,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert generated.returncode == 0, generated.stderr
    assert _myspec_run_in_process(cli, "validate-main", preview).returncode == 0
    diff = _myspec_run_in_process(cli, "diff", specs, preview)
    assert diff.returncode == 0, diff.stderr
    for fragment in expected_diff:
        assert fragment in diff.stdout
    applied = _myspec_run_in_process(
        cli,
        "apply-delta",
        specs,
        delta,
        specs,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert applied.returncode == 0, applied.stderr
    assert _myspec_run_in_process(cli, "validate-main", specs).returncode == 0
    assert _myspec_run_in_process(cli, "diff", specs, preview).stdout == ""
    return diff.stdout


class TestMySpec:
    def test_candidate_controller_prepares_once_and_preserves_supplied_tarball(self, tmp_path, monkeypatch, npm_candidate):
        from types import SimpleNamespace
        from tests.support import npm_candidates as candidates
        spec = importlib.util.spec_from_file_location("myspec_candidate_controller", REPO_ROOT / "tests/integration/conftest.py")
        assert spec is not None and spec.loader is not None
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
        supplied = tmp_path / "supplied.tgz"
        shutil.copy2(npm_candidate.tarball, supplied)
        original_bytes = supplied.read_bytes()
        original_mkdtemp = tempfile.mkdtemp
        monkeypatch.setattr(controller.tempfile, "mkdtemp", lambda **kwargs: original_mkdtemp(dir=tmp_path, **kwargs))
        prepared = []
        original_prepare = candidates.prepare_candidate
        def prepare(name, root, *, tarball=None):
            assert name == "myspec" and tarball == supplied
            prepared.append(root)
            return original_prepare(name, root, tarball=tarball)
        def install(command):
            prefix = Path(command[command.index("--prefix") + 1])
            assert command == [npm_candidate.npm, "install", "--global", "--prefix", str(prefix),
                "--ignore-scripts", "--no-audit", "--no-fund", str(prefix.parent / "package" / supplied.name)]
            shutil.copytree(npm_candidate.prefix, prefix)
            return ""
        monkeypatch.setattr(candidates, "prepare_candidate", prepare)
        monkeypatch.setattr(candidates, "_run", install)
        monkeypatch.delenv(candidates.CANDIDATES_ENV, raising=False)
        monkeypatch.setenv(candidates.TARBALL_ENV["myspec"], str(supplied))
        cleanups = []
        config = SimpleNamespace(args=[str(REPO_ROOT / "tests/integration/test_npm.py") + "::TestMySpec"],
            invocation_params=SimpleNamespace(dir=REPO_ROOT), add_cleanup=cleanups.append)
        try:
            controller.pytest_configure(config)
            controller.pytest_configure(config)
            worker = SimpleNamespace(**vars(config), workerinput={})
            controller.pytest_configure(worker)
            inherited = candidates.candidate_for("myspec")
            assert prepared == [inherited.prefix.parent]
            assert inherited.tarball != supplied and inherited.tarball.read_bytes() == original_bytes
            first, package = candidates.copy_install(inherited, tmp_path / "first-install")
            second, other = candidates.copy_install(inherited, tmp_path / "second-install")
            assert first != second and package != other
            manifest = package / "package.json"
            manifest.write_bytes(manifest.read_bytes() + b"\n")
            assert other.joinpath("package.json").read_bytes() == inherited.installed_package.joinpath("package.json").read_bytes()
            assert supplied.read_bytes() == original_bytes
            assert os.environ[candidates.TARBALL_ENV["myspec"]] == str(supplied)
        finally:
            for cleanup in reversed(cleanups):
                cleanup()
        assert len(prepared) == 1 and not prepared[0].parent.exists()
        assert supplied.read_bytes() == original_bytes
        assert os.environ[candidates.TARBALL_ENV["myspec"]] == str(supplied)


    @pytest.mark.parametrize("failure", ["pack-start", "missing-resource"])
    def test_candidate_failed_preparation_cleans_only_owned_partial_state(self, tmp_path, monkeypatch, npm_candidate, failure):
        from tests.support import npm_candidates as candidates
        supplied = tmp_path / "supplied.tgz"
        shutil.copy2(npm_candidate.tarball, supplied)
        before = supplied.read_bytes()
        owned = tmp_path / "owned-candidate"
        def execute(command):
            if failure == "pack-start":
                assert command == [sys.executable, str(candidates.PACK), "myspec", str(owned / "package")]
                raise OSError("candidate pack cannot start")
            prefix = Path(command[command.index("--prefix") + 1])
            assert command[0:3] == [npm_candidate.npm, "install", "--global"]
            shutil.copytree(npm_candidate.prefix, prefix)
            candidates._writable(prefix)
            (prefix / npm_candidate.installed_package.relative_to(npm_candidate.prefix) / "python/spec_ops.py").unlink()
            return ""
        monkeypatch.setattr(candidates, "_run", execute)
        expected = OSError if failure == "pack-start" else FileNotFoundError
        with pytest.raises(expected) as error:
            candidates.prepare_candidate("myspec", owned, tarball=None if failure == "pack-start" else supplied)
        if failure == "pack-start":
            assert "candidate pack cannot start" in str(error.value)
        assert not owned.exists() and supplied.read_bytes() == before
        assert npm_candidate.executable.is_file()


    def test_candidate_baseline_reaches_two_real_workers_with_private_installs(self, tmp_path, npm_candidate):
        reports = tmp_path / "reports"
        reports.mkdir()
        probe = tmp_path / "test_candidate_workers.py"
        probe.write_text("""import json
import os
from pathlib import Path
from tests.support.npm_candidates import candidate_for, copy_install


def test_candidate_inheritance(tmp_path):
    candidate = candidate_for("myspec")
    executable, package = copy_install(candidate, tmp_path / "prefix")
    home = tmp_path / "home"
    home.mkdir()
    assert executable.is_file()
    manifest = package / "package.json"
    original = manifest.read_bytes()
    manifest.write_bytes(original + b"\\n")
    assert candidate.installed_package.joinpath("package.json").read_bytes() == original
    report = {"tarball": str(candidate.tarball), "baseline": str(candidate.prefix),
        "prefix": str(executable), "home": str(home), "package": str(package)}
    Path(os.environ["OWN_SKILLS_CANDIDATE_REPORTS"], os.environ["PYTEST_XDIST_WORKER"] + ".json").write_text(json.dumps(report))
""", encoding="utf-8")
        before = npm_candidate.installed_package.joinpath("package.json").read_bytes()
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "-n", "2", "--dist=each", "--rootdir", str(REPO_ROOT), "--basetemp", str(tmp_path / "workers"), str(probe)],
            cwd=REPO_ROOT, env={**os.environ, "OWN_SKILLS_CANDIDATE_REPORTS": str(reports),
                "PYTHONPATH": os.pathsep.join(filter(None, [str(REPO_ROOT), os.environ.get("PYTHONPATH")]))},
            text=True, capture_output=True, check=False, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        paths = sorted(reports.glob("gw*.json"))
        assert [path.stem for path in paths] == ["gw0", "gw1"]
        payloads = [json.loads(path.read_text()) for path in paths]
        assert {item["tarball"] for item in payloads} == {str(npm_candidate.tarball)}
        assert {item["baseline"] for item in payloads} == {str(npm_candidate.prefix)}
        for field in ("prefix", "home", "package"):
            assert len({item[field] for item in payloads}) == 2
        assert npm_candidate.installed_package.joinpath("package.json").read_bytes() == before


    @pytest.fixture(autouse=True)
    def _package_versions(self, npm_candidate, monkeypatch):
        global bumped_patch, main_spec, npm_prefix_for, requirement
        from tests.support.myspec_cases import bumped_patch, main_spec, npm_prefix_for, requirement
        global _MYSPEC_PACKAGE_VERSION, _MYSPEC_PREVIOUS_VERSION, _MYSPEC_NEXT_VERSION, _MYSPEC_LATER_VERSION
        _MYSPEC_PACKAGE_VERSION = json.loads((npm_candidate.installed_package / "package.json").read_text(encoding="utf-8"))["version"]
        _MYSPEC_PREVIOUS_VERSION = bumped_patch(_MYSPEC_PACKAGE_VERSION, -1)
        _MYSPEC_NEXT_VERSION = bumped_patch(_MYSPEC_PACKAGE_VERSION)
        _MYSPEC_LATER_VERSION = bumped_patch(_MYSPEC_PACKAGE_VERSION, 2)
        monkeypatch.setenv("MYSPEC_PACKAGE_VERSION", _MYSPEC_PACKAGE_VERSION)


    def test_packed_myspec_bare_cli_uses_isolated_package_before_host_commands(self,
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        installed = tmp_path / "installed"
        installed.mkdir()
        executable, installed_package = _myspec_install_packed_myspec(installed)
        prefix = npm_prefix_for(installed_package)
        host_bin = tmp_path / "host-bin"
        host_bin.mkdir()
        host_markers = {}
        host_commands = {}
        for name in ("myspec", "pi", "claude", "codex"):
            marker = tmp_path / f"host-{name}.used"
            host_markers[name] = marker
            script = tmp_path / f"host-{name}.py"
            _myspec_write(
                script,
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('used', encoding='utf-8')\nraise SystemExit(99)",
            )
            command = host_bin / (f"{name}.cmd" if os.name == "nt" else name)
            host_commands[name] = command
            if os.name == "nt":
                _myspec_write(command, f'@"{sys.executable}" "{script}" %*')
            else:
                _myspec_write(command, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
                command.chmod(0o755)

        host_path = os.pathsep.join((str(host_bin), os.environ["PATH"]))
        monkeypatch.setenv("PATH", host_path)
        for name, command in host_commands.items():
            resolved_host = shutil.which(name)
            assert resolved_host is not None
            assert Path(resolved_host).resolve() == command.resolve()

        env = _myspec_isolated_myspec_env(tmp_path, prefix)

        resolved = shutil.which("myspec", path=env["PATH"])
        assert resolved is not None
        assert Path(resolved).resolve() == executable.resolve()
        assert shutil.which("pi", path=env["PATH"]) is None
        assert shutil.which("claude", path=env["PATH"]) is None
        assert shutil.which("codex", path=env["PATH"]) is None

        project = tmp_path / "consumer"
        specs = project / "myspec" / "specs"
        delta = project / "myspec" / "delta"
        preview = project / ".local" / "spec-preview"
        work = project / ".local" / "spec-work"
        conflicts = project / "no-conflicts.json"
        _myspec_write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
        _myspec_write(
            delta / "accounts" / "spec.md",
            '## MODIFIED Requirements\n\n### Requirement: 登录\n\n系统 MUST 允许密码登录。\n\n#### Scenario: 密码正确\n\n- **WHEN** 用户提交正确密码\n- **THEN** 系统创建会话\n',
        )
        _myspec_write(conflicts, "[]")

        def run_bare(*args: object) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["myspec", *(str(arg) for arg in args)],
                cwd=project,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                shell=os.name == "nt",
            )

        for result in (
            run_bare("validate-main", specs),
            run_bare("state-init", work, "add", "specs-fingerprint", "input-fingerprint"),
            run_bare("state-set-conflicts", work, conflicts, "specs-fingerprint", "input-fingerprint"),
            run_bare("validate-delta", delta, specs),
            run_bare(
                "apply-delta",
                specs,
                delta,
                preview,
                work,
                "specs-fingerprint",
                "input-fingerprint",
            ),
        ):
            assert result.returncode == 0, result.stderr

        diff = run_bare("diff", specs, preview)
        assert diff.returncode == 0, diff.stderr
        assert "密码登录" in diff.stdout

        applied = run_bare(
            "apply-delta",
            specs,
            delta,
            specs,
            work,
            "specs-fingerprint",
            "input-fingerprint",
        )
        assert applied.returncode == 0, applied.stderr
        validated = run_bare("validate-main", specs)
        assert validated.returncode == 0, validated.stderr
        assert "系统 MUST 允许密码登录。" in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")
        assert not any(marker.exists() for marker in host_markers.values())


    def test_packed_myspec_update_recovers_external_success_before_bookkeeping(self,
        tmp_path: Path,
    ) -> None:
        installed = tmp_path / "installed"
        installed.mkdir()
        executable, installed_package = _myspec_install_packed_myspec(installed)
        prefix = npm_prefix_for(installed_package)
        old_tarball = next((installed / "package").glob("*.tgz"))
        marker = tmp_path / "new-cli.log"
        new_tarball = _myspec_pack_myspec_version(tmp_path, _MYSPEC_NEXT_VERSION, marker)
        npm_bin, npm_log = _myspec_install_fake_npm(tmp_path / "fake-npm", old_tarball)
        claude_bin, claude_log, claude_state = _myspec_install_fake_claude(tmp_path / "fake-claude")
        codex_bin, codex_log, codex_state = _myspec_install_fake_codex(tmp_path / "fake-codex")
        env = _myspec_isolated_myspec_env(tmp_path, prefix, npm_bin, claude_bin, codex_bin)
        env.update(
            {
                "MYSPEC_NPM_LOG": str(npm_log),
                "MYSPEC_REAL_NPM": str(shutil.which("npm")),
                "MYSPEC_RELEASE_TARBALL": str(old_tarball),
                "MYSPEC_NPM_LATEST": _MYSPEC_NEXT_VERSION,
                "MYSPEC_REEXEC_MARKER": str(marker),
                "MYSPEC_CLAUDE_LOG": str(claude_log),
                "MYSPEC_CLAUDE_STATE": str(claude_state),
                "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
                "CODEX_HOME": str(Path(env["HOME"]) / ".codex"),
                "MYSPEC_CODEX_LOG": str(codex_log),
                "MYSPEC_CODEX_STATE": str(codex_state),
            }
        )
        _myspec_write(claude_state, json.dumps({"marketplaces": [], "plugins": []}, indent=2))
        _myspec_write(codex_state, json.dumps({"marketplaces": [], "installed": [], "available": []}, indent=2))
        assert _myspec_run_cli(executable, "init", "--all", env=env).returncode == 0
        for log in (npm_log, claude_log, codex_log):
            log.write_text("", encoding="utf-8")
        env["MYSPEC_RELEASE_TARBALL"] = str(new_tarball)

        failures = [
            ("MYSPEC_NPM_FAIL_AFTER_INSTALL", "npm_install_failed: simulated interruption after npm install"),
            ("MYSPEC_CLAUDE_FAIL_AFTER_UNINSTALL", "claude_plugin_uninstall_failed: simulated interruption after uninstall"),
            ("MYSPEC_CLAUDE_FAIL_AFTER_INSTALL", "claude_plugin_install_failed: simulated interruption after install"),
            ("MYSPEC_CODEX_FAIL_AFTER_ADD", "codex_plugin_add_failed: simulated interruption after add"),
        ]
        for failure_variable, expected_error in failures:
            failed = _myspec_run_cli(executable, "update", env={**env, failure_variable: "1"})
            assert failed.returncode == 1
            assert f"error: {expected_error}" in failed.stderr

        retried = _myspec_run_cli(executable, "update", env=env)

        assert retried.returncode == 0, retried.stderr
        output = json.loads(retried.stdout)
        assert output["version"] == _MYSPEC_NEXT_VERSION
        assert output["doctor"]["cliVersion"] == _MYSPEC_NEXT_VERSION
        assert output["doctor"]["claude"]["version"] == _MYSPEC_NEXT_VERSION
        assert output["doctor"]["codex"]["version"] == _MYSPEC_NEXT_VERSION
        assert marker.read_text(encoding="utf-8").strip()
        npm_calls = [json.loads(line) for line in npm_log.read_text(encoding="utf-8").splitlines()]
        claude_calls = [json.loads(line) for line in claude_log.read_text(encoding="utf-8").splitlines()]
        codex_calls = [json.loads(line) for line in codex_log.read_text(encoding="utf-8").splitlines()]
        assert npm_calls.count(
            ["install", "--global", "--ignore-scripts", "--no-audit", "--no-fund", f"@liuli195/myspec@{_MYSPEC_NEXT_VERSION}"]
        ) == 1
        assert claude_calls.count(
            ["plugin", "uninstall", "my-spec@myspec", "--scope", "user", "--keep-data"]
        ) == 1
        assert claude_calls.count(["plugin", "install", "my-spec@myspec", "--scope", "user"]) == 1
        assert codex_calls.count(["plugin", "add", "my-spec@myspec", "--json"]) == 1
        state_path = Path(env["HOME"]) / ".myspec" / "state.json"
        assert "pendingOperation" not in json.loads(state_path.read_text(encoding="utf-8"))

        wrong_version_tarball = _myspec_pack_myspec_version(tmp_path, _MYSPEC_LATER_VERSION)
        mismatch = _myspec_run_cli(
            executable,
            "update",
            env={
                **env,
                "MYSPEC_RELEASE_TARBALL": str(wrong_version_tarball),
                "MYSPEC_NPM_LATEST": _MYSPEC_LATER_VERSION,
                "MYSPEC_CLAUDE_REPORTED_VERSION": "0.0.0",
            },
        )
        expected_error = "claude_plugin_refresh_version_mismatch"
        assert mismatch.returncode == 1
        assert f"error: {expected_error}" in mismatch.stderr
        pending = json.loads(state_path.read_text(encoding="utf-8"))["pendingOperation"]
        assert pending["targetVersion"] == _MYSPEC_LATER_VERSION
        assert pending["lastError"] == expected_error
        assert "doctor" not in pending["completed"]


    def test_packed_myspec_preserves_lock_when_process_status_is_unknown(self,
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        executable, installed_package = _myspec_install_packed_myspec(tmp_path)
        prefix = npm_prefix_for(installed_package)
        release_tarball = next((tmp_path / "package").glob("*.tgz"))
        npm_bin, npm_log = _myspec_install_fake_npm(tmp_path / "fake-npm", release_tarball)
        spec_ops = _myspec_load_in_process_spec_ops(installed_package / "python" / "spec_ops.py")
        monkeypatch.setitem(spec_ops.run_management.__globals__, "_pid_alive", lambda _pid: None)
        env = _myspec_isolated_myspec_env(tmp_path, prefix, npm_bin)
        env.update(
            {
                "MYSPEC_NPM_LOG": str(npm_log),
                "MYSPEC_REAL_NPM": str(shutil.which("npm")),
                "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            }
        )
        lock_path = Path(env["HOME"]) / ".myspec" / "install.lock"
        lock = {
            "pid": 424242,
            "startedAt": "2000-01-01T00:00:00+00:00",
            "command": "myspec update",
            "operationId": "unknown-process",
        }

        for command in (("init", "--claude"), ("update",)):
            _myspec_write(lock_path, json.dumps(lock, indent=2))
            before = lock_path.read_bytes()
            npm_log.write_text("", encoding="utf-8")

            rejected = _myspec_run_in_process(installed_package / "python" / "spec_ops.py", *command, env=env)

            assert rejected.returncode == 1
            assert "error: install_lock_process_unknown: pid=424242" in rejected.stderr
            assert lock_path.read_bytes() == before
            assert npm_log.read_text(encoding="utf-8") == ""


    def test_packed_myspec_serializes_init_and_reports_locks_without_mutating_them(self,
        tmp_path: Path,
    ) -> None:
        executable, installed_package = _myspec_install_packed_myspec(tmp_path)
        env = _myspec_isolated_myspec_env(tmp_path, npm_prefix_for(installed_package))
        lock_path = Path(env["HOME"]) / ".myspec" / "install.lock"
        for malformed in ({"command": "myspec update"}, {"pid": True}, {"pid": "123"}, {"pid": 0}):
            _myspec_write(lock_path, json.dumps(malformed))
            malformed_before = lock_path.read_bytes()
            rejected = _myspec_run_cli(executable, "init", "--all", env=env)
            assert rejected.returncode == 1
            assert f"error: invalid_install_lock: {lock_path}" in rejected.stderr
            assert lock_path.read_bytes() == malformed_before

        active = {
            "pid": os.getpid(),
            "startedAt": "2000-01-01T00:00:00+00:00",
            "command": "myspec update",
            "operationId": "active",
        }
        _myspec_write(lock_path, json.dumps(active, indent=2))
        before = lock_path.read_bytes()

        diagnosed = _myspec_run_cli(executable, "doctor", env=env)
        blocked = _myspec_run_cli(executable, "init", "--all", env=env)

        assert diagnosed.returncode == 0, diagnosed.stderr
        assert json.loads(diagnosed.stdout)["installation"]["lock"] == {
            "pid": os.getpid(),
            "startedAt": active["startedAt"],
            "command": "myspec update",
            "active": True,
        }
        assert blocked.returncode == 1
        assert f"error: install_locked: pid={os.getpid()}" in blocked.stderr
        assert lock_path.read_bytes() == before

        stale = {**active, "pid": 99999999, "operationId": "stale"}
        _myspec_write(lock_path, json.dumps(stale, indent=2))
        recovered = _myspec_run_cli(executable, "init", "--all", env=env)
        assert recovered.returncode == 0, recovered.stderr
        assert json.loads(lock_path.read_text(encoding="utf-8"))["released"] is True


    @pytest.mark.parametrize("shared_marketplaces_include_tool", [True, False])
    def test_packed_myspec_switches_package_between_development_and_saved_release(self,
        tmp_path: Path,
        shared_marketplaces_include_tool: bool,
    ) -> None:
        executable, installed_package = _myspec_install_packed_myspec(tmp_path)
        prefix = npm_prefix_for(installed_package)
        release_tarball = next((tmp_path / "package").glob("*.tgz"))
        npm_bin, npm_log = _myspec_install_fake_npm(tmp_path / "fake-npm", release_tarball)
        env = _myspec_isolated_myspec_env(tmp_path, prefix, npm_bin)
        env.update(
            {
                "MYSPEC_NPM_LOG": str(npm_log),
                "MYSPEC_REAL_NPM": str(shutil.which("npm")),
                "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            }
        )

        source = _myspec_controlled_dev_source(tmp_path)
        if shared_marketplaces_include_tool:
            for catalog, source_value in (
                (source / ".agents/plugins/marketplace.json", {"source": "local", "path": "./plugins/my-spec"}),
                (source / ".claude-plugin/marketplace.json", "./plugins/my-spec"),
            ):
                content = json.loads(catalog.read_text(encoding="utf-8"))
                content["plugins"].append({"name": "my-spec", "source": source_value})
                catalog.write_text(json.dumps(content), encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=source, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.name=MySpec Test", "-c", "user.email=myspec@example.invalid", "commit", "-m", "legacy shared entries"], cwd=source, check=True, capture_output=True)
        env = _myspec_controlled_dev_env(env, source)
        entered = _myspec_run_cli(executable, "init", "--dev", env=env, cwd=source)
        assert entered.returncode == 0, entered.stderr
        assert subprocess.run(
            ["git", "status", "--porcelain"], cwd=source, text=True, capture_output=True, check=True
        ).stdout == ""
        assert json.loads(entered.stdout) == {
            "mode": "dev",
            "source": str(source),
            "previousReleaseVersion": _MYSPEC_PACKAGE_VERSION,
            "reloadRequired": False,
        }
        state_path = Path(env["HOME"]) / ".myspec" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["mode"] == "dev"
        assert state["source"] == str(source)
        assert state["previousReleaseVersion"] == _MYSPEC_PACKAGE_VERSION
        expected_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True, capture_output=True, check=True
        ).stdout.strip()
        assert state["sourceCommit"] == expected_commit
        dev_report = _myspec_run_cli(executable, "doctor", env=env)
        assert dev_report.returncode == 0, dev_report.stderr
        dev_diagnosis = json.loads(dev_report.stdout)
        assert dev_diagnosis["source"] == str(source / "plugins" / "my-spec")
        assert dev_diagnosis["mode"] == "dev"
        restored = _myspec_run_cli(executable, "init", "--release", env=env)
        assert restored.returncode == 0, restored.stderr
        assert json.loads(restored.stdout) == {
            "mode": "release",
            "version": _MYSPEC_PACKAGE_VERSION,
            "reloadRequired": False,
        }
        assert json.loads(state_path.read_text(encoding="utf-8"))["mode"] == "release"
        report = json.loads(_myspec_run_cli(executable, "doctor", env=env).stdout)
        assert report["mode"] == "release"
        assert report["source"] == str(installed_package)
        npm_calls = [json.loads(line) for line in npm_log.read_text(encoding="utf-8").splitlines()]
        assert ["link"] in npm_calls
        assert ["install", "--global", "--ignore-scripts", "--no-audit", "--no-fund", f"@liuli195/myspec@{_MYSPEC_PACKAGE_VERSION}"] in npm_calls
        assert subprocess.run(
            ["git", "status", "--porcelain"], cwd=source, text=True, capture_output=True, check=True
        ).stdout == ""

        explicit = _myspec_run_cli(executable, "init", "--dev", "--source", source, env=env, cwd=tmp_path)
        assert explicit.returncode == 0, explicit.stderr
        assert json.loads(explicit.stdout)["source"] == str(source)


    def test_packed_myspec_dev_doctor_keeps_published_ancestor_for_unrelated_commit(self,
        tmp_path: Path,
    ) -> None:
        installed = tmp_path / "installed"
        installed.mkdir()
        executable, installed_package = _myspec_install_packed_myspec(installed)
        source = _myspec_controlled_dev_source(tmp_path)
        assert not subprocess.run(
            ["git", "for-each-ref", "--format=%(refname)", "refs/remotes/origin"],
            cwd=source,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        env = _myspec_controlled_dev_env(_myspec_isolated_myspec_env(tmp_path, npm_prefix_for(installed_package)), source)
        assert _myspec_run_cli(executable, "init", "--dev", "--source", source, env=env, cwd=source).returncode == 0

        first = json.loads(_myspec_run_cli(executable, "doctor", env=env, cwd=source).stdout)
        published_commit = first["toolchain"]["sourceCommit"]
        publisher = tmp_path / "publisher"
        assert subprocess.run(
            ["git", "clone", "--branch", "main", str(tmp_path / "origin.git"), publisher], check=False
        ).returncode == 0
        _myspec_write(publisher / "unrelated.txt", "does not ship in the MySpec package")
        assert subprocess.run(["git", "add", "unrelated.txt"], cwd=publisher, check=False).returncode == 0
        assert subprocess.run(
            [
                "git",
                "-c",
                "user.name=MySpec Test",
                "-c",
                "user.email=myspec@example.invalid",
                "commit",
                "-m",
                "unrelated",
            ],
            cwd=publisher,
            check=False,
        ).returncode == 0
        assert subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=publisher, check=False).returncode == 0
        remote_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=publisher, check=True, text=True, capture_output=True
        ).stdout.strip()
        assert subprocess.run(["git", "cat-file", "-e", remote_head], cwd=source, check=False).returncode != 0

        diagnosed = _myspec_run_cli(executable, "doctor", env=env, cwd=source)

        assert diagnosed.returncode == 0, diagnosed.stderr
        assert json.loads(diagnosed.stdout)["toolchain"]["sourceCommit"] == published_commit
        assert subprocess.run(["git", "cat-file", "-e", remote_head], cwd=source, check=False).returncode == 0
        assert not subprocess.run(
            ["git", "for-each-ref", "--format=%(refname)", "refs/remotes/origin"],
            cwd=source,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()


    def test_packed_myspec_reuses_confirmation_when_implementation_diff_is_unchanged(self,
        tmp_path: Path,
    ) -> None:
        installed = tmp_path / "installed"
        installed.mkdir()
        executable, installed_package = _myspec_install_packed_myspec(installed)
        env = _myspec_isolated_myspec_env(tmp_path, npm_prefix_for(installed_package))
        source = _myspec_controlled_dev_source(tmp_path, "first")
        env = _myspec_controlled_dev_env(env, source)
        assert _myspec_run_cli(executable, "init", "--dev", "--source", source, env=env, cwd=source).returncode == 0

        specs = source / "myspec" / "specs"
        delta = source / "myspec" / "delta"
        preview = source / ".local" / "spec-preview"
        _myspec_write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
        _myspec_write(
            delta / "accounts" / "spec.md",
            '## MODIFIED Requirements\n\n### Requirement: 登录\n\n系统 MUST 允许密码登录。\n\n#### Scenario: 密码正确\n\n- **WHEN** 用户提交正确密码\n- **THEN** 系统创建会话\n',
        )
        work = source / ".local" / "spec-work"
        conflicts = source / "no-conflicts.json"
        _myspec_write(conflicts, "[]")
        assert _myspec_run_cli(
            executable,
            "state-init",
            work,
            "add",
            "specs-fingerprint",
            "input-fingerprint",
            env=env,
            cwd=source,
        ).returncode == 0
        assert _myspec_run_cli(
            executable,
            "state-set-conflicts",
            work,
            conflicts,
            "specs-fingerprint",
            "input-fingerprint",
            env=env,
            cwd=source,
        ).returncode == 0
        previewed = _myspec_run_cli(
            executable,
            "apply-delta",
            specs,
            delta,
            preview,
            work,
            "specs-fingerprint",
            "input-fingerprint",
            env=env,
            cwd=source,
        )
        assert previewed.returncode == 0, previewed.stderr

        skill = source / "plugins" / "my-spec" / "skills" / "my-spec" / "SKILL.md"
        _myspec_write(skill, skill.read_text(encoding="utf-8") + "\nimplementation-only change")
        applied = _myspec_run_cli(
            executable,
            "apply-delta",
            specs,
            delta,
            specs,
            work,
            "specs-fingerprint",
            "input-fingerprint",
            env=env,
            cwd=source,
        )

        assert applied.returncode == 0, applied.stderr
        assert "系统 MUST 允许密码登录。" in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")


    def test_packed_myspec_dev_doctor_drops_commit_after_closure_branch_removed(self,
        tmp_path: Path,
    ) -> None:
        installed = tmp_path / "installed"
        installed.mkdir()
        executable, installed_package = _myspec_install_packed_myspec(installed)
        source = _myspec_controlled_dev_source(tmp_path)
        env = _myspec_controlled_dev_env(_myspec_isolated_myspec_env(tmp_path, npm_prefix_for(installed_package)), source)
        entered = _myspec_run_cli(executable, "init", "--dev", "--source", source, env=env, cwd=source)
        assert entered.returncode == 0, entered.stderr

        skill = source / "plugins" / "my-spec" / "skills" / "my-spec" / "SKILL.md"
        _myspec_write(skill, skill.read_text(encoding="utf-8") + "\nclosure change")
        assert subprocess.run(["git", "-C", str(source), "add", str(skill)], check=False).returncode == 0
        committed = subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "-c",
                "user.name=MySpec Test",
                "-c",
                "user.email=myspec@example.invalid",
                "commit",
                "-m",
                "closure change",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assert committed.returncode == 0, committed.stderr
        local_commit = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        pushed = subprocess.run(
            ["git", "-C", str(source), "push", "origin", "HEAD:refs/heads/closure-change"],
            text=True,
            capture_output=True,
            check=False,
        )
        assert pushed.returncode == 0, pushed.stderr

        published = _myspec_run_cli(executable, "doctor", env=env, cwd=source)
        assert published.returncode == 0, published.stderr
        assert json.loads(published.stdout)["toolchain"]["sourceCommit"] == local_commit

        deleted = subprocess.run(
            ["git", "-C", str(source), "push", "origin", "--delete", "closure-change"],
            text=True,
            capture_output=True,
            check=False,
        )
        assert deleted.returncode == 0, deleted.stderr
        unpublished = _myspec_run_cli(executable, "doctor", env=env, cwd=source)
        assert unpublished.returncode == 0, unpublished.stderr
        assert "sourceCommit" not in json.loads(unpublished.stdout)["toolchain"]


    def test_packed_myspec_dev_binding_allows_cross_worktree_apply_with_target_context(self,
        tmp_path: Path,
    ) -> None:
        installed = tmp_path / "installed"
        installed.mkdir()
        executable, installed_package = _myspec_install_packed_myspec(installed)
        prefix = npm_prefix_for(installed_package)
        (tmp_path / "source-a").mkdir()
        source_a = _myspec_controlled_dev_source(tmp_path / "source-a")
        configured = subprocess.run(
            ["git", "-C", str(source_a), "config", "core.autocrlf", "false"],
            text=True,
            capture_output=True,
            check=False,
        )
        assert configured.returncode == 0, configured.stderr
        source_b = tmp_path / "source-b"
        worktree = subprocess.run(
            [
                "git",
                "-C",
                str(source_a),
                "worktree",
                "add",
                "-b",
                "worktree-b",
                str(source_b),
                "HEAD",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assert worktree.returncode == 0, worktree.stderr

        target = main_spec(
            "Accounts",
            requirement("登录", "允许登录"),
            requirement("旧设置", "显示设置"),
        )
        delta_text = '## REMOVED Requirements\n\n### Requirement: 旧设置\n'

        def add_spec_fixture(source: Path, remote_branch: str) -> None:
            _myspec_write(source / "myspec" / "specs" / "accounts" / "spec.md", target)
            _myspec_write(source / "myspec" / "delta" / "accounts" / "spec.md", delta_text)
            _myspec_write(source / "myspec" / "specs" / "profiles" / "spec.md", main_spec("Profiles", requirement("查看资料", "显示姓名")))
            settings = source / "myspec" / "specs" / "settings" / "spec.md"
            settings.parent.mkdir(parents=True, exist_ok=True)
            settings.write_bytes(main_spec("Settings", requirement("修改设置", "保存设置")).replace("\n", "\r\n").encode("utf-8"))
            subprocess.run(
                ["git", "-C", str(source), "add", "myspec"],
                text=True,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=MySpec Test",
                    "-c",
                    "user.email=myspec@example.invalid",
                    "commit",
                    "-m",
                    "spec fixture",
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            pushed = subprocess.run(
                ["git", "-C", str(source), "push", "origin", f"HEAD:refs/heads/{remote_branch}"],
                text=True,
                capture_output=True,
                check=False,
            )
            assert pushed.returncode == 0, pushed.stderr

        add_spec_fixture(source_a, "main")
        add_spec_fixture(source_b, "worktree-b")

        def head(source: Path) -> str:
            return subprocess.run(
                ["git", "-C", str(source), "rev-parse", "HEAD"],
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()

        env = _myspec_isolated_myspec_env(tmp_path, prefix)
        env_a = _myspec_controlled_dev_env(env, source_a)
        env_b = env_a
        entered = _myspec_run_cli(executable, "init", "--dev", "--source", source_a, env=env_a, cwd=source_a)
        assert entered.returncode == 0, entered.stderr

        diagnosis = _myspec_run_cli(executable, "doctor", env=env_a, cwd=source_b)
        assert diagnosis.returncode == 0, diagnosis.stderr
        report = json.loads(diagnosis.stdout)
        assert report["binding"] == {
            "sourceWorktree": str(source_a),
            "sourceCommit": head(source_a),
            "targetWorktree": str(source_b),
            "targetCommit": head(source_b),
            "worktreeMatch": False,
        }

        specs = source_b / "myspec" / "specs"
        delta = source_b / "myspec" / "delta"
        preview = source_b / ".local" / "spec-preview"
        work = source_b / ".local" / "spec-work"
        conflicts = tmp_path / "no-conflicts.json"
        _myspec_write(conflicts, "[]")
        assert _myspec_run_cli(
            executable,
            "state-init",
            work,
            "add",
            "specs-fingerprint",
            "input-fingerprint",
            env=env_a,
            cwd=source_b,
        ).returncode == 0
        assert _myspec_run_cli(
            executable,
            "state-set-conflicts",
            work,
            conflicts,
            "specs-fingerprint",
            "input-fingerprint",
            env=env_a,
            cwd=source_b,
        ).returncode == 0
        before = {
            relative: (specs / relative).read_bytes()
            for relative in ("accounts/spec.md", "profiles/spec.md", "settings/spec.md")
        }
        source_before = {
            relative: (source_a / "myspec" / "specs" / relative).read_bytes()
            for relative in before
        }
        status = _myspec_run_cli(
            executable,
            "state-status",
            work,
            "specs-fingerprint",
            "input-fingerprint",
            env=env_a,
            cwd=source_b,
        )
        assert status.returncode == 0, status.stderr
        assert json.loads(status.stdout) == {"status": "READY_TO_APPLY", "total": 0, "decided": 0, "remaining": 0}

        previewed = _myspec_run_cli(
            executable,
            "apply-delta",
            specs,
            delta,
            preview,
            work,
            "specs-fingerprint",
            "input-fingerprint",
            env=env_a,
            cwd=source_b,
        )
        assert previewed.returncode == 0, previewed.stderr
        assert (preview / "profiles" / "spec.md").read_bytes() == before["profiles/spec.md"]
        assert (preview / "settings" / "spec.md").read_bytes() == before["settings/spec.md"]
        assert {relative: (specs / relative).read_bytes() for relative in before} == before
        diffed = _myspec_run_cli(executable, "diff", specs, preview, env=env_a, cwd=source_b)
        assert diffed.returncode == 0, diffed.stderr
        assert "旧设置" in diffed.stdout
        wrong_diff = _myspec_run_cli(executable, "diff", source_a / "myspec" / "specs", preview, env=env_a, cwd=source_b)
        assert wrong_diff.returncode != 0
        assert "cross_worktree_path" in wrong_diff.stderr
        wrong_apply = _myspec_run_cli(
            executable,
            "apply-delta",
            source_a / "myspec" / "specs",
            delta,
            preview,
            work,
            "specs-fingerprint",
            "input-fingerprint",
            env=env_a,
            cwd=source_b,
        )
        assert wrong_apply.returncode != 0
        assert "cross_worktree_path" in wrong_apply.stderr
        assert work.exists()

        applied = _myspec_run_cli(
            executable,
            "apply-delta",
            specs,
            delta,
            specs,
            work,
            "specs-fingerprint",
            "input-fingerprint",
            env=env_a,
            cwd=source_b,
        )
        assert applied.returncode == 0, applied.stderr
        assert (specs / "profiles" / "spec.md").read_bytes() == before["profiles/spec.md"]
        assert (specs / "settings" / "spec.md").read_bytes() == before["settings/spec.md"]
        assert "旧设置".encode("utf-8") not in (specs / "accounts" / "spec.md").read_bytes()
        assert {
            relative: (source_a / "myspec" / "specs" / relative).read_bytes()
            for relative in source_before
        } == source_before
        assert not work.exists()
        after_first = {
            relative: (specs / relative).read_bytes()
            for relative in before
        }

        repeated_work = source_b / ".local" / "spec-work-repeat"
        repeated_conflicts = tmp_path / "repeated-no-conflicts.json"
        _myspec_write(repeated_conflicts, "[]")
        assert _myspec_run_cli(
            executable,
            "state-init",
            repeated_work,
            "add",
            "specs-fingerprint",
            "input-fingerprint",
            env=env_b,
            cwd=source_b,
        ).returncode == 0
        assert _myspec_run_cli(
            executable,
            "state-set-conflicts",
            repeated_work,
            repeated_conflicts,
            "specs-fingerprint",
            "input-fingerprint",
            env=env_b,
            cwd=source_b,
        ).returncode == 0
        shutil.rmtree(preview)
        repeated_preview = _myspec_run_cli(
            executable,
            "apply-delta",
            specs,
            delta,
            preview,
            repeated_work,
            "specs-fingerprint",
            "input-fingerprint",
            env=env_b,
            cwd=source_b,
        )
        assert repeated_preview.returncode == 0, repeated_preview.stderr
        repeated = _myspec_run_cli(
            executable,
            "apply-delta",
            specs,
            delta,
            specs,
            repeated_work,
            "specs-fingerprint",
            "input-fingerprint",
            env=env_b,
            cwd=source_b,
        )
        assert repeated.returncode == 0, repeated.stderr
        assert not repeated_work.exists()
        assert {relative: (specs / relative).read_bytes() for relative in before} == after_first


    def test_packed_myspec_refreshes_enabled_codex_across_global_mode_switches(self,
        tmp_path: Path,
    ) -> None:
        installed = tmp_path / "installed"
        installed.mkdir()
        executable, installed_package = _myspec_install_packed_myspec(installed)
        prefix = npm_prefix_for(installed_package)
        release_tarball = next((installed / "package").glob("*.tgz"))
        npm_bin, npm_log = _myspec_install_fake_npm(tmp_path / "fake-npm", release_tarball)
        codex_bin, codex_log, codex_state = _myspec_install_fake_codex(tmp_path / "fake-codex")
        env = _myspec_isolated_myspec_env(tmp_path, prefix, npm_bin, codex_bin)
        env.update(
            {
                "MYSPEC_NPM_LOG": str(npm_log),
                "MYSPEC_REAL_NPM": str(shutil.which("npm")),
                "MYSPEC_RELEASE_TARBALL": str(release_tarball),
                "CODEX_HOME": str(Path(env["HOME"]) / ".codex"),
                "MYSPEC_CODEX_LOG": str(codex_log),
                "MYSPEC_CODEX_STATE": str(codex_state),
            }
        )
        _myspec_write(codex_state, json.dumps({"marketplaces": [], "installed": [], "available": []}, indent=2))
        assert _myspec_run_cli(executable, "init", "--codex", env=env).returncode == 0
        codex_log.write_text("", encoding="utf-8")

        source = _myspec_controlled_dev_source(tmp_path, "development source")
        env = _myspec_controlled_dev_env(env, source)

        entered = _myspec_run_cli(executable, "init", "--dev", "--source", source, env=env)
        assert entered.returncode == 0, entered.stderr
        entered_output = json.loads(entered.stdout)
        assert entered_output["codex"] == "refreshed"
        assert entered_output["newSessionRequired"] is True
        assert entered_output["reloadRequired"] is False
        state = json.loads(codex_state.read_text(encoding="utf-8"))
        plugin = next(item for item in state["installed"] if item["pluginId"] == "my-spec@myspec")
        assert plugin["source"] == {"source": "local", "path": str(source / "plugins" / "my-spec")}
        dev_cache = Path(env["CODEX_HOME"]) / "plugins" / "cache" / "myspec" / "my-spec" / _MYSPEC_PACKAGE_VERSION
        assert (dev_cache / "skills" / "my-spec" / "dev-marker.txt").read_text(
            encoding="utf-8"
        ) == "development source\n"

        restored = _myspec_run_cli(executable, "init", "--release", env=env)
        assert restored.returncode == 0, restored.stderr
        restored_output = json.loads(restored.stdout)
        assert restored_output["codex"] == "refreshed"
        assert restored_output["newSessionRequired"] is True
        assert restored_output["reloadRequired"] is False
        state = json.loads(codex_state.read_text(encoding="utf-8"))
        plugin = next(item for item in state["installed"] if item["pluginId"] == "my-spec@myspec")
        assert plugin["source"] == {"source": "local", "path": str(installed_package)}
        assert not (dev_cache / "skills" / "my-spec" / "dev-marker.txt").exists()
        calls = [json.loads(line) for line in codex_log.read_text(encoding="utf-8").splitlines()]
        assert calls.count(["plugin", "remove", "my-spec@myspec", "--json"]) == 2
        assert calls.count(["plugin", "add", "my-spec@myspec", "--json"]) == 2
        assert not any(call[:3] == ["plugin", "marketplace", "upgrade"] for call in calls)


    def test_packed_myspec_refreshes_enabled_claude_across_global_mode_switches(self,
        tmp_path: Path,
    ) -> None:
        installed = tmp_path / "installed"
        installed.mkdir()
        executable, installed_package = _myspec_install_packed_myspec(installed)
        prefix = npm_prefix_for(installed_package)
        release_tarball = next((installed / "package").glob("*.tgz"))
        npm_bin, npm_log = _myspec_install_fake_npm(tmp_path / "fake-npm", release_tarball)
        claude_bin, claude_log, claude_state = _myspec_install_fake_claude(tmp_path / "fake-claude")
        env = _myspec_isolated_myspec_env(tmp_path, prefix, npm_bin, claude_bin)
        env.update(
            {
                "MYSPEC_NPM_LOG": str(npm_log),
                "MYSPEC_REAL_NPM": str(shutil.which("npm")),
                "MYSPEC_RELEASE_TARBALL": str(release_tarball),
                "MYSPEC_CLAUDE_LOG": str(claude_log),
                "MYSPEC_CLAUDE_STATE": str(claude_state),
                "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
            }
        )
        _myspec_write(claude_state, json.dumps({"marketplaces": [], "plugins": []}, indent=2))
        assert _myspec_run_cli(executable, "init", "--claude", env=env).returncode == 0
        claude_log.write_text("", encoding="utf-8")

        source = _myspec_controlled_dev_source(tmp_path, "development source")
        env = _myspec_controlled_dev_env(env, source)

        entered = _myspec_run_cli(executable, "init", "--dev", "--source", source, env=env)
        assert entered.returncode == 0, entered.stderr
        assert json.loads(entered.stdout)["claude"] == "refreshed"
        state = json.loads(claude_state.read_text(encoding="utf-8"))
        plugin = next(item for item in state["plugins"] if item["id"] == "my-spec@myspec")
        dev_cache = Path(plugin["installPath"])
        assert (dev_cache / "skills" / "my-spec" / "dev-marker.txt").read_text(
            encoding="utf-8"
        ) == "development source\n"

        restored = _myspec_run_cli(executable, "init", "--release", env=env)
        assert restored.returncode == 0, restored.stderr
        assert json.loads(restored.stdout)["claude"] == "refreshed"
        state = json.loads(claude_state.read_text(encoding="utf-8"))
        plugin = next(item for item in state["plugins"] if item["id"] == "my-spec@myspec")
        assert not (Path(plugin["installPath"]) / "skills" / "my-spec" / "dev-marker.txt").exists()
        calls = [json.loads(line) for line in claude_log.read_text(encoding="utf-8").splitlines()]
        assert calls.count(["plugin", "marketplace", "update", "myspec"]) == 2
        assert calls.count(["plugin", "uninstall", "my-spec@myspec", "--scope", "user", "--keep-data"]) == 2
        assert calls.count(["plugin", "install", "my-spec@myspec", "--scope", "user"]) == 2
        assert calls.count(["plugin", "enable", "my-spec@myspec", "--scope", "user"]) == 0
        assert not any(call[:2] == ["plugin", "update"] for call in calls)


    def test_packed_myspec_release_install_failure_stays_in_dev_and_retries(self,
        tmp_path: Path,
    ) -> None:
        executable, installed_package = _myspec_install_packed_myspec(tmp_path)
        prefix = npm_prefix_for(installed_package)
        release_tarball = next((tmp_path / "package").glob("*.tgz"))
        npm_bin, npm_log = _myspec_install_fake_npm(tmp_path / "fake-npm", release_tarball)
        env = _myspec_isolated_myspec_env(tmp_path, prefix, npm_bin)
        env.update(
            {
                "MYSPEC_NPM_LOG": str(npm_log),
                "MYSPEC_REAL_NPM": str(shutil.which("npm")),
                "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            }
        )

        source = _myspec_controlled_dev_source(tmp_path)
        env = _myspec_controlled_dev_env(env, source)
        entered = _myspec_run_cli(executable, "init", "--dev", env=env, cwd=source)
        assert entered.returncode == 0, entered.stderr
        state_path = Path(env["HOME"]) / ".myspec" / "state.json"

        failed_env = {**env, "MYSPEC_NPM_FAIL_INSTALL": "1"}
        failed = _myspec_run_cli(executable, "init", "--release", env=failed_env)
        assert failed.returncode == 1
        assert "error: npm_install_failed: simulated install failure" in failed.stderr
        failed_state = json.loads(state_path.read_text(encoding="utf-8"))
        assert failed_state["mode"] == "dev"
        assert failed_state["previousReleaseVersion"] == _MYSPEC_PACKAGE_VERSION

        retried = _myspec_run_cli(executable, "init", "--release", env=env)
        assert retried.returncode == 0, retried.stderr
        assert json.loads(state_path.read_text(encoding="utf-8"))["mode"] == "release"


    def test_atomic_management_write_retries_windows_sharing_violation(self,
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        management = _myspec_load_management_module()
        target = tmp_path / "settings.json"
        target.write_text("{}\n", encoding="utf-8")
        attempts = 0

        def transient_replace(source: Path, destination: Path) -> Path:
            nonlocal attempts
            attempts += 1
            raise PermissionError("simulated file watcher sharing violation")

        monkeypatch.setattr(management.os, "name", "nt")
        monkeypatch.setattr(Path, "replace", transient_replace)
        monkeypatch.setattr(management.time, "sleep", lambda _seconds: None)

        management._atomic_json(target, {"packages": ["myspec"]})

        assert attempts == 5
        assert json.loads(target.read_text(encoding="utf-8")) == {"packages": ["myspec"]}


    def test_packed_myspec_installs_a_working_cli_with_agent_resources(self, tmp_path: Path) -> None:
        executable, installed_package = _myspec_install_packed_myspec(tmp_path)
        assert not list(installed_package.rglob("__pycache__"))
        assert not list(installed_package.rglob("*.pyc"))
        path_candidates = {"python3.12": "3.12", "python3": "3.12", "python": "3.12"}
        if sys.platform == "win32":
            path_candidates["py"] = "3.12"

        override, observed, paths = _myspec_run_launcher_selection(
            executable,
            tmp_path / "override-case",
            path_candidates,
            override_version="3.12",
        )
        assert override.returncode == 0, override.stderr
        assert observed[-1] == paths["MYSPEC_PYTHON"]

        cases = [
            ({**path_candidates}, "python3.12"),
            ({**path_candidates, "python3.12": "3.11"}, "python3"),
            ({**path_candidates, "python3.12": "3.11", "python3": "3.11"}, "python"),
        ]
        if sys.platform == "win32":
            cases.append(({name: "3.11" for name in path_candidates} | {"py": "3.12"}, "py"))
        for index, (versions, expected) in enumerate(cases):
            result, observed, paths = _myspec_run_launcher_selection(
                executable,
                tmp_path / f"priority-case-{index}",
                versions,
                override_version="3.11" if index == 0 else None,
            )
            assert result.returncode == 0, result.stderr
            if expected == "py":
                assert observed[-1] not in paths.values()
            else:
                assert observed[-1] == paths[expected]

        ineligible_versions = {name: "3.11" for name in path_candidates}
        ineligible, _, _ = _myspec_run_launcher_selection(
            executable,
            tmp_path / "ineligible-case",
            ineligible_versions,
            override_version="3.11",
        )
        assert ineligible.returncode != 0
        assert "error: Python 3.12 or newer is required" in ineligible.stderr
        assert ineligible.stderr.count("(3.11)") == len(ineligible_versions) + 1

        help_result = _myspec_run_cli(executable, "--help")
        assert help_result.returncode == 0
        assert help_result.stdout.startswith("usage: myspec ")
        for command in (
            "state-init",
            "state-set-conflicts",
            "state-current",
            "state-decide",
            "state-status",
            "validate-main",
            "validate-delta",
            "apply-delta",
            "diff",
        ):
            assert command in help_result.stdout

        specs = tmp_path / "specs"
        delta = tmp_path / "delta"
        preview = tmp_path / "preview"
        work = tmp_path / "work"
        conflicts_file = tmp_path / "conflicts.json"
        _myspec_write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
        _myspec_write(
            delta / "accounts" / "spec.md",
            '## ADDED Requirements\n\n### Requirement: 注销\n\n系统 MUST 允许用户注销。\n\n#### Scenario: 主动注销\n\n- **WHEN** 用户选择注销\n- **THEN** 系统结束会话\n',
        )
        conflict = {
            "id": "conflict-1",
            "candidate": "新增注销",
            "evidence": ["accounts/spec.md:1"],
            "reason": "需要确认",
            "recommendation": "接受",
        }
        _myspec_write(conflicts_file, json.dumps([conflict], ensure_ascii=False))

        for command in (
            _myspec_run_cli(executable, "validate-main", specs),
            _myspec_run_cli(executable, "validate-delta", delta, specs),
            _myspec_run_cli(executable, "state-init", work, "add", "specs-fingerprint", "input-fingerprint"),
        ):
            assert command.returncode == 0, command.stderr
            assert command.stdout == ""
            assert command.stderr == ""

        stored = _myspec_run_cli(
            executable,
            "state-set-conflicts",
            work,
            conflicts_file,
            "specs-fingerprint",
            "input-fingerprint",
        )
        assert stored.returncode == 0, stored.stderr
        assert json.loads(stored.stdout) == {"status": "WAITING_DECISION", "total": 1, "remaining": 1}
        current = _myspec_run_cli(executable, "state-current", work, "specs-fingerprint", "input-fingerprint")
        assert current.returncode == 0, current.stderr
        assert json.loads(current.stdout) == {"index": 0, "total": 1, "conflict": conflict}

        wrong_decision = _myspec_run_cli(
            executable,
            "state-decide",
            work,
            "wrong-conflict",
            "accept",
            "specs-fingerprint",
            "input-fingerprint",
        )
        assert wrong_decision.returncode == 1
        assert "error: unexpected_conflict_id: expected_conflict-1: wrong-conflict" in wrong_decision.stderr
        decided = _myspec_run_cli(
            executable,
            "state-decide",
            work,
            "conflict-1",
            "accept",
            "specs-fingerprint",
            "input-fingerprint",
        )
        assert decided.returncode == 0, decided.stderr
        expected_ready = {"status": "READY_TO_APPLY", "total": 1, "decided": 1, "remaining": 0}
        assert json.loads(decided.stdout) == expected_ready
        status = _myspec_run_cli(executable, "state-status", work, "specs-fingerprint", "input-fingerprint")
        assert status.returncode == 0, status.stderr
        assert json.loads(status.stdout) == expected_ready

        applied = _myspec_run_cli(
            executable,
            "apply-delta",
            specs,
            delta,
            preview,
            work,
            "specs-fingerprint",
            "input-fingerprint",
        )
        assert applied.returncode == 0, applied.stderr
        assert applied.stdout == ""
        assert _myspec_run_cli(executable, "validate-main", preview).returncode == 0
        assert "### Requirement: 注销" in (preview / "accounts" / "spec.md").read_text(encoding="utf-8")
        diff = _myspec_run_cli(executable, "diff", specs, preview)
        assert diff.returncode == 0, diff.stderr
        assert "+### Requirement: 注销" in diff.stdout

        final_apply = _myspec_run_cli(
            executable,
            "apply-delta",
            specs,
            delta,
            specs,
            work,
            "specs-fingerprint",
            "input-fingerprint",
        )
        assert final_apply.returncode == 0, final_apply.stderr
        assert final_apply.stdout == ""
        assert _myspec_run_cli(executable, "validate-main", specs).returncode == 0
        assert _myspec_run_cli(executable, "diff", specs, preview).stdout == ""
        assert (specs / "accounts" / "spec.md").read_bytes() == (
            preview / "accounts" / "spec.md"
        ).read_bytes()
        assert not (work / "current").exists()
        assert not (work / "lock").exists()
        assert not work.exists()
        assert not any(path.name.startswith(".my-spec-") for path in specs.parent.iterdir())

        _myspec_write(
            specs / "accounts" / "spec.md",
            main_spec("Accounts", requirement("登录", "允许登录")).replace("MUST", "必须"),
        )
        invalid = _myspec_run_cli(executable, "validate-main", specs)
        assert invalid.returncode == 1
        assert "error: missing_must_or_shall: 登录" in invalid.stderr
        assert "Traceback" not in invalid.stderr
        missing_argument = _myspec_run_cli(executable, "state-init", work)
        assert missing_argument.returncode == 2
        assert "usage: myspec state-init" in missing_argument.stderr

        node = shutil.which("node")
        assert node is not None
        no_python = _myspec_run_cli(
            executable,
            "validate-main",
            specs,
            env={**os.environ, "PATH": str(Path(node).parent), "MYSPEC_PYTHON": "not-a-python"},
        )
        assert no_python.returncode != 0
        assert "error: Python 3.12 or newer is required" in no_python.stderr
        assert (
            "checked not-a-python (unavailable), python3.12 (unavailable), "
            "python3 (unavailable), python (unavailable)"
        ) in no_python.stderr

        assert {path.name for path in (installed_package / "skills").iterdir()} == set(_MYSPEC_SKILL_NAMES)
        assert (installed_package / ".claude-plugin" / "plugin.json").is_file()
        claude_marketplace = json.loads(
            (installed_package / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        assert claude_marketplace["name"] == "myspec"
        assert claude_marketplace["description"] == "Self-contained MySpec plugin marketplace"
        assert claude_marketplace["plugins"] == [
            {
                "name": "my-spec",
                "source": "./",
                "description": "MySpec audit, review, and document-to-delta Skill（开放规格审计、审查与文档增量技能）",
            }
        ]
        claude_manifest = json.loads(
            (installed_package / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        assert claude_manifest["author"] == {"name": "liuli195"}
        assert (installed_package / ".codex-plugin" / "plugin.json").is_file()
        assert [path.relative_to(installed_package).as_posix() for path in installed_package.rglob("spec_ops.py")] == [
            "python/spec_ops.py",
        ]
        skill_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((installed_package / "skills").rglob("*.md"))
        )
        assert "spec_ops.py" not in skill_text
        rules = (installed_package / "skills" / "my-spec" / "references" / "myspec-rules.md").read_text(
            encoding="utf-8"
        )
        for command in (
            "state-init",
            "state-set-conflicts",
            "state-current",
            "state-decide",
            "state-status",
            "validate-main",
            "validate-delta",
            "apply-delta",
            "diff",
        ):
            assert f"myspec {command}" in rules


    def test_myspec_launcher_forwards_sigterm_to_python(self, tmp_path: Path) -> None:
        if sys.platform == "win32":
            pytest.skip("Windows cannot deliver a catchable SIGTERM to another process")
        executable, installed_package = _myspec_install_packed_myspec(tmp_path)
        marker = tmp_path / "signal.txt"
        ready = tmp_path / "ready.txt"
        (installed_package / "python" / "spec_ops.py").write_text(
            'import os\nimport signal\nimport sys\nimport time\nfrom pathlib import Path\n\nmarker = Path(sys.argv[1])\nready = Path(sys.argv[2])\nparent = os.getppid()\n\ndef stop(signum, _frame):\n    marker.write_text(str(signum), encoding="utf-8")\n    raise SystemExit(0)\n\nsignal.signal(signal.SIGTERM, stop)\nready.write_text("ready", encoding="utf-8")\nwhile os.getppid() == parent:\n    time.sleep(0.01)\n',
            encoding="utf-8",
        )
        process = subprocess.Popen(
            [str(executable), str(marker), str(ready)],
            env={**os.environ, "MYSPEC_PYTHON": sys.executable},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 10
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), "Python child did not start"

        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=10) == 0
        assert marker.read_text(encoding="utf-8") == str(signal.SIGTERM)


    def test_myspec_cli_preserves_untouched_lf_and_crlf_bytes_for_preview_and_apply(self,
        tmp_path: Path,
    ) -> None:
        specs = tmp_path / "specs"
        delta = tmp_path / "delta"
        preview = tmp_path / "preview"
        target = main_spec(
            "Accounts",
            requirement("登录", "允许登录"),
            requirement("旧设置", "显示设置"),
        )
        untouched_lf = main_spec("Profiles", requirement("查看资料", "显示姓名"))
        untouched_crlf = main_spec("Settings", requirement("修改设置", "保存设置"))
        (specs / "accounts" / "spec.md").parent.mkdir(parents=True)
        (specs / "accounts" / "spec.md").write_bytes(target.replace("\n", "\r\n").encode("utf-8"))
        (specs / "profiles" / "spec.md").parent.mkdir(parents=True)
        (specs / "profiles" / "spec.md").write_bytes(untouched_lf.encode("utf-8"))
        (specs / "settings" / "spec.md").parent.mkdir(parents=True)
        (specs / "settings" / "spec.md").write_bytes(untouched_crlf.replace("\n", "\r\n").encode("utf-8"))
        original_lf = (specs / "profiles" / "spec.md").read_bytes()
        original_crlf = (specs / "settings" / "spec.md").read_bytes()
        _myspec_write(
            delta / "accounts" / "spec.md",
            '## MODIFIED Requirements\n\n### Requirement: 登录\n\n系统 MUST 允许密码登录。\n\n#### Scenario: 密码正确\n\n- **WHEN** 用户提交正确密码\n- **THEN** 系统创建会话\n\n## REMOVED Requirements\n\n### Requirement: 旧设置\n',
        )

        work = tmp_path / "state"
        conflicts = tmp_path / "conflicts.json"
        _myspec_write(conflicts, "[]")
        initialized = _myspec_run_public_spec_cli(
            "state-init", work, "add", "specs-fingerprint", "input-fingerprint"
        )
        assert initialized.returncode == 0, initialized.stderr
        stored = _myspec_run_public_spec_cli(
            "state-set-conflicts", work, conflicts, "specs-fingerprint", "input-fingerprint"
        )
        assert stored.returncode == 0, stored.stderr
        before_rejected_apply = {
            relative: (specs / relative).read_bytes()
            for relative in ("accounts/spec.md", "profiles/spec.md", "settings/spec.md")
        }
        rejected = _myspec_run_public_spec_cli(
            "apply-delta", specs, delta, preview, work, "stale-specs-fingerprint", "input-fingerprint"
        )
        assert rejected.returncode != 0
        assert {
            relative: (specs / relative).read_bytes()
            for relative in before_rejected_apply
        } == before_rejected_apply
        assert _myspec_run_public_spec_cli("validate-main", specs).returncode == 0
        assert _myspec_run_public_spec_cli("validate-delta", delta, specs).returncode == 0
        previewed = _myspec_run_public_spec_cli(
            "apply-delta", specs, delta, preview, work, "specs-fingerprint", "input-fingerprint"
        )
        assert previewed.returncode == 0, previewed.stderr
        assert _myspec_run_public_spec_cli("validate-main", preview).returncode == 0
        assert (preview / "profiles" / "spec.md").read_bytes() == original_lf
        assert (preview / "settings" / "spec.md").read_bytes() == original_crlf
        target_preview = (preview / "accounts" / "spec.md").read_bytes()
        assert b"\r" not in target_preview
        assert "系统 MUST 允许密码登录。".encode("utf-8") in target_preview
        assert "旧设置".encode("utf-8") not in target_preview

        applied = _myspec_run_public_spec_cli(
            "apply-delta", specs, delta, specs, work, "specs-fingerprint", "input-fingerprint"
        )
        assert applied.returncode == 0, applied.stderr
        assert _myspec_run_public_spec_cli("validate-main", specs).returncode == 0
        assert (specs / "profiles" / "spec.md").read_bytes() == original_lf
        assert (specs / "settings" / "spec.md").read_bytes() == original_crlf
        assert (specs / "accounts" / "spec.md").read_bytes() == target_preview

        repeated_work = tmp_path / "repeated-state"
        repeated_conflicts = tmp_path / "repeated-conflicts.json"
        _myspec_write(repeated_conflicts, "[]")
        assert _myspec_run_public_spec_cli(
            "state-init", repeated_work, "add", "specs-fingerprint", "input-fingerprint"
        ).returncode == 0
        assert _myspec_run_public_spec_cli(
            "state-set-conflicts",
            repeated_work,
            repeated_conflicts,
            "specs-fingerprint",
            "input-fingerprint",
        ).returncode == 0
        before_repeat = {
            relative: (specs / relative).read_bytes()
            for relative in ("accounts/spec.md", "profiles/spec.md", "settings/spec.md")
        }
        shutil.rmtree(preview)
        repeated_preview = _myspec_run_public_spec_cli(
            "apply-delta", specs, delta, preview, repeated_work, "specs-fingerprint", "input-fingerprint"
        )
        assert repeated_preview.returncode == 0, repeated_preview.stderr
        repeated = _myspec_run_public_spec_cli(
            "apply-delta",
            specs,
            delta,
            specs,
            repeated_work,
            "specs-fingerprint",
            "input-fingerprint",
        )
        assert repeated.returncode == 0, repeated.stderr
        assert {
            relative: (specs / relative).read_bytes()
            for relative in before_repeat
        } == before_repeat


    def test_spec_ops_cli_persists_complete_conflicts_and_resumes_in_a_new_process(self,
        tmp_path: Path,
    ) -> None:
        work = tmp_path / ".local" / "spec-work"
        conflicts_file = tmp_path / "conflicts.json"
        conflicts = [
            {
                "id": f"conflict-{index:02d}",
                "candidate": f"候选 {index}",
                "evidence": [f"spec.md:{index}"],
                "reason": "语义冲突",
                "recommendation": "采用建议",
            }
            for index in range(1, 14)
        ]
        _myspec_write(conflicts_file, json.dumps(conflicts, ensure_ascii=False))

        initialized = _myspec_run_python(
            _MYSPEC_SPEC_OPS,
            "state-init",
            work,
            "review",
            "specs-fingerprint",
            "input-fingerprint",
        )
        assert initialized.returncode == 0, initialized.stderr
        stored = _myspec_run_python(
            _MYSPEC_SPEC_OPS,
            "state-set-conflicts",
            work,
            conflicts_file,
            "specs-fingerprint",
            "input-fingerprint",
        )
        assert stored.returncode == 0, stored.stderr
        assert json.loads(stored.stdout) == {"status": "WAITING_DECISION", "total": 13, "remaining": 13}

        first = json.loads(
            _myspec_run_python(
                _MYSPEC_SPEC_OPS, "state-current", work, "specs-fingerprint", "input-fingerprint"
            ).stdout
        )
        assert first["index"] == 0
        assert first["total"] == 13
        assert first["conflict"] == conflicts[0]

        decided = _myspec_run_python(
            _MYSPEC_SPEC_OPS,
            "state-decide",
            work,
            "conflict-01",
            "accept",
            "specs-fingerprint",
            "input-fingerprint",
        )
        assert decided.returncode == 0, decided.stderr
        second = json.loads(
            _myspec_run_python(
                _MYSPEC_SPEC_OPS, "state-current", work, "specs-fingerprint", "input-fingerprint"
            ).stdout
        )
        assert second["index"] == 1
        assert second["total"] == 13
        assert second["conflict"] == conflicts[1]
        assert json.loads(
            _myspec_run_python(_MYSPEC_SPEC_OPS, "state-status", work, "specs-fingerprint", "input-fingerprint").stdout
        ) == {
            "status": "WAITING_DECISION",
            "total": 13,
            "decided": 1,
            "remaining": 12,
        }


    def test_apply_delta_can_atomically_replace_main_after_final_confirmation(self, tmp_path: Path) -> None:
        specs = tmp_path / "myspec" / "specs"
        delta = tmp_path / "delta"
        preview = tmp_path / "preview"
        _myspec_write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
        _myspec_write(
            delta / "accounts" / "spec.md",
            '## MODIFIED Requirements\n\n### Requirement: 登录\n\n系统 MUST 允许密码登录。\n\n#### Scenario: 密码正确\n\n- **WHEN** 用户提交正确密码\n- **THEN** 系统创建会话\n',
        )

        work = _myspec_ready_state(_MYSPEC_SPEC_OPS, tmp_path / "state")
        previewed = _myspec_apply_ready(_MYSPEC_SPEC_OPS, specs, delta, preview, work)
        assert previewed.returncode == 0, previewed.stderr
        applied = _myspec_apply_ready(_MYSPEC_SPEC_OPS, specs, delta, specs, work)
        assert applied.returncode == 0, applied.stderr
        assert "系统 MUST 允许密码登录。" in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")
        assert not any(path.name.startswith(".my-spec-") for path in specs.parent.iterdir())
        assert not work.exists()
        assert _myspec_run_python(_MYSPEC_SPEC_OPS, "validate-main", specs).returncode == 0

        before = (specs / "accounts" / "spec.md").read_bytes()
        repeated_validation = _myspec_run_python(_MYSPEC_SPEC_OPS, "validate-delta", delta, specs)
        assert repeated_validation.returncode == 0, repeated_validation.stderr
        repeated_work = _myspec_ready_state(_MYSPEC_SPEC_OPS, tmp_path / "repeated-state")
        shutil.rmtree(preview)
        repeated_preview = _myspec_apply_ready(_MYSPEC_SPEC_OPS, specs, delta, preview, repeated_work)
        assert repeated_preview.returncode == 0, repeated_preview.stderr
        repeated = _myspec_apply_ready(_MYSPEC_SPEC_OPS, specs, delta, specs, repeated_work)
        assert repeated.returncode == 0, repeated.stderr
        assert (specs / "accounts" / "spec.md").read_bytes() == before


    def test_myspec_recovery_init_preserves_existing_current(self, tmp_path: Path, _myspec_recovery_cli) -> None:
        work = tmp_path / "consumer" / ".local" / "spec-work"
        draft = work / "current" / "delta" / "accounts" / "spec.md"
        _myspec_write(draft, "not yet analyzed draft\n")
        initialized = _myspec_recovery_cli("state-init", work, "add", "specs", "input")
        assert initialized.returncode != 0
        assert "current_not_empty" in initialized.stderr
        assert draft.read_text(encoding="utf-8") == "not yet analyzed draft\n"
        assert not (work / "lock").exists()


    def test_myspec_recovery_aborts_legacy_preview_and_preserves_material(self,
        _myspec_recovery_session, _myspec_recovery_cli,
    ) -> None:
        target, work, specs, delta, preview = _myspec_recovery_session
        state_path = work / "current" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.pop("sessionId", None)
        state.pop("applicationPhase", None)
        _myspec_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        _myspec_write(work / "lock", "add\n")
        delta_path = delta / "accounts" / "spec.md"
        delta_path.write_text(delta_path.read_text(encoding="utf-8").replace("密码登录", "密码及验证码登录"), encoding="utf-8")
        failed = _myspec_recovery_cli("apply-delta", specs, delta, preview, work, "specs", "input")
        assert failed.returncode != 0
        assert "input_content_changed" in failed.stderr
        _myspec_write(work / "current" / "failure.txt", failed.stderr)
        original = {path.relative_to(work / "current"): path.read_bytes() for path in (work / "current").rglob("*") if path.is_file()}
        arguments = _myspec_abort_arguments(_myspec_recovery_session, _myspec_recovery_cli)
        inspected = _myspec_recovery_cli("state-status", work, "specs", "input", "--abort-identity")
        assert inspected.returncode == 0, inspected.stderr
        identity = json.loads(inspected.stdout)["abortIdentity"]
        assert identity == {
            "stateSha256": arguments[6], "lockIdentitySha256": arguments[9], "lockCommand": "add", "workRoot": str(work),
            "targetWorktree": str(target), "specsRoot": str(specs), "deltaRoot": str(delta),
            "previewRoot": str(preview), "sessionId": None, "applicationPhase": None,
        }
        aborted = _myspec_recovery_cli(*arguments)
        assert aborted.returncode == 0, aborted.stderr
        result = json.loads(aborted.stdout)
        archive = Path(result["archive"])
        assert archive.parent == work / "aborted"
        assert {path.relative_to(archive / "current"): path.read_bytes() for path in (archive / "current").rglob("*") if path.is_file()} == original
        assert not (work / "lock").exists()
        assert not (work / "current").exists()
        assert "允许密码及验证码登录" not in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")
        repeated = _myspec_recovery_cli(*arguments)
        assert repeated.returncode == 0, repeated.stderr
        assert json.loads(repeated.stdout)["archive"] == str(archive)
        assert _myspec_recovery_cli("state-init", work, "add", "new-specs", "new-input").returncode == 0
        new_state = (work / "current" / "state.json").read_bytes()
        new_lock = (work / "lock").read_bytes()
        refused = _myspec_recovery_cli(*arguments)
        assert refused.returncode != 0
        assert (work / "current" / "state.json").read_bytes() == new_state
        assert (work / "lock").read_bytes() == new_lock


    def test_myspec_recovery_reimports_only_delta_and_restarts_confirmation(self,
        _myspec_recovery_session, _myspec_recovery_cli,
    ) -> None:
        target, work, specs, delta, preview = _myspec_recovery_session
        old_state = json.loads((work / "current" / "state.json").read_text(encoding="utf-8"))
        assert old_state["sessionId"]
        old_delta = (delta / "accounts" / "spec.md").read_bytes()
        original_specs = (specs / "accounts" / "spec.md").read_bytes()
        started = time.perf_counter()
        aborted = _myspec_recovery_cli(*_myspec_abort_arguments(_myspec_recovery_session, _myspec_recovery_cli))
        assert aborted.returncode == 0, aborted.stderr
        archive_seconds = time.perf_counter() - started
        archive = Path(json.loads(aborted.stdout)["archive"])
        started = time.perf_counter()
        initialized = _myspec_recovery_cli("state-init", work, "add", "new-specs", "new-input", "--import-aborted", archive)
        assert initialized.returncode == 0, initialized.stderr
        state = json.loads((work / "current" / "state.json").read_text(encoding="utf-8"))
        assert state["sessionId"] != old_state["sessionId"]
        assert state["status"] == "ANALYZING"
        assert state["decisions"] == state["conflicts"] == []
        assert state["currentConflict"] == 0
        assert state["previewRoot"] is None
        assert not preview.exists()
        assert (delta / "accounts" / "spec.md").read_bytes() == old_delta
        blocked = _myspec_recovery_cli("apply-delta", specs, delta, specs, work, "new-specs", "new-input")
        assert blocked.returncode != 0
        assert "expected_READY_TO_APPLY" in blocked.stderr
        conflicts = target / "conflicts.json"
        for result in (
            _myspec_recovery_cli("state-set-conflicts", work, conflicts, "new-specs", "new-input"),
            _myspec_recovery_cli("state-current", work, "new-specs", "new-input"),
            _myspec_recovery_cli("state-decide", work, "login", "accept", "new-specs", "new-input"),
            _myspec_recovery_cli("validate-delta", delta, specs),
            _myspec_recovery_cli("apply-delta", specs, delta, preview, work, "new-specs", "new-input"),
        ):
            assert result.returncode == 0, result.stderr
        difference = _myspec_recovery_cli("diff", specs, preview)
        assert difference.returncode == 0, difference.stderr
        assert "允许密码登录" in difference.stdout
        assert (specs / "accounts" / "spec.md").read_bytes() == original_specs
        rebuilt_seconds = time.perf_counter() - started
        # This isolated consumer explicitly models the existing final-confirmation step.
        applied = _myspec_recovery_cli("apply-delta", specs, delta, specs, work, "new-specs", "new-input")
        assert applied.returncode == 0, applied.stderr
        assert "允许密码登录" in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")
        assert (archive / "current" / "delta" / "accounts" / "spec.md").read_bytes() == old_delta
        print(f"recovery sample: 1 capability; archive={archive_seconds:.3f}s; rebuild-and-preview={rebuilt_seconds:.3f}s")


    @pytest.mark.parametrize("fault", ["failure-before", "failure-after", "interrupt-before", "interrupt-after", "cleanup-lock", "cleanup-draft"])
    def test_myspec_recovery_refuses_interrupted_or_failed_formal_application(self,
        tmp_path: Path, _myspec_recovery_session, _myspec_recovery_cli, fault: str,
    ) -> None:
        target, work, specs, delta, preview = _myspec_recovery_session
        original = (specs / "accounts" / "spec.md").read_bytes()
        draft = (delta / "accounts" / "spec.md").read_bytes()
        injection = tmp_path / "application-fault"
        _myspec_write(injection / "sitecustomize.py", 'import os\nimport shutil\nfrom pathlib import Path\noriginal, original_unlink, original_rmtree = os.rename, os.unlink, shutil.rmtree\n\ndef rename(source, destination, *args, **kwargs):\n    source, destination = Path(source), Path(destination)\n    specs = Path(os.environ["RECOVERY_FAULT_SPECS"])\n    fault = os.environ["RECOVERY_FAULT"]\n    before = source == specs and destination.name.startswith(".my-spec-backup-")\n    after = destination == specs and source.name.startswith(".my-spec-preview-")\n    if before and fault.endswith("before"):\n        if fault.startswith("interrupt"):\n            original(source, destination, *args, **kwargs)\n            os._exit(91)\n        raise OSError("injected failure before formal replacement")\n    result = original(source, destination, *args, **kwargs)\n    if after and fault.endswith("after"):\n        if fault.startswith("interrupt"):\n            os._exit(92)\n        raise OSError("injected failure after formal replacement")\n    return result\n\nos.rename = rename\n\ndef unlink(path, *args, **kwargs):\n    if os.environ["RECOVERY_FAULT"] == "cleanup-lock" and Path(path) == Path(os.environ["RECOVERY_FAULT_WORK"]) / "lock":\n        raise PermissionError("injected final lock cleanup failure")\n    return original_unlink(path, *args, **kwargs)\n\nos.unlink = unlink\n\ndef rmtree(path, *args, **kwargs):\n    if os.environ["RECOVERY_FAULT"] == "cleanup-draft" and Path(path) == Path(os.environ["RECOVERY_FAULT_WORK"]) / "current":\n        raise PermissionError("injected final draft cleanup failure")\n    return original_rmtree(path, *args, **kwargs)\n\nshutil.rmtree = rmtree\n')
        failed = _myspec_recovery_cli("apply-delta", specs, delta, specs, work, "specs", "input", extra_env={
            "PYTHONPATH": str(injection), "RECOVERY_FAULT_SPECS": str(specs), "RECOVERY_FAULT_WORK": str(work), "RECOVERY_FAULT": fault,
        })
        if fault == "cleanup-draft":
            assert failed.returncode == 0, failed.stderr
            assert "session_cleanup_failed" in failed.stderr
            assert "允许密码登录" in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")
            assert not (work / "lock").exists()
            assert (delta / "accounts" / "spec.md").read_bytes() == draft
            refused = _myspec_recovery_cli(*_myspec_abort_arguments(_myspec_recovery_session, _myspec_recovery_cli))
            assert refused.returncode != 0
            assert "application_recovery_required" in refused.stderr
            return
        assert failed.returncode != 0
        assert (work / "lock").exists()
        assert (delta / "accounts" / "spec.md").read_bytes() == draft
        if fault.startswith("failure") or fault == "cleanup-lock":
            assert (specs / "accounts" / "spec.md").read_bytes() == original
            assert not list(specs.parent.glob(".my-spec-backup-*"))
        else:
            backups = list(specs.parent.glob(".my-spec-backup-*"))
            assert len(backups) == 1
            assert (backups[0] / "accounts" / "spec.md").read_bytes() == original
        refused = _myspec_recovery_cli(*_myspec_abort_arguments(_myspec_recovery_session, _myspec_recovery_cli))
        assert refused.returncode != 0
        assert "application_recovery_required" in refused.stderr
        assert (work / "lock").exists()
        assert (work / "current" / "state.json").is_file()
        assert (delta / "accounts" / "spec.md").read_bytes() == draft


    @pytest.mark.parametrize("evidence,error", [
        ("no-confirmation", "no_active_session_confirmation_required"),
        ("wrong-state", "abort_state_mismatch"),
        ("foreign-lock", "abort_lock_identity_mismatch"),
        ("replaced-same-lock", "abort_lock_identity_mismatch"),
        ("wrong-target", "abort_target_mismatch"),
        ("cross-worktree", "cross_worktree_path"),
        ("legacy-no-baseline", "abort_specs_baseline_mismatch"),
        ("legacy-no-path", "invalid_state_context"),
        ("legacy-changed-specs", "abort_specs_baseline_mismatch"),
        ("legacy-backup", "application_recovery_required"),
        ("legacy-pending-replacement", "application_recovery_required"),
        ("legacy-unknown-status", "invalid_state_document"),
        ("unknown-phase", "application_recovery_required"),
        ("redirected-draft", "unsafe_recovery_entry"),
    ])
    def test_myspec_recovery_rejects_insufficient_or_foreign_evidence(self,
        tmp_path: Path, _myspec_recovery_session, _myspec_recovery_cli, evidence: str, error: str,
    ) -> None:
        target, work, specs, delta, preview = _myspec_recovery_session
        state_path = work / "current" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if evidence.startswith("legacy-"):
            state.pop("sessionId")
            state.pop("applicationPhase")
            _myspec_write(work / "lock", "add\n")
        if evidence == "legacy-no-baseline":
            state["specsContentFingerprint"] = None
        elif evidence == "legacy-no-path":
            state.pop("previewRoot")
        elif evidence == "legacy-changed-specs":
            _myspec_write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "已变化")))
        elif evidence == "legacy-backup":
            (specs.parent / ".my-spec-backup-preserved").mkdir()
        elif evidence == "legacy-pending-replacement":
            (specs.parent / ".my-spec-preview-preserved").mkdir()
        elif evidence == "legacy-unknown-status":
            state["status"] = "UNRECOGNIZED"
        elif evidence == "unknown-phase":
            state["applicationPhase"] = "UNRECOGNIZED"
        elif evidence == "redirected-draft":
            if os.name == "nt":
                pytest.skip("symlink creation needs platform permission")
            external = tmp_path / "external.txt"
            _myspec_write(external, "must not be touched")
            (work / "current" / "redirected").symlink_to(external)
        _myspec_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        arguments = _myspec_abort_arguments(_myspec_recovery_session, _myspec_recovery_cli)
        if evidence == "no-confirmation":
            arguments.pop()
        elif evidence == "wrong-state":
            arguments[6] = "0" * 64
        elif evidence == "foreign-lock":
            _myspec_write(work / "lock", '{"command":"add","sessionId":"foreign","workRoot":"elsewhere"}\n')
        elif evidence == "replaced-same-lock":
            content = (work / "lock").read_bytes()
            (work / "lock").unlink()
            (work / "lock").write_bytes(content)
        elif evidence == "wrong-target":
            arguments[2] = target.parent
        elif evidence == "cross-worktree":
            other = tmp_path / "other-worktree"
            created = subprocess.run(["git", "worktree", "add", "--detach", str(other), "HEAD"], cwd=target, text=True, capture_output=True, check=False)
            assert created.returncode == 0, created.stderr
            arguments[4] = other / ".local" / "spec-work" / "current" / "delta"
        state_bytes, lock_bytes = state_path.read_bytes(), (work / "lock").read_bytes()
        draft = (delta / "accounts" / "spec.md").read_bytes()
        refused = _myspec_recovery_cli(*arguments)
        assert refused.returncode != 0
        assert error in refused.stderr
        assert state_path.read_bytes() == state_bytes
        assert (work / "lock").read_bytes() == lock_bytes
        assert (delta / "accounts" / "spec.md").read_bytes() == draft
        assert not (work / "aborted").exists()


    @pytest.mark.parametrize("fault", ["archive-directory", "archive-rename", "interrupt-after-archive", "unlock", "foreign-lock-after-archive"])
    def test_myspec_recovery_preserves_lock_until_archive_and_retries_safely(self,
        tmp_path: Path, _myspec_recovery_session, _myspec_recovery_cli, fault: str,
    ) -> None:
        target, work, specs, delta, preview = _myspec_recovery_session
        arguments = _myspec_abort_arguments(_myspec_recovery_session, _myspec_recovery_cli)
        original = {path.relative_to(work / "current"): path.read_bytes() for path in (work / "current").rglob("*") if path.is_file()}
        lock_bytes = (work / "lock").read_bytes()
        injection = tmp_path / "abort-fault"
        _myspec_write(injection / "sitecustomize.py", 'import os\nfrom pathlib import Path\nrename_original, unlink_original = os.rename, os.unlink\nwork = Path(os.environ["RECOVERY_FAULT_WORK"])\nfault = os.environ["RECOVERY_FAULT"]\n\ndef rename(source, destination, *args, **kwargs):\n    if Path(source) == work / "current":\n        if fault == "archive-rename":\n            raise OSError("injected archive rename failure")\n        result = rename_original(source, destination, *args, **kwargs)\n        if fault == "interrupt-after-archive":\n            os._exit(93)\n        if fault == "foreign-lock-after-archive":\n            (work / "lock").write_text("foreign session lock\\n", encoding="utf-8")\n        return result\n    return rename_original(source, destination, *args, **kwargs)\n\ndef unlink(path, *args, **kwargs):\n    if Path(path) == work / "lock" and fault == "unlock":\n        raise PermissionError("injected lock removal failure")\n    return unlink_original(path, *args, **kwargs)\n\nos.rename, os.unlink = rename, unlink\n')
        if fault == "archive-directory":
            _myspec_write(work / "aborted", "not a directory")
        failed = _myspec_recovery_cli(*arguments, extra_env={
            "PYTHONPATH": str(injection), "RECOVERY_FAULT_WORK": str(work), "RECOVERY_FAULT": fault,
        })
        assert failed.returncode != 0
        assert (work / "lock").is_file()
        before_archive = fault in {"archive-directory", "archive-rename"}
        material = work / "current" if before_archive else next((work / "aborted").glob("*/current"))
        assert {path.relative_to(material): path.read_bytes() for path in material.rglob("*") if path.is_file()} == original
        if fault == "foreign-lock-after-archive":
            assert (work / "lock").read_text(encoding="utf-8") == "foreign session lock\n"
            refused = _myspec_recovery_cli(*arguments)
            assert refused.returncode != 0
            assert (work / "lock").read_text(encoding="utf-8") == "foreign session lock\n"
            return
        assert (work / "lock").read_bytes() == lock_bytes
        if fault == "archive-directory":
            (work / "aborted").unlink()
        retried = _myspec_recovery_cli(*arguments)
        assert retried.returncode == 0, retried.stderr
        archive = Path(json.loads(retried.stdout)["archive"])
        assert {path.relative_to(archive / "current"): path.read_bytes() for path in (archive / "current").rglob("*") if path.is_file()} == original
        assert not (work / "lock").exists()


    @pytest.mark.parametrize("replace_lock", [False, True])
    def test_myspec_recovery_init_failure_removes_only_its_own_lock(self,
        tmp_path: Path, _myspec_recovery_cli, replace_lock: bool,
    ) -> None:
        work = tmp_path / "consumer" / ".local" / "spec-work"
        injection = tmp_path / "initialization-fault"
        _myspec_write(injection / "sitecustomize.py", 'import os\nfrom pathlib import Path\noriginal = os.replace\nwork = Path(os.environ["RECOVERY_FAULT_WORK"])\n\ndef replace(source, destination, *args, **kwargs):\n    if Path(destination) == work / "current" / "state.json":\n        (work / "current" / "diagnostics.txt").write_text("preserved initialization material", encoding="utf-8")\n        if os.environ["RECOVERY_REPLACE_LOCK"] == "1":\n            (work / "lock").unlink()\n            (work / "lock").write_text("other session lock\\n", encoding="utf-8")\n        raise OSError("injected initialization state write failure")\n    return original(source, destination, *args, **kwargs)\n\nos.replace = replace\n')
        failed = _myspec_recovery_cli("state-init", work, "add", "specs", "input", extra_env={
            "PYTHONPATH": str(injection), "RECOVERY_FAULT_WORK": str(work), "RECOVERY_REPLACE_LOCK": str(int(replace_lock)),
        })
        assert failed.returncode != 0
        assert (work / "current" / "diagnostics.txt").read_text(encoding="utf-8") == "preserved initialization material"
        if replace_lock:
            assert (work / "lock").read_text(encoding="utf-8") == "other session lock\n"
        else:
            assert not (work / "lock").exists()
        refused = _myspec_recovery_cli("state-init", work, "add", "specs", "input")
        assert refused.returncode != 0
        assert "current_not_empty" in refused.stderr


    @pytest.mark.parametrize("empty_specs", [False, True])
    def test_myspec_recovery_preserves_failed_first_preview(self, _myspec_recovery_git_project: Path, _myspec_recovery_cli, empty_specs: bool) -> None:
        git_project = _myspec_recovery_git_project
        work = git_project / ".local" / "spec-work"
        specs = git_project / "myspec" / "specs"
        delta = work / "current" / "delta"
        preview = work / "current" / "preview"
        if not empty_specs:
            _myspec_write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
        assert _myspec_recovery_cli("state-init", work, "add", "specs", "input").returncode == 0
        content = "# Accounts\n\n## Purpose\n\n账户能力。\n\n## ADDED Requirements\n\n" if empty_specs else "## MODIFIED Requirements\n\n"
        _myspec_write(delta / "accounts" / "spec.md", content + requirement("登录", "新登录方式"))
        _myspec_write(git_project / "empty.json", "[]")
        assert _myspec_recovery_cli("state-set-conflicts", work, git_project / "empty.json", "specs", "input").returncode == 0
        _myspec_write(preview / "failure.txt", "partial first preview, must be retained")
        failed = _myspec_recovery_cli("apply-delta", specs, delta, preview, work, "specs", "input")
        assert failed.returncode != 0
        assert "output_not_empty" in failed.stderr
        result = _myspec_recovery_cli(*_myspec_abort_arguments((git_project, work, specs, delta, preview), _myspec_recovery_cli))
        assert result.returncode == 0, result.stderr
        archive = Path(json.loads(result.stdout)["archive"])
        assert (archive / "current" / "preview" / "failure.txt").read_text(encoding="utf-8") == "partial first preview, must be retained\n"
        assert not (work / "lock").exists()


    @pytest.mark.parametrize("evidence,error", [
        ("foreign", "foreign_abort_archive"),
        ("changed-state", "invalid_abort_archive"),
        ("traversal-delta", "invalid_abort_archive"),
        ("redirected-delta", "unsafe_recovery_entry"),
    ])
    def test_myspec_recovery_rejects_foreign_or_unsafe_archive_import(self,
        tmp_path: Path, _myspec_recovery_session, _myspec_recovery_cli, evidence: str, error: str,
    ) -> None:
        target, work, specs, delta, preview = _myspec_recovery_session
        aborted = _myspec_recovery_cli(*_myspec_abort_arguments(_myspec_recovery_session, _myspec_recovery_cli))
        assert aborted.returncode == 0, aborted.stderr
        archive = Path(json.loads(aborted.stdout)["archive"])
        if evidence == "foreign":
            copied = tmp_path / "foreign-archive"
            shutil.copytree(archive, copied)
            archive = copied
        elif evidence == "changed-state":
            state_path = archive / "current" / "state.json"
            state_path.write_bytes(state_path.read_bytes() + b"\n")
        elif evidence == "traversal-delta":
            state_path = archive / "current" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["deltaRoot"] = str(work / "current" / ".." / "outside-delta")
            _myspec_write(state_path, json.dumps(state))
            receipt_path = archive / "abort.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["deltaRoot"] = state["deltaRoot"]
            receipt["stateSha256"] = hashlib.sha256(state_path.read_bytes()).hexdigest()
            _myspec_write(receipt_path, json.dumps(receipt))
            _myspec_write(archive / "outside-delta" / "unrelated.txt", "must not be imported")
        elif evidence == "redirected-delta":
            if os.name == "nt":
                pytest.skip("symlink creation needs platform permission")
            external = tmp_path / "external.txt"
            _myspec_write(external, "must not be imported")
            (archive / "current" / "delta" / "redirected").symlink_to(external)
        refused = _myspec_recovery_cli("state-init", work, "add", "new-specs", "new-input", "--import-aborted", archive)
        assert refused.returncode != 0
        assert error in refused.stderr
        assert not (work / "lock").exists()
        assert not (work / "current").exists()


    def test_myspec_recovery_rejects_old_request_for_identical_new_legacy_session(self,
        _myspec_recovery_session, _myspec_recovery_cli,
    ) -> None:
        target, work, specs, delta, preview = _myspec_recovery_session
        state_path = work / "current/state.json"
        legacy = json.loads(state_path.read_text(encoding="utf-8"))
        legacy.pop("sessionId")
        legacy.pop("applicationPhase")
        # Retain the existing legacy-state fixture shape without depending on Git
        # history, a downloaded old release, or a mocked abort implementation.
        _myspec_write(state_path, json.dumps(legacy, ensure_ascii=False, indent=2))
        (work / "lock").write_bytes(b"add\n")
        first_state = state_path.read_bytes()
        material = {path.relative_to(work / "current"): path.read_bytes() for path in (work / "current").rglob("*") if path.is_file()}
        old_arguments = _myspec_abort_arguments(_myspec_recovery_session, _myspec_recovery_cli)
        first = _myspec_recovery_cli(*old_arguments)
        assert first.returncode == 0, first.stderr

        initialized = _myspec_recovery_cli("state-init", work, "add", "specs", "input")
        assert initialized.returncode == 0, initialized.stderr
        for relative, content in material.items():
            destination = work / "current" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        (work / "lock").write_bytes(b"add\n")
        assert state_path.read_bytes() == first_state
        marker = work / "current/new-session-only.txt"
        _myspec_write(marker, "new session must survive old authorization")
        new_lock_bytes = (work / "lock").read_bytes()
        new_lock_stat = (work / "lock").stat()
        replayed = _myspec_recovery_cli(*old_arguments)
        assert replayed.returncode != 0
        assert "abort_request_already_completed" in replayed.stderr
        assert marker.read_text(encoding="utf-8") == "new session must survive old authorization\n"
        assert state_path.read_bytes() == first_state
        assert (work / "lock").read_bytes() == new_lock_bytes
        current_lock_stat = (work / "lock").stat()
        # Reading may advance atime; identity and modification metadata must not change.
        for field in (
            "st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_gid", "st_size",
            "st_mtime_ns", "st_ctime_ns",
        ):
            assert getattr(current_lock_stat, field) == getattr(new_lock_stat, field), field
        fresh_arguments = _myspec_abort_arguments(_myspec_recovery_session, _myspec_recovery_cli)
        assert fresh_arguments[6] == old_arguments[6]
        assert fresh_arguments[9] != old_arguments[9]
        fresh = _myspec_recovery_cli(*fresh_arguments)
        assert fresh.returncode == 0, fresh.stderr
        assert json.loads(fresh.stdout)["archive"] != json.loads(first.stdout)["archive"]


    @pytest.mark.parametrize("command", ["inspect", "abort"])
    def test_myspec_recovery_outputs_ascii_json_for_non_utf8_stdout(self,
        _myspec_recovery_git_project: Path, _myspec_recovery_cli, command: str,
    ) -> None:
        git_project = _myspec_recovery_git_project
        work = git_project / ".local" / "中文会话"
        specs = git_project / "中文规格" / "specs"
        delta, preview = work / "current/delta", work / "current/preview"
        _myspec_write(specs / "accounts/spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
        initialized = _myspec_recovery_cli("state-init", work, "add", "specs", "input")
        assert initialized.returncode == 0, initialized.stderr
        _myspec_write(delta / "accounts/spec.md", "## MODIFIED Requirements\n\n" + requirement("登录", "允许密码登录"))
        empty = git_project / "empty-conflicts.json"
        _myspec_write(empty, "[]")
        for result in (
            _myspec_recovery_cli("state-set-conflicts", work, empty, "specs", "input"),
            _myspec_recovery_cli("apply-delta", specs, delta, preview, work, "specs", "input"),
        ):
            assert result.returncode == 0, result.stderr
        environment = {"PYTHONIOENCODING": "cp1252:strict", "PYTHONUTF8": "0"}
        if command == "inspect":
            state_bytes = (work / "current/state.json").read_bytes()
            lock_bytes = (work / "lock").read_bytes()
            inspected = _myspec_recovery_cli("state-status", work, "specs", "input", "--abort-identity", extra_env=environment)
            assert inspected.returncode == 0, inspected.stderr
            assert inspected.stdout.isascii()
            assert json.loads(inspected.stdout)["abortIdentity"]["workRoot"] == str(work)
            assert (work / "current/state.json").read_bytes() == state_bytes
            assert (work / "lock").read_bytes() == lock_bytes
        else:
            arguments = _myspec_abort_arguments((git_project, work, specs, delta, preview), _myspec_recovery_cli)
            aborted = _myspec_recovery_cli(*arguments, extra_env=environment)
            assert aborted.returncode == 0, aborted.stderr
            assert aborted.stdout.isascii()
            archive = Path(json.loads(aborted.stdout)["archive"])
            assert archive.parent == work / "aborted"
            assert (archive / "current/state.json").is_file()
            assert not (work / "lock").exists()
            assert not (work / "current").exists()



    def test_packed_myspec_bare_doctor_reports_only_package(self, tmp_path: Path) -> None:
        executable, package = _myspec_install_packed_myspec(tmp_path)
        prefix = npm_prefix_for(package)
        pi_bin, pi_log = _myspec_install_removed_pi_command(tmp_path / 'removed-pi')
        claude_bin, claude_log, claude_state = _myspec_install_fake_claude(tmp_path / 'fake-claude')
        codex_bin, codex_log, codex_state = _myspec_install_fake_codex(tmp_path / 'fake-codex')
        env = _myspec_isolated_myspec_env(tmp_path, prefix, pi_bin, claude_bin, codex_bin)
        invalid_home = tmp_path / 'invalid-codex-home'
        invalid_home.write_text('not a directory', encoding='utf-8')
        env.update(CODEX_HOME=str(invalid_home), MYSPEC_PI_LOG=str(pi_log), MYSPEC_CLAUDE_LOG=str(claude_log), MYSPEC_CLAUDE_STATE=str(claude_state), MYSPEC_CODEX_LOG=str(codex_log), MYSPEC_CODEX_STATE=str(codex_state))
        env['BUILD_AND_VERIFY_PYTHON'] = sys.executable
        diagnosed = subprocess.run([str(executable), 'doctor'], env=env, text=True, capture_output=True, check=False)
        assert diagnosed.returncode == 0, diagnosed.stderr
        report = json.loads(diagnosed.stdout)
        assert report['toolchain']['mode'] == 'release'
        assert report['npm']['versionMismatch'] is False
        assert report['installation']['pendingOperation'] is None
        assert not {'pi', 'claude', 'codex'}.intersection(report)
        assert not any((log.exists() for log in (pi_log, claude_log, codex_log)))
        installed_package = prefix / ('node_modules' if os.name == 'nt' else 'lib/node_modules') / '@liuli195' / 'myspec'
        manifest = json.loads((installed_package / 'package.json').read_text())
        assert 'pi' not in manifest and 'pi-package' not in manifest.get('keywords', [])


    def test_packed_myspec_all_and_removed_pi_options(self, tmp_path: Path) -> None:
        executable, package = _myspec_install_packed_myspec(tmp_path)
        prefix = npm_prefix_for(package)
        env = _myspec_isolated_myspec_env(tmp_path, prefix)
        env['BUILD_AND_VERIFY_PYTHON'] = sys.executable
        for command in ('doctor', 'init'):
            removed = subprocess.run([str(executable), command, '--pi'], env=env, text=True, capture_output=True, check=False)
            assert removed.returncode == 2, removed.stdout + removed.stderr
            assert 'error:' in removed.stderr
            selected = subprocess.run([str(executable), command, '--all'], env=env, text=True, capture_output=True, check=False)
            assert selected.returncode == 0, selected.stderr
            report = json.loads(selected.stdout)
            assert 'pi' not in report
            assert {'claude', 'codex'}.issubset(report)


    def test_packed_myspec_reject_legacy_pi_pending_before_writes(self, tmp_path: Path) -> None:
        executable, package = _myspec_install_packed_myspec(tmp_path)
        prefix = npm_prefix_for(package)
        release_tarball = next((tmp_path / 'package').glob('*.tgz'))
        npm_bin, npm_log = _myspec_install_fake_npm(tmp_path / 'fake-npm', release_tarball)
        env = _myspec_isolated_myspec_env(tmp_path, prefix, npm_bin)
        env.update(BUILD_AND_VERIFY_PYTHON=sys.executable, MYSPEC_NPM_LOG=str(npm_log), MYSPEC_NPM_FAIL_INSTALL='1', MYSPEC_RELEASE_TARBALL=str(release_tarball))
        pending = {'command': 'update', 'targetVersion': '99.0.0', 'integrations': ['pi', 'claude'], 'completed': ['preflight'], 'enabled': {'pi': True, 'claude': False}, 'scopes': {}}
        state_path = Path(env['HOME']) / f".{'myspec'}" / 'state.json'
        pi_settings = Path(env['HOME']) / '.pi' / 'agent' / 'settings.json'
        _myspec_write(state_path, json.dumps({'mode': 'release', 'pendingOperation': pending}, indent=2))
        _myspec_write(pi_settings, '{"packages": ["old-pi-source"], "other": "keep"}')
        before = (state_path.read_bytes(), pi_settings.read_bytes(), (package / 'package.json').read_bytes())
        diagnosed = subprocess.run([str(executable), 'doctor'], env=env, text=True, capture_output=True, check=False)
        assert diagnosed.returncode == 0, diagnosed.stderr
        assert json.loads(diagnosed.stdout)['installation']['pendingOperation']['integrations'] == ['pi', 'claude']
        rejected = subprocess.run([str(executable), 'update'], env=env, text=True, capture_output=True, check=False)
        assert rejected.returncode == 1
        assert 'error: invalid_update_state' in rejected.stderr
        assert (state_path.read_bytes(), pi_settings.read_bytes(), (package / 'package.json').read_bytes()) == before
        assert not npm_log.exists() or npm_log.read_text() == ''


    def test_packed_myspec_update_ignores_removed_pi_client(self, tmp_path: Path) -> None:
        executable, package = _myspec_install_packed_myspec(tmp_path)
        tarball = next((tmp_path / 'package').glob('*.tgz'))
        npm_bin, npm_log = _myspec_install_fake_npm(tmp_path / 'fake-npm', tarball)
        pi_bin, pi_log = _myspec_install_removed_pi_command(tmp_path / 'fake-pi')
        env = _myspec_isolated_myspec_env(tmp_path, npm_prefix_for(package), npm_bin, pi_bin)
        env.update(MYSPEC_NPM_LOG=str(npm_log), MYSPEC_PI_LOG=str(pi_log), MYSPEC_REAL_NPM=str(shutil.which('npm')))
        settings = Path(env['PI_CODING_AGENT_DIR']) / 'settings.json'
        _myspec_write(settings, '{"packages": "unsupported-old-configuration"}')
        before = settings.read_bytes()
        updated = subprocess.run([str(executable), 'update'], env=env, text=True, capture_output=True, check=False)
        assert updated.returncode == 0, updated.stderr
        report = json.loads(updated.stdout)
        assert 'pi' not in report and 'pi' not in report['doctor']
        assert settings.read_bytes() == before
        assert not pi_log.exists() or pi_log.read_text() == ''


    def test_packed_myspec_supported_clients_initialize_and_resume_update(self, tmp_path: Path) -> None:
        executable, package = _myspec_install_packed_myspec(tmp_path)
        prefix = npm_prefix_for(package)
        version = json.loads((package / 'package.json').read_text())['version']
        claude_bin, claude_log, claude_state = _myspec_install_fake_claude(tmp_path / 'fake-claude')
        codex_bin, codex_log, codex_state = _myspec_install_fake_codex(tmp_path / 'fake-codex')
        pi_bin, pi_log = _myspec_install_removed_pi_command(tmp_path / 'removed-pi')
        env = _myspec_isolated_myspec_env(tmp_path, prefix, claude_bin, codex_bin, pi_bin)
        codex_home = Path(env['HOME']) / '.codex'
        codex_home.mkdir()
        env.update(BUILD_AND_VERIFY_PYTHON=sys.executable, MYSPEC_CLAUDE_LOG=str(claude_log), MYSPEC_CLAUDE_STATE=str(claude_state), MYSPEC_CLAUDE_HOME=str(Path(env['HOME']) / '.claude'), MYSPEC_CODEX_LOG=str(codex_log), MYSPEC_CODEX_STATE=str(codex_state), CODEX_HOME=str(codex_home), MYSPEC_PI_LOG=str(pi_log))
        _myspec_write(claude_state, '{"marketplaces": [], "plugins": []}')
        _myspec_write(codex_state, '{"marketplaces": [], "installed": [], "available": []}')
        initialized = subprocess.run([str(executable), 'init', '--all'], env=env, text=True, capture_output=True, check=False)
        assert initialized.returncode == 0, initialized.stderr
        assert (codex_home / 'config.toml').is_file()
        assert set(json.loads(initialized.stdout)) == {'claude', 'codex'}
        diagnosed = subprocess.run([str(executable), 'doctor', '--all'], env=env, text=True, capture_output=True, check=False)
        assert diagnosed.returncode == 0, diagnosed.stderr
        report = json.loads(diagnosed.stdout)
        for client in ('claude', 'codex'):
            assert report[client]['version'] == version
            assert report[client]['skills']
            assert report[client]['sources'][0]['effective'] is True
        state_path = Path(env['HOME']) / f".{'myspec'}" / 'state.json'
        _myspec_write(state_path, json.dumps({'mode': 'release', 'pendingOperation': {'command': 'update', 'targetVersion': version, 'integrations': ['claude', 'codex'], 'completed': ['preflight', 'npm'], 'enabled': {'claude': False, 'codex': False}, 'scopes': {'claude': 'user'}}}))
        updated = subprocess.run([str(executable), 'update'], env=env, text=True, capture_output=True, check=False)
        assert updated.returncode == 0, updated.stderr
        result = json.loads(updated.stdout)
        assert result['claude'] == result['codex'] == 'refreshed'
        assert 'pi' not in result and 'pi' not in result['doctor']
        assert result['doctor']['claude']['enabled'] is False
        assert result['doctor']['codex']['enabled'] is False
        assert 'pendingOperation' not in json.loads(state_path.read_text())
        assert not pi_log.exists()

    def test_packed_myspec_reconfirms_when_in_process_identity_changes_preview(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        specs = tmp_path / 'specs'
        delta = tmp_path / 'delta'
        preview = tmp_path / 'preview'
        _myspec_write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('登录', '允许登录')))
        _myspec_write(delta / 'accounts' / 'spec.md', '## MODIFIED Requirements\n\n### Requirement: 登录\n\n系统 MUST 允许密码登录。\n\n#### Scenario: 密码正确\n\n- **WHEN** 用户提交正确密码\n- **THEN** 系统创建会话\n')
        work = _myspec_memory_migration_ready_state(_MYSPEC_SPEC_OPS, tmp_path / 'state')
        previewed = _myspec_memory_migration_apply_ready(_MYSPEC_SPEC_OPS, specs, delta, preview, work)
        assert previewed.returncode == 0, previewed.stderr
        before = (specs / 'accounts' / 'spec.md').read_bytes()
        spec_ops = _myspec_load_in_process_spec_ops(_MYSPEC_SPEC_OPS)
        original_write_preview = spec_ops._write_preview

        def changed_write_preview(merged, output_root, source_root):
            original_write_preview(merged, output_root, source_root)
            path = output_root / 'accounts' / 'spec.md'
            _myspec_write(path, path.read_text(encoding='utf-8') + '\nimplementation-only change')
        monkeypatch.setattr(spec_ops, 'implementation_identity', lambda: 'changed-implementation')
        monkeypatch.setattr(spec_ops, '_write_preview', changed_write_preview)
        applied = _myspec_memory_migration_apply_ready(_MYSPEC_SPEC_OPS, specs, delta, specs, work)
        assert applied.returncode != 0
        assert 'preview_changed_requires_confirmation' in applied.stderr
        assert (specs / 'accounts' / 'spec.md').read_bytes() == before


    def test_packed_myspec_preserves_modified_requirement_order(self, tmp_path: Path) -> None:
        executable = _MYSPEC_SPEC_OPS
        titles = ('首部', '中部', '尾部')

        def preview_delta(root: Path, specs: Path, delta: Path) -> tuple[Path, Path]:
            preview = root / 'preview'
            work = root / 'work'
            conflicts = root / 'conflicts.json'
            _myspec_write(conflicts, '[]')
            for result in (_myspec_run_in_process(executable, 'state-init', work, 'add', 'specs-fingerprint', 'input-fingerprint'), _myspec_run_in_process(executable, 'state-set-conflicts', work, conflicts, 'specs-fingerprint', 'input-fingerprint'), _myspec_run_in_process(executable, 'validate-delta', delta, specs), _myspec_run_in_process(executable, 'apply-delta', specs, delta, preview, work, 'specs-fingerprint', 'input-fingerprint')):
                assert result.returncode == 0, result.stderr
            return (preview, work)
        for target in titles:
            root = tmp_path / target
            specs = root / 'specs'
            delta = root / 'delta'
            _myspec_write(specs / 'accounts' / 'spec.md', main_spec('Accounts', *(requirement(title, f'保留{title}') for title in titles)))
            _myspec_write(delta / 'accounts' / 'spec.md', f'## MODIFIED Requirements\n\n### Requirement: {target}\n\n系统 MUST 更新{target}。\n\n#### Scenario: 修改{target}\n\n- **WHEN** 用户修改{target}\n- **THEN** 系统保留需求顺序\n')
            preview, work = preview_delta(root, specs, delta)
            preview_text = (preview / 'accounts' / 'spec.md').read_text(encoding='utf-8')
            assert [line.removeprefix('### Requirement: ') for line in preview_text.splitlines() if line.startswith('### Requirement: ')] == list(titles)
            assert f'系统 MUST 更新{target}。' in preview_text
            assert f'系统 MUST 保留{target}。' not in preview_text
            diff = _myspec_run_in_process(executable, 'diff', specs, preview)
            assert diff.returncode == 0, diff.stderr
            assert f'-### Requirement: {target}' not in diff.stdout
            assert f'+### Requirement: {target}' not in diff.stdout
            applied = _myspec_run_in_process(executable, 'apply-delta', specs, delta, specs, work, 'specs-fingerprint', 'input-fingerprint')
            assert applied.returncode == 0, applied.stderr
            assert (specs / 'accounts' / 'spec.md').read_bytes() == (preview / 'accounts' / 'spec.md').read_bytes()
            before_repeat = (specs / 'accounts' / 'spec.md').read_bytes()
            repeated_preview, repeated_work = preview_delta(root / 'repeat', specs, delta)
            repeated = _myspec_run_in_process(executable, 'apply-delta', specs, delta, specs, repeated_work, 'specs-fingerprint', 'input-fingerprint')
            assert repeated.returncode == 0, repeated.stderr
            assert (repeated_preview / 'accounts' / 'spec.md').read_bytes() == before_repeat
            assert (specs / 'accounts' / 'spec.md').read_bytes() == before_repeat
        root = tmp_path / 'cross-capability'
        specs = root / 'specs'
        delta = root / 'delta'
        _myspec_write(specs / 'source' / 'spec.md', main_spec('Source', requirement('移动项', '留在来源')))
        _myspec_write(specs / 'target' / 'spec.md', main_spec('Target', requirement('现有项', '留在目标')))
        _myspec_write(delta / 'target' / 'spec.md', '## MODIFIED Requirements\n\n### Requirement: 移动项\n\n系统 MUST 移入目标能力。\n\n#### Scenario: 跨能力修改\n\n- **WHEN** 用户修改其他能力中的需求\n- **THEN** 系统把需求移入目标能力\n')
        preview, work = preview_delta(root, specs, delta)
        assert '### Requirement: 移动项' not in (preview / 'source' / 'spec.md').read_text(encoding='utf-8')
        target_text = (preview / 'target' / 'spec.md').read_text(encoding='utf-8')
        assert target_text.index('### Requirement: 现有项') < target_text.index('### Requirement: 移动项')
        applied = _myspec_run_in_process(executable, 'apply-delta', specs, delta, specs, work, 'specs-fingerprint', 'input-fingerprint')
        assert applied.returncode == 0, applied.stderr
        assert (specs / 'source' / 'spec.md').read_bytes() == (preview / 'source' / 'spec.md').read_bytes()
        assert (specs / 'target' / 'spec.md').read_bytes() == (preview / 'target' / 'spec.md').read_bytes()


    def test_spec_ops_cli_validates_applies_all_delta_operations_and_diffs(self, tmp_path: Path) -> None:
        specs = tmp_path / 'specs'
        delta = tmp_path / 'delta'
        preview = tmp_path / 'preview'
        _myspec_write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('旧登录', '允许登录'), requirement('旧导出', '允许导出'), requirement('个人资料', '显示姓名')))
        _myspec_write(delta / 'accounts' / 'spec.md', '# Accounts\n\n## Purpose\n\n描述 Accounts 的外部行为。\n\n## RENAMED Requirements\n\nFROM: 旧登录\nTO: 密码登录\n\n## REMOVED Requirements\n\n### Requirement: 旧导出\n\n## MODIFIED Requirements\n\n### Requirement: 个人资料\n\n系统 SHALL 显示姓名和头像。\n\n#### Scenario: 查看资料\n\n- **WHEN** 用户打开个人资料\n- **THEN** 系统显示姓名和头像\n\n## ADDED Requirements\n\n### Requirement: 注销\n\n系统 MUST 允许用户注销。\n\n#### Scenario: 主动注销\n\n- **WHEN** 用户选择注销\n- **THEN** 系统结束会话\n')
        work = _myspec_memory_migration_ready_state(_MYSPEC_SPEC_OPS, tmp_path / 'state')
        assert _myspec_run_in_process(_MYSPEC_SPEC_OPS, 'validate-main', specs).returncode == 0
        assert _myspec_run_in_process(_MYSPEC_SPEC_OPS, 'validate-delta', delta, specs).returncode == 0
        applied = _myspec_memory_migration_apply_ready(_MYSPEC_SPEC_OPS, specs, delta, preview, work)
        assert applied.returncode == 0, applied.stderr
        assert _myspec_run_in_process(_MYSPEC_SPEC_OPS, 'validate-main', preview).returncode == 0
        merged = (preview / 'accounts' / 'spec.md').read_text(encoding='utf-8')
        assert '### Requirement: 密码登录' in merged
        assert '### Requirement: 旧登录' not in merged
        assert '### Requirement: 旧导出' not in merged
        assert '系统 SHALL 显示姓名和头像。' in merged
        assert '### Requirement: 注销' in merged
        diff = _myspec_run_in_process(_MYSPEC_SPEC_OPS, 'diff', specs, preview)
        assert diff.returncode == 0
        assert '-### Requirement: 旧登录' in diff.stdout
        assert '+### Requirement: 密码登录' in diff.stdout
        assert '旧导出' in diff.stdout
        assert '注销' in diff.stdout
        first_apply = _myspec_memory_migration_apply_ready(_MYSPEC_SPEC_OPS, specs, delta, specs, work)
        assert first_apply.returncode == 0, first_apply.stderr
        before_repeat = (specs / 'accounts' / 'spec.md').read_bytes()
        repeated_validation = _myspec_run_in_process(_MYSPEC_SPEC_OPS, 'validate-delta', delta, specs)
        assert repeated_validation.returncode == 0, repeated_validation.stderr
        repeated_work = _myspec_memory_migration_ready_state(_MYSPEC_SPEC_OPS, tmp_path / 'repeated-state')
        shutil.rmtree(preview)
        repeated_preview = _myspec_memory_migration_apply_ready(_MYSPEC_SPEC_OPS, specs, delta, preview, repeated_work)
        assert repeated_preview.returncode == 0, repeated_preview.stderr
        repeated_apply = _myspec_memory_migration_apply_ready(_MYSPEC_SPEC_OPS, specs, delta, specs, repeated_work)
        assert repeated_apply.returncode == 0, repeated_apply.stderr
        assert (specs / 'accounts' / 'spec.md').read_bytes() == before_repeat


    def test_spec_add_deterministic_post_analysis_flow_previews_diffs_and_applies(self, tmp_path: Path) -> None:
        cli = _MYSPEC_SPEC_OPS
        specs = tmp_path / 'add' / 'specs'
        delta = tmp_path / 'add' / 'delta'
        preview = tmp_path / 'add' / 'preview'
        _myspec_write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('登录', '允许用户登录')))
        _myspec_write(delta / 'accounts' / 'spec.md', '## ADDED Requirements\n\n### Requirement: 注销\n\n系统 MUST 允许用户注销。\n\n#### Scenario: 主动注销\n\n- **WHEN** 用户选择注销\n- **THEN** 系统结束会话\n')
        _myspec_memory_migration_confirmed_workflow(cli, specs, delta, preview, '+### Requirement: 注销')
        assert '### Requirement: 注销' in (specs / 'accounts' / 'spec.md').read_text(encoding='utf-8')


    def test_spec_review_deterministic_duplicate_flow_previews_diffs_and_applies(self, tmp_path: Path) -> None:
        cli = _MYSPEC_SPEC_OPS
        specs = tmp_path / 'review' / 'specs'
        delta = tmp_path / 'review' / 'delta'
        preview = tmp_path / 'review' / 'preview'
        duplicate = requirement('登录', '允许用户登录')
        _myspec_write(specs / 'accounts' / 'spec.md', main_spec('Accounts', duplicate, duplicate))
        delta.mkdir(parents=True)
        _myspec_memory_migration_confirmed_workflow(cli, specs, delta, preview, '-### Requirement: 登录')
        assert (specs / 'accounts' / 'spec.md').read_text(encoding='utf-8').count('### Requirement: 登录') == 1


    def test_spec_audit_deterministic_post_analysis_flow_previews_diffs_and_applies(self, tmp_path: Path) -> None:
        cli = _MYSPEC_SPEC_OPS
        specs = tmp_path / 'audit' / 'missing-specs'
        delta = tmp_path / 'audit' / 'delta'
        preview = tmp_path / 'audit' / 'preview'
        _myspec_write(delta / 'notifications' / 'spec.md', '# Notifications\n\n## Purpose\n\n描述通知的外部行为。\n\n## ADDED Requirements\n\n### Requirement: 接收通知\n\n系统 MUST 向订阅用户发送通知。\n\n#### Scenario: 新消息\n\n- **WHEN** 新消息到达\n- **THEN** 系统发送通知\n')
        _myspec_memory_migration_confirmed_workflow(cli, specs, delta, preview, '+### Requirement: 接收通知')
        assert (specs / 'notifications' / 'spec.md').is_file()
