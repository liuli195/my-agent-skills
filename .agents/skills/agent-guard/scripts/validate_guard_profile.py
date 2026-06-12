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

REQUIRED_FIELDS = {
    "manifest": [
        "schema_version",
        "guard_profile_id",
        "name",
        "description",
        "mode",
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


def validate_references(configs: dict[str, dict[str, Any]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    state_ids = list_ids(configs["state_machine"], "states")
    transition_ids = list_ids(configs["state_machine"], "transitions")
    guard_point_ids = list_ids(configs["guard_points"], "guard_points")
    artifact_ids = list_ids(configs["artifacts"], "artifacts")
    signal_ids = list_ids(configs["observation_model"], "signals")
    node_ids = list_ids(configs["execution_model"], "nodes")

    issues.extend(validate_hook_binding_contract(configs))

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
