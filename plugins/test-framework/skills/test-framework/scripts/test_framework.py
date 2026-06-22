"""Test Framework Plugin（测试框架插件）命令入口。"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _templates_root() -> Path:
    return _skill_root() / "assets" / "templates"


def _init_project(project: Path) -> int:
    target_files = {
        project / "scripts" / "check.py": _templates_root() / "scripts" / "check.py",
        project / ".test-framework" / "config.json": _templates_root()
        / "test-framework"
        / "config.json",
        project / ".test-framework" / ".gitignore": _templates_root()
        / "test-framework"
        / "gitignore",
    }

    for target in target_files:
        if target.exists():
            print(f"existing_file: {target}", file=sys.stderr)
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "init":
        return _init_project(Path(args.project).resolve())
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
