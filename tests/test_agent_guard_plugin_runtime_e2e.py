import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


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


def git(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def init_git_project(project: Path) -> Path:
    project.mkdir(parents=True)
    git(project, "init")
    git(project, "config", "user.name", "Agent Guard Test")
    git(project, "config", "user.email", "agent-guard@example.invalid")
    (project / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    git(project, "add", "tracked.txt")
    git(project, "commit", "-m", "initial")
    return project


def write_guard_defined_artifact(
    profile: Path,
    artifact_id: str = "demo-pass",
    *,
    owner: str = "agent-guard",
    artifact_type: str = "json",
    path: str = ".local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json",
) -> None:
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "artifacts.yaml").write_text(
        "artifacts:\n"
        f"  - id: {json.dumps(artifact_id)}\n"
        f"    owner: {json.dumps(owner)}\n"
        f"    type: {json.dumps(artifact_type)}\n"
        f"    path: {json.dumps(path)}\n",
        encoding="utf-8",
    )


def record_evidence_args(
    project: Path,
    user_home: Path,
    fields: Path,
    **overrides: str,
) -> list[str]:
    values = {
        "profile_source": "user",
        "profile": "demo-profile",
        "artifact": "demo-pass",
        "subject_type": "change",
        "subject_id": "demo",
        "producer": "reviewer",
    }
    values.update(overrides)
    return [
        str(RUNTIME_CLI),
        "record-evidence",
        "--project",
        str(project),
        "--user-home",
        str(user_home),
        "--profile-source",
        values["profile_source"],
        "--profile",
        values["profile"],
        "--artifact",
        values["artifact"],
        "--subject-type",
        values["subject_type"],
        "--subject-id",
        values["subject_id"],
        "--producer",
        values["producer"],
        "--business-fields-file",
        str(fields),
    ]


def assert_record_failed(result: subprocess.CompletedProcess[str], reason: str) -> None:
    assert result.returncode != 0
    assert result.stderr == ""
    assert output_json(result) == {"status": "failed", "reason": reason}
    assert "Traceback" not in result.stdout + result.stderr


def test_record_evidence_writes_current_head_guard_owned_artifact(tmp_path: Path) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    profile = user_home / ".agents" / "guards" / "demo-profile"
    write_guard_defined_artifact(profile)
    fields = write_payload(tmp_path / "fields.json", {"blocking_findings": 0, "report": "inline:review"})

    result = run(record_evidence_args(project, user_home, fields))

    assert result.returncode == 0, result.stdout + result.stderr
    body = output_json(result)
    head = git(project, "rev-parse", "HEAD")
    assert body == {
        "status": "evidence_recorded",
        "head_ref": head,
        "head_ref_short": head[:12],
        "path": f".local/guard/evidence/demo-profile/demo-pass/demo/{head[:12]}/pass.json",
    }
    evidence = json.loads((project / body["path"]).read_text(encoding="utf-8"))
    assert evidence == {
        "schema_version": "guard-evidence/v1",
        "status": "pass",
        "producer": "reviewer",
        "profile_id": "demo-profile",
        "artifact_id": "demo-pass",
        "subject_type": "change",
        "subject_id": "demo",
        "head_ref": head,
        "head_ref_short": head[:12],
        "created_at": evidence["created_at"],
        "blocking_findings": 0,
        "report": "inline:review",
    }
    assert evidence["created_at"].endswith("Z")


def test_record_evidence_does_not_fall_back_to_other_profile_source(tmp_path: Path) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile")
    fields = write_payload(tmp_path / "fields.json", {})

    result = run(record_evidence_args(project, user_home, fields, profile_source="project"))

    assert_record_failed(result, "profile_not_found")


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        ("profile_missing", "profile_not_found"),
        ("registry_missing", "artifact_registry_missing"),
        ("registry_invalid", "artifact_registry_invalid"),
        ("artifact_duplicate", "artifact_id_duplicate: demo-pass"),
        ("artifact_missing", "artifact_not_found"),
        ("owner_invalid", "artifact_not_guard_defined"),
        ("type_invalid", "artifact_not_guard_defined"),
    ],
)
def test_record_evidence_rejects_invalid_profile_registry_or_artifact(
    tmp_path: Path,
    setup: str,
    reason: str,
) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    profile = user_home / ".agents" / "guards" / "demo-profile"
    artifact = "demo-pass"
    if setup == "registry_missing":
        profile.mkdir(parents=True)
    elif setup == "registry_invalid":
        profile.mkdir(parents=True)
        (profile / "artifacts.yaml").write_text("artifacts: [", encoding="utf-8")
    elif setup == "artifact_duplicate":
        write_guard_defined_artifact(profile)
        with (profile / "artifacts.yaml").open("a", encoding="utf-8") as stream:
            stream.write("  - id: demo-pass\n    owner: agent-guard\n    type: json\n    path: pass.json\n")
    elif setup == "artifact_missing":
        write_guard_defined_artifact(profile, "another-pass")
    elif setup == "owner_invalid":
        write_guard_defined_artifact(profile, owner="upstream")
    elif setup == "type_invalid":
        write_guard_defined_artifact(profile, artifact_type="yaml")
    fields = write_payload(tmp_path / "fields.json", {})

    result = run(record_evidence_args(project, user_home, fields, artifact=artifact))

    assert_record_failed(result, reason)


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("/tmp/pass.json", "unsafe_evidence_path"),
        (r"C:\\temp\\pass.json", "unsafe_evidence_path"),
        ("../pass.json", "unsafe_evidence_path"),
        (".local/guard/evidence/{missing}/pass.json", "evidence_path_template_value_missing: missing"),
    ],
)
def test_record_evidence_rejects_unsafe_or_unrenderable_artifact_path(
    tmp_path: Path,
    path: str,
    reason: str,
) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile", path=path)
    fields = write_payload(tmp_path / "fields.json", {})

    result = run(record_evidence_args(project, user_home, fields))

    assert_record_failed(result, reason)


@pytest.mark.parametrize(
    ("override", "value"),
    [
        ("profile", "bad/profile"),
        ("artifact", "bad/artifact"),
        ("subject_id", "bad/subject"),
    ],
)
def test_record_evidence_rejects_non_segment_identifiers(tmp_path: Path, override: str, value: str) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile")
    fields = write_payload(tmp_path / "fields.json", {})

    result = run(record_evidence_args(project, user_home, fields, **{override: value}))

    assert_record_failed(result, "unsafe_segment")


def test_record_evidence_requires_git_repository(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile")
    fields = write_payload(tmp_path / "fields.json", {})

    result = run(record_evidence_args(project, user_home, fields))

    assert_record_failed(result, "git_repository_required")


def test_record_evidence_requires_clean_worktree(tmp_path: Path) -> None:
    project = init_git_project(tmp_path / "project")
    (project / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile")
    fields = write_payload(tmp_path / "fields.json", {})

    result = run(record_evidence_args(project, user_home, fields))

    assert_record_failed(result, "dirty_worktree")


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("{", "business_fields_invalid_json"),
        ("[]", "business_fields_object_required"),
    ],
)
def test_record_evidence_rejects_invalid_business_fields(tmp_path: Path, content: str, reason: str) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile")
    fields = tmp_path / "fields.json"
    fields.write_text(content, encoding="utf-8")

    result = run(record_evidence_args(project, user_home, fields))

    assert_record_failed(result, reason)


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "status",
        "producer",
        "profile_id",
        "artifact_id",
        "subject_type",
        "subject_id",
        "head_ref",
        "head_ref_short",
        "created_at",
    ],
)
def test_record_evidence_rejects_each_reserved_business_field(tmp_path: Path, field: str) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile")
    fields = write_payload(tmp_path / "fields.json", {field: "caller-value"})

    result = run(record_evidence_args(project, user_home, fields))

    assert_record_failed(result, f"reserved_field_conflict: {field}")


def test_record_evidence_does_not_accept_caller_head_override(tmp_path: Path) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile")
    fields = write_payload(tmp_path / "fields.json", {})
    args = record_evidence_args(project, user_home, fields)
    args.extend(["--head-ref", "caller-value"])

    result = run(args)

    assert result.returncode != 0
    assert result.stderr == ""
    body = output_json(result)
    assert body["status"] == "failed"
    assert "unrecognized arguments: --head-ref caller-value" in body["reason"]


def test_record_evidence_atomically_replaces_hardlink_without_mutating_target(tmp_path: Path) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    artifact_path = ".local/guard/evidence/demo-profile/demo-pass/demo/pass.json"
    write_guard_defined_artifact(
        user_home / ".agents" / "guards" / "demo-profile",
        path=artifact_path,
    )
    target = project / "target.json"
    target.write_text('{"original": true}\n', encoding="utf-8")
    evidence = project / artifact_path
    evidence.parent.mkdir(parents=True)
    os.link(target, evidence)
    git(project, "add", ".")
    git(project, "commit", "-m", "track hardlink fixture")
    fields = write_payload(tmp_path / "fields.json", {"result": "ok"})

    result = run(record_evidence_args(project, user_home, fields))

    assert result.returncode == 0, result.stdout + result.stderr
    assert target.read_text(encoding="utf-8") == '{"original": true}\n'
    assert json.loads(evidence.read_text(encoding="utf-8"))["result"] == "ok"


def test_record_evidence_rejects_symlink_without_mutating_target(tmp_path: Path) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    artifact_path = ".local/guard/evidence/demo-profile/demo-pass/demo/pass.json"
    write_guard_defined_artifact(
        user_home / ".agents" / "guards" / "demo-profile",
        path=artifact_path,
    )
    target = project / "target.json"
    target.write_text('{"original": true}\n', encoding="utf-8")
    evidence = project / artifact_path
    evidence.parent.mkdir(parents=True)
    try:
        evidence.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {error}")
    git(project, "add", ".")
    git(project, "commit", "-m", "track symlink fixture")
    fields = write_payload(tmp_path / "fields.json", {"result": "ok"})

    result = run(record_evidence_args(project, user_home, fields))

    assert_record_failed(result, "unsafe_evidence_path")
    assert target.read_text(encoding="utf-8") == '{"original": true}\n'


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
