---
change: add-comet-agent-review-gate
design-doc: docs/superpowers/specs/2026-06-20-comet-agent-review-gate-design.md
base-ref: db0459da3e5a7f63c5de64c2779a23a3ea1a926a
archived-with: 2026-06-20-add-comet-agent-review-gate
---

# Comet Agent Review Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-level Agent Guard Global Command Guard profile for Comet build-to-verify review gating, backed by `artifacts.yaml` and cross-agent-review pass markers.

**Architecture:** Keep Comet, Agent Guard, and cross-agent-review decoupled. The user-level guard profile matches `comet-guard.sh <change> build --apply`, resolves `cross_agent_review_pass` through `artifacts.yaml`, and denies build completion until `review-pass.json` validates. Deny `reason` / `next` / `suggestion` can be configured in the profile; Agent Guard only returns those fields and does not own the business flow. Agent Guard skill docs expose this through scenario-specific entrypoints with progressive disclosure.

**Tech Stack:** Python runtime and pytest tests, YAML guard profiles, Markdown skills/references, OpenSpec/Comet workflow files.

archived-with: 2026-06-20-add-comet-agent-review-gate
---

## Pre-Execution Gate

Current code inspection shows Global Command Guard reads only `evidence.path` in `plugins/agent-guard/scripts/guard_runtime/global_command_guards.py`, and `validate_guard_profile.py` currently requires `evidence.path` for global command guards. That means the Comet gate cannot be completed by configuration alone.

Before editing runtime or validator code, present this reason and the minimal modification set to the user:

- Add `artifact` / `artifact_id` support to Global Command Guard evidence evaluation.
- Validate that referenced artifact IDs exist in the same Guard Profile `artifacts.yaml`.
- Resolve relative artifact paths from the project root for project commands, including user-level profiles.
- Keep legacy `evidence.path` compatible for existing configs.

Do not edit runtime code until the user confirms this non-configuration change.

## File Map

- Modify `plugins/agent-guard/scripts/guard_runtime/global_command_guards.py`: add artifact reference loading and path resolution for Global Command Guard.
- Modify `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py`: allow global command guards to use `artifact` / `artifact_id`, validate references, and keep `evidence.path` compatibility.
- Create `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/`: skill-visible Comet review gate Guard Profile sample. It is user-level by target/install semantics, not by directory name.
- Create `plugins/agent-guard/assets/templates/guard-profile/comet-review-gate/`: mirrored plugin package sample.
- Modify `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py`: include the new template files in package validation.
- Modify Agent Guard entrypoint docs:
  - `plugins/agent-guard/skills/agent-guard/SKILL.md`
  - `plugins/agent-guard/skills/agent-guard-install/SKILL.md`
  - `plugins/agent-guard/skills/agent-guard-init/SKILL.md`
  - `plugins/agent-guard/skills/agent-guard-update/SKILL.md`
  - `plugins/agent-guard/skills/agent-guard-run/SKILL.md`
- Modify scenario references:
  - `plugins/agent-guard/skills/agent-guard-install/references/profile-draft.md`
  - `plugins/agent-guard/skills/agent-guard-init/references/init-flow.md`
  - `plugins/agent-guard/skills/agent-guard-update/references/profile-sync.md`
  - `plugins/agent-guard/skills/agent-guard-run/references/events.md`
  - `plugins/agent-guard/skills/agent-guard/references/template-index.md`
- Modify tests:
  - `tests/test_validate_guard_profile.py`
  - `tests/test_agent_guard_runtime_router.py`
  - `tests/test_agent_guard_skill_entrypoints.py`
  - `tests/test_agent_guard_plugin_package.py`
- Modify `openspec/changes/add-comet-agent-review-gate/tasks.md` as tasks complete.

archived-with: 2026-06-20-add-comet-agent-review-gate
---

### Task 1: Add Comet Review Gate Profile Template

**Files:**
- Create: `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/GUARD-MANIFEST.yaml`
- Create: `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/global-command-guards.yaml`
- Create: `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/artifacts.yaml`
- Create: `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/validation-plan.md`
- Create mirrored copies under `plugins/agent-guard/assets/templates/guard-profile/comet-review-gate/`
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py`
- Test: `tests/test_validate_guard_profile.py`
- Test: `tests/test_agent_guard_plugin_package.py`

- [x] **Step 1: Add failing template validation tests**

Add tests that assert both skill and plugin template copies exist and are byte-identical:

```python
def test_comet_review_gate_user_template_is_mirrored() -> None:
    skill_template = PLUGIN_SKILL / "assets" / "templates" / "guard-profile" / "comet-review-gate"
    plugin_template = REPO_ROOT / "plugins" / "agent-guard" / "assets" / "templates" / "guard-profile" / "comet-review-gate"

    for name in ["GUARD-MANIFEST.yaml", "global-command-guards.yaml", "artifacts.yaml", "validation-plan.md"]:
        assert (skill_template / name).exists()
        assert (plugin_template / name).exists()
        assert (skill_template / name).read_text(encoding="utf-8") == (plugin_template / name).read_text(encoding="utf-8")
```

Add a package test assertion:

```python
def test_plugin_package_contains_comet_review_gate_template() -> None:
    template = PLUGIN_ROOT / "skills" / "agent-guard" / "assets" / "templates" / "guard-profile" / "comet-review-gate"
    for name in ["GUARD-MANIFEST.yaml", "global-command-guards.yaml", "artifacts.yaml", "validation-plan.md"]:
        assert (template / name).exists()
```

- [x] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest tests/test_validate_guard_profile.py::test_comet_review_gate_user_template_is_mirrored tests/test_agent_guard_plugin_package.py::test_plugin_package_contains_comet_review_gate_template -q
```

Expected: both tests fail because the template files do not exist.

- [x] **Step 3: Create the user-level template files**

Create `GUARD-MANIFEST.yaml` using the repo's Guard Profile manifest shape:

```yaml
schema_version: guard-profile/v1
runtime_api_version: agent-guard-runtime/v1
guard_profile_id: comet-review-gate
name: Comet Review Gate Guard Profile（样例）
description: 拦截 Comet build 命令，校验 cross-agent-review pass marker。
source:
  kind: built-in-comet-review-gate
  status: template
files:
  target_model: target-model.yaml
  state_machine: state-machine.yaml
  guard_points: guard-points.yaml
  artifacts: artifacts.yaml
  brief_template: brief-template.md
  validation_plan: validation-plan.md
```

Create `artifacts.yaml`:

```yaml
artifacts:
  - id: cross_agent_review_pass
    type: json
    owner: external
    path: .local/cross-agent-review/{change}/{git_head}/review-pass.json
    reuse_policy: deny
    description: cross-agent-review 通过时生成的 pass marker。
```

Create `global-command-guards.yaml`:

```yaml
global_command_guards:
  - id: comet_build_requires_cross_agent_review
    description: Comet build 完成进入 verify 前必须有 cross-agent-review pass marker。
    tool: Bash
    match:
      command_patterns:
        - '(^|[\\s''"])(?:[^\\s''"]*/)?comet-guard\\.sh[''"]?\\s+(?P<change>[A-Za-z0-9._-]+)\\s+build\\s+--apply(?:\\s|$)'
        - '\\$COMET_GUARD[''"]?\\s+(?P<change>[A-Za-z0-9._-]+)\\s+build\\s+--apply(?:\\s|$)'
      required_captures:
        - change
    evidence:
      artifact: cross_agent_review_pass
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
      suggestion: 生成当前 change 和当前 HEAD 对应的 cross-agent-review pass marker 后重试 build completion。
```

Create `validation-plan.md` following the existing Guard Profile template convention. User-level installation is expressed by the profile target/configuration and documented install path, not by placing the source template under a `user-guard-profile` directory. The validation plan should check that the Comet review gate files exist, `artifacts.yaml` registers `cross_agent_review_pass`, and `global-command-guards.yaml` references that artifact instead of legacy `evidence.path`.

```markdown
# Validation Plan（验证计划）

- 校验所有必需 Guard Profile（守卫画像）文件存在。
- 校验 `artifacts.yaml` 注册 `cross_agent_review_pass`。
- 校验 `global-command-guards.yaml` 使用 `artifact: cross_agent_review_pass`。
- 校验命令匹配覆盖 direct、path-qualified 和 `$COMET_GUARD` 调用。
- 校验禁止项：不新增 wrapper、不修改 cross-agent-review 输出目录、不复制 pass marker、不使用 `verify --apply` 作为主拦截点。
```

- [x] **Step 4: Mirror the template**

Copy the four files to:

```text
plugins/agent-guard/assets/templates/guard-profile/comet-review-gate/
```

Keep content identical to the skill-visible template.

- [x] **Step 5: Include template files in package validation**

In `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py`, append these items to `PACKAGE_ITEMS`:

```python
"skills/agent-guard/assets/templates/guard-profile/comet-review-gate",
"assets/templates/guard-profile/comet-review-gate",
```

- [x] **Step 6: Run template tests**

Run:

```bash
python -m pytest tests/test_validate_guard_profile.py::test_comet_review_gate_user_template_is_mirrored tests/test_agent_guard_plugin_package.py::test_plugin_package_contains_comet_review_gate_template -q
```

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate plugins/agent-guard/assets/templates/guard-profile/comet-review-gate plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py tests/test_validate_guard_profile.py tests/test_agent_guard_plugin_package.py
git commit -m "feat: add comet review gate guard template"
```

archived-with: 2026-06-20-add-comet-agent-review-gate
---

### Task 2: Add Artifact Reference Support To Global Command Guard

**Files:**
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py`
- Modify: `plugins/agent-guard/scripts/guard_runtime/global_command_guards.py`
- Test: `tests/test_validate_guard_profile.py`
- Test: `tests/test_agent_guard_runtime_router.py`

- [x] **Step 1: Stop for user review before code edits**

Before editing the runtime files, tell the user:

```text
纯配置不能完成这一点：Global Command Guard 当前只读取 evidence.path，validator 也要求 evidence.path。要使用 artifacts.yaml，必须最小修改 validate_guard_profile.py 和 global_command_guards.py；legacy evidence.path 保持兼容。
```

Proceed only after the user confirms.

- [x] **Step 2: Add failing validator tests**

Add tests:

```python
def test_global_command_guard_accepts_artifact_reference(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "artifacts.yaml").write_text(
        """
artifacts:
  - id: cross_agent_review_pass
    type: json
    path: .local/cross-agent-review/{change}/{git_head}/review-pass.json
""".lstrip(),
        encoding="utf-8",
    )
    write_global_command_guards(
        profile,
        """
global_command_guards:
  - id: comet_build_requires_review
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard\\.sh (?P<change>[A-Za-z0-9._-]+) build --apply'
      required_captures:
        - change
    evidence:
      artifact: cross_agent_review_pass
    checks:
      - field: status
        predicate: equals
        value: pass
""",
    )

    result = run_validator(profile)

    assert result.returncode == 0, result.stdout + result.stderr
```

```python
def test_global_command_guard_rejects_unknown_artifact_reference(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    write_global_command_guards(
        profile,
        """
global_command_guards:
  - id: comet_build_requires_review
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard\\.sh (?P<change>[A-Za-z0-9._-]+) build --apply'
    evidence:
      artifact: missing_review_pass
    checks:
      - field: status
        predicate: exists
""",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "missing_review_pass" in result.stdout
    assert "artifacts" in result.stdout
```

- [x] **Step 3: Add failing runtime tests**

Add tests near existing global command guard tests:

```python
def test_global_command_guard_reads_registered_artifact_from_project_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    subprocess.run(["git", "init"], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    (project / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
    profile = user_home / ".agents" / "guards" / "comet-review-gate"
    profile.mkdir(parents=True)
    profile.joinpath("artifacts.yaml").write_text(
        """
artifacts:
  - id: cross_agent_review_pass
    type: json
    path: .local/cross-agent-review/{change}/{git_head}/review-pass.json
""".lstrip(),
        encoding="utf-8",
    )
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: comet_build_requires_review
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard\\.sh (?P<change>[A-Za-z0-9._-]+) build --apply'
    evidence:
      artifact: cross_agent_review_pass
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
""",
    )
    pass_marker = project / ".local" / "cross-agent-review" / "add-comet-agent-review-gate" / head / "review-pass.json"
    pass_marker.parent.mkdir(parents=True)
    pass_marker.write_text(json.dumps({"status": "pass", "change": "add-comet-agent-review-gate", "head_ref": head}, ensure_ascii=False), encoding="utf-8")

    result = pre_tool(project, user_home, "comet-guard.sh add-comet-agent-review-gate build --apply")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
    assert str(payload["audit_path"]).startswith(str(project / ".local" / "guard" / "audit"))
    assert not (user_home / ".agents" / "guard").exists()
```

```python
def test_global_command_guard_denies_missing_registered_artifact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = user_home / ".agents" / "guards" / "comet-review-gate"
    profile.mkdir(parents=True)
    profile.joinpath("artifacts.yaml").write_text(
        """
artifacts:
  - id: cross_agent_review_pass
    type: json
    path: .local/cross-agent-review/{change}/{git_head}/review-pass.json
""".lstrip(),
        encoding="utf-8",
    )
    write_global_command_guard_yaml(
        profile,
        """
global_command_guards:
  - id: comet_build_requires_review
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard\\.sh (?P<change>[A-Za-z0-9._-]+) build --apply'
    evidence:
      artifact: cross_agent_review_pass
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: comet_cross_agent_review_required
      next: produce_cross_agent_review_pass_marker
      suggestion: produce review pass marker
""",
    )

    result = pre_tool(project, user_home, "comet-guard.sh add-comet-agent-review-gate build --apply")

    assert result.returncode == 1
    payload = body(result)
    assert payload["reason"] == "comet_cross_agent_review_required"
    assert payload["next"] == "produce_cross_agent_review_pass_marker"
    assert payload["failing_guards"][0]["failure_reason"] == "evidence_missing"
    assert "cross_agent_review_pass" in payload["failing_guards"][0]["artifact"]
```

- [x] **Step 4: Run new tests to verify failure**

Run:

```bash
python -m pytest tests/test_validate_guard_profile.py::test_global_command_guard_accepts_artifact_reference tests/test_validate_guard_profile.py::test_global_command_guard_rejects_unknown_artifact_reference tests/test_agent_guard_runtime_router.py::test_global_command_guard_reads_registered_artifact_from_project_root tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_missing_registered_artifact -q
```

Expected: FAIL because artifact references are not implemented.

- [x] **Step 5: Implement validator support**

In `validate_guard_profile.py`, update `validate_global_command_guards` to collect artifact IDs:

```python
artifact_ids = {
    item.get("id")
    for item in (configs["artifacts"].get("artifacts", []) if isinstance(configs.get("artifacts"), dict) else [])
    if isinstance(item, dict) and isinstance(item.get("id"), str)
}
```

Pass `artifact_ids` into global command guard validation. Accept either:

```yaml
evidence:
  artifact: cross_agent_review_pass
```

or:

```yaml
evidence:
  path: .local/guard/evidence/...
```

Reject configs that contain neither. Reject unknown artifact IDs with a `ValidationIssue` category `global_command_guards` and a field like `global_command_guards.<id>.evidence.artifact`.

- [x] **Step 6: Implement runtime artifact resolution**

In `global_command_guards.py`, add helper functions:

```python
def _profile_dir(user_home: Path, project: Path, guard: EffectiveGlobalCommandGuard) -> Path:
    root = user_home / ".agents" / "guards" if guard.source_scope == "user" else project / ".agents" / "guards"
    return root / guard.profile_id


def _load_artifact_path(project: Path, user_home: Path, guard: EffectiveGlobalCommandGuard, artifact_id: str) -> str | None:
    path = _profile_dir(user_home, project, guard) / "artifacts.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    for item in data.get("artifacts", []) if isinstance(data, dict) else []:
        if isinstance(item, dict) and item.get("id") == artifact_id and isinstance(item.get("path"), str):
            return item["path"]
    return None
```

Add a resolver that:

- Uses artifact path when `evidence.artifact` or `evidence.artifact_id` exists.
- Resolves relative artifact paths against `project.resolve()`.
- Rejects absolute paths and path traversal outside the project root.
- Uses the existing legacy `_resolve_evidence_path` only for `evidence.path`.
- Adds `artifact` to failure details when artifact lookup is used.

- [x] **Step 7: Run validator and runtime tests**

Run:

```bash
python -m pytest tests/test_validate_guard_profile.py::test_global_command_guard_accepts_artifact_reference tests/test_validate_guard_profile.py::test_global_command_guard_rejects_unknown_artifact_reference tests/test_agent_guard_runtime_router.py::test_global_command_guard_reads_registered_artifact_from_project_root tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_missing_registered_artifact -q
```

Expected: PASS.

- [x] **Step 8: Run adjacent regression tests**

Run:

```bash
python -m pytest tests/test_validate_guard_profile.py tests/test_agent_guard_runtime_router.py -q
```

Expected: PASS.

- [x] **Step 9: Commit**

```bash
git add plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py plugins/agent-guard/scripts/guard_runtime/global_command_guards.py tests/test_validate_guard_profile.py tests/test_agent_guard_runtime_router.py
git commit -m "feat: let global command guards use artifacts"
```

archived-with: 2026-06-20-add-comet-agent-review-gate
---

### Task 3: Update Agent Guard Skill Entry Docs

**Files:**
- Modify: `plugins/agent-guard/skills/agent-guard/SKILL.md`
- Modify: `plugins/agent-guard/skills/agent-guard-install/SKILL.md`
- Modify: `plugins/agent-guard/skills/agent-guard-init/SKILL.md`
- Modify: `plugins/agent-guard/skills/agent-guard-update/SKILL.md`
- Modify: `plugins/agent-guard/skills/agent-guard-run/SKILL.md`
- Modify: `plugins/agent-guard/skills/agent-guard-install/references/profile-draft.md`
- Modify: `plugins/agent-guard/skills/agent-guard-init/references/init-flow.md`
- Modify: `plugins/agent-guard/skills/agent-guard-update/references/profile-sync.md`
- Modify: `plugins/agent-guard/skills/agent-guard-run/references/events.md`
- Modify: `plugins/agent-guard/skills/agent-guard/references/template-index.md`
- Test: `tests/test_agent_guard_skill_entrypoints.py`

- [x] **Step 1: Add failing docs tests**

Add a test that checks the four writing standards and scenario coverage:

```python
def test_agent_guard_global_command_guard_docs_are_scenario_based() -> None:
    files = [
        SOURCE_SKILL / "SKILL.md",
        SOURCE_SKILL.parent / "agent-guard-install" / "SKILL.md",
        SOURCE_SKILL.parent / "agent-guard-init" / "SKILL.md",
        SOURCE_SKILL.parent / "agent-guard-update" / "SKILL.md",
        SOURCE_SKILL.parent / "agent-guard-run" / "SKILL.md",
        SOURCE_SKILL / "references" / "template-index.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    for phrase in [
        "Global Command Guard",
        "global-command-guards.yaml",
        "artifacts.yaml",
        "artifact",
        "禁止新增 reviewed wrapper",
        "禁止修改 cross-agent-review 默认输出目录",
        "禁止复制 pass marker 到 `.local/guard/evidence`",
        "禁止把 `verify --apply` 作为主拦截点",
        "禁止在 Agent Guard 中实现 cross-agent-review 内部流程",
    ]:
        assert phrase in combined

    for scenario in ["install", "init", "update", "run", "troubleshoot"]:
        assert scenario in combined
```

- [x] **Step 2: Run docs test and verify failure**

Run:

```bash
python -m pytest tests/test_agent_guard_skill_entrypoints.py::test_agent_guard_global_command_guard_docs_are_scenario_based -q
```

Expected: FAIL because current docs do not mention Global Command Guard.

- [x] **Step 3: Update router entrypoint**

In `plugins/agent-guard/skills/agent-guard/SKILL.md`, add rows to the routing table:

```markdown
| 安装或配置 Global Command Guard（全局命令守卫点） | `$agent-guard-install` |
| 初始化或同步用户级全局命令守卫画像 | `$agent-guard-init` / `$agent-guard-update` |
| 解释 PreToolUse deny（工具使用前拒绝）并按画像提示决定下一步 | `$agent-guard-run` |
```

Keep this file as a thin router. Do not add runtime field details here.

- [x] **Step 4: Update install/init/update/run entrypoints**

Add one short Global Command Guard section to each entrypoint:

```markdown
## Global Command Guard

- install：生成 `global-command-guards.yaml`，需要外部证据时同步生成 `artifacts.yaml`。
- init：初始化前必须运行 `validate_guard_profile.py <guard-profile-dir>`。
- update：同步前必须重新校验，保留 `.local/guard/*` 运行态材料。
- run：PreToolUse deny 不依赖 Session Focus Instance；解释 reason、next、suggestion、captures、failing guards 和 artifact 信息。reason/next/suggestion 可来自 Guard Profile 配置，Runtime 只透传或渲染，不内置业务流程。
```

For `$agent-guard-run`, state only the generic deny interpretation contract. It may point to configured `next` and `suggestion` fields from the Guard Profile, but must not describe the cross-agent-review internal flow.

- [x] **Step 5: Update references with progressive disclosure**

Add short sections:

- `profile-draft.md`: when a profile needs Global Command Guard, create or update `global-command-guards.yaml` and `artifacts.yaml`.
- `init-flow.md`: user-level profile path is `~/.agents/guards/<profile_id>/`; validation must cover global guards.
- `profile-sync.md`: sync preserves runtime data and revalidates global guard artifact references.
- `events.md`: explain PreToolUse deny handling for Global Command Guard.
- `template-index.md`: list `assets/templates/guard-profile/comet-review-gate/` as the Comet review gate Guard Profile template and explain it is intended for user-level installation.

Use short bullets. Put field details in template files, not entrypoints.

- [x] **Step 6: Run docs tests**

Run:

```bash
python -m pytest tests/test_agent_guard_skill_entrypoints.py tests/test_agent_guard_plugin_package.py -q
```

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add plugins/agent-guard/skills/agent-guard/SKILL.md plugins/agent-guard/skills/agent-guard-install/SKILL.md plugins/agent-guard/skills/agent-guard-init/SKILL.md plugins/agent-guard/skills/agent-guard-update/SKILL.md plugins/agent-guard/skills/agent-guard-run/SKILL.md plugins/agent-guard/skills/agent-guard-install/references/profile-draft.md plugins/agent-guard/skills/agent-guard-init/references/init-flow.md plugins/agent-guard/skills/agent-guard-update/references/profile-sync.md plugins/agent-guard/skills/agent-guard-run/references/events.md plugins/agent-guard/skills/agent-guard/references/template-index.md tests/test_agent_guard_skill_entrypoints.py
git commit -m "docs: expose global command guard skill flows"
```

archived-with: 2026-06-20-add-comet-agent-review-gate
---

### Task 4: Document The Guard Boundary

**Files:**
- Modify: `plugins/agent-guard/skills/agent-guard/references/template-index.md`
- Modify: `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/validation-plan.md`
- Modify mirrored `plugins/agent-guard/assets/templates/guard-profile/comet-review-gate/validation-plan.md`
- Test: `tests/test_agent_guard_skill_entrypoints.py`

- [x] **Step 1: Add failing flow documentation test**

Add:

```python
def test_comet_review_gate_docs_state_guarded_flow_and_prohibitions() -> None:
    validation_plan = SOURCE_SKILL / "assets" / "templates" / "guard-profile" / "comet-review-gate" / "validation-plan.md"
    text = validation_plan.read_text(encoding="utf-8")

    for phrase in [
        "comet-guard.sh <change> build --apply",
        "cross-agent-review",
        "review-pass.json",
        "禁止新增 reviewed wrapper",
        "禁止修改 cross-agent-review 默认输出目录",
        "禁止复制 pass marker 到 `.local/guard/evidence`",
        "禁止把 `verify --apply` 作为主拦截点",
        "禁止在 Agent Guard 中实现 cross-agent-review 内部流程",
    ]:
        assert phrase in text
```

- [x] **Step 2: Run test and verify failure**

Run:

```bash
python -m pytest tests/test_agent_guard_skill_entrypoints.py::test_comet_review_gate_docs_state_guarded_flow_and_prohibitions -q
```

Expected: FAIL until README is expanded.

- [x] **Step 3: Update Comet template validation plan or scenario reference**

Record the boundary in the template validation plan or scenario reference:

```markdown
## Boundary

- Agent Guard matches `comet-guard.sh <change> build --apply`.
- Agent Guard validates the registered `cross_agent_review_pass` artifact.
- Agent Guard does not run cross-agent-review or prepare its inputs.

## 禁止项

- 禁止新增 reviewed wrapper。
- 禁止修改 cross-agent-review 默认输出目录。
- 禁止复制 pass marker 到 `.local/guard/evidence`。
- 禁止把 `verify --apply` 作为主拦截点。
- 禁止在 Agent Guard 中实现 cross-agent-review 内部流程。
```

Mirror the same text to the plugin root template when the edited file is part of the mirrored template.

- [x] **Step 4: Run docs tests**

Run:

```bash
python -m pytest tests/test_agent_guard_skill_entrypoints.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/comet-review-gate/validation-plan.md plugins/agent-guard/assets/templates/guard-profile/comet-review-gate/validation-plan.md tests/test_agent_guard_skill_entrypoints.py
git commit -m "docs: document comet review gate boundary"
```

archived-with: 2026-06-20-add-comet-agent-review-gate
---

### Task 5: End-to-End Regression And Comet Task Sync

**Files:**
- Modify: `openspec/changes/add-comet-agent-review-gate/tasks.md`

- [x] **Step 1: Run focused tests**

Run:

```bash
python -m pytest tests/test_validate_guard_profile.py tests/test_agent_guard_runtime_router.py tests/test_agent_guard_skill_entrypoints.py tests/test_agent_guard_plugin_package.py -q
```

Expected: PASS.

- [x] **Step 2: Run full repository test suite**

Run:

```bash
python -m pytest -q
```

Expected: PASS.

- [x] **Step 3: Run OpenSpec validation**

Run:

```bash
openspec validate add-comet-agent-review-gate --strict
```

Expected: `Change 'add-comet-agent-review-gate' is valid`.

- [x] **Step 4: Update Comet tasks**

Check off completed tasks in `openspec/changes/add-comet-agent-review-gate/tasks.md` only after the corresponding tests pass:

```markdown
- [x] 1.1 Add a Comet agent review gate Guard Profile sample or template.
- [x] 1.2 Configure the user-level profile to use Global Command Guard on `comet-guard.sh <change> build --apply`.
- [x] 1.3 Cover direct script calls, path-qualified script calls, and `"$COMET_BASH" "$COMET_GUARD" <change> build --apply` command forms.
- [x] 1.4 Register cross-agent-review `review-pass.json` in `artifacts.yaml` as `cross_agent_review_pass`.
- [x] 1.5 Validate the registered artifact with JSON predicate checks for `status`, `change`, `head_ref`, `blocking_findings`, `report`, and `report_hash`.
- [x] 1.6 Update Agent Guard skill entry docs and shared references for Global Command Guard configuration, user-level setup, artifact registration, deny handling, and troubleshooting.
- [x] 1.7 Ensure those docs use progressive disclosure, are organized by agent use scenario, list explicit prohibitions, and keep language concise.
- [x] 2.1 Extend Global Command Guard evidence evaluation to accept `artifact` / `artifact_id` references from `artifacts.yaml`.
- [x] 2.2 Resolve user-level profile artifact paths relative to the current project root for project commands.
- [x] 2.3 Support Global Command Guard artifact path templates with command captures and `{git_head}`.
- [x] 2.4 Ensure Global Command Guard artifact lookup does not require Session Focus `{instance_id}` or `{state_version}`.
- [x] 2.5 Keep legacy `evidence.path` behavior for existing Global Command Guard configs, but do not use it for the Comet review gate.
```

Leave flow and full regression tasks unchecked until actual end-to-end review gate behavior has been verified.

- [x] **Step 5: Commit**

```bash
git add openspec/changes/add-comet-agent-review-gate/tasks.md
git commit -m "chore: sync comet review gate tasks"
```

archived-with: 2026-06-20-add-comet-agent-review-gate
---

## Plan Self-Review

- Spec coverage: tasks cover user-level Global Command Guard profile, artifact registration, runtime artifact reference, skill entry docs, deny handling, command pattern variants, and regression tests.
- Pure configuration constraint: preserved by the pre-execution gate before runtime edits.
- Boundary behavior: no wrapper, no cross-agent-review output change, no pass marker copy, no Comet phase change.
- Test coverage: validator, runtime, docs/package, focused suite, full suite, and OpenSpec validation are included.

