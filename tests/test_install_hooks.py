import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PROJECT_GUARD = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "init_project_guard.py"
INSTALL_HOOKS = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "install_hooks.py"
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
CODEX_HOOKS_TEMPLATE = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "agent-guard"
    / "assets"
    / "templates"
    / "codex-hooks"
    / "hooks.json"
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


def run_install(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALL_HOOKS), *args],
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


def adapter(project: Path) -> Path:
    return project / ".agents" / "guard-runtime" / "hook_event_adapter.py"


def runtime(project: Path) -> Path:
    return project / ".agents" / "guard-runtime" / "guard_runner.py"


def test_codex_hook_template_does_not_enable_blocking_by_default() -> None:
    assert "--blocking" not in CODEX_HOOKS_TEMPLATE.read_text(encoding="utf-8")


def test_install_hooks_defaults_to_dry_run_without_writing_hooks(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)

    result = run_install(["--project", str(project), "--profile", "minimal-sample"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "authorization: missing" in result.stdout
    assert "target: .codex/hooks.json" in result.stdout
    assert "target: .githooks/pre-push" in result.stdout
    assert "rollback:" in result.stdout
    assert not (project / ".codex" / "hooks.json").exists()
    assert not (project / ".githooks" / "pre-push").exists()
    assert not adapter(project).exists()


def test_authorized_install_writes_hook_entries_and_verify_confirms_them(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    git_init = subprocess.run(
        ["git", "init"],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert git_init.returncode == 0, git_init.stdout + git_init.stderr

    install = run_install(["--project", str(project), "--profile", "minimal-sample", "--authorize-install"])

    assert install.returncode == 0, install.stdout + install.stderr
    assert "status: installed" in install.stdout
    assert adapter(project).exists()
    assert (project / ".githooks" / "pre-push").exists()
    hooks = json.loads((project / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    for event_name in ["UserPromptSubmit", "SubagentStart", "SubagentStop", "PreToolUse", "PostToolUse"]:
        command = hooks["hooks"][event_name][0]["hooks"][0]["command"]
        assert "hook_event_adapter.py" in command
        assert "--profile minimal-sample" in command
        assert "--blocking" not in command
        assert "review" not in command.lower()
    hooks_path = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert hooks_path.stdout.strip() == ".githooks"

    verify = run_install(["--project", str(project), "--profile", "minimal-sample", "--verify"])

    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "status: verified" in verify.stdout
    assert "codex_hook: present" in verify.stdout
    assert "git_pre_push: present" in verify.stdout
    assert "git_hooks_path: .githooks" in verify.stdout


def test_codex_hook_adapter_prints_standard_event_envelope(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    install = run_install(["--project", str(project), "--profile", "minimal-sample", "--authorize-install"])
    assert install.returncode == 0, install.stdout + install.stderr
    payload = tmp_path / "codex-payload.json"
    payload.write_text(
        json.dumps(
            {
                "session_id": "session-1",
                "context": {"pr_number": "17", "task_id": "task-a"},
                "prompt": "请执行当前任务",
                "tool_name": "Write",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(adapter(project)),
            "codex",
            "--project",
            str(project),
            "--profile",
            "minimal-sample",
            "--codex-event",
            "UserPromptSubmit",
            "--payload-file",
            str(payload),
            "--print-envelope",
        ],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["guard_profile_id"] == "minimal-sample"
    assert envelope["source"] == "codex"
    assert envelope["event_type"] == "codex.user_prompt_submit"
    assert envelope["context"]["session_id"] == "session-1"
    assert envelope["context"]["pr_number"] == "17"
    assert envelope["context"]["task_id"] == "task-a"
    assert envelope["context"]["worktree"] == str(project.resolve())
    assert envelope["payload"]["prompt"] == "请执行当前任务"
    assert envelope["hook"]["trigger_event"] == "UserPromptSubmit"


def test_codex_hook_adapter_does_not_persist_auto_event_file(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    install = run_install(["--project", str(project), "--profile", "minimal-sample", "--authorize-install"])
    assert install.returncode == 0, install.stdout + install.stderr

    activation = subprocess.run(
        [
            sys.executable,
            str(runtime(project)),
            "activate",
            "--profile",
            "minimal-sample",
            "--scope",
            "current_context",
            "--source",
            "agent-guard-skill",
            "--context-json",
            json.dumps({"session_id": "session-1", "repo": "", "worktree": str(project.resolve())}),
        ],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert activation.returncode == 0, activation.stdout + activation.stderr

    payload = tmp_path / "codex-payload.json"
    payload.write_text(json.dumps({"session_id": "session-1"}, ensure_ascii=False), encoding="utf-8")
    events_root = project / ".local" / "guard" / "events" / "minimal-sample"

    result = subprocess.run(
        [
            sys.executable,
            str(adapter(project)),
            "codex",
            "--project",
            str(project),
            "--profile",
            "minimal-sample",
            "--codex-event",
            "UserPromptSubmit",
            "--payload-file",
            str(payload),
        ],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "decision: ignored" in result.stdout
    assert "reason: no_matching_transition" in result.stdout
    assert not events_root.exists()
    assert not list(events_root.glob("*.json"))


def test_codex_hook_adapter_preserves_explicit_out_file(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    install = run_install(["--project", str(project), "--profile", "minimal-sample", "--authorize-install"])
    assert install.returncode == 0, install.stdout + install.stderr

    payload = tmp_path / "codex-payload.json"
    out = tmp_path / "event-out.json"
    payload.write_text(json.dumps({"session_id": "session-1"}, ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(adapter(project)),
            "codex",
            "--project",
            str(project),
            "--profile",
            "minimal-sample",
            "--codex-event",
            "UserPromptSubmit",
            "--payload-file",
            str(payload),
            "--out",
            str(out),
        ],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert out.exists()
    envelope = json.loads(out.read_text(encoding="utf-8"))
    assert envelope["guard_profile_id"] == "minimal-sample"
    assert envelope["hook"]["trigger_event"] == "UserPromptSubmit"


def test_git_pre_push_adapter_prints_standard_event_envelope(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    install = run_install(["--project", str(project), "--profile", "minimal-sample", "--authorize-install"])
    assert install.returncode == 0, install.stdout + install.stderr

    result = subprocess.run(
        [
            sys.executable,
            str(adapter(project)),
            "git-pre-push",
            "--project",
            str(project),
            "--profile",
            "minimal-sample",
            "--remote-name",
            "origin",
            "--remote-url",
            "https://example.test/repo.git",
            "--print-envelope",
        ],
        cwd=project,
        input="refs/heads/main abc123 refs/heads/main def456\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["guard_profile_id"] == "minimal-sample"
    assert envelope["source"] == "git"
    assert envelope["event_type"] == "git.pre_push"
    assert envelope["context"]["worktree"] == str(project.resolve())
    assert envelope["tool"] == {"name": "git"}
    assert envelope["action"] == {"name": "pre_push", "blocking": False}
    assert envelope["payload"]["git"]["remote_name"] == "origin"
    assert envelope["payload"]["git"]["refs"][0]["local_ref"] == "refs/heads/main"


def test_authorized_blocking_install_marks_blocking_hook_entries(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)

    install = run_install(
        [
            "--project",
            str(project),
            "--profile",
            "minimal-sample",
            "--authorize-install",
            "--authorize-blocking",
        ]
    )

    assert install.returncode == 0, install.stdout + install.stderr
    assert "blocking_mode: enabled" in install.stdout
    hooks = json.loads((project / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    assert "--blocking" in hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "--blocking" in hooks["hooks"]["SubagentStart"][0]["hooks"][0]["command"]
    assert "--blocking" not in hooks["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
    assert "--blocking" in (project / ".githooks" / "pre-push").read_text(encoding="utf-8")
