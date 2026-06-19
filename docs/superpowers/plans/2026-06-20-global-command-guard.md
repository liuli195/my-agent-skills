---
change: add-guard-gate-binding
design-doc: docs/superpowers/specs/2026-06-20-global-command-guard-design.md
base-ref: 9c8ce9016907bbd75a29ad9e4dfb6b38eff28f84
---

# 全局命令守卫点 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Agent Guard（代理守卫）Runtime（运行时）中新增 Global Command Guard（全局命令守卫点），在 PreToolUse（工具使用前）阶段收集多来源规则、匹配命令、校验证据，并在证据不通过时拒绝命令。

**Architecture:** 新增一个可复用的全局命令守卫层：先从项目级和用户级 Guard Profile（守卫画像）收集 `global-command-guards.yaml`，生成 Effective Global Command Guard Set（有效全局命令守卫集），再对当前命令执行匹配和 evidence（证据）检查。该层运行在现有 Session Focus permission（会话焦点权限）之前，并复用现有命令提取、JSON predicate（JSON 谓词）、审计和校验器风格。

**Tech Stack:** Python 3、PyYAML、pytest、现有 Agent Guard hook router（钩子路由）、OpenSpec delta spec（增量规格）。

---

## File Structure

新增或修改文件：

- Modify: `plugins/agent-guard/scripts/guard_runtime/core.py`
  - 接入全局命令守卫评估入口。
  - 保留现有 Session Focus 行为。
  - 可先保留既有函数位置，避免一次性大重构。
- Create: `plugins/agent-guard/scripts/guard_runtime/global_command_guards.py`
  - 收集项目级和用户级 `global-command-guards.yaml`。
  - 生成 `effective_guard_id`。
  - 匹配 command pattern（命令模式）。
  - 解析 evidence path template（证据路径模板）。
  - 聚合 allow / deny 结果。
- Create: `plugins/agent-guard/scripts/guard_runtime/json_checks.py`
  - 抽出 JSON 字段读取和 predicate 评估。
  - 供现有 `json_artifact` 和全局命令守卫点复用。
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py`
  - 校验单个 Guard Profile 内的 `global-command-guards.yaml`。
  - 同一文件内 `guard_id` 必须唯一。
- Create: `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/minimal/global-command-guards.yaml`
  - 提供空配置模板。
- Create: `plugins/agent-guard/assets/templates/guard-profile/minimal/global-command-guards.yaml`
  - 与 skill 内模板保持一致。
- Modify: `tests/test_validate_guard_profile.py`
  - 覆盖配置校验。
- Modify: `tests/test_agent_guard_runtime_router.py`
  - 覆盖 PreToolUse 多来源拦截、证据通过/失败、无 Session Focus 仍生效。
- Modify: `tests/test_agent_guard_runtime_session_focus.py`
  - 回归验证 Session Focus permission 仍在全局守卫之后执行。
- Modify: `plugins/agent-guard/scripts/guard_runtime/README.md`
  - 说明全局命令守卫点和运行态目录规则。

---

## Task 1: Guard Profile 校验器和模板

**Files:**
- Modify: `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py`
- Modify: `tests/test_validate_guard_profile.py`
- Create: `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/minimal/global-command-guards.yaml`
- Create: `plugins/agent-guard/assets/templates/guard-profile/minimal/global-command-guards.yaml`

- [x] **Step 1: 写失败测试：最小模板允许空全局命令守卫配置**

在 `tests/test_validate_guard_profile.py` 添加：

```python
def test_global_command_guards_template_file_is_allowed() -> None:
    result = run_validator(MINIMAL_PROFILE)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "通过：Guard Profile（守卫画像）校验" in result.stdout
```

Run:

```powershell
python -m pytest tests/test_validate_guard_profile.py::test_global_command_guards_template_file_is_allowed -q
```

Expected: FAIL，因为模板文件还不存在或 validator（校验器）还不会检查该配置。

- [x] **Step 2: 添加空模板文件**

创建两个模板文件，内容完全一致：

```yaml
global_command_guards: []
```

路径：

```text
plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/minimal/global-command-guards.yaml
plugins/agent-guard/assets/templates/guard-profile/minimal/global-command-guards.yaml
```

- [x] **Step 3: 写失败测试：有效全局命令守卫配置通过**

在 `tests/test_validate_guard_profile.py` 添加：

```python
def test_global_command_guard_valid_config_passes(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "global-command-guards.yaml").write_text(
        """
global_command_guards:
  - id: verify_requires_review
    description: Comet verify 前必须有 review 证据。
    tool: Bash
    match:
      command_patterns:
        - 'comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply'
      required_captures:
        - change
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{change}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: global_command_guard_required
      next: produce_required_evidence
      suggestion: 先完成 reviewed flow（已审查流程）。
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 0, result.stdout + result.stderr
```

Run:

```powershell
python -m pytest tests/test_validate_guard_profile.py::test_global_command_guard_valid_config_passes -q
```

Expected: FAIL，因为 validator 还没有 `global-command-guards.yaml` 规则。

- [x] **Step 4: 实现 validator 支持**

在 `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py` 中添加：

```python
GLOBAL_COMMAND_GUARD_VALUE_FROM_FIELDS = {
    "source_scope",
    "profile_id",
    "guard_id",
    "effective_guard_id",
    "runtime_scope",
    "git_head",
}


def validate_global_command_guards(profile_dir: Path) -> list[ValidationIssue]:
    path = profile_dir / "global-command-guards.yaml"
    if not path.exists():
        return []
    data, issue = load_yaml(path, "global_command_guards")
    if issue or data is None:
        return [issue] if issue else []
    guards = data.get("global_command_guards")
    if guards is None:
        return []
    if not isinstance(guards, list):
        return [
            ValidationIssue(
                "global_command_guards",
                "global_command_guards",
                "必须是 list（列表）。",
                "把 global_command_guards 改成列表；没有规则时写 `global_command_guards: []`。",
            )
        ]
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    for index, guard in enumerate(guards):
        if not isinstance(guard, dict):
            issues.append(
                ValidationIssue(
                    "global_command_guards",
                    f"global_command_guards.{index}",
                    "必须是 mapping（映射）。",
                    "把该条规则改成包含 id、tool、match、evidence、checks 的映射。",
                )
            )
            continue
        guard_id = guard.get("id")
        base = f"global_command_guards.{guard_id if isinstance(guard_id, str) else index}"
        if not isinstance(guard_id, str) or not guard_id:
            issues.append(ValidationIssue("global_command_guards", f"{base}.id", "必须声明非空 id。", "为该全局命令守卫点添加唯一 id。"))
        elif guard_id in seen:
            issues.append(ValidationIssue("global_command_guards", f"{base}.id", f"重复 id `{guard_id}`。", "同一个 global-command-guards.yaml 内 guard id 必须唯一。"))
        else:
            seen.add(guard_id)
        if not isinstance(guard.get("tool"), str) or not guard.get("tool"):
            issues.append(ValidationIssue("global_command_guards", f"{base}.tool", "必须声明工具名。", "例如写 `tool: Bash`。"))
        match = guard.get("match")
        patterns = match.get("command_patterns") if isinstance(match, dict) else None
        if not isinstance(patterns, list) or not patterns or not all(isinstance(item, str) and item for item in patterns):
            issues.append(ValidationIssue("global_command_guards", f"{base}.match.command_patterns", "必须声明至少一个命令模式。", "添加 command_patterns 列表。"))
        evidence = guard.get("evidence")
        if not isinstance(evidence, dict) or not isinstance(evidence.get("path"), str) or not evidence.get("path"):
            issues.append(ValidationIssue("global_command_guards", f"{base}.evidence.path", "必须声明 evidence path template（证据路径模板）。", "添加 evidence.path。"))
        checks = guard.get("checks")
        if not isinstance(checks, list) or not checks:
            issues.append(ValidationIssue("global_command_guards", f"{base}.checks", "必须声明至少一个 JSON 检查。", "添加 checks 列表。"))
        for check_index, check in enumerate(checks if isinstance(checks, list) else []):
            if not isinstance(check, dict):
                continue
            predicate = check.get("predicate")
            if not isinstance(predicate, str) or predicate not in JSON_ARTIFACT_PREDICATES:
                issues.append(ValidationIssue("global_command_guards", f"{base}.checks.{check_index}.predicate", "未知或缺失 JSON predicate（JSON 谓词）。", "使用 json_artifact 支持的 predicate。"))
            value_from = check.get("value_from")
            if value_from is not None and not isinstance(value_from, str):
                issues.append(ValidationIssue("global_command_guards", f"{base}.checks.{check_index}.value_from", "必须是字符串。", "引用命名捕获或内置上下文字段。"))
    return issues
```

再把 `validate_global_command_guards(profile_dir)` 接入 validator 的主校验结果列表。

- [x] **Step 5: 写失败测试：单文件内重复 id 报错**

在 `tests/test_validate_guard_profile.py` 添加：

```python
def test_global_command_guard_duplicate_id_in_same_file_fails(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "global-command-guards.yaml").write_text(
        """
global_command_guards:
  - id: duplicate
    tool: Bash
    match:
      command_patterns: ['tool (?P<name>[A-Za-z0-9._-]+)']
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{name}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
  - id: duplicate
    tool: Bash
    match:
      command_patterns: ['other (?P<name>[A-Za-z0-9._-]+)']
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{name}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=global_command_guards" in result.stdout
    assert "重复 id `duplicate`" in result.stdout
```

Run:

```powershell
python -m pytest tests/test_validate_guard_profile.py::test_global_command_guard_duplicate_id_in_same_file_fails -q
```

Expected: PASS after Step 4.

- [x] **Step 6: 运行 validator 聚焦测试**

Run:

```powershell
python -m pytest tests/test_validate_guard_profile.py -q
```

Expected: PASS.

- [x] **Step 7: 提交 Task 1**

```powershell
git add plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py `
        plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/minimal/global-command-guards.yaml `
        plugins/agent-guard/assets/templates/guard-profile/minimal/global-command-guards.yaml `
        tests/test_validate_guard_profile.py
git commit -m "feat: 校验全局命令守卫配置"
```

---

## Task 2: 抽象 JSON 检查能力

**Files:**
- Create: `plugins/agent-guard/scripts/guard_runtime/json_checks.py`
- Modify: `plugins/agent-guard/scripts/guard_runtime/core.py`
- Modify: `tests/test_agent_guard_runtime_router.py`

- [x] **Step 1: 写失败测试：现有 json_artifact 行为保持不变**

先运行现有 JSON artifact 测试，作为重构保护：

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py -k "json_artifact or guard_point" -q
```

Expected: PASS before refactor.

- [x] **Step 2: 创建 JSON 检查模块**

创建 `plugins/agent-guard/scripts/guard_runtime/json_checks.py`：

```python
"""共享 JSON check（JSON 检查）能力。"""

from __future__ import annotations

from typing import Any


JSON_PREDICATES = {
    "exists",
    "equals",
    "not_equals",
    "number_lte",
    "number_gte",
    "array_none",
    "array_all",
}


VALUE_PREDICATES = {"equals", "not_equals", "number_lte", "number_gte"}
ARRAY_PREDICATES = {"array_none", "array_all"}


def json_field(data: Any, field: str) -> Any:
    current = data
    for part in field.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def evaluate_json_predicate(actual: Any, predicate: str, expected: Any = None, where: dict[str, Any] | None = None) -> bool:
    if predicate == "exists":
        return actual is not None
    if predicate == "equals":
        return actual == expected
    if predicate == "not_equals":
        return actual != expected
    if predicate == "number_lte":
        return isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and actual <= expected
    if predicate == "number_gte":
        return isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and actual >= expected
    if predicate in {"array_none", "array_all"}:
        if not isinstance(actual, list) or not isinstance(where, dict):
            return False
        child_field = where.get("field")
        child_predicate = where.get("predicate")
        if not isinstance(child_field, str) or not isinstance(child_predicate, str):
            return False
        results = [
            evaluate_json_predicate(json_field(item, child_field), child_predicate, where.get("value"), where.get("where"))
            for item in actual
        ]
        return not any(results) if predicate == "array_none" else all(results)
    return False
```

- [x] **Step 3: 迁移 core.py 使用共享模块**

在 `plugins/agent-guard/scripts/guard_runtime/core.py` 顶部添加：

```python
from json_checks import evaluate_json_predicate, json_field
```

然后删除或替换 `core.py` 内重复的 JSON 字段读取和 predicate 函数。保留函数名兼容时，可以改成薄包装：

```python
def read_json_field(data: Any, field: str) -> Any:
    return json_field(data, field)
```

如果现有函数名为 `json_field`，直接用 import 替换调用。

- [x] **Step 4: 运行回归测试**

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py -q
```

Expected: PASS.

- [x] **Step 5: 提交 Task 2**

```powershell
git add plugins/agent-guard/scripts/guard_runtime/json_checks.py `
        plugins/agent-guard/scripts/guard_runtime/core.py `
        tests/test_agent_guard_runtime_router.py
git commit -m "refactor: 抽象 JSON 守卫检查"
```

---

## Task 3: 命令上下文与命令模式匹配

**Files:**
- Create: `plugins/agent-guard/scripts/guard_runtime/global_command_guards.py`
- Modify: `tests/test_agent_guard_runtime_router.py`

- [x] **Step 1: 写失败测试：命令模式提取命名捕获**

在 `tests/test_agent_guard_runtime_router.py` 添加：

```python
def test_global_command_pattern_extracts_named_captures(tmp_path: Path) -> None:
    from importlib import util

    module_path = PLUGIN_ROOT / "scripts" / "guard_runtime" / "global_command_guards.py"
    spec = util.spec_from_file_location("global_command_guards", module_path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    match = module.match_command_pattern(
        "comet-guard.sh add-guard-gate-binding verify --apply",
        "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply",
    )

    assert match == {"change": "add-guard-gate-binding"}
```

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py::test_global_command_pattern_extracts_named_captures -q
```

Expected: FAIL because module/function does not exist.

- [x] **Step 2: 创建命令匹配基础能力**

在 `plugins/agent-guard/scripts/guard_runtime/global_command_guards.py` 添加：

```python
"""Global Command Guard（全局命令守卫点）收集、匹配和评估。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GuardSource:
    source_scope: str
    profile_id: str
    path: Path


@dataclass(frozen=True)
class EffectiveGlobalCommandGuard:
    source_scope: str
    profile_id: str
    guard_id: str
    effective_guard_id: str
    config: dict[str, Any]


def match_command_pattern(command: str, pattern: str) -> dict[str, str] | None:
    matched = re.search(pattern, command)
    if matched is None:
        return None
    return {key: value for key, value in matched.groupdict().items() if value is not None}
```

- [x] **Step 3: 写失败测试：PowerShell 包装 Git Bash 能匹配内层命令**

在 `tests/test_agent_guard_runtime_router.py` 添加：

```python
def test_global_command_pattern_matches_powershell_wrapped_git_bash(tmp_path: Path) -> None:
    from importlib import util

    module_path = PLUGIN_ROOT / "scripts" / "guard_runtime" / "global_command_guards.py"
    spec = util.spec_from_file_location("global_command_guards", module_path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    command = "& 'C:\\\\Program Files\\\\Git\\\\bin\\\\bash.exe' -lc 'cd \"/d/My Project/my-agent-skills\" && comet-guard.sh add-guard-gate-binding verify --apply'"

    normalized = module.normalized_command_texts(command)

    assert "comet-guard.sh add-guard-gate-binding verify --apply" in normalized
```

- [x] **Step 4: 实现命令文本标准化**

在 `global_command_guards.py` 添加：

```python
def normalized_command_texts(command: str) -> list[str]:
    texts = [command]
    marker = " -lc "
    if marker in command:
        after = command.split(marker, 1)[1].strip()
        if (after.startswith("'") and after.endswith("'")) or (after.startswith('"') and after.endswith('"')):
            after = after[1:-1]
        parts = [part.strip() for part in after.split("&&") if part.strip()]
        texts.extend(parts)
    return list(dict.fromkeys(texts))
```

- [x] **Step 5: 运行命令匹配测试**

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py::test_global_command_pattern_extracts_named_captures tests/test_agent_guard_runtime_router.py::test_global_command_pattern_matches_powershell_wrapped_git_bash -q
```

Expected: PASS.

- [x] **Step 6: 提交 Task 3**

```powershell
git add plugins/agent-guard/scripts/guard_runtime/global_command_guards.py `
        tests/test_agent_guard_runtime_router.py
git commit -m "feat: 添加全局命令匹配基础能力"
```

---

## Task 4: 多来源收集和有效守卫 ID

**Files:**
- Modify: `plugins/agent-guard/scripts/guard_runtime/global_command_guards.py`
- Modify: `tests/test_agent_guard_runtime_router.py`

- [x] **Step 1: 写失败测试：项目级和用户级来源都会被收集**

在 `tests/test_agent_guard_runtime_router.py` 添加：

```python
def write_global_command_guard(profile: Path, guard_id: str, command_pattern: str) -> None:
    profile.joinpath("global-command-guards.yaml").write_text(
        f"""
global_command_guards:
  - id: {guard_id}
    description: 测试全局命令守卫点。
    tool: Bash
    match:
      command_patterns:
        - '{command_pattern}'
    evidence:
      path: '.local/guard/evidence/{{source_scope}}/{{profile_id}}/{{guard_id}}/{{change}}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
    deny:
      reason: global_command_guard_required
      next: produce_required_evidence
      suggestion: 先生成证据。
""".lstrip(),
        encoding="utf-8",
    )


def test_collects_project_and_user_global_command_guards(tmp_path: Path) -> None:
    from importlib import util

    module_path = PLUGIN_ROOT / "scripts" / "guard_runtime" / "global_command_guards.py"
    spec = util.spec_from_file_location("global_command_guards", module_path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project_profile = project / ".agents" / "guards" / "repo-policy"
    user_profile = user_home / ".agents" / "guards" / "personal-policy"
    project_profile.mkdir(parents=True)
    user_profile.mkdir(parents=True)
    write_global_command_guard(project_profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply")
    write_global_command_guard(user_profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply")

    guards = module.collect_global_command_guards(project, user_home)
    ids = sorted(guard.effective_guard_id for guard in guards)

    assert ids == [
        "project:repo-policy:verify_requires_review",
        "user:personal-policy:verify_requires_review",
    ]
```

- [x] **Step 2: 实现收集器**

在 `global_command_guards.py` 添加：

```python
import yaml


def _guard_sources(project: Path, user_home: Path) -> list[GuardSource]:
    sources: list[GuardSource] = []
    for path in sorted((project / ".agents" / "guards").glob("*/global-command-guards.yaml")):
        sources.append(GuardSource("project", path.parent.name, path))
    for path in sorted((user_home / ".agents" / "guards").glob("*/global-command-guards.yaml")):
        sources.append(GuardSource("user", path.parent.name, path))
    return sources


def collect_global_command_guards(project: Path, user_home: Path) -> list[EffectiveGlobalCommandGuard]:
    guards: list[EffectiveGlobalCommandGuard] = []
    for source in _guard_sources(project, user_home):
        data = yaml.safe_load(source.path.read_text(encoding="utf-8")) or {}
        items = data.get("global_command_guards", [])
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            guard_id = item.get("id")
            if not isinstance(guard_id, str) or not guard_id:
                continue
            effective_id = f"{source.source_scope}:{source.profile_id}:{guard_id}"
            guards.append(
                EffectiveGlobalCommandGuard(
                    source_scope=source.source_scope,
                    profile_id=source.profile_id,
                    guard_id=guard_id,
                    effective_guard_id=effective_id,
                    config=item,
                )
            )
    return guards
```

- [x] **Step 3: 运行收集器测试**

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py::test_collects_project_and_user_global_command_guards -q
```

Expected: PASS.

- [x] **Step 4: 提交 Task 4**

```powershell
git add plugins/agent-guard/scripts/guard_runtime/global_command_guards.py `
        tests/test_agent_guard_runtime_router.py
git commit -m "feat: 收集多来源全局命令守卫"
```

---

## Task 5: Runtime 评估、deny 输出和审计

**Files:**
- Modify: `plugins/agent-guard/scripts/guard_runtime/global_command_guards.py`
- Modify: `plugins/agent-guard/scripts/guard_runtime/core.py`
- Modify: `tests/test_agent_guard_runtime_router.py`
- Modify: `tests/test_agent_guard_runtime_session_focus.py`

- [ ] **Step 1: 写失败测试：无 Session Focus 时全局守卫仍拒绝命令**

在 `tests/test_agent_guard_runtime_router.py` 添加：

```python
def test_global_command_guard_denies_without_session_focus(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply")

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 1, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "global_command_guard_required"
    assert payload["matched_guard_ids"] == ["project:repo-policy:verify_requires_review"]
    assert payload["failing_guards"][0]["effective_guard_id"] == "project:repo-policy:verify_requires_review"
    assert ".local" in payload["failing_guards"][0]["evidence_path"]
```

- [ ] **Step 2: 实现 evidence 评估**

在 `global_command_guards.py` 添加：

```python
import json
import subprocess
from json_checks import evaluate_json_predicate, json_field


def git_head(project: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def runtime_scope_for_command(project: Path, user_home: Path, envelope: dict[str, Any]) -> str:
    context = envelope.get("context", {})
    cwd = Path(str(context.get("cwd") or project))
    try:
        return "project" if cwd.resolve().is_relative_to(project.resolve()) else "user"
    except OSError:
        return "project"


def render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered
```

再添加 `evaluate_global_command_guards(...)`，返回：

```python
{
    "effect": "allow" | "deny",
    "reason": "global_command_guard_passed" | "global_command_guard_required",
    "matched_guard_ids": [...],
    "failing_guards": [...],
}
```

要求：

- 没有匹配规则：返回 `effect=allow`、`matched_guard_ids=[]`，不写全局守卫审计。
- 有匹配规则且全部通过：返回 `effect=allow`、`reason=global_command_guard_passed`，调用方写 allow 审计。
- 任意失败：返回 `effect=deny`。
- `value_from` 先查 captures，再查内置上下文字段。

- [ ] **Step 3: 在 core.py 接入 PreToolUse**

在 `plugins/agent-guard/scripts/guard_runtime/core.py` 顶部添加：

```python
from global_command_guards import evaluate_global_command_guards
```

在 `route_pre_tool_use` 的 `session_id` 检查之后、`focus_boundary_result` 之前添加：

```python
    global_guard = evaluate_global_command_guards(project, user_home, envelope)
    if global_guard["effect"] == "deny":
        audit_path = write_audit(project, "deny", str(global_guard["reason"]), {"global_command_guard": global_guard})
        return {
            "status": "deny",
            "reason": global_guard["reason"],
            "next": global_guard.get("next"),
            "suggestion": global_guard.get("suggestion"),
            "matched_guard_ids": global_guard.get("matched_guard_ids", []),
            "failing_guards": global_guard.get("failing_guards", []),
            "audit_path": str(audit_path),
        }, 1
```

如果 `effect=allow` 且 `matched_guard_ids` 非空，也写 allow 审计后继续进入原有 Session Focus 流程。

- [ ] **Step 4: 写失败测试：evidence 通过后允许继续**

在 `tests/test_agent_guard_runtime_router.py` 添加：

```python
def test_global_command_guard_passes_with_valid_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = project / ".agents" / "guards" / "repo-policy"
    profile.mkdir(parents=True)
    write_global_command_guard(profile, "verify_requires_review", "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply")
    evidence = project / ".local" / "guard" / "evidence" / "project" / "repo-policy" / "verify_requires_review" / "add-guard-gate-binding" / "evidence.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(json.dumps({"status": "pass"}, ensure_ascii=False), encoding="utf-8")

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = body(result)
    assert payload["status"] == "allow"
```

- [ ] **Step 5: 写失败测试：多规则任一失败则 deny**

在 `tests/test_agent_guard_runtime_router.py` 添加：

```python
def test_global_command_guard_denies_when_any_matching_guard_fails(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    project_profile = project / ".agents" / "guards" / "repo-policy"
    user_profile = user_home / ".agents" / "guards" / "personal-policy"
    project_profile.mkdir(parents=True)
    user_profile.mkdir(parents=True)
    pattern = "comet-guard.sh (?P<change>[A-Za-z0-9._-]+) verify --apply"
    write_global_command_guard(project_profile, "verify_requires_review", pattern)
    write_global_command_guard(user_profile, "verify_requires_review", pattern)
    evidence = project / ".local" / "guard" / "evidence" / "project" / "repo-policy" / "verify_requires_review" / "add-guard-gate-binding" / "evidence.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(json.dumps({"status": "pass"}, ensure_ascii=False), encoding="utf-8")

    result = pre_tool(project, user_home, "comet-guard.sh add-guard-gate-binding verify --apply")

    assert result.returncode == 1
    payload = body(result)
    assert sorted(payload["matched_guard_ids"]) == [
        "project:repo-policy:verify_requires_review",
        "user:personal-policy:verify_requires_review",
    ]
    assert [item["effective_guard_id"] for item in payload["failing_guards"]] == ["user:personal-policy:verify_requires_review"]
    assert ".local" in payload["failing_guards"][0]["evidence_path"]
```

- [ ] **Step 6: 写回归测试：全局守卫 allow 后 Session Focus 仍可 deny**

在 `tests/test_agent_guard_runtime_session_focus.py` 或 `tests/test_agent_guard_runtime_router.py` 添加：

```python
def test_global_command_guard_allow_does_not_bypass_session_focus_deny(tmp_path: Path) -> None:
    project = tmp_path / "project"
    user_home = tmp_path / "user-home"
    project.mkdir()
    profile = write_profile(project)
    write_state_machine(profile, "deny")
    write_global_command_guard(profile, "push_requires_evidence", "git push (?P<branch>[A-Za-z0-9._/-]+)")
    evidence = project / ".local" / "guard" / "evidence" / "project" / "minimal-sample" / "push_requires_evidence" / "main" / "evidence.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(json.dumps({"status": "pass"}, ensure_ascii=False), encoding="utf-8")
    session_start(project, user_home)
    activate(project, user_home)

    result = pre_tool(project, user_home, "git push main")

    assert result.returncode == 1
    payload = body(result)
    assert payload["status"] == "deny"
    assert payload["reason"] == "当前状态要求 deny。"
```

- [ ] **Step 7: 运行 runtime 聚焦测试**

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py tests/test_agent_guard_runtime_session_focus.py -q
```

Expected: PASS.

- [ ] **Step 8: 提交 Task 5**

```powershell
git add plugins/agent-guard/scripts/guard_runtime/global_command_guards.py `
        plugins/agent-guard/scripts/guard_runtime/core.py `
        tests/test_agent_guard_runtime_router.py `
        tests/test_agent_guard_runtime_session_focus.py
git commit -m "feat: 在 PreToolUse 执行全局命令守卫"
```

---

## Task 6: 文档、端到端验证和 OpenSpec 任务勾选

**Files:**
- Modify: `plugins/agent-guard/scripts/guard_runtime/README.md`
- Modify: `openspec/changes/add-guard-gate-binding/tasks.md`

- [ ] **Step 1: 更新 runtime README**

在 `plugins/agent-guard/scripts/guard_runtime/README.md` 添加一节：

```markdown
## Global Command Guard（全局命令守卫点）

Runtime（运行时）在 PreToolUse（工具使用前）阶段收集：

- `.agents/guards/*/global-command-guards.yaml`
- `~/.agents/guards/*/global-command-guards.yaml`

每条规则的 effective guard id（有效守卫 ID）为：

```text
<source_scope>:<profile_id>:<guard_id>
```

一个命令匹配多个规则时，所有规则都必须通过；任意规则失败则命令拒绝。

项目命令的 evidence（证据）和 audit（审计）默认写入项目 `.local/guard`，即使规则来源是用户级 Guard Profile（守卫画像）。
```
```

- [ ] **Step 2: 运行模板/包测试**

Run:

```powershell
python -m pytest tests/test_agent_guard_plugin_package.py tests/test_agent_guard_plugin_runtime_e2e.py -q
```

Expected: PASS.

- [ ] **Step 3: 运行 Agent Guard 相关测试**

Run:

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py tests/test_agent_guard_runtime_session_focus.py tests/test_validate_guard_profile.py tests/test_agent_guard_plugin_package.py tests/test_agent_guard_plugin_runtime_e2e.py -q
```

Expected: PASS.

- [ ] **Step 4: 运行 OpenSpec 校验**

Run:

```powershell
openspec validate add-guard-gate-binding --strict
```

Expected:

```text
Change 'add-guard-gate-binding' is valid
```

- [ ] **Step 5: 勾选 OpenSpec tasks**

在 `openspec/changes/add-guard-gate-binding/tasks.md` 中勾选已完成条目。至少应勾选：

```markdown
- [x] 1.1 ...
- [x] 1.2 ...
- [x] 1.3 ...
- [x] 1.4 ...
- [x] 1.5 ...
- [x] 2.1 ...
- [x] 2.2 ...
- [x] 2.3 ...
- [x] 2.4 ...
- [x] 2.5 ...
- [x] 2.6 ...
- [x] 2.7 ...
- [x] 3.1 ...
- [x] 3.2 ...
- [x] 3.3 ...
- [x] 3.4 ...
- [x] 3.5 ...
- [x] 3.6 ...
- [x] 4.1 ...
- [x] 4.2 ...
- [x] 4.3 ...
- [x] 4.4 ...
- [x] 4.5 ...
- [x] 4.6 ...
- [x] 4.7 ...
- [x] 4.8 ...
- [x] 4.9 ...
- [x] 5.1 ...
- [x] 5.2 ...
- [x] 5.3 ...
- [x] 5.4 ...
- [x] 5.5 ...
```

只勾选实际完成且测试通过的任务；如果完整仓库测试未运行，不勾选 `5.6`。

- [ ] **Step 6: 提交 Task 6**

```powershell
git add plugins/agent-guard/scripts/guard_runtime/README.md `
        openspec/changes/add-guard-gate-binding/tasks.md
git commit -m "docs: 说明全局命令守卫运行规则"
```

---

## Full Verification

在所有任务完成后运行：

```powershell
python -m pytest tests/test_agent_guard_runtime_router.py tests/test_agent_guard_runtime_session_focus.py tests/test_validate_guard_profile.py tests/test_agent_guard_plugin_package.py tests/test_agent_guard_plugin_runtime_e2e.py -q
openspec validate add-guard-gate-binding --strict
```

如果仓库完整测试时间可接受，再运行：

```powershell
python -m pytest -q
```

完成条件：

- 全局命令守卫点可在没有 Session Focus 时拒绝命令。
- 用户级和项目级 `global-command-guards.yaml` 都会被收集。
- 不同 profile 或不同 source scope 中同名 `guard_id` 不冲突。
- 一个命令匹配多个规则时，任一规则失败都会 deny。
- deny 输出包含 `matched_guard_ids` 和 `failing_guards`。
- 项目命令的 evidence 和 audit 默认写入 `.local/guard`。
- 现有 Session Focus permission 语义保持不变。
