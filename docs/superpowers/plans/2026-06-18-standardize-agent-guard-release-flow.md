---
archived-with: 2026-06-18-standardize-agent-guard-release-flow
status: final
---
# Standardize Agent Guard Release Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a reusable dual-compatible `release-flow` Plugin（发布流程插件） and use it to standardize Agent Guard fixed release（固定版本发布） and latest channel（最新通道） publishing.

**Architecture:** `plugins/release-flow` owns the Skill（技能）, deterministic Python scripts, and reusable templates. Target projects only keep `.release-flow/config.yaml`, `.release-flow/projection.yaml`, `.release-flow/.gitignore`, and a thin GitHub Workflow（工作流） entry; release plans and reports are local audit records under ignored `.release-flow/releases/<tag>/`. Local commands validate and trigger; GitHub Actions performs branch, tag, and GitHub Release writes.

**Tech Stack:** Python stdlib, PyYAML (`yaml.safe_load`), pytest, Git CLI, GitHub CLI (`gh`), GitHub Actions, JSON Pointer（JSON 指针） for JSON mutation.

---

## Scope And Current State

This plan implements one unified design across:

- the new reusable `release-flow` plugin package,
- the current repository's `.release-flow` project configuration,
- Agent Guard's marketplace release projection,
- tests covering Codex and Claude plugin compatibility.

Current branch note from `git diff --name-status origin/main origin/marketplace`:

- The intended marketplace catalog drift is in `.agents/plugins/marketplace.json` and `.claude-plugin/marketplace.json`.
- The current `marketplace` branch also contains non-catalog drift in `.comet/config.yaml`, archived OpenSpec files, one report file, and `tests/test_agent_guard_plugin_package.py`.
- The first preflight must report this non-projection drift as blocking. This plan does not force-push or manually rewrite the remote branch during implementation.

## File Structure

Create:

- `plugins/release-flow/.codex-plugin/plugin.json`: Codex manifest.
- `plugins/release-flow/.claude-plugin/plugin.json`: Claude manifest.
- `plugins/release-flow/skills/release-flow/SKILL.md`: shared skill entrypoint.
- `plugins/release-flow/skills/release-flow/scripts/release_flow.py`: single deterministic CLI for setup, release init, preflight, publish, summarize, and CI publish.
- `plugins/release-flow/skills/release-flow/assets/templates/release-flow/config.yaml`: target `.release-flow/config.yaml` template.
- `plugins/release-flow/skills/release-flow/assets/templates/release-flow/projection.yaml`: target `.release-flow/projection.yaml` template.
- `plugins/release-flow/skills/release-flow/assets/templates/release-flow/gitignore`: target `.release-flow/.gitignore` template.
- `plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml`: thin workflow template.
- `.release-flow/config.yaml`: current repo release-flow configuration, tracked.
- `.release-flow/projection.yaml`: current repo projection registry, tracked.
- `.release-flow/.gitignore`: ignores local release records, tracked.
- `.github/workflows/release.yml`: thin release workflow entry, tracked.
- `tests/test_release_flow_plugin_package.py`: plugin package and marketplace catalog contract tests.
- `tests/test_release_flow_cli.py`: CLI tests for setup, release-init, preflight, publish, summarize, and projection transforms.

Modify:

- `.agents/plugins/marketplace.json`: add local dev entry for `release-flow`.
- `.claude-plugin/marketplace.json`: add local dev entry for `release-flow`.
- `openspec/changes/standardize-agent-guard-release-flow/tasks.md`: check off implemented items at the end.
- `openspec/changes/standardize-agent-guard-release-flow/.comet.yaml`: point to this plan when plan is accepted.

Do not create:

- `scripts/release-flow/*` in the target repo.
- `.release-flow/releases/<tag>/release-plan.json` during project setup.
- a local `marketplace` branch during implementation.

## CLI Contract

All commands run from the plugin script:

```powershell
python plugins/release-flow/skills/release-flow/scripts/release_flow.py <command> [options]
```

Commands:

- `setup`: project enablement. Generates tracked config/projection/gitignore/workflow only when `--authorize-project-files` is present.
- `github-plan`: prints expected Actions permissions, Rulesets, and Actions Variables.
- `configure-github`: writes GitHub settings only when `--authorize-github` is present, then reads back and verifies.
- `release-init`: creates `.release-flow/releases/<tag>/release-plan.json` before a release.
- `preflight`: validates config, projection, variables, version/tag, GitHub settings, and marketplace drift.
- `publish`: reads an existing release-plan and triggers workflow_dispatch; local git writes are forbidden.
- `summarize`: writes `workflow-run.json` and `release-summary.md`.
- `ci-publish`: GitHub Actions entrypoint; applies projection and performs remote branch/tag/release writes inside CI.

Every command must print machine-readable status lines such as `status: verified`, `status: issues`, or `status: dry_run`.

## Task 1: Add Release Flow Package Contract Tests

**Files:**

- Create: `tests/test_release_flow_plugin_package.py`
- Modify: none

- [x] **Step 1: Write failing package tests**

Create `tests/test_release_flow_plugin_package.py`:

```python
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "release-flow"
CODEX_REPO_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_release_flow_manifests_are_valid_json() -> None:
    codex_manifest = read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    claude_manifest = read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")

    assert codex_manifest["name"] == "release-flow"
    assert claude_manifest["name"] == "release-flow"
    assert codex_manifest["version"] == claude_manifest["version"]
    assert codex_manifest["skills"] == "./skills"
    assert claude_manifest["skills"] == "./skills"
    assert codex_manifest["description"]
    assert claude_manifest["description"]


def test_release_flow_package_contains_skill_scripts_and_templates() -> None:
    skill_root = PLUGIN_ROOT / "skills" / "release-flow"

    required = [
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        "skills/release-flow/SKILL.md",
        "skills/release-flow/scripts/release_flow.py",
        "skills/release-flow/assets/templates/release-flow/config.yaml",
        "skills/release-flow/assets/templates/release-flow/projection.yaml",
        "skills/release-flow/assets/templates/release-flow/gitignore",
        "skills/release-flow/assets/templates/github/workflows/release.yml",
    ]
    for item in required:
        assert (PLUGIN_ROOT / item).exists(), item

    text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    assert "release-flow" in text
    assert "Lorem ipsum" not in text
    assert "sample text only" not in text
    assert "not yet written" not in text


def test_repo_marketplace_catalogs_include_release_flow_local_entry() -> None:
    codex_catalog = read_json(CODEX_REPO_MARKETPLACE)
    claude_catalog = read_json(CLAUDE_REPO_MARKETPLACE)

    codex_entries = [
        plugin for plugin in codex_catalog["plugins"] if plugin.get("name") == "release-flow"
    ]
    claude_entries = [
        plugin for plugin in claude_catalog["plugins"] if plugin.get("name") == "release-flow"
    ]

    assert codex_entries == [
        {
            "name": "release-flow",
            "source": {"source": "local", "path": "./plugins/release-flow"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        }
    ]
    assert claude_entries == [
        {
            "name": "release-flow",
            "source": "./plugins/release-flow",
            "description": "Release flow plugin for Codex and Claude agents",
        }
    ]
```

- [x] **Step 2: Run package tests to verify failure**

Run:

```powershell
python -m pytest tests/test_release_flow_plugin_package.py -q
```

Expected:

```text
FAILED tests/test_release_flow_plugin_package.py::test_release_flow_manifests_are_valid_json
```

The failure reason should include a missing `plugins/release-flow` manifest path.

- [x] **Step 3: Commit checkpoint after test red state**

Do not commit unless the user has explicitly authorized commits in the execution session.

Authorized command:

```powershell
git add tests/test_release_flow_plugin_package.py
git commit -m "test: 添加 release-flow 插件包契约"
```

## Task 2: Create Release Flow Plugin Skeleton

**Files:**

- Create: `plugins/release-flow/.codex-plugin/plugin.json`
- Create: `plugins/release-flow/.claude-plugin/plugin.json`
- Create: `plugins/release-flow/skills/release-flow/SKILL.md`
- Create: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- Create: `plugins/release-flow/skills/release-flow/assets/templates/release-flow/config.yaml`
- Create: `plugins/release-flow/skills/release-flow/assets/templates/release-flow/projection.yaml`
- Create: `plugins/release-flow/skills/release-flow/assets/templates/release-flow/gitignore`
- Create: `plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml`
- Modify: `.agents/plugins/marketplace.json`
- Modify: `.claude-plugin/marketplace.json`

- [x] **Step 1: Create Codex manifest**

Create `plugins/release-flow/.codex-plugin/plugin.json`:

```json
{
  "name": "release-flow",
  "version": "0.1.0",
  "description": "Release Flow Plugin（发布流程插件）",
  "skills": "./skills",
  "assets": "skills/release-flow/assets"
}
```

- [x] **Step 2: Create Claude manifest**

Create `plugins/release-flow/.claude-plugin/plugin.json`:

```json
{
  "name": "release-flow",
  "version": "0.1.0",
  "description": "Release Flow Plugin（发布流程插件）",
  "skills": "./skills",
  "assets": "skills/release-flow/assets"
}
```

- [x] **Step 3: Create skill entrypoint**

Create `plugins/release-flow/skills/release-flow/SKILL.md`:

```markdown
---
name: release-flow
description: Use when a project needs a reusable GitHub-based release flow with setup, release-init, preflight, publish, and summarize phases.
---

# Release Flow

Release Flow（发布流程）标准化一个项目的 fixed release（固定版本发布）和 latest channel（最新通道）发布。

Use this skill when the user wants to:

- enable release-flow in a project,
- create a release plan for a tag,
- run release preflight checks,
- trigger a GitHub workflow release,
- summarize release results.

## Boundaries

- Project setup writes only `.release-flow/config.yaml`, `.release-flow/projection.yaml`, `.release-flow/.gitignore`, and a thin GitHub Workflow entry after explicit authorization.
- Project setup does not create `.release-flow/releases/<tag>/release-plan.json`.
- Plugin scripts and templates stay inside this plugin package.
- Local publish commands do not create branches, create tags, or push commits.
- GitHub repository settings are modified only after explicit user authorization.

## Commands

Run commands from the target repository root:

```powershell
python <plugin-root>/skills/release-flow/scripts/release_flow.py setup --project .
python <plugin-root>/skills/release-flow/scripts/release_flow.py release-init --project . --tag v0.1.0 --version 0.1.0
python <plugin-root>/skills/release-flow/scripts/release_flow.py preflight --project . --tag v0.1.0
python <plugin-root>/skills/release-flow/scripts/release_flow.py publish --project . --tag v0.1.0
python <plugin-root>/skills/release-flow/scripts/release_flow.py summarize --project . --tag v0.1.0
```

Read `.release-flow/config.yaml` and `.release-flow/projection.yaml` before running release commands.
```

- [x] **Step 4: Create executable CLI skeleton**

Create `plugins/release-flow/skills/release-flow/scripts/release_flow.py`:

```python
"""Release Flow Plugin（发布流程插件）命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable


def run_setup(args: argparse.Namespace) -> int:
    print("status: dry_run")
    print(f"project: {args.project}")
    print("action: setup_entrypoint_loaded")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Release Flow Plugin（发布流程插件）。")
    subparsers = parser.add_subparsers(dest="command", required=True)
    setup = subparsers.add_parser("setup", help="启用 release-flow 项目配置。")
    setup.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    setup.add_argument("--authorize-project-files", action="store_true", help="授权写入项目配置文件。")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "setup":
        return run_setup(args)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 5: Create initial templates**

Create `plugins/release-flow/skills/release-flow/assets/templates/release-flow/config.yaml`:

```yaml
version: 1

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
    main:
      requirePullRequest: true
    channel:
      branch: marketplace
      writers:
        - github-actions
    tags:
      immutable: true

manifests:
  versionFiles:
    - plugins/agent-guard/.codex-plugin/plugin.json
    - plugins/agent-guard/.claude-plugin/plugin.json
```

Create `plugins/release-flow/skills/release-flow/assets/templates/release-flow/projection.yaml`:

```yaml
version: 1

variables:
  CODEX_MARKETPLACE_CATALOG_NAME:
    source: github-actions-variable
    required: true
    sensitive: false
    description: Codex marketplace catalog name for the latest channel
    example: agent-guard-marketplace
  CODEX_MARKETPLACE_DISPLAY_NAME:
    source: github-actions-variable
    required: true
    sensitive: false
    description: Codex marketplace display name for the latest channel
    example: Agent Guard
  CLAUDE_MARKETPLACE_CATALOG_NAME:
    source: github-actions-variable
    required: true
    sensitive: false
    description: Claude marketplace catalog name for the latest channel
    example: agent-guard-marketplace
  CLAUDE_MARKETPLACE_OWNER_NAME:
    source: github-actions-variable
    required: true
    sensitive: false
    description: Claude marketplace owner name for the latest channel
    example: Agent Guard

transforms:
  - path: .agents/plugins/marketplace.json
    type: json-env
    set:
      /name: CODEX_MARKETPLACE_CATALOG_NAME
      /interface/displayName: CODEX_MARKETPLACE_DISPLAY_NAME
  - path: .claude-plugin/marketplace.json
    type: json-env
    set:
      /name: CLAUDE_MARKETPLACE_CATALOG_NAME
      /owner/name: CLAUDE_MARKETPLACE_OWNER_NAME
```

Create `plugins/release-flow/skills/release-flow/assets/templates/release-flow/gitignore`:

```gitignore
/releases/
```

Create `plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml`:

```yaml
name: Release

on:
  workflow_dispatch:
    inputs:
      tag:
        description: Release tag
        required: true
        type: string
      releasePlan:
        description: Release plan path
        required: true
        type: string

permissions:
  contents: write
  actions: read

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout source
        uses: actions/checkout@v4
        with:
          ref: ${{ vars.RELEASE_FLOW_SOURCE_REF || 'main' }}
          path: source

      - name: Checkout release-flow plugin
        uses: actions/checkout@v4
        with:
          repository: ${{ vars.RELEASE_FLOW_PLUGIN_REPOSITORY }}
          ref: ${{ vars.RELEASE_FLOW_PLUGIN_REF }}
          path: release-flow-plugin

      - name: Publish release channel
        run: >
          python release-flow-plugin/plugins/release-flow/skills/release-flow/scripts/release_flow.py
          ci-publish
          --project source
          --tag "${{ inputs.tag }}"
          --release-plan "${{ inputs.releasePlan }}"
```

- [x] **Step 6: Add release-flow to repo marketplaces**

Modify `.agents/plugins/marketplace.json` so `plugins` contains the existing `agent-guard` entry and this second entry:

```json
{
  "name": "release-flow",
  "source": {
    "source": "local",
    "path": "./plugins/release-flow"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Developer Tools"
}
```

Modify `.claude-plugin/marketplace.json` so `plugins` contains the existing `agent-guard` entry and this second entry:

```json
{
  "name": "release-flow",
  "source": "./plugins/release-flow",
  "description": "Release flow plugin for Codex and Claude agents"
}
```

- [x] **Step 7: Run package tests**

Run:

```powershell
python -m pytest tests/test_release_flow_plugin_package.py -q
```

Expected:

```text
3 passed
```

- [x] **Step 8: Commit checkpoint**

Do not commit unless the user has explicitly authorized commits in the execution session.

Authorized command:

```powershell
git add plugins/release-flow .agents/plugins/marketplace.json .claude-plugin/marketplace.json tests/test_release_flow_plugin_package.py
git commit -m "feat: 新增 release-flow 插件骨架"
```

## Task 3: Add Config, Projection, And Transform Tests

**Files:**

- Create: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`

- [x] **Step 1: Write failing parser and transform tests**

Create `tests/test_release_flow_cli.py` with these base helpers and tests:

```python
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "plugins" / "release-flow" / "skills" / "release-flow" / "scripts" / "release_flow.py"


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd or REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_release_flow_files(project: Path) -> None:
    release_flow = project / ".release-flow"
    release_flow.mkdir(parents=True)
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
    - plugins/agent-guard/.claude-plugin/plugin.json
""",
        encoding="utf-8",
    )
    (release_flow / "projection.yaml").write_text(
        """version: 1
variables:
  CODEX_MARKETPLACE_CATALOG_NAME:
    source: github-actions-variable
    required: true
    sensitive: false
    description: Codex marketplace catalog name
    example: agent-guard-marketplace
transforms:
  - path: .agents/plugins/marketplace.json
    type: json-env
    set:
      /name: CODEX_MARKETPLACE_CATALOG_NAME
""",
        encoding="utf-8",
    )


def test_validate_rejects_projection_variable_values(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    projection = project / ".release-flow" / "projection.yaml"
    projection.write_text(
        """version: 1
variables:
  CODEX_MARKETPLACE_CATALOG_NAME:
    source: github-actions-variable
    required: true
    sensitive: false
    description: Codex marketplace catalog name
    value: agent-guard-marketplace
transforms: []
""",
        encoding="utf-8",
    )

    result = run(["validate", "--project", str(project)])

    assert result.returncode == 1
    assert "projection_variable_value_forbidden: CODEX_MARKETPLACE_CATALOG_NAME" in result.stdout


def test_project_applies_json_env_transform(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    write_json(project / ".agents" / "plugins" / "marketplace.json", {"name": "agent-guard-local-dev", "plugins": []})
    vars_file = tmp_path / "vars.json"
    write_json(vars_file, {"CODEX_MARKETPLACE_CATALOG_NAME": "agent-guard-marketplace"})

    result = run(["project", "--project", str(project), "--vars-file", str(vars_file)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: projected" in result.stdout
    data = json.loads((project / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    assert data["name"] == "agent-guard-marketplace"
```

- [x] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_validate_rejects_projection_variable_values tests/test_release_flow_cli.py::test_project_applies_json_env_transform -q
```

Expected:

```text
FAILED tests/test_release_flow_cli.py::test_validate_rejects_projection_variable_values
FAILED tests/test_release_flow_cli.py::test_project_applies_json_env_transform
```

The failure reason should show `invalid choice: 'validate'` or `invalid choice: 'project'`.

## Task 4: Implement Config, Projection, And JSON Pointer Core

**Files:**

- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`

- [x] **Step 1: Replace CLI skeleton with core implementation**

Modify `plugins/release-flow/skills/release-flow/scripts/release_flow.py` to include these functions and dataclasses:

```python
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


FORBIDDEN_VARIABLE_KEYS = {"value", "secret", "defaultValue", "default_value"}


@dataclass(frozen=True)
class FlowConfig:
    source_ref: str
    channel_branch: str
    branch_mode: str
    workflow_file: str
    workflow_trigger: str
    records_directory: str
    manifest_files: list[str]


@dataclass(frozen=True)
class ProjectionVariable:
    name: str
    source: str
    required: bool
    sensitive: bool
    description: str


@dataclass(frozen=True)
class ProjectionTransform:
    path: str
    type: str
    set_values: dict[str, str]


@dataclass(frozen=True)
class Projection:
    variables: dict[str, ProjectionVariable]
    transforms: list[ProjectionTransform]
```

Implement these helpers in the same file:

```python
def normalize(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    return Path(os.path.abspath(expanded))


def load_yaml_mapping(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"missing_yaml: {path}"]
    except yaml.YAMLError as exc:
        return None, [f"invalid_yaml: {path}: {exc}"]
    if not isinstance(data, dict):
        return None, [f"invalid_yaml_mapping: {path}"]
    return data, []


def read_config(project: Path) -> tuple[FlowConfig | None, list[str]]:
    path = project / ".release-flow" / "config.yaml"
    data, errors = load_yaml_mapping(path)
    if errors:
        return None, errors

    release = data.get("release")
    workflow = data.get("workflow")
    records = data.get("records")
    manifests = data.get("manifests", {})
    if not isinstance(release, dict):
        return None, ["invalid_config: release must be mapping"]
    if not isinstance(workflow, dict):
        return None, ["invalid_config: workflow must be mapping"]
    if not isinstance(records, dict):
        return None, ["invalid_config: records must be mapping"]
    version_files = manifests.get("versionFiles", [])
    if not isinstance(version_files, list) or not all(isinstance(item, str) for item in version_files):
        return None, ["invalid_config: manifests.versionFiles must be string list"]

    config = FlowConfig(
        source_ref=str(release.get("sourceRef", "")),
        channel_branch=str(release.get("channelBranch", "")),
        branch_mode=str(release.get("branchMode", "")),
        workflow_file=str(workflow.get("file", "")),
        workflow_trigger=str(workflow.get("trigger", "")),
        records_directory=str(records.get("directory", "")),
        manifest_files=version_files,
    )
    errors = []
    if config.branch_mode != "remote-only":
        errors.append("invalid_config: release.branchMode must be remote-only")
    if config.workflow_trigger != "workflow_dispatch":
        errors.append("invalid_config: workflow.trigger must be workflow_dispatch")
    if config.records_directory != ".release-flow/releases":
        errors.append("invalid_config: records.directory must be .release-flow/releases")
    return (None, errors) if errors else (config, [])
```

Implement projection parsing and forbidden value checks:

```python
def read_projection(project: Path) -> tuple[Projection | None, list[str]]:
    path = project / ".release-flow" / "projection.yaml"
    data, errors = load_yaml_mapping(path)
    if errors:
        return None, errors

    variables_data = data.get("variables", {})
    transforms_data = data.get("transforms", [])
    if not isinstance(variables_data, dict):
        return None, ["invalid_projection: variables must be mapping"]
    if not isinstance(transforms_data, list):
        return None, ["invalid_projection: transforms must be list"]

    variables: dict[str, ProjectionVariable] = {}
    errors = []
    for name, spec in variables_data.items():
        if not isinstance(name, str) or not isinstance(spec, dict):
            errors.append("invalid_projection: variable entries must be mappings")
            continue
        forbidden = sorted(FORBIDDEN_VARIABLE_KEYS.intersection(spec))
        if forbidden:
            errors.append(f"projection_variable_value_forbidden: {name}")
        variable = ProjectionVariable(
            name=name,
            source=str(spec.get("source", "")),
            required=bool(spec.get("required", False)),
            sensitive=bool(spec.get("sensitive", False)),
            description=str(spec.get("description", "")),
        )
        if variable.source != "github-actions-variable":
            errors.append(f"invalid_projection_variable_source: {name}")
        variables[name] = variable

    transforms: list[ProjectionTransform] = []
    for transform in transforms_data:
        if not isinstance(transform, dict):
            errors.append("invalid_projection_transform: transform must be mapping")
            continue
        set_values = transform.get("set", {})
        if not isinstance(set_values, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in set_values.items()):
            errors.append("invalid_projection_transform: set must map JSON Pointer paths to variable names")
            continue
        transforms.append(
            ProjectionTransform(
                path=str(transform.get("path", "")),
                type=str(transform.get("type", "")),
                set_values=set_values,
            )
        )
    for transform in transforms:
        if transform.type != "json-env":
            errors.append(f"invalid_projection_transform_type: {transform.path}")
        for variable_name in transform.set_values.values():
            if variable_name not in variables:
                errors.append(f"unknown_projection_variable: {variable_name}")

    return (None, errors) if errors else (Projection(variables=variables, transforms=transforms), [])
```

Implement JSON Pointer mutation:

```python
def decode_pointer_part(value: str) -> str:
    return value.replace("~1", "/").replace("~0", "~")


def set_json_pointer(document: Any, pointer: str, value: Any) -> None:
    if not pointer.startswith("/"):
        raise ValueError(f"invalid_json_pointer: {pointer}")
    parts = [decode_pointer_part(part) for part in pointer.split("/")[1:]]
    current = document
    for part in parts[:-1]:
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise ValueError(f"invalid_json_pointer_parent: {pointer}")
    final = parts[-1]
    if isinstance(current, dict):
        current[final] = value
        return
    if isinstance(current, list):
        current[int(final)] = value
        return
    raise ValueError(f"invalid_json_pointer_parent: {pointer}")


def read_vars_file(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in data.items()):
        raise ValueError(f"invalid_vars_file: {path}")
    return data
```

Implement commands:

```python
def print_errors(errors: list[str]) -> None:
    print("status: issues")
    print("errors:")
    for error in errors:
        print(f"  - {error}")


def run_validate(args: argparse.Namespace) -> int:
    project = normalize(args.project)
    config, config_errors = read_config(project)
    projection, projection_errors = read_projection(project)
    errors = [*config_errors, *projection_errors]
    if errors:
        print_errors(errors)
        return 1
    print("status: verified")
    print(f"source_ref: {config.source_ref}")
    print(f"channel_branch: {config.channel_branch}")
    print(f"projection_variables: {len(projection.variables)}")
    return 0


def apply_projection(project: Path, projection: Projection, variables: dict[str, str]) -> list[str]:
    errors = []
    for variable in projection.variables.values():
        if variable.required and variable.name not in variables:
            errors.append(f"missing_required_variable: {variable.name}")
    if errors:
        return errors
    for transform in projection.transforms:
        target = project / transform.path
        document = json.loads(target.read_text(encoding="utf-8"))
        for pointer, variable_name in transform.set_values.items():
            set_json_pointer(document, pointer, variables[variable_name])
        target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return []


def run_project(args: argparse.Namespace) -> int:
    project = normalize(args.project)
    projection, errors = read_projection(project)
    if errors:
        print_errors(errors)
        return 1
    try:
        variables = read_vars_file(args.vars_file)
        errors = apply_projection(project, projection, variables)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
    if errors:
        print_errors(errors)
        return 1
    print("status: projected")
    return 0
```

Extend parser:

```python
validate = subparsers.add_parser("validate", help="验证 release-flow 配置。")
validate.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")

project_cmd = subparsers.add_parser("project", help="应用 projection 到项目文件。")
project_cmd.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
project_cmd.add_argument("--vars-file", type=Path, required=True, help="测试或 CI 提供的变量 JSON 文件。")
```

Route commands:

```python
if args.command == "validate":
    return run_validate(args)
if args.command == "project":
    return run_project(args)
```

- [x] **Step 2: Run parser and transform tests**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_validate_rejects_projection_variable_values tests/test_release_flow_cli.py::test_project_applies_json_env_transform -q
```

Expected:

```text
2 passed
```

## Task 5: Implement Project Setup And GitHub Plan

**Files:**

- Modify: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`

- [x] **Step 1: Add setup tests**

Append to `tests/test_release_flow_cli.py`:

```python
def test_setup_dry_run_does_not_write_project_files(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run(["setup", "--project", str(project)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "would_write: .release-flow/config.yaml" in result.stdout
    assert "would_write: .release-flow/projection.yaml" in result.stdout
    assert "would_write: .release-flow/.gitignore" in result.stdout
    assert "would_write: .github/workflows/release.yml" in result.stdout
    assert not (project / ".release-flow").exists()
    assert not (project / ".github").exists()


def test_setup_authorized_writes_only_config_projection_gitignore_and_workflow(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run(["setup", "--project", str(project), "--authorize-project-files"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: setup_complete" in result.stdout
    assert (project / ".release-flow" / "config.yaml").exists()
    assert (project / ".release-flow" / "projection.yaml").exists()
    assert (project / ".release-flow" / ".gitignore").read_text(encoding="utf-8") == "/releases/\n"
    assert (project / ".github" / "workflows" / "release.yml").exists()
    assert not (project / ".release-flow" / "releases").exists()
    assert not (project / "scripts" / "release-flow").exists()


def test_github_plan_outputs_expected_settings(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)

    result = run(["github-plan", "--project", str(project)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: github_plan" in result.stdout
    assert "actions_workflow_permissions: read-and-write" in result.stdout
    assert "rulesets: required" in result.stdout
    assert "branch_protection_fallback: false" in result.stdout
    assert "actions_variables:" in result.stdout
    assert "CODEX_MARKETPLACE_CATALOG_NAME" in result.stdout
```

- [x] **Step 2: Run setup tests to verify failure**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_setup_dry_run_does_not_write_project_files tests/test_release_flow_cli.py::test_setup_authorized_writes_only_config_projection_gitignore_and_workflow tests/test_release_flow_cli.py::test_github_plan_outputs_expected_settings -q
```

Expected:

```text
FAILED tests/test_release_flow_cli.py::test_setup_authorized_writes_only_config_projection_gitignore_and_workflow
FAILED tests/test_release_flow_cli.py::test_github_plan_outputs_expected_settings
```

- [x] **Step 3: Implement setup template copy and GitHub plan**

Add constants:

```python
SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"
```

Add helper:

```python
def copy_template(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
```

Replace `run_setup`:

```python
def setup_targets(project: Path) -> list[tuple[Path, Path, str]]:
    return [
        (TEMPLATE_ROOT / "release-flow" / "config.yaml", project / ".release-flow" / "config.yaml", ".release-flow/config.yaml"),
        (TEMPLATE_ROOT / "release-flow" / "projection.yaml", project / ".release-flow" / "projection.yaml", ".release-flow/projection.yaml"),
        (TEMPLATE_ROOT / "release-flow" / "gitignore", project / ".release-flow" / ".gitignore", ".release-flow/.gitignore"),
        (TEMPLATE_ROOT / "github" / "workflows" / "release.yml", project / ".github" / "workflows" / "release.yml", ".github/workflows/release.yml"),
    ]


def run_setup(args: argparse.Namespace) -> int:
    project = normalize(args.project)
    targets = setup_targets(project)
    if not args.authorize_project_files:
        print("status: dry_run")
        for _, _, label in targets:
            print(f"would_write: {label}")
        print("release_plan: not_created")
        print("scripts: not_copied")
        return 0
    for source, target, _ in targets:
        copy_template(source, target)
    print("status: setup_complete")
    for _, _, label in targets:
        print(f"wrote: {label}")
    print("release_plan: not_created")
    print("scripts: not_copied")
    return 0
```

Add GitHub plan command:

```python
def run_github_plan(args: argparse.Namespace) -> int:
    project = normalize(args.project)
    config, config_errors = read_config(project)
    projection, projection_errors = read_projection(project)
    errors = [*config_errors, *projection_errors]
    if errors:
        print_errors(errors)
        return 1
    print("status: github_plan")
    print("actions_workflow_permissions: read-and-write")
    print("rulesets: required")
    print("branch_protection_fallback: false")
    print(f"channel_branch: {config.channel_branch}")
    print("actions_variables:")
    for variable in projection.variables.values():
        required = "required" if variable.required else "optional"
        sensitive = "sensitive" if variable.sensitive else "plain"
        print(f"  - {variable.name}: {required}, {sensitive}")
    return 0
```

Extend parser and router:

```python
github_plan = subparsers.add_parser("github-plan", help="输出 GitHub 仓库期望设置。")
github_plan.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
```

```python
if args.command == "github-plan":
    return run_github_plan(args)
```

- [x] **Step 4: Run setup tests**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_setup_dry_run_does_not_write_project_files tests/test_release_flow_cli.py::test_setup_authorized_writes_only_config_projection_gitignore_and_workflow tests/test_release_flow_cli.py::test_github_plan_outputs_expected_settings -q
```

Expected:

```text
3 passed
```

## Task 6: Implement Release Init

**Files:**

- Modify: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`

- [x] **Step 1: Add release-init tests**

Append to `tests/test_release_flow_cli.py`:

```python
def test_release_init_creates_release_plan_only_for_tag(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)

    result = run(["release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: release_plan_created" in result.stdout
    plan_path = project / ".release-flow" / "releases" / "v0.1.1" / "release-plan.json"
    assert plan_path.exists()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["version"] == "0.1.1"
    assert plan["tag"] == "v0.1.1"
    assert plan["sourceRef"] == "main"
    assert plan["channelBranch"] == "marketplace"
    assert plan["workflowFile"] == ".github/workflows/release.yml"
    assert plan["projectionRegistry"] == ".release-flow/projection.yaml"
    assert plan["dryRun"] is False
    assert not (project / "marketplace").exists()


def test_release_init_refuses_existing_plan_without_replace(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)
    first = run(["release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1"])
    second = run(["release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1"])

    assert first.returncode == 0
    assert second.returncode == 1
    assert "release_plan_exists: v0.1.1" in second.stdout
```

- [x] **Step 2: Run release-init tests to verify failure**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_release_init_creates_release_plan_only_for_tag tests/test_release_flow_cli.py::test_release_init_refuses_existing_plan_without_replace -q
```

Expected:

```text
FAILED tests/test_release_flow_cli.py::test_release_init_creates_release_plan_only_for_tag
FAILED tests/test_release_flow_cli.py::test_release_init_refuses_existing_plan_without_replace
```

- [x] **Step 3: Implement release-init**

Add helpers:

```python
def release_dir(project: Path, tag: str) -> Path:
    return project / ".release-flow" / "releases" / tag


def release_plan_path(project: Path, tag: str) -> Path:
    return release_dir(project, tag) / "release-plan.json"
```

Add command:

```python
def run_release_init(args: argparse.Namespace) -> int:
    project = normalize(args.project)
    config, config_errors = read_config(project)
    projection, projection_errors = read_projection(project)
    errors = [*config_errors, *projection_errors]
    if errors:
        print_errors(errors)
        return 1
    plan_path = release_plan_path(project, args.tag)
    if plan_path.exists() and not args.replace:
        print_errors([f"release_plan_exists: {args.tag}"])
        return 1
    plan = {
        "version": args.version,
        "tag": args.tag,
        "sourceRef": config.source_ref,
        "channelBranch": config.channel_branch,
        "workflowFile": config.workflow_file,
        "projectionRegistry": ".release-flow/projection.yaml",
        "projectionVariables": sorted(projection.variables),
        "dryRun": bool(args.dry_run),
    }
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("status: release_plan_created")
    print(f"release_plan: {plan_path}")
    print("local_branch: not_created")
    print("tag: not_created")
    print("push: not_run")
    return 0
```

Extend parser and router:

```python
release_init = subparsers.add_parser("release-init", help="创建单次发布计划。")
release_init.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
release_init.add_argument("--tag", required=True, help="发布 tag。")
release_init.add_argument("--version", required=True, help="发布版本。")
release_init.add_argument("--dry-run", action="store_true", help="记录 dryRun 标记。")
release_init.add_argument("--replace", action="store_true", help="覆盖同 tag 的本地 release-plan。")
```

```python
if args.command == "release-init":
    return run_release_init(args)
```

- [x] **Step 4: Run release-init tests**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_release_init_creates_release_plan_only_for_tag tests/test_release_flow_cli.py::test_release_init_refuses_existing_plan_without_replace -q
```

Expected:

```text
2 passed
```

## Task 7: Implement Preflight

**Files:**

- Modify: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`

- [x] **Step 1: Add preflight tests**

Append to `tests/test_release_flow_cli.py`:

```python
def write_manifest(path: Path, version: str) -> None:
    write_json(path, {"name": "agent-guard", "version": version, "description": "Agent Guard"})


def test_preflight_rejects_missing_release_plan(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)

    result = run(["preflight", "--project", str(project), "--tag", "v0.1.1"])

    assert result.returncode == 1
    assert "missing_release_plan: v0.1.1" in result.stdout


def test_preflight_rejects_missing_required_github_variable(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)
    run(["release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1"])
    vars_file = tmp_path / "vars.json"
    write_json(vars_file, {})

    result = run(["preflight", "--project", str(project), "--tag", "v0.1.1", "--github-vars-file", str(vars_file)])

    assert result.returncode == 1
    assert "missing_required_variable: CODEX_MARKETPLACE_CATALOG_NAME" in result.stdout


def test_preflight_rejects_tag_manifest_version_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.2")
    write_manifest(project / "plugins" / "agent-guard" / ".claude-plugin" / "plugin.json", "0.1.2")
    run(["release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1"])
    vars_file = tmp_path / "vars.json"
    write_json(vars_file, {"CODEX_MARKETPLACE_CATALOG_NAME": "agent-guard-marketplace"})

    result = run(["preflight", "--project", str(project), "--tag", "v0.1.1", "--github-vars-file", str(vars_file)])

    assert result.returncode == 1
    assert "manifest_version_mismatch: plugins/agent-guard/.codex-plugin/plugin.json" in result.stdout


def test_preflight_writes_report_when_checks_pass(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.1")
    write_manifest(project / "plugins" / "agent-guard" / ".claude-plugin" / "plugin.json", "0.1.1")
    run(["release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1"])
    vars_file = tmp_path / "vars.json"
    write_json(vars_file, {"CODEX_MARKETPLACE_CATALOG_NAME": "agent-guard-marketplace"})

    result = run(["preflight", "--project", str(project), "--tag", "v0.1.1", "--github-vars-file", str(vars_file)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: preflight_passed" in result.stdout
    report_path = project / ".release-flow" / "releases" / "v0.1.1" / "preflight-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["tag"] == "v0.1.1"
    assert report["variables"]["missing"] == []
    assert report["version"]["expected"] == "0.1.1"
```

- [x] **Step 2: Run preflight tests to verify failure**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_preflight_rejects_missing_release_plan tests/test_release_flow_cli.py::test_preflight_rejects_missing_required_github_variable tests/test_release_flow_cli.py::test_preflight_rejects_tag_manifest_version_mismatch tests/test_release_flow_cli.py::test_preflight_writes_report_when_checks_pass -q
```

Expected:

```text
FAILED tests/test_release_flow_cli.py::test_preflight_rejects_missing_release_plan
FAILED tests/test_release_flow_cli.py::test_preflight_rejects_missing_required_github_variable
FAILED tests/test_release_flow_cli.py::test_preflight_rejects_tag_manifest_version_mismatch
FAILED tests/test_release_flow_cli.py::test_preflight_writes_report_when_checks_pass
```

- [x] **Step 3: Implement preflight**

Add helpers:

```python
def read_release_plan(project: Path, tag: str) -> tuple[dict[str, Any] | None, list[str]]:
    path = release_plan_path(project, tag)
    if not path.exists():
        return None, [f"missing_release_plan: {tag}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"invalid_release_plan: {path}: {exc}"]
    if not isinstance(data, dict):
        return None, [f"invalid_release_plan: {path}"]
    return data, []


def tag_version(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


def manifest_versions(project: Path, files: list[str]) -> tuple[dict[str, str], list[str]]:
    versions = {}
    errors = []
    for item in files:
        path = project / item
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            errors.append(f"missing_manifest: {item}")
            continue
        except json.JSONDecodeError as exc:
            errors.append(f"invalid_manifest_json: {item}: {exc}")
            continue
        version = data.get("version")
        if not isinstance(version, str):
            errors.append(f"missing_manifest_version: {item}")
            continue
        versions[item] = version
    return versions, errors
```

Add preflight command:

```python
def run_preflight(args: argparse.Namespace) -> int:
    project = normalize(args.project)
    config, config_errors = read_config(project)
    projection, projection_errors = read_projection(project)
    plan, plan_errors = read_release_plan(project, args.tag)
    errors = [*config_errors, *projection_errors, *plan_errors]
    if errors:
        print_errors(errors)
        return 1

    variables = read_vars_file(args.github_vars_file)
    missing = [
        variable.name
        for variable in projection.variables.values()
        if variable.required and variable.name not in variables
    ]
    if missing:
        print_errors([f"missing_required_variable: {name}" for name in missing])
        return 1

    versions, version_errors = manifest_versions(project, config.manifest_files)
    expected_version = tag_version(args.tag)
    for path, version in versions.items():
        if version != expected_version:
            version_errors.append(f"manifest_version_mismatch: {path}")
    if plan.get("version") != expected_version:
        version_errors.append("release_plan_version_mismatch")
    if version_errors:
        print_errors(version_errors)
        return 1

    report = {
        "tag": args.tag,
        "variables": {"required": sorted(projection.variables), "missing": []},
        "version": {"expected": expected_version, "manifests": versions},
        "github": {"rulesets": "not_checked_in_offline_mode"},
        "projection": {"status": "validated"},
    }
    report_path = release_dir(project, args.tag) / "preflight-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("status: preflight_passed")
    print(f"preflight_report: {report_path}")
    return 0
```

Extend parser and router:

```python
preflight = subparsers.add_parser("preflight", help="执行发布前检查。")
preflight.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
preflight.add_argument("--tag", required=True, help="发布 tag。")
preflight.add_argument("--github-vars-file", type=Path, help="离线测试变量文件；生产环境为空时使用 gh。")
```

```python
if args.command == "preflight":
    return run_preflight(args)
```

- [x] **Step 4: Run preflight tests**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_preflight_rejects_missing_release_plan tests/test_release_flow_cli.py::test_preflight_rejects_missing_required_github_variable tests/test_release_flow_cli.py::test_preflight_rejects_tag_manifest_version_mismatch tests/test_release_flow_cli.py::test_preflight_writes_report_when_checks_pass -q
```

Expected:

```text
4 passed
```

## Task 8: Add Drift Detection For Marketplace Channel

**Files:**

- Modify: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`

- [x] **Step 1: Add unmanaged drift test**

Append to `tests/test_release_flow_cli.py`:

```python
def test_preflight_rejects_unmanaged_marketplace_drift(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.1")
    write_manifest(project / "plugins" / "agent-guard" / ".claude-plugin" / "plugin.json", "0.1.1")
    write_json(project / ".agents" / "plugins" / "marketplace.json", {"name": "agent-guard-local-dev", "plugins": []})
    run(["release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1"])
    vars_file = tmp_path / "vars.json"
    write_json(vars_file, {"CODEX_MARKETPLACE_CATALOG_NAME": "agent-guard-marketplace"})
    channel_tree = tmp_path / "marketplace-tree"
    write_json(channel_tree / ".agents" / "plugins" / "marketplace.json", {"name": "agent-guard-marketplace", "plugins": [], "manual": True})

    result = run(
        [
            "preflight",
            "--project",
            str(project),
            "--tag",
            "v0.1.1",
            "--github-vars-file",
            str(vars_file),
            "--channel-tree",
            str(channel_tree),
        ]
    )

    assert result.returncode == 1
    assert "unmanaged_channel_diff: .agents/plugins/marketplace.json" in result.stdout
```

- [x] **Step 2: Run drift test to verify failure**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_preflight_rejects_unmanaged_marketplace_drift -q
```

Expected:

```text
FAILED tests/test_release_flow_cli.py::test_preflight_rejects_unmanaged_marketplace_drift
```

- [x] **Step 3: Implement expected tree comparison**

Add helpers:

```python
def copy_project_tree(source: Path, target: Path) -> None:
    ignore = shutil.ignore_patterns(".git", ".release-flow/releases", "__pycache__", ".pytest_cache")
    shutil.copytree(source, target, ignore=ignore)


def file_bytes(path: Path) -> bytes:
    return path.read_bytes() if path.exists() else b""


def projection_paths(projection: Projection) -> set[str]:
    return {transform.path.replace("\\", "/") for transform in projection.transforms}


def changed_files_between(left: Path, right: Path) -> set[str]:
    files = set()
    for root in [left, right]:
        for path in root.rglob("*"):
            if path.is_file():
                files.add(path.relative_to(root).as_posix())
    return {
        item
        for item in files
        if file_bytes(left / item) != file_bytes(right / item)
    }


def detect_unmanaged_channel_diff(project: Path, channel_tree: Path | None, projection: Projection, variables: dict[str, str]) -> list[str]:
    if channel_tree is None:
        return []
    expected = project.parent / f"{project.name}-expected-channel"
    if expected.exists():
        shutil.rmtree(expected)
    copy_project_tree(project, expected)
    errors = apply_projection(expected, projection, variables)
    if errors:
        return errors
    changed = changed_files_between(expected, channel_tree)
    allowed = projection_paths(projection)
    unmanaged = sorted(item for item in changed if item not in allowed)
    return [f"unmanaged_channel_diff: {item}" for item in unmanaged]
```

Update `run_preflight` after version checks:

```python
    drift_errors = detect_unmanaged_channel_diff(project, args.channel_tree, projection, variables)
    if drift_errors:
        print_errors(drift_errors)
        return 1
```

Extend parser:

```python
preflight.add_argument("--channel-tree", type=Path, help="离线测试或已 checkout 的 marketplace tree。")
```

- [x] **Step 4: Run drift test**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_preflight_rejects_unmanaged_marketplace_drift -q
```

Expected:

```text
1 passed
```

## Task 9: Implement Publish And Summarize Local Commands

**Files:**

- Modify: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`

- [x] **Step 1: Add publish and summarize tests**

Append to `tests/test_release_flow_cli.py`:

```python
def test_publish_refuses_missing_release_plan(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)

    result = run(["publish", "--project", str(project), "--tag", "v0.1.1", "--dry-run"])

    assert result.returncode == 1
    assert "missing_release_plan: v0.1.1" in result.stdout


def test_publish_dry_run_prints_workflow_dispatch_without_git_writes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)
    run(["release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1"])

    result = run(["publish", "--project", str(project), "--tag", "v0.1.1", "--dry-run"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "gh workflow run .github/workflows/release.yml" in result.stdout
    assert "local_branch: not_created" in result.stdout
    assert "tag: not_created" in result.stdout
    assert "push: not_run" in result.stdout


def test_summarize_writes_release_summary(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)
    run(["release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1"])
    workflow_run = tmp_path / "workflow-run.json"
    write_json(
        workflow_run,
        {
            "databaseId": 123,
            "url": "https://github.com/example/repo/actions/runs/123",
            "conclusion": "success",
            "releaseUrl": "https://github.com/example/repo/releases/tag/v0.1.1",
            "marketplaceCommit": "abc123",
            "variables": {"missing": []},
        },
    )

    result = run(["summarize", "--project", str(project), "--tag", "v0.1.1", "--workflow-run-file", str(workflow_run)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: summarized" in result.stdout
    summary = (project / ".release-flow" / "releases" / "v0.1.1" / "release-summary.md").read_text(encoding="utf-8")
    assert "tag: v0.1.1" in summary
    assert "GitHub Release: https://github.com/example/repo/releases/tag/v0.1.1" in summary
    assert "marketplace commit: abc123" in summary
    assert "conclusion: success" in summary
```

- [x] **Step 2: Run publish and summarize tests to verify failure**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_publish_refuses_missing_release_plan tests/test_release_flow_cli.py::test_publish_dry_run_prints_workflow_dispatch_without_git_writes tests/test_release_flow_cli.py::test_summarize_writes_release_summary -q
```

Expected:

```text
FAILED tests/test_release_flow_cli.py::test_publish_refuses_missing_release_plan
FAILED tests/test_release_flow_cli.py::test_publish_dry_run_prints_workflow_dispatch_without_git_writes
FAILED tests/test_release_flow_cli.py::test_summarize_writes_release_summary
```

- [x] **Step 3: Implement publish and summarize**

Add command runner:

```python
def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
```

Add publish:

```python
def workflow_dispatch_command(config: FlowConfig, tag: str) -> list[str]:
    release_plan = f".release-flow/releases/{tag}/release-plan.json"
    return [
        "gh",
        "workflow",
        "run",
        config.workflow_file,
        "-f",
        f"tag={tag}",
        "-f",
        f"releasePlan={release_plan}",
    ]


def run_publish(args: argparse.Namespace) -> int:
    project = normalize(args.project)
    config, config_errors = read_config(project)
    plan, plan_errors = read_release_plan(project, args.tag)
    errors = [*config_errors, *plan_errors]
    if errors:
        print_errors(errors)
        return 1
    command = workflow_dispatch_command(config, args.tag)
    if args.dry_run:
        print("status: dry_run")
        print("command: " + " ".join(command))
        print("local_branch: not_created")
        print("tag: not_created")
        print("push: not_run")
        return 0
    if not args.authorize_publish:
        print_errors(["publish_requires_authorize_publish"])
        return 2
    result = run_command(command, project)
    if result.returncode != 0:
        print_errors([result.stderr.strip() or result.stdout.strip() or "workflow_dispatch_failed"])
        return result.returncode
    workflow_run_path = release_dir(project, args.tag) / "workflow-run.json"
    workflow_run_path.write_text(json.dumps({"tag": args.tag, "dispatch": "triggered"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("status: workflow_triggered")
    print(f"workflow_run: {workflow_run_path}")
    print("local_branch: not_created")
    print("tag: not_created")
    print("push: not_run")
    return 0
```

Add summarize:

```python
def run_summarize(args: argparse.Namespace) -> int:
    project = normalize(args.project)
    plan, plan_errors = read_release_plan(project, args.tag)
    if plan_errors:
        print_errors(plan_errors)
        return 1
    workflow_data = json.loads(args.workflow_run_file.read_text(encoding="utf-8"))
    output_dir = release_dir(project, args.tag)
    workflow_output = output_dir / "workflow-run.json"
    workflow_output.write_text(json.dumps(workflow_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = "\n".join(
        [
            f"# Release {args.tag}",
            "",
            f"tag: {args.tag}",
            f"GitHub Release: {workflow_data.get('releaseUrl', '')}",
            f"marketplace commit: {workflow_data.get('marketplaceCommit', '')}",
            f"variables: {json.dumps(workflow_data.get('variables', {}), ensure_ascii=False)}",
            f"conclusion: {workflow_data.get('conclusion', '')}",
            "",
        ]
    )
    summary_path = output_dir / "release-summary.md"
    summary_path.write_text(summary, encoding="utf-8")
    print("status: summarized")
    print(f"workflow_run: {workflow_output}")
    print(f"release_summary: {summary_path}")
    return 0
```

Extend parser and router:

```python
publish = subparsers.add_parser("publish", help="触发 GitHub Workflow 发布。")
publish.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
publish.add_argument("--tag", required=True, help="发布 tag。")
publish.add_argument("--dry-run", action="store_true", help="只输出 workflow_dispatch 命令。")
publish.add_argument("--authorize-publish", action="store_true", help="授权触发 GitHub Workflow。")

summarize = subparsers.add_parser("summarize", help="生成发布总结。")
summarize.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
summarize.add_argument("--tag", required=True, help="发布 tag。")
summarize.add_argument("--workflow-run-file", type=Path, required=True, help="workflow run JSON 文件。")
```

```python
if args.command == "publish":
    return run_publish(args)
if args.command == "summarize":
    return run_summarize(args)
```

- [x] **Step 4: Run publish and summarize tests**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_publish_refuses_missing_release_plan tests/test_release_flow_cli.py::test_publish_dry_run_prints_workflow_dispatch_without_git_writes tests/test_release_flow_cli.py::test_summarize_writes_release_summary -q
```

Expected:

```text
3 passed
```

## Task 10: Implement GitHub Workflow CI Publish Entry

**Files:**

- Modify: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- Modify: `plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml`

- [x] **Step 1: Add workflow template and ci-publish tests**

Append to `tests/test_release_flow_cli.py`:

```python
def test_workflow_template_is_thin_entrypoint() -> None:
    workflow = (
        REPO_ROOT
        / "plugins"
        / "release-flow"
        / "skills"
        / "release-flow"
        / "assets"
        / "templates"
        / "github"
        / "workflows"
        / "release.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "contents: write" in workflow
    assert "Checkout release-flow plugin" in workflow
    assert "release_flow.py" in workflow
    assert "ci-publish" in workflow
    assert "scripts/release-flow" not in workflow


def test_ci_publish_dry_run_applies_projection_without_remote_writes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)
    write_json(project / ".agents" / "plugins" / "marketplace.json", {"name": "agent-guard-local-dev", "plugins": []})
    run(["release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1"])
    vars_file = tmp_path / "vars.json"
    write_json(vars_file, {"CODEX_MARKETPLACE_CATALOG_NAME": "agent-guard-marketplace"})

    result = run(
        [
            "ci-publish",
            "--project",
            str(project),
            "--tag",
            "v0.1.1",
            "--release-plan",
            ".release-flow/releases/v0.1.1/release-plan.json",
            "--vars-file",
            str(vars_file),
            "--dry-run",
        ]
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: ci_dry_run" in result.stdout
    assert "channel_branch: marketplace" in result.stdout
    assert "tag: v0.1.1" in result.stdout
    assert "remote_write: not_run" in result.stdout
```

- [x] **Step 2: Run ci-publish tests to verify failure**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_workflow_template_is_thin_entrypoint tests/test_release_flow_cli.py::test_ci_publish_dry_run_applies_projection_without_remote_writes -q
```

Expected:

```text
FAILED tests/test_release_flow_cli.py::test_ci_publish_dry_run_applies_projection_without_remote_writes
```

- [x] **Step 3: Implement ci-publish dry-run**

Add command:

```python
def run_ci_publish(args: argparse.Namespace) -> int:
    project = normalize(args.project)
    config, config_errors = read_config(project)
    projection, projection_errors = read_projection(project)
    plan, plan_errors = read_release_plan(project, args.tag)
    errors = [*config_errors, *projection_errors, *plan_errors]
    if errors:
        print_errors(errors)
        return 1
    variables = read_vars_file(args.vars_file)
    if args.dry_run:
        projected = project.parent / f"{project.name}-ci-projected"
        if projected.exists():
            shutil.rmtree(projected)
        copy_project_tree(project, projected)
        projection_errors = apply_projection(projected, projection, variables)
        if projection_errors:
            print_errors(projection_errors)
            return 1
        print("status: ci_dry_run")
        print(f"channel_branch: {config.channel_branch}")
        print(f"tag: {args.tag}")
        print(f"projected_tree: {projected}")
        print("remote_write: not_run")
        return 0
    if not args.authorize_ci_publish:
        print_errors(["ci_publish_requires_authorize_ci_publish"])
        return 2
    print_errors(["ci_publish_remote_write_requires_github_runner_context"])
    return 2
```

Extend parser and router:

```python
ci_publish = subparsers.add_parser("ci-publish", help="GitHub Actions 内部发布入口。")
ci_publish.add_argument("--project", type=Path, required=True, help="checkout 后的源码目录。")
ci_publish.add_argument("--tag", required=True, help="发布 tag。")
ci_publish.add_argument("--release-plan", required=True, help="release-plan 相对路径。")
ci_publish.add_argument("--vars-file", type=Path, help="离线测试变量文件。")
ci_publish.add_argument("--dry-run", action="store_true", help="只生成投影树，不写远端。")
ci_publish.add_argument("--authorize-ci-publish", action="store_true", help="授权 CI 内远端写操作。")
```

```python
if args.command == "ci-publish":
    return run_ci_publish(args)
```

- [x] **Step 4: Run ci-publish tests**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_workflow_template_is_thin_entrypoint tests/test_release_flow_cli.py::test_ci_publish_dry_run_applies_projection_without_remote_writes -q
```

Expected:

```text
2 passed
```

## Task 11: Add Current Repository Release Flow Config

**Files:**

- Create: `.release-flow/config.yaml`
- Create: `.release-flow/projection.yaml`
- Create: `.release-flow/.gitignore`
- Create: `.github/workflows/release.yml`
- Modify: `tests/test_release_flow_cli.py`

- [x] **Step 1: Add current repo config tests**

Append to `tests/test_release_flow_cli.py`:

```python
def test_current_repo_release_flow_files_are_valid() -> None:
    result = run(["validate", "--project", str(REPO_ROOT)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: verified" in result.stdout
    assert ".release-flow" in (REPO_ROOT / ".release-flow" / ".gitignore").read_text(encoding="utf-8")


def test_current_repo_projection_registers_agent_guard_marketplace_variables() -> None:
    projection = (REPO_ROOT / ".release-flow" / "projection.yaml").read_text(encoding="utf-8")

    assert "CODEX_MARKETPLACE_CATALOG_NAME" in projection
    assert "CODEX_MARKETPLACE_DISPLAY_NAME" in projection
    assert "CLAUDE_MARKETPLACE_CATALOG_NAME" in projection
    assert "CLAUDE_MARKETPLACE_OWNER_NAME" in projection
    assert "value:" not in projection
    assert "secret:" not in projection
```

- [x] **Step 2: Run current repo config tests to verify failure**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_current_repo_release_flow_files_are_valid tests/test_release_flow_cli.py::test_current_repo_projection_registers_agent_guard_marketplace_variables -q
```

Expected:

```text
FAILED tests/test_release_flow_cli.py::test_current_repo_release_flow_files_are_valid
FAILED tests/test_release_flow_cli.py::test_current_repo_projection_registers_agent_guard_marketplace_variables
```

- [x] **Step 3: Create current repo release-flow files**

Create `.release-flow/config.yaml` with the same content as `plugins/release-flow/skills/release-flow/assets/templates/release-flow/config.yaml`.

Create `.release-flow/projection.yaml` with the same content as `plugins/release-flow/skills/release-flow/assets/templates/release-flow/projection.yaml`.

Create `.release-flow/.gitignore`:

```gitignore
/releases/
```

Create `.github/workflows/release.yml` with the same content as `plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml`.

- [x] **Step 4: Run current repo config tests**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_current_repo_release_flow_files_are_valid tests/test_release_flow_cli.py::test_current_repo_projection_registers_agent_guard_marketplace_variables -q
```

Expected:

```text
2 passed
```

## Task 12: Configure GitHub Settings Command Boundary

**Files:**

- Modify: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`

- [x] **Step 1: Add configure-github authorization tests**

Append to `tests/test_release_flow_cli.py`:

```python
def test_configure_github_requires_authorization(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)

    result = run(["configure-github", "--project", str(project)])

    assert result.returncode == 2
    assert "configure_github_requires_authorize_github" in result.stdout


def test_configure_github_dry_run_prints_manual_steps(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_release_flow_files(project)

    result = run(["configure-github", "--project", str(project), "--dry-run"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: manual_steps" in result.stdout
    assert "Set Actions workflow permissions to read-and-write" in result.stdout
    assert "Create Rulesets for main, marketplace, and tags" in result.stdout
    assert "Create GitHub Actions Variables" in result.stdout
```

- [x] **Step 2: Run configure-github tests to verify failure**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_configure_github_requires_authorization tests/test_release_flow_cli.py::test_configure_github_dry_run_prints_manual_steps -q
```

Expected:

```text
FAILED tests/test_release_flow_cli.py::test_configure_github_requires_authorization
FAILED tests/test_release_flow_cli.py::test_configure_github_dry_run_prints_manual_steps
```

- [x] **Step 3: Implement configure-github boundary**

Add command:

```python
def run_configure_github(args: argparse.Namespace) -> int:
    project = normalize(args.project)
    config, config_errors = read_config(project)
    projection, projection_errors = read_projection(project)
    errors = [*config_errors, *projection_errors]
    if errors:
        print_errors(errors)
        return 1
    if args.dry_run:
        print("status: manual_steps")
        print("1. Set Actions workflow permissions to read-and-write.")
        print("2. Create Rulesets for main, marketplace, and tags.")
        print("3. Create GitHub Actions Variables:")
        for variable in projection.variables.values():
            print(f"   - {variable.name}")
        return 0
    if not args.authorize_github:
        print_errors(["configure_github_requires_authorize_github"])
        return 2
    print_errors(["github_write_not_available_without_repository_context"])
    return 2
```

Extend parser and router:

```python
configure_github = subparsers.add_parser("configure-github", help="配置 GitHub 仓库设置。")
configure_github.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
configure_github.add_argument("--dry-run", action="store_true", help="输出手动步骤，不写 GitHub。")
configure_github.add_argument("--authorize-github", action="store_true", help="授权写入 GitHub 仓库设置。")
```

```python
if args.command == "configure-github":
    return run_configure_github(args)
```

- [x] **Step 4: Run configure-github tests**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_configure_github_requires_authorization tests/test_release_flow_cli.py::test_configure_github_dry_run_prints_manual_steps -q
```

Expected:

```text
2 passed
```

## Task 13: Full Release Flow Regression

**Files:**

- Modify: `tests/test_release_flow_cli.py`

- [x] **Step 1: Add end-to-end test through user entrypoints**

Append to `tests/test_release_flow_cli.py`:

```python
def test_release_flow_local_e2e(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    setup = run(["setup", "--project", str(project), "--authorize-project-files"])
    assert setup.returncode == 0, setup.stdout + setup.stderr

    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.1")
    write_manifest(project / "plugins" / "agent-guard" / ".claude-plugin" / "plugin.json", "0.1.1")
    write_json(project / ".agents" / "plugins" / "marketplace.json", {"name": "agent-guard-local-dev", "interface": {"displayName": "Agent Guard Local Dev"}, "plugins": []})
    write_json(project / ".claude-plugin" / "marketplace.json", {"name": "agent-guard-local-dev", "owner": {"name": "Agent Guard Local Dev"}, "plugins": []})

    vars_file = tmp_path / "vars.json"
    write_json(
        vars_file,
        {
            "CODEX_MARKETPLACE_CATALOG_NAME": "agent-guard-marketplace",
            "CODEX_MARKETPLACE_DISPLAY_NAME": "Agent Guard",
            "CLAUDE_MARKETPLACE_CATALOG_NAME": "agent-guard-marketplace",
            "CLAUDE_MARKETPLACE_OWNER_NAME": "Agent Guard",
        },
    )

    release_init = run(["release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1"])
    preflight = run(["preflight", "--project", str(project), "--tag", "v0.1.1", "--github-vars-file", str(vars_file)])
    publish = run(["publish", "--project", str(project), "--tag", "v0.1.1", "--dry-run"])
    workflow_run = tmp_path / "workflow-run.json"
    write_json(
        workflow_run,
        {
            "databaseId": 123,
            "url": "https://github.com/example/repo/actions/runs/123",
            "conclusion": "success",
            "releaseUrl": "https://github.com/example/repo/releases/tag/v0.1.1",
            "marketplaceCommit": "abc123",
            "variables": {"missing": []},
        },
    )
    summarize = run(["summarize", "--project", str(project), "--tag", "v0.1.1", "--workflow-run-file", str(workflow_run)])

    assert release_init.returncode == 0, release_init.stdout + release_init.stderr
    assert preflight.returncode == 0, preflight.stdout + preflight.stderr
    assert publish.returncode == 0, publish.stdout + publish.stderr
    assert summarize.returncode == 0, summarize.stdout + summarize.stderr
    assert (project / ".release-flow" / "releases" / "v0.1.1" / "release-plan.json").exists()
    assert (project / ".release-flow" / "releases" / "v0.1.1" / "preflight-report.json").exists()
    assert (project / ".release-flow" / "releases" / "v0.1.1" / "workflow-run.json").exists()
    assert (project / ".release-flow" / "releases" / "v0.1.1" / "release-summary.md").exists()
```

- [x] **Step 2: Run end-to-end test**

Run:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_release_flow_local_e2e -q
```

Expected:

```text
1 passed
```

- [x] **Step 3: Run release-flow test suite**

Run:

```powershell
python -m pytest tests/test_release_flow_plugin_package.py tests/test_release_flow_cli.py -q
```

Expected:

```text
passed
```

The exact count can vary as tests are added during execution; every selected test must pass.

## Task 14: Update OpenSpec Tasks And Validate

**Files:**

- Modify: `openspec/changes/standardize-agent-guard-release-flow/tasks.md`
- Modify: `openspec/changes/standardize-agent-guard-release-flow/.comet.yaml`

- [x] **Step 1: Mark implemented task groups**

After implementation, update `openspec/changes/standardize-agent-guard-release-flow/tasks.md`:

```markdown
- [x] 2.1 新增 `plugins/release-flow/.codex-plugin/plugin.json`，遵循 Codex 官方插件 manifest 结构。
- [x] 2.2 新增 `plugins/release-flow/.claude-plugin/plugin.json`，遵循 Claude 官方插件 manifest 结构。
- [x] 2.3 新增 `plugins/release-flow/skills/release-flow/SKILL.md`，作为 Codex/Claude 共享技能入口。
- [x] 2.4 新增 `plugins/release-flow/skills/release-flow/scripts/`，承载确定性脚本。
- [x] 2.5 新增 `plugins/release-flow/skills/release-flow/assets/templates/`，承载 `.release-flow` 和 GitHub Workflow 模板。
```

Also mark groups 3, 4, 5, and 6 when the corresponding implementation tasks above are complete.

- [x] **Step 2: Update Comet metadata**

Update `openspec/changes/standardize-agent-guard-release-flow/.comet.yaml`:

```yaml
phase: build
plan: docs/superpowers/plans/2026-06-18-standardize-agent-guard-release-flow.md
```

Keep existing fields not shown here unchanged.

- [x] **Step 3: Run OpenSpec strict validation**

Run:

```powershell
openspec validate "standardize-agent-guard-release-flow" --strict
```

Expected:

```text
Change 'standardize-agent-guard-release-flow' is valid
```

- [x] **Step 4: Run full related tests**

Run:

```powershell
python -m pytest tests/test_release_flow_plugin_package.py tests/test_release_flow_cli.py tests/test_agent_guard_plugin_package.py tests/test_agent_guard_plugin_installer.py -q
```

Expected:

```text
passed
```

- [x] **Step 5: Check worktree before handoff**

Run:

```powershell
git status --short
```

Expected:

```text
modified and new files only for standardize-agent-guard-release-flow
```

If the output still includes unrelated deletions under `openspec/changes/fix-agent-guard-plugin-manifest-paths/`, leave them untouched and mention them in the final summary.

## Self-Review Checklist

- Spec coverage:
  - Dual Codex/Claude plugin structure: Tasks 1 and 2.
  - `.release-flow/config.yaml` tracked configuration: Tasks 5 and 11.
  - `.release-flow/projection.yaml` tracked variable registry without values: Tasks 3, 4, and 11.
  - Project setup without release-plan and without copied scripts: Task 5.
  - Single release init creates `.release-flow/releases/<tag>/release-plan.json`: Task 6.
  - Preflight checks config, projection, required variables, version/tag, and channel drift: Tasks 7 and 8.
  - Publish triggers workflow_dispatch and performs no local git writes: Task 9.
  - Workflow template calls plugin-owned script: Task 10.
  - Summary artifacts: Task 9.
  - Agent Guard marketplace variable projection: Task 11.
- Placeholder scan:
  - This plan avoids incomplete code markers and unspecified file paths.
- Type consistency:
  - CLI command names match the tests: `setup`, `github-plan`, `configure-github`, `release-init`, `preflight`, `publish`, `summarize`, `ci-publish`, `validate`, `project`.
  - Release plan keys match the spec: `version`, `tag`, `sourceRef`, `channelBranch`, `workflowFile`, `projectionRegistry`, `dryRun`.
