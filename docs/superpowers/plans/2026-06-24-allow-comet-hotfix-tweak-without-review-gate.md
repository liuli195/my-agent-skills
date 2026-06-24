---
change: allow-comet-hotfix-tweak-without-review-gate
design-doc: docs/superpowers/specs/2026-06-24-allow-comet-hotfix-tweak-without-review-gate-design.md
base-ref: e6b93beacaa990463ec267c3aa96f27b9ee940ad
---

# Allow Comet Hotfix/Tweak Without Review Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `comet-review-gate`（Comet 审查门禁）在 `hotfix`（热修复）和 `tweak`（小改）workflow（流程）中跳过 cross-agent-review（跨代理审查）要求，同时保持 `full`（完整流程）继续阻断。

**Architecture:** 在 Global Command Guard（全局命令守卫）中增加通用 `skip_when`（跳过条件）机制，运行时只读取配置声明的 YAML（配置文件）字段，不硬编码 Comet（彗星流程）业务规则。内置 `comet-review-gate`（Comet 审查门禁）模板通过 `skip_when`（跳过条件）读取 `.comet.yaml`（Comet 状态文件）的 `workflow`（流程类型）字段。

**Tech Stack:** Python 3、PyYAML、pytest（测试）、OpenSpec（开放规格）、Agent Guard Runtime（代理守卫运行时）。

---

## File Structure

- Modify: `plugins/agent-guard/scripts/guard_runtime/global_command_guards.py`
  - 增加 `skip_when`（跳过条件）评估。
  - 在 evidence（证据）检查前跳过命中条件的 guard（守卫）。
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py`
  - 校验 `skip_when`（跳过条件）的 YAML（配置文件）结构、路径模板字段、读取字段和值列表。
- Modify: `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/global-command-guards.yaml`
  - 为内置模板增加 `hotfix`（热修复）和 `tweak`（小改）跳过条件。
- Modify: `plugins/agent-guard/assets/templates/guard-profile/comet-review-gate/global-command-guards.yaml`
  - 保持插件级模板镜像一致。
- Modify: `tests/test_agent_guard_runtime_router.py`
  - 覆盖运行时跳过条件、full（完整流程）阻断、hotfix/tweak（热修复/小改）放行。
- Modify: `tests/test_validate_guard_profile.py`
  - 覆盖合法 `skip_when`（跳过条件）配置校验。
- Modify: `C:\Users\liuli\.agents\guards\comet-review-gate\global-command-guards.yaml`
  - 同步用户级 Guard Profile（守卫画像）配置，让当前环境立即生效。

## Task 1: Runtime Skip Condition

**Files:**
- Modify: `plugins/agent-guard/scripts/guard_runtime/global_command_guards.py`
- Modify: `tests/test_agent_guard_runtime_router.py`

- [x] **Step 1: Write failing runtime test**

Add `test_global_command_guard_skips_when_yaml_condition_matches` to `tests/test_agent_guard_runtime_router.py`.

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py::test_global_command_guard_skips_when_yaml_condition_matches -q
```

Expected before implementation: FAIL because the guard still checks `review-pass.json`.

- [x] **Step 2: Implement `skip_when` evaluation**

Add `_skip_when_matches(...)` to `global_command_guards.py`. It reads `skip_when`（跳过条件） entries, renders the YAML（配置文件） path with existing context values, resolves it through the existing relative path resolver, reads the configured `field`, and returns true when the value is in the configured `in` list.

- [x] **Step 3: Skip evidence evaluation when the condition matches**

Call `_skip_when_matches(...)` after required captures（必需捕获） are available and before appending the guard to `matched_guard_ids`. A skipped guard does not produce deny（拒绝） and does not appear as matched.

- [x] **Step 4: Verify runtime behavior**

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py::test_global_command_guard_skips_when_yaml_condition_matches -q
```

Expected after implementation: PASS.

## Task 2: Validator Support

**Files:**
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py`
- Modify: `tests/test_validate_guard_profile.py`

- [x] **Step 1: Write validator test**

Add `test_global_command_guard_valid_skip_when_yaml_config_passes` to `tests/test_validate_guard_profile.py`.

Run:

```powershell
python -m pytest tests/test_validate_guard_profile.py::test_global_command_guard_valid_skip_when_yaml_config_passes -q
```

Expected after validator support: PASS.

- [x] **Step 2: Implement validator checks**

Add `validate_global_command_guard_skip_when(...)` and call it from `validate_global_command_guards(...)`. Validate list shape, YAML（配置文件） condition mapping, non-empty `path` and `field`, non-empty `in` list, and path template fields.

- [x] **Step 3: Verify validator behavior**

Run:

```powershell
python -m pytest tests/test_validate_guard_profile.py::test_global_command_guard_valid_skip_when_yaml_config_passes -q
```

Expected: PASS.

## Task 3: Comet Review Gate Template

**Files:**
- Modify: `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/global-command-guards.yaml`
- Modify: `plugins/agent-guard/assets/templates/guard-profile/comet-review-gate/global-command-guards.yaml`
- Modify: `tests/test_agent_guard_runtime_router.py`

- [x] **Step 1: Add template tests**

Add:

- `test_comet_review_gate_template_blocks_full_workflow_without_marker`
- `test_comet_review_gate_template_skips_hotfix_and_tweak_workflows`

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py::test_comet_review_gate_template_blocks_full_workflow_without_marker tests/test_agent_guard_runtime_router.py::test_comet_review_gate_template_skips_hotfix_and_tweak_workflows -q
```

Expected after template update: PASS.

- [x] **Step 2: Update both template copies**

Add:

```yaml
skip_when:
  - yaml:
      path: openspec/changes/{change}/.comet.yaml
      field: workflow
      in:
        - hotfix
        - tweak
```

- [x] **Step 3: Verify template behavior**

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py::test_comet_review_gate_template_blocks_full_workflow_without_marker tests/test_agent_guard_runtime_router.py::test_comet_review_gate_template_skips_hotfix_and_tweak_workflows -q
```

Expected: PASS.

## Task 4: User-Level Profile Sync and Full Verification

**Files:**
- Modify: `C:\Users\liuli\.agents\guards\comet-review-gate\global-command-guards.yaml`
- Modify: `openspec/changes/allow-comet-hotfix-tweak-without-review-gate/tasks.md`

- [x] **Step 1: Sync user-level profile**

Apply the same `skip_when`（跳过条件） block to the user-level Guard Profile（守卫画像） at `C:\Users\liuli\.agents\guards\comet-review-gate\global-command-guards.yaml`.

- [x] **Step 2: Validate user-level profile**

Run:

```powershell
python plugins\agent-guard\skills\agent-guard\scripts\validate_guard_profile.py 'C:\Users\liuli\.agents\guards\comet-review-gate'
```

Expected: PASS with `通过：Guard Profile（守卫画像）校验`.

- [x] **Step 3: Verify real user-level behavior**

Use a temporary Git repository and the user-level Guard Profile（守卫画像） to check:

- `workflow: full` returns deny（拒绝）。
- `workflow: hotfix` returns allow（允许）。
- `workflow: tweak` returns allow（允许）。

- [x] **Step 4: Run focused regression**

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py tests/test_validate_guard_profile.py tests/test_agent_guard_plugin_package.py tests/test_agent_guard_plugin_runtime_e2e.py -q
```

Expected: PASS.

- [x] **Step 5: Run full regression**

Run:

```powershell
python -m pytest -q
```

Expected: PASS.

- [x] **Step 6: Run OpenSpec validation**

Run:

```powershell
openspec validate allow-comet-hotfix-tweak-without-review-gate --strict
```

Expected: `Change 'allow-comet-hotfix-tweak-without-review-gate' is valid`.

## Self-Review

- Spec coverage: covered by runtime support, validator support, template behavior, user-level sync, and OpenSpec（开放规格） validation.
- Placeholder scan: no placeholder text remains.
- Type consistency: `skip_when`（跳过条件） uses `yaml.path`, `yaml.field`, and `yaml.in` consistently across runtime, validator, templates, and tests.
