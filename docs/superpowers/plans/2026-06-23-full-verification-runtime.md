---
change: optimize-full-verification-runtime
design-doc: docs/superpowers/specs/2026-06-23-full-verification-runtime-design.md
base-ref: e15b4dbea94b773f100343b0654f60f4a5f12489
---

# Full Verification Runtime（完整验证耗时）Implementation Plan（实施计划）

我正在使用 writing-plans（编写计划）技能创建 implementation plan（实施计划）。

> **For agentic workers（面向代理执行者）:** REQUIRED SUB-SKILL（必须子技能）: 使用 superpowers:subagent-driven-development（子代理驱动开发，推荐）或 superpowers:executing-plans（执行计划）逐项实施。步骤使用 checkbox（复选框）语法跟踪。

**Goal（目标）:** 将本仓库 full verification（完整验证）压到本机 60 秒以内，同时保留 local build contract（本地构建契约）、PR Flow（拉取请求流程）、Release Flow（发布流程）、Agent Guard（代理守卫）、cross-agent-review（跨代理审查）、Test Framework（测试框架）和 OpenSpec（开放规格）的行为覆盖。

**Architecture（架构）:** 先做 repo-native（仓库内自带）测试优化：共享 Git（版本管理）fixture（测试夹具）、fake gh（模拟 GitHub 命令行工具）stub（替身）、in-process（进程内）调用、必要 end-to-end（端到端）路径保留。再在 Test Framework（测试框架）runner（运行器）统一协调所有 verify check（验证检查项）的并行运行和 serial fallback（串行兜底）。pytest-xdist（并行测试插件）只在项目环境已可用或用户明确授权安装后接入，让 pytest（Python 测试框架）检查项内部并行。

**Tech Stack（技术栈）:** Python（Python 语言）standard library（标准库）、pytest（Python 测试框架）、Git（版本管理）、OpenSpec（规格流程）、Test Framework（测试框架）；pytest-xdist（并行测试插件）为条件接入项。

---

## Scope Guard（范围护栏）

- 本计划只指导后续实施；本计划本身只新增这个 plan（实施计划）文件，后续实施按 File Structure（文件结构）修改。
- 实施期间不得修改 `docs/rules/` 下任何文件；测试规则只沉淀在 OpenSpec（规格流程）产物、Design Doc（设计文档）和本 plan（实施计划）中。
- 不回滚、不清理当前工作区已有旧归档改动；遇到无关 dirty file（未提交文件）只记录，不处理。
- 不靠 marker-filtered（测试标记过滤）子集、删除测试或跳过 full verification（完整验证）达标。
- 不在未获用户明确授权时 commit（提交）、push（推送）、切换分支或合并分支。
- `base-ref` 说明：本 plan（实施计划）文件头的 `base-ref` 是 implementation baseline（实施基准），来自计划生成前的 `git rev-parse HEAD`；`.comet.yaml` 里的 `base_ref` 是 change init baseline（变更初始化基准），两者允许不同，不要互相覆盖。

## File Structure（文件结构）

- Modify（修改）: `docs/superpowers/specs/2026-06-23-full-verification-runtime-design.md`，记录 baseline（基线）和 after（优化后）计时证据。
- Modify（修改）: `openspec/changes/optimize-full-verification-runtime/tasks.md`，只在对应验证证据存在后勾选任务。
- Modify（修改）: `openspec/changes/optimize-full-verification-runtime/specs/full-verification-runtime/spec.md`，如实现中发现契约需要更精确表达，只按 OpenSpec（规格流程）标准更新。
- Create（新建）: `tests/conftest.py`，放全仓库共享 fixture（测试夹具）入口。
- Create（新建）: `tests/support/git_templates.py`，封装不可变 Git（版本管理）模板、按测试复制的 project（项目）和 remote（远端）仓库。
- Create（新建）: `tests/support/command_stubs.py`，封装 CompletedProcess（完成进程结果）构造、fake gh（模拟 GitHub 命令行工具）stub（替身）和 call recorder（调用记录器）。
- Create（新建）: `tests/support/pr_flow_invocation.py`，封装 PR Flow（拉取请求流程）in-process（进程内）调用和 stdout/stderr（标准输出/标准错误）捕获。
- Modify（修改）: `tests/test_pr_flow_cli.py`，先行优化 PR Flow（拉取请求流程）慢测试。
- Modify（修改）: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`，仅在测试注入现有 `main()`、`git()`、`gh()`、`run_hotfix_verify_command()` 仍不够时增加窄 test seam（测试接缝）；不得改变用户可见 CLI（命令行界面）行为。
- Modify（修改）: `plugins/test-framework/skills/test-framework/scripts/test_framework_runner.py`，增加 suite-wide（全套）并行协调、serial fallback（串行兜底）和耗时汇总。
- Modify（修改）: `plugins/test-framework/skills/test-framework/scripts/test_framework.py`，只在 runner（运行器）需要新的 full verify（完整验证）参数时透传。
- Modify（修改）: `tests/test_test_framework_plugin.py`，覆盖并行调度、串行兜底、失败汇总和 full（完整）不走 cache skip（缓存跳过）。
- Modify（修改）: `.test-framework/config.json`，为所有 verify check（验证检查项）声明 parallel（并行）/serial（串行）策略；只有当 pytest-xdist（并行测试插件）已可用或用户授权安装后，才给 pytest（Python 测试框架）命令接入 `-n auto`。
- Modify（修改）: `pyproject.toml`，只在采用 pytest-xdist（并行测试插件）时记录 pytest（Python 测试框架）配置。
- Create（新建）: `requirements-dev.txt`，仅当最终决定采用 pytest-xdist（并行测试插件）、用户已授权依赖记录、且没有其它依赖声明位置时创建；未采用时不创建依赖文件。

## Commit Policy（提交策略）

仓库规则要求 commit（提交）必须由用户明确授权。实施者每个 task（任务）完成后只运行验证并汇报，不执行 `git commit`。

## Task 1: Baseline（基线）计时和耗时归因

**Files（文件）:**
- Modify（修改）: `docs/superpowers/specs/2026-06-23-full-verification-runtime-design.md`
- Read（读取）: `.test-framework/config.json`
- Read（读取）: `tests/test_pr_flow_cli.py`

- [ ] **Step 1: 记录当前工作区状态**

Run（运行）:

```powershell
git status --short
git rev-parse HEAD
```

Expected（期望）:
- `git rev-parse HEAD` 输出 `e15b4dbea94b773f100343b0654f60f4a5f12489`，除非用户已经明确切换 base（基准）。
- `git status --short` 可以有旧归档改动；只记录，不回滚、不清理。

- [ ] **Step 2: 重跑 full verification（完整验证）计时**

Run（运行）:

```powershell
$sw = [System.Diagnostics.Stopwatch]::StartNew()
python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full
$sw.Stop()
"full_verify_seconds={0:N2}" -f $sw.Elapsed.TotalSeconds
```

Expected（期望）:
- 命令完整运行所有 `.test-framework/config.json` 里的 verify check（验证检查项）。
- 输出包含 `full-not-run: false` 和最终 `status:`。
- 这是当前仓库的 canonical full verification command（规范完整验证命令）；当前工作区不存在 `scripts/check.py`，不得把不可运行入口写入验收步骤。
- 记录总秒数，作为 before（优化前）证据。

- [ ] **Step 3: 重跑 pytest durations（耗时报告）**

Run（运行）:

```powershell
python -m pytest --durations=25 -q
python -m pytest tests/test_pr_flow_cli.py --durations=25 -q
python -m pytest tests/test_test_framework_plugin.py --durations=15 -q
```

Expected（期望）:
- 每条命令结束后都有 slowest durations（最慢耗时）列表。
- 如果某条失败，先记录失败测试名和失败原因，不直接修代码。

- [ ] **Step 4: 按 verify check（验证检查项）分组计时**

Run（运行）:

```powershell
$config = Get-Content -Raw .test-framework/config.json | ConvertFrom-Json
foreach ($check in $config.verify.checks) {
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  if ($check.command -is [System.Array]) {
    $exe = [string]$check.command[0]
    $argv = @($check.command | Select-Object -Skip 1)
    & $exe @argv
  } else {
    powershell -NoProfile -Command ([string]$check.command)
  }
  $code = $LASTEXITCODE
  $sw.Stop()
  "{0} seconds={1:N2} code={2}" -f $check.id, $sw.Elapsed.TotalSeconds, $code
}
```

Expected（期望）:
- 看到 `verify.pr-flow`、`verify.agent-guard`、`verify.release-flow`、`verify.cross-agent-review`、`verify.test-framework`、`verify.openspec` 等分组耗时。
- 最大耗时组会指导后续优化优先级；预期 PR Flow（拉取请求流程）仍是第一目标。

- [ ] **Step 5: 写入 Design Doc（设计文档）证据块**

在 `docs/superpowers/specs/2026-06-23-full-verification-runtime-design.md` 末尾追加：

```markdown
## Baseline Evidence（基线证据）

- plan base-ref（实施基准提交）: e15b4dbea94b773f100343b0654f60f4a5f12489
- comet init base-ref（变更初始化基准提交）: b58fde2cf4ddcc91316737670271c938bc83714f
- full verification（完整验证）before: 复制 Step 2 打印的 `full_verify_seconds` 数值
- slowest pytest durations（最慢 pytest 耗时）: 复制 Step 3 输出中最慢的 5 项
- verify check（验证检查项）group timings（分组耗时）: 逐行复制 Step 4 的 `id seconds code` 结果
- largest contributor（最大耗时来源）: 写 Step 4 中 seconds（秒数）最高的 verify check（验证检查项）id
```

Expected（期望）:
- 证据只写 Design Doc（设计文档），不写 `docs/rules/`。

## Task 2: 全仓库 repo-native（仓库内自带）测试优化规则落地

**Files（文件）:**
- Create（新建）: `tests/conftest.py`
- Create（新建）: `tests/support/git_templates.py`
- Create（新建）: `tests/support/command_stubs.py`
- Create（新建）: `tests/support/pr_flow_invocation.py`
- Modify（修改）: `openspec/changes/optimize-full-verification-runtime/specs/full-verification-runtime/spec.md`

- [ ] **Step 1: 写共享 helper（辅助函数）的失败测试**

Create（新建）或追加到 `tests/test_pr_flow_cli.py` 的顶部辅助测试附近：

```python
def test_command_stub_records_gh_calls() -> None:
    from tests.support.command_stubs import CommandStub

    stub = CommandStub()
    stub.add(["pr", "view"], stdout="{\"number\":1}\n", returncode=0)

    result = stub("gh", "pr", "view")

    assert result.returncode == 0
    assert result.stdout == "{\"number\":1}\n"
    assert stub.calls == [("gh", "pr", "view")]


def test_pr_flow_in_process_invocation_captures_output(tmp_path: Path) -> None:
    from tests.support.pr_flow_invocation import invoke_pr_flow

    result = invoke_pr_flow(["init", "--project", str(tmp_path)])

    assert result.returncode == 0
    assert "status: initialized" in result.stdout
    assert result.stderr == ""
```

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_command_stub_records_gh_calls tests/test_pr_flow_cli.py::test_pr_flow_in_process_invocation_captures_output -q
```

Expected（期望）:
- FAIL（失败），因为 `tests/support` helper（辅助函数）还不存在。

- [ ] **Step 2: 新建 command stub（命令替身）helper（辅助函数）**

Create（新建）`tests/support/command_stubs.py`:

```python
from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


def completed(
    args: Sequence[str],
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=list(args),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


@dataclass
class CommandStub:
    responses: list[tuple[tuple[str, ...], subprocess.CompletedProcess[str]]] = field(
        default_factory=list
    )
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def add(
        self,
        args: Sequence[str],
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ) -> None:
        key = tuple(args)
        self.responses.append((key, completed(key, stdout=stdout, stderr=stderr, returncode=returncode)))

    def __call__(self, *args: str, **_: Any) -> subprocess.CompletedProcess[str]:
        call = tuple(args)
        self.calls.append(call)
        normalized = call[1:] if call and call[0] == "gh" else call
        for expected, response in self.responses:
            if expected == normalized or expected == call:
                return completed(call, stdout=response.stdout, stderr=response.stderr, returncode=response.returncode)
        return completed(call, stderr=f"unexpected_command: {' '.join(call)}\n", returncode=1)
```

- [ ] **Step 3: 新建 PR Flow（拉取请求流程）进程内调用 helper（辅助函数）**

Create（新建）`tests/support/pr_flow_invocation.py`:

```python
from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow" / "scripts" / "pr_flow.py"


def load_pr_flow_module():
    spec = importlib.util.spec_from_file_location("pr_flow_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"missing_pr_flow_script: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def invoke_pr_flow(argv: list[str], *, module=None) -> subprocess.CompletedProcess[str]:
    if module is None:
        module = load_pr_flow_module()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        returncode = int(module.main(argv))
    return subprocess.CompletedProcess(
        args=[str(SCRIPT), *argv],
        returncode=returncode,
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
    )
```

- [ ] **Step 4: 新建 Git（版本管理）模板 helper（辅助函数）**

Create（新建）`tests/support/git_templates.py`:

```python
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def run_git(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def init_user(project: Path) -> None:
    run_git(project, "config", "user.email", "test@example.com")
    run_git(project, "config", "user.name", "Test User")


def copy_template(source: Path, target: Path) -> Path:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git/hooks"))
    return target
```

- [ ] **Step 5: 暴露全仓库 fixture（测试夹具）入口**

Create（新建）`tests/conftest.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.git_templates import init_user, run_git


@pytest.fixture(scope="session")
def bare_remote_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    remote = tmp_path_factory.mktemp("git-template") / "remote.git"
    result = __import__("subprocess").run(
        ["git", "init", "--bare", str(remote)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return remote


@pytest.fixture
def git_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    result = __import__("subprocess").run(
        ["git", "init", "-b", "main"],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        result = __import__("subprocess").run(
            ["git", "init"],
            cwd=project,
            check=False,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        run_git(project, "checkout", "-b", "main")
    init_user(project)
    (project / "README.md").write_text("# Test Project\n", encoding="utf-8")
    run_git(project, "add", "README.md")
    run_git(project, "commit", "-m", "initial")
    return project
```

- [ ] **Step 6: 运行 helper（辅助函数）测试**

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py::test_command_stub_records_gh_calls tests/test_pr_flow_cli.py::test_pr_flow_in_process_invocation_captures_output -q
```

Expected（期望）:
- PASS（通过）。

- [ ] **Step 7: 在 OpenSpec（规格流程）中沉淀测试写法规则**

如果 `openspec/changes/optimize-full-verification-runtime/specs/full-verification-runtime/spec.md` 还没有明确以下规则，追加或收紧对应 requirement（要求）：

```markdown
#### Scenario: Shared test helpers are repository-wide
- **WHEN** tests need repeated Git（版本管理）state, fake CLI（命令行界面）responses, or in-process（进程内）command execution
- **THEN** they SHOULD use shared helpers under `tests/support/`
- **THEN** they MUST keep required end-to-end（端到端）paths for user-facing workflows
- **THEN** they MUST NOT document the rule under `docs/rules/`
```

Run（运行）:

```powershell
openspec validate optimize-full-verification-runtime --strict --no-interactive
```

Expected（期望）:
- PASS（通过）。
- `docs/rules/` 没有任何改动。

## Task 3: PR Flow（拉取请求流程）先行优化

**Files（文件）:**
- Modify（修改）: `tests/test_pr_flow_cli.py`
- Modify（修改）: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`，仅在现有 monkeypatch（运行时替换）能力不足时修改。
- Use（使用）: `tests/support/git_templates.py`
- Use（使用）: `tests/support/command_stubs.py`
- Use（使用）: `tests/support/pr_flow_invocation.py`

- [ ] **Step 1: 标记必须保留的真实 end-to-end（端到端）路径**

在 `tests/test_pr_flow_cli.py` 中保留这些真实路径继续使用 subprocess（子进程）和真实 Git（版本管理）状态：

```python
def test_complete_creates_pr_when_none_exists_then_merges_and_cleans_up(tmp_path: Path) -> None:
    ...

def test_cleanup_merged_pr_checks_out_base_pulls_and_deletes_branches(tmp_path: Path) -> None:
    ...

def test_hotfix_pushes_head_to_target_and_writes_audit_record(tmp_path: Path) -> None:
    ...
```

Expected（期望）:
- 这三类路径仍覆盖 complete（完成）、cleanup（清理）和 hotfix（热修复）的真实 CLI（命令行界面）+ Git（版本管理）行为。

- [ ] **Step 2: 把 diagnose（诊断）stop state（停机状态）矩阵改为 in-process（进程内）调用**

将 `test_diagnose_outputs_dispatch_required_for_pending_checks`、`test_diagnose_outputs_reply_or_fix_required_for_failing_checks`、`test_diagnose_outputs_reply_or_fix_required_for_changes_requested`、`test_diagnose_outputs_reply_or_fix_required_for_review_required`、`test_diagnose_outputs_ready_when_no_stop_state_remains`、`test_diagnose_outputs_dispatch_required_for_draft_pr` 合并为参数化测试：

```python
@pytest.mark.parametrize(
    ("pr_json", "expected_status"),
    [
        (pr_view_json(checks=[{"status": "PENDING"}]), "DISPATCH_REQUIRED"),
        (pr_view_json(checks=[{"conclusion": "FAILURE"}]), "REPLY_OR_FIX_REQUIRED"),
        (pr_view_json(review_decision="CHANGES_REQUESTED"), "REPLY_OR_FIX_REQUIRED"),
        (pr_view_json(review_decision="REVIEW_REQUIRED"), "REPLY_OR_FIX_REQUIRED"),
        (pr_view_json(review_decision="APPROVED"), "READY"),
        (pr_view_json(is_draft=True), "DISPATCH_REQUIRED"),
    ],
)
def test_diagnose_stop_states_use_in_process_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pr_json: str,
    expected_status: str,
) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    init_repo(project)
    configure_complete(project, review_mode="github")

    def fake_gh(project_arg: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["gh", *args], 0, pr_json, "")

    monkeypatch.setattr(module, "gh", fake_gh)
    result = invoke_pr_flow(["diagnose", "--project", str(project)], module=module)

    assert result.returncode == 0
    assert expected_status in result.stdout
```

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py -k "diagnose_stop_states" -q
```

Expected（期望）:
- PASS（通过）。
- 原重复 fake gh（模拟 GitHub 命令行工具）脚本调用可以删除或改为共享 stub（替身）。

- [ ] **Step 3: 把 fake gh（模拟 GitHub 命令行工具）脚本矩阵改为 stub（替身）**

对 complete（完成）和 tweak（小改）分支测试优先 monkeypatch（运行时替换）`pr_flow.gh`：

```python
def test_complete_uses_configured_merge_strategy_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_pr_flow_module()
    project, _remote = init_complete_project(tmp_path, merge_strategy="squash")
    stub = CommandStub()
    stub.add(["pr", "view", "--json", module.PR_VIEW_FIELDS], stdout=passing_pr_view_json(project))
    stub.add(["pr", "merge", "1", "--squash", "--delete-branch"], stdout="")

    monkeypatch.setattr(module, "gh", lambda project_arg, *args: stub("gh", *args))
    result = invoke_pr_flow(["complete", "--project", str(project)], module=module)

    assert result.returncode == 0, result.stdout + result.stderr
    assert ("gh", "pr", "merge", "1", "--squash", "--delete-branch") in stub.calls
```

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py -k "complete_uses_configured_merge_strategy_flag or tweak" -q
```

Expected（期望）:
- PASS（通过）。
- 不再为这些分支写临时 `gh` 可执行脚本。

- [ ] **Step 4: 降低 repeated Git（重复版本管理）setup（初始化）**

把只需要配置差异、不会 push（推送）或 mutate remote（修改远端）的 complete（完成）矩阵改成复用 immutable template（不可变模板）。仍会 push（推送）、clone（克隆）、delete remote branch（删除远端分支）或验证真实 remote（远端）状态的测试继续走 `init_complete_project()`：

```python
@pytest.fixture(scope="session")
def complete_project_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("complete-template")
    project, _remote = init_complete_project(root, review_mode="github")
    return project


@pytest.fixture
def fast_complete_project(
    tmp_path: Path,
    complete_project_template: Path,
) -> Path:
    from tests.support.git_templates import copy_template

    project = copy_template(complete_project_template, tmp_path / "project")
    git(project, "checkout", "feature/example")
    return project
```

然后删除等价重复初始化，只把不依赖真实 remote（远端）变更的 branch-state（分支状态）、review gate（审查门禁）和 stop-state（停机状态）矩阵迁到 `fast_complete_project`；完整 lifecycle（生命周期）测试继续走真实 `init_complete_project()`。

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py -k "complete" --durations=15 -q
```

Expected（期望）:
- complete/tweak（完成/小改）分组耗时接近或低于 25 秒。
- 必须保留的真实 complete（完成）生命周期仍通过。

- [ ] **Step 5: 优化 cleanup（清理）和 hotfix（热修复）错误分支**

对以下错误分支使用 monkeypatch（运行时替换）或更小 Git（版本管理）状态：

```python
test_cleanup_rejects_pr_state_that_is_not_merged
test_cleanup_rejects_dirty_worktree
test_cleanup_rejects_head_branch_equal_to_base_branch
test_cleanup_rejects_current_branch_mismatch
test_hotfix_rejects_authorization_phrase_mismatch_without_leaking_phrase
test_hotfix_missing_authorization_config_does_not_run_verify_command
test_hotfix_rejects_target_branch_without_allow_hotfix_push
test_hotfix_requires_explicit_target_branch_allow_hotfix_push
```

Pattern（写法）:

```python
def test_cleanup_rejects_pr_state_that_is_not_merged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    init_repo(project)
    configure_complete(project, review_mode="github")
    git(project, "checkout", "-b", "feature/example")

    monkeypatch.setattr(
        module,
        "gh",
        lambda project_arg, *args: subprocess.CompletedProcess(
            ["gh", *args],
            0,
            cleanup_pr_view_json(state="OPEN"),
            "",
        ),
    )
    result = invoke_pr_flow(["cleanup", "--project", str(project), "--pr", "1"], module=module)

    assert result.returncode == 1
    assert "EXCEPTION_REQUIRED" in result.stdout
    assert "pr_not_merged" in result.stdout
```

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py -k "cleanup or hotfix" --durations=15 -q
```

Expected（期望）:
- cleanup+hotfix（清理+热修复）分组耗时接近或低于 20 秒。
- `test_cleanup_merged_pr_checks_out_base_pulls_and_deletes_branches` 和 `test_hotfix_pushes_head_to_target_and_writes_audit_record` 仍为真实 end-to-end（端到端）路径。

- [ ] **Step 6: 重跑 PR Flow（拉取请求流程）目标测试**

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py --durations=25 -q
```

Expected（期望）:
- PASS（通过）。
- `tests/test_pr_flow_cli.py` 不再是 full suite（全套测试）中压倒性耗时来源。
- 如果超过目标，继续按 durations（耗时报告）处理剩余最大的 3 个测试。

## Task 4: Test Framework（测试框架）runner（运行器）并行协调和串行兜底

**Files（文件）:**
- Modify（修改）: `plugins/test-framework/skills/test-framework/scripts/test_framework_runner.py`
- Modify（修改）: `plugins/test-framework/skills/test-framework/scripts/test_framework.py`
- Modify（修改）: `tests/test_test_framework_plugin.py`
- Modify（修改）: `.test-framework/config.json`

- [ ] **Step 1: 增加 runner（运行器）模块加载 helper（辅助函数）**

在 `tests/test_test_framework_plugin.py` 现有 `load_test_framework_module()` 附近新增：

```python
def load_test_framework_runner_module():
    script = TEST_FRAMEWORK_SCRIPT.with_name("test_framework_runner.py")
    spec = importlib.util.spec_from_file_location("test_framework_runner_under_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
```

Expected（期望）:
- 后续 Task 4（任务 4）测试调用 runner（运行器）里的 `run_verify()`，不是入口脚本 `test_framework.py`。
- 如果 helper（辅助函数）需要复用已有 import（导入），只补缺失的 `importlib.util` 或 `sys`，不重复导入。

- [ ] **Step 2: 写并行调度失败测试**

Append（追加）到 `tests/test_test_framework_plugin.py`:

```python
def test_test_framework_runner_full_verify_runs_parallel_safe_checks_concurrently(tmp_path: Path) -> None:
    import threading
    import time

    module = load_test_framework_runner_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "a", "command": ["check-a"], "parallel": True},
                    {"id": "b", "command": ["check-b"], "parallel": True},
                ]
            },
        },
    )
    barrier = threading.Barrier(2)
    calls: list[list[str]] = []

    def fake_runner(command, **kwargs):
        calls.append(list(command))
        barrier.wait(timeout=1)
        time.sleep(0.05)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    started = time.perf_counter()
    result = module.run_verify(project, runner=fake_runner, full=True)
    elapsed = time.perf_counter() - started

    assert result == 0
    assert sorted(calls) == [["check-a"], ["check-b"]]
    assert elapsed < 0.5
```

Run（运行）:

```powershell
python -m pytest tests/test_test_framework_plugin.py::test_test_framework_runner_full_verify_runs_parallel_safe_checks_concurrently -q
```

Expected（期望）:
- 先 FAIL（失败），因为 runner（运行器）还没有并行分组语义。
- 该测试通过 `threading.Barrier`（线程屏障）和 elapsed（耗时）断言证明两个 parallel-safe（可并行）check（检查项）有重叠执行；串行实现会在 barrier（屏障）处失败。

- [ ] **Step 3: 写 serial fallback（串行兜底）失败测试**

Append（追加）:

```python
def test_test_framework_runner_full_verify_preserves_serial_checks(tmp_path: Path) -> None:
    module = load_test_framework_runner_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-a", "command": ["check-a"], "parallel": True},
                    {"id": "serial-b", "command": ["check-b"], "parallel": False},
                ]
            },
        },
    )
    calls: list[list[str]] = []

    def fake_runner(command, **kwargs):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = module.run_verify(project, runner=fake_runner, full=True)

    assert result == 0
    assert calls == [["check-a"], ["check-b"]]
```

Expected（期望）:
- FAIL（失败），直到 runner（运行器）识别 `parallel: false`。

- [ ] **Step 4: 写缺省串行策略失败测试**

Append（追加）:

```python
def test_test_framework_runner_full_verify_treats_missing_parallel_as_serial(tmp_path: Path) -> None:
    module = load_test_framework_runner_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "parallel-a", "command": ["check-a"], "parallel": True},
                    {"id": "missing-b", "command": ["check-b"]},
                ]
            },
        },
    )
    calls: list[list[str]] = []

    def fake_runner(command, **kwargs):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = module.run_verify(project, runner=fake_runner, full=True)

    assert result == 0
    assert calls == [["check-a"], ["check-b"]]
```

Expected（期望）:
- FAIL（失败），直到缺失 `parallel`（并行）元数据的 check（检查项）按 serial（串行）处理。
- 后续 `.test-framework/config.json` 仍必须给仓库内所有 verify check（验证检查项）显式声明 `parallel`，这个缺省规则只是保守兜底。

- [ ] **Step 5: 写稳定汇总顺序失败测试**

Append（追加）:

```python
def test_test_framework_runner_full_verify_reports_results_in_config_order(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import time

    module = load_test_framework_runner_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".test-framework").mkdir()
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {"id": "first", "command": ["check-first"], "parallel": True},
                    {"id": "second", "command": ["check-second"], "parallel": True},
                ]
            },
        },
    )

    def fake_runner(command, **kwargs):
        if command == ["check-first"]:
            time.sleep(0.1)
            return subprocess.CompletedProcess(command, 1, stdout="first-out\n", stderr="first-err\n")
        return subprocess.CompletedProcess(command, 0, stdout="second-out\n", stderr="")

    result = module.run_verify(project, runner=fake_runner, full=True)
    output = capsys.readouterr()

    assert result == 1
    assert output.out.index("first-out") < output.out.index("second-out")
    assert output.out.index("duration: first") < output.out.index("duration: second")
    assert "failed: first" in output.out
    assert "first-err" in output.err
```

Expected（期望）:
- FAIL（失败），直到两个 parallel（并行）check（检查项）即使反序完成，也按 `.test-framework/config.json` 原始顺序输出 stdout（标准输出）、stderr（标准错误）、duration（耗时）和 failed（失败）汇总。

- [ ] **Step 6: 实现 check（检查项）分组函数**

在 `test_framework_runner.py` 增加：

```python
def _is_parallel_safe(check: dict[str, Any]) -> bool:
    return check.get("parallel") is True


def _split_parallel_checks(
    indexed_checks: list[tuple[int, dict[str, Any]]],
) -> tuple[list[tuple[int, dict[str, Any]]], list[tuple[int, dict[str, Any]]]]:
    parallel: list[tuple[int, dict[str, Any]]] = []
    serial: list[tuple[int, dict[str, Any]]] = []
    for index, check in indexed_checks:
        if _is_parallel_safe(check):
            parallel.append((index, check))
        else:
            serial.append((index, check))
    return parallel, serial
```

- [ ] **Step 7: 实现 full（完整）模式并行运行和稳定结果汇总**

在 `test_framework_runner.py` 增加标准库 ThreadPoolExecutor（线程池执行器）实现：

```python
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


@dataclass(frozen=True)
class CheckResult:
    index: int
    check: dict[str, Any]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    exception: str | None = None
    cache_key: str | None = None


def _run_check_result(
    index: int,
    project: Path,
    check: dict[str, Any],
    config: dict[str, Any],
    changed_files: list[str],
    runner: Runner,
) -> CheckResult:
    command = check.get("command")
    started = time.perf_counter()
    try:
        cache_key = _cache_key(project, config, check, changed_files)
    except ValueError as error:
        return CheckResult(index, check, 1, stderr=f"{error}\n", duration_seconds=time.perf_counter() - started)
    if not command:
        return CheckResult(index, check, 1, stderr=f"missing_command: {check.get('id')}\n")
    use_shell = isinstance(command, str)
    try:
        result = runner(
            command,
            cwd=project,
            check=False,
            text=True,
            capture_output=True,
            shell=use_shell,
        )
    except FileNotFoundError as error:
        executable = command[0] if isinstance(command, list) else str(command)
        return CheckResult(
            index,
            check,
            1,
            stderr=f"command_not_found: {check.get('id')}: {executable}\n",
            duration_seconds=time.perf_counter() - started,
            exception=str(error),
        )
    return CheckResult(
        index,
        check,
        int(result.returncode),
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        duration_seconds=time.perf_counter() - started,
        cache_key=cache_key,
    )


def _run_checks_parallel(
    project: Path,
    config: dict[str, Any],
    indexed_checks: list[tuple[int, dict[str, Any]]],
    changed_files: list[str],
    runner: Runner,
) -> list[CheckResult]:
    if not indexed_checks:
        return []
    max_workers = min(len(indexed_checks), max(1, (os.cpu_count() or 2) - 1))
    results: list[CheckResult | None] = [None] * len(indexed_checks)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(
                _run_check_result,
                original_index,
                project,
                check,
                config,
                changed_files,
                runner,
            ): position
            for position, (original_index, check) in enumerate(indexed_checks)
        }
        for future in as_completed(future_to_index):
            position = future_to_index[future]
            original_index, check = indexed_checks[position]
            try:
                results[position] = future.result()
            except Exception as error:  # defensive aggregation; should be rare
                results[position] = CheckResult(
                    original_index,
                    check,
                    1,
                    stderr=f"check_exception: {check.get('id')}: {error}\n",
                    exception=repr(error),
                )
    return [result for result in results if result is not None]
```

Then（然后）调整 `run_verify(..., full=True)`：

```python
indexed_selected = list(enumerate(selected))
parallel_checks, serial_checks = _split_parallel_checks(indexed_selected)
results = _run_checks_parallel(project, config, parallel_checks, changed_files, runner)
results.extend(
    _run_check_result(index, project, check, config, changed_files, runner)
    for index, check in serial_checks
)
results.sort(key=lambda result: result.index)
failed_ids: list[str] = []
for result in results:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    print(f"duration: {result.check.get('id')} seconds={result.duration_seconds:.2f}")
    if result.returncode == 0:
        if result.cache_key is not None:
            _cache_store(project, result.cache_key, result.check)
    else:
        failures += 1
        failed_ids.append(str(result.check.get("id")))
if failed_ids:
    print(f"failed: {', '.join(failed_ids)}")
```

Expected（期望）:
- default verify（默认验证）仍保持原 cache（缓存）语义。
- full verify（完整验证）运行所有 selected check（已选检查项），并按 `parallel` 元数据分组。
- 并行 check（检查项）执行完成后，按原始 `.test-framework/config.json` 配置顺序打印 stdout/stderr（标准输出/标准错误）、duration（耗时）和 failed（失败）汇总，避免并发输出交错或遗漏失败原因。
- `_cache_key()` 的 invalid input（无效输入）错误被转换成 `CheckResult`（检查结果）失败项，不得中断整轮汇总。

- [ ] **Step 8: 增加耗时输出和失败汇总验收**

在 `_run_check()` 或 wrapper（包装器）中记录每个 check（检查项）耗时，并在 full verify（完整验证）结束前输出：

```text
duration: verify.pr-flow seconds=...
duration: verify.test-framework seconds=...
failed: verify.some-check
```

Expected（期望）:
- full verification（完整验证）报告能满足 OpenSpec（规格流程）“before and after timing evidence（前后计时证据）”要求。
- 任一并行 check（检查项）失败时，最终退出码仍为失败，并且 stdout/stderr（标准输出/标准错误）与 failed（失败）汇总都可用于定位。
- invalid input path（无效输入路径）这类配置错误也进入 failed（失败）汇总，最终输出 `status: failed`。

- [ ] **Step 9: 更新 `.test-framework/config.json` 并声明所有 check（检查项）策略**

给每个 verify check（验证检查项）增加明确 `parallel`：

```json
{
  "id": "verify.pr-flow",
  "parallel": true,
  "command": "python -m pytest -p no:cacheprovider tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py",
  "paths": ["..."],
  "inputs": ["..."]
}
```

Initial classification（初始分类）:
- `verify.local-build-contract`: 只有 command-level cache（命令级缓存）写入已禁用或已隔离时，才设为 `parallel: true`。
- `verify.agent-guard`: 只有 pytest（Python 测试框架）命令已加 `-p no:cacheprovider` 或证明具备等价 cache isolation（缓存隔离）时，才设为 `parallel: true`。
- `verify.release-flow`: 只有 pytest（Python 测试框架）命令已加 `-p no:cacheprovider` 或证明具备等价 cache isolation（缓存隔离）时，才设为 `parallel: true`。
- `verify.pr-flow`: 只有 pytest（Python 测试框架）命令已加 `-p no:cacheprovider` 或证明具备等价 cache isolation（缓存隔离）时，才设为 `parallel: true`。
- `verify.cross-agent-review`: 只有 pytest（Python 测试框架）命令已加 `-p no:cacheprovider` 或证明具备等价 cache isolation（缓存隔离）时，才设为 `parallel: true`。
- `verify.test-framework`: `parallel: false`，因为它会读写 `.test-framework/cache` 并验证 runner（运行器）自身。
- `verify.openspec`: `parallel: true`

如果任何 pytest（Python 测试框架）check（检查项）仍写入共享 `.pytest_cache` 或其它 shared mutable cache（共享可变缓存），在证明隔离前保持 `parallel: false`。

Run（运行）:

```powershell
python -m pytest tests/test_test_framework_plugin.py -q
python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full
```

Expected（期望）:
- PASS（通过）。
- full（完整）模式仍运行所有 verify check（验证检查项），不能少跑。
- 输出每个 verify check（验证检查项）的 duration（耗时）行；失败时输出 failed（失败）汇总。

## Task 5: pytest-xdist（并行测试插件）评估和接入

**Files（文件）:**
- Modify（修改）: `.test-framework/config.json`
- Modify（修改）: `pyproject.toml`
- Create（新建）: `requirements-dev.txt`，仅当最终决定采用 pytest-xdist（并行测试插件）、用户已授权依赖记录、且没有其它依赖声明位置时创建。
- Modify（修改）: `docs/superpowers/specs/2026-06-23-full-verification-runtime-design.md`

- [ ] **Step 1: 检查 pytest-xdist（并行测试插件）是否已可用**

Run（运行）:

```powershell
python -c "import xdist; print('xdist_available')"
python -m pytest --help | Select-String -Pattern "-n"
```

Expected（期望）:
- 如果输出 `xdist_available` 且 help（帮助）中存在 `-n`，可以进入 Step 3 接入。
- 如果失败，继续 Step 2 记录依赖，并且不得在未安装前把 verify check（验证检查项）命令改成需要 `-n auto`。

- [ ] **Step 2: 明确依赖记录位置，但未采用时不新增依赖文件**

如果 pytest-xdist（并行测试插件）已可用，或用户明确授权采用并记录依赖，再检查依赖记录位置。如果仓库仍只有 `pyproject.toml` 且没有 dev dependency（开发依赖）区域，Create（新建）`requirements-dev.txt`：

```text
pytest
pytest-xdist
```

Expected（期望）:
- 依赖记录清楚，但实施者不得自动全局安装；如需安装，先获得用户授权或使用项目既有环境。
- 如果 pytest-xdist（并行测试插件）不可用且用户未授权采用，不创建 `requirements-dev.txt`，跳过 Step 3 和 Step 4 的 `-n auto` 命令修改，直接在 Step 5 记录 `not adopted: dependency unavailable`（未接入：依赖不可用）。

- [ ] **Step 3: 给 pytest（Python 测试框架）命令接入 xdist（并行测试插件）**

仅当 pytest-xdist（并行测试插件）已可用或用户已授权安装并完成安装时，将 `.test-framework/config.json` 中 pytest（Python 测试框架）命令改为分组内部并行：

```json
"command": "python -m pytest -p no:cacheprovider -n auto tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py"
```

Apply（应用）到：
- `verify.local-build-contract`，仅当它是 pytest（Python 测试框架）命令且加 `-p no:cacheprovider -n auto` 后验证通过；否则记录不接入原因
- `verify.agent-guard`
- `verify.release-flow`
- `verify.pr-flow`
- `verify.cross-agent-review`
- `verify.test-framework`，如果该检查项内部测试证明可以并行且不破坏 `.test-framework/cache`（测试框架缓存）；否则保持 `parallel: false` 且不加 `-n auto`

如果 pytest-xdist（并行测试插件）不可用且未获安装授权：
- 保持所有 pytest（Python 测试框架）命令不带 `-n auto`
- 保留 Test Framework（测试框架）runner（运行器）的 verify check（验证检查项）级并行
- 在 Design Doc（设计文档）记录未接入原因

Do not（不要）:
- 不使用 `-m "not slow"` 这类 marker-filtered（测试标记过滤）。
- 不把 full verification（完整验证）改成测试子集。

- [ ] **Step 4: 验证 xdist（并行测试插件）没有隐藏共享状态问题**

Run（运行）:

```powershell
python -m pytest -p no:cacheprovider -n auto tests/test_local_plugin_build_checks.py -q
python -m pytest -p no:cacheprovider -n auto tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py -q
python -m pytest -p no:cacheprovider -n auto tests/test_agent_guard_runtime_session_focus.py tests/test_agent_guard_runtime_brief.py tests/test_agent_guard_skill_entrypoints.py tests/test_agent_guard_runtime_router.py tests/test_agent_guard_plugin_installer.py tests/test_agent_guard_plugin_runtime_e2e.py tests/test_agent_guard_plugin_package.py tests/test_agent_guard_prd_full_e2e.py tests/test_extract_guard_model.py tests/test_validate_guard_profile.py tests/test_init_user_guard.py tests/test_init_project_guard.py -q
python -m pytest -p no:cacheprovider -n auto tests/test_release_flow_cli.py tests/test_release_flow_plugin_package.py -q
python -m pytest -p no:cacheprovider -n auto tests/test_cross_agent_review_cli.py tests/test_cross_agent_review_plugin_package.py -q
python -m pytest -p no:cacheprovider -n auto tests/test_test_framework_plugin.py -q
```

Expected（期望）:
- 仅在 pytest-xdist（并行测试插件）可用时运行这些命令，每组 PASS（通过）。
- 如果某组失败，先把该 verify check（验证检查项）标为 `parallel: false` 或移除 `-n auto`，记录失败原因，再继续保证 full（完整）仍全量运行。
- 如果当前仓库的 `verify.local-build-contract` 或 `verify.test-framework` 映射到的测试文件名不同，先从 `.test-framework/config.json` 读取实际 command（命令）后运行等价 `-p no:cacheprovider -n auto` 验证；不要凭上面的示例文件名硬编码。

- [ ] **Step 5: 写评估结论到 Design Doc（设计文档）**

在 Design Doc（设计文档）追加：

```markdown
## pytest-xdist（并行测试插件）Evaluation（评估）

- availability（可用性）: 写 Step 1 的 `xdist_available` 检查结果
- adoption（接入结论）: 列出已经使用 `-n auto` 的 verify check（验证检查项）id
- serial fallback（串行兜底）: 列出保持串行的 verify check（验证检查项）id 和失败原因
- full verification（完整验证）coverage（覆盖）: 未使用 marker-filtered（测试标记过滤）子集
```

Expected（期望）:
- pytest-xdist（并行测试插件）是否接入、为什么接入或为什么保留串行，都有证据。

## Task 6: 套件级优化扩展到其它慢测试

**Files（文件）:**
- Modify（修改）: `tests/test_release_flow_cli.py`
- Modify（修改）: `tests/test_agent_guard_plugin_runtime_e2e.py`
- Modify（修改）: `tests/test_agent_guard_prd_full_e2e.py`
- Modify（修改）: `tests/test_cross_agent_review_cli.py`
- Use（使用）: `tests/support/command_stubs.py`
- Use（使用）: `tests/support/git_templates.py`

- [ ] **Step 1: 根据最新 durations（耗时报告）选择下一个最大组**

Run（运行）:

```powershell
python -m pytest tests/test_release_flow_cli.py --durations=15 -q
python -m pytest tests/test_agent_guard_plugin_runtime_e2e.py tests/test_agent_guard_prd_full_e2e.py --durations=15 -q
python -m pytest tests/test_cross_agent_review_cli.py --durations=15 -q
```

Expected（期望）:
- 只优化当前最大耗时来源，不做无关重构。

- [ ] **Step 2: Release Flow（发布流程）保留一个 local E2E（本地端到端）并轻量化矩阵**

保留 `test_release_flow_local_e2e` 作为真实路径。对只验证参数、状态和 JSON artifact（数据产物）的测试，优先使用 in-process（进程内）module（模块）调用或共享 `write_json()` fixture（测试夹具）。

Run（运行）:

```powershell
python -m pytest tests/test_release_flow_cli.py tests/test_release_flow_plugin_package.py --durations=15 -q
```

Expected（期望）:
- PASS（通过）。
- Release Flow（发布流程）仍保留真实 `setup -> release-init -> preflight -> publish -> summarize` 路径。

- [ ] **Step 3: Agent Guard（代理守卫）保留 plugin runtime E2E（插件运行时端到端）并共享大文本 fixture（测试夹具）**

把 `write_confirmed_research_notes()` 这类长输入模板移动到共享 fixture（测试夹具），多个测试复用不可变文本，只在测试目录复制输出。

Run（运行）:

```powershell
python -m pytest tests/test_agent_guard*.py tests/test_extract_guard_model.py tests/test_validate_guard_profile.py tests/test_init_user_guard.py tests/test_init_project_guard.py --durations=20 -q
```

Expected（期望）:
- PASS（通过）。
- Agent Guard（代理守卫）仍覆盖 install（安装）、verify（验证）、runtime（运行时）和 PRD full E2E（需求文档完整端到端）。

- [ ] **Step 4: cross-agent-review（跨代理审查）减少重复 subprocess（子进程）启动**

对纯文本生成、参数校验和错误分支，使用 module（模块）函数或 in-process（进程内）调用；保留一个真实 CLI（命令行界面）路径覆盖入口。

Run（运行）:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py tests/test_cross_agent_review_plugin_package.py --durations=15 -q
```

Expected（期望）:
- PASS（通过）。
- 真实 CLI（命令行界面）入口仍被覆盖。

## Task 7: 全量验证、OpenSpec（规格流程）校验和证据收尾

**Files（文件）:**
- Modify（修改）: `docs/superpowers/specs/2026-06-23-full-verification-runtime-design.md`
- Modify（修改）: `openspec/changes/optimize-full-verification-runtime/tasks.md`

- [ ] **Step 1: 运行 OpenSpec（规格流程）严格校验**

Run（运行）:

```powershell
openspec validate optimize-full-verification-runtime --strict --no-interactive
openspec validate --all --strict --no-interactive
```

Expected（期望）:
- 两条命令都 PASS（通过）。

- [ ] **Step 2: 运行目标测试**

Run（运行）:

```powershell
python -m pytest tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py --durations=25 -q
python -m pytest tests/test_test_framework_plugin.py --durations=20 -q
```

Expected（期望）:
- 两条命令都 PASS（通过）。
- PR Flow（拉取请求流程）和 Test Framework（测试框架）不再出现单个明显不可接受慢点。

- [ ] **Step 3: 运行 full verification（完整验证）并计时**

Run（运行）:

```powershell
$sw = [System.Diagnostics.Stopwatch]::StartNew()
python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full
$code = $LASTEXITCODE
$sw.Stop()
"full_verify_seconds={0:N2} code={1}" -f $sw.Elapsed.TotalSeconds, $code
```

Expected（期望）:
- `code=0`
- `status: passed`
- `full-not-run: false`
- 使用当前仓库 canonical full verification command（规范完整验证命令）：`python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full`。
- `full_verify_seconds` 小于 60.00。

- [ ] **Step 4: 如果仍超过 60 秒，按最大剩余耗时继续一轮**

Run（运行）:

```powershell
python -m pytest --durations=30 -q
python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full
```

Expected（期望）:
- 根据 runner（运行器）duration（耗时）输出和 pytest durations（耗时报告）选择最大剩余项。
- 继续使用 Task 2 的 repo-native（仓库内自带）规则，不添加一次性特殊逻辑。

- [ ] **Step 5: 写 after（优化后）证据**

在 Design Doc（设计文档）追加：

```markdown
## Verification Evidence（验证证据）

- target（目标）: full verification（完整验证）under 60 seconds
- before（优化前）: 复制 Task 1 Step 2 的 `full_verify_seconds`
- after（优化后）: 复制 Task 7 Step 3 的 `full_verify_seconds`
- verify check（验证检查项）after timings（优化后耗时）:
  - `verify.local-build-contract`: 复制 runner（运行器）duration（耗时）输出
  - `verify.agent-guard`: 复制 runner（运行器）duration（耗时）输出
  - `verify.release-flow`: 复制 runner（运行器）duration（耗时）输出
  - `verify.pr-flow`: 复制 runner（运行器）duration（耗时）输出
  - `verify.cross-agent-review`: 复制 runner（运行器）duration（耗时）输出
  - `verify.test-framework`: 复制 runner（运行器）duration（耗时）输出
  - `verify.openspec`: 复制 runner（运行器）duration（耗时）输出
- PR Flow（拉取请求流程）after: 复制 Task 7 Step 2 中 PR Flow（拉取请求流程）命令耗时，作为 `verify.pr-flow` 的明细证据
- Test Framework（测试框架）parallel coordination（并行协调）: 写 Task 4 验证命令和结果
- pytest-xdist（并行测试插件）: 写 Task 5 的接入组或串行原因
- remaining largest contributors（剩余最大耗时来源）: 如果 after（优化后）超过 50 秒，列出 runner（运行器）duration（耗时）输出最高的 3 项；低于 50 秒则写 `none above risk threshold`
```

- [ ] **Step 6: 勾选 OpenSpec tasks（规格任务）**

只有当对应证据存在后，更新 `openspec/changes/optimize-full-verification-runtime/tasks.md`。必须按当前 tasks（任务）文件逐项勾选，不得只勾选 baseline（基线）三项。最低完成面应覆盖：

```markdown
- [x] 1.1 Re-run full verification timing and `--durations` evidence before implementation.
- [x] 1.2 Record verify-check and pytest grouped timings for local build contract, PR Flow, Release Flow, Agent Guard, cross-agent-review, Test Framework, and OpenSpec.
- [x] 1.3 Identify the smallest set of true end-to-end tests that must remain process-and-Git based for each user-facing workflow.
- [x] 1.4 Confirm implementation keeps `docs/rules/` out of scope and does not use marker-filtered subsets to satisfy full verification.
- [x] 2.1 Add or reuse shared test helpers under `tests/support/` for immutable Git repository templates, command stubs/recorders, and in-process command invocation.
- [x] 2.5 Express test-writing rules in OpenSpec artifacts only; do not create or modify `docs/rules/`.
- [x] 4.1 Add full verification scheduling that runs parallel-safe verify checks concurrently and serial-only checks in the same full verification run.
- [x] 5.4 Document adoption, serial fallback, and no marker-filtered subset evidence in the Design Doc.
- [x] 7.4 Run `openspec validate optimize-full-verification-runtime --strict --no-interactive` and `openspec validate --all --strict --no-interactive`.
```

Expected（期望）:
- 只勾选已经真实完成且有验证证据的项；上方列表是最低覆盖提示，不是完整 tasks（任务）替代品。
- 不伪造通过结果。

## Self-Review（自查）

- Spec coverage（规格覆盖）: 覆盖 baseline（基线）、全仓库 repo-native（仓库内自带）测试规则、PR Flow（拉取请求流程）先行优化、Test Framework（测试框架）并行协调、pytest-xdist（并行测试插件）评估/接入、OpenSpec（规格流程）规则沉淀和全量前后计时。
- Scope guard（范围护栏）: 明确禁止修改 `docs/rules/`，也禁止回滚旧归档改动。
- Runtime guard（耗时护栏）: 不靠 marker-filtered（测试标记过滤）子集达标；full verification（完整验证）仍运行完整 verify check（验证检查项）集合。
- Coverage guard（覆盖护栏）: PR Flow（拉取请求流程）保留 complete（完成）、cleanup（清理）、hotfix（热修复）真实 end-to-end（端到端）路径；其它插件也保留代表性真实入口路径。
- Dependency guard（依赖护栏）: pytest-xdist（并行测试插件）先评估再接入；如需安装依赖，另行获得授权。
