"""校验最小 Guard Profile（守卫画像）契约。"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

import yaml


REQUIRED_FILES = {
    "manifest": "GUARD-MANIFEST.yaml",
    "target_model": "target-model.yaml",
    "state_machine": "state-machine.yaml",
    "guard_points": "guard-points.yaml",
    "artifacts": "artifacts.yaml",
    "brief_template": "brief-template.md",
    "validation_plan": "validation-plan.md",
}

LEGACY_FILES = {
    "subject-resolver.yaml",
    "hook-bindings.yaml",
}

LEGACY_TOKENS = {
    "subject_key_hash",
    "no_subject_match",
    "ambiguous_subject",
    "target_hint",
}

ALLOWED_PROFILE_SOURCE_KINDS = {
    "grill-with-docs-confirmed-notes",
    "built-in-minimal-sample",
    "built-in-comet-review-gate",
}
JSON_ARTIFACT_PREDICATES = {
    "exists",
    "equals",
    "not_equals",
    "number_lte",
    "number_gte",
    "array_none",
    "array_all",
}
JSON_ARTIFACT_VALUE_PREDICATES = {"equals", "not_equals", "number_lte", "number_gte"}
JSON_ARTIFACT_ARRAY_PREDICATES = {"array_none", "array_all"}
GLOBAL_COMMAND_GUARD_VALUE_FROM_FIELDS = {
    "source_scope",
    "profile_id",
    "guard_id",
    "effective_guard_id",
    "runtime_scope",
    "git_head",
    "git_head_short",
}
GLOBAL_COMMAND_GUARDS_FILE = "global-command-guards.yaml"
SESSION_FOCUS_CATEGORIES = {"state_machine", "guard_points", "artifacts"}

REQUIRED_FIELDS = {
    "manifest": [
        "schema_version",
        "runtime_api_version",
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
    "state_machine": ["initial_state", "terminal_states", "states", "transitions"],
    "guard_points": ["guard_points"],
    "artifacts": ["artifacts"],
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
            message = "是最小 Guard Profile（守卫画像）契约的必填字段。"
            fix = f"在 {REQUIRED_FILES[category]} 中添加 `{field}`。"
            if category == "manifest" and field == "runtime_api_version":
                message = "必须声明 Runtime API version（运行时接口版本）。"
                fix = "在 GUARD-MANIFEST.yaml 中添加 `runtime_api_version: agent-guard-runtime/v1`。"
            issues.append(
                ValidationIssue(
                    category,
                    field,
                    message,
                    fix,
                )
            )
    return issues


def validate_legacy_contract(profile_dir: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for relative_path in sorted(LEGACY_FILES):
        path = profile_dir / relative_path
        if path.exists():
            issues.append(
                ValidationIssue(
                    "legacy_contract",
                    relative_path,
                    "已从 Session Focus Binding（会话焦点绑定）契约删除。",
                    f"删除 `{relative_path}`；实例选择只能通过 Session Focus Binding（会话焦点绑定）显式完成。",
                )
            )

    for path in sorted(profile_dir.iterdir()) if profile_dir.exists() else []:
        if not path.is_file() or path.suffix not in {".yaml", ".yml", ".md", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in sorted(LEGACY_TOKENS):
            if token in text:
                issues.append(
                    ValidationIssue(
                        "legacy_contract",
                        f"{path.name}:{token}",
                        "是旧 Subject Resolver（主体解析器）契约残留，不能出现在新 Guard Profile（守卫画像）中。",
                        "改用 opaque instance_id（不透明实例 ID）和 Session Focus Binding（会话焦点绑定）。",
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
                "必须说明 Guard Profile（守卫画像）来自本轮调研提取，或是已知内置模板。",
                "用 extract_guard_model.py 从已确认调研记录生成画像，或使用已知内置模板。",
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
        if "trigger" in guard_point:
            issues.append(
                ValidationIssue(
                    "guard_points",
                    f"guard_points.{guard_point_id}.trigger",
                    "Guard Point（守卫点）不再绑定 Hook（钩子）或事件。",
                    "删除 `trigger`；Hook（钩子）只把标准事件交给 Runtime Router（运行时路由器）。",
                )
            )
        for field in ["mode", "on_fail", "on_error"]:
            if field in guard_point:
                issues.append(
                    deprecated_field_issue(
                        "guard_points",
                        f"guard_points.{guard_point_id}.{field}",
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


def artifact_ids_in_profile(profile_dir: Path) -> set[str]:
    path = profile_dir / REQUIRED_FILES["artifacts"]
    if not path.exists():
        return set()
    data, issue = load_yaml(path, "artifacts")
    if issue or data is None:
        return set()
    return list_ids(data, "artifacts")


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


def named_captures_from_pattern(pattern: str) -> tuple[set[str], ValidationIssue | None]:
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return set(), ValidationIssue(
            "global_command_guards",
            "match.command_patterns",
            f"命令模式不是有效正则表达式：{exc}。",
            "修正 command_patterns 中的正则表达式。",
        )
    return set(compiled.groupindex), None


def template_fields(template: str) -> set[str]:
    return set(re.findall(r"{([A-Za-z_][A-Za-z0-9_]*)}", template))


def validate_global_command_guard_check(
    base: str,
    check_index: int,
    check: Any,
    capture_names: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(check, dict):
        return [
            ValidationIssue(
                "global_command_guards",
                f"{base}.checks.{check_index}",
                "必须是 mapping（映射）。",
                "把该 JSON 检查改成包含 field、predicate 的映射。",
            )
        ]

    field = check.get("field")
    if not isinstance(field, str) or not field:
        issues.append(
            ValidationIssue(
                "global_command_guards",
                f"{base}.checks.{check_index}.field",
                "必须声明 JSON field（JSON 字段）。",
                "为该检查添加非空 field。",
            )
        )

    predicate = check.get("predicate")
    if not isinstance(predicate, str) or predicate not in JSON_ARTIFACT_PREDICATES:
        issues.append(
            ValidationIssue(
                "global_command_guards",
                f"{base}.checks.{check_index}.predicate",
                "未知或缺失 JSON predicate（JSON 谓词）。",
                "使用 json_artifact 支持的 predicate。",
            )
        )
    elif predicate in JSON_ARTIFACT_VALUE_PREDICATES and "value" not in check and "value_from" not in check:
        issues.append(
            ValidationIssue(
                "global_command_guards",
                f"{base}.checks.{check_index}.value",
                "比较类 JSON predicate（JSON 谓词）必须声明 value 或 value_from。",
                "添加 value，或用 value_from 引用命名捕获或内置上下文字段。",
            )
        )
    elif predicate in JSON_ARTIFACT_ARRAY_PREDICATES and not isinstance(check.get("where"), dict):
        issues.append(
            ValidationIssue(
                "global_command_guards",
                f"{base}.checks.{check_index}.where",
                "数组类 JSON predicate（JSON 谓词）必须声明 where。",
                "添加 where 映射描述数组元素检查。",
            )
        )

    value_from = check.get("value_from")
    if value_from is not None:
        if not isinstance(value_from, str) or not value_from:
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{base}.checks.{check_index}.value_from",
                    "必须是非空字符串。",
                    "引用命名捕获或内置上下文字段。",
                )
            )
        elif value_from not in capture_names and value_from not in GLOBAL_COMMAND_GUARD_VALUE_FROM_FIELDS:
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{base}.checks.{check_index}.value_from",
                    "必须引用命名捕获或内置上下文字段。",
                    "把 value_from 改成 command_patterns 的命名捕获，或 source_scope、profile_id、guard_id、effective_guard_id、runtime_scope、git_head、git_head_short。",
                )
            )

    return issues


def validate_global_command_guard_skip_when(
    base: str,
    guard: dict[str, Any],
    capture_names: set[str],
) -> list[ValidationIssue]:
    skip_when = guard.get("skip_when")
    if skip_when is None:
        return []
    if not isinstance(skip_when, list):
        return [
            ValidationIssue(
                "global_command_guards",
                f"{base}.skip_when",
                "必须是 list（列表）。",
                "把 skip_when 改成跳过条件列表；每项可声明 yaml 条件。",
            )
        ]
    if not skip_when:
        return [
            ValidationIssue(
                "global_command_guards",
                f"{base}.skip_when",
                "必须至少声明一个跳过条件。",
                "添加一个 yaml 条件，或删除 skip_when 让守卫始终执行 evidence 检查。",
            )
        ]

    issues: list[ValidationIssue] = []
    for index, condition in enumerate(skip_when):
        yaml_condition = condition.get("yaml") if isinstance(condition, dict) else None
        condition_base = f"{base}.skip_when.{index}.yaml"
        if not isinstance(yaml_condition, dict):
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{base}.skip_when.{index}",
                    "必须声明 yaml mapping（YAML 映射）条件。",
                    "使用 `yaml: {path, field, in}` 结构声明跳过条件。",
                )
            )
            continue

        path = yaml_condition.get("path")
        if not isinstance(path, str) or not path:
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{condition_base}.path",
                    "必须声明非空相对路径模板。",
                    "添加相对路径，例如 `openspec/changes/{change}/.comet.yaml`。",
                )
            )
        else:
            windows_path = PureWindowsPath(path)
            path_parts = path.replace("\\", "/").split("/")
            if Path(path).is_absolute() or windows_path.is_absolute() or windows_path.drive or windows_path.root or ".." in path_parts:
                issues.append(
                    ValidationIssue(
                        "global_command_guards",
                        f"{condition_base}.path",
                        "必须声明安全的相对路径模板。",
                        "使用不含绝对路径或 `..` 的相对路径，例如 `openspec/changes/{change}/.comet.yaml`。",
                    )
                )
            for field in sorted(template_fields(path) - capture_names - GLOBAL_COMMAND_GUARD_VALUE_FROM_FIELDS):
                issues.append(
                    ValidationIssue(
                        "global_command_guards",
                        f"{condition_base}.path.{field}",
                        f"缺少必需捕获值 `{field}`。",
                        "在 command_patterns 中添加同名命名捕获，或改用内置上下文字段。",
                    )
                )

        field = yaml_condition.get("field")
        if not isinstance(field, str) or not field:
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{condition_base}.field",
                    "必须声明非空 YAML field（YAML 字段）。",
                    "添加要读取的字段，例如 `workflow`。",
                )
            )

        allowed = yaml_condition.get("in")
        if not isinstance(allowed, list) or not allowed:
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{condition_base}.in",
                    "必须声明至少一个允许值。",
                    "添加 in 列表，例如 `hotfix` 和 `tweak`。",
                )
            )
        elif not all(isinstance(item, str) and item for item in allowed):
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{condition_base}.in",
                    "必须是非空字符串列表。",
                    "把每个 in 值改成非空字符串，例如 `hotfix` 和 `tweak`。",
                )
            )

    return issues


def validate_global_command_guards(profile_dir: Path) -> tuple[bool, list[ValidationIssue]]:
    path = profile_dir / GLOBAL_COMMAND_GUARDS_FILE
    if not path.exists():
        return False, []

    data, issue = load_yaml(path, "global_command_guards")
    if issue or data is None:
        return False, [issue] if issue else []

    guards = data.get("global_command_guards")
    if guards is None:
        return False, []
    if not isinstance(guards, list):
        return False, [
            ValidationIssue(
                "global_command_guards",
                "global_command_guards",
                "必须是 list（列表）。",
                "把 global_command_guards 改成列表；没有规则时写 `global_command_guards: []`。",
            )
        ]

    issues: list[ValidationIssue] = []
    artifact_ids = artifact_ids_in_profile(profile_dir)
    seen: set[str] = set()
    for index, guard in enumerate(guards):
        if not isinstance(guard, dict):
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"global_command_guards.{index}",
                    "必须是 mapping（映射）。",
                    "把该条规则改成包含 id、tool、match、evidence、checks 的映射。",
                )
            )
            continue

        guard_id = guard.get("id")
        base = f"global_command_guards.{guard_id if isinstance(guard_id, str) and guard_id else index}"
        if not isinstance(guard_id, str) or not guard_id:
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{base}.id",
                    "必须声明非空 id。",
                    "为该全局命令守卫点添加唯一 id。",
                )
            )
        elif guard_id in seen:
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{base}.id",
                    f"重复 id `{guard_id}`。",
                    "同一个 global-command-guards.yaml 内 guard id 必须唯一。",
                )
            )
        else:
            seen.add(guard_id)

        if not isinstance(guard.get("tool"), str) or not guard.get("tool"):
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{base}.tool",
                    "必须声明工具名。",
                    "例如写 `tool: Bash`。",
                )
            )

        match = guard.get("match")
        patterns = match.get("command_patterns") if isinstance(match, dict) else None
        capture_names: set[str] = set()
        if not isinstance(patterns, list) or not patterns or not all(isinstance(item, str) and item for item in patterns):
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{base}.match.command_patterns",
                    "必须声明至少一个命令模式。",
                    "添加 command_patterns 列表。",
                )
            )
        else:
            for pattern_index, pattern in enumerate(patterns):
                captures, pattern_issue = named_captures_from_pattern(pattern)
                if pattern_issue:
                    issues.append(
                        ValidationIssue(
                            "global_command_guards",
                            f"{base}.match.command_patterns.{pattern_index}",
                            pattern_issue.message,
                            pattern_issue.fix,
                        )
                    )
                capture_names.update(captures)

        required_captures = match.get("required_captures") if isinstance(match, dict) else []
        if required_captures is None:
            required_captures = []
        if not isinstance(required_captures, list) or not all(isinstance(item, str) and item for item in required_captures):
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{base}.match.required_captures",
                    "必须是字符串列表。",
                    "把 required_captures 改成命名捕获字段列表。",
                )
            )
            required_captures = []
        for capture in required_captures:
            if capture not in capture_names:
                issues.append(
                    ValidationIssue(
                        "global_command_guards",
                        f"{base}.match.required_captures.{capture}",
                        f"缺少必需捕获值 `{capture}`。",
                        "在 command_patterns 中添加同名命名捕获，例如 `(?P<change>...)`。",
                    )
                )

        issues.extend(validate_global_command_guard_skip_when(base, guard, capture_names))

        evidence = guard.get("evidence")
        evidence_path = evidence.get("path") if isinstance(evidence, dict) else None
        if not isinstance(evidence, dict):
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{base}.evidence.path",
                    "必须声明 evidence artifact（产物）或 evidence.path（证据路径模板）。",
                    "添加 evidence.artifact 或 evidence.path。",
                )
            )
        elif isinstance(evidence, dict):
            evidence_artifact = evidence.get("artifact")
            evidence_artifact_id = evidence.get("artifact_id")
            if isinstance(evidence_artifact, str) and evidence_artifact:
                artifact_id = evidence_artifact
            elif isinstance(evidence_artifact_id, str) and evidence_artifact_id:
                artifact_id = evidence_artifact_id
            elif isinstance(evidence_artifact, str) or isinstance(evidence_artifact_id, str):
                artifact_id = None
            else:
                artifact_id = None

            if artifact_id is not None:
                if not isinstance(artifact_id, str) or not artifact_id:
                    issues.append(
                        ValidationIssue(
                            "global_command_guards",
                            f"{base}.evidence.artifact",
                            "artifact 或 artifact_id 必须是非空字符串。",
                            "填写有效的 evidence.artifact 或 evidence.artifact_id。",
                        )
                    )
                elif artifact_id not in artifact_ids:
                    issues.append(
                        missing_reference(
                            "global_command_guards",
                            f"{base}.evidence.artifact",
                            artifact_id,
                            "artifacts",
                            "定义该产物，或改用 evidence.path。",
                        )
                    )
            elif not isinstance(evidence_path, str) or not evidence_path:
                issues.append(
                    ValidationIssue(
                        "global_command_guards",
                        f"{base}.evidence.path",
                        "必须声明 evidence artifact（产物）或 evidence.path（证据路径模板）。",
                        "添加 evidence.artifact 或 evidence.path。",
                    )
                )
            else:
                for field in sorted(template_fields(evidence_path) - capture_names - GLOBAL_COMMAND_GUARD_VALUE_FROM_FIELDS):
                    issues.append(
                        ValidationIssue(
                            "global_command_guards",
                            f"{base}.evidence.path.{field}",
                            f"缺少必需捕获值 `{field}`。",
                            "在 command_patterns 中添加同名命名捕获，或改用内置上下文字段。",
                        )
                    )

        checks = guard.get("checks")
        if not isinstance(checks, list) or not checks:
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"{base}.checks",
                    "必须声明至少一个 JSON 检查。",
                    "添加 checks 列表。",
                )
            )
            checks = []
        for check_index, check in enumerate(checks):
            issues.extend(validate_global_command_guard_check(base, check_index, check, capture_names))

    return bool(guards) and not issues, issues


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


def required_json_artifact_field(field: str, path: str) -> ValidationIssue:
    return ValidationIssue(
        "guard_points",
        path,
        f"是 json_artifact 检查的必填字段 `{field}`。",
        f"为 json_artifact 检查添加 `{field}`。",
    )


def validate_json_artifact_check(
    guard_point_id: str,
    check_id: str,
    check: dict[str, Any],
    artifact_ids: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    base_field = f"guard_points.{guard_point_id}.checks.{check_id}"

    artifact = check.get("artifact") or check.get("artifact_id")
    if not isinstance(artifact, str) or not artifact:
        issues.append(required_json_artifact_field("artifact", f"{base_field}.artifact"))
    elif artifact not in artifact_ids:
        issues.append(
            missing_reference(
                "guard_points",
                f"{base_field}.artifact",
                artifact,
                "artifacts",
                "定义该产物，或更新 Guard Point（守卫点）检查里的 artifact。",
            )
        )

    field = check.get("field")
    if not isinstance(field, str) or not field:
        issues.append(required_json_artifact_field("field", f"{base_field}.field"))

    predicate = check.get("predicate")
    if not isinstance(predicate, str) or not predicate:
        issues.append(required_json_artifact_field("predicate", f"{base_field}.predicate"))
        return issues
    if predicate not in JSON_ARTIFACT_PREDICATES:
        issues.append(
            ValidationIssue(
                "guard_points",
                f"{base_field}.predicate",
                f"未知 json_artifact predicate `{predicate}`。",
                "改用 exists、equals、not_equals、number_lte、number_gte、array_none 或 array_all。",
            )
        )
        return issues

    if predicate in JSON_ARTIFACT_VALUE_PREDICATES and "value" not in check:
        issues.append(required_json_artifact_field("value", f"{base_field}.value"))
    if predicate in JSON_ARTIFACT_ARRAY_PREDICATES and not isinstance(check.get("where"), dict):
        issues.append(required_json_artifact_field("where", f"{base_field}.where"))

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
    guard_point_ids = list_ids(configs["guard_points"], "guard_points")
    guard_points_by_id = {
        item["id"]: item
        for item in configs["guard_points"].get("guard_points", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    artifact_ids = list_ids(configs["artifacts"], "artifacts")

    issues.extend(validate_deprecated_fields(configs))
    issues.extend(validate_state_permissions(configs))
    issues.extend(validate_artifact_contract(configs))
    issues.extend(validate_state_transition_shape(configs))

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
            if check.get("type") == "json_artifact":
                issues.extend(validate_json_artifact_check(guard_point_id, check_id, check, artifact_ids))
                continue
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

    issues.extend(validate_legacy_contract(profile_dir))
    has_global_command_guards_file = (profile_dir / GLOBAL_COMMAND_GUARDS_FILE).exists()
    has_active_global_command_guards, global_command_guard_issues = validate_global_command_guards(profile_dir)
    issues.extend(global_command_guard_issues)

    for category, relative_path in REQUIRED_FILES.items():
        path = profile_dir / relative_path
        if not path.exists():
            if has_active_global_command_guards and category in SESSION_FOCUS_CATEGORIES:
                continue
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

    if has_global_command_guards_file:
        checked.append("global_command_guards")

    reference_categories = {"state_machine", "guard_points", "artifacts"}
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
