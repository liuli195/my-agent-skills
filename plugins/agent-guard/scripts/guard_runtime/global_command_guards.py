"""Global Command Guard command matching helpers."""

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    from .json_checks import MISSING_JSON_VALUE, evaluate_json_predicate, json_field
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from json_checks import MISSING_JSON_VALUE, evaluate_json_predicate, json_field


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


def git_head(project: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def runtime_scope_for_command(project: Path, user_home: Path, envelope: dict[str, Any]) -> str:
    context = envelope.get("context", {})
    cwd = Path(str(context.get("cwd") or project))
    try:
        return "project" if cwd.resolve().is_relative_to(project.resolve()) else "user"
    except OSError:
        return "project"


def runtime_root(project: Path, user_home: Path, scope: str) -> Path:
    if scope == "user":
        return user_home / ".agents" / "guard"
    return project / ".local" / "guard"


def render_template(template: str, values: dict[str, str]) -> tuple[str, list[str]]:
    missing = sorted({key for key in re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", template) if key not in values})
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
        rendered = rendered.replace("{" + key + "}", value)
    return rendered, missing


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


def _matched_captures(config: dict[str, Any], command: str) -> dict[str, str] | None:
    match = config.get("match")
    patterns = match.get("command_patterns") if isinstance(match, dict) else []
    if not isinstance(patterns, list):
        return None
    for text in normalized_command_texts(command):
        for pattern in patterns:
            if not isinstance(pattern, str):
                continue
            captures = match_command_pattern(text, pattern)
            if captures is not None:
                return captures
    return None


def _required_captures(config: dict[str, Any]) -> list[str]:
    match = config.get("match")
    captures = match.get("required_captures") if isinstance(match, dict) else []
    return [item for item in captures if isinstance(item, str)] if isinstance(captures, list) else []


def _deny_config(config: dict[str, Any]) -> dict[str, Any]:
    deny = config.get("deny")
    return deny if isinstance(deny, dict) else {}


def _context_values(guard: EffectiveGlobalCommandGuard, captures: dict[str, str], runtime_scope: str, head: str) -> dict[str, str]:
    values = {
        "source_scope": guard.source_scope,
        "profile_id": guard.profile_id,
        "guard_id": guard.guard_id,
        "effective_guard_id": guard.effective_guard_id,
        "runtime_scope": runtime_scope,
        "git_head": head,
    }
    values.update(captures)
    return values


def _value_from(name: str, captures: dict[str, str], builtins: dict[str, str]) -> Any:
    if name in captures:
        return captures[name]
    return builtins.get(name)


def _resolve_evidence_path(project: Path, user_home: Path, runtime_scope: str, rendered: str) -> Path:
    path = Path(rendered)
    if path.is_absolute():
        return path
    normalized = path.as_posix()
    root = runtime_root(project, user_home, runtime_scope)
    if normalized == ".local/guard":
        return root
    if normalized.startswith(".local/guard/"):
        return root / normalized.removeprefix(".local/guard/")
    if normalized == ".agents/guard":
        return root
    if normalized.startswith(".agents/guard/"):
        return root / normalized.removeprefix(".agents/guard/")
    return root / normalized


def _json_check_detail(check: dict[str, Any], actual: Any, expected: Any, include_expected: bool) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "field": check.get("field"),
        "predicate": check.get("predicate"),
    }
    if include_expected:
        detail["expected"] = expected
    if actual is not MISSING_JSON_VALUE:
        detail["actual"] = actual
    where = check.get("where")
    if isinstance(where, dict):
        detail["where"] = where
    return detail


def _evaluate_checks(evidence: dict[str, Any], checks: Any, captures: dict[str, str], builtins: dict[str, str]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for check in checks if isinstance(checks, list) else []:
        if not isinstance(check, dict):
            failures.append({"failure_reason": "invalid_json_check"})
            continue
        field = check.get("field")
        predicate = check.get("predicate")
        if not isinstance(field, str) or not isinstance(predicate, str):
            failures.append({"failure_reason": "invalid_json_check"})
            continue
        value_from = check.get("value_from")
        expected = _value_from(value_from, captures, builtins) if isinstance(value_from, str) else check.get("value")
        actual = json_field(evidence, field)
        if not evaluate_json_predicate(actual, predicate, expected, check.get("where") if isinstance(check.get("where"), dict) else None):
            failures.append(_json_check_detail(check, actual, expected, predicate != "exists"))
    return failures


def evaluate_global_command_guards(project: Path, user_home: Path, envelope: dict[str, Any]) -> dict[str, Any]:
    tool_name = tool_name_from_envelope(envelope)
    command = command_from_envelope(envelope)
    runtime_scope = runtime_scope_for_command(project, user_home, envelope)
    head = git_head(project)
    matched_guard_ids: list[str] = []
    failing_guards: list[dict[str, Any]] = []
    captures: dict[str, str] = {}
    captures_by_guard: dict[str, dict[str, str]] = {}
    first_deny: dict[str, Any] = {}

    for guard in collect_global_command_guards(project, user_home):
        config = guard.config
        guard_tool = config.get("tool")
        if isinstance(guard_tool, str) and guard_tool != tool_name:
            continue
        guard_captures = _matched_captures(config, command)
        if guard_captures is None:
            continue

        matched_guard_ids.append(guard.effective_guard_id)
        captures.update(guard_captures)
        captures_by_guard[guard.effective_guard_id] = guard_captures
        deny = _deny_config(config)

        missing_captures = [item for item in _required_captures(config) if item not in guard_captures]
        builtins = {
            "source_scope": guard.source_scope,
            "profile_id": guard.profile_id,
            "guard_id": guard.guard_id,
            "effective_guard_id": guard.effective_guard_id,
            "runtime_scope": runtime_scope,
            "git_head": head,
        }
        values = _context_values(guard, guard_captures, runtime_scope, head)
        evidence = config.get("evidence")
        template = evidence.get("path") if isinstance(evidence, dict) else ""
        rendered, missing_template_values = render_template(template if isinstance(template, str) else "", values)
        evidence_path = _resolve_evidence_path(project, user_home, runtime_scope, rendered)
        failure: dict[str, Any] = {
            "effective_guard_id": guard.effective_guard_id,
            "source_scope": guard.source_scope,
            "profile_id": guard.profile_id,
            "guard_id": guard.guard_id,
            "captures": guard_captures,
            "evidence_path": str(evidence_path),
        }
        if missing_captures:
            failure.update({"failure_reason": "required_capture_missing", "missing_captures": missing_captures})
            if not first_deny:
                first_deny = deny
            failing_guards.append(failure)
            continue
        if missing_template_values:
            failure.update({"failure_reason": "evidence_path_template_value_missing", "missing_values": missing_template_values})
            if not first_deny:
                first_deny = deny
            failing_guards.append(failure)
            continue
        if not evidence_path.exists():
            failure["failure_reason"] = "evidence_missing"
            if not first_deny:
                first_deny = deny
            failing_guards.append(failure)
            continue
        try:
            data = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            failure["failure_reason"] = "invalid_evidence_json"
            if not first_deny:
                first_deny = deny
            failing_guards.append(failure)
            continue
        if not isinstance(data, dict):
            failure["failure_reason"] = "invalid_evidence_json"
            if not first_deny:
                first_deny = deny
            failing_guards.append(failure)
            continue
        failed_checks = _evaluate_checks(data, config.get("checks"), guard_captures, builtins)
        if failed_checks:
            failure.update({"failure_reason": "json_check_failed", "failed_checks": failed_checks})
            if not first_deny:
                first_deny = deny
            failing_guards.append(failure)

    if not matched_guard_ids:
        return {"effect": "allow", "reason": "global_command_guard_not_matched", "matched_guard_ids": [], "runtime_scope": runtime_scope}

    result: dict[str, Any] = {
        "effect": "deny" if failing_guards else "allow",
        "reason": "global_command_guard_required" if failing_guards else "global_command_guard_passed",
        "matched_guard_ids": matched_guard_ids,
        "failing_guards": failing_guards,
        "captures": captures,
        "captures_by_guard": captures_by_guard,
        "runtime_scope": runtime_scope,
        "tool": tool_name,
        "command": command,
    }
    if failing_guards:
        result["reason"] = str(first_deny.get("reason") or "global_command_guard_required")
        result["next"] = first_deny.get("next")
        result["suggestion"] = first_deny.get("suggestion")
    return result
