---
change: rename-test-framework-to-build-and-verify
design-doc: docs/superpowers/specs/2026-06-25-build-and-verify-rename-design.md
base-ref: 4030d1ceb81fa6e450ef517e09d2ff391f5260b2
---

# Build and Verify Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 `test-framework`（测试框架）按 rename（改名）迁移为 `build-and-verify`（构建与验证），并保留原有 build（构建检查）和 verify（验证）逻辑。

**Architecture:** 采用机械 rename（改名）：移动目录和文件，更新字符串、路径、配置目录、测试断言和文档引用。不得重构或重写 runner（运行器）逻辑；任何代码修改都应是命名、路径和错误消息同步。

**Tech Stack:** Python（Python 语言）、pytest（Python 测试运行器）、OpenSpec（开放规格）、Comet（双星流程）、PR Flow（拉取请求流程）、Release Flow（发布流程）。

---

## File Structure

- Rename: `plugins/test-framework/` -> `plugins/build-and-verify/`
- Rename: `plugins/build-and-verify/skills/test-framework/` -> `plugins/build-and-verify/skills/build-and-verify/`
- Rename: `plugins/build-and-verify/skills/build-and-verify/scripts/test_framework.py` -> `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py`
- Rename: `plugins/build-and-verify/skills/build-and-verify/scripts/test_framework_runner.py` -> `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py`
- Rename: `.test-framework/` -> `.build-and-verify/`
- Delete: `pyproject.toml`
- Modify: `.comet.yaml`
- Modify: `.pr-flow/config.yaml`
- Modify: `.agents/plugins/marketplace.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `.release-flow/projection.yaml`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Modify: `openspec/specs/test-framework-plugin/spec.md`
- Modify: `openspec/specs/local-verification-modes/spec.md`
- Modify: `openspec/specs/local-plugin-build-checks/spec.md`
- Modify: `openspec/specs/full-verification-runtime/spec.md`
- Modify: `openspec/specs/pr-flow-plugin/spec.md`
- Rename/Modify: `tests/test_test_framework_plugin.py` -> `tests/test_build_and_verify_plugin.py`
- Modify: `tests/test_local_plugin_build_checks.py`
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `tests/test_pr_flow_plugin_package.py`
- Modify: `tests/test_release_flow_cli.py`
- Modify: `tests/test_release_flow_plugin_package.py`
- Modify: `tests/test_agent_guard_plugin_package.py`
- Modify: `.build-and-verify/config.json`

## 1. Test First: Public Plugin Surface

**Files:**
- Modify: `tests/test_test_framework_plugin.py`
- Modify: `tests/test_agent_guard_plugin_package.py`
- Modify: `tests/test_release_flow_cli.py`
- Modify: `tests/test_release_flow_plugin_package.py`

- [ ] **Step 1: Rename the plugin test file and constants**

Rename `tests/test_test_framework_plugin.py` to `tests/test_build_and_verify_plugin.py`. Change its top-level constants only:

```python
PLUGIN_ROOT = REPO_ROOT / "plugins" / "build-and-verify"
BUILD_AND_VERIFY_SCRIPT = (
    PLUGIN_ROOT / "skills" / "build-and-verify" / "scripts" / "build_and_verify.py"
)
PLUGIN_NAME = "build-and-verify"
```

Do not change runner（运行器） behavior assertions yet beyond names and paths.

- [ ] **Step 2: Update manifest and Skill expectations**

In the renamed test file, update assertions so they expect:

```python
assert codex_manifest["name"] == "build-and-verify"
assert claude_manifest["name"] == "build-and-verify"
assert script_path == skill_root / "build-and-verify" / "scripts" / "build_and_verify.py"
assert "scripts/build_and_verify.py init" in skill_text
assert "scripts/build_and_verify.py build" in skill_text
assert "scripts/build_and_verify.py verify" in skill_text
```

- [ ] **Step 3: Update marketplace and projection expectations**

Update test expectations from:

```python
"source": "./plugins/test-framework"
"test-framework"
```

to:

```python
"source": "./plugins/build-and-verify"
"build-and-verify"
```

Keep all other marketplace（市场目录） and release projection（发布投影） behavior unchanged.

- [ ] **Step 4: Run the public surface tests and confirm failure**

Run:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py tests/test_agent_guard_plugin_package.py tests/test_release_flow_cli.py tests/test_release_flow_plugin_package.py
```

Expected before implementation: FAIL because plugin files and registry entries still use `test-framework`（测试框架）.

## 2. Mechanical Rename Implementation

**Files:**
- Rename: `plugins/test-framework/`
- Modify: new files under `plugins/build-and-verify/`
- Rename: `.test-framework/`

- [ ] **Step 1: Move plugin and Skill directories**

Use `git mv`:

```powershell
git mv plugins/test-framework plugins/build-and-verify
git mv plugins/build-and-verify/skills/test-framework plugins/build-and-verify/skills/build-and-verify
```

- [ ] **Step 2: Move script files**

Use `git mv`:

```powershell
git mv plugins/build-and-verify/skills/build-and-verify/scripts/test_framework.py plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py
git mv plugins/build-and-verify/skills/build-and-verify/scripts/test_framework_runner.py plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py
```

- [ ] **Step 3: Move template and repository config directories**

Use `git mv`:

```powershell
git mv plugins/build-and-verify/skills/build-and-verify/assets/templates/test-framework plugins/build-and-verify/skills/build-and-verify/assets/templates/build-and-verify
git mv .test-framework .build-and-verify
```

- [ ] **Step 4: Update the entrypoint names without changing logic**

In `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py`, only update names and paths:

```python
"""Build and Verify Plugin（构建与验证插件）命令入口。"""
runner_path = Path(__file__).resolve().with_name("build_and_verify_runner.py")
spec = importlib.util.spec_from_file_location("build_and_verify_runner", runner_path)
project / ".build-and-verify" / "config.json"
project / ".build-and-verify" / ".gitignore"
_templates_root() / "build-and-verify" / "config.json"
_templates_root() / "build-and-verify" / "gitignore"
project / ".build-and-verify" / "cache"
argparse.ArgumentParser(prog="build_and_verify.py")
```

Do not change `init`（初始化）、`build`（构建检查） or `verify`（验证） control flow.

- [ ] **Step 5: Update runner config and cache paths**

In `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py`, replace only path/error strings:

```python
project / ".build-and-verify" / "config.json"
"missing_config: .build-and-verify/config.json"
"invalid_config: .build-and-verify/config.json: ..."
relative == ".build-and-verify/cache"
relative.startswith(".build-and-verify/cache/")
project / ".build-and-verify" / "cache" / f"{key}.json"
```

Do not change selection, cache, timeout, parallel, or subprocess execution logic.

- [ ] **Step 6: Update Skill text and manifests**

Update:

```text
plugins/build-and-verify/.codex-plugin/plugin.json
plugins/build-and-verify/.claude-plugin/plugin.json
plugins/build-and-verify/skills/build-and-verify/SKILL.md
```

Expected manifest values:

```json
{
  "name": "build-and-verify",
  "description": "Build and Verify Plugin（构建与验证插件）"
}
```

Skill（技能） frontmatter:

```yaml
---
name: build-and-verify
description: 本仓库 build（构建检查）和 verify（验证）统一入口；verify（验证）默认 fast（快速），--full（完整）只允许 hotfix（热修复）直推和 PR CI（拉取请求持续集成）
---
```

- [ ] **Step 7: Run public surface tests again**

Run:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py tests/test_agent_guard_plugin_package.py tests/test_release_flow_cli.py tests/test_release_flow_plugin_package.py
```

Expected: PASS or only fail on repository integration references that Task 3 will update.

## 3. Repository Configuration and Integration References

**Files:**
- Modify: `.comet.yaml`
- Modify: `.pr-flow/config.yaml`
- Modify: `.agents/plugins/marketplace.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `.release-flow/projection.yaml`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Modify: `.build-and-verify/config.json`
- Delete: `pyproject.toml`

- [ ] **Step 1: Update Comet commands**

Update `.comet.yaml`:

```yaml
build_command: python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py build --project .
verify_command: python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .
```

The `verify_command` MUST NOT include `--full`.

- [ ] **Step 2: Update PR Flow hotfix command**

Update `.pr-flow/config.yaml`:

```yaml
hotfix:
  verifyCommand: python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full
```

Do not add `--full` to complete（收尾） or tweak（小改） paths.

- [ ] **Step 3: Update marketplace entries**

Replace active entries:

```json
{
  "name": "build-and-verify",
  "source": "./plugins/build-and-verify",
  "description": "Build and Verify Plugin（构建与验证插件）"
}
```

For Codex（Codex 版本） marketplace, keep existing policy and category values.

- [ ] **Step 4: Update release projection**

Update `.release-flow/projection.yaml` generator plugin list:

```yaml
plugins:
  - agent-guard
  - release-flow
  - cross-agent-review
  - pr-flow
  - build-and-verify
```

Update `plugins/release-flow/skills/release-flow/scripts/release_flow.py` built-in projection defaults from `test-framework`（测试框架） to `build-and-verify`（构建与验证）.

- [ ] **Step 5: Update PR Flow script defaults**

Update `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py` default hotfix verify command to:

```python
"verifyCommand": "python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full"
```

- [ ] **Step 6: Delete root Python test config**

Delete:

```powershell
Remove-Item -LiteralPath pyproject.toml
```

Then update `.build-and-verify/config.json` pytest（Python 测试运行器） commands so each command explicitly keeps quiet output:

```json
"command": "python -m pytest -q -n 8 -p no:cacheprovider tests/test_local_plugin_build_checks.py"
```

Apply the same `-q`（安静输出） addition to every pytest（Python 测试运行器） command that relied on root `pyproject.toml`.

- [ ] **Step 7: Run repository integration tests**

Run:

```powershell
python -m pytest -q tests/test_local_plugin_build_checks.py tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py tests/test_release_flow_cli.py tests/test_release_flow_plugin_package.py
```

Expected: FAIL only where tests still expect old names; Task 4 updates those.

## 4. Test Rename and Mode Boundary Updates

**Files:**
- Modify: `tests/test_build_and_verify_plugin.py`
- Modify: `tests/test_local_plugin_build_checks.py`
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `tests/test_pr_flow_plugin_package.py`
- Modify: `tests/test_release_flow_cli.py`
- Modify: `tests/test_release_flow_plugin_package.py`

- [ ] **Step 1: Update config path assertions**

Replace active test expectations:

```python
Path(".test-framework/config.json")
Path(".test-framework/.gitignore")
".test-framework/cache"
"missing_config: .test-framework/config.json"
"invalid_config: .test-framework/config.json"
```

with:

```python
Path(".build-and-verify/config.json")
Path(".build-and-verify/.gitignore")
".build-and-verify/cache"
"missing_config: .build-and-verify/config.json"
"invalid_config: .build-and-verify/config.json"
```

- [ ] **Step 2: Update command assertions**

Replace active command assertions with:

```python
"python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py build --project ."
"python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project ."
"python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full"
```

- [ ] **Step 3: Add old-entrypoint rejection assertions**

In `tests/test_local_plugin_build_checks.py`, keep or add assertions that active command/config files do not contain:

```python
for forbidden in [
    "scripts/check.py",
    "plugins/test-framework/",
    ".test-framework/",
    "test_framework.py",
    "pyproject.toml",
]:
    assert forbidden not in text
```

Scope this assertion to active files only, not `openspec/changes/archive/` history.

- [ ] **Step 4: Preserve full-mode boundary tests**

In `tests/test_pr_flow_cli.py`, assert:

```python
assert hotfix_command == "python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full"
assert "--full" not in comet_verify_command
```

Also keep tests that complete（收尾） and tweak（小改） paths do not infer or run full verify（完整验证）.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest -q tests/test_build_and_verify_plugin.py tests/test_local_plugin_build_checks.py tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py tests/test_release_flow_cli.py tests/test_release_flow_plugin_package.py tests/test_agent_guard_plugin_package.py
```

Expected: PASS.

## 5. OpenSpec and Current Documentation

**Files:**
- Modify: `openspec/specs/test-framework-plugin/spec.md`
- Modify: `openspec/specs/local-verification-modes/spec.md`
- Modify: `openspec/specs/local-plugin-build-checks/spec.md`
- Modify: `openspec/specs/full-verification-runtime/spec.md`
- Modify: `openspec/specs/pr-flow-plugin/spec.md`

- [ ] **Step 1: Sync main specs with delta wording**

Update main OpenSpec（开放规格） specs so active requirements use `build-and-verify`（构建与验证） wording and paths. Keep the capability folder `test-framework-plugin` until archive（归档） applies the rename semantics.

- [ ] **Step 2: Do not edit archive history**

Do not rewrite files under:

```text
openspec/changes/archive/
docs/superpowers/specs/2026-06-23-test-framework-plugin-design.md
docs/superpowers/plans/2026-06-23-test-framework-plugin.md
```

Archive（归档） history may keep old names.

- [ ] **Step 3: Validate OpenSpec**

Run:

```powershell
openspec validate rename-test-framework-to-build-and-verify --strict
openspec validate --all --strict --no-interactive
```

Expected: PASS.

## 6. Final Verification

**Files:**
- Modify: `openspec/changes/rename-test-framework-to-build-and-verify/tasks.md`

- [ ] **Step 1: Run build command**

Run:

```powershell
python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py build --project .
```

Expected: build checks passed（构建检查通过）.

- [ ] **Step 2: Run default fast verify**

Run:

```powershell
python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project .
```

Expected: default fast verify（快速验证） runs selected checks and does not run all checks unconditionally.

- [ ] **Step 3: Run full verify**

Run:

```powershell
python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full
```

Expected: full verify（完整验证） runs all configured checks and remains under the full-verification runtime target.

- [ ] **Step 4: Search for active old references**

Run:

```powershell
rg -n "plugins/test-framework|\\.test-framework|test_framework\\.py|test-framework|pyproject\\.toml" . --glob "!openspec/changes/archive/**" --glob "!docs/superpowers/specs/2026-06-23-test-framework-plugin-design.md" --glob "!docs/superpowers/plans/2026-06-23-test-framework-plugin.md" --glob "!**/__pycache__/**" --glob "!**/.git/**"
```

Expected: only current change discussion or intentionally retained capability folder names where OpenSpec（开放规格） rename semantics require them.

- [ ] **Step 5: Mark OpenSpec tasks complete**

After implementation and verification pass, update:

```text
openspec/changes/rename-test-framework-to-build-and-verify/tasks.md
```

Check off completed tasks without changing their meaning.

- [ ] **Step 6: Commit**

Run:

```powershell
git add -A
git commit -m "重命名构建与验证入口"
```

Expected: commit succeeds with only rename（改名）, reference update, config cleanup, test update, and OpenSpec（开放规格） files.

## Self-Review

- Spec coverage: Tasks cover rename（改名）, no refactor（重构）, config directory migration, root `pyproject.toml`（Python 测试配置） removal, fast/full（快速/完整） verification boundary, PR Flow（拉取请求流程） hotfix（热修复） exception, and PR CI（拉取请求持续集成） boundary.
- Placeholder scan: No placeholder tasks remain.
- Type consistency: New names are consistently `build-and-verify`（构建与验证）, `.build-and-verify`, `build_and_verify.py`, and `build_and_verify_runner.py`.
