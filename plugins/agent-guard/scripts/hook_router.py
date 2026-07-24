"""Agent Guard Plugin（代理守卫插件）的 Hook Router（钩子路由器）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from guard_runtime.core import adapt_lifecycle_event, route_pre_tool_use, write_session_observation


def hook_block_reason(body: dict) -> str:
    parts = [str(body.get("reason") or "agent_guard_blocked")]
    suggestion = body.get("suggestion")
    if suggestion:
        parts.append(str(suggestion))
    return "\n".join(parts)


def codex_pre_tool_use_output(body: dict) -> dict:
    reason = hook_block_reason(body)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def exit_code_for_pre_tool_use(body: dict, code: int, stdin_hook: bool, source: str) -> int:
    if stdin_hook and source == "codex" and body.get("status") in {"deny", "ask"}:
        return 0
    if stdin_hook and body.get("status") in {"deny", "ask"}:
        print(hook_block_reason(body), file=sys.stderr)
        return 2
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent Guard Hook Router（钩子路由器）。")
    parser.add_argument("--source", choices=["codex", "claude", "pi"], required=True, help="Hook（钩子）来源。")
    parser.add_argument("--event", choices=["SessionStart", "PreToolUse"], required=True, help="Hook（钩子）事件。")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="项目目录。")
    parser.add_argument("--user-home", type=Path, default=Path.home(), help="用户级运行态根目录。")
    parser.add_argument("--payload-file", type=Path, help="Hook payload（钩子载荷）JSON 文件；未提供时读取 stdin。")
    parser.add_argument("--print-envelope", action="store_true", help="只输出标准事件 envelope（信封）。")
    args = parser.parse_args(argv)

    if args.payload_file:
        payload = json.loads(args.payload_file.read_text(encoding="utf-8"))
    else:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
    if not isinstance(payload, dict):
        raise SystemExit("payload must be JSON object")

    project = args.project.resolve()
    user_home = args.user_home.resolve()
    envelope = adapt_lifecycle_event(args.source, args.event, payload, project)
    if args.print_envelope:
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if args.event == "SessionStart":
        try:
            observation_path = write_session_observation(project, user_home, envelope)
        except ValueError:
            json.dump({"status": "error", "reason": "missing_session_id"}, sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n")
            return 1
        json.dump(
            {
                "status": "observed",
                "source": args.source,
                "event_type": envelope["event_type"],
                "session_id": envelope["context"]["session_id"],
                "observation_path": str(observation_path),
            },
            sys.stdout,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
        return 0

    body, code = route_pre_tool_use(project, user_home, envelope)
    if args.payload_file is None and args.source == "codex" and body.get("status") in {"deny", "ask"}:
        output_body = codex_pre_tool_use_output(body)
    else:
        output_body = body
    json.dump(output_body, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return exit_code_for_pre_tool_use(body, code, args.payload_file is None, args.source)


if __name__ == "__main__":
    sys.exit(main())
