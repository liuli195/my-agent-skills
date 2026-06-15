import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
HOOK_ROUTER = PLUGIN_ROOT / "scripts" / "hook_router.py"
RUNTIME_CLI = PLUGIN_ROOT / "scripts" / "guard_runtime" / "cli.py"
RENDER_GUARD_BRIEF = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "render_guard_brief.py"
RUN_GUARD_EVENT = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "run_guard_event.py"
MINIMAL_PROFILE = REPO_ROOT / "skills" / "agent-guard" / "assets" / "templates" / "guard-profile" / "minimal"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def body(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def write_payload(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def setup_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    shutil.copytree(MINIMAL_PROFILE, project / ".agents" / "guards" / "minimal-sample")
    session_start = run(
        [
            str(HOOK_ROUTER),
            "--source",
            "codex",
            "--event",
            "SessionStart",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--payload-file",
            str(write_payload(project / "session-start.json", {"session_id": "session-1", "cwd": str(project)})),
        ]
    )
    assert session_start.returncode == 0, session_start.stdout + session_start.stderr
    return project, user_home


def activate(project: Path, user_home: Path) -> dict:
    result = run(
        [
            str(RUNTIME_CLI),
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
            "简报实例",
            "--description",
            "验证 Session Focus 版 Guard Brief。",
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return body(result)


def run_brief(project: Path, user_home: Path) -> subprocess.CompletedProcess[str]:
    return run(
        [
            str(RUNTIME_CLI),
            "brief",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            "codex",
            "--session-id",
            "session-1",
        ]
    )


def write_completion_note(project: Path, instance_id: str) -> None:
    path = project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "1" / "completion-note.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"value": "done"}, ensure_ascii=False), encoding="utf-8")


def write_state_completed_event(project: Path) -> Path:
    return write_payload(
        project / "state-completed.json",
        {
            "source": "codex",
            "event_type": "state_completed",
            "context": {"session_id": "session-1", "cwd": str(project)},
        },
    )


def test_activation_writes_latest_guard_brief_for_session_focus_instance(tmp_path: Path) -> None:
    project, user_home = setup_project(tmp_path)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]

    brief_path = project / ".local" / "guard" / "latest" / "minimal-sample" / instance_id / "brief.json"
    text_path = project / ".local" / "guard" / "latest" / "minimal-sample" / instance_id / "brief.md"

    assert brief_path.exists()
    assert text_path.exists()
    payload = json.loads(brief_path.read_text(encoding="utf-8"))
    assert payload["profile_id"] == "minimal-sample"
    assert payload["instance_id"] == instance_id
    assert payload["state"] == "open"
    assert payload["state_version"] == 1
    assert payload["brief_hash"]
    assert payload["brief_path"] == str(brief_path)
    assert payload["brief_text_path"] == str(text_path)
    assert "subject_key_hash" not in payload
    assert "completed_state_id" not in payload["brief_text"]
    assert "当前状态：open" in payload["brief_text"]
    assert "状态推进：" in payload["brief_text"]


def test_brief_injection_dedupes_by_session_and_brief_hash(tmp_path: Path) -> None:
    project, user_home = setup_project(tmp_path)
    activated = activate(project, user_home)

    first = run_brief(project, user_home)
    second = run_brief(project, user_home)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    first_body = body(first)
    second_body = body(second)
    assert first_body["status"] == "injectable"
    assert first_body["already_injected"] is False
    assert second_body["status"] == "already_injected"
    assert second_body["already_injected"] is True
    assert second_body["brief_hash"] == first_body["brief_hash"]
    assert first_body["instance_id"] == activated["instance_id"]

    record = json.loads(Path(first_body["injection_record_path"]).read_text(encoding="utf-8"))
    assert record["brief_hashes"] == [first_body["brief_hash"]]
    assert record["session_id"] == "session-1"
    assert record["instance_id"] == activated["instance_id"]


def test_skill_render_guard_brief_delegates_to_plugin_runtime(tmp_path: Path) -> None:
    project, user_home = setup_project(tmp_path)
    activated = activate(project, user_home)

    result = run(
        [
            str(RENDER_GUARD_BRIEF),
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            "codex",
            "--session-id",
            "session-1",
        ]
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "injectable"
    assert payload["instance_id"] == activated["instance_id"]
    assert payload["brief_text"]


def test_state_completed_refreshes_latest_guard_brief(tmp_path: Path) -> None:
    project, user_home = setup_project(tmp_path)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    brief_path = project / ".local" / "guard" / "latest" / "minimal-sample" / instance_id / "brief.json"
    initial = json.loads(brief_path.read_text(encoding="utf-8"))
    write_completion_note(project, instance_id)
    read_brief = run_brief(project, user_home)
    assert read_brief.returncode == 0, read_brief.stdout + read_brief.stderr

    completed = run(
        [
            str(RUNTIME_CLI),
            "state-completed",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            "codex",
            "--session-id",
            "session-1",
        ]
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    updated = json.loads(brief_path.read_text(encoding="utf-8"))
    assert updated["state"] == "closed"
    assert updated["state_version"] == 2
    assert updated["brief_hash"] != initial["brief_hash"]
    assert "completed_state_id" not in updated["brief_text"]


def test_state_completed_requires_current_guard_brief_to_be_read(tmp_path: Path) -> None:
    project, user_home = setup_project(tmp_path)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)

    blocked = run(
        [
            str(RUNTIME_CLI),
            "state-completed",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            "codex",
            "--session-id",
            "session-1",
        ]
    )

    assert blocked.returncode == 1, blocked.stdout + blocked.stderr
    blocked_body = body(blocked)
    assert blocked_body["status"] == "brief_required"
    assert blocked_body["reason"] == "latest_guard_brief_required"
    assert blocked_body["instance_id"] == instance_id
    assert blocked_body["brief_text"]
    assert not (project / ".local" / "guard" / "injections").exists()

    read_brief = run_brief(project, user_home)
    assert read_brief.returncode == 0, read_brief.stdout + read_brief.stderr

    completed = run(
        [
            str(RUNTIME_CLI),
            "state-completed",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            "codex",
            "--session-id",
            "session-1",
        ]
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert body(completed)["reason"] == "state_completed"


def test_run_guard_event_surfaces_brief_required_instead_of_hidden_read_and_advance(tmp_path: Path) -> None:
    project, user_home = setup_project(tmp_path)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    event_path = write_state_completed_event(project)

    blocked = run(
        [
            str(RUN_GUARD_EVENT),
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--event",
            str(event_path),
        ]
    )

    assert blocked.returncode == 1, blocked.stdout + blocked.stderr
    blocked_body = body(blocked)
    assert blocked_body["status"] == "brief_required"
    assert blocked_body["brief_text"]
    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json"
    assert json.loads(state_path.read_text(encoding="utf-8"))["current_state"] == "open"

    read_brief = run_brief(project, user_home)
    assert read_brief.returncode == 0, read_brief.stdout + read_brief.stderr
    completed = run(
        [
            str(RUN_GUARD_EVENT),
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--event",
            str(event_path),
        ]
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert body(completed)["reason"] == "state_completed"
