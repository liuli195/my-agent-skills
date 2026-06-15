import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PROJECT_GUARD = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "init_project_guard.py"
RUN_GUARD_EVENT = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "run_guard_event.py"
MINIMAL_PROFILE = (
    REPO_ROOT
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


def write_project_artifacts(project: Path, yaml_text: str) -> None:
    path = project / ".agents" / "guards" / "minimal-sample" / "artifacts.yaml"
    path.write_text(yaml_text.lstrip(), encoding="utf-8")


def write_project_state_machine(project: Path, yaml_text: str) -> None:
    path = project / ".agents" / "guards" / "minimal-sample" / "state-machine.yaml"
    path.write_text(yaml_text.lstrip(), encoding="utf-8")


def write_completion_note(project: Path, subject_hash: str, state_version: int = 1) -> Path:
    path = (
        project
        / ".local"
        / "guard"
        / "artifacts"
        / "minimal-sample"
        / subject_hash
        / str(state_version)
        / "completion-note.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "value": "关闭说明",
                "updated_at": "2026-06-12T00:00:00Z",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_confirmation_record(project: Path, subject_hash: str, confirmation_id: str, body: dict) -> Path:
    path = project / ".local" / "guard" / "confirmations" / "minimal-sample" / subject_hash / f"{confirmation_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


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


def state_completed_event(**overrides: object) -> dict:
    event = minimal_close_event(
        event_type="state_completed",
        completed_state_id="open",
        raw_event_summary="主 agent 声明当前状态已完成。",
    )
    event.update(overrides)
    return event


def tool_event(tool_name: str, **overrides: object) -> dict:
    event = {
        "event_id": "tool-event-1",
        "event_type": "codex.pre_tool_use",
        "source": "codex",
        "timestamp": "2026-06-12T00:00:00Z",
        "guard_profile_id": "minimal-sample",
        "context": {"session_id": "session-1", "repo": "repo-a", "worktree": "main"},
        "payload": {},
        "tool": {"name": tool_name},
        "action": {"name": "PreToolUse"},
        "raw_event_summary": "Codex PreToolUse 权限检查。",
    }
    event.update(overrides)
    return event


def test_non_state_completed_event_does_not_advance_state(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: ignored" in result.stdout
    assert "reason: non_state_completed_event" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1


def test_state_permission_deny_blocks_tool_event_without_advancing_state(tmp_path: Path) -> None:
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
    permissions:
      default: allow
      rules:
        - effect: deny
          tool: Bash
          match:
            command_prefix:
              - git
              - push
          reason: 当前状态禁止 push。
          suggestion: 先完成当前状态。
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""",
    )
    event_path = write_event(
        tmp_path / "tool-event.json",
        tool_event(
            "Bash",
            payload={
                "command": "git push origin main",
                "parameters": {"remote": "origin"},
                "tool_input": {"branch": "main"},
            },
        ),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: deny" in result.stdout
    assert "decision: denied" in result.stdout
    assert "reason: 当前状态禁止 push。" in result.stdout
    assert "suggestion: 先完成当前状态。" in result.stdout
    assert "details:" in result.stdout
    assert '"permission"' in result.stdout
    assert '"effect": "deny"' in result.stdout
    assert '"tool": "Bash"' in result.stdout
    assert '"command": "git push origin main"' in result.stdout
    assert "failed_guard_points:" not in result.stdout
    details = json.loads(output_value(result.stdout, "details"))
    input_summary = details["permission"]["input_summary"]
    assert input_summary["command"] == "git push origin main"
    assert input_summary["parameters"] == {"remote": "origin"}
    assert input_summary["tool_input"] == {"branch": "main"}

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "deny"
    assert audit["detail"]["decision"] == "denied"
    assert audit["detail"]["permission"]["effect"] == "deny"
    assert audit["detail"]["permission"]["input_summary"]["parameters"] == {"remote": "origin"}


def test_state_permission_ask_requires_confirmation_without_advancing_state(tmp_path: Path) -> None:
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
    permissions:
      default: allow
      rules:
        - effect: ask
          tool: Bash
          match:
            command_prefix:
              - git
              - push
          reason: push 需要用户确认。
          suggestion: 请求用户确认后重试同一命令。
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""",
    )
    event_path = write_event(
        tmp_path / "tool-event.json",
        tool_event("Bash", payload={"command": "git push origin main"}),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: ask" in result.stdout
    assert "decision: confirmation_required" in result.stdout
    assert "reason: push 需要用户确认。" in result.stdout
    assert "suggestion: 请求用户确认后重试同一命令。" in result.stdout
    assert "confirmation_id:" in result.stdout
    assert "confirmation_path:" in result.stdout
    assert "tool_input_hash:" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "ask"
    assert audit["detail"]["decision"] == "confirmation_required"


def test_state_permission_ask_allows_retry_with_valid_confirmation(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    activate_minimal(project)
    write_project_state_machine(
        project,
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
    permissions:
      default: allow
      rules:
        - effect: ask
          tool: Bash
          match:
            command_prefix:
              - git
              - push
          reason: push 需要用户确认。
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""",
    )
    event = tool_event("Bash", payload={"command": "git push origin main"})
    event_path = write_event(tmp_path / "tool-event.json", event)

    ask = run_runtime(project, ["run", "--event", str(event_path)])
    assert ask.returncode == 1, ask.stdout + ask.stderr
    confirmation_path = Path(output_value(ask.stdout, "confirmation_path"))
    confirmation_path.parent.mkdir(parents=True, exist_ok=True)
    confirmation_path.write_text(
        json.dumps(
            {
                "guard_profile_id": "minimal-sample",
                "subject_key_hash": confirmation_path.parent.name,
                "confirmation_id": output_value(ask.stdout, "confirmation_id"),
                "state": "open",
                "tool": "Bash",
                "tool_input_hash": output_value(ask.stdout, "tool_input_hash"),
                "approved_by": "user",
                "approved_at": "2026-06-12T00:00:00Z",
                "expires_at": "2999-01-01T00:00:00Z",
                "reason": "用户允许本次 push。",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    retry = run_runtime(project, ["run", "--event", str(event_path)])

    assert retry.returncode == 0, retry.stdout + retry.stderr
    assert "status: allow" in retry.stdout
    assert "decision: guard_passed" in retry.stdout
    assert "reason: confirmation_valid" in retry.stdout


def test_state_permission_shorthand_deny_blocks_matching_tool_event(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    activate_minimal(project)
    write_project_state_machine(
        project,
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
    permissions:
      default: allow
      deny:
        - "Bash(git push *)"
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""",
    )
    event_path = write_event(
        tmp_path / "tool-event.json",
        tool_event("Bash", payload={"command": "git push origin main"}),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: deny" in result.stdout
    assert "decision: denied" in result.stdout


def test_state_permission_missing_default_returns_profile_error(tmp_path: Path) -> None:
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
    permissions:
      deny:
        - Bash(git push*)
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""",
    )
    event_path = write_event(tmp_path / "tool-event.json", tool_event("Bash", payload={"command": "git push origin main"}))

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "decision: failed" in result.stdout
    assert "reason: invalid_state_permissions" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1


def test_state_permission_matches_codex_tool_input_command(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    activate_minimal(project)
    write_project_state_machine(
        project,
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
    permissions:
      default: allow
      deny:
        - "Bash(git push *)"
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""",
    )
    event_path = write_event(
        tmp_path / "tool-event.json",
        tool_event("Bash", payload={"tool_input": {"command": "git push origin main"}}),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: deny" in result.stdout
    assert "decision: denied" in result.stdout


def test_state_permission_matches_tool_input_parameters(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    activate_minimal(project)
    write_project_state_machine(
        project,
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
    permissions:
      default: allow
      rules:
        - effect: deny
          tool: Read
          match:
            parameters:
              pattern: TODO
              query: status
          reason: 当前状态禁止这个查询。
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""",
    )
    event_path = write_event(
        tmp_path / "tool-event.json",
        tool_event(
            "Read",
            payload={
                "tool_input": {"path": "docs/plan.md", "pattern": "TODO"},
                "parameters": {"query": "status"},
            },
        ),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: deny" in result.stdout
    assert "decision: denied" in result.stdout
    assert "reason: 当前状态禁止这个查询。" in result.stdout
    details = json.loads(output_value(result.stdout, "details"))
    assert details["permission"]["input_summary"]["tool_input"]["pattern"] == "TODO"
    assert details["permission"]["input_summary"]["parameters"]["query"] == "status"


def test_state_permission_matches_path_and_event_fields(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    activate_minimal(project)
    write_project_state_machine(
        project,
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
    permissions:
      default: allow
      rules:
        - effect: deny
          tool: Read
          match:
            path_prefix: docs/private/
            fields:
              payload.reason: secret-review
          reason: 当前状态禁止读取私有文档。
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""",
    )
    blocked_event = write_event(
        tmp_path / "blocked-tool-event.json",
        tool_event("Read", payload={"path": "docs/private/plan.md", "reason": "secret-review"}),
    )
    allowed_event = write_event(
        tmp_path / "allowed-tool-event.json",
        tool_event("Read", payload={"path": "docs/public/plan.md", "reason": "secret-review"}),
    )

    blocked = run_runtime(project, ["run", "--event", str(blocked_event)])
    allowed = run_runtime(project, ["run", "--event", str(allowed_event)])

    assert blocked.returncode == 1, blocked.stdout + blocked.stderr
    assert "status: deny" in blocked.stdout
    assert "reason: 当前状态禁止读取私有文档。" in blocked.stdout
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert "status: allow" in allowed.stdout


def test_state_permission_invalid_field_matcher_does_not_match(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    activate_minimal(project)
    write_project_state_machine(
        project,
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
    permissions:
      default: allow
      rules:
        - effect: deny
          tool: Read
          match:
            fields:
              payload.reason:
                in: secret-review
          reason: 无效 matcher 不应命中。
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""",
    )
    event_path = write_event(
        tmp_path / "tool-event.json",
        tool_event("Read", payload={"path": "docs/private/plan.md", "reason": "secret-review"}),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "reason: 状态 `open` 权限结果为 `allow`。" in result.stdout


def test_state_completed_event_advances_state(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: guard_passed" in result.stdout
    assert "transition_id: close_after_note" in result.stdout
    assert "from_state: open" in result.stdout
    assert "to_state: closed" in result.stdout
    assert "state_version: 2" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["state_version"] == 2


def test_codex_source_state_completed_without_hook_advances_state(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
    event_path = write_event(tmp_path / "event.json", state_completed_event(source="codex"))

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: guard_passed" in result.stdout
    assert "transition_id: close_after_note" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["state_version"] == 2


def test_state_completed_event_ignores_tool_permissions(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
    write_project_state_machine(
        project,
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
    permissions:
      default: deny
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""",
    )
    event_path = write_event(
        tmp_path / "event.json",
        state_completed_event(tool={"name": "Bash"}, payload={"command": "git push origin main"}),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: guard_passed" in result.stdout
    assert "to_state: closed" in result.stdout


def test_state_completed_ignores_payload_artifacts_as_completion_evidence(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    event_path = write_event(
        tmp_path / "event.json",
        state_completed_event(payload={"artifacts": {"completion_note": "payload 里的完成说明不算证据"}}),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "decision: guard_failed" in result.stdout
    assert 'missing_artifacts: ["completion_note"]' in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1


def test_state_completed_rejects_stale_artifact_when_reuse_policy_denies_reuse(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_project_artifacts(
        project,
        """
artifacts:
  - id: completion_note
    description: 不含 state_version（状态版本）的旧完成说明。
    path: .local/guard/artifacts/{guard_profile_id}/{subject_key_hash}/completion-note.json
    freshness:
      scope: current_state_entry
    reuse_policy: deny
""",
    )
    stale_artifact = (
        project
        / ".local"
        / "guard"
        / "artifacts"
        / "minimal-sample"
        / subject_hash
        / "completion-note.json"
    )
    stale_artifact.parent.mkdir(parents=True, exist_ok=True)
    stale_artifact.write_text(
        json.dumps({"value": "旧说明", "updated_at": "2000-01-01T00:00:00Z"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    old_epoch = 946684800
    os.utime(stale_artifact, (old_epoch, old_epoch))
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "decision: guard_failed" in result.stdout
    assert 'missing_artifacts: ["completion_note"]' in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1


def test_state_completed_rejects_unversioned_artifact_when_reuse_policy_defaults_deny(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_project_artifacts(
        project,
        """
artifacts:
  - id: completion_note
    type: note
    owner: guard
    required_for:
      - close_after_note
    path: .local/guard/artifacts/{guard_profile_id}/{subject_key_hash}/completion-note.json
    description: 未声明新鲜度的完成说明。
""",
    )
    path = project / ".local" / "guard" / "artifacts" / "minimal-sample" / subject_hash / "completion-note.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"value": "旧说明"}, ensure_ascii=False), encoding="utf-8")
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "missing_artifacts:" in result.stdout
    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1


def test_state_completed_event_requires_current_completed_state_id(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    event_path = write_event(tmp_path / "event.json", state_completed_event(completed_state_id="wrong_state"))

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "decision: failed" in result.stdout
    assert "reason: completed_state_mismatch" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "error"
    assert audit["detail"]["reason"] == "completed_state_mismatch"
    assert audit["detail"]["completed_state_id"] == "wrong_state"
    assert audit["detail"]["current_state"] == "open"


def test_hook_state_completed_event_does_not_advance_state(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
    event_path = write_event(
        tmp_path / "event.json",
        state_completed_event(
            source="codex",
            hook={"source": "codex", "trigger_event": "PostToolUse", "binding_id": "bad-binding"},
        ),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "decision: failed" in result.stdout
    assert "reason: hook_state_completed_forbidden" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1


def test_state_completed_without_matching_transition_returns_state_machine_error(tmp_path: Path) -> None:
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
  - id: close_route_a
    from: open
    to: closed
    on_event: state_completed
    conditions:
      - field: payload.route
        equals: a
    guard_points:
      - completion_note_present
""",
    )
    event_path = write_event(tmp_path / "event.json", state_completed_event(payload={"route": "b"}))

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "decision: failed" in result.stdout
    assert "reason: invalid_state_machine_transition" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1


def test_state_completed_on_terminal_state_returns_error(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
    first_event = write_event(tmp_path / "first-event.json", state_completed_event())
    first = run_runtime(project, ["run", "--event", str(first_event)])
    assert first.returncode == 0, first.stdout + first.stderr

    second_event = write_event(
        tmp_path / "second-event.json",
        state_completed_event(event_id="event-2", completed_state_id="closed"),
    )

    result = run_runtime(project, ["run", "--event", str(second_event)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "decision: failed" in result.stdout
    assert "reason: terminal_state_completed" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["state_version"] == 2


def test_guard_point_failure_returns_error_and_reports_fix(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求事件已经人工批准。
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
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
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
    assert audit["status"] == "error"
    assert audit["raw_event_path"] == str(audit_path.parent / "raw-event.json")
    assert raw_event["event_id"] == "event-1"
    assert audit["detail"]["current_state"] == "open"
    assert audit["detail"]["failed_guard_points"] == ["completion_note_present"]


def test_guard_point_failure_holds_state_and_writes_audit(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 失败时只写审计并保持状态。
    checks:
      - id: approval_flag_true
        type: event_field
        field: payload.approved
        equals: true
        failure_reason: 事件缺少人工批准标记。
        fix_hint: 在事件 payload.approved 写入 true。
""",
    )
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "decision: guard_failed" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "error"
    assert audit["detail"]["decision"] == "guard_failed"
    assert "state_change" not in audit["detail"]


def test_guard_point_failure_does_not_advance_state(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 失败时不推进状态。
    checks:
      - id: approval_flag_true
        type: event_field
        field: payload.approved
        equals: true
        failure_reason: 事件缺少人工批准标记。
        fix_hint: 在事件 payload.approved 写入 true。
""",
    )
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "decision: guard_failed" in result.stdout
    assert "state: open" in result.stdout
    assert "state_version: 1" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1


def test_transition_failure_holds_state_without_extra_mode_configuration(tmp_path: Path) -> None:
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
    on_event: state_completed
    guard_points:
      - completion_note_present
""",
    )
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 失败配置为不推进。
    checks:
      - id: approval_flag_true
        type: event_field
        field: payload.approved
        equals: true
        failure_reason: 事件缺少人工批准标记。
        fix_hint: 在事件 payload.approved 写入 true。
""",
    )
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
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
    write_completion_note(project, subject_hash)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求事件已经人工批准。
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
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: guard_passed" in result.stdout
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
    write_completion_note(project, subject_hash)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求事件已经人工批准。
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
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout

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
    write_completion_note(project, subject_hash)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求事件已经人工批准。
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
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout

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
    write_completion_note(project, subject_hash)
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求状态、产物新鲜度和人工确认都通过。
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
    write_confirmation_record(
        project,
        subject_hash,
        "close-approved",
        {
            "guard_profile_id": "minimal-sample",
            "subject_key_hash": subject_hash,
            "guard_point_id": "completion_note_present",
            "confirmed": True,
            "expires_at": "2999-01-01T00:00:00Z",
            "reason": "允许关闭。",
        },
    )
    event = state_completed_event(timestamp="2026-06-12T00:05:00Z", payload={})
    event_path = write_event(tmp_path / "event.json", event)

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: guard_passed" in result.stdout
    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["state_version"] == 2


def test_matching_event_advances_state_and_writes_audit(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: guard_passed" in result.stdout
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
    assert audit["detail"]["decision"] == "guard_passed"
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
    assert "reason: non_state_completed_event" in result.stdout
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
        state_completed_event(context={"repo": "repo-a", "worktree": "main"}),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: no_subject_match" in result.stdout
    assert "reason: missing_required_fields" in result.stdout
    assert "context.session_id" in result.stdout
    assert "fix_suggestions:" in result.stdout

    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "no_subject_match"
    assert audit["detail"]["reason"] == "missing_required_fields"
    assert audit["detail"]["missing_fields"] == ["context.session_id"]
    assert audit["detail"]["fix_suggestions"]


def test_hook_event_missing_subject_field_is_ignored_without_audit(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    event_path = write_event(
        tmp_path / "hook-event.json",
        tool_event(
            "Bash",
            context={"repo": "repo-a", "worktree": "main"},
            payload={"command": "git status"},
            hook={"source": "codex", "event": "PreToolUse"},
        ),
    )
    runs_root = project / ".local" / "guard" / "runs" / "minimal-sample"

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: ignored" in result.stdout
    assert "reason: no_guard_instance" in result.stdout
    assert "audit_path:" not in result.stdout
    assert not runs_root.exists()


def test_hook_event_without_matching_instance_is_ignored_without_audit(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    event_path = write_event(
        tmp_path / "hook-event.json",
        tool_event(
            "Bash",
            payload={"command": "git status"},
            hook={"source": "codex", "event": "PreToolUse"},
        ),
    )
    runs_root = project / ".local" / "guard" / "runs" / "minimal-sample"

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: ignored" in result.stdout
    assert "reason: no_guard_instance" in result.stdout
    assert "audit_path:" not in result.stdout
    assert not runs_root.exists()


def test_event_with_multiple_matching_instances_returns_ambiguous_subject(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    state_root = project / ".local" / "guard" / "state" / "minimal-sample"
    shutil.copytree(state_root / subject_hash, state_root / "duplicate-candidate")
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: ambiguous_subject" in result.stdout
    assert "candidate_count: 2" in result.stdout
    assert "fix_suggestions:" in result.stdout

    state = json.loads((state_root / subject_hash / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1
    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "ambiguous_subject"
    assert len(audit["detail"]["candidate_state_paths"]) == 2
    assert audit["detail"]["fix_suggestions"]


def test_hook_event_with_multiple_matching_instances_is_ignored_without_audit(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    state_root = project / ".local" / "guard" / "state" / "minimal-sample"
    shutil.copytree(state_root / subject_hash, state_root / "duplicate-candidate")
    runs_root = project / ".local" / "guard" / "runs" / "minimal-sample"
    before_runs = sorted(path.name for path in runs_root.iterdir())
    event_path = write_event(
        tmp_path / "hook-event.json",
        tool_event(
            "Bash",
            payload={"command": "git status"},
            hook={"source": "codex", "event": "PreToolUse"},
        ),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: ignored" in result.stdout
    assert "reason: no_guard_instance" in result.stdout
    assert "audit_path:" not in result.stdout
    assert sorted(path.name for path in runs_root.iterdir()) == before_runs


def test_multiple_matching_transitions_return_ambiguous_transition_without_state_change(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
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
    on_event: state_completed
    guard_points:
      - completion_note_present
    required_artifacts:
      - completion_note
  - id: duplicate_close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
    required_artifacts:
      - completion_note
""".lstrip(),
        encoding="utf-8",
    )
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "decision: failed" in result.stdout
    assert "reason: ambiguous_transition" in result.stdout
    assert "transition_count: 2" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1
    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "error"
    assert audit["detail"]["decision"] == "failed"
    assert audit["detail"]["reason"] == "ambiguous_transition"
    assert audit["detail"]["matching_transitions"] == ["close_after_note", "duplicate_close_after_note"]


def test_multiple_candidate_transitions_with_no_passing_candidate_return_invalid_transition(tmp_path: Path) -> None:
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
    on_event: state_completed
    guard_points:
      - completion_note_present
    required_artifacts:
      - completion_note
  - id: duplicate_close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
    required_artifacts:
      - completion_note
""".lstrip(),
        encoding="utf-8",
    )
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: error" in result.stdout
    assert "decision: failed" in result.stdout
    assert "reason: invalid_state_machine_transition" in result.stdout
    assert "transition_count: 0" in result.stdout

    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
    assert state["state_version"] == 1
    audit_path = Path(output_value(result.stdout, "audit_path"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "error"
    assert audit["detail"]["reason"] == "invalid_state_machine_transition"
    assert audit["detail"]["matching_transitions"] == []


def test_transition_conditions_use_envelope_fields_to_select_transition(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
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
    on_event: state_completed
    conditions:
      - field: context.session_id
        equals: other-session
    guard_points:
      - completion_note_present
  - id: close_route_b
    from: open
    to: closed_b
    on_event: state_completed
    conditions:
      - field: context.session_id
        equals: session-1
    guard_points:
      - completion_note_present
""".lstrip(),
        encoding="utf-8",
    )
    event_path = write_event(
        tmp_path / "event.json",
        state_completed_event(payload={}),
    )

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "transition_id: close_route_b" in result.stdout
    assert "to_state: closed_b" in result.stdout
    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed_b"


def test_required_artifacts_can_select_one_state_completed_transition(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    write_project_artifacts(
        project,
        """
artifacts:
  - id: note_a
    type: note
    owner: guard
    path: .local/guard/artifacts/{guard_profile_id}/{subject_key_hash}/{state_version}/note-a.json
    freshness:
      scope: current_state_entry
    reuse_policy: deny
  - id: note_b
    type: note
    owner: guard
    path: .local/guard/artifacts/{guard_profile_id}/{subject_key_hash}/{state_version}/note-b.json
    freshness:
      scope: current_state_entry
    reuse_policy: deny
""",
    )
    write_project_guard_points(
        project,
        """
guard_points:
  - id: note_a_present
    checks:
      - id: note_a_exists
        type: artifact_exists
        artifact: note_a
  - id: note_b_present
    checks:
      - id: note_b_exists
        type: artifact_exists
        artifact: note_b
""",
    )
    write_project_state_machine(
        project,
        """
initial_state: open
terminal_states:
  - closed_a
  - closed_b
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
  - id: closed_a
    description: 通过 A 产物关闭。
  - id: closed_b
    description: 通过 B 产物关闭。
transitions:
  - id: close_route_a
    from: open
    to: closed_a
    on_event: state_completed
    guard_points:
      - note_a_present
    required_artifacts:
      - note_a
  - id: close_route_b
    from: open
    to: closed_b
    on_event: state_completed
    guard_points:
      - note_b_present
    required_artifacts:
      - note_b
""",
    )
    note_b = project / ".local" / "guard" / "artifacts" / "minimal-sample" / subject_hash / "1" / "note-b.json"
    note_b.parent.mkdir(parents=True, exist_ok=True)
    note_b.write_text(json.dumps({"value": "B", "updated_at": "2026-06-12T00:00:00Z"}), encoding="utf-8")
    event_path = write_event(tmp_path / "event.json", state_completed_event())

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
    event_path = write_event(tmp_path / "event.json", state_completed_event())

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
    subject_hash = activate_minimal(project)
    write_completion_note(project, subject_hash)
    event_path = write_event(tmp_path / "event.json", state_completed_event())

    result = run_skill_event(project, event_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: allow" in result.stdout
    assert "decision: guard_passed" in result.stdout
