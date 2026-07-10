import hashlib
import importlib.util
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


def profile_path(project: Path, user_home: Path, source: str) -> Path:
    anchor = project if source == "project" else user_home
    return anchor / ".agents" / "guards" / "demo-profile"


def create_directory_alias(alias: Path, target: Path) -> None:
    alias.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(target)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            pytest.skip(f"junction unavailable: {result.stdout}{result.stderr}")
        return
    try:
        alias.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {error}")


def create_file_symlink(alias: Path, target: Path) -> None:
    alias.parent.mkdir(parents=True, exist_ok=True)
    try:
        alias.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {error}")


def load_runtime_cli(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(RUNTIME_CLI.parent))
    monkeypatch.delitem(sys.modules, "core", raising=False)
    monkeypatch.delitem(sys.modules, "global_command_guards", raising=False)
    spec = importlib.util.spec_from_file_location("agent_guard_runtime_cli_test", RUNTIME_CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_evidence_link_fixture(project: Path) -> tuple[Path, Path]:
    target = project / "target.json"
    target.write_text('{"original": true}\n', encoding="utf-8")
    (project / ".gitignore").write_text(".local/guard/evidence/\n", encoding="utf-8")
    git(project, "add", ".")
    git(project, "commit", "-m", "track link fixture")
    head = git(project, "rev-parse", "HEAD")
    evidence = project / ".local" / "guard" / "evidence" / "demo-profile" / "demo-pass" / "demo" / head[:12] / "pass.json"
    evidence.parent.mkdir(parents=True)
    return target, evidence


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

    result = run(
        record_evidence_args(
            project,
            user_home,
            fields,
            producer=" reviewer ",
            subject_type=" change ",
        )
    )

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
        "producer": " reviewer ",
        "profile_id": "demo-profile",
        "artifact_id": "demo-pass",
        "subject_type": " change ",
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
        ("registry_invalid_utf8", "artifact_registry_invalid"),
        ("registry_invalid_structure", "artifact_registry_invalid"),
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
    elif setup == "registry_invalid_utf8":
        profile.mkdir(parents=True)
        (profile / "artifacts.yaml").write_bytes(b"artifacts:\n  - \xff\n")
    elif setup == "registry_invalid_structure":
        profile.mkdir(parents=True)
        (profile / "artifacts.yaml").write_text("artifacts: {}\n", encoding="utf-8")
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
    "path",
    [
        ".git/config",
        "src/main.py",
        ".agents/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json",
        ".local/guard/evidence/{profile_id}/{artifact_id}/../{subject_id}/{git_head_short}/pass.json",
    ],
)
def test_record_evidence_rejects_nonstandard_template_before_git(tmp_path: Path, path: str) -> None:
    project = tmp_path / "project"
    project.mkdir()
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile", path=path)
    fields = write_payload(tmp_path / "fields.json", {})

    result = run(record_evidence_args(project, user_home, fields))

    assert_record_failed(result, "unsafe_evidence_path")


@pytest.mark.parametrize("source", ["project", "user"])
def test_record_evidence_rejects_profile_alias_outside_source_root(tmp_path: Path, source: str) -> None:
    project = tmp_path / "project"
    project.mkdir()
    user_home = tmp_path / "home"
    external_profile = tmp_path / "external" / "demo-profile"
    write_guard_defined_artifact(external_profile)
    create_directory_alias(profile_path(project, user_home, source), external_profile)
    fields = write_payload(tmp_path / "fields.json", {})

    result = run(record_evidence_args(project, user_home, fields, profile_source=source))

    assert_record_failed(result, "profile_not_found")


@pytest.mark.parametrize("source", ["project", "user"])
def test_record_evidence_rejects_guard_root_alias_outside_source_anchor(tmp_path: Path, source: str) -> None:
    project = tmp_path / "project"
    project.mkdir()
    user_home = tmp_path / "home"
    external_root = tmp_path / "external-guards"
    write_guard_defined_artifact(external_root / "demo-profile")
    root = profile_path(project, user_home, source).parent
    create_directory_alias(root, external_root)
    fields = write_payload(tmp_path / "fields.json", {})

    result = run(record_evidence_args(project, user_home, fields, profile_source=source))

    assert_record_failed(result, "profile_not_found")


@pytest.mark.parametrize("source", ["project", "user"])
def test_record_evidence_rejects_guard_root_alias_inside_source_anchor(tmp_path: Path, source: str) -> None:
    project = tmp_path / "project"
    project.mkdir()
    user_home = tmp_path / "home"
    anchor = project if source == "project" else user_home
    alternate_root = anchor / "alternate-guards"
    write_guard_defined_artifact(alternate_root / "demo-profile")
    root = profile_path(project, user_home, source).parent
    create_directory_alias(root, alternate_root)
    fields = write_payload(tmp_path / "fields.json", {})

    result = run(record_evidence_args(project, user_home, fields, profile_source=source))

    assert_record_failed(result, "profile_not_found")


@pytest.mark.parametrize("source", ["project", "user"])
def test_record_evidence_rejects_symlinked_artifact_registry(tmp_path: Path, source: str) -> None:
    project = tmp_path / "project"
    project.mkdir()
    user_home = tmp_path / "home"
    external_profile = tmp_path / "external"
    write_guard_defined_artifact(external_profile)
    profile = profile_path(project, user_home, source)
    profile.mkdir(parents=True)
    create_file_symlink(profile / "artifacts.yaml", external_profile / "artifacts.yaml")
    fields = write_payload(tmp_path / "fields.json", {})

    result = run(record_evidence_args(project, user_home, fields, profile_source=source))

    assert_record_failed(result, "artifact_registry_invalid")


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


@pytest.mark.parametrize(
    ("override", "value", "reason"),
    [
        ("producer", "", "producer_required"),
        ("producer", "   ", "producer_required"),
        ("subject_type", "", "subject_type_required"),
        ("subject_type", "\t ", "subject_type_required"),
    ],
)
def test_record_evidence_rejects_blank_metadata_before_profile_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    override: str,
    value: str,
    reason: str,
) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "home"
    fields = write_payload(tmp_path / "fields.json", {})
    module = load_runtime_cli(monkeypatch)

    def reject_resolve(_path: Path, *_args, **_kwargs) -> Path:
        raise OSError("path resolution should not run")

    monkeypatch.setattr(Path, "resolve", reject_resolve)

    code = module.main(record_evidence_args(project, user_home, fields, **{override: value})[1:])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err == ""
    assert json.loads(captured.out) == {"status": "failed", "reason": reason}


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
        (b'{"value":"\xff"}', "business_fields_invalid_utf8"),
        (b"{", "business_fields_invalid_json"),
        (b'{"score":NaN}', "business_fields_invalid_json"),
        (b'{"score":Infinity}', "business_fields_invalid_json"),
        (b'{"score":-Infinity}', "business_fields_invalid_json"),
        (b'{"decision":"pass","decision":"fail"}', "business_fields_invalid_json"),
        (b'{"nested":{"key":1,"key":2}}', "business_fields_invalid_json"),
        (b"[]", "business_fields_object_required"),
        (b'"value"', "business_fields_object_required"),
    ],
)
def test_record_evidence_rejects_invalid_business_fields(tmp_path: Path, content: bytes, reason: str) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile")
    fields = tmp_path / "fields.json"
    fields.write_bytes(content)

    result = run(record_evidence_args(project, user_home, fields))

    assert_record_failed(result, reason)


def test_record_evidence_maps_registry_read_error_without_leaking_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile")
    fields = write_payload(tmp_path / "fields.json", {})
    module = load_runtime_cli(monkeypatch)

    def unreadable_registry(_profile: Path) -> dict:
        raise PermissionError("C:/secret/outside/artifacts.yaml")

    monkeypatch.setattr(module, "load_profile_artifacts", unreadable_registry)

    code = module.main(record_evidence_args(project, user_home, fields)[1:])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err == ""
    assert json.loads(captured.out) == {"status": "failed", "reason": "artifact_registry_unreadable"}


def test_atomic_write_evidence_rejects_nonfinite_numbers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_runtime_cli(monkeypatch)
    path = tmp_path / "evidence.json"

    with pytest.raises(ValueError, match="Out of range float values"):
        module.atomic_write_evidence(path, {"score": float("nan")})

    assert not path.exists()


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
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile")
    target, evidence = prepare_evidence_link_fixture(project)
    os.link(target, evidence)
    fields = write_payload(tmp_path / "fields.json", {"result": "ok"})

    result = run(record_evidence_args(project, user_home, fields))

    assert result.returncode == 0, result.stdout + result.stderr
    assert target.read_text(encoding="utf-8") == '{"original": true}\n'
    assert json.loads(evidence.read_text(encoding="utf-8"))["result"] == "ok"


def test_record_evidence_rejects_symlink_without_mutating_target(tmp_path: Path) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    write_guard_defined_artifact(user_home / ".agents" / "guards" / "demo-profile")
    target, evidence = prepare_evidence_link_fixture(project)
    try:
        evidence.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {error}")
    fields = write_payload(tmp_path / "fields.json", {"result": "ok"})

    result = run(record_evidence_args(project, user_home, fields))

    assert_record_failed(result, "unsafe_evidence_path")
    assert target.read_text(encoding="utf-8") == '{"original": true}\n'


def test_planning_review_uses_generic_evidence_entry_and_existing_hook_router(tmp_path: Path) -> None:
    project = init_git_project(tmp_path / "project")
    (project / ".gitignore").write_text(".local/guard/evidence/\n", encoding="utf-8")
    git(project, "add", ".gitignore")
    git(project, "commit", "-m", "ignore runtime evidence")
    user_home = tmp_path / "home"
    profile = user_home / ".agents" / "guards" / "demo-profile"
    write_guard_defined_artifact(profile, artifact_id="planning_review_pass")
    (profile / "global-command-guards.yaml").write_text(
        """
global_command_guards:
  - id: planning_review_gate
    description: 规划审查门禁。
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard\\.sh\\s+(?P<subject_id>[A-Za-z0-9._-]+)\\s+design\\s+--apply(?:\\s|$)'
      required_captures:
        - subject_id
    evidence:
      artifact: planning_review_pass
    checks:
      - field: status
        predicate: equals
        value: pass
      - field: schema_version
        predicate: equals
        value: guard-evidence/v1
      - field: producer
        predicate: equals
        value: planning-review
      - field: profile_id
        predicate: equals
        value_from: profile_id
      - field: artifact_id
        predicate: equals
        value_from: artifact_id
      - field: subject_type
        predicate: equals
        value: comet-change
      - field: subject_id
        predicate: equals
        value_from: subject_id
      - field: head_ref
        predicate: equals
        value_from: git_head
      - field: head_ref_short
        predicate: equals
        value_from: git_head_short
      - field: blocking_findings
        predicate: number_lte
        value: 0
      - field: review.decision
        predicate: equals
        value: PASS
      - field: scope
        predicate: exists
      - field: report
        predicate: equals
        value: inline:review
      - field: report_hash
        predicate: exists
    deny:
      reason: planning_review_required
      next: record_planning_review_evidence
      suggestion: 记录当前规划审查结论。
""".lstrip(),
        encoding="utf-8",
    )
    review = {
        "mode": "convergence",
        "scope": ["proposal.md", "design.md", "tasks.md"],
        "blocking": 0,
        "findings": [],
        "decision": "PASS",
    }
    canonical = json.dumps(
        review,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    fields = write_payload(
        tmp_path / "planning-fields.json",
        {
            "review": review,
            "blocking_findings": 0,
            "scope": review["scope"],
            "report": "inline:review",
            "report_hash": "sha256:" + hashlib.sha256(canonical).hexdigest(),
        },
    )

    recorded = run(
        record_evidence_args(
            project,
            user_home,
            fields,
            artifact="planning_review_pass",
            subject_type="comet-change",
            subject_id="planning-demo",
            producer="planning-review",
        )
    )

    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    evidence = json.loads((project / output_json(recorded)["path"]).read_text(encoding="utf-8"))
    assert evidence["review"] == review
    assert evidence["report_hash"] == "sha256:" + hashlib.sha256(canonical).hexdigest()

    routed = run(
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
            str(
                write_payload(
                    tmp_path / "planning-hook.json",
                    {
                        "session_id": "planning-session",
                        "cwd": str(project),
                        "tool_name": "Bash",
                        "tool_input": {
                            "command": "comet-guard.sh planning-demo design --apply"
                        },
                    },
                )
            ),
        ]
    )

    assert routed.returncode == 0, routed.stdout + routed.stderr
    assert output_json(routed)["status"] == "allow"


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
