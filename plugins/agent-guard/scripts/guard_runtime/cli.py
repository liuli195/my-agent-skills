"""Agent Guard Plugin Runtime（插件运行时）CLI。"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from core import (
    close_instance,
    create_instance,
    instance_table,
    list_active_instances,
    load_instance,
    now_iso,
    profile_dir,
    read_session_observation,
    run_brief,
    run_state_completed,
    target_table,
    write_latest_brief,
    write_focus_binding,
)
from global_command_guards import load_profile_artifacts, render_template, resolve_artifact_path


RESERVED_EVIDENCE_FIELDS = {
    "schema_version",
    "status",
    "producer",
    "profile_id",
    "artifact_id",
    "subject_type",
    "subject_id",
    "head_ref",
    "head_ref_short",
    "created_at",
}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def print_json(body: dict[str, Any]) -> None:
    json.dump(body, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def safe_segment(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) or value in {".", ".."}:
        raise ValueError("unsafe_segment")
    return value


def git_head_and_clean(project: Path) -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if head.returncode != 0 or not head.stdout.strip():
        raise ValueError("git_repository_required")
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if status.returncode != 0:
        raise ValueError("git_status_failed")
    if status.stdout:
        raise ValueError("dirty_worktree")
    return head.stdout.strip()


def load_business_fields(path: Path) -> dict[str, Any]:
    try:
        fields = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("business_fields_invalid_json") from error
    if not isinstance(fields, dict):
        raise ValueError("business_fields_object_required")
    return fields


def atomic_write_evidence(path: Path, body: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(body, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def record_evidence(args: argparse.Namespace) -> int:
    project = args.project.resolve()
    user_home = args.user_home.resolve()
    for value in (args.profile, args.artifact, args.subject_id):
        safe_segment(value)

    profile = profile_dir(project, args.profile, user_home, args.profile_source)
    if not profile.is_dir():
        raise ValueError("profile_not_found")
    registry = profile / "artifacts.yaml"
    if not registry.is_file():
        raise ValueError("artifact_registry_missing")
    try:
        artifacts = load_profile_artifacts(profile)
    except yaml.YAMLError as error:
        raise ValueError("artifact_registry_invalid") from error
    artifact = artifacts.get(args.artifact)
    if artifact is None:
        raise ValueError("artifact_not_found")
    if artifact.get("owner") != "agent-guard" or artifact.get("type") != "json":
        raise ValueError("artifact_not_guard_defined")

    head = git_head_and_clean(project)
    values = {
        "profile_id": args.profile,
        "artifact_id": args.artifact,
        "subject_id": args.subject_id,
        "git_head": head,
        "git_head_short": head[:12],
    }
    rendered, missing = render_template(str(artifact.get("path", "")), values)
    if missing:
        raise ValueError(f"evidence_path_template_value_missing: {','.join(missing)}")
    if (project / Path(rendered)).is_symlink():
        raise ValueError("unsafe_evidence_path")
    path = resolve_artifact_path(project, user_home, "project", rendered)

    fields = load_business_fields(args.business_fields_file)
    conflicts = sorted(RESERVED_EVIDENCE_FIELDS & set(fields))
    if conflicts:
        raise ValueError(f"reserved_field_conflict: {','.join(conflicts)}")
    body = {
        "schema_version": "guard-evidence/v1",
        "status": "pass",
        "producer": args.producer,
        "profile_id": args.profile,
        "artifact_id": args.artifact,
        "subject_type": args.subject_type,
        "subject_id": args.subject_id,
        "head_ref": head,
        "head_ref_short": head[:12],
        "created_at": now_iso(),
        **fields,
    }
    atomic_write_evidence(path, body)
    print_json(
        {
            "status": "evidence_recorded",
            "head_ref": head,
            "head_ref_short": head[:12],
            "path": path.relative_to(project).as_posix(),
        }
    )
    return 0


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


def add_record_evidence_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--user-home", type=Path, default=Path.home())
    parser.add_argument("--profile-source", required=True, choices=["project", "user"])
    parser.add_argument("--profile", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--subject-type", required=True)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--producer", required=True)
    parser.add_argument("--business-fields-file", required=True, type=Path)


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

    evidence_parser = subparsers.add_parser("record-evidence", help="记录通用 Guard Evidence（守卫证据）。")
    add_record_evidence_arguments(evidence_parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if raw_argv and raw_argv[0] == "record-evidence":
        try:
            parser = JsonArgumentParser(prog=f"{Path(sys.argv[0]).name} record-evidence")
            add_record_evidence_arguments(parser)
            return record_evidence(parser.parse_args(raw_argv[1:]))
        except (ValueError, json.JSONDecodeError, OSError, yaml.YAMLError) as error:
            print_json({"status": "failed", "reason": str(error)})
            return 1

    args = build_parser().parse_args(raw_argv)
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
