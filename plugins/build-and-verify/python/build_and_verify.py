"""Build and Verify Plugin（构建与验证插件）命令入口。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType


_RUNNER_MODULE: ModuleType | None = None
RUNTIME_FILES = ("build_and_verify.py", "build_and_verify_runner.py")
VERSION_FILE = "version.json"
DEFAULT_CONFIG = {"version": 1, "build": {"checks": []}, "verify": {"checks": []}}
DEFAULT_GITIGNORE = "/cache/\n/runs/\n/backups/\n"


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _templates_root() -> Path:
    return _skill_root() / "assets" / "templates"


def _runtime_target(project: Path) -> Path:
    return project / ".build-and-verify" / "runtime"


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _runtime_metadata() -> dict[str, str]:
    manifest_path = _plugin_root() / ".codex-plugin" / "plugin.json"
    if manifest_path.is_file():
        try:
            version = str(json.loads(manifest_path.read_text(encoding="utf-8")).get("version") or "unknown")
            return {
                "plugin": "build-and-verify",
                "plugin_version": version,
                "runtime_version": version,
            }
        except json.JSONDecodeError:
            pass
    return {
        "plugin": "build-and-verify",
        "plugin_version": "unknown",
        "runtime_version": "unknown",
    }


def _load_config_file(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"missing_config_file: {path}") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid_config_file: {path}: {error.msg}") from None
    if not isinstance(data, dict):
        raise ValueError(f"invalid_config_file: {path}: root must be object")
    return data


def _merge_gitignore(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for entry in DEFAULT_GITIGNORE.splitlines():
        if entry not in lines:
            lines.append(entry)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _backup_config(config_target: Path, project: Path) -> Path:
    backup_dir = project / ".build-and-verify" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"config-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    shutil.copy2(config_target, backup)
    return backup


def _runner() -> ModuleType:
    global _RUNNER_MODULE
    if _RUNNER_MODULE is not None:
        return _RUNNER_MODULE
    runner_path = Path(__file__).resolve().with_name("build_and_verify_runner.py")
    spec = importlib.util.spec_from_file_location("build_and_verify_runner", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"missing_runner: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _RUNNER_MODULE = module
    return module


def _init_project(
    project: Path,
    *,
    config: Path | None = None,
    overwrite: bool = False,
) -> int:
    config_target = project / ".build-and-verify" / "config.json"
    gitignore_target = project / ".build-and-verify" / ".gitignore"
    try:
        confirmed_config = DEFAULT_CONFIG if config is None else _load_config_file(config)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    # Preflight before mkdir/copy so a failed init does not create framework artifacts.
    if not overwrite or config is None:
        for target in [config_target, gitignore_target]:
            if target.exists():
                print(f"existing_file: {target.relative_to(project).as_posix()}", file=sys.stderr)
                return 1

    project.mkdir(parents=True, exist_ok=True)
    config_target.parent.mkdir(parents=True, exist_ok=True)
    backup = _backup_config(config_target, project) if config_target.exists() else None
    _merge_gitignore(gitignore_target)
    config_target.write_text(
        json.dumps(confirmed_config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (project / ".build-and-verify" / "cache").mkdir(parents=True, exist_ok=True)

    if backup is not None:
        print(f"backup: {backup.relative_to(project).as_posix()}")
    print("status: initialized")
    return 0


def _legacy_runtime(project: Path) -> tuple[Path | None, bool]:
    runtime = _runtime_target(project)
    if not runtime.exists():
        return None, False
    if (
        not runtime.is_dir()
        or {path.name for path in runtime.iterdir()} != {*RUNTIME_FILES, VERSION_FILE}
        or not all(path.is_file() for path in runtime.iterdir())
    ):
        return runtime, False
    try:
        metadata = json.loads((runtime / VERSION_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return runtime, False
    required_metadata = {"plugin", "plugin_version", "runtime_version"}
    recognized = (
        isinstance(metadata, dict)
        and set(metadata) == required_metadata
        and metadata.get("plugin") == "build-and-verify"
        and all(
            isinstance(metadata.get(field), str) and metadata[field]
            for field in required_metadata
        )
    )
    return runtime, recognized


def _git(project: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=project, text=True, capture_output=True, check=False
        )
    except OSError:
        return None


def _migration_ready(project: Path) -> bool:
    status = _git(project, "status", "--porcelain")
    if status is None or status.returncode != 0:
        print("legacy_runtime_not_migrated: git_repository_required", file=sys.stderr)
        return False
    if status.stdout:
        print("legacy_runtime_not_migrated: git_worktree_not_clean", file=sys.stderr)
        return False
    return True


def _restore_runtime(project: Path, relative: str) -> None:
    _git(project, "restore", "--source=HEAD", "--staged", "--worktree", "--", relative)


def _only_runtime_deletions_staged(project: Path, relative: str) -> bool:
    staged = _git(project, "diff", "--cached", "--name-status", "-z")
    if staged is None or staged.returncode != 0:
        return False
    entries = staged.stdout.split("\0")
    pairs = zip(entries[::2], entries[1::2])
    allowed_prefix = relative.rstrip("/") + "/"
    return bool(entries[0]) and all(
        status == "D" and path.startswith(allowed_prefix)
        for status, path in pairs
        if status
    )


def _migrate_legacy_runtime(project: Path, runtime: Path) -> int:
    relative = runtime.relative_to(project).as_posix()
    if not _migration_ready(project):
        return 1
    removed = _git(project, "rm", "-r", "--", relative)
    if removed is None or removed.returncode != 0:
        _restore_runtime(project, relative)
        print("legacy_runtime_not_migrated: removal_failed", file=sys.stderr)
        return 1
    if not _only_runtime_deletions_staged(project, relative):
        _restore_runtime(project, relative)
        print("legacy_runtime_not_migrated: unexpected_staged_changes", file=sys.stderr)
        return 1
    committed = _git(
        project,
        "commit",
        "--only",
        "-m",
        "迁移：移除 Build and Verify 旧运行时",
        "--",
        relative,
    )
    if committed is not None and committed.returncode == 0:
        print("status: legacy-runtime-migrated")
        return 0
    _restore_runtime(project, relative)
    print("legacy_runtime_not_migrated: commit_failed", file=sys.stderr)
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build_and_verify.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--config")
    init_parser.add_argument("--overwrite", action="store_true")
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--project", default=".")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--project", default=".")
    verify_parser.add_argument("--full", action="store_true")
    verify_parser.add_argument("--base", dest="baseline")
    verify_parser.add_argument("--performance-report", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
        if (
            args.command == "verify"
            and args.performance_report
            and not args.full
        ):
            parser.error("--performance-report requires --full")
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 2
    if args.command == "init":
        return _init_project(
            Path(args.project).resolve(),
            config=Path(args.config).resolve() if args.config else None,
            overwrite=bool(args.overwrite),
        )
    if args.command == "build":
        return int(_runner().run_build(Path(args.project).resolve()))
    if args.command == "verify":
        project = Path(args.project).resolve()
        legacy_runtime, recognized_legacy_runtime = _legacy_runtime(project)
        if legacy_runtime is not None and not recognized_legacy_runtime:
            print("legacy_runtime_not_migrated: unrecognized_runtime", file=sys.stderr)
            return 1
        if legacy_runtime is not None and not _migration_ready(project):
            return 1
        result = int(
            _runner().run_verify(
                project,
                full=args.full,
                baseline=args.baseline,
                performance_report=args.performance_report,
                runtime_version=_runtime_metadata()["runtime_version"],
                synthetic_changed_paths=(
                    sorted(
                        path.relative_to(project).as_posix()
                        for path in legacy_runtime.iterdir()
                    )
                    if legacy_runtime is not None
                    else None
                ),
            )
        )
        if result != 0 or legacy_runtime is None:
            return result
        return _migrate_legacy_runtime(project, legacy_runtime)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
