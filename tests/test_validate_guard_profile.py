import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "validate_guard_profile.py"
MINIMAL_PROFILE = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "agent-guard"
    / "assets"
    / "templates"
    / "guard-profile"
    / "minimal"
)


def run_validator(profile_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(profile_path)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_minimal_guard_profile_passes_validation() -> None:
    result = run_validator(MINIMAL_PROFILE)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "通过：Guard Profile（守卫画像）校验" in result.stdout
    for category in [
        "manifest",
        "target_model",
        "activation_model",
        "subject_resolver",
        "execution_model",
        "observation_model",
        "state_machine",
        "guard_points",
        "artifacts",
        "hook_bindings",
        "brief_template",
        "validation_plan",
    ]:
        assert f"已检查：{category}" in result.stdout


def test_missing_required_file_reports_category_and_fix(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "target-model.yaml").unlink()

    result = run_validator(profile)

    assert result.returncode == 1
    assert "失败：Guard Profile（守卫画像）校验未通过" in result.stdout
    assert "category=target_model field=target-model.yaml" in result.stdout
    assert "把 target-model.yaml 添加到 Guard Profile（守卫画像）目录" in result.stdout


def test_activation_initial_state_must_reference_state_machine_state(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    activation_model = profile / "activation-model.yaml"
    activation_model.write_text(
        activation_model.read_text(encoding="utf-8").replace(
            "initial_state: open", "initial_state: missing_state"
        ),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=activation_model field=activation.initial_state" in result.stdout
    assert "引用了 `missing_state`" in result.stdout
    assert "state_machine.states" in result.stdout


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


def test_guard_point_and_hook_blocking_fields_are_rejected(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 带旧字段的守卫点。
    mode: warn
    on_fail: warn
    on_error: block
    required_artifacts:
      - completion_note
""".lstrip(),
        encoding="utf-8",
    )
    (profile / "hook-bindings.yaml").write_text(
        """
hook_bindings:
  - id: manual-close
    source: manual
    trigger_event: guard.close
    event_type: guard.close
    blocking: false
    transitions:
      - close_after_note
    guard_points:
      - completion_note_present
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "field=guard_points.completion_note_present.mode" in result.stdout
    assert "field=guard_points.completion_note_present.on_fail" in result.stdout
    assert "field=guard_points.completion_note_present.on_error" in result.stdout
    assert "field=hook_bindings.manual-close.blocking" in result.stdout


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


def test_permissions_rules_items_must_be_mappings(tmp_path: Path) -> None:
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
        - deny Bash(git push*)
""".rstrip(),
        ),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=state_machine field=states.open.permissions.rules.0" in result.stdout
    assert "必须是 YAML mapping（YAML 映射）" in result.stdout


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


def test_non_terminal_state_must_have_state_completed_exit(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    state_machine = profile / "state-machine.yaml"
    state_machine.write_text(
        state_machine.read_text(encoding="utf-8").replace(
            "    from: open",
            "    from: closed",
        ),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=state_machine field=states.open.transitions" in result.stdout
    assert "非终止状态完成后没有 `state_completed` 出口转换" in result.stdout


def test_duplicate_unconditional_state_completed_transitions_are_rejected(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "state-machine.yaml").write_text(
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活，正在等待必需 note（说明记录）。
  - id: closed
    description: Guard Profile（守卫画像）已完成样例 flow（流程）。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
  - id: close_without_note
    from: open
    to: closed
    on_event: state_completed
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=state_machine field=states.open.transitions" in result.stdout
    assert "重复无条件 `state_completed` 转换" in result.stdout
    assert "close_after_note, close_without_note" in result.stdout


def test_duplicate_transition_ids_are_rejected(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "state-machine.yaml").write_text(
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活，正在等待必需 note（说明记录）。
  - id: closed
    description: Guard Profile（守卫画像）已完成样例 flow（流程）。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    required_artifacts:
      - completion_note
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    conditions:
      - field: context.route
        equals: other
    required_artifacts:
      - completion_note
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=state_machine field=transitions.close_after_note.id" in result.stdout
    assert "必须唯一" in result.stdout


def test_transition_id_is_required(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "state-machine.yaml").write_text(
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活，正在等待必需 note（说明记录）。
  - id: closed
    description: Guard Profile（守卫画像）已完成样例 flow（流程）。
transitions:
  - from: open
    to: closed
    on_event: state_completed
    required_artifacts:
      - completion_note
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=state_machine field=transitions.0.id" in result.stdout
    assert "是必填字段，且必须唯一" in result.stdout


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


def test_state_completed_guard_point_event_field_cannot_use_payload(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 错误地信任完成事件载荷。
    checks:
      - id: approval_flag
        type: event_field
        field: payload.approved
        equals: true
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=guard_points field=guard_points.completion_note_present.checks.approval_flag.field" in result.stdout
    assert "`state_completed` 不能用 `payload.*` 作为完成证据" in result.stdout


def test_state_permissions_must_use_known_effects(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    state_machine = profile / "state-machine.yaml"
    state_machine.write_text(
        state_machine.read_text(encoding="utf-8").replace(
            "  - id: open\n    description: Guard Profile（守卫画像）已激活，正在等待必需 note（说明记录）。",
            """  - id: open
    description: Guard Profile（守卫画像）已激活，正在等待必需 note（说明记录）。
    permissions:
      default: maybe
      rules:
        - effect: block
          tool: Bash""",
        ),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "field=states.open.permissions.default" in result.stdout
    assert "field=states.open.permissions.rules.0.effect" in result.stdout


def test_state_permission_shorthand_must_be_normalizable(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    state_machine = profile / "state-machine.yaml"
    state_machine.write_text(
        state_machine.read_text(encoding="utf-8").replace(
            "  - id: open\n    description: Guard Profile（守卫画像）已激活，正在等待必需 note（说明记录）。",
            """  - id: open
    description: Guard Profile（守卫画像）已激活，正在等待必需 note（说明记录）。
    permissions:
      default: allow
      deny:
        - Bash""",
        ),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "field=states.open.permissions.deny.0" in result.stdout
    assert "不能规范化为 `permissions.rules`" in result.stdout


def test_hook_binding_requires_source_trigger_and_event_type(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "hook-bindings.yaml").write_text(
        """
hook_bindings:
  - id: manual-close
    transitions:
      - close_after_note
    guard_points:
      - completion_note_present
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=hook_bindings" in result.stdout
    assert "field=hook_bindings.manual-close.source" in result.stdout
    assert "field=hook_bindings.manual-close.trigger_event" in result.stdout
    assert "field=hook_bindings.manual-close.event_type" in result.stdout


def test_codex_hook_binding_cannot_map_to_state_completed(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "hook-bindings.yaml").write_text(
        """
hook_bindings:
  - id: codex-complete
    source: codex
    trigger_event: PostToolUse
    event_type: state_completed
    transitions:
      - close_after_note
    guard_points:
      - completion_note_present
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "field=hook_bindings.codex-complete.event_type" in result.stdout
    assert "Hook（钩子）事件不能映射为 `state_completed`" in result.stdout
