from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


FRAMEWORK_VERSION = "0.1.0"
CACHE_VERSION = "1"
REPO_ROOT = Path(__file__).resolve().parents[1]
Runner = Callable[..., subprocess.CompletedProcess[Any]]


def _load_config(root: Path) -> dict[str, Any]:
    config_path = root / ".test-framework" / "config.json"
    return json.loads(config_path.read_text(encoding="utf-8"))


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


def _git_names(root: Path, *args: str) -> list[str] | None:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
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


def _all_project_files(root: Path) -> list[str]:
    files: list[str] = []
    for current_root, dirs, names in os.walk(root):
        current_path = Path(current_root)
        kept_dirs: list[str] = []
        for name in dirs:
            relative = (current_path / name).relative_to(root).as_posix()
            if not _is_excluded_relative(relative):
                kept_dirs.append(name)
        dirs[:] = kept_dirs
        for name in names:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if not _is_excluded_relative(relative):
                files.append(relative)
    return sorted(files)


def _changed_files(root: Path) -> list[str]:
    commands = [
        ("diff", "--name-only", "--cached"),
        ("diff", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ]
    names: list[str] = []
    any_git_command_succeeded = False
    for command in commands:
        result = _git_names(root, *command)
        if result is None:
            continue
        any_git_command_succeeded = True
        names.extend(result)
    if not any_git_command_succeeded:
        names = _all_project_files(root)
    return _dedupe(names)


def _path_matches(pattern: str, changed_file: str) -> bool:
    pattern = _normalize_path(pattern)
    changed_file = _normalize_path(changed_file)
    if not pattern:
        return False
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return changed_file == prefix or changed_file.startswith(prefix + "/")
    if pattern.endswith("/"):
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


def _is_relative_to_project(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _validate_project_relative_input(root: Path, input_path: str) -> tuple[str, Path]:
    raw_path = Path(input_path)
    relative = _normalize_path(input_path)
    if raw_path.anchor or ".." in Path(relative).parts:
        raise ValueError(f"invalid_input_path: {input_path}")
    path = root / relative
    if not _is_relative_to_project(root, path):
        raise ValueError(f"invalid_input_path: {input_path}")
    return relative, path


def _hash_input(root: Path, input_path: str) -> dict[str, Any]:
    relative, path = _validate_project_relative_input(root, input_path)
    if not path.exists():
        return {"path": relative, "missing": True}
    if path.is_file():
        return {"path": relative, "type": "file", "sha256": _hash_file(path)}
    if path.is_dir():
        files: list[dict[str, str]] = []
        for current_root, dirs, names in os.walk(path):
            current_path = Path(current_root)
            kept_dirs: list[str] = []
            for name in dirs:
                child_relative = (current_path / name).relative_to(root).as_posix()
                if not _is_excluded_relative(child_relative):
                    kept_dirs.append(name)
            dirs[:] = kept_dirs
            for name in sorted(names):
                file_path = current_path / name
                child_relative = file_path.relative_to(root).as_posix()
                if _is_excluded_relative(child_relative):
                    continue
                if not _is_relative_to_project(root, file_path):
                    raise ValueError(f"invalid_input_path: {child_relative}")
                files.append({"path": child_relative, "sha256": _hash_file(file_path)})
        return {
            "path": relative,
            "type": "directory",
            "files": sorted(files, key=lambda item: item["path"]),
        }
    return {"path": relative, "type": "other"}


def _default_cache_inputs(root: Path, paths: list[str]) -> list[str]:
    matched: list[str] = []
    for pattern in paths:
        normalized = _normalize_path(pattern)
        if Path(pattern).anchor or ".." in Path(normalized).parts:
            raise ValueError(f"invalid_input_path: {pattern}")
        matched.extend(
            relative
            for relative in _all_project_files(root)
            if _path_matches(normalized, relative)
        )
    return _dedupe(matched)


def _cache_key(
    root: Path,
    config: dict[str, Any],
    check: dict[str, Any],
    changed_files: list[str] | None = None,
) -> str:
    if "inputs" in check and check.get("inputs") is not None:
        inputs = check.get("inputs") or []
    else:
        paths = check.get("paths") or []
        if paths:
            inputs = _default_cache_inputs(root, paths)
        else:
            inputs = changed_files if changed_files is not None else _changed_files(root)
    payload = {
        "cache_version": CACHE_VERSION,
        "framework_version": FRAMEWORK_VERSION,
        "python_version": platform.python_version(),
        "check_id": check.get("id"),
        "command": check.get("command"),
        "inputs": [_hash_input(root, item) for item in inputs],
        "config": hashlib.sha256(_stable_json(config).encode("utf-8")).hexdigest(),
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _cache_path(root: Path, key: str) -> Path:
    return root / ".test-framework" / "cache" / f"{key}.json"


def _cache_load(root: Path, key: str) -> bool:
    path = _cache_path(root, key)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return data.get("status") == "passed"


def _cache_store(root: Path, key: str, check: dict[str, Any]) -> None:
    path = _cache_path(root, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _stable_json({"status": "passed", "id": check.get("id")}) + "\n",
        encoding="utf-8",
    )


def _run_check(root: Path, check: dict[str, Any], runner: Runner) -> int:
    command = check.get("command")
    if not command:
        print(f"missing_command: {check.get('id')}", file=sys.stderr)
        return 1
    use_shell = isinstance(command, str)
    try:
        result = runner(
            command,
            cwd=root,
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


def run_build(root: Path = REPO_ROOT, runner: Runner = subprocess.run) -> int:
    config = _load_config(root)
    checks = _checks(config, "build")
    failures = 0
    for check in checks:
        if _run_check(root, check, runner) != 0:
            failures += 1
    print(f"checked: {_check_ids(checks)}")
    if failures:
        print("status: failed")
        return 1
    print("status: passed")
    return 0


def run_verify(
    root: Path = REPO_ROOT,
    runner: Runner = subprocess.run,
    *,
    full: bool = False,
) -> int:
    config = _load_config(root)
    checks = _checks(config, "verify")
    changed_files = _changed_files(root)
    selected = checks if full else _selected_checks(checks, changed_files)
    failures = 0
    for check in selected:
        if full:
            if _run_check(root, check, runner) != 0:
                failures += 1
            continue
        try:
            key = _cache_key(root, config, check, changed_files)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            failures += 1
            continue
        if _cache_load(root, key):
            print(f"cache-hit: {check.get('id')}")
            continue
        result = _run_check(root, check, runner)
        if result == 0:
            _cache_store(root, key, check)
        else:
            failures += 1
    print(f"checked: {_check_ids(selected)}")
    print(f"full-not-run: {str(not full).lower()}")
    if failures:
        print("status: failed")
        return 1
    print("status: passed")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="check.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--full", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "build":
        return run_build(REPO_ROOT)
    if args.command == "verify":
        return run_verify(REPO_ROOT, full=args.full)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
