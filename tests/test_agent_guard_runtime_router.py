import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
PLUGIN_SKILL = PLUGIN_ROOT / "skills" / "agent-guard"
HOOK_ROUTER = PLUGIN_ROOT / "scripts" / "hook_router.py"
RUNTIME_CLI = PLUGIN_ROOT / "scripts" / "guard_runtime" / "cli.py"
MINIMAL_PROFILE = PLUGIN_SKILL / "assets" / "templates" / "guard-profile" / "minimal"


def run_hook(args: list[str], payload: dict) -> subprocess.CompletedProcess[str]:
    payload_file = Path(args[args.index("--payload-file") + 1])
    payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(HOOK_ROUTER), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNTIME_CLI), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def body(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def write_profile(project: Path) -> Path:
    profile_dir = project / ".agents" / "guards" / "minimal-sample"
    shutil.copytree(MINIMAL_PROFILE, profile_dir)
    return profile_dir


def session_start(project: Path, user_home: Path) -> None:
    result = run_hook(
        [
            "--source",
            "codex",
            "--event",
            "SessionStart",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--payload-file",
            str(project / "session-start.json"),
        ],
        {"session_id": "session-1", "cwd": str(project)},
    )
    assert result.returncode == 0, result.stdout + result.stderr


def activate(project: Path, user_home: Path) -> dict:
    result = run_cli(
        [
            "activate",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            "codex",
            "--session-id",
            "session-1",
            "--profile",
            "minimal-sample",
            "--create",
            "--title",
            "Router 测试",
            "--description",
            "验证 Runtime Router。",
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return body(result)


def pre_tool(project: Path, user_home: Path, command: str = "git status") -> subprocess.CompletedProcess[str]:
    return pre_tool_payload(project, user_home, {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": command}})


def pre_tool_payload(project: Path, user_home: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    return run_hook(
        [
            "--source",
            "codex",
            "--event",
            "PreToolUse",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--payload-file",
            str(project / "pre-tool.json"),
        ],
        payload,
    )


def write_state_machine(profile: Path, permission_effect: str) -> None:
    profile.joinpath("state-machine.yaml").write_text(
        f"""
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
    permissions:
      default: allow
      rules:
        - effect: {permission_effect}
          tool: Bash
          match:
            command_prefix: git push
          reason: 当前状态要求 {permission_effect}。
          suggestion: 按守卫提示处理。
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    required_artifacts:
      - completion_note
""".lstrip(),
        encoding="utf-8",
    )


def write_state_machine_with_guard_point_only(profile: Path) -> None:
    profile.joinpath("state-machine.yaml").write_text(
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
  - id: close_after_guard_point
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""".lstrip(),
        encoding="utf-8",
    )


def write_completion_note(project: Path, instance_id: str) -> None:
    path = project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "1" / "completion-note.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"value": "完成"}, ensure_ascii=False), encoding="utf-8")


def completion_note_path(project: Path, instance_id: str) -> Path:
    return project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "1" / "completion-note.json"


def write_completion_note_json(project: Path, instance_id: str, data: dict | list) -> None:
    path = completion_note_path(project, instance_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def write_completion_note_text(project: Path, instance_id: str, content: str) -> None:
    path = completion_note_path(project, instance_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json_guard_point(profile: Path, checks_yaml: str) -> None:
    profile.joinpath("guard-points.yaml").write_text(
        f"""
guard_points:
  - id: completion_note_present
    description: JSON artifact 必须满足字段断言。
    checks:
{checks_yaml}
""".lstrip(),
        encoding="utf-8",
    )


def read_brief(project: Path, user_home: Path) -> dict:
    result = run_cli(["brief", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])
    assert result.returncode == 0, result.stdout + result.stderr
    return body(result)


def test_pre_tool_use_without_focus_allows_and_audits(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    write_profile(project)

    result = pre_tool(project, user_home)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert payload["reason"] == "no_session_focus_instance"
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["status"] == "allow"
    assert audit["reason"] == "no_session_focus_instance"


def test_pre_tool_use_missing_session_id_returns_error_without_focus_audit(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    write_profile(project)

    result = pre_tool_payload(project, user_home, {"cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "git status"}})

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload == {"status": "error", "reason": "missing_session_id"}
    assert not (project / ".local" / "guard" / "audit").exists()


def test_invalid_and_multiple_focus_bindings_error_without_permission_deny(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    write_profile(project)
    binding_path = project / ".local" / "guard" / "session-focus" / "codex" / "session-1.json"
    binding_path.parent.mkdir(parents=True, exist_ok=True)
    binding_path.write_text("{broken", encoding="utf-8")

    invalid = pre_tool(project, user_home)

    assert invalid.returncode == 1, invalid.stdout + invalid.stderr
    invalid_body = body(invalid)
    assert invalid_body["status"] == "invalid_session_focus_binding"
    assert invalid_body["reason"] == "invalid_session_focus_binding"
    invalid_audit = json.loads(Path(invalid_body["audit_path"]).read_text(encoding="utf-8"))
    assert invalid_audit["status"] == "error"

    binding_path.write_text(
        json.dumps(
            {
                "source": "codex",
                "session_id": "session-1",
                "scope": "project",
                "profile_id": "minimal-sample",
                "instance_id": "agi_missing",
                "bound_at": "2026-06-16T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    user_binding = user_home / ".agents" / "guard" / "session-focus" / "codex" / "session-1.json"
    user_binding.parent.mkdir(parents=True, exist_ok=True)
    user_binding.write_text(binding_path.read_text(encoding="utf-8"), encoding="utf-8")

    multiple = pre_tool(project, user_home)

    assert multiple.returncode == 1, multiple.stdout + multiple.stderr
    multiple_body = body(multiple)
    assert multiple_body["status"] == "multiple_session_focus_bindings"
    assert multiple_body["reason"] == "multiple_session_focus_bindings"
    multiple_audit = json.loads(Path(multiple_body["audit_path"]).read_text(encoding="utf-8"))
    assert multiple_audit["status"] == "error"


def test_missing_or_closed_instance_is_treated_as_no_focus(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    write_profile(project)
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]

    missing_state = project / ".local" / "guard" / "state" / "minimal-sample" / instance_id
    shutil.rmtree(missing_state)
    missing = pre_tool(project, user_home)
    assert missing.returncode == 0, missing.stdout + missing.stderr
    assert body(missing)["reason"] == "no_session_focus_instance"

    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    close = run_cli(["close-instance", "--project", str(project), "--profile", "minimal-sample", "--instance-id", instance_id])
    assert close.returncode == 0, close.stdout + close.stderr
    closed = pre_tool(project, user_home)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert body(closed)["reason"] == "no_session_focus_instance"


def test_valid_focus_evaluates_allow_ask_deny_and_incompatible_version(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    session_start(project, user_home)
    activate(project, user_home)

    write_state_machine(profile, "deny")
    denied = pre_tool(project, user_home, "git push origin main")
    assert denied.returncode == 1, denied.stdout + denied.stderr
    assert body(denied)["status"] == "deny"
    assert body(denied)["reason"] == "当前状态要求 deny。"

    write_state_machine(profile, "ask")
    asked = pre_tool(project, user_home, "git push origin main")
    assert asked.returncode == 1, asked.stdout + asked.stderr
    assert body(asked)["status"] == "ask"

    allowed = pre_tool(project, user_home, "git status")
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert body(allowed)["status"] == "allow"

    manifest = profile / "GUARD-MANIFEST.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("runtime_api_version: agent-guard-runtime/v1", "runtime_api_version: old/v0"),
        encoding="utf-8",
    )
    incompatible = pre_tool(project, user_home, "git push origin main")
    assert incompatible.returncode == 0, incompatible.stdout + incompatible.stderr
    assert body(incompatible)["status"] == "allow"
    assert body(incompatible)["reason"] == "incompatible_runtime_api_version"


def test_state_completed_requires_focus_and_rejects_profile_or_instance_args(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    write_profile(project)

    no_focus = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])
    assert no_focus.returncode == 1
    assert body(no_focus)["status"] == "no_session_focus_instance"
    assert "activate" in body(no_focus)["next"]

    rejected = run_cli(
        [
            "state-completed",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            "codex",
            "--session-id",
            "session-1",
            "--profile",
            "minimal-sample",
        ]
    )
    assert rejected.returncode == 2
    assert "unrecognized arguments: --profile" in rejected.stderr


def test_state_completed_advances_current_focus_and_lock_timeout_audits(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    write_profile(project)
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    assert body(result)["status"] == "brief_required"

    read_brief(project, user_home)
    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert payload["reason"] == "state_completed"
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["state_version"] == 2

    read_brief(project, user_home)
    terminal = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])
    assert terminal.returncode == 1, terminal.stdout + terminal.stderr
    terminal_body = body(terminal)
    assert terminal_body["status"] == "error"
    assert terminal_body["reason"] == "terminal_state_completed"
    assert terminal_body["current_state"] == "closed"

    second = activate(project, user_home)
    second_id = second["instance_id"]
    write_completion_note(project, second_id)
    read_brief(project, user_home)
    lock = project / ".local" / "guard" / "locks" / "minimal-sample" / f"{second_id}.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("held", encoding="utf-8")

    locked = run_cli(
        [
            "state-completed",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            "codex",
            "--session-id",
            "session-1",
            "--lock-timeout",
            "0",
        ]
    )

    assert locked.returncode == 1, locked.stdout + locked.stderr
    locked_body = body(locked)
    assert locked_body["status"] == "lock_timeout"
    audit = json.loads(Path(locked_body["audit_path"]).read_text(encoding="utf-8"))
    assert audit["status"] == "lock_timeout"


def test_state_completed_evaluates_guard_points_before_advancing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 必须失败的守卫点。
    checks:
      - id: impossible_artifact
        type: artifact_exists
        artifact: missing_artifact
        failure_reason: 缺少 impossible artifact。
        fix_hint: 提供 impossible artifact。
    override_policy:
      allowed: false
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "error"
    assert payload["reason"] == "guard_failed"
    assert payload["guard_point_id"] == "completion_note_present"
    assert payload["check_id"] == "impossible_artifact"
    assert payload["current_state"] == "open"
    details = payload["details"]
    assert details["guard_point_id"] == "completion_note_present"
    assert details["failure_reason"] == "缺少 impossible artifact。"
    assert details["current_state"] == "open"
    assert details["required_conditions"] == ["artifact_exists:missing_artifact"]
    assert details["fix_hint"] == "提供 impossible artifact。"
    assert details["override_allowed"] is False
    assert Path(details["override_record_path"]).parts[-4:] == ("overrides", "minimal-sample", instance_id, "completion_note_present.json")
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "open"


def test_state_completed_allows_json_artifact_equals_check(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: JSON artifact 必须满足字段断言。
    checks:
      - id: completion_status_done
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: equals
        value: done
        failure_reason: completion note 状态不正确。
        fix_hint: 更新 completion note。
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    path = project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "1" / "completion-note.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": "done"}, ensure_ascii=False), encoding="utf-8")
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert payload["reason"] == "state_completed"
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"


def test_state_completed_blocks_json_artifact_equals_check_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: JSON artifact 必须满足字段断言。
    checks:
      - id: completion_status_done
        type: json_artifact
        artifact: completion_note
        field: security_review.tool
        predicate: equals
        value: codex-security
        failure_reason: security review 工具不正确。
        fix_hint: 更新 security review artifact。
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    path = project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "1" / "completion-note.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"security_review": {"tool": "manual"}}, ensure_ascii=False), encoding="utf-8")
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "error"
    assert payload["reason"] == "guard_failed"
    assert payload["guard_point_id"] == "completion_note_present"
    assert payload["check_id"] == "completion_status_done"
    details = payload["details"]
    assert details["failure_reason"] == "security review 工具不正确。"
    assert details["json_check"] == {
        "artifact": "completion_note",
        "field": "security_review.tool",
        "predicate": "equals",
        "expected": "codex-security",
        "actual": "manual",
    }
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "open"


def test_state_completed_supports_json_exists_and_value_predicates(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_exists
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: exists
      - id: review_status_passes
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: equals
        value: pass
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_does_not_accept_expected_config_key_for_json_value(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_passes
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: equals
        expected: pass
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact_check"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "review.status",
        "predicate": "equals",
        "actual": "pass",
    }


def test_state_completed_blocks_json_not_equals_with_legacy_expected_config_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_not_blocked
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: not_equals
        expected: blocked
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact_check"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "review.status",
        "predicate": "not_equals",
        "actual": "pass",
    }


def test_state_completed_blocks_json_not_equals_without_value(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_not_blocked
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: not_equals
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact_check"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "review.status",
        "predicate": "not_equals",
        "actual": "pass",
    }


def test_state_completed_supports_json_not_equals_predicate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_not_blocked
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: not_equals
        value: blocked
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_blocks_json_not_equals_predicate_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_not_blocked
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: not_equals
        value: blocked
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "blocked"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "review.status",
        "predicate": "not_equals",
        "expected": "blocked",
        "actual": "blocked",
    }


def test_state_completed_blocks_json_missing_field(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_exists
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: exists
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"result": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "json_artifact_check_failed"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "review.status",
        "predicate": "exists",
    }


def test_state_completed_supports_json_number_predicates(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: p0_count_within_limit
        type: json_artifact
        artifact: completion_note
        field: findings.p0
        predicate: number_lte
        value: 0
      - id: confidence_high_enough
        type: json_artifact
        artifact: completion_note
        field: confidence
        predicate: number_gte
        value: 0.8
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"findings": {"p0": 0}, "confidence": 0.9})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_blocks_json_number_predicate_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: p0_count_within_limit
        type: json_artifact
        artifact: completion_note
        field: findings.p0
        predicate: number_lte
        value: 0
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"findings": {"p0": 1}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "findings.p0",
        "predicate": "number_lte",
        "expected": 0,
        "actual": 1,
    }


def test_state_completed_supports_json_array_none_predicate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: no_blocking_findings
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_none
        where:
          field: severity
          predicate: equals
          value: P0
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"findings": [{"severity": "P2"}, {"severity": "P3"}]})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_blocks_json_array_none_predicate_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: no_blocking_findings
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_none
        where:
          field: severity
          predicate: equals
          value: P0
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    findings = [{"severity": "P0"}, {"severity": "P2"}]
    write_completion_note_json(project, instance_id, {"findings": findings})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "findings",
        "predicate": "array_none",
        "expected": "no matching elements",
        "actual": findings,
    }


def test_state_completed_blocks_json_array_none_where_with_legacy_expected_config_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: no_blocking_findings
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_none
        where:
          field: severity
          predicate: equals
          expected: P0
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    findings = [{"severity": "P0"}, {"severity": "P2"}]
    write_completion_note_json(project, instance_id, {"findings": findings})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact_check"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "findings",
        "predicate": "equals",
        "actual": findings,
    }


def test_state_completed_supports_json_array_all_predicate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: all_findings_triaged
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_all
        where:
          field: triaged
          predicate: equals
          value: true
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"findings": [{"triaged": True}, {"triaged": True}]})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_blocks_json_array_all_predicate_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: all_findings_triaged
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_all
        where:
          field: triaged
          predicate: equals
          value: true
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    findings = [{"triaged": True}, {"triaged": False}]
    write_completion_note_json(project, instance_id, {"findings": findings})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "findings",
        "predicate": "array_all",
        "expected": "all elements match",
        "actual": findings,
    }


def test_state_completed_blocks_json_array_all_where_without_value(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: all_findings_triaged
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_all
        where:
          field: triaged
          predicate: equals
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    findings = [{"triaged": True}, {"triaged": True}]
    write_completion_note_json(project, instance_id, {"findings": findings})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact_check"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "findings",
        "predicate": "equals",
        "actual": findings,
    }


def test_state_completed_blocks_invalid_json_artifact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: status_passes
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: equals
        value: pass
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_text(project, instance_id, "{broken")
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "status",
        "predicate": "equals",
        "expected": "pass",
    }
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["detail"]["details"]["json_check"] == payload["details"]["json_check"]


def test_state_completed_blocks_json_artifact_absolute_path_outside_runtime_artifacts_without_leak(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    outside = tmp_path / "outside-secret.json"
    secret = "outside-json-secret-should-not-leak"
    outside.write_text(json.dumps({"secret": secret}, ensure_ascii=False), encoding="utf-8")
    profile.joinpath("artifacts.yaml").write_text(
        f"""
artifacts:
  - id: completion_note
    type: note
    path: '{outside.as_posix()}'
""".lstrip(),
        encoding="utf-8",
    )
    write_json_guard_point(
        profile,
        """
      - id: secret_matches
        type: json_artifact
        artifact: completion_note
        field: secret
        predicate: equals
        value: allowed
""",
    )
    session_start(project, user_home)
    activate(project, user_home)
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    assert secret not in result.stdout
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "json_artifact_path_outside_runtime_artifacts"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "secret",
        "predicate": "equals",
        "expected": "allowed",
    }
    audit_text = Path(payload["audit_path"]).read_text(encoding="utf-8")
    assert secret not in audit_text


def test_state_completed_blocks_missing_json_artifact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_state_machine_with_guard_point_only(profile)
    write_json_guard_point(
        profile,
        """
      - id: status_passes
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: equals
        value: pass
""",
    )
    session_start(project, user_home)
    activate(project, user_home)
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "missing_required_artifacts"
    assert payload["details"]["missing_artifacts"] == ["completion_note"]
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "status",
        "predicate": "equals",
        "expected": "pass",
    }


def test_state_completed_blocks_unsupported_json_artifact_predicate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: status_matches
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: matches_regex
        value: pass
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"status": "pass"})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "unsupported_json_artifact_predicate"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "status",
        "predicate": "matches_regex",
        "expected": "pass",
        "actual": "pass",
    }


def test_state_completed_reports_supported_guard_point_check_types(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 守卫点包含不支持的检查类型。
    checks:
      - id: unsupported
        type: shell_command
        artifact: completion_note
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "unsupported_guard_point_check"
    assert payload["details"]["fix_hint"] == "Runtime（运行时）当前支持 artifact_exists 和 json_artifact 检查。"
    assert payload["details"]["required_conditions"] == ["supported_check:artifact_exists", "supported_check:json_artifact"]


def test_state_completed_allows_guard_point_failure_with_valid_override(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 可人工覆盖的守卫点。
    allow_override: true
    checks:
      - id: impossible_artifact
        type: artifact_exists
        artifact: missing_artifact
        failure_reason: 缺少 impossible artifact。
        fix_hint: 提供 impossible artifact。
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    override_path = project / ".local" / "guard" / "overrides" / "minimal-sample" / instance_id / "completion_note_present.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(
        json.dumps(
            {
                "decision": "allow",
                "reason": "人工确认允许跳过该守卫点。",
                "approved_by": "test-user",
                "approved_at": "2026-06-16T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert payload["reason"] == "state_completed"
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["reason"] == "state_completed"
    assert audit["detail"]["overrides"][0]["guard_point_id"] == "completion_note_present"
    assert audit["detail"]["overrides"][0]["override_record_path"] == str(override_path)


def test_state_completed_allows_profile_level_override(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    manifest = profile.joinpath("GUARD-MANIFEST.yaml")
    manifest.write_text(manifest.read_text(encoding="utf-8") + "allow_override: true\n", encoding="utf-8")
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 由画像级配置允许覆盖。
    checks:
      - id: impossible_artifact
        type: artifact_exists
        artifact: missing_artifact
        failure_reason: 缺少 impossible artifact。
        fix_hint: 提供 impossible artifact。
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    override_path = project / ".local" / "guard" / "overrides" / "minimal-sample" / instance_id / "completion_note_present.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(
        json.dumps(
            {
                "decision": "allow",
                "reason": "画像级配置允许跳过该守卫点。",
                "approved_by": "test-user",
                "approved_at": "2026-06-16T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert payload["reason"] == "state_completed"
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["detail"]["overrides"][0]["override_record_path"] == str(override_path)


def test_profile_level_override_does_not_allow_missing_guard_point(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    manifest = profile.joinpath("GUARD-MANIFEST.yaml")
    manifest.write_text(manifest.read_text(encoding="utf-8") + "allow_override: true\n", encoding="utf-8")
    profile.joinpath("guard-points.yaml").write_text("guard_points: []\n", encoding="utf-8")
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    override_path = project / ".local" / "guard" / "overrides" / "minimal-sample" / instance_id / "completion_note_present.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(
        json.dumps(
            {
                "decision": "allow",
                "reason": "缺失守卫点不应被覆盖。",
                "approved_by": "test-user",
                "approved_at": "2026-06-16T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "error"
    assert payload["reason"] == "guard_failed"
    assert payload["guard_point_id"] == "completion_note_present"
    assert payload["failure_reason"] == "missing_guard_point"
    assert payload["override_allowed"] is False
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "open"


def test_state_completed_rejects_ambiguous_transition_matches(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    state_machine = profile.joinpath("state-machine.yaml")
    state_machine.write_text(
        state_machine.read_text(encoding="utf-8")
        + """
  - id: also_close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
    required_artifacts:
      - completion_note
""",
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "error"
    assert payload["reason"] == "ambiguous_state_transition"
    assert payload["candidate_transition_ids"] == ["close_after_note", "also_close_after_note"]
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
