---
change: fix-pr-flow-pr-body
design-doc: docs/superpowers/specs/2026-06-30-fix-pr-flow-pr-body-design.md
base-ref: 8205bf9bb61e4bc3cafd743b19ca55e14f732671
archived-with: 2026-06-30-fix-pr-flow-pr-body
---

# PR Flow（拉取请求流程）PR Body（拉取请求正文）Implementation Plan（实施计划）

> **For agentic workers（代理工作者）：** REQUIRED SUB-SKILL（必需子技能）：Use `superpowers:subagent-driven-development`（子代理驱动开发，推荐）或 `superpowers:executing-plans`（执行计划）逐项实施。步骤使用 checkbox（复选框）语法跟踪。

**Goal（目标）：** 让 `complete`（收尾）和 `tweak`（小改）共用三节 PR body（拉取请求正文）生成、校验、写入和人工正文保护规则。

**Architecture（架构）：** 在 `pr_flow.py`（PR Flow 脚本）内增加一个小型共享 helper（辅助函数）组，集中处理模板读取、章节校验、HTML comment（HTML 注释）剥离、正文渲染和已有正文保护。`complete`（收尾）和 `tweak`（小改）在进入 push（推送）、PR（拉取请求）创建、checks（检查）和 merge（合并）前调用同一套逻辑；`diagnose`（诊断）只输出下一步命令和停止详情，不推断正文内容。

**Tech Stack（技术栈）：** Python（编程语言）标准库、PyYAML（配置解析库）、GitHub CLI（GitHub 命令行工具）、pytest（测试运行器）、OpenSpec（开放规格）。

archived-with: 2026-06-30-fix-pr-flow-pr-body
---

## File Structure（文件结构）

- Modify（修改）：`D:\My Project\my-agent-skills\tests\test_pr_flow_cli.py`
  - 增加 PR body（拉取请求正文）测试；更新现有 complete（收尾）和 tweak（小改）测试命令参数；让测试覆盖模板、正文参数、closing references（关闭引用）、已有正文保护和 diagnose（诊断）输出。
- Modify（修改）：`D:\My Project\my-agent-skills\plugins\pr-flow\skills\pr-flow\scripts\pr_flow.py`
  - 更新默认模板和配置；增加 PR body（拉取请求正文）helper（辅助函数）；更新 CLI（命令行界面）参数；调整 complete（收尾）、tweak（小改）、diagnose（诊断）和 lifecycle（生命周期）流程。
- Modify（修改）：`D:\My Project\my-agent-skills\plugins\pr-flow\skills\pr-flow-complete\SKILL.md`
  - 更新 complete（收尾）命令示例，显式传入 `--summary`、`--scope` 和 `--fixes`。
- Modify（修改）：`D:\My Project\my-agent-skills\plugins\pr-flow\skills\pr-flow-tweak\SKILL.md`
  - 更新 tweak（小改）命令示例，保留 `--reason`，同时显式传入 `--summary`、`--scope` 和 `--fixes`。

## Task 1（任务 1）：默认三节模板和正文参数门禁

**Files（文件）：**
- Modify（修改）：`D:\My Project\my-agent-skills\tests\test_pr_flow_cli.py`
- Modify（修改）：`D:\My Project\my-agent-skills\plugins\pr-flow\skills\pr-flow\scripts\pr_flow.py`

- [x] **Step 1（步骤 1）：Write the failing tests（编写失败测试）**

在 `tests/test_pr_flow_cli.py`（PR Flow 测试）中更新 `test_init_creates_config_template_and_gitignore`（初始化测试），并添加两个正文参数门禁测试：

```python
def test_init_creates_config_template_and_gitignore(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    draft = tmp_path / "confirmed.yaml"
    draft.write_text(
        yaml.safe_dump(default_pr_flow_config_for_test("main"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    result = run("init", "--project", str(project), "--config", str(draft))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: initialized" in result.stdout
    assert "GitHub remote task: configure GitHub required review" in result.stdout
    assert "GitHub Rulesets suggestion" not in result.stdout

    config = yaml.safe_load((project / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))
    assert config["defaults"]["baseBranch"] == "main"
    assert config["defaults"]["mergeStrategy"] == "merge"
    assert config["defaults"]["reviewGate"]["mode"] == "github"
    assert "evidencePath" not in config["defaults"]["reviewGate"]
    assert (
        config["defaults"]["hotfix"]["verifyCommand"]
        == "python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full"
    )
    assert config["defaults"]["wait"] == {"timeoutSeconds": 600, "pollSeconds": 15}
    assert config["defaults"]["pr"]["bodyTemplatePath"] == ".pr-flow/pr-template.md"
    assert config["defaults"]["pr"]["requiredSections"] == ["Summary", "Scope", "Closing References"]
    assert config["branches"]["main"]["remote"] == "origin"
    assert config["branches"]["main"]["allowHotfixPush"] is False

    template = (project / ".pr-flow" / "pr-template.md").read_text(encoding="utf-8")
    assert "## Summary" in template
    assert "## Scope" in template
    assert "## Closing References" in template
    assert "## Verification" not in template
    assert "## Risk" not in template
    assert "## Rollback" not in template
    assert "<!--" in template

    assert (project / ".pr-flow" / ".gitignore").read_text(encoding="utf-8") == "/runs/\n/last-status.json\n"


def test_complete_requires_summary_scope_before_auto_push_or_pr_create(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    gh_stub = CommandStub()
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(["complete", "--project", str(project)], module=module)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert git_stub.calls == []
    assert gh_stub.calls == []
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "complete"
    assert status["details"]["reason"] == "pr_body_required"
    assert status["details"]["missingArgs"] == ["--summary", "--scope"]
    assert "--summary" in status["details"]["nextCommand"]
    assert "--scope" in status["details"]["nextCommand"]


def test_tweak_requires_summary_scope_before_pr_sync(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    git_stub = CommandStub()
    gh_stub = CommandStub()
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(["tweak", "--project", str(project), "--reason", "small docs polish"], module=module)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert git_stub.calls == []
    assert gh_stub.calls == []
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "EXCEPTION_REQUIRED"
    assert status["command"] == "tweak"
    assert status["details"]["reason"] == "pr_body_required"
    assert status["details"]["missingArgs"] == ["--summary", "--scope"]
```

- [x] **Step 2（步骤 2）：Run tests to verify they fail（运行测试确认失败）**

Run（运行）：

```bash
python -m pytest tests/test_pr_flow_cli.py::test_init_creates_config_template_and_gitignore tests/test_pr_flow_cli.py::test_complete_requires_summary_scope_before_auto_push_or_pr_create tests/test_pr_flow_cli.py::test_tweak_requires_summary_scope_before_pr_sync -q
```

Expected（预期）：FAIL（失败），包含旧模板仍有 `Verification`（验证）等章节，且 `complete`（收尾）和 `tweak`（小改）没有 `pr_body_required`（正文必需）停止状态。

- [x] **Step 3（步骤 3）：Write minimal implementation（编写最小实现）**

在 `pr_flow.py`（PR Flow 脚本）中替换模板常量、默认配置和 CLI（命令行界面）参数，并在 `run_complete`（运行收尾）和 `run_tweak`（运行小改）入口最前面检查正文参数：

```python
PR_BODY_REQUIRED_SECTIONS = ("Summary", "Scope", "Closing References")
PR_VIEW_FIELDS = "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid"
BLOCKING_REVIEW_DECISIONS = {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}
SUPPORTED_REVIEW_GATE_MODES = {"github", "skip"}
PR_TEMPLATE = """## Summary

<!-- 用一句话说明本次 PR 的目的和主要变化。 -->

## Scope

<!-- 列出本次 PR 的影响范围，例如代码、测试、文档或配置。 -->

## Closing References

<!-- 写 Fixes #123；没有关闭的问题单时写 None。 -->
"""
PR_FLOW_GITIGNORE = "/runs/\n/last-status.json\n"
```

```python
def default_config(base_branch: str) -> dict:
    return {
        "defaults": {
            "baseBranch": base_branch,
            "mergeStrategy": "merge",
            "reviewGate": {"mode": "github"},
            "hotfix": {
                "verifyCommand": "python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full"
            },
            "wait": {"timeoutSeconds": 600, "pollSeconds": 15},
            "pr": {
                "bodyTemplatePath": ".pr-flow/pr-template.md",
                "requiredSections": list(PR_BODY_REQUIRED_SECTIONS),
            },
        },
        "branches": {
            base_branch: {
                "remote": "origin",
                "allowHotfixPush": False,
            },
        },
    }
```

```python
def pr_body_next_command(command: str, project: Path, args: argparse.Namespace) -> str:
    command_args = [
        sys.executable,
        "plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py",
        command,
        "--project",
        str(project),
    ]
    if command == "tweak":
        command_args.extend(["--reason", str(getattr(args, "reason", "") or "small docs polish")])
    command_args.extend(["--summary", str(getattr(args, "summary", "") or "说明本次 PR 的主要变化")])
    command_args.extend(["--scope", str(getattr(args, "scope", "") or "列出本次 PR 的影响范围")])
    for issue in getattr(args, "fixes", []) or []:
        command_args.extend(["--fixes", str(issue)])
    return " ".join(shlex.quote(part) for part in command_args)


def require_pr_body_args(project: Path, command: str, args: argparse.Namespace) -> tuple[str, str, list[str]]:
    summary = str(getattr(args, "summary", "") or "").strip()
    scope = str(getattr(args, "scope", "") or "").strip()
    fixes = [str(issue).strip() for issue in (getattr(args, "fixes", None) or []) if str(issue).strip()]
    missing = []
    if not summary:
        missing.append("--summary")
    if not scope:
        missing.append("--scope")
    if missing:
        raise PrFlowError(
            "pr_body_required",
            {
                "reason": "pr_body_required",
                "missingArgs": missing,
                "nextCommand": pr_body_next_command(command, project, args),
            },
        )
    return summary, scope, fixes
```

```python
def run_complete(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    try:
        config = load_config(project)
        require_pr_body_args(project, args.command, args)
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)
    except PrFlowError as exc:
        return stop(project, args.command, "EXCEPTION_REQUIRED", exc.reason, exc.details)
    return run_lifecycle(project, config, args.command)


def run_tweak(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    try:
        config = load_config(project)
        require_pr_body_args(project, args.command, args)
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)
    except PrFlowError as exc:
        return stop(project, args.command, "EXCEPTION_REQUIRED", exc.reason, exc.details)

    body = TWEAK_BODY_TEMPLATE.format(reason=args.reason)
    return run_lifecycle(
        project,
        config,
        args.command,
        skip_review_gate=True,
        before_checks=lambda pr: update_pr_body(project, pr, body),
    )
```

```python
if command in {"complete", "tweak"}:
    subparser.add_argument("--summary")
    subparser.add_argument("--scope")
    subparser.add_argument("--fixes", action="append", default=[])
if command == "tweak":
    subparser.add_argument("--reason")
```

- [x] **Step 4（步骤 4）：Run tests to verify they pass（运行测试确认通过）**

Run（运行）：

```bash
python -m pytest tests/test_pr_flow_cli.py::test_init_creates_config_template_and_gitignore tests/test_pr_flow_cli.py::test_complete_requires_summary_scope_before_auto_push_or_pr_create tests/test_pr_flow_cli.py::test_tweak_requires_summary_scope_before_pr_sync -q
```

Expected（预期）：PASS（通过）。

- [x] **Step 5（步骤 5）：Commit（提交）**

```bash
git add tests/test_pr_flow_cli.py plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py
git commit -m "test: 覆盖 PR body 参数门禁"
```

## Task 2（任务 2）：模板校验和统一正文渲染

**Files（文件）：**
- Modify（修改）：`D:\My Project\my-agent-skills\tests\test_pr_flow_cli.py`
- Modify（修改）：`D:\My Project\my-agent-skills\plugins\pr-flow\skills\pr-flow\scripts\pr_flow.py`

- [x] **Step 1（步骤 1）：Write the failing tests（编写失败测试）**

在 `tests/test_pr_flow_cli.py`（PR Flow 测试）中更新测试 helper（辅助函数）写入模板，并添加正文渲染与模板缺节测试：

```python
def write_complete_pr_flow_config(
    project: Path,
    *,
    review_mode: str = "github",
    merge_strategy: str = "merge",
    evidence_path: str | None = None,
) -> None:
    config_dir = project / ".pr-flow"
    config_dir.mkdir(parents=True, exist_ok=True)
    review_gate = {"mode": review_mode}
    if evidence_path is not None:
        review_gate["evidencePath"] = evidence_path
    config = {
        "defaults": {
            "baseBranch": "main",
            "mergeStrategy": merge_strategy,
            "reviewGate": review_gate,
            "wait": {"timeoutSeconds": 0, "pollSeconds": 0},
            "pr": {
                "bodyTemplatePath": ".pr-flow/pr-template.md",
                "requiredSections": ["Summary", "Scope", "Closing References"],
            },
        },
        "branches": {"main": {"remote": "origin"}},
    }
    (config_dir / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (config_dir / "pr-template.md").write_text(
        "## Summary\n\n<!-- summary guide -->\n\n"
        "## Scope\n\n<!-- scope guide -->\n\n"
        "## Closing References\n\n<!-- closing guide -->\n",
        encoding="utf-8",
    )


def expected_pr_body(summary: str = "修复 PR Flow 创建空正文 PR", scope: str = "更新 complete、tweak、diagnose 和测试", fixes: tuple[int, ...] = (98,)) -> str:
    references = "\n".join(f"Fixes #{issue}" for issue in fixes) if fixes else "None"
    return f"## Summary\n\n{summary}\n\n## Scope\n\n{scope}\n\n## Closing References\n\n{references}\n"


def test_complete_and_tweak_share_three_section_body_renderer(tmp_path: Path) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    config = yaml.safe_load((project / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))

    complete_body = module.render_pr_body(project, config, "修复 PR Flow 创建空正文 PR", "更新 complete、tweak、diagnose 和测试", ["98"])
    tweak_body = module.render_pr_body(project, config, "修复 PR Flow 创建空正文 PR", "更新 complete、tweak、diagnose 和测试", ["98"])

    assert complete_body == expected_pr_body()
    assert tweak_body == expected_pr_body()


def test_complete_rejects_missing_template_sections_before_pr_work(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    (project / ".pr-flow" / "pr-template.md").write_text("## Summary\n\n## Scope\n", encoding="utf-8")
    config = yaml.safe_load((project / ".pr-flow" / "config.yaml").read_text(encoding="utf-8"))
    config["defaults"]["pr"]["requiredSections"] = ["Summary", "Scope"]
    (project / ".pr-flow" / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    git_stub = CommandStub()
    gh_stub = CommandStub()
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "gh", gh_stub)

    result = invoke_pr_flow(
        [
            "complete",
            "--project",
            str(project),
            "--summary",
            "修复 PR Flow 创建空正文 PR",
            "--scope",
            "更新 complete、tweak、diagnose 和测试",
            "--fixes",
            "98",
        ],
        module=module,
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert git_stub.calls == []
    assert gh_stub.calls == []
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "pr_body_required"
    assert status["details"]["templatePath"] == str(project / ".pr-flow" / "pr-template.md")
    assert status["details"]["missingSections"] == ["Closing References"]
    assert "Add ## Closing References" in status["details"]["nextAction"]
```

- [x] **Step 2（步骤 2）：Run tests to verify they fail（运行测试确认失败）**

Run（运行）：

```bash
python -m pytest tests/test_pr_flow_cli.py::test_complete_and_tweak_share_three_section_body_renderer tests/test_pr_flow_cli.py::test_complete_rejects_missing_template_sections_before_pr_work -q
```

Expected（预期）：FAIL（失败），包含 `render_pr_body`（渲染正文）未定义或模板缺节未停止。

- [x] **Step 3（步骤 3）：Write minimal implementation（编写最小实现）**

在 `pr_flow.py`（PR Flow 脚本）增加 `re`（正则模块）导入和正文 helper（辅助函数）；然后让 `run_complete`（运行收尾）和 `run_tweak`（运行小改）调用 `render_pr_body`（渲染正文）：

```python
import re
```

```python
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
```

```python
def pr_body_config(config: dict[str, Any]) -> dict[str, Any]:
    defaults = defaults_from_config(config)
    pr_config = defaults.get("pr")
    return pr_config if isinstance(pr_config, dict) else {}


def pr_body_template_path(project: Path, config: dict[str, Any]) -> Path:
    template_path = pr_body_config(config).get("bodyTemplatePath")
    if not isinstance(template_path, str) or not template_path.strip():
        raise PrFlowError(
            "pr_body_required",
            {
                "reason": "pr_body_required",
                "templatePath": "",
                "missingSections": list(PR_BODY_REQUIRED_SECTIONS),
                "nextAction": "Set defaults.pr.bodyTemplatePath to .pr-flow/pr-template.md and include Summary, Scope, Closing References.",
            },
        )
    return (project / template_path).resolve()


def configured_required_sections(config: dict[str, Any]) -> list[str]:
    sections = pr_body_config(config).get("requiredSections")
    if not isinstance(sections, list):
        return []
    return [section for section in sections if isinstance(section, str)]


def validate_pr_body_template(project: Path, config: dict[str, Any]) -> Path:
    path = pr_body_template_path(project, config)
    try:
        template = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PrFlowError(
            "pr_body_required",
            {
                "reason": "pr_body_required",
                "templatePath": str(path),
                "missingSections": list(PR_BODY_REQUIRED_SECTIONS),
                "nextAction": "Create .pr-flow/pr-template.md with Summary, Scope, Closing References.",
            },
        ) from exc
    required = configured_required_sections(config)
    missing = [
        section
        for section in PR_BODY_REQUIRED_SECTIONS
        if section not in required or f"## {section}" not in template
    ]
    if missing or not strip_html_comments(template):
        raise PrFlowError(
            "pr_body_required",
            {
                "reason": "pr_body_required",
                "templatePath": str(path),
                "missingSections": missing or list(PR_BODY_REQUIRED_SECTIONS),
                "configuredRequiredSections": required,
                "nextAction": "Add ## Summary, ## Scope and ## Closing References to the template and defaults.pr.requiredSections.",
            },
        )
    return path


def strip_html_comments(body: str | None) -> str:
    if not isinstance(body, str):
        return ""
    return HTML_COMMENT_RE.sub("", body).strip()


def render_closing_references(fixes: Sequence[str]) -> str:
    if not fixes:
        return "None"
    return "\n".join(f"Fixes #{issue}" for issue in fixes)


def render_pr_body(project: Path, config: dict[str, Any], summary: str, scope: str, fixes: Sequence[str]) -> str:
    validate_pr_body_template(project, config)
    return (
        "## Summary\n\n"
        f"{summary}\n\n"
        "## Scope\n\n"
        f"{scope}\n\n"
        "## Closing References\n\n"
        f"{render_closing_references(fixes)}\n"
    )
```

```python
def run_complete(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    try:
        config = load_config(project)
        summary, scope, fixes = require_pr_body_args(project, args.command, args)
        render_pr_body(project, config, summary, scope, fixes)
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)
    except PrFlowError as exc:
        return stop(project, args.command, "EXCEPTION_REQUIRED", exc.reason, exc.details)
    return run_lifecycle(project, config, args.command)


def run_tweak(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    try:
        config = load_config(project)
        summary, scope, fixes = require_pr_body_args(project, args.command, args)
        render_pr_body(project, config, summary, scope, fixes)
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)
    except PrFlowError as exc:
        return stop(project, args.command, "EXCEPTION_REQUIRED", exc.reason, exc.details)

    body = TWEAK_BODY_TEMPLATE.format(reason=args.reason)
    return run_lifecycle(
        project,
        config,
        args.command,
        skip_review_gate=True,
        before_checks=lambda pr: update_pr_body(project, pr, body),
    )
```

- [x] **Step 4（步骤 4）：Run tests to verify they pass（运行测试确认通过）**

Run（运行）：

```bash
python -m pytest tests/test_pr_flow_cli.py::test_complete_and_tweak_share_three_section_body_renderer tests/test_pr_flow_cli.py::test_complete_rejects_missing_template_sections_before_pr_work -q
```

Expected（预期）：PASS（通过）。

- [x] **Step 5（步骤 5）：Commit（提交）**

```bash
git add tests/test_pr_flow_cli.py plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py
git commit -m "feat: 统一 PR body 模板校验"
```

## Task 3（任务 3）：创建、补写和保护 PR body（拉取请求正文）

**Files（文件）：**
- Modify（修改）：`D:\My Project\my-agent-skills\tests\test_pr_flow_cli.py`
- Modify（修改）：`D:\My Project\my-agent-skills\plugins\pr-flow\skills\pr-flow\scripts\pr_flow.py`

- [x] **Step 1（步骤 1）：Write the failing tests（编写失败测试）**

在 `tests/test_pr_flow_cli.py`（PR Flow 测试）中更新 PR（拉取请求）JSON（结构化文本）helper（辅助函数）和 complete/tweak（收尾/小改）调用 helper（辅助函数）：

```python
def pr_view_json(
    *,
    checks: list[dict],
    review_decision: str = "REVIEW_REQUIRED",
    head_oid: str | None = None,
    is_draft: bool = False,
    body: str | None = "",
) -> str:
    payload = {
        "number": 12,
        "state": "OPEN",
        "isDraft": is_draft,
        "mergeStateStatus": "BLOCKED",
        "reviewDecision": review_decision,
        "headRefName": "feature/example",
        "baseRefName": "main",
        "statusCheckRollup": checks,
        "body": body,
    }
    if head_oid is not None:
        payload["headRefOid"] = head_oid
    return json.dumps(payload) + "\n"


def complete_args(project: Path, *, summary: str = "修复 PR Flow 创建空正文 PR", scope: str = "更新 complete、tweak、diagnose 和测试", fixes: tuple[str, ...] = ("98",)) -> list[str]:
    args = ["complete", "--project", str(project), "--summary", summary, "--scope", scope]
    for issue in fixes:
        args.extend(["--fixes", issue])
    return args


def tweak_args(project: Path, *, reason: str, summary: str = "修复 PR Flow 创建空正文 PR", scope: str = "更新 complete、tweak、diagnose 和测试", fixes: tuple[str, ...] = ("98",)) -> list[str]:
    args = ["tweak", "--project", str(project), "--reason", reason, "--summary", summary, "--scope", scope]
    for issue in fixes:
        args.extend(["--fixes", issue])
    return args
```

把 `run_complete_in_process`（进程内运行 complete）里的调用改为：

```python
result = invoke_pr_flow(complete_args(project), module=module)
```

把 `run_tweak_in_process`（进程内运行 tweak）里的调用改为：

```python
result = invoke_pr_flow(tweak_args(project, reason=reason), module=module)
```

添加新建 PR（拉取请求）、已有空正文、已有人工正文和 closing references（关闭引用）冲突测试：

```python
def test_complete_creates_pr_with_generated_body_file(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path)
    head_oid = git(project, "rev-parse", "HEAD")
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stderr": "no pull requests found\n", "exit_code": 1},
            {"stdout": "https://github.example/test/repo/pull/12\n"},
            {"stdout": passing_pr_view_json(project)},
            {"stdout": passing_pr_view_json(project)},
            {"stdout": ""},
            {"stdout": cleanup_pr_view_json()},
        ],
    )

    result = run_with_path(fake_bin, *complete_args(project))

    assert result.returncode == 0, result.stdout + result.stderr
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls[1][:5] == ["pr", "create", "--base", "main", "--fill"]
    assert "--body-file" in calls[1]
    assert calls[4] == ["pr", "merge", "12", "--merge", "--match-head-commit", head_oid]
    body_files = captured_body_files(fake_bin)
    assert body_files[0]["args"][:2] == ["pr", "create"]
    assert body_files[0]["body"] == expected_pr_body()


def test_complete_fills_existing_empty_body_before_checks(tmp_path: Path) -> None:
    project, _remote = init_complete_project(tmp_path)
    head_oid = git(project, "rev-parse", "HEAD")
    empty_body_pr = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid=head_oid,
        body="   <!-- GitHub template comment -->   ",
    )
    fake_bin, calls_path = write_fake_gh_sequence(
        tmp_path / "bin",
        [
            {"stdout": empty_body_pr},
            {"stdout": empty_body_pr},
            {"stdout": ""},
            {"stdout": ""},
            {"stdout": cleanup_pr_view_json()},
        ],
    )

    result = run_with_path(fake_bin, *complete_args(project))

    assert result.returncode == 0, result.stdout + result.stderr
    body_files = captured_body_files(fake_bin)
    assert body_files[0]["body"] == expected_pr_body()
    calls = json.loads(calls_path.read_text(encoding="utf-8"))
    assert calls[2][:3] == ["pr", "edit", "12"]
    assert calls[3][:2] == ["pr", "merge"]


def test_complete_keeps_existing_human_body_without_fixes(tmp_path: Path, monkeypatch) -> None:
    project, result = run_complete_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid="b" * 40,
            body="## Summary\n\nHuman text\n",
        ),
        cleanup_stdout=cleanup_pr_view_json(),
        git_responses=[
            (["branch", "--show-current"], "feature/example\n", 0),
            (["rev-parse", "HEAD"], "b" * 40 + "\n", 0),
        ],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: cleanup_complete" in result.stdout


def test_complete_stops_when_existing_human_body_conflicts_with_fixes(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    human_body_pr = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid="b" * 40,
        body="## Summary\n\nHuman text\n",
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=human_body_pr)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=human_body_pr)
    git_stub = CommandStub(consume=True)
    git_stub.add(["branch", "--show-current"], stdout="feature/example\n")
    git_stub.add(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], stdout="origin/feature/example\n")
    git_stub.add(["rev-list", "--count", "@{u}..HEAD"], stdout="0\n")
    monkeypatch.setattr(module, "gh", gh_stub)
    monkeypatch.setattr(module, "git", git_stub)

    result = invoke_pr_flow(complete_args(project, fixes=("98",)), module=module)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "pr_body_required"
    assert status["details"]["pr"] == "12"
    assert status["details"]["conflict"] == "existing_body_not_overwritten"
    assert status["details"]["closingReferences"] == ["Fixes #98"]
    assert all(call[:2] != ("pr", "edit") for call in gh_stub.calls)
```

- [x] **Step 2（步骤 2）：Run tests to verify they fail（运行测试确认失败）**

Run（运行）：

```bash
python -m pytest tests/test_pr_flow_cli.py::test_complete_creates_pr_with_generated_body_file tests/test_pr_flow_cli.py::test_complete_fills_existing_empty_body_before_checks tests/test_pr_flow_cli.py::test_complete_keeps_existing_human_body_without_fixes tests/test_pr_flow_cli.py::test_complete_stops_when_existing_human_body_conflicts_with_fixes -q
```

Expected（预期）：FAIL（失败），包含 `gh pr create`（创建拉取请求）未传 `--body-file`（正文文件）或已有正文保护逻辑缺失。

- [x] **Step 3（步骤 3）：Write minimal implementation（编写最小实现）**

在 `pr_flow.py`（PR Flow 脚本）中把 PR（拉取请求）读取字段、创建函数和 lifecycle（生命周期）改为正文感知：

```python
PR_VIEW_FIELDS = "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid,body"
```

```python
def gh_with_body_file(project: Path, args: Sequence[str], body: str) -> subprocess.CompletedProcess[str]:
    body_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as body_file:
            body_file.write(body)
            body_path = Path(body_file.name)
        return gh(project, *args, "--body-file", str(body_path))
    finally:
        if body_path is not None:
            body_path.unlink(missing_ok=True)


def create_pr(project: Path, config: dict[str, Any], body: str | None = None) -> dict[str, Any]:
    args = ["pr", "create", "--base", base_branch_from_config(config), "--fill"]
    result = gh_with_body_file(project, args, body) if body is not None else gh(project, *args)
    if result.returncode != 0:
        details = command_failure_details("gh_pr_create_failed", result)
        raise PrFlowError("gh_pr_create_failed", details)
    pr = find_pr(project)
    if pr is None:
        details = command_failure_details("gh_pr_create_missing_pr", result)
        raise PrFlowError("gh_pr_create_missing_pr", details)
    return pr
```

```python
def update_pr_body(project: Path, pr: dict[str, Any], body: str) -> None:
    pr_number = pr_number_for_command(pr)
    result = gh_with_body_file(project, ["pr", "edit", pr_number], body)
    if result.returncode != 0:
        details = command_failure_details("gh_pr_edit_failed", result)
        details["pr"] = pr_number
        raise PrFlowError("gh_pr_edit_failed", details)


def reconcile_existing_pr_body(project: Path, pr: dict[str, Any], body: str, fixes: Sequence[str]) -> None:
    if not strip_html_comments(pr.get("body")):
        update_pr_body(project, pr, body)
        return
    if fixes:
        closing_references = [f"Fixes #{issue}" for issue in fixes]
        pr_number = pr_number_for_command(pr)
        raise PrFlowError(
            "pr_body_required",
            {
                "reason": "pr_body_required",
                "pr": pr_number,
                "conflict": "existing_body_not_overwritten",
                "closingReferences": closing_references,
                "nextAction": f"Edit PR #{pr_number} body manually and add: {', '.join(closing_references)}",
            },
        )
```

```python
def run_lifecycle(
    project: Path,
    config: dict[str, Any],
    command: str,
    *,
    skip_review_gate: bool = False,
    before_checks: Any | None = None,
    pr_body: str | None = None,
    fixes: Sequence[str] = (),
) -> int:
    try:
        pr = find_pr(project)
        existing_pr = pr is not None
        if command == "complete":
            push_stop = auto_push_current_branch_if_needed(project, config)
            if push_stop is not None:
                return stop_from_state(project, command, push_stop)
        elif pr is None:
            push_stop = missing_upstream_state(project, config)
            if push_stop is not None:
                return stop_from_state(project, command, push_stop)
        if pr is None:
            pr = create_pr(project, config, pr_body)
        pr = sync_pr(project, pr)
        if pr_body is not None and existing_pr:
            reconcile_existing_pr_body(project, pr, pr_body, fixes)
        if before_checks is not None:
            before_checks(pr)
    except PrFlowError as exc:
        return stop(project, command, "EXCEPTION_REQUIRED", exc.reason, exc.details)
```

在 `run_complete`（运行收尾）和 `run_tweak`（运行小改）中传入统一正文，并删除 tweak（小改）独立正文写入：

```python
def run_complete(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    try:
        config = load_config(project)
        summary, scope, fixes = require_pr_body_args(project, args.command, args)
        body = render_pr_body(project, config, summary, scope, fixes)
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)
    except PrFlowError as exc:
        return stop(project, args.command, "EXCEPTION_REQUIRED", exc.reason, exc.details)
    return run_lifecycle(project, config, args.command, pr_body=body, fixes=fixes)


def run_tweak(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    try:
        config = load_config(project)
        summary, scope, fixes = require_pr_body_args(project, args.command, args)
        body = render_pr_body(project, config, summary, scope, fixes)
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)
    except PrFlowError as exc:
        return stop(project, args.command, "EXCEPTION_REQUIRED", exc.reason, exc.details)
    return run_lifecycle(project, config, args.command, skip_review_gate=True, pr_body=body, fixes=fixes)
```

- [x] **Step 4（步骤 4）：Run tests to verify they pass（运行测试确认通过）**

Run（运行）：

```bash
python -m pytest tests/test_pr_flow_cli.py::test_complete_creates_pr_with_generated_body_file tests/test_pr_flow_cli.py::test_complete_fills_existing_empty_body_before_checks tests/test_pr_flow_cli.py::test_complete_keeps_existing_human_body_without_fixes tests/test_pr_flow_cli.py::test_complete_stops_when_existing_human_body_conflicts_with_fixes tests/test_pr_flow_cli.py::test_tweak_creates_pr_when_none_exists_and_writes_body tests/test_pr_flow_cli.py::test_tweak_skips_review_gate_for_changes_requested_then_merges_and_cleans_up -q
```

Expected（预期）：PASS（通过）。

- [x] **Step 5（步骤 5）：Commit（提交）**

```bash
git add tests/test_pr_flow_cli.py plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py
git commit -m "feat: 写入并保护 PR body"
```

## Task 4（任务 4）：Diagnose（诊断）下一步命令和 Skill（技能）示例

**Files（文件）：**
- Modify（修改）：`D:\My Project\my-agent-skills\tests\test_pr_flow_cli.py`
- Modify（修改）：`D:\My Project\my-agent-skills\plugins\pr-flow\skills\pr-flow\scripts\pr_flow.py`
- Modify（修改）：`D:\My Project\my-agent-skills\plugins\pr-flow\skills\pr-flow-complete\SKILL.md`
- Modify（修改）：`D:\My Project\my-agent-skills\plugins\pr-flow\skills\pr-flow-tweak\SKILL.md`

- [x] **Step 1（步骤 1）：Write the failing tests（编写失败测试）**

在 `tests/test_pr_flow_cli.py`（PR Flow 测试）中更新 diagnose（诊断）helper（辅助函数）配置，并添加 body-aware（正文感知）测试：

```python
def write_minimal_pr_flow_config(project: Path) -> None:
    config_dir = project / ".pr-flow"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "defaults": {
            "baseBranch": "main",
            "pr": {
                "bodyTemplatePath": ".pr-flow/pr-template.md",
                "requiredSections": ["Summary", "Scope", "Closing References"],
            },
        },
        "branches": {"main": {"remote": "origin"}},
    }
    (config_dir / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (config_dir / "pr-template.md").write_text(
        "## Summary\n\n<!-- summary guide -->\n\n"
        "## Scope\n\n<!-- scope guide -->\n\n"
        "## Closing References\n\n<!-- closing guide -->\n",
        encoding="utf-8",
    )


def test_diagnose_on_feature_branch_without_pr_reports_body_aware_command(tmp_path: Path, monkeypatch) -> None:
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    assert init_repo(project) == "main"
    write_confirmed_pr_flow_config(project)
    git(project, "switch", "-c", "feature/body-required")

    result = invoke_pr_flow(["diagnose", "--project", str(project)], module=module)

    assert result.returncode == 1
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["details"]["reason"] == "pr_missing"
    assert "--summary" in status["details"]["nextCommand"]
    assert "--scope" in status["details"]["nextCommand"]
    assert status["details"]["optionalFixesArg"] == "--fixes 98"


def test_diagnose_existing_empty_body_reports_pr_body_required(tmp_path: Path, monkeypatch) -> None:
    project, result = run_diagnose_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout=pr_view_json(
            checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            review_decision="APPROVED",
            head_oid="b" * 40,
            body="<!-- template comment -->",
        ),
    )

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "pr_body_required"
    assert status["details"]["pr"] == 12
    assert "--summary" in status["details"]["nextCommand"]
    assert "--scope" in status["details"]["nextCommand"]
```

添加 Skill（技能）文本测试，复用现有文档测试附近的路径断言：

```python
def test_pr_flow_complete_and_tweak_skills_show_body_args() -> None:
    complete = (REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-complete" / "SKILL.md").read_text(encoding="utf-8")
    tweak = (REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow-tweak" / "SKILL.md").read_text(encoding="utf-8")

    for text in (complete, tweak):
        assert "--summary" in text
        assert "--scope" in text
        assert "--fixes" in text
    assert "--reason" in tweak
```

- [x] **Step 2（步骤 2）：Run tests to verify they fail（运行测试确认失败）**

Run（运行）：

```bash
python -m pytest tests/test_pr_flow_cli.py::test_diagnose_on_feature_branch_without_pr_reports_body_aware_command tests/test_pr_flow_cli.py::test_diagnose_existing_empty_body_reports_pr_body_required tests/test_pr_flow_cli.py::test_pr_flow_complete_and_tweak_skills_show_body_args -q
```

Expected（预期）：FAIL（失败），包含 diagnose（诊断）未读取 `body`（正文）、`nextCommand`（下一步命令）缺正文参数或 Skill（技能）示例未更新。

- [x] **Step 3（步骤 3）：Write minimal implementation（编写最小实现）**

在 `run_diagnose`（运行诊断）中读取 `body`（正文），并在缺 PR（拉取请求）和空正文时输出正文感知 details（详情）：

```python
pr_result = gh(
    project,
    "pr",
    "view",
    "--json",
    "number,state,isDraft,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,body",
)
```

```python
if pr_result.returncode != 0:
    gh_details.update(command_failure_details("gh_pr_view_failed", pr_result))
    if gh_pr_not_found(pr_result) and branch != base_branch:
        gh_details["reason"] = "pr_missing"
        gh_details["nextCommand"] = pr_body_next_command("complete", project, argparse.Namespace(summary="", scope="", fixes=[]))
        gh_details["optionalFixesArg"] = "--fixes 98"
        return stop(project, args.command, "DISPATCH_REQUIRED", "pr_missing", gh_details)
    return stop(project, args.command, "EXCEPTION_REQUIRED", "gh_pr_view_failed", gh_details)
```

```python
gh_details.update(
    {
        "reason": "pr_state",
        "pr": pr.get("number"),
        "reviewDecision": pr.get("reviewDecision"),
        "mergeStateStatus": pr.get("mergeStateStatus"),
        "isDraft": pr.get("isDraft"),
        "headRefName": pr.get("headRefName"),
        "baseRefName": pr.get("baseRefName"),
    }
)
if not strip_html_comments(pr.get("body")):
    gh_details["reason"] = "pr_body_required"
    gh_details["nextCommand"] = pr_body_next_command("complete", project, argparse.Namespace(summary="", scope="", fixes=[]))
    gh_details["optionalFixesArg"] = "--fixes 98"
    return stop(project, args.command, "EXCEPTION_REQUIRED", "pr_body_required", gh_details)
```

把 `plugins/pr-flow/skills/pr-flow-complete/SKILL.md`（收尾技能说明）替换为：

```markdown
archived-with: 2026-06-30-fix-pr-flow-pr-body
---
name: pr-flow-complete
description: "执行 PR Flow（拉取请求流程）收尾：创建或同步 PR、等待 checks（检查）、执行 review gate（审查门禁）、合并并清理。"
archived-with: 2026-06-30-fix-pr-flow-pr-body
---

# PR Flow Complete

## 边界

会根据 `.pr-flow/config.yaml` 处理 PR 收尾。命令可能创建或同步 PR、等待 checks（检查）、执行 review gate（审查门禁）、合并 PR，并在合并后调用 cleanup（清理）。

不创建本地提交，不强制推送，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py complete --project . --summary "修复 PR Flow 创建空正文 PR" --scope "更新 complete、tweak、diagnose 和测试" --fixes 98
```
```

把 `plugins/pr-flow/skills/pr-flow-tweak/SKILL.md`（小改技能说明）替换为：

```markdown
archived-with: 2026-06-30-fix-pr-flow-pr-body
---
name: pr-flow-tweak
description: "PR Flow（拉取请求流程）tweak（小改）路径，用于非 BUG（缺陷）小改动 PR（拉取请求）。"
archived-with: 2026-06-30-fix-pr-flow-pr-body
---

# PR Flow Tweak

## 边界

用于非 BUG（缺陷）小改动 PR（拉取请求），例如文案、格式、注释或低风险配置微调。

该路径跳过 review gate（审查门禁），但仍保留 checks（检查）、merge（合并）和 cleanup（清理）。

只进入 PR Flow（拉取请求流程）tweak（小改）路径，不修改 OpenSpec（开放规格）任务。`--reason` 只说明为什么使用 tweak（小改）路径，不写入 PR body（拉取请求正文）。

## 命令

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tweak --project . --reason "small docs polish" --summary "更新 PR Flow 文档措辞" --scope "只修改 PR Flow 文档" --fixes 98
```
```

- [x] **Step 4（步骤 4）：Run tests to verify they pass（运行测试确认通过）**

Run（运行）：

```bash
python -m pytest tests/test_pr_flow_cli.py::test_diagnose_on_feature_branch_without_pr_reports_body_aware_command tests/test_pr_flow_cli.py::test_diagnose_existing_empty_body_reports_pr_body_required tests/test_pr_flow_cli.py::test_pr_flow_complete_and_tweak_skills_show_body_args -q
```

Expected（预期）：PASS（通过）。

- [x] **Step 5（步骤 5）：Commit（提交）**

```bash
git add tests/test_pr_flow_cli.py plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py plugins/pr-flow/skills/pr-flow-complete/SKILL.md plugins/pr-flow/skills/pr-flow-tweak/SKILL.md
git commit -m "docs: 更新 PR Flow 正文参数示例"
```

## Task 5（任务 5）：Focused Regression（聚焦回归）和 Full Verification（完整验证）

**Files（文件）：**
- Verify（验证）：`D:\My Project\my-agent-skills\tests\test_pr_flow_cli.py`
- Verify（验证）：`D:\My Project\my-agent-skills\openspec\changes\fix-pr-flow-pr-body\specs\pr-flow-plugin\spec.md`

- [x] **Step 1（步骤 1）：Run focused PR Flow tests（运行聚焦 PR Flow 测试）**

Run（运行）：

```bash
python -m pytest tests/test_pr_flow_cli.py -k "pr_body or body_args or body_aware or complete_creates_pr_with_generated_body_file or complete_fills_existing_empty_body_before_checks or complete_keeps_existing_human_body_without_fixes or complete_stops_when_existing_human_body_conflicts_with_fixes or tweak_creates_pr_when_none_exists_and_writes_body or diagnose_existing_empty_body" -q
```

Expected（预期）：PASS（通过），覆盖 init（初始化）、complete（收尾）、tweak（小改）和 diagnose（诊断）主流程。

- [x] **Step 2（步骤 2）：Run full PR Flow CLI tests（运行完整 PR Flow 命令行测试）**

Run（运行）：

```bash
python -m pytest tests/test_pr_flow_cli.py -q
```

Expected（预期）：PASS（通过），旧 complete（收尾）和 tweak（小改）测试已全部显式传入正文参数。

- [x] **Step 3（步骤 3）：Run OpenSpec strict validation（运行 OpenSpec 严格校验）**

Run（运行）：

```bash
openspec validate fix-pr-flow-pr-body --strict
```

Expected（预期）：PASS（通过），`fix-pr-flow-pr-body`（修复 PR Flow 正文）变更规格有效。

- [x] **Step 4（步骤 4）：Run repository verification（运行仓库验证）**

Run（运行）：

```bash
python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full
```

Expected（预期）：PASS（通过），覆盖仓库发布形态的主验证路径。

- [x] **Step 5（步骤 5）：Commit verification adjustments（提交验证修正）**

只有当 Step 1 到 Step 4（步骤 1 到步骤 4）暴露出必需修正并完成代码修正后运行：

```bash
git add tests/test_pr_flow_cli.py plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py plugins/pr-flow/skills/pr-flow-complete/SKILL.md plugins/pr-flow/skills/pr-flow-tweak/SKILL.md
git commit -m "fix: 补齐 PR body 回归验证"
```

如果 Step 1 到 Step 4（步骤 1 到步骤 4）直接通过，不创建空提交。

## Self-Review（自检）

- Spec coverage（规格覆盖）：计划覆盖三节模板、`--summary`、`--scope`、repeatable `--fixes`（可重复关闭引用参数）、新建 PR（拉取请求）正文、已有空正文补写、人工正文保护、diagnose（诊断）下一步命令和 Skill（技能）示例。
- Gap scan（空洞扫描）：计划没有留下未定字段、空命令或需要猜测的测试步骤。
- Type consistency（类型一致性）：正文 helper（辅助函数）使用 `Path`（路径）、`dict[str, Any]`（字典类型）、`Sequence[str]`（字符串序列）和现有 `PrFlowError`（流程错误）结构；调用方复用现有 `stop`（停止）、`write_status`（写状态）和 `CommandStub`（命令替身）。
