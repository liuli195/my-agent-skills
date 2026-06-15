import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "install_agent_guard_plugin.py"
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd or REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def output_json(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def write_confirmed_research_notes(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
grill_with_docs:
  status: confirmed
  confirmed_decisions:
    - 使用旁路 Guard Profile（守卫画像）记录发布流程顺序。
    - Hook（钩子）只做会话观察和工具权限拦截，不推进状态。
    - Guard Brief（守卫简报）是状态推进前必须读取的上下文。
  terminology:
    - term: Guard Profile
      meaning: 守卫画像
    - term: Guard Brief
      meaning: 守卫简报
  boundaries:
    - 不修改被守卫发布流程说明。
  scenarios:
    - 发布前必须先完成复核。
    - 完成复核后必须读取最新简报，再推进状态。
    - 流程完成后关闭守卫实例。
  exceptions:
    - 人工覆盖必须单独记录。
  documentation_changes:
    - docs/adr/0001-agent-guard-architecture.md 已确认 Runtime（运行时）不写业务规则。
initialization:
  requested_profile_ref: release-review-order
  hook_installation:
    enabled: true
    reason: 调研确认需要安装 Hook（钩子）观察发布流程。
profile:
  id: release-review-order
  name: 发布复核顺序守卫
  description: 从已确认调研记录生成的发布复核顺序 Guard Profile（守卫画像）草案。
target:
  id: release-review-process
  type: workflow
  name: 发布复核流程
  source: docs/release.md
  boundary: 只旁路观察发布流程，不修改发布流程说明。
  goals:
    - 发布前完成复核。
  allowed_actions:
    - 启动复核节点。
    - 复核完成后关闭守卫。
  forbidden_actions:
    - 未复核直接发布。
activation:
  allowed_sources:
    - agent-guard-skill
    - manual
  required_profile_ref: true
  scopes:
    - project
  on_existing_instance: select
  on_missing_instance: create
  initial_state: review_required
session_focus:
  binding_scope: project
  requires_session_observation: true
  instance_selection: explicit
execution:
  nodes:
    - id: complete_review
      type: review
      required_artifacts:
        - review_note
      completion_signals:
        - state_completed
    - id: close_guard
      type: closure
      required_artifacts:
        - review_note
      completion_signals:
        - state_completed
  states:
    - id: review_required
      allowed_next:
        - complete_review
      forbidden_next:
        - publish
      missing_artifacts:
        - review_note
      brief:
        current_state: review_required
        next_step: 完成复核并登记 review_note。
    - id: ready_to_close
      allowed_next:
        - close_guard
      forbidden_next: []
      missing_artifacts:
        - review_note
      brief:
        current_state: ready_to_close
        next_step: 读取最新 Guard Brief（守卫简报）后推进到 closed。
    - id: closed
      allowed_next: []
      forbidden_next: []
      missing_artifacts: []
      brief:
        current_state: closed
        next_step: 不需要更多被守卫动作。
observation:
  signals:
    - id: session_started
      source: codex
      event_type: SessionStart
      strength: high
      maps_to_node: complete_review
    - id: pre_tool_use
      source: codex
      event_type: PreToolUse
      strength: high
      maps_to_node: complete_review
    - id: state_completed
      source: agent
      event_type: state_completed
      strength: high
      maps_to_node: close_guard
state_machine:
  initial_state: review_required
  terminal_states:
    - closed
  states:
    - id: review_required
      description: 等待发布复核完成。
      permissions:
        default: deny
        rules:
          - effect: allow
            tool: Bash
            match:
              command_prefix: git status
            reason: git status allowed
          - effect: ask
            tool: Bash
            match:
              command_prefix: git push
            reason: git push requires confirmation
    - id: ready_to_close
      description: 复核完成，可以关闭守卫。
      permissions:
        default: allow
    - id: closed
      description: 守卫已关闭。
      permissions:
        default: allow
  transitions:
    - id: mark_review_complete
      from: review_required
      to: ready_to_close
      on_event: state_completed
      guard_points:
        - review_note_present
      required_artifacts:
        - review_note
    - id: close_after_review
      from: ready_to_close
      to: closed
      on_event: state_completed
      guard_points:
        - review_note_present
      required_artifacts:
        - review_note
guard_points:
  - id: review_note_present
    description: 发布前必须有复核记录。
    inputs:
      artifacts:
        - review_note
    required_artifacts:
      - review_note
    checks:
      - id: review_note_exists
        type: artifact_exists
        artifact: review_note
        failure_reason: missing_review_note
        fix_hint: 写入 review_note 后重试 state_completed。
artifacts:
  - id: review_note
    type: note
    owner: external
    path: .local/guard/artifacts/{profile_id}/{instance_id}/{state_version}/review-note.json
    reuse_policy: deny
    required_for:
      - mark_review_complete
      - close_after_review
    description: 发布复核记录，由原流程拥有，守卫只读取。
validation:
  items:
    - 校验生成文件符合最小 Guard Profile（守卫画像）契约。
    - 校验复核记录引用完整。
    - 校验 Hook（钩子）只做拦截，不推进状态。
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def install_plugin(tmp_path: Path) -> Path:
    args = [
        str(INSTALLER),
        "install",
        "--plugin-source",
        str(PLUGIN_ROOT),
        "--target",
        "all",
        "--authorize-install",
        "--codex-home",
        str(tmp_path / "codex-home"),
        "--claude-home",
        str(tmp_path / "claude-home"),
        "--codex-marketplace",
        str(tmp_path / "codex-marketplace.json"),
        "--claude-marketplace",
        str(tmp_path / "claude-marketplace.json"),
    ]
    installed = run(args)
    assert installed.returncode == 0, installed.stdout + installed.stderr

    verified = run(
        [
            str(INSTALLER),
            "verify",
            "--plugin-source",
            str(PLUGIN_ROOT),
            "--target",
            "all",
            "--codex-home",
            str(tmp_path / "codex-home"),
            "--claude-home",
            str(tmp_path / "claude-home"),
            "--codex-marketplace",
            str(tmp_path / "codex-marketplace.json"),
            "--claude-marketplace",
            str(tmp_path / "claude-marketplace.json"),
        ]
    )
    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert "status: verified" in verified.stdout
    return tmp_path / "codex-home" / "plugins" / "agent-guard"


def prepare_project_from_research(tmp_path: Path, plugin_root: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    draft_profile = tmp_path / "drafts" / "release-review-order"
    confirmed_notes = write_confirmed_research_notes(tmp_path / "confirmed-notes.yaml")
    skill_scripts = plugin_root / "skills" / "agent-guard" / "scripts"

    generated = run(
        [
            str(skill_scripts / "extract_guard_model.py"),
            str(confirmed_notes),
            "--output",
            str(draft_profile),
            "--authorize-deny-permissions",
        ]
    )
    assert generated.returncode == 0, generated.stdout + generated.stderr
    assert "status: generated" in generated.stdout
    assert "validation: passed" in generated.stdout

    validated = run([str(skill_scripts / "validate_guard_profile.py"), str(draft_profile)])
    assert validated.returncode == 0, validated.stdout + validated.stderr

    dry_run = run(
        [
            str(skill_scripts / "init_project_guard.py"),
            "--profile",
            str(draft_profile),
            "--project",
            str(project),
        ]
    )
    assert dry_run.returncode == 0, dry_run.stdout + dry_run.stderr
    assert "status: dry_run" in dry_run.stdout
    assert "authorization: missing" in dry_run.stdout

    initialized = run(
        [
            str(skill_scripts / "init_project_guard.py"),
            "--profile",
            str(draft_profile),
            "--project",
            str(project),
            "--authorize-init",
            "--authorize-deny-permissions",
        ]
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert "status: initialized" in initialized.stdout
    assert (project / ".agents" / "guards" / "release-review-order" / "GUARD-MANIFEST.yaml").exists()
    assert not (project / ".local" / "guard").exists()

    return project, user_home


def run_hook(plugin_root: Path, project: Path, user_home: Path, event: str, payload: dict, name: str) -> subprocess.CompletedProcess[str]:
    payload_path = write_json(project / f"{name}.json", payload)
    return run(
        [
            str(plugin_root / "scripts" / "hook_router.py"),
            "--source",
            "codex",
            "--event",
            event,
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--payload-file",
            str(payload_path),
        ],
        cwd=project,
    )


def pre_tool_payload(project: Path, command: str) -> dict:
    return {
        "session_id": "session-prd",
        "cwd": str(project),
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def test_agent_guard_plugin_prd_full_end_to_end_regression(tmp_path: Path) -> None:
    plugin_root = install_plugin(tmp_path)
    project, user_home = prepare_project_from_research(tmp_path, plugin_root)
    runtime = plugin_root / "scripts" / "guard_runtime" / "cli.py"
    skill_scripts = plugin_root / "skills" / "agent-guard" / "scripts"
    activate_wrapper = skill_scripts / "activate_guard.py"
    brief_wrapper = skill_scripts / "render_guard_brief.py"
    wrapper = plugin_root / "skills" / "agent-guard" / "scripts" / "run_guard_event.py"

    no_focus = run_hook(plugin_root, project, user_home, "PreToolUse", pre_tool_payload(project, "git status"), "pre-tool-no-focus")
    assert no_focus.returncode == 0, no_focus.stdout + no_focus.stderr
    assert output_json(no_focus)["status"] == "allow"
    assert output_json(no_focus)["reason"] == "no_session_focus_instance"

    session_start = run_hook(
        plugin_root,
        project,
        user_home,
        "SessionStart",
        {"session_id": "session-prd", "cwd": str(project), "transcript_path": str(project / "transcript.jsonl")},
        "session-start",
    )
    assert session_start.returncode == 0, session_start.stdout + session_start.stderr

    selection = run(
        [
            str(activate_wrapper),
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            "codex",
            "--session-id",
            "session-prd",
            "--profile",
            "release-review-order",
        ],
        cwd=project,
    )
    assert selection.returncode == 1, selection.stdout + selection.stderr
    assert output_json(selection)["status"] == "selection_required"
    assert "target_table" in output_json(selection)
    assert "instance_table" in output_json(selection)

    activated = run(
        [
            str(activate_wrapper),
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--source",
            "codex",
            "--session-id",
            "session-prd",
            "--profile",
            "release-review-order",
            "--create",
            "--title",
            "PRD 全链路实例",
            "--description",
            "验证插件安装后的完整守卫流程。",
        ],
        cwd=project,
    )
    assert activated.returncode == 0, activated.stdout + activated.stderr
    activated_body = output_json(activated)
    instance_id = activated_body["instance_id"]
    assert activated_body["status"] == "session_focus_bound"
    assert Path(activated_body["brief_path"]).exists()

    first_brief = run([str(brief_wrapper), "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-prd"], cwd=project)
    second_brief = run([str(brief_wrapper), "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-prd"], cwd=project)
    assert output_json(first_brief)["status"] == "injectable"
    assert output_json(second_brief)["status"] == "already_injected"
    assert "completed_state_id" not in output_json(first_brief)["brief_text"]

    allowed = run_hook(plugin_root, project, user_home, "PreToolUse", pre_tool_payload(project, "git status"), "pre-tool-allow")
    asked = run_hook(plugin_root, project, user_home, "PreToolUse", pre_tool_payload(project, "git push origin main"), "pre-tool-ask")
    denied = run_hook(plugin_root, project, user_home, "PreToolUse", pre_tool_payload(project, "rm important.txt"), "pre-tool-deny")
    assert output_json(allowed)["status"] == "allow"
    assert output_json(asked)["status"] == "ask"
    assert output_json(denied)["status"] == "deny"

    first_review_note = project / ".local" / "guard" / "artifacts" / "release-review-order" / instance_id / "1" / "review-note.json"
    write_json(first_review_note, {"reviewed": True, "step": "review_required"})
    event_path = write_json(project / "state-completed.json", {"source": "codex", "event_type": "state_completed", "context": {"session_id": "session-prd", "cwd": str(project)}})

    blocked = run([str(wrapper), "--project", str(project), "--user-home", str(user_home), "--event", str(event_path)], cwd=project)
    assert blocked.returncode == 1, blocked.stdout + blocked.stderr
    assert output_json(blocked)["status"] == "brief_required"

    reread = run([str(brief_wrapper), "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-prd"], cwd=project)
    assert reread.returncode == 0, reread.stdout + reread.stderr
    completed = run([str(wrapper), "--project", str(project), "--user-home", str(user_home), "--event", str(event_path)], cwd=project)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert output_json(completed)["reason"] == "state_completed"
    assert output_json(completed)["transition_id"] == "mark_review_complete"

    second_review_note = project / ".local" / "guard" / "artifacts" / "release-review-order" / instance_id / "2" / "review-note.json"
    write_json(second_review_note, {"reviewed": True, "step": "ready_to_close"})
    close_ready_brief = run([str(brief_wrapper), "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-prd"], cwd=project)
    assert close_ready_brief.returncode == 0, close_ready_brief.stdout + close_ready_brief.stderr
    closed_state = run([str(wrapper), "--project", str(project), "--user-home", str(user_home), "--event", str(event_path)], cwd=project)
    assert closed_state.returncode == 0, closed_state.stdout + closed_state.stderr
    assert output_json(closed_state)["transition_id"] == "close_after_review"
    assert output_json(closed_state)["state_version"] == 3

    terminal_brief = run([str(brief_wrapper), "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-prd"], cwd=project)
    assert terminal_brief.returncode == 0, terminal_brief.stdout + terminal_brief.stderr
    terminal = run([str(runtime), "state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-prd"], cwd=project)
    assert terminal.returncode == 1, terminal.stdout + terminal.stderr
    assert output_json(terminal)["reason"] == "terminal_state_completed"

    state_path = project / ".local" / "guard" / "state" / "release-review-order" / instance_id / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    assert state["status"] == "active"

    closed = run([str(runtime), "close-instance", "--project", str(project), "--user-home", str(user_home), "--profile", "release-review-order", "--instance-id", instance_id], cwd=project)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert output_json(closed)["status"] == "instance_closed"

    after_close = run_hook(plugin_root, project, user_home, "PreToolUse", pre_tool_payload(project, "rm important.txt"), "pre-tool-after-close")
    assert after_close.returncode == 0, after_close.stdout + after_close.stderr
    assert output_json(after_close)["reason"] == "no_session_focus_instance"

    combined_output = "\n".join(
        [
            no_focus.stdout,
            session_start.stdout,
            selection.stdout,
            activated.stdout,
            first_brief.stdout,
            second_brief.stdout,
            allowed.stdout,
            asked.stdout,
            denied.stdout,
            blocked.stdout,
            completed.stdout,
            closed_state.stdout,
            terminal.stdout,
            closed.stdout,
            after_close.stdout,
        ]
    )
    assert "subject_key_hash" not in combined_output
    assert "no_subject_match" not in combined_output
    assert "ambiguous_subject" not in combined_output
