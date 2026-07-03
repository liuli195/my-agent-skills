---
change: stabilize-flow-recovery-actions
design-doc: docs/superpowers/specs/2026-07-03-stabilize-flow-recovery-actions-design.md
base-ref: 7cc2c413a9d34845a899ad826b859b6e83996dc8
---

# 稳定流程恢复动作 Implementation Plan（实施计划）

> **For agentic workers（给代理执行者）:** REQUIRED SUB-SKILL（必需子技能）: Use superpowers:subagent-driven-development（子代理驱动开发，推荐） or superpowers:executing-plans（执行计划） to implement this plan task-by-task（逐项执行）。Steps（步骤） use checkbox（复选框） `- [ ]` syntax（语法） for tracking（跟踪）。

**Goal（目标）:** 让 PR Flow（拉取请求流程）和 Release Flow（发布流程）的已知可恢复失败输出明确恢复动作，同时保持最小实现。

**Architecture（架构）:** PR Flow（拉取请求流程）在现有 `reason`（原因）和 `details`（详情）字典上补 `nextAction`（下一步动作）或 `nextCommand`（下一条命令），不新增状态机。Release Flow（发布流程）只在 preflight（发布预检）输出层把三类已知错误翻译成有序恢复动作，不改变 publish（发布）行为。

**Tech Stack（技术栈）:** Python（Python 语言）、pytest（测试工具）、现有 `gh`（GitHub 命令行）和 git（版本控制）调用封装。

---

## File Structure（文件结构）

- Modify（修改）: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`  
  负责 PR Flow（拉取请求流程）失败分类、恢复动作补全和 `--fixes None`（修复问题编号为空）提示。
- Modify（修改）: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`  
  负责 Release Flow（发布流程）preflight（发布预检）错误输出层恢复动作格式化。
- Modify（修改）: `tests/test_pr_flow_cli.py`  
  覆盖 PR Flow（拉取请求流程）鉴权失败、瞬时 PR（拉取请求）查询失败、checks（检查）等待、ruleset（规则集）阻塞和 `--fixes None`（修复问题编号为空）。
- Modify（修改）: `tests/test_release_flow_cli.py`  
  覆盖 Release Flow（发布流程）三类 preflight（发布预检）恢复动作，保留 publish（发布）现有行为。
- Modify（修改）: `tests/test_pr_flow_plugin_package.py`  
  放仓库级防回归检查，确保可恢复 stop state（停止状态）带 `nextAction`（下一步动作）或 `nextCommand`（下一条命令）。

不新增依赖、不新增框架、不新增状态机。

---

### Task 1: PR Flow（拉取请求流程）恢复动作测试

**Files（文件）:**
- Modify（修改）: `tests/test_pr_flow_cli.py`
- Later modify（稍后修改）: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

- [x] **Step 1: Write failing tests（写失败测试）**

在 `tests/test_pr_flow_cli.py` 现有 PR body（拉取请求正文）和 diagnose（诊断）测试附近加入这些测试；同时给现有 ruleset（规则集）和 checks（检查）测试补断言。

```python
def test_diagnose_reports_dispatch_for_gh_auth_failure(tmp_path: Path, monkeypatch) -> None:
    project, result = run_diagnose_in_process(
        tmp_path,
        monkeypatch,
        pr_stdout="",
        pr_stderr="gh: To get started with GitHub CLI, please run: gh auth login\n",
        pr_returncode=4,
    )

    assert result.returncode == 1
    assert "status: DISPATCH_REQUIRED" in result.stdout
    assert "gh_auth_required" in result.stdout
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "DISPATCH_REQUIRED"
    assert status["details"]["reason"] == "gh_auth_required"
    assert status["details"]["nextCommand"] == "gh auth status"


@pytest.mark.parametrize(
    ("command_args", "command"),
    [
        (lambda project: complete_args(project, fixes=("None",)), "complete"),
        (lambda project: tweak_args(project, reason="small docs polish", fixes=("None",)), "tweak"),
    ],
)
def test_pr_body_commands_reject_none_fixes_with_remove_guidance(
    tmp_path: Path, monkeypatch, command_args, command: str
) -> None:
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

    result = invoke_pr_flow(command_args(project), module=module)

    assert result.returncode == 1
    assert "status: REPLY_OR_FIX_REQUIRED" in result.stdout
    assert git_stub.calls == []
    assert gh_stub.calls == []
    status = json.loads((project / ".pr-flow" / "last-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "REPLY_OR_FIX_REQUIRED"
    assert status["command"] == command
    assert status["details"]["reason"] == "invalid_fixes"
    assert status["details"]["invalidFixes"] == ["None"]
    assert status["details"]["nextAction"] == "Remove --fixes when there is no issue to close."
```

在 `test_diagnose_reports_dispatch_when_transient_eof_retries_are_exhausted`（瞬时 EOF 重试耗尽）末尾保留已有断言，并确认恢复字段存在：

```python
assert status["details"]["nextCommand"].endswith(f"diagnose --project {project}")
```

在 `test_tweak_auto_pushes_clean_unprotected_branch_without_upstream`（小改自动推送后 checks 等待）末尾加入：

```python
assert "nextAction" in status["details"] or "nextCommand" in status["details"]
assert "checks" in (status["details"].get("nextAction") or status["details"].get("nextCommand"))
```

在 `test_complete_reports_dispatch_when_ruleset_blocks_merge`（ruleset 阻塞合并）末尾加入：

```python
assert "nextAction" in status["details"] or "nextCommand" in status["details"]
assert "ruleset" in (status["details"].get("nextAction") or status["details"].get("nextCommand"))
```

在 `test_complete_returns_checks_pending_when_ruleset_recovery_wait_times_out`（ruleset 恢复等待超时）末尾加入：

```python
assert "nextAction" in status["details"] or "nextCommand" in status["details"]
assert "checks" in (status["details"].get("nextAction") or status["details"].get("nextCommand"))
```

- [x] **Step 2: Run tests to verify failure（运行测试确认失败）**

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_diagnose_reports_dispatch_for_gh_auth_failure tests/test_pr_flow_cli.py::test_pr_body_commands_reject_none_fixes_with_remove_guidance tests/test_pr_flow_cli.py::test_diagnose_reports_dispatch_when_transient_eof_retries_are_exhausted tests/test_pr_flow_cli.py::test_tweak_auto_pushes_clean_unprotected_branch_without_upstream tests/test_pr_flow_cli.py::test_complete_reports_dispatch_when_ruleset_blocks_merge tests/test_pr_flow_cli.py::test_complete_returns_checks_pending_when_ruleset_recovery_wait_times_out -q
```

Expected（预期）: FAIL（失败）。失败点应包含当前 `gh`（GitHub 命令行）鉴权仍是 `gh_pr_view_failed`（查看拉取请求失败）、`--fixes None`（修复问题编号为空）仍是普通 `EXCEPTION_REQUIRED`（需要人工处理）、checks（检查）或 ruleset（规则集）缺恢复动作。

---

### Task 2: PR Flow（拉取请求流程）最小实现

**Files（文件）:**
- Modify（修改）: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Test（测试）: `tests/test_pr_flow_cli.py`

- [x] **Step 1: Add shared recovery helpers（添加共享恢复辅助函数）**

在 `command_failure_details`（命令失败详情）附近加入，保持普通字典，不引入新对象：

```python
GH_AUTH_REQUIRED_MARKERS = (
    "gh auth login",
    "not logged into any github hosts",
    "authentication required",
    "requires authentication",
    "bad credentials",
    "http 401",
)

RECOVERABLE_NEXT_ACTIONS = {
    "checks_pending": {
        "nextAction": "Wait for GitHub checks to finish, then rerun the same PR Flow command.",
    },
    "checks_or_review_blocking": {
        "nextAction": "Fix failing checks or requested changes, then rerun the same PR Flow command.",
    },
    "ruleset_merge_blocking": {
        "nextAction": "Wait for ruleset requirements to pass or enable auto-merge, then rerun the same PR Flow command.",
    },
    "gh_auth_required": {
        "nextCommand": "gh auth status",
    },
}


def gh_auth_required(result: subprocess.CompletedProcess[str]) -> bool:
    text = f"{result.stdout}\n{result.stderr}".lower()
    return any(marker in text for marker in GH_AUTH_REQUIRED_MARKERS)


def classify_command_failure(reason: str, result: subprocess.CompletedProcess[str]) -> str:
    if reason.startswith("gh_") and gh_auth_required(result):
        return "gh_auth_required"
    return reason


def add_recovery_action(details: dict[str, Any], next_command: str | None = None) -> dict[str, Any]:
    reason = str(details.get("reason") or "")
    if next_command and reason in {"gh_pr_view_transient_failed", "checks_pending", "ruleset_merge_blocking"}:
        details.setdefault("nextCommand", next_command)
    for key, value in RECOVERABLE_NEXT_ACTIONS.get(reason, {}).items():
        details.setdefault(key, value)
    return details
```

把 `command_failure_details`（命令失败详情）改成使用分类结果：

```python
def command_failure_details(reason: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    classified_reason = classify_command_failure(reason, result)
    return add_recovery_action(
        {
            "reason": classified_reason,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    )
```

- [x] **Step 2: Route status by classified reason（按分类后的原因返回状态）**

替换 `error_status`（错误状态）：

```python
def error_status(reason: str) -> str:
    if reason in {"gh_auth_required", "gh_pr_view_transient_failed", "checks_pending", "ruleset_merge_blocking"}:
        return "DISPATCH_REQUIRED"
    if reason in {"checks_or_review_blocking", "invalid_fixes"}:
        return "REPLY_OR_FIX_REQUIRED"
    return "EXCEPTION_REQUIRED"
```

替换 `add_default_next_command`（添加默认下一条命令），让旧调用点继续工作：

```python
def add_default_next_command(details: dict[str, Any], next_command: str | None) -> dict[str, Any]:
    return add_recovery_action(details, next_command)
```

在 `pr_view_failure_details`（查看拉取请求失败详情）中使用分类后的 `reason`（原因）：

```python
def pr_view_failure_details(
    result: subprocess.CompletedProcess[str],
    transient_category: str,
    retry_attempts: int,
    *,
    pr: str | None = None,
    next_command: str | None = None,
) -> tuple[str, dict[str, Any]]:
    reason = "gh_pr_view_transient_failed" if transient_category else "gh_pr_view_failed"
    details = command_failure_details(reason, result)
    reason = str(details["reason"])
    if pr is not None:
        details["pr"] = pr
    if transient_category:
        details["transientCategory"] = transient_category
        details["retryAttempts"] = retry_attempts
    add_recovery_action(details, next_command)
    return reason, details
```

- [x] **Step 3: Add action to checks and ruleset stops（给检查和规则集停止补动作）**

在 `wait_for_checks`（等待检查）中返回前补恢复动作：

```python
if has_failing_check(checks):
    details["reason"] = "checks_or_review_blocking"
    return stop_state("REPLY_OR_FIX_REQUIRED", "checks_or_review_blocking", add_recovery_action(details))
if not has_pending_check(checks):
    return None
if timeout_seconds <= 0:
    return stop_state("DISPATCH_REQUIRED", "checks_pending", add_recovery_action(details))

remaining = timeout_seconds - (time.monotonic() - started_at)
if remaining <= 0:
    return stop_state("DISPATCH_REQUIRED", "checks_pending", add_recovery_action(details))
```

在 `merge_pr`（合并拉取请求）中，ruleset（规则集）阻塞时补恢复动作：

```python
if gh_pr_merge_policy_blocked(result):
    details["reason"] = "ruleset_merge_blocking"
    details["autoMergeSuggested"] = gh_pr_merge_auto_suggested(result)
    raise PrFlowError("ruleset_merge_blocking", add_recovery_action(details))
```

在 `run_diagnose`（运行诊断）中 pending checks（等待检查）分支补恢复动作：

```python
if has_pending_check(checks):
    gh_details["reason"] = "checks_pending"
    return stop(project, args.command, "DISPATCH_REQUIRED", "checks_pending", add_recovery_action(gh_details, command_next_command(args.command, project)))
```

- [x] **Step 4: Make `--fixes None` actionable（让修复问题编号为空可恢复）**

在 `require_pr_body_args`（要求拉取请求正文参数）中替换 `invalid_fixes`（无效修复编号）处理：

```python
if invalid_fixes:
    next_action = "Pass each issue number separately, for example --fixes 41 --fixes 43 --fixes 44."
    if any(issue.lower() == "none" for issue in invalid_fixes):
        next_action = "Remove --fixes when there is no issue to close."
    raise PrFlowError(
        "invalid_fixes",
        {
            "reason": "invalid_fixes",
            "invalidFixes": invalid_fixes,
            "nextAction": next_action,
        },
    )
```

在 `run_complete`（运行收尾）和 `run_tweak`（运行小改）的 `except PrFlowError`（捕获流程错误）分支改用 `error_status`（错误状态）：

```python
except PrFlowError as exc:
    return stop(project, args.command, error_status(exc.reason), exc.reason, add_recovery_action(exc.details))
```

- [x] **Step 5: Run PR Flow tests（运行拉取请求流程测试）**

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_diagnose_reports_dispatch_for_gh_auth_failure tests/test_pr_flow_cli.py::test_pr_body_commands_reject_none_fixes_with_remove_guidance tests/test_pr_flow_cli.py::test_diagnose_reports_dispatch_when_transient_eof_retries_are_exhausted tests/test_pr_flow_cli.py::test_tweak_auto_pushes_clean_unprotected_branch_without_upstream tests/test_pr_flow_cli.py::test_complete_reports_dispatch_when_ruleset_blocks_merge tests/test_pr_flow_cli.py::test_complete_returns_checks_pending_when_ruleset_recovery_wait_times_out -q
```

Expected（预期）: PASS（通过）。

- [x] **Step 6: Commit（提交）**

```powershell
git add tests/test_pr_flow_cli.py plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py
git commit -m "补齐 PR Flow 恢复动作"
```

Expected（预期）: 创建一个只包含 PR Flow（拉取请求流程）测试和实现的 commit（提交）。

---

### Task 3: Release Flow（发布流程）preflight（发布预检）恢复动作

**Files（文件）:**
- Modify（修改）: `tests/test_release_flow_cli.py`
- Modify（修改）: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`

- [x] **Step 1: Write failing tests（写失败测试）**

在 `tests/test_release_flow_cli.py` 的 preflight（发布预检）测试附近加入：

```python
def test_preflight_source_ref_requires_pr_prints_next_action(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["source_ref_requires_pr: main: plugins/agent-guard/.codex-plugin/plugin.json"],
        bump_plugins=["agent-guard"],
    )

    assert result.returncode == 1
    assert "error: source_ref_requires_pr: main: plugins/agent-guard/.codex-plugin/plugin.json" in result.stdout
    assert "nextAction: create and merge the version bump through PR Flow, then rerun release-flow preflight" in result.stdout


def test_preflight_manifest_mismatch_prints_next_action(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["manifest_version_mismatch: plugins/agent-guard/.codex-plugin/plugin.json"],
        bump_plugins=["agent-guard"],
    )

    assert result.returncode == 1
    assert "error: manifest_version_mismatch: plugins/agent-guard/.codex-plugin/plugin.json" in result.stdout
    assert "nextAction: correct the manifest version in plugins/agent-guard/.codex-plugin/plugin.json, then rerun release-flow preflight" in result.stdout


def test_preflight_existing_release_prints_next_action(tmp_path: Path, monkeypatch) -> None:
    result = run_preflight_with_errors(
        monkeypatch,
        tmp_path,
        ["release already exists: v0.1.1"],
        bump_plugins=["agent-guard"],
    )

    assert result.returncode == 1
    assert "error: release already exists: v0.1.1" in result.stdout
    assert "nextAction: choose a new release version and rerun release-flow preflight" in result.stdout
```

- [x] **Step 2: Run tests to verify failure（运行测试确认失败）**

Run（运行）:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_preflight_source_ref_requires_pr_prints_next_action tests/test_release_flow_cli.py::test_preflight_manifest_mismatch_prints_next_action tests/test_release_flow_cli.py::test_preflight_existing_release_prints_next_action -q
```

Expected（预期）: FAIL（失败）。失败点是 `nextAction`（下一步动作）行缺失。

- [x] **Step 3: Add output-only formatter（添加只影响输出的格式化函数）**

在 `preflight_errors`（预检错误）后、`run_preflight`（运行预检）前加入：

```python
def preflight_next_action(error: str) -> str:
    if error.startswith("source_ref_requires_pr: "):
        return "create and merge the version bump through PR Flow, then rerun release-flow preflight"
    if error.startswith("manifest_version_mismatch: "):
        manifest_path = error.split(": ", 1)[1]
        return f"correct the manifest version in {manifest_path}, then rerun release-flow preflight"
    if error.startswith("release already exists: "):
        return "choose a new release version and rerun release-flow preflight"
    return ""


def print_preflight_errors(errors: list[str]) -> None:
    for error in errors:
        print(f"error: {error}")
        next_action = preflight_next_action(error)
        if next_action:
            print(f"nextAction: {next_action}")
```

在 `run_preflight`（运行预检）和 `run_ci_publish`（运行 CI 发布）中替换错误打印循环：

```python
if errors:
    print("status: issues")
    print_preflight_errors(errors)
    return 1
```

- [x] **Step 4: Run Release Flow tests（运行发布流程测试）**

Run（运行）:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_preflight_source_ref_requires_pr_prints_next_action tests/test_release_flow_cli.py::test_preflight_manifest_mismatch_prints_next_action tests/test_release_flow_cli.py::test_preflight_existing_release_prints_next_action tests/test_release_flow_cli.py::test_publish_rejects_dry_run_argument tests/test_release_flow_cli.py::test_publish_retries_workflow_run_eof_then_succeeds -q
```

Expected（预期）: PASS（通过）。preflight（发布预检）有 `nextAction`（下一步动作）；publish（发布）行为不变，`--dry-run`（试运行）仍按现有形态拒绝。

- [x] **Step 5: Commit（提交）**

```powershell
git add tests/test_release_flow_cli.py plugins/release-flow/skills/release-flow/scripts/release_flow.py
git commit -m "补齐 Release Flow 预检恢复动作"
```

Expected（预期）: 创建一个只包含 Release Flow（发布流程）测试和实现的 commit（提交）。

---

### Task 4: 仓库级防回归检查

**Files（文件）:**
- Modify（修改）: `tests/test_pr_flow_plugin_package.py`
- Test（测试）: `tests/test_pr_flow_plugin_package.py`

- [x] **Step 1: Write guard test（写防回归测试）**

在 `tests/test_pr_flow_plugin_package.py` 的 `run_pr_flow`（运行拉取请求流程）测试后加入：

```python
def test_recoverable_stop_states_have_recovery_actions() -> None:
    module = pr_flow_module()
    recoverable_reasons = {
        "gh_auth_required",
        "gh_pr_view_transient_failed",
        "checks_pending",
        "checks_or_review_blocking",
        "ruleset_merge_blocking",
        "invalid_fixes",
    }

    for reason in recoverable_reasons:
        assert module.error_status(reason) in {"DISPATCH_REQUIRED", "PUSH_REQUIRED", "REPLY_OR_FIX_REQUIRED"}

    for reason in recoverable_reasons - {"gh_pr_view_transient_failed", "invalid_fixes"}:
        details = module.add_recovery_action({"reason": reason})
        assert "nextAction" in details or "nextCommand" in details
```

- [x] **Step 2: Run guard test（运行防回归测试）**

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_plugin_package.py::test_recoverable_stop_states_have_recovery_actions -q
```

Expected（预期）: PASS（通过）。如果 Task 2（任务 2）未完成，应 FAIL（失败）并指出缺少恢复动作。

- [x] **Step 3: Commit（提交）**

```powershell
git add tests/test_pr_flow_plugin_package.py
git commit -m "增加恢复动作防回归检查"
```

Expected（预期）: 创建一个只包含仓库级防回归测试的 commit（提交）。

---

### Task 5: Focused Verification（聚焦验证）

**Files（文件）:**
- Verify（验证）: `tests/test_pr_flow_cli.py`
- Verify（验证）: `tests/test_release_flow_cli.py`
- Verify（验证）: `tests/test_pr_flow_plugin_package.py`

- [x] **Step 1: Run focused CLI tests（运行聚焦命令行测试）**

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py tests/test_release_flow_cli.py tests/test_pr_flow_plugin_package.py -q
```

Expected（预期）: PASS（通过）。PR Flow（拉取请求流程）、Release Flow（发布流程）和仓库级检查都通过。

- [x] **Step 2: Run fast repository verification（运行快速仓库验证）**

Run（运行）:

```powershell
python .build-and-verify/runtime/build_and_verify.py verify --project . --fast
```

Expected（预期）: `status: passed`（状态通过）或等价成功输出；命令退出码为 `0`。

---

### Task 6: End-to-End Regression（端到端回归）

**Files（文件）:**
- Verify（验证）: `tests/test_pr_flow_cli.py`
- Verify（验证）: `tests/test_release_flow_cli.py`

- [x] **Step 1: Run PR Flow user entrypoint regression（运行拉取请求流程用户入口回归）**

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_complete_fills_existing_empty_body_before_checks tests/test_pr_flow_cli.py::test_complete_reports_dispatch_when_ruleset_blocks_merge tests/test_pr_flow_cli.py::test_diagnose_reports_dispatch_when_transient_eof_retries_are_exhausted tests/test_pr_flow_cli.py::test_cleanup_merged_pr_checks_out_base_pulls_and_deletes_branches -q
```

Expected（预期）: PASS（通过）。这些测试从 `main()`（主入口）调用 PR Flow（拉取请求流程）用户命令，覆盖创建/收尾、诊断恢复、ruleset（规则集）阻塞和 cleanup（清理）。

- [x] **Step 2: Run Release Flow preflight and publish shape regression（运行发布流程预检和发布形态回归）**

Run（运行）:

```powershell
python -m pytest tests/test_release_flow_cli.py::test_preflight_source_ref_requires_pr_prints_next_action tests/test_release_flow_cli.py::test_preflight_manifest_mismatch_prints_next_action tests/test_release_flow_cli.py::test_preflight_existing_release_prints_next_action tests/test_release_flow_cli.py::test_publish_rejects_dry_run_argument tests/test_release_flow_cli.py::test_publish_retries_workflow_run_eof_then_succeeds -q
```

Expected（预期）: PASS（通过）。preflight（发布预检）输出恢复动作；publish（发布）授权和当前 dry-run（试运行）拒绝形态不变。

- [x] **Step 3: Final status check（最终状态检查）**

Run（运行）:

```powershell
git status --short
```

Expected（预期）: 只显示本 change（变更）相关文件；没有未预期文件、状态文件或生成物。

- [x] **Step 4: Final commit if verification changed files（如验证后还有文件变更则提交）**

如果 Step 3（步骤 3）显示还有已验证但未提交的相关文件：

```powershell
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py plugins/release-flow/skills/release-flow/scripts/release_flow.py tests/test_pr_flow_cli.py tests/test_release_flow_cli.py tests/test_pr_flow_plugin_package.py
git commit -m "完成恢复动作稳定化验证"
```

Expected（预期）: 没有遗漏的实现或测试文件。
