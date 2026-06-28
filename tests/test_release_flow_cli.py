import json
import os
import subprocess
import sys
from pathlib import Path

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


def run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_manifest(path: Path, version: str) -> None:
    write_json(path, {"version": version})


def git(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(project), *args],
        check=False,
        text=True,
        capture_output=True,
    )


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

records:
  directory: .release-flow/releases

github:
  actions:
    workflowPermissions: read-and-write
  rulesets:
    enabled: true
    branchProtectionFallback: false

manifests:
  versionFiles:
    - plugins/agent-guard/.codex-plugin/plugin.json
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
    assert "would_write: .release-flow/.gitignore" in result.stdout
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
    assert (project / ".release-flow" / ".gitignore").read_text(encoding="utf-8") == "/releases/\n"
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
    assert "rulesets: required" in result.stdout
    assert "branch_protection_fallback: false" in result.stdout
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
    assert (REPO_ROOT / ".release-flow" / ".gitignore").read_text(encoding="utf-8") == "/releases/\n"
    assert (REPO_ROOT / ".github" / "workflows" / "release.yml").is_file()


def test_current_repo_release_flow_version_files_cover_marketplace_plugins() -> None:
    config = yaml.safe_load((REPO_ROOT / ".release-flow" / "config.yaml").read_text(encoding="utf-8"))
    projection = yaml.safe_load((REPO_ROOT / ".release-flow" / "projection.yaml").read_text(encoding="utf-8"))
    version_files = set(config["manifests"]["versionFiles"])
    plugin_names = next(
        generator["plugins"]
        for generator in projection["generators"]
        if generator["path"] == ".agents/plugins/marketplace.json"
    )

    for plugin_name in plugin_names:
        assert f"plugins/{plugin_name}/.codex-plugin/plugin.json" in version_files
        assert f"plugins/{plugin_name}/.claude-plugin/plugin.json" in version_files


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
    assert "Create Rulesets for main, marketplace, and tags" in result.stdout
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


def test_release_init_creates_release_plan_only_for_tag(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    assert result.returncode == 0
    plan_path = project / ".release-flow" / "releases" / "v0.1.1" / "release-plan.json"
    assert plan_path.is_file()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["version"] == "0.1.1"
    assert plan["tag"] == "v0.1.1"
    assert plan["sourceRef"] == "main"
    assert plan["channelBranch"] == "marketplace"
    assert plan["workflowFile"] == ".github/workflows/release.yml"
    assert plan["projectionRegistry"] == ".release-flow/projection.yaml"
    assert "dryRun" not in plan
    assert not (project / "marketplace").exists()


def test_release_init_rejects_dry_run_flag(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1", "--dry-run")

    assert result.returncode == 2
    assert not (project / ".release-flow" / "releases" / "v0.1.1" / "release-plan.json").exists()


def test_release_init_refuses_existing_plan_without_replace(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    first = run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    result = run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    assert first.returncode == 0
    assert result.returncode == 1
    assert "release_plan_exists: v0.1.1" in result.stdout


def test_release_init_rejects_tag_with_path_separator(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("release-init", "--project", str(project), "--tag", "../escaped", "--version", "0.1.1")

    assert result.returncode == 1
    assert "invalid_release_tag:" in result.stdout
    assert not (project / ".release-flow" / "escaped").exists()
    assert not (project / ".release-flow" / "releases").exists()


def test_release_init_rejects_tag_with_leading_dash(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("release-init", "--project", str(project), "--tag=-d", "--version", "0.1.1")

    assert result.returncode == 1
    assert "invalid_release_tag: -d" in result.stdout
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
        "--release-plan",
        ".release-flow/releases/v0.1.1/release-plan.json",
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


def test_preflight_rejects_missing_release_plan(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("preflight", "--project", str(project), "--tag", "v0.1.1")

    assert result.returncode == 1
    assert "missing_release_plan: v0.1.1" in result.stdout


def test_preflight_rejects_tag_manifest_version_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.2")
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    result = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
    )

    assert result.returncode == 1
    assert "manifest_version_mismatch: plugins/agent-guard/.codex-plugin/plugin.json" in result.stdout


def test_preflight_rejects_release_plan_tag_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.1")
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")
    plan_path = project / ".release-flow" / "releases" / "v0.1.1" / "release-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["tag"] = "v9.9.9"
    write_json(plan_path, plan)

    result = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
    )

    assert result.returncode == 1
    assert "release_plan_tag_mismatch" in result.stdout


def test_preflight_writes_report_when_checks_pass(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.1")
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    result = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
    )

    assert result.returncode == 0
    assert "status: preflight_passed" in result.stdout
    report_path = project / ".release-flow" / "releases" / "v0.1.1" / "preflight-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["tag"] == "v0.1.1"
    assert "variables" not in report
    assert report["version"]["expected"] == "0.1.1"


def test_preflight_checks_projection_without_channel_tree(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(
        project,
        marketplace_identity_projection(
            transforms="""  - path: .claude-plugin/marketplace.json
    type: json-env
    set:
      /name: identity.claude.marketplaceName
"""
        ),
    )
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.1")
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    result = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
    )

    assert result.returncode == 1
    assert "missing_file:" in result.stdout
    assert ".claude-plugin" in result.stdout
    assert "marketplace.json" in result.stdout


def test_preflight_rejects_channel_tree_argument(tmp_path: Path) -> None:
    project = tmp_path / "project"
    channel_tree = tmp_path / "channel"
    write_release_flow_files(project)
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.1")
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")
    channel_tree.mkdir()

    result = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--channel-tree",
        str(channel_tree),
    )

    assert result.returncode == 2


def test_publish_refuses_missing_release_plan(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("publish", "--project", str(project), "--tag", "v0.1.1", "--dry-run")

    assert result.returncode == 1
    assert "missing_release_plan: v0.1.1" in result.stdout


def test_publish_dry_run_prints_workflow_dispatch_without_git_writes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    config = project / ".release-flow" / "config.yaml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("sourceRef: main", "sourceRef: release-source"),
        encoding="utf-8",
    )
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    result = run("publish", "--project", str(project), "--tag", "v0.1.1", "--dry-run")

    assert result.returncode == 0
    assert "status: dry_run" in result.stdout
    assert "gh workflow run .github/workflows/release.yml" in result.stdout
    assert "--ref release-source" in result.stdout
    assert "-f version=0.1.1" in result.stdout
    assert "release_tag: v0.1.1" in result.stdout
    assert "local_branch_created: false" in result.stdout
    assert "git_tag_created: false" in result.stdout
    assert "push_run: false" in result.stdout
    assert not any(line.startswith("tag:") for line in result.stdout.splitlines())


def test_publish_requires_authorization_without_dry_run(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    result = run("publish", "--project", str(project), "--tag", "v0.1.1")

    assert result.returncode == 2
    assert "publish_requires_authorize_publish" in result.stdout


def test_summarize_writes_release_summary(tmp_path: Path) -> None:
    project = tmp_path / "project"
    workflow_run_file = tmp_path / "workflow-run-input.json"
    write_release_flow_files(project)
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")
    write_json(
        workflow_run_file,
        {
            "databaseId": 12345,
            "url": "https://github.example/actions/runs/12345",
            "conclusion": "success",
            "releaseUrl": "https://github.example/releases/tag/v0.1.1",
            "marketplaceCommit": "abc1234",
        },
    )

    result = run(
        "summarize",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--workflow-run-file",
        str(workflow_run_file),
    )

    assert result.returncode == 0
    release_dir = project / ".release-flow" / "releases" / "v0.1.1"
    assert json.loads((release_dir / "workflow-run.json").read_text(encoding="utf-8"))[
        "databaseId"
    ] == 12345
    summary = (release_dir / "release-summary.md").read_text(encoding="utf-8")
    assert "v0.1.1" in summary
    assert "https://github.example/releases/tag/v0.1.1" in summary
    assert "abc1234" in summary
    assert "success" in summary


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
        assert "release-init" in workflow
        assert "--version" in workflow
        assert "version:" in workflow
        assert "ci-publish" in workflow
        assert "release-vars.json" not in workflow
        assert "--vars-file" not in workflow
        assert "release-flow-plugin/" not in workflow
        assert "--authorize-ci-publish" in workflow
        assert "GH_TOKEN" in workflow
        assert "github.token" in workflow
        assert "scripts/release-flow" not in workflow


def test_ci_publish_rejects_dry_run_argument(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(
        project,
        marketplace_identity_projection().replace(
            "      - release-flow\n",
            "      - release-flow\n      - cross-agent-review\n      - pr-flow\n",
        ),
    )
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    result = run(
        "ci-publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--release-plan",
        ".release-flow/releases/v0.1.1/release-plan.json",
        "--dry-run",
    )

    assert result.returncode == 2
    assert not (tmp_path / "project-projected").exists()


def test_ci_publish_rejects_untrusted_release_plan_path(tmp_path: Path) -> None:
    project = tmp_path / "project"
    outside_plan = tmp_path / "whatever.json"
    write_release_flow_files(project)
    write_json(outside_plan, {"tag": "v0.1.1", "version": "0.1.1"})
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    result = run(
        "ci-publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--release-plan",
        str(outside_plan),
        "--authorize-ci-publish",
    )

    assert result.returncode == 1
    assert "invalid_release_plan_path:" in result.stdout


def test_ci_publish_rejects_other_project_release_plan_path(tmp_path: Path) -> None:
    project = tmp_path / "project"
    other_plan = project / ".release-flow" / "releases" / "v0.1.1" / "other-plan.json"
    write_release_flow_files(project)
    write_json(other_plan, {"tag": "v0.1.1", "version": "0.1.1"})
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    result = run(
        "ci-publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--release-plan",
        ".release-flow/releases/v0.1.1/other-plan.json",
        "--authorize-ci-publish",
    )

    assert result.returncode == 1
    assert "invalid_release_plan_path:" in result.stdout


def test_ci_publish_authorized_pushes_channel_tag_and_creates_release(tmp_path: Path) -> None:
    project = tmp_path / "project"
    clone = tmp_path / "fresh-clone"
    remote = tmp_path / "remote.git"
    fake_bin = tmp_path / "bin"
    gh_log = tmp_path / "gh.log"
    fake_bin.mkdir()
    fake_gh = f"@echo off\r\necho %*>> \"{gh_log}\"\r\n"
    (fake_bin / "gh.cmd").write_text(fake_gh, encoding="utf-8")
    (fake_bin / "gh.bat").write_text(fake_gh, encoding="utf-8")
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
    (project / ".release-flow" / ".gitignore").write_text("/releases/\n", encoding="utf-8")
    write_json(project / ".agents" / "plugins" / "marketplace.json", {"name": "local-dev"})
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)
    assert git(project, "init").returncode == 0
    assert git(project, "config", "user.email", "test@example.com").returncode == 0
    assert git(project, "config", "user.name", "Test").returncode == 0
    assert git(project, "add", ".").returncode == 0
    assert git(project, "commit", "-m", "baseline").returncode == 0
    assert git(project, "remote", "add", "origin", str(remote)).returncode == 0
    assert git(project, "push", "origin", "HEAD:refs/heads/main").returncode == 0
    clone_result = subprocess.run(
        ["git", "clone", str(remote), str(clone)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert clone_result.returncode == 0, clone_result.stdout + clone_result.stderr
    assert not (clone / ".release-flow" / "releases" / "v0.1.1" / "release-plan.json").exists()
    release_init = run(
        "release-init",
        "--project",
        str(clone),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--replace",
    )
    assert release_init.returncode == 0, release_init.stdout + release_init.stderr

    env = os.environ.copy()
    env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
    env["PATHEXT"] = ".CMD;.BAT;.EXE;.COM"
    result = run(
        "ci-publish",
        "--project",
        str(clone),
        "--tag",
        "v0.1.1",
        "--release-plan",
        ".release-flow/releases/v0.1.1/release-plan.json",
        "--authorize-ci-publish",
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: ci_published" in result.stdout
    assert "channel_branch: marketplace" in result.stdout
    assert "tag: v0.1.1" in result.stdout
    assert "remote_write: completed" in result.stdout
    assert git(remote, "show-ref", "--verify", "refs/heads/marketplace").returncode == 0
    assert git(remote, "show-ref", "--verify", "refs/tags/v0.1.1").returncode == 0
    show = git(remote, "show", "refs/heads/marketplace:.agents/plugins/marketplace.json")
    assert show.returncode == 0
    assert json.loads(show.stdout)["name"] == "my-agent-skills-marketplace"
    assert "release create v0.1.1" in gh_log.read_text(encoding="utf-8")


def test_ci_publish_requires_authorization_without_dry_run(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    result = run(
        "ci-publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--release-plan",
        ".release-flow/releases/v0.1.1/release-plan.json",
    )

    assert result.returncode == 2
    assert "ci_publish_requires_authorize_ci_publish" in result.stdout


def test_release_flow_local_e2e(tmp_path: Path) -> None:
    project = tmp_path / "project"
    workflow_run_file = tmp_path / "workflow-run.json"

    setup = run("setup", "--project", str(project), "--authorize-project-files")
    assert setup.returncode == 0, setup.stdout + setup.stderr
    write_json(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", {"version": "0.1.1"})
    write_json(project / "plugins" / "agent-guard" / ".claude-plugin" / "plugin.json", {"version": "0.1.1"})
    write_json(
        project / ".claude-plugin" / "marketplace.json",
        {"name": "local-dev", "owner": {"name": "Local Dev"}},
    )

    release_init = run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")
    assert release_init.returncode == 0, release_init.stdout + release_init.stderr
    preflight = run(
        "preflight",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
    )
    assert preflight.returncode == 0, preflight.stdout + preflight.stderr
    publish = run("publish", "--project", str(project), "--tag", "v0.1.1", "--dry-run")
    assert publish.returncode == 0, publish.stdout + publish.stderr
    write_json(
        workflow_run_file,
        {
            "conclusion": "success",
            "releaseUrl": "https://example.invalid/releases/v0.1.1",
            "marketplaceCommit": "abc123",
            "url": "https://example.invalid/actions/runs/1",
            "databaseId": 1,
        },
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
    assert summarize.returncode == 0, summarize.stdout + summarize.stderr

    record_dir = project / ".release-flow" / "releases" / "v0.1.1"
    assert (record_dir / "release-plan.json").is_file()
    assert (record_dir / "preflight-report.json").is_file()
    assert (record_dir / "workflow-run.json").is_file()
    assert (record_dir / "release-summary.md").is_file()
