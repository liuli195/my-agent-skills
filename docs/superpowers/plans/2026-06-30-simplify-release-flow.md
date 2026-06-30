---
change: simplify-release-flow
design-doc: docs/superpowers/specs/2026-06-30-simplify-release-flow-design.md
base-ref: f4eecc28da22940e63f7b284ea3fafcf9d9454b4
archived-with: 2026-06-30-simplify-release-flow
---

# Simplify Release Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（子代理驱动开发，推荐） or superpowers:executing-plans（执行计划） to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除本地 release plan（发布计划）和 release record（发布记录），让 Release Flow（发布流程）只接收 `tag`（标签）、`version`（版本）和 `bumpPlugins`（提升插件列表），并只在 CI（持续集成）隔离发布树生成正式 marketplace（市场）投影。

**Architecture:** 继续使用现有单文件脚本 `release_flow.py`，不新增依赖、不新增兼容层。用一个内置 Plugin registry（插件注册表）同时驱动 projection（投影）校验、Codex marketplace（Codex 市场）生成和 manifest（插件清单）版本路径；本地命令只检查和触发 GitHub Workflow（GitHub 工作流），CI（持续集成）命令在临时发布树里写远端产物。

**Tech Stack:** Python（编程语言）、argparse（参数解析）、YAML（配置格式）、JSON（数据格式）、git（版本管理）、gh（GitHub 命令行）、pytest（测试工具）、GitHub Actions（GitHub 自动化）。

archived-with: 2026-06-30-simplify-release-flow
---

## 文件结构

- Modify: `tests/test_release_flow_cli.py`
  - 覆盖 setup（项目启用）、github-plan（GitHub 配置方案）、configure-github（配置 GitHub）、preflight（发布前检查）、publish（发布）、ci-publish（持续集成发布）和端到端回归。
- Modify: `tests/test_release_flow_plugin_package.py`
  - 删除 `release-flow/gitignore`（发布流程忽略文件）模板必须存在的包检查。
- Modify: `tests/test_build_and_verify_plugin.py`
  - 删除对 `release-vars.json`（发布变量文件）和 `.release-flow/config.yaml` 中插件版本清单的旧假设。
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
  - 删除 `release-init`（发布初始化）、`summarize`（摘要）、release plan（发布计划）、release record（发布记录）逻辑；新增 `bumpPlugins`（提升插件列表）、Plugin registry（插件注册表）、远端冲突检查和 CI（持续集成）隔离发布树。
- Modify: `plugins/release-flow/skills/release-flow/assets/templates/release-flow/config.yaml`
  - 删除 `records`（记录）、`github.rulesets`（GitHub 规则集）和 `manifests.versionFiles`（版本文件列表）。
- Delete: `plugins/release-flow/skills/release-flow/assets/templates/release-flow/gitignore`
  - 不再生成仅服务 `.release-flow/releases/`（发布记录目录）的忽略文件。
- Modify: `plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml`
  - 删除 `releasePlan`（发布计划文件）输入和 `release-init`（发布初始化）步骤，改传 `bumpPlugins`（提升插件列表）。
- Modify: `plugins/release-flow/skills/release-flow/SKILL.md`
  - 删除旧阶段说明，保留 setup（项目启用）、preflight（发布前检查）、publish（发布）和 CI（持续集成）边界。
- Modify: `.release-flow/config.yaml`
  - 当前仓库配置同步删除本地记录、Rulesets（规则集）和版本文件清单。
- Delete: `.release-flow/.gitignore`
  - 当前仓库不再保留 release record（发布记录）忽略规则。
- Modify: `.github/workflows/release.yml`
  - 当前仓库 workflow（工作流）同步模板输入和 CI（持续集成）调用。

## Task 1: 写失败测试，锁定删除面

**Files:**
- Modify: `tests/test_release_flow_cli.py`
- Modify: `tests/test_release_flow_plugin_package.py`
- Modify: `tests/test_build_and_verify_plugin.py`

- [x] **Step 1: 更新测试配置 helper（辅助函数）**

In `tests/test_release_flow_cli.py`, change `write_release_flow_files()` config text to remove `records`（记录）、`github.rulesets`（GitHub 规则集） and `manifests.versionFiles`（版本文件列表）:

```python
version: 1

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
```

- [x] **Step 2: 更新 setup（项目启用）测试**

Change setup dry-run and authorized assertions:

```python
assert "would_write: .release-flow/config.yaml" in result.stdout
assert "would_write: .release-flow/projection.yaml" in result.stdout
assert "would_write: .release-flow/.gitignore" not in result.stdout
assert "would_write: .github/workflows/release.yml" in result.stdout

assert not (project / ".release-flow" / ".gitignore").exists()
assert not (project / ".release-flow" / "releases").exists()
```

- [x] **Step 3: 更新 GitHub（GitHub）配置输出测试**

In `test_github_plan_outputs_expected_settings`, replace Rulesets（规则集） assertions with:

```python
assert "actions_workflow_permissions: read-and-write" in result.stdout
assert "rulesets:" not in result.stdout
assert "branch_protection_fallback:" not in result.stdout
```

In `test_configure_github_dry_run_prints_manual_steps`, assert:

```python
assert "Set Actions workflow permissions to read-and-write" in result.stdout
assert "Rulesets" not in result.stdout
assert "rulesets" not in result.stdout
assert "Create GitHub Actions Variables" not in result.stdout
```

- [x] **Step 4: 删除 release-init（发布初始化）和 summarize（摘要）旧测试**

Delete tests that require these old artifacts:

```text
test_release_init_creates_release_plan_only_for_tag
test_release_init_rejects_dry_run_flag
test_release_init_refuses_existing_plan_without_replace
test_release_init_rejects_tag_with_path_separator
test_release_init_rejects_tag_with_leading_dash
test_preflight_rejects_missing_release_plan
test_preflight_rejects_release_plan_tag_mismatch
test_preflight_writes_report_when_checks_pass
test_publish_refuses_missing_release_plan
test_summarize_writes_release_summary
test_ci_publish_rejects_untrusted_release_plan_path
test_ci_publish_rejects_other_project_release_plan_path
```

Add one parser（参数解析） deletion check:

```python
def test_removed_commands_are_not_registered(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    assert run("release-init", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1").returncode == 2
    assert run("summarize", "--project", str(project), "--tag", "v0.1.1", "--workflow-run-file", str(tmp_path / "run.json")).returncode == 2
```

- [x] **Step 5: 更新包完整性测试**

In `tests/test_release_flow_plugin_package.py`, remove this required item:

```python
"skills/release-flow/assets/templates/release-flow/gitignore",
```

Add:

```python
assert not (PLUGIN_ROOT / "skills/release-flow/assets/templates/release-flow/gitignore").exists()
```

- [x] **Step 6: 更新 build-and-verify（构建与验证）相关测试**

In `tests/test_build_and_verify_plugin.py`, make `write_release_projection_project()` return `None` and stop writing `release-vars.json`:

```python
def write_release_projection_project(project: Path) -> None:
    release_flow_dir = project / ".release-flow"
    release_flow_dir.mkdir(parents=True)
    (project / ".agents" / "plugins").mkdir(parents=True)
    (project / ".claude-plugin").mkdir(parents=True)
    (release_flow_dir / "config.yaml").write_text(RELEASE_FLOW_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    (release_flow_dir / "projection.yaml").write_text(RELEASE_FLOW_PROJECTION.read_text(encoding="utf-8"), encoding="utf-8")
    (project / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"name": "placeholder", "owner": {"name": "placeholder"}, "plugins": []}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
```

In `test_build_and_verify_registered_in_release_flow_sources`, remove `RELEASE_FLOW_CONFIG` from `release_files` because config（配置） no longer lists plugin names.

- [x] **Step 7: 运行失败测试**

Run:

```bash
python -m pytest -q tests/test_release_flow_cli.py tests/test_release_flow_plugin_package.py tests/test_build_and_verify_plugin.py
```

Expected: FAIL（失败） on current implementation still generating `.release-flow/.gitignore`（发布流程忽略文件）, printing Rulesets（规则集）, accepting old commands, and requiring release plan（发布计划）.

- [x] **Step 8: Commit（提交）测试合同**

Run:

```bash
git add tests/test_release_flow_cli.py tests/test_release_flow_plugin_package.py tests/test_build_and_verify_plugin.py
git commit -m "测试 release-flow 简化合同"
```

## Task 2: 精简配置、注册表和命令面

**Files:**
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- Modify: `plugins/release-flow/skills/release-flow/assets/templates/release-flow/config.yaml`
- Delete: `plugins/release-flow/skills/release-flow/assets/templates/release-flow/gitignore`
- Modify: `.release-flow/config.yaml`
- Delete: `.release-flow/.gitignore`

- [x] **Step 1: 删除 setup（项目启用）里的 gitignore（忽略文件）目标**

Change `SETUP_TARGETS` to:

```python
SETUP_TARGETS = [
    ("release-flow/config.yaml", ".release-flow/config.yaml"),
    ("release-flow/projection.yaml", ".release-flow/projection.yaml"),
    ("github/workflows/release.yml", ".github/workflows/release.yml"),
]
```

- [x] **Step 2: 精简 FlowConfig（流程配置）**

Remove these fields from `FlowConfig`:

```python
records_directory: str
manifest_version_files: list[str]
```

In `read_config()`, delete validation for `records`（记录） and `manifests.versionFiles`（版本文件列表）. Add rejection for old keys so stale config（配置） fails clearly:

```python
if "records" in data:
    raise ValueError("invalid_config: records is no longer supported")
if "manifests" in data:
    raise ValueError("invalid_config: manifests.versionFiles is no longer supported")
github = data.get("github", {})
if isinstance(github, dict) and "rulesets" in github:
    raise ValueError("invalid_config: github.rulesets is no longer supported")
```

- [x] **Step 3: 建立单一 Plugin registry（插件注册表）**

Replace `SUPPORTED_CODEX_MARKETPLACE_PLUGINS` and the local `entries` dict inside `codex_marketplace_entry()` with one module-level dict:

```python
PLUGIN_REGISTRY: dict[str, dict[str, Any]] = {
    "agent-guard": {
        "manifests": [
            "plugins/agent-guard/.codex-plugin/plugin.json",
            "plugins/agent-guard/.claude-plugin/plugin.json",
        ],
        "codexMarketplace": {
            "name": "agent-guard",
            "source": {"source": "local", "path": "./plugins/agent-guard"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        },
    },
    "release-flow": {
        "manifests": [
            "plugins/release-flow/.codex-plugin/plugin.json",
            "plugins/release-flow/.claude-plugin/plugin.json",
        ],
        "codexMarketplace": {
            "name": "release-flow",
            "source": {"source": "local", "path": "./plugins/release-flow"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    },
    "cross-agent-review": {
        "manifests": [
            "plugins/cross-agent-review/.codex-plugin/plugin.json",
            "plugins/cross-agent-review/.claude-plugin/plugin.json",
        ],
        "codexMarketplace": {
            "name": "cross-agent-review",
            "source": {"source": "local", "path": "./plugins/cross-agent-review"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    },
    "pr-flow": {
        "manifests": [
            "plugins/pr-flow/.codex-plugin/plugin.json",
            "plugins/pr-flow/.claude-plugin/plugin.json",
        ],
        "codexMarketplace": {
            "name": "pr-flow",
            "source": {"source": "local", "path": "./plugins/pr-flow"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    },
    "build-and-verify": {
        "manifests": [
            "plugins/build-and-verify/.codex-plugin/plugin.json",
            "plugins/build-and-verify/.claude-plugin/plugin.json",
        ],
        "codexMarketplace": {
            "name": "build-and-verify",
            "source": {"source": "local", "path": "./plugins/build-and-verify"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    },
}
```

Then implement:

```python
def registry_plugin_names() -> set[str]:
    return set(PLUGIN_REGISTRY)


def plugin_manifest_paths(plugin_name: str) -> list[str]:
    try:
        return list(PLUGIN_REGISTRY[plugin_name]["manifests"])
    except KeyError as exc:
        raise ValueError(f"plugin_unknown: {plugin_name}") from exc
```

- [x] **Step 4: 让 projection（投影）和 marketplace（市场）生成共用注册表**

In `projection_errors()`, replace membership check with:

```python
if plugin_name not in PLUGIN_REGISTRY:
    errors.append(f"projection_generator_plugin_unknown: {plugin_name}")
```

Change `codex_marketplace_entry()` to:

```python
def codex_marketplace_entry(plugin_name: str) -> dict[str, Any]:
    try:
        return dict(PLUGIN_REGISTRY[plugin_name]["codexMarketplace"])
    except KeyError as exc:
        raise ValueError(f"projection_generator_plugin_unknown: {plugin_name}") from exc
```

- [x] **Step 5: 删除旧 release plan（发布计划）和 summary（摘要）函数**

Delete these functions:

```text
release_plan_path
read_release_plan
run_release_init
release_record_directory
release_summary_markdown
run_summarize
resolve_release_plan_arg
```

Also remove `release-init`（发布初始化） and `summarize`（摘要） parser（参数解析） registration and their `main()` branches.

- [x] **Step 6: 更新配置文件**

In both config（配置） files:

```text
plugins/release-flow/skills/release-flow/assets/templates/release-flow/config.yaml
.release-flow/config.yaml
```

Keep only:

```yaml
version: 1

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
```

Delete both `.release-flow/.gitignore` files listed in the file structure.

- [x] **Step 7: Run（运行）配置和包测试**

Run:

```bash
python -m pytest -q tests/test_release_flow_plugin_package.py tests/test_build_and_verify_plugin.py::test_build_and_verify_release_projection_passes_real_validate
```

Expected: PASS（通过）.

- [x] **Step 8: Commit（提交）配置和命令删除**

Run:

```bash
git add plugins/release-flow/skills/release-flow/scripts/release_flow.py plugins/release-flow/skills/release-flow/assets/templates/release-flow/config.yaml plugins/release-flow/skills/release-flow/assets/templates/release-flow/gitignore .release-flow/config.yaml .release-flow/.gitignore tests/test_release_flow_plugin_package.py
git commit -m "精简 release-flow 配置和命令"
```

## Task 3: 实现 bumpPlugins（提升插件列表）和 preflight（发布前检查）

**Files:**
- Modify: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`

- [x] **Step 1: 添加输入解析测试**

Add tests:

```python
def test_preflight_rejects_missing_bump_plugins(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("preflight", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1")

    assert result.returncode == 2


def test_preflight_rejects_unknown_bump_plugin(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run("preflight", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1", "--bump-plugins", "missing-plugin")

    assert result.returncode == 1
    assert "plugin_unknown: missing-plugin" in result.stdout
```

- [x] **Step 2: 添加远端基准测试 helper（辅助函数）**

Add a helper in `tests/test_release_flow_cli.py`:

```python
def init_project_with_remote(project: Path, remote: Path) -> None:
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(remote)], check=True, capture_output=True, text=True)
    assert git(project, "init").returncode == 0
    assert git(project, "config", "user.email", "test@example.com").returncode == 0
    assert git(project, "config", "user.name", "Test").returncode == 0
    assert git(project, "add", ".").returncode == 0
    assert git(project, "commit", "-m", "baseline").returncode == 0
    assert git(project, "remote", "add", "origin", str(remote)).returncode == 0
    assert git(project, "push", "origin", "HEAD:refs/heads/main").returncode == 0
    assert git(project, "fetch", "origin", "main:refs/remotes/origin/marketplace").returncode == 0
```

Use the existing `git()` helper already in the test file.

- [x] **Step 3: 添加版本检查测试**

Add three focused tests:

```python
def test_preflight_accepts_partial_plugin_bump(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    write_release_flow_files(project)
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.1")
    write_manifest(project / "plugins" / "agent-guard" / ".claude-plugin" / "plugin.json", "0.1.1")
    write_manifest(project / "plugins" / "release-flow" / ".codex-plugin" / "plugin.json", "0.1.0")
    write_manifest(project / "plugins" / "release-flow" / ".claude-plugin" / "plugin.json", "0.1.0")
    init_project_with_remote(project, remote)

    result = run("preflight", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1", "--bump-plugins", "agent-guard")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: preflight_passed" in result.stdout


def test_preflight_accepts_empty_bump_plugins_when_versions_do_not_drift(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    write_release_flow_files(project)
    for plugin in ["agent-guard", "release-flow"]:
        write_manifest(project / "plugins" / plugin / ".codex-plugin" / "plugin.json", "0.1.0")
        write_manifest(project / "plugins" / plugin / ".claude-plugin" / "plugin.json", "0.1.0")
    init_project_with_remote(project, remote)

    result = run("preflight", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1", "--bump-plugins", "")

    assert result.returncode == 0, result.stdout + result.stderr


def test_preflight_rejects_unbumped_manifest_drift(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    write_release_flow_files(project)
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.0")
    write_manifest(project / "plugins" / "agent-guard" / ".claude-plugin" / "plugin.json", "0.1.0")
    init_project_with_remote(project, remote)
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.1")

    result = run("preflight", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1", "--bump-plugins", "")

    assert result.returncode == 1
    assert "plugin_requires_bump: agent-guard" in result.stdout
```

- [x] **Step 4: 添加远端冲突测试**

Add tests:

```python
def test_preflight_rejects_existing_remote_tag(tmp_path: Path) -> None:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    write_release_flow_files(project)
    write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.1")
    write_manifest(project / "plugins" / "agent-guard" / ".claude-plugin" / "plugin.json", "0.1.1")
    init_project_with_remote(project, remote)
    assert git(project, "tag", "v0.1.1").returncode == 0
    assert git(project, "push", "origin", "refs/tags/v0.1.1").returncode == 0

    result = run("preflight", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1", "--bump-plugins", "agent-guard")

    assert result.returncode == 1
    assert "release already exists" in result.stdout
```

For GitHub Release（GitHub 发布）, reuse the fake `gh` pattern already used in the file and make `gh release view v0.1.1` return 0.

- [x] **Step 5: 添加 CLI（命令行界面）输入**

In `build_parser()`:

```python
preflight.add_argument("--version", required=True, help="发布版本。")
preflight.add_argument("--bump-plugins", required=True, help="逗号分隔插件名；空字符串表示不提升插件。")
publish.add_argument("--version", required=True, help="发布版本。")
publish.add_argument("--bump-plugins", required=True, help="逗号分隔插件名；空字符串表示不提升插件。")
ci_publish.add_argument("--version", required=True, help="发布版本。")
ci_publish.add_argument("--bump-plugins", required=True, help="逗号分隔插件名；空字符串表示不提升插件。")
```

- [x] **Step 6: 实现输入和版本 helper（辅助函数）**

Add:

```python
def parse_bump_plugins(raw: str) -> list[str]:
    if raw == "":
        return []
    plugins = [item.strip() for item in raw.split(",")]
    if any(not item for item in plugins):
        raise ValueError("bump_plugins_invalid")
    unknown = [plugin for plugin in plugins if plugin not in PLUGIN_REGISTRY]
    if unknown:
        raise ValueError(f"plugin_unknown: {unknown[0]}")
    return plugins


def manifest_version(project: Path, manifest_file: str) -> str:
    manifest = read_json_mapping(resolve_project_path(project, Path(manifest_file), "invalid_manifest_path"))
    version = manifest.get("version")
    if not isinstance(version, str):
        raise ValueError(f"manifest_version_missing: {manifest_file}")
    return version
```

- [x] **Step 7: 实现远端基准读取**

Add:

```python
def git_output(project: Path, args: list[str]) -> str:
    result = subprocess.run(["git", "-C", str(project), *args], check=False, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"command_failed: git {' '.join(args)}: {detail}")
    return result.stdout


def remote_manifest_version(project: Path, config: FlowConfig, manifest_file: str) -> str | None:
    ref = f"origin/{config.release_channel_branch}"
    git_output(project, ["rev-parse", "--verify", ref])
    result = subprocess.run(["git", "-C", str(project), "show", f"{ref}:{manifest_file}"], check=False, text=True, capture_output=True)
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    version = data.get("version")
    if not isinstance(version, str):
        raise ValueError(f"remote_manifest_version_missing: {manifest_file}")
    return version
```

- [x] **Step 8: 实现远端 tag/release（标签/发布）检查**

Add:

```python
def remote_release_errors(project: Path, tag: str) -> list[str]:
    errors: list[str] = []
    tag_result = subprocess.run(["git", "-C", str(project), "ls-remote", "--tags", "origin", f"refs/tags/{tag}"], check=False, text=True, capture_output=True)
    if tag_result.returncode != 0:
        return [f"remote_release_unknown: {tag}"]
    if tag_result.stdout.strip():
        errors.append(f"release already exists: {tag}")
    gh_result = subprocess.run(["gh", "release", "view", tag], cwd=project, check=False, text=True, capture_output=True)
    gh_output = (gh_result.stderr or gh_result.stdout).lower()
    if gh_result.returncode == 0:
        errors.append(f"release already exists: {tag}")
    elif "not found" not in gh_output and "could not resolve" not in gh_output:
        errors.append(f"remote_release_unknown: {tag}")
    return errors
```

- [x] **Step 9: 重写 preflight_errors（发布前检查错误）**

Replace release plan（发布计划） logic with:

```python
def preflight_errors(project: Path, tag: str, version: str, bump_plugins: list[str], config: FlowConfig, projection: Projection) -> list[str]:
    errors: list[str] = []
    expected_version = tag_version(tag)
    if version != expected_version:
        errors.append(f"release_version_mismatch: {tag}")
    projection_plugins = sorted({plugin for generator in projection.generators for plugin in generator.plugins})
    for plugin_name in projection_plugins:
        if plugin_name not in PLUGIN_REGISTRY:
            errors.append(f"projection_generator_plugin_unknown: {plugin_name}")
    bumped = set(bump_plugins)
    for plugin_name in projection_plugins:
        for manifest_file in plugin_manifest_paths(plugin_name):
            try:
                current = manifest_version(project, manifest_file)
                if plugin_name in bumped:
                    if current != version:
                        errors.append(f"manifest_version_mismatch: {manifest_file}")
                else:
                    remote = remote_manifest_version(project, config, manifest_file)
                    if remote is None or current != remote:
                        errors.append(f"plugin_requires_bump: {plugin_name}")
                        break
            except ValueError as exc:
                errors.append(str(exc))
    if not errors:
        with tempfile.TemporaryDirectory(prefix="release-flow-preflight-") as temp_dir:
            expected_tree = Path(temp_dir) / "expected"
            copy_project_for_expected(project, expected_tree)
            expected_projection = read_projection(expected_tree)
            apply_projection(expected_tree, expected_projection)
            errors.extend(marketplace_identity_errors(expected_tree, expected_projection))
    errors.extend(remote_release_errors(project, tag))
    return errors
```

- [x] **Step 10: 更新 run_preflight（运行发布前检查）**

Use:

```python
bump_plugins = parse_bump_plugins(args.bump_plugins)
errors = preflight_errors(args.project, args.tag, args.version, bump_plugins, config, projection)
```

Do not write `preflight-report.json`（发布前检查报告）. On success print only:

```python
print("status: preflight_passed")
print(f"release_tag: {args.tag}")
print(f"version: {args.version}")
print(f"bumpPlugins: {','.join(bump_plugins)}")
```

- [x] **Step 11: Run（运行）preflight（发布前检查）测试**

Run:

```bash
python -m pytest -q tests/test_release_flow_cli.py -k "preflight"
```

Expected: PASS（通过）.

- [x] **Step 12: Commit（提交）preflight（发布前检查）**

Run:

```bash
git add tests/test_release_flow_cli.py plugins/release-flow/skills/release-flow/scripts/release_flow.py
git commit -m "加入 release-flow 提升插件检查"
```

## Task 4: 改 publish（发布）、workflow（工作流）和 CI（持续集成）隔离发布

**Files:**
- Modify: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- Modify: `plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml`
- Modify: `.github/workflows/release.yml`

- [x] **Step 1: 更新 publish --dry-run（发布试运行）测试**

Change dry-run setup so it no longer calls `release-init`（发布初始化）. Assert:

```python
result = run("publish", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1", "--bump-plugins", "agent-guard", "--dry-run")

assert result.returncode == 0
assert "status: dry_run" in result.stdout
assert "-f tag=v0.1.1" in result.stdout
assert "-f version=0.1.1" in result.stdout
assert "-f bumpPlugins=agent-guard" in result.stdout
assert "releasePlan" not in result.stdout
assert "release_tag: v0.1.1" in result.stdout
assert "local_branch_created: false" in result.stdout
assert "git_tag_created: false" in result.stdout
assert "push_run: false" in result.stdout
```

- [x] **Step 2: 更新 workflow（工作流）模板测试**

In `test_workflows_are_thin_entrypoints`, assert both workflow（工作流） files:

```python
assert "releasePlan" not in workflow
assert "release-init" not in workflow
assert "bumpPlugins:" in workflow
assert "--bump-plugins" in workflow
assert "ci-publish" in workflow
assert "--release-plan" not in workflow
```

- [x] **Step 3: 更新 CI（持续集成）发布测试**

Rename `test_ci_publish_authorized_pushes_channel_tag_and_creates_release` to include isolation（隔离）. Remove `release-init`（发布初始化） call and call:

```python
result = run(
    "ci-publish",
    "--project",
    str(clone),
    "--tag",
    "v0.1.1",
    "--version",
    "0.1.1",
    "--bump-plugins",
    "agent-guard",
    "--authorize-ci-publish",
    env=env,
)
```

Assert:

```python
assert "status: ci_published" in result.stdout
assert "release_url:" in result.stdout
assert "marketplace_commit:" in result.stdout
assert "tag_commit:" in result.stdout
assert "workflow_run_url:" in result.stdout
assert git(clone, "status", "--short").stdout == ""
assert git(clone, "show-ref", "--verify", "refs/tags/v0.1.1").returncode != 0
```

- [x] **Step 4: 更新 workflow_dispatch_command（工作流触发命令）**

Replace the old signature with:

```python
def workflow_dispatch_command(config: FlowConfig, tag: str, version: str, bump_plugins: list[str]) -> str:
    validate_release_tag(tag)
    return (
        f"gh workflow run {config.workflow_file} --ref {config.release_source_ref} "
        f"-f tag={tag} -f version={version} -f bumpPlugins={','.join(bump_plugins)}"
    )
```

In `run_publish()`, parse `bump_plugins`, require authorization only for non-dry-run, and never read release plan（发布计划）.

- [x] **Step 5: 更新 workflow（工作流）文件**

In both workflow（工作流） files, replace inputs with:

```yaml
      bumpPlugins:
        description: Comma-separated plugins to bump; empty means catalog/projection only
        required: true
        type: string
```

Delete the entire `Initialize release plan` step. Change CI（持续集成） command to:

```yaml
          ci-publish
          --project source
          --tag "${{ inputs.tag }}"
          --version "${{ inputs.version }}"
          --bump-plugins "${{ inputs.bumpPlugins }}"
          --authorize-ci-publish
```

- [x] **Step 6: 实现隔离发布树 helper（辅助函数）**

Add:

```python
def origin_url(project: Path) -> str:
    return git_output(project, ["config", "--get", "remote.origin.url"]).strip()


def workflow_run_url() -> str:
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return ""
```

Add `import os` at the top.

- [x] **Step 7: 重写 run_ci_publish_remote（运行持续集成发布远端写入）**

Keep one implementation path, no dry-run（试运行） branch:

```python
def run_ci_publish_remote(project: Path, config: FlowConfig, projection: Projection, tag: str) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="release-flow-ci-") as temp_dir:
        release_tree = Path(temp_dir) / "release-tree"
        copy_project_for_expected(project, release_tree)
        apply_projection(release_tree, projection)
        run_checked(["git", "init"], release_tree)
        run_checked(["git", "remote", "add", "origin", origin_url(project)], release_tree)
        run_checked(["git", "config", "user.name", "github-actions[bot]"], release_tree)
        run_checked(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], release_tree)
        run_checked(["git", "checkout", "--orphan", release_branch_name(tag)], release_tree)
        run_checked(["git", "add", "-A"], release_tree)
        run_checked(["git", "commit", "-m", f"release: {tag}"], release_tree)
        marketplace_commit = git_output(release_tree, ["rev-parse", "HEAD"]).strip()
        run_checked(["git", "push", "origin", f"HEAD:refs/heads/{config.release_channel_branch}", "--force"], release_tree)
        run_checked(["git", "tag", "--", tag], release_tree)
        tag_commit = git_output(release_tree, ["rev-list", "-n", "1", tag]).strip()
        run_checked(["git", "push", "origin", f"refs/tags/{tag}"], release_tree)
        release = run_checked(["gh", "release", "create", tag, "--title", tag, "--notes", f"Release {tag}"], release_tree)
        return {
            "release_url": release.stdout.strip().splitlines()[0] if release.stdout.strip() else "",
            "marketplace_commit": marketplace_commit,
            "tag_commit": tag_commit,
            "workflow_run_url": workflow_run_url(),
        }
```

- [x] **Step 8: 更新 run_ci_publish（运行持续集成发布）**

Before writing remote产物, repeat checks:

```python
bump_plugins = parse_bump_plugins(args.bump_plugins)
errors = preflight_errors(args.project, args.tag, args.version, bump_plugins, config, projection)
if errors:
    print("status: issues")
    for error in errors:
        print(f"error: {error}")
    return 1
trace = run_ci_publish_remote(args.project, config, projection, args.tag)
print("status: ci_published")
print(f"channel_branch: {config.release_channel_branch}")
print(f"tag: {args.tag}")
for key, value in trace.items():
    print(f"{key}: {value}")
```

- [x] **Step 9: Run（运行）publish（发布）和 CI（持续集成）测试**

Run:

```bash
python -m pytest -q tests/test_release_flow_cli.py -k "publish or workflow"
```

Expected: PASS（通过）.

- [x] **Step 10: Commit（提交）发布执行**

Run:

```bash
git add tests/test_release_flow_cli.py plugins/release-flow/skills/release-flow/scripts/release_flow.py plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml .github/workflows/release.yml
git commit -m "隔离执行 release-flow 发布"
```

## Task 5: 更新技能说明和端到端回归

**Files:**
- Modify: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/SKILL.md`

- [x] **Step 1: 更新本地端到端测试**

Rewrite `test_release_flow_local_e2e` to run the user path without release record（发布记录）:

```python
setup = run("setup", "--project", str(project), "--authorize-project-files")
assert setup.returncode == 0, setup.stdout + setup.stderr
write_manifest(project / "plugins" / "agent-guard" / ".codex-plugin" / "plugin.json", "0.1.1")
write_manifest(project / "plugins" / "agent-guard" / ".claude-plugin" / "plugin.json", "0.1.1")
init_project_with_remote(project, tmp_path / "remote.git")

preflight = run("preflight", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1", "--bump-plugins", "agent-guard")
assert preflight.returncode == 0, preflight.stdout + preflight.stderr

publish = run("publish", "--project", str(project), "--tag", "v0.1.1", "--version", "0.1.1", "--bump-plugins", "agent-guard", "--dry-run")
assert publish.returncode == 0, publish.stdout + publish.stderr

assert not (project / ".release-flow" / "releases").exists()
assert not (project / ".release-flow" / ".gitignore").exists()
```

- [x] **Step 2: 更新 CI（持续集成）端到端测试**

In the CI（持续集成） publish test, also assert source checkout（源码检出） keeps DEV（开发） identity:

```python
source_marketplace = json.loads((clone / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
assert source_marketplace["name"] == "local-dev"
show = git(remote, "show", "refs/heads/marketplace:.agents/plugins/marketplace.json")
assert json.loads(show.stdout)["name"] == "my-agent-skills-marketplace"
```

- [x] **Step 3: 更新 Skill（技能）说明**

In `plugins/release-flow/skills/release-flow/SKILL.md`, change description to:

```yaml
description: Use when a project needs a reusable GitHub-based release flow with setup, preflight, publish, and CI publish phases.
```

Replace the old bullet list with:

```markdown
- enable release-flow in a project,
- run release preflight checks with `tag`, `version`, and `bumpPlugins`,
- trigger a GitHub workflow release,
- inspect CI release trace fields from workflow output.
```

In Boundaries（边界）, remove `.release-flow/.gitignore` and `.release-flow/releases/<tag>/release-plan.json`; add:

```markdown
- Project setup writes only `.release-flow/config.yaml`, `.release-flow/projection.yaml`, and a thin GitHub Workflow entry after explicit authorization.
- Local commands do not create release plan files, release records, branches, tags, or release summaries.
- `bumpPlugins` is required; an empty value means catalog/projection-only release.
```

- [x] **Step 4: Run（运行）端到端测试**

Run:

```bash
python -m pytest -q tests/test_release_flow_cli.py::test_release_flow_local_e2e tests/test_release_flow_cli.py::test_ci_publish_authorized_pushes_channel_tag_and_creates_release
```

Expected: PASS（通过）.

- [x] **Step 5: Commit（提交）文档和回归**

Run:

```bash
git add tests/test_release_flow_cli.py plugins/release-flow/skills/release-flow/SKILL.md
git commit -m "更新 release-flow 端到端回归"
```

## Task 6: 完整验证

**Files:**
- Verify only.

- [x] **Step 1: 扫描旧合同残留**

Run:

```bash
rg "release-init|summarize|releasePlan|release-plan|release-summary|preflight-report|workflow-run.json|records:|versionFiles|github\\.rulesets|Rulesets|\\.release-flow/releases|release-vars.json" plugins/release-flow tests .release-flow .github docs/superpowers/plans/2026-06-30-simplify-release-flow.md
```

Expected: only this plan file may contain old terms as deletion instructions; runtime（运行时）、template（模板）、config（配置） and tests（测试） must not require old behavior.

- [x] **Step 2: 运行 release-flow（发布流程）测试**

Run:

```bash
python -m pytest -q tests/test_release_flow_cli.py tests/test_release_flow_plugin_package.py
```

Expected: PASS（通过）.

- [x] **Step 3: 运行 build-and-verify（构建与验证）相关测试**

Run:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py
```

Expected: PASS（通过）.

- [x] **Step 4: 运行 OpenSpec（开放规格）校验**

Run:

```bash
openspec validate simplify-release-flow --strict
```

Expected: PASS（通过）.

- [x] **Step 5: 运行仓库 verify（验证）入口**

Run:

```bash
python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .
```

Expected: PASS（通过） for affected checks（受影响检查项）.

- [x] **Step 6: Commit（提交）验证收尾**

Run:

```bash
git status --short
git commit --allow-empty -m "验证 release-flow 简化实现"
```

Only use the empty commit if project workflow expects a verification checkpoint; otherwise skip it.

## Self-Review

- Spec coverage（规格覆盖）: 覆盖删除 `release-init`（发布初始化）、release plan（发布计划）、release record（发布记录）、`summarize`（摘要）、Rulesets（规则集）输出和 `.release-flow/.gitignore`；覆盖 `bumpPlugins`（提升插件列表）、单一 Plugin registry（插件注册表）、远端 tag/release（标签/发布）检查、CI（持续集成）隔离 projection（投影）和端到端回归。
- Placeholder scan（占位扫描）: 没有占位词或“以后实现”；每个实现步骤都指定文件、代码形状、命令和期望结果。
- Type consistency（类型一致性）: CLI（命令行界面）使用 `--bump-plugins`，workflow（工作流）输入使用 `bumpPlugins`，内部统一为 `list[str]`；版本路径只从 `PLUGIN_REGISTRY`（插件注册表）读取。
