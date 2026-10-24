import importlib.util
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

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


# Only the exact file leaves used by this command-line contract are declared.
RELEASE_TEST_PLUGINS = ("pr-flow", "release-flow", "build-and-verify", "my-spec")
RELEASE_TEST_INPUTS = {
    "pr-flow": ("plugins/pr-flow",),
    "release-flow": ("plugins/release-flow",),
    "build-and-verify": ("plugins/build-and-verify", "plugins/tool-lifecycle/python/management.py", "plugins/tool-lifecycle/pack.py"),
    "my-spec": ("plugins/my-spec", "plugins/tool-lifecycle/python/management.py", "plugins/tool-lifecycle/pack.py"),
}


@pytest.fixture
def flow_root() -> Path:
    return REPO_ROOT / "__release_flow_memory__"


@pytest.fixture(autouse=True)
def release_memory(monkeypatch, flow_root):
    from tests.support.command_stubs import CommandStub, completed
    from tests.support.pr_flow_invocation import fixed_text_file_io

    module = load_release_flow_module()
    project = flow_root / "project"
    expected = flow_root / "preflight/expected"
    project_files = (
        ".release-flow/config.yaml", ".release-flow/projection.yaml", ".release-flow/.gitignore",
        ".github/workflows/release.yml", ".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json",
        ".build-and-verify/config.json", ".build-and-verify/runtime/version.json",
        "plugins/tool-lifecycle/python/management.py", "plugins/tool-lifecycle/pack.py",
    )
    plugin_files = tuple(
        f"plugins/{plugin}/{relative}"
        for plugin in RELEASE_TEST_PLUGINS
        for relative in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json", "package.json", "content.txt")
    )
    relative_files = (*project_files, *plugin_files)
    files = {root / relative: None for root in (project, expected) for relative in relative_files}
    files.update({flow_root / relative: None for relative in ("vars.json", "release-vars.json", "outside.json", "gh-calls.txt", "workflow-run-input.json")})
    directories = {flow_root, *(flow_root / name for name in ("source", "release-tree", "checkout", "channel", "bin", "project-projected")), project / ".release-flow/releases", project / "plugins/other"}
    # Missing registered plugins are explicit absent inputs, not arbitrary tree entries.
    directories.update(project / "plugins" / plugin for plugin in ("dev-flow", "subagent-policy", "plugin-sync", "retro-to-issues", "data-store"))
    for path in files:
        directories.update(parent for parent in path.parents if parent == flow_root or flow_root in parent.parents)
    fixed_text_file_io(monkeypatch, root=flow_root, files=files, directories=directories)
    state = {"files": files, "origin": "", "commands": CommandStub(), "dispatch": CommandStub(consume=True), "calls_path": None}

    def external_command(command, **kwargs):
        raw = tuple(str(part) for part in command)
        if raw in {
            ("git", "-C", str(project), "config", "--get", "remote.origin.url"),
            ("git", "-C", str(REPO_ROOT), "config", "--get", "remote.origin.url"),
        }:
            origin = "https://github.com/liuli195/my-agent-skills.git" if raw[2] == str(REPO_ROOT) else state["origin"]
            return completed(raw, stdout=origin, returncode=0 if origin else 1)
        if raw and raw[0] == "gh":
            path = state["calls_path"]
            if path is not None:
                files[path] = (files[path] or "") + " ".join(raw[1:]) + "\n"
            return state["dispatch"](*raw)
        return state["commands"](*raw)

    monkeypatch.setattr(module.subprocess, "run", external_command)
    original_which = module.shutil.which
    monkeypatch.setattr(module.shutil, "which", lambda command: "gh" if command == "gh" else original_which(command))

    @contextlib.contextmanager
    def temporary_preflight(*, prefix):
        assert prefix == "release-flow-preflight-", f"unexpected_temporary_directory: {prefix}"
        yield str(flow_root / "preflight")

    def copy_preflight_inputs(source, target):
        assert (source, target) == (project, expected)
        for relative in relative_files:
            files[expected / relative] = files[project / relative]
        expected.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(module.tempfile, "TemporaryDirectory", temporary_preflight)
    monkeypatch.setattr(module, "copy_project_for_expected", copy_preflight_inputs)
    return state


def git(release_memory, project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    from tests.support.command_stubs import completed
    if args == ("init",):
        return completed(args)
    if len(args) == 4 and args[:3] == ("remote", "add", "origin"):
        release_memory["origin"] = args[3]
        return completed(args)
    raise AssertionError(f"unexpected_setup_command: {args}")


def fake_gh_for_publish(release_memory, bin_dir: Path, calls: Path, *, always_eof: bool = False) -> Path:
    release_memory["calls_path"] = calls
    for version, plugin in (("1.0.0", "my-spec"), ("9.9.1", "pr-flow")):
        command = ("workflow", "run", ".github/workflows/release.yml", "--ref", "main", "-f", f"tag=v{version}", "-f", f"version={version}", "-f", f"bumpPlugins={plugin}")
        for index in range(4):
            eof = always_eof or index == 0
            release_memory["dispatch"].add(command, stderr='Get "https://api.github.com/repos/x/actions/workflows/release.yml": EOF' if eof else "", returncode=int(eof))
    return bin_dir


def prepare_release_input_case(release_memory, flow_root: Path, *, baseline="1.0.0", versions=None, package_versions=None, changed=frozenset(), shared_input=None) -> Path:
    project = flow_root / "project"
    write_release_flow_files(project)
    versions = versions or {}
    package_versions = package_versions or {}
    release_memory["origin"] = "https://github.com/liuli195/my-agent-skills.git"
    commands = release_memory["commands"]
    for plugin in RELEASE_TEST_PLUGINS:
        current = versions.get(plugin, baseline)
        write_plugin_manifests(project, plugin, current)
        if plugin in {"build-and-verify", "my-spec"}:
            write_npm_package(project, plugin, version=package_versions.get(plugin, current))
        for suffix in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json", *(["package.json"] if plugin in {"build-and-verify", "my-spec"} else [])):
            relative = f"plugins/{plugin}/{suffix}"
            for branch, version in (("marketplace", baseline), ("main", current)):
                commands.add(("git", "-C", str(project), "show", f"origin/{branch}:{relative}"), stdout=json.dumps({"version": version}))
        for revisions in (("origin/marketplace",), ("origin/main",), ("origin/main", "origin/marketplace")):
            commands.add(("git", "-C", str(project), "diff", "--quiet", *revisions, "--", *RELEASE_TEST_INPUTS[plugin]), returncode=int(plugin in changed))
    if shared_input is not None:
        assert shared_input in {"plugins/tool-lifecycle/python/management.py", "plugins/tool-lifecycle/pack.py"}
    for branch in ("main", "marketplace"):
        commands.add(("git", "-C", str(project), "fetch", "--depth=1", "origin", f"+{branch}:refs/remotes/origin/{branch}"))
        commands.add(("git", "-C", str(project), "rev-parse", "--verify", f"origin/{branch}"), stdout="a" * 40)
    for plugin in ("dev-flow", "subagent-policy", "plugin-sync", "retro-to-issues", "data-store"):
        commands.add(("git", "-C", str(project), "ls-tree", "--name-only", "origin/marketplace", "--", f"plugins/{plugin}"), stdout="")
    for version in (baseline, *versions.values(), *package_versions.values()):
        commands.add(("git", "-C", str(project), "ls-remote", "--tags", "origin", f"refs/tags/v{version}"), stdout="")
    return project


def preflight_result(project: Path, selection: str, *, version="1.0.0"):
    return run("preflight", "--project", str(project), "--tag", f"v{version}", "--version", version, "--bump-plugins", selection)


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


def test_setup_dry_run_does_not_write_project_files(flow_root: Path) -> None:
    project = flow_root / "project"

    result = run("setup", "--project", str(project))

    assert result.returncode == 0
    assert "status: dry_run" in result.stdout
    assert "would_write: .release-flow/config.yaml" in result.stdout
    assert "would_write: .release-flow/projection.yaml" in result.stdout
    assert "would_write: .release-flow/.gitignore" not in result.stdout
    assert "would_write: .github/workflows/release.yml" in result.stdout
    assert not (project / ".release-flow").exists()
    assert not (project / ".github").exists()


def test_github_plan_outputs_expected_settings(flow_root: Path) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)

    result = run("github-plan", "--project", str(project))

    assert result.returncode == 0
    assert "status: github_plan" in result.stdout
    assert "actions_workflow_permissions: read-and-write" in result.stdout
    assert "rulesets:" not in result.stdout
    assert "branch_protection_fallback:" not in result.stdout
    assert "actions_variables:" not in result.stdout
    assert "CODEX_MARKETPLACE_CATALOG_NAME" not in result.stdout


def test_github_plan_does_not_print_marketplace_identity_variables(flow_root: Path) -> None:
    project = flow_root / "project"
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


def test_validate_rejects_missing_npm_repository_metadata(flow_root: Path, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    write_json(project / "plugins" / "my-spec" / "package.json", {"version": "1.0.0"})
    assert git(release_memory, project, "init").returncode == 0
    assert git(release_memory,
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
    flow_root: Path, repository_url: str, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec", repository_url=repository_url)
    assert git(release_memory, project, "init").returncode == 0
    assert git(release_memory,
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
    flow_root: Path, repository_url: str, expected_error: str, actual: str, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec", repository_url=repository_url)
    assert git(release_memory, project, "init").returncode == 0
    assert git(release_memory,
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


def test_validate_checks_all_existing_registered_npm_packages(flow_root: Path, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec")
    write_npm_package(
        project,
        "build-and-verify",
        repository_url="https://github.com/other/repository.git",
    )
    assert git(release_memory, project, "init").returncode == 0
    assert git(release_memory,
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


def test_validate_reports_wrong_existing_npm_repository_directory(flow_root: Path, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec", directory="plugins/other")
    (project / "plugins" / "other").mkdir(parents=True)
    assert git(release_memory, project, "init").returncode == 0
    assert git(release_memory,
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
    flow_root: Path,
) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec")
    environment = {
        **{key: value for key, value in os.environ.items() if key != "GITHUB_REPOSITORY"},
        "GITHUB_ACTIONS": "false",
    }

    result = run("validate", "--project", str(project), env=environment)

    assert result.returncode == 1
    assert "npm_repository_identity_unavailable" in result.stdout
    assert "plugins/my-spec/package.json" in result.stdout
    assert "expected=GitHub owner/repository" in result.stdout
    assert "nextAction: configure a GitHub origin or trusted GITHUB_REPOSITORY" in result.stdout


def test_validate_requires_repository_identity_in_github_actions(flow_root: Path, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec")
    assert git(release_memory, project, "init").returncode == 0
    assert git(release_memory,
        project,
        "remote",
        "add",
        "origin",
        "https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0
    environment = {
        key: value
        for key, value in os.environ.items()
        if key != "GITHUB_REPOSITORY"
    }
    environment["GITHUB_ACTIONS"] = "true"

    result = run("validate", "--project", str(project), env=environment)

    assert result.returncode == 1
    assert "npm_repository_identity_unavailable" in result.stdout
    assert "plugins/my-spec/package.json" in result.stdout
    assert "GITHUB_REPOSITORY" in result.stdout
    assert "actual=<missing>" in result.stdout


def test_validate_uses_origin_outside_github_actions(flow_root: Path, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec")
    assert git(release_memory, project, "init").returncode == 0
    assert git(release_memory,
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


def test_validate_rejects_conflicting_github_actions_repository_identity(flow_root: Path, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec")
    assert git(release_memory, project, "init").returncode == 0
    assert git(release_memory,
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


def test_configure_github_requires_authorization(flow_root: Path) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)

    result = run("configure-github", "--project", str(project))

    assert result.returncode == 2
    assert "configure_github_requires_authorize_github" in result.stdout


def test_configure_github_dry_run_prints_manual_steps(flow_root: Path) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)

    result = run("configure-github", "--project", str(project), "--dry-run")

    assert result.returncode == 0
    assert "status: manual_steps" in result.stdout
    assert "Set Actions workflow permissions to read-and-write" in result.stdout
    assert "Rulesets" not in result.stdout
    assert "rulesets" not in result.stdout
    assert "Create GitHub Actions Variables" not in result.stdout


def test_configure_github_dry_run_does_not_print_marketplace_identity_variables(flow_root: Path) -> None:
    project = flow_root / "project"
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


def test_removed_commands_are_not_registered(flow_root: Path) -> None:
    project = flow_root / "project"
    workflow_run_file = flow_root / "workflow-run-input.json"
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


def test_project_rejects_transform_path_outside_project(flow_root: Path) -> None:
    project = flow_root / "project"
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
    assert not (flow_root / "outside.json").exists()


def test_project_rejects_vars_file_argument(flow_root: Path) -> None:
    project = flow_root / "project"
    vars_file = flow_root / "vars.json"
    write_release_flow_files(project, marketplace_identity_projection())
    write_json(vars_file, {})

    result = run("project", "--project", str(project), "--vars-file", str(vars_file))

    assert result.returncode == 2


def test_preflight_rejects_github_vars_file_argument(flow_root: Path) -> None:
    project = flow_root / "project"
    vars_file = flow_root / "vars.json"
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


def test_ci_publish_rejects_vars_file_argument(flow_root: Path) -> None:
    project = flow_root / "project"
    vars_file = flow_root / "vars.json"
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


def test_validate_rejects_projection_variable_values(flow_root: Path) -> None:
    project = flow_root / "project"
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


def test_project_applies_json_env_transform(flow_root: Path) -> None:
    project = flow_root / "project"
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


def test_project_generates_codex_marketplace_from_projection_identity(flow_root: Path) -> None:
    project = flow_root / "project"
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


def test_validate_rejects_invalid_branch_mode(flow_root: Path) -> None:
    project = flow_root / "project"
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


def test_project_applies_json_env_transform_inside_list(flow_root: Path) -> None:
    project = flow_root / "project"
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


def test_project_adds_missing_final_dict_key(flow_root: Path) -> None:
    project = flow_root / "project"
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


def test_project_rejects_negative_json_pointer_list_index(flow_root: Path) -> None:
    project = flow_root / "project"
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


def test_preflight_rejects_missing_bump_plugins(flow_root: Path) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)

    result = run("preflight", "--project", str(project), "--tag", "v9.9.1", "--version", "9.9.1")

    assert result.returncode == 2


def test_preflight_rejects_unknown_bump_plugin(flow_root: Path) -> None:
    project = flow_root / "project"
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
    flow_root: Path,
    errors: list[str],
    *,
    bump_plugins: list[str],
    projection: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    project = flow_root / "project"
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


def test_preflight_accepts_partial_plugin_bump(flow_root: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        flow_root,
        [],
        bump_plugins=["pr-flow"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: preflight_passed" in result.stdout
    assert "bumpPlugins: pr-flow" in result.stdout


def test_preflight_rejects_bump_not_merged_to_source_ref(flow_root: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        flow_root,
        ["source_ref_requires_pr: main: plugins/pr-flow/.codex-plugin/plugin.json"],
        bump_plugins=["pr-flow"],
    )

    assert result.returncode == 1
    assert "source_ref_requires_pr: main: plugins/pr-flow/.codex-plugin/plugin.json" in result.stdout


def test_preflight_source_ref_requires_pr_prints_next_action(flow_root: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        flow_root,
        ["source_ref_requires_pr: main: plugins/pr-flow/.codex-plugin/plugin.json"],
        bump_plugins=["pr-flow"],
    )

    assert result.returncode == 1
    assert "error: source_ref_requires_pr: main: plugins/pr-flow/.codex-plugin/plugin.json" in result.stdout
    assert (
        "nextAction: create and merge the version bump through PR Flow, "
        "then rerun release-flow preflight"
    ) in result.stdout


def test_preflight_manifest_mismatch_prints_next_action(flow_root: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        flow_root,
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
    flow_root: Path, monkeypatch
) -> None:
    release_flow = load_release_flow_module()
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if "ls-remote" in command:
            return subprocess.CompletedProcess(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(release_flow.subprocess, "run", fake_run)

    assert release_flow.remote_release_errors(flow_root, "v9.9.1") == []
    assert len(calls) == 1


def test_preflight_existing_release_prints_next_action(flow_root: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        flow_root,
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
    flow_root: Path, monkeypatch
) -> None:
    errors = [
        "release already exists: v9.9.1",
        "manifest_version_mismatch: plugins/pr-flow/.codex-plugin/plugin.json",
        "source_ref_requires_pr: main: plugins/pr-flow/.codex-plugin/plugin.json",
        "plugin_requires_bump: release-flow",
    ]

    result = run_preflight_with_errors(
        monkeypatch,
        flow_root,
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


def test_preflight_ignores_legacy_build_and_verify_runtime(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, baseline="9.9.0")
    write_json(project / ".build-and-verify/config.json", {"version": 1, "build": {"checks": []}, "verify": {"checks": []}})
    write_json(project / ".build-and-verify/runtime/version.json", {"plugin": "build-and-verify", "plugin_version": "9.8.0", "runtime_version": "9.8.0"})
    result = preflight_result(project, "build-and-verify", version="9.9.0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "runtime_update_required" not in result.stdout


def test_preflight_merges_repeated_bump_plugins(flow_root: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        flow_root,
        [],
        bump_plugins=["pr-flow", "release-flow"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "bumpPlugins: pr-flow,release-flow" in result.stdout


def test_remote_ref_manifest_version_fetches_missing_channel_branch_for_actions_checkout(
    flow_root: Path,
    monkeypatch,
) -> None:
    release_flow = load_release_flow_module()
    checkout = flow_root / "checkout"
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


def test_preflight_accepts_empty_bump_plugins_when_versions_do_not_drift(flow_root: Path, monkeypatch) -> None:
    env = os.environ.copy()
    env["GITHUB_REPOSITORY"] = "liuli195/my-agent-skills"

    result = run_preflight_with_errors(
        monkeypatch,
        flow_root,
        [],
        bump_plugins=[""],
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: preflight_passed" in result.stdout
    assert "bumpPlugins: " in result.stdout


def test_preflight_rejects_unbumped_manifest_drift(flow_root: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        flow_root,
        ["plugin_requires_bump: pr-flow"],
        bump_plugins=[""],
    )

    assert result.returncode == 1
    assert "plugin_requires_bump: pr-flow" in result.stdout


def test_preflight_rejects_remote_tag_that_already_exists(flow_root: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        flow_root,
        ["release already exists: v9.9.1"],
        bump_plugins=["pr-flow"],
    )

    assert result.returncode == 1
    assert "release already exists: v9.9.1" in result.stdout


def test_preflight_checks_projection_without_channel_tree(flow_root: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        flow_root,
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


def test_preflight_rejects_channel_tree_argument(flow_root: Path) -> None:
    project = flow_root / "project"
    channel_tree = flow_root / "channel"
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


def test_publish_rejects_dry_run_argument(flow_root: Path) -> None:
    project = flow_root / "project"
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


def test_publish_rejects_metadata_before_triggering_remote_workflow(flow_root: Path, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    write_npm_package(
        project,
        "my-spec",
        repository_url="https://github.com/other/repository.git",
    )
    assert git(release_memory, project, "init").returncode == 0
    assert git(release_memory,
        project,
        "remote",
        "add",
        "origin",
        "https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0
    calls = flow_root / "gh-calls.txt"
    bin_dir = flow_root / "bin"
    fake_gh_for_publish(release_memory, bin_dir, calls)
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
    flow_root: Path, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    write_npm_package(project, "my-spec")
    assert git(release_memory, project, "init").returncode == 0
    assert git(release_memory,
        project,
        "remote",
        "add",
        "origin",
        "https://github.com/liuli195/my-agent-skills.git",
    ).returncode == 0
    calls = flow_root / "gh-calls.txt"
    bin_dir = flow_root / "bin"
    fake_gh_for_publish(release_memory, bin_dir, calls)
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


def test_publish_retries_workflow_run_eof_then_succeeds(flow_root: Path, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    calls = flow_root / "gh-calls.txt"
    bin_dir = flow_root / "bin"
    fake_gh_for_publish(release_memory, bin_dir, calls)
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


def test_publish_reports_last_eof_after_workflow_run_retries_exhausted(flow_root: Path, release_memory) -> None:
    project = flow_root / "project"
    write_release_flow_files(project)
    calls = flow_root / "gh-calls.txt"
    bin_dir = flow_root / "bin"
    fake_gh_for_publish(release_memory, bin_dir, calls, always_eof=True)
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


def test_publish_requires_authorization_without_dry_run(flow_root: Path) -> None:
    project = flow_root / "project"
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
    from tests.support.npm_candidates import TARBALL_ENV

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
    assert TARBALL_ENV["myspec"] == "MYSPEC_TEST_TARBALL"
    candidate_setup = (REPO_ROOT / "tests/integration/conftest.py").read_text(encoding="utf-8")
    assert "supplied = os.environ.get(TARBALL_ENV[name])" in candidate_setup
    assert "prepare_candidate(name, root / name, tarball=Path(supplied) if supplied else None)" in candidate_setup
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


def test_release_workflows_publish_only_verified_selected_npm_packages() -> None:
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


def test_ci_publish_rejects_dry_run_argument(flow_root: Path) -> None:
    project = flow_root / "project"
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
    assert not (flow_root / "project-projected").exists()


def test_ci_publish_copies_checkout_git_auth_config_to_release_tree(flow_root: Path, monkeypatch) -> None:
    release_flow = load_release_flow_module()
    source = flow_root / "source"
    release_tree = flow_root / "release-tree"
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


def test_origin_is_github_uses_exact_host(flow_root: Path, monkeypatch) -> None:
    release_flow = load_release_flow_module()
    project = flow_root / "project"
    project = flow_root / "project"

    monkeypatch.setattr(release_flow, "origin_url", lambda _project: "https://evilgithub.com/org/repo.git")
    assert not release_flow.origin_is_github(project)

    monkeypatch.setattr(release_flow, "origin_url", lambda _project: "https://github.com/org/repo.git")
    assert release_flow.origin_is_github(project)

    monkeypatch.setattr(release_flow, "origin_url", lambda _project: "git@github.com:org/repo.git")
    assert release_flow.origin_is_github(project)


def test_ci_publish_rejects_metadata_before_candidate_release_tree_is_built(
    flow_root: Path, monkeypatch, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root)
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


def test_ci_publish_authorized_pushes_channel_tag_and_creates_release(flow_root: Path, monkeypatch) -> None:
    release_flow = load_release_flow_module()
    project = flow_root / "project"
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


def test_ci_publish_recovers_an_existing_tag_without_republishing_channel(
    flow_root: Path, monkeypatch
) -> None:
    release_flow = load_release_flow_module()
    project = flow_root / "project"
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


def test_ci_publish_requires_authorization_without_dry_run(flow_root: Path) -> None:
    project = flow_root / "project"
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


def test_preflight_rejects_changed_marketplace_input_without_bump(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, changed={'pr-flow'})
    result = preflight_result(project, '', version='1.0.0')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'plugin_requires_bump: pr-flow' in result.stdout


def test_preflight_rejects_changed_unprojected_marketplace_input_without_bump(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, changed={'release-flow'})
    projection = project / '.release-flow/projection.yaml'
    projection.write_text(projection.read_text(encoding='utf-8').replace('      - release-flow\n', ''), encoding='utf-8')
    result = preflight_result(project, '', version='1.0.0')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'plugin_requires_bump: release-flow' in result.stdout


def test_preflight_rejects_changed_npm_input_without_bump_when_not_in_projection(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, changed={'build-and-verify'})
    result = preflight_result(project, '', version='1.0.0')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'plugin_requires_bump: build-and-verify' in result.stdout


def test_preflight_rejects_shared_npm_input_when_only_one_npm_plugin_is_selected(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, changed={'build-and-verify', 'my-spec'}, shared_input='plugins/tool-lifecycle/python/management.py')
    result = preflight_result(project, 'build-and-verify', version='1.0.0')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'plugin_requires_bump: my-spec' in result.stdout


def test_preflight_checks_repository_metadata_only_for_selected_npm_plugin(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root)
    write_npm_package(project, "build-and-verify", repository_url="https://github.com/other/repository.git")
    selected_other = preflight_result(project, "my-spec")
    assert selected_other.returncode == 0, selected_other.stdout + selected_other.stderr
    selected_invalid = preflight_result(project, "build-and-verify")
    assert selected_invalid.returncode == 1
    assert "npm_repository_url_mismatch" in selected_invalid.stdout
    assert "plugins/build-and-verify/package.json" in selected_invalid.stdout


def test_preflight_rejects_npm_metadata_drift_without_bump(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, changed={'my-spec'})
    write_json(project / 'plugins/my-spec/package.json', {'version': '1.0.0', 'description': 'changed'})
    result = preflight_result(project, '', version='1.0.0')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'plugin_requires_bump: my-spec' in result.stdout


def test_preflight_rejects_selected_content_without_version_advancement(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, changed={'release-flow'})
    result = preflight_result(project, 'release-flow', version='1.0.0')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'plugin_version_not_bumped: release-flow' in result.stdout


def test_preflight_accepts_semver_prerelease_advancement(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, baseline='1.0.0-alpha', versions={'release-flow': '1.0.0-beta'}, changed={'release-flow'})
    result = preflight_result(project, 'release-flow', version='1.0.0-beta')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'status: preflight_passed' in result.stdout


def test_preflight_rejects_selected_version_downgrade(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, versions={'release-flow': '0.9.0'}, changed={'release-flow'})
    result = preflight_result(project, 'release-flow', version='0.9.0')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'plugin_version_not_bumped: release-flow' in result.stdout


def test_preflight_accepts_selected_npm_plugin_with_all_versions_advanced(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, versions={'build-and-verify': '1.0.1'}, changed={'build-and-verify'})
    result = preflight_result(project, 'build-and-verify', version='1.0.1')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'status: preflight_passed' in result.stdout


def test_preflight_checks_npm_package_version_with_plugin_manifests(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, versions={'build-and-verify': '1.0.1'}, package_versions={'build-and-verify': '1.0.0'}, changed={'build-and-verify'})
    result = preflight_result(project, 'build-and-verify', version='1.0.1')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'manifest_version_mismatch: plugins/build-and-verify/package.json' in result.stdout


def test_preflight_accepts_projection_only_change_without_plugin_input_drift(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root)
    projection = project / '.release-flow/projection.yaml'
    projection.write_text(projection.read_text(encoding='utf-8').replace('displayName: My Agent Skills Marketplace', 'displayName: Local Test Marketplace'), encoding='utf-8')
    result = preflight_result(project, '', version='1.0.0')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'status: preflight_passed' in result.stdout


def test_preflight_rejects_shared_npm_packer_input_when_only_one_npm_plugin_is_selected(flow_root: Path, release_memory) -> None:
    project = prepare_release_input_case(release_memory, flow_root, changed={'build-and-verify', 'my-spec'}, shared_input='plugins/tool-lifecycle/pack.py')
    result = preflight_result(project, 'build-and-verify', version='1.0.0')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'plugin_requires_bump: my-spec' in result.stdout
