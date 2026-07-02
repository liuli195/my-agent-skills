---
change: remove-release-flow-github-vars
design-doc: docs/superpowers/specs/2026-06-29-remove-release-flow-github-vars-design.md
base-ref: 4c062b57d1e7e6e477aaa12aeb1c3109a36a59ed
archived-with: 2026-06-28-remove-release-flow-github-vars
---

# Remove Release-Flow GitHub Variables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（子代理驱动开发，推荐） or superpowers:executing-plans（执行计划） to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 删除 release-flow（发布流程）对六个非敏感 GitHub Variables（GitHub 变量）和本地变量文件的依赖，让 `.release-flow/projection.yaml` 的 identity（身份）成为 marketplace（市场）身份唯一来源。

**Architecture:** 最小修复集中在 release_flow.py（发布流程脚本）的 projection（投影）读取、transform（转换）应用和 CLI（命令行界面）参数上；workflow（工作流）模板直接运行 source repo（源仓库）里的脚本。保留 `json-env` 这个 transform type（转换类型）名称，只把取值从变量名改为 identity（身份）引用。

**Tech Stack:** Python（编程语言）、argparse（参数解析库）、YAML（配置格式）、JSON（数据格式）、pytest（测试工具）、GitHub Actions（GitHub 自动化）。

---

## 文件结构

- Modify: `tests/test_release_flow_cli.py`
  - 负责 CLI（命令行界面）、模板、当前仓库文件和端到端回归覆盖。
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
  - 负责 projection（投影）模型、identity（身份）取值、旧参数删除、validate（校验）、release-init（发布初始化）、github-plan（GitHub 计划）、configure-github --dry-run（配置 GitHub 试运行）、project（投影）、preflight（预检）、ci-publish（持续集成发布）。
- Modify: `plugins/release-flow/skills/release-flow/assets/templates/release-flow/projection.yaml`
  - 负责新项目 projection（投影）模板。
- Modify: `.release-flow/projection.yaml`
  - 负责当前仓库 projection（投影）。
- Modify: `plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml`
  - 负责新项目 workflow（工作流）模板。
- Modify: `.github/workflows/release.yml`
  - 负责当前仓库 workflow（工作流）。
- Modify: `openspec/changes/remove-release-flow-github-vars/specs/release-flow-plugin/spec.md`
  - 负责 delta spec（差异规格）与实现语义一致。

## Task 1: 写失败测试

**Files:**
- Modify: `tests/test_release_flow_cli.py`

- [x] **Step 1: 把测试 helper（辅助函数）改成 identity-only（仅身份）projection（投影）**

Replace `marketplace_identity_projection()` and `marketplace_identity_vars()` with this:

```python
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
```

- [x] **Step 2: 更新 GitHub 计划测试**

Change `test_github_plan_outputs_expected_settings` so it asserts no variable block:

```python
assert "actions_variables:" not in result.stdout
assert "CODEX_MARKETPLACE_CATALOG_NAME" not in result.stdout
```

Change `test_github_plan_prints_required_projection_variable_details` into:

```python
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
```

- [x] **Step 3: 更新当前仓库 projection（投影）测试**

Rename `test_current_repo_projection_registers_agent_guard_marketplace_variables` to `test_current_repo_projection_does_not_register_marketplace_variables` and assert absence:

```python
for variable in [
    "CODEX_MARKETPLACE_CATALOG_NAME",
    "CODEX_MARKETPLACE_DISPLAY_NAME",
    "CLAUDE_MARKETPLACE_CATALOG_NAME",
    "CLAUDE_MARKETPLACE_OWNER_NAME",
    "RELEASE_FLOW_PLUGIN_REPOSITORY",
    "RELEASE_FLOW_PLUGIN_REF",
]:
    assert variable not in result.stdout
```

- [x] **Step 4: 删除旧的 release-flow plugin（发布流程插件）变量必填测试**

Delete `test_validate_rejects_projection_identity_without_required_release_flow_variables`; the new contract（契约）要求 validate（校验）接受没有这些变量的 projection（投影）。

- [x] **Step 5: 更新 configure-github（配置 GitHub）试运行测试**

In `test_configure_github_dry_run_prints_manual_steps`, replace variable assertions with:

```python
assert "Create GitHub Actions Variables" not in result.stdout
```

Change `test_configure_github_dry_run_prints_projection_variable_details` into:

```python
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
```

- [x] **Step 6: 更新 project（投影）测试，不再传 `--vars-file`**

Update transform（转换） tests to use identity（身份） references:

```yaml
transforms:
  - path: .agents/plugins/marketplace.json
    type: json-env
    set:
      /name: identity.codex.marketplaceName
```

Run project（投影） with:

```python
result = run("project", "--project", str(project))
```

Expected assertions stay on generated JSON（数据格式） values.

- [x] **Step 7: 增加旧参数拒绝测试**

Add three focused tests:

```python
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

    result = run("preflight", "--project", str(project), "--tag", "v0.1.1", "--github-vars-file", str(vars_file))

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
```

- [x] **Step 8: 更新 preflight（预检）、ci-publish（持续集成发布）和 e2e（端到端）测试**

Remove `vars_file` setup and old argument passing from preflight（预检）、ci-publish（持续集成发布） and `test_release_flow_local_e2e`. For passing projection（投影） checks, write target files before preflight（预检）:

```python
write_json(project / ".agents" / "plugins" / "marketplace.json", {"name": "local-dev", "interface": {"displayName": "Local Dev"}})
write_json(project / ".claude-plugin" / "marketplace.json", {"name": "local-dev", "owner": {"name": "Local Dev"}})
```

Expected report assertion:

```python
assert "variables" not in report
```

- [x] **Step 9: 更新 workflow（工作流）模板测试**

Change `test_workflow_template_is_thin_entrypoint` assertions to:

```python
assert "Checkout release-flow plugin" not in template
assert "release-vars.json" not in template
assert "--vars-file" not in template
assert "release-flow-plugin/" not in template
assert "source/plugins/release-flow/skills/release-flow/scripts/release_flow.py" in template
```

- [x] **Step 10: 运行失败测试**

Run:

```bash
python -m pytest tests/test_release_flow_cli.py -q
```

Expected: FAIL（失败） because release_flow.py（发布流程脚本）、projection（投影）文件和 workflow（工作流）文件 still use old variables and old arguments.

## Task 2: 最小修改 release_flow.py（发布流程脚本）

**Files:**
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`

- [x] **Step 1: 删除 releaseFlowPlugin（发布流程插件）identity（身份）字段**

Remove `ProjectionReleaseFlowPluginIdentity` and remove `release_flow_plugin` from `ProjectionIdentity`. In `read_projection_identity()`, stop reading `identity.releaseFlowPlugin`.

- [x] **Step 2: 保留 identity（身份）值解析的四个 marketplace（市场）字段**

Make `projection_identity_value()` contain only:

```python
values = {
    "identity.codex.marketplaceName": projection.identity.codex.marketplace_name,
    "identity.codex.displayName": projection.identity.codex.display_name,
    "identity.claude.marketplaceName": projection.identity.claude.marketplace_name,
    "identity.claude.ownerName": projection.identity.claude.owner_name,
}
```

- [x] **Step 3: 简化 projection_errors（投影错误）**

Delete `projection_identity_variable_errors()` and remove the block that requires `RELEASE_FLOW_PLUGIN_REPOSITORY` and `RELEASE_FLOW_PLUGIN_REF`. In transform（转换） validation, check the set value by calling `projection_identity_value(projection, reference)` instead of checking `reference in projection.variables`.

- [x] **Step 4: 让 json-env（JSON 环境转换）从 identity（身份）取值**

Change signatures:

```python
def apply_json_env_transform(project: Path, projection: Projection, transform: ProjectionTransform) -> None:
    target_path = resolve_project_path(project, transform.path, "invalid_projection_transform_path")
    target = read_json_mapping(target_path)
    for pointer, reference in transform.set.items():
        set_json_pointer(target, pointer, projection_identity_value(projection, reference))
    target_path.write_text(json.dumps(target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_projection(project: Path, projection: Projection) -> None:
    for generator in projection.generators:
        apply_projection_generator(project, projection, generator)
    for transform in projection.transforms:
        apply_json_env_transform(project, projection, transform)
```

- [x] **Step 5: 删除 project（投影）变量文件读取**

In `run_project()`, remove `read_json_mapping(args.vars_file)` and call:

```python
apply_projection(args.project, projection)
```

- [x] **Step 6: 删除 GitHub Variables（GitHub 变量）输出**

In `run_github_plan()`, keep only status（状态）、Actions（动作） permissions（权限）、Rulesets（规则集） and branch protection fallback（分支保护兜底） lines. Delete `actions_variables:` output.

In `run_configure_github()`, delete `variables = [...]`, delete `Create GitHub Actions Variables`, and delete the loop that prints variable details.

- [x] **Step 7: 删除 preflight（预检）变量逻辑**

Change `preflight_errors()` signature to remove `vars_data`. Delete missing variable checks, required variable report, and identity variable mismatch checks. Change projection（投影） application call to:

```python
apply_projection(expected_tree, expected_projection)
```

Change report（报告） to omit `variables`:

```python
report = {
    "tag": tag,
    "version": {
        "expected": expected_version,
        "releasePlan": plan_version,
        "manifests": versions,
        "mismatchedManifests": mismatched_manifests,
    },
}
```

- [x] **Step 8: 删除 ci-publish（持续集成发布）变量逻辑**

Change `run_ci_publish_remote()` signature to remove `vars_data`, and call:

```python
apply_projection(project, projection)
```

In `run_ci_publish()`, delete `vars_data = read_json_mapping(args.vars_file)` and call:

```python
run_ci_publish_remote(args.project, config, projection, args.tag)
```

- [x] **Step 9: 删除旧 CLI（命令行界面）参数**

In `build_parser()`, delete these lines:

```python
project.add_argument("--vars-file", type=Path, required=True, help="变量 JSON 文件。")
preflight.add_argument("--github-vars-file", type=Path, help="GitHub Actions variables JSON 文件。")
ci_publish.add_argument("--vars-file", type=Path, required=True, help="变量 JSON 文件。")
```

- [x] **Step 10: 运行脚本测试**

Run:

```bash
python -m pytest tests/test_release_flow_cli.py -q
```

Expected: FAIL（失败） only on projection（投影） templates/current workflow（当前工作流） and spec（规格） related assertions if script behavior is fixed; fix any direct script failures before moving on.

## Task 3: 更新 projection（投影）和 workflow（工作流）文件

**Files:**
- Modify: `plugins/release-flow/skills/release-flow/assets/templates/release-flow/projection.yaml`
- Modify: `.release-flow/projection.yaml`
- Modify: `plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml`
- Modify: `.github/workflows/release.yml`

- [x] **Step 1: 删除 projection（投影）里的六个 GitHub Variables（GitHub 变量）**

In both projection（投影） files:

```yaml
variables: {}
```

Remove `identity.releaseFlowPlugin`.

- [x] **Step 2: 把 transform（转换）值改成 identity（身份）引用**

In both projection（投影） files:

```yaml
transforms:
  - path: .agents/plugins/marketplace.json
    type: json-env
    set:
      /name: identity.codex.marketplaceName
      /interface/displayName: identity.codex.displayName
  - path: .claude-plugin/marketplace.json
    type: json-env
    set:
      /name: identity.claude.marketplaceName
      /owner/name: identity.claude.ownerName
```

- [x] **Step 3: 删除 workflow（工作流）外部插件 checkout（检出）和变量文件**

In both workflow（工作流） files, delete the `Checkout release-flow plugin` step and delete the `Write release variables` step.

- [x] **Step 4: 直接运行 source repo（源仓库）里的脚本**

In both workflow（工作流） files, use this command path for release-init（发布初始化） and ci-publish（持续集成发布）:

```yaml
python source/plugins/release-flow/skills/release-flow/scripts/release_flow.py
```

In ci-publish（持续集成发布）, remove:

```yaml
--vars-file release-vars.json
```

- [x] **Step 5: 运行 release-flow（发布流程）测试**

Run:

```bash
python -m pytest tests/test_release_flow_cli.py -q
```

Expected: PASS（通过） for release-flow（发布流程） CLI（命令行界面） and template（模板） coverage.

## Task 4: 更新 delta spec（差异规格）

**Files:**
- Modify: `openspec/changes/remove-release-flow-github-vars/specs/release-flow-plugin/spec.md`

- [x] **Step 1: 保持 spec（规格）只描述新行为**

Ensure this file says:

```markdown
- **THEN** projection MUST NOT 将 `CODEX_MARKETPLACE_CATALOG_NAME`、`CODEX_MARKETPLACE_DISPLAY_NAME`、`CLAUDE_MARKETPLACE_CATALOG_NAME`、`CLAUDE_MARKETPLACE_OWNER_NAME`、`RELEASE_FLOW_PLUGIN_REPOSITORY` 或 `RELEASE_FLOW_PLUGIN_REF` 声明为 GitHub Actions Variables
- **THEN** 系统 MUST NOT 接收 `--vars-file`
- **THEN** 系统 MUST NOT 接收 `--github-vars-file`
- **THEN** `ci-publish` MUST NOT 接收 `--vars-file`
```

- [x] **Step 2: 运行 OpenSpec（规格工具）严格校验**

Run:

```bash
openspec validate remove-release-flow-github-vars --strict
```

Expected: PASS（通过）.

## Task 5: 完整验证和提交

**Files:**
- Verify only; no extra files.

- [x] **Step 1: 运行目标测试**

Run:

```bash
python -m pytest tests/test_release_flow_cli.py -q
```

Expected: PASS（通过）.

- [x] **Step 2: 运行 OpenSpec（规格工具）严格校验**

Run:

```bash
openspec validate remove-release-flow-github-vars --strict
```

Expected: PASS（通过）.

- [x] **Step 3: 检查旧入口和旧变量已消失**

Run:

```bash
rg "vars-file|github-vars-file|release-vars.json|RELEASE_FLOW_PLUGIN_REPOSITORY|RELEASE_FLOW_PLUGIN_REF|CODEX_MARKETPLACE_CATALOG_NAME|CODEX_MARKETPLACE_DISPLAY_NAME|CLAUDE_MARKETPLACE_CATALOG_NAME|CLAUDE_MARKETPLACE_OWNER_NAME" plugins/release-flow/skills/release-flow .release-flow .github tests/test_release_flow_cli.py openspec/changes/remove-release-flow-github-vars/specs/release-flow-plugin/spec.md
```

Expected: only negative assertion strings in tests（测试） and required spec（规格） prohibition text remain; no workflow（工作流） command, projection（投影） variable declaration, parser（参数解析） argument, or runtime（运行时） requirement remains.

- [x] **Step 4: 提交**

Run:

```bash
git add tests/test_release_flow_cli.py plugins/release-flow/skills/release-flow/scripts/release_flow.py plugins/release-flow/skills/release-flow/assets/templates/release-flow/projection.yaml .release-flow/projection.yaml plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml .github/workflows/release.yml openspec/changes/remove-release-flow-github-vars/specs/release-flow-plugin/spec.md
git commit -m "移除 release-flow 非敏感 GitHub 变量"
```

## Self-Review

- Spec coverage（规格覆盖）: 覆盖旧入口删除、projection（投影）承载 marketplace（市场）身份、六个旧 GitHub Variables（GitHub 变量）不声明/不输出/不要求、workflow（工作流）不 checkout（检出）外部插件、不写 `release-vars.json`、不传 `--vars-file`，并覆盖 validate（校验）、release-init（发布初始化）、github-plan（GitHub 计划）、configure-github --dry-run（配置 GitHub 试运行）、project（投影）、preflight（预检）、ci-publish（持续集成发布）。
- Placeholder scan（占位扫描）: 无占位任务；每个代码改动步骤包含目标文件、具体行为、命令和期望结果。
- Type consistency（类型一致性）: `apply_projection(project, projection)` 是唯一投影应用入口；`json-env` set（设置）值统一为 `identity.*` 引用。
