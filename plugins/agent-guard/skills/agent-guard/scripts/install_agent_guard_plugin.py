"""安装和验证 Agent Guard Plugin（代理守卫插件）。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PLUGIN_NAME = "agent-guard"
RELEASE_REF = "marketplace"
HOOK_NAMES = {"SessionStart", "PreToolUse"}
MANIFEST_ITEMS = {
    "codex": ".codex-plugin/plugin.json",
    "claude": ".claude-plugin/plugin.json",
}
ENTRYPOINT_REFERENCES = {
    "agent-guard-install": ["research-and-extract.md", "profile-draft.md"],
    "agent-guard-init": ["init-flow.md", "init-boundaries.md"],
    "agent-guard-update": ["runtime-update.md", "profile-sync.md"],
    "agent-guard-run": ["activate.md", "brief.md", "events.md", "close.md"],
}
PACKAGE_ITEMS = [
    *MANIFEST_ITEMS.values(),
    "hooks/hooks.json",
    "scripts/hook_router.py",
    "scripts/guard_runtime/cli.py",
    "scripts/guard_runtime/core.py",
    "skills/agent-guard/SKILL.md",
    "skills/agent-guard/references/architecture.md",
    "skills/agent-guard/references/template-index.md",
    "skills/agent-guard/references/terminology.md",
    "skills/agent-guard/scripts/activate_guard.py",
    "skills/agent-guard/scripts/render_guard_brief.py",
    "skills/agent-guard/scripts/run_guard_event.py",
    "skills/agent-guard/scripts/validate_guard_profile.py",
    "skills/agent-guard/assets/templates/guard-profile/minimal/GUARD-MANIFEST.yaml",
    "assets/templates/guard-profile/minimal/GUARD-MANIFEST.yaml",
]
for entrypoint, references in ENTRYPOINT_REFERENCES.items():
    PACKAGE_ITEMS.append(f"skills/{entrypoint}/SKILL.md")
    for reference in references:
        PACKAGE_ITEMS.append(f"skills/{entrypoint}/references/{reference}")


@dataclass(frozen=True)
class PackageCheck:
    status: str
    missing: list[str]
    errors: list[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


CODEX_REPO_MARKETPLACE = repo_root() / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = repo_root() / ".claude-plugin" / "marketplace.json"


def normalize(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    return Path(os.path.abspath(expanded))


def default_plugin_source() -> Path:
    return repo_root() / "plugins" / PLUGIN_NAME


def default_codex_personal_marketplace() -> Path:
    return Path.home() / ".agents" / "plugins" / "marketplace.json"


def default_claude_personal_marketplace() -> Path:
    return Path.home() / ".claude-plugin" / "marketplace.json"


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


def check_package(plugin_root: Path, target: str | None = None) -> PackageCheck:
    selected_manifests = [MANIFEST_ITEMS[item] for item in targets_for(target)]
    shared_items = [item for item in PACKAGE_ITEMS if item not in MANIFEST_ITEMS.values()]
    required_items = [*selected_manifests, *shared_items]
    missing = [item for item in required_items if not (plugin_root / item).exists()]
    errors: list[str] = []

    for manifest in selected_manifests:
        data, error = read_json(plugin_root / manifest)
        if error is not None:
            errors.append(error)
        elif data.get("name") != PLUGIN_NAME:
            errors.append(f"invalid_manifest_name: {manifest}")

    hooks_config, error = read_json(plugin_root / "hooks" / "hooks.json")
    if error is not None:
        errors.append(error)
    elif not isinstance(hooks_config, dict) or set(hooks_config) != {"hooks"} or not isinstance(hooks_config.get("hooks"), dict):
        errors.append("invalid_hooks: expected top-level hooks object")
    else:
        hooks = hooks_config["hooks"]
        if set(hooks) != HOOK_NAMES:
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


def scopes_for(scope: str | None) -> list[str]:
    if scope is None or scope == "all":
        return ["personal", "repo"]
    return [scope]


def codex_catalog_root() -> dict:
    return {"name": "agent-guard-marketplace", "interface": {"displayName": "Agent Guard"}, "plugins": []}


def claude_catalog_root() -> dict:
    return {"name": "agent-guard-marketplace", "owner": {"name": "Agent Guard"}, "plugins": []}


def catalog_root(target: str) -> dict:
    return codex_catalog_root() if target == "codex" else claude_catalog_root()


def codex_marketplace_entry() -> dict:
    return {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": "./plugins/agent-guard"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }


def claude_marketplace_entry() -> dict:
    return {
        "name": PLUGIN_NAME,
        "source": "./plugins/agent-guard",
        "description": "Guard workflow plugin for Codex and Claude agents",
    }


def expected_marketplace_entry(target: str) -> dict:
    return codex_marketplace_entry() if target == "codex" else claude_marketplace_entry()


def read_marketplace(path: Path, target: str) -> dict:
    if not path.exists():
        return catalog_root(target)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid_marketplace_catalog: {path}")
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not all(isinstance(entry, dict) for entry in plugins):
        raise ValueError(f"invalid_marketplace_plugins: {path}")
    return data


def write_marketplace(path: Path, target: str) -> None:
    data = read_marketplace(path, target)
    plugins = [entry for entry in data["plugins"] if entry.get("name") != PLUGIN_NAME]
    plugins.append(expected_marketplace_entry(target))
    data["plugins"] = plugins
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def marketplace_write_errors(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid_json: {path}: {exc}"]
    if not isinstance(data, dict):
        return [f"invalid_marketplace_catalog: {path}"]
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not all(isinstance(entry, dict) for entry in plugins):
        return [f"invalid_marketplace_plugins: {path}"]
    entries = [entry for entry in plugins if entry.get("name") == PLUGIN_NAME]
    if any("kind" in entry or "install_path" in entry for entry in entries):
        return [f"legacy_marketplace_entry: {path}"]
    return []


def marketplace_entry_status(path: Path, target: str) -> tuple[str, list[str]]:
    if not path.exists():
        return "missing", [f"missing_marketplace: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return "invalid", [f"invalid_json: {path}: {exc}"]
    if not isinstance(data, dict):
        return "invalid", [f"invalid_marketplace_catalog: {path}"]
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not all(isinstance(entry, dict) for entry in plugins):
        return "invalid", [f"invalid_marketplace_plugins: {path}"]
    entries = [entry for entry in plugins if entry.get("name") == PLUGIN_NAME]
    if not entries:
        return "missing", [f"missing_marketplace_entry: {path}"]
    if any("kind" in entry or "install_path" in entry for entry in entries):
        return "legacy", [f"legacy_marketplace_entry: {path}"]
    if len(entries) == 1 and entries[0] == expected_marketplace_entry(target):
        return "present", []
    return "invalid", [f"invalid_marketplace_entry: {path}"]


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
    print("safety: marketplace_catalog_only")
    print("safety:")
    print("  guard_profile: not_modified")
    print("  project_hooks: not_installed")
    print("  git_config: not_modified")


def catalog_paths(args: argparse.Namespace) -> dict[tuple[str, str], Path]:
    return {
        ("codex", "repo"): args.codex_repo_marketplace,
        ("claude", "repo"): args.claude_repo_marketplace,
        ("codex", "personal"): args.codex_personal_marketplace,
        ("claude", "personal"): args.claude_personal_marketplace,
    }


def run_dry_run(args: argparse.Namespace) -> int:
    print("status: dry_run")
    print(f"target: {args.target or 'all'}")
    print(f"scope: {args.scope or 'all'}")
    print(f"release_ref: {args.release_ref}")
    print(f"plugin_source: {args.plugin_source}")
    print(f"codex_repo_marketplace: {args.codex_repo_marketplace}")
    print(f"claude_repo_marketplace: {args.claude_repo_marketplace}")
    print(f"codex_personal_marketplace: {args.codex_personal_marketplace}")
    print(f"claude_personal_marketplace: {args.claude_personal_marketplace}")
    print("action: would_update_marketplace_catalogs")
    print_safety()
    return 0


def run_install(args: argparse.Namespace) -> int:
    if args.target is None:
        print("install requires --target", file=sys.stderr)
        return 2
    if args.scope is None:
        print("install requires --scope", file=sys.stderr)
        return 2
    if not args.authorize_install:
        print("install requires --authorize-install", file=sys.stderr)
        return 2

    source_check = check_package(args.plugin_source, args.target)
    if source_check.status != "complete":
        print("status: issues")
        print_package_check("source_package", source_check)
        print_safety()
        return 1

    paths = catalog_paths(args)
    install_errors: list[tuple[str, list[str]]] = []
    for target in targets_for(args.target):
        for scope in scopes_for(args.scope):
            label = f"{target}_{scope}_marketplace"
            errors = marketplace_write_errors(paths[(target, scope)])
            if errors:
                install_errors.append((label, errors))

    if install_errors:
        print("status: issues")
        for label, errors in install_errors:
            print(f"{label}: invalid")
            print(f"{label}_errors:")
            for error in errors:
                print(f"  - {error}")
        print_safety()
        return 1

    for target in targets_for(args.target):
        for scope in scopes_for(args.scope):
            write_marketplace(paths[(target, scope)], target)

    print("status: installed")
    print(f"target: {args.target}")
    print(f"scope: {args.scope}")
    print(f"release_ref: {args.release_ref}")
    print_safety()
    return 0


def verify_marketplace_entry(label: str, target: str, marketplace: Path) -> bool:
    status, errors = marketplace_entry_status(marketplace, target)
    print(f"{label}: {status}")
    if errors:
        print(f"{label}_errors:")
        for error in errors:
            print(f"  - {error}")
    return status == "present"


def run_verify(args: argparse.Namespace) -> int:
    source_check = check_package(args.plugin_source, args.target)
    results: list[bool] = [source_check.status == "complete"]

    print_package_check("source_package", source_check)
    paths = catalog_paths(args)
    for target in targets_for(args.target):
        for scope in scopes_for(args.scope):
            label = f"{target}_{scope}_marketplace_entry"
            results.append(verify_marketplace_entry(label, target, paths[(target, scope)]))
    print_safety()
    ok = all(results)
    print(f"status: {'verified' if ok else 'issues'}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="安装和验证 Agent Guard Plugin（代理守卫插件）。")
    parser.add_argument("mode", choices=["dry-run", "install", "verify"], help="操作模式。")
    parser.add_argument("--plugin-source", type=Path, default=default_plugin_source(), help="插件源码目录。")
    parser.add_argument("--target", choices=["codex", "claude", "all"], help="安装或验证目标。")
    parser.add_argument("--scope", choices=["personal", "repo", "all"], help="写入或验证范围。")
    parser.add_argument("--codex-repo-marketplace", type=Path, default=CODEX_REPO_MARKETPLACE, help="仓库级 Codex marketplace（市场）文件。")
    parser.add_argument("--claude-repo-marketplace", type=Path, default=CLAUDE_REPO_MARKETPLACE, help="仓库级 Claude marketplace（市场）文件。")
    parser.add_argument("--codex-personal-marketplace", type=Path, default=default_codex_personal_marketplace(), help="个人级 Codex marketplace（市场）文件。")
    parser.add_argument("--claude-personal-marketplace", type=Path, default=default_claude_personal_marketplace(), help="个人级 Claude marketplace（市场）文件。")
    parser.add_argument("--release-ref", default=RELEASE_REF, choices=[RELEASE_REF], help="发布引用。")
    parser.add_argument("--authorize-install", action="store_true", help="明确授权写入 marketplace catalog（市场目录）。")
    return parser


def normalize_args(args: argparse.Namespace) -> argparse.Namespace:
    for name in [
        "plugin_source",
        "codex_repo_marketplace",
        "claude_repo_marketplace",
        "codex_personal_marketplace",
        "claude_personal_marketplace",
    ]:
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
