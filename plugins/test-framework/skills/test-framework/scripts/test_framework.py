"""Test Framework Plugin（测试框架插件）命令入口。"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType


_RUNNER_MODULE: ModuleType | None = None


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _templates_root() -> Path:
    return _skill_root() / "assets" / "templates"


def _runner() -> ModuleType:
    global _RUNNER_MODULE
    if _RUNNER_MODULE is not None:
        return _RUNNER_MODULE
    runner_path = Path(__file__).resolve().with_name("test_framework_runner.py")
    spec = importlib.util.spec_from_file_location("test_framework_runner", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"missing_runner: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _RUNNER_MODULE = module
    return module


def _init_project(project: Path) -> int:
    target_files = {
        project / ".test-framework" / "config.json": _templates_root()
        / "test-framework"
        / "config.json",
        project / ".test-framework" / ".gitignore": _templates_root()
        / "test-framework"
        / "gitignore",
    }

    # Preflight before mkdir/copy so a failed init does not create framework artifacts.
    for target in target_files:
        if target.exists():
            print(f"existing_file: {target.relative_to(project).as_posix()}", file=sys.stderr)
            return 1

    project.mkdir(parents=True, exist_ok=True)
    for target, source in target_files.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (project / ".test-framework" / "cache").mkdir(parents=True, exist_ok=True)

    print("status: initialized")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="test_framework.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--project", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--project", default=".")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--project", default=".")
    verify_parser.add_argument("--full", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 2
    if args.command == "init":
        return _init_project(Path(args.project).resolve())
    if args.command == "build":
        return int(_runner().run_build(Path(args.project).resolve()))
    if args.command == "verify":
        return int(_runner().run_verify(Path(args.project).resolve(), full=args.full))
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
