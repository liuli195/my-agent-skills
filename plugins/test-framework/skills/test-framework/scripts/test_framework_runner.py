from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any
from collections.abc import Callable


FRAMEWORK_VERSION = "0.1.0"
CACHE_VERSION = "1"
Runner = Callable[..., subprocess.CompletedProcess[Any]]


class ConfigError(Exception):
    pass


def _load_config(project: Path) -> dict[str, Any]:
    config_path = project / ".test-framework" / "config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError("missing_config: .test-framework/config.json") from None
    except json.JSONDecodeError as error:
        raise ConfigError(
            f"invalid_config: .test-framework/config.json: {error.msg}"
        ) from None
    if not isinstance(config, dict):
        raise ConfigError(
            "invalid_config: .test-framework/config.json: root must be object"
        )
    for section in ("build", "verify"):
        section_config = config.get(section, {})
        if not isinstance(section_config, dict):
            raise ConfigError(
                f"invalid_config: .test-framework/config.json: {section} must be object"
            )
        checks = section_config.get("checks", [])
        if not isinstance(checks, list):
            raise ConfigError(
                f"invalid_config: .test-framework/config.json: {section}.checks must be list"
            )
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                raise ConfigError(
                    "invalid_config: .test-framework/config.json: "
                    f"{section}.checks[{index}] must be object"
                )
    return config


def _normalize_path(path: str | Path) -> str:
    return Path(path).as_posix().strip("/")


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


def _is_excluded_relative(relative: str) -> bool:
    parts = relative.split("/")
    return (
        ".git" in parts
        or "__pycache__" in parts
        or relative == ".test-framework/cache"
        or relative.startswith(".test-framework/cache/")
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
    if raw_path.anchor or ".." in Path(relative).parts:
        raise ValueError(f"invalid_input_path: {input_path}")
    path = project / relative
    if not _is_relative_to_project(project, path):
        raise ValueError(f"invalid_input_path: {input_path}")
    return relative, path


def _hash_input(project: Path, input_path: str) -> dict[str, Any]:
    relative, path = _validate_project_relative_input(project, input_path)
    if not path.exists():
        return {"path": relative, "missing": True}
    if path.is_file():
        return {"path": relative, "type": "file", "sha256": _hash_file(path)}
    if path.is_dir():
        files: list[dict[str, str]] = []
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
        "check_id": check.get("id"),
        "command": check.get("command"),
        "inputs": [_hash_input(project, item) for item in inputs],
        "config": hashlib.sha256(_stable_json(config).encode("utf-8")).hexdigest(),
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _cache_path(project: Path, key: str) -> Path:
    return project / ".test-framework" / "cache" / f"{key}.json"


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
    path.write_text(
        _stable_json({"status": "passed", "id": check.get("id")}) + "\n",
        encoding="utf-8",
    )


def _run_check(project: Path, check: dict[str, Any], runner: Runner) -> int:
    command = check.get("command")
    if not command:
        print(f"missing_command: {check.get('id')}", file=sys.stderr)
        return 1
    use_shell = isinstance(command, str)
    try:
        result = runner(
            command,
            cwd=project,
            check=False,
            text=True,
            capture_output=True,
            shell=use_shell,
        )
    except FileNotFoundError:
        executable = command[0] if isinstance(command, list) else str(command)
        print(f"command_not_found: {check.get('id')}: {executable}", file=sys.stderr)
        return 1
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return int(result.returncode)


def _checks(config: dict[str, Any], section: str) -> list[dict[str, Any]]:
    return list(config.get(section, {}).get("checks", []))


def _check_ids(checks: list[dict[str, Any]]) -> str:
    return ", ".join(str(check.get("id")) for check in checks)


def _config_error(error: ConfigError) -> int:
    print(str(error), file=sys.stderr)
    print("status: failed")
    return 1


def run_build(project: Path, runner: Runner = subprocess.run) -> int:
    try:
        config = _load_config(project)
    except ConfigError as error:
        return _config_error(error)
    checks = _checks(config, "build")
    failures = 0
    for check in checks:
        if _run_check(project, check, runner) != 0:
            failures += 1
    print(f"checked: {_check_ids(checks)}")
    if failures:
        print("status: failed")
        return 1
    print("status: passed")
    return 0


def run_verify(
    project: Path,
    runner: Runner = subprocess.run,
    *,
    full: bool = False,
) -> int:
    try:
        config = _load_config(project)
    except ConfigError as error:
        return _config_error(error)
    checks = _checks(config, "verify")
    changed_files = _changed_files(project)
    selected = checks if full else _selected_checks(checks, changed_files)
    failures = 0
    for check in selected:
        try:
            key = _cache_key(project, config, check, changed_files)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            failures += 1
            continue
        if full:
            result = _run_check(project, check, runner)
            if result == 0:
                _cache_store(project, key, check)
            else:
                failures += 1
            continue
        if _cache_load(project, key):
            print(f"cache-hit: {check.get('id')}")
            continue
        result = _run_check(project, check, runner)
        if result == 0:
            _cache_store(project, key, check)
        else:
            failures += 1
    print(f"checked: {_check_ids(selected)}")
    print(f"full-not-run: {str(not full).lower()}")
    if failures:
        print("status: failed")
        return 1
    print("status: passed")
    return 0
