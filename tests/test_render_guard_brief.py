import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PROJECT_GUARD = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "init_project_guard.py"
RENDER_GUARD_BRIEF = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "render_guard_brief.py"
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


def run_skill_brief(project: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RENDER_GUARD_BRIEF), "--project", str(project), *args],
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


def write_project_guard_points(project: Path, yaml_text: str) -> None:
    path = project / ".agents" / "guards" / "minimal-sample" / "guard-points.yaml"
    path.write_text(yaml_text.lstrip(), encoding="utf-8")


def write_project_execution_model(project: Path, yaml_text: str) -> None:
    path = project / ".agents" / "guards" / "minimal-sample" / "execution-model.yaml"
    path.write_text(yaml_text.lstrip(), encoding="utf-8")


def test_activation_generates_initial_latest_guard_brief(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)

    subject_hash = activate_minimal(project)

    latest = project / ".local" / "guard" / "latest" / "minimal-sample" / subject_hash
    latest_json = latest / "brief.json"
    latest_text = latest / "brief.md"
    assert latest_json.exists()
    assert latest_text.exists()

    payload = json.loads(latest_json.read_text(encoding="utf-8"))
    assert payload["guard_profile_id"] == "minimal-sample"
    assert payload["subject_key_hash"] == subject_hash
    assert payload["state"] == "open"
    assert payload["state_version"] == 1
    assert payload["allowed_next"] == ["close"]
    assert payload["forbidden_next"] == []
    assert payload["missing_artifacts"] == ["completion_note"]
    assert payload["source"] == "guard-runtime"
    assert payload["expires_at"]
    assert payload["brief_hash"]
    assert Path(payload["audit_path"]).exists()
    assert "当前状态：open" in payload["brief_text"]
    assert "允许下一步：close" in payload["brief_text"]
    assert "缺失 Artifacts（产物）：completion_note" in payload["brief_text"]

    result = run_runtime(
        project,
        ["brief", "--profile", "minimal-sample", "--subject", subject_hash, "--format", "json"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    read_payload = json.loads(result.stdout)
    assert read_payload["status"] == "ok"
    assert read_payload["brief_hash"] == payload["brief_hash"]


def test_state_change_updates_latest_guard_brief_and_hash(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    latest_json = project / ".local" / "guard" / "latest" / "minimal-sample" / subject_hash / "brief.json"
    initial = json.loads(latest_json.read_text(encoding="utf-8"))
    event_path = write_event(tmp_path / "event.json", minimal_close_event())

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 0, result.stdout + result.stderr
    updated = json.loads(latest_json.read_text(encoding="utf-8"))
    assert updated["state"] == "closed"
    assert updated["state_version"] == 2
    assert updated["missing_artifacts"] == []
    assert updated["brief_hash"] != initial["brief_hash"]
    assert "当前状态：closed" in updated["brief_text"]
    assert "缺失 Artifacts（产物）：[]" in updated["brief_text"]


def test_missing_artifact_block_updates_latest_guard_brief_without_state_change(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    write_project_execution_model(
        project,
        """
nodes:
  - id: activate
    type: activation
    required_artifacts: []
    completion_signals:
      - guard.activation
  - id: close
    type: closure
    required_artifacts:
      - completion_note
    completion_signals:
      - guard.close
states:
  - id: open
    allowed_next:
      - close
    forbidden_next: []
    missing_artifacts: []
    brief:
      current_state: open
      next_step: 发出 guard.close。
  - id: closed
    allowed_next: []
    forbidden_next: []
    missing_artifacts: []
    brief:
      current_state: closed
      next_step: 不需要更多被守卫动作。
""",
    )
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求样例 completion_note（完成说明）存在。
    trigger:
      events:
        - guard.close
    mode: block
    required_artifacts:
      - completion_note
    checks:
      - id: completion_note_exists
        type: artifact_exists
        artifact: completion_note
        failure_reason: 缺少 completion_note（完成说明）。
        fix_hint: 在事件 payload.artifacts 或 payload.artifact_ids 中提供 completion_note。
    failure_reason: 关闭前缺少必需完成说明。
    fix_hint: 提供 completion_note 后重试 guard.close。
""",
    )
    subject_hash = activate_minimal(project)
    latest_json = project / ".local" / "guard" / "latest" / "minimal-sample" / subject_hash / "brief.json"
    initial = json.loads(latest_json.read_text(encoding="utf-8"))
    assert initial["missing_artifacts"] == []
    event_path = write_event(tmp_path / "event.json", minimal_close_event(payload={}))

    result = run_runtime(project, ["run", "--event", str(event_path)])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "status: block" in result.stdout
    updated = json.loads(latest_json.read_text(encoding="utf-8"))
    assert updated["state"] == "open"
    assert updated["state_version"] == 1
    assert updated["missing_artifacts"] == ["completion_note"]
    assert updated["brief_hash"] != initial["brief_hash"]
    assert "brief_path:" in result.stdout


def test_same_brief_hash_is_not_injected_twice_for_session(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)

    first = run_runtime(
        project,
        [
            "brief",
            "--profile",
            "minimal-sample",
            "--subject",
            subject_hash,
            "--session",
            "codex-session-1",
            "--format",
            "json",
        ],
    )
    second = run_runtime(
        project,
        [
            "brief",
            "--profile",
            "minimal-sample",
            "--subject",
            subject_hash,
            "--session",
            "codex-session-1",
            "--format",
            "json",
        ],
    )

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)
    assert first_payload["status"] == "injectable"
    assert first_payload["already_injected"] is False
    assert second_payload["status"] == "already_injected"
    assert second_payload["already_injected"] is True
    assert second_payload["brief_hash"] == first_payload["brief_hash"]

    injection_path = Path(first_payload["injection_record_path"])
    record = json.loads(injection_path.read_text(encoding="utf-8"))
    assert record["brief_hashes"] == [first_payload["brief_hash"]]
    assert len(record["records"]) == 1


def test_brief_injection_rejects_subject_mismatch(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    latest_json = project / ".local" / "guard" / "latest" / "minimal-sample" / subject_hash / "brief.json"
    payload = json.loads(latest_json.read_text(encoding="utf-8"))
    payload["subject_key_hash"] = "wrong-subject"
    latest_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = run_runtime(
        project,
        ["brief", "--profile", "minimal-sample", "--subject", subject_hash, "--session", "codex-session-1"],
    )

    assert result.returncode == 1, result.stdout + result.stderr
    body = json.loads(result.stdout)
    assert body["status"] == "stale_brief"
    assert body["reason"] == "subject_mismatch"


def test_brief_injection_rejects_state_version_mismatch(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["state_version"] = 2
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = run_runtime(
        project,
        ["brief", "--profile", "minimal-sample", "--subject", subject_hash, "--session", "codex-session-1"],
    )

    assert result.returncode == 1, result.stdout + result.stderr
    body = json.loads(result.stdout)
    assert body["status"] == "stale_brief"
    assert body["reason"] == "state_version_mismatch"
    assert body["brief_state_version"] == 1
    assert body["current_state_version"] == 2


def test_brief_injection_rejects_expired_brief(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    latest_json = project / ".local" / "guard" / "latest" / "minimal-sample" / subject_hash / "brief.json"
    payload = json.loads(latest_json.read_text(encoding="utf-8"))
    payload["expires_at"] = "2000-01-01T00:00:00Z"
    latest_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = run_runtime(
        project,
        ["brief", "--profile", "minimal-sample", "--subject", subject_hash, "--session", "codex-session-1"],
    )

    assert result.returncode == 1, result.stdout + result.stderr
    body = json.loads(result.stdout)
    assert body["status"] == "expired_brief"
    assert body["reason"] == "expires_at_elapsed"


def test_no_subject_match_does_not_generate_injectable_brief(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)

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
            json.dumps({"repo": "repo-a", "worktree": "main"}),
        ],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: no_subject_match" in result.stdout
    assert not (project / ".local" / "guard" / "latest" / "minimal-sample").exists()


def test_block_reason_updates_latest_guard_brief_without_state_change(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)
    latest_json = project / ".local" / "guard" / "latest" / "minimal-sample" / subject_hash / "brief.json"
    initial = json.loads(latest_json.read_text(encoding="utf-8"))
    write_project_guard_points(
        project,
        """
guard_points:
  - id: completion_note_present
    description: 关闭前要求事件已经人工批准。
    mode: block
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
    updated = json.loads(latest_json.read_text(encoding="utf-8"))
    assert updated["state"] == "open"
    assert updated["state_version"] == 1
    assert updated["missing_artifacts"] == []
    assert updated["recent_block_reasons"] == ["事件缺少人工批准标记。"]
    assert updated["brief_hash"] != initial["brief_hash"]
    assert "最近阻断原因：事件缺少人工批准标记。" in updated["brief_text"]


def test_skill_render_guard_brief_command_delegates_to_project_runtime(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    subject_hash = activate_minimal(project)

    result = run_skill_brief(project, ["--profile", "minimal-sample", "--subject", subject_hash, "--format", "json"])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["guard_profile_id"] == "minimal-sample"
    assert payload["subject_key_hash"] == subject_hash
