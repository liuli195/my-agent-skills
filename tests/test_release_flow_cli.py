import importlib.util
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
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


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.setdefault("GITHUB_ACTIONS", "true")
    environment.setdefault("GITHUB_REPOSITORY", "liuli195/my-agent-skills")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_manifest(path: Path, version: str) -> None:
    write_json(path, {"version": version})


def write_plugin_manifests(project: Path, plugin: str, version: str) -> None:
    write_manifest(project / "plugins" / plugin / ".codex-plugin" / "plugin.json", version)
    write_manifest(project / "plugins" / plugin / ".claude-plugin" / "plugin.json", version)


def write_npm_package(
    project: Path,
    plugin: str,
    *,
    repository_url: str = "https://github.com/liuli195/my-agent-skills",
    directory: str | None = None,
    version: str = "1.0.0",
) -> None:
    write_json(
        project / "plugins" / plugin / "package.json",
        {
            "version": version,
            "repository": {
                "type": "git",
                "url": repository_url,
                "directory": directory or f"plugins/{plugin}",
            },
        },
    )


def init_release_input_project(project: Path, remote: Path, version: str = "1.0.0") -> None:
    write_release_flow_files(project)
    for plugin in ("release-flow", "pr-flow", "build-and-verify", "my-spec"):
        write_plugin_manifests(project, plugin, version)
        (project / "plugins" / plugin / "content.txt").parent.mkdir(parents=True, exist_ok=True)
        (project / "plugins" / plugin / "content.txt").write_text("baseline\n", encoding="utf-8")
    for plugin in ("build-and-verify", "my-spec"):
        write_npm_package(project, plugin, version=version)
    for path in (
        project / "plugins" / "tool-lifecycle" / "pack.py",
        project / "plugins" / "tool-lifecycle" / "python" / "management.py",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("baseline\n", encoding="utf-8")
    init_project_with_remote(project, remote)


def advance_plugin_version_on_source_ref(project: Path, plugin: str, version: str) -> None:
    write_plugin_manifests(project, plugin, version)
    if plugin in {"build-and-verify", "my-spec"}:
        write_npm_package(project, plugin, version=version)
    assert git(project, "add", f"plugins/{plugin}").returncode == 0
    assert git(project, "commit", "-m", f"bump {plugin}").returncode == 0
    assert git(project, "push", "origin", "HEAD:refs/heads/main").returncode == 0
    assert git(project, "fetch", "origin", "main").returncode == 0


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
      - pr-flow
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


def test_validate_rejects_missing_npm_repository_metadata(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_json(project / "plugins" / "my-spec" / "package.json", {"version": "1.0.0"})
    assert git(project, "init").returncode == 0
    assert git(
        project,
        "remote",
        "add",
        "origin",
        "https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0

    result = run("validate", "--project", str(project))

    assert result.returncode == 1
    assert "npm_repository_url_missing" in result.stdout
    assert "plugins/my-spec/package.json" in result.stdout
    assert "expected=liuli195/my-agent-skills" in result.stdout
    assert "actual=<missing>" in result.stdout
    assert "npm_repository_directory_missing" in result.stdout
    assert "nextAction:" in result.stdout


@pytest.mark.parametrize(
    "repository_url",
    [
        "https://github.com/liuli195/my-agent-skills",
        "https://github.com/liuli195/my-agent-skills.git",
        "git+https://github.com/liuli195/my-agent-skills.git",
        "git@github.com:liuli195/my-agent-skills.git",
        "ssh://git@github.com/liuli195/my-agent-skills.git",
    ],
)
def test_validate_accepts_supported_github_repository_urls(
    tmp_path: Path, repository_url: str
) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec", repository_url=repository_url)
    assert git(project, "init").returncode == 0
    assert git(
        project,
        "remote",
        "add",
        "origin",
        "git+https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0

    result = run("validate", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: verified" in result.stdout


@pytest.mark.parametrize(
    ("repository_url", "expected_error", "actual"),
    [
        (
            "https://github.com/other/repository.git",
            "npm_repository_url_mismatch",
            "other/repository",
        ),
        (
            "https://github.com/liuli195/My-Agent-Skills.git",
            "npm_repository_url_mismatch",
            "liuli195/My-Agent-Skills",
        ),
        (
            "https://example.com/liuli195/my-agent-skills.git",
            "npm_repository_url_invalid",
            "https://example.com/liuli195/my-agent-skills.git",
        ),
        (
            "https://user@github.com/liuli195/my-agent-skills.git",
            "npm_repository_url_invalid",
            "https://user@github.com/liuli195/my-agent-skills.git",
        ),
        (
            "https://github.com:443/liuli195/my-agent-skills.git",
            "npm_repository_url_invalid",
            "https://github.com:443/liuli195/my-agent-skills.git",
        ),
        (
            "git@x@github.com:liuli195/my-agent-skills.git",
            "npm_repository_url_invalid",
            "git@x@github.com:liuli195/my-agent-skills.git",
        ),
        (
            "https://[github.com/liuli195/my-agent-skills",
            "npm_repository_url_invalid",
            "https://[github.com/liuli195/my-agent-skills",
        ),
    ],
)
def test_validate_reports_stable_npm_repository_errors(
    tmp_path: Path, repository_url: str, expected_error: str, actual: str
) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec", repository_url=repository_url)
    assert git(project, "init").returncode == 0
    assert git(
        project,
        "remote",
        "add",
        "origin",
        "https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0

    result = run("validate", "--project", str(project))

    assert result.returncode == 1
    assert expected_error in result.stdout
    assert "plugins/my-spec/package.json" in result.stdout
    assert "expected=liuli195/my-agent-skills" in result.stdout
    assert f"actual={actual}" in result.stdout
    assert "nextAction: correct npm repository metadata in plugins/my-spec/package.json" in result.stdout


def test_validate_checks_all_existing_registered_npm_packages(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec")
    write_npm_package(
        project,
        "build-and-verify",
        repository_url="https://github.com/other/repository.git",
    )
    assert git(project, "init").returncode == 0
    assert git(
        project,
        "remote",
        "add",
        "origin",
        "https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0

    result = run("validate", "--project", str(project))

    assert result.returncode == 1
    assert "plugins/build-and-verify/package.json" in result.stdout
    assert "plugins/my-spec/package.json" not in result.stdout


def test_validate_reports_wrong_existing_npm_repository_directory(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec", directory="plugins/other")
    (project / "plugins" / "other").mkdir(parents=True)
    assert git(project, "init").returncode == 0
    assert git(
        project,
        "remote",
        "add",
        "origin",
        "https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0

    result = run("validate", "--project", str(project))

    assert result.returncode == 1
    assert "npm_repository_directory_mismatch" in result.stdout
    assert "plugins/my-spec/package.json" in result.stdout
    assert "expected=plugins/my-spec" in result.stdout
    assert "actual=plugins/other" in result.stdout


def test_validate_fails_closed_when_github_repository_identity_is_unknown(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec")
    environment = {key: value for key, value in os.environ.items() if key != "GITHUB_REPOSITORY"}

    result = run("validate", "--project", str(project), env=environment)

    assert result.returncode == 1
    assert "npm_repository_identity_unavailable" in result.stdout
    assert "plugins/my-spec/package.json" in result.stdout
    assert "expected=GitHub owner/repository" in result.stdout
    assert "nextAction: configure a GitHub origin or trusted GITHUB_REPOSITORY" in result.stdout


def test_validate_uses_origin_outside_github_actions(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec")
    assert git(project, "init").returncode == 0
    assert git(
        project,
        "remote",
        "add",
        "origin",
        "https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0

    result = run(
        "validate",
        "--project",
        str(project),
        env={
            **os.environ,
            "GITHUB_ACTIONS": "false",
            "GITHUB_REPOSITORY": "other/repository",
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_validate_rejects_conflicting_github_actions_repository_identity(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec")
    assert git(project, "init").returncode == 0
    assert git(
        project,
        "remote",
        "add",
        "origin",
        "https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0

    result = run(
        "validate",
        "--project",
        str(project),
        env={
            **os.environ,
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "other/repository",
        },
    )

    assert result.returncode == 1
    assert "npm_repository_identity_conflict" in result.stdout
    assert "plugins/my-spec/package.json" in result.stdout
    assert "expected=other/repository" in result.stdout
    assert "actual=liuli195/my-agent-skills" in result.stdout
    assert "nextAction: align the GitHub origin and GITHUB_REPOSITORY identity" in result.stdout


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
        "v9.9.1",
        "--version",
        "9.9.1",
    )
    summarize = run(
        "summarize",
        "--project",
        str(project),
        "--tag",
        "v9.9.1",
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
        "v9.9.1",
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
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "pr-flow",
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
    value: pr-flow-marketplace

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
    assert [entry["name"] for entry in target["plugins"]] == ["pr-flow", "release-flow"]
    assert target["plugins"][0]["source"] == {
        "source": "local",
        "path": "./plugins/pr-flow",
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

    result = run("preflight", "--project", str(project), "--tag", "v9.9.1", "--version", "9.9.1")

    assert result.returncode == 2


def test_preflight_rejects_unknown_bump_plugin(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "missing-plugin",
    )

    assert result.returncode == 1
    assert "plugin_unknown: missing-plugin" in result.stdout


def test_bump_plugins_parser_accepts_comma_empty_and_repeated_args() -> None:
    release_flow = load_release_flow_module()
    parser = release_flow.build_parser()

    assert release_flow.parse_bump_plugins("pr-flow,release-flow") == ["pr-flow", "release-flow"]
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
                "v9.9.1",
                "--version",
                "9.9.1",
                "--bump-plugins",
                "pr-flow",
                "--bump-plugins",
                "release-flow",
                *authorization,
            ]
        )
        assert release_flow.parse_bump_plugins(args.bump_plugins) == ["pr-flow", "release-flow"]


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
        "v9.9.1",
        "--version",
        "9.9.1",
    ]
    for plugin in bump_plugins:
        args.extend(["--bump-plugins", plugin])
    return run(*args, env=env)


def test_preflight_accepts_partial_plugin_bump(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        [],
        bump_plugins=["pr-flow"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: preflight_passed" in result.stdout
    assert "bumpPlugins: pr-flow" in result.stdout


def test_preflight_rejects_bump_not_merged_to_source_ref(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["source_ref_requires_pr: main: plugins/pr-flow/.codex-plugin/plugin.json"],
        bump_plugins=["pr-flow"],
    )

    assert result.returncode == 1
    assert "source_ref_requires_pr: main: plugins/pr-flow/.codex-plugin/plugin.json" in result.stdout


def test_preflight_source_ref_requires_pr_prints_next_action(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["source_ref_requires_pr: main: plugins/pr-flow/.codex-plugin/plugin.json"],
        bump_plugins=["pr-flow"],
    )

    assert result.returncode == 1
    assert "error: source_ref_requires_pr: main: plugins/pr-flow/.codex-plugin/plugin.json" in result.stdout
    assert (
        "nextAction: create and merge the version bump through PR Flow, "
        "then rerun release-flow preflight"
    ) in result.stdout


def test_preflight_manifest_mismatch_prints_next_action(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["manifest_version_mismatch: plugins/pr-flow/.codex-plugin/plugin.json"],
        bump_plugins=["pr-flow"],
    )

    assert result.returncode == 1
    assert "error: manifest_version_mismatch: plugins/pr-flow/.codex-plugin/plugin.json" in result.stdout
    assert (
        "nextAction: correct the manifest version in "
        "plugins/pr-flow/.codex-plugin/plugin.json, then rerun release-flow preflight"
    ) in result.stdout


def test_remote_release_does_not_query_github_without_a_remote_tag(
    tmp_path: Path, monkeypatch
) -> None:
    release_flow = load_release_flow_module()
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if "ls-remote" in command:
            return subprocess.CompletedProcess(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(release_flow.subprocess, "run", fake_run)

    assert release_flow.remote_release_errors(tmp_path, "v9.9.1") == []
    assert len(calls) == 1


def test_preflight_existing_release_prints_next_action(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["release already exists: v9.9.1"],
        bump_plugins=["pr-flow"],
    )

    assert result.returncode == 1
    assert "error: release already exists: v9.9.1" in result.stdout
    assert (
        "nextAction: requested release/tag already exists; choose the release version with the user and agent, "
        "then rerun release-flow preflight"
    ) in result.stdout
    assert "new release version" not in result.stdout


def test_preflight_multi_error_prints_one_summary_path_without_version_inference(
    tmp_path: Path, monkeypatch
) -> None:
    errors = [
        "release already exists: v9.9.1",
        "manifest_version_mismatch: plugins/pr-flow/.codex-plugin/plugin.json",
        "source_ref_requires_pr: main: plugins/pr-flow/.codex-plugin/plugin.json",
        "plugin_requires_bump: release-flow",
    ]

    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        errors,
        bump_plugins=["pr-flow"],
    )

    assert result.returncode == 1
    for error in errors:
        assert f"error: {error}" in result.stdout
    next_actions = [line for line in result.stdout.splitlines() if line.startswith("nextAction:")]
    assert next_actions == [
        "nextAction: current state: release/tag already exists; manifest versions do not match requested release; "
        "source ref lacks version bump; some plugins need bumpPlugins. handling path: choose the release version "
        "with the user and agent, correct manifest versions through PR Flow, create and merge the source-ref "
        "version bump through PR Flow, include required plugins in bumpPlugins through PR Flow when they should "
        "ship, then rerun release-flow preflight"
    ]
    assert "latest version" not in result.stdout
    assert "next version" not in result.stdout


def test_preflight_ignores_legacy_build_and_verify_runtime(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
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

variables:
  {}
generators:
  - path: .agents/plugins/marketplace.json
    type: codex-marketplace
    identity: codex
    plugins:
      - build-and-verify

transforms:
  []
""",
    )
    write_plugin_manifests(project, "build-and-verify", "9.9.0")
    write_npm_package(project, "build-and-verify", version="9.9.0")
    write_json(
        project / ".build-and-verify" / "config.json",
        {"version": 1, "build": {"checks": []}, "verify": {"checks": []}},
    )
    runtime_version = project / ".build-and-verify" / "runtime" / "version.json"
    write_json(
        runtime_version,
        {
            "plugin": "build-and-verify",
            "plugin_version": "9.8.0",
            "runtime_version": "9.8.0",
        },
    )
    init_project_with_remote(project, remote)
    monkeypatch.setattr(load_release_flow_module(), "remote_release_errors", lambda *_args: [])

    result = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v9.9.0",
        "--version",
        "9.9.0",
        "--bump-plugins",
        "build-and-verify",
        env={
            **os.environ,
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "liuli195/my-agent-skills",
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "runtime_update_required" not in result.stdout


def test_preflight_merges_repeated_bump_plugins(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        [],
        bump_plugins=["pr-flow", "release-flow"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "bumpPlugins: pr-flow,release-flow" in result.stdout


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
            return subprocess.CompletedProcess(command, 0, json.dumps({"version": "9.9.1"}), "")
        return subprocess.CompletedProcess(command, 1, "", "unexpected command")

    monkeypatch.setattr(release_flow, "git_ref_exists", fake_ref_exists)
    monkeypatch.setattr(release_flow.subprocess, "run", fake_run)

    version = release_flow.remote_ref_manifest_version(
        checkout,
        "marketplace",
        "plugins/pr-flow/.codex-plugin/plugin.json",
    )

    assert version == "9.9.1"
    assert calls == [
        ("exists", checkout, "origin/marketplace"),
        (
            "git",
            "-C",
            str(checkout),
            "fetch",
            "--depth=1",
            "origin",
            "+marketplace:refs/remotes/origin/marketplace",
        ),
        (
            "git",
            "-C",
            str(checkout),
            "show",
            "origin/marketplace:plugins/pr-flow/.codex-plugin/plugin.json",
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
        ["plugin_requires_bump: pr-flow"],
        bump_plugins=[""],
    )

    assert result.returncode == 1
    assert "plugin_requires_bump: pr-flow" in result.stdout


def test_preflight_rejects_remote_tag_that_already_exists(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["release already exists: v9.9.1"],
        bump_plugins=["pr-flow"],
    )

    assert result.returncode == 1
    assert "release already exists: v9.9.1" in result.stdout


def test_preflight_checks_projection_without_channel_tree(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["missing_file: .claude-plugin/marketplace.json"],
        bump_plugins=["pr-flow"],
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
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "pr-flow",
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
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "pr-flow",
        "--dry-run",
    )

    assert result.returncode == 2
    assert "--dry-run" in result.stderr
    assert "workflow_dispatch:" not in result.stdout


def test_publish_rejects_metadata_before_triggering_remote_workflow(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_npm_package(
        project,
        "my-spec",
        repository_url="https://github.com/other/repository.git",
    )
    assert git(project, "init").returncode == 0
    assert git(
        project,
        "remote",
        "add",
        "origin",
        "https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0
    calls = tmp_path / "gh-calls.txt"
    bin_dir = tmp_path / "bin"
    fake_gh_for_publish(bin_dir, calls)
    environment = os.environ.copy()
    environment["PATH"] = str(bin_dir) + os.pathsep + environment.get("PATH", "")

    result = run(
        "publish",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "my-spec",
        "--authorize-publish",
        env=environment,
    )

    assert result.returncode == 1
    assert "npm_repository_url_mismatch" in result.stdout
    assert "then rerun release-flow publish" in result.stdout
    assert not calls.exists()


def test_publish_accepts_valid_selected_npm_metadata_and_dispatches(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec")
    assert git(project, "init").returncode == 0
    assert git(
        project,
        "remote",
        "add",
        "origin",
        "https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0
    calls = tmp_path / "gh-calls.txt"
    bin_dir = tmp_path / "bin"
    fake_gh_for_publish(bin_dir, calls)
    environment = os.environ.copy()
    environment["PATH"] = str(bin_dir) + os.pathsep + environment.get("PATH", "")

    result = run(
        "publish",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "my-spec",
        "--authorize-publish",
        env=environment,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert calls.read_text(encoding="utf-8").count("workflow run") == 2


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
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "pr-flow",
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
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "pr-flow",
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
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "pr-flow",
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
        assert "Install release-flow dependencies" in workflow or "source/requirements-dev.txt" in workflow
        assert "python -m pip install PyYAML" in workflow or "pip install -r source/requirements-dev.txt" in workflow
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


def test_myspec_source_ci_and_release_use_the_packed_current_checkout() -> None:
    full_verify = (REPO_ROOT / ".github" / "workflows" / "full-verify.yml").read_text(encoding="utf-8")
    release = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "npm pack ./plugins/my-spec" not in full_verify
    assert 'tarball="$(python plugins/tool-lifecycle/pack.py myspec "$RUNNER_TEMP")"' in full_verify
    assert 'npm install -g --prefix "$prefix" --ignore-scripts --no-audit --no-fund "$tarball"' in full_verify
    assert 'myspec" --help' in full_verify
    assert 'MYSPEC_TEST_TARBALL=$tarball' in full_verify
    assert full_verify.index("pack.py myspec") < full_verify.index("Run candidate quick verification")
    for workflow in (full_verify, release):
        assert "verify --project" in workflow
        assert "build-and-verify verify --project . --full" not in workflow
        assert "build-and-verify verify --project source --full" not in workflow
        assert "@liuli195/myspec@latest" not in workflow
        assert ".whl" not in workflow
        assert "pi-my-spec" not in workflow

    assert "node plugins/build-and-verify/bin/build-and-verify.js verify --project . --full" in full_verify
    assert "id-token: write" in release
    assert "registry-url: https://registry.npmjs.org" in release
    assert 'npm publish "$MYSPEC_TARBALL" --provenance --access public' in release
    assert "supplied_tarball = os.environ.get(\"MYSPEC_TEST_TARBALL\")" in (
        REPO_ROOT / "tests" / "test_my_spec.py"
    ).read_text(encoding="utf-8")
    assert release.count("${{ inputs.") == 3
    assert "BUMP_PLUGINS: ${{ inputs.bumpPlugins }}" in release
    assert 'NORMALIZED_BUMP_PLUGINS=${BUMP_PLUGINS//[[:space:]]/}' in release
    assert '",$normalized_plugins,"' in release
    assert "package.json').name" not in release
    assert "dist.integrity" in release and "integrity" in release
    assert "does not match the verified Tarball" in release
    assert "--allow-existing-release" in release
    assert release.index("Validate release plan") < release.index("Prepare verified MySpec npm package")
    assert release.index('npm publish "$MYSPEC_TARBALL"') < release.index("Publish release channel")


def test_release_workflows_publish_only_verified_selected_npm_packages(tmp_path: Path) -> None:
    workflow_paths = [
        REPO_ROOT / ".github" / "workflows" / "release.yml",
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
    for workflow_path in workflow_paths:
        workflow = workflow_path.read_text(encoding="utf-8")
        assert "replace(" not in workflow
        assert 'NORMALIZED_BUMP_PLUGINS=${BUMP_PLUGINS//[[:space:]]/}' in workflow
        assert workflow.index("Validate release plan") < workflow.index("Prepare verified MySpec npm package")
        for plugin, package_tool in (("my-spec", "myspec"), ("build-and-verify", "build-and-verify")):
            selected = f'[[ ",$normalized_plugins," == *",{plugin},"* ]] || exit 0'
            assert workflow.count(selected) == 2
            assert f'pack.py "{package_tool}"' in workflow
            assert f'npm install -g --prefix "$prefix"' in workflow
            assert f'"$prefix/bin/{package_tool}"' in workflow
            assert f'plugins/{plugin}' in workflow
        assert '"$prefix/bin/myspec" doctor' in workflow
        assert '"$prefix/bin/build-and-verify" verify --project source' in workflow
        assert 'p.repository?.url !== "https://github.com/liuli195/my-agent-skills"' not in workflow
        assert "p.repository?.url !== s.repository?.url" in workflow
        assert "p.repository?.directory !== s.repository?.directory" in workflow
        assert 'npm publish "$MYSPEC_TARBALL" --provenance --access public' in workflow
        assert 'npm publish "$BUILD_AND_VERIFY_TARBALL" --provenance --access public' in workflow
        assert "actions/upload-artifact@v6" in workflow
        assert "actions/upload-artifact@v4" not in workflow
        assert "actions/upload-artifact@v5" not in workflow
        assert "FIRST_PUBLISH_REQUIRED" in workflow
        assert "env.FIRST_PUBLISH_REQUIRED != 'true'" in workflow
        assert workflow.index("Upload npm package candidates") < workflow.index("Publish release channel")
        for plugin in ("my-spec", "build-and-verify"):
            manifest = f"./source/plugins/{plugin}/package.json"
            assert workflow.count(manifest) == 3
            path = tmp_path / manifest.removeprefix("./")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
            loaded = subprocess.run(
                ["node", "-e", "require(process.argv[1])", manifest],
                cwd=tmp_path,
                text=True,
                capture_output=True,
                check=False,
            )
            assert loaded.returncode == 0, loaded.stderr


@pytest.mark.parametrize(
    ("changed_field", "expected_returncode"),
    [(None, 0), ("url", 1), ("directory", 1)],
)
def test_release_workflows_compare_packed_repository_metadata(
    tmp_path: Path, changed_field: str | None, expected_returncode: int
) -> None:
    source = {
        "name": "@liuli195/myspec",
        "repository": {
            "type": "git",
            "url": "https://github.com/liuli195/my-agent-skills",
            "directory": "plugins/my-spec",
        },
    }
    packed = json.loads(json.dumps(source))
    if changed_field:
        packed["repository"][changed_field] = "changed"
    source_path = tmp_path / "source.json"
    packed_path = tmp_path / "packed.json"
    write_json(source_path, source)
    write_json(packed_path, packed)

    for workflow_path in (
        REPO_ROOT / ".github" / "workflows" / "release.yml",
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
    ):
        workflow = workflow_path.read_text(encoding="utf-8")
        match = re.search(
            r"node -e '([^']+)' \./source/plugins/my-spec/package.json "
            r'"\$prefix/lib/node_modules/\$package_name/package.json" "\$package_name"',
            workflow,
        )
        assert match is not None
        result = subprocess.run(
            [
                "node",
                "-e",
                match.group(1),
                str(source_path),
                str(packed_path),
                source["name"],
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == expected_returncode, result.stderr


def test_release_workflows_reject_invalid_selection_before_package_steps() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert workflow.index("Validate release plan") < workflow.index("Normalize selected npm packages")
    assert "--bump-plugins \"$BUMP_PLUGINS\"" in workflow


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
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "pr-flow",
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


def test_ci_publish_rejects_metadata_before_candidate_release_tree_is_built(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    write_npm_package(
        project,
        "my-spec",
        repository_url="https://github.com/other/repository.git",
    )
    release_flow = load_release_flow_module()
    monkeypatch.setattr(
        release_flow,
        "run_ci_publish_remote",
        lambda *_args: (_ for _ in ()).throw(AssertionError("candidate tree must not be built")),
    )

    result = run(
        "ci-publish",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "my-spec",
        "--authorize-ci-publish",
        env={
            **os.environ,
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "liuli195/my-agent-skills",
        },
    )

    assert result.returncode == 1
    assert "npm_repository_url_mismatch" in result.stdout


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
    write_plugin_manifests(project, "pr-flow", "9.9.1")
    write_plugin_manifests(project, "release-flow", "9.9.1")
    write_json(project / ".agents" / "plugins" / "marketplace.json", {"name": "local-dev"})

    preflight_calls = []
    remote_calls = []

    def fake_preflight(project_arg, tag, version, bump_plugins, config, projection):
        preflight_calls.append((project_arg, tag, version, bump_plugins, config.release_channel_branch, projection.path))
        return []

    def fake_ci_publish_remote(project_arg, config, projection, tag):
        remote_calls.append((project_arg, config.release_channel_branch, projection.path, tag))
        return {
            "release_url": "https://github.example/releases/tag/v9.9.1",
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
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "pr-flow",
        "--authorize-ci-publish",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: ci_published" in result.stdout
    assert "channel_branch: marketplace" in result.stdout
    assert "tag: v9.9.1" in result.stdout
    assert "release_url: https://github.example/releases/tag/v9.9.1" in result.stdout
    assert "marketplace_commit: marketplace-commit" in result.stdout
    assert "tag_commit: tag-commit" in result.stdout
    assert "workflow_run_url: https://github.example/actions/runs/1" in result.stdout
    projection_path = project.resolve() / ".release-flow" / "projection.yaml"
    assert preflight_calls == [(project.resolve(), "v9.9.1", "9.9.1", ["pr-flow"], "marketplace", projection_path)]
    assert remote_calls == [(project.resolve(), "marketplace", projection_path, "v9.9.1")]
    source_marketplace = json.loads((project / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    assert source_marketplace["name"] == "local-dev"


def test_existing_release_must_match_the_current_projection_tree(
    tmp_path: Path, monkeypatch
) -> None:
    release_flow = load_release_flow_module()
    project = tmp_path / "project"
    write_release_flow_files(project)
    config = release_flow.read_config(project)
    projection = release_flow.read_projection(project)
    tree_ids = iter(["expected-tree", "different-remote-tree"])
    monkeypatch.setattr(release_flow, "remote_ref_oid", lambda *_args: "same-commit")
    monkeypatch.setattr(release_flow, "run_checked", lambda *_args: None)
    monkeypatch.setattr(release_flow, "copy_git_auth_config", lambda *_args: None)
    monkeypatch.setattr(release_flow, "origin_url", lambda *_args: "https://example.invalid/repo.git")
    monkeypatch.setattr(release_flow, "git_output", lambda *_args: next(tree_ids))

    error = release_flow.existing_release_ref_error(
        project, config, projection, "v9.9.1"
    )

    assert error == "release_projection_mismatch: v9.9.1"


def test_ci_publish_recovers_an_existing_tag_without_republishing_channel(
    tmp_path: Path, monkeypatch
) -> None:
    release_flow = load_release_flow_module()
    project = tmp_path / "project"
    write_release_flow_files(project)
    recovered = {
        "release_url": "https://github.example/releases/tag/v9.9.1",
        "marketplace_commit": "same-commit",
        "tag_commit": "same-commit",
        "workflow_run_url": "https://github.example/actions/runs/2",
    }
    monkeypatch.setattr(
        release_flow,
        "preflight_errors",
        lambda *_args: ["release already exists: v9.9.1"],
    )
    monkeypatch.setattr(
        release_flow,
        "recover_existing_ci_publish",
        lambda *_args: recovered,
    )
    monkeypatch.setattr(
        release_flow,
        "run_ci_publish_remote",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not republish channel")),
    )

    result = run(
        "ci-publish",
        "--project",
        str(project),
        "--tag",
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "my-spec",
        "--authorize-ci-publish",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: ci_published" in result.stdout
    assert "tag_commit: same-commit" in result.stdout


def test_ci_publish_requires_authorization_without_dry_run(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run(
        "ci-publish",
        "--project",
        str(project),
        "--tag",
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "pr-flow",
    )

    assert result.returncode == 2
    assert "ci_publish_requires_authorize_ci_publish" in result.stdout


def test_release_flow_local_e2e(tmp_path: Path, monkeypatch) -> None:
    release_flow = load_release_flow_module()
    project = tmp_path / "project"

    setup = run("setup", "--project", str(project), "--authorize-project-files")
    assert setup.returncode == 0, setup.stdout + setup.stderr
    write_plugin_manifests(project, "pr-flow", "9.9.1")
    write_plugin_manifests(project, "release-flow", "9.9.1")
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
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "pr-flow",
    )
    assert preflight.returncode == 0, preflight.stdout + preflight.stderr
    assert preflight_calls == [
        (project.resolve(), "v9.9.1", "9.9.1", ["pr-flow"], "marketplace", project.resolve() / ".release-flow" / "projection.yaml")
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
        "v9.9.1",
        "--version",
        "9.9.1",
        "--bump-plugins",
        "pr-flow",
        "--authorize-publish",
        env=env,
    )
    assert publish.returncode == 0, publish.stdout + publish.stderr
    assert calls.read_text(encoding="utf-8").count("workflow run") == 2
    assert not (project / ".release-flow" / ".gitignore").exists()
    assert not (project / ".release-flow" / "releases").exists()


def test_preflight_rejects_changed_marketplace_input_without_bump(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    (project / "plugins" / "pr-flow" / "content.txt").write_text("changed\n", encoding="utf-8")

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "",
    )

    assert result.returncode == 1
    assert "plugin_requires_bump: pr-flow" in result.stdout


def test_preflight_refreshes_remote_baseline_before_comparing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    old_main = git(project, "rev-parse", "origin/main").stdout.strip()
    old_marketplace = git(project, "rev-parse", "origin/marketplace").stdout.strip()
    (project / "plugins" / "pr-flow" / "content.txt").write_text("remote\n", encoding="utf-8")
    assert git(project, "add", "plugins/pr-flow/content.txt").returncode == 0
    assert git(project, "commit", "-m", "remote marketplace content").returncode == 0
    assert git(project, "push", "origin", "HEAD:refs/heads/main").returncode == 0
    assert git(project, "push", "origin", "HEAD:refs/heads/marketplace").returncode == 0
    assert git(project, "update-ref", "refs/remotes/origin/main", old_main).returncode == 0
    assert git(project, "update-ref", "refs/remotes/origin/marketplace", old_marketplace).returncode == 0

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: preflight_passed" in result.stdout


def test_preflight_rejects_changed_unprojected_marketplace_input_without_bump(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    projection = project / ".release-flow" / "projection.yaml"
    projection.write_text(
        projection.read_text(encoding="utf-8").replace("      - release-flow\n", ""),
        encoding="utf-8",
    )
    (project / "plugins" / "release-flow" / "content.txt").write_text("changed\n", encoding="utf-8")

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "",
    )

    assert result.returncode == 1
    assert "plugin_requires_bump: release-flow" in result.stdout


def test_preflight_rejects_changed_npm_input_without_bump_when_not_in_projection(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    (project / "plugins" / "build-and-verify" / "content.txt").write_text("changed\n", encoding="utf-8")

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "",
    )

    assert result.returncode == 1
    assert "plugin_requires_bump: build-and-verify" in result.stdout


def test_preflight_rejects_shared_npm_input_when_only_one_npm_plugin_is_selected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    (project / "plugins" / "tool-lifecycle" / "python" / "management.py").write_text(
        "changed\n", encoding="utf-8"
    )

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "build-and-verify",
    )

    assert result.returncode == 1
    assert "plugin_requires_bump: my-spec" in result.stdout


def test_preflight_checks_repository_metadata_only_for_selected_npm_plugin(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    write_npm_package(
        project,
        "build-and-verify",
        repository_url="https://github.com/other/repository.git",
    )
    assert git(project, "add", "plugins/build-and-verify/package.json").returncode == 0
    assert git(project, "commit", "-m", "invalid build metadata baseline").returncode == 0
    assert git(project, "push", "origin", "HEAD:refs/heads/main").returncode == 0
    assert git(project, "push", "origin", "HEAD:refs/heads/marketplace").returncode == 0
    assert git(project, "fetch", "origin", "main").returncode == 0
    assert git(project, "fetch", "origin", "marketplace").returncode == 0

    selected_other = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "my-spec",
    )
    assert selected_other.returncode == 0, selected_other.stdout + selected_other.stderr

    selected_invalid = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "build-and-verify",
    )
    assert selected_invalid.returncode == 1
    assert "npm_repository_url_mismatch" in selected_invalid.stdout
    assert "plugins/build-and-verify/package.json" in selected_invalid.stdout


def test_preflight_rejects_npm_metadata_drift_without_bump(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    write_json(
        project / "plugins" / "my-spec" / "package.json",
        {"version": "1.0.0", "description": "changed"},
    )

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "",
    )

    assert result.returncode == 1
    assert "plugin_requires_bump: my-spec" in result.stdout


def test_preflight_rejects_selected_content_without_version_advancement(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    (project / "plugins" / "release-flow" / "content.txt").write_text("changed\n", encoding="utf-8")

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "release-flow",
    )

    assert result.returncode == 1
    assert "plugin_version_not_bumped: release-flow" in result.stdout


def test_preflight_accepts_semver_prerelease_advancement(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote, version="1.0.0-alpha")
    advance_plugin_version_on_source_ref(project, "release-flow", "1.0.0-beta")

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0-beta",
        "--version",
        "1.0.0-beta",
        "--bump-plugins",
        "release-flow",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: preflight_passed" in result.stdout


def test_preflight_rejects_selected_version_downgrade(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    advance_plugin_version_on_source_ref(project, "release-flow", "0.9.0")

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.9.0",
        "--version",
        "0.9.0",
        "--bump-plugins",
        "release-flow",
    )

    assert result.returncode == 1
    assert "plugin_version_not_bumped: release-flow" in result.stdout


def test_preflight_accepts_selected_npm_plugin_with_all_versions_advanced(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    (project / "plugins" / "build-and-verify" / "content.txt").write_text("changed\n", encoding="utf-8")
    advance_plugin_version_on_source_ref(project, "build-and-verify", "1.0.1")

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.1",
        "--version",
        "1.0.1",
        "--bump-plugins",
        "build-and-verify",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: preflight_passed" in result.stdout


def test_preflight_checks_npm_package_version_with_plugin_manifests(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    (project / "plugins" / "build-and-verify" / "content.txt").write_text("changed\n", encoding="utf-8")
    write_plugin_manifests(project, "build-and-verify", "1.0.1")

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.1",
        "--version",
        "1.0.1",
        "--bump-plugins",
        "build-and-verify",
    )

    assert result.returncode == 1
    assert "manifest_version_mismatch: plugins/build-and-verify/package.json" in result.stdout


def test_preflight_accepts_projection_only_change_without_plugin_input_drift(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    projection = project / ".release-flow" / "projection.yaml"
    projection.write_text(
        projection.read_text(encoding="utf-8").replace(
            "displayName: My Agent Skills Marketplace",
            "displayName: Local Test Marketplace",
        ),
        encoding="utf-8",
    )

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: preflight_passed" in result.stdout


def test_preflight_rejects_shared_npm_packer_input_when_only_one_npm_plugin_is_selected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    init_release_input_project(project, remote)
    (project / "plugins" / "tool-lifecycle" / "pack.py").write_text("changed\n", encoding="utf-8")

    result = run_cli(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v1.0.0",
        "--version",
        "1.0.0",
        "--bump-plugins",
        "build-and-verify",
    )

    assert result.returncode == 1
    assert "plugin_requires_bump: my-spec" in result.stdout
