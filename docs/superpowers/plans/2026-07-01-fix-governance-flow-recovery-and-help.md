---
change: fix-governance-flow-recovery-and-help
design-doc: docs/superpowers/specs/2026-07-01-fix-governance-flow-recovery-and-help-design.md
base-ref: b99c574ed10222db03401887ff10fe9137a3f09c
---

# Governance Flow Recovery and Help Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `PR Flow`（拉取请求流程）、`Release Flow`（发布流程）和 `cross-agent-review`（跨代理审查）的恢复路径与参数提示，并删除 `publish --dry-run`（发布试运行）。

**Architecture:** 保持局部修改：每个插件只改自己的脚本、测试和 Skill（技能）文档。`Release Flow`（发布流程）只在 `publish`（发布）触发 `gh workflow run`（触发工作流）处增加小型 EOF（连接提前结束）重试，不新增共享框架。

**Tech Stack:** Python（编程语言）、argparse（参数解析）、pytest（测试框架）、GitHub CLI（GitHub 命令行）命令桩、OpenSpec（开放规格）。

---

## File Map

- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
  - Report invalid `--fixes`（修复问题编号） before missing PR body（拉取请求正文） fields.
  - Improve `--fixes` help（帮助） text.
- Modify: `tests/test_pr_flow_cli.py`
  - Add invalid fixes cases and post-create sync EOF（连接提前结束） regression.
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
  - Remove `publish --dry-run`（发布试运行）.
  - Add bounded EOF（连接提前结束） retry for `gh workflow run`（触发工作流）.
- Modify: `plugins/release-flow/skills/release-flow/SKILL.md`
  - Remove any `publish --dry-run`（发布试运行） guidance and mention migration.
- Modify: `tests/test_release_flow_cli.py`
  - Replace dry-run test, add retry success and retry exhaustion tests.
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
  - Print `head_ref_short`（短头引用） and copyable paths from `run`（运行） and `mark-pass`（标记通过）.
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`
  - Define `<head_ref_short>`（短头引用） as first 12 chars of `head_ref`（头引用）.
- Modify: `tests/test_cross_agent_review_cli.py`
  - Cover new output lines.
- Modify: `tests/test_cross_agent_review_plugin_package.py`
  - Cover Skill（技能） documentation rule.
- Modify: `openspec/changes/fix-governance-flow-recovery-and-help/tasks.md`
  - Check off tasks after verified completion.

## Task 1: PR Flow Invalid `--fixes`

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: Write failing invalid fixes tests**

Add or extend tests around `test_complete_rejects_non_numeric_fixes_before_auto_push_or_pr_create`.

Use parametrized invalid values:

```python
@pytest.mark.parametrize("bad_fix", ["41,43", "#98", "abc", "0", "-1"])
def test_complete_rejects_invalid_fixes_before_auto_push_or_pr_create(tmp_path: Path, monkeypatch, bad_fix: str) -> None:
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

    result = invoke_pr_flow(complete_args(project, fixes=(bad_fix,)), module=module)

    assert result.returncode == 1
    assert "status: EXCEPTION_REQUIRED" in result.stdout
    assert "invalid_fixes" in result.stdout
    assert "--fixes 41 --fixes 43 --fixes 44" in result.stdout
    assert git_stub.calls == []
    assert gh_stub.calls == []
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["details"]["reason"] == "invalid_fixes"
    assert status["details"]["invalidFixes"] == [bad_fix]
```

- [x] **Step 2: Run the failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "invalid_fixes or non_numeric_fixes" -q
```

Expected: FAIL because current reason is `pr_body_required`（需要拉取请求正文） and output lacks the repeated-argument example.

- [x] **Step 3: Implement minimal invalid fixes reporting**

In `require_pr_body_args`, validate `fixes` before `missing`.

Use this shape:

```python
fixes = [str(issue).strip() for issue in (getattr(args, "fixes", None) or []) if str(issue).strip()]
invalid_fixes = [issue for issue in fixes if not issue.isdecimal() or int(issue) <= 0]
if invalid_fixes:
    raise PrFlowError(
        "invalid_fixes",
        {
            "reason": "invalid_fixes",
            "invalidFixes": invalid_fixes,
            "nextAction": "Pass each issue number separately, for example --fixes 41 --fixes 43 --fixes 44.",
        },
    )
```

Keep missing `--summary`（摘要） / `--scope`（范围） behavior unchanged.

- [x] **Step 4: Add help text**

In `build_parser`, change the `--fixes` argument to include help（帮助）:

```python
subparser.add_argument(
    "--fixes",
    action="append",
    default=[],
    help="Issue number to close; repeat for multiple issues, for example --fixes 41 --fixes 43.",
)
```

- [x] **Step 5: Verify PR Flow invalid fixes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "invalid_fixes or repeated_fixes or non_numeric_fixes" -q
```

Expected: PASS.

## Task 2: PR Flow Post-Create Sync EOF

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify only if test fails: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: Write failing post-create sync retry test**

Add a test near existing transient EOF tests.

Use `CommandStub(consume=True)` so the sequence proves `create_pr`（创建拉取请求） followed by `sync_pr`（同步拉取请求） retries.

Test shape:

```python
def test_complete_retries_transient_eof_after_pr_create_sync(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow

    module = load_pr_flow_module()
    project = tmp_path / "project"
    project.mkdir()
    write_complete_pr_flow_config(project)
    monkeypatch.setenv("PR_FLOW_GH_PR_VIEW_RETRIES", "1")

    pr_stdout = pr_view_json(
        checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        review_decision="APPROVED",
        head_oid="b" * 40,
        body=expected_pr_body(fixes=("98",)),
    )
    gh_stub = CommandStub(consume=True)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], returncode=1, stderr="no pull requests found\n")
    gh_stub.add_body_file(["pr", "create", "--base", "main", "--fill", "--body-file"], stdout="created\n")
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stderr='Post "https://api.github.com/graphql": EOF\n', returncode=1)
    gh_stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=pr_stdout)
    # Add any later gh calls already required by the complete happy path.
```

If existing helpers make a full merge happy path too long, keep the assertion scoped by injecting `before_checks` through `run_lifecycle` in a unit-style test. Prefer full `invoke_pr_flow`（调用命令入口） if practical.

- [x] **Step 2: Run the failing test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "post_create or transient_eof" -q
```

Expected: PASS if existing code already covers it; if FAIL, fix only `gh_pr_view` / `find_pr` reuse path.

- [x] **Step 3: Minimal implementation if needed**

Only if Step 2 fails, route the failing post-create lookup through `gh_pr_view`; do not add caller-specific retry logic.

- [x] **Step 4: Verify PR Flow EOF path**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "transient_eof or post_create or cleanup_retries" -q
```

Expected: PASS.

## Task 3: Release Flow Publish Retry and Dry-Run Removal

**Files:**
- Modify: `tests/test_release_flow_cli.py`
- Modify: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- Modify: `plugins/release-flow/skills/release-flow/SKILL.md`

- [x] **Step 1: Replace publish dry-run test**

Replace `test_publish_dry_run_prints_workflow_dispatch_without_git_writes` with a rejection test:

```python
def test_publish_rejects_dry_run_argument(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)

    result = run(
        "publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
        "--dry-run",
    )

    assert result.returncode == 2
    assert "--dry-run" in result.stderr
    assert "workflow_dispatch:" not in result.stdout
```

- [x] **Step 2: Add publish EOF retry success test**

Add a test that writes a fake `gh` executable earlier in `PATH`:

```python
def test_publish_retries_workflow_run_eof_then_succeeds(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_release_flow_files(project)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "gh-calls.txt"
    gh = bin_dir / ("gh.bat" if os.name == "nt" else "gh")
    gh.write_text(
        "@echo off\n"
        f"echo %*>>\"{calls}\"\n"
        f"if not exist \"{tmp_path / 'seen'}\" (echo seen>\"{tmp_path / 'seen'}\" & echo Get \"\"https://api.github.com/repos/x/actions/workflows/release.yml\"\": EOF 1>&2 & exit /b 1)\n"
        "exit /b 0\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    result = run(
        "publish",
        "--project",
        str(project),
        "--tag",
        "v0.1.1",
        "--version",
        "0.1.1",
        "--bump-plugins",
        "agent-guard",
        "--authorize-publish",
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert calls.read_text(encoding="utf-8").count("workflow run") == 2
```

Adjust the fake executable for POSIX if tests need cross-platform support; existing tests already run on Windows in this repo.

- [x] **Step 3: Add publish EOF retry exhaustion test**

Use a fake `gh` that always returns EOF.

Assert:

```python
assert result.returncode == 1
assert "EOF" in result.stderr
assert calls.read_text(encoding="utf-8").count("workflow run") == 4
```

Use 4 total calls if the implementation uses one initial call plus 3 retries.

- [x] **Step 4: Run failing Release Flow tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_release_flow_cli.py -k "publish and (dry_run or eof or authorize)" -q
```

Expected: FAIL before implementation.

- [x] **Step 5: Remove publish dry-run parser and branch**

In `build_parser`, delete:

```python
publish.add_argument("--dry-run", action="store_true", help="只打印 workflow dispatch 命令。")
```

In `run_publish`, replace authorization check with:

```python
if not args.authorize_publish:
    print("status: issues")
    print("error: publish_requires_authorize_publish")
    return 2
```

Delete the `if args.dry_run:` block.

- [x] **Step 6: Replace string command execution with list command**

Change `workflow_dispatch_command` to return a list, or add a sibling `workflow_dispatch_args`.

Minimal shape:

```python
def workflow_dispatch_args(config: FlowConfig, tag: str, version: str, bump_plugins: list[str]) -> list[str]:
    validate_release_tag(tag)
    return [
        "gh",
        "workflow",
        "run",
        config.workflow_file,
        "--ref",
        config.release_source_ref,
        "-f",
        f"tag={tag}",
        "-f",
        f"version={version}",
        "-f",
        f"bumpPlugins={','.join(bump_plugins)}",
    ]
```

Keep `workflow_dispatch_command` only if other tests still assert string output; otherwise remove it with the dry-run path.

- [x] **Step 7: Add bounded EOF retry helper**

Near `run_publish`, add:

```python
DEFAULT_GH_WORKFLOW_RUN_RETRIES = 3


def gh_transient_eof(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode != 0 and "eof" in f"{result.stdout}\n{result.stderr}".lower()


def run_workflow_dispatch(project: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=project, check=False, text=True, capture_output=True)
    for _ in range(DEFAULT_GH_WORKFLOW_RUN_RETRIES):
        if not gh_transient_eof(result):
            break
        result = subprocess.run(command, cwd=project, check=False, text=True, capture_output=True)
    return result
```

In `run_publish`, print final stdout/stderr and return final code:

```python
result = run_workflow_dispatch(args.project, workflow_dispatch_args(config, args.tag, args.version, bump_plugins))
if result.stdout:
    print(result.stdout, end="")
if result.stderr:
    print(result.stderr, end="", file=sys.stderr)
return result.returncode
```

Add `import sys` if the file does not already import it.

- [x] **Step 8: Update Release Flow docs/help**

In `plugins/release-flow/skills/release-flow/SKILL.md`, add a short publish command example:

```markdown
Publish（发布） must use explicit authorization:

```powershell
python <plugin-root>/skills/release-flow/scripts/release_flow.py publish --project . --tag v0.1.1 --version 0.1.1 --bump-plugins agent-guard --authorize-publish
```

Use `preflight`（发布前检查） for validation before publish（发布）.
```

Ensure no `publish --dry-run` reference remains outside archive folders.

- [x] **Step 9: Verify Release Flow**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_release_flow_cli.py -k "publish" -q
```

Expected: PASS.

## Task 4: Cross-Agent Review Path Output

**Files:**
- Modify: `tests/test_cross_agent_review_cli.py`
- Modify: `tests/test_cross_agent_review_plugin_package.py`
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`

- [x] **Step 1: Add run output test**

Extend `test_default_run_does_not_archive_context_snapshots_or_git_manifest`:

```python
assert f"head_ref_short: {head[:12]}" in result.stdout
assert f"input_file: {input_file.relative_to(project)}" in result.stdout
```

- [x] **Step 2: Add mark-pass output test**

Extend `test_mark_pass_writes_guard_evidence_default_path`:

```python
assert f"head_ref_short: {head[:12]}" in result.stdout
assert f"path: {marker_path.relative_to(project)}" in result.stdout
```

- [x] **Step 3: Add Skill docs package test**

In `test_cross_agent_review_skill_documents_single_review_input_contract`, assert:

```python
assert "first 12 characters of `head_ref`" in text
```

If the final docs use Chinese wording, assert that exact Chinese sentence instead.

- [x] **Step 4: Run failing cross-agent tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cross_agent_review_cli.py tests/test_cross_agent_review_plugin_package.py -k "head_ref_short or review_input_contract or default_run or mark_pass" -q
```

Expected: FAIL before output/docs changes.

- [x] **Step 5: Print output lines**

In `run_review`, after `status: review_ready`, print:

```python
print(f"head_ref_short: {short_ref(review_args.head_ref)}")
print(f"input_file: {review_args.input_file.relative_to(Path.cwd())}")
```

In `run_mark_pass`, after `status: pass_marked`, keep existing path print and add:

```python
print(f"head_ref_short: {short_ref(review_args.head_ref)}")
```

If `relative_to` can fail for absolute paths outside cwd, use the same location validation assumption: valid inputs are under cwd.

- [x] **Step 6: Update Skill docs**

In `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`, after the path block, add:

```markdown
`<head_ref_short>`（短头引用）等于 `head_ref`（头引用）的前 12 个字符。
```

- [x] **Step 7: Verify cross-agent-review**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cross_agent_review_cli.py tests/test_cross_agent_review_plugin_package.py -q
```

Expected: PASS.

## Task 5: End-to-End Regression and OpenSpec

**Files:**
- Modify: `openspec/changes/fix-governance-flow-recovery-and-help/tasks.md`
- Create during verify phase later: `docs/superpowers/reports/2026-07-01-fix-governance-flow-recovery-and-help-verify.md`

- [x] **Step 1: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py tests/test_release_flow_cli.py tests/test_cross_agent_review_cli.py tests/test_cross_agent_review_plugin_package.py -q
```

Expected: PASS.

- [x] **Step 2: Run CLI end-to-end regression**

Use existing CLI tests as end-to-end coverage from user entrypoints:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pr_flow_cli.py -k "complete" -q
.\.venv\Scripts\python.exe -m pytest tests/test_release_flow_cli.py -k "publish" -q
.\.venv\Scripts\python.exe -m pytest tests/test_cross_agent_review_cli.py -k "default_run or mark_pass" -q
```

Expected: PASS. Record that live GitHub（真实代码托管平台） side effects were not executed; command stubs cover GitHub CLI（GitHub 命令行） boundaries.

- [x] **Step 3: Run OpenSpec validation**

Run:

```powershell
openspec validate fix-governance-flow-recovery-and-help --strict
```

Expected: `Change 'fix-governance-flow-recovery-and-help' is valid`.

- [x] **Step 4: Update OpenSpec task checkboxes**

Check off completed tasks in `openspec/changes/fix-governance-flow-recovery-and-help/tasks.md` after implementation and verification pass.

- [x] **Step 5: Commit checkpoint**

Commit with a Chinese message after all tests pass:

```powershell
git add plugins tests docs openspec
git commit -m "修复治理流程恢复路径和帮助提示"
```

If the workflow owner does not want a commit in this session, skip this step and record the reason in the final response.
