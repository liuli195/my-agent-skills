import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PROJECT_GUARD = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "init_project_guard.py"
RUN_GUARD_EVENT = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "run_guard_event.py"
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


def run_init(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INIT_PROJECT_GUARD), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_runtime(project: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    runner = project / ".agents" / "guard-runtime" / "guard_runner.py"
    return subprocess.run(
        [sys.executable, str(runner), *args],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_skill_event(project: Path, event_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUN_GUARD_EVENT), "--project", str(project), "--event", str(event_path)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def initialized_project(tmp_path: Path) -> Path:
    project = tmp_path / "target-project"
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)
    result = run_init(["--profile", str(draft), "--project", str(project), "--authorize-init"])
    assert result.returncode == 0, result.stdout + result.stderr
    return project


def output_value(stdout: str, key: str) -> str:
    prefix = f"{key}: "
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"missing output key: {key}\n{stdout}")


def activate_minimal(project: Path) -> str:
    result = run_runtime(
        project,
        [
            "activate",
            "--profile",
            "minimal-sample",
            "--scope",
            "current_context",
            "--source",
            "agent-guard-skill",
            "--context-json",
            json.dumps({"session_id": "session-1", "repo": "repo-a", "worktree": "main"}),
        ],
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return output_value(result.stdout, "subject_key_hash")


def write_event(path: Path, body: dict) -> Path:
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_project_guard_points(project: Path, yaml_text: str) -> None:
    path = project / ".agents" / "guards" / "minimal-sample" / "guard-points.yaml"
    path.write_text(yaml_text.lstrip(), encoding="utf-8")


def write_project_state_machine(project: Path, yaml_text: str) -> None:
    path = project / ".agents" / "guards" / "minimal-sample" / "state-machine.yaml"
    path.write_text(yaml_text.lstrip(), encoding="utf-8")


def write_override_record(project: Path, subject_hash: str, guard_point_id: str, body: dict) -> Path:
    path = project / ".local" / "guard" / "overrides" / "minimal-sample" / subject_hash / f"{guard_point_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def minimal_close_event(**overrides: object) -> dict:
    event = {
        "event_id": "event-1",
        "event_type": "guard.close",
        "source": "manual",
        "timestamp": "2026-06-12T00:00:00Z",
        "guard_profile_id": "minimal-sample",
        "context": {"session_id": "session-1", "repo": "repo-a", "worktree": "main"},
        "payload": {"artifacts": {"completion_note": "关闭说明"}},
        "tool": {"name": "manual"},
        "action": {"name": "close"},
        "raw_event_summary": "人工关闭样例 Guard Profile（守卫画像）。",
    }
    event.update(overrides)
    return event


def test_block_mode_guard_point_failure_blocks_and_reports_fix(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求事件已经人工批准。
    mode: block
    override_policy:
      allowed: true
    checks:
      - id: approval_flag_true
        type: event_field
        field: payload.approved
        equals: true
        failure_reason: 事件缺少人工批准标记。
        fix_hint: 在事件 payload.approved 写入 true。
""",
    )
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: block" in result.stdout
    assert "decision: guard_failed" in result.stdout
    assert 'failed_guard_points: ["completion_note_present"]' in result.stdout
    assert 'fix_suggestions: ["在事件 payload.approved 写入 true。"]' in result.stdout
    assert "override_allowed: true" in result.stdout
    assert "override_record_path:" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    raw_event = json.loads((audit_path.parent / "raw-event.json").read_text(encoding="utf-8"))
    assert audit["status"] == "block"
    assert audit["raw_event_path"] == str(audit_path.parent / "raw-event.json")
    assert raw_event["event_id"] == "event-1"
    assert audit["detail"]["current_state"] == "open"
    assert audit["detail"]["failed_guard_points"] == ["completion_note_present"]


def test_record_mode_guard_point_failure_audits_and_advances_state(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 记录模式下只审计失败。
    mode: record
    checks:
      - id: approval_flag_true
        type: event_field
        field: payload.approved
        equals: true
        failure_reason: 事件缺少人工批准标记。
        fix_hint: 在事件 payload.approved 写入 true。
""",
    )
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: guard_recorded" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["state_version"] == 2

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "allow"
    assert audit["detail"]["decision"] == "guard_recorded"
    assert audit["detail"]["state_change"] == {"from": "open", "to": "closed", "version": 2}


def test_warn_mode_guard_point_failure_warns_and_advances_state(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 警告模式下失败仍推进状态。
    mode: warn
    checks:
      - id: approval_flag_true
        type: event_field
        field: payload.approved
        equals: true
        failure_reason: 事件缺少人工批准标记。
        fix_hint: 在事件 payload.approved 写入 true。
""",
    )
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: warn" in result.stdout
    assert "decision: guard_failed" in result.stdout
    assert "from_state: open" in result.stdout
    assert "to_state: closed" in result.stdout
    assert "state_version: 2" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["state_version"] == 2


def test_warn_failure_can_be_configured_to_hold_state(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_project_state_machine(
        project,
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: guard.close
    advance_on_warn_failure: false
    guard_points:
      - completion_note_present
""",
    )
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 警告失败配置为不推进。
    mode: warn
    checks:
      - id: approval_flag_true
        type: event_field
        field: payload.approved
        equals: true
        failure_reason: 事件缺少人工批准标记。
        fix_hint: 在事件 payload.approved 写入 true。
""",
    )
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: warn" in result.stdout
    assert "decision: guard_failed" in result.stdout
    assert "state: open" in result.stdout
    assert "state_version: 1" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1


def test_valid_override_allows_specific_subject_and_guard_point_to_advance(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求事件已经人工批准。
    mode: block
    override_policy:
      allowed: true
    checks:
      - id: approval_flag_true
        type: event_field
        field: payload.approved
        equals: true
        failure_reason: 事件缺少人工批准标记。
        fix_hint: 在事件 payload.approved 写入 true。
""",
    )
    write_override_record(
        project,
        subject_hash,
        "completion_note_present",
        {
            "guard_profile_id": "minimal-sample",
            "subject_key_hash": subject_hash,
            "guard_point_id": "completion_note_present",
            "expires_at": "2999-01-01T00:00:00Z",
            "reason": "用户确认本次允许跳过批准字段。",
        },
    )
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: advanced" in result.stdout
    assert "to_state: closed" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["state_version"] == 2

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["detail"]["guard_results"][0]["result"] == "overridden"
    assert audit["detail"]["guard_results"][0]["override"]["reason"] == "override_valid"


def test_expired_override_does_not_allow_blocked_guard_point(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求事件已经人工批准。
    mode: block
    override_policy:
      allowed: true
    checks:
      - id: approval_flag_true
        type: event_field
        field: payload.approved
        equals: true
        failure_reason: 事件缺少人工批准标记。
        fix_hint: 在事件 payload.approved 写入 true。
""",
    )
    write_override_record(
        project,
        subject_hash,
        "completion_note_present",
        {
            "guard_profile_id": "minimal-sample",
            "subject_key_hash": subject_hash,
            "guard_point_id": "completion_note_present",
            "expires_at": "2000-01-01T00:00:00Z",
            "reason": "过期覆盖不应生效。",
        },
    )
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: block" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["detail"]["guard_results"][0]["override"]["reason"] == "override_expired"


def test_mismatched_override_does_not_allow_blocked_guard_point(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求事件已经人工批准。
    mode: block
    override_policy:
      allowed: true
    checks:
      - id: approval_flag_true
        type: event_field
        field: payload.approved
        equals: true
        failure_reason: 事件缺少人工批准标记。
        fix_hint: 在事件 payload.approved 写入 true。
""",
    )
    write_override_record(
        project,
        subject_hash,
        "completion_note_present",
        {
            "guard_profile_id": "minimal-sample",
            "subject_key_hash": "wrong-subject",
            "guard_point_id": "completion_note_present",
            "expires_at": "2999-01-01T00:00:00Z",
            "reason": "Subject 不匹配时不能放行。",
        },
    )
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: block" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["detail"]["guard_results"][0]["override"]["reason"] == "override_subject_mismatch"


def test_state_freshness_and_human_confirmation_checks_can_pass_together(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求状态、产物新鲜度和人工确认都通过。
    mode: block
    checks:
      - id: still_open
        type: state
        current_state: open
      - id: completion_note_fresh
        type: artifact_freshness
        artifact: completion_note
        max_age_seconds: 600
      - id: user_confirmed_close
        type: human_confirmation
        confirmation_id: close-approved
""",
    )
    event = minimal_close_event(
        timestamp="2026-06-12T00:05:00Z",
        payload={
            "artifacts": {
                "completion_note": {
                    "value": "关闭说明",
                    "updated_at": "2026-06-12T00:00:00Z",
                }
            },
            "confirmations": {
                "close-approved": {
                    "confirmed": True,
                    "reason": "允许关闭。",
                }
            },
        },
    )
    event_path = write_event(tmp_path / "event.json", event)

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: advanced" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["state_version"] == 2


def test_matching_event_advances_state_and_writes_audit(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: advanced" in result.stdout
    assert "transition_id: close_after_note" in result.stdout
    assert "from_state: open" in result.stdout
    assert "to_state: closed" in result.stdout
    assert "state_version: 2" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["state_version"] == 2
    assert state["last_transition_id"] == "close_after_note"

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "allow"
    assert audit["detail"]["decision"] == "advanced"
    assert audit["detail"]["transition"]["id"] == "close_after_note"
    assert audit["detail"]["state_change"] == {"from": "open", "to": "closed", "version": 2}


def test_unmatched_event_is_allowed_ignored_and_does_not_advance_state(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    event_path = write_event(tmp_path / "event.json", minimal_close_event(event_type="guard.unrelated"))
    runs_root = project / ".local" / "guard" / "runs" / "minimal-sample"
    before_runs = sorted(path.name for path in runs_root.iterdir())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: ignored" in result.stdout
    assert "reason: no_matching_transition" in result.stdout
    assert "state_version: 1" in result.stdout
    assert "audit_path:" not in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1

    assert sorted(path.name for path in runs_root.iterdir()) == before_runs


def test_event_missing_subject_field_returns_no_subject_match_and_writes_audit(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    event_path = write_event(
        tmp_path / "event.json",
        minimal_close_event(context={"repo": "repo-a", "worktree": "main"}),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: no_subject_match" in result.stdout
    assert "reason: missing_required_fields" in result.stdout
    assert "context.session_id" in result.stdout

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "no_subject_match"
    assert audit["detail"]["reason"] == "missing_required_fields"
    assert audit["detail"]["missing_fields"] == ["context.session_id"]


def test_event_with_multiple_matching_instances_returns_ambiguous_subject(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    state_root = project / ".local" / "guard" / "state" / "minimal-sample"
    shutil.copytree(state_root / subject_hash, state_root / "duplicate-candidate")
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: ambiguous_subject" in result.stdout
    assert "candidate_count: 2" in result.stdout

    state = json.loads((state_root / subject_hash / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1
    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "ambiguous_subject"
    assert len(audit["detail"]["candidate_state_paths"]) == 2


def test_multiple_matching_transitions_return_ambiguous_transition_without_state_change(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    state_machine = project / ".agents" / "guards" / "minimal-sample" / "state-machine.yaml"
    state_machine.write_text(
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
    on_event: guard.close
    guard_points:
      - completion_note_present
    required_artifacts:
      - completion_note
  - id: duplicate_close_after_note
    from: open
    to: closed
    on_event: guard.close
    guard_points:
      - completion_note_present
    required_artifacts:
      - completion_note
""".lstrip(),
        encoding="utf-8",
    )
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: ambiguous_transition" in result.stdout
    assert "transition_count: 2" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1
    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "ambiguous_transition"
    assert audit["detail"]["matching_transitions"] == ["close_after_note", "duplicate_close_after_note"]


def test_transition_conditions_use_envelope_fields_to_select_transition(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    state_machine = project / ".agents" / "guards" / "minimal-sample" / "state-machine.yaml"
    state_machine.write_text(
        """
initial_state: open
terminal_states:
  - closed_a
  - closed_b
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
  - id: closed_a
    description: 通过 A 路径关闭。
  - id: closed_b
    description: 通过 B 路径关闭。
transitions:
  - id: close_route_a
    from: open
    to: closed_a
    on_event: guard.close
    conditions:
      - field: payload.route
        equals: a
    guard_points:
      - completion_note_present
  - id: close_route_b
    from: open
    to: closed_b
    on_event: guard.close
    conditions:
      - field: payload.route
        equals: b
    guard_points:
      - completion_note_present
""".lstrip(),
        encoding="utf-8",
    )
    event_path = write_event(
        tmp_path / "event.json",
        minimal_close_event(payload={"route": "b", "artifacts": {"completion_note": "关闭说明"}}),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "transition_id: close_route_b" in result.stdout
    assert "to_state: closed_b" in result.stdout
    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed_b"


def test_run_event_lock_timeout_writes_error_audit_without_state_change(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    concurrency = project / ".agents" / "guards" / "minimal-sample" / "concurrency.yaml"
    concurrency.write_text(
        """
concurrency:
  lock_scope: guard-profile-and-subject
  lock_root: .local/guard/locks
  lock_key_fields:
    - guard_profile_id
    - subject_key_hash
  timeout_seconds: 0
  on_timeout: audit_error
""".lstrip(),
        encoding="utf-8",
    )
    lock = project / ".local" / "guard" / "locks" / "minimal-sample" / f"{subject_hash}.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("held\n", encoding="utf-8")
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: lock_timeout" in result.stdout
    assert f"subject_key_hash: {subject_hash}" in result.stdout
    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1
    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "lock_timeout"
    assert audit["detail"]["reason"] == "lock_timeout"


def test_skill_run_guard_event_command_delegates_to_project_runtime(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    activate_minimal(project)
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_skill_event(project, event_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: advanced" in result.stdout
