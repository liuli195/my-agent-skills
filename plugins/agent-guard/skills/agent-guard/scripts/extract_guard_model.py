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
    "state_machine": "state-machine.yaml",
    "guard_points": "guard-points.yaml",
    "artifacts": "artifacts.yaml",
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
    "initialization.hook_installation.enabled",
    "profile.id",
    "profile.name",
    "profile.description",
    "target.id",
    "target.type",
    "target.name",
    "target.source",
    "target.boundary",
    "state_machine.initial_state",
    "state_machine.terminal_states",
    "state_machine.states",
    "state_machine.transitions",
    "guard_points",
    "artifacts",
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

    hook_installation_enabled = value_at(data, "initialization.hook_installation.enabled")
    if is_present(hook_installation_enabled) and not isinstance(hook_installation_enabled, bool):
        needs.append(
            ConfirmationNeed(
                field="initialization.hook_installation.enabled",
                reason="初始化调研必须明确是否启用 Hook（钩子）。",
                ask="请把 `initialization.hook_installation.enabled` 明确为 `true` 或 `false`。",
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
        "runtime_api_version": "agent-guard-runtime/v1",
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
            "- 校验状态机、守卫点和产物引用完整。",
            "- 确认生成过程只写入 Guard Profile（守卫画像）草案目录，不修改被守卫对象。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_implementation_plan(data: dict[str, Any]) -> str:
    profile = value_at(data, "profile")
    initialization = value_at(data, "initialization")
    guard_points = value_at(data, "guard_points")
    artifacts = value_at(data, "artifacts")
    assert isinstance(profile, dict)
    assert isinstance(initialization, dict)
    assert isinstance(guard_points, list)
    assert isinstance(artifacts, list)

    lines = [
        "# Implementation Plan（实施计划）",
        "",
        f"Guard Profile（守卫画像）：{profile['id']}",
        "",
        "## 初始化",
        "",
        f"- 根据本次调用确认画像：`{initialization['requested_profile_ref']}`。",
        "- 在目标范围显式初始化 Guard Profile（守卫画像）目录。",
        "- Runtime code（运行时代码）由 Agent Guard Plugin（代理守卫插件）发布，不复制到目标项目。",
        "- 初始化阶段只生成配置和验证计划，不预建 `.local/guard/*` 运行态目录，不修改被守卫对象。",
        "- 初始化输入必须是本轮调研生成并校验通过的 Guard Profile（守卫画像）草案目录。",
        "",
        "## Session Focus（会话焦点）",
        "",
        "- 激活时通过 Session Observation（会话观察记录）识别当前会话。",
        "- 用户显式选择或创建 Guard Instance（守卫实例），再写 Session Focus Binding（会话焦点绑定）。",
        "- Guard Instance（守卫实例）使用 opaque instance_id（不透明实例 ID），只区分 active（活跃）和 closed（关闭）。",
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
                "- Hook（钩子）由 Agent Guard Plugin（代理守卫插件）安装，只声明 SessionStart 和 PreToolUse。",
                "- Hook Router（钩子路由器）不接收画像参数，不绑定 Guard Profile（守卫画像）。",
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
        "- Guarded Target（被守卫目标）写在 target-model.yaml。",
        "- 状态推进只允许 `state_completed`，且只能推进当前 Session Focus Instance（会话焦点实例）。",
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
                "1. 确认该守卫点的目标、依赖产物和失败行为。",
                "2. 只启用该守卫点关联的状态转换和产物引用。",
                "3. 运行 `validate_guard_profile.py <guard-profile-dir>` 校验文件和引用。",
                "4. 验证该守卫点失败时不会推进状态，并能输出清晰修复建议。",
                "5. 如果误报或检查错误，只回滚该守卫点，不回滚整个 Guard Profile（守卫画像）。",
                "",
            ]
        )

    lines.extend(["## 产物", ""])
    for artifact in artifacts:
        if isinstance(artifact, dict):
            lines.append(
                f"- Artifact（产物）`{artifact.get('id', '<unknown>')}`：owner（所有者）=`{artifact.get('owner', '<unknown>')}`。"
            )

    return "\n".join(lines).rstrip() + "\n"


def format_inline_list(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "`[]`"
    return ", ".join(f"`{item}`" for item in value)


def write_profile(data: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    dump_yaml_file(output / "GUARD-MANIFEST.yaml", build_manifest(data))
    dump_yaml_file(output / "target-model.yaml", {"target": data["target"]})
    dump_yaml_file(output / "state-machine.yaml", data["state_machine"])
    dump_yaml_file(output / "guard-points.yaml", {"guard_points": data["guard_points"]})
    dump_yaml_file(output / "artifacts.yaml", {"artifacts": data["artifacts"]})
    (output / "brief-template.md").write_text(default_brief_template(), encoding="utf-8")
    (output / "validation-plan.md").write_text(build_validation_plan(data), encoding="utf-8")
    (output / "implementation-plan.md").write_text(build_implementation_plan(data), encoding="utf-8")


def default_brief_template() -> str:
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
