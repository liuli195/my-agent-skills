import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PROJECT_GUARD = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "init_project_guard.py"
ACTIVATE_GUARD = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "activate_guard.py"
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


def run_activate(project: Path, context: dict[str, str]) -> subprocess.CompletedProcess[str]:
    runner = project / ".agents" / "guard-runtime" / "guard_runner.py"
    return subprocess.run(
        [
            sys.executable,
            str(runner),
            "activate",
            "--profile",
            "minimal-sample",
            "--scope",
            "current_context",
            "--source",
            "agent-guard-skill",
            "--context-json",
            json.dumps(context, ensure_ascii=False),
        ],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_skill_activate(project: Path, context: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ACTIVATE_GUARD),
            "--project",
            str(project),
            "--profile",
            "minimal-sample",
            "--scope",
            "current_context",
            "--source",
            "agent-guard-skill",
            "--context-json",
            json.dumps(context, ensure_ascii=False),
        ],
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


def initialized_project_with_profile(tmp_path: Path, draft: Path) -> Path:
    project = tmp_path / "target-project"
    result = run_init(["--profile", str(draft), "--project", str(project), "--authorize-init"])
    assert result.returncode == 0, result.stdout + result.stderr
    return project


def output_value(stdout: str, key: str) -> str:
    prefix = f"{key}: "
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"missing output key: {key}\n{stdout}")


def test_explicit_activation_creates_guard_instance(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)

    result = run_activate(project, {"session_id": "session-1", "repo": "repo-a", "worktree": "main"})

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: activated" in result.stdout
    assert "resolution: created" in result.stdout
    assert "guard_profile_id: minimal-sample" in result.stdout
    assert "state: open" in result.stdout

    subject_hash = output_value(result.stdout, "subject_key_hash")
    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["guard_profile_id"] == "minimal-sample"
    assert state["subject_key_hash"] == subject_hash
    assert state["current_state"] == "open"
    assert state["subject"]["values"]["context.session_id"] == "session-1"
    assert state["created_by"] == "agent-guard-skill"

    audit_path = Path(output_value(result.stdout, "audit_path"))
    brief_input_path = Path(output_value(result.stdout, "brief_input_path"))
    assert audit_path.exists()
    assert brief_input_path.exists()


def test_repeated_activation_matches_existing_guard_instance(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    context = {"session_id": "session-1", "repo": "repo-a", "worktree": "main"}
    first = run_activate(project, context)
    assert first.returncode == 0, first.stdout + first.stderr
    subject_hash = output_value(first.stdout, "subject_key_hash")

    second = run_activate(project, context)

    assert second.returncode == 0, second.stdout + second.stderr
    assert "status: activated" in second.stdout
    assert "resolution: matched" in second.stdout
    assert output_value(second.stdout, "subject_key_hash") == subject_hash
    state_root = project / ".local" / "guard" / "state" / "minimal-sample"
    assert len(list(state_root.glob("*/state.json"))) == 1


def test_missing_required_field_returns_no_subject_match_and_writes_audit(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)

    result = run_activate(project, {"repo": "repo-a", "worktree": "main"})

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: no_subject_match" in result.stdout
    assert "reason: missing_required_fields" in result.stdout
    assert "context.session_id" in result.stdout
    audit_path = Path(output_value(result.stdout, "audit_path"))
    assert audit_path.exists()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "no_subject_match"
    assert audit["detail"]["missing_fields"] == ["context.session_id"]
    state_root = project / ".local" / "guard" / "state" / "minimal-sample"
    assert not list(state_root.glob("*/state.json"))


def test_multiple_matching_instances_return_ambiguous_subject_and_write_audit(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    context = {"session_id": "session-1", "repo": "repo-a", "worktree": "main"}
    first = run_activate(project, context)
    assert first.returncode == 0, first.stdout + first.stderr
    subject_hash = output_value(first.stdout, "subject_key_hash")

    state_root = project / ".local" / "guard" / "state" / "minimal-sample"
    shutil.copytree(state_root / subject_hash, state_root / "duplicate-candidate")

    second = run_activate(project, context)

    assert second.returncode == 0, second.stdout + second.stderr
    assert "status: ambiguous_subject" in second.stdout
    assert f"subject_key_hash: {subject_hash}" in second.stdout
    assert "candidate_count: 2" in second.stdout
    audit_path = Path(output_value(second.stdout, "audit_path"))
    assert audit_path.exists()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["status"] == "ambiguous_subject"
    assert len(audit["detail"]["candidate_state_paths"]) == 2


def test_subject_key_fields_come_from_guard_profile_not_runtime_defaults(tmp_path: Path) -> None:
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)
    (draft / "subject-resolver.yaml").write_text(
        """
subject:
  identity_fields:
    - context.repo
    - context.branch
  required_fields:
    - context.repo
    - context.branch
  optional_fields: []
  context_sources:
    - context
  existing_match_policy: exact
  create_policy: explicit_activation_only
  ambiguous_policy: audit
""".lstrip(),
        encoding="utf-8",
    )
    project = initialized_project_with_profile(tmp_path, draft)

    missing_branch = run_activate(project, {"session_id": "session-1", "repo": "repo-a"})
    assert missing_branch.returncode == 0, missing_branch.stdout + missing_branch.stderr
    assert "status: no_subject_match" in missing_branch.stdout
    assert "context.branch" in missing_branch.stdout

    activated = run_activate(project, {"session_id": "session-1", "repo": "repo-a", "branch": "main"})
    assert activated.returncode == 0, activated.stdout + activated.stderr
    subject_hash = output_value(activated.stdout, "subject_key_hash")
    state_path = project / ".local" / "guard" / "state" / "minimal-sample" / subject_hash / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["subject"]["values"] == {"context.repo": "repo-a", "context.branch": "main"}
    assert "context.session_id" not in state["subject"]["values"]


def test_skill_activate_command_delegates_to_project_runtime(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)

    result = run_skill_activate(project, {"session_id": "session-1", "repo": "repo-a"})

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: activated" in result.stdout
    assert "resolution: created" in result.stdout
