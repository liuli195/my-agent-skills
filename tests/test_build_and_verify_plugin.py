import contextlib
import importlib.util
import io
import json
import re
import shutil
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "build-and-verify"
CODEX_REPO_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
RELEASE_FLOW_PROJECTION = REPO_ROOT / ".release-flow" / "projection.yaml"
RELEASE_FLOW_CONFIG = REPO_ROOT / ".release-flow" / "config.yaml"
RELEASE_FLOW_SCRIPT = REPO_ROOT / "plugins" / "release-flow" / "skills" / "release-flow" / "scripts" / "release_flow.py"
BUILD_AND_VERIFY_SCRIPT = (
    PLUGIN_ROOT / "skills" / "build-and-verify" / "scripts" / "build_and_verify.py"
)
_BUILD_AND_VERIFY_MODULE = None

PLUGIN_NAME = "build-and-verify"
INIT_SKILL_NAME = "build-and-verify-init"
INIT_SKILL_ROOT = PLUGIN_ROOT / "skills" / INIT_SKILL_NAME
INIT_REFERENCE_ROOT = INIT_SKILL_ROOT / "references"
REQUIRED_INIT_REFERENCES = {
    "questionnaire.md",
    "ecosystem-detection.md",
    "config-draft.md",
    "validation.md",
}
PLUGIN_DESCRIPTION = "Repository Build and Verify Entry Point（本仓库构建检查与验证入口）"
DEFAULT_BUILD_AND_VERIFY_GITIGNORE = ["/cache/", "/runs/", "/backups/"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_runner_config(
    project: Path,
    *,
    build_checks: list[dict[str, Any]] | None = None,
    verify_checks: list[dict[str, Any]] | None = None,
    verify_config: dict[str, Any] | None = None,
) -> None:
    config = {
        "version": 1,
        "build": {"checks": build_checks or []},
        "verify": {"checks": verify_checks or []},
    }
    if verify_config:
        config["verify"].update(verify_config)
    build_dir = project / ".build-and-verify"
    build_dir.mkdir(parents=True, exist_ok=True)
    write_json(build_dir / "config.json", config)
    (build_dir / "cache").mkdir(parents=True, exist_ok=True)


def completed(
    command: Any,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[Any]:
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


_LOG_COMMANDS: dict[tuple[Any, ...], tuple[str, str]] = {}
_FAIL_ONCE_COMMANDS: dict[tuple[Any, ...], dict[str, Any]] = {}


def command_key(command: Any) -> tuple[Any, ...] | None:
    if isinstance(command, list):
        return tuple(command)
    return None


def simulate_registered_command(
    command: Any, cwd: Path | str | None
) -> subprocess.CompletedProcess[Any] | None:
    key = command_key(command)
    if key is None:
        return None
    project = Path(cwd or ".")
    if key in _LOG_COMMANDS:
        label, log_name = _LOG_COMMANDS[key]
        log_path = project / log_name
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as file:
            file.write(label + "\n")
        return completed(command)
    if key in _FAIL_ONCE_COMMANDS:
        state = _FAIL_ONCE_COMMANDS[key]
        log_path = project / "run.log"
        with log_path.open("a", encoding="utf-8") as file:
            file.write(str(state["label"]) + "\n")
        if not state["failed"]:
            state["failed"] = True
            return completed(command, 7)
        return completed(command)
    return None


class FakeRunner:
    def __init__(
        self,
        outcomes: dict[Any, subprocess.CompletedProcess[Any]] | None = None,
    ) -> None:
        self.calls: list[Any] = []
        self.outcomes = outcomes or {}

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        key = tuple(command) if isinstance(command, list) else command
        outcome = self.outcomes.get(key)
        if outcome is None:
            outcome = simulate_registered_command(command, kwargs.get("cwd"))
        if outcome is None:
            outcome = completed(command)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def run_build_and_verify(*args: str) -> subprocess.CompletedProcess[str]:
    return call_build_and_verify_main(*args)


def run_build_and_verify_subprocess(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUILD_AND_VERIFY_SCRIPT), *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def load_build_and_verify_module():
    global _BUILD_AND_VERIFY_MODULE
    if _BUILD_AND_VERIFY_MODULE is not None:
        return _BUILD_AND_VERIFY_MODULE
    spec = importlib.util.spec_from_file_location(
        "build_and_verify_entrypoint", BUILD_AND_VERIFY_SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _BUILD_AND_VERIFY_MODULE = module
    return module


def load_build_and_verify_runner_module():
    return load_build_and_verify_module()._runner()


class FakeRunnerModule:
    def __init__(
        self,
        runner_module,
        runner: Callable[..., subprocess.CompletedProcess[Any]],
        changed_files: list[str] | None,
    ) -> None:
        self.runner_module = runner_module
        self.runner = runner
        self.changed_files = changed_files

    def __getattr__(self, name: str):
        return getattr(self.runner_module, name)

    def run_build(self, project: Path) -> int:
        return int(self.runner_module.run_build(project, runner=self.runner))

    def run_verify(self, project: Path, *, full: bool = False) -> int:
        if self.changed_files is None:
            return int(self.runner_module.run_verify(project, runner=self.runner, full=full))
        original_changed_files = self.runner_module._changed_files
        self.runner_module._changed_files = lambda _project: list(self.changed_files)
        try:
            return int(self.runner_module.run_verify(project, runner=self.runner, full=full))
        finally:
            self.runner_module._changed_files = original_changed_files


def run_check(
    project: Path,
    *args: str,
    runner: Callable[..., subprocess.CompletedProcess[Any]] | None = None,
    changed_files: list[str] | None = None,
    check_user_runtime: bool = False,
) -> subprocess.CompletedProcess[str]:
    module = load_build_and_verify_module()
    original_runner_module = module._RUNNER_MODULE
    original_print_runtime_update_hint = module._print_runtime_update_hint
    runner = runner or FakeRunner()
    module._RUNNER_MODULE = FakeRunnerModule(module._runner(), runner, changed_files)
    if not check_user_runtime:
        module._print_runtime_update_hint = lambda _project: None
    argv = [*args, "--project", str(project)]
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            returncode = int(module.main(argv))
    finally:
        module._RUNNER_MODULE = original_runner_module
        module._print_runtime_update_hint = original_print_runtime_update_hint
    return subprocess.CompletedProcess(
        args=[str(BUILD_AND_VERIFY_SCRIPT), *argv],
        returncode=returncode,
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
    )


def call_build_and_verify_main(*args: str) -> subprocess.CompletedProcess[str]:
    module = load_build_and_verify_module()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            returncode = int(module.main(list(args)))
        except SystemExit as error:
            returncode = error.code if isinstance(error.code, int) else 1
    return subprocess.CompletedProcess(
        args=[str(BUILD_AND_VERIFY_SCRIPT), *args],
        returncode=returncode,
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
    )


def load_release_flow_module():
    spec = importlib.util.spec_from_file_location(
        "release_flow_entrypoint", RELEASE_FLOW_SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def call_release_flow_main(
    *args: str, cwd: Path = REPO_ROOT
) -> subprocess.CompletedProcess[str]:
    module = load_release_flow_module()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.chdir(cwd):
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            returncode = int(module.main(list(args)))
    return subprocess.CompletedProcess(
        args=[str(RELEASE_FLOW_SCRIPT), *args],
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
    command = [sys.executable, "-c", code]
    _LOG_COMMANDS[tuple(command)] = (label, log_name)
    return command


def init_wizard_command_tokens(command: Any) -> list[str]:
    if isinstance(command, str):
        try:
            return shlex.split(command)
        except ValueError:
            return command.split()
    if isinstance(command, list):
        return [str(token) for token in command]
    return []


def init_wizard_command_name(command: Any) -> str:
    tokens = init_wizard_command_tokens(command)
    if not tokens:
        return ""
    return tokens[0].strip('"')


def init_wizard_uses_pytest_parallel(command: Any) -> bool:
    return load_build_and_verify_runner_module().uses_pytest_xdist(command)


def init_wizard_node_package_manager_resolution(
    project: Path,
    *,
    selected: str | None = None,
) -> dict[str, Any]:
    lockfiles = [
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("package-lock.json", "npm"),
    ]
    found = [manager for lockfile, manager in lockfiles if (project / lockfile).exists()]
    if len(found) > 1 and selected is None:
        return {
            "requires_user_choice": True,
            "lockfiles": found,
            "package_manager": None,
            "commands": [],
        }
    package_manager = selected or (found[0] if found else "npm")
    package_json = read_json(project / "package.json")
    scripts = package_json.get("scripts", {})
    commands = []
    for script in scripts:
        if package_manager == "npm":
            commands.append(f"npm run {script}")
        else:
            commands.append(f"{package_manager} {script}")
    return {
        "requires_user_choice": False,
        "lockfiles": found,
        "package_manager": package_manager,
        "commands": commands,
    }


def init_wizard_ensure_unique_check_ids(
    candidates: list[dict[str, str]],
) -> dict[str, Any]:
    seen_by_section: dict[str, set[str]] = {}
    rename_reasons: list[str] = []
    unique_candidates: list[dict[str, str]] = []
    for candidate in candidates:
        section = candidate["section"]
        original_id = candidate["id"]
        seen = seen_by_section.setdefault(section, set())
        check_id = original_id
        suffix = 2
        while check_id in seen:
            check_id = f"{original_id}-{suffix}"
            suffix += 1
        if check_id != original_id:
            rename_reasons.append(
                f"{original_id} -> {check_id}: 同一分组内 check id（检查项标识）冲突"
            )
        seen.add(check_id)
        unique_candidates.append({**candidate, "id": check_id})
    return {"candidates": unique_candidates, "rename_reasons": rename_reasons}


def init_wizard_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def init_wizard_path_exists(project: Path, pattern: str) -> bool:
    if re.search(r"[*?\[]", pattern):
        return any(project.glob(pattern))
    return (project / pattern).exists()


def init_wizard_issue(problem: str, impact: str, suggestion: str) -> dict[str, str]:
    return {
        "问题": problem,
        "影响": impact,
        "建议": suggestion,
        "是否阻止写入": "不阻止",
    }


def init_wizard_iter_checks(config: dict[str, Any]):
    for section in ("build", "verify"):
        checks = config.get(section, {}).get("checks", [])
        for check in checks:
            yield section, check


def init_wizard_targeted_dependency_issues(
    project: Path,
    config: dict[str, Any],
    *,
    executable_resolver: Callable[[str], str | None] = shutil.which,
    xdist_available: bool = True,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for section, check in init_wizard_iter_checks(config):
        check_id = check.get("id", "<missing-id>")
        command = check.get("command")
        command_tokens = init_wizard_command_tokens(command)
        workers = check.get("pytestXdistWorkers")
        command_needs_xdist = init_wizard_uses_pytest_parallel(command) or (
            workers is not None and "pytest" in command_tokens
        )
        if command_needs_xdist and not xdist_available:
            issues.append(
                init_wizard_issue(
                    f"{check_id} 需要 pytest-xdist（Pytest 并行插件），但当前环境不可用",
                    "该 check（检查项）后续 verify（验证）可能失败。",
                    "请安装 pytest-xdist（Pytest 并行插件），或移除 `pytestXdistWorkers`（Pytest 工作进程数）后再运行。",
                )
            )

        command_name = init_wizard_command_name(command)
        if command_name and executable_resolver(command_name) is None:
            issues.append(
                init_wizard_issue(
                    f"{check_id} 调用的可执行入口 `{command_name}` 不可找到",
                    f"{section}（检查分组）运行到该命令时会失败。",
                    "确认该工具已安装并在 PATH（命令搜索路径）中，或修改 command（命令）。",
                )
            )

        for field in ("paths", "inputs"):
            for pattern in check.get(field, []) or []:
                if not init_wizard_path_exists(project, pattern):
                    issues.append(
                        init_wizard_issue(
                            f"{check_id} 的 {field}（路径清单）指向缺失文件或目录：`{pattern}`",
                            "快速验证选择或 cache key（缓存键）可能不符合预期。",
                            "确认路径是否应保留；如果是未来才会出现的路径，可继续写入配置。",
                        )
                    )
    return issues


def assert_init_wizard_config_structure(config: dict[str, Any]) -> None:
    assert isinstance(config, dict)
    for section in ("build", "verify"):
        section_config = config.get(section)
        assert isinstance(section_config, dict)
        checks = section_config.get("checks")
        assert isinstance(checks, list)
        seen_ids: set[str] = set()
        for check in checks:
            assert isinstance(check, dict)
            check_id = check.get("id")
            assert init_wizard_non_empty_string(check_id)
            assert check_id not in seen_ids
            seen_ids.add(check_id)
            command = check.get("command")
            assert init_wizard_non_empty_string(command) or (
                isinstance(command, list)
                and bool(command)
                and all(init_wizard_non_empty_string(token) for token in command)
            )
            for field in ("paths", "inputs"):
                value = check.get(field)
                assert value is None or (
                    isinstance(value, list)
                    and all(init_wizard_non_empty_string(item) for item in value)
                )
            assert "parallel" not in check
            check_parallel = check.get("checkParallel")
            assert check_parallel is None or isinstance(check_parallel, bool)
            workers = check.get("pytestXdistWorkers")
            assert workers is None or workers == "auto" or (
                not isinstance(workers, bool) and isinstance(workers, int) and workers > 0
            )
            check_timeout_seconds = check.get("timeoutSeconds")
            assert check_timeout_seconds is None or (
                not isinstance(check_timeout_seconds, bool)
                and isinstance(check_timeout_seconds, (int, float))
                and check_timeout_seconds > 0
            )

    verify_config = config.get("verify", {})
    max_parallel = verify_config.get("maxParallel")
    assert max_parallel is None or (
        not isinstance(max_parallel, bool)
        and isinstance(max_parallel, int)
        and max_parallel >= 0
    )
    timeout_seconds = verify_config.get("timeoutSeconds")
    assert timeout_seconds is None or (
        not isinstance(timeout_seconds, bool)
        and isinstance(timeout_seconds, (int, float))
        and timeout_seconds > 0
    )


def ensure_init_wizard_gitignore(build_dir: Path) -> None:
    gitignore = build_dir / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    for entry in DEFAULT_BUILD_AND_VERIFY_GITIGNORE:
        if entry not in lines:
            lines.append(entry)
    gitignore.write_text("\n".join(lines) + "\n", encoding="utf-8")


def init_wizard_can_create_directory(directory: Path, boundary: Path) -> bool:
    created: list[Path] = []
    current = directory
    while not current.exists() and current != boundary and current != current.parent:
        created.append(current)
        current = current.parent
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    finally:
        for path in created:
            with contextlib.suppress(OSError):
                path.rmdir()
    return True


def init_wizard_can_write_directory(directory: Path) -> bool:
    probe = directory / ".init-write-check"
    try:
        probe.write_text("ok\n", encoding="utf-8")
    except OSError:
        return False
    finally:
        with contextlib.suppress(OSError):
            probe.unlink()
    return True


def init_wizard_environment_issues(
    project: Path,
    *,
    overwrite: bool,
    backup_path: Path | None,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    build_dir = project / ".build-and-verify"

    if not project.exists():
        issues.append(
            init_wizard_issue(
                f"目标仓库路径不存在：`{project}`",
                "初始化写入会创建缺失目录；请确认目标路径是否正确。",
                "确认目标仓库路径；如果需要准备环境，可以让 agent（代理）在授权后协助处理。",
            )
        )
    elif not project.is_dir():
        issues.append(
            init_wizard_issue(
                f"目标仓库路径不是目录：`{project}`",
                "无法在该路径下写入 .build-and-verify（配置目录）。",
                "选择一个目录作为目标仓库路径，或在授权后让 agent（代理）协助处理。",
            )
        )
    elif build_dir.exists() and not build_dir.is_dir():
        issues.append(
            init_wizard_issue(
                f"配置目录路径不是目录：`{build_dir}`",
                "无法写入 .build-and-verify/config.json（配置文件）。",
                "移动或删除同名文件；如果需要处理本地文件，可以让 agent（代理）在授权后协助处理。",
            )
        )
    elif build_dir.exists() and not init_wizard_can_write_directory(build_dir):
        issues.append(
            init_wizard_issue(
                f"配置目录不可写入：`{build_dir}`",
                "无法可靠写入 .build-and-verify/config.json（配置文件）。",
                "修复目录权限；如果需要准备环境，可以让 agent（代理）在授权后协助处理。",
            )
        )
    elif not build_dir.exists() and not init_wizard_can_create_directory(build_dir, project):
        issues.append(
            init_wizard_issue(
                f"配置目录不可创建：`{build_dir}`",
                "无法创建 .build-and-verify（配置目录）。",
                "修复目标仓库目录权限；如果需要准备环境，可以让 agent（代理）在授权后协助处理。",
            )
        )

    if overwrite:
        candidate = (
            project / ".build-and-verify" / "backups"
            if backup_path is None
            else (backup_path if backup_path.is_absolute() else project / backup_path).parent
        )
        backup_inside_project = True
        try:
            candidate.resolve().relative_to(project.resolve())
        except ValueError:
            backup_inside_project = False
            issues.append(
                init_wizard_issue(
                    f"备份目录不在目标仓库内：`{candidate}`",
                    "覆盖已有配置时可能把备份写到仓库外部。",
                    "选择目标仓库内的备份目录，或使用默认 backups（备份）目录。",
                )
            )
        if backup_inside_project and candidate.exists() and not candidate.is_dir():
            issues.append(
                init_wizard_issue(
                    f"备份目录路径不是目录：`{candidate}`",
                    "覆盖已有配置时无法创建备份文件。",
                    "移动或删除同名文件；如果需要处理本地文件，可以让 agent（代理）在授权后协助处理。",
                )
            )
        elif backup_inside_project and project.exists() and project.is_dir():
            if candidate.exists() and not init_wizard_can_write_directory(candidate):
                issues.append(
                    init_wizard_issue(
                        f"备份目录不可写入：`{candidate}`",
                        "覆盖已有配置时无法可靠创建备份文件。",
                        "修复备份目录权限，或选择其他仓库内备份目录。",
                    )
                )
            elif not candidate.exists() and not init_wizard_can_create_directory(candidate, project):
                issues.append(
                    init_wizard_issue(
                        f"备份目录不可创建：`{candidate}`",
                        "覆盖已有配置时无法创建备份目录。",
                        "修复目标仓库目录权限，或使用其他仓库内备份目录。",
                    )
                )

    return issues


def init_wizard_backup_path(project: Path, backup_path: Path | None, timestamp: str) -> Path:
    if backup_path is None:
        return project / ".build-and-verify" / "backups" / f"config-{timestamp}.json"
    candidate = backup_path if backup_path.is_absolute() else project / backup_path
    try:
        candidate.resolve().relative_to(project.resolve())
    except ValueError as error:
        raise AssertionError("backup_path must stay inside target repository") from error
    assert not candidate.exists(), "backup_path must not overwrite existing file"
    return candidate


def simulate_init_wizard_write(
    project: Path,
    config: dict[str, Any],
    *,
    overwrite: bool,
    backup_path: Path | None = None,
    timestamp: str = "20260626-120000",
    executable_resolver: Callable[[str], str | None] = shutil.which,
    xdist_available: bool = True,
) -> dict[str, Any]:
    requested_backup_path = backup_path
    dependency_issues = init_wizard_targeted_dependency_issues(
        project,
        config,
        executable_resolver=executable_resolver,
        xdist_available=xdist_available,
    )
    environment_issues = init_wizard_environment_issues(
        project,
        overwrite=overwrite,
        backup_path=requested_backup_path,
    )
    build_dir = project / ".build-and-verify"
    config_path = build_dir / "config.json"
    reported_backup_path = None
    build_dir.mkdir(parents=True, exist_ok=True)
    ensure_init_wizard_gitignore(build_dir)

    if config_path.exists():
        assert overwrite
        reported_backup_path = init_wizard_backup_path(
            project,
            requested_backup_path,
            timestamp,
        )
        reported_backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_path, reported_backup_path)

    write_json(config_path, config)
    assert_init_wizard_config_structure(read_json(config_path))

    return {
        "backup_path": reported_backup_path,
        "dependency_issues": dependency_issues,
        "environment_issues": environment_issues,
        "structure_valid": True,
    }


def test_build_and_verify_main_returns_error_without_command(capsys) -> None:
    module = load_build_and_verify_module()

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
    command = [sys.executable, "-c", code]
    _FAIL_ONCE_COMMANDS[tuple(command)] = {"label": label, "failed": False}
    return command


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


def write_release_projection_project(project: Path) -> None:
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


def test_build_and_verify_plugin_has_dual_manifests() -> None:
    codex_manifest = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    claude_manifest = read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")

    assert codex_manifest["name"] == PLUGIN_NAME
    assert claude_manifest["name"] == PLUGIN_NAME
    assert codex_manifest["version"] == claude_manifest["version"]
    assert codex_manifest["description"] == PLUGIN_DESCRIPTION
    assert claude_manifest["description"] == PLUGIN_DESCRIPTION
    assert codex_manifest["skills"] == "./skills"
    assert claude_manifest["skills"] == "./skills"


def test_build_and_verify_plugin_has_runtime_and_init_skill_entrypoints() -> None:
    skill_root = PLUGIN_ROOT / "skills"
    runtime_script_path = skill_root / PLUGIN_NAME / "scripts" / "build_and_verify.py"
    skill_dirs = sorted(path.name for path in skill_root.iterdir() if path.is_dir())
    runtime_skill_text = (skill_root / PLUGIN_NAME / "SKILL.md").read_text(encoding="utf-8")
    runtime_front_matter = runtime_skill_text.split("---", 2)[1]
    init_skill_text = (INIT_SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    init_front_matter = init_skill_text.split("---", 2)[1]

    assert skill_dirs == [PLUGIN_NAME, INIT_SKILL_NAME]
    assert runtime_script_path.is_file()
    assert runtime_skill_text.startswith("---\n")
    assert f"name: {PLUGIN_NAME}" in runtime_front_matter
    assert "本仓库 build（构建检查）和 verify（验证）的统一入口" in runtime_skill_text
    assert "默认 verify（验证）使用 fast（快速）模式" in runtime_skill_text
    assert "`--full`（完整）只允许 PR Flow hotfix（拉取请求流程热修复）直推流程和 PR CI（拉取请求持续集成）使用" in runtime_skill_text
    assert "不安装依赖" in runtime_skill_text
    assert "不写用户级配置" in runtime_skill_text
    assert "不配置 CI（持续集成）" in runtime_skill_text
    assert "不内置仓库业务逻辑" in runtime_skill_text
    assert "复制同一套 runtime（运行时）到 `.build-and-verify/runtime/`" in runtime_skill_text
    assert "只提示 runtime（运行时）版本落后，不自动更新仓库文件" in runtime_skill_text
    assert "scripts/build_and_verify.py init" in runtime_skill_text
    assert "scripts/build_and_verify.py update-runtime" in runtime_skill_text
    assert "scripts/build_and_verify.py build" in runtime_skill_text
    assert "scripts/build_and_verify.py verify" in runtime_skill_text
    assert ".build-and-verify/runtime/build_and_verify.py verify" in runtime_skill_text
    assert "timeoutSeconds" in runtime_skill_text
    assert "pytest-xdist" in runtime_skill_text

    assert init_skill_text.startswith("---\n")
    assert f"name: {INIT_SKILL_NAME}" in init_front_matter
    assert "questionnaire.md" in init_skill_text
    assert "ecosystem-detection.md" in init_skill_text
    assert "config-draft.md" in init_skill_text
    assert "validation.md" in init_skill_text
    assert init_skill_text.index("questionnaire.md") < init_skill_text.index("ecosystem-detection.md")
    assert init_skill_text.index("ecosystem-detection.md") < init_skill_text.index("config-draft.md")
    assert init_skill_text.index("config-draft.md") < init_skill_text.index("validation.md")
    assert "用户沉默不能视为确认" in init_skill_text
    assert "不新增命令行初始化脚本" in init_skill_text
    assert "不安装依赖" in init_skill_text
    assert "不写用户级配置" in init_skill_text
    assert "不配置 CI（持续集成）" in init_skill_text
    assert "dry run" not in init_skill_text
    assert "试运行）" not in init_skill_text


def test_build_and_verify_init_references_all_required_files() -> None:
    assert INIT_SKILL_ROOT.is_dir()
    assert INIT_REFERENCE_ROOT.is_dir()
    assert {
        path.name for path in INIT_REFERENCE_ROOT.iterdir() if path.is_file()
    } == REQUIRED_INIT_REFERENCES


def test_build_and_verify_init_questionnaire_contains_fixed_flow() -> None:
    text = (INIT_REFERENCE_ROOT / "questionnaire.md").read_text(encoding="utf-8")
    required_options = [
        "使用当前目录。",
        "使用用户提供的绝对路径。",
        "允许扫描仓库文件。",
        "不允许扫描，改为手动提供命令。",
        "接受建议候选 checks（检查项）。",
        "修改候选 checks（检查项）。",
        "手动新增 checks（检查项）。",
        "接受建议 paths（受影响路径）。",
        "修改 paths（受影响路径）。",
        "接受建议运行参数。",
        "修改 `verify.maxParallel`（最大并行检查数）。",
        "修改 `verify.timeoutSeconds`（超时秒数）。",
        "确认写入。",
        "返回前面问题修改草案。",
    ]
    required_questions = [
        "Q1 目标仓库路径确认",
        "Q2 扫描授权",
        "Q3 候选 check（检查项）确认",
        "Q4 paths（受影响路径）确认",
        "Q5 并行和超时确认",
        "Q6 覆盖与最终写入确认",
    ]

    for question in required_questions:
        assert question in text
        section_start = text.index(f"## {question}")
        next_question_index = required_questions.index(question) + 1
        if next_question_index < len(required_questions):
            section_end = text.index(f"## {required_questions[next_question_index]}")
            section = text[section_start:section_end]
        else:
            section = text[section_start:]
        assert "固定选项" in section
        assert "选择后果" in section
        assert "跳转规则" in section
    for option in required_options:
        assert option in text
    assert "固定选项" in text
    assert "选择后果" in text
    assert "跳转规则" in text
    assert "不得自由编造初始化问题" in text
    assert "不得跳过 Q6 最终写入确认" in text
    assert "用户沉默不能视为确认" in text
    assert "inputs（缓存输入）默认由 agent（代理）根据 paths（受影响路径）和 command（命令）来源推导" in text
    assert "覆盖已有配置时自动使用默认备份路径" in text
    assert "Q7" not in text
    assert "Q8" not in text
    assert "Q9" not in text
    assert "Q10" not in text
    assert "Q6 inputs（缓存输入）确认" not in text
    assert "Q9 备份路径确认" not in text
    assert "dry run" not in text
    assert "试运行）" not in text


def test_build_and_verify_init_current_specs_match_simplified_flow() -> None:
    active_spec = (
        REPO_ROOT / "openspec" / "specs" / "test-framework-plugin" / "spec.md"
    ).read_text(encoding="utf-8")
    design = (
        REPO_ROOT
        / "docs"
        / "superpowers"
        / "specs"
        / "2026-06-26-build-and-verify-init-skill-design.md"
    ).read_text(encoding="utf-8")

    assert "默认从 `paths`（受影响路径）和 command（命令）来源推导 `inputs`" in active_spec
    assert "不得单独要求用户选择备份路径" in active_spec
    assert "通用候选" in active_spec
    assert "固定为 6 步" in design
    assert "inputs（缓存输入）默认由 agent（代理）从 paths（受影响路径）和 command（命令）来源推导" in design
    assert "不单独询问备份路径" in design
    assert "通用候选" in design
    for stale_text in [active_spec, design]:
        assert "10 个固定问题" not in stale_text
        assert "inputs（缓存输入）确认" not in stale_text
        assert "备份路径确认" not in stale_text
        assert "首版只识别 Node（节点运行时）和 Python（Python 语言）" not in stale_text


def test_build_and_verify_init_ecosystem_detection_covers_node_python_and_fallback() -> None:
    text = (INIT_REFERENCE_ROOT / "ecosystem-detection.md").read_text(encoding="utf-8")
    exact_node_rules = [
        "`pnpm-lock.yaml` -> `pnpm <script>`",
        "`yarn.lock` -> `yarn <script>`",
        "`package-lock.json` -> `npm run <script>`",
        "无 lockfile（锁文件） -> `npm run <script>`",
        "`build` -> `build.node`",
        "`test` -> `verify.node-tests`",
        "`lint` -> `verify.node-lint`",
        "`typecheck` -> `verify.node-typecheck`",
        "`check` -> `verify.node-check`",
        "`verify` -> `verify.node-verify`",
    ]
    exact_python_rules = [
        "pytest（Python 测试运行器） -> `verify.python-tests`",
        "tox（测试环境工具） -> `verify.python-tox`",
        "nox（自动化任务工具） -> `verify.python-nox`",
    ]

    for token in [
        "package.json",
        "scripts",
        "build",
        "test",
        "lint",
        "typecheck",
        "pyproject.toml",
        "pytest.ini",
        "tox.ini",
        "noxfile.py",
        "requirements*.txt",
        "未识别生态",
        "手动提供 build（构建检查）和 verify（验证）命令",
    ]:
        assert token in text
    for rule in exact_node_rules:
        assert rule in text
    for rule in exact_python_rules:
        assert rule in text
    for token in [
        "同一分组内 check id（检查项标识）冲突",
        "改成唯一 id（标识）",
        "向用户说明改名原因",
        "只使用第一个匹配的 lockfile（锁文件）选择包管理器",
        "如果多个 lockfile（锁文件）同时存在，必须展示冲突并让用户选择一个包管理器",
        "不得同时生成多个互相冲突的 command（命令）",
        "Mixed Repository（混合仓库）",
        "同时展示两类候选 checks（检查项）",
        "不根据文件数量、语言比例或 agent（代理）偏好自动删减候选项",
        "由用户选择纳入哪些 checks（检查项）",
    ]:
        assert token in text
    assert "dry run" not in text
    assert "试运行）" not in text


def test_build_and_verify_init_references_limit_pyproject_to_detection_signal() -> None:
    references = {
        path.name: path.read_text(encoding="utf-8")
        for path in INIT_REFERENCE_ROOT.glob("*.md")
    }
    ecosystem_lines = [
        line
        for line in references["ecosystem-detection.md"].splitlines()
        if "pyproject.toml" in line
    ]
    config_draft_lines = [
        line
        for line in references["config-draft.md"].splitlines()
        if "pyproject.toml" in line
    ]

    assert "- `pyproject.toml`（项目配置）" in ecosystem_lines
    assert ecosystem_lines
    assert all("command（命令）" not in line for line in ecosystem_lines)
    assert config_draft_lines
    assert all("command（命令）" not in line for line in config_draft_lines)
    assert all(
        "paths（受影响路径）" in line or "inputs（缓存输入）" in line
        for line in config_draft_lines
    )
    assert "pyproject.toml" not in references["questionnaire.md"]
    assert "pyproject.toml" not in references["validation.md"]


def test_build_and_verify_init_template_node_lockfile_conflict_requires_user_choice(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text(
        json.dumps({"scripts": {"build": "vite build", "test": "vitest"}}, indent=2),
        encoding="utf-8",
    )
    (project / "package-lock.json").write_text("{}", encoding="utf-8")
    (project / "yarn.lock").write_text("", encoding="utf-8")

    unresolved = init_wizard_node_package_manager_resolution(project)
    resolved = init_wizard_node_package_manager_resolution(project, selected="yarn")

    assert unresolved["requires_user_choice"] is True
    assert unresolved["commands"] == []
    assert resolved["requires_user_choice"] is False
    assert resolved["package_manager"] == "yarn"
    assert all(command.startswith("yarn ") for command in resolved["commands"])
    assert all("npm run" not in command for command in resolved["commands"])


def test_build_and_verify_init_generic_candidate_rules_are_constrained() -> None:
    questionnaire = (INIT_REFERENCE_ROOT / "questionnaire.md").read_text(encoding="utf-8")
    ecosystem = (INIT_REFERENCE_ROOT / "ecosystem-detection.md").read_text(encoding="utf-8")
    config_draft = (INIT_REFERENCE_ROOT / "config-draft.md").read_text(encoding="utf-8")

    for token in [
        "Generic Candidate Discovery（通用候选发现）",
        "不得运行候选 command（命令）",
        "Makefile（任务文件）",
        "`scripts/`（脚本目录）",
        "`tests/`（测试目录）",
        "`openspec/`（开放规格目录）",
        "source（来源）",
        "confidence（置信度）",
        "reason（纳入理由）",
        "risk（风险提示）",
        "High（高）",
        "Medium（中）",
        "Low（低）",
        "deploy（部署）",
        "publish（发布）",
        "release（发布流程）",
        "push（推送）",
        "delete（删除）",
        "remove（移除）",
        "migrate（迁移）",
    ]:
        assert token in ecosystem

    for token in [
        "已有配置候选、生态候选和通用候选",
        "高置信度候选",
        "中低置信度候选",
    ]:
        assert token in questionnaire

    for token in [
        "高置信度候选可以默认建议纳入",
        "中低置信度候选只能展示给用户选择",
        "风险候选不得默认纳入",
    ]:
        assert token in config_draft


def test_build_and_verify_init_template_deduplicates_conflicting_check_ids() -> None:
    candidates = [
        {"section": "verify", "id": "verify.node-tests", "script": "test"},
        {"section": "verify", "id": "verify.node-tests", "script": "test:unit"},
        {"section": "build", "id": "build.node", "script": "build"},
    ]

    result = init_wizard_ensure_unique_check_ids(candidates)

    verify_ids = [
        candidate["id"] for candidate in result["candidates"] if candidate["section"] == "verify"
    ]
    assert verify_ids == ["verify.node-tests", "verify.node-tests-2"]
    assert result["rename_reasons"] == [
        "verify.node-tests -> verify.node-tests-2: 同一分组内 check id（检查项标识）冲突"
    ]


def test_build_and_verify_init_config_draft_rules_cover_commands_paths_inputs_and_runtime_tuning() -> None:
    text = (INIT_REFERENCE_ROOT / "config-draft.md").read_text(encoding="utf-8")

    for token in [
        "build.checks",
        "verify.checks",
        "check id（检查项标识）",
        "短横线",
        "command（命令）默认使用字符串形式",
        "列表形式 command（命令）只在用户明确要求",
        "paths（受影响路径）",
        "inputs（缓存输入）",
        "verify.maxParallel",
        "verify.timeoutSeconds",
        "checkParallel",
        "pytestXdistWorkers",
        "auto（自动）语义",
        "只能在解释含义并获得用户确认后写入",
    ]:
        assert token in text
    assert "inputs（缓存输入）默认从 paths（受影响路径）和 command（命令）来源推导" in text
    assert "写入前必须逐项展示 inputs（缓存输入）并等待用户确认" not in text
    assert "`parallel: true`" not in text


def test_build_and_verify_init_references_have_cross_file_flow_invariants() -> None:
    questionnaire = (INIT_REFERENCE_ROOT / "questionnaire.md").read_text(encoding="utf-8")
    ecosystem = (INIT_REFERENCE_ROOT / "ecosystem-detection.md").read_text(encoding="utf-8")
    config_draft = (INIT_REFERENCE_ROOT / "config-draft.md").read_text(encoding="utf-8")
    validation = (INIT_REFERENCE_ROOT / "validation.md").read_text(encoding="utf-8")

    assert "候选 Node（节点运行时）和 Python（Python 语言）checks（检查项）" in questionnaire
    assert "展示脚本名、原始 script（脚本）内容、建议 check id（检查项标识）和建议 command（命令）" in ecosystem
    assert "展示检测到的配置文件、建议 check id（检查项标识）和建议 command（命令）" in ecosystem
    assert "写入后执行 config（配置）结构校验" in validation
    assert "dry run" not in questionnaire + validation
    assert "试运行）" not in questionnaire + validation

    assert "短横线风格" in config_draft
    for check_id in [
        "build.node",
        "verify.node-tests",
        "verify.node-lint",
        "verify.node-typecheck",
        "verify.node-check",
        "verify.node-verify",
    ]:
        assert check_id in ecosystem


def test_build_and_verify_init_skill_closes_interactive_validation_loop_inside_plugin() -> None:
    text = (INIT_SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    for token in [
        "Closed Loop（闭环）",
        "必须在插件内完成",
        "不得把交互式配置、config validation（配置校验）、targeted dependency checks（定向依赖检查）或 environment checks（环境检查）外包给 OpenSpec（开放规格）、测试文件或仓库外说明",
        "references/questionnaire.md",
        "references/ecosystem-detection.md",
        "references/config-draft.md",
        "references/validation.md",
        "targeted dependency checks（定向依赖检查）结果",
        "environment checks（环境检查）结果",
        "config（配置）结构校验结果",
    ]:
        assert token in text
    assert "dry run" not in text
    assert "试运行）" not in text


def test_build_and_verify_init_skill_calls_runtime_init_config_overwrite() -> None:
    skill = (INIT_SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    validation = (INIT_REFERENCE_ROOT / "validation.md").read_text(encoding="utf-8")

    assert "init --config --overwrite" in skill
    assert "init --config --overwrite" in validation
    assert "仍只写空模板" not in skill
    assert "不得由 agent（代理）直接写 `.build-and-verify/config.json`" in skill


def test_build_and_verify_init_references_use_check_parallel_and_pytest_workers() -> None:
    text = "\n".join(
        (INIT_SKILL_ROOT / name).read_text(encoding="utf-8")
        for name in [
            "SKILL.md",
            "references/questionnaire.md",
            "references/ecosystem-detection.md",
            "references/config-draft.md",
            "references/validation.md",
        ]
    )

    assert "checkParallel" in text
    assert "pytestXdistWorkers" in text
    assert "`parallel: true`" not in text
    assert "保留 check id（检查项标识）、command（命令）、paths（受影响路径）、inputs（缓存输入）、parallel" not in text


def test_build_and_verify_init_validation_rules_cover_dependency_backup_and_config_validation() -> None:
    text = (INIT_REFERENCE_ROOT / "validation.md").read_text(encoding="utf-8")

    for token in [
        "targeted dependency checks（定向依赖检查）",
        "environment checks（环境检查）",
        "pytest-xdist",
        "可执行入口",
        "缺失文件或目录",
        "不安装依赖",
        ".build-and-verify/backups/config-YYYYMMDD-HHMMSS.json",
        "如果 backups（备份）目录不存在，必须先创建该目录",
        "Local Git Ignore（本地 Git 忽略）",
        "/cache/",
        "/runs/",
        "/backups/",
        "config（配置）结构校验",
        "verify.timeoutSeconds",
        "checkParallel",
        "pytestXdistWorkers",
        "大于 0 的 number（数字）",
        "允许为空 string list（字符串清单）",
        "Closed Loop（闭环）",
        "写入前摘要必须同时列出 targeted dependency checks（定向依赖检查）结果和 environment checks（环境检查）结果",
        "尝试创建再删除临时探针文件",
        "纯空白字符串必须视为无效",
        "不得把校验结果留到插件外部流程补做",
    ]:
        assert token in text
    assert "dry run" not in text
    assert "试运行）" not in text
    ordered_steps = [
        "写入前执行 targeted dependency checks（定向依赖检查）",
        "写入前执行 environment checks（环境检查）",
        "用户最终确认后，把草案保存为临时 confirmed config（已确认配置）",
        "init --config --overwrite",
        "写入后执行 config（配置）结构校验",
    ]
    positions = [text.index(step) for step in ordered_steps]
    assert positions == sorted(positions)


def test_build_and_verify_init_spec_targets_test_framework_plugin_capability() -> None:
    spec_path = REPO_ROOT / "openspec" / "specs" / "test-framework-plugin" / "spec.md"
    text = spec_path.read_text(encoding="utf-8")

    assert "Runtime and initialization skill surfaces" in text
    assert "build-and-verify-init" in text
    assert "template-driven guided initialization" in text
    assert "Guided initialization drafts generic repository checks" in text
    assert "Guided initialization protects existing configuration" in text
    assert "Guided initialization validates config and environment before completion" in text
    assert "Targeted dependency checks report issues before write without blocking write" in text
    assert "Config structure is validated after write" in text
    assert "dry run" not in text
    assert "试运行）" not in text


def test_build_and_verify_registered_in_marketplaces_and_projection() -> None:
    claude_catalog = read_json(CLAUDE_REPO_MARKETPLACE)
    codex_catalog = read_json(CODEX_REPO_MARKETPLACE)
    claude_names = plugin_names(claude_catalog)
    codex_names = plugin_names(codex_catalog)
    projection_plugins = release_projection_plugins()

    assert plugin_after(claude_names, "pr-flow") == PLUGIN_NAME
    assert claude_catalog["plugins"][claude_names.index(PLUGIN_NAME)] == {
        "name": PLUGIN_NAME,
        "source": "./plugins/build-and-verify",
        "description": PLUGIN_DESCRIPTION,
    }
    assert plugin_after(codex_names, "pr-flow") == PLUGIN_NAME
    assert codex_catalog["plugins"][codex_names.index(PLUGIN_NAME)] == {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": "./plugins/build-and-verify"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools",
    }
    assert plugin_after(projection_plugins, "pr-flow") == PLUGIN_NAME


def test_build_and_verify_registered_in_release_flow_sources() -> None:
    release_files = [
        RELEASE_FLOW_PROJECTION,
        RELEASE_FLOW_SCRIPT,
    ]

    for path in release_files:
        text = path.read_text(encoding="utf-8")
        assert "build-and-verify" in text, f"{path} does not reference build-and-verify"
        assert "test-framework" not in text, f"{path} still references test-framework"


def test_build_and_verify_active_surfaces_do_not_keep_old_entrypoints() -> None:
    assert not (REPO_ROOT / "pyproject.toml").exists()
    assert not (REPO_ROOT / ".test-framework").exists()
    assert not (REPO_ROOT / "plugins" / "test-framework").exists()
    active_paths = [
        REPO_ROOT / ".build-and-verify" / "config.json",
        REPO_ROOT / ".comet.yaml",
        REPO_ROOT / ".pr-flow" / "config.yaml",
        REPO_ROOT / ".release-flow" / "config.yaml",
        REPO_ROOT / ".release-flow" / "projection.yaml",
        CODEX_REPO_MARKETPLACE,
        CLAUDE_REPO_MARKETPLACE,
        RELEASE_FLOW_SCRIPT,
        REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow" / "scripts" / "pr_flow.py",
    ]
    active_paths.extend(sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")))
    active_paths.extend(sorted((REPO_ROOT / ".github" / "workflows").glob("*.yaml")))
    active_paths.extend(sorted((REPO_ROOT / ".comet").glob("*.yaml")))
    plugin_paths = [
        path
        for path in PLUGIN_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    plugin_forbidden = [
        "plugins/test-framework",
        ".test-framework",
        "test_framework.py",
        "test_framework_runner.py",
        "verify.test-framework",
    ]
    active_forbidden = [*plugin_forbidden, "pyproject.toml"]

    for path in active_paths:
        text = path.read_text(encoding="utf-8")
        for old_entrypoint in active_forbidden:
            assert old_entrypoint not in text, f"{path} still references {old_entrypoint}"

    for path in plugin_paths:
        text = path.read_text(encoding="utf-8")
        for old_entrypoint in plugin_forbidden:
            assert old_entrypoint not in text, f"{path} still references {old_entrypoint}"


def test_build_and_verify_root_build_check_uses_local_plugin_build() -> None:
    config = read_json(REPO_ROOT / ".build-and-verify" / "config.json")
    build_checks = config["build"]["checks"]

    assert len(build_checks) == 1
    assert build_checks[0]["id"] == "build.local-plugin-package"
    assert build_checks[0]["command"] == "python scripts/local_plugin_build.py"
    assert "scripts/local_plugin_build.py" in build_checks[0]["inputs"]


def test_build_and_verify_pytest_options_live_in_explicit_commands() -> None:
    config = read_json(REPO_ROOT / ".build-and-verify" / "config.json")
    verify_checks = config["verify"]["checks"]

    assert "pyproject.toml" not in json.dumps(config, ensure_ascii=False)
    for check in verify_checks:
        command = check["command"]
        if "pytest" in command:
            tokens = command.split()
            assert " -q " in f" {command} "
            assert "-n" not in tokens
            assert check["pytestXdistWorkers"]
            assert "-p" in tokens
            assert "no:cacheprovider" in tokens
            assert " tests/" in f" {command} "
            assert any(token.startswith("tests/") and token.endswith(".py") for token in tokens)


def test_build_and_verify_explicit_pytest_paths_cover_removed_pyproject_testpaths() -> None:
    config = read_json(REPO_ROOT / ".build-and-verify" / "config.json")
    verify_checks = config["verify"]["checks"]
    explicit_test_files = {
        token
        for check in verify_checks
        if "pytest" in check["command"]
        for token in check["command"].split()
        if token.startswith("tests/") and token.endswith(".py")
    }
    expected_test_files = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "tests").glob("test_*.py")
    }

    assert explicit_test_files == expected_test_files


def test_build_and_verify_release_projection_passes_real_validate() -> None:
    result = call_release_flow_main("validate", "--project", ".")

    assert result.returncode == 0, result.stdout + result.stderr


def test_build_and_verify_release_projection_projects_real_catalogs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_projection_project(project)

    result = call_release_flow_main("project", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: projected" in result.stdout

    codex_catalog = read_json(project / ".agents" / "plugins" / "marketplace.json")
    codex_names = plugin_names(codex_catalog)
    assert plugin_after(codex_names, "pr-flow") == PLUGIN_NAME
    assert codex_catalog["plugins"][codex_names.index(PLUGIN_NAME)] == {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": "./plugins/build-and-verify"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools",
    }


def test_build_and_verify_init_writes_config_gitignore_and_cache(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run_build_and_verify("init", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: initialized" in result.stdout
    assert (project / ".build-and-verify" / "config.json").is_file()
    assert (project / ".build-and-verify" / ".gitignore").is_file()
    assert (project / ".build-and-verify" / "cache").is_dir()
    assert not (project / "scripts" / "check.py").exists()
    assert read_json(project / ".build-and-verify" / "config.json") == {
        "version": 1,
        "build": {"checks": []},
        "verify": {"checks": []},
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


def test_build_and_verify_init_copies_repository_runtime(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run_build_and_verify("init", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    runtime = project / ".build-and-verify" / "runtime"
    assert (runtime / "build_and_verify.py").is_file()
    assert (runtime / "build_and_verify_runner.py").is_file()
    assert (runtime / "version.json").is_file()


def test_build_and_verify_init_writes_confirmed_config_with_overwrite(
    tmp_path: Path,
) -> None:
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

    result = run_build_and_verify(
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
    assert (build_dir / "runtime" / "build_and_verify.py").is_file()
    assert (build_dir / "cache").is_dir()


def test_build_and_verify_init_config_overwrite_e2e_temp_target_repo(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target-repo"
    target.mkdir()
    assert git(target, "init").returncode == 0
    assert git(target, "config", "user.email", "test@example.invalid").returncode == 0
    assert git(target, "config", "user.name", "Test User").returncode == 0
    confirmed = tmp_path / "confirmed.json"
    verify_script = (
        "from pathlib import Path; "
        "Path('e2e.log').open('a', encoding='utf-8').write('verify\\n')"
    )
    write_json(
        confirmed,
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "verify.e2e",
                        "command": [sys.executable, "-c", verify_script],
                        "paths": ["src/**"],
                        "inputs": ["src"],
                        "checkParallel": True,
                    }
                ]
            },
        },
    )
    (target / "src").mkdir()
    (target / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    init = run_build_and_verify_subprocess(
        "init",
        "--project",
        str(target),
        "--config",
        str(confirmed),
        "--overwrite",
    )
    repository_script = target / ".build-and-verify" / "runtime" / "build_and_verify.py"
    fast = subprocess.run(
        [sys.executable, str(repository_script), "verify", "--project", str(target)],
        cwd=target,
        check=False,
        text=True,
        capture_output=True,
    )

    assert init.returncode == 0, init.stdout + init.stderr
    assert (target / ".build-and-verify" / "config.json").is_file()
    assert (target / ".build-and-verify" / "cache").is_dir()
    assert repository_script.is_file()
    assert fast.returncode == 0, fast.stdout + fast.stderr
    assert "full-not-run: true" in fast.stdout
    assert (target / "e2e.log").read_text(encoding="utf-8").splitlines() == ["verify"]


def test_copied_repository_runtime_can_initialize_another_project(tmp_path: Path) -> None:
    source_project = tmp_path / "source"
    target_project = tmp_path / "target"
    source_project.mkdir()
    target_project.mkdir()
    assert run_build_and_verify("init", "--project", str(source_project)).returncode == 0
    repository_script = (
        source_project / ".build-and-verify" / "runtime" / "build_and_verify.py"
    )

    result = subprocess.run(
        [sys.executable, str(repository_script), "init", "--project", str(target_project)],
        cwd=target_project,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (target_project / ".build-and-verify" / "config.json").is_file()
    assert (target_project / ".build-and-verify" / "runtime" / "build_and_verify.py").is_file()


def test_build_and_verify_update_runtime_refreshes_runtime_without_config(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    config_path = project / ".build-and-verify" / "config.json"
    runtime_file = project / ".build-and-verify" / "runtime" / "build_and_verify.py"
    config_before = config_path.read_text(encoding="utf-8")
    runtime_file.write_text("stale\n", encoding="utf-8")

    result = run_build_and_verify("update-runtime", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "stale" not in runtime_file.read_text(encoding="utf-8")
    assert config_path.read_text(encoding="utf-8") == config_before


def test_copied_repository_runtime_can_update_itself(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    repository_script = project / ".build-and-verify" / "runtime" / "build_and_verify.py"

    result = subprocess.run(
        [sys.executable, str(repository_script), "update-runtime", "--project", str(project)],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: runtime-updated" in result.stdout


def test_build_and_verify_verify_does_not_mutate_repository_runtime(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    write_json(
        project / ".build-and-verify" / "config.json",
        {"version": 1, "build": {"checks": []}, "verify": {"checks": []}},
    )
    runtime_file = project / ".build-and-verify" / "runtime" / "build_and_verify.py"
    before = runtime_file.read_bytes()

    result = run_check(project, "verify", check_user_runtime=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert runtime_file.read_bytes() == before


def test_build_and_verify_verify_reports_newer_user_runtime_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    installed_runtime = (
        home
        / ".codex"
        / "plugins"
        / "cache"
        / "vendor"
        / "build-and-verify"
        / "9.9.9"
        / "skills"
        / "build-and-verify"
        / "scripts"
    )
    installed_runtime.mkdir(parents=True)
    installed_script = installed_runtime / "build_and_verify.py"
    installed_script.write_text("# newer\n", encoding="utf-8")
    write_json(
        installed_runtime / "version.json",
        {
            "plugin": "build-and-verify",
            "plugin_version": "9.9.9",
            "runtime_version": "9.9.9",
        },
    )
    monkeypatch.setenv("USERPROFILE", str(home))
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    write_json(
        project / ".build-and-verify" / "config.json",
        {"version": 1, "build": {"checks": []}, "verify": {"checks": []}},
    )
    runtime_file = project / ".build-and-verify" / "runtime" / "build_and_verify.py"
    before = runtime_file.read_bytes()

    result = run_check(project, "verify", check_user_runtime=True)

    assert result.returncode == 0, result.stdout + result.stderr
    repository_version = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")["version"]
    assert f"runtime_outdated: repository={repository_version} installed=9.9.9" in result.stdout
    assert f"python {installed_script} update-runtime --project {project}" in result.stdout
    assert runtime_file.read_bytes() == before


def test_build_and_verify_verify_runtime_hint_preserves_failure_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    installed_runtime = (
        home
        / ".codex"
        / "plugins"
        / "cache"
        / "vendor"
        / "build-and-verify"
        / "9.9.9"
        / "skills"
        / "build-and-verify"
        / "scripts"
    )
    installed_runtime.mkdir(parents=True)
    installed_script = installed_runtime / "build_and_verify.py"
    installed_script.write_text("# newer\n", encoding="utf-8")
    write_json(
        installed_runtime / "version.json",
        {
            "plugin": "build-and-verify",
            "plugin_version": "9.9.9",
            "runtime_version": "9.9.9",
        },
    )
    monkeypatch.setenv("USERPROFILE", str(home))
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "fails",
                        "command": command_that_fails_once("fails"),
                        "inputs": [],
                    }
                ]
            },
        },
    )
    runtime_file = project / ".build-and-verify" / "runtime" / "build_and_verify.py"
    before = runtime_file.read_bytes()

    result = run_check(project, "verify", "--full", check_user_runtime=True)

    assert result.returncode == 1
    repository_version = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")["version"]
    assert f"runtime_outdated: repository={repository_version} installed=9.9.9" in result.stdout
    assert f"python {installed_script} update-runtime --project {project}" in result.stdout
    assert "failed: fails" in result.stdout
    assert "status: failed" in result.stdout
    assert runtime_file.read_bytes() == before


@pytest.mark.parametrize(
    "existing",
    [
        Path(".build-and-verify/config.json"),
        Path(".build-and-verify/.gitignore"),
        Path(".build-and-verify/runtime"),
    ],
)
def test_build_and_verify_init_refuses_existing_files_before_writes(
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

    result = run_build_and_verify("init", "--project", str(project))

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


def test_build_and_verify_init_template_simulation_writes_default_gitignore(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    draft_config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {"checks": []},
    }

    report = simulate_init_wizard_write(project, draft_config, overwrite=False)

    gitignore = project / ".build-and-verify" / ".gitignore"
    assert gitignore.read_text(encoding="utf-8").splitlines() == DEFAULT_BUILD_AND_VERIFY_GITIGNORE
    assert report["backup_path"] is None
    assert read_json(project / ".build-and-verify" / "config.json") == draft_config


def test_build_and_verify_init_template_simulation_writes_backup_and_valid_config(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "tests").mkdir()
    (project / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (project / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    build_dir = project / ".build-and-verify"
    build_dir.mkdir()
    old_config = {
        "version": 1,
        "build": {"checks": [{"id": "build.old", "command": command_that_logs("old")}]},
        "verify": {"checks": []},
    }
    write_json(build_dir / "config.json", old_config)
    (build_dir / ".gitignore").write_text("/cache/\n/runs/\n", encoding="utf-8")
    draft_config = {
        "version": 1,
        "build": {
            "checks": [
                {
                    "id": "build.local",
                    "command": command_that_logs("build-ok"),
                    "inputs": ["src"],
                }
            ]
        },
        "verify": {
            "maxParallel": 2,
            "timeoutSeconds": 60,
            "checks": [
                {
                    "id": "verify.python-tests",
                    "command": [sys.executable, "-m", "pytest", "--version"],
                    "paths": ["src/**", "tests/**"],
                    "inputs": ["pyproject.toml", "pytest.ini", "src", "tests"],
                    "checkParallel": True,
                    "timeoutSeconds": 30,
                }
            ],
        },
    }

    report = simulate_init_wizard_write(
        project,
        draft_config,
        overwrite=True,
    )

    backup_path = build_dir / "backups" / "config-20260626-120000.json"
    assert report["backup_path"] == backup_path
    assert read_json(backup_path) == old_config
    assert "/backups/" in (build_dir / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert read_json(build_dir / "config.json") == draft_config
    assert report["structure_valid"] is True
    assert not (project / "run.log").exists()


def test_build_and_verify_init_template_simulation_validates_custom_backup_path(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    build_dir = project / ".build-and-verify"
    build_dir.mkdir()
    old_config = {"version": 1, "build": {"checks": []}, "verify": {"checks": []}}
    new_config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {"checks": []},
    }
    write_json(build_dir / "config.json", old_config)

    report = simulate_init_wizard_write(
        project,
        new_config,
        overwrite=True,
        backup_path=Path(".build-and-verify/custom/config-custom.json"),
    )

    assert report["backup_path"] == project / ".build-and-verify/custom/config-custom.json"
    assert read_json(report["backup_path"]) == old_config

    write_json(build_dir / "config.json", old_config)
    existing_backup = project / ".build-and-verify/custom/existing.json"
    existing_backup.parent.mkdir(parents=True, exist_ok=True)
    existing_backup.write_text("existing\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="must not overwrite existing file"):
        simulate_init_wizard_write(
            project,
            new_config,
            overwrite=True,
            backup_path=existing_backup,
        )

    with pytest.raises(AssertionError, match="inside target repository"):
        simulate_init_wizard_write(
            project,
            new_config,
            overwrite=True,
            backup_path=tmp_path / "outside.json",
        )


def test_build_and_verify_init_template_simulation_accepts_mixed_candidates(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text(
        json.dumps({"scripts": {"build": "vite build", "test": "vitest"}}, indent=2),
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    config = {
        "version": 1,
        "build": {
            "checks": [
                {"id": "build.node", "command": command_that_logs("node-build")}
            ]
        },
        "verify": {
            "checks": [
                {"id": "verify.node-tests", "command": command_that_logs("node-tests")},
                {
                    "id": "verify.python-tests",
                    "command": command_that_logs("python-tests"),
                },
            ]
        },
    }

    report = simulate_init_wizard_write(
        project,
        config,
        overwrite=False,
    )

    written = read_json(project / ".build-and-verify" / "config.json")
    assert [check["id"] for check in written["build"]["checks"]] == ["build.node"]
    assert [check["id"] for check in written["verify"]["checks"]] == [
        "verify.node-tests",
        "verify.python-tests",
    ]
    assert report["structure_valid"] is True
    assert not (project / "run.log").exists()


def test_build_and_verify_init_template_simulation_accepts_manual_fallback_config(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Manual Project\n", encoding="utf-8")
    config = {
        "version": 1,
        "build": {
            "checks": [
                {
                    "id": "build.manual",
                    "command": [sys.executable, "-c", "print('manual build')"],
                    "inputs": ["README.md"],
                }
            ]
        },
        "verify": {
            "checks": [
                {
                    "id": "verify.manual",
                    "command": [sys.executable, "-c", "print('manual verify')"],
                    "inputs": ["README.md"],
                }
            ]
        },
    }

    report = simulate_init_wizard_write(
        project,
        config,
        overwrite=False,
    )

    assert not (project / "package.json").exists()
    assert not (project / "pyproject.toml").exists()
    assert read_json(project / ".build-and-verify" / "config.json") == config
    assert report["dependency_issues"] == []
    assert report["environment_issues"] == []
    assert report["structure_valid"] is True


def test_build_and_verify_init_template_detects_pytest_xdist_dependency(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {
            "checks": [
                {
                    "id": "verify.pytest-parallel",
                    "command": "python -m pytest",
                    "pytestXdistWorkers": "auto",
                },
                {"id": "verify.pytest-serial", "command": "python -m pytest"},
            ]
        },
    }

    issues = init_wizard_targeted_dependency_issues(
        project,
        config,
        executable_resolver=lambda command: command if command in {"python", "pytest"} else None,
        xdist_available=False,
    )

    assert len([issue for issue in issues if "pytest-xdist" in issue["问题"]]) == 1
    assert all(issue["是否阻止写入"] == "不阻止" for issue in issues)


@pytest.mark.parametrize(
    "command",
    [
        "pytest -n auto",
        "python -m pytest -n auto",
        "python -m pytest --numprocesses=auto",
        [sys.executable, "-m", "pytest", "-n", "auto"],
        "tools/pytest -n auto",
        r"tools\pytest -n auto",
        "python -m unittest -n auto",
    ],
)
def test_build_and_verify_init_template_pytest_xdist_detection_matches_runner(
    command: Any,
) -> None:
    runner = load_build_and_verify_runner_module()

    assert init_wizard_uses_pytest_parallel(command) is runner.uses_pytest_xdist(command)


def test_build_and_verify_init_template_detects_missing_executable(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = {
        "version": 1,
        "build": {
            "checks": [
                {"id": "build.missing-tool", "command": "missing-build-tool --version"}
            ]
        },
        "verify": {"checks": []},
    }

    issues = init_wizard_targeted_dependency_issues(
        project,
        config,
        executable_resolver=lambda _command: None,
    )

    assert any(
        "可执行入口 `missing-build-tool` 不可找到" in issue["问题"]
        for issue in issues
    )
    assert all(issue["是否阻止写入"] == "不阻止" for issue in issues)


def test_build_and_verify_init_template_detects_missing_paths_and_inputs(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {
            "checks": [
                {
                    "id": "verify.missing-paths",
                    "command": command_that_logs("unused"),
                    "paths": ["missing-src/**"],
                    "inputs": ["missing-config.toml"],
                }
            ]
        },
    }

    issues = init_wizard_targeted_dependency_issues(project, config)

    assert any("missing-src/**" in issue["问题"] for issue in issues)
    assert any("missing-config.toml" in issue["问题"] for issue in issues)
    assert all(issue["是否阻止写入"] == "不阻止" for issue in issues)


def test_build_and_verify_init_template_dependency_issues_do_not_block_write(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {
            "checks": [
                {
                    "id": "verify.missing-tool",
                    "command": "missing-verify-tool --version",
                    "paths": ["future-src/**"],
                    "inputs": [],
                }
            ]
        },
    }

    report = simulate_init_wizard_write(
        project,
        config,
        overwrite=False,
        executable_resolver=lambda _command: None,
    )

    assert (project / ".build-and-verify" / "config.json").is_file()
    assert report["dependency_issues"]
    assert any("可执行入口 `missing-verify-tool` 不可找到" in issue["问题"] for issue in report["dependency_issues"])
    assert any("future-src/**" in issue["问题"] for issue in report["dependency_issues"])
    assert all(issue["是否阻止写入"] == "不阻止" for issue in report["dependency_issues"])
    assert report["structure_valid"] is True


def test_build_and_verify_init_template_environment_issues_do_not_block_write(
    tmp_path: Path,
) -> None:
    project = tmp_path / "missing-project"
    config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {"checks": []},
    }

    report = simulate_init_wizard_write(
        project,
        config,
        overwrite=False,
    )

    assert (project / ".build-and-verify" / "config.json").is_file()
    assert report["environment_issues"]
    assert any("目标仓库路径不存在" in issue["问题"] for issue in report["environment_issues"])
    assert all(issue["是否阻止写入"] == "不阻止" for issue in report["environment_issues"])
    assert report["structure_valid"] is True


def test_build_and_verify_init_template_environment_issues_report_unwritable_config_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    original_write_text = Path.write_text

    def deny_write_probe(path: Path, *args: Any, **kwargs: Any) -> int:
        if path.name == ".init-write-check":
            raise PermissionError("denied")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", deny_write_probe)

    issues = init_wizard_environment_issues(
        project,
        overwrite=False,
        backup_path=None,
    )

    assert any("配置目录不可写入" in issue["问题"] for issue in issues)
    assert all(issue["是否阻止写入"] == "不阻止" for issue in issues)


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("project_is_file", "目标仓库路径不是目录"),
        ("build_dir_is_file", "配置目录路径不是目录"),
        ("backup_outside_repo", "备份目录不在目标仓库内"),
        ("backup_dir_is_file", "备份目录路径不是目录"),
        ("backup_dir_unwritable", "备份目录不可写入"),
        ("backup_dir_cannot_create", "备份目录不可创建"),
    ],
)
def test_build_and_verify_init_template_environment_issues_cover_edge_branches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected: str,
) -> None:
    project = tmp_path / "project"
    overwrite = False
    backup_path = None

    if scenario == "project_is_file":
        project.write_text("not a directory\n", encoding="utf-8")
    else:
        project.mkdir()
        build_dir = project / ".build-and-verify"
        if scenario == "build_dir_is_file":
            build_dir.write_text("not a directory\n", encoding="utf-8")
        else:
            build_dir.mkdir()
        if scenario.startswith("backup_dir_"):
            overwrite = True
            backup_path = Path(".build-and-verify/backups/config.json")
            backup_dir = project / ".build-and-verify" / "backups"
            if scenario == "backup_dir_is_file":
                backup_dir.write_text("not a directory\n", encoding="utf-8")
            elif scenario == "backup_dir_unwritable":
                backup_dir.mkdir()
                original_can_write = init_wizard_can_write_directory

                def fake_can_write(directory: Path) -> bool:
                    if directory == backup_dir:
                        return False
                    return original_can_write(directory)

                monkeypatch.setattr(
                    sys.modules[__name__],
                    "init_wizard_can_write_directory",
                    fake_can_write,
                )
            elif scenario == "backup_dir_cannot_create":
                original_can_create = init_wizard_can_create_directory

                def fake_can_create(directory: Path, boundary: Path) -> bool:
                    if directory == backup_dir:
                        return False
                    return original_can_create(directory, boundary)

                monkeypatch.setattr(
                    sys.modules[__name__],
                    "init_wizard_can_create_directory",
                    fake_can_create,
                )
        elif scenario == "backup_outside_repo":
            overwrite = True
            backup_path = tmp_path / "outside.json"

    issues = init_wizard_environment_issues(
        project,
        overwrite=overwrite,
        backup_path=backup_path,
    )

    assert any(expected in issue["问题"] for issue in issues)
    assert all(issue["是否阻止写入"] == "不阻止" for issue in issues)


@pytest.mark.parametrize(
    ("field", "value", "valid"),
    [
        ("id", "verify.runtime", True),
        ("id", "  ", False),
        ("command", command_that_logs("runtime"), True),
        ("command", "  ", False),
        ("command", [sys.executable, "-c", "print('ok')"], True),
        ("command", [sys.executable, "  "], False),
        ("paths", ["src"], True),
        ("paths", [], True),
        ("paths", [""], False),
        ("paths", ["  "], False),
        ("inputs", ["README.md"], True),
        ("inputs", [], True),
        ("inputs", [""], False),
        ("inputs", ["  "], False),
    ],
)
def test_build_and_verify_init_template_validates_check_string_fields(
    field: str,
    value: Any,
    valid: bool,
) -> None:
    check = {"id": "verify.runtime", "command": command_that_logs("runtime")}
    check[field] = value
    config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {"checks": [check]},
    }

    if valid:
        assert_init_wizard_config_structure(config)
    else:
        with pytest.raises(AssertionError):
            assert_init_wizard_config_structure(config)


@pytest.mark.parametrize(
    ("field", "value", "valid"),
    [
        ("maxParallel", 0, True),
        ("maxParallel", 1, True),
        ("maxParallel", 128, True),
        ("maxParallel", True, False),
        ("maxParallel", -1, False),
        ("maxParallel", "1", False),
        ("timeoutSeconds", 0.5, True),
        ("timeoutSeconds", 1, True),
        ("timeoutSeconds", 3600, True),
        ("timeoutSeconds", 0, False),
        ("timeoutSeconds", -1, False),
        ("timeoutSeconds", True, False),
        ("timeoutSeconds", "60", False),
    ],
)
def test_build_and_verify_init_template_validates_runtime_tuning_boundaries(
    field: str,
    value: Any,
    valid: bool,
) -> None:
    config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {"checks": []},
    }
    config["verify"][field] = value

    if valid:
        assert_init_wizard_config_structure(config)
    else:
        with pytest.raises(AssertionError):
            assert_init_wizard_config_structure(config)


@pytest.mark.parametrize(
    ("field", "value", "valid"),
    [
        ("checkParallel", True, True),
        ("checkParallel", False, True),
        ("checkParallel", "true", False),
        ("pytestXdistWorkers", "auto", True),
        ("pytestXdistWorkers", 1, True),
        ("pytestXdistWorkers", 0, False),
        ("pytestXdistWorkers", True, False),
        ("parallel", True, False),
        ("timeoutSeconds", 0.5, True),
        ("timeoutSeconds", 1, True),
        ("timeoutSeconds", None, True),
        ("timeoutSeconds", 0, False),
        ("timeoutSeconds", -1, False),
        ("timeoutSeconds", True, False),
        ("timeoutSeconds", "60", False),
    ],
)
def test_build_and_verify_init_template_validates_per_check_runtime_tuning(
    field: str,
    value: Any,
    valid: bool,
) -> None:
    check = {"id": "verify.runtime", "command": command_that_logs("runtime")}
    if value is not None:
        check[field] = value
    config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {"checks": [check]},
    }

    if valid:
        assert_init_wizard_config_structure(config)
    else:
        with pytest.raises(AssertionError):
            assert_init_wizard_config_structure(config)


def test_build_and_verify_runner_build_verify_and_full_verify(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "docs").mkdir()
    (project / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
    (project / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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
    verify = run_check(project, "verify", changed_files=["src/app.py", "docs/guide.md"])
    full_verify = run_check(
        project, "verify", "--full", changed_files=["src/app.py", "docs/guide.md"]
    )

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


def test_build_and_verify_runner_full_verify_allows_empty_checks(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0

    result = run_check(project, "verify", "--full")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "checked:" in result.stdout
    assert "full-not-run: false" in result.stdout
    assert "status: passed" in result.stdout


def test_build_and_verify_runner_rejects_legacy_parallel_field(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "legacy-parallel",
                        "command": command_that_logs("legacy-parallel"),
                        "parallel": True,
                        "inputs": [],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 1
    assert "parallel is no longer supported; use checkParallel" in result.stderr
    assert "status: failed" in result.stdout


@pytest.mark.parametrize("value", [True, False])
def test_build_and_verify_runner_accepts_check_parallel_bool(
    tmp_path: Path, value: bool
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "check-parallel",
                        "command": command_that_logs("check-parallel"),
                        "checkParallel": value,
                        "inputs": [],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("value", ["true", 1, 0, None])
def test_build_and_verify_runner_rejects_invalid_check_parallel(
    tmp_path: Path, value: object
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "bad-check-parallel",
                        "command": command_that_logs("bad-check-parallel"),
                        "checkParallel": value,
                        "inputs": [],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 1
    assert "checkParallel must be boolean" in result.stderr


def test_build_and_verify_runner_full_verify_runs_parallel_checks_concurrently(tmp_path: Path, capsys) -> None:
    import threading
    import time

    module = load_build_and_verify_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "checkParallel": True, "inputs": []},
                    {"id": "parallel-b", "command": ["parallel-b"], "checkParallel": True, "inputs": []},
                    {"id": "serial-c", "command": ["serial-c"], "checkParallel": False, "inputs": []},
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


def test_build_and_verify_runner_fast_verify_runs_check_parallel_cache_misses_concurrently(
    tmp_path: Path, capsys
) -> None:
    import threading
    import time

    module = load_build_and_verify_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "fast-a",
                        "command": ["fast-a"],
                        "paths": ["src/**"],
                        "inputs": ["src"],
                        "checkParallel": True,
                    },
                    {
                        "id": "fast-b",
                        "command": ["fast-b"],
                        "paths": ["src/**"],
                        "inputs": ["src"],
                        "checkParallel": True,
                    },
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

    result = module._runner().run_verify(project, runner=fake_runner, full=False)
    captured = capsys.readouterr()

    assert result == 0
    assert max_active > 1
    assert "checked: fast-a, fast-b" in captured.out
    assert "full-not-run: true" in captured.out


def test_build_and_verify_runner_full_verify_honors_max_parallel_checks(tmp_path: Path) -> None:
    import threading
    import time

    module = load_build_and_verify_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "maxParallel": 2,
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "checkParallel": True, "inputs": []},
                    {"id": "parallel-b", "command": ["parallel-b"], "checkParallel": True, "inputs": []},
                    {"id": "parallel-c", "command": ["parallel-c"], "checkParallel": True, "inputs": []},
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


def test_build_and_verify_runner_full_verify_zero_max_parallel_means_unlimited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    import time

    module = load_build_and_verify_module()
    monkeypatch.setattr(module._runner().os, "cpu_count", lambda: 2)
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "maxParallel": 0,
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "checkParallel": True, "inputs": []},
                    {"id": "parallel-b", "command": ["parallel-b"], "checkParallel": True, "inputs": []},
                    {"id": "parallel-c", "command": ["parallel-c"], "checkParallel": True, "inputs": []},
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


def test_build_and_verify_runner_rejects_negative_max_parallel(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "maxParallel": -1,
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "checkParallel": True, "inputs": []},
                ],
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 1
    assert "verify.maxParallel must be non-negative integer" in result.stderr
    assert "status: failed" in result.stdout


def test_build_and_verify_runner_reports_missing_xdist_before_running_pytest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    module = load_build_and_verify_module()
    runner = module._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "pytest-parallel",
                        "command": "python -m pytest -n 8 tests",
                        "checkParallel": False,
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


@pytest.mark.parametrize("workers", ["auto", 1, 8])
def test_build_and_verify_runner_applies_pytest_xdist_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, workers: object
) -> None:
    module = load_build_and_verify_module()
    runner = module._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "pytest-workers",
                        "command": [sys.executable, "-m", "pytest", "tests"],
                        "pytestXdistWorkers": workers,
                        "inputs": [],
                    }
                ]
            },
        },
    )
    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)
    calls = []

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs.get("env")))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(
        runner.importlib.util,
        "find_spec",
        lambda name: object() if name == "xdist" else None,
    )

    result = runner.run_verify(project, runner=fake_runner, full=True)

    assert result == 0
    assert calls[0][0] == [sys.executable, "-m", "pytest", "-n", str(workers), "tests"]
    if workers == "auto":
        assert calls[0][1]["PYTEST_XDIST_AUTO_NUM_WORKERS"] == "4"
    else:
        assert calls[0][1] is None


def test_build_and_verify_runner_keeps_existing_pytest_xdist_auto_worker_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_build_and_verify_module()
    runner = module._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "pytest-workers",
                        "command": [sys.executable, "-m", "pytest", "tests"],
                        "pytestXdistWorkers": "auto",
                        "inputs": [],
                    }
                ]
            },
        },
    )
    calls = []

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs.get("env")))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setenv("PYTEST_XDIST_AUTO_NUM_WORKERS", "7")
    monkeypatch.setattr(
        runner.importlib.util,
        "find_spec",
        lambda name: object() if name == "xdist" else None,
    )

    result = runner.run_verify(project, runner=fake_runner, full=True)

    assert result == 0
    assert calls == [([sys.executable, "-m", "pytest", "-n", "auto", "tests"], None)]


@pytest.mark.parametrize("workers", [0, -1, True, "8", ""])
def test_build_and_verify_runner_rejects_invalid_pytest_xdist_workers(
    tmp_path: Path, workers: object
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "bad-workers",
                        "command": [sys.executable, "-m", "pytest"],
                        "pytestXdistWorkers": workers,
                        "inputs": [],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 1
    assert 'pytestXdistWorkers must be "auto" or positive integer' in result.stderr


def test_build_and_verify_runner_rejects_pytest_xdist_workers_on_non_pytest_command(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "not-pytest",
                        "command": [sys.executable, "-m", "unittest"],
                        "pytestXdistWorkers": 8,
                        "inputs": [],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 1
    assert "pytestXdistWorkers requires pytest command" in result.stderr


def test_build_and_verify_runner_requires_xdist_for_pytest_xdist_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    module = load_build_and_verify_module()
    runner = module._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "pytest-workers",
                        "command": [sys.executable, "-m", "pytest"],
                        "pytestXdistWorkers": "auto",
                        "inputs": [],
                    }
                ]
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
    assert "missing_dependency: pytest-workers: pytest-xdist is required" in captured.err


def test_build_and_verify_runner_full_verify_aggregates_missing_xdist_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    module = load_build_and_verify_module()
    runner = module._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "pytest-a",
                        "command": "python -m pytest -n 8 tests/a",
                        "checkParallel": True,
                        "inputs": [],
                    },
                    {
                        "id": "pytest-b",
                        "command": [sys.executable, "-m", "pytest", "-n", "8", "tests/b"],
                        "checkParallel": True,
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
def test_build_and_verify_runner_rejects_invalid_check_timeout_seconds(
    tmp_path: Path, timeout_seconds: object
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "invalid-timeout",
                        "command": command_that_logs("invalid-timeout"),
                        "timeoutSeconds": timeout_seconds,
                        "checkParallel": False,
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


def test_build_and_verify_runner_full_verify_reports_parallel_check_timeout(
    tmp_path: Path, capsys
) -> None:
    module = load_build_and_verify_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "timeoutSeconds": 1,
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "checkParallel": True, "inputs": []},
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


def test_build_and_verify_runner_full_verify_reports_parallel_check_exception(
    tmp_path: Path, capsys
) -> None:
    module = load_build_and_verify_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "checkParallel": True, "inputs": []},
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


def test_build_and_verify_runner_full_verify_reports_keyboard_interrupt_from_parallel_check(
    tmp_path: Path, capsys
) -> None:
    module = load_build_and_verify_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "checkParallel": True, "inputs": []},
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


def test_build_and_verify_runner_full_verify_skips_serial_checks_after_parallel_interrupt(
    tmp_path: Path, capsys
) -> None:
    module = load_build_and_verify_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-a", "command": ["parallel-a"], "checkParallel": True, "inputs": []},
                    {"id": "serial-after-interrupt", "command": ["serial-after-interrupt"], "checkParallel": False, "inputs": []},
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


def test_build_and_verify_runner_full_verify_reports_serial_failure_after_parallel_pass(
    tmp_path: Path, capsys
) -> None:
    module = load_build_and_verify_module()
    project = tmp_path / "project"
    project.mkdir()
    cache_dir = project / ".build-and-verify" / "cache"
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-pass", "command": ["parallel-pass"], "checkParallel": True, "inputs": []},
                    {"id": "serial-fail", "command": ["serial-fail"], "checkParallel": False, "inputs": []},
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


def test_build_and_verify_cache_store_writes_temp_file_before_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_build_and_verify_module()
    runner = module._runner()
    project = tmp_path / "project"
    project.mkdir()
    cache_dir = project / ".build-and-verify" / "cache"
    path_type = type(project)
    original_write_text = path_type.write_text

    def tracking_write_text(self, *args, **kwargs):
        assert self.name != "cache-key.json"
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "write_text", tracking_write_text)

    runner._cache_store(project, "cache-key", {"id": "cache-check"})

    assert read_json(cache_dir / "cache-key.json") == {"status": "passed", "id": "cache-check"}


def test_build_and_verify_runner_reads_changed_files_with_single_git_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_build_and_verify_module()
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


def test_build_and_verify_runner_reads_git_status_rename_and_copy_destinations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_build_and_verify_module()
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


def test_build_and_verify_user_level_skill_path_runs_verify_without_git(
    tmp_path: Path,
) -> None:
    user_skill = tmp_path / "user-skills" / "build-and-verify"
    shutil.copytree(PLUGIN_ROOT / "skills" / "build-and-verify", user_skill)
    script = user_skill / "scripts" / "build_and_verify.py"
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
        project / ".build-and-verify" / "config.json",
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


def test_build_and_verify_non_git_project_uses_filesystem_scan(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "docs").mkdir()
    (project / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    (project / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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


def test_build_and_verify_runner_uses_passed_result_cache(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "cached.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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

    first = run_check(project, "verify", changed_files=["src/cached.py"])
    cache_files = list((project / ".build-and-verify" / "cache").glob("*.json"))
    second = run_check(project, "verify", changed_files=["src/cached.py"])

    assert first.returncode == 0, first.stdout + first.stderr
    assert len(cache_files) == 1
    assert read_json(cache_files[0]) == {"status": "passed", "id": "cache-check"}
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: cache-check" in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "cache-check"
    ]


def test_build_and_verify_runner_full_verify_ignores_existing_default_cache(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify" / "cache").mkdir(parents=True)
    (project / "src").mkdir()
    (project / "src" / "cached.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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

    default = run_check(project, "verify", changed_files=["src/cached.py"])
    cached_default = run_check(project, "verify", changed_files=["src/cached.py"])
    full = run_check(project, "verify", "--full", changed_files=["src/cached.py"])

    assert default.returncode == 0, default.stdout + default.stderr
    assert cached_default.returncode == 0, cached_default.stdout + cached_default.stderr
    assert full.returncode == 0, full.stdout + full.stderr
    assert "cache-hit: full-ignores-fast-cache" in cached_default.stdout
    assert "cache-hit:" not in full.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "full-ignores-fast-cache",
        "full-ignores-fast-cache",
    ]


def test_build_and_verify_runner_full_verify_refreshes_cache_for_default_verify(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify" / "cache").mkdir(parents=True)
    (project / "src").mkdir()
    (project / "src" / "cached.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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

    full = run_check(project, "verify", "--full", changed_files=["src/cached.py"])
    default = run_check(project, "verify", changed_files=["src/cached.py"])

    assert full.returncode == 0, full.stdout + full.stderr
    assert default.returncode == 0, default.stdout + default.stderr
    assert "cache-hit:" not in full.stdout
    assert "cache-hit: full-primes-cache" in default.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "full-primes-cache"
    ]


def test_build_and_verify_runner_cache_misses_when_input_is_deleted(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    input_file = project / "src" / "input.txt"
    input_file.write_text("base\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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

    input_file.write_text("changed\n", encoding="utf-8")
    first = run_check(project, "verify", changed_files=["src/input.txt"])
    input_file.unlink()
    second = run_check(project, "verify", changed_files=["src/input.txt"])

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit:" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "deleted-input",
        "deleted-input",
    ]


def test_build_and_verify_runner_default_cache_key_tracks_glob_path_contents(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    app_path = project / "src" / "app.txt"
    app_path.write_text("first\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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

    first = run_check(project, "verify", changed_files=["src/app.txt"])
    app_path.write_text("second\n", encoding="utf-8")
    second = run_check(project, "verify", changed_files=["src/app.txt"])

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: glob-default-inputs" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "glob-default-inputs",
        "glob-default-inputs",
    ]


def test_build_and_verify_runner_default_check_cache_key_tracks_changed_files(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    write_json(
        project / ".build-and-verify" / "config.json",
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

    (project / "a.txt").write_text("a\n", encoding="utf-8")
    first = run_check(project, "verify", changed_files=["a.txt"])
    (project / "b.txt").write_text("b\n", encoding="utf-8")
    second = run_check(project, "verify", changed_files=["b.txt"])

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: default-check" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "default-check",
        "default-check",
    ]


def test_build_and_verify_pathless_check_skips_clean_git_worktree(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    write_json(
        project / ".build-and-verify" / "config.json",
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

    verify = run_check(project, "verify", changed_files=[])

    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "checked:" in verify.stdout
    assert "checked: pathless" not in verify.stdout
    assert not (project / "run.log").exists()


def test_build_and_verify_runner_default_check_cache_key_tracks_dirty_file_contents(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    dirty_file = project / "dirty.txt"
    dirty_file.write_text("base\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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

    dirty_file.write_text("first\n", encoding="utf-8")
    first = run_check(project, "verify", changed_files=["dirty.txt"])
    dirty_file.write_text("second\n", encoding="utf-8")
    second = run_check(project, "verify", changed_files=["dirty.txt"])

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: default-dirty-check" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "default-dirty-check",
        "default-dirty-check",
    ]


def test_build_and_verify_runner_reports_missing_list_command_without_traceback(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "missing-command",
                        "command": ["missing-build-and-verify-executable"],
                        "paths": ["src/app.txt"],
                        "inputs": ["src/app.txt"],
                    }
                ]
            },
        },
    )

    result = run_check(
        project,
        "verify",
        runner=FakeRunner({("missing-build-and-verify-executable",): FileNotFoundError()}),
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "command_not_found: missing-command" in output
    assert "Traceback" not in output


def test_build_and_verify_runner_verify_reports_missing_config_without_traceback(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / ".build-and-verify" / "config.json").unlink()

    result = run_check(project, "verify")
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "missing_config: .build-and-verify/config.json" in output
    assert "status: failed" in result.stdout
    assert "Traceback" not in output


@pytest.mark.parametrize(
    "invalid_input",
    [
        "../outside.txt",
        "{outside}",
    ],
)
def test_build_and_verify_runner_rejects_inputs_outside_project(
    tmp_path: Path, invalid_input: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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


def test_build_and_verify_runner_full_verify_rejects_inputs_outside_project(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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
def test_build_and_verify_runner_cache_key_changes_with_check_contract(
    tmp_path: Path, mutation: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify" / "cache").mkdir(parents=True)
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

    write_json(project / ".build-and-verify" / "config.json", config())
    first = run_check(project, "verify", changed_files=["src/sample.py"])
    cached = run_check(project, "verify", changed_files=["src/sample.py"])

    assert first.returncode == 0, first.stdout + first.stderr
    cache_files = list((project / ".build-and-verify" / "cache").glob("*.json"))
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

    write_json(project / ".build-and-verify" / "config.json", changed_config)
    changed = run_check(project, "verify", changed_files=["src/sample.py"])

    assert changed.returncode == 0, changed.stdout + changed.stderr
    assert "cache-hit:" not in changed.stdout
    assert f"checked: {expected_checked}" in changed.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "base",
        expected_log,
    ]


def test_build_and_verify_runner_cache_miss_does_not_fall_back_to_full(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "sample.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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

    result = run_check(project, "verify", changed_files=["src/sample.txt"])

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
        Path(".build-and-verify/cache/noise.txt"),
        Path(".git/noise.txt"),
        Path("src/__pycache__/noise.pyc"),
    ],
)
def test_build_and_verify_runner_directory_hash_ignores_generated_paths(
    tmp_path: Path, excluded_relative: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "sample.txt").write_text("changed\n", encoding="utf-8")
    run_log = project / ".build-and-verify" / "cache" / "directory-hash-runs.txt"
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "directory-hash",
                        "command": command_that_logs(
                            "directory-hash",
                            ".build-and-verify/cache/directory-hash-runs.txt",
                        ),
                        "paths": ["src/**"],
                        "inputs": ["."],
                    }
                ]
            },
        },
    )

    first = run_check(project, "verify", changed_files=["src/sample.txt"])
    noise_path = project / excluded_relative
    noise_path.parent.mkdir(parents=True, exist_ok=True)
    noise_path.write_text("ignored\n", encoding="utf-8")
    second = run_check(project, "verify", changed_files=["src/sample.txt"])

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: directory-hash" in second.stdout
    assert run_log.read_text(encoding="utf-8").splitlines() == ["directory-hash"]


def test_build_and_verify_cache_key_covers_runtime_and_cache_versions() -> None:
    template = (
        PLUGIN_ROOT / "skills" / "build-and-verify" / "scripts" / "build_and_verify_runner.py"
    ).read_text(encoding="utf-8")

    assert '"cache_version": CACHE_VERSION' in template
    assert '"framework_version": FRAMEWORK_VERSION' in template
    assert '"python_version": platform.python_version()' in template


def test_build_and_verify_runner_does_not_cache_failed_results(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "fails.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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

    first = run_check(project, "verify", changed_files=["src/fails.py"])
    second = run_check(project, "verify", changed_files=["src/fails.py"])

    assert first.returncode != 0
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: fail-once" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "fail-once",
        "fail-once",
    ]


def test_build_and_verify_runner_no_check_does_not_fall_back_to_full(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    (project / "docs").mkdir()
    (project / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
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

    result = run_check(project, "verify", changed_files=["docs/guide.md"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "checked:" in result.stdout
    assert "full-not-run: true" in result.stdout
    assert not (project / "run.log").exists()


def test_build_and_verify_runner_reads_worktree_changed_files(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    write_json(
        project / ".build-and-verify" / "config.json",
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
    (project / "staged.txt").write_text("staged\n", encoding="utf-8")
    (project / "unstaged.txt").write_text("unstaged\n", encoding="utf-8")
    (project / "untracked.txt").write_text("untracked\n", encoding="utf-8")

    result = run_check(
        project,
        "verify",
        changed_files=["staged.txt", "unstaged.txt", "untracked.txt"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "checked: staged-check, unstaged-check, untracked-check" in result.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "staged-check",
        "unstaged-check",
        "untracked-check",
    ]
