"""读取当前 Session Focus Instance（会话焦点实例）的 Guard Brief（守卫简报）。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def runtime_cli() -> Path:
    return Path(__file__).resolve().parents[3] / "plugins" / "agent-guard" / "scripts" / "guard_runtime" / "cli.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="读取并注入当前 Guard Brief（守卫简报）。")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目目录，默认当前目录")
    parser.add_argument("--user-home", type=Path, default=Path.home(), help="用户级运行态根目录")
    parser.add_argument("--source", default="codex", choices=["codex", "claude"], help="当前会话来源")
    parser.add_argument("--session-id", help="当前 session_id")
    parser.add_argument("--context-json", help="可从其中读取 session_id")
    args = parser.parse_args(argv)

    session_id = args.session_id
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
        return 2

    completed = subprocess.run(
        [
            sys.executable,
            str(runtime_cli()),
            "brief",
            "--project",
            str(args.project.resolve()),
            "--user-home",
            str(args.user_home.resolve()),
            "--source",
            args.source,
            "--session-id",
            session_id,
        ],
        cwd=args.project.resolve(),
        text=True,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
