"""显式绑定当前 Session Focus Instance（会话焦点实例）。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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


def runtime_cli() -> Path:
    fallback = plugin_root_candidates()[1] / "scripts" / "guard_runtime" / "cli.py"
    for root in plugin_root_candidates():
        candidate = root / "scripts" / "guard_runtime" / "cli.py"
        if candidate.exists():
            return candidate
    return fallback


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="激活当前 Session Focus Instance（会话焦点实例）。")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目目录，默认当前目录")
    parser.add_argument("--user-home", type=Path, default=Path.home(), help="用户级运行态根目录")
    parser.add_argument("--profile", required=True, help="Guard Profile（守卫画像）ID")
    parser.add_argument("--source", default=os.environ.get("AGENT_GUARD_SOURCE", "codex"), choices=["codex", "claude", "pi"], help="当前会话来源")
    parser.add_argument("--session-id", help="当前 session_id")
    parser.add_argument("--scope", default="project", choices=["project", "user"], help="Session Focus Binding（会话焦点绑定）作用域")
    parser.add_argument("--context-json", help="兼容旧参数；可从其中读取 session_id")
    parser.add_argument("--create", action="store_true", help="创建新 Guard Instance（守卫实例）")
    parser.add_argument("--title", default="新 Guard Instance（守卫实例）")
    parser.add_argument("--description", default="")
    parser.add_argument("--select-instance")
    args = parser.parse_args(argv)

    session_id = args.session_id or os.environ.get("AGENT_GUARD_SESSION_ID")
    if not session_id and args.context_json:
        try:
            context = json.loads(args.context_json)
        except json.JSONDecodeError as exc:
            print("status: error")
            print(f"reason: invalid_context_json: {exc}")
            return 2
        if isinstance(context, dict) and isinstance(context.get("session_id"), str):
            session_id = context["session_id"]
    if not session_id:
        print("status: error")
        print("reason: session_id_required")
        print("next: 先确保 SessionStart Hook（会话启动钩子）记录了当前 session_id。")
        return 2

    command = [
        sys.executable,
        str(runtime_cli()),
        "activate",
        "--project",
        str(args.project.resolve()),
        "--user-home",
        str(args.user_home.resolve()),
        "--source",
        args.source,
        "--session-id",
        session_id,
        "--scope",
        args.scope,
        "--profile",
        args.profile,
    ]
    if args.select_instance:
        command.extend(["--select-instance", args.select_instance])
    if args.create:
        command.append("--create")
        command.extend(["--title", args.title, "--description", args.description])

    completed = subprocess.run(command, cwd=args.project.resolve(), text=True, check=False)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
