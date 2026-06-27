---
change: refactor-pr-flow-init
design-doc: docs/superpowers/specs/2026-06-27-pr-flow-init-refactor-design.md
base-ref: 098ee7c1ef9b2347808b864749fbb0df28d6c5ef
---

# PR Flow Init Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（子代理驱动开发，recommended） or superpowers:executing-plans（执行计划） to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `pr-flow-init` Skill（初始化技能）改成 agent（代理）问答、草案、只读 validate（校验）和最终确认写入流程，同时阻止旧 init（初始化）默认静默写入。

**Architecture:** Skill（技能）入口只保留边界和流程，细节下沉到三个 reference（参考文件）。`pr_flow.py`（共享脚本）新增只读 `validate --config`（校验配置）和 `init --config`（初始化写入已确认配置），运行命令继续只消费 `.pr-flow/config.yaml` 中的运行配置，不消费 `setup.github`（GitHub 配置建议）。测试先锁契约，再改最少代码。

**Tech Stack:** Python（编程语言）, argparse（命令行参数解析）, PyYAML（YAML 配置读取）, pytest（测试框架）, Markdown（文档格式）, OpenSpec（开放规格）。

---

## 文件结构

- Modify: `plugins/pr-flow/skills/pr-flow-init/SKILL.md`
  - 入口只写 Hard Boundaries（硬边界）、Closed Loop（闭环）、Required Flow（必需流程）、Output（输出）和 `references/`（参考文件）清单。
- Create: `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`
  - 固定问题、固定选项、选择后果和跳转规则；按用户场景组织。
- Create: `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`
  - `.pr-flow/config.yaml`（配置文件）草案结构、默认值、分支覆盖、`setup.github`（GitHub 配置建议）。
- Create: `plugins/pr-flow/skills/pr-flow-init/references/validation.md`
  - validate（校验）输出类别、依赖矩阵、写入摘要规则。
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
  - 增加 `validate`（校验）命令；让 `init`（初始化）只接受已确认 `--config`（配置文件路径）输入并复用 validate（校验）。
- Modify: `tests/test_pr_flow_cli.py`
  - 更新旧 init（初始化）测试和 helper（辅助函数）；新增 validate（校验）、依赖矩阵、端到端回归测试。
- Modify: `plugins/pr-flow/.codex-plugin/plugin.json`
  - 只在 init（初始化）入口描述或路由需要时更新。
- Modify: `plugins/pr-flow/.claude-plugin/plugin.json`
  - 只在 init（初始化）入口描述或路由需要时更新。
- Modify: `plugins/pr-flow/skills/pr-flow/SKILL.md`
  - 只在总入口描述或路由 init（初始化）需要时更新。

## 任务拆分

### Task 1: 锁定 pr-flow-init Skill（初始化技能）渐进式披露契约

**Files:**
- Test: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow-init/SKILL.md`
- Create: `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`
- Create: `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`
- Create: `plugins/pr-flow/skills/pr-flow-init/references/validation.md`

- [ ] **Step 1: 写失败测试，要求入口引用三个 references（参考文件）且不内联完整问答**

Add near current init（初始化） tests in `tests/test_pr_flow_cli.py`:

```python
def test_pr_flow_init_skill_uses_progressive_disclosure_references() -> None:
    skill_path = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-init" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")

    for heading in ["## Hard Boundaries", "## Closed Loop", "## Required Flow", "## Output", "## References"]:
        assert heading in text
    for reference in [
        "references/questionnaire.md",
        "references/config-draft.md",
        "references/validation.md",
    ]:
        assert reference in text
        assert (skill_path.parent / reference).is_file()
    assert text.count("?") <= 1
    assert "用户沉默 MUST NOT 被视为确认" in text
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_skill_uses_progressive_disclosure_references -q
```

Expected: FAIL（失败），因为 references（参考文件）不存在且入口结构未拆分。

- [ ] **Step 3: 写最小 Skill（技能）入口**

Replace `plugins/pr-flow/skills/pr-flow-init/SKILL.md` body with:

```markdown
---
name: pr-flow-init
description: "初始化 PR Flow（拉取请求流程）本地配置、PR 模板和运行态忽略文件。Use when 需要为仓库启用 PR Flow 配置。"
---

# PR Flow Init

## Hard Boundaries

- 只准备和写入 PR Flow（拉取请求流程）本地配置。
- 不提交、不推送、不合并。
- 不调用 GitHub API（GitHub 接口）写入远端设置。
- 不运行 diagnose、complete、cleanup、hotfix 或 tweak（诊断、收尾、清理、热修复、小改）。
- GitHub Rulesets（GitHub 规则集）只输出配置建议。

## Closed Loop

agent（代理）必须完成问答、草案展示、只读 validate（校验）、校验摘要、最终确认和本地写入结果说明。用户沉默 MUST NOT 被视为确认。

## Required Flow

1. 读取 `references/questionnaire.md`（问答模板）。
2. 按固定问题收集运行配置和 `setup.github`（GitHub 配置建议）意图。
3. 读取 `references/config-draft.md`（配置草案规则）并展示 `.pr-flow/config.yaml`（配置文件）草案。
4. 读取 `references/validation.md`（校验规则）并运行只读 `validate --config <path>`（校验配置）。
5. 如果 validate（校验）有 error（错误），停止，不写入。
6. 如果只有 warning（警告）或 setup suggestion（配置建议），展示影响并请求最终确认。
7. 用户明确确认后，运行 `init --project <repo> --config <path>`（初始化写入配置）。

## Output

- `.pr-flow/config.yaml`（配置文件）。
- `.pr-flow/pr-template.md`（拉取请求模板）。
- `.pr-flow/.gitignore`（忽略文件）。
- GitHub（代码托管平台）远端配置建议摘要，不声明已执行。

## References

- `references/questionnaire.md`
- `references/config-draft.md`
- `references/validation.md`
```

- [ ] **Step 4: 创建三个 references（参考文件）的最小骨架**

Create `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`:

```markdown
# PR Flow Init Questionnaire

## 场景：初次启用 PR Flow（拉取请求流程）

固定问题：目标分支是哪一个？

固定选项：
- `main`: 默认主分支。
- `master`: 旧仓库主分支。
- 自定义分支名：只在用户明确提供时使用。

选择后果：写入 `defaults.baseBranch`（默认目标分支）和 `branches.<branch>`（分支覆盖）。

跳转规则：继续 review gate（审查门禁）场景。

## 场景：选择 review gate（审查门禁）

固定问题：PR Flow（拉取请求流程）合并前使用哪种审查门禁？

固定选项：
- `github`: 依赖 GitHub（代码托管平台）required review（必需审查）。
- `local`: 依赖本地 `review-pass.json`（审查通过文件）。
- `dual`: 同时要求 GitHub（代码托管平台）和本地证据。
- `skip`: 只允许明确的小改或特殊仓库使用。

选择后果：写入 `defaults.reviewGate.mode`（默认审查门禁模式）；`local` 和 `dual` 必须写入 `defaults.reviewGate.evidencePath`（审查证据路径）。

跳转规则：继续 hotfix（热修复）场景。

## 场景：启用 hotfix（热修复）直推

固定问题：是否允许目标分支 hotfix（热修复）直推？

固定选项：
- `false`: 默认，不允许。
- `true`: 只在用户明确授权时允许。

选择后果：`true` 必须写入 `branches.<branch>.allowHotfixPush: true`（允许热修复直推）、`authorization`（授权短语哈希）、`hotfix.verifyCommand`（热修复验证命令）和 `remote`（远端名），并生成 Rulesets bypass（规则集绕过权限）建议。

跳转规则：继续 cleanup（清理）场景。

## 场景：配置 cleanup（清理）行为

固定问题：GitHub（代码托管平台）是否也启用 auto-delete head branch（自动删除源分支）？

固定选项：
- `false`: 由 PR Flow cleanup（清理）命令负责。
- `true`: 输出职责重叠 warning（警告）。

选择后果：写入 `setup.github.autoDeleteHeadBranch`（GitHub 自动删除源分支建议），不作为运行命令输入。

跳转规则：继续 GitHub setup suggestions（GitHub 配置建议）场景。

## 场景：GitHub setup suggestions（GitHub 配置建议）

固定问题：需要哪些远端规则建议？

固定选项：
- protected branches（受保护分支）。
- required checks（必需检查）。
- required review（必需审查）。
- allowed merge methods（允许合并方式）。
- Rulesets bypass（规则集绕过权限）。

选择后果：只写入 `setup.github`（GitHub 配置建议），complete、cleanup、hotfix、tweak 和 diagnose（收尾、清理、热修复、小改、诊断）不得消费。

跳转规则：继续最终写入确认。

## 场景：最终写入确认

固定问题：是否确认写入 `.pr-flow/config.yaml`、`.pr-flow/pr-template.md` 和 `.pr-flow/.gitignore`？

固定选项：
- `yes`: 仅在 validate（校验）没有 error（错误）时写入。
- `no`: 停止，不写入。

选择后果：用户沉默 MUST NOT 被视为确认。

跳转规则：`yes` 运行 init（初始化）写入；`no` 停止。
```

Create `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`:

```markdown
# PR Flow Init Config Draft

## 场景：运行配置

草案 MUST 使用 `defaults`（默认配置）加 `branches`（分支覆盖）。

```yaml
defaults:
  baseBranch: main
  mergeStrategy: merge
  reviewGate:
    mode: github
    evidencePath: .pr-flow/review-pass.json
  hotfix:
    verifyCommand: python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full
  wait:
    timeoutSeconds: 600
    pollSeconds: 15
  pr:
    bodyTemplatePath: .pr-flow/pr-template.md
    requiredSections:
      - Summary
      - Scope
      - Verification
      - Risk
      - Rollback
branches:
  main:
    remote: origin
    allowHotfixPush: false
```

## 场景：GitHub setup suggestions（GitHub 配置建议）

`setup.github`（GitHub 配置建议）MAY include protected branches（受保护分支）、required checks（必需检查）、required review（必需审查）、allowed merge methods（允许合并方式）、auto-delete head branch（自动删除源分支）和 Rulesets bypass（规则集绕过权限）。

`setup.github`（GitHub 配置建议）MUST NOT be consumed by diagnose、complete、cleanup、hotfix or tweak（诊断、收尾、清理、热修复、小改）。
```

Create `plugins/pr-flow/skills/pr-flow-init/references/validation.md`:

```markdown
# PR Flow Init Validation

## validate（校验）输出

- error（错误）：配置不可用，init（初始化）必须停止且不写入。
- warning（警告）：配置可写入，但存在流程风险。
- setup suggestion（配置建议）：需要用户或 agent（代理）另行处理的 GitHub（代码托管平台）或环境事项。

## 依赖矩阵

| 场景 | validate（校验）规则 |
| --- | --- |
| hotfix（热修复） | `allowHotfixPush: true` 要求 `authorization.phraseHashAlgorithm: md5`、非空 `authorization.phraseHash`、非空 `hotfix.verifyCommand`、非空 `remote`，并输出 Rulesets bypass（规则集绕过权限）建议。 |
| review gate（审查门禁） | `github` 或 `dual` 输出 required review（必需审查）建议；`local` 或 `dual` 要求 `evidencePath`（证据路径）并输出 `review-pass.json`（审查通过文件）契约建议。 |
| checks（检查） | `wait`（等待）只控制等待；required checks（必需检查）只作为 GitHub Rulesets（GitHub 规则集）建议。 |
| merge strategy（合并方式） | `merge`、`squash`、`rebase` 输出对应 GitHub（代码托管平台）allowed merge method（允许合并方式）建议。 |
| cleanup（清理） | auto-delete head branch（自动删除源分支）和 PR Flow cleanup（清理）同时存在时输出 warning（警告）。 |
| tweak（小改） | 只跳过插件内 review gate（审查门禁），不得声称绕过远端 required review（必需审查）。 |
| fast/full verify（快速/完整验证） | full verify（完整验证）只作为显式 `hotfix.verifyCommand`（热修复验证命令）或 PR CI（拉取请求持续集成）建议，不从证据路径推断。 |

## 写入摘要

init（初始化）写入后只说明本地文件路径和 GitHub（代码托管平台）建议摘要，不声明远端已配置。
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_skill_uses_progressive_disclosure_references -q
```

Expected: PASS（通过）。

- [ ] **Step 6: Commit（提交）**

```bash
git add plugins/pr-flow/skills/pr-flow-init/SKILL.md plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md plugins/pr-flow/skills/pr-flow-init/references/config-draft.md plugins/pr-flow/skills/pr-flow-init/references/validation.md tests/test_pr_flow_cli.py
git commit -m "test: 锁定 pr-flow-init 渐进式披露契约"
```

### Task 2: 增加 validate（校验）只读命令和结构化输出

**Files:**
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Test: `tests/test_pr_flow_cli.py`

- [ ] **Step 1: 写 validate（校验）成功测试，确认只读且不调用 GitHub API（GitHub 接口）**

Add:

```python
def write_config_draft(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")


def valid_pr_flow_config() -> dict:
    return {
        "defaults": {
            "baseBranch": "main",
            "mergeStrategy": "merge",
            "reviewGate": {"mode": "github", "evidencePath": ".pr-flow/review-pass.json"},
            "hotfix": {"verifyCommand": "python -m pytest"},
            "wait": {"timeoutSeconds": 600, "pollSeconds": 15},
        },
        "branches": {"main": {"remote": "origin", "allowHotfixPush": False}},
        "setup": {"github": {"requiredReviews": True, "allowedMergeMethods": ["merge"]}},
    }


def test_validate_reads_only_provided_config_and_reports_suggestions(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    draft = tmp_path / "draft.yaml"
    write_config_draft(draft, valid_pr_flow_config())

    result = run("validate", "--project", str(project), "--config", str(draft))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: validation_passed" in result.stdout
    assert "setup suggestion:" in result.stdout
    assert not (project / ".pr-flow" / "config.yaml").exists()
    assert "gh api" not in result.stdout
```

- [ ] **Step 2: 写 validate（校验）错误测试**

Add:

```python
def test_validate_reports_errors_for_missing_core_shape(tmp_path: Path) -> None:
    draft = tmp_path / "draft.yaml"
    write_config_draft(draft, {"defaults": {"reviewGate": {"mode": "local"}}, "branches": {}})

    result = run("validate", "--config", str(draft))

    assert result.returncode == 1
    assert "status: validation_failed" in result.stdout
    assert "error: defaults.baseBranch missing" in result.stdout
    assert "error: branches must contain at least one branch" in result.stdout
    assert "error: defaults.reviewGate.evidencePath missing" in result.stdout
```

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_validate_reads_only_provided_config_and_reports_suggestions tests/test_pr_flow_cli.py::test_validate_reports_errors_for_missing_core_shape -q
```

Expected: FAIL（失败），因为 `validate`（校验）命令不存在。

- [ ] **Step 4: 加最小 validate（校验）实现**

In `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`, change:

```python
COMMANDS = ("diagnose", "init", "validate", "complete", "cleanup", "hotfix", "tweak")
```

Add:

```python
VALID_REVIEW_GATE_MODES = {"github", "local", "dual", "skip"}
VALID_MERGE_STRATEGIES = {"merge", "squash", "rebase"}


def load_config_file(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return data


def add_issue(issues: list[dict[str, str]], level: str, message: str) -> None:
    issues.append({"level": level, "message": message})


def validate_config(config: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    defaults = config.get("defaults")
    branches = config.get("branches")
    defaults = defaults if isinstance(defaults, dict) else {}
    branches = branches if isinstance(branches, dict) else {}

    if not defaults.get("baseBranch"):
        add_issue(issues, "error", "defaults.baseBranch missing")
    if not branches:
        add_issue(issues, "error", "branches must contain at least one branch")

    merge_strategy = defaults.get("mergeStrategy", "merge")
    if merge_strategy not in VALID_MERGE_STRATEGIES:
        add_issue(issues, "error", f"defaults.mergeStrategy unsupported: {merge_strategy}")
    else:
        add_issue(issues, "setup suggestion", f"enable GitHub merge method: {merge_strategy}")

    review_gate = defaults.get("reviewGate")
    review_gate = review_gate if isinstance(review_gate, dict) else {}
    review_mode = review_gate.get("mode", "github")
    if review_mode not in VALID_REVIEW_GATE_MODES:
        add_issue(issues, "error", f"defaults.reviewGate.mode unsupported: {review_mode}")
    if review_mode in {"github", "dual"}:
        add_issue(issues, "setup suggestion", "configure GitHub required review")
    if review_mode in {"local", "dual"}:
        if not review_gate.get("evidencePath"):
            add_issue(issues, "error", "defaults.reviewGate.evidencePath missing")
        add_issue(issues, "setup suggestion", "review-pass.json must include status, base_ref, head_ref, diff_fingerprint and blocking_findings")

    setup = config.get("setup")
    github_setup = setup.get("github") if isinstance(setup, dict) else None
    github_setup = github_setup if isinstance(github_setup, dict) else {}
    if github_setup.get("requiredChecks"):
        add_issue(issues, "setup suggestion", "configure GitHub Rulesets required checks")
    if github_setup.get("autoDeleteHeadBranch"):
        add_issue(issues, "warning", "GitHub auto-delete head branch overlaps with pr-flow cleanup")

    hotfix_defaults = defaults.get("hotfix")
    hotfix_defaults = hotfix_defaults if isinstance(hotfix_defaults, dict) else {}
    authorization = config.get("authorization")
    authorization = authorization if isinstance(authorization, dict) else {}
    for branch_name, branch_config in branches.items():
        if not isinstance(branch_config, dict) or branch_config.get("allowHotfixPush") is not True:
            continue
        if authorization.get("phraseHashAlgorithm") != "md5":
            add_issue(issues, "error", "authorization.phraseHashAlgorithm must be md5")
        if not authorization.get("phraseHash"):
            add_issue(issues, "error", "authorization.phraseHash missing")
        branch_hotfix = branch_config.get("hotfix")
        branch_hotfix = branch_hotfix if isinstance(branch_hotfix, dict) else {}
        verify_command = branch_hotfix.get("verifyCommand") or hotfix_defaults.get("verifyCommand")
        if not verify_command:
            add_issue(issues, "error", f"branches.{branch_name}.hotfix.verifyCommand missing")
        if not branch_config.get("remote"):
            add_issue(issues, "error", f"branches.{branch_name}.remote missing")
        add_issue(issues, "setup suggestion", f"configure GitHub Rulesets bypass for {branch_name}")

    add_issue(issues, "setup suggestion", "tweak only skips the plugin review gate; it does not bypass GitHub required review")
    add_issue(issues, "setup suggestion", "full verify is only explicit hotfix.verifyCommand or PR CI configuration")
    return issues


def validation_has_errors(issues: list[dict[str, str]]) -> bool:
    return any(issue["level"] == "error" for issue in issues)


def print_validation(issues: list[dict[str, str]]) -> None:
    for issue in issues:
        print(f"{issue['level']}: {issue['message']}")


def run_validate(args: argparse.Namespace) -> int:
    config = load_config_file(args.config)
    issues = validate_config(config)
    if validation_has_errors(issues):
        print("status: validation_failed")
        print_validation(issues)
        return 1
    print("status: validation_passed")
    print_validation(issues)
    return 0
```

Update parser:

```python
if command in {"diagnose", "init", "complete", "tweak"}:
    subparser.add_argument("--project", type=Path, required=True)
if command == "validate":
    subparser.add_argument("--project", type=Path)
    subparser.add_argument("--config", type=Path, required=True)
```

Update `main`:

```python
if args.command == "validate":
    return run_validate(args)
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_validate_reads_only_provided_config_and_reports_suggestions tests/test_pr_flow_cli.py::test_validate_reports_errors_for_missing_core_shape -q
```

Expected: PASS（通过）。

- [ ] **Step 6: Commit（提交）**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "feat: 添加 pr-flow 配置只读校验"
```

### Task 3: 覆盖 hotfix（热修复）/review gate（审查门禁）/cleanup（清理）/tweak（小改）依赖矩阵

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [ ] **Step 1: 写参数化矩阵测试**

Add:

```python
@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda config: (
                config["branches"]["main"].update({"allowHotfixPush": True}),
                config.pop("authorization", None),
            ),
            "error: authorization.phraseHashAlgorithm must be md5",
        ),
        (
            lambda config: config["defaults"].update({"reviewGate": {"mode": "local"}}),
            "error: defaults.reviewGate.evidencePath missing",
        ),
        (
            lambda config: config["setup"]["github"].update({"autoDeleteHeadBranch": True}),
            "warning: GitHub auto-delete head branch overlaps with pr-flow cleanup",
        ),
        (
            lambda config: config["setup"]["github"].update({"requiredChecks": ["ci"]}),
            "setup suggestion: configure GitHub Rulesets required checks",
        ),
        (
            lambda config: config["defaults"].update({"mergeStrategy": "squash"}),
            "setup suggestion: enable GitHub merge method: squash",
        ),
    ],
)
def test_validate_dependency_matrix(tmp_path: Path, mutate, expected: str) -> None:
    config = valid_pr_flow_config()
    config["authorization"] = {
        "phraseHashAlgorithm": "md5",
        "phraseHash": hashlib.md5(HOTFIX_PHRASE.encode("utf-8")).hexdigest(),
    }
    mutate(config)
    draft = tmp_path / "draft.yaml"
    write_config_draft(draft, config)

    result = run("validate", "--config", str(draft))

    assert expected in result.stdout
```

Add:

```python
def test_validate_setup_github_is_not_runtime_config(tmp_path: Path) -> None:
    config = valid_pr_flow_config()
    config["setup"]["github"] = {
        "requiredChecks": ["ci"],
        "requiredReviews": True,
        "allowedMergeMethods": ["merge"],
        "autoDeleteHeadBranch": True,
    }
    draft = tmp_path / "draft.yaml"
    write_config_draft(draft, config)

    result = run("validate", "--config", str(draft))

    assert result.returncode == 0
    assert "setup suggestion: configure GitHub Rulesets required checks" in result.stdout
    assert "warning: GitHub auto-delete head branch overlaps with pr-flow cleanup" in result.stdout
    assert "setup.github consumed" not in result.stdout
```

- [ ] **Step 2: 运行测试确认失败或暴露缺口**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_validate_dependency_matrix tests/test_pr_flow_cli.py::test_validate_setup_github_is_not_runtime_config -q
```

Expected: FAIL（失败）或 PASS（通过）；如果 FAIL（失败），只补 `validate_config`（校验配置）遗漏规则。

- [ ] **Step 3: 补最小遗漏规则**

Only edit `validate_config`（校验配置）. Keep rules as issue strings; do not add classes（类） or schema framework（结构校验框架）.

Use these exact issue messages when missing:

```python
add_issue(issues, "setup suggestion", "configure GitHub Rulesets required checks")
add_issue(issues, "warning", "GitHub auto-delete head branch overlaps with pr-flow cleanup")
add_issue(issues, "setup suggestion", "tweak only skips the plugin review gate; it does not bypass GitHub required review")
add_issue(issues, "setup suggestion", "full verify is only explicit hotfix.verifyCommand or PR CI configuration")
```

- [ ] **Step 4: 运行矩阵测试确认通过**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_validate_dependency_matrix tests/test_pr_flow_cli.py::test_validate_setup_github_is_not_runtime_config -q
```

Expected: PASS（通过）。

- [ ] **Step 5: Commit（提交）**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "test: 覆盖 pr-flow 初始化依赖矩阵"
```

### Task 4: 改 init（初始化）为只写已确认配置并阻止 validate error（错误）写入

**Files:**
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Test: `tests/test_pr_flow_cli.py`

- [ ] **Step 1: 写 confirmed config（已确认配置）写入测试**

Replace old `test_init_creates_config_template_and_gitignore` with:

```python
def test_init_writes_confirmed_config_template_and_gitignore(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    draft = tmp_path / "confirmed.yaml"
    write_config_draft(draft, valid_pr_flow_config())

    result = run("init", "--project", str(project), "--config", str(draft))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: initialized" in result.stdout
    assert "GitHub setup suggestion" in result.stdout

    config = yaml.safe_load((project / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))
    assert config["defaults"]["baseBranch"] == "main"
    assert config["branches"]["main"]["remote"] == "origin"
    assert config["setup"]["github"]["requiredReviews"] is True
    template = (project / ".pr-flow" / "pr-template.md").read_text(encoding="utf-8")
    for section in ["Summary", "Scope", "Verification", "Risk", "Rollback"]:
        assert f"## {section}" in template
    assert (project / ".pr-flow" / ".gitignore").read_text(encoding="utf-8") == "/runs/\n/last-status.json\n"
```

- [ ] **Step 2: 写旧默认调用拒绝测试**

Add:

```python
def test_init_without_confirmed_config_does_not_write_defaults(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run("init", "--project", str(project), "--base-branch", "main")

    assert result.returncode == 2
    assert "confirmed config required" in result.stdout
    assert not (project / ".pr-flow" / "config.yaml").exists()
    assert not (project / ".pr-flow" / "pr-template.md").exists()
    assert not (project / ".pr-flow" / ".gitignore").exists()
```

- [ ] **Step 3: 写 validate error（错误）阻止写入测试**

Add:

```python
def test_init_validation_errors_block_all_writes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    draft = tmp_path / "bad.yaml"
    write_config_draft(draft, {"defaults": {"reviewGate": {"mode": "local"}}, "branches": {}})

    result = run("init", "--project", str(project), "--config", str(draft))

    assert result.returncode == 1
    assert "status: validation_failed" in result.stdout
    assert not (project / ".pr-flow" / "config.yaml").exists()
    assert not (project / ".pr-flow" / "pr-template.md").exists()
    assert not (project / ".pr-flow" / ".gitignore").exists()
```

- [ ] **Step 4: 运行测试确认失败**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_init_writes_confirmed_config_template_and_gitignore tests/test_pr_flow_cli.py::test_init_without_confirmed_config_does_not_write_defaults tests/test_pr_flow_cli.py::test_init_validation_errors_block_all_writes -q
```

Expected: FAIL（失败），因为 init（初始化）仍写默认配置。

- [ ] **Step 5: 改 init（初始化）最小实现**

Replace `run_init` with:

```python
def run_init(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    if args.config is None:
        print("status: confirmed_config_required")
        print("confirmed config required: use pr-flow-init Skill and pass --config <path>")
        return 2

    config = load_config_file(args.config)
    issues = validate_config(config)
    if validation_has_errors(issues):
        print("status: validation_failed")
        print_validation(issues)
        return 1

    pr_flow_dir = project / ".pr-flow"
    pr_flow_dir.mkdir(parents=True, exist_ok=True)
    (pr_flow_dir / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    write_text_if_missing(pr_flow_dir / "pr-template.md", PR_TEMPLATE)
    write_text_if_missing(pr_flow_dir / ".gitignore", PR_FLOW_GITIGNORE)

    print("status: initialized")
    for issue in issues:
        if issue["level"] == "setup suggestion":
            print(f"GitHub setup suggestion: {issue['message']}")
    return 0
```

Update parser:

```python
if command == "init":
    subparser.add_argument("--base-branch", default=None)
    subparser.add_argument("--config", type=Path)
```

- [ ] **Step 6: 更新测试 helper（辅助函数）摆脱旧默认 init（初始化）**

Add:

```python
def write_confirmed_pr_flow_config(project: Path, config: dict | None = None) -> None:
    draft = project.parent / f"{project.name}-confirmed-pr-flow.yaml"
    write_config_draft(draft, config or valid_pr_flow_config())
    result = run("init", "--project", str(project), "--config", str(draft))
    assert result.returncode == 0, result.stdout + result.stderr
```

Replace helper calls:

```python
assert run("init", "--project", str(project)).returncode == 0
```

with:

```python
write_confirmed_pr_flow_config(project)
```

For hotfix（热修复） helper（辅助函数）, build config first and call `write_confirmed_pr_flow_config(project, config)`.

- [ ] **Step 7: 运行 init（初始化）相关测试确认通过**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_init_writes_confirmed_config_template_and_gitignore tests/test_pr_flow_cli.py::test_init_without_confirmed_config_does_not_write_defaults tests/test_pr_flow_cli.py::test_init_validation_errors_block_all_writes tests/test_pr_flow_cli.py::test_init_does_not_call_gh_api -q
```

Expected: PASS（通过）。

- [ ] **Step 8: Commit（提交）**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "feat: 只允许 pr-flow init 写入已确认配置"
```

### Task 5: 固定 Plugin（插件）/Skill（技能）入口按用户场景组织

**Files:**
- Test: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/.codex-plugin/plugin.json`
- Modify: `plugins/pr-flow/.claude-plugin/plugin.json`
- Modify: `plugins/pr-flow/skills/pr-flow/SKILL.md`
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/validation.md`

- [ ] **Step 1: 写内容组织测试**

Add:

```python
def test_pr_flow_init_content_is_organized_by_user_scenario() -> None:
    init_dir = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-init"
    texts = [
        (init_dir / "SKILL.md").read_text(encoding="utf-8"),
        (init_dir / "references" / "questionnaire.md").read_text(encoding="utf-8"),
        (init_dir / "references" / "config-draft.md").read_text(encoding="utf-8"),
        (init_dir / "references" / "validation.md").read_text(encoding="utf-8"),
    ]
    combined = "\n".join(texts)

    for scenario in [
        "初次启用 PR Flow",
        "review gate",
        "hotfix",
        "cleanup",
        "GitHub setup suggestions",
        "最终写入确认",
    ]:
        assert scenario in combined
    assert "固定问题" in combined
    assert "固定选项" in combined
    assert "选择后果" in combined
    assert "跳转规则" in combined


def test_pr_flow_plugin_init_entrypoints_route_to_pr_flow_init() -> None:
    paths = [
        REPO_ROOT / "plugins" / "pr-flow" / ".codex-plugin" / "plugin.json",
        REPO_ROOT / "plugins" / "pr-flow" / ".claude-plugin" / "plugin.json",
        REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow" / "SKILL.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "pr-flow-init" in text
        assert "初始化" in text or "init" in text
```

- [ ] **Step 2: 运行测试确认失败或找出缺口**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_content_is_organized_by_user_scenario tests/test_pr_flow_cli.py::test_pr_flow_plugin_init_entrypoints_route_to_pr_flow_init -q
```

Expected: FAIL（失败） if entrypoints（入口） do not mention `pr-flow-init`（初始化技能） clearly.

- [ ] **Step 3: 最小更新入口描述**

Only update init（初始化）相关描述 or routing（路由） text. Do not reorganize complete、cleanup、hotfix or tweak（收尾、清理、热修复、小改） Skill（技能）内容 unless the text directly describes init（初始化）.

Required wording to include somewhere visible in each relevant entrypoint（入口）:

```text
pr-flow-init 初始化 PR Flow（拉取请求流程）配置：agent（代理）问答、配置草案、只读 validate（校验）和用户确认后本地写入。
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_content_is_organized_by_user_scenario tests/test_pr_flow_cli.py::test_pr_flow_plugin_init_entrypoints_route_to_pr_flow_init -q
```

Expected: PASS（通过）。

- [ ] **Step 5: Commit（提交）**

```bash
git add plugins/pr-flow/.codex-plugin/plugin.json plugins/pr-flow/.claude-plugin/plugin.json plugins/pr-flow/skills/pr-flow/SKILL.md plugins/pr-flow/skills/pr-flow-init/references tests/test_pr_flow_cli.py
git commit -m "docs: 按用户场景组织 pr-flow init 入口"
```

### Task 6: 从 Skill（技能）入口到写入的端到端回归

**Files:**
- Test: `tests/test_pr_flow_cli.py`

- [ ] **Step 1: 写端到端回归测试**

Add:

```python
def test_pr_flow_init_end_to_end_from_skill_to_confirmed_write(tmp_path: Path) -> None:
    skill_dir = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-init"
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    questionnaire = (skill_dir / "references" / "questionnaire.md").read_text(encoding="utf-8")
    config_draft = (skill_dir / "references" / "config-draft.md").read_text(encoding="utf-8")
    validation = (skill_dir / "references" / "validation.md").read_text(encoding="utf-8")
    assert "references/questionnaire.md" in skill_text
    assert "固定问题" in questionnaire
    assert "setup.github" in config_draft
    assert "error（错误）" in validation

    project = tmp_path / "project"
    project.mkdir()
    draft = tmp_path / "confirmed.yaml"
    config = valid_pr_flow_config()
    config["setup"]["github"]["requiredChecks"] = ["ci"]
    write_config_draft(draft, config)

    validate_result = run("validate", "--project", str(project), "--config", str(draft))
    assert validate_result.returncode == 0, validate_result.stdout + validate_result.stderr
    assert "status: validation_passed" in validate_result.stdout

    init_result = run("init", "--project", str(project), "--config", str(draft))
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr
    assert (project / ".pr-flow" / "config.yaml").is_file()
    assert (project / ".pr-flow" / "pr-template.md").is_file()
    assert (project / ".pr-flow" / ".gitignore").is_file()

    combined_output = validate_result.stdout + init_result.stdout
    for forbidden in ["status: cleanup_complete", "status: hotfix_complete", "ready_to_complete", "gh api"]:
        assert forbidden not in combined_output
```

- [ ] **Step 2: 运行端到端测试确认通过**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_end_to_end_from_skill_to_confirmed_write -q
```

Expected: PASS（通过）。

- [ ] **Step 3: Commit（提交）**

```bash
git add tests/test_pr_flow_cli.py
git commit -m "test: 增加 pr-flow init 端到端回归"
```

### Task 7: 聚焦验证和 OpenSpec（开放规格）严格校验

**Files:**
- No code changes expected（预期不改代码）

- [ ] **Step 1: 运行 PR Flow（拉取请求流程）聚焦测试**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected: PASS（通过）。

- [ ] **Step 2: 运行 OpenSpec（开放规格）严格校验**

Run:

```bash
openspec validate refactor-pr-flow-init --strict
```

Expected: PASS（通过）。

- [ ] **Step 3: 若 OpenSpec（开放规格）命令不可用，记录替代验证**

Run:

```bash
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_skill_uses_progressive_disclosure_references tests/test_pr_flow_cli.py::test_pr_flow_init_end_to_end_from_skill_to_confirmed_write -q
```

Expected: PASS（通过）。在最终说明中写明 `openspec validate`（开放规格校验）不可用和错误输出。

- [ ] **Step 4: 检查无意改动范围**

Run:

```bash
git diff --name-only
```

Expected output includes only:

```text
plugins/pr-flow/.claude-plugin/plugin.json
plugins/pr-flow/.codex-plugin/plugin.json
plugins/pr-flow/skills/pr-flow/SKILL.md
plugins/pr-flow/skills/pr-flow-init/SKILL.md
plugins/pr-flow/skills/pr-flow-init/references/config-draft.md
plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md
plugins/pr-flow/skills/pr-flow-init/references/validation.md
plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py
tests/test_pr_flow_cli.py
```

- [ ] **Step 5: Final commit（最终提交） if previous tasks left verification-only changes**

```bash
git status --short
```

Expected: clean（干净） or only intentional changes already committed.

## Self-Review Checklist

- [ ] Spec（规格）覆盖：计划覆盖 `pr-flow-init` Skill（初始化技能）渐进式披露、三个 references（参考文件）、只读 validate（校验）、validate error（错误）阻止 init（初始化）写入、已确认配置写入、旧默认 init（初始化）拒绝、`setup.github`（GitHub 配置建议）不被运行命令消费、依赖矩阵、端到端回归。
- [ ] 无新依赖：只用现有 Python（编程语言）、argparse（命令行参数解析）、PyYAML（YAML 配置读取）和 pytest（测试框架）。
- [ ] 无不必要抽象：validate（校验）用简单 list（列表） issue（问题）结构，不新增 schema（结构定义）库或 class（类）。
- [ ] 运行边界：init（初始化）不做终端交互、不调用 GitHub API（GitHub 接口）、不运行 diagnose、complete、cleanup、hotfix 或 tweak（诊断、收尾、清理、热修复、小改）。
- [ ] 写入边界：init（初始化）只写 `.pr-flow/config.yaml`、`.pr-flow/pr-template.md`、`.pr-flow/.gitignore`。
