import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
PLUGIN_SKILL = PLUGIN_ROOT / "skills" / "agent-guard"
INSTALLER = PLUGIN_SKILL / "scripts" / "install_agent_guard_plugin.py"
HOOK_ROUTER = PLUGIN_ROOT / "scripts" / "hook_router.py"
RUNTIME_CLI = PLUGIN_ROOT / "scripts" / "guard_runtime" / "cli.py"
MINIMAL_PROFILE = PLUGIN_SKILL / "assets" / "templates" / "guard-profile" / "minimal"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_payload(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def output_json(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def test_plugin_runtime_e2e_from_verify_to_state_completed(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo-marketplace"
    codex_personal = tmp_path / "codex-personal" / ".agents" / "plugins" / "marketplace.json"
    claude_personal = tmp_path / "claude-personal" / ".claude-plugin" / "marketplace.json"
    marketplace_args = [
        "--target",
        "all",
        "--scope",
        "all",
        "--codex-repo-marketplace",
        str(repo_root / ".agents" / "plugins" / "marketplace.json"),
        "--claude-repo-marketplace",
        str(repo_root / ".claude-plugin" / "marketplace.json"),
        "--codex-personal-marketplace",
        str(codex_personal),
        "--claude-personal-marketplace",
        str(claude_personal),
    ]
    install = run(
        [
            str(INSTALLER),
            "install",
            "--plugin-source",
            str(PLUGIN_ROOT),
            *marketplace_args,
            "--authorize-install",
        ]
    )
    assert install.returncode == 0, install.stdout + install.stderr

    verify = run(
        [
            str(INSTALLER),
            "verify",
            "--plugin-source",
            str(PLUGIN_ROOT),
            *marketplace_args,
        ]
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "status: verified" in verify.stdout

    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    profile_dir = project / ".agents" / "guards" / "minimal-sample"
    shutil.copytree(MINIMAL_PROFILE, profile_dir)

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
    assert output_json(session_start)["status"] == "observed"

    activate = run(
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
            "端到端实例",
            "--description",
            "验证 Plugin Runtime 端到端流程。",
        ]
    )
    assert activate.returncode == 0, activate.stdout + activate.stderr
    instance_id = output_json(activate)["instance_id"]

    pre_tool = run(
        [
            str(HOOK_ROUTER),
            "--source",
            "codex",
            "--event",
            "PreToolUse",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--payload-file",
            str(write_payload(project / "pre-tool.json", {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "git status"}})),
        ]
    )
    assert pre_tool.returncode == 0, pre_tool.stdout + pre_tool.stderr
    assert output_json(pre_tool)["status"] == "allow"

    completion_note = project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "1" / "completion-note.json"
    completion_note.parent.mkdir(parents=True, exist_ok=True)
    completion_note.write_text(json.dumps({"value": "done"}, ensure_ascii=False), encoding="utf-8")

    brief = run(
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
    assert brief.returncode == 0, brief.stdout + brief.stderr
    assert output_json(brief)["status"] == "injectable"

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
    assert output_json(completed)["reason"] == "state_completed"

    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["state_version"] == 2
    combined_output = verify.stdout + session_start.stdout + activate.stdout + pre_tool.stdout + brief.stdout + completed.stdout
    assert "subject_key_hash" not in combined_output
    assert "no_subject_match" not in combined_output
    assert "ambiguous_subject" not in combined_output
