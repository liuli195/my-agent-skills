"""把标准事件交给 Agent Guard Plugin Runtime（插件运行时）处理。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def plugin_root_candidates() -> list[Path]:
    source_root = Path(__file__).resolve().parents[3]
    candidates = [
        source_root,
        source_root / "plugins" / "agent-guard",
    ]
    for env_name in ["PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "AGENT_GUARD_PLUGIN_ROOT"]:
        env_value = os.environ.get(env_name)
        if env_value:
            candidates.append(Path(env_value))
    candidates.extend(
        [
            Path.home() / ".codex" / "plugins" / "agent-guard",
            Path.home() / ".claude" / "plugins" / "agent-guard",
        ]
    )
    return candidates


def plugin_root() -> Path:
    fallback = plugin_root_candidates()[1]
    for root in plugin_root_candidates():
        if (root / "scripts" / "guard_runtime" / "cli.py").exists() and (root / "scripts" / "hook_router.py").exists():
            return root
    return fallback


def runtime_cli() -> Path:
    return plugin_root() / "scripts" / "guard_runtime" / "cli.py"


def hook_router() -> Path:
    return plugin_root() / "scripts" / "hook_router.py"


def read_event(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("event 顶层必须是 JSON object（JSON 对象）。")
    return data


def session_id(event: dict) -> str | None:
    context = event.get("context")
    value = context.get("session_id") if isinstance(context, dict) else None
    return value if isinstance(value, str) else None


def run_state_completed(project: Path, user_home: Path, event: dict) -> int:
    source = event.get("source") if isinstance(event.get("source"), str) else "codex"
    sid = session_id(event)
    if not sid:
        print("status: error")
        print("reason: session_id_required")
        return 2
    completed = subprocess.run(
        [
            sys.executable,
            str(runtime_cli()),
            "state-completed",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            source,
            "--session-id",
            sid,
        ],
        cwd=project,
        text=True,
        check=False,
    )
    return completed.returncode


def run_pre_tool_use(project: Path, user_home: Path, event: dict) -> int:
    context = event.get("context") if isinstance(event.get("context"), dict) else {}
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    tool = event.get("tool") if isinstance(event.get("tool"), dict) else {}
    hook_payload = dict(payload)
    if "tool_input" not in hook_payload and isinstance(payload.get("command"), str):
        hook_payload["tool_input"] = {"command": payload["command"]}
    hook_payload["session_id"] = context.get("session_id")
    hook_payload["cwd"] = context.get("cwd") or str(project)
    if isinstance(tool.get("name"), str):
        hook_payload["tool_name"] = tool["name"]
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(hook_payload, handle, ensure_ascii=False)
        payload_file = Path(handle.name)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(hook_router()),
                "--source",
                str(event.get("source") or "codex"),
                "--event",
                "PreToolUse",
                "--project",
                str(project),
                "--user-home",
                str(user_home),
                "--payload-file",
                str(payload_file),
            ],
            cwd=project,
            text=True,
            check=False,
        )
        return completed.returncode
    finally:
        try:
            payload_file.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="为一个标准事件运行 Agent Guard Plugin Runtime（插件运行时）。")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目目录，默认当前目录")
    parser.add_argument("--user-home", type=Path, default=Path.home(), help="用户级运行态根目录")
    parser.add_argument("--event", type=Path, required=True, help="标准事件 envelope（信封）文件")
    args = parser.parse_args(argv)

    try:
        event = read_event(args.event)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print("status: error")
        print(f"reason: invalid_event: {exc}")
        return 2

    event_type = event.get("event_type")
    project = args.project.resolve()
    user_home = args.user_home.resolve()
    if event_type == "state_completed":
        return run_state_completed(project, user_home, event)
    if event_type in {"lifecycle.pre_tool_use", "codex.pre_tool_use", "claude.pre_tool_use"}:
        return run_pre_tool_use(project, user_home, event)

    print("status: allow")
    print("reason: unsupported_event_noop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
