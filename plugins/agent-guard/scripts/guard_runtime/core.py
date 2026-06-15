"""Session Focus（会话焦点）运行时核心。"""

from __future__ import annotations

import json
import os
import hashlib
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


RUNTIME_API_VERSION = "agent-guard-runtime/v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是 JSON object（JSON 对象）。")
    return data


def runtime_root(project: Path, user_home: Path | None = None, scope: str = "project") -> Path:
    if scope == "user":
        if user_home is None:
            raise ValueError("user_home_required")
        return user_home / ".agents" / "guard"
    return project / ".local" / "guard"


def scope_from_state(state: dict[str, Any]) -> str:
    value = state.get("scope")
    return value if value in {"project", "user"} else "project"


def write_audit(project: Path, status: str, reason: str, detail: dict[str, Any], user_home: Path | None = None, scope: str = "project") -> Path:
    audit_path = runtime_root(project, user_home, scope) / "audit" / f"{uuid.uuid4().hex}.json"
    write_json(
        audit_path,
        {
            "status": status,
            "reason": reason,
            "created_at": now_iso(),
            "detail": detail,
        },
    )
    return audit_path


def read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是 YAML mapping（YAML 映射）。")
    return data


def read_yaml_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_yaml(path)


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def adapt_lifecycle_event(source: str, event: str, payload: dict[str, Any], project: Path) -> dict[str, Any]:
    event_type = {
        "SessionStart": "lifecycle.session_start",
        "PreToolUse": "lifecycle.pre_tool_use",
    }[event]
    session_id = payload.get("session_id") or payload.get("sessionId") or payload.get("conversation_id")
    cwd = payload.get("cwd") or payload.get("workspace_dir") or payload.get("project_dir") or str(project)
    envelope: dict[str, Any] = {
        "source": source,
        "event_type": event_type,
        "context": {
            "session_id": session_id,
            "cwd": str(cwd),
        },
        "payload": {},
    }
    if event == "SessionStart":
        envelope["payload"] = {
            key: value
            for key, value in payload.items()
            if key not in {"guard_profile_id", "profile_id"}
        }
    else:
        tool_name = payload.get("tool_name") or payload.get("tool", {}).get("name")
        tool_input = payload.get("tool_input") or payload.get("input") or payload.get("parameters") or {}
        envelope["payload"] = {
            "tool": {"name": tool_name},
            "tool_input": tool_input,
        }
        if "parameters" in payload and "parameters" not in envelope["payload"]:
            envelope["payload"]["parameters"] = payload["parameters"]
    return envelope


def project_observation_path(project: Path, source: str, session_id: str) -> Path:
    return project / ".local" / "guard" / "session-observations" / source / f"{session_id}.json"


def user_observation_path(user_home: Path, source: str, session_id: str) -> Path:
    return user_home / ".agents" / "guard" / "session-observations" / source / f"{session_id}.json"


def project_focus_path(project: Path, source: str, session_id: str) -> Path:
    return project / ".local" / "guard" / "session-focus" / source / f"{session_id}.json"


def user_focus_path(user_home: Path, source: str, session_id: str) -> Path:
    return user_home / ".agents" / "guard" / "session-focus" / source / f"{session_id}.json"


def resolve_focus(project: Path, user_home: Path, source: str, session_id: str) -> dict[str, Any]:
    project_path = project_focus_path(project, source, session_id)
    user_path = user_focus_path(user_home, source, session_id)
    existing = [path for path in [project_path, user_path] if path.exists()]
    if not existing:
        return {"status": "none"}
    if len(existing) > 1:
        return {"status": "multiple", "paths": [str(path) for path in existing]}

    path = existing[0]
    try:
        binding = read_json(path)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        return {"status": "invalid", "path": str(path), "error": str(exc)}

    required = ["source", "session_id", "scope", "profile_id", "instance_id", "bound_at"]
    missing = [field for field in required if not binding.get(field)]
    if missing:
        return {"status": "invalid", "path": str(path), "missing_fields": missing}
    return {"status": "ok", "binding": binding, "path": str(path)}


def write_session_observation(project: Path, user_home: Path, envelope: dict[str, Any]) -> Path:
    context = envelope.get("context", {})
    session_id = str(context.get("session_id") or "")
    if not session_id:
        raise ValueError("missing_session_id")
    cwd = Path(str(context.get("cwd") or project))
    target = project_observation_path(project, envelope["source"], session_id)
    if not cwd.resolve().is_relative_to(project.resolve()):
        target = user_observation_path(user_home, envelope["source"], session_id)
    write_json(
        target,
        {
            "source": envelope["source"],
            "session_id": session_id,
            "cwd": str(context.get("cwd") or project),
            "transcript_path": envelope.get("payload", {}).get("transcript_path"),
            "observed_at": now_iso(),
        },
    )
    return target


def read_session_observation(project: Path, user_home: Path, source: str, session_id: str) -> tuple[dict[str, Any] | None, Path | None]:
    for path in [
        project_observation_path(project, source, session_id),
        user_observation_path(user_home, source, session_id),
    ]:
        if path.exists():
            return read_json(path), path
    return None, None


def profile_dir(project: Path, profile_id: str, user_home: Path | None = None, scope: str = "project") -> Path:
    if scope == "user":
        if user_home is None:
            raise ValueError("user_home_required")
        return user_home / ".agents" / "guards" / profile_id
    return project / ".agents" / "guards" / profile_id


def instance_state_path(project: Path, profile_id: str, instance_id: str, user_home: Path | None = None, scope: str = "project") -> Path:
    return runtime_root(project, user_home, scope) / "state" / profile_id / instance_id / "state.json"


def profile_manifest(project: Path, profile_id: str, user_home: Path | None = None, scope: str = "project") -> dict[str, Any]:
    return read_yaml(profile_dir(project, profile_id, user_home, scope) / "GUARD-MANIFEST.yaml")


def profile_target(project: Path, profile_id: str, user_home: Path | None = None, scope: str = "project") -> dict[str, Any]:
    return read_yaml(profile_dir(project, profile_id, user_home, scope) / "target-model.yaml").get("target", {})


def profile_state_machine(project: Path, profile_id: str, user_home: Path | None = None, scope: str = "project") -> dict[str, Any]:
    return read_yaml(profile_dir(project, profile_id, user_home, scope) / "state-machine.yaml")


def profile_execution_model(project: Path, profile_id: str, user_home: Path | None = None, scope: str = "project") -> dict[str, Any]:
    return read_yaml_if_exists(profile_dir(project, profile_id, user_home, scope) / "execution-model.yaml")


def latest_brief_dir(project: Path, profile_id: str, instance_id: str, user_home: Path | None = None, scope: str = "project") -> Path:
    return runtime_root(project, user_home, scope) / "latest" / profile_id / instance_id


def injection_record_path(project: Path, source: str, session_id: str, profile_id: str, instance_id: str, user_home: Path | None = None, scope: str = "project") -> Path:
    return runtime_root(project, user_home, scope) / "injections" / source / stable_hash(session_id) / profile_id / f"{instance_id}.json"


def list_active_instances(project: Path, profile_id: str, user_home: Path | None = None, scope: str = "project") -> list[dict[str, Any]]:
    state_root = runtime_root(project, user_home, scope) / "state" / profile_id
    instances: list[dict[str, Any]] = []
    for state_file in sorted(state_root.glob("*/state.json")) if state_root.exists() else []:
        try:
            state = read_json(state_file)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if state.get("status") == "active":
            instances.append(state)
    return instances


def new_instance_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"agi_{stamp}_{uuid.uuid4().hex[:8]}"


def initial_state(project: Path, profile_id: str, user_home: Path | None = None, scope: str = "project") -> str:
    state_machine = profile_state_machine(project, profile_id, user_home, scope)
    value = state_machine.get("initial_state")
    return value if isinstance(value, str) else "open"


def create_instance(project: Path, profile_id: str, title: str, description: str, user_home: Path | None = None, scope: str = "project") -> dict[str, Any]:
    instance_id = new_instance_id()
    created_at = now_iso()
    state = {
        "instance_id": instance_id,
        "profile_id": profile_id,
        "scope": scope,
        "status": "active",
        "title": title,
        "description": description,
        "current_state": initial_state(project, profile_id, user_home, scope),
        "state_version": 1,
        "created_at": created_at,
        "last_seen_at": created_at,
    }
    write_json(instance_state_path(project, profile_id, instance_id, user_home, scope), state)
    return state


def load_instance(project: Path, profile_id: str, instance_id: str, user_home: Path | None = None, scope: str = "project") -> dict[str, Any] | None:
    path = instance_state_path(project, profile_id, instance_id, user_home, scope)
    if not path.exists():
        return None
    return read_json(path)


def save_instance(project: Path, state: dict[str, Any], user_home: Path | None = None) -> None:
    write_json(instance_state_path(project, state["profile_id"], state["instance_id"], user_home, scope_from_state(state)), state)


def close_instance(project: Path, profile_id: str, instance_id: str, user_home: Path | None = None, scope: str = "project") -> dict[str, Any]:
    state = load_instance(project, profile_id, instance_id, user_home, scope)
    if state is None:
        raise ValueError("instance_not_found")
    state["status"] = "closed"
    state["last_seen_at"] = now_iso()
    save_instance(project, state, user_home)
    return state


def profile_runtime_api_version(project: Path, profile_id: str, user_home: Path | None = None, scope: str = "project") -> str | None:
    value = profile_manifest(project, profile_id, user_home, scope).get("runtime_api_version")
    return value if isinstance(value, str) else None


def focus_path_for_scope(project: Path, user_home: Path, scope: str, source: str, session_id: str) -> Path:
    if scope == "project":
        return project_focus_path(project, source, session_id)
    if scope == "user":
        return user_focus_path(user_home, source, session_id)
    raise ValueError("invalid_scope")


def write_focus_binding(project: Path, user_home: Path, source: str, session_id: str, scope: str, profile_id: str, instance_id: str) -> tuple[Path, Path]:
    binding = {
        "source": source,
        "session_id": session_id,
        "scope": scope,
        "profile_id": profile_id,
        "instance_id": instance_id,
        "bound_at": now_iso(),
    }
    path = focus_path_for_scope(project, user_home, scope, source, session_id)
    write_json(path, binding)
    audit_path = write_audit(
        project,
        "allow",
        "session_focus_changed",
        {"source": source, "session_id": session_id, "scope": scope, "profile_id": profile_id, "instance_id": instance_id, "binding_path": str(path)},
        user_home,
        scope,
    )
    return path, audit_path


def target_table(project: Path, profile_id: str, user_home: Path | None = None, scope: str = "project") -> str:
    target = profile_target(project, profile_id, user_home, scope)
    lines = [
        "| 序号 | 作用域 | 守卫目标 | 类型 | 来源 | 边界 | 画像 ID |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        f"| 1 | project | {target.get('name', '')} | {target.get('type', '')} | {target.get('source', '')} | {target.get('boundary', '')} | {profile_id} |",
    ]
    return "\n".join(lines)


def instance_table(instances: list[dict[str, Any]]) -> str:
    lines = [
        "| 序号 | 实例标题 | 实例说明 | 创建时间 | 最后使用 | 状态 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for index, item in enumerate(instances, start=1):
        lines.append(
            f"| {index} | {item.get('title', '')} | {item.get('description', '')} | {item.get('created_at', '')} | {item.get('last_seen_at', '')} | {item.get('status', '')} |"
        )
    lines.extend(["", "| 选项 | 动作 |", "| --- | --- |", "| N | 创建新实例 |"])
    return "\n".join(lines)


def format_brief_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "[]"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def load_brief_template(project: Path, profile_id: str, user_home: Path | None = None, scope: str = "project") -> str:
    path = profile_dir(project, profile_id, user_home, scope) / "brief-template.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return """# Guard Brief（守卫简报）

Guard Profile（守卫画像）：{{ guard_profile_id }}
Guard Instance（守卫实例）：{{ instance_id }}
当前状态：{{ state }}
允许下一步：{{ allowed_next }}
禁止下一步：{{ forbidden_next }}
缺失 Artifacts（产物）：{{ missing_artifacts }}
最近拒绝原因：{{ recent_denial_reasons }}
状态权限：{{ permissions }}
完成条件：{{ transition_conditions }}
下一步：{{ next_step }}
状态推进：{{ state_completion_instruction }}
Audit（审计）：{{ audit_path }}
"""


def render_brief_text(template: str, values: dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        formatted = format_brief_value(value)
        rendered = rendered.replace("{{ " + key + " }}", formatted)
        rendered = rendered.replace("{{" + key + "}}", formatted)
    return rendered.rstrip() + "\n"


def execution_state_summary(project: Path, profile_id: str, state_id: str, user_home: Path | None = None, scope: str = "project") -> dict[str, Any]:
    execution = profile_execution_model(project, profile_id, user_home, scope)
    states = execution.get("states")
    for state in states if isinstance(states, list) else []:
        if not isinstance(state, dict) or state.get("id") != state_id:
            continue
        brief = state.get("brief") if isinstance(state.get("brief"), dict) else {}
        return {
            "allowed_next": state.get("allowed_next", []),
            "forbidden_next": state.get("forbidden_next", []),
            "missing_artifacts": state.get("missing_artifacts", []),
            "next_step": brief.get("next_step", "") if isinstance(brief, dict) else "",
        }
    return {"allowed_next": [], "forbidden_next": [], "missing_artifacts": [], "next_step": ""}


def transition_conditions_for_state(state_machine: dict[str, Any], state_id: str) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    transitions = state_machine.get("transitions")
    for transition in transitions if isinstance(transitions, list) else []:
        if not isinstance(transition, dict) or transition.get("from") != state_id:
            continue
        conditions.append(
            {
                "transition_id": transition.get("id"),
                "to": transition.get("to"),
                "required_artifacts": transition.get("required_artifacts", []),
                "guard_points": transition.get("guard_points", []),
            }
        )
    return conditions


def state_completion_instruction(state_machine: dict[str, Any], state_id: str) -> str:
    terminal_states = state_machine.get("terminal_states")
    if isinstance(terminal_states, list) and state_id in terminal_states:
        return "流程已完成；只需查看 Audit（审计）位置。"
    return "提交 event_type=state_completed。"


def brief_hash_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": payload["profile_id"],
        "instance_id": payload["instance_id"],
        "state": payload["state"],
        "state_version": payload["state_version"],
        "allowed_next": payload["allowed_next"],
        "forbidden_next": payload["forbidden_next"],
        "missing_artifacts": payload["missing_artifacts"],
        "recent_denial_reasons": payload["recent_denial_reasons"],
        "transition_conditions": payload["transition_conditions"],
    }


def write_latest_brief(
    project: Path,
    profile_id: str,
    state: dict[str, Any],
    recent_denial_reasons: list[str] | None = None,
    audit_path: Path | None = None,
    user_home: Path | None = None,
) -> dict[str, Any]:
    instance_id = str(state["instance_id"])
    state_id = str(state.get("current_state") or "")
    scope = scope_from_state(state)
    state_machine = profile_state_machine(project, profile_id, user_home, scope)
    current_state = state_by_id(state_machine, state_id)
    summary = execution_state_summary(project, profile_id, state_id, user_home, scope)
    directory = latest_brief_dir(project, profile_id, instance_id, user_home, scope)
    json_path = directory / "brief.json"
    text_path = directory / "brief.md"
    payload: dict[str, Any] = {
        "profile_id": profile_id,
        "guard_profile_id": profile_id,
        "instance_id": instance_id,
        "scope": scope,
        "state": state_id,
        "state_version": int(state.get("state_version") or 1),
        "generated_at": now_iso(),
        "source": "guard-runtime",
        "allowed_next": summary["allowed_next"],
        "forbidden_next": summary["forbidden_next"],
        "missing_artifacts": summary["missing_artifacts"],
        "next_step": summary["next_step"],
        "recent_denial_reasons": recent_denial_reasons or [],
        "permissions": current_state.get("permissions", {}) if isinstance(current_state, dict) else {},
        "transition_conditions": transition_conditions_for_state(state_machine, state_id),
        "state_completion_instruction": state_completion_instruction(state_machine, state_id),
        "audit_path": str(audit_path) if audit_path is not None else "",
        "brief_path": str(json_path),
        "brief_text_path": str(text_path),
    }
    payload["brief_hash"] = stable_hash(json.dumps(brief_hash_payload(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    payload["brief_text"] = render_brief_text(load_brief_template(project, profile_id, user_home, scope), payload)

    write_json(json_path, payload)
    text_path.write_text(payload["brief_text"], encoding="utf-8")
    return payload


def load_or_refresh_latest_brief(project: Path, profile_id: str, state: dict[str, Any], user_home: Path | None = None) -> dict[str, Any]:
    scope = scope_from_state(state)
    path = latest_brief_dir(project, profile_id, str(state["instance_id"]), user_home, scope) / "brief.json"
    if not path.exists():
        return write_latest_brief(project, profile_id, state, user_home=user_home)
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return write_latest_brief(project, profile_id, state, user_home=user_home)
    if (
        payload.get("state_version") != state.get("state_version")
        or payload.get("state") != state.get("current_state")
        or not payload.get("brief_path")
        or not payload.get("brief_text_path")
    ):
        return write_latest_brief(project, profile_id, state, user_home=user_home)
    payload["brief_path"] = str(path)
    payload["brief_text_path"] = str(path.with_name("brief.md"))
    return payload


def record_brief_injection(project: Path, source: str, session_id: str, payload: dict[str, Any], user_home: Path | None = None) -> dict[str, Any]:
    profile_id = str(payload["profile_id"])
    instance_id = str(payload["instance_id"])
    scope = str(payload.get("scope") or "project")
    path = injection_record_path(project, source, session_id, profile_id, instance_id, user_home, scope)
    record = read_json(path) if path.exists() else {
        "source": source,
        "session_id": session_id,
        "profile_id": profile_id,
        "instance_id": instance_id,
        "brief_hashes": [],
        "records": [],
    }
    hashes = record.get("brief_hashes")
    if not isinstance(hashes, list):
        hashes = []
        record["brief_hashes"] = hashes
    brief_hash = str(payload["brief_hash"])
    already_injected = brief_hash in hashes
    if not already_injected:
        hashes.append(brief_hash)
        records = record.get("records")
        if not isinstance(records, list):
            records = []
            record["records"] = records
        records.append({"brief_hash": brief_hash, "state": payload.get("state"), "state_version": payload.get("state_version"), "injected_at": now_iso()})
    record["updated_at"] = now_iso()
    write_json(path, record)
    return {"already_injected": already_injected, "injection_record_path": str(path)}


def brief_was_injected(project: Path, source: str, session_id: str, payload: dict[str, Any], user_home: Path | None = None) -> bool:
    profile_id = str(payload["profile_id"])
    instance_id = str(payload["instance_id"])
    scope = str(payload.get("scope") or "project")
    path = injection_record_path(project, source, session_id, profile_id, instance_id, user_home, scope)
    if not path.exists():
        return False
    try:
        record = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    hashes = record.get("brief_hashes")
    return isinstance(hashes, list) and str(payload["brief_hash"]) in hashes


def state_by_id(state_machine: dict[str, Any], state_id: str) -> dict[str, Any]:
    states = state_machine.get("states")
    for state in states if isinstance(states, list) else []:
        if isinstance(state, dict) and state.get("id") == state_id:
            return state
    return {}


def normalize_command_prefix(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return " ".join(value)
    return None


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


def shorthand_rules(permissions: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for effect in ["allow", "ask", "deny"]:
        values = permissions.get(effect)
        for value in values if isinstance(values, list) else []:
            if not isinstance(value, str) or "(" not in value or not value.endswith(")"):
                continue
            tool, raw_pattern = value.split("(", 1)
            pattern = raw_pattern[:-1]
            prefix = pattern[:-1] if pattern.endswith("*") else pattern
            rules.append({"effect": effect, "tool": tool.strip(), "match": {"command_prefix": prefix.strip()}})
    return rules


def rule_matches(rule: dict[str, Any], tool_name: str, command: str) -> bool:
    rule_tool = rule.get("tool")
    if isinstance(rule_tool, str) and rule_tool != tool_name:
        return False
    match = rule.get("match")
    if not isinstance(match, dict):
        return True
    command_prefix = normalize_command_prefix(match.get("command_prefix"))
    if command_prefix is not None:
        return command.startswith(command_prefix)
    return True


def evaluate_permissions(project: Path, profile_id: str, state: dict[str, Any], envelope: dict[str, Any], user_home: Path | None = None) -> dict[str, Any]:
    state_machine = profile_state_machine(project, profile_id, user_home, scope_from_state(state))
    current_state = state_by_id(state_machine, str(state.get("current_state") or ""))
    permissions = current_state.get("permissions")
    if not isinstance(permissions, dict):
        return {"effect": "allow", "reason": "guard_passed"}

    rules = permissions.get("rules")
    normalized_rules = [rule for rule in rules if isinstance(rule, dict)] if isinstance(rules, list) else []
    normalized_rules.extend(shorthand_rules(permissions))
    tool_name = tool_name_from_envelope(envelope)
    command = command_from_envelope(envelope)
    for rule in normalized_rules:
        if rule_matches(rule, tool_name, command):
            return {
                "effect": str(rule.get("effect") or "allow"),
                "reason": str(rule.get("reason") or rule.get("effect") or "guard_passed"),
                "suggestion": rule.get("suggestion"),
            }
    return {"effect": str(permissions.get("default") or "allow"), "reason": "guard_passed"}


def focus_boundary_result(
    project: Path,
    user_home: Path,
    source: str,
    session_id: str,
    deny_on_no_focus: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any], int]:
    focus = resolve_focus(project, user_home, source, session_id)
    if focus["status"] == "none":
        audit_path = write_audit(project, "allow", "no_session_focus_instance", {"source": source, "session_id": session_id})
        status = "no_session_focus_instance" if deny_on_no_focus else "allow"
        return None, {
            "status": status,
            "reason": "no_session_focus_instance",
            "audit_path": str(audit_path),
            "next": "先 activate（激活）当前 Session Focus Instance（会话焦点实例）。",
        }, 1 if deny_on_no_focus else 0
    if focus["status"] == "invalid":
        audit_path = write_audit(project, "deny", "invalid_session_focus_binding", focus)
        return None, {"status": "deny", "reason": "invalid_session_focus_binding", "audit_path": str(audit_path)}, 1
    if focus["status"] == "multiple":
        audit_path = write_audit(project, "deny", "multiple_session_focus_bindings", focus)
        return None, {"status": "deny", "reason": "multiple_session_focus_bindings", "audit_path": str(audit_path)}, 1

    binding = focus["binding"]
    profile_id = str(binding["profile_id"])
    instance_id = str(binding["instance_id"])
    scope = str(binding.get("scope") or "project")
    state = load_instance(project, profile_id, instance_id, user_home, scope)
    if state is None or state.get("status") != "active":
        audit_path = write_audit(
            project,
            "allow",
            "no_session_focus_instance",
            {"source": source, "session_id": session_id, "profile_id": profile_id, "instance_id": instance_id},
            user_home,
            scope,
        )
        status = "no_session_focus_instance" if deny_on_no_focus else "allow"
        return None, {"status": status, "reason": "no_session_focus_instance", "audit_path": str(audit_path)}, 1 if deny_on_no_focus else 0
    return {"binding": binding, "state": state}, {}, 0


def route_pre_tool_use(project: Path, user_home: Path, envelope: dict[str, Any]) -> tuple[dict[str, Any], int]:
    context = envelope.get("context", {})
    source = str(envelope.get("source") or "")
    session_id = str(context.get("session_id") or "")
    if not session_id:
        return {"status": "error", "reason": "missing_session_id"}, 1
    focus, boundary_body, code = focus_boundary_result(project, user_home, source, session_id, False)
    if focus is None:
        return boundary_body, code

    binding = focus["binding"]
    state = focus["state"]
    profile_id = str(binding["profile_id"])
    scope = scope_from_state(state)
    if profile_runtime_api_version(project, profile_id, user_home, scope) != RUNTIME_API_VERSION:
        audit_path = write_audit(project, "allow", "incompatible_runtime_api_version", {"profile_id": profile_id}, user_home, scope)
        return {"status": "allow", "reason": "incompatible_runtime_api_version", "audit_path": str(audit_path)}, 0

    permission = evaluate_permissions(project, profile_id, state, envelope, user_home)
    effect = permission["effect"]
    if effect == "deny":
        audit_path = write_audit(project, "deny", str(permission["reason"]), {"permission": permission}, user_home, scope)
        brief = write_latest_brief(project, profile_id, state, [str(permission["reason"])], audit_path, user_home)
        return {"status": "deny", "reason": permission["reason"], "suggestion": permission.get("suggestion"), "audit_path": str(audit_path)}, 1
    if effect == "ask":
        audit_path = write_audit(project, "ask", str(permission["reason"]), {"permission": permission}, user_home, scope)
        brief = write_latest_brief(project, profile_id, state, [str(permission["reason"])], audit_path, user_home)
        return {"status": "ask", "reason": permission["reason"], "suggestion": permission.get("suggestion"), "audit_path": str(audit_path)}, 1
    audit_path = write_audit(project, "allow", str(permission["reason"]), {"permission": permission}, user_home, scope)
    return {"status": "allow", "reason": permission["reason"], "audit_path": str(audit_path)}, 0


def artifact_path(project: Path, user_home: Path | None, scope: str, template: str, profile_id: str, instance_id: str, state_version: int) -> Path:
    formatted = template.format(
        profile_id=profile_id,
        guard_profile_id=profile_id,
        instance_id=instance_id,
        state_version=state_version,
    )
    path = Path(formatted)
    if path.is_absolute():
        return path
    if scope == "user":
        parts = path.parts
        if len(parts) >= 2 and parts[0] == ".local" and parts[1] == "guard":
            return runtime_root(project, user_home, scope).joinpath(*parts[2:])
        return runtime_root(project, user_home, scope) / path
    return project / path


def artifact_exists(project: Path, profile_id: str, instance_id: str, state_version: int, artifact_id: str, user_home: Path | None = None, scope: str = "project") -> bool:
    artifacts = read_yaml(profile_dir(project, profile_id, user_home, scope) / "artifacts.yaml").get("artifacts", [])
    for artifact in artifacts if isinstance(artifacts, list) else []:
        if not isinstance(artifact, dict) or artifact.get("id") != artifact_id:
            continue
        template = artifact.get("path")
        if not isinstance(template, str):
            return False
        return artifact_path(project, user_home, scope, template, profile_id, instance_id, state_version).exists()
    return False


def acquire_instance_lock(project: Path, profile_id: str, instance_id: str, timeout_seconds: float, user_home: Path | None = None, scope: str = "project") -> tuple[bool, Path]:
    lock_path = runtime_root(project, user_home, scope) / "locks" / profile_id / f"{instance_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True, lock_path
        except FileExistsError:
            if time.monotonic() - started >= timeout_seconds:
                return False, lock_path
            time.sleep(0.05)


def release_instance_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def run_state_completed(project: Path, user_home: Path, source: str, session_id: str, lock_timeout: float) -> tuple[dict[str, Any], int]:
    focus, boundary_body, code = focus_boundary_result(project, user_home, source, session_id, True)
    if focus is None:
        if boundary_body.get("status") == "deny":
            boundary_body["status"] = boundary_body["reason"]
        return boundary_body, code

    binding = focus["binding"]
    state = focus["state"]
    profile_id = str(binding["profile_id"])
    instance_id = str(binding["instance_id"])
    scope = scope_from_state(state)
    current_brief = load_or_refresh_latest_brief(project, profile_id, state, user_home)
    if not brief_was_injected(project, source, session_id, current_brief, user_home):
        return {
            **current_brief,
            "status": "brief_required",
            "reason": "latest_guard_brief_required",
            "already_injected": False,
            "next": "读取当前 Session Focus Instance（会话焦点实例）的最新 Guard Brief（守卫简报）后，再提交 state_completed。",
        }, 1

    acquired, lock_path = acquire_instance_lock(project, profile_id, instance_id, lock_timeout, user_home, scope)
    if not acquired:
        audit_path = write_audit(project, "lock_timeout", "lock_timeout", {"profile_id": profile_id, "instance_id": instance_id, "lock_path": str(lock_path)}, user_home, scope)
        return {"status": "lock_timeout", "reason": "lock_timeout", "lock_path": str(lock_path), "audit_path": str(audit_path)}, 1

    try:
        state_machine = profile_state_machine(project, profile_id, user_home, scope)
        transitions = state_machine.get("transitions", [])
        current_state = state.get("current_state")
        state_version = int(state.get("state_version") or 1)
        for transition in transitions if isinstance(transitions, list) else []:
            if not isinstance(transition, dict):
                continue
            if transition.get("from") != current_state or transition.get("on_event") != "state_completed":
                continue
            required = [item for item in transition.get("required_artifacts", []) if isinstance(item, str)]
            if any(not artifact_exists(project, profile_id, instance_id, state_version, artifact, user_home, scope) for artifact in required):
                continue
            state["current_state"] = transition.get("to")
            state["state_version"] = state_version + 1
            state["last_transition_id"] = transition.get("id")
            state["last_seen_at"] = now_iso()
            save_instance(project, state, user_home)
            audit_path = write_audit(project, "allow", "state_completed", {"profile_id": profile_id, "instance_id": instance_id, "transition": transition}, user_home, scope)
            brief = write_latest_brief(project, profile_id, state, audit_path=audit_path, user_home=user_home)
            return {
                "status": "allow",
                "reason": "state_completed",
                "profile_id": profile_id,
                "instance_id": instance_id,
                "transition_id": transition.get("id"),
                "state_version": state["state_version"],
                "audit_path": str(audit_path),
                "brief_path": brief["brief_path"],
                "brief_hash": brief["brief_hash"],
            }, 0
        audit_path = write_audit(project, "error", "missing_required_artifacts", {"profile_id": profile_id, "instance_id": instance_id}, user_home, scope)
        brief = write_latest_brief(project, profile_id, state, ["missing_required_artifacts"], audit_path, user_home)
        return {"status": "error", "reason": "missing_required_artifacts", "audit_path": str(audit_path), "brief_path": brief["brief_path"], "brief_hash": brief["brief_hash"]}, 1
    finally:
        release_instance_lock(lock_path)


def run_brief(project: Path, user_home: Path, source: str, session_id: str) -> tuple[dict[str, Any], int]:
    focus, boundary_body, code = focus_boundary_result(project, user_home, source, session_id, True)
    if focus is None:
        return boundary_body, code

    binding = focus["binding"]
    state = focus["state"]
    profile_id = str(binding["profile_id"])
    payload = load_or_refresh_latest_brief(project, profile_id, state, user_home)
    injection = record_brief_injection(project, source, session_id, payload, user_home)
    already_injected = injection["already_injected"]
    status = "already_injected" if already_injected else "injectable"
    body = {
        **payload,
        "status": status,
        "already_injected": already_injected,
        "injection_record_path": injection["injection_record_path"],
    }
    return body, 0
