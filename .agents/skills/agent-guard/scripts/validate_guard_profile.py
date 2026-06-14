"""校验最小 Guard Profile（守卫画像）契约。"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REQUIRED_FILES = {
    "manifest": "GUARD-MANIFEST.yaml",
    "target_model": "target-model.yaml",
    "activation_model": "activation-model.yaml",
    "subject_resolver": "subject-resolver.yaml",
    "execution_model": "execution-model.yaml",
    "observation_model": "observation-model.yaml",
    "state_machine": "state-machine.yaml",
    "guard_points": "guard-points.yaml",
    "artifacts": "artifacts.yaml",
    "hook_bindings": "hook-bindings.yaml",
    "brief_template": "brief-template.md",
    "validation_plan": "validation-plan.md",
}

ALLOWED_PROFILE_SOURCE_KINDS = {"grill-with-docs-confirmed-notes", "built-in-minimal-sample"}

REQUIRED_FIELDS = {
    "manifest": [
        "schema_version",
        "guard_profile_id",
        "name",
        "description",
        "source.kind",
    ],
    "target_model": [
        "target.id",
        "target.type",
        "target.name",
        "target.source",
        "target.boundary",
    ],
    "activation_model": [
        "activation.allowed_sources",
        "activation.required_profile_ref",
        "activation.scopes",
        "activation.on_existing_subject",
        "activation.on_missing_subject",
        "activation.initial_state",
    ],
    "subject_resolver": [
        "subject.identity_fields",
        "subject.required_fields",
        "subject.context_sources",
        "subject.existing_match_policy",
        "subject.create_policy",
        "subject.ambiguous_policy",
    ],
    "execution_model": ["nodes", "states"],
    "observation_model": ["signals"],
    "state_machine": ["initial_state", "terminal_states", "states", "transitions"],
    "guard_points": ["guard_points"],
    "artifacts": ["artifacts"],
    "hook_bindings": ["hook_bindings"],
}


@dataclass(frozen=True)
class ValidationIssue:
    category: str
    field: str
    message: str
    fix: str

    def render(self) -> str:
        return (
            f"错误：category={self.category} field={self.field} {self.message}\n"
            f"修复：{self.fix}"
        )


def load_yaml(path: Path, category: str) -> tuple[dict[str, Any] | None, ValidationIssue | None]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, ValidationIssue(
            category,
            str(path),
            f"包含无效 YAML（YAML 配置格式）：{exc}",
            "修正 YAML（YAML 配置格式）语法。",
        )
    if not isinstance(data, dict):
        return None, ValidationIssue(
            category,
            str(path),
            "顶层必须是 YAML mapping（YAML 映射）。",
            "把文件内容改成 key-value YAML（键值 YAML）。",
        )
    return data, None


def value_at(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)) and not value:
        return False
    return True


def is_payload_field(value: Any) -> bool:
    return isinstance(value, str) and (value == "payload" or value.startswith("payload."))


def require_fields(category: str, data: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for field in REQUIRED_FIELDS.get(category, []):
        if not is_present(value_at(data, field)):
            issues.append(
                ValidationIssue(
                    category,
                    field,
                    "是最小 Guard Profile（守卫画像）契约的必填字段。",
                    f"在 {REQUIRED_FILES[category]} 中添加 `{field}`。",
                )
            )
    return issues


def validate_manifest_contract(data: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if "mode" in data:
        issues.append(
            ValidationIssue(
                "manifest",
                "mode",
                "已废弃，不能出现在 GUARD-MANIFEST.yaml 中。",
                "删除 `mode`；状态权限请写入 state-machine.yaml 的 `states[].permissions`。",
            )
        )

    source_kind = value_at(data, "source.kind")
    if source_kind not in ALLOWED_PROFILE_SOURCE_KINDS:
        issues.append(
            ValidationIssue(
                "manifest",
                "source.kind",
                "必须说明 Guard Profile（守卫画像）来自本轮调研提取，或是内置最小样例。",
                "用 extract_guard_model.py 从已确认调研记录生成画像，或使用内置 minimal-sample 模板。",
            )
        )
    if source_kind == "grill-with-docs-confirmed-notes":
        source_status = value_at(data, "source.status")
        if source_status != "confirmed":
            issues.append(
                ValidationIssue(
                    "manifest",
                    "source.status",
                    "必须是 `confirmed`，表示已完成 `$grill-with-docs`（带文档拷问方法）调研确认。",
                    "先用 `$grill-with-docs`（带文档拷问方法）确认术语、决策、边界、场景、例外和文档变更，再重新提取 Guard Profile（守卫画像）。",
                )
            )
    return issues


def deprecated_field_issue(category: str, field: str) -> ValidationIssue:
    return ValidationIssue(
        category,
        field,
        "已废弃，不能出现在 Guard Profile（守卫画像）中。",
        f"删除 `{field.split('.')[-1]}`；状态权限请写入 state-machine.yaml 的 `states[].permissions`。",
    )


def validate_deprecated_fields(configs: dict[str, dict[str, Any]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for transition in configs["state_machine"].get("transitions", []):
        if not isinstance(transition, dict):
            continue
        transition_id = transition.get("id", "<unknown>")
        if "advance_on_warn_failure" in transition:
            issues.append(
                deprecated_field_issue(
                    "state_machine",
                    f"transitions.{transition_id}.advance_on_warn_failure",
                )
            )

    for guard_point in configs["guard_points"].get("guard_points", []):
        if not isinstance(guard_point, dict):
            continue
        guard_point_id = guard_point.get("id", "<unknown>")
        for field in ["mode", "on_fail", "on_error"]:
            if field in guard_point:
                issues.append(
                    deprecated_field_issue(
                        "guard_points",
                        f"guard_points.{guard_point_id}.{field}",
                    )
                )

    for binding in configs["hook_bindings"].get("hook_bindings", []):
        if not isinstance(binding, dict):
            continue
        binding_id = binding.get("id", "<unknown>")
        if "blocking" in binding:
            issues.append(
                deprecated_field_issue(
                    "hook_bindings",
                    f"hook_bindings.{binding_id}.blocking",
                )
            )
    return issues


def list_ids(data: dict[str, Any], field: str) -> set[str]:
    value = value_at(data, field)
    if not isinstance(value, list):
        return set()
    ids: set[str] = set()
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            ids.add(item["id"])
    return ids


def hook_binding_has_trigger(binding: dict[str, Any]) -> bool:
    if is_present(binding.get("trigger_event")):
        return True
    trigger = binding.get("trigger")
    return isinstance(trigger, dict) and is_present(trigger.get("event"))


def validate_hook_binding_contract(configs: dict[str, dict[str, Any]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    signal_ids = list_ids(configs["observation_model"], "signals")
    bindings = configs["hook_bindings"].get("hook_bindings", [])
    for index, binding in enumerate(bindings if isinstance(bindings, list) else []):
        if not isinstance(binding, dict):
            continue
        binding_id = binding.get("id") if isinstance(binding.get("id"), str) else f"#{index}"
        for field in ["source", "event_type"]:
            if not is_present(binding.get(field)):
                issues.append(
                    ValidationIssue(
                        "hook_bindings",
                        f"hook_bindings.{binding_id}.{field}",
                        "是 Hook Binding（钩子绑定）契约的必填字段。",
                        f"在 hook-bindings.yaml 的 `{binding_id}` 绑定中添加 `{field}`。",
                    )
                )
        if not hook_binding_has_trigger(binding):
            issues.append(
                ValidationIssue(
                    "hook_bindings",
                    f"hook_bindings.{binding_id}.trigger_event",
                    "是 Hook Binding（钩子绑定）契约的必填字段。",
                    "添加 `trigger_event`，或添加 `trigger.event`。",
                )
            )
        event_type = binding.get("event_type")
        source = binding.get("source")
        if isinstance(source, str) and source in {"codex", "git"} and event_type == "state_completed":
            issues.append(
                ValidationIssue(
                    "hook_bindings",
                    f"hook_bindings.{binding_id}.event_type",
                    "Hook（钩子）事件不能映射为 `state_completed`。",
                    "把 Hook Binding（钩子绑定）的 `event_type` 改成观察或权限检查事件；状态推进只能由主 agent（主代理）主动提交 `state_completed`。",
                )
            )
        if isinstance(event_type, str) and event_type not in signal_ids:
            issues.append(
                missing_reference(
                    "hook_bindings",
                    f"hook_bindings.{binding_id}.event_type",
                    event_type,
                    "observation_model.signals",
                    "定义该 signal（信号），或更新 Hook Binding（钩子绑定）的 `event_type`。",
                )
            )
    return issues


def validate_state_permissions(configs: dict[str, dict[str, Any]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    valid_effects = {"allow", "ask", "deny"}
    states = configs["state_machine"].get("states", [])
    for state in states if isinstance(states, list) else []:
        if not isinstance(state, dict):
            continue
        state_id = state.get("id", "<unknown>")
        permissions = state.get("permissions")
        if not isinstance(permissions, dict):
            continue
        default = permissions.get("default")
        if default not in valid_effects:
            issues.append(
                ValidationIssue(
                    "state_machine",
                    f"states.{state_id}.permissions.default",
                    "必须是 `allow`、`ask` 或 `deny`。",
                    "把 `permissions.default` 改成 `allow`、`ask` 或 `deny`。",
                )
            )
        rules = permissions.get("rules")
        if rules is not None and not isinstance(rules, list):
            issues.append(
                ValidationIssue(
                    "state_machine",
                    f"states.{state_id}.permissions.rules",
                    "必须是权限规则清单。",
                    "把 `permissions.rules` 改成 YAML list（YAML 清单），每项使用结构化权限规则。",
                )
            )
            rules = []
        for index, rule in enumerate(rules if isinstance(rules, list) else []):
            if not isinstance(rule, dict):
                issues.append(
                    ValidationIssue(
                        "state_machine",
                        f"states.{state_id}.permissions.rules.{index}",
                        "必须是 YAML mapping（YAML 映射）的结构化权限规则。",
                        "把该规则改成包含 `effect`、`tool` 和 `match` 的 mapping（映射），或使用 allow/ask/deny 简写清单。",
                    )
                )
                continue
            if rule.get("effect") not in valid_effects:
                issues.append(
                    ValidationIssue(
                        "state_machine",
                        f"states.{state_id}.permissions.rules.{index}.effect",
                        "必须是 `allow`、`ask` 或 `deny`。",
                        "把权限规则的 `effect` 改成 `allow`、`ask` 或 `deny`。",
                    )
                )
        for effect in ["allow", "ask", "deny"]:
            shorthand = permissions.get(effect)
            if shorthand is None:
                continue
            if not isinstance(shorthand, list):
                issues.append(
                    ValidationIssue(
                        "state_machine",
                        f"states.{state_id}.permissions.{effect}",
                        "必须是可以规范化为 `permissions.rules` 的清单。",
                        f"把 `{effect}` 改成字符串清单，例如 `Bash(git status*)`，或改写为 `permissions.rules`。",
                    )
                )
                continue
            for index, value in enumerate(shorthand):
                if shorthand_permission_rule(effect, value) is None:
                    issues.append(
                        ValidationIssue(
                            "state_machine",
                            f"states.{state_id}.permissions.{effect}.{index}",
                            "不能规范化为 `permissions.rules`。",
                            f"把 `{value}` 改成 `<tool>(<command-prefix>*)` 格式，或改写为结构化 `permissions.rules`。",
                        )
                    )
    return issues


def permissions_include_deny(permissions: Any) -> bool:
    if not isinstance(permissions, dict):
        return False
    if permissions.get("default") == "deny":
        return True
    rules = permissions.get("rules")
    if isinstance(rules, list):
        for rule in rules:
            if isinstance(rule, dict) and rule.get("effect") == "deny":
                return True
    deny = permissions.get("deny")
    return isinstance(deny, list) and bool(deny)


def state_machine_has_deny_permissions(state_machine: dict[str, Any]) -> bool:
    states = state_machine.get("states")
    for state in states if isinstance(states, list) else []:
        if isinstance(state, dict) and permissions_include_deny(state.get("permissions")):
            return True
    return False


def profile_has_deny_permissions(profile_dir: Path) -> bool:
    path = profile_dir / "state-machine.yaml"
    data, issue = load_yaml(path, "state_machine")
    if issue or data is None:
        return False
    return state_machine_has_deny_permissions(data)


def validate_artifact_contract(configs: dict[str, dict[str, Any]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    artifacts = configs["artifacts"].get("artifacts", [])
    for index, artifact in enumerate(artifacts if isinstance(artifacts, list) else []):
        if not isinstance(artifact, dict):
            continue
        artifact_id = artifact.get("id") if isinstance(artifact.get("id"), str) else f"#{index}"
        reuse_policy = artifact.get("reuse_policy", "deny")
        if reuse_policy not in {"deny", "allow"}:
            issues.append(
                ValidationIssue(
                    "artifacts",
                    f"artifacts.{artifact_id}.reuse_policy",
                    "必须是 `deny` 或 `allow`。",
                    "把 `reuse_policy` 改成 `deny` 或 `allow`；未写时默认按 `deny` 处理。",
                )
            )
    return issues


def has_items(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def is_unconditional_state_completed_transition(transition: dict[str, Any]) -> bool:
    return (
        transition.get("on_event") == "state_completed"
        and not has_items(transition.get("conditions"))
        and not has_items(transition.get("guard_points"))
        and not has_items(transition.get("required_artifacts"))
    )


def validate_state_transition_shape(configs: dict[str, dict[str, Any]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    state_ids = list_ids(configs["state_machine"], "states")
    terminal_states = {
        state
        for state in configs["state_machine"].get("terminal_states", [])
        if isinstance(state, str)
    }
    transitions = configs["state_machine"].get("transitions", [])
    transitions_by_from: dict[str, list[dict[str, Any]]] = {state_id: [] for state_id in state_ids}
    unconditional_by_from: dict[str, list[str]] = {}
    missing_transition_id_fields: list[str] = []
    seen_transition_ids: set[str] = set()
    duplicate_transition_ids: set[str] = set()

    for index, transition in enumerate(transitions if isinstance(transitions, list) else []):
        if not isinstance(transition, dict):
            continue
        transition_id = transition.get("id")
        if not is_present(transition_id) or not isinstance(transition_id, str):
            missing_transition_id_fields.append(f"transitions.{index}.id")
        else:
            if transition_id in seen_transition_ids:
                duplicate_transition_ids.add(transition_id)
            seen_transition_ids.add(transition_id)
        from_state = transition.get("from")
        if isinstance(from_state, str):
            transitions_by_from.setdefault(from_state, []).append(transition)
            if is_unconditional_state_completed_transition(transition):
                transition_id = transition.get("id")
                unconditional_by_from.setdefault(from_state, []).append(
                    transition_id if isinstance(transition_id, str) else "<unknown>"
                )

    for field in missing_transition_id_fields:
        issues.append(
            ValidationIssue(
                "state_machine",
                field,
                "是必填字段，且必须唯一，用于审计和错误输出。",
                "为每条状态转换设置唯一 `id`；主 agent（主代理）不得通过转换 ID 选择下一状态。",
            )
        )

    for transition_id in sorted(duplicate_transition_ids):
        issues.append(
            ValidationIssue(
                "state_machine",
                f"transitions.{transition_id}.id",
                "必须唯一，不能被多条状态转换重复使用。",
                "为每条状态转换设置唯一 `id`，用于审计和错误输出。",
            )
        )

    for state_id in sorted(state_ids - terminal_states):
        outgoing = transitions_by_from.get(state_id, [])
        if not any(transition.get("on_event") == "state_completed" for transition in outgoing):
            issues.append(
                ValidationIssue(
                    "state_machine",
                    f"states.{state_id}.transitions",
                    "非终止状态完成后没有 `state_completed` 出口转换。",
                    "为该状态添加唯一的 `state_completed` 转换，或把该状态加入 `terminal_states`。",
                )
            )

    for state_id, transition_ids in sorted(unconditional_by_from.items()):
        if len(transition_ids) <= 1:
            continue
        issues.append(
            ValidationIssue(
                "state_machine",
                f"states.{state_id}.transitions",
                f"存在重复无条件 `state_completed` 转换：{', '.join(transition_ids)}。",
                "为这些转换添加互斥条件、Guard Point（守卫点）或 required_artifacts（必需产物），确保完成后只能唯一匹配一条转换。",
            )
        )

    return issues


def shorthand_permission_rule(effect: str, value: Any) -> dict[str, Any] | None:
    if effect not in {"allow", "ask", "deny"}:
        return None
    if not isinstance(value, str) or "(" not in value or not value.endswith(")"):
        return None
    tool, remainder = value.split("(", 1)
    command_pattern = remainder[:-1].strip()
    if not tool.strip() or not command_pattern:
        return None
    tool_name = tool.strip()
    if tool_name.lower() in {"read", "write", "edit", "multi_edit"}:
        return {
            "effect": effect,
            "tool": tool_name,
            "match": {"path": command_pattern},
        }
    command_prefix = command_pattern[:-1].strip() if command_pattern.endswith("*") else command_pattern
    if not command_prefix:
        return None
    return {
        "effect": effect,
        "tool": tool_name,
        "match": {"command_prefix": command_prefix},
    }


def validate_references(configs: dict[str, dict[str, Any]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    state_ids = list_ids(configs["state_machine"], "states")
    transition_ids = list_ids(configs["state_machine"], "transitions")
    guard_point_ids = list_ids(configs["guard_points"], "guard_points")
    guard_points_by_id = {
        item["id"]: item
        for item in configs["guard_points"].get("guard_points", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    artifact_ids = list_ids(configs["artifacts"], "artifacts")
    signal_ids = list_ids(configs["observation_model"], "signals")
    node_ids = list_ids(configs["execution_model"], "nodes")

    issues.extend(validate_deprecated_fields(configs))
    issues.extend(validate_hook_binding_contract(configs))
    issues.extend(validate_state_permissions(configs))
    issues.extend(validate_artifact_contract(configs))
    issues.extend(validate_state_transition_shape(configs))

    activation_initial_state = value_at(configs["activation_model"], "activation.initial_state")
    if isinstance(activation_initial_state, str) and activation_initial_state not in state_ids:
        issues.append(
            missing_reference(
                "activation_model",
                "activation.initial_state",
                activation_initial_state,
                "state_machine.states",
                "定义该状态，或更新 `activation.initial_state`。",
            )
        )

    initial_state = configs["state_machine"].get("initial_state")
    if isinstance(initial_state, str) and initial_state not in state_ids:
        issues.append(
            missing_reference(
                "state_machine",
                "initial_state",
                initial_state,
                "states",
                "定义该状态，或修改 `initial_state`。",
            )
        )

    for terminal_state in configs["state_machine"].get("terminal_states", []):
        if terminal_state not in state_ids:
            issues.append(
                missing_reference(
                    "state_machine",
                    "terminal_states",
                    terminal_state,
                    "states",
                    "定义该终止状态，或移除该引用。",
                )
            )

    for transition in configs["state_machine"].get("transitions", []):
        if not isinstance(transition, dict):
            continue
        transition_id = transition.get("id", "<unknown>")
        for field in ["from", "to"]:
            state = transition.get(field)
            if isinstance(state, str) and state not in state_ids:
                issues.append(
                    missing_reference(
                        "state_machine",
                        f"transitions.{transition_id}.{field}",
                        state,
                        "states",
                        "定义该状态，或更新该状态转换。",
                    )
                )
        for guard_point in transition.get("guard_points", []):
            if guard_point not in guard_point_ids:
                issues.append(
                    missing_reference(
                        "state_machine",
                        f"transitions.{transition_id}.guard_points",
                        guard_point,
                        "guard_points",
                        "定义该守卫点，或移除状态转换里的引用。",
                    )
                )
        for artifact in transition.get("required_artifacts", []):
            if artifact not in artifact_ids:
                issues.append(
                    missing_reference(
                        "state_machine",
                        f"transitions.{transition_id}.required_artifacts",
                        artifact,
                        "artifacts",
                        "定义该产物，或移除状态转换里的引用。",
                    )
                )
        event_type = transition.get("on_event")
        if isinstance(event_type, str) and event_type != "state_completed":
            issues.append(
                ValidationIssue(
                    "state_machine",
                    f"transitions.{transition_id}.on_event",
                    f"必须是 `state_completed`，当前是 `{event_type}`。",
                    "把状态推进转换的 `on_event` 改为 `state_completed`；普通 Hook（钩子）事件只能做权限检查。",
                )
            )
        if isinstance(event_type, str) and event_type not in signal_ids:
            issues.append(
                missing_reference(
                    "state_machine",
                    f"transitions.{transition_id}.on_event",
                    event_type,
                    "observation_model.signals",
                    "定义该信号，或更新 `on_event`。",
                )
            )
        if event_type == "state_completed":
            conditions = transition.get("conditions")
            for index, condition in enumerate(conditions if isinstance(conditions, list) else []):
                if not isinstance(condition, dict):
                    continue
                if is_payload_field(condition.get("field")):
                    issues.append(
                        ValidationIssue(
                            "state_machine",
                            f"transitions.{transition_id}.conditions.{index}.field",
                            "`state_completed` 不能用 `payload.*` 选择完成证据。",
                            "把完成证据写入 artifacts.yaml 声明的产物路径，或改用非 payload 的上下文字段。",
                        )
                    )
            for guard_point_id in transition.get("guard_points", []):
                guard_point = guard_points_by_id.get(guard_point_id)
                if not isinstance(guard_point, dict):
                    continue
                checks = guard_point.get("checks")
                for check in checks if isinstance(checks, list) else []:
                    if not isinstance(check, dict) or check.get("type") != "event_field":
                        continue
                    if is_payload_field(check.get("field")):
                        check_id = check.get("id", "<unknown>")
                        issues.append(
                            ValidationIssue(
                                "guard_points",
                                f"guard_points.{guard_point_id}.checks.{check_id}.field",
                                "`state_completed` 不能用 `payload.*` 作为完成证据。",
                                "把完成证据写入 artifacts.yaml 声明的产物路径，再用 artifact_exists 或 artifact_freshness 检查。",
                            )
                        )

    for guard_point in configs["guard_points"].get("guard_points", []):
        if not isinstance(guard_point, dict):
            continue
        guard_point_id = guard_point.get("id", "<unknown>")
        for artifact in guard_point.get("required_artifacts", []):
            if artifact not in artifact_ids:
                issues.append(
                    missing_reference(
                        "guard_points",
                        f"guard_points.{guard_point_id}.required_artifacts",
                        artifact,
                        "artifacts",
                        "定义该产物，或移除 Guard Point（守卫点）里的引用。",
                    )
                )
        inputs = guard_point.get("inputs")
        input_artifacts = value_at(inputs, "artifacts") if isinstance(inputs, dict) else []
        for artifact in input_artifacts if isinstance(input_artifacts, list) else []:
            if artifact not in artifact_ids:
                issues.append(
                    missing_reference(
                        "guard_points",
                        f"guard_points.{guard_point_id}.inputs.artifacts",
                        artifact,
                        "artifacts",
                        "定义该产物，或移除 Guard Point（守卫点）输入里的引用。",
                    )
                )
        checks = guard_point.get("checks")
        for check in checks if isinstance(checks, list) else []:
            if not isinstance(check, dict):
                continue
            check_id = check.get("id", "<unknown>")
            if check.get("type") not in {"artifact_exists", "artifact_freshness"}:
                continue
            artifact = check.get("artifact") or check.get("artifact_id")
            if isinstance(artifact, str) and artifact not in artifact_ids:
                issues.append(
                    missing_reference(
                        "guard_points",
                        f"guard_points.{guard_point_id}.checks.{check_id}.artifact",
                        artifact,
                        "artifacts",
                        "定义该产物，或更新 Guard Point（守卫点）检查里的 artifact。",
                    )
                )

    for binding in configs["hook_bindings"].get("hook_bindings", []):
        if not isinstance(binding, dict):
            continue
        binding_id = binding.get("id", "<unknown>")
        for transition in binding.get("transitions", []):
            if transition not in transition_ids:
                issues.append(
                    missing_reference(
                        "hook_bindings",
                        f"hook_bindings.{binding_id}.transitions",
                        transition,
                        "state_machine.transitions",
                        "定义该状态转换，或移除 Hook Binding（钩子绑定）里的引用。",
                    )
                )
        for guard_point in binding.get("guard_points", []):
            if guard_point not in guard_point_ids:
                issues.append(
                    missing_reference(
                        "hook_bindings",
                        f"hook_bindings.{binding_id}.guard_points",
                        guard_point,
                        "guard_points",
                        "定义该守卫点，或移除 Hook Binding（钩子绑定）里的引用。",
                    )
                )

    for node in configs["execution_model"].get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = node.get("id", "<unknown>")
        for signal in node.get("completion_signals", []):
            if signal not in signal_ids:
                issues.append(
                    missing_reference(
                        "execution_model",
                        f"nodes.{node_id}.completion_signals",
                        signal,
                        "observation_model.signals",
                        "定义该信号，或更新节点完成信号。",
                    )
                )
        for artifact in node.get("required_artifacts", []):
            if artifact not in artifact_ids:
                issues.append(
                    missing_reference(
                        "execution_model",
                        f"nodes.{node_id}.required_artifacts",
                        artifact,
                        "artifacts",
                        "定义该产物，或更新节点必需产物。",
                    )
                )

    for state in configs["execution_model"].get("states", []):
        if not isinstance(state, dict):
            continue
        state_id = state.get("id", "<unknown>")
        if isinstance(state_id, str) and state_id not in state_ids:
            issues.append(
                missing_reference(
                    "execution_model",
                    f"states.{state_id}.id",
                    state_id,
                    "state_machine.states",
                    "在 state-machine.yaml 中定义该状态，或更新 execution-model.yaml。",
                )
            )
        for next_node in state.get("allowed_next", []):
            if next_node not in node_ids:
                issues.append(
                    missing_reference(
                        "execution_model",
                        f"states.{state_id}.allowed_next",
                        next_node,
                        "execution_model.nodes",
                        "定义该节点，或从 `allowed_next` 中移除它。",
                    )
                )
        for artifact in state.get("missing_artifacts", []):
            if artifact not in artifact_ids:
                issues.append(
                    missing_reference(
                        "execution_model",
                        f"states.{state_id}.missing_artifacts",
                        artifact,
                        "artifacts",
                        "定义该产物，或从 `missing_artifacts` 中移除它。",
                    )
                )

    return issues


def missing_reference(
    category: str,
    field: str,
    value: str,
    target: str,
    fix: str,
) -> ValidationIssue:
    return ValidationIssue(
        category,
        field,
        f"引用了 `{value}`，但 `{target}` 未定义它。",
        fix,
    )


def validate_profile(profile_dir: Path) -> tuple[list[str], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    configs: dict[str, dict[str, Any]] = {}
    checked: list[str] = []

    if not profile_dir.exists() or not profile_dir.is_dir():
        return checked, [
            ValidationIssue(
                "profile",
                str(profile_dir),
                "不存在或不是目录。",
                "传入 Guard Profile（守卫画像）目录路径。",
            )
        ]

    for category, relative_path in REQUIRED_FILES.items():
        path = profile_dir / relative_path
        if not path.exists():
            issues.append(
                ValidationIssue(
                    category,
                    relative_path,
                    "缺失。",
                    f"把 {relative_path} 添加到 Guard Profile（守卫画像）目录。",
                )
            )
            continue

        if path.suffix in {".yaml", ".yml"}:
            data, issue = load_yaml(path, category)
            if issue:
                issues.append(issue)
                continue
            assert data is not None
            issues.extend(require_fields(category, data))
            if category == "manifest":
                issues.extend(validate_manifest_contract(data))
            configs[category] = data

        checked.append(category)

    reference_categories = {
        "activation_model",
        "state_machine",
        "guard_points",
        "artifacts",
        "hook_bindings",
        "observation_model",
        "execution_model",
    }
    if not issues and reference_categories.issubset(configs):
        issues.extend(validate_references(configs))

    return checked, issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 Guard Profile（守卫画像）目录。")
    parser.add_argument("profile_dir", type=Path)
    args = parser.parse_args(argv)

    checked, issues = validate_profile(args.profile_dir)
    if issues:
        print("失败：Guard Profile（守卫画像）校验未通过")
        for issue in issues:
            print(issue.render())
        return 1

    print("通过：Guard Profile（守卫画像）校验")
    for category in checked:
        print(f"已检查：{category}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
