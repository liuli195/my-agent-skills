import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "extract_guard_model.py"
VALIDATOR = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "validate_guard_profile.py"


def run_extractor(input_path: Path, output_path: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EXTRACTOR), str(input_path), "--output", str(output_path), *(extra_args or [])],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
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


def write_complete_extraction_input(path: Path) -> None:
    path.write_text(
        """
grill_with_docs:
  status: confirmed
  confirmed_decisions:
    - 使用旁路 Guard Profile（守卫画像）记录发布流程顺序。
  terminology:
    - term: Guard Profile
      meaning: 守卫画像
  boundaries:
    - 不修改被守卫发布流程说明。
  scenarios:
    - 发布前必须先完成复核。
  exceptions:
    - 人工覆盖必须单独记录。
  documentation_changes:
    - docs/adr/0001-agent-guard-architecture.md 已确认 Runtime（运行时）不写业务规则。
initialization:
  requested_profile_ref: release-review-order
  guard_injection:
    enabled: true
  hook_installation:
    enabled: true
    reason: 调研确认需要安装 Hook（钩子）观察发布流程。
profile:
  id: release-review-order
  name: 发布复核顺序守卫
  description: 从已确认问答记录生成的发布复核顺序 Guard Profile（守卫画像）草案。
target:
  id: release-review-process
  type: workflow
  name: 发布复核流程
  source: docs/release.md
  boundary: 只旁路观察发布流程，不修改发布流程说明。
  goals:
    - 发布前完成复核。
  allowed_actions:
    - 启动复核节点。
    - 复核完成后关闭守卫。
  forbidden_actions:
    - 未复核直接发布。
activation:
  allowed_sources:
    - agent-guard-skill
    - manual
  required_profile_ref: true
  scopes:
    - current_context
  on_existing_subject: reuse
  on_missing_subject: create
  initial_state: review_required
subject:
  identity_fields:
    - context.repo
    - context.branch
  required_fields:
    - context.repo
    - context.branch
  optional_fields:
    - context.session_id
  context_sources:
    - context
    - event
  existing_match_policy: exact
  create_policy: explicit_activation_only
  ambiguous_policy: audit
execution:
  nodes:
    - id: complete_review
      type: review
      required_artifacts:
        - review_note
      completion_signals:
        - review.completed
    - id: close_guard
      type: closure
      required_artifacts:
        - review_note
      completion_signals:
        - state_completed
  states:
    - id: review_required
      allowed_next:
        - complete_review
      forbidden_next:
        - publish
      missing_artifacts:
        - review_note
      brief:
        current_state: review_required
        next_step: 完成复核并登记 review_note。
    - id: ready_to_close
      allowed_next:
        - close_guard
      forbidden_next: []
      missing_artifacts: []
      brief:
        current_state: ready_to_close
        next_step: 可以关闭 Guard Profile（守卫画像）。
    - id: closed
      allowed_next: []
      forbidden_next: []
      missing_artifacts: []
      brief:
        current_state: closed
        next_step: 不需要更多被守卫动作。
observation:
  signals:
    - id: review.completed
      source: manual
      event_type: review.completed
      strength: medium
      maps_to_node: complete_review
    - id: guard.close
      source: manual
      event_type: guard.close
      strength: medium
      maps_to_node: close_guard
    - id: state_completed
      source: agent
      event_type: state_completed
      strength: high
      maps_to_node: close_guard
state_machine:
  initial_state: review_required
  terminal_states:
    - closed
  states:
    - id: review_required
      description: 等待发布复核完成。
    - id: ready_to_close
      description: 复核完成，可以关闭守卫。
    - id: closed
      description: 守卫已关闭。
  transitions:
    - id: mark_review_complete
      from: review_required
      to: ready_to_close
      on_event: state_completed
      guard_points:
        - review_note_present
      required_artifacts:
        - review_note
    - id: close_after_review
      from: ready_to_close
      to: closed
      on_event: state_completed
      guard_points:
        - review_note_present
      required_artifacts:
        - review_note
guard_points:
  - id: review_note_present
    description: 发布前必须有复核记录。
    inputs:
      artifacts:
        - review_note
artifacts:
  - id: review_note
    type: note
    owner: external
    required_for:
      - mark_review_complete
      - close_after_review
    description: 发布复核记录，由原流程拥有，守卫只读取。
hook_bindings:
  - id: manual-review-complete
    source: manual
    event_type: review.completed
    transitions:
      - mark_review_complete
    guard_points:
      - review_note_present
  - id: manual-close
    source: manual
    event_type: state_completed
    transitions:
      - close_after_review
    guard_points:
      - review_note_present
validation:
  items:
    - 校验生成文件符合最小 Guard Profile（守卫画像）契约。
    - 校验复核记录引用完整。
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_confirmed_notes_generate_valid_guard_profile(tmp_path: Path) -> None:
    input_path = tmp_path / "confirmed.yaml"
    output_path = tmp_path / "release-review-order"
    write_complete_extraction_input(input_path)

    result = run_extractor(input_path, output_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: generated" in result.stdout
    assert "validation: passed" in result.stdout

    validation = run_validator(output_path)
    assert validation.returncode == 0, validation.stdout + validation.stderr
    assert (output_path / "GUARD-MANIFEST.yaml").exists()
    assert (output_path / "target-model.yaml").exists()
    assert (output_path / "validation-plan.md").exists()
    brief_template = (output_path / "brief-template.md").read_text(encoding="utf-8")
    assert "{{ subject_key_hash }}" in brief_template
    assert "{{ permissions }}" in brief_template
    assert "{{ transition_conditions }}" in brief_template
    assert "{{ state_completion_instruction }}" in brief_template


def test_generation_includes_guard_point_implementation_plan(tmp_path: Path) -> None:
    input_path = tmp_path / "confirmed.yaml"
    output_path = tmp_path / "release-review-order"
    write_complete_extraction_input(input_path)

    result = run_extractor(input_path, output_path)

    assert result.returncode == 0, result.stdout + result.stderr
    implementation_plan = (output_path / "implementation-plan.md").read_text(encoding="utf-8")
    assert "# Implementation Plan（实施计划）" in implementation_plan
    assert "## 初始化" in implementation_plan
    assert "## 守卫注入" in implementation_plan
    assert "## Hook（钩子）" in implementation_plan
    assert "## 配置" in implementation_plan
    assert "## 守卫点划分" in implementation_plan
    assert "## 单个守卫点单独实施计划" in implementation_plan
    assert "review_note_present" in implementation_plan
    assert "初始化阶段只生成配置和验证计划" in implementation_plan
    assert "根据本次调用确认画像：`release-review-order`" in implementation_plan
    assert "Guard Injection（守卫注入）默认启用" in implementation_plan
    assert "调研已确认启用 Hook（钩子）" in implementation_plan
    assert "install_hooks.py --authorize-install" in implementation_plan
    assert "审计目录" not in implementation_plan
    assert "验证该守卫点失败时不会推进状态" in implementation_plan
    assert "warn" not in implementation_plan
    assert "record" not in implementation_plan


def test_missing_required_field_reports_needs_confirmation_without_full_profile(tmp_path: Path) -> None:
    input_path = tmp_path / "missing-boundary.yaml"
    output_path = tmp_path / "release-review-order"
    write_complete_extraction_input(input_path)
    input_path.write_text(
        input_path.read_text(encoding="utf-8").replace(
            "  boundary: 只旁路观察发布流程，不修改发布流程说明。\n", ""
        ),
        encoding="utf-8",
    )

    result = run_extractor(input_path, output_path)

    assert result.returncode == 1
    assert "status: needs_confirmation" in result.stdout
    assert "field: target.boundary" in result.stdout
    assert "$grill-with-docs" in result.stdout
    assert (output_path / "needs-confirmation.yaml").exists()
    assert not (output_path / "GUARD-MANIFEST.yaml").exists()


def test_profile_ref_mismatch_reports_needs_confirmation(tmp_path: Path) -> None:
    input_path = tmp_path / "mismatch.yaml"
    output_path = tmp_path / "release-review-order"
    write_complete_extraction_input(input_path)
    input_path.write_text(
        input_path.read_text(encoding="utf-8").replace(
            "  requested_profile_ref: release-review-order\n",
            "  requested_profile_ref: other-profile\n",
        ),
        encoding="utf-8",
    )

    result = run_extractor(input_path, output_path)

    assert result.returncode == 1
    assert "initialization.requested_profile_ref" in result.stdout


def test_deny_permissions_require_extra_authorization_before_generation(tmp_path: Path) -> None:
    input_path = tmp_path / "confirmed-with-deny.yaml"
    output_path = tmp_path / "release-review-order"
    write_complete_extraction_input(input_path)
    input_path.write_text(
        input_path.read_text(encoding="utf-8").replace(
            "    - id: review_required\n      description: 等待发布复核完成。",
            """    - id: review_required
      description: 等待发布复核完成。
      permissions:
        default: deny""",
        ),
        encoding="utf-8",
    )

    blocked = run_extractor(input_path, output_path)

    assert blocked.returncode == 1
    assert "status: authorization_required" in blocked.stdout
    assert "authorization: deny_permissions_missing" in blocked.stdout
    assert (output_path / "deny-authorization-required.yaml").exists()
    assert not (output_path / "GUARD-MANIFEST.yaml").exists()

    allowed = run_extractor(input_path, output_path, ["--authorize-deny-permissions"])

    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert "status: generated" in allowed.stdout


def test_disabled_guard_injection_reports_needs_confirmation(tmp_path: Path) -> None:
    input_path = tmp_path / "injection-disabled.yaml"
    output_path = tmp_path / "release-review-order"
    write_complete_extraction_input(input_path)
    input_path.write_text(
        input_path.read_text(encoding="utf-8").replace(
            "  guard_injection:\n    enabled: true\n",
            "  guard_injection:\n    enabled: false\n",
        ),
        encoding="utf-8",
    )

    result = run_extractor(input_path, output_path)

    assert result.returncode == 1
    assert "initialization.guard_injection.enabled" in result.stdout


def test_generation_does_not_modify_guarded_target_file(tmp_path: Path) -> None:
    input_path = tmp_path / "confirmed.yaml"
    output_path = tmp_path / "release-review-order"
    target_file = tmp_path / "release.md"
    target_file.write_text("# 发布流程\n\n原流程说明保持原样。\n", encoding="utf-8")
    before = target_file.read_text(encoding="utf-8")
    write_complete_extraction_input(input_path)
    input_path.write_text(
        input_path.read_text(encoding="utf-8").replace(
            "  source: docs/release.md\n", f"  source: {target_file}\n"
        ),
        encoding="utf-8",
    )

    result = run_extractor(input_path, output_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert target_file.read_text(encoding="utf-8") == before
