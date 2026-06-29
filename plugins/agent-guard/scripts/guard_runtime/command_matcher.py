"""Shared command matching helpers."""

import re
from typing import Any


def normalized_command_texts(command: str) -> list[str]:
    texts = [command]
    marker = " -lc "
    if marker in command:
        inner = command.split(marker, 1)[1].strip()
        if (inner.startswith("'") and inner.endswith("'")) or (inner.startswith('"') and inner.endswith('"')):
            inner = inner[1:-1]
        texts.extend(part.strip() for part in inner.split("&&") if part.strip())
    return list(dict.fromkeys(texts))


def match_command_pattern(command: str, pattern: str) -> dict[str, str] | None:
    matched = re.search(pattern, command)
    if matched is None:
        return None
    return {key: value for key, value in matched.groupdict().items() if value is not None}


def match_any_command_pattern(command: str, patterns: list[Any], normalize_texts: bool = True) -> dict[str, str] | None:
    texts = normalized_command_texts(command) if normalize_texts else [command]
    for text in texts:
        for pattern in patterns:
            if not isinstance(pattern, str):
                continue
            captures = match_command_pattern(text, pattern)
            if captures is not None:
                return captures
    return None


def normalize_command_prefix(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return " ".join(value)
    return None


def command_prefix_matches(command: str, prefix: str, normalize_texts: bool = False) -> bool:
    texts = normalized_command_texts(command) if normalize_texts else [command]
    return any(text.startswith(prefix) for text in texts)
