"""校验用户级 agent-guard Skill（技能）安装和 Claude Junction（目录联接）。"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path


REQUIRED_SKILL_ITEMS = [
    "SKILL.md",
    "agents/openai.yaml",
    "references/architecture.md",
    "references/terminology.md",
    "references/template-index.md",
    "assets/templates/guard-profile/minimal/GUARD-MANIFEST.yaml",
    "assets/templates/guard-profile/minimal/target-model.yaml",
    "assets/templates/guard-profile/minimal/state-machine.yaml",
    "assets/templates/guard-profile/minimal/guard-points.yaml",
    "assets/templates/guard-profile/minimal/artifacts.yaml",
    "assets/templates/guard-profile/minimal/brief-template.md",
    "assets/templates/guard-profile/minimal/validation-plan.md",
    "scripts/init_project_guard.py",
    "scripts/init_user_guard.py",
    "scripts/extract_guard_model.py",
    "scripts/activate_guard.py",
    "scripts/run_guard_event.py",
    "scripts/validate_guard_profile.py",
    "scripts/install_agent_guard_plugin.py",
]

ENTRYPOINT_SKILL_NAMES = [
    "agent-guard-install",
    "agent-guard-init",
    "agent-guard-update",
    "agent-guard-run",
    "agent-guard-hooks",
]

ENTRYPOINT_REQUIRED_ITEMS = {
    "agent-guard-install": [
        "SKILL.md",
        "references/research-and-extract.md",
        "references/profile-draft.md",
    ],
    "agent-guard-init": [
        "SKILL.md",
        "references/init-flow.md",
        "references/init-boundaries.md",
    ],
    "agent-guard-update": [
        "SKILL.md",
        "references/runtime-update.md",
        "references/profile-sync.md",
    ],
    "agent-guard-run": [
        "SKILL.md",
        "references/activate.md",
        "references/brief.md",
        "references/events.md",
        "references/close.md",
    ],
    "agent-guard-hooks": [
        "SKILL.md",
        "references/hook-install.md",
        "references/hook-adapter.md",
        "references/hook-results.md",
    ],
}

ENTRYPOINT_DISALLOWED_RESOURCE_DIRS = ["scripts", "assets"]


@dataclass(frozen=True)
class LayoutCheck:
    status: str
    missing: list[str]


@dataclass(frozen=True)
class EntryPointCheck:
    status: str
    missing: list[str]
    unexpected_shared_dirs: list[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_source_skill() -> Path:
    return repo_root() / "plugins" / "agent-guard" / "skills" / "agent-guard"


def user_home() -> Path:
    return Path.home()


def default_user_skill() -> Path:
    return user_home() / ".agents" / "skills" / "agent-guard"


def default_claude_skill() -> Path:
    return user_home() / ".claude" / "skills" / "agent-guard"


def normalize(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    return Path(os.path.abspath(expanded))


def check_skill_layout(skill_path: Path) -> LayoutCheck:
    if not skill_path.exists():
        return LayoutCheck("missing", REQUIRED_SKILL_ITEMS.copy())
    if not skill_path.is_dir():
        return LayoutCheck("not_directory", REQUIRED_SKILL_ITEMS.copy())

    missing = [relative for relative in REQUIRED_SKILL_ITEMS if not (skill_path / relative).exists()]
    status = "complete" if not missing else "incomplete"
    return LayoutCheck(status, missing)


def check_entrypoint_layout(core_skill_path: Path) -> EntryPointCheck:
    skills_root = core_skill_path.parent
    missing: list[str] = []
    unexpected_shared_dirs: list[str] = []
    for skill_name in ENTRYPOINT_SKILL_NAMES:
        skill_dir = skills_root / skill_name
        for required_item in ENTRYPOINT_REQUIRED_ITEMS[skill_name]:
            if not (skill_dir / required_item).exists():
                missing.append(f"{skill_name}/{required_item}")
        for shared_dir in ENTRYPOINT_DISALLOWED_RESOURCE_DIRS:
            if (skill_dir / shared_dir).exists():
                unexpected_shared_dirs.append(f"{skill_name}/{shared_dir}")

    if not missing and not unexpected_shared_dirs:
        return EntryPointCheck("complete", missing, unexpected_shared_dirs)
    if all(not (skills_root / skill_name / "SKILL.md").exists() for skill_name in ENTRYPOINT_SKILL_NAMES):
        return EntryPointCheck("missing", missing, unexpected_shared_dirs)
    return EntryPointCheck("incomplete", missing, unexpected_shared_dirs)


def path_same(left: Path, right: Path) -> bool:
    try:
        return left.resolve(strict=False) == right.resolve(strict=False)
    except OSError:
        return False


def is_junction(path: Path) -> bool:
    checker = getattr(os.path, "isjunction", None)
    if checker is None:
        return False
    return bool(checker(path))


def junction_status(claude_skill: Path, expected_target: Path) -> tuple[str, str | None]:
    if not claude_skill.exists():
        return "missing", None
    if not claude_skill.is_dir():
        return "not_directory", None
    if not is_junction(claude_skill):
        return "not_junction", str(claude_skill.resolve(strict=False))

    actual_target = claude_skill.resolve(strict=False)
    if path_same(actual_target, expected_target):
        return "correct_target", str(actual_target)
    return "wrong_target", str(actual_target)


def print_layout(prefix: str, path: Path, check: LayoutCheck) -> None:
    print(f"{prefix}: {check.status}")
    print(f"{prefix}_path: {path}")
    if check.missing:
        print(f"{prefix}_missing:")
        for item in check.missing:
            print(f"  - {item}")


def print_entrypoints(prefix: str, core_skill_path: Path, check: EntryPointCheck) -> None:
    print(f"{prefix}: {check.status}")
    print(f"{prefix}_root: {core_skill_path.parent}")
    if check.missing:
        print(f"{prefix}_missing:")
        for item in check.missing:
            print(f"  - {item}")
    if check.unexpected_shared_dirs:
        print(f"{prefix}_unexpected_shared_dirs:")
        for item in check.unexpected_shared_dirs:
            print(f"  - {item}")


def print_safety() -> None:
    print("safety:")
    print("  project_guard_initialization: not_performed")
    print("  project_hooks: not_installed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验用户级 agent-guard 安装。")
    parser.add_argument("--source-skill", type=Path, default=default_source_skill(), help="源码仓库里的 agent-guard Skill（技能）路径")
    parser.add_argument("--user-skill", type=Path, default=default_user_skill(), help="用户级 agent-guard Skill（技能）安装路径")
    parser.add_argument("--claude-skill", type=Path, default=default_claude_skill(), help="Claude agent-guard Junction（目录联接）路径")
    args = parser.parse_args(argv)

    source_skill = normalize(args.source_skill)
    user_skill = normalize(args.user_skill)
    claude_skill = normalize(args.claude_skill)

    source_check = check_skill_layout(source_skill)
    user_check = check_skill_layout(user_skill)
    source_entrypoints = check_entrypoint_layout(source_skill)
    user_entrypoints = check_entrypoint_layout(user_skill)
    claude_status, claude_target = junction_status(claude_skill, user_skill)

    ok = (
        source_check.status == "complete"
        and source_entrypoints.status == "complete"
        and user_check.status == "complete"
        and user_entrypoints.status == "complete"
        and claude_status == "correct_target"
    )
    print(f"status: {'verified' if ok else 'issues'}")
    print_layout("source_skill", source_skill, source_check)
    print_entrypoints("source_entrypoints", source_skill, source_entrypoints)
    print_layout("user_skill", user_skill, user_check)
    print_entrypoints("user_entrypoints", user_skill, user_entrypoints)
    print(f"claude_junction: {claude_status}")
    print(f"claude_junction_path: {claude_skill}")
    print(f"expected_claude_target: {user_skill}")
    if claude_target is not None:
        print(f"actual_claude_target: {claude_target}")
    print_safety()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
