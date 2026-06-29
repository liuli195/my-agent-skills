"""Shared PreToolUse command context helpers."""

from typing import Any


def command_from_envelope(envelope: dict[str, Any]) -> str:
    payload = envelope.get("payload", {})
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else {}
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str):
            return command
    command = payload.get("command") if isinstance(payload, dict) else None
    return command if isinstance(command, str) else ""


def tool_name_from_envelope(envelope: dict[str, Any]) -> str:
    payload = envelope.get("payload", {})
    tool = payload.get("tool") if isinstance(payload, dict) else {}
    name = tool.get("name") if isinstance(tool, dict) else None
    return name if isinstance(name, str) else ""
