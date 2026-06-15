"""从已确认问答记录生成 Guard Profile（守卫画像）草案。"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from validate_guard_profile import ValidationIssue, state_machine_has_deny_permissions, validate_profile


PROFILE_FILES = {
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
    "implementation_plan": "implementation-plan.md",
}

REQUIRED_INPUT_FIELDS = [
    "grill_with_docs.status",
    "grill_with_docs.confirmed_decisions",
    "grill_with_docs.terminology",
    "grill_with_docs.boundaries",
    "grill_with_docs.scenarios",
    "grill_with_docs.exceptions",
    "grill_with_docs.documentation_changes",
    "initialization.requested_profile_ref",
    "initialization.guard_injection.enabled",
    "initialization.hook_installation.enabled",
    "profile.id",
    "profile.name",
    "profile.description",
    "target.id",
    "target.type",
    "target.name",
    "target.source",
    "target.boundary",
    "activation.allowed_sources",
    "activation.required_profile_ref",
    "activation.scopes",
    "activation.on_existing_subject",
    "activation.on_missing_subject",
    "activation.initial_state",
    "subject.identity_fields",
    "subject.required_fields",
    "subject.context_sources",
    "subject.existing_match_policy",
    "subject.create_policy",
    "subject.ambiguous_policy",
    "execution.nodes",
    "execution.states",
    "observation.signals",
    "state_machine.initial_state",
    "state_machine.terminal_states",
    "state_machine.states",
    "state_machine.transitions",
    "guard_points",
    "artifacts",
    "hook_bindings",
    "validation.items",
]


@dataclass(frozen=True)
class ConfirmationNeed:
    field: str
    reason: str
    ask: str

    def as_dict(self) -> dict[str, str]:
        return {"field": self.field, "reason": self.reason, "ask": self.ask}


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"输入不是有效 YAML（YAML 配置格式）：{exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("输入顶层必须是 YAML mapping（YAML 映射）。")
    return data


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


def collect_needs_confirmation(data: dict[str, Any]) -> list[ConfirmationNeed]:
    needs: list[ConfirmationNeed] = []
    for field in REQUIRED_INPUT_FIELDS:
        if not is_present(value_at(data, field)):
            needs.append(
                ConfirmationNeed(
                    field=field,
                    reason="生成可校验 Guard Profile（守卫画像）草案需要该字段。",
                    ask=f"请用 $grill-with-docs（带文档拷问方法）确认 `{field}`。",
                )
            )

    status = value_at(data, "grill_with_docs.status")
    if is_present(status) and status != "confirmed":
        needs.append(
            ConfirmationNeed(
                field="grill_with_docs.status",
                reason="问答记录必须先完成术语和决策校准。",
                ask="请先用 $grill-with-docs（带文档拷问方法）把状态确认到 `confirmed`。",
            )
        )

    profile_id = value_at(data, "profile.id")
    requested_profile_ref = value_at(data, "initialization.requested_profile_ref")
    if is_present(profile_id) and is_present(requested_profile_ref) and profile_id != requested_profile_ref:
        needs.append(
            ConfirmationNeed(
                field="initialization.requested_profile_ref",
                reason="初始化调研必须根据本次调用确认画像，调用里的画像 ID 要和 `profile.id` 一致。",
                ask="请确认本次调用要初始化的 Guard Profile（守卫画像）ID，并让它和 `profile.id` 对齐。",
            )
        )

    guard_injection_enabled = value_at(data, "initialization.guard_injection.enabled")
    if is_present(guard_injection_enabled) and guard_injection_enabled is not True:
        needs.append(
            ConfirmationNeed(
                field="initialization.guard_injection.enabled",
                reason="初始化调研默认启用 Guard Injection（守卫注入），让 agent 能读取 latest Guard Brief（最新守卫简报）。",
                ask="请确认是否按默认启用 Guard Injection（守卫注入）。",
            )
        )

    hook_installation_enabled = value_at(data, "initialization.hook_installation.enabled")
    if is_present(hook_installation_enabled) and not isinstance(hook_installation_enabled, bool):
        needs.append(
            ConfirmationNeed(
                field="initialization.hook_installation.enabled",
                reason="初始化调研必须明确是否启用 Hook（钩子）。",
                ask="请把 `initialization.hook_installation.enabled` 明确为 `true` 或 `false`。",
            )
        )

    hook_bindings = value_at(data, "hook_bindings")
    if hook_installation_enabled is True and isinstance(hook_bindings, list) and not hook_bindings:
        needs.append(
            ConfirmationNeed(
                field="hook_bindings",
                reason="已确认启用 Hook（钩子），但没有可安装的 Hook Binding（钩子绑定）。",
                ask="请确认至少一个 Hook Binding（钩子绑定），或把 `initialization.hook_installation.enabled` 改为 `false`。",
            )
        )

    target_boundary = value_at(data, "target.boundary")
    if isinstance(target_boundary, str) and "修改" in target_boundary and "不修改" not in target_boundary:
        needs.append(
            ConfirmationNeed(
                field="target.boundary",
                reason="Guard Profile（守卫画像）必须保持旁路解耦，不能要求修改被守卫对象。",
                ask="请确认边界是否改为只旁路观察、校验和记录，不修改被守卫对象。",
            )
        )

    return needs


def dump_yaml_file(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def build_manifest(data: dict[str, Any]) -> dict[str, Any]:
    profile = value_at(data, "profile")
    assert isinstance(profile, dict)
    return {
        "schema_version": "guard-profile/v1",
        "guard_profile_id": profile["id"],
        "name": profile["name"],
        "description": profile["description"],
        "source": {
            "kind": "grill-with-docs-confirmed-notes",
            "status": value_at(data, "grill_with_docs.status"),
        },
        "files": PROFILE_FILES,
    }


def build_validation_plan(data: dict[str, Any]) -> str:
    grill = value_at(data, "grill_with_docs")
    validation = value_at(data, "validation")
    assert isinstance(grill, dict)
    assert isinstance(validation, dict)

    lines = [
        "# Validation Plan（验证计划）",
        "",
        "## 输入校准",
        "",
        "- 已要求使用 `$grill-with-docs`（带文档拷问方法）完成术语、决策、边界、场景、例外和文档变更校准。",
    ]

    for decision in grill.get("confirmed_decisions", []):
        lines.append(f"- 已确认决策：{decision}")
    for change in grill.get("documentation_changes", []):
        lines.append(f"- 文档变更摘要：{change}")

    lines.extend(["", "## 验证项", ""])
    for item in validation.get("items", []):
        lines.append(f"- {item}")

    lines.extend(
        [
            "- 校验所有必需 Guard Profile（守卫画像）文件存在。",
            "- 校验状态机、守卫点、产物、观察信号和 Hook Binding（钩子绑定）引用完整。",
            "- 确认生成过程只写入 Guard Profile（守卫画像）草案目录，不修改被守卫对象。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_implementation_plan(data: dict[str, Any]) -> str:
    profile = value_at(data, "profile")
    initialization = value_at(data, "initialization")
    activation = value_at(data, "activation")
    subject = value_at(data, "subject")
    guard_points = value_at(data, "guard_points")
    artifacts = value_at(data, "artifacts")
    hook_bindings = value_at(data, "hook_bindings")
    assert isinstance(profile, dict)
    assert isinstance(initialization, dict)
    assert isinstance(activation, dict)
    assert isinstance(subject, dict)
    assert isinstance(guard_points, list)
    assert isinstance(artifacts, list)
    assert isinstance(hook_bindings, list)

    lines = [
        "# Implementation Plan（实施计划）",
        "",
        f"Guard Profile（守卫画像）：{profile['id']}",
        "",
        "## 初始化",
        "",
        f"- 根据本次调用确认画像：`{initialization['requested_profile_ref']}`。",
        "- 在目标范围显式初始化 Guard Runtime（守卫运行时）和 Guard Profile（守卫画像）目录。",
        "- 初始化阶段只生成配置和验证计划，不预建 `.local/guard/*` 运行态目录，不修改被守卫对象。",
        "- 初始化输入必须是本轮调研生成并校验通过的 Guard Profile（守卫画像）草案目录。",
        "",
        "## 守卫注入",
        "",
        "- Guard Injection（守卫注入）默认启用。",
        "- 初始化后 agent（代理）通过 latest Guard Brief（最新守卫简报）读取当前状态和下一步要求。",
        "- 使用 `brief --session <session-id>` 时按 session（会话）记录 `brief_hash`，避免重复注入。",
        "",
        "## Hook（钩子）",
        "",
    ]

    hook_installation = initialization.get("hook_installation")
    hook_installation = hook_installation if isinstance(hook_installation, dict) else {}
    if hook_installation.get("enabled") is True:
        lines.extend(
            [
                "- 调研已确认启用 Hook（钩子）。",
                "- 初始化完成并校验画像后，使用 `install_hooks.py --authorize-install` 安装 Hook（钩子）。",
                "- 安装 Hook（钩子）前仍必须获得用户明确授权。",
            ]
        )
    else:
        reason = hook_installation.get("reason")
        suffix = f"原因：{reason}" if isinstance(reason, str) and reason else "后续需要用户明确授权后再安装。"
        lines.append(f"- 调研已确认暂不启用 Hook（钩子）。{suffix}")

    lines.extend(
        [
        "",
        "## 配置",
        "",
        f"- activation.initial_state：`{activation['initial_state']}`。",
        f"- activation.on_existing_subject：`{activation['on_existing_subject']}`。",
        f"- activation.on_missing_subject：`{activation['on_missing_subject']}`。",
        f"- subject.identity_fields：{format_inline_list(subject['identity_fields'])}。",
        f"- subject.required_fields：{format_inline_list(subject['required_fields'])}。",
        "- 业务规则只放在 Guard Profile（守卫画像）配置中，Runtime（运行时）和 Hook（钩子）只做通用执行。",
        "",
        "## 守卫点划分",
        "",
        ]
    )

    for guard_point in guard_points:
        if not isinstance(guard_point, dict):
            continue
        guard_point_id = guard_point.get("id", "<unknown>")
        artifact_ids = guard_point.get("inputs", {}).get("artifacts", [])
        lines.append(f"- `{guard_point_id}`：依赖产物={format_inline_list(artifact_ids)}。")

    lines.extend(
        [
            "",
            "## 单个守卫点单独实施计划",
            "",
        ]
    )

    for guard_point in guard_points:
        if not isinstance(guard_point, dict):
            continue
        guard_point_id = guard_point.get("id", "<unknown>")
        lines.extend(
            [
                f"### `{guard_point_id}`",
                "",
                "1. 确认该守卫点的目标、触发事件、依赖产物和失败行为。",
                "2. 只启用该守卫点关联的状态转换、产物引用和 Hook Binding（钩子绑定）。",
                "3. 运行 `validate_guard_profile.py <guard-profile-dir>` 校验文件和引用。",
                "4. 验证该守卫点失败时不会推进状态，并能输出清晰修复建议。",
                "5. 如果误报或检查错误，只回滚该守卫点，不回滚整个 Guard Profile（守卫画像）。",
                "",
            ]
        )

    lines.extend(["## 产物和 Hook（钩子）接入", ""])
    for artifact in artifacts:
        if isinstance(artifact, dict):
            lines.append(
                f"- Artifact（产物）`{artifact.get('id', '<unknown>')}`：owner（所有者）=`{artifact.get('owner', '<unknown>')}`。"
            )
    for binding in hook_bindings:
        if isinstance(binding, dict):
            lines.append(
                f"- Hook Binding（钩子绑定）`{binding.get('id', '<unknown>')}`：event_type=`{binding.get('event_type', '<unknown>')}`。"
            )

    return "\n".join(lines).rstrip() + "\n"


def hook_binding_has_trigger(binding: dict[str, Any]) -> bool:
    if is_present(binding.get("trigger_event")):
        return True
    trigger = binding.get("trigger")
    return isinstance(trigger, dict) and is_present(trigger.get("event"))


def normalize_hook_bindings(data: dict[str, Any]) -> None:
    profile = value_at(data, "profile")
    hook_bindings = value_at(data, "hook_bindings")
    if not isinstance(profile, dict) or not isinstance(hook_bindings, list):
        return

    for binding in hook_bindings:
        if not isinstance(binding, dict):
            continue
        event_type = binding.get("event_type")
        if isinstance(event_type, str) and not hook_binding_has_trigger(binding):
            binding["trigger_event"] = event_type
        binding.setdefault("target_profile", profile.get("id"))
        install = binding.get("install")
        if not isinstance(install, dict):
            install = {}
            binding["install"] = install
        install.setdefault("status", "not_installed")
        install.setdefault("target", binding.get("source", "manual"))
        install.setdefault("rollback", "remove installed hook entry")


def format_inline_list(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "`[]`"
    return ", ".join(f"`{item}`" for item in value)


def write_profile(data: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    dump_yaml_file(output / "GUARD-MANIFEST.yaml", build_manifest(data))
    dump_yaml_file(output / "target-model.yaml", {"target": data["target"]})
    dump_yaml_file(output / "activation-model.yaml", {"activation": data["activation"]})
    dump_yaml_file(output / "subject-resolver.yaml", {"subject": data["subject"]})
    dump_yaml_file(output / "execution-model.yaml", data["execution"])
    dump_yaml_file(output / "observation-model.yaml", data["observation"])
    dump_yaml_file(output / "state-machine.yaml", data["state_machine"])
    dump_yaml_file(output / "guard-points.yaml", {"guard_points": data["guard_points"]})
    dump_yaml_file(output / "artifacts.yaml", {"artifacts": data["artifacts"]})
    dump_yaml_file(output / "hook-bindings.yaml", {"hook_bindings": data["hook_bindings"]})
    (output / "brief-template.md").write_text(default_brief_template(), encoding="utf-8")
    (output / "validation-plan.md").write_text(build_validation_plan(data), encoding="utf-8")
    (output / "implementation-plan.md").write_text(build_implementation_plan(data), encoding="utf-8")


def default_brief_template() -> str:
    return """# Guard Brief（守卫简报）

Guard Profile（守卫画像）：{{ guard_profile_id }}
Subject（主体）：{{ subject_key_hash }}
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


def print_needs_confirmation(needs: list[ConfirmationNeed], output: Path | None) -> None:
    payload = {"status": "needs_confirmation", "needs_confirmation": [need.as_dict() for need in needs]}
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    print(text, end="")
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / "needs-confirmation.yaml").write_text(text, encoding="utf-8")


def print_validation_failure(output: Path, issues: list[ValidationIssue]) -> None:
    print("status: validation_failed")
    print(f"output: {output}")
    print("issues:")
    for issue in issues:
        print(f"  - category: {issue.category}")
        print(f"    field: {issue.field}")
        print(f"    message: {issue.message}")
        print(f"    fix: {issue.fix}")


def print_deny_authorization_required(output: Path) -> None:
    payload = {
        "status": "authorization_required",
        "authorization": "deny_permissions_missing",
        "message": "调研记录包含会返回 `deny` 的状态权限，生成 Guard Profile（守卫画像）草案前必须额外授权。",
        "next": "如果确认要生成这些拒绝规则，请重试并加 --authorize-deny-permissions。",
    }
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    print(text, end="")
    output.mkdir(parents=True, exist_ok=True)
    (output / "deny-authorization-required.yaml").write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从已确认问答记录生成 Guard Profile（守卫画像）草案。")
    parser.add_argument("notes", type=Path, help="已确认问答记录 YAML（YAML 配置格式）路径")
    parser.add_argument("--output", type=Path, required=True, help="Guard Profile（守卫画像）草案输出目录")
    parser.add_argument(
        "--authorize-deny-permissions",
        action="store_true",
        help="明确授权生成含 `deny` 状态权限的 Guard Profile（守卫画像）草案",
    )
    args = parser.parse_args(argv)

    try:
        data = load_yaml(args.notes)
    except ValueError as exc:
        print("status: error")
        print(f"message: {exc}")
        return 2

    needs = collect_needs_confirmation(data)
    if needs:
        print_needs_confirmation(needs, args.output)
        return 1

    state_machine = value_at(data, "state_machine")
    if isinstance(state_machine, dict) and state_machine_has_deny_permissions(state_machine) and not args.authorize_deny_permissions:
        print_deny_authorization_required(args.output)
        return 1

    normalize_hook_bindings(data)
    write_profile(data, args.output)
    _checked, issues = validate_profile(args.output)
    if issues:
        print_validation_failure(args.output, issues)
        return 1

    print("status: generated")
    print(f"output: {args.output}")
    print("validation: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
