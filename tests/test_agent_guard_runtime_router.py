import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from tests.support.git_templates import copy_template


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
PLUGIN_SKILL = PLUGIN_ROOT / "skills" / "agent-guard"
HOOK_ROUTER = PLUGIN_ROOT / "scripts" / "hook_router.py"
RUN_GUARD_EVENT = PLUGIN_SKILL / "scripts" / "run_guard_event.py"
RUNTIME_CLI = PLUGIN_ROOT / "scripts" / "guard_runtime" / "cli.py"
MINIMAL_PROFILE = PLUGIN_SKILL / "assets" / "templates" / "guard-profile" / "minimal"
GIT_TEMPLATE_ROOT = Path(tempfile.gettempdir()) / "agent-guard-runtime-router-git-template-v1"
GIT_TEMPLATE_LOCK_STALE_SECONDS = 30
GIT_TEMPLATE_LOCK_TIMEOUT_SECONDS = 30
_HOOK_ROUTER_MODULE = None
_RUNTIME_CLI_MODULE = None
_GLOBAL_COMMAND_GUARDS_MODULE = None


def load_hook_router_module():
    global _HOOK_ROUTER_MODULE
    if _HOOK_ROUTER_MODULE is not None:
        return _HOOK_ROUTER_MODULE
    if str(HOOK_ROUTER.parent) not in sys.path:
        sys.path.insert(0, str(HOOK_ROUTER.parent))
    spec = importlib.util.spec_from_file_location("agent_guard_hook_router_for_tests", HOOK_ROUTER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _HOOK_ROUTER_MODULE = module
    return module


def load_runtime_cli_module():
    global _RUNTIME_CLI_MODULE
    if _RUNTIME_CLI_MODULE is not None:
        return _RUNTIME_CLI_MODULE
    sys.path.insert(0, str(RUNTIME_CLI.parent))
    spec = importlib.util.spec_from_file_location("agent_guard_runtime_cli_for_tests", RUNTIME_CLI)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _RUNTIME_CLI_MODULE = module
    return module


def load_global_command_guards_module():
    global _GLOBAL_COMMAND_GUARDS_MODULE
    if _GLOBAL_COMMAND_GUARDS_MODULE is not None:
        return _GLOBAL_COMMAND_GUARDS_MODULE
    module_path = PLUGIN_ROOT / "scripts" / "guard_runtime" / "global_command_guards.py"
    spec = importlib.util.spec_from_file_location("global_command_guards_for_tests", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _GLOBAL_COMMAND_GUARDS_MODULE = module
    return module


def run_main_in_process(
    module,
    script: Path,
    args: list[str],
    *,
    cwd: Path = REPO_ROOT,
    stdin: str = "",
) -> subprocess.CompletedProcess[str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    previous_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(stdin)
        with contextlib.chdir(cwd), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                returncode = int(module.main(args))
            except SystemExit as error:
                returncode = error.code if isinstance(error.code, int) else 1
    finally:
        sys.stdin = previous_stdin
    return subprocess.CompletedProcess(
        [sys.executable, str(script), *args],
        returncode,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def run_hook(args: list[str], payload: dict) -> subprocess.CompletedProcess[str]:
    payload_file = Path(args[args.index("--payload-file") + 1])
    payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return run_main_in_process(load_hook_router_module(), HOOK_ROUTER, args)


def run_hook_stdin(args: list[str], payload: dict) -> subprocess.CompletedProcess[str]:
    return run_main_in_process(
        load_hook_router_module(),
        HOOK_ROUTER,
        args,
        stdin=json.dumps(payload, ensure_ascii=False),
    )


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    module = load_runtime_cli_module()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            returncode = int(module.main(args))
        except SystemExit as error:
            returncode = error.code if isinstance(error.code, int) else 1
    return subprocess.CompletedProcess(
        [sys.executable, str(RUNTIME_CLI), *args],
        returncode,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def run_guard_event(project: Path, user_home: Path, event_file: Path, event: dict) -> subprocess.CompletedProcess[str]:
    event_file.write_text(json.dumps(event, ensure_ascii=False), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(RUN_GUARD_EVENT),
            "--project",
            str(project),
            "--user-home",
            str(user_home),
            "--event",
            str(event_file),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def body(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def test_json_checks_module_exposes_shared_predicates_and_helpers() -> None:
    from importlib import util

    module_path = PLUGIN_ROOT / "scripts" / "guard_runtime" / "json_checks.py"
    spec = util.spec_from_file_location("json_checks", module_path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.JSON_PREDICATES == {
        "exists",
        "equals",
        "not_equals",
        "number_lte",
        "number_gte",
        "array_none",
        "array_all",
    }
    assert module.VALUE_PREDICATES == {"equals", "not_equals", "number_lte", "number_gte"}
    assert module.ARRAY_PREDICATES == {"array_none", "array_all"}
    assert module.json_field({"review": {"status": "pass"}}, "review.status") == "pass"
    assert module.json_field({"review": {"status": "pass"}}, "review.missing") is module.MISSING_JSON_VALUE
    assert not module.evaluate_json_predicate(module.json_field({"review": {}}, "review.status"), "exists")
    assert module.evaluate_json_predicate(module.json_field({"review": {"status": None}}, "review.status"), "exists")
    assert module.evaluate_json_predicate("pass", "equals", "pass")
    assert module.evaluate_json_predicate("pass", "not_equals", "fail")
    assert module.evaluate_json_predicate(2, "number_lte", 3)
    assert module.evaluate_json_predicate(4, "number_gte", 3)
    assert not module.evaluate_json_predicate(True, "number_lte", 1)
    assert module.evaluate_json_predicate(
        [{"severity": "P2"}, {"severity": "P3"}],
        "array_none",
        where={"field": "severity", "predicate": "equals", "value": "P0"},
    )
    assert module.evaluate_json_predicate(
        [{"triaged": True}, {"triaged": True}],
        "array_all",
        where={"field": "triaged", "predicate": "equals", "value": True},
    )


def test_command_context_module_exposes_shared_envelope_helpers() -> None:
    from importlib import util

    module_path = PLUGIN_ROOT / "scripts" / "guard_runtime" / "command_context.py"
    spec = util.spec_from_file_location("command_context", module_path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    envelope = {"payload": {"tool": {"name": "Bash"}, "tool_input": {"command": "git status"}}}

    assert module.tool_name_from_envelope(envelope) == "Bash"
    assert module.command_from_envelope(envelope) == "git status"
    assert module.command_from_envelope({"payload": {"command": "git status --short"}}) == "git status --short"
    for container in ["input", "parameters", "params", "args", "arguments"]:
        assert module.command_from_envelope({"payload": {container: {"command": f"git status --{container}"}}}) == f"git status --{container}"
        assert module.command_from_envelope({"payload": {container: {"cmd": f"git diff --{container}"}}}) == f"git diff --{container}"
    assert module.command_from_envelope({"payload": {"tool_input": {"command": ["git", "status"]}}}) == ""


def test_command_matcher_module_exposes_shared_pattern_and_prefix_matching() -> None:
    from importlib import util

    module_path = PLUGIN_ROOT / "scripts" / "guard_runtime" / "command_matcher.py"
    spec = util.spec_from_file_location("command_matcher", module_path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    command = "& 'C:\\Program Files\\Git\\bin\\bash.exe' -lc 'cd \"/d/My Project/my-agent-skills\" && comet-guard.sh add-guard-gate-binding verify --apply'"

    assert "comet-guard.sh add-guard-gate-binding verify --apply" in module.normalized_command_texts(command)
    assert module.match_command_pattern(
        "comet-guard.sh add-guard-gate-binding verify --apply",
        "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply",
    ) == {"change": "add-guard-gate-binding"}
    assert module.command_prefix_matches("git push origin main", "git push")
    assert not module.command_prefix_matches(command, "comet-guard.sh")
    assert module.command_prefix_matches(command, "comet-guard.sh", normalize_texts=True)


def test_global_command_pattern_extracts_named_captures(tmp_path: Path) -> None:
    from importlib import util

    module_path = PLUGIN_ROOT / "scripts" / "guard_runtime" / "global_command_guards.py"
    spec = util.spec_from_file_location("global_command_guards", module_path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    match = module.match_command_pattern(
        "comet-guard.sh add-guard-gate-binding verify --apply",
        "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply",
    )

    assert match == {"change": "add-guard-gate-binding"}


def test_global_command_pattern_matches_powershell_wrapped_git_bash(tmp_path: Path) -> None:
    from importlib import util

    module_path = PLUGIN_ROOT / "scripts" / "guard_runtime" / "global_command_guards.py"
    spec = util.spec_from_file_location("global_command_guards", module_path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    command = "& 'C:\\Program Files\\Git\\bin\\bash.exe' -lc 'cd \"/d/My Project/my-agent-skills\" && comet-guard.sh add-guard-gate-binding verify --apply'"

    normalized = module.normalized_command_texts(command)

    assert "comet-guard.sh add-guard-gate-binding verify --apply" in normalized


def write_global_command_guard(profile: Path, guard_id: str, command_pattern: str) -> None:
    profile.joinpath("global-command-guards.yaml").write_text(
        f"""
global_command_guards:
  - id: {guard_id}
    description: 测试全局命令守卫点。
    tool: Bash
    match:
      command_patterns:
        - '{command_pattern}'
    evidence:
      path: '.local/guard/evidence/{{source_scope}}/{{profile_id}}/{{guard_id}}/{{change}}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: global_command_guard_required
      next: produce_required_evidence
      suggestion: 先生成证据。
""".lstrip(),
        encoding="utf-8",
    )


def write_global_command_guard_yaml(profile: Path, body: str) -> None:
    profile.joinpath("global-command-guards.yaml").write_text(body.lstrip(), encoding="utf-8")


def write_guard_evidence(project: Path, *parts: str, data: dict) -> Path:
    path = project / ".local" / "guard" / "evidence" / Path(*parts) / "evidence.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def write_user_guard_evidence(user_home: Path, *parts: str, data: dict) -> Path:
    path = user_home / ".agents" / "guard" / "evidence" / Path(*parts) / "evidence.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def write_cross_agent_review_marker(
    project: Path,
    change: str,
    head_ref: str,
    data: dict,
    *,
    profile_id: str = "personal-policy",
) -> Path:
    path = (
        project
        / ".local"
        / "guard"
        / "evidence"
        / profile_id
        / "cross_agent_review_pass"
        / change
        / head_ref[:12]
        / "pass.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def write_user_scope_cross_agent_review_marker(user_home: Path, change: str, head_ref: str, data: dict) -> Path:
    path = (
        user_home
        / ".agents"
        / "guard"
        / ".local"
        / "guard"
        / "evidence"
        / "personal-policy"
        / "cross_agent_review_pass"
        / change
        / head_ref[:12]
        / "pass.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def write_global_command_guard_with_artifact(profile: Path, command_pattern: str, artifact_id: str = "completion_note") -> None:
    profile.joinpath("global-command-guards.yaml").write_text(
        f"""
global_command_guards:
  - id: verify_requires_review
    description: Comet build 审查门禁。
    tool: Bash
    match:
      command_patterns:
        - '{command_pattern}'
      required_captures:
        - change
    evidence:
      artifact: {artifact_id}
    checks:
      - field: status
        predicate: equals
        value: pass
      - field: change
        predicate: equals
        value_from: change
      - field: head_ref
        predicate: equals
        value_from: git_head
      - field: blocking_findings
        predicate: number_lte
        value: 0
      - field: report
        predicate: exists
      - field: report_hash
        predicate: exists
    deny:
      reason: comet_cross_agent_review_required
      next: produce_cross_agent_review_pass_marker
      suggestion: 生成当前 change 和当前 HEAD 对应的 cross-agent-review pass marker。
""".lstrip(),
        encoding="utf-8",
    )


def write_cross_agent_review_artifacts(profile: Path) -> None:
    profile.joinpath("artifacts.yaml").write_text(
        """
artifacts:
  - id: cross_agent_review_pass
    type: json
    owner: agent-guard
    required_for:
      - produce_cross_agent_review_pass_marker
    path: .local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json
    reuse_policy: deny
""".lstrip(),
        encoding="utf-8",
    )


def test_load_profile_artifacts_preserves_owner_type_and_path(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    profile.mkdir()
    write_cross_agent_review_artifacts(profile)
    module = load_global_command_guards_module()

    artifacts = module.load_profile_artifacts(profile)

    assert artifacts["cross_agent_review_pass"] == {
        "id": "cross_agent_review_pass",
        "type": "json",
        "owner": "agent-guard",
        "required_for": ["produce_cross_agent_review_pass_marker"],
        "path": ".local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json",
        "reuse_policy": "deny",
    }


def test_load_profile_artifacts_rejects_duplicate_id(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    profile.mkdir()
    write_cross_agent_review_artifacts(profile)
    artifacts = profile / "artifacts.yaml"
    declaration = artifacts.read_text(encoding="utf-8").split("artifacts:\n", 1)[1]
    artifacts.write_text(f"artifacts:\n{declaration}{declaration}", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact_id_duplicate: cross_agent_review_pass"):
        load_global_command_guards_module().load_profile_artifacts(profile)


def test_resolve_artifact_path_uses_explicit_scope_roots(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    module = load_global_command_guards_module()

    assert module.resolve_artifact_path(project, user_home, "project", "evidence/pass.json") == project / "evidence" / "pass.json"
    assert module.resolve_artifact_path(project, user_home, "user", "evidence/pass.json") == user_home / ".agents" / "guard" / "evidence" / "pass.json"


def test_resolve_artifact_path_rejects_unsafe_inputs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    module = load_global_command_guards_module()

    for scope, rendered in [
        ("invalid", "evidence/pass.json"),
        ("project", str(tmp_path / "absolute.json")),
        ("project", "C:\\outside\\pass.json"),
        ("project", "\\outside\\pass.json"),
        ("project", "../outside/pass.json"),
    ]:
        with pytest.raises(module.UnsafeEvidencePath, match="unsafe_evidence_path"):
            module.resolve_artifact_path(project, user_home, scope, rendered)


def test_resolve_artifact_path_rejects_symlink_escape(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    try:
        (project / "linked").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    module = load_global_command_guards_module()
    with pytest.raises(module.UnsafeEvidencePath, match="unsafe_evidence_path"):
        module.resolve_artifact_path(project, user_home, "project", "linked/pass.json")


def write_short_head_cross_agent_review_artifacts(profile: Path) -> None:
    profile.joinpath("artifacts.yaml").write_text(
        """
artifacts:
  - id: cross_agent_review_pass
    type: json
    owner: agent-guard
    required_for:
      - produce_cross_agent_review_pass_marker
    path: .local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json
    reuse_policy: deny
""".lstrip(),
        encoding="utf-8",
    )


def write_planning_review_artifacts(profile: Path) -> None:
    profile.joinpath("artifacts.yaml").write_text(
        """
artifacts:
  - id: planning_review_pass
    type: json
    owner: agent-guard
    required_for:
      - produce_planning_review_pass_marker
    path: .local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json
    reuse_policy: deny
""".lstrip(),
        encoding="utf-8",
    )


def write_planning_review_guard(profile: Path) -> None:
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: comet_design_requires_planning_review
    description: Comet build 前必须完成 planning-review。
    tool: Bash
    match:
      command_patterns:
        - '(^|[\\s''"])(?:[^\\s''"]*[\\\\/])?comet-guard\\.sh[''"]?\\s+(?P<subject_id>[A-Za-z0-9._-]+)\\s+design\\s+--apply(?:\\s|$)'
        - '\\$COMET_GUARD"? (?P<subject_id>[A-Za-z0-9._-]+) design --apply'
        - '%COMET_GUARD% (?P<subject_id>[A-Za-z0-9._-]+) design --apply'
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
      - field: scope
        predicate: exists
      - field: report_hash
        predicate: exists
      - field: created_at
        predicate: exists
    deny:
      reason: comet_planning_review_required
      next: produce_planning_review_pass_marker
      suggestion: 先完成 planning-review，并写入当前 change 和当前 HEAD 对应的 pass marker。
""",
    )


def write_planning_review_profile(user_home: Path) -> Path:
    profile = user_home / ".agents" / "guards" / "comet-review-gate"
    profile.mkdir(parents=True)
    write_planning_review_artifacts(profile)
    write_planning_review_guard(profile)
    return profile


def planning_review_pass_data(change: str, head_ref: str) -> dict:
    return {
        "schema_version": "guard-evidence/v1",
        "status": "pass",
        "producer": "planning-review",
        "profile_id": "comet-review-gate",
        "artifact_id": "planning_review_pass",
        "subject_type": "comet-change",
        "subject_id": change,
        "head_ref": head_ref,
        "head_ref_short": head_ref[:12],
        "blocking_findings": 0,
        "scope": {"change": change},
        "report": "ok",
        "report_hash": "sha256:abc123",
        "created_at": "2026-06-25T00:00:00Z",
    }


def write_planning_review_pass(project: Path, change: str, head_ref: str, data: dict | None = None) -> Path:
    path = project / ".local" / "guard" / "evidence" / "comet-review-gate" / "planning_review_pass" / change / head_ref[:12] / "pass.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data or planning_review_pass_data(change, head_ref), ensure_ascii=False), encoding="utf-8")
    return path


def project_git_head(project: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()


def remove_git_template_lock(lock_dir: Path) -> None:
    for _ in range(5):
        shutil.rmtree(lock_dir, ignore_errors=True)
        if not lock_dir.exists():
            return
        time.sleep(0.05)


def create_basic_git_repo(project: Path) -> str:
    subprocess.run(["git", "init"], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=project,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=project,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    (project / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=project,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return project_git_head(project)


def basic_git_template() -> Path:
    ready = GIT_TEMPLATE_ROOT / ".ready"
    lock_dir = GIT_TEMPLATE_ROOT.with_name(f"{GIT_TEMPLATE_ROOT.name}.lock")
    if ready.exists():
        if lock_dir.exists():
            remove_git_template_lock(lock_dir)
        return GIT_TEMPLATE_ROOT

    deadline = time.monotonic() + GIT_TEMPLATE_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock_dir.mkdir(parents=True)
            break
        except FileExistsError:
            try:
                lock_age = time.time() - lock_dir.stat().st_mtime
            except FileNotFoundError:
                continue
            if lock_age > GIT_TEMPLATE_LOCK_STALE_SECONDS:
                remove_git_template_lock(lock_dir)
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"template_lock_timeout: {lock_dir}")
            time.sleep(0.05)

    try:
        if not ready.exists():
            if GIT_TEMPLATE_ROOT.exists():
                shutil.rmtree(GIT_TEMPLATE_ROOT)
            GIT_TEMPLATE_ROOT.mkdir(parents=True, exist_ok=True)
            create_basic_git_repo(GIT_TEMPLATE_ROOT)
            ready.write_text("ok\n", encoding="utf-8")
    finally:
        remove_git_template_lock(lock_dir)
    return GIT_TEMPLATE_ROOT


def init_git_repo(project: Path) -> str:
    copy_template(basic_git_template(), project)
    return project_git_head(project)


def write_comet_state(project: Path, change: str, workflow: str) -> Path:
    state = project / "openspec" / "changes" / change / ".comet.yaml"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(f"workflow: {workflow}\nphase: build\n", encoding="utf-8")
    return state


def read_project_audits(project: Path) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (project / ".local" / "guard" / "audit").glob("*.json")
    ]


def test_collects_project_and_user_global_command_guards(tmp_path: Path) -> None:
    from importlib import util

    module_path = PLUGIN_ROOT / "scripts" / "guard_runtime" / "global_command_guards.py"
    spec = util.spec_from_file_location("global_command_guards", module_path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project_profile = project / ".agents" / "guards" / "repo-policy"
    user_profile = user_home / ".agents" / "guards" / "personal-policy"
    project_profile.mkdir(parents=True)
    user_profile.mkdir(parents=True)
    command_pattern = "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply"
    write_global_command_guard(project_profile, "verify_requires_review", command_pattern)
    write_global_command_guard(user_profile, "verify_requires_review", command_pattern)

    guards = module.collect_global_command_guards(project, user_home)
    ids = sorted(guard.effective_guard_id for guard in guards)

    assert ids == [
        "project:repo-policy:verify_requires_review",
        "user:personal-policy:verify_requires_review",
    ]


def test_global_command_guard_denies_without_session_focus(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply")

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "global_command_guard_required"
    assert payload["next"] == "produce_required_evidence"
    assert payload["suggestion"] == "先生成证据。"
    assert payload["matched_guard_ids"] == ["project:repo-policy:verify_requires_review"]
    assert payload["captures"] == {"change": "add-guard-gate-binding"}
    assert payload["failing_guards"][0]["effective_guard_id"] == "project:repo-policy:verify_requires_review"
    assert ".local" in payload["failing_guards"][0]["evidence_path"]
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["detail"]["kind"] == "global_command_guard"


def test_hook_router_preserves_top_level_command_for_global_command_guard(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply")

    result = pre_tool_payload(
        project,
        user_home,
        {
            "session_id": "session-1",
            "cwd": str(project),
            "tool_name": "Bash",
            "command": "comet-guard.sh demo build --apply",
        },
    )

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "global_command_guard_required"
    assert payload["captures"] == {"change": "demo"}


def test_global_command_guard_uses_parameters_command_and_audits_command(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    command = "comet-guard.sh demo build --apply"
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply")

    result = pre_tool_payload(
        project,
        user_home,
        {
            "session_id": "session-1",
            "cwd": str(project),
            "tool_name": "Bash",
            "parameters": {"command": command},
        },
    )

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["captures"] == {"change": "demo"}
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["detail"]["global_command_guard"]["command"] == command


def test_hook_router_blocks_codex_stdin_hook_with_native_deny_output(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply")

    result = run_hook_stdin(
        [
            "--source",
            "codex",
            "--event",
            "PreToolUse",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
        ],
        {
            "session_id": "session-1",
            "cwd": str(project),
            "tool_name": "Bash",
            "tool_input": {"command": "comet-guard.sh demo build --apply"},
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "global_command_guard_required\n先生成证据。",
        }
    }
    assert result.stderr == ""


def test_hook_router_blocks_claude_stdin_hook_with_exit_code_2(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply")

    result = run_hook_stdin(
        [
            "--source",
            "claude",
            "--event",
            "PreToolUse",
            "--project",
            str(project),
            "--user-home",
            str(user_home),
        ],
        {
            "session_id": "session-1",
            "cwd": str(project),
            "tool_name": "Bash",
            "tool_input": {"command": "comet-guard.sh demo build --apply"},
        },
    )

    assert result.returncode == 2, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "global_command_guard_required"
    assert "global_command_guard_required" in result.stderr


def test_run_guard_event_preserves_standard_payload_command_for_global_command_guard(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    init_git_repo(project)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply")

    result = run_guard_event(
        project,
        user_home,
        tmp_path / "event.json",
        {
            "source": "codex",
            "event_type": "codex.pre_tool_use",
            "context": {
                "session_id": "s1",
                "cwd": str(project),
                "runtime_scope": "project",
            },
            "tool": {"name": "Bash"},
            "payload": {"command": "comet-guard.sh demo build --apply"},
        },
    )

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "global_command_guard_required"
    assert payload["captures"] == {"change": "demo"}


def test_global_command_guard_passes_with_valid_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply")
    write_guard_evidence(
        project,
        "project",
        "repo-policy",
        "verify_requires_review",
        "add-guard-gate-binding",
        data={"status": "pass"},
    )

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["detail"]["kind"] == "session_focus_boundary"
    global_audits = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (project / ".local" / "guard" / "audit").glob("*.json")
        if json.loads(path.read_text(encoding="utf-8"))["reason"] == "global_command_guard_passed"
    ]
    assert global_audits[0]["detail"]["kind"] == "global_command_guard"


def test_global_command_guard_passes_with_artifact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    write_global_command_guard_with_artifact(profile, "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply", "cross_agent_review_pass")
    write_cross_agent_review_marker(
        project,
        "add-guard-gate-binding",
        head_ref,
        data={"status": "pass", "change": "add-guard-gate-binding", "head_ref": head_ref, "blocking_findings": 0, "report": "ok", "report_hash": "abc123"},
    )

    result = pre_tool_payload(
        project,
        user_home,
        {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "comet-guard.sh add-guard-gate-binding build --apply"}},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["detail"]["kind"] == "session_focus_boundary"


def assert_artifact_registry_invalid(profile: Path, project: Path, user_home: Path) -> None:
    write_global_command_guard_with_artifact(
        profile,
        "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply",
        "cross_agent_review_pass",
    )

    result = pre_tool(project, user_home, "comet-guard.sh demo build --apply")

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["failing_guards"][0]["failure_reason"] == "artifact_registry_invalid"


def test_hook_router_denies_missing_artifact_registry_as_invalid(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)

    assert_artifact_registry_invalid(profile, project, user_home)


def test_hook_router_denies_invalid_yaml_artifact_registry_as_invalid(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    profile.joinpath("artifacts.yaml").write_text("artifacts: [\n", encoding="utf-8")

    assert_artifact_registry_invalid(profile, project, user_home)


def test_hook_router_denies_duplicate_artifact_id_registry_as_invalid(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    artifacts = profile / "artifacts.yaml"
    declaration = artifacts.read_text(encoding="utf-8").split("artifacts:\n", 1)[1]
    artifacts.write_text(f"artifacts:\n{declaration}{declaration}", encoding="utf-8")

    assert_artifact_registry_invalid(profile, project, user_home)


def test_hook_router_denies_structurally_invalid_artifact_registry(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    profile.joinpath("artifacts.yaml").write_text("artifacts: invalid\n", encoding="utf-8")

    assert_artifact_registry_invalid(profile, project, user_home)


def test_global_command_guard_passes_with_short_head_artifact_path(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_short_head_cross_agent_review_artifacts(profile)
    write_global_command_guard_with_artifact(profile, "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply", "cross_agent_review_pass")
    write_cross_agent_review_marker(
        project,
        "add-guard-gate-binding",
        head_ref[:12],
        data={"status": "pass", "change": "add-guard-gate-binding", "head_ref": head_ref, "blocking_findings": 0, "report": "ok", "report_hash": "abc123"},
    )

    result = pre_tool_payload(
        project,
        user_home,
        {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "comet-guard.sh add-guard-gate-binding build --apply"}},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert (project / ".local" / "guard" / "evidence").exists()


def test_global_command_guard_skips_when_yaml_condition_matches(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    init_git_repo(project)
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: verify_requires_review
    description: 测试跳过条件。
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply'
      required_captures:
        - change
    skip_when:
      - yaml:
          path: openspec/changes/{change}/.comet.yaml
          field: workflow
          in:
            - hotfix
            - tweak
    evidence:
      artifact: cross_agent_review_pass
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: comet_cross_agent_review_required
""",
    )

    for workflow in ["hotfix", "tweak"]:
        change = f"quick-{workflow}"
        write_comet_state(project, change, workflow)
        result = pre_tool_payload(
            project,
            user_home,
            {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": f"comet-guard.sh {change} build --apply"}},
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = body(result)
        assert payload["status"] == "allow"
        global_audits = [
            audit
            for audit in read_project_audits(project)
            if audit["reason"] == "global_command_guard_skipped"
            and audit["detail"]["global_command_guard"]["captures"] == {"change": change}
        ]
        assert len(global_audits) == 1
        global_guard = global_audits[0]["detail"]["global_command_guard"]
        assert global_guard["matched_guard_ids"] == []
        assert global_guard["skipped_guard_ids"] == ["user:personal-policy:verify_requires_review"]
        assert global_guard["skipped_guards"][0] == {
            "effective_guard_id": "user:personal-policy:verify_requires_review",
            "source_scope": "user",
            "profile_id": "personal-policy",
            "guard_id": "verify_requires_review",
            "captures": {"change": change},
            "skip_reason": "skip_when_matched",
        }
        assert global_guard["captures_by_guard"]["user:personal-policy:verify_requires_review"] == {"change": change}


def test_global_command_guard_skip_when_falls_back_when_yaml_condition_does_not_match(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    init_git_repo(project)
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: verify_requires_review
    description: 测试跳过条件回退。
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply'
      required_captures:
        - change
    skip_when:
      - yaml:
          path: openspec/changes/{change}/.comet.yaml
          field: workflow
          in:
            - hotfix
            - tweak
    evidence:
      artifact: cross_agent_review_pass
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: comet_cross_agent_review_required
""",
    )

    cases = {
        "missing-state": None,
        "empty-yaml": "",
        "missing-workflow": "phase: build\n",
        "field-list": "workflow: [hotfix, tweak]\n",
        "boolean-workflow": "workflow: true\n",
        "yaml-list": "- workflow\n- tweak\n",
        "malformed-yaml": "workflow: [\n",
        "nonmatching-workflow": "workflow: full\nphase: build\n",
    }

    for change, state_text in cases.items():
        if state_text is not None:
            state = project / "openspec" / "changes" / change / ".comet.yaml"
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text(state_text, encoding="utf-8")

        result = pre_tool_payload(
            project,
            user_home,
            {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": f"comet-guard.sh {change} build --apply"}},
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = body(result)
        assert payload["status"] == "deny"
        assert payload["reason"] == "comet_cross_agent_review_required"
        assert payload["matched_guard_ids"] == ["user:personal-policy:verify_requires_review"]


def test_global_command_guard_skip_when_uses_later_matching_condition(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    init_git_repo(project)
    write_comet_state(project, "quick-hotfix", "hotfix")
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: verify_requires_review
    description: 测试多条件跳过。
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply'
      required_captures:
        - change
    skip_when:
      - yaml:
          path: openspec/changes/{change}/missing.yaml
          field: workflow
          in:
            - hotfix
      - yaml:
          path: openspec/changes/{change}/.comet.yaml
          field: workflow
          in:
            - hotfix
    evidence:
      artifact: cross_agent_review_pass
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: comet_cross_agent_review_required
""",
    )

    result = pre_tool_payload(
        project,
        user_home,
        {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "comet-guard.sh quick-hotfix build --apply"}},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    global_audits = [
        audit
        for audit in read_project_audits(project)
        if audit["reason"] == "global_command_guard_skipped"
    ]
    assert len(global_audits) == 1
    global_guard = global_audits[0]["detail"]["global_command_guard"]
    assert global_guard["skipped_guard_ids"] == ["user:personal-policy:verify_requires_review"]
    assert global_guard["skipped_guards"][0]["skip_reason"] == "skip_when_matched"


def test_global_command_guard_skip_when_unsafe_path_falls_back_to_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    init_git_repo(project)
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)

    unsafe_paths = {
        "parent-segment": "../openspec/changes/{change}/.comet.yaml",
        "absolute": "C:/Windows/win.ini",
    }
    for case, skip_path in unsafe_paths.items():
        change = f"unsafe-{case}"
        write_comet_state(project, change, "tweak")
        write_global_command_guard_yaml(
            profile,
            f"""
global_command_guards:
  - id: verify_requires_review
    description: 测试不安全跳过路径回退。
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply'
      required_captures:
        - change
    skip_when:
      - yaml:
          path: {skip_path}
          field: workflow
          in:
            - tweak
    evidence:
      artifact: cross_agent_review_pass
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: comet_cross_agent_review_required
""",
        )

        result = pre_tool_payload(
            project,
            user_home,
            {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": f"comet-guard.sh {change} build --apply"}},
        )

        assert result.returncode == 1, result.stdout + result.stderr
        payload = body(result)
        assert payload["status"] == "deny"
        assert payload["reason"] == "comet_cross_agent_review_required"
        assert payload["matched_guard_ids"] == ["user:personal-policy:verify_requires_review"]
        assert payload["skipped_guard_ids"] == []


def test_global_command_guard_reports_skipped_and_failing_guards_together(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    init_git_repo(project)
    write_comet_state(project, "mixed-change", "tweak")
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: skipped_review
    description: 测试被跳过的守卫。
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply'
      required_captures:
        - change
    skip_when:
      - yaml:
          path: openspec/changes/{change}/.comet.yaml
          field: workflow
          in:
            - tweak
    evidence:
      artifact: cross_agent_review_pass
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: comet_cross_agent_review_required
  - id: blocking_review
    description: 测试仍需证据的守卫。
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply'
      required_captures:
        - change
    evidence:
      artifact: cross_agent_review_pass
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: comet_cross_agent_review_required
""",
    )

    result = pre_tool_payload(
        project,
        user_home,
        {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "comet-guard.sh mixed-change build --apply"}},
    )

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "comet_cross_agent_review_required"
    assert payload["skipped_guard_ids"] == ["user:personal-policy:skipped_review"]
    assert payload["matched_guard_ids"] == ["user:personal-policy:blocking_review"]
    assert payload["failing_guards"][0]["effective_guard_id"] == "user:personal-policy:blocking_review"
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    global_guard = audit["detail"]["global_command_guard"]
    assert global_guard["skipped_guard_ids"] == ["user:personal-policy:skipped_review"]
    assert global_guard["failing_guards"][0]["effective_guard_id"] == "user:personal-policy:blocking_review"


def test_global_command_guard_denies_stale_review_pass_with_short_head_artifact_path(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_short_head_cross_agent_review_artifacts(profile)
    write_global_command_guard_with_artifact(profile, "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply", "cross_agent_review_pass")
    write_cross_agent_review_marker(
        project,
        "add-guard-gate-binding",
        head_ref[:12],
        data={"status": "pass", "change": "add-guard-gate-binding", "head_ref": "stale-head", "blocking_findings": 0, "report": "ok", "report_hash": "abc123"},
    )

    result = pre_tool_payload(
        project,
        user_home,
        {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "comet-guard.sh add-guard-gate-binding build --apply"}},
    )

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "comet_cross_agent_review_required"
    assert payload["failing_guards"][0]["failure_reason"] == "json_check_failed"
    assert payload["failing_guards"][0]["failed_checks"][0]["field"] == "head_ref"


def test_global_command_guard_pass_does_not_change_comet_phase(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    comet_state = project / "openspec" / "changes" / "add-guard-gate-binding" / ".comet.yaml"
    comet_state.parent.mkdir(parents=True)
    original_state = "phase: build\nverify_result: pending\n"
    comet_state.write_text(original_state, encoding="utf-8")
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    write_global_command_guard_with_artifact(profile, "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply", "cross_agent_review_pass")
    write_cross_agent_review_marker(
        project,
        "add-guard-gate-binding",
        head_ref,
        data={"status": "pass", "change": "add-guard-gate-binding", "head_ref": head_ref, "blocking_findings": 0, "report": "ok", "report_hash": "abc123"},
    )

    result = pre_tool_payload(
        project,
        user_home,
        {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "comet-guard.sh add-guard-gate-binding build --apply"}},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert comet_state.read_text(encoding="utf-8") == original_state


def test_global_command_guard_denies_when_artifact_missing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    write_global_command_guard_with_artifact(profile, "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply", "cross_agent_review_pass")

    result = pre_tool_payload(
        project,
        user_home,
        {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "comet-guard.sh add-guard-gate-binding build --apply"}},
    )

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "comet_cross_agent_review_required"
    assert payload["failing_guards"][0]["failure_reason"] == "evidence_missing"
    assert str(
        project
        / ".local"
        / "guard"
        / "evidence"
        / "personal-policy"
        / "cross_agent_review_pass"
        / "add-guard-gate-binding"
        / head_ref[:12]
        / "pass.json"
    ) in payload["failing_guards"][0]["evidence_path"]


def test_global_command_guard_denies_blocking_review_findings(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    write_global_command_guard_with_artifact(profile, "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply", "cross_agent_review_pass")
    write_cross_agent_review_marker(
        project,
        "add-guard-gate-binding",
        head_ref,
        data={"status": "pass", "change": "add-guard-gate-binding", "head_ref": head_ref, "blocking_findings": 1, "report": "has findings", "report_hash": "abc123"},
    )

    result = pre_tool_payload(
        project,
        user_home,
        {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "comet-guard.sh add-guard-gate-binding build --apply"}},
    )

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "comet_cross_agent_review_required"
    assert payload["failing_guards"][0]["failure_reason"] == "json_check_failed"
    assert payload["failing_guards"][0]["failed_checks"][0]["field"] == "blocking_findings"


def test_global_command_guard_denies_stale_review_pass_for_build_gate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    write_global_command_guard_with_artifact(profile, "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply", "cross_agent_review_pass")
    write_cross_agent_review_marker(
        project,
        "add-guard-gate-binding",
        head_ref,
        data={"status": "pass", "change": "add-guard-gate-binding", "head_ref": "stale-head", "blocking_findings": 0, "report": "ok", "report_hash": "abc123"},
    )

    result = pre_tool_payload(
        project,
        user_home,
        {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "comet-guard.sh add-guard-gate-binding build --apply"}},
    )

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "comet_cross_agent_review_required"
    assert payload["failing_guards"][0]["failure_reason"] == "json_check_failed"
    assert payload["failing_guards"][0]["failed_checks"][0]["field"] == "head_ref"


def test_planning_review_guard_denies_without_pass_marker(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    write_planning_review_profile(user_home)

    result = pre_tool(project, user_home, "comet-guard.sh add-comet-agent-review-gate design --apply")

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "comet_planning_review_required"
    failure = payload["failing_guards"][0]
    assert failure["failure_reason"] == "evidence_missing"
    assert failure["artifact_id"] == "planning_review_pass"
    assert str(project / ".local" / "guard" / "evidence" / "comet-review-gate" / "planning_review_pass" / "add-comet-agent-review-gate" / head_ref[:12] / "pass.json") in failure["evidence_path"]


def test_planning_review_guard_allows_with_valid_pass_marker(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    write_planning_review_profile(user_home)
    write_planning_review_pass(project, "add-comet-agent-review-gate", head_ref)

    result = pre_tool(project, user_home, "comet-guard.sh add-comet-agent-review-gate design --apply")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"


def test_planning_review_guard_matches_direct_path_env_and_wrapped_commands(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    write_planning_review_profile(user_home)
    write_planning_review_pass(project, "add-comet-agent-review-gate", head_ref)

    commands = [
        "comet-guard.sh add-comet-agent-review-gate design --apply",
        "/opt/comet/scripts/comet-guard.sh add-comet-agent-review-gate design --apply",
        "C:\\Users\\liuli\\.codex\\skills\\comet\\scripts\\comet-guard.sh add-comet-agent-review-gate design --apply",
        '"$COMET_BASH" "$COMET_GUARD" add-comet-agent-review-gate design --apply',
        "bash -lc '\"$COMET_GUARD\" add-comet-agent-review-gate design --apply'",
    ]

    for command in commands:
        result = pre_tool(project, user_home, command)

        assert result.returncode == 0, result.stdout + result.stderr
        payload = body(result)
        assert payload["status"] == "allow"
        global_audits = [
            audit
            for audit in read_project_audits(project)
            if audit["reason"] == "global_command_guard_passed"
            and audit["detail"]["global_command_guard"]["command"] == command
        ]
        assert len(global_audits) == 1
        assert global_audits[0]["detail"]["global_command_guard"]["matched_guard_ids"] == [
            "user:comet-review-gate:comet_design_requires_planning_review"
        ]


def test_planning_review_guard_denies_stale_pass_marker(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    write_planning_review_profile(user_home)
    stale_data = planning_review_pass_data("add-comet-agent-review-gate", "stale-head")
    write_planning_review_pass(project, "add-comet-agent-review-gate", head_ref, stale_data)

    result = pre_tool(project, user_home, "comet-guard.sh add-comet-agent-review-gate design --apply")

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "comet_planning_review_required"
    failure = payload["failing_guards"][0]
    assert failure["failure_reason"] == "json_check_failed"
    assert failure["failed_checks"][0]["field"] == "head_ref"


def test_planning_review_guard_denies_invalid_pass_marker_fields(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    write_planning_review_profile(user_home)
    cases = [
        ("bad-status", {"status": "fail"}, "status"),
        ("bad-producer", {"producer": "other-review"}, "producer"),
        ("bad-artifact", {"artifact_id": "cross_agent_review_pass"}, "artifact_id"),
        ("bad-subject", {"subject_id": "other-change"}, "subject_id"),
        ("blocking-findings", {"blocking_findings": 1}, "blocking_findings"),
        ("missing-scope", {"scope": None}, "scope"),
        ("missing-report-hash", {"report_hash": None}, "report_hash"),
    ]

    for change, overrides, failed_field in cases:
        data = planning_review_pass_data(change, head_ref)
        for key, value in overrides.items():
            if value is None:
                data.pop(key)
            else:
                data[key] = value
        write_planning_review_pass(project, change, head_ref, data)

        result = pre_tool(project, user_home, f"comet-guard.sh {change} design --apply")

        assert result.returncode == 1, result.stdout + result.stderr
        payload = body(result)
        assert payload["status"] == "deny"
        assert payload["reason"] == "comet_planning_review_required"
        failure = payload["failing_guards"][0]
        assert failure["failure_reason"] == "json_check_failed"
        assert failure["failed_checks"][0]["field"] == failed_field


def test_global_command_guard_denies_unknown_artifact_reference(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    write_global_command_guard_with_artifact(profile, "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply", "missing_review_pass")
    write_cross_agent_review_marker(
        project,
        "add-guard-gate-binding",
        head_ref,
        data={"status": "pass", "change": "add-guard-gate-binding", "head_ref": head_ref, "blocking_findings": 0, "report": "ok", "report_hash": "abc123"},
    )

    result = pre_tool_payload(
        project,
        user_home,
        {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "comet-guard.sh add-guard-gate-binding build --apply"}},
    )

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "comet_cross_agent_review_required"
    assert payload["failing_guards"][0]["failure_reason"] == "artifact_reference_missing"
    assert payload["failing_guards"][0]["artifact_id"] == "missing_review_pass"


def test_user_global_command_guard_uses_project_runtime_for_artifact_scope(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    head_ref = init_git_repo(project)
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_cross_agent_review_artifacts(profile)
    write_global_command_guard_with_artifact(profile, "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) build --apply", "cross_agent_review_pass")
    write_user_scope_cross_agent_review_marker(
        user_home,
        "add-guard-gate-binding",
        head_ref,
        data={"status": "pass", "change": "add-guard-gate-binding", "head_ref": head_ref, "blocking_findings": 0, "report": "ok", "report_hash": "abc123"},
    )

    result = pre_tool_payload(
        project,
        user_home,
        {"session_id": "session-1", "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": "comet-guard.sh add-guard-gate-binding build --apply"}},
    )

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["failing_guards"][0]["failure_reason"] == "evidence_missing"
    assert payload["failing_guards"][0]["evidence_path"].startswith(str(project / ".local"))


def test_global_command_guard_uses_named_capture_value_from_json_check(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: verify_requires_review
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply'
      required_captures:
        - change
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{change}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
      - field: change
        predicate: equals
        value_from: change
    deny:
      reason: global_command_guard_required
""",
    )
    write_guard_evidence(
        project,
        "project",
        "repo-policy",
        "verify_requires_review",
        "add-guard-gate-binding",
        data={"status": "pass", "change": "add-guard-gate-binding"},
    )

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_global_command_guard_denies_when_any_matching_guard_fails(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    project_profile = project / ".agents" / "guards" / "repo-policy"
    user_profile = user_home / ".agents" / "guards" / "personal-policy"
    project_profile.mkdir(parents=True)
    user_profile.mkdir(parents=True)
    pattern = "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply"
    write_global_command_guard(project_profile, "verify_requires_review", pattern)
    write_global_command_guard(user_profile, "verify_requires_review", pattern)
    write_guard_evidence(
        project,
        "project",
        "repo-policy",
        "verify_requires_review",
        "add-guard-gate-binding",
        data={"status": "pass"},
    )

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 1
    payload = body(result)
    assert sorted(payload["matched_guard_ids"]) == [
        "project:repo-policy:verify_requires_review",
        "user:personal-policy:verify_requires_review",
    ]
    assert [item["effective_guard_id"] for item in payload["failing_guards"]] == ["user:personal-policy:verify_requires_review"]
    assert ".local" in payload["failing_guards"][0]["evidence_path"]


def test_global_command_guard_denies_stale_head_ref_from_git_head(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    subprocess.run(["git", "init"], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    (project / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"],
        cwd=project,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: verify_requires_review
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply'
      required_captures:
        - change
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{change}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
      - field: head_ref
        predicate: equals
        value_from: git_head
    deny:
      reason: global_command_guard_required
""",
    )
    write_guard_evidence(
        project,
        "project",
        "repo-policy",
        "verify_requires_review",
        "add-guard-gate-binding",
        data={"status": "pass", "head_ref": "stale-head"},
    )

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["failing_guards"][0]["failed_checks"][0]["field"] == "head_ref"


def test_global_command_guard_denies_missing_required_capture(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: verify_requires_review
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh [A-Za-z0-9._-]+ verify --apply'
      required_captures:
        - change
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{change}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: global_command_guard_required
""",
    )

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "global_command_guard_required"
    assert payload["failing_guards"][0]["failure_reason"] == "required_capture_missing"
    assert payload["failing_guards"][0]["missing_captures"] == ["change"]


def test_user_global_command_guard_uses_project_runtime_for_project_command(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply")
    write_guard_evidence(
        project,
        "user",
        "personal-policy",
        "verify_requires_review",
        "add-guard-gate-binding",
        data={"status": "pass"},
    )

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert str(payload["audit_path"]).startswith(str(project / ".local" / "guard" / "audit"))
    assert not (user_home / ".agents" / "guard" / "evidence").exists()


def test_project_comet_command_ignores_user_runtime_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply")
    write_user_guard_evidence(
        user_home,
        "user",
        "personal-policy",
        "verify_requires_review",
        "add-guard-gate-binding",
        data={"status": "pass"},
    )

    result = pre_tool_payload(
        project,
        user_home,
        {
            "session_id": "session-1",
            "cwd": str(user_home),
            "tool_name": "Bash",
            "tool_input": {"command": "comet-guard.sh add-guard-gate-binding verify --apply"},
        },
    )

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["failing_guards"][0]["failure_reason"] == "evidence_missing"
    assert str(project / ".local" / "guard" / "evidence") in payload["failing_guards"][0]["evidence_path"]


def test_explicit_user_runtime_scope_uses_user_guard_runtime(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = user_home / ".agents" / "guards" / "personal-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply")
    write_user_guard_evidence(
        user_home,
        "user",
        "personal-policy",
        "verify_requires_review",
        "add-guard-gate-binding",
        data={"status": "pass"},
    )

    result = pre_tool_payload(
        project,
        user_home,
        {
            "session_id": "session-1",
            "cwd": str(project),
            "runtime_scope": "user",
            "tool_name": "Bash",
            "tool_input": {"command": "comet-guard.sh add-guard-gate-binding verify --apply"},
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert str(payload["audit_path"]).startswith(str(user_home / ".agents" / "guard" / "audit"))


def test_global_command_guard_rejects_capture_path_traversal_outside_evidence_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: verify_requires_review
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._/-]+) verify --apply'
      required_captures:
        - change
    evidence:
      path: '.local/guard/evidence/{change}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: global_command_guard_required
""",
    )
    outside_evidence = project / ".local" / "guard" / "outside" / "evidence.json"
    outside_evidence.parent.mkdir(parents=True)
    outside_evidence.write_text(json.dumps({"status": "pass"}, ensure_ascii=False), encoding="utf-8")

    result = pre_tool(project, user_home, "comet-guard.sh ../outside verify --apply")

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["failing_guards"][0]["failure_reason"] == "unsafe_evidence_path"
    assert payload["failing_guards"][0]["evidence_path"].startswith(str(project / ".local" / "guard" / "evidence"))


def test_global_command_guard_rejects_absolute_evidence_path(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    outside_evidence = tmp_path / "outside-evidence.json"
    outside_evidence.write_text(json.dumps({"status": "pass"}, ensure_ascii=False), encoding="utf-8")
    write_global_command_guard_yaml(
        profile,
        f"""
global_command_guards:
  - id: verify_requires_review
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply'
    evidence:
      path: '{outside_evidence.as_posix()}'
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: global_command_guard_required
""",
    )

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["failing_guards"][0]["failure_reason"] == "unsafe_evidence_path"


def test_global_command_guard_reports_unreadable_evidence_separately_from_invalid_json(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply")
    evidence_directory = (
        project
        / ".local"
        / "guard"
        / "evidence"
        / "project"
        / "repo-policy"
        / "verify_requires_review"
        / "add-guard-gate-binding"
        / "evidence.json"
    )
    evidence_directory.mkdir(parents=True)

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    failure = payload["failing_guards"][0]
    assert failure["failure_reason"] == "evidence_unreadable"
    assert failure["error_type"] in {"IsADirectoryError", "PermissionError", "OSError"}
    assert "error" not in failure


def test_pre_tool_use_without_global_command_guard_match_keeps_existing_session_focus_behavior(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply")

    result = pre_tool(project, user_home, "git status")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert payload["reason"] == "no_session_focus_instance"
    assert len(list((project / ".local" / "guard" / "audit").glob("*.json"))) == 1


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


def test_global_command_guard_allow_does_not_bypass_session_focus_deny(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_state_machine(profile, "deny")
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: push_requires_evidence
    tool: Bash
    match:
      command_patterns:
        - 'git push (?P<branch>[A-Za-z0-9._/-]+)'
      required_captures:
        - branch
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{branch}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: global_command_guard_required
""",
    )
    write_guard_evidence(project, "project", "minimal-sample", "push_requires_evidence", "main", data={"status": "pass"})
    session_start(project, user_home)
    activate(project, user_home)

    result = pre_tool(project, user_home, "git push main")

    assert result.returncode == 1
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "当前状态要求 deny。"
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["detail"]["kind"] == "session_focus_permission"


def write_state_machine_with_guard_point_only(profile: Path) -> None:
    profile.joinpath("state-machine.yaml").write_text(
        """
initial_state: open
terminal_states:
  - closed
states:
  - id: open
    description: Guard Profile（守卫画像）已激活。
  - id: closed
    description: Guard Profile（守卫画像）已关闭。
transitions:
  - id: close_after_guard_point
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
""".lstrip(),
        encoding="utf-8",
    )


def write_completion_note(project: Path, instance_id: str) -> None:
    path = project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "1" / "completion-note.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"value": "完成"}, ensure_ascii=False), encoding="utf-8")


def completion_note_path(project: Path, instance_id: str) -> Path:
    return project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "1" / "completion-note.json"


def write_completion_note_json(project: Path, instance_id: str, data: dict | list) -> None:
    path = completion_note_path(project, instance_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def write_completion_note_text(project: Path, instance_id: str, content: str) -> None:
    path = completion_note_path(project, instance_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json_guard_point(profile: Path, checks_yaml: str) -> None:
    profile.joinpath("guard-points.yaml").write_text(
        f"""
guard_points:
  - id: completion_note_present
    description: JSON artifact 必须满足字段断言。
    checks:
{checks_yaml}
""".lstrip(),
        encoding="utf-8",
    )


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


def test_invalid_and_multiple_focus_bindings_error_without_permission_deny(tmp_path: Path) -> None:
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
    assert invalid_body["status"] == "invalid_session_focus_binding"
    assert invalid_body["reason"] == "invalid_session_focus_binding"
    invalid_audit = json.loads(Path(invalid_body["audit_path"]).read_text(encoding="utf-8"))
    assert invalid_audit["status"] == "error"

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
    assert multiple_body["status"] == "multiple_session_focus_bindings"
    assert multiple_body["reason"] == "multiple_session_focus_bindings"
    multiple_audit = json.loads(Path(multiple_body["audit_path"]).read_text(encoding="utf-8"))
    assert multiple_audit["status"] == "error"


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

    read_brief(project, user_home)
    terminal = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])
    assert terminal.returncode == 1, terminal.stdout + terminal.stderr
    terminal_body = body(terminal)
    assert terminal_body["status"] == "error"
    assert terminal_body["reason"] == "terminal_state_completed"
    assert terminal_body["current_state"] == "closed"

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


def test_state_completed_evaluates_guard_points_before_advancing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 必须失败的守卫点。
    checks:
      - id: impossible_artifact
        type: artifact_exists
        artifact: missing_artifact
        failure_reason: 缺少 impossible artifact。
        fix_hint: 提供 impossible artifact。
    override_policy:
      allowed: false
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "error"
    assert payload["reason"] == "guard_failed"
    assert payload["guard_point_id"] == "completion_note_present"
    assert payload["check_id"] == "impossible_artifact"
    assert payload["current_state"] == "open"
    details = payload["details"]
    assert details["guard_point_id"] == "completion_note_present"
    assert details["failure_reason"] == "缺少 impossible artifact。"
    assert details["current_state"] == "open"
    assert details["required_conditions"] == ["artifact_exists:missing_artifact"]
    assert details["fix_hint"] == "提供 impossible artifact。"
    assert details["override_allowed"] is False
    assert Path(details["override_record_path"]).parts[-4:] == ("overrides", "minimal-sample", instance_id, "completion_note_present.json")
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "open"


def test_state_completed_allows_json_artifact_equals_check(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: JSON artifact 必须满足字段断言。
    checks:
      - id: completion_status_done
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: equals
        value: done
        failure_reason: completion note 状态不正确。
        fix_hint: 更新 completion note。
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    path = project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "1" / "completion-note.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": "done"}, ensure_ascii=False), encoding="utf-8")
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert payload["reason"] == "state_completed"
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"


def test_state_completed_blocks_json_artifact_equals_check_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: JSON artifact 必须满足字段断言。
    checks:
      - id: completion_status_done
        type: json_artifact
        artifact: completion_note
        field: security_review.tool
        predicate: equals
        value: codex-security
        failure_reason: security review 工具不正确。
        fix_hint: 更新 security review artifact。
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    path = project / ".local" / "guard" / "artifacts" / "minimal-sample" / instance_id / "1" / "completion-note.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"security_review": {"tool": "manual"}}, ensure_ascii=False), encoding="utf-8")
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "error"
    assert payload["reason"] == "guard_failed"
    assert payload["guard_point_id"] == "completion_note_present"
    assert payload["check_id"] == "completion_status_done"
    details = payload["details"]
    assert details["failure_reason"] == "security review 工具不正确。"
    assert details["json_check"] == {
        "artifact": "completion_note",
        "field": "security_review.tool",
        "predicate": "equals",
        "expected": "codex-security",
        "actual": "manual",
    }
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "open"


def test_state_completed_supports_json_exists_and_value_predicates(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_exists
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: exists
      - id: review_status_passes
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: equals
        value: pass
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_does_not_accept_expected_config_key_for_json_value(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_passes
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: equals
        expected: pass
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact_check"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "review.status",
        "predicate": "equals",
        "actual": "pass",
    }


def test_state_completed_blocks_json_not_equals_with_legacy_expected_config_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_not_blocked
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: not_equals
        expected: blocked
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact_check"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "review.status",
        "predicate": "not_equals",
        "actual": "pass",
    }


def test_state_completed_blocks_json_not_equals_without_value(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_not_blocked
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: not_equals
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact_check"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "review.status",
        "predicate": "not_equals",
        "actual": "pass",
    }


def test_state_completed_supports_json_not_equals_predicate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_not_blocked
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: not_equals
        value: blocked
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_blocks_json_not_equals_predicate_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_not_blocked
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: not_equals
        value: blocked
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"status": "blocked"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "review.status",
        "predicate": "not_equals",
        "expected": "blocked",
        "actual": "blocked",
    }


def test_state_completed_blocks_json_missing_field(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: review_status_exists
        type: json_artifact
        artifact: completion_note
        field: review.status
        predicate: exists
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"review": {"result": "pass"}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "json_artifact_check_failed"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "review.status",
        "predicate": "exists",
    }


def test_state_completed_supports_json_number_predicates(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: p0_count_within_limit
        type: json_artifact
        artifact: completion_note
        field: findings.p0
        predicate: number_lte
        value: 0
      - id: confidence_high_enough
        type: json_artifact
        artifact: completion_note
        field: confidence
        predicate: number_gte
        value: 0.8
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"findings": {"p0": 0}, "confidence": 0.9})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_blocks_json_number_predicate_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: p0_count_within_limit
        type: json_artifact
        artifact: completion_note
        field: findings.p0
        predicate: number_lte
        value: 0
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"findings": {"p0": 1}})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "findings.p0",
        "predicate": "number_lte",
        "expected": 0,
        "actual": 1,
    }


def test_state_completed_supports_json_array_none_predicate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: no_blocking_findings
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_none
        where:
          field: severity
          predicate: equals
          value: P0
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"findings": [{"severity": "P2"}, {"severity": "P3"}]})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_blocks_json_array_none_predicate_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: no_blocking_findings
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_none
        where:
          field: severity
          predicate: equals
          value: P0
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    findings = [{"severity": "P0"}, {"severity": "P2"}]
    write_completion_note_json(project, instance_id, {"findings": findings})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "findings",
        "predicate": "array_none",
        "expected": "no matching elements",
        "actual": findings,
    }


def test_state_completed_blocks_json_array_none_where_with_legacy_expected_config_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: no_blocking_findings
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_none
        where:
          field: severity
          predicate: equals
          expected: P0
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    findings = [{"severity": "P0"}, {"severity": "P2"}]
    write_completion_note_json(project, instance_id, {"findings": findings})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact_check"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "findings",
        "predicate": "equals",
        "actual": findings,
    }


def test_state_completed_supports_json_array_all_predicate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: all_findings_triaged
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_all
        where:
          field: triaged
          predicate: equals
          value: true
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"findings": [{"triaged": True}, {"triaged": True}]})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_supports_json_array_where_exists_when_value_is_null(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: all_findings_have_resolution
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_all
        where:
          field: resolution
          predicate: exists
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"findings": [{"resolution": None}, {"resolution": "accepted"}]})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert body(result)["status"] == "allow"


def test_state_completed_blocks_json_array_all_predicate_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: all_findings_triaged
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_all
        where:
          field: triaged
          predicate: equals
          value: true
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    findings = [{"triaged": True}, {"triaged": False}]
    write_completion_note_json(project, instance_id, {"findings": findings})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "findings",
        "predicate": "array_all",
        "expected": "all elements match",
        "actual": findings,
    }


def test_state_completed_blocks_json_array_all_where_without_value(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: all_findings_triaged
        type: json_artifact
        artifact: completion_note
        field: findings
        predicate: array_all
        where:
          field: triaged
          predicate: equals
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    findings = [{"triaged": True}, {"triaged": True}]
    write_completion_note_json(project, instance_id, {"findings": findings})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact_check"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "findings",
        "predicate": "equals",
        "actual": findings,
    }


def test_state_completed_blocks_invalid_json_artifact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: status_passes
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: equals
        value: pass
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_text(project, instance_id, "{broken")
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "invalid_json_artifact"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "status",
        "predicate": "equals",
        "expected": "pass",
    }
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["detail"]["details"]["json_check"] == payload["details"]["json_check"]


def test_state_completed_blocks_json_artifact_absolute_path_outside_runtime_artifacts_without_leak(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    outside = tmp_path / "outside-secret.json"
    secret = "outside-json-secret-should-not-leak"
    outside.write_text(json.dumps({"secret": secret}, ensure_ascii=False), encoding="utf-8")
    profile.joinpath("artifacts.yaml").write_text(
        f"""
artifacts:
  - id: completion_note
    type: note
    path: '{outside.as_posix()}'
""".lstrip(),
        encoding="utf-8",
    )
    write_json_guard_point(
        profile,
        """
      - id: secret_matches
        type: json_artifact
        artifact: completion_note
        field: secret
        predicate: equals
        value: allowed
""",
    )
    session_start(project, user_home)
    activate(project, user_home)
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    assert secret not in result.stdout
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "json_artifact_path_outside_runtime_artifacts"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "secret",
        "predicate": "equals",
        "expected": "allowed",
    }
    audit_text = Path(payload["audit_path"]).read_text(encoding="utf-8")
    assert secret not in audit_text


def test_state_completed_blocks_missing_json_artifact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_state_machine_with_guard_point_only(profile)
    write_json_guard_point(
        profile,
        """
      - id: status_passes
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: equals
        value: pass
""",
    )
    session_start(project, user_home)
    activate(project, user_home)
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "missing_required_artifacts"
    assert payload["details"]["missing_artifacts"] == ["completion_note"]
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "status",
        "predicate": "equals",
        "expected": "pass",
    }


def test_state_completed_blocks_unsupported_json_artifact_predicate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_json_guard_point(
        profile,
        """
      - id: status_matches
        type: json_artifact
        artifact: completion_note
        field: status
        predicate: matches_regex
        value: pass
""",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note_json(project, instance_id, {"status": "pass"})
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "unsupported_json_artifact_predicate"
    assert payload["details"]["json_check"] == {
        "artifact": "completion_note",
        "field": "status",
        "predicate": "matches_regex",
        "expected": "pass",
        "actual": "pass",
    }


def test_state_completed_reports_supported_guard_point_check_types(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 守卫点包含不支持的检查类型。
    checks:
      - id: unsupported
        type: shell_command
        artifact: completion_note
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["reason"] == "guard_failed"
    assert payload["details"]["failure_reason"] == "unsupported_guard_point_check"
    assert payload["details"]["fix_hint"] == "Runtime（运行时）当前支持 artifact_exists 和 json_artifact 检查。"
    assert payload["details"]["required_conditions"] == ["supported_check:artifact_exists", "supported_check:json_artifact"]


def test_state_completed_allows_guard_point_failure_with_valid_override(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 可人工覆盖的守卫点。
    allow_override: true
    checks:
      - id: impossible_artifact
        type: artifact_exists
        artifact: missing_artifact
        failure_reason: 缺少 impossible artifact。
        fix_hint: 提供 impossible artifact。
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    override_path = project / ".local" / "guard" / "overrides" / "minimal-sample" / instance_id / "completion_note_present.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(
        json.dumps(
            {
                "decision": "allow",
                "reason": "人工确认允许跳过该守卫点。",
                "approved_by": "test-user",
                "approved_at": "2026-06-16T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert payload["reason"] == "state_completed"
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["reason"] == "state_completed"
    assert audit["detail"]["overrides"][0]["guard_point_id"] == "completion_note_present"
    assert audit["detail"]["overrides"][0]["override_record_path"] == str(override_path)


def test_state_completed_allows_profile_level_override(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    manifest = profile.joinpath("GUARD-MANIFEST.yaml")
    manifest.write_text(manifest.read_text(encoding="utf-8") + "allow_override: true\n", encoding="utf-8")
    profile.joinpath("guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 由画像级配置允许覆盖。
    checks:
      - id: impossible_artifact
        type: artifact_exists
        artifact: missing_artifact
        failure_reason: 缺少 impossible artifact。
        fix_hint: 提供 impossible artifact。
""".lstrip(),
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    override_path = project / ".local" / "guard" / "overrides" / "minimal-sample" / instance_id / "completion_note_present.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(
        json.dumps(
            {
                "decision": "allow",
                "reason": "画像级配置允许跳过该守卫点。",
                "approved_by": "test-user",
                "approved_at": "2026-06-16T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert payload["reason"] == "state_completed"
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "closed"
    audit = json.loads(Path(payload["audit_path"]).read_text(encoding="utf-8"))
    assert audit["detail"]["overrides"][0]["override_record_path"] == str(override_path)


def test_profile_level_override_does_not_allow_missing_guard_point(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    manifest = profile.joinpath("GUARD-MANIFEST.yaml")
    manifest.write_text(manifest.read_text(encoding="utf-8") + "allow_override: true\n", encoding="utf-8")
    profile.joinpath("guard-points.yaml").write_text("guard_points: []\n", encoding="utf-8")
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    override_path = project / ".local" / "guard" / "overrides" / "minimal-sample" / instance_id / "completion_note_present.json"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(
        json.dumps(
            {
                "decision": "allow",
                "reason": "缺失守卫点不应被覆盖。",
                "approved_by": "test-user",
                "approved_at": "2026-06-16T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "error"
    assert payload["reason"] == "guard_failed"
    assert payload["guard_point_id"] == "completion_note_present"
    assert payload["failure_reason"] == "missing_guard_point"
    assert payload["override_allowed"] is False
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "open"


def test_state_completed_rejects_ambiguous_transition_matches(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    state_machine = profile.joinpath("state-machine.yaml")
    state_machine.write_text(
        state_machine.read_text(encoding="utf-8")
        + """
  - id: also_close_after_note
    from: open
    to: closed
    on_event: state_completed
    guard_points:
      - completion_note_present
    required_artifacts:
      - completion_note
""",
        encoding="utf-8",
    )
    session_start(project, user_home)
    activated = activate(project, user_home)
    instance_id = activated["instance_id"]
    write_completion_note(project, instance_id)
    read_brief(project, user_home)

    result = run_cli(["state-completed", "--project", str(project), "--user-home", str(user_home), "--source", "codex", "--session-id", "session-1"])

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "error"
    assert payload["reason"] == "ambiguous_state_transition"
    assert payload["candidate_transition_ids"] == ["close_after_note", "also_close_after_note"]
    state = json.loads((project / ".local" / "guard" / "state" / "minimal-sample" / instance_id / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "open"
