from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


REPO_ROOT = Path(__file__).resolve().parents[1]
Runner = Callable[..., subprocess.CompletedProcess[Any]]


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing_file: {path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid_json: {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"invalid_json_object: {path}"
    return data, None


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def _manifest_paths(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return []


def _check_manifest(
    manifest_path: Path,
    plugin_name: str,
    plugin_dir: Path,
    name_error_code: str,
    path_fields: tuple[str, ...],
) -> list[str]:
    errors: list[str] = []
    manifest, load_error = _load_json(manifest_path)
    if load_error is not None:
        return [load_error]
    assert manifest is not None

    for field in ("name", "version", "description", "skills"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            errors.append(f"invalid_manifest_field: {manifest_path}: {field}")

    if manifest.get("name") != plugin_name:
        errors.append(f"{name_error_code}: {manifest_path}: expected {plugin_name!r}")

    for field in path_fields:
        if field not in manifest:
            continue
        paths = _manifest_paths(manifest[field])
        if not paths:
            errors.append(f"invalid_manifest_path_field: {manifest_path}: {field}")
            continue
        for raw_path in paths:
            candidate = plugin_dir / raw_path
            if not _inside(candidate, plugin_dir) or not candidate.exists():
                errors.append(f"missing_manifest_path: {manifest_path}: {field}: {raw_path}")

    return errors


def _marketplace_plugins(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    marketplace_path = root / ".claude-plugin" / "marketplace.json"
    data, load_error = _load_json(marketplace_path)
    if load_error is not None:
        return [], [load_error]
    assert data is not None

    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        return [], [f"invalid_marketplace_plugins: {marketplace_path}"]
    valid_plugins: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, plugin in enumerate(plugins):
        if isinstance(plugin, dict):
            valid_plugins.append(plugin)
        else:
            errors.append(f"invalid_marketplace_entry: {marketplace_path}: index={index}")
    return valid_plugins, errors


def _projection_plugins(root: Path) -> tuple[list[str], list[str]]:
    projection_path = root / ".release-flow" / "projection.yaml"
    if yaml is None:
        return [], ["missing_dependency: PyYAML"]
    try:
        data = yaml.safe_load(projection_path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return [], [f"missing_file: {projection_path}"]
    except yaml.YAMLError as exc:
        return [], [f"invalid_yaml: {projection_path}: {exc}"]

    plugins: list[str] = []
    generators = data.get("generators") if isinstance(data, dict) else None
    if not isinstance(generators, list):
        return plugins, [f"invalid_projection_generators: {projection_path}"]

    for generator in generators:
        if not isinstance(generator, dict) or generator.get("type") != "codex-marketplace":
            continue
        raw_plugins = generator.get("plugins", [])
        if not isinstance(raw_plugins, list):
            return plugins, [f"invalid_projection_plugins: {projection_path}"]
        plugins.extend(plugin for plugin in raw_plugins if isinstance(plugin, str))
    return plugins, []


def _relative_file_set(root: Path) -> set[Path]:
    if not root.exists():
        return set()
    return {path.relative_to(root) for path in root.rglob("*") if path.is_file()}


def check_guard_profile_template_mirrors(root: Path) -> list[str]:
    left = root / "plugins" / "agent-guard" / "assets" / "templates" / "guard-profile"
    right = (
        root
        / "plugins"
        / "agent-guard"
        / "skills"
        / "agent-guard"
        / "assets"
        / "templates"
        / "guard-profile"
    )

    errors: list[str] = []
    left_files = _relative_file_set(left)
    right_files = _relative_file_set(right)
    if left_files != right_files:
        errors.append(
            "guard_profile_template_files_mismatch: "
            f"left_only={sorted(str(path) for path in left_files - right_files)} "
            f"right_only={sorted(str(path) for path in right_files - left_files)}"
        )

    for relative_path in sorted(left_files & right_files):
        if (left / relative_path).read_bytes() != (right / relative_path).read_bytes():
            errors.append(f"guard_profile_template_mismatch: {relative_path}")

    return errors


def run_build(root: Path = REPO_ROOT, runner: Runner = subprocess.run) -> list[str]:
    errors: list[str] = []
    plugins, marketplace_errors = _marketplace_plugins(root)
    errors.extend(marketplace_errors)

    validate_commands: list[list[str]] = [["claude", "plugin", "validate", "."]]
    marketplace_names: list[str] = []
    seen_marketplace_names: set[str] = set()

    for index, plugin in enumerate(plugins):
        name = plugin.get("name")
        source = plugin.get("source")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"invalid_marketplace_plugin: index={index}: name")
            continue
        if name in seen_marketplace_names:
            errors.append(f"duplicate_marketplace_plugin: {name}")
        seen_marketplace_names.add(name)
        if not isinstance(source, str) or not source.strip():
            errors.append(f"invalid_marketplace_plugin: {name}: source")
            continue
        marketplace_names.append(name)

        source_path = Path(source)
        plugin_dir = root / source_path
        if source_path.is_absolute() or not _inside(plugin_dir, root):
            errors.append(f"source_outside_repo: {name}: {source}")
            continue

        validate_commands.append(["claude", "plugin", "validate", str(plugin_dir)])
        errors.extend(
            _check_manifest(
                plugin_dir / ".claude-plugin" / "plugin.json",
                name,
                plugin_dir,
                "claude_manifest_name_mismatch",
                ("skills",),
            )
        )
        errors.extend(
            _check_manifest(
                plugin_dir / ".codex-plugin" / "plugin.json",
                name,
                plugin_dir,
                "codex_manifest_name_mismatch",
                ("skills", "hooks", "assets"),
            )
        )

    missing_commands: set[str] = set()
    for command in validate_commands:
        try:
            result = runner(command, cwd=root, text=True, capture_output=True, check=False)
        except FileNotFoundError:
            command_name = command[0]
            if command_name not in missing_commands:
                errors.append(f"missing_command: {command_name}")
                missing_commands.add(command_name)
            continue
        if getattr(result, "returncode", 0) != 0:
            errors.append(f"claude_validate_failed: {' '.join(command)}")

    projection_plugins, projection_errors = _projection_plugins(root)
    errors.extend(projection_errors)
    duplicate_projection_plugins = sorted(
        {plugin for plugin in projection_plugins if projection_plugins.count(plugin) > 1}
    )
    for plugin in duplicate_projection_plugins:
        errors.append(f"duplicate_projection_plugin: {plugin}")

    if set(projection_plugins) != set(marketplace_names):
        errors.append(
            "projection_plugins_mismatch: "
            f"marketplace={sorted(marketplace_names)} projection={sorted(set(projection_plugins))}"
        )

    errors.extend(check_guard_profile_template_mirrors(root))
    return errors


def run_verify(root: Path = REPO_ROOT, runner: Runner = subprocess.run) -> int:
    result = runner(
        [sys.executable, "-m", "pytest"],
        cwd=root,
        text=True,
        capture_output=False,
        check=False,
    )
    return int(result.returncode)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    command = args[0] if args else "build"

    if command == "build":
        errors = run_build()
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("status: build checks passed")
        return 0
    if command == "verify":
        return run_verify()

    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
