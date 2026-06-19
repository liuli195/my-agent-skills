"""Global Command Guard command matching helpers."""

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

import yaml

try:
    from .command_context import command_from_envelope, tool_name_from_envelope
    from .command_matcher import match_any_command_pattern, match_command_pattern, normalized_command_texts
    from .json_checks import MISSING_JSON_VALUE, evaluate_json_predicate, json_field
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from command_context import command_from_envelope, tool_name_from_envelope
    from command_matcher import match_any_command_pattern, match_command_pattern, normalized_command_texts
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


class UnsafeEvidencePath(ValueError):
    pass


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
    explicit_scope = context.get("runtime_scope") or context.get("scope")
    if explicit_scope in {"project", "user"}:
        return str(explicit_scope)
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


def _matched_captures(config: dict[str, Any], command: str) -> dict[str, str] | None:
    match = config.get("match")
    patterns = match.get("command_patterns") if isinstance(match, dict) else []
    if not isinstance(patterns, list):
        return None
    return match_any_command_pattern(command, patterns)


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
    windows_path = PureWindowsPath(rendered)
    if path.is_absolute() or windows_path.is_absolute() or windows_path.drive or windows_path.root:
        raise UnsafeEvidencePath("unsafe_evidence_path")
    normalized = path.as_posix()
    root = (runtime_root(project, user_home, runtime_scope) / "evidence").resolve()
    if normalized == ".local/guard/evidence":
        candidate = root
    elif normalized.startswith(".local/guard/evidence/"):
        candidate = root / normalized.removeprefix(".local/guard/evidence/")
    elif normalized == ".agents/guard/evidence":
        candidate = root
    elif normalized.startswith(".agents/guard/evidence/"):
        candidate = root / normalized.removeprefix(".agents/guard/evidence/")
    elif normalized == ".local/guard" or normalized.startswith(".local/guard/"):
        raise UnsafeEvidencePath("unsafe_evidence_path")
    elif normalized == ".agents/guard" or normalized.startswith(".agents/guard/"):
        raise UnsafeEvidencePath("unsafe_evidence_path")
    else:
        candidate = root / normalized
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise UnsafeEvidencePath("unsafe_evidence_path") from exc
    return resolved


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
        try:
            evidence_path = _resolve_evidence_path(project, user_home, runtime_scope, rendered)
        except UnsafeEvidencePath:
            evidence_path = (runtime_root(project, user_home, runtime_scope) / "evidence").resolve()
            failure = {
                "effective_guard_id": guard.effective_guard_id,
                "source_scope": guard.source_scope,
                "profile_id": guard.profile_id,
                "guard_id": guard.guard_id,
                "captures": guard_captures,
                "evidence_path": str(evidence_path),
                "failure_reason": "unsafe_evidence_path",
            }
            if not first_deny:
                first_deny = deny
            failing_guards.append(failure)
            continue
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
            evidence_text = evidence_path.read_text(encoding="utf-8")
        except OSError as exc:
            failure.update({"failure_reason": "evidence_unreadable", "error_type": type(exc).__name__})
            if not first_deny:
                first_deny = deny
            failing_guards.append(failure)
            continue
        try:
            data = json.loads(evidence_text)
        except json.JSONDecodeError:
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
