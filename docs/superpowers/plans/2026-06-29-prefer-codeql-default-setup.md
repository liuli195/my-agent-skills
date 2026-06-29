---
change: prefer-codeql-default-setup
design-doc: docs/superpowers/specs/2026-06-29-prefer-codeql-default-setup-design.md
base-ref: 2ff3172c4141ea4349a9c0280efb3f76beb89115
---

# Prefer CodeQL Default Setup（优先 CodeQL 默认配置）Implementation Plan（实施计划）

> **For agentic workers（代理执行者）:** REQUIRED SUB-SKILL（必需子技能）: Use superpowers:executing-plans（执行计划） to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal（目标）:** 让 PR Flow init（拉取请求流程初始化）默认引导 CodeQL Default setup（CodeQL 默认配置），不再把 CodeQL（代码查询扫描）当作 PR status check（拉取请求状态检查）选项。

**Architecture（实现方式）:** 复用现有 `setup.github.codeScanning`（代码扫描配置）开关，不新增 `defaultSetup` 或等价字段。`validate`（校验）只读本地配置和文件，固定输出 CodeQL Default setup（CodeQL 默认配置）远端待办，不调用 `gh` CLI（GitHub 命令行工具）或 GitHub API（GitHub 接口）。

**Tech Stack（技术栈）:** Python（编程语言）、pytest（测试框架）、YAML（配置格式）、OpenSpec（开放规格）、PR Flow（拉取请求流程）。

---

## 文件结构

- Modify: `tests/test_pr_flow_cli.py`
  - 负责先写失败断言，覆盖问答模板、配置草案、`validate`（校验）输出、不调用 `gh` CLI（GitHub 命令行工具）、不新增 `defaultSetup` 字段、端到端回归。
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`
  - 负责 CodeQL security check（CodeQL 安全检查）和 PR status checks（拉取请求状态检查）的用户问答文案。
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`
  - 负责配置草案摘要里的 GitHub（代码托管平台）远端待办表述。
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/validation.md`
  - 负责 `validate`（校验）输出说明和依赖矩阵。
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
  - 负责 `setup.github.codeScanning`（代码扫描配置）到 remote task（远端待办）的只读校验输出。

## Task 1: 写失败测试

**Files（文件）:**
- Modify: `tests/test_pr_flow_cli.py`

- [x] **Step 1: 更新 questionnaire（问答模板）断言**

在 `test_pr_flow_init_questionnaire_uses_latest_flow` 中，把 CodeQL（代码查询扫描）选项断言改成 Default setup（默认配置）语义：

```python
assert codeql_options == [
    "- 开启：启用 CodeQL Default setup（CodeQL 默认配置）；在 GitHub Rulesets（GitHub 规则集）中配置 `Require code scanning results`（要求代码扫描结果），选择 `CodeQL` 作为 code scanning tool（代码扫描工具），阈值采用 GitHub 默认阈值。",
    "- 不开启：不生成 CodeQL（代码扫描工具）远端待办。",
]
assert "开启：继续 PR status checks（拉取请求状态检查）场景；后续只展示非安全扫描 check name（检查名称）" in codeql_section
assert "Analyze Python" not in codeql_section
assert "Analyze (python)" not in codeql_section
assert "Analyze (actions)" not in codeql_section
assert "CodeQL scan producer" not in codeql_section
```

同一测试里的 `pr_status_section` 断言改成禁止 CodeQL（代码查询扫描）相关状态检查选项：

```python
for forbidden in ["Analyze Python", "Analyze (python)", "Analyze (actions)", "`CodeQL` status check"]:
    assert forbidden not in pr_status_section
assert "非安全扫描 check name（检查名称）" in pr_status_section
assert "CodeQL security gate（CodeQL 安全门禁）默认由 `Require code scanning results`（要求代码扫描结果）表达" in pr_status_section
```

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_questionnaire_uses_latest_flow -q
```

Expected（预期）: FAIL（失败），因为文档仍包含 `Analyze Python` 和 `创建或启用 CodeQL scan producer`。

- [x] **Step 2: 更新 config draft（配置草案）和 validation（校验说明）断言**

在 `test_pr_flow_init_draft_and_validation_are_user_readable` 中替换 CodeQL（代码查询扫描）断言：

```python
for text in [config_draft, validation]:
    assert "启用 CodeQL Default setup（CodeQL 默认配置）" in text
    assert "Require code scanning results" in text
    assert "CodeQL" in text
    assert "GitHub 默认阈值" in text
    assert "CodeQL scan producer" not in text
    assert "defaultSetup" not in text
    assert "default_setup" not in text
```

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_draft_and_validation_are_user_readable -q
```

Expected（预期）: FAIL（失败），因为现有说明仍说 `CodeQL scan producer`。

- [x] **Step 3: 更新 validate（校验）输出测试**

把 `test_validate_reports_missing_codeql_scan_source` 改名为 `test_validate_reports_codeql_default_setup_tasks`，断言固定输出两个 remote tasks（远端待办）：

```python
assert "remote task: enable CodeQL Default setup" in result.stdout
assert "remote task: configure GitHub Rulesets CodeQL code scanning" in result.stdout
```

把 `test_validate_accepts_existing_codeql_workflow_source` 改名为 `test_validate_reports_codeql_default_setup_even_with_existing_codeql_workflow`，保留本地 `codeql-action` workflow（工作流），但断言仍输出 Default setup（默认配置）待办：

```python
assert result.returncode == 0, result.stdout + result.stderr
assert "remote task: enable CodeQL Default setup" in result.stdout
assert "remote task: configure GitHub Rulesets CodeQL code scanning" in result.stdout
```

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_validate_reports_codeql_default_setup_tasks tests/test_pr_flow_cli.py::test_validate_reports_codeql_default_setup_even_with_existing_codeql_workflow -q
```

Expected（预期）: FAIL（失败），因为当前 `validate`（校验）在已有本地 `codeql-action` workflow（工作流）时不会输出扫描来源待办，也不会输出 Default setup（默认配置）待办。

- [x] **Step 4: 增加 validate（校验）不调用 gh（GitHub 命令行工具）的测试**

新增测试：

```python
def test_validate_does_not_call_gh_cli_or_github_api(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    config = default_pr_flow_config_for_test()
    config["setup"] = {"github": {"codeScanning": {"tool": "CodeQL"}}}
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    gh_stub = CommandStub()
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(["validate", "--project", str(project), "--config", str(draft)], module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert gh_stub.calls == []
    assert "remote task: enable CodeQL Default setup" in result.stdout
```

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_validate_does_not_call_gh_cli_or_github_api -q
```

Expected（预期）: FAIL（失败），因为当前 `validate`（校验）还没有输出 Default setup（默认配置）待办。

- [x] **Step 5: 扩展端到端回归和字段禁用断言**

在 `test_pr_flow_init_end_to_end_from_skill_to_confirmed_write` 中把配置改成包含 CodeQL（代码查询扫描）开关：

```python
config["setup"] = {
    "github": {
        "requiredChecks": ["ci"],
        "requiredReview": True,
        "codeScanning": {"tool": "CodeQL"},
    }
}
```

在写入后增加字段约束：

```python
serialized = json.dumps(written, sort_keys=True)
for forbidden in ["defaultSetup", "default_setup", "codeqlDefaultSetup", "codeql_default_setup"]:
    assert forbidden not in serialized
assert written["setup"]["github"]["codeScanning"] == {"tool": "CodeQL"}
assert "remote task: enable CodeQL Default setup" in validate_result.stdout
```

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_end_to_end_from_skill_to_confirmed_write -q
```

Expected（预期）: FAIL（失败），因为 `validate`（校验）还没有输出 Default setup（默认配置）待办。

## Task 2: 更新 pr-flow-init（拉取请求流程初始化）文档

**Files（文件）:**
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`
- Modify: `plugins/pr-flow/skills/pr-flow-init/references/validation.md`

- [x] **Step 1: 更新 CodeQL security check（CodeQL 安全检查）场景**

在 `questionnaire.md` 中把开启选项和选择后果改成：

```markdown
- 开启：启用 CodeQL Default setup（CodeQL 默认配置）；在 GitHub Rulesets（GitHub 规则集）中配置 `Require code scanning results`（要求代码扫描结果），选择 `CodeQL` 作为 code scanning tool（代码扫描工具），阈值采用 GitHub 默认阈值。
```

```markdown
- 开启：只写入 `setup.github`（GitHub 配置建议）remote task（远端待办），包含启用 CodeQL Default setup（CodeQL 默认配置）和 Rulesets rule（规则集规则），不自动写 GitHub（代码托管平台）远端。
```

跳转规则改成：

```markdown
- 开启：继续 PR status checks（拉取请求状态检查）场景；后续只展示非安全扫描 check name（检查名称）。
- 不开启：继续 PR status checks（拉取请求状态检查）场景；不得展示 `Analyze Python`、`Analyze (python)`、`Analyze (actions)` 或 `CodeQL` 作为 CodeQL（代码扫描工具）相关 status check（状态检查）选项。
```

- [x] **Step 2: 更新 PR status checks（拉取请求状态检查）场景**

删除 `Analyze Python` 高级额外选项，保留非安全扫描检查：

```markdown
- 启用已检查到的非安全扫描 check name（检查名称）。
```

检查项展示规则保留 CodeQL（代码查询扫描）由 code scanning gate（代码扫描门禁）表达：

```markdown
- `Analyze Python`、`Analyze (python)`、`Analyze (actions)` 和 `CodeQL` 不得作为 CodeQL（代码扫描工具）相关 status check（状态检查）选项展示；CodeQL security gate（CodeQL 安全门禁）默认由 `Require code scanning results`（要求代码扫描结果）表达。
```

- [x] **Step 3: 更新 config draft（配置草案）和 validation（校验说明）**

在 `config-draft.md` 和 `validation.md` 中，把 CodeQL（代码查询扫描）远端待办统一改成：

```markdown
- 如启用 CodeQL security check（CodeQL 安全检查），启用 CodeQL Default setup（CodeQL 默认配置）；在 GitHub Rulesets（GitHub 规则集）中配置 `Require code scanning results`（要求代码扫描结果），选择 `CodeQL` 作为 code scanning tool（代码扫描工具），阈值采用 GitHub 默认阈值。
```

保留 `setup.github.codeScanning`（代码扫描配置）字段说明，不加入 `defaultSetup`、`default_setup` 或等价字段。

## Task 3: 更新 validate（校验）本地输出

**Files（文件）:**
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: 删除本地 workflow（工作流）影响 CodeQL（代码查询扫描）待办的逻辑**

删除 `has_codeql_workflow()`，并把 `validate_config()` 的 CodeQL（代码查询扫描）分支改成：

```python
if github.get("codeScanning"):
    add_issue(issues, "remote task", "enable CodeQL Default setup")
    add_issue(issues, "remote task", "configure GitHub Rulesets CodeQL code scanning")
```

不要新增 `defaultSetup`、`default_setup` 或等价配置字段。不要让 `run_validate()` 或 `validate_config()` 调用 `gh()`、`subprocess.run(["gh", ...])` 或 GitHub API（GitHub 接口）。

- [x] **Step 2: 跑 Task 1 的聚焦测试**

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_questionnaire_uses_latest_flow tests/test_pr_flow_cli.py::test_pr_flow_init_draft_and_validation_are_user_readable tests/test_pr_flow_cli.py::test_validate_reports_codeql_default_setup_tasks tests/test_pr_flow_cli.py::test_validate_reports_codeql_default_setup_even_with_existing_codeql_workflow tests/test_pr_flow_cli.py::test_validate_does_not_call_gh_cli_or_github_api tests/test_pr_flow_cli.py::test_pr_flow_init_end_to_end_from_skill_to_confirmed_write -q
```

Expected（预期）: PASS（通过）。

## Task 4: 验证与收尾

**Files（文件）:**
- Verify only（只验证）: `openspec/changes/prefer-codeql-default-setup/specs/pr-flow-plugin/spec.md`
- Verify only（只验证）: `openspec/changes/prefer-codeql-default-setup/tasks.md`

- [x] **Step 1: OpenSpec（开放规格）校验**

Run（运行）:

```powershell
openspec validate prefer-codeql-default-setup --strict
```

Expected（预期）: PASS（通过），change（变更）有效。

- [x] **Step 2: 聚焦测试**

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_questionnaire_uses_latest_flow tests/test_pr_flow_cli.py::test_pr_flow_init_draft_and_validation_are_user_readable tests/test_pr_flow_cli.py::test_validate_reports_codeql_default_setup_tasks tests/test_pr_flow_cli.py::test_validate_reports_codeql_default_setup_even_with_existing_codeql_workflow tests/test_pr_flow_cli.py::test_validate_does_not_call_gh_cli_or_github_api -q
```

Expected（预期）: PASS（通过）。

- [x] **Step 3: pr-flow-init（拉取请求流程初始化）到 validate/init（校验/初始化）写入端到端回归**

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_pr_flow_init_end_to_end_from_skill_to_confirmed_write -q
```

Expected（预期）: PASS（通过），并确认：

```python
assert written["setup"]["github"]["codeScanning"] == {"tool": "CodeQL"}
assert "defaultSetup" not in json.dumps(written, sort_keys=True)
assert "remote task: enable CodeQL Default setup" in validate_result.stdout
```

- [x] **Step 4: 按 Comet（彗星流程）收尾提交**

已按 Comet（彗星流程）收尾要求提交本地改动；不运行 `git push`（推送）、不创建 PR（拉取请求）。
