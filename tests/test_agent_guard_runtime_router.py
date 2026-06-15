import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
HOOK_ROUTER = PLUGIN_ROOT / "scripts" / "hook_router.py"
RUNTIME_CLI = PLUGIN_ROOT / "scripts" / "guard_runtime" / "cli.py"
MINIMAL_PROFILE = (
    REPO_ROOT
    / "skills"
    / "agent-guard"
    / "assets"
    / "templates"
    / "guard-profile"
    / "minimal"
)


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


def write_completion_note(project: Path, instance_id: str) -> None:
    path = project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "1" / "completion-note.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"value": "完成"}, ensure_ascii=False), encoding="utf-8")


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


def test_invalid_and_multiple_focus_bindings_deny_and_audit(tmp_path: Path) -> None:
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
    assert invalid_body["status"] == "deny"
    assert invalid_body["reason"] == "invalid_session_focus_binding"

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
    assert multiple_body["status"] == "deny"
    assert multiple_body["reason"] == "multiple_session_focus_bindings"


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
