"""Agent Guard Plugin Runtime（插件运行时）CLI。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from core import (
    close_instance,
    create_instance,
    instance_table,
    list_active_instances,
    load_instance,
    read_session_observation,
    run_brief,
    run_state_completed,
    target_table,
    write_latest_brief,
    write_focus_binding,
)


def print_json(body: dict[str, Any]) -> None:
    json.dump(body, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def activate(args: argparse.Namespace) -> int:
    observation, observation_path = read_session_observation(args.project, args.user_home, args.source, args.session_id)
    if observation is None:
        print_json(
            {
                "status": "session_observation_missing",
                "source": args.source,
                "session_id": args.session_id,
                "next": "activate 前确认 Plugin Hook（插件钩子）已启用、已信任，且当前会话已触发 SessionStart。",
            }
        )
        return 1

    instances = list_active_instances(args.project, args.profile, args.user_home, args.scope)
    if args.select_instance:
        selected = load_instance(args.project, args.profile, args.select_instance, args.user_home, args.scope)
        if selected is None or selected.get("status") != "active":
            print_json({"status": "instance_not_found", "profile_id": args.profile, "instance_id": args.select_instance})
            return 1
        state = selected
        resolution = "selected"
    elif args.create:
        state = create_instance(args.project, args.profile, args.title, args.description, args.user_home, args.scope)
        resolution = "created"
    else:
        print_json(
            {
                "status": "selection_required",
                "target_table": target_table(args.project, args.profile, args.user_home, args.scope),
                "instance_table": instance_table(instances),
            }
        )
        return 1

    binding_path, audit_path = write_focus_binding(args.project, args.user_home, args.source, args.session_id, args.scope, args.profile, state["instance_id"])
    brief = write_latest_brief(args.project, args.profile, state, audit_path=audit_path, user_home=args.user_home)
    print_json(
        {
            "status": "session_focus_bound",
            "resolution": resolution,
            "source": args.source,
            "session_id": args.session_id,
            "scope": args.scope,
            "profile_id": args.profile,
            "instance_id": state["instance_id"],
            "binding_path": str(binding_path),
            "audit_path": str(audit_path),
            "brief_path": brief["brief_path"],
            "brief_hash": brief["brief_hash"],
            "observation_path": str(observation_path),
            "target_table": target_table(args.project, args.profile, args.user_home, args.scope),
            "instance_table": instance_table(instances),
        }
    )
    return 0


def close_instance_command(args: argparse.Namespace) -> int:
    try:
        state = close_instance(args.project, args.profile, args.instance_id, args.user_home, args.scope)
    except ValueError:
        print_json({"status": "instance_not_found", "profile_id": args.profile, "instance_id": args.instance_id})
        return 1
    print_json({"status": "instance_closed", "profile_id": args.profile, "instance_id": state["instance_id"]})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent Guard Plugin Runtime（插件运行时）。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    activate_parser = subparsers.add_parser("activate", help="绑定当前 Session Focus Instance（会话焦点实例）。")
    activate_parser.add_argument("--project", type=Path, default=Path.cwd())
    activate_parser.add_argument("--user-home", type=Path, default=Path.home())
    activate_parser.add_argument("--source", required=True, choices=["codex", "claude"])
    activate_parser.add_argument("--session-id", required=True)
    activate_parser.add_argument("--scope", choices=["project", "user"], default="project")
    activate_parser.add_argument("--profile", required=True)
    activate_parser.add_argument("--create", action="store_true")
    activate_parser.add_argument("--title", default="新 Guard Instance（守卫实例）")
    activate_parser.add_argument("--description", default="")
    activate_parser.add_argument("--select-instance")

    close_parser = subparsers.add_parser("close-instance", help="关闭 Guard Instance（守卫实例）。")
    close_parser.add_argument("--project", type=Path, default=Path.cwd())
    close_parser.add_argument("--user-home", type=Path, default=Path.home())
    close_parser.add_argument("--scope", choices=["project", "user"], default="project")
    close_parser.add_argument("--profile", required=True)
    close_parser.add_argument("--instance-id", required=True)

    completed_parser = subparsers.add_parser("state-completed", help="推进当前 Session Focus Instance（会话焦点实例）的状态。")
    completed_parser.add_argument("--project", type=Path, default=Path.cwd())
    completed_parser.add_argument("--user-home", type=Path, default=Path.home())
    completed_parser.add_argument("--source", required=True, choices=["codex", "claude"])
    completed_parser.add_argument("--session-id", required=True)
    completed_parser.add_argument("--lock-timeout", type=float, default=30.0)

    brief_parser = subparsers.add_parser("brief", help="读取并注入当前 Session Focus Instance（会话焦点实例）的 Guard Brief（守卫简报）。")
    brief_parser.add_argument("--project", type=Path, default=Path.cwd())
    brief_parser.add_argument("--user-home", type=Path, default=Path.home())
    brief_parser.add_argument("--source", required=True, choices=["codex", "claude"])
    brief_parser.add_argument("--session-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.project = args.project.resolve()
    if hasattr(args, "user_home"):
        args.user_home = args.user_home.resolve()
    if args.command == "activate":
        return activate(args)
    if args.command == "close-instance":
        return close_instance_command(args)
    if args.command == "state-completed":
        body, code = run_state_completed(args.project, args.user_home, args.source, args.session_id, args.lock_timeout)
        print_json(body)
        return code
    if args.command == "brief":
        body, code = run_brief(args.project, args.user_home, args.source, args.session_id)
        print_json(body)
        return code
    raise AssertionError(args.command)


if __name__ == "__main__":
    sys.exit(main())
