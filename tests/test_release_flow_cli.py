import importlib.util
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

from tests.support.git_templates import copy_template


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "release-flow"
    / "skills"
    / "release-flow"
    / "scripts"
    / "release_flow.py"
)
_RELEASE_FLOW_MODULE = None
TEMPLATE_ROOT = Path(tempfile.gettempdir()) / "release-flow-test-templates-v3"
TEMPLATE_LOCK_TIMEOUT_SECONDS = 30
TEMPLATE_LOCK_STALE_SECONDS = 30


def run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    module = load_release_flow_module()
    stdout = io.StringIO()
    stderr = io.StringIO()
    previous_env = os.environ.copy()
    if env is not None:
        os.environ.clear()
        os.environ.update(env)
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                returncode = int(module.main(args))
            except SystemExit as error:
                returncode = error.code if isinstance(error.code, int) else 1
    finally:
        if env is not None:
            os.environ.clear()
            os.environ.update(previous_env)
    return subprocess.CompletedProcess(
        [sys.executable, str(SCRIPT), *args],
        returncode,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_manifest(path: Path, version: str) -> None:
    write_json(path, {"version": version})


def write_plugin_manifests(project: Path, plugin: str, version: str) -> None:
    write_manifest(project / "plugins" / plugin / ".codex-plugin" / "plugin.json", version)
    write_manifest(project / "plugins" / plugin / ".claude-plugin" / "plugin.json", version)


def load_release_flow_module():
    global _RELEASE_FLOW_MODULE
    if _RELEASE_FLOW_MODULE is not None:
        return _RELEASE_FLOW_MODULE
    spec = importlib.util.spec_from_file_location("release_flow_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _RELEASE_FLOW_MODULE = module
    return module


def git(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(project), *args],
        check=False,
        text=True,
        capture_output=True,
    )


def project_tree_cache_key(project: Path) -> str:
    digest = hashlib.sha256()
    digest.update(Path(__file__).read_bytes())
    for path in sorted(project.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        digest.update(path.relative_to(project).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def remove_template_lock(lock_dir: Path) -> None:
    for _ in range(5):
        shutil.rmtree(lock_dir, ignore_errors=True)
        if not lock_dir.exists():
            return
        time.sleep(0.05)


def copy_project_remote_template(template_dir: Path, project: Path, remote: Path) -> None:
    copy_template(template_dir / "remote.git", remote)
    copy_template(template_dir / "project", project)
    assert git(project, "remote", "set-url", "origin", str(remote)).returncode == 0


def _init_project_with_remote_uncached(project: Path, remote: Path) -> None:
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(remote)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert git(project, "init").returncode == 0
    assert git(project, "config", "user.email", "test@example.com").returncode == 0
    assert git(project, "config", "user.name", "Test").returncode == 0
    assert git(project, "add", ".").returncode == 0
    assert git(project, "commit", "-m", "baseline").returncode == 0
    assert git(project, "remote", "add", "origin", str(remote)).returncode == 0
    assert git(project, "push", "origin", "HEAD:refs/heads/main").returncode == 0
    assert git(project, "push", "origin", "HEAD:refs/heads/marketplace").returncode == 0
    assert git(project, "fetch", "origin", "marketplace").returncode == 0


def init_project_with_remote(project: Path, remote: Path) -> None:
    template_dir = TEMPLATE_ROOT / project_tree_cache_key(project)
    ready = template_dir / ".ready"
    lock_dir = TEMPLATE_ROOT / f"{template_dir.name}.lock"
    if ready.exists():
        if lock_dir.exists():
            remove_template_lock(lock_dir)
        copy_project_remote_template(template_dir, project, remote)
        return

    deadline = time.monotonic() + TEMPLATE_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock_dir.mkdir(parents=True)
            break
        except FileExistsError:
            try:
                lock_age = time.time() - lock_dir.stat().st_mtime
            except FileNotFoundError:
                continue
            if lock_age > TEMPLATE_LOCK_STALE_SECONDS:
                remove_template_lock(lock_dir)
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"template_lock_timeout: {lock_dir}")
            time.sleep(0.05)

    try:
        if not ready.exists():
            if template_dir.exists():
                shutil.rmtree(template_dir)
            template_dir.mkdir(parents=True, exist_ok=True)
            template_project = copy_template(project, template_dir / "project")
            template_remote = template_dir / "remote.git"
            _init_project_with_remote_uncached(template_project, template_remote)
            ready.write_text("ok\n", encoding="utf-8")
    finally:
        remove_template_lock(lock_dir)

    copy_project_remote_template(template_dir, project, remote)


def write_release_flow_files(project: Path, projection: str | None = None) -> None:
    release_flow = project / ".release-flow"
    release_flow.mkdir(parents=True, exist_ok=True)
    (release_flow / "config.yaml").write_text(
        """version: 1

release:
  sourceRef: main
  channelBranch: marketplace
  branchMode: remote-only

workflow:
  file: .github/workflows/release.yml
  trigger: workflow_dispatch

github:
  actions:
    workflowPermissions: read-and-write
""",
        encoding="utf-8",
    )
    (release_flow / "projection.yaml").write_text(
        projection or marketplace_identity_projection(),
        encoding="utf-8",
    )


def marketplace_identity_projection(extra_variables: str = "", transforms: str = "") -> str:
    return f"""version: 1

identity:
  codex:
    marketplaceName: my-agent-skills-marketplace
    displayName: My Agent Skills Marketplace
  claude:
    marketplaceName: my-agent-skills-marketplace
    ownerName: My Agent Skills Marketplace

variables:
{extra_variables or "  {}"}
generators:
  - path: .agents/plugins/marketplace.json
    type: codex-marketplace
    identity: codex
    plugins:
      - agent-guard
      - release-flow

transforms:
{transforms or "  []"}
"""


def test_setup_dry_run_does_not_write_project_files(tmp_path: Path) -> None:
    project = tmp_path / "project"

    result = run("setup", "--project", str(project))

    assert result.returncode == 0
    assert "status: dry_run" in result.stdout
    assert "would_write: .release-flow/config.yaml" in result.stdout
    assert "would_write: .release-flow/projection.yaml" in result.stdout
    assert "would_write: .release-flow/.gitignore" not in result.stdout
    assert "would_write: .github/workflows/release.yml" in result.stdout
    assert not (project / ".release-flow").exists()
    assert not (project / ".github").exists()


def test_setup_authorized_writes_only_config_projection_gitignore_and_workflow(tmp_path: Path) -> None:
    project = tmp_path / "project"

    result = run("setup", "--project", str(project), "--authorize-project-files")

    assert result.returncode == 0
    assert "status: setup_complete" in result.stdout
    assert (project / ".release-flow" / "config.yaml").is_file()
    assert (project / ".release-flow" / "projection.yaml").is_file()
    assert not (project / ".release-flow" / ".gitignore").exists()
    assert (project / ".github" / "workflows" / "release.yml").is_file()
    assert not (project / ".release-flow" / "releases").exists()
    assert not (project / "scripts" / "release-flow").exists()


def test_github_plan_outputs_expected_settings(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("github-plan", "--project", str(project))

    assert result.returncode == 0
    assert "status: github_plan" in result.stdout
    assert "actions_workflow_permissions: read-and-write" in result.stdout
    assert "rulesets:" not in result.stdout
    assert "branch_protection_fallback:" not in result.stdout
    assert "actions_variables:" not in result.stdout
    assert "CODEX_MARKETPLACE_CATALOG_NAME" not in result.stdout


def test_github_plan_does_not_print_marketplace_identity_variables(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project, marketplace_identity_projection())

    result = run("github-plan", "--project", str(project))

    assert result.returncode == 0
    for variable in [
        "CODEX_MARKETPLACE_CATALOG_NAME",
        "CODEX_MARKETPLACE_DISPLAY_NAME",
        "CLAUDE_MARKETPLACE_CATALOG_NAME",
        "CLAUDE_MARKETPLACE_OWNER_NAME",
        "RELEASE_FLOW_PLUGIN_REPOSITORY",
        "RELEASE_FLOW_PLUGIN_REF",
    ]:
        assert variable not in result.stdout


def test_current_repo_release_flow_files_are_valid() -> None:
    result = run("validate", "--project", str(REPO_ROOT))

    assert result.returncode == 0
    assert "status: verified" in result.stdout
    assert not (REPO_ROOT / ".release-flow" / ".gitignore").exists()
    assert (REPO_ROOT / ".github" / "workflows" / "release.yml").is_file()


def test_current_repo_release_flow_config_does_not_list_manifest_versions() -> None:
    config = yaml.safe_load((REPO_ROOT / ".release-flow" / "config.yaml").read_text(encoding="utf-8"))

    assert "manifests" not in config
    assert "records" not in config
    assert "rulesets" not in config.get("github", {})


def test_current_repo_projection_does_not_register_marketplace_variables() -> None:
    result = run("github-plan", "--project", str(REPO_ROOT))

    assert result.returncode == 0
    for variable in [
        "CODEX_MARKETPLACE_CATALOG_NAME",
        "CODEX_MARKETPLACE_DISPLAY_NAME",
        "CLAUDE_MARKETPLACE_CATALOG_NAME",
        "CLAUDE_MARKETPLACE_OWNER_NAME",
        "RELEASE_FLOW_PLUGIN_REPOSITORY",
        "RELEASE_FLOW_PLUGIN_REF",
    ]:
        assert variable not in result.stdout


def test_configure_github_requires_authorization(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("configure-github", "--project", str(project))

    assert result.returncode == 2
    assert "configure_github_requires_authorize_github" in result.stdout


def test_configure_github_dry_run_prints_manual_steps(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("configure-github", "--project", str(project), "--dry-run")

    assert result.returncode == 0
    assert "status: manual_steps" in result.stdout
    assert "Set Actions workflow permissions to read-and-write" in result.stdout
    assert "Rulesets" not in result.stdout
    assert "rulesets" not in result.stdout
    assert "Create GitHub Actions Variables" not in result.stdout


def test_configure_github_dry_run_does_not_print_marketplace_identity_variables(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project, marketplace_identity_projection())

    result = run("configure-github", "--project", str(project), "--dry-run")

    assert result.returncode == 0
    for variable in [
        "CODEX_MARKETPLACE_CATALOG_NAME",
        "CODEX_MARKETPLACE_DISPLAY_NAME",
        "CLAUDE_MARKETPLACE_CATALOG_NAME",
        "CLAUDE_MARKETPLACE_OWNER_NAME",
        "RELEASE_FLOW_PLUGIN_REPOSITORY",
        "RELEASE_FLOW_PLUGIN_REF",
    ]:
        assert variable not in result.stdout


def test_removed_commands_are_not_registered(tmp_path: Path) -> None:
    project = tmp_path / "project"
    workflow_run_file = tmp_path / "workflow-run-input.json"
    write_release_flow_files(project)
    write_json(workflow_run_file, {})

    release_init = run(
        "release-init",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
    )
    summarize = run(
        "summarize",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--workflow-run-file",
        str(workflow_run_file),
    )

    assert release_init.returncode == 2
    assert summarize.returncode == 2
    assert not (project / ".release-flow" / "releases").exists()


def test_project_rejects_transform_path_outside_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(
        project,
        marketplace_identity_projection(
            transforms="""  - path: ../outside.json
    type: json-env
    set:
      /name: identity.codex.marketplaceName
"""
        ),
    )

    result = run("project", "--project", str(project))

    assert result.returncode == 1
    assert "invalid_projection_transform_path:" in result.stdout
    assert not (tmp_path / "outside.json").exists()


def test_project_rejects_vars_file_argument(tmp_path: Path) -> None:
    project = tmp_path / "project"
    vars_file = tmp_path / "vars.json"
    write_release_flow_files(project, marketplace_identity_projection())
    write_json(vars_file, {})

    result = run("project", "--project", str(project), "--vars-file", str(vars_file))

    assert result.returncode == 2


def test_preflight_rejects_github_vars_file_argument(tmp_path: Path) -> None:
    project = tmp_path / "project"
    vars_file = tmp_path / "vars.json"
    write_release_flow_files(project, marketplace_identity_projection())
    write_json(vars_file, {})

    result = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--github-vars-file",
        str(vars_file),
    )

    assert result.returncode == 2


def test_ci_publish_rejects_vars_file_argument(tmp_path: Path) -> None:
    project = tmp_path / "project"
    vars_file = tmp_path / "vars.json"
    write_release_flow_files(project, marketplace_identity_projection())
    write_json(vars_file, {})

    result = run(
        "ci-publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
        "--vars-file",
        str(vars_file),
        "--authorize-ci-publish",
    )

    assert result.returncode == 2


def test_validate_rejects_projection_variable_values(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(
        project,
        """version: 1

variables:
  SOME_VARIABLE:
    source: github-actions-variable
    required: true
    value: agent-guard-marketplace

transforms: []
""",
    )

    result = run("validate", "--project", str(project))

    assert result.returncode == 1
    assert "projection_variable_value_forbidden: SOME_VARIABLE" in result.stdout


def test_project_applies_json_env_transform(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(
        project,
        marketplace_identity_projection(
            transforms="""  - path: .agents/plugins/marketplace.json
    type: json-env
    set:
      /name: identity.codex.marketplaceName
"""
        ),
    )
    write_json(project / ".agents" / "plugins" / "marketplace.json", {"name": "local-dev"})

    result = run("project", "--project", str(project))

    assert result.returncode == 0
    assert "status: projected" in result.stdout
    target = json.loads(
        (project / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert target["name"] == "my-agent-skills-marketplace"


def test_project_generates_codex_marketplace_from_projection_identity(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project, marketplace_identity_projection())

    result = run("project", "--project", str(project))

    assert result.returncode == 0
    assert "status: projected" in result.stdout
    target = json.loads(
        (project / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert target["name"] == "my-agent-skills-marketplace"
    assert target["interface"]["displayName"] == "My Agent Skills Marketplace"
    assert [entry["name"] for entry in target["plugins"]] == ["agent-guard", "release-flow"]
    assert target["plugins"][0]["source"] == {
        "source": "local",
        "path": "./plugins/agent-guard",
    }


def test_validate_rejects_invalid_branch_mode(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(
        project,
        """version: 1

variables: {}
transforms: []
""",
    )
    config = project / ".release-flow" / "config.yaml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("branchMode: remote-only", "branchMode: local"),
        encoding="utf-8",
    )

    result = run("validate", "--project", str(project))

    assert result.returncode == 1
    assert "invalid_config: release.branchMode must be remote-only" in result.stdout


def test_project_applies_json_env_transform_inside_list(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(
        project,
        marketplace_identity_projection(
            transforms="""  - path: .agents/plugins/marketplace.json
    type: json-env
    set:
      /plugins/0/name: identity.codex.marketplaceName
"""
        ),
    )
    write_json(project / ".agents" / "plugins" / "marketplace.json", {"plugins": [{"name": "old"}]})

    result = run("project", "--project", str(project))

    assert result.returncode == 0
    target = json.loads(
        (project / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert target["plugins"][0]["name"] == "my-agent-skills-marketplace"


def test_project_adds_missing_final_dict_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(
        project,
        """version: 1

identity:
  codex:
    marketplaceName: my-agent-skills-marketplace
    displayName: My Agent Skills Marketplace
  claude:
    marketplaceName: my-agent-skills-marketplace
    ownerName: My Agent Skills Marketplace

variables: {}
generators: []
transforms:
  - path: .agents/plugins/marketplace.json
    type: json-env
    set:
      /metadata/name: identity.claude.ownerName
""",
    )
    write_json(project / ".agents" / "plugins" / "marketplace.json", {"metadata": {}})

    result = run("project", "--project", str(project))

    assert result.returncode == 0
    target = json.loads(
        (project / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert target == {"metadata": {"name": "My Agent Skills Marketplace"}}


def test_project_rejects_negative_json_pointer_list_index(tmp_path: Path) -> None:
    project = tmp_path / "project"
    initial_target = {"plugins": [{"name": "first"}, {"name": "last"}]}
    write_release_flow_files(
        project,
        """version: 1

identity:
  codex:
    marketplaceName: my-agent-skills-marketplace
    displayName: My Agent Skills Marketplace
  claude:
    marketplaceName: my-agent-skills-marketplace
    ownerName: My Agent Skills Marketplace

variables: {}
generators: []
transforms:
  - path: .agents/plugins/marketplace.json
    type: json-env
    set:
      /plugins/-1/name: identity.codex.marketplaceName
""",
    )
    target_path = project / ".agents" / "plugins" / "marketplace.json"
    write_json(target_path, initial_target)

    result = run("project", "--project", str(project))

    assert result.returncode == 1
    assert "json_pointer_list_index_invalid: /plugins/-1/name" in result.stdout
    assert json.loads(target_path.read_text(encoding="utf-8")) == initial_target


def test_preflight_rejects_missing_bump_plugins(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("preflight", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    assert result.returncode == 2


def test_preflight_rejects_unknown_bump_plugin(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "missing-plugin",
    )

    assert result.returncode == 1
    assert "plugin_unknown: missing-plugin" in result.stdout


def test_bump_plugins_parser_accepts_comma_empty_and_repeated_args() -> None:
    release_flow = load_release_flow_module()
    parser = release_flow.build_parser()

    assert release_flow.parse_bump_plugins("agent-guard,release-flow") == ["agent-guard", "release-flow"]
    assert release_flow.parse_bump_plugins("") == []
    for command, authorization in [
        ("preflight", []),
        ("publish", ["--authorize-publish"]),
        ("ci-publish", ["--authorize-ci-publish"]),
    ]:
        args = parser.parse_args(
            [
                command,
                "--project",
                ".",
                "--tag",
                "v0.1.1",
                "--version",
                "0.1.1",
                "--bump-plugins",
                "agent-guard",
                "--bump-plugins",
                "release-flow",
                *authorization,
            ]
        )
        assert release_flow.parse_bump_plugins(args.bump_plugins) == ["agent-guard", "release-flow"]


def run_preflight_with_errors(
    monkeypatch,
    tmp_path: Path,
    errors: list[str],
    *,
    bump_plugins: list[str],
    projection: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    project = tmp_path / "project"
    write_release_flow_files(project, projection)
    monkeypatch.setattr(load_release_flow_module(), "preflight_errors", lambda *_args: list(errors))

    args = [
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
    ]
    for plugin in bump_plugins:
        args.extend(["--bump-plugins", plugin])
    return run(*args, env=env)


def test_preflight_accepts_partial_plugin_bump(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        [],
        bump_plugins=["agent-guard"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: preflight_passed" in result.stdout
    assert "bumpPlugins: agent-guard" in result.stdout


def test_preflight_rejects_bump_not_merged_to_source_ref(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["source_ref_requires_pr: main: plugins/agent-guard/.codex-plugin/plugin.json"],
        bump_plugins=["agent-guard"],
    )

    assert result.returncode == 1
    assert "source_ref_requires_pr: main: plugins/agent-guard/.codex-plugin/plugin.json" in result.stdout


def test_preflight_source_ref_requires_pr_prints_next_action(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["source_ref_requires_pr: main: plugins/agent-guard/.codex-plugin/plugin.json"],
        bump_plugins=["agent-guard"],
    )

    assert result.returncode == 1
    assert "error: source_ref_requires_pr: main: plugins/agent-guard/.codex-plugin/plugin.json" in result.stdout
    assert (
        "nextAction: create and merge the version bump through PR Flow, "
        "then rerun release-flow preflight"
    ) in result.stdout


def test_preflight_manifest_mismatch_prints_next_action(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["manifest_version_mismatch: plugins/agent-guard/.codex-plugin/plugin.json"],
        bump_plugins=["agent-guard"],
    )

    assert result.returncode == 1
    assert "error: manifest_version_mismatch: plugins/agent-guard/.codex-plugin/plugin.json" in result.stdout
    assert (
        "nextAction: correct the manifest version in "
        "plugins/agent-guard/.codex-plugin/plugin.json, then rerun release-flow preflight"
    ) in result.stdout


def test_preflight_existing_release_prints_next_action(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["release already exists: v0.1.1"],
        bump_plugins=["agent-guard"],
    )

    assert result.returncode == 1
    assert "error: release already exists: v0.1.1" in result.stdout
    assert "nextAction: choose a new release version and rerun release-flow preflight" in result.stdout


def test_preflight_merges_repeated_bump_plugins(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        [],
        bump_plugins=["agent-guard", "release-flow"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "bumpPlugins: agent-guard,release-flow" in result.stdout


def test_remote_ref_manifest_version_fetches_missing_channel_branch_for_actions_checkout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    release_flow = load_release_flow_module()
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    calls = []

    def fake_ref_exists(project_arg: Path, ref: str) -> bool:
        calls.append(("exists", project_arg, ref))
        return False

    def fake_run(command, **kwargs):
        calls.append(tuple(command))
        if "fetch" in command:
            return subprocess.CompletedProcess(command, 0, "", "")
        if "show" in command:
            return subprocess.CompletedProcess(command, 0, json.dumps({"version": "0.1.1"}), "")
        return subprocess.CompletedProcess(command, 1, "", "unexpected command")

    monkeypatch.setattr(release_flow, "git_ref_exists", fake_ref_exists)
    monkeypatch.setattr(release_flow.subprocess, "run", fake_run)

    version = release_flow.remote_ref_manifest_version(
        checkout,
        "marketplace",
        "plugins/agent-guard/.codex-plugin/plugin.json",
    )

    assert version == "0.1.1"
    assert calls == [
        ("exists", checkout, "origin/marketplace"),
        (
            "git",
            "-C",
            str(checkout),
            "fetch",
            "--depth=1",
            "origin",
            "marketplace:refs/remotes/origin/marketplace",
        ),
        (
            "git",
            "-C",
            str(checkout),
            "show",
            "origin/marketplace:plugins/agent-guard/.codex-plugin/plugin.json",
        ),
    ]


def test_preflight_accepts_empty_bump_plugins_when_versions_do_not_drift(tmp_path: Path, monkeypatch) -> None:
    env = os.environ.copy()
    env["GITHUB_REPOSITORY"] = "liuli195/my-agent-skills"

    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        [],
        bump_plugins=[""],
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: preflight_passed" in result.stdout
    assert "bumpPlugins: " in result.stdout


def test_preflight_rejects_unbumped_manifest_drift(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["plugin_requires_bump: agent-guard"],
        bump_plugins=[""],
    )

    assert result.returncode == 1
    assert "plugin_requires_bump: agent-guard" in result.stdout


def test_preflight_rejects_remote_tag_that_already_exists(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["release already exists: v0.1.1"],
        bump_plugins=["agent-guard"],
    )

    assert result.returncode == 1
    assert "release already exists: v0.1.1" in result.stdout


def test_preflight_checks_projection_without_channel_tree(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["missing_file: .claude-plugin/marketplace.json"],
        bump_plugins=["agent-guard"],
        projection=(
        marketplace_identity_projection(
            transforms="""  - path: .claude-plugin/marketplace.json
    type: json-env
    set:
      /name: identity.claude.marketplaceName
"""
        )
        ),
    )

    assert result.returncode == 1
    assert "missing_file:" in result.stdout
    assert ".claude-plugin" in result.stdout
    assert "marketplace.json" in result.stdout


def test_preflight_rejects_channel_tree_argument(tmp_path: Path) -> None:
    project = tmp_path / "project"
    channel_tree = tmp_path / "channel"
    write_release_flow_files(project)
    channel_tree.mkdir()

    result = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
        "--channel-tree",
        str(channel_tree),
    )

    assert result.returncode == 2


def fake_gh_for_publish(bin_dir: Path, calls: Path, *, always_eof: bool = False) -> Path:
    bin_dir.mkdir()
    seen = calls.with_name("gh-seen.txt")
    if os.name == "nt":
        gh = bin_dir / "gh.cmd"
        eof_line = 'echo Get ""https://api.github.com/repos/x/actions/workflows/release.yml"": EOF 1>&2'
        if always_eof:
            body = f'@echo off\r\necho %*>>"{calls}"\r\n{eof_line}\r\nexit /b 1\r\n'
        else:
            body = (
                f'@echo off\r\necho %*>>"{calls}"\r\n'
                f'if not exist "{seen}" (echo seen>"{seen}" & {eof_line} & exit /b 1)\r\n'
                "exit /b 0\r\n"
            )
        gh.write_text(body, encoding="utf-8")
        return gh

    gh = bin_dir / "gh"
    if always_eof:
        body = (
            "#!/bin/sh\n"
            f'printf "%s\\n" "$*" >> "{calls}"\n'
            'printf "%s\\n" "Get \\"https://api.github.com/repos/x/actions/workflows/release.yml\\": EOF" >&2\n'
            "exit 1\n"
        )
    else:
        body = (
            "#!/bin/sh\n"
            f'printf "%s\\n" "$*" >> "{calls}"\n'
            f'if [ ! -f "{seen}" ]; then touch "{seen}"; '
            'printf "%s\\n" "Get \\"https://api.github.com/repos/x/actions/workflows/release.yml\\": EOF" >&2; exit 1; fi\n'
            "exit 0\n"
        )
    gh.write_text(body, encoding="utf-8")
    gh.chmod(0o755)
    return gh


def test_publish_rejects_dry_run_argument(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run(
        "publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
        "--dry-run",
    )

    assert result.returncode == 2
    assert "--dry-run" in result.stderr
    assert "workflow_dispatch:" not in result.stdout


def test_publish_retries_workflow_run_eof_then_succeeds(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    calls = tmp_path / "gh-calls.txt"
    bin_dir = tmp_path / "bin"
    fake_gh_for_publish(bin_dir, calls)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    result = run(
        "publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
        "--authorize-publish",
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert calls.read_text(encoding="utf-8").count("workflow run") == 2


def test_publish_reports_last_eof_after_workflow_run_retries_exhausted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    calls = tmp_path / "gh-calls.txt"
    bin_dir = tmp_path / "bin"
    fake_gh_for_publish(bin_dir, calls, always_eof=True)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    result = run(
        "publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
        "--authorize-publish",
        env=env,
    )

    assert result.returncode == 1
    assert "EOF" in result.stderr
    assert calls.read_text(encoding="utf-8").count("workflow run") == 4


def test_publish_requires_authorization_without_dry_run(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run(
        "publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
    )

    assert result.returncode == 2
    assert "publish_requires_authorize_publish" in result.stdout


def test_workflows_are_thin_entrypoints() -> None:
    workflow_paths = [
        REPO_ROOT
        / "plugins"
        / "release-flow"
        / "skills"
        / "release-flow"
        / "assets"
        / "templates"
        / "github"
        / "workflows"
        / "release.yml",
        REPO_ROOT / ".github" / "workflows" / "release.yml",
    ]
    for workflow_path in workflow_paths:
        workflow = workflow_path.read_text(encoding="utf-8")
        assert "workflow_dispatch:" in workflow
        assert "contents: write" in workflow
        assert "ref: main" not in workflow
        assert "Checkout release-flow plugin" not in workflow
        assert "Install release-flow dependencies" in workflow
        assert "python -m pip install PyYAML" in workflow
        assert "source/plugins/release-flow/skills/release-flow/scripts/release_flow.py" in workflow
        assert "release-init" not in workflow
        assert "releasePlan" not in workflow
        assert "bumpPlugins:" in workflow
        assert "--bump-plugins" in workflow
        assert "--version" in workflow
        assert "version:" in workflow
        assert "ci-publish" in workflow
        assert "--release-plan" not in workflow
        assert "release-vars.json" not in workflow
        assert "--vars-file" not in workflow
        assert "release-flow-plugin/" not in workflow
        assert "--authorize-ci-publish" in workflow
        assert "GH_TOKEN" in workflow
        assert "github.token" in workflow
        assert "scripts/release-flow" not in workflow


def test_workflows_use_current_low_risk_action_versions() -> None:
    workflow_paths = [
        *sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")),
        REPO_ROOT
        / "plugins"
        / "release-flow"
        / "skills"
        / "release-flow"
        / "assets"
        / "templates"
        / "github"
        / "workflows"
        / "release.yml",
    ]
    workflows = {path: path.read_text(encoding="utf-8") for path in workflow_paths}
    combined = "\n".join(workflows.values())

    assert "actions/checkout@v4" not in combined
    assert "actions/setup-node@v4" not in combined
    assert 'node-version: "20"' not in combined
    assert "actions/setup-python@v5" not in combined

    codeql_workflow = workflows[REPO_ROOT / ".github" / "workflows" / "codeql.yml"]
    assert "github/codeql-action/init@v4" in codeql_workflow
    assert "github/codeql-action/analyze@v4" in codeql_workflow


def test_ci_publish_rejects_dry_run_argument(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(
        project,
        marketplace_identity_projection().replace(
            "      - release-flow\n",
                "      - release-flow\n      - cross-agent-review\n      - pr-flow\n",
        ),
    )

    result = run(
        "ci-publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
        "--dry-run",
    )

    assert result.returncode == 2
    assert not (tmp_path / "project-projected").exists()


def test_ci_publish_copies_checkout_git_auth_config_to_release_tree(tmp_path: Path, monkeypatch) -> None:
    release_flow = load_release_flow_module()
    source = tmp_path / "source"
    release_tree = tmp_path / "release-tree"
    source.mkdir()
    release_tree.mkdir()
    add_calls = []

    def fake_run(command, **kwargs):
        if command == ["git", "-C", str(source), "config", "--local", "--list"]:
            return subprocess.CompletedProcess(
                command,
                0,
                "http.https://github.com/.extraheader=AUTHORIZATION: basic secret\n"
                "core.repositoryformatversion=0\n",
                "",
            )
        if command == ["git", "-C", str(source), "config", "--local", "--get-all", "credential.helper"]:
            return subprocess.CompletedProcess(command, 0, "store\n", "")
        if command == ["git", "-C", str(source), "config", "--local", "--get-all", "credential.useHttpPath"]:
            return subprocess.CompletedProcess(command, 0, "true\n", "")
        if command[:5] == ["git", "-C", str(release_tree), "config", "--local"] and command[5] == "--add":
            add_calls.append(tuple(command[6:]))
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "unexpected command")

    monkeypatch.setattr(release_flow.subprocess, "run", fake_run)

    release_flow.copy_git_auth_config(source, release_tree)

    assert add_calls == [
        ("http.https://github.com/.extraheader", "AUTHORIZATION: basic secret"),
        ("credential.helper", "store"),
        ("credential.useHttpPath", "true"),
    ]


def test_origin_is_github_uses_exact_host(tmp_path: Path, monkeypatch) -> None:
    release_flow = load_release_flow_module()
    project = tmp_path / "project"

    monkeypatch.setattr(release_flow, "origin_url", lambda _project: "https://evilgithub.com/org/repo.git")
    assert not release_flow.origin_is_github(project)

    monkeypatch.setattr(release_flow, "origin_url", lambda _project: "https://github.com/org/repo.git")
    assert release_flow.origin_is_github(project)

    monkeypatch.setattr(release_flow, "origin_url", lambda _project: "git@github.com:org/repo.git")
    assert release_flow.origin_is_github(project)


def test_ci_publish_authorized_pushes_channel_tag_and_creates_release(tmp_path: Path, monkeypatch) -> None:
    release_flow = load_release_flow_module()
    project = tmp_path / "project"
    write_release_flow_files(
        project,
        marketplace_identity_projection(
            transforms="""  - path: .agents/plugins/marketplace.json
    type: json-env
    set:
      /name: identity.codex.marketplaceName
"""
        ),
    )
    write_plugin_manifests(project, "agent-guard", "0.1.1")
    write_plugin_manifests(project, "release-flow", "0.1.1")
    write_json(project / ".agents" / "plugins" / "marketplace.json", {"name": "local-dev"})

    preflight_calls = []
    remote_calls = []

    def fake_preflight(project_arg, tag, version, bump_plugins, config, projection):
        preflight_calls.append((project_arg, tag, version, bump_plugins, config.release_channel_branch, projection.path))
        return []

    def fake_ci_publish_remote(project_arg, config, projection, tag):
        remote_calls.append((project_arg, config.release_channel_branch, projection.path, tag))
        return {
            "release_url": "https://github.example/releases/tag/v0.1.1",
            "marketplace_commit": "marketplace-commit",
            "tag_commit": "tag-commit",
            "workflow_run_url": "https://github.example/actions/runs/1",
        }

    monkeypatch.setattr(release_flow, "preflight_errors", fake_preflight)
    monkeypatch.setattr(release_flow, "run_ci_publish_remote", fake_ci_publish_remote)
    result = run(
        "ci-publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
        "--authorize-ci-publish",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: ci_published" in result.stdout
    assert "channel_branch: marketplace" in result.stdout
    assert "tag: v0.1.1" in result.stdout
    assert "release_url: https://github.example/releases/tag/v0.1.1" in result.stdout
    assert "marketplace_commit: marketplace-commit" in result.stdout
    assert "tag_commit: tag-commit" in result.stdout
    assert "workflow_run_url: https://github.example/actions/runs/1" in result.stdout
    projection_path = project.resolve() / ".release-flow" / "projection.yaml"
    assert preflight_calls == [(project.resolve(), "v0.1.1", "0.1.1", ["agent-guard"], "marketplace", projection_path)]
    assert remote_calls == [(project.resolve(), "marketplace", projection_path, "v0.1.1")]
    source_marketplace = json.loads((project / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    assert source_marketplace["name"] == "local-dev"


def test_ci_publish_requires_authorization_without_dry_run(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run(
        "ci-publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
    )

    assert result.returncode == 2
    assert "ci_publish_requires_authorize_ci_publish" in result.stdout


def test_release_flow_local_e2e(tmp_path: Path, monkeypatch) -> None:
    release_flow = load_release_flow_module()
    project = tmp_path / "project"

    setup = run("setup", "--project", str(project), "--authorize-project-files")
    assert setup.returncode == 0, setup.stdout + setup.stderr
    write_plugin_manifests(project, "agent-guard", "0.1.1")
    write_plugin_manifests(project, "release-flow", "0.1.1")
    write_json(
        project / ".claude-plugin" / "marketplace.json",
        {"name": "local-dev", "owner": {"name": "Local Dev"}},
    )

    preflight_calls = []

    def fake_preflight(project_arg, tag, version, bump_plugins, config, projection):
        preflight_calls.append((project_arg, tag, version, bump_plugins, config.release_channel_branch, projection.path))
        return []

    monkeypatch.setattr(release_flow, "preflight_errors", fake_preflight)

    preflight = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
    )
    assert preflight.returncode == 0, preflight.stdout + preflight.stderr
    assert preflight_calls == [
        (project.resolve(), "v0.1.1", "0.1.1", ["agent-guard"], "marketplace", project.resolve() / ".release-flow" / "projection.yaml")
    ]
    calls = tmp_path / "gh-calls.txt"
    bin_dir = tmp_path / "bin"
    fake_gh_for_publish(bin_dir, calls)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    publish = run(
        "publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
        "--authorize-publish",
        env=env,
    )
    assert publish.returncode == 0, publish.stdout + publish.stderr
    assert calls.read_text(encoding="utf-8").count("workflow run") == 2
    assert not (project / ".release-flow" / ".gitignore").exists()
    assert not (project / ".release-flow" / "releases").exists()
