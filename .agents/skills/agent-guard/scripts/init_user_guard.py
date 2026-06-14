"""初始化用户级 Guard Profile（守卫画像）。"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from validate_guard_profile import ValidationIssue, profile_has_deny_permissions, validate_profile


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


def normalize_user_profile(profile_dir: Path, profile_id: str) -> None:
    manifest_path = profile_dir / "GUARD-MANIFEST.yaml"
    manifest = load_yaml_mapping(manifest_path)
    manifest["guard_profile_id"] = profile_id
    manifest.setdefault("user_initialization", {})
    manifest["user_initialization"].update(
        {
            "scope": "user",
            "hook_installation": "not_installed",
        }
    )
    dump_yaml(manifest_path, manifest)


def write_user_notes(profile_dir: Path, profile_id: str) -> None:
    path = profile_dir / "user-scope.md"
    path.write_text(
        f"""# User Guard Profile（用户级守卫画像）

Guard Profile（守卫画像）：{profile_id}

- 存放范围：用户级。
- Hook（钩子）未安装。
- 用户级初始化只写 Guard Profile（守卫画像）配置，不初始化目标项目，也不修改目标项目 hook。
""",
        encoding="utf-8",
    )


def print_plan(
    user_guard_root: Path,
    source_profile: Path,
    target_profile: Path,
    profile_id: str,
    has_deny_permissions: bool,
) -> None:
    print("status: dry_run")
    print("authorization: missing")
    print(f"user_guard_root: {user_guard_root}")
    print(f"source_profile: {source_profile}")
    print(f"profile: {target_profile}")
    print(f"guard_profile_id: {profile_id}")
    print(f"deny_permissions: {'present' if has_deny_permissions else 'absent'}")
    print("changes:")
    print(f"  - target: {target_profile}")
    print("    action: would_write")
    print("project_guard_initialization: not_performed")
    print("project_hooks: not_installed")
    if has_deny_permissions:
        print("next: 加 --authorize-init 和 --authorize-deny-permissions 才会写入含 `deny` 状态权限的用户级 Guard Profile（守卫画像）。")
    else:
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
    parser.add_argument("--authorize-init", action="store_true", help="明确授权写入用户级 Guard Profile（守卫画像）")
    parser.add_argument(
        "--authorize-deny-permissions",
        action="store_true",
        help="明确授权初始化含 `deny` 状态权限的 Guard Profile（守卫画像）",
    )
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
    except ValueError as exc:
        print("status: error")
        print(f"message: {exc}")
        return 2

    target_profile = user_guard_root / profile_id
    if target_profile.resolve() == source_profile:
        print("status: error")
        print("message: 输出 Guard Profile（守卫画像）不能和输入草案目录相同。")
        return 2

    has_deny_permissions = profile_has_deny_permissions(source_profile)
    if not args.authorize_init:
        print_plan(user_guard_root, source_profile, target_profile, profile_id, has_deny_permissions)
        return 0

    if has_deny_permissions and not args.authorize_deny_permissions:
        print("status: authorization_required")
        print("authorization: deny_permissions_missing")
        print(f"profile: {source_profile}")
        print("message: 该 Guard Profile（守卫画像）包含会返回 `deny` 的状态权限，初始化前必须额外授权。")
        print("next: 如果确认要初始化这些拒绝规则，请重试并加 --authorize-deny-permissions。")
        return 1

    if target_profile.exists() and args.on_existing == "abort":
        print("status: exists")
        print(f"profile: {target_profile}")
        print("action: abort")
        print("next: 使用 --on-existing update 或 --on-existing overwrite 明确处理已有配置。")
        return 1

    user_guard_root.mkdir(parents=True, exist_ok=True)
    copy_profile(source_profile, target_profile, args.on_existing)
    normalize_user_profile(target_profile, profile_id)
    write_user_notes(target_profile, profile_id)

    _checked, output_issues = validate_profile(target_profile)
    if output_issues:
        print_validation_failure(target_profile, output_issues)
        return 1

    print("status: initialized")
    print(f"user_guard_root: {user_guard_root}")
    print(f"profile: {target_profile}")
    print("project_guard_initialization: not_performed")
    print("project_hooks: not_installed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
