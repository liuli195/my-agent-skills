"""Shared PreToolUse command context helpers."""

from typing import Any


def command_from_envelope(envelope: dict[str, Any]) -> str:
    payload = envelope.get("payload", {})
    if not isinstance(payload, dict):
        return ""
    for container_name in ["tool_input", None, "input", "parameters", "params", "args", "arguments"]:
        container = payload if container_name is None else payload.get(container_name)
        if not isinstance(container, dict):
            continue
        for key in ["command", "cmd"]:
            command = container.get(key)
            if isinstance(command, str):
                return command
    return ""


def tool_name_from_envelope(envelope: dict[str, Any]) -> str:
    payload = envelope.get("payload", {})
    tool = payload.get("tool") if isinstance(payload, dict) else {}
    name = tool.get("name") if isinstance(tool, dict) else None
    return name if isinstance(name, str) else ""
