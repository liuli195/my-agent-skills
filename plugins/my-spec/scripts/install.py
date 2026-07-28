from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PLUGIN_ROOT / "skills" / "my-spec"
MARKER = ".my-spec-install.json"


class InstallError(RuntimeError):
    pass


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _expected_link(path: Path, target: Path) -> bool:
    if not _is_link(path):
        return False
    try:
        return path.resolve(strict=False) == target.resolve(strict=False)
    except OSError:
        return False


def _owned_install(path: Path) -> bool:
    if not path.is_dir() or _is_link(path):
        return False
    try:
        data = json.loads((path / MARKER).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data == {"installer": "my-spec", "format": 1}


def _create_directory_link(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except OSError as symlink_error:
        if os.name != "nt":
            raise InstallError(f"cannot_create_claude_link: {symlink_error}") from symlink_error
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "mklink failed"
        raise InstallError(f"cannot_create_claude_link: {detail}")


def install(agents_home: Path, claude_home: Path) -> None:
    target = agents_home / "skills" / "my-spec"
    claude_target = claude_home / "skills" / "my-spec"

    if _lexists(claude_target) and not _expected_link(claude_target, target):
        raise InstallError(f"claude_target_not_expected_link: {claude_target}")
    if _lexists(target) and not _owned_install(target):
        raise InstallError(f"agents_target_not_owned: {target}")
    if not SOURCE.is_dir():
        raise InstallError(f"missing_source: {SOURCE}")

    target.parent.mkdir(parents=True, exist_ok=True)
    claude_target.parent.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex
    stage = target.parent / f".my-spec-installing-{nonce}"
    backup = target.parent / f".my-spec-backup-{nonce}"
    had_target = _lexists(target)
    try:
        shutil.copytree(SOURCE, stage)
        (stage / MARKER).write_text(
            json.dumps({"installer": "my-spec", "format": 1}, indent=2) + "\n",
            encoding="utf-8",
        )
        if had_target:
            target.rename(backup)
        stage.rename(target)
        if not _lexists(claude_target):
            _create_directory_link(claude_target, target)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        if target.exists() and backup.exists():
            shutil.rmtree(target)
            backup.rename(target)
        elif not had_target and target.exists():
            shutil.rmtree(target)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install the my-spec shared skill")
    parser.add_argument("--agents-home", type=Path, default=Path.home() / ".agents")
    parser.add_argument("--claude-home", type=Path, default=Path.home() / ".claude")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        install(args.agents_home, args.claude_home)
    except (InstallError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"installed: {args.agents_home / 'skills' / 'my-spec'}")
    print(f"claude-link: {args.claude_home / 'skills' / 'my-spec'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
