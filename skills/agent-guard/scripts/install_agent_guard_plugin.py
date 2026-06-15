"""安装和验证 Agent Guard Plugin（代理守卫插件）。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PLUGIN_NAME = "agent-guard"
HOOK_NAMES = {"SessionStart", "PreToolUse"}
PACKAGE_ITEMS = [
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    "hooks/hooks.json",
    "scripts/hook_router.py",
    "scripts/guard_runtime",
    "skills/agent-guard/SKILL.md",
    "assets/templates",
]


@dataclass(frozen=True)
class PackageCheck:
    status: str
    missing: list[str]
    errors: list[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def normalize(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    return Path(os.path.abspath(expanded))


def default_plugin_source() -> Path:
    return repo_root() / "plugins" / PLUGIN_NAME


def default_codex_home() -> Path:
    return Path.home() / ".codex"


def default_claude_home() -> Path:
    return Path.home() / ".claude"


def default_codex_marketplace() -> Path:
    return default_codex_home() / "marketplace.json"


def default_claude_marketplace() -> Path:
    return default_claude_home() / "marketplace.json"


def plugin_target(home: Path) -> Path:
    return home / "plugins" / PLUGIN_NAME


def read_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"missing_json: {path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid_json: {path}: {exc}"


def collect_hook_commands(hooks: dict) -> list[str]:
    commands: list[str] = []
    for entries in hooks.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("command"), str):
                commands.append(entry["command"])
            if not isinstance(entry, dict):
                continue
            nested_hooks = entry.get("hooks", [])
            if not isinstance(nested_hooks, list):
                continue
            for hook in nested_hooks:
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    commands.append(hook["command"])
    return commands


def check_package(plugin_root: Path) -> PackageCheck:
    missing = [item for item in PACKAGE_ITEMS if not (plugin_root / item).exists()]
    errors: list[str] = []

    for manifest in [".codex-plugin/plugin.json", ".claude-plugin/plugin.json"]:
        data, error = read_json(plugin_root / manifest)
        if error is not None:
            errors.append(error)
        elif data.get("name") != PLUGIN_NAME:
            errors.append(f"invalid_manifest_name: {manifest}")

    hooks, error = read_json(plugin_root / "hooks" / "hooks.json")
    if error is not None:
        errors.append(error)
    elif set(hooks) != HOOK_NAMES:
        errors.append("invalid_hooks: expected SessionStart and PreToolUse only")
    else:
        commands = collect_hook_commands(hooks)
        if not commands:
            errors.append("invalid_hooks: missing hook commands")
        if not all("hook_router.py" in command.replace("\\", "/") for command in commands):
            errors.append("invalid_hooks: command must reference scripts/hook_router.py")
        if not any("PLUGIN_ROOT" in command for command in commands):
            errors.append("invalid_hooks: missing PLUGIN_ROOT command")
        if not any("CLAUDE_PLUGIN_ROOT" in command for command in commands):
            errors.append("invalid_hooks: missing CLAUDE_PLUGIN_ROOT command")
        if any("--profile" in command for command in commands):
            errors.append("invalid_hooks: command must not include --profile")

    status = "complete" if not missing and not errors else "incomplete"
    return PackageCheck(status, missing, errors)


def targets_for(target: str | None) -> list[str]:
    if target is None or target == "all":
        return ["codex", "claude"]
    return [target]


def copy_plugin(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def read_marketplace(path: Path) -> dict:
    if not path.exists():
        return {"plugins": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        data["plugins"] = []
    return data


def write_marketplace(path: Path, kind: str, source: Path, install_path: Path) -> None:
    data = read_marketplace(path)
    plugins = [entry for entry in data["plugins"] if entry.get("name") != PLUGIN_NAME]
    plugins.append(
        {
            "name": PLUGIN_NAME,
            "kind": kind,
            "source": str(source),
            "install_path": str(install_path),
        }
    )
    data["plugins"] = plugins
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def marketplace_has_entry(path: Path, install_path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = read_marketplace(path)
    except json.JSONDecodeError:
        return False
    expected = str(install_path)
    return any(entry.get("name") == PLUGIN_NAME and entry.get("install_path") == expected for entry in data["plugins"])


def print_package_check(prefix: str, check: PackageCheck) -> None:
    print(f"{prefix}: {check.status}")
    if check.missing:
        print(f"{prefix}_missing:")
        for item in check.missing:
            print(f"  - {item}")
    if check.errors:
        print(f"{prefix}_errors:")
        for error in check.errors:
            print(f"  - {error}")


def print_safety() -> None:
    print("safety:")
    print("  guard_profile: not_modified")
    print("  project_hooks: not_installed")
    print("  git_config: not_modified")


def run_dry_run(args: argparse.Namespace) -> int:
    target_names = targets_for(args.target)
    print("status: dry_run")
    print(f"plugin_source: {args.plugin_source}")
    if "codex" in target_names:
        print(f"codex_plugin_target: {plugin_target(args.codex_home)}")
        print(f"codex_marketplace: {args.codex_marketplace}")
    if "claude" in target_names:
        print(f"claude_plugin_target: {plugin_target(args.claude_home)}")
        print(f"claude_marketplace: {args.claude_marketplace}")
    print("action: would_install_plugin_and_update_marketplace")
    print_safety()
    return 0


def run_install(args: argparse.Namespace) -> int:
    if args.target is None:
        print("install requires --target", file=sys.stderr)
        return 2
    if not args.authorize_install:
        print("install requires --authorize-install", file=sys.stderr)
        return 2

    source_check = check_package(args.plugin_source)
    if source_check.status != "complete":
        print("status: issues")
        print_package_check("source_package", source_check)
        print_safety()
        return 1

    target_names = targets_for(args.target)
    if "codex" in target_names:
        codex_target = plugin_target(args.codex_home)
        copy_plugin(args.plugin_source, codex_target)
        write_marketplace(args.codex_marketplace, "codex", args.plugin_source, codex_target)
    if "claude" in target_names:
        claude_target = plugin_target(args.claude_home)
        copy_plugin(args.plugin_source, claude_target)
        write_marketplace(args.claude_marketplace, "claude", args.plugin_source, claude_target)

    print("status: installed")
    if "codex" in target_names:
        print(f"codex_plugin_target: {plugin_target(args.codex_home)}")
        print(f"codex_marketplace: {args.codex_marketplace}")
    if "claude" in target_names:
        print(f"claude_plugin_target: {plugin_target(args.claude_home)}")
        print(f"claude_marketplace: {args.claude_marketplace}")
    print_safety()
    return 0


def verify_target(name: str, install_path: Path, marketplace: Path) -> bool:
    check = check_package(install_path)
    print_package_check(f"{name}_install", check)
    entry_status = "present" if marketplace_has_entry(marketplace, install_path) else "missing"
    print(f"{name}_marketplace_entry: {entry_status}")
    return check.status == "complete" and entry_status == "present"


def run_verify(args: argparse.Namespace) -> int:
    target_names = targets_for(args.target)
    source_check = check_package(args.plugin_source)
    results: list[bool] = [source_check.status == "complete"]

    print_package_check("source_package", source_check)
    if "codex" in target_names:
        results.append(verify_target("codex", plugin_target(args.codex_home), args.codex_marketplace))
    if "claude" in target_names:
        results.append(verify_target("claude", plugin_target(args.claude_home), args.claude_marketplace))
    print_safety()
    ok = all(results)
    print(f"status: {'verified' if ok else 'issues'}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="安装和验证 Agent Guard Plugin（代理守卫插件）。")
    parser.add_argument("mode", choices=["dry-run", "install", "verify"], help="操作模式。")
    parser.add_argument("--plugin-source", type=Path, default=default_plugin_source(), help="插件源码目录。")
    parser.add_argument("--target", choices=["codex", "claude", "all"], help="安装或验证目标。")
    parser.add_argument("--codex-home", type=Path, default=default_codex_home(), help="Codex home（主目录）。")
    parser.add_argument("--claude-home", type=Path, default=default_claude_home(), help="Claude home（主目录）。")
    parser.add_argument("--codex-marketplace", type=Path, default=default_codex_marketplace(), help="Codex marketplace（市场）文件。")
    parser.add_argument("--claude-marketplace", type=Path, default=default_claude_marketplace(), help="Claude marketplace（市场）文件。")
    parser.add_argument("--authorize-install", action="store_true", help="明确授权写入插件安装位置。")
    return parser


def normalize_args(args: argparse.Namespace) -> argparse.Namespace:
    for name in ["plugin_source", "codex_home", "claude_home", "codex_marketplace", "claude_marketplace"]:
        setattr(args, name, normalize(getattr(args, name)))
    return args


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = normalize_args(parser.parse_args(list(argv) if argv is not None else None))

    if args.mode == "dry-run":
        return run_dry_run(args)
    if args.mode == "install":
        return run_install(args)
    return run_verify(args)


if __name__ == "__main__":
    sys.exit(main())
