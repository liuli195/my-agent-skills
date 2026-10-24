from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "plugins" / "build-and-verify"


@pytest.fixture
def memory_cli(monkeypatch):
    """Only configuration, cache, report I/O and the process/clock boundaries."""
    spec = importlib.util.spec_from_file_location("ordinary_cli_entrypoint", PACKAGE_ROOT / "python/build_and_verify.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    runner = module._runner()
    state = SimpleNamespace(config={}, cache={}, reports=[], clock=0.0,
        outcomes={}, calls=[], fail_report=False, fail_cache=False)
    def load_config(project):
        return runner._validate_config(json.loads(json.dumps(state.config)))
    def store(project, key, check):
        if state.fail_cache:
            raise OSError("cache blocked")
        state.cache[key] = check["id"]
    def report(path, payload):
        if state.fail_report:
            return False
        state.reports.append(json.loads(json.dumps(payload)))
        return True
    def execute(command, **kwargs):
        key = tuple(command) if isinstance(command, list) else command
        assert key in state.outcomes, f"unexpected command: {command!r}"
        state.calls.append(command)
        duration, code, stdout, stderr = state.outcomes[key]
        allowed = kwargs.get("timeout", duration)
        state.clock += min(duration, allowed)
        if duration > allowed:
            raise subprocess.TimeoutExpired(command, allowed, output=stdout, stderr=stderr)
        return subprocess.CompletedProcess(command, code, stdout, stderr)
    monkeypatch.setattr(runner, "_load_config", load_config)
    monkeypatch.setattr(runner, "_cache_load", lambda project, key: key in state.cache)
    monkeypatch.setattr(runner, "_cache_store", store)
    monkeypatch.setattr(runner, "_write_performance_report", report)
    monkeypatch.setattr(runner.time, "monotonic", lambda: state.clock)
    monkeypatch.setattr(module, "_runtime_metadata", lambda: {
        "runtime_version": "test-runtime", "implementation_identity": "test-implementation",
    })
    class ProcessBoundary:
        def __init__(self):
            self.runner = execute
        def __getattr__(self, name):
            return getattr(runner, name)
        def run_verify(self, project, **kwargs):
            return runner.run_verify(project, runner=self.runner, **kwargs)
    monkeypatch.setattr(runner, "_changed_files", lambda project: ["code.py"])
    monkeypatch.setattr(module, "_RUNNER_MODULE", ProcessBoundary())
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    monkeypatch.setenv("CI", "false")
    monkeypatch.delenv("BUILD_AND_VERIFY_EXECUTION_CONTEXT", raising=False)
    # This is a fresh CLI invocation, not the enclosing official check's start.
    monkeypatch.delenv("BUILD_AND_VERIFY_STARTED_MONOTONIC", raising=False)
    assert module.time is runner.time
    assert module.time.monotonic() == runner.time.monotonic() == state.clock
    state.module = module
    return state


def _budget_run(state, *, settings=None, context="local", extra=(), full=True, checks=None):
    checks = checks if checks is not None else [
        {"id": "slow", "command": ["slow"], "inputs": []},
        {"id": "later", "command": ["later"], "inputs": []},
    ]
    state.config = {"version": 1, "verify": {"fullBudgetSeconds": 3,
        "checks": checks, **(settings or {})}}
    state.outcomes = {tuple(check["command"]): (0.0, 0, "", "") for check in checks}
    if any(check["id"] == "slow" for check in checks):
        state.outcomes[("slow",)] = (state.config["verify"]["fullBudgetSeconds"] + .2, 0, "", "")
    if any(check["id"] == "later" for check in checks):
        state.outcomes[("later",)] = (0.0, 0, "LATER_STARTED\n", "")
    argv = ["verify", "--project", "/memory/build-and-verify", *( ("--full",) if full else ()), *extra]
    if context is not None:
        argv.extend(["--execution-context", context])
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = state.module.main(argv)
    return subprocess.CompletedProcess(argv, code, stdout.getvalue(), stderr.getvalue()), state


def test_public_verify_budget_warning_does_not_fail_exempt_runs(memory_cli):
    result, state = _budget_run(memory_cli, settings={"fullBudgetSeconds": 1, "enforceLocalBudget": False})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "LATER_STARTED" in result.stdout and "performance-warning:" in result.stdout
    assert state.reports[-1]["overBudget"] is True


def test_public_verify_timeout_report_failure_warns_without_changing_failure(memory_cli):
    memory_cli.fail_report = True
    result, state = _budget_run(memory_cli)
    assert result.returncode == 1
    assert "total_budget_timeout" in result.stdout
    assert "performance-report-warning:" in result.stderr
    assert "LATER_STARTED" not in result.stdout and "status: passed" not in result.stdout
    assert state.cache == {}


def test_public_verify_protocol_like_check_output_is_preserved(memory_cli, monkeypatch):
    lines = ["build-and-verify-formal-result: ordinary-test-output",
        'build-and-verify-formal-result: {"status":"passed"}',
        "build-and-verify-selected: ordinary-test-output",
        'build-and-verify-selected: {"ids":"ordinary-test-output","runtimeVersion":"test"}']
    runner = memory_cli.module._RUNNER_MODULE
    def exact_output(command, **kwargs):
        assert command == ["output"]
        return subprocess.CompletedProcess(command, 0, "\n".join(lines) + "\n", "")
    monkeypatch.setattr(runner, "runner", exact_output)
    result, _ = _budget_run(memory_cli, checks=[{"id": "output", "command": ["output"], "inputs": []}])
    assert result.returncode == 0 and all(line in result.stdout for line in lines)
    assert "status: passed" in result.stdout


def test_public_verify_unknown_context_fails_before_launch(memory_cli):
    result, state = _budget_run(memory_cli, context=None)
    assert result.returncode == 1
    assert "execution-context-warning: unknown" in result.stdout
    assert "execution_context_required_for_local_budget" in result.stderr
    assert "check-start:" not in result.stdout and state.calls == []


def test_public_verify_parallel_queue_shares_deadline(memory_cli):
    checks = [{"id": name, "command": [name], "inputs": [], "checkParallel": parallel}
        for name, parallel in (("slow", True), ("queued", True), ("serial", False))]
    result, state = _budget_run(memory_cli, settings={"maxParallel": 1}, checks=checks)
    assert result.returncode == 1
    assert state.calls == [["slow"]]
    assert state.reports[-1]["notStarted"] == ["queued", "serial"]


def test_public_verify_serial_checks_share_remaining_budget_and_cache_only_completed(memory_cli, monkeypatch):
    def exact_timed_process(command, **kwargs):
        duration = {"first": .5, "second": 4.7, "third": .1}[command[0]]
        memory_cli.calls.append(command)
        remaining = kwargs["timeout"]
        memory_cli.clock += min(duration, remaining)
        if duration > remaining:
            raise subprocess.TimeoutExpired(command, remaining)
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr(memory_cli.module._RUNNER_MODULE, "runner", exact_timed_process)
    checks = [{"id": name, "command": [name], "inputs": []} for name in ("first", "second", "third")]
    result, state = _budget_run(memory_cli, settings={"fullBudgetSeconds": 5}, checks=checks)
    assert result.returncode == 1
    assert [check["status"] for check in state.reports[-1]["checks"]] == ["passed", "timed_out", "not_started"]
    assert list(state.cache.values()) == ["first"]


@pytest.mark.parametrize("extra,settings", [(("--diagnostic",), {}), ((), {"enforceLocalBudget": False})])
def test_public_verify_warning_and_diagnostic_preserve_real_errors(memory_cli, monkeypatch, extra, settings):
    def exact_failure(command, **kwargs):
        assert command == ["error"]
        return subprocess.CompletedProcess(command, 7, "", "REAL_ASSERTION\n")
    monkeypatch.setattr(memory_cli.module._RUNNER_MODULE, "runner", exact_failure)
    result, _ = _budget_run(memory_cli, settings=settings, extra=extra,
        checks=[{"id": "error", "command": ["error"], "inputs": []}])
    assert result.returncode == 1 and "REAL_ASSERTION" in result.stderr


def test_public_verify_diagnostic_is_not_formal_acceptance(memory_cli):
    result, state = _budget_run(memory_cli, settings={"fullBudgetSeconds": 1}, extra=("--diagnostic",))
    assert result.returncode == 0
    assert "LATER_STARTED" in result.stdout and "check-start: slow" in result.stdout
    assert "status: diagnostic" in result.stdout and "status: passed\n" not in result.stdout
    assert state.reports[-1]["verificationStatus"] == "diagnostic"
    assert state.reports[-1]["diagnostic"] is True and state.cache == {}
    assert "enforceLocalBudget" not in state.config["verify"]


@pytest.mark.parametrize("extra,settings", [
    (("--diagnostic",), {"timeoutSeconds": .2}),
    ((), {"enforceLocalBudget": False, "timeoutSeconds": .2}),
])
def test_public_verify_diagnostic_and_warning_preserve_check_timeout(memory_cli, extra, settings):
    result, _ = _budget_run(memory_cli, extra=extra, settings=settings)
    assert result.returncode == 1 and "check_timeout: slow" in result.stderr


def test_public_verify_does_not_swallow_cache_write_failure(memory_cli):
    memory_cli.fail_cache = True
    result, state = _budget_run(memory_cli, extra=("--performance-report",),
        checks=[{"id": "success", "command": ["success"], "inputs": []}])
    assert result.returncode == 1 and "cache_write_error" in result.stderr
    assert state.reports[-1]["verificationStatus"] == "failed"
    assert state.reports[-1]["checks"][0]["reason"] == "cache_write_error"


@pytest.mark.parametrize("argv,error", [
    (["verify", "--performance-report"], "--performance-report requires --full"),
    (["verify", "--execution-context", "elsewhere"], "invalid choice"),
])
def test_public_verify_rejects_invalid_arguments_before_execution(memory_cli, argv, error):
    output = io.StringIO()
    with contextlib.redirect_stderr(output):
        assert memory_cli.module.main(argv) == 2
    assert error in output.getvalue() and memory_cli.calls == []

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
