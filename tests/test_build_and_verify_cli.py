from __future__ import annotations

import json
import os
import shutil
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "plugins" / "build-and-verify"
PACK = REPO_ROOT / "plugins" / "tool-lifecycle" / "pack.py"
PACKAGE_VERSION = json.loads((PACKAGE_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
_installed_template: tempfile.TemporaryDirectory[str] | None = None


def test_public_verify_local_budget_stops_before_next_check(tmp_path: Path) -> None:
    project = tmp_path / "budget-project"
    (project / ".build-and-verify").mkdir(parents=True)
    (project / ".build-and-verify" / "config.json").write_text(json.dumps({
        "version": 1, "verify": {"fullBudgetSeconds": 3, "checks": [
            {"id": "slow", "command": [sys.executable, "-c", "import time; time.sleep(6)"], "inputs": []},
            {"id": "later", "command": [sys.executable, "-c", "print('LATER_STARTED')"], "inputs": []},
        ]},
    }), encoding="utf-8")
    initialized = subprocess.run(["git", "init", str(project)], capture_output=True)
    assert initialized.returncode == 0
    started = time.monotonic()
    result = subprocess.run([
        shutil.which("node"), str(PACKAGE_ROOT / "bin" / "build-and-verify.js"),
        "verify", "--project", str(project), "--full",
    ], env={**os.environ, "BUILD_AND_VERIFY_PYTHON": sys.executable,
            "BUILD_AND_VERIFY_EXECUTION_CONTEXT": "local", "GITHUB_ACTIONS": "false", "CI": "false"},
        text=True, capture_output=True, timeout=8)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "total_budget_timeout" in result.stdout + result.stderr
    assert "LATER_STARTED" not in result.stdout
    assert "not-started: later" in result.stdout
    assert time.monotonic() - started < 5


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
    package_root = Path(os.environ.get("BUILD_AND_VERIFY_TEST_PACKAGE", str(PACKAGE_ROOT)))
    result = subprocess.run([shutil.which("node"), str(package_root / "bin" / "build-and-verify.js"),
        "verify", "--project", str(project), *(('--full',) if full else ()), *extra],
        env=env, capture_output=True, text=True, timeout=8)
    return result, project


@pytest.mark.parametrize("full", [False, True])
def test_public_verify_budget_applies_to_fast_and_full(tmp_path: Path, full: bool) -> None:
    result, project = _budget_run(tmp_path, full=full)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "total_budget_timeout" in result.stdout
    assert "LATER_STARTED" not in result.stdout
    report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
    assert report["verificationStatus"] == "failed"
    assert report["reason"] == "total_budget_timeout"
    assert report["overBudget"] is True
    assert report["notStarted"] == ["later"]
    assert report["checks"][0]["status"] == "timed_out"
    assert not list((project / ".build-and-verify/cache").glob("*.json"))


@pytest.mark.parametrize("settings,context,extra", [
    ({"enforceLocalBudget": False}, "local", ()),
    ({}, "cloud", ()), ({}, "ci", ()), ({}, "local", ("--pr",)),
])
def test_public_verify_budget_warning_does_not_fail_exempt_runs(tmp_path: Path, settings: dict,
        context: str, extra: tuple[str, ...]) -> None:
    result, _ = _budget_run(tmp_path, settings={"fullBudgetSeconds": 1, **settings}, context=context, extra=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "LATER_STARTED" in result.stdout
    assert "performance-warning:" in result.stdout


def test_public_verify_unknown_context_fails_before_launch(tmp_path: Path) -> None:
    result, _ = _budget_run(tmp_path, context=None)
    assert result.returncode == 1
    assert "execution-context-warning: unknown" in result.stdout
    assert "execution_context_required_for_local_budget" in result.stderr
    assert "check-start:" not in result.stdout


def test_public_verify_parallel_queue_shares_deadline(tmp_path: Path) -> None:
    checks = [
        {"id": "slow", "command": [sys.executable, "-c", "import time; time.sleep(6)"], "inputs": [], "checkParallel": True},
        {"id": "queued", "command": [sys.executable, "-c", "print('QUEUED_STARTED')"], "inputs": [], "checkParallel": True},
        {"id": "serial", "command": [sys.executable, "-c", "print('SERIAL_STARTED')"], "inputs": []},
    ]
    result, project = _budget_run(tmp_path, settings={"maxParallel": 1}, checks=checks)
    assert result.returncode == 1
    assert "QUEUED_STARTED" not in result.stdout
    assert "SERIAL_STARTED" not in result.stdout
    report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
    assert report["notStarted"] == ["queued", "serial"]


def test_public_verify_serial_checks_share_remaining_budget_and_cache_only_completed(tmp_path: Path) -> None:
    checks = [{"id": name, "command": [sys.executable, "-c", f"import time; time.sleep({delay})"], "inputs": []}
              for name, delay in (("first", 0.5), ("second", 4.7), ("third", 0.1))]
    result, project = _budget_run(tmp_path, settings={"fullBudgetSeconds": 5}, checks=checks)
    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
    assert [check["status"] for check in report["checks"]] == ["passed", "timed_out", "not_started"]
    caches = list((project / ".build-and-verify/cache").glob("*.json"))
    assert len(caches) == 1


def test_public_verify_parallel_active_checks_share_cancellation(tmp_path: Path) -> None:
    checks = [{"id": name, "command": [sys.executable, "-c", "import time; time.sleep(6)"],
               "inputs": [], "checkParallel": True} for name in ("first", "second")]
    result, project = _budget_run(tmp_path, settings={"maxParallel": 2}, checks=checks)
    assert result.returncode == 1
    report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
    assert report["unfinished"] == ["first", "second"]
    assert all(check["status"] == "timed_out" for check in report["checks"])


@pytest.mark.parametrize("extra,settings", [
    (("--diagnostic",), {}), ((), {"enforceLocalBudget": False}),
])
def test_public_verify_warning_and_diagnostic_preserve_real_errors(tmp_path: Path,
        extra: tuple[str, ...], settings: dict) -> None:
    result, _ = _budget_run(tmp_path, settings=settings, extra=extra, checks=[
        {"id": "error", "command": [sys.executable, "-c", "assert False, 'REAL_ASSERTION'"], "inputs": []}])
    assert result.returncode == 1
    assert "REAL_ASSERTION" in result.stderr


def test_public_verify_explicit_context_overrides_inherited_context(tmp_path: Path) -> None:
    result, _ = _budget_run(tmp_path, context="cloud", extra=("--execution-context=local",))
    assert result.returncode == 1
    assert "total_budget_timeout" in result.stdout


@pytest.mark.parametrize("value", [0, 1, "true", None])
def test_public_verify_rejects_non_boolean_budget_switch(tmp_path: Path, value) -> None:
    result, _ = _budget_run(tmp_path, settings={"enforceLocalBudget": value})
    assert result.returncode == 1
    assert "verify.enforceLocalBudget must be boolean" in result.stderr
    assert "check-start:" not in result.stdout


def test_public_verify_diagnostic_is_not_formal_acceptance(tmp_path: Path) -> None:
    result, project = _budget_run(tmp_path, settings={"fullBudgetSeconds": 1}, extra=("--diagnostic",))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "LATER_STARTED" in result.stdout
    assert "check-start: slow" in result.stdout
    assert "check-end: slow status=passed" in result.stdout
    assert "status: diagnostic" in result.stdout
    assert "status: passed\n" not in result.stdout
    report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
    assert report["verificationStatus"] == "diagnostic"
    assert report["diagnostic"] is True
    assert "enforceLocalBudget" not in json.loads((project / ".build-and-verify/config.json").read_text())["verify"]


@pytest.mark.parametrize("extra,settings", [
    (("--diagnostic",), {"timeoutSeconds": 0.2}),
    ((), {"enforceLocalBudget": False, "timeoutSeconds": 0.2}),
])
def test_public_verify_diagnostic_and_warning_preserve_check_timeout(tmp_path: Path,
        extra: tuple[str, ...], settings: dict) -> None:
    result, _ = _budget_run(tmp_path, extra=extra, settings=settings)
    assert result.returncode == 1
    assert "check_timeout: slow" in result.stderr


def test_public_verify_budget_reaps_descendants_and_preserves_other_processes(tmp_path: Path) -> None:
    pid_file = tmp_path / "descendant.pid"
    child_code = "import time; time.sleep(10)"
    parent_code = ("import subprocess,sys,time,pathlib; "
        f"child=subprocess.Popen([sys.executable,'-c',{child_code!r}]); "
        f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid)); time.sleep(10)")
    unrelated = subprocess.Popen([sys.executable, "-c", child_code])
    try:
        result, _ = _budget_run(tmp_path, checks=[
            {"id": "tree", "command": [sys.executable, "-c", parent_code], "inputs": []}])
        assert result.returncode == 1, result.stdout + result.stderr
        assert pid_file.exists(), result.stdout + result.stderr
        assert unrelated.poll() is None
        _assert_pid_terminated(int(pid_file.read_text()))
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=2)


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
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def test_public_verify_budget_interrupts_blocked_preparation_and_its_descendants(tmp_path: Path) -> None:
    # A real Git filesystem monitor models a blocked external preparation read.
    # This is confined to the synthetic repository, never the user's hooks.
    pids = tmp_path / "preparation-pids.json"
    monitor = tmp_path / "monitor.py"
    monitor.write_text(
        "import json,os,subprocess,sys,time\nfrom pathlib import Path\n"
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)'])\n"
        f"Path({str(pids)!r}).write_text(json.dumps([os.getpid(),child.pid]))\n"
        "time.sleep(10)\n", encoding="utf-8")
    hook = tmp_path / "monitor.sh"
    hook.write_text(f"#!/bin/sh\nexec {shlex.quote(Path(sys.executable).as_posix())} -B {shlex.quote(monitor.as_posix())}\n", encoding="utf-8")
    hook.chmod(0o755)

    def prepare(project: Path) -> None:
        (project / "probe.txt").write_text("tracked", encoding="utf-8")
        assert _git(project, "add", "probe.txt").returncode == 0
        assert _git(project, "config", "core.fsmonitor", hook.as_posix()).returncode == 0

    started = time.monotonic()
    result, project = _budget_run(tmp_path, before_run=prepare)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "bounded-cleanup-fallback" in result.stdout
    assert "check-start:" not in result.stdout
    assert time.monotonic() - started < 6
    assert pids.exists(), result.stdout + result.stderr
    for pid in json.loads(pids.read_text()):
        _assert_pid_terminated(pid)
    report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
    assert report["verificationStatus"] == "failed"
    assert report["reason"] == "total_budget_timeout"
    assert report["notStarted"] == ["slow", "later"]


def test_public_verify_does_not_swallow_cache_write_failure(tmp_path: Path) -> None:
    def blocked_cache(project: Path) -> None:
        (project / ".build-and-verify/cache").write_text("blocked", encoding="utf-8")

    result, project = _budget_run(tmp_path, extra=("--performance-report",), before_run=blocked_cache,
        checks=[{"id": "success", "command": [sys.executable, "-c", "print('CHECK_COMPLETED')"], "inputs": []}])
    assert result.returncode == 1, result.stdout + result.stderr
    assert "CHECK_COMPLETED" in result.stdout
    assert "cache_write_error" in result.stderr
    report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
    assert report["verificationStatus"] == "failed"
    assert report["checks"][0]["reason"] == "cache_write_error"


def test_review_python_startup_is_inside_total_budget(tmp_path: Path, monkeypatch) -> None:
    startup = tmp_path / "startup"
    startup.mkdir()
    (startup / "sitecustomize.py").write_text(
        "import sys,time\n"
        "if sys.argv[0].endswith('build_and_verify.py'): time.sleep(2)\n",
        encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(startup))
    started = time.monotonic()
    result, _ = _budget_run(tmp_path, settings={"fullBudgetSeconds": 1}, checks=[
        {"id": "quick", "command": [sys.executable, "-c", "print('QUICK_STARTED')"], "inputs": []}])
    elapsed = time.monotonic() - started
    assert result.returncode == 1, f"elapsed={elapsed:.2f}\n{result.stdout}\n{result.stderr}"
    assert elapsed < 1.8
    assert "QUICK_STARTED" not in result.stdout


def test_review_python_probe_is_bounded(tmp_path: Path, monkeypatch) -> None:
    startup = tmp_path / "startup"
    startup.mkdir()
    (startup / "sitecustomize.py").write_text(
        "import sys,time\nif sys.argv[0] == '-c': time.sleep(2)\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(startup))
    started = time.monotonic()
    result, _ = _budget_run(tmp_path, settings={"fullBudgetSeconds": 1}, checks=[
        {"id": "quick", "command": [sys.executable, "-c", "print('QUICK_STARTED')"], "inputs": []}])
    assert result.returncode == 1, result.stdout + result.stderr
    assert time.monotonic() - started < 1.8
    assert "QUICK_STARTED" not in result.stdout


def test_review_legacy_migration_is_inside_total_budget(tmp_path: Path) -> None:
    project = _legacy_project(tmp_path)
    config = project / ".build-and-verify/config.json"
    config.write_text(json.dumps({"version": 1, "verify": {
        "fullBudgetSeconds": 1, "checks": []}}), encoding="utf-8")
    assert _git(project, "add", ".").returncode == 0
    assert _git(project, "commit", "-m", "short budget").returncode == 0
    hook = project / ".git/hooks/pre-commit"
    hook.write_text(f"#!/bin/sh\nexec {shlex.quote(Path(sys.executable).as_posix())} -c 'import time; time.sleep(3)'\n", encoding="utf-8")
    hook.chmod(0o755)
    before = {"status": _git(project, "status", "--porcelain").stdout,
              "head": _git(project, "rev-parse", "HEAD").stdout.strip()}
    started = time.monotonic()
    result = subprocess.run([shutil.which("node"), str(PACKAGE_ROOT / "bin/build-and-verify.js"),
        "verify", "--project", str(project), "--execution-context", "local"],
        env={**os.environ, "BUILD_AND_VERIFY_PYTHON": sys.executable, "CI": "false", "GITHUB_ACTIONS": "false"},
        text=True, capture_output=True, timeout=7)
    elapsed = time.monotonic() - started
    after = {"status": _git(project, "status", "--porcelain").stdout,
             "head": _git(project, "rev-parse", "HEAD").stdout.strip(),
             "runtimeExists": (project / ".build-and-verify/runtime").exists()}
    print(f"migration-state: before={before!r} after={after!r}")
    assert result.returncode == 1, f"elapsed={elapsed:.2f}\n{result.stdout}\n{result.stderr}"
    assert elapsed < 1.8
    assert after["head"] == before["head"]
    assert set(after["status"].splitlines()) == {
        "D  .build-and-verify/runtime/build_and_verify.py",
        "D  .build-and-verify/runtime/build_and_verify_runner.py",
        "D  .build-and-verify/runtime/version.json",
        "?? .build-and-verify/runs/"}


def _delay_report(tmp_path: Path, monkeypatch, seconds: float, *, main_only: bool,
                  deadline_relative: bool = False) -> None:
    startup = tmp_path / "startup"
    startup.mkdir()
    (startup / "sitecustomize.py").write_text(
        "import sys,threading,time\n"
        "def profile(frame,event,arg):\n"
        "    if event == 'call' and frame.f_code.co_name == '_write_performance_report'"
        + (" and threading.current_thread() is threading.main_thread()" if main_only else "") + ":\n"
        + (f"        time.sleep(max(0, frame.f_locals['payload']['budgetSeconds'] - frame.f_locals['payload']['totalSeconds'] + {seconds}))\n"
           if deadline_relative else f"        time.sleep({seconds})\n") +
        "if sys.argv[0].endswith('build_and_verify.py'):\n"
        "    sys.setprofile(profile)\n    threading.setprofile(profile)\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(startup))


def test_review_report_crossing_deadline_cannot_pass(tmp_path: Path, monkeypatch) -> None:
    _delay_report(tmp_path, monkeypatch, 0.2, main_only=True, deadline_relative=True)
    started = time.monotonic()
    result, project = _budget_run(tmp_path, settings={"fullBudgetSeconds": 1},
        extra=("--performance-report",), checks=[{"id": "quick", "command":
            [sys.executable, "-c", "import time; time.sleep(.05)"], "inputs": []}])
    assert "check-end: quick status=passed" in result.stdout, result.stdout + result.stderr
    assert result.returncode == 1, f"elapsed={time.monotonic()-started:.2f}\n{result.stdout}\n{result.stderr}"
    assert "status: passed" not in result.stdout
    report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
    assert report["verificationStatus"] == "failed"
    assert report["reason"] == "total_budget_timeout"


@pytest.mark.parametrize("blocked_io", ["report", "output"])
def test_review_blocked_failure_report_cannot_delay_reaping(tmp_path: Path, monkeypatch, blocked_io: str) -> None:
    if blocked_io == "report":
        _delay_report(tmp_path, monkeypatch, 4, main_only=False)
    else:
        startup = tmp_path / "startup"
        startup.mkdir()
        (startup / "sitecustomize.py").write_text(
            "import builtins,sys,time\noriginal=builtins.print\n"
            "def delayed(*args,**kwargs):\n"
            "    if args and str(args[0]).startswith(('check-end:', 'total_budget_timeout:')): time.sleep(4)\n"
            "    return original(*args,**kwargs)\n"
            "if sys.argv[0].endswith('build_and_verify.py'): builtins.print=delayed\n", encoding="utf-8")
        monkeypatch.setenv("PYTHONPATH", str(startup))
    pid_file = tmp_path / "descendant.pid"
    parent_code = ("import subprocess,sys,time,pathlib; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(5)']); "
        f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid)); time.sleep(5)")
    started = time.monotonic()
    result, _ = _budget_run(tmp_path, settings={"fullBudgetSeconds": 1}, checks=[
        {"id": "tree", "command": [sys.executable, "-c", parent_code], "inputs": []}])
    elapsed = time.monotonic() - started
    assert result.returncode == 1, result.stdout + result.stderr
    assert elapsed < 2.5, f"cutoff was blocked by report I/O: {elapsed:.2f}s"
    assert pid_file.exists(), result.stdout + result.stderr
    _assert_pid_terminated(int(pid_file.read_text()))


def test_review_output_crossing_deadline_cannot_pass(tmp_path: Path, monkeypatch) -> None:
    startup = tmp_path / "startup"
    startup.mkdir()
    (startup / "sitecustomize.py").write_text(
        "import builtins,sys,time\noriginal=builtins.print\nstarted=time.monotonic()\n"
        "def delayed(*args,**kwargs):\n"
        "    if args and str(args[0]).startswith('checked:'):\n"
        "        time.sleep(max(0, started+.9-time.monotonic())+.3)\n"
        "    return original(*args,**kwargs)\n"
        "if sys.argv[0].endswith('build_and_verify.py'): builtins.print=delayed\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(startup))
    result, project = _budget_run(tmp_path, settings={"fullBudgetSeconds": 1},
        extra=("--performance-report",), checks=[{"id": "quick", "command":
            [sys.executable, "-c", "print('DONE')"], "inputs": []}])
    assert "check-end: quick status=passed" in result.stdout, result.stdout + result.stderr
    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: passed" not in result.stdout
    report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
    assert report["verificationStatus"] == "failed"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows suspended-process ownership")
def test_review_expired_windows_launch_is_never_resumed(tmp_path: Path, monkeypatch) -> None:
    import importlib.util
    package_root = Path(os.environ.get("BUILD_AND_VERIFY_TEST_PACKAGE", str(PACKAGE_ROOT)))
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
def test_review_startup_reaps_descendants_after_parent_exits(tmp_path: Path, monkeypatch, phase: str) -> None:
    startup = tmp_path / "startup"
    startup.mkdir()
    pids = tmp_path / "startup-pids.txt"
    condition = "sys.argv[0] == '-c'" if phase == "probe" else "sys.argv[0].endswith('build_and_verify.py')"
    (startup / "sitecustomize.py").write_text(
        "import subprocess,sys\nfrom pathlib import Path\n"
        f"if {condition}:\n"
        "    child=subprocess.Popen([sys.executable,'-S','-c','import time; time.sleep(3)'])\n"
        f"    with Path({str(pids)!r}).open('a') as stream: stream.write(str(child.pid)+'\\n')\n"
        + ("    raise SystemExit(1)\n" if phase == "entry" else ""), encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(startup))
    started = time.monotonic()
    result, _ = _budget_run(tmp_path, settings={"fullBudgetSeconds": 1}, checks=[
        {"id": "quick", "command": [sys.executable, "-c", "print('DONE')"], "inputs": []}])
    elapsed = time.monotonic() - started
    assert result.returncode == 1, result.stdout + result.stderr
    assert elapsed < 1.8, f"startup descendant held the public entry open for {elapsed:.2f}s"
    assert pids.exists(), result.stdout + result.stderr
    owned_pids = [int(pid) for pid in pids.read_text().splitlines()]
    try:
        for pid in owned_pids:
            _assert_pid_terminated(pid)
    finally:
        # Red runs let these known synthetic children finish naturally; never
        # terminate a PID after its owning parent has exited and released it.
        for pid in owned_pids:
            until = time.monotonic() + 4
            while time.monotonic() < until:
                try:
                    _assert_pid_terminated(pid)
                    break
                except AssertionError:
                    time.sleep(0.02)


def test_review_interpreter_exit_remains_inside_total_budget(tmp_path: Path, monkeypatch) -> None:
    startup = tmp_path / "startup"
    startup.mkdir()
    (startup / "sitecustomize.py").write_text(
        "import atexit,sys,time\n"
        "if sys.argv[0].endswith('build_and_verify.py'): atexit.register(time.sleep,2)\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(startup))
    started = time.monotonic()
    result, project = _budget_run(tmp_path, settings={"fullBudgetSeconds": 1}, extra=("--performance-report",), checks=[
        {"id": "quick", "command": [sys.executable, "-c", "print('DONE')"], "inputs": []}])
    assert result.returncode == 1, result.stdout + result.stderr
    assert time.monotonic() - started < 1.8
    assert "status: passed" not in result.stdout
    report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
    assert report["verificationStatus"] == "failed"
    assert report["phase"] == "finalization"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows background-process compatibility")
def test_review_budget_off_preserves_background_dependency(tmp_path: Path) -> None:
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


def _installed_build_and_verify(tmp_path: Path) -> tuple[str, Path, Path]:
    global _installed_template
    npm = shutil.which("npm")
    assert npm is not None
    if _installed_template is None:
        _installed_template = tempfile.TemporaryDirectory(prefix="build-and-verify-test-")
        root = Path(_installed_template.name)
        packed = subprocess.run(
            [sys.executable, str(PACK), "build-and-verify", str(root / "package")],
            text=True,
            capture_output=True,
            check=False,
        )
        assert packed.returncode == 0, packed.stderr
        installed = subprocess.run(
            [npm, "install", "--global", "--prefix", str(root / "prefix"), "--ignore-scripts", "--no-audit", "--no-fund", packed.stdout.strip()],
            text=True,
            capture_output=True,
            check=False,
        )
        assert installed.returncode == 0, installed.stderr
    prefix = tmp_path / "prefix"
    shutil.copytree(Path(_installed_template.name) / "prefix", prefix, symlinks=True)
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")
    return npm, prefix, executable


def _tree_snapshot() -> dict[str, bytes]:
    roots = ("plugins/my-spec", "plugins/build-and-verify", "plugins/tool-lifecycle")
    return {
        path.relative_to(REPO_ROOT).as_posix(): path.read_bytes()
        for root in roots
        for path in (REPO_ROOT / root).rglob("*")
        if path.is_file()
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


def test_repository_automation_uses_build_and_verify_cli() -> None:
    commands = [
        (REPO_ROOT / ".github" / "workflows" / "full-verify.yml").read_text(encoding="utf-8"),
        (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"),
        (PACKAGE_ROOT / "skills" / "build-and-verify" / "SKILL.md").read_text(encoding="utf-8"),
    ]

    assert all("build-and-verify" in command for command in commands)
    assert all(".build-and-verify/runtime/build_and_verify.py" not in command for command in commands)
    assert all("scripts/build_and_verify.py" not in command for command in commands)
    assert "build-and-verify verify --project . --full" not in commands[0]
    assert "node plugins/build-and-verify/bin/build-and-verify.js verify --project . --full" in commands[0]
    assert "build-and-verify verify --project source --full" not in commands[1]


def test_full_verify_is_the_cross_platform_required_gate() -> None:
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "full-verify.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]
    gate = jobs["full-verify-gate"]
    gate_step = gate["steps"][0]
    gate_run = gate_step["run"]

    assert jobs["full-verify"]["name"] == "Linux Full Verify"
    assert jobs["windows-worktree-smoke"]["name"] == "Windows worktree smoke"
    assert "needs" not in jobs["full-verify"]
    assert "needs" not in jobs["windows-worktree-smoke"]
    assert gate["name"] == "Full Verify"
    assert set(gate["needs"]) == {"full-verify", "windows-worktree-smoke"}
    assert gate["if"] == "${{ always() }}"
    assert gate_step["env"]["LINUX_RESULT"] == "${{ needs.full-verify.result }}"
    assert gate_step["env"]["WINDOWS_RESULT"] == "${{ needs.windows-worktree-smoke.result }}"
    assert 'if [ "$LINUX_RESULT" != "success" ] || [ "$WINDOWS_RESULT" != "success" ]; then' in gate_run
    assert "exit 1" in gate_run


def test_windows_pr_verification_uses_fixed_baseline_and_manual_full_mode() -> None:
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "full-verify.yml").read_text(encoding="utf-8")
    )
    windows = workflow["jobs"]["windows-worktree-smoke"]
    checkout = next(step for step in windows["steps"] if step.get("name") == "Checkout")
    fast = next(
        step for step in windows["steps"] if step.get("name") == "Run PR fast verification"
    )
    manual = next(
        step
        for step in windows["steps"]
        if step.get("name") == "Run manual Windows full verification"
    )
    fast_run = fast["run"]
    manual_run = manual["run"]
    step_names = [step.get("name") for step in windows["steps"]]

    assert checkout["with"]["fetch-depth"] == 0
    assert windows["env"]["PYTHONUTF8"] == "1"
    assert step_names.index("Run PR fast verification") < step_names.index(
        "Initialize linked worktree"
    )
    assert step_names.index("Run manual Windows full verification") < step_names.index(
        "Initialize linked worktree"
    )
    assert step_names.index("Initialize linked worktree") < step_names.index(
        "Build from linked worktree"
    )
    assert fast["env"]["BASELINE"] == "${{ github.event.pull_request.base.sha }}"
    assert fast["if"] == "${{ github.event_name == 'pull_request' }}"
    assert manual["if"] == "${{ github.event_name == 'workflow_dispatch' }}"
    assert ". ./.venv/Scripts/Activate.ps1" in fast_run
    assert "$env:BUILD_AND_VERIFY_PYTHON = (Get-Command python).Source" in fast_run
    assert fast_run.index("Activate.ps1") < fast_run.index("BUILD_AND_VERIFY_PYTHON")
    assert fast_run.index("BUILD_AND_VERIFY_PYTHON") < fast_run.index("build-and-verify verify")
    assert "build-and-verify verify --project . --base $env:BASELINE" in fast_run
    assert "checked:" in fast_run
    assert "status: passed" in fast_run
    assert "exit 1" in fast_run
    assert ". ./.venv/Scripts/Activate.ps1" in manual_run
    assert "$env:BUILD_AND_VERIFY_PYTHON = (Get-Command python).Source" in manual_run
    assert manual_run.index("Activate.ps1") < manual_run.index("BUILD_AND_VERIFY_PYTHON")
    assert manual_run.index("BUILD_AND_VERIFY_PYTHON") < manual_run.index(
        "build-and-verify.js verify"
    )
    assert "node plugins/build-and-verify/bin/build-and-verify.js verify --project . --full" in manual_run
    assert "pytest" not in fast_run
    assert "build_and_verify.py" not in fast_run
    assert "scripts/" not in fast_run


def test_build_and_verify_package_excludes_legacy_skill_runtime() -> None:
    npm = shutil.which("npm")
    assert npm is not None

    packed = subprocess.run(
        [npm, "pack", "--dry-run", "--json"],
        cwd=PACKAGE_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert packed.returncode == 0, packed.stderr
    files = {entry["path"] for entry in json.loads(packed.stdout)[0]["files"]}
    assert "python/build_and_verify.py" in files
    assert "python/build_and_verify_runner.py" in files
    assert not any(path.startswith("skills/build-and-verify/scripts/") for path in files)


def test_controlled_pack_rejects_unknown_package(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(PACK), "unknown", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_controlled_pack_rejects_repository_output() -> None:
    result = subprocess.run(
        [sys.executable, str(PACK), "build-and-verify", str(REPO_ROOT / ".temporary-pack")],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "output_inside_repository" in result.stderr
    assert not (REPO_ROOT / ".temporary-pack").exists()


def test_packed_build_and_verify_rejects_untrusted_dev_source(tmp_path: Path) -> None:
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


def test_packed_build_and_verify_doctor_reports_machine_readable_release_identity(tmp_path: Path) -> None:
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
        "packageVersion": PACKAGE_VERSION,
    }


def test_packed_build_and_verify_update_blocks_legacy_codex_before_writes(tmp_path: Path) -> None:
    npm, prefix, executable = _installed_build_and_verify(tmp_path)
    node = shutil.which("node")
    assert node is not None
    latest = PACKAGE_VERSION
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
        "BUILD_PACKAGE_VERSION": PACKAGE_VERSION,
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
    assert json.loads(updated.stdout)["version"] == PACKAGE_VERSION


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
        json.dumps({"plugin": "build-and-verify", "plugin_version": PACKAGE_VERSION, "runtime_version": PACKAGE_VERSION}),
        encoding="utf-8",
    )
    assert _git(project, "init").returncode == 0
    assert _git(project, "config", "user.name", "test").returncode == 0
    assert _git(project, "config", "user.email", "test@example.invalid").returncode == 0
    assert _git(project, "add", ".").returncode == 0
    committed = _git(project, "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "initial")
    assert committed.returncode == 0, committed.stderr
    return project


def test_packed_build_and_verify_migrates_recognized_runtime_after_fast_verify(tmp_path: Path) -> None:
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


def test_packed_build_and_verify_preserves_legacy_runtime_when_verify_fails(tmp_path: Path) -> None:
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


def test_packed_build_and_verify_rejects_unrecognized_legacy_runtime(tmp_path: Path) -> None:
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


def test_packed_build_and_verify_preserves_runtime_when_fast_verify_stages_external_file(tmp_path: Path) -> None:
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


def test_packed_build_and_verify_restores_runtime_when_migration_commit_fails(tmp_path: Path) -> None:
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


def test_packed_build_and_verify_codex_doctor_resolves_orca_and_explicit_homes(
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


def test_packed_build_and_verify_rejects_dirty_legacy_migration(tmp_path: Path) -> None:
    _, prefix, executable = _installed_build_and_verify(tmp_path)
    project = _legacy_project(tmp_path)
    (project / "unrelated.txt").write_text("keep", encoding="utf-8")

    migrated = subprocess.run([executable, "verify", "--project", str(project)], cwd=project, text=True, capture_output=True, check=False, env=_isolated_env(tmp_path, prefix))

    assert migrated.returncode == 1
    assert "git_worktree_not_clean" in migrated.stderr
    assert (project / ".build-and-verify" / "runtime").is_dir()
    assert _git(project, "status", "--porcelain").stdout == "?? unrelated.txt\n"


def test_packed_build_and_verify_accepts_controlled_ssh_dev_source(tmp_path: Path) -> None:
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
        [executable, "doctor"], cwd=source, text=True, capture_output=True, check=False, env=env
    )
    assert diagnosed.returncode == 0, diagnosed.stderr
    toolchain = json.loads(diagnosed.stdout)["toolchain"]
    assert toolchain["sourceCommit"] == _git(source, "rev-parse", "HEAD").stdout.strip()


def test_packed_build_and_verify_dev_identity_controls_public_verify_cache(
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

    diagnosed = subprocess.run(
        [executable, "doctor"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert diagnosed.returncode == 0, diagnosed.stderr
    first_identity = json.loads(diagnosed.stdout)["toolchain"]["implementationIdentity"]

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

    def verify(*extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [executable, "verify", "--project", project, *extra],
            cwd=project,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    first = verify()
    second = verify()
    full = verify("--full")
    full_cached = verify()
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert full.returncode == 0, full.stderr
    assert full_cached.returncode == 0, full_cached.stderr
    assert "cache-hit: public-cache" in second.stdout
    assert "cache-hit:" not in full.stdout
    assert "cache-hit: public-cache" in full_cached.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == ["ran", "ran"]

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

    config["version"] = 2
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    config_diagnosed = subprocess.run(
        [executable, "doctor"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert config_diagnosed.returncode == 0, config_diagnosed.stderr
    assert json.loads(config_diagnosed.stdout)["toolchain"]["implementationIdentity"] == shared_identity
    config_changed = verify()
    assert config_changed.returncode == 0, config_changed.stderr
    assert "cache-hit: public-cache" not in config_changed.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "ran",
        "ran",
        "ran",
        "ran",
        "ran",
    ]
