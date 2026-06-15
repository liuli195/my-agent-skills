import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PROJECT_GUARD = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "init_project_guard.py"
INSTALL_HOOKS = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "install_hooks.py"
PRD = REPO_ROOT / "docs" / "prd" / "agent-guard-prd.md"
HOOK_CONTRACT = REPO_ROOT / "skills" / "agent-guard" / "references" / "hook-contract.md"
MINIMAL_PROFILE = (
    REPO_ROOT
    / "skills"
    / "agent-guard"
    / "assets"
    / "templates"
    / "guard-profile"
    / "minimal"
)
CODEX_HOOKS_TEMPLATE = (
    REPO_ROOT
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


def test_codex_hook_template_has_no_blocking_flag() -> None:
    assert "--blocking" not in CODEX_HOOKS_TEMPLATE.read_text(encoding="utf-8")


def test_docs_distinguish_first_version_hook_scope_from_future_extensions() -> None:
    prd = PRD.read_text(encoding="utf-8")
    hook_contract = HOOK_CONTRACT.read_text(encoding="utf-8")

    assert "MVP 第一版必须支持的 Codex 生命周期事件" in prd
    for event_name in ["UserPromptSubmit", "PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop"]:
        assert f"- `{event_name}`" in prd
    assert "MVP 后续扩展的 Codex 生命周期事件" in prd
    for event_name in ["SessionStart", "PreCompact", "Stop"]:
        assert f"- `{event_name}`" in prd
    assert "MVP 第一版必须支持的 Git hook" in prd
    assert "- `pre-push`" in prd
    assert "MVP 后续扩展的 Git hook" in prd
    assert "- `pre-commit`" in prd

    assert "第一版 adapter（适配器）支持" in hook_contract
    assert "后续扩展" in hook_contract
    assert "SessionStart" in hook_contract
    assert "pre-commit" in hook_contract


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
                "context": {
                    "pr_number": "17",
                    "repo": "repo-a",
                    "repository": "https://user:password@example.test/other.git",
                    "task_id": "task-a",
                    "secret": "不要透传",
                },
                "subject": {"issue": "17", "secret": "不要透传"},
                "prompt": "请执行当前任务",
                "tool": {"name": "Write", "secret": "不要透传"},
                "command": "write-file",
                "args": {"path": "docs/args.md", "secret": "不要透传"},
                "arguments": [{"query": "ok", "secret": "不要透传"}],
                "tool_input": {"path": "docs/plan.md", "pattern": "TODO", "value": "不要透传", "secret": "不要透传"},
                "parameters": {"query": "status", "secret": "不要透传"},
                "secret": "不要透传",
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
    assert envelope["context"]["repo"] == "repo-a"
    assert envelope["context"]["repo_url_hash"]
    assert envelope["context"]["repository"] == "example.test/other.git"
    assert envelope["context"]["repository_host"] == "example.test"
    assert envelope["context"]["repository_path"] == "/other.git"
    assert envelope["context"]["repository_url_hash"]
    assert envelope["context"]["task_id"] == "task-a"
    assert envelope["context"]["worktree"] == str(project.resolve())
    assert "token" not in json.dumps(envelope["context"], ensure_ascii=False)
    assert "secret" not in json.dumps(envelope["context"], ensure_ascii=False)
    assert "secret" not in envelope["context"]
    assert envelope["subject"] == {"issue": "17"}
    assert envelope["payload"] == {
        "args": {"path": "docs/args.md"},
        "arguments": [{"query": "ok"}],
        "command": "write-file",
        "parameters": {"query": "status"},
        "tool_input": {"path": "docs/plan.md", "pattern": "TODO"},
    }
    assert envelope["tool"] == {"name": "Write"}
    assert "secret" not in envelope["payload"]
    assert "secret" not in envelope["payload"]["args"]
    assert "secret" not in envelope["payload"]["arguments"][0]
    assert "secret" not in envelope["payload"]["tool_input"]
    assert "value" not in envelope["payload"]["tool_input"]
    assert "secret" not in envelope["payload"]["parameters"]
    assert envelope["hook"]["trigger_event"] == "UserPromptSubmit"


def test_codex_hook_adapter_never_maps_hook_to_state_completed(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    install = run_install(["--project", str(project), "--profile", "minimal-sample", "--authorize-install"])
    assert install.returncode == 0, install.stdout + install.stderr
    (project / ".agents" / "guards" / "minimal-sample" / "hook-bindings.yaml").write_text(
        """
hook_bindings:
  - id: bad-codex-complete
    source: codex
    trigger_event: PostToolUse
    event_type: state_completed
""".lstrip(),
        encoding="utf-8",
    )
    payload = tmp_path / "codex-payload.json"
    payload.write_text(json.dumps({"session_id": "session-1", "tool_name": "Write"}, ensure_ascii=False), encoding="utf-8")

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
            "PostToolUse",
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
    assert envelope["event_type"] == "codex.post_tool_use"
    assert envelope["hook"]["binding_id"] == "bad-codex-complete"


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
    assert "reason: non_state_completed_event" in result.stdout
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
            "https://token:secret@example.test/repo.git",
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
    assert envelope["subject"] == {}
    assert envelope["tool"] == {"name": "git"}
    assert envelope["action"] == {"name": "pre_push"}
    assert envelope["payload"]["git"]["remote_name"] == "origin"
    assert envelope["payload"]["git"]["remote"] == {
        "host": "example.test",
        "path": "/repo.git",
        "scheme": "https",
        "url_hash": envelope["payload"]["git"]["remote"]["url_hash"],
    }
    assert "token" not in json.dumps(envelope["payload"]["git"]["remote"], ensure_ascii=False)
    assert "secret" not in json.dumps(envelope["payload"]["git"]["remote"], ensure_ascii=False)
    assert "remote_url" not in envelope["payload"]["git"]
    assert envelope["payload"]["git"]["refs"][0]["local_ref"] == "refs/heads/main"


def test_git_pre_push_adapter_hashes_unparseable_remote_url(tmp_path: Path) -> None:
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
            "token-secret-raw-remote",
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
    remote = envelope["payload"]["git"]["remote"]
    assert list(remote.keys()) == ["url_hash"]
    assert "token-secret-raw-remote" not in json.dumps(envelope, ensure_ascii=False)


def test_authorize_blocking_install_argument_is_removed(tmp_path: Path) -> None:
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

    assert install.returncode == 2
    assert "unrecognized arguments: --authorize-blocking" in install.stderr
    assert not (project / ".codex" / "hooks.json").exists()
