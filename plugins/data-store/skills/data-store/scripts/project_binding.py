"""Connect the installed skill to one shared, project-local entry."""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import uuid


def is_link(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or getattr(info, "st_reparse_tag", 0) == 0xA0000003


def skill_root():
    root = Path(__file__).resolve().parents[1]
    for relative in ("SKILL.md", "scripts/data_store.py", "requirements.txt"):
        if not (root / relative).is_file():
            raise ValueError(f"安装不完整：{root / relative}")
    return root


def project_entry(project):
    project = project.resolve(strict=True)
    if not project.is_dir():
        raise ValueError("项目必须是现有目录")
    entry = project / ".local" / "skills" / "data-store"
    for parent in (project / ".local", entry.parent):
        if is_link(parent) or (parent.exists() and not parent.is_dir()):
            raise ValueError(f"接入父目录不能是链接或文件：{parent}")
    return entry


def make_link(entry, target):
    if os.name == "nt":
        # LiteralPath / environment arguments avoid shell interpolation of paths.
        env = dict(os.environ, DATA_STORE_ENTRY=str(entry), DATA_STORE_TARGET=str(target))
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "$ErrorActionPreference='Stop'; New-Item -ItemType Junction "
             "-Path $env:DATA_STORE_ENTRY -Target $env:DATA_STORE_TARGET | Out-Null"],
            env=env, text=True, capture_output=True,
        )
        if result.returncode:
            raise OSError(result.stderr.strip())
    else:
        entry.symlink_to(target, target_is_directory=True)


def remove_link(entry):
    if not is_link(entry):
        raise ValueError(f"仅能清理链接：{entry}")
    # Never recurse into the installed skill, including on Python 3.10.
    if entry.is_symlink():
        entry.unlink()
    else:
        entry.rmdir()


def ignore_binding(entry):
    ignore = entry.parent / ".gitignore"
    if is_link(ignore) or (ignore.exists() and not ignore.is_file()):
        raise ValueError(f"忽略文件不能是链接或目录：{ignore}")
    rules = ("/data-store", "/.data-store-new-*", "/.data-store-old-*", "/.gitignore")
    existing = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    missing = [rule for rule in rules if rule not in existing.splitlines()]
    if missing:
        with ignore.open("a", encoding="utf-8") as stream:
            stream.write(("\n" if existing and not existing.endswith("\n") else "")
                         + "\n".join(missing) + "\n")


def update_link(entry, target, expected):
    if not is_link(entry) or entry.resolve() != expected.resolve():
        raise ValueError("现有来源与 --from 不符，保留原入口")
    if entry.resolve() == target:
        return
    suffix = uuid.uuid4().hex
    staged = entry.with_name(f".data-store-new-{suffix}")
    saved = entry.with_name(f".data-store-old-{suffix}")
    moved = False
    try:
        make_link(staged, target)
        if staged.resolve(strict=True) != target:
            raise ValueError("新来源检查失败，保留原入口")
        if entry.resolve() != expected.resolve():
            raise ValueError("操作期间现有来源变化，保留原入口")
        entry.rename(saved)
        moved = True
        try:
            staged.rename(entry)
            if entry.resolve(strict=True) != target:
                raise ValueError("切换后检查失败")
        except (OSError, ValueError):
            if os.path.lexists(entry):
                remove_link(entry)
            saved.rename(entry)
            moved = False
            raise
        remove_link(saved)
        moved = False
    finally:
        if os.path.lexists(staged):
            remove_link(staged)
        if moved:
            print(f"旧入口保留在 {saved}，请核对后恢复", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("connect", "check", "update"))
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--from", dest="expected", type=Path)
    args = parser.parse_args()
    if (args.command == "update") != (args.expected is not None):
        parser.error("仅 update 必须提供 --from 原来源")
    try:
        target = skill_root()
        entry = project_entry(args.project)
        if args.command == "update":
            update_link(entry, target, args.expected)
        elif os.path.lexists(entry):
            if not is_link(entry):
                raise ValueError(f"入口被普通目录或文件占用，保留原内容：{entry}")
            if entry.resolve() != target:
                raise ValueError(f"入口来源不同，请核对后使用 update：{entry.resolve()}")
        elif args.command == "check":
            raise ValueError(f"项目尚未接入：{entry}")
        else:
            entry.parent.mkdir(parents=True, exist_ok=True)
            ignore_binding(entry)
            make_link(entry, target)
        if entry.resolve(strict=True) != target:
            raise ValueError("接入检查失败")
        print(json.dumps({"entry": str(entry), "target": str(target)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
