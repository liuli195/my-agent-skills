"""Global Command Guard command matching helpers."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


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


def _guard_sources(project: Path, user_home: Path) -> list[GuardSource]:
    sources: list[GuardSource] = []
    for path in sorted((project / ".agents" / "guards").glob("*/global-command-guards.yaml")):
        sources.append(GuardSource("project", path.parent.name, path))
    for path in sorted((user_home / ".agents" / "guards").glob("*/global-command-guards.yaml")):
        sources.append(GuardSource("user", path.parent.name, path))
    return sources


def collect_global_command_guards(project: Path, user_home: Path) -> list[EffectiveGlobalCommandGuard]:
    guards: list[EffectiveGlobalCommandGuard] = []
    for source in _guard_sources(project, user_home):
        data = yaml.safe_load(source.path.read_text(encoding="utf-8")) or {}
        items = data.get("global_command_guards", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            guard_id = item.get("id")
            if not isinstance(guard_id, str) or not guard_id:
                continue
            effective_guard_id = f"{source.source_scope}:{source.profile_id}:{guard_id}"
            guards.append(
                EffectiveGlobalCommandGuard(
                    source_scope=source.source_scope,
                    profile_id=source.profile_id,
                    guard_id=guard_id,
                    effective_guard_id=effective_guard_id,
                    config=item,
                )
            )
    return guards
