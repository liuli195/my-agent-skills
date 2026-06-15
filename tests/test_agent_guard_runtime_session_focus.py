import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
HOOK_ROUTER = PLUGIN_ROOT / "scripts" / "hook_router.py"
RUNTIME_CLI = PLUGIN_ROOT / "scripts" / "guard_runtime" / "cli.py"
ACTIVATE_GUARD = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "activate_guard.py"
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


def output_json(stdout: str) -> dict:
    return json.loads(stdout)


def write_profile(project: Path) -> Path:
    profile_dir = project / ".agents" / "guards" / "minimal-sample"
    shutil.copytree(MINIMAL_PROFILE, profile_dir)
    return profile_dir


def session_start(project: Path, user_home: Path, session_id: str = "session-1", source: str = "codex") -> dict:
    payload_path = project / f"{source}-session-start.json"
    result = run_hook(
        [
            "--source",
            source,
            "--event",
            "SessionStart",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--payload-file",
            str(payload_path),
        ],
        {"session_id": session_id, "cwd": str(project), "transcript_path": "transcript.jsonl"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return output_json(result.stdout)


def activate_new(project: Path, user_home: Path, title: str = "样例实例", scope: str = "project") -> dict:
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
            "--scope",
            scope,
            "--profile",
            "minimal-sample",
            "--create",
            "--title",
            title,
            "--description",
            "测试 Session Focus Binding。",
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return output_json(result.stdout)


def run_activate_guard(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ACTIVATE_GUARD), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_hook_adapter_converts_codex_and_claude_lifecycle_payloads(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    cases = [
        ("codex", "SessionStart", {"session_id": "codex-s1", "cwd": str(project)}, "lifecycle.session_start"),
        (
            "codex",
            "PreToolUse",
            {"session_id": "codex-s1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "git status"}},
            "lifecycle.pre_tool_use",
        ),
        ("claude", "SessionStart", {"session_id": "claude-s1", "cwd": str(project)}, "lifecycle.session_start"),
        (
            "claude",
            "PreToolUse",
            {"session_id": "claude-s1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "git status"}},
            "lifecycle.pre_tool_use",
        ),
    ]

    for source, event, payload, expected_event_type in cases:
        payload_path = tmp_path / f"{source}-{event}.json"
        result = run_hook(
            [
                "--source",
                source,
                "--event",
                event,
                "--project",
                str(project),
                "--user-home",
                str(tmp_path / "user-home"),
                "--payload-file",
                str(payload_path),
                "--print-envelope",
            ],
            payload,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        envelope = output_json(result.stdout)
        assert envelope["source"] == source
        assert envelope["event_type"] == expected_event_type
        assert envelope["context"]["session_id"] == payload["session_id"]
        assert envelope["context"]["cwd"] == str(project)
        assert "guard_profile_id" not in envelope
        assert "profile_id" not in envelope
        if event == "PreToolUse":
            assert envelope["payload"]["tool"]["name"] == "Bash"
            assert envelope["payload"]["tool_input"]["command"] == "git status"


def test_session_start_writes_observation_and_missing_observation_blocks_activation(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    write_profile(project)

    result = session_start(project, user_home)

    assert result["status"] == "observed"
    observation_path = project / ".local" / "guard" / "session-observations" / "codex" / "session-1.json"
    assert observation_path.exists()
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    assert observation["source"] == "codex"
    assert observation["session_id"] == "session-1"
    assert observation["cwd"] == str(project)

    missing = run_cli(
        [
            "activate",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            "codex",
            "--session-id",
            "missing-session",
            "--profile",
            "minimal-sample",
            "--create",
            "--title",
            "不会创建",
            "--description",
            "缺少 observation。",
        ]
    )

    assert missing.returncode == 1
    body = output_json(missing.stdout)
    assert body["status"] == "session_observation_missing"
    assert "activate 前确认 Plugin Hook" in body["next"]


def test_activate_creates_opaque_instance_and_session_focus_binding(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    write_profile(project)
    session_start(project, user_home)

    body = activate_new(project, user_home)

    assert body["status"] == "session_focus_bound"
    assert body["resolution"] == "created"
    assert "| 序号 | 作用域 | 守卫目标 | 类型 | 来源 | 边界 | 画像 ID |" in body["target_table"]
    assert "| 选项 | 动作 |" in body["instance_table"]
    instance_id = body["instance_id"]
    assert instance_id.startswith("agi_")
    assert "minimal" not in instance_id

    binding_path = project / ".local" / "guard" / "session-focus" / "codex" / "session-1.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    assert binding == {
        "source": "codex",
        "session_id": "session-1",
        "scope": "project",
        "profile_id": "minimal-sample",
        "instance_id": instance_id,
        "bound_at": binding["bound_at"],
    }
    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["instance_id"] == instance_id
    assert state["profile_id"] == "minimal-sample"
    assert state["status"] == "active"
    assert state["current_state"] == "open"
    audit = json.loads(Path(body["audit_path"]).read_text(encoding="utf-8"))
    assert audit["status"] == "allow"
    assert audit["reason"] == "session_focus_changed"
    assert audit["detail"]["scope"] == "project"


def test_activate_can_write_user_scope_focus_binding(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    shutil.copytree(MINIMAL_PROFILE, user_home / ".agents" / "guards" / "minimal-sample")
    session_start(project, user_home)

    body = activate_new(project, user_home, scope="user")

    binding_path = user_home / ".agents" / "guard" / "session-focus" / "codex" / "session-1.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    assert binding["scope"] == "user"
    assert binding["instance_id"] == body["instance_id"]
    assert not (project / ".local" / "guard" / "session-focus" / "codex" / "session-1.json").exists()
    state_path = user_home / ".agents" / "guard" / "state" / "minimal-sample" / body["instance_id"] / "state.json"
    brief_path = user_home / ".agents" / "guard" / "latest" / "minimal-sample" / body["instance_id"] / "brief.json"
    assert state_path.exists()
    assert brief_path.exists()
    audit = json.loads(Path(body["audit_path"]).read_text(encoding="utf-8"))
    assert str(body["audit_path"]).startswith(str(user_home / ".agents" / "guard" / "audit"))
    assert audit["reason"] == "session_focus_changed"
    assert audit["detail"]["scope"] == "user"


def test_activate_wrapper_does_not_create_without_explicit_create_or_selection(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    write_profile(project)
    session_start(project, user_home)

    result = run_activate_guard(
        [
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

    assert result.returncode == 1, result.stdout + result.stderr
    body = output_json(result.stdout)
    assert body["status"] == "selection_required"
    assert "| 选项 | 动作 |" in body["instance_table"]
    assert not (project / ".local" / "guard" / "state").exists()


def test_activate_can_switch_and_close_instances_without_closing_previous_focus(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    write_profile(project)
    session_start(project, user_home)
    first = activate_new(project, user_home, "第一个实例")
    second = activate_new(project, user_home, "第二个实例")

    select = run_cli(
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
            "--scope",
            "project",
            "--profile",
            "minimal-sample",
            "--select-instance",
            first["instance_id"],
        ]
    )
    assert select.returncode == 0, select.stdout + select.stderr
    assert output_json(select.stdout)["resolution"] == "selected"

    state_root = project / ".local" / "guard" / "state" / "minimal-sample"
    first_state = json.loads((state_root / first["instance_id"] / "state.json").read_text(encoding="utf-8"))
    second_state = json.loads((state_root / second["instance_id"] / "state.json").read_text(encoding="utf-8"))
    assert first_state["status"] == "active"
    assert second_state["status"] == "active"

    close = run_cli(
        [
            "close-instance",
            "--project",
            str(project),
            "--profile",
            "minimal-sample",
            "--instance-id",
            first["instance_id"],
        ]
    )

    assert close.returncode == 0, close.stdout + close.stderr
    assert output_json(close.stdout)["status"] == "instance_closed"
    first_state = json.loads((state_root / first["instance_id"] / "state.json").read_text(encoding="utf-8"))
    second_state = json.loads((state_root / second["instance_id"] / "state.json").read_text(encoding="utf-8"))
    assert first_state["status"] == "closed"
    assert second_state["status"] == "active"
