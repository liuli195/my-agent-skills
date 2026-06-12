"""Hook（钩子）事件到标准 Guard envelope（信封）的适配器。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


CODEX_EVENT_TYPES = {
    "UserPromptSubmit": "codex.user_prompt_submit",
    "SubagentStart": "codex.subagent_start",
    "SubagentStop": "codex.subagent_stop",
    "PreToolUse": "codex.pre_tool_use",
    "PostToolUse": "codex.post_tool_use",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json_text(text: str, label: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} 不是有效 JSON（JSON 格式）：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} 顶层必须是 JSON object（JSON 对象）。")
    return data


def load_payload(path: Path | None) -> dict[str, Any]:
    if path is not None:
        return load_json_text(path.read_text(encoding="utf-8"), str(path))
    return load_json_text(sys.stdin.read(), "stdin")


def profile_dir(project: Path, profile_id: str) -> Path:
    return project / ".agents" / "guards" / profile_id


def load_hook_bindings(project: Path, profile_id: str) -> list[dict[str, Any]]:
    path = profile_dir(project, profile_id) / "hook-bindings.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    bindings = data.get("hook_bindings")
    if not isinstance(bindings, list):
        return []
    return [binding for binding in bindings if isinstance(binding, dict)]


def binding_trigger_values(binding: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for field in ["trigger_event", "codex_event", "git_event", "hook_event"]:
        value = binding.get(field)
        if isinstance(value, str):
            values.add(value)
    trigger = binding.get("trigger")
    if isinstance(trigger, dict):
        for field in ["event", "name", "type"]:
            value = trigger.get(field)
            if isinstance(value, str):
                values.add(value)
    trigger_events = binding.get("trigger_events")
    if isinstance(trigger_events, list):
        values.update(value for value in trigger_events if isinstance(value, str))
    return values


def matching_binding(
    project: Path,
    profile_id: str,
    source: str,
    trigger_event: str,
) -> dict[str, Any] | None:
    for binding in load_hook_bindings(project, profile_id):
        if binding.get("source") != source:
            continue
        triggers = binding_trigger_values(binding)
        if trigger_event in triggers:
            return binding
    return None


def mapped_event_type(
    project: Path,
    profile_id: str,
    source: str,
    trigger_event: str,
    default_event_type: str,
) -> tuple[str, str | None]:
    binding = matching_binding(project, profile_id, source, trigger_event)
    if binding is None:
        return default_event_type, None
    event_type = binding.get("event_type")
    return event_type if isinstance(event_type, str) and event_type else default_event_type, binding.get("id")


def git_value(project: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", "-C", str(project), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def context_from_payload(project: Path, payload: dict[str, Any]) -> dict[str, Any]:
    payload_context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    session_id = (
        payload.get("session_id")
        or payload_context.get("session_id")
        or os.environ.get("CODEX_SESSION_ID")
        or os.environ.get("AGENT_SESSION_ID")
        or os.environ.get("CLAUDE_SESSION_ID")
        or ""
    )
    context = dict(payload_context)
    context["session_id"] = context.get("session_id") or session_id
    context["repo"] = context.get("repo") or git_value(project, ["config", "--get", "remote.origin.url"])
    context["worktree"] = context.get("worktree") or str(project.resolve())
    context["branch"] = context.get("branch") or git_value(project, ["branch", "--show-current"])
    return context


def write_event_file(project: Path, profile_id: str, envelope: dict[str, Any], output: Path | None) -> Path:
    if output is None:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", prefix="agent-guard-event-", delete=False)
        with handle:
            json.dump(envelope, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return Path(handle.name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def run_runtime(project: Path, event_path: Path) -> tuple[int, str]:
    runner = project / ".agents" / "guard-runtime" / "guard_runner.py"
    if not runner.exists():
        print(f"status: runtime_missing\nexpected_runner: {runner}", file=sys.stderr)
        return 2, ""
    completed = subprocess.run(
        [sys.executable, str(runner), "run", "--event", str(event_path)],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return completed.returncode, completed.stdout


def cleanup_event_file(event_path: Path) -> None:
    try:
        event_path.unlink()
    except FileNotFoundError:
        pass


def maybe_print_or_run(args: argparse.Namespace, envelope: dict[str, Any]) -> int:
    if args.print_envelope:
        print(json.dumps(envelope, ensure_ascii=False, indent=2))
        return 0
    event_path = write_event_file(args.project, args.profile, envelope, args.out)
    return_code, runtime_stdout = run_runtime(args.project, event_path)
    if args.out is None:
        cleanup_event_file(event_path)
    return return_code if bool(getattr(args, "blocking", False)) else 0


def build_codex_envelope(args: argparse.Namespace) -> dict[str, Any]:
    payload = load_payload(args.payload_file)
    default_event_type = CODEX_EVENT_TYPES.get(args.codex_event, f"codex.{args.codex_event.lower()}")
    event_type, binding_id = mapped_event_type(
        args.project,
        args.profile,
        "codex",
        args.codex_event,
        default_event_type,
    )
    context = context_from_payload(args.project, payload)
    return {
        "event_id": payload.get("event_id") or uuid.uuid4().hex,
        "event_type": event_type,
        "source": "codex",
        "timestamp": payload.get("timestamp") or now_iso(),
        "guard_profile_id": args.profile,
        "context": context,
        "payload": payload,
        "tool": {"name": payload.get("tool_name") or payload.get("tool") or ""},
        "action": {"name": args.codex_event, "blocking": bool(args.blocking)},
        "raw_event_summary": f"Codex lifecycle hook（生命周期钩子）：{args.codex_event}",
        "hook": {
            "source": "codex",
            "trigger_event": args.codex_event,
            "binding_id": binding_id,
            "blocking": bool(args.blocking),
        },
    }


def parse_pre_push_refs(stdin_text: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for line in stdin_text.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        refs.append(
            {
                "local_ref": parts[0],
                "local_sha": parts[1],
                "remote_ref": parts[2],
                "remote_sha": parts[3],
            }
        )
    return refs


def build_git_pre_push_envelope(args: argparse.Namespace) -> dict[str, Any]:
    refs = parse_pre_push_refs(sys.stdin.read())
    event_type, binding_id = mapped_event_type(args.project, args.profile, "git", "pre-push", "git.pre_push")
    payload = {
        "git": {
            "hook": "pre-push",
            "remote_name": args.remote_name,
            "remote_url": args.remote_url,
            "refs": refs,
        }
    }
    return {
        "event_id": uuid.uuid4().hex,
        "event_type": event_type,
        "source": "git",
        "timestamp": now_iso(),
        "guard_profile_id": args.profile,
        "context": context_from_payload(args.project, {}),
        "payload": payload,
        "tool": {"name": "git"},
        "action": {"name": "pre_push", "blocking": bool(args.blocking)},
        "raw_event_summary": "Git pre-push hook（Git 推送前钩子）。",
        "hook": {
            "source": "git",
            "trigger_event": "pre-push",
            "binding_id": binding_id,
            "blocking": bool(args.blocking),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 Hook（钩子）输入转换为标准 Guard envelope（信封）。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    codex = subparsers.add_parser("codex", help="适配 Codex lifecycle hook（生命周期钩子）。")
    codex.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目目录")
    codex.add_argument("--profile", required=True, help="Guard Profile（守卫画像）ID")
    codex.add_argument("--codex-event", required=True, help="Codex hook（钩子）事件名")
    codex.add_argument("--payload-file", type=Path, help="Codex hook payload（载荷）JSON 文件")
    codex.add_argument("--out", type=Path, help="写入 envelope（信封）的路径")
    codex.add_argument("--print-envelope", action="store_true", help="只输出 envelope（信封），不调用 Runtime（运行时）")
    codex.add_argument("--blocking", action="store_true", help="该 hook（钩子）入口可阻断")

    git_pre_push = subparsers.add_parser("git-pre-push", help="适配 Git pre-push hook（推送前钩子）。")
    git_pre_push.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目目录")
    git_pre_push.add_argument("--profile", required=True, help="Guard Profile（守卫画像）ID")
    git_pre_push.add_argument("--remote-name", default="", help="Git remote（远端）名称")
    git_pre_push.add_argument("--remote-url", default="", help="Git remote（远端）URL")
    git_pre_push.add_argument("--out", type=Path, help="写入 envelope（信封）的路径")
    git_pre_push.add_argument("--print-envelope", action="store_true", help="只输出 envelope（信封），不调用 Runtime（运行时）")
    git_pre_push.add_argument("--blocking", action="store_true", help="该 hook（钩子）入口可阻断")

    args = parser.parse_args(argv)
    args.project = args.project.resolve()
    try:
        if args.command == "codex":
            return maybe_print_or_run(args, build_codex_envelope(args))
        if args.command == "git-pre-push":
            return maybe_print_or_run(args, build_git_pre_push_envelope(args))
    except ValueError as exc:
        print(f"status: error\nreason: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
