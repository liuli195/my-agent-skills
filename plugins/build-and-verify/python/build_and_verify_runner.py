from __future__ import annotations

import concurrent.futures
import dataclasses
import fnmatch
import hashlib
import importlib.util
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections.abc import Callable


FRAMEWORK_VERSION = "0.1.0"
CACHE_VERSION = "1"
DEFAULT_CHECK_TIMEOUT_SECONDS = 300
PYTEST_XDIST_AUTO_WORKERS_ENV = "PYTEST_XDIST_AUTO_NUM_WORKERS"
DEFAULT_PYTEST_XDIST_AUTO_NUM_WORKERS = "4"
Runner = Callable[..., subprocess.CompletedProcess[Any]]


class ConfigError(Exception):
    pass


@dataclasses.dataclass
class CheckResult:
    index: int
    check: dict[str, Any]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    cache_key: str | None = None
    status: str | None = None
    reason: str | None = None


class TotalBudgetTimeout(subprocess.TimeoutExpired):
    pass


class RunControl:
    """One invocation's clock and launch lock; never owns unrelated processes."""

    def __init__(self, deadline: float | None):
        self.deadline = deadline
        self.lock = threading.Lock()
        self.cancelled = threading.Event()
        self.processes: dict[int, subprocess.Popen] = {}
        self.selected: list[dict[str, Any]] = []
        self.results: dict[str, CheckResult] = {}
        self.active_checks: set[str] = set()
        self.runtime_version = "unknown"

    def expired(self) -> bool:
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.cancelled.set()
        return self.cancelled.is_set()


def _windows_job(process: subprocess.Popen) -> tuple[Any, Any]:
    # Spawn suspended, assign before resuming: descendants cannot escape the job
    # in the gap between process creation and assignment.
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [("processTime", ctypes.c_int64), ("jobTime", ctypes.c_int64),
                    ("flags", wintypes.DWORD), ("minWorkingSet", ctypes.c_size_t),
                    ("maxWorkingSet", ctypes.c_size_t), ("activeProcesses", wintypes.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                    ("scheduling", wintypes.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ("readOps", "writeOps", "otherOps", "readBytes", "writeBytes", "otherBytes")]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("basic", BasicLimits), ("io", IoCounters),
                    ("processMemory", ctypes.c_size_t), ("jobMemory", ctypes.c_size_t),
                    ("peakProcessMemory", ctypes.c_size_t), ("peakJobMemory", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(job, wintypes.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())
        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        ntdll.NtResumeProcess.restype = ctypes.c_long
        if ntdll.NtResumeProcess(wintypes.HANDLE(int(process._handle))) != 0:
            raise OSError("cannot_resume_owned_process")
        return kernel, job
    except BaseException:
        kernel.CloseHandle(job)
        raise


def _managed_run(command: Any, control: RunControl, **kwargs: Any) -> subprocess.CompletedProcess:
    import signal

    timeout = kwargs.pop("timeout", DEFAULT_CHECK_TIMEOUT_SECONDS)
    kwargs.pop("check", None)
    kwargs.pop("capture_output", None)
    kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.name == "nt":
        kwargs.update(creationflags=0x4, startupinfo=subprocess.STARTUPINFO())
        kwargs["startupinfo"].dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        kwargs["start_new_session"] = True
    job = None
    process = None
    try:
        with control.lock:
            if control.expired():
                raise TotalBudgetTimeout(command, 0)
            process = subprocess.Popen(command, **kwargs)
            control.processes[process.pid] = process
            if os.name == "nt":
                job = _windows_job(process)
        single_deadline = time.monotonic() + timeout
        while True:
            remaining = single_deadline - time.monotonic()
            if control.expired():
                raise TotalBudgetTimeout(command, timeout)
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            wait = min(0.05, remaining)
            if control.deadline is not None:
                wait = min(wait, max(0.001, control.deadline - time.monotonic()))
            try:
                stdout, stderr = process.communicate(timeout=wait)
                if control.expired():
                    raise TotalBudgetTimeout(command, timeout, output=stdout, stderr=stderr)
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired as error:
                if isinstance(error, TotalBudgetTimeout):
                    raise
    finally:
        if process is not None:
            if job is not None:
                job[0].CloseHandle(job[1])
            elif os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()
            try:
                process.communicate(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()
                # Close pipes instead of waiting indefinitely for an inherited handle.
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
            with control.lock:
                control.processes.pop(process.pid, None)


def _invocation_guard(project: Path, *, context: str | None, pr: bool,
                      diagnostic: bool, started_at: float) -> tuple[RunControl | None, Any]:
    """CLI-only last resort for blocked preparation or bounded cleanup failure."""
    context = context or os.environ.get("BUILD_AND_VERIFY_EXECUTION_CONTEXT")
    if (context != "local" or pr or diagnostic or os.environ.get("GITHUB_ACTIONS") == "true"
            or os.environ.get("CI", "").lower() == "true"):
        return None, None
    config = _load_config(project)
    verify = config.get("verify", {})
    budget = verify.get("fullBudgetSeconds")
    if (verify.get("enforceLocalBudget", True) is not True or isinstance(budget, bool)
            or not isinstance(budget, int) or budget <= 0):
        return None, None
    control = RunControl(started_at + budget)
    control.selected = _checks(config, "verify")
    root_job = None
    if os.name == "nt":
        # Keep this handle until process exit. Closing it terminates this CLI and
        # every descendant, even if preparation never reaches the scheduler.
        import ctypes
        from types import SimpleNamespace
        kernel = ctypes.WinDLL("kernel32")
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        root_job = _windows_job(SimpleNamespace(_handle=kernel.GetCurrentProcess()))
    else:
        if os.getsid(0) != os.getpid():
            os.setsid()

    def cutoff() -> None:
        control.cancelled.set()
        elapsed = round(time.monotonic() - started_at, 2)
        active = list(control.processes.values())
        for process in active:
            if os.name != "nt":
                import signal
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        completed = dict(control.results)
        unfinished = [check['id'] for check in control.selected if check['id'] in control.active_checks]
        not_started = [check['id'] for check in control.selected if check['id'] not in completed and check['id'] not in unfinished]
        payload = {"schemaVersion": 1, "runtimeVersion": control.runtime_version,
            "generatedAt": datetime.now(timezone.utc).isoformat(), "totalSeconds": elapsed,
            "budgetSeconds": budget, "overBudget": True, "verificationStatus": "failed",
            "executionContext": "local", "diagnostic": False, "reason": "total_budget_timeout",
            "unfinished": unfinished, "notStarted": not_started,
            "checks": [{"id": check['id'], "status": completed[check['id']].status if check['id'] in completed
                else ("timed_out" if check['id'] in unfinished else "not_started"),
                "durationSeconds": round(completed[check['id']].duration_seconds, 2) if check['id'] in completed else 0}
                for check in control.selected]}
        _write_performance_report(project / ".build-and-verify/runs/performance-report.json", payload)
        print(f"total_budget_timeout: totalSeconds={elapsed:.2f} budgetSeconds={budget}; bounded-cleanup-fallback", flush=True)
        print(f"unfinished: {', '.join(unfinished)}", flush=True)
        print(f"not-started: {', '.join(not_started)}", flush=True)
        print("status: failed", flush=True)
        if root_job is not None:
            root_job[0].CloseHandle(root_job[1])
        else:
            import signal
            os.killpg(os.getpid(), signal.SIGKILL)
        os._exit(1)

    timer = threading.Timer(max(0, started_at + budget + 0.75 - time.monotonic()), cutoff)
    timer.daemon = True
    timer.start()
    # Keep the owning Windows handle alive after cancellation until CLI exit.
    timer.root_job = root_job
    return control, timer


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        _is_non_empty_string(item) for item in value
    )


def _command_tokens(command: Any) -> list[str]:
    if isinstance(command, str):
        try:
            return shlex.split(command)
        except ValueError:
            return command.split()
    if isinstance(command, list):
        return [str(item) for item in command]
    return []


def _uses_pytest(command: Any) -> bool:
    tokens = _command_tokens(command)
    has_pytest = any(token == "pytest" or token.endswith("/pytest") or token.endswith("\\pytest") for token in tokens)
    has_pytest_module = any(
        token == "-m" and index + 1 < len(tokens) and tokens[index + 1] == "pytest"
        for index, token in enumerate(tokens)
    )
    return has_pytest or has_pytest_module


def uses_pytest_xdist(command: Any) -> bool:
    tokens = _command_tokens(command)
    has_xdist_flag = any(
        token == "-n"
        or (token.startswith("-n") and len(token) > 2)
        or token == "--numprocesses"
        or token.startswith("--numprocesses=")
        for token in tokens
    )
    return has_xdist_flag and _uses_pytest(command)


def _pytest_xdist_workers(value: Any) -> str | None:
    if value is None:
        return None
    if value == "auto":
        return "auto"
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError('pytestXdistWorkers must be "auto" or positive integer')
    return str(value)


def _string_command_token_spans(command: str) -> list[tuple[str, int]]:
    spans: list[tuple[str, int]] = []
    for match in re.finditer(r'''"[^"]*"|'[^']*'|\S+''', command):
        raw = match.group(0)
        token = (
            raw[1:-1]
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}
            else raw
        )
        spans.append((token, match.end()))
    return spans


def _command_with_pytest_xdist_workers(command: Any, workers: str | None) -> Any:
    if workers is None or not _uses_pytest(command) or uses_pytest_xdist(command):
        return command
    if isinstance(command, list):
        tokens = [str(item) for item in command]
        for index, token in enumerate(tokens):
            if token == "pytest" or token.endswith("/pytest") or token.endswith("\\pytest"):
                return tokens[: index + 1] + ["-n", workers] + tokens[index + 1 :]
            if token == "-m" and index + 1 < len(tokens) and tokens[index + 1] == "pytest":
                insert_at = index + 2
                return tokens[:insert_at] + ["-n", workers] + tokens[insert_at:]
    if isinstance(command, str):
        tokens = _string_command_token_spans(command)
        for index, (token, end) in enumerate(tokens):
            if token == "pytest" or token.endswith("/pytest") or token.endswith("\\pytest"):
                return f"{command[:end]} -n {workers}{command[end:]}"
            if (
                token == "-m"
                and index + 1 < len(tokens)
                and tokens[index + 1][0] == "pytest"
            ):
                end = tokens[index + 1][1]
                return f"{command[:end]} -n {workers}{command[end:]}"
    return command


def _pytest_xdist_env(workers: str | None) -> dict[str, str] | None:
    if workers != "auto" or os.environ.get(PYTEST_XDIST_AUTO_WORKERS_ENV):
        return None
    env = os.environ.copy()
    env[PYTEST_XDIST_AUTO_WORKERS_ENV] = DEFAULT_PYTEST_XDIST_AUTO_NUM_WORKERS
    return env


def _dependency_error(check: dict[str, Any]) -> str | None:
    command = check.get("command")
    workers = _pytest_xdist_workers(check.get("pytestXdistWorkers"))
    needs_xdist = uses_pytest_xdist(command) or (workers is not None and _uses_pytest(command))
    if needs_xdist and importlib.util.find_spec("xdist") is None:
        return (
            f"missing_dependency: {check.get('id')}: pytest-xdist is required "
            "for pytest xdist workers; install requirements-dev.txt\n"
        )
    return None


def _load_config(project: Path) -> dict[str, Any]:
    config_path = project / ".build-and-verify" / "config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError("missing_config: .build-and-verify/config.json") from None
    except json.JSONDecodeError as error:
        raise ConfigError(
            f"invalid_config: .build-and-verify/config.json: {error.msg}"
        ) from None
    if not isinstance(config, dict):
        raise ConfigError(
            "invalid_config: .build-and-verify/config.json: root must be object"
        )
    for section in ("build", "verify"):
        section_config = config.get(section, {})
        if not isinstance(section_config, dict):
            raise ConfigError(
                f"invalid_config: .build-and-verify/config.json: {section} must be object"
            )
        if section == "verify":
            max_parallel = section_config.get("maxParallel")
            if max_parallel is not None and (
                isinstance(max_parallel, bool)
                or not isinstance(max_parallel, int)
                or max_parallel < 0
            ):
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    "verify.maxParallel must be non-negative integer"
                )
        checks = section_config.get("checks", [])
        if not isinstance(checks, list):
            raise ConfigError(
                f"invalid_config: .build-and-verify/config.json: {section}.checks must be list"
            )
        seen_ids: set[str] = set()
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}] must be object"
                )
            check_id = check.get("id")
            if not _is_non_empty_string(check_id):
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}].id must be non-empty string"
                )
            if check_id in seen_ids:
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}].id must be unique"
                )
            seen_ids.add(check_id)
            if "pr" in check and not isinstance(check["pr"], bool):
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}].pr must be boolean"
                )
            command = check.get("command")
            if not (
                _is_non_empty_string(command) or _is_non_empty_string_list(command)
            ):
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}].command must be non-empty string or list of non-empty strings"
                )
            if "parallel" in check:
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}].parallel is no longer supported; use checkParallel"
                )
            if "checkParallel" in check and not isinstance(check.get("checkParallel"), bool):
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}].checkParallel must be boolean"
                )
            try:
                workers = _pytest_xdist_workers(check.get("pytestXdistWorkers"))
            except ConfigError as error:
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}].{error}"
                ) from None
            if workers is not None and not _uses_pytest(command):
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}].pytestXdistWorkers requires pytest command"
                )
            for field in ("paths", "inputs"):
                value = check.get(field)
                if value is not None and not _is_non_empty_string_list(value):
                    raise ConfigError(
                        "invalid_config: .build-and-verify/config.json: "
                        f"{section}.checks[{index}].{field} must be list of non-empty strings"
                    )
    return config


def _normalize_path(path: str | Path) -> str:
    return Path(str(path).replace("\\", "/")).as_posix().strip("/")


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        normalized = _normalize_path(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def _git_names(project: Path, *args: str) -> list[str] | None:
    result = subprocess.run(
        ["git", *args],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.splitlines()


def _git_status_names(project: Path) -> list[str] | None:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    entries = result.stdout.split("\0")
    names: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        if status[0] in {"R", "C"}:
            # In porcelain v1 -z mode, rename/copy entries are destination then source.
            if path:
                names.append(path)
            index += 1
            continue
        if path:
            names.append(path)
    return names


def _is_excluded_relative(relative: str) -> bool:
    parts = relative.split("/")
    return (
        ".git" in parts
        or "__pycache__" in parts
        or relative == ".build-and-verify/cache"
        or relative.startswith(".build-and-verify/cache/")
    )


def _all_project_files(project: Path) -> list[str]:
    files: list[str] = []
    for root, dirs, names in os.walk(project):
        root_path = Path(root)
        kept_dirs: list[str] = []
        for name in dirs:
            relative = (root_path / name).relative_to(project).as_posix()
            if not _is_excluded_relative(relative):
                kept_dirs.append(name)
        dirs[:] = kept_dirs
        for name in names:
            path = root_path / name
            relative = path.relative_to(project).as_posix()
            if not _is_excluded_relative(relative):
                files.append(relative)
    return sorted(files)


def _changed_files(project: Path) -> list[str]:
    status_names = _git_status_names(project)
    if status_names is not None:
        return _dedupe(status_names)
    commands = [
        ("diff", "--name-only", "--cached"),
        ("diff", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ]
    names: list[str] = []
    any_git_command_succeeded = False
    for command in commands:
        result = _git_names(project, *command)
        if result is None:
            continue
        any_git_command_succeeded = True
        names.extend(result)
    if not any_git_command_succeeded:
        names = _all_project_files(project)
    return _dedupe(names)


def _git_result(project: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=project,
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError:
        return None


def _resolve_commit(project: Path, ref: str) -> str | None:
    result = _git_result(
        project,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{ref}^{{commit}}",
    )
    if result is None or result.returncode != 0:
        return None
    commit = result.stdout.strip()
    return commit if commit and "\n" not in commit else None


def _baseline_changed_files(
    project: Path, baseline: str
) -> tuple[list[str] | None, str | None]:
    if not _is_non_empty_string(baseline):
        return None, "invalid_baseline"
    baseline_commit = _resolve_commit(project, baseline)
    if baseline_commit is None:
        return None, f"invalid_baseline: {baseline}"
    head_commit = _resolve_commit(project, "HEAD")
    if head_commit is None:
        return None, "baseline_git_repository_required"
    status = _git_result(
        project,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    if status is None or status.returncode != 0:
        return None, "baseline_git_repository_required"
    if status.stdout:
        return None, "baseline_worktree_not_clean"
    diff = _git_result(
        project,
        "diff",
        "--name-only",
        "-z",
        f"{baseline_commit}...{head_commit}",
    )
    if diff is None or diff.returncode != 0:
        return None, "baseline_diff_failed"
    return _dedupe([path for path in diff.stdout.split("\0") if path]), None


def _path_matches(pattern: str, changed_file: str) -> bool:
    raw_pattern = str(pattern).replace("\\", "/").strip()
    directory_pattern = raw_pattern.endswith("/")
    pattern = raw_pattern.strip("/")
    changed_file = _normalize_path(changed_file)
    if not pattern:
        return False
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return changed_file == prefix or changed_file.startswith(prefix + "/")
    if directory_pattern:
        prefix = pattern.rstrip("/")
        return changed_file == prefix or changed_file.startswith(prefix + "/")
    if any(char in pattern for char in "*?["):
        return fnmatch.fnmatch(changed_file, pattern)
    if "/" in pattern:
        return changed_file == pattern or changed_file.startswith(pattern.rstrip("/") + "/")
    return changed_file == pattern


def _selected_checks(
    checks: list[dict[str, Any]], changed_files: list[str]
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for check in checks:
        paths = check.get("paths") or []
        if not paths:
            # Pathless checks are global checks in default verify mode.
            if changed_files:
                selected.append(check)
            continue
        if any(_path_matches(pattern, changed) for pattern in paths for changed in changed_files):
            selected.append(check)
    return selected


def _stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to_project(project: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(project.resolve())
    except ValueError:
        return False
    return True


def _validate_project_relative_input(project: Path, input_path: str) -> tuple[str, Path]:
    raw_path = Path(input_path)
    relative = _normalize_path(input_path)
    if (
        raw_path.is_absolute()
        or str(input_path).replace("\\", "/").startswith("/")
        or raw_path.anchor
        or ".." in Path(relative).parts
    ):
        raise ValueError(f"invalid_input_path: {input_path}")
    path = project / relative
    if not _is_relative_to_project(project, path):
        raise ValueError(f"invalid_input_path: {input_path}")
    return relative, path


def _validate_check_inputs(project: Path, check: dict[str, Any]) -> None:
    for input_path in check.get("inputs") or []:
        _validate_project_relative_input(project, input_path)


def _git_visible_files(project: Path, relative: str) -> list[Path] | None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", relative],
            cwd=project,
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return [project / name for name in result.stdout.split("\0") if name]


def _is_glob_input(path: str) -> bool:
    return any(character in path for character in "*?[")


def _hash_input(project: Path, input_path: str) -> dict[str, Any]:
    relative, path = _validate_project_relative_input(project, input_path)
    if _is_glob_input(relative):
        git_files = _git_visible_files(project, ".")
        candidates = (
            git_files
            if git_files is not None
            else [project / item for item in _all_project_files(project)]
        )
        files: list[dict[str, str]] = []
        for file_path in candidates:
            if not file_path.is_file():
                continue
            child_relative = file_path.relative_to(project).as_posix()
            if fnmatch.fnmatch(child_relative, relative):
                if not _is_relative_to_project(project, file_path):
                    raise ValueError(f"invalid_input_path: {input_path}")
                files.append({"path": child_relative, "sha256": _hash_file(file_path)})
        return {"path": relative, "type": "glob", "files": sorted(files, key=lambda item: item["path"])}
    if not path.exists():
        return {"path": relative, "missing": True}
    if path.is_file():
        return {"path": relative, "type": "file", "sha256": _hash_file(path)}
    if path.is_dir():
        files: list[dict[str, str]] = []
        git_files = _git_visible_files(project, relative)
        if git_files is not None:
            for file_path in git_files:
                if not file_path.is_file():
                    continue
                child_relative = file_path.relative_to(project).as_posix()
                if not _is_relative_to_project(project, file_path):
                    raise ValueError(f"invalid_input_path: {child_relative}")
                files.append({"path": child_relative, "sha256": _hash_file(file_path)})
        else:
            for root, dirs, names in os.walk(path):
                root_path = Path(root)
                kept_dirs: list[str] = []
                for name in dirs:
                    child_relative = (root_path / name).relative_to(project).as_posix()
                    if not _is_excluded_relative(child_relative):
                        kept_dirs.append(name)
                dirs[:] = kept_dirs
                for name in sorted(names):
                    file_path = root_path / name
                    child_relative = file_path.relative_to(project).as_posix()
                    if _is_excluded_relative(child_relative):
                        continue
                    if not _is_relative_to_project(project, file_path):
                        raise ValueError(f"invalid_input_path: {child_relative}")
                    files.append({"path": child_relative, "sha256": _hash_file(file_path)})
        return {"path": relative, "type": "directory", "files": sorted(files, key=lambda item: item["path"])}
    return {"path": relative, "type": "other"}


def _default_cache_inputs(project: Path, paths: list[str]) -> list[str]:
    matched: list[str] = []
    for pattern in paths:
        normalized = _normalize_path(pattern)
        if Path(pattern).anchor or ".." in Path(normalized).parts:
            raise ValueError(f"invalid_input_path: {pattern}")
        matched.extend(
            relative
            for relative in _all_project_files(project)
            if _path_matches(normalized, relative)
        )
    return _dedupe(matched)


def _cache_key(
    project: Path,
    config: dict[str, Any],
    check: dict[str, Any],
    changed_files: list[str] | None = None,
    runtime_identity: str = "unknown",
) -> str:
    if "inputs" in check and check.get("inputs") is not None:
        inputs = check.get("inputs") or []
    else:
        paths = check.get("paths") or []
        if paths:
            inputs = _default_cache_inputs(project, paths)
        else:
            inputs = changed_files if changed_files is not None else _changed_files(project)
    payload = {
        "cache_version": CACHE_VERSION,
        "framework_version": FRAMEWORK_VERSION,
        "python_version": platform.python_version(),
        "runtime_identity": runtime_identity,
        "check_id": check.get("id"),
        "command": check.get("command"),
        "inputs": [_hash_input(project, item) for item in inputs],
        "config": hashlib.sha256(_stable_json(config).encode("utf-8")).hexdigest(),
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _cache_path(project: Path, key: str) -> Path:
    return project / ".build-and-verify" / "cache" / f"{key}.json"


def _cache_load(project: Path, key: str) -> bool:
    path = _cache_path(project, key)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return data.get("status") == "passed"


def _cache_store(project: Path, key: str, check: dict[str, Any]) -> None:
    path = _cache_path(project, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temp.write_text(
            _stable_json({"status": "passed", "id": check.get("id")}) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def _format_seconds(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


def _check_timeout_seconds(config: dict[str, Any], check: dict[str, Any]) -> float | None:
    timeout = check.get("timeoutSeconds")
    verify_config = config.get("verify")
    if timeout is None and isinstance(verify_config, dict):
        timeout = verify_config.get("timeoutSeconds")
    if timeout is None:
        return float(DEFAULT_CHECK_TIMEOUT_SECONDS)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError(f"invalid_timeoutSeconds: {check.get('id')}")
    return float(timeout)


def _run_check(project: Path, check: dict[str, Any], runner: Runner) -> int:
    command = check.get("command")
    if not command:
        print(f"missing_command: {check.get('id')}", file=sys.stderr)
        return 1
    dependency_error = _dependency_error(check)
    if dependency_error is not None:
        print(dependency_error, end="", file=sys.stderr)
        return 1
    workers = _pytest_xdist_workers(check.get("pytestXdistWorkers"))
    command = _command_with_pytest_xdist_workers(command, workers)
    use_shell = isinstance(command, str)
    run_kwargs = {
        "cwd": project,
        "check": False,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "capture_output": True,
        "shell": use_shell,
    }
    env = _pytest_xdist_env(workers)
    if env is not None:
        run_kwargs["env"] = env
    try:
        result = runner(command, **run_kwargs)
    except FileNotFoundError:
        executable = command[0] if isinstance(command, list) else str(command)
        print(f"command_not_found: {check.get('id')}: {executable}", file=sys.stderr)
        return 1
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return int(result.returncode)


def _run_check_result(
    index: int,
    project: Path,
    check: dict[str, Any],
    config: dict[str, Any],
    changed_files: list[str],
    runner: Runner,
    runtime_identity: str,
    control: RunControl | None = None,
) -> CheckResult:
    started_at = time.monotonic()
    try:
        if control is not None and control.expired():
            return CheckResult(index, check, 1, status="not_started", reason="total_budget_timeout")
        key = _cache_key(project, config, check, changed_files, runtime_identity)
        timeout_seconds = _check_timeout_seconds(config, check)
    except ValueError as error:
        return CheckResult(
            index,
            check,
            1,
            stderr=f"{error}\n",
            duration_seconds=time.monotonic() - started_at,
        )

    command = check.get("command")
    if not command:
        return CheckResult(
            index,
            check,
            1,
            stderr=f"missing_command: {check.get('id')}\n",
            duration_seconds=time.monotonic() - started_at,
            cache_key=key,
        )
    dependency_error = _dependency_error(check)
    if dependency_error is not None:
        return CheckResult(
            index,
            check,
            1,
            stderr=dependency_error,
            duration_seconds=time.monotonic() - started_at,
            cache_key=key,
        )
    workers = _pytest_xdist_workers(check.get("pytestXdistWorkers"))
    command = _command_with_pytest_xdist_workers(command, workers)
    use_shell = isinstance(command, str)
    run_kwargs = {
        "cwd": project,
        "check": False,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "capture_output": True,
        "shell": use_shell,
    }
    env = _pytest_xdist_env(workers)
    if env is not None:
        run_kwargs["env"] = env
    if timeout_seconds is not None:
        run_kwargs["timeout"] = timeout_seconds
    try:
        if control is not None and runner is subprocess.run:
            result = _managed_run(command, control, **run_kwargs)
        else:
            if control is not None and control.deadline is not None:
                remaining = control.deadline - time.monotonic()
                if remaining <= 0:
                    raise TotalBudgetTimeout(command, 0)
                run_kwargs["timeout"] = min(timeout_seconds, remaining)
            result = runner(command, **run_kwargs)
            if control is not None and control.expired():
                raise TotalBudgetTimeout(command, timeout_seconds)
    except FileNotFoundError:
        executable = command[0] if isinstance(command, list) else str(command)
        return CheckResult(
            index,
            check,
            1,
            stderr=f"command_not_found: {check.get('id')}: {executable}\n",
            duration_seconds=time.monotonic() - started_at,
            cache_key=key,
        )
    except subprocess.TimeoutExpired as error:
        total_timeout = isinstance(error, TotalBudgetTimeout) or (control is not None and control.expired())
        return CheckResult(
            index,
            check,
            1,
            stderr=(f"{'total_budget_timeout' if total_timeout else 'check_timeout'}: {check.get('id')}\n"
                    if control is not None else
                    f"check_timeout: {check.get('id')} exceeded {_format_seconds(timeout_seconds or 0)}s\n"),
            duration_seconds=time.monotonic() - started_at,
            cache_key=key,
            status="timed_out",
            reason="total_budget_timeout" if total_timeout else "check_timeout",
        )
    except Exception as error:
        return CheckResult(
            index,
            check,
            1,
            stderr=(
                f"parallel_check_exception: {check.get('id')}: "
                f"{type(error).__name__}: {error}\n"
            ),
            duration_seconds=time.monotonic() - started_at,
            cache_key=key,
        )
    return CheckResult(
        index,
        check,
        int(result.returncode),
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        duration_seconds=time.monotonic() - started_at,
        cache_key=key,
    )


def _checks(config: dict[str, Any], section: str) -> list[dict[str, Any]]:
    return list(config.get(section, {}).get("checks", []))


def _max_parallel_checks(config: dict[str, Any], parallel_count: int) -> int:
    verify_config = config.get("verify")
    configured = verify_config.get("maxParallel") if isinstance(verify_config, dict) else None
    if isinstance(configured, bool):
        return parallel_count
    if configured == 0:
        return parallel_count
    if isinstance(configured, int) and configured > 0:
        return min(parallel_count, configured)
    return min(parallel_count, os.cpu_count() or 1)


def _check_ids(checks: list[dict[str, Any]]) -> str:
    return ", ".join(str(check.get("id")) for check in checks)


def _config_error(error: ConfigError) -> int:
    print(str(error), file=sys.stderr)
    print("status: failed")
    return 1


def _verify_error(message: str) -> int:
    print(message, file=sys.stderr)
    print("status: failed")
    return 1


def _run_scheduled_checks(
    project: Path,
    config: dict[str, Any],
    selected: list[dict[str, Any]],
    changed_files: list[str],
    runner: Runner,
    runtime_identity: str,
) -> tuple[int, list[str], list[CheckResult]]:
    indexed_selected = list(enumerate(selected))
    parallel_checks = [(index, check) for index, check in indexed_selected if check.get("checkParallel") is True]
    serial_checks = [(index, check) for index, check in indexed_selected if check.get("checkParallel") is not True]
    results: list[CheckResult] = []
    if parallel_checks:
        max_workers = _max_parallel_checks(config, len(parallel_checks))
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        interrupted = False
        try:
            futures = {
                executor.submit(
                    _run_check_result,
                    index,
                    project,
                    check,
                    config,
                    changed_files,
                    runner,
                    runtime_identity,
                ): (index, check)
                for index, check in parallel_checks
            }
            for future in futures:
                index, check = futures[future]
                try:
                    results.append(future.result())
                except KeyboardInterrupt as error:
                    interrupted = True
                    results.append(
                        CheckResult(
                            index,
                            check,
                            1,
                            stderr=(
                                f"parallel_check_interrupted: {check.get('id')}: "
                                f"KeyboardInterrupt: {error}\n"
                            ),
                        )
                    )
                    break
        finally:
            executor.shutdown(wait=not interrupted, cancel_futures=interrupted)
        if not interrupted:
            results.extend(
                _run_check_result(
                    index,
                    project,
                    check,
                    config,
                    changed_files,
                    runner,
                    runtime_identity,
                )
                for index, check in serial_checks
            )
    else:
        results.extend(
            _run_check_result(
                index,
                project,
                check,
                config,
                changed_files,
                runner,
                runtime_identity,
            )
            for index, check in serial_checks
        )

    failures = 0
    failed_ids: list[str] = []
    ordered_results = sorted(results, key=lambda item: item.index)
    for result in ordered_results:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        print(f"duration: {result.check.get('id')} seconds={result.duration_seconds:.2f}")
        if result.returncode == 0:
            if result.cache_key is not None:
                _cache_store(project, result.cache_key, result.check)
        else:
            failures += 1
            failed_ids.append(str(result.check.get("id")))
    return failures, failed_ids, ordered_results


def _write_performance_report(path: Path, payload: dict[str, Any]) -> bool:
    temp = path.with_name(".performance-report.json.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
    except OSError:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def run_build(project: Path, runner: Runner = subprocess.run, *, pr: bool = False) -> int:
    try:
        config = _load_config(project)
    except ConfigError as error:
        return _config_error(error)
    configured = _checks(config, "build")
    checks = [check for check in configured if not pr or check.get("pr", True)]
    print(f"scene: {'pr' if pr else 'local'}")
    if pr:
        print(f"excluded-by-pr: {_check_ids([check for check in configured if check.get('pr') is False])}")
    if pr and not checks:
        print("checked: ")
        print("status: skipped")
        print("reason: no_matching_checks")
        return 0
    failures = 0
    for check in checks:
        try:
            _validate_check_inputs(project, check)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            failures += 1
            continue
        if _run_check(project, check, runner) != 0:
            failures += 1
    print(f"checked: {_check_ids(checks)}")
    if failures:
        print("status: failed")
        return 1
    print("status: passed")
    return 0


def run_verify(
    project: Path, runner: Runner = subprocess.run, *, pr: bool = False,
    full: bool = False, baseline: str | None = None, performance_report: bool = False,
    runtime_version: str = "unknown", synthetic_changed_paths: list[str] | None = None,
    implementation_identity: str | None = None, execution_context: str | None = None,
    diagnostic: bool = False, started_at: float | None = None,
    invocation_control: RunControl | None = None,
) -> int:
    context = execution_context or os.environ.get("BUILD_AND_VERIFY_EXECUTION_CONTEXT", "unknown")
    if context not in {"local", "cloud", "ci", "unknown"}:
        return _verify_error("invalid_execution_context")
    # CODEX_CI describes the host shell and also occurs on desktop machines.
    if pr or os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI", "").lower() == "true":
        context = "ci"
    try:
        config = _load_config(project)
    except ConfigError as error:
        return _config_error(error)
    verify = config.get("verify", {})
    enforce = verify.get("enforceLocalBudget", True)
    if not isinstance(enforce, bool):
        return _verify_error("verify.enforceLocalBudget must be boolean")
    budget = verify.get("fullBudgetSeconds")
    if context == "unknown":
        print("execution-context-warning: unknown; declare --execution-context or BUILD_AND_VERIFY_EXECUTION_CONTEXT", flush=True)
        if budget is not None and enforce and not diagnostic:
            return _verify_error("execution_context_required_for_local_budget")
    if context != "local" and not diagnostic:
        return _run_verify_legacy(project, runner, pr=pr, full=full, baseline=baseline,
            performance_report=performance_report, runtime_version=runtime_version,
            synthetic_changed_paths=synthetic_changed_paths, implementation_identity=implementation_identity)
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0):
        return _verify_error("verify.fullBudgetSeconds must be positive integer")
    if not _is_non_empty_string(runtime_version) or runtime_version == "unknown":
        return _verify_error("missing_runtime_version")
    identity = runtime_version if implementation_identity is None else implementation_identity
    if not _is_non_empty_string(identity) or identity == "unknown":
        return _verify_error("missing_implementation_identity")
    if baseline is not None and full:
        return _verify_error("baseline_not_allowed_with_full")
    started = time.monotonic() if started_at is None else started_at
    deadline = started + budget if context == "local" and enforce and budget is not None and not diagnostic else None
    control = invocation_control or RunControl(deadline)
    control.runtime_version = runtime_version
    if baseline is not None:
        changed, error = _baseline_changed_files(project, baseline)
        if error is not None:
            return _verify_error(error)
    else:
        changed = _dedupe(synthetic_changed_paths) if synthetic_changed_paths is not None else _changed_files(project)
    configured = _checks(config, "verify")
    checks = [check for check in configured if not pr or check.get("pr", True)]
    config_changed = ".build-and-verify/config.json" in changed
    selected = checks if full or config_changed else _selected_checks(checks, changed)
    control.selected = selected
    print(f"scene: {'pr' if pr else 'local'}", flush=True)
    print(f"execution-context: {context}", flush=True)
    if diagnostic:
        print("diagnostic: true; formal-budget-acceptance: false", flush=True)
    if pr:
        print(f"excluded-by-pr: {_check_ids([check for check in configured if check.get('pr') is False])}")
    if config_changed and not full:
        print("selection-reason: config-changed")
    results: list[CheckResult] = []
    pending: list[tuple[int, dict[str, Any]]] = []
    for index, check in enumerate(selected):
        if control.expired():
            results.append(CheckResult(index, check, 1, status="not_started", reason="total_budget_timeout"))
            continue
        try:
            key = _cache_key(project, config, check, changed, identity)
        except ValueError as error:
            results.append(CheckResult(index, check, 1, stderr=f"{error}\n", status="failed"))
            continue
        if control.expired():
            results.append(CheckResult(index, check, 1, status="not_started", reason="total_budget_timeout"))
            continue
        if not full and not diagnostic and _cache_load(project, key):
            print(f"cache-hit: {check['id']}", flush=True)
            results.append(CheckResult(index, check, 0, status="cached"))
        else:
            pending.append((index, check))

    def execute(item: tuple[int, dict[str, Any]]) -> CheckResult:
        index, check = item
        if control.expired():
            return CheckResult(index, check, 1, status="not_started", reason="total_budget_timeout")
        print(f"check-start: {check['id']}", flush=True)
        control.active_checks.add(check['id'])
        result = _run_check_result(index, project, check, config, changed, runner, identity, control)
        result.status = result.status or ("passed" if result.returncode == 0 else "failed")
        control.results[check['id']] = result
        control.active_checks.discard(check['id'])
        print(f"check-end: {check['id']} status={result.status} seconds={result.duration_seconds:.2f}", flush=True)
        if result.returncode == 0 and result.cache_key is not None and not diagnostic:
            _cache_store(project, result.cache_key, result.check)
        return result

    control.results.update({result.check['id']: result for result in results})

    parallel = [item for item in pending if item[1].get("checkParallel") is True]
    serial = [item for item in pending if item[1].get("checkParallel") is not True]
    try:
        if parallel:
            with concurrent.futures.ThreadPoolExecutor(max_workers=_max_parallel_checks(config, len(parallel))) as executor:
                try:
                    results.extend(executor.map(execute, parallel))
                except BaseException:
                    control.cancelled.set()
                    raise
        for item in serial:
            results.append(execute(item))
    except KeyboardInterrupt:
        control.cancelled.set()
        return _verify_error("verification_interrupted")
    results.sort(key=lambda result: result.index)
    total = round(time.monotonic() - started, 2)
    timed_out = control.expired()
    failures = any(result.returncode != 0 for result in results) or timed_out
    over = total > budget if budget is not None else None
    for result in results:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        print(f"duration: {result.check['id']} seconds={result.duration_seconds:.2f}")
    unfinished = [result.check['id'] for result in results if result.status == "timed_out"]
    unstarted = [result.check['id'] for result in results if result.status == "not_started"]
    if timed_out:
        print(f"total_budget_timeout: totalSeconds={total:.2f} budgetSeconds={budget}", flush=True)
        print(f"unfinished: {', '.join(unfinished)}")
        print(f"not-started: {', '.join(unstarted)}")
    elif over:
        print(f"performance-warning: totalSeconds={total:.2f} budgetSeconds={budget} exceededSeconds={total-budget:.2f}")
    if performance_report or over or timed_out or diagnostic:
        report_path = project / ".build-and-verify" / "runs" / "performance-report.json"
        payload = {"schemaVersion": 1, "runtimeVersion": runtime_version,
            "generatedAt": datetime.now(timezone.utc).isoformat(), "totalSeconds": total,
            "budgetSeconds": budget, "overBudget": over,
            "verificationStatus": "failed" if failures else ("diagnostic" if diagnostic else "passed"),
            "executionContext": context, "diagnostic": diagnostic,
            "reason": "total_budget_timeout" if timed_out else None,
            "unfinished": unfinished, "notStarted": unstarted,
            "checks": [{"id": result.check['id'], "status": result.status,
                        "reason": result.reason, "durationSeconds": round(result.duration_seconds, 2)} for result in results]}
        if _write_performance_report(report_path, payload):
            print("performance-report: .build-and-verify/runs/performance-report.json")
        else:
            print("performance-report-warning: .build-and-verify/runs/performance-report.json", file=sys.stderr)
    print(f"checked: {_check_ids([result.check for result in results if result.status != 'not_started'])}")
    print(f"full-not-run: {str(not full).lower()}")
    if failures:
        print(f"failed: {_check_ids([result.check for result in results if result.returncode != 0])}")
        return _verify_error("verification_failed")
    if not selected:
        print("status: skipped")
        print(f"reason: {'no_changed_files' if not changed and not full else 'no_matching_checks'}")
    else:
        print(f"status: {'diagnostic' if diagnostic else 'passed'}")
    return 0


def _run_verify_legacy(
    project: Path,
    runner: Runner = subprocess.run,
    *,
    pr: bool = False,
    full: bool = False,
    baseline: str | None = None,
    performance_report: bool = False,
    runtime_version: str = "unknown",
    synthetic_changed_paths: list[str] | None = None,
    implementation_identity: str | None = None,
) -> int:
    if not _is_non_empty_string(runtime_version) or runtime_version == "unknown":
        print("missing_runtime_version", file=sys.stderr)
        print("status: failed")
        return 1
    runtime_identity = runtime_version if implementation_identity is None else implementation_identity
    if not _is_non_empty_string(runtime_identity) or runtime_identity == "unknown":
        print("missing_implementation_identity", file=sys.stderr)
        print("status: failed")
        return 1
    if baseline is not None and full:
        return _verify_error("baseline_not_allowed_with_full")
    if baseline is not None:
        changed_files, baseline_error = _baseline_changed_files(project, baseline)
        if baseline_error is not None:
            return _verify_error(baseline_error)
        assert changed_files is not None
    else:
        changed_files = (
            _dedupe(synthetic_changed_paths)
            if synthetic_changed_paths is not None
            else _changed_files(project)
        )
    try:
        config = _load_config(project)
    except ConfigError as error:
        return _config_error(error)
    configured = _checks(config, "verify")
    checks = [check for check in configured if not pr or check.get("pr", True)]
    print(f"scene: {'pr' if pr else 'local'}")
    if pr:
        print(f"excluded-by-pr: {_check_ids([check for check in configured if check.get('pr') is False])}")
    config_changed = ".build-and-verify/config.json" in changed_files
    selected = checks if full or config_changed else _selected_checks(checks, changed_files)
    if full:
        verify_config = config.get("verify", {})
        budget_seconds = verify_config.get("fullBudgetSeconds")
        if budget_seconds is not None and (
            isinstance(budget_seconds, bool)
            or not isinstance(budget_seconds, int)
            or budget_seconds <= 0
        ):
            return _config_error(
                ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    "verify.fullBudgetSeconds must be positive integer"
                )
            )
    if pr and not selected:
        if config_changed and not full:
            print("selection-reason: config-changed")
        print("checked: ")
        print(f"full-not-run: {str(not full).lower()}")
        print("status: skipped")
        print(f"reason: {'no_changed_files' if not changed_files and not full else 'no_matching_checks'}")
        return 0
    if config_changed and not full:
        print("selection-reason: config-changed")
    failures = 0
    if full:
        started_at = time.monotonic()
        failures, failed_ids, results = _run_scheduled_checks(
            project,
            config,
            selected,
            changed_files,
            runner,
            runtime_identity,
        )
        total_seconds = round(time.monotonic() - started_at, 2)
        if len(results) == len(selected):
            over_budget = (
                total_seconds > budget_seconds if budget_seconds is not None else None
            )
            report_path = (
                project / ".build-and-verify" / "runs" / "performance-report.json"
            )
            report_relative_path = report_path.relative_to(project).as_posix()
            if performance_report or over_budget is True:
                payload = {
                    "schemaVersion": 1,
                    "runtimeVersion": runtime_version,
                    "generatedAt": datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "totalSeconds": total_seconds,
                    "budgetSeconds": budget_seconds,
                    "overBudget": over_budget,
                    "verificationStatus": "failed" if failures else "passed",
                    "checks": [
                        {
                            "id": str(result.check.get("id")),
                            "status": "passed" if result.returncode == 0 else "failed",
                            "durationSeconds": round(result.duration_seconds, 2),
                        }
                        for result in results
                    ],
                }
                if _write_performance_report(report_path, payload):
                    print(f"performance-report: {report_relative_path}")
                else:
                    print(
                        f"performance-report-warning: {report_relative_path}",
                        file=sys.stderr,
                    )
            if over_budget is True:
                exceeded_seconds = total_seconds - budget_seconds
                exceeded_percent = exceeded_seconds / budget_seconds * 100
                print(
                    "performance-warning: "
                    f"totalSeconds={total_seconds:.2f} "
                    f"budgetSeconds={budget_seconds} "
                    f"exceededSeconds={exceeded_seconds:.2f} "
                    f"exceededPercent={exceeded_percent:.2f} "
                    f"report={report_relative_path}"
                )
        if failed_ids:
            print(f"failed: {', '.join(failed_ids)}")
        print(f"checked: {_check_ids(selected)}")
        print(f"full-not-run: {str(not full).lower()}")
        if failures:
            print("status: failed")
            return 1
        print("status: passed")
        return 0
    if not selected:
        reason = "no_changed_files" if not changed_files else "no_matching_checks"
        print(f"checked: {_check_ids(selected)}")
        print(f"full-not-run: {str(not full).lower()}")
        print("status: skipped")
        print(f"reason: {reason}")
        return 0
    cache_misses: list[dict[str, Any]] = []
    for check in selected:
        try:
            key = _cache_key(project, config, check, changed_files, runtime_identity)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            failures += 1
            continue
        if _cache_load(project, key):
            print(f"cache-hit: {check.get('id')}")
            continue
        cache_misses.append(check)
    scheduled_failures, failed_ids, _ = _run_scheduled_checks(
        project,
        config,
        cache_misses,
        changed_files,
        runner,
        runtime_identity,
    )
    failures += scheduled_failures
    if failed_ids:
        print(f"failed: {', '.join(failed_ids)}")
    print(f"checked: {_check_ids(selected)}")
    print(f"full-not-run: {str(not full).lower()}")
    if failures:
        print("status: failed")
        return 1
    print("status: passed")
    return 0
