"""初始化用户级 Guard Profile（守卫画像）。"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from validate_guard_profile import ValidationIssue, validate_profile


SAFE_MODES = {"record", "warn"}
ALL_MODES = {"record", "warn", "block"}
PROFILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path} 不是有效 YAML（YAML 配置格式）：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是 YAML mapping（YAML 映射）。")
    return data


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def validate_profile_id(profile_id: str) -> str:
    normalized = profile_id.strip()
    if not PROFILE_ID_PATTERN.fullmatch(normalized):
        raise ValueError("Guard Profile（守卫画像）ID 只能使用 ASCII 字母、数字、点、下划线和连字符，且不能包含路径分隔符。")
    return normalized


def read_profile_id(profile_dir: Path) -> str:
    manifest = load_yaml_mapping(profile_dir / "GUARD-MANIFEST.yaml")
    profile_id = manifest.get("guard_profile_id")
    if not isinstance(profile_id, str):
        raise ValueError("GUARD-MANIFEST.yaml 缺少有效 `guard_profile_id`。")
    return validate_profile_id(profile_id)


def resolve_initial_mode(profile_dir: Path, requested_mode: str | None, authorize_blocking: bool) -> str:
    if requested_mode == "block" and authorize_blocking:
        return "block"
    if requested_mode in SAFE_MODES:
        return requested_mode

    manifest = load_yaml_mapping(profile_dir / "GUARD-MANIFEST.yaml")
    mode = manifest.get("mode")
    if mode == "block" and authorize_blocking:
        return "block"
    if isinstance(mode, str) and mode in SAFE_MODES:
        return mode
    return "warn"


def print_validation_failure(profile: Path, issues: list[ValidationIssue]) -> None:
    print("status: validation_failed")
    print(f"profile: {profile}")
    print("issues:")
    for issue in issues:
        print(f"  - category: {issue.category}")
        print(f"    field: {issue.field}")
        print(f"    message: {issue.message}")
        print(f"    fix: {issue.fix}")


def validate_source_profile(profile: Path) -> bool:
    _checked, issues = validate_profile(profile)
    if issues:
        print_validation_failure(profile, issues)
        return False
    return True


def copy_profile(source_profile: Path, target_profile: Path, on_existing: str) -> None:
    if target_profile.exists() and on_existing == "overwrite":
        shutil.rmtree(target_profile)
    if target_profile.exists() and on_existing == "update":
        shutil.copytree(source_profile, target_profile, dirs_exist_ok=True)
        return
    shutil.copytree(source_profile, target_profile)


def normalize_user_profile(profile_dir: Path, profile_id: str, mode: str) -> None:
    manifest_path = profile_dir / "GUARD-MANIFEST.yaml"
    manifest = load_yaml_mapping(manifest_path)
    manifest["guard_profile_id"] = profile_id
    manifest["mode"] = mode
    manifest.setdefault("user_initialization", {})
    manifest["user_initialization"].update(
        {
            "scope": "user",
            "hook_installation": "not_installed",
            "blocking_mode": "enabled" if mode == "block" else "not_enabled",
            "mode": mode,
        }
    )
    dump_yaml(manifest_path, manifest)

    if mode == "block":
        return

    guard_points_path = profile_dir / "guard-points.yaml"
    guard_points_doc = load_yaml_mapping(guard_points_path)
    guard_points = guard_points_doc.get("guard_points")
    if isinstance(guard_points, list):
        for guard_point in guard_points:
            if not isinstance(guard_point, dict):
                continue
            for field in ["mode", "on_fail", "on_error"]:
                if guard_point.get(field) == "block":
                    guard_point[field] = mode
    dump_yaml(guard_points_path, guard_points_doc)


def write_user_notes(profile_dir: Path, profile_id: str, mode: str) -> None:
    path = profile_dir / "user-scope.md"
    path.write_text(
        f"""# User Guard Profile（用户级守卫画像）

Guard Profile（守卫画像）：{profile_id}

- 存放范围：用户级。
- 初始模式：`{mode}`。
- Hook（钩子）未安装。
- blocking mode（阻断模式）：{'enabled' if mode == 'block' else 'not_enabled'}。
- 用户级初始化只写 Guard Profile（守卫画像）配置，不初始化目标项目，也不修改目标项目 hook。
""",
        encoding="utf-8",
    )


def print_plan(user_guard_root: Path, source_profile: Path, target_profile: Path, profile_id: str, mode: str) -> None:
    print("status: dry_run")
    print("authorization: missing")
    print(f"user_guard_root: {user_guard_root}")
    print(f"source_profile: {source_profile}")
    print(f"profile: {target_profile}")
    print(f"guard_profile_id: {profile_id}")
    print(f"mode: {mode}")
    print("changes:")
    print(f"  - target: {target_profile}")
    print("    action: would_write")
    print("project_guard_initialization: not_performed")
    print("project_hooks: not_installed")
    print(f"blocking_mode: {'enabled' if mode == 'block' else 'not_enabled'}")
    print("next: 加 --authorize-init 才会写入用户级 Guard Profile（守卫画像）。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="初始化用户级 Guard Profile（守卫画像）。")
    parser.add_argument("--profile", type=Path, required=True, help="已校验 Guard Profile（守卫画像）草案目录")
    parser.add_argument(
        "--user-guard-root",
        type=Path,
        default=Path.home() / ".agents" / "guards",
        help="用户级 Guard Profile（守卫画像）根目录",
    )
    parser.add_argument("--guard-profile-id", help="覆盖输出 Guard Profile（守卫画像）ID")
    parser.add_argument("--mode", choices=sorted(ALL_MODES), help="初始化模式；block（阻断）必须同时加 --authorize-blocking")
    parser.add_argument("--authorize-init", action="store_true", help="明确授权写入用户级 Guard Profile（守卫画像）")
    parser.add_argument("--authorize-blocking", action="store_true", help="明确授权初始化为 blocking mode（阻断模式）")
    parser.add_argument(
        "--on-existing",
        choices=["abort", "overwrite", "update"],
        default="abort",
        help="同名画像已存在时的处理方式，默认 abort（中止）",
    )
    args = parser.parse_args(argv)

    source_profile = args.profile.resolve()
    user_guard_root = args.user_guard_root.expanduser().resolve()

    if not validate_source_profile(source_profile):
        return 1

    try:
        source_profile_id = read_profile_id(source_profile)
        profile_id = validate_profile_id(args.guard_profile_id) if args.guard_profile_id else source_profile_id
        mode = resolve_initial_mode(source_profile, args.mode, args.authorize_blocking)
    except ValueError as exc:
        print("status: error")
        print(f"message: {exc}")
        return 2

    target_profile = user_guard_root / profile_id
    if target_profile.resolve() == source_profile:
        print("status: error")
        print("message: 输出 Guard Profile（守卫画像）不能和输入草案目录相同。")
        return 2

    if not args.authorize_init:
        print_plan(user_guard_root, source_profile, target_profile, profile_id, mode)
        return 0

    if target_profile.exists() and args.on_existing == "abort":
        print("status: exists")
        print(f"profile: {target_profile}")
        print("action: abort")
        print("next: 使用 --on-existing update 或 --on-existing overwrite 明确处理已有配置。")
        return 1

    user_guard_root.mkdir(parents=True, exist_ok=True)
    copy_profile(source_profile, target_profile, args.on_existing)
    normalize_user_profile(target_profile, profile_id, mode)
    write_user_notes(target_profile, profile_id, mode)

    _checked, output_issues = validate_profile(target_profile)
    if output_issues:
        print_validation_failure(target_profile, output_issues)
        return 1

    print("status: initialized")
    print(f"user_guard_root: {user_guard_root}")
    print(f"profile: {target_profile}")
    print(f"mode: {mode}")
    print("project_guard_initialization: not_performed")
    print("project_hooks: not_installed")
    print(f"blocking_mode: {'enabled' if mode == 'block' else 'not_enabled'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
