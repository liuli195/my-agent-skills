import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SKILL = REPO_ROOT / "plugins" / "agent-guard" / "skills" / "agent-guard"
VALIDATOR = PLUGIN_SKILL / "scripts" / "validate_guard_profile.py"
MINIMAL_PROFILE = PLUGIN_SKILL / "assets" / "templates" / "guard-profile" / "minimal"
MIRRORED_MINIMAL_PROFILE = REPO_ROOT / "plugins" / "agent-guard" / "assets" / "templates" / "guard-profile" / "minimal"


def run_validator(profile_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(profile_path)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_global_command_guards(profile: Path, body: str) -> None:
    (profile / "global-command-guards.yaml").write_text(body.lstrip(), encoding="utf-8")


def valid_global_command_guard_yaml() -> str:
    return """
global_command_guards:
  - id: verify_requires_review
    description: Comet verify 前必须有 review 证据。
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply'
      required_captures:
        - change
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{change}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
      - field: change
        predicate: equals
        value_from: change
      - field: head_ref
        predicate: equals
        value_from: git_head
    deny:
      reason: global_command_guard_required
      next: produce_required_evidence
      suggestion: 先完成 reviewed flow（已审查流程）。
"""


def test_global_command_guards_template_file_is_allowed() -> None:
    skill_template = MINIMAL_PROFILE / "global-command-guards.yaml"
    plugin_template = MIRRORED_MINIMAL_PROFILE / "global-command-guards.yaml"

    assert skill_template.exists()
    assert plugin_template.exists()
    assert skill_template.read_text(encoding="utf-8") == "global_command_guards: []\n"
    assert plugin_template.read_text(encoding="utf-8") == "global_command_guards: []\n"
    assert plugin_template.read_text(encoding="utf-8") == skill_template.read_text(encoding="utf-8")

    result = run_validator(MINIMAL_PROFILE)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "通过：Guard Profile（守卫画像）校验" in result.stdout
    assert "已检查：global_command_guards" in result.stdout


def test_minimal_guard_profile_passes_new_session_focus_contract() -> None:
    result = run_validator(MINIMAL_PROFILE)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "通过：Guard Profile（守卫画像）校验" in result.stdout
    for category in [
        "manifest",
        "target_model",
        "state_machine",
        "guard_points",
        "artifacts",
        "brief_template",
        "validation_plan",
    ]:
        assert f"已检查：{category}" in result.stdout
    assert "subject_resolver" not in result.stdout
    assert "hook_bindings" not in result.stdout


def test_global_command_guard_valid_config_passes(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    write_global_command_guards(profile, valid_global_command_guard_yaml())

    result = run_validator(profile)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "已检查：global_command_guards" in result.stdout


def test_global_command_guard_allows_profile_without_session_focus_config(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    for relative_path in ["state-machine.yaml", "guard-points.yaml", "artifacts.yaml"]:
        (profile / relative_path).unlink()
    write_global_command_guards(profile, valid_global_command_guard_yaml())

    result = run_validator(profile)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "已检查：global_command_guards" in result.stdout
    assert "category=state_machine" not in result.stdout
    assert "category=guard_points" not in result.stdout
    assert "category=artifacts" not in result.stdout


def test_global_command_guard_missing_command_patterns_fails(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    write_global_command_guards(
        profile,
        """
global_command_guards:
  - id: verify_requires_review
    tool: Bash
    match:
      required_captures:
        - change
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{change}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
""",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=global_command_guards" in result.stdout
    assert "field=global_command_guards.verify_requires_review.match.command_patterns" in result.stdout
    assert "必须声明至少一个命令模式" in result.stdout


def test_global_command_guard_missing_evidence_path_fails(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    write_global_command_guards(
        profile,
        """
global_command_guards:
  - id: verify_requires_review
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply'
      required_captures:
        - change
    evidence: {}
    checks:
      - field: status
        predicate: equals
        value: pass
""",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=global_command_guards" in result.stdout
    assert "field=global_command_guards.verify_requires_review.evidence.path" in result.stdout
    assert "必须声明 evidence path template" in result.stdout


def test_global_command_guard_rejects_unsupported_json_predicate(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    write_global_command_guards(
        profile,
        valid_global_command_guard_yaml().replace("predicate: equals", "predicate: contains", 1),
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=global_command_guards" in result.stdout
    assert "field=global_command_guards.verify_requires_review.checks.0.predicate" in result.stdout
    assert "未知或缺失 JSON predicate" in result.stdout


def test_global_command_guard_missing_required_capture_value_fails(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    write_global_command_guards(
        profile,
        valid_global_command_guard_yaml().replace("(?P<change>[A-Za-z0-9._-]+)", "[A-Za-z0-9._-]+"),
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=global_command_guards" in result.stdout
    assert "field=global_command_guards.verify_requires_review.match.required_captures.change" in result.stdout
    assert "缺少必需捕获值 `change`" in result.stdout


def test_global_command_guard_rejects_illegal_value_from(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    write_global_command_guards(
        profile,
        valid_global_command_guard_yaml().replace("value_from: change", "value_from: missing_capture"),
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=global_command_guards" in result.stdout
    assert "field=global_command_guards.verify_requires_review.checks.1.value_from" in result.stdout
    assert "必须引用命名捕获或内置上下文字段" in result.stdout


def test_global_command_guard_duplicate_id_in_same_file_fails(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    write_global_command_guards(
        profile,
        """
global_command_guards:
  - id: duplicate
    tool: Bash
    match:
      command_patterns: ['tool (?P<name>[A-Za-z0-9._-]+)']
      required_captures: [name]
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{name}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
  - id: duplicate
    tool: Bash
    match:
      command_patterns: ['other (?P<name>[A-Za-z0-9._-]+)']
      required_captures: [name]
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{name}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
""",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=global_command_guards" in result.stdout
    assert "重复 id `duplicate`" in result.stdout


def test_manifest_requires_runtime_api_version(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    manifest = profile / "GUARD-MANIFEST.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("runtime_api_version: agent-guard-runtime/v1\n", ""),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=manifest field=runtime_api_version" in result.stdout
    assert "必须声明 Runtime API version" in result.stdout


def test_legacy_subject_resolver_file_is_rejected(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "subject-resolver.yaml").write_text("subject: {}\n", encoding="utf-8")

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=legacy_contract field=subject-resolver.yaml" in result.stdout
    assert "已从 Session Focus Binding（会话焦点绑定）契约删除" in result.stdout


def test_legacy_hook_bindings_file_is_rejected(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "hook-bindings.yaml").write_text("hook_bindings: []\n", encoding="utf-8")

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=legacy_contract field=hook-bindings.yaml" in result.stdout
    assert "已从 Session Focus Binding（会话焦点绑定）契约删除" in result.stdout


def test_legacy_contract_tokens_are_rejected(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "state-machine.yaml").write_text(
        (profile / "state-machine.yaml").read_text(encoding="utf-8")
        + "\nlegacy_reason: no_subject_match\n",
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=legacy_contract field=state-machine.yaml:no_subject_match" in result.stdout


def test_guard_point_trigger_field_is_rejected(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 错误地绑定 Hook 事件。
    trigger:
      events:
        - state_completed
    checks:
      - id: completion_note_exists
        type: artifact_exists
        artifact: completion_note
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "field=guard_points.completion_note_present.trigger" in result.stdout
    assert "Guard Point（守卫点）不再绑定 Hook（钩子）或事件" in result.stdout


def test_missing_required_file_reports_category_and_fix(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "target-model.yaml").unlink()

    result = run_validator(profile)

    assert result.returncode == 1
    assert "失败：Guard Profile（守卫画像）校验未通过" in result.stdout
    assert "category=target_model field=target-model.yaml" in result.stdout
    assert "把 target-model.yaml 添加到 Guard Profile（守卫画像）目录" in result.stdout


def test_initial_state_must_reference_state_machine_state(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    state_machine = profile / "state-machine.yaml"
    state_machine.write_text(
        state_machine.read_text(encoding="utf-8").replace("initial_state: open", "initial_state: missing_state"),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=state_machine field=initial_state" in result.stdout
    assert "引用了 `missing_state`" in result.stdout
    assert "states" in result.stdout


def test_guard_point_check_artifact_must_reference_defined_artifact(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 引用缺失产物的守卫点。
    checks:
      - id: missing_artifact_exists
        type: artifact_exists
        artifact: missing_artifact
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=guard_points" in result.stdout
    assert "field=guard_points.completion_note_present.checks.missing_artifact_exists.artifact" in result.stdout
    assert "引用了 `missing_artifact`" in result.stdout
    assert "artifacts" in result.stdout


def test_json_artifact_guard_point_check_accepts_defined_artifact_and_predicate(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 保留状态机引用的既有守卫点。
    checks:
      - id: completion_note_exists
        type: artifact_exists
        artifact: completion_note
  - id: review_pass_valid
    description: 校验 JSON 产物里的 review 状态。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: equals
        value: pass
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "通过：Guard Profile（守卫画像）校验" in result.stdout


def test_json_artifact_guard_point_check_requires_artifact(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 保留状态机引用的既有守卫点。
    checks:
      - id: completion_note_exists
        type: artifact_exists
        artifact: completion_note
  - id: review_pass_valid
    description: 缺少 JSON 产物引用。
    checks:
      - id: status_pass
        type: json_artifact
        field: status
        predicate: exists
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=guard_points" in result.stdout
    assert "field=guard_points.review_pass_valid.checks.status_pass.artifact" in result.stdout


def test_json_artifact_guard_point_check_artifact_must_reference_defined_artifact(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 保留状态机引用的既有守卫点。
    checks:
      - id: completion_note_exists
        type: artifact_exists
        artifact: completion_note
  - id: review_pass_valid
    description: 引用缺失 JSON 产物。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: missing_artifact
        field: status
        predicate: exists
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=guard_points" in result.stdout
    assert "field=guard_points.review_pass_valid.checks.status_pass.artifact" in result.stdout
    assert "引用了 `missing_artifact`" in result.stdout
    assert "artifacts" in result.stdout


def test_json_artifact_guard_point_check_requires_string_field(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 保留状态机引用的既有守卫点。
    checks:
      - id: completion_note_exists
        type: artifact_exists
        artifact: completion_note
  - id: review_pass_valid
    description: JSON field 必须是字符串。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: completion_note
        field:
          - not
          - a
          - path
        predicate: exists
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=guard_points" in result.stdout
    assert "field=guard_points.review_pass_valid.checks.status_pass.field" in result.stdout


def test_json_artifact_guard_point_check_requires_predicate(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 保留状态机引用的既有守卫点。
    checks:
      - id: completion_note_exists
        type: artifact_exists
        artifact: completion_note
  - id: review_pass_valid
    description: 缺少 JSON predicate。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: completion_note
        field: status
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=guard_points" in result.stdout
    assert "field=guard_points.review_pass_valid.checks.status_pass.predicate" in result.stdout


def test_json_artifact_guard_point_check_rejects_unknown_predicate(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 保留状态机引用的既有守卫点。
    checks:
      - id: completion_note_exists
        type: artifact_exists
        artifact: completion_note
  - id: review_pass_valid
    description: 使用未知 JSON predicate。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: contains
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=guard_points" in result.stdout
    assert "field=guard_points.review_pass_valid.checks.status_pass.predicate" in result.stdout
    assert "contains" in result.stdout


def test_json_artifact_guard_point_check_requires_value_for_comparison_predicate(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 保留状态机引用的既有守卫点。
    checks:
      - id: completion_note_exists
        type: artifact_exists
        artifact: completion_note
  - id: review_pass_valid
    description: 比较 predicate 缺少 value。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: completion_note
        field: score
        predicate: number_gte
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=guard_points" in result.stdout
    assert "field=guard_points.review_pass_valid.checks.status_pass.value" in result.stdout


def test_json_artifact_guard_point_check_requires_where_for_array_predicate(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 保留状态机引用的既有守卫点。
    checks:
      - id: completion_note_exists
        type: artifact_exists
        artifact: completion_note
  - id: review_pass_valid
    description: array predicate 缺少 where。
    checks:
      - id: status_pass
        type: json_artifact
        artifact: completion_note
        field: comments
        predicate: array_none
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=guard_points" in result.stdout
    assert "field=guard_points.review_pass_valid.checks.status_pass.where" in result.stdout


def test_artifact_reuse_policy_must_be_allow_or_deny(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    artifacts = profile / "artifacts.yaml"
    artifacts.write_text(
        artifacts.read_text(encoding="utf-8").replace("reuse_policy: deny", "reuse_policy: maybe"),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=artifacts field=artifacts.completion_note.reuse_policy" in result.stdout
    assert "必须是 `deny` 或 `allow`" in result.stdout


def test_manifest_mode_is_rejected(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    manifest = profile / "GUARD-MANIFEST.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + "mode: warn\n",
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=manifest field=mode" in result.stdout
    assert "已废弃" in result.stdout
    assert "states[].permissions" in result.stdout


def test_grill_with_docs_source_requires_confirmed_status(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    manifest = profile / "GUARD-MANIFEST.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace("kind: built-in-minimal-sample", "kind: grill-with-docs-confirmed-notes")
        .replace("status: template", "status: needs_confirmation"),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=manifest field=source.status" in result.stdout
    assert "必须是 `confirmed`" in result.stdout
    assert "$grill-with-docs" in result.stdout


def test_permissions_rules_must_be_a_list(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    state_machine = profile / "state-machine.yaml"
    state_machine.write_text(
        state_machine.read_text(encoding="utf-8").replace(
            "    description: Guard Profile（守卫画像）已激活，正在等待必需 note（说明记录）。",
            """
    description: Guard Profile（守卫画像）已激活，正在等待必需 note（说明记录）。
    permissions:
      default: allow
      rules:
        effect: deny
""".rstrip(),
        ),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=state_machine field=states.open.permissions.rules" in result.stdout
    assert "必须是权限规则清单" in result.stdout


def test_state_transition_on_event_must_be_state_completed(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    state_machine = profile / "state-machine.yaml"
    state_machine.write_text(
        state_machine.read_text(encoding="utf-8").replace("on_event: state_completed", "on_event: guard.close"),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=state_machine field=transitions.close_after_note.on_event" in result.stdout
    assert "必须是 `state_completed`" in result.stdout


def test_state_completed_transition_conditions_cannot_use_payload(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    state_machine = profile / "state-machine.yaml"
    state_machine.write_text(
        state_machine.read_text(encoding="utf-8").replace(
            "    required_artifacts:\n      - completion_note",
            """    conditions:
      - field: payload.route
        equals: done
    required_artifacts:
      - completion_note""",
        ),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=state_machine field=transitions.close_after_note.conditions.0.field" in result.stdout
    assert "`state_completed` 不能用 `payload.*` 选择完成证据" in result.stdout
