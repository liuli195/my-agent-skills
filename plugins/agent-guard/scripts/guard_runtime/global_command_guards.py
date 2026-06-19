"""Global Command Guard command matching helpers."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GuardSource:
    source_scope: str
    profile_id: str
    path: Path


@dataclass(frozen=True)
class EffectiveGlobalCommandGuard:
    source_scope: str
    profile_id: str
    guard_id: str
    effective_guard_id: str
    config: dict[str, Any]


def match_command_pattern(command: str, pattern: str) -> dict[str, str] | None:
    matched = re.search(pattern, command)
    if matched is None:
        return None
    return {key: value for key, value in matched.groupdict().items() if value is not None}


def normalized_command_texts(command: str) -> list[str]:
    texts = [command]
    marker = " -lc "
    if marker in command:
        inner = command.split(marker, 1)[1].strip()
        if (inner.startswith("'") and inner.endswith("'")) or (inner.startswith('"') and inner.endswith('"')):
            inner = inner[1:-1]
        texts.extend(part.strip() for part in inner.split("&&") if part.strip())
    return list(dict.fromkeys(texts))
