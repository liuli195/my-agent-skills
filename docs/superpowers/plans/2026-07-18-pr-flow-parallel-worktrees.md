---
change: support-parallel-pr-flow-worktrees
design-doc: docs/superpowers/specs/2026-07-18-pr-flow-parallel-worktrees-design.md
base-ref: 897308bf86dfd47024749812f9a7abada2826d31
---

# PR Flow（拉取请求流程）多工作树并行实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让关联 Git worktree（Git 工作树）可并行运行 PR Flow（拉取请求流程），同时以工作树级锁、最新远端目标提交和安全清理阻止同一工作树竞争及过期结果合并。

**Architecture:** 只扩展现有 `pr_flow.py`，把工作树身份、操作系统文件锁、远端目标快照、required checks（必需检查）和工作树清理实现为少量共享函数。继续复用现有 Git（版本控制）/ GitHub CLI（GitHub 命令行工具）封装、状态载荷、测试替身和裸仓库夹具，不拆模块。

**Tech Stack:** Python（编程语言）标准库、Git（版本控制）原生命令、GitHub CLI（GitHub 命令行工具）、pytest（测试工具）、OpenSpec（开放规格）。

## Global Constraints

- 不新增依赖、配置、运行模块或通用工作流框架。
- 修改命令只锁当前工作树；不同工作树必须保持并行。
- 不自动变基、合并目标分支、解决冲突或强制删除工作树。
- 默认保留工作树；仅显式 `--remove-worktree`（删除工作树参数）触发删除。
- cleanup（清理）仍只检测脏工作区并停止，不修改或清理用户改动。
- 所有改动必须通过 PR Flow（拉取请求流程）完整端到端回归。

---

## 文件范围

- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py` — 唯一运行实现，承载上下文、锁、远端快照、门禁和清理。
- Modify: `tests/test_pr_flow_cli.py` — 复用现有替身与裸仓库夹具，完成定向和并行端到端测试。
- Modify: `plugins/pr-flow/skills/pr-flow-complete/SKILL.md` — 说明默认保留、显式删除和恢复命令。
- Modify: `plugins/pr-flow/skills/pr-flow-tweak/SKILL.md` — 说明小改流程的删除参数传播。
- Modify: `plugins/pr-flow/skills/pr-flow-cleanup/SKILL.md` — 说明分离头安全收尾、幂等重试和外部删除。
- Modify: `plugins/pr-flow/skills/pr-flow-hotfix/SKILL.md` — 说明推送回读后的可选工作树删除。

### Task 1: 隔离每个工作树的运行状态和修改命令

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

**Interfaces:**
- Consumes: 现有 `git()`、`write_status()`、`command_next_command()`、`hotfix_actor()` 和 `main()`。
- Produces: `worktree_context(project) -> dict[str, str]`、`stable_key(value) -> str`、`operation_lock(project, command, args)`；后续任务通过上下文字段和外层锁运行。测试直接复用现有 `init_repo()`，不新增测试框架。

- [ ] **Step 1: 写入隔离状态和锁竞争的失败测试**

在 `tests/test_pr_flow_cli.py` 增加定向测试，复用 `load_pr_flow_module()` 和现有 Git（版本控制）初始化助手；断言两个工作树写入不同分支状态，同一工作树的锁竞争不覆盖任何状态，diagnose（诊断）只输出持锁者信息：

```python
def test_write_status_keeps_compatibility_file_and_branch_run(tmp_path: Path) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    init_repo(project)
    module.write_status(project, "complete", "ready", {"sourceBranch": "feature/one"})

    latest = json.loads((project / ".pr-flow/last-status.json").read_text(encoding="utf-8"))
    runs = list((project / ".pr-flow/runs").glob("*.json"))
    assert len(runs) == 1
    assert json.loads(runs[0].read_text(encoding="utf-8")) == latest
    assert latest["details"]["sourceBranch"] == "feature/one"
    assert Path(latest["details"]["worktreePath"]) == project.resolve()
    assert latest["details"]["commonGitDir"]


def test_competing_mutation_reports_lock_without_rewriting_status(tmp_path: Path, monkeypatch, capsys) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    init_repo(project)
    module.write_status(project, "complete", "ready", {"sourceBranch": "feature/one"})
    before = (project / ".pr-flow/last-status.json").read_bytes()
    lock = module.operation_lock(project, "complete", argparse.Namespace(project=project))
    with lock:
        result = module.main(["cleanup", "--project", str(project), "--pr", "12"])
    assert result == 1
    assert "flow_locked" in capsys.readouterr().out
    assert (project / ".pr-flow/last-status.json").read_bytes() == before


def test_diagnose_reports_active_lock_without_writing_status(tmp_path: Path, capsys) -> None:
    module = load_pr_flow_module()
    project = tmp_path / "project"
    init_repo(project)
    with module.operation_lock(project, "complete", argparse.Namespace(project=project)):
        assert module.main(["diagnose", "--project", str(project)]) == 1
    output = capsys.readouterr().out
    assert "flow_locked" in output
    assert "actor" in output
    assert "nextCommand" in output
    assert not (project / ".pr-flow/last-status.json").exists()
```

- [ ] **Step 2: 运行测试并确认 RED（失败）**

Run: `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py -k "write_status_keeps or competing_mutation or diagnose_reports_active_lock"`

Expected: FAIL（失败），因为分支状态、上下文和 `operation_lock` 尚不存在。

- [ ] **Step 3: 在现有脚本实现最小工作树上下文、双写状态和文件锁**

在 `pr_flow.py` 顶部增加 `hashlib`、`contextlib` 和平台锁所需的标准库导入。紧邻 `write_status()`/`git()` 增加下列结构；平台锁仅封装 `msvcrt.locking` 与 `fcntl.flock`，竞争时抛出携带元数据的 `PrFlowError("flow_locked", ...)`：

```python
def stable_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def worktree_context(project: Path) -> dict[str, str]:
    worktree = project.resolve()
    common = require_git_success(worktree, "git_common_dir_failed", "rev-parse", "--git-common-dir").stdout.strip()
    common_dir = (worktree / common).resolve() if not Path(common).is_absolute() else Path(common).resolve()
    normalized = os.path.normcase(str(worktree)) if os.name == "nt" else str(worktree)
    return {"worktreePath": str(worktree), "commonGitDir": str(common_dir), "worktreeKey": stable_key(normalized)}


def status_source_branch(project: Path, details: dict[str, Any]) -> str:
    for key in ("sourceBranch", "headRefName", "branch"):
        value = details.get(key)
        if isinstance(value, str) and value:
            return value
    return require_git_success(project, "git_current_branch_failed", "branch", "--show-current").stdout.strip()


def write_status(project: Path, command: str, status: str, details: dict) -> None:
    enriched = {**worktree_context(project), **details}
    branch = status_source_branch(project, enriched)
    if branch:
        enriched.setdefault("sourceBranch", branch)
    payload = {"status": status, "command": command, "details": enriched}
    status_dir = project / ".pr-flow"
    status_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    (status_dir / "last-status.json").write_text(text, encoding="utf-8")
    if branch:
        runs = status_dir / "runs"
        runs.mkdir(exist_ok=True)
        (runs / f"{stable_key(branch)}.json").write_text(text, encoding="utf-8")
```

实现 `operation_lock()` 时把锁文件放到 `commonGitDir/pr-flow-locks/<worktreeKey>.lock`，成功加锁后先截断、写入并 `flush()` 元数据，再运行命令；`main()` 仅包围 `complete`、`tweak`、`cleanup`、`hotfix`，内部 cleanup（清理）直接调用 `run_cleanup()`，不二次加锁。diagnose（诊断）先非阻塞探测相同锁；锁被占用时打印 `DISPATCH_REQUIRED / flow_locked` 和元数据并直接返回，不调用 `stop()`。

- [ ] **Step 4: 运行定向测试并确认 GREEN（通过）**

Run: `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py -k "status or lock or diagnose"`

Expected: PASS（通过），且现有状态兼容测试不变。

- [ ] **Step 5: 提交此独立交付**

```powershell
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "实现 PR Flow 工作树状态与操作锁隔离"
```

### Task 2: 使用最新远端目标提交约束推送和合并

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

**Interfaces:**
- Consumes: Task 1 的外层锁，现有 `remote_for_base_branch()`、`require_git_success()`、`auto_push_current_branch_if_needed()` 和 `run_lifecycle()`。
- Produces: `remote_branch_snapshot(project, remote, branch) -> str`、`require_current_base(project, config, base_branch, source_oid, next_command) -> str`；Task 3 的 hotfix（热修复）复用同一快照函数。测试继续使用现有 `init_complete_project()`、`CommandStub` 和 `complete_args()`。

- [ ] **Step 1: 写入远端目标推进时禁止修改的失败测试**

基于现有 `test_complete_auto_pushes_*` 测试的 `CommandStub`（命令替身）增加：

```python
def test_complete_stops_before_push_when_remote_base_advanced(tmp_path: Path, monkeypatch) -> None:
    project, module, git_stub, gh_stub = init_complete_project(tmp_path, monkeypatch)
    git_stub.add(["fetch", "origin", "main"])
    git_stub.add(["rev-parse", "origin/main"], stdout="new-base\n")
    git_stub.add(["rev-parse", "HEAD"], stdout="feature-head\n")
    git_stub.add(["merge-base", "--is-ancestor", "new-base", "feature-head"], returncode=1)

    result = invoke_pr_flow(complete_args(project), module=module)

    assert result.returncode == 1
    assert "base_outdated" in result.stdout
    assert not any(call[:2] == ["push", "origin"] for call in git_stub.calls)
    assert not any(call[:2] in (["pr", "create"], ["pr", "edit"], ["pr", "merge"]) for call in gh_stub.calls)
```

再增加合并门禁完成后 `baseRefOid` 改变的测试，断言不调用 `gh pr merge` 且状态为 `base_outdated`。

- [ ] **Step 2: 运行测试并确认 RED（失败）**

Run: `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py -k "remote_base_advanced or base_oid_changed"`

Expected: FAIL（失败），现有流程仍可能继续推送或合并。

- [ ] **Step 3: 提取并复用远端快照，在所有远端修改前校验祖先关系**

在 `remote_for_base_branch()` 后增加：

```python
def remote_branch_snapshot(project: Path, remote: str, branch: str) -> str:
    require_git_success(project, "git_fetch_target_failed", "fetch", remote, branch)
    return require_git_success(
        project, "git_remote_target_head_failed", "rev-parse", f"{remote}/{branch}"
    ).stdout.strip()


def require_current_base(
    project: Path, config: dict[str, Any], base_branch: str, source_oid: str, next_command: str | None
) -> str:
    remote = remote_for_base_branch(config, base_branch)
    base_oid = remote_branch_snapshot(project, remote, base_branch)
    ancestor = git(project, "merge-base", "--is-ancestor", base_oid, source_oid)
    if ancestor.returncode != 0:
        raise PrFlowError("base_outdated", add_recovery_action({
            "reason": "base_outdated", "sourceCommit": source_oid,
            "baseCommit": base_oid, "baseRefName": base_branch,
            "remote": remote, "nextCommand": next_command,
        }))
    return base_oid
```

将 `PR_VIEW_FIELDS` 补入 `baseRefOid`。`run_lifecycle()` 在 auto-push（自动推送）前读取配置目标分支并调用 `require_current_base()`；检查和 review gate（审查门禁）完成后 `sync_pr()`，比较首次与最新 `headRefOid`/`baseRefOid`：源变化使用 `head_moved`，目标变化使用 `base_outdated`，随后才调用 `merge_pr()`。只读 `find_pr()`/`sync_pr()` 可先执行，但 `push`、`pr create`、`pr edit`、`pr merge` 必须位于基线校验之后。

- [ ] **Step 4: 运行最新基线相关测试并确认 GREEN（通过）**

Run: `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py -k "base_outdated or base_oid or auto_push or merge"`

Expected: PASS（通过）；过期基线路径无远端修改。

- [ ] **Step 5: 提交此独立交付**

```powershell
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "使用最新远端目标提交约束 PR Flow"
```

### Task 3: 只接受当前提交的非空必需检查，并复核 hotfix（热修复）目标

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`

**Interfaces:**
- Consumes: Task 2 的 `remote_branch_snapshot()`，现有 `sync_pr()`、`wait_for_checks()`、`merge_pr()`、`run_hotfix()`。
- Produces: `required_checks(project, pr_number) -> list[dict[str, Any]]`；合并前固定源/目标提交，hotfix（热修复）验证后复核目标快照。测试继续使用现有 `init_hotfix_project()`、`run_hotfix_in_process()` 和 Git（版本控制）远端读取助手，不创建平行夹具。

- [ ] **Step 1: 写入必需检查和 hotfix（热修复）竞争的失败测试**

用参数化测试覆盖空、缺失、等待、失败和成功 bucket（分组）；明确断言命令包含 `--required`：

```python
@pytest.mark.parametrize(
    ("payload", "expected"),
    [([], "checks_or_review_blocking"),
     ([{"bucket": "pending", "name": "ci"}], "checks_pending"),
     ([{"bucket": "fail", "name": "ci"}], "checks_or_review_blocking")],
)
def test_required_checks_reject_empty_pending_and_failed(tmp_path: Path, monkeypatch, payload, expected) -> None:
    project, module, _, gh_stub = init_complete_project(tmp_path, monkeypatch)
    gh_stub.add(
        ["pr", "checks", "12", "--required", "--json", "bucket,name,state,workflow,link"],
        stdout=json.dumps(payload),
    )
    result = invoke_pr_flow(complete_args(project), module=module)
    assert expected in result.stdout


def test_hotfix_stops_when_target_moves_during_verification(tmp_path: Path, monkeypatch) -> None:
    project, module = init_hotfix_project(tmp_path, monkeypatch)
    snapshots = iter(["base-before", "base-after"])
    monkeypatch.setattr(module, "remote_branch_snapshot", lambda *_: next(snapshots))
    result = invoke_pr_flow(hotfix_args(project), module=module)
    assert result.returncode == 1
    assert "base_outdated" in result.stdout
    assert not remote_target_was_pushed(project)
```

并改造现有 head moved（源提交变化）测试，使 required checks（必需检查）完成后再次读取 PR（拉取请求），源或目标提交变化均废弃旧结果。

- [ ] **Step 2: 运行测试并确认 RED（失败）**

Run: `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py -k "required_checks or target_moves_during_verification or head_moved"`

Expected: FAIL（失败），因为当前代码读取 `statusCheckRollup` 且 hotfix（热修复）不做推送前目标复核。

- [ ] **Step 3: 用 GitHub CLI（GitHub 命令行工具）直接读取必需检查并复核快照**

以最小函数替换 `pr_checks()` 的数据来源：

```python
REQUIRED_CHECK_FIELDS = "bucket,name,state,workflow,link"


def required_checks(project: Path, pr_number: Any) -> list[dict[str, Any]]:
    result = gh(project, "pr", "checks", str(pr_number), "--required", "--json", REQUIRED_CHECK_FIELDS)
    if result.returncode != 0:
        raise PrFlowError("checks_or_review_blocking", command_failure_details("checks_or_review_blocking", result))
    try:
        checks = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PrFlowError("checks_or_review_blocking", {"reason": "checks_or_review_blocking", "error": str(exc)}) from exc
    if not isinstance(checks, list) or not checks:
        raise PrFlowError("checks_or_review_blocking", {"reason": "checks_or_review_blocking", "pr": pr_number})
    return [check for check in checks if isinstance(check, dict)]
```

`wait_for_checks()` 每轮调用 `required_checks()`，只按 `bucket` 的 `pending`、`fail`、`cancel` 分类；其余非空结果视为通过。每轮 `sync_pr()` 后比较最初 `headRefOid`，变化立即返回 `head_moved`。门禁结束后 `run_lifecycle()` 再同步并比较 `baseRefOid`，再调用 `merge_pr()`。

在 `run_hotfix()` 中首次使用 `remote_branch_snapshot()` 记录 `remote_head`；完整验证与授权校验之后、push（推送）之前再次调用。如果值变化，返回 `base_outdated`，不得推送；相同才执行现有推送与 `confirm_hotfix_remote_readback()`。

- [ ] **Step 4: 运行门禁和 hotfix（热修复）测试并确认 GREEN（通过）**

Run: `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py -k "checks or head_moved or hotfix"`

Expected: PASS（通过）；成功门禁至少有一项必需检查，目标推进时 hotfix（热修复）不推送。

- [ ] **Step 5: 提交此独立交付**

```powershell
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "收紧必需检查与热修复目标复核"
```

### Task 4: 按实时工作树状态安全、幂等地清理

**Files:**
- Modify: `tests/test_pr_flow_cli.py`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Modify: `plugins/pr-flow/skills/pr-flow-complete/SKILL.md`
- Modify: `plugins/pr-flow/skills/pr-flow-tweak/SKILL.md`
- Modify: `plugins/pr-flow/skills/pr-flow-cleanup/SKILL.md`
- Modify: `plugins/pr-flow/skills/pr-flow-hotfix/SKILL.md`

**Interfaces:**
- Consumes: Task 1 的上下文/外层锁，Task 2 的 `remote_branch_snapshot()`，现有 cleanup（清理）错误状态和 hotfix（热修复）回读结果。
- Produces: `list_worktrees(project) -> list[dict[str, Any]]`、`remove_worktree(project, target) -> None`；四条修改流程支持 `--remove-worktree`（删除工作树参数）。测试从现有 `init_cleanup_project()` 和 `init_complete_project()` 扩展关联工作树、分支存在性和 Git（版本控制）调用断言，不另建夹具模块。

- [ ] **Step 1: 写入工作树解析、占用保护、幂等重试和显式删除的失败测试**

增加解析器最小样例及真实 Git（版本控制）清理场景：

```python
def test_parse_worktrees_handles_spaces_and_detached_entries() -> None:
    module = load_pr_flow_module()
    raw = (
        "worktree C:/repo/main\0HEAD aaaa\0branch refs/heads/main\0\0"
        "worktree C:/repo/feature one\0HEAD bbbb\0detached\0\0"
    )
    assert module.parse_worktrees(raw) == [
        {"path": "C:/repo/main", "head": "aaaa", "branch": "refs/heads/main"},
        {"path": "C:/repo/feature one", "head": "bbbb", "detached": True},
    ]


def test_cleanup_stops_before_deletion_when_source_is_checked_out_elsewhere(tmp_path: Path, monkeypatch) -> None:
    project, other, module = init_two_worktrees(tmp_path, monkeypatch, shared_branch="feature/one")
    result = invoke_pr_flow(["cleanup", "--project", str(project), "--pr", "12"], module=module)
    assert result.returncode == 1
    assert str(other.resolve()) in result.stdout
    assert remote_branch_exists(project, "feature/one")
    assert local_branch_exists(project, "feature/one")


def test_cleanup_retry_from_latest_detached_base_finishes(tmp_path: Path, monkeypatch) -> None:
    project, module = init_cleanup_after_detach_failure(tmp_path, monkeypatch)
    result = invoke_pr_flow(["cleanup", "--project", str(project), "--pr", "12"], module=module)
    assert result.returncode == 0
    assert "cleanup_complete" in result.stdout
    assert not local_branch_exists(project, "feature/one")


def test_remove_worktree_is_explicit_and_never_forced(tmp_path: Path, monkeypatch) -> None:
    project, target, module = init_external_cleanup_project(tmp_path, monkeypatch)
    kept = invoke_pr_flow(["cleanup", "--project", str(target), "--pr", "12"], module=module)
    assert kept.returncode == 0 and target.exists()
    removed = invoke_pr_flow(
        ["cleanup", "--project", str(target), "--pr", "12", "--remove-worktree"], module=module
    )
    assert removed.returncode == 0 and not target.exists()
    assert "--force" not in recorded_git_arguments()
```

另加主工作树、脏工作树、从待删除目录内运行时只输出外部重试命令，以及 hotfix（热修复）回读后删除且不调用 `gh pr view` 的测试。更新 complete（完整流程）/tweak（小改）测试，断言参数传给内部 cleanup（清理）。

- [ ] **Step 2: 运行测试并确认 RED（失败）**

Run: `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py -k "worktree or cleanup_retry or remove_worktree"`

Expected: FAIL（失败），现有 cleanup（清理）切换本地目标分支且没有删除参数。

- [ ] **Step 3: 使用 Git（版本控制）原生清单实现预检和分离头清理**

在 `pr_flow.py` 增加空字符解析器：

```python
def parse_worktrees(raw: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for field in raw.split("\0"):
        if not field:
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = field.partition(" ")
        mapped = {"worktree": "path", "HEAD": "head"}.get(key, key)
        current[mapped] = value if value else True
    if current:
        records.append(current)
    return records


def list_worktrees(project: Path) -> list[dict[str, Any]]:
    result = require_git_success(project, "git_worktree_list_failed", "worktree", "list", "--porcelain", "-z")
    return parse_worktrees(result.stdout)
```

重写 `run_cleanup()` 的动作顺序：先完成 PR（拉取请求）已合并、干净、源/目标合法、当前位置为源分支或最新目标提交 detached HEAD（分离头）、源分支未被其他工作树占用、远端目标可读等全部预检；再运行 `git checkout --detach <base-oid>`、按实时存在性删除远端源分支、`git branch -d <head>`。删除 `completed_cleanup_steps` 和“禁止重跑”恢复文本；每次重试重新读取分支/远端/工作树状态。

为四个命令解析 `--remove-worktree`。complete（完整流程）与 tweak（小改）把该布尔值放进内部 cleanup（清理）的 `Namespace`。hotfix（热修复）仅在 `remote_after == current_head` 后进入共享删除函数，绝不查询 PR（拉取请求）。

```python
def remove_worktree(project: Path, target: Path) -> None:
    worktrees = list_worktrees(project)
    normalized = target.resolve()
    if Path(worktrees[0]["path"]).resolve() == normalized:
        raise PrFlowError("main_worktree_removal_forbidden", {"reason": "main_worktree_removal_forbidden"})
    dirty = require_git_success(target, "git_status_failed", "status", "--short").stdout.strip()
    if dirty:
        raise PrFlowError("dirty_worktree", {"reason": "dirty_worktree", "dirty": dirty})
    require_git_success(project, "git_worktree_remove_failed", "worktree", "remove", str(normalized))
    if any(Path(item["path"]).resolve() == normalized for item in list_worktrees(project)):
        raise PrFlowError("git_worktree_remove_failed", {"reason": "git_worktree_remove_failed"})
```

从目标内部运行时不调用 `remove_worktree()`，而是在安全收尾后输出保留全部参数、可从外部执行的 `nextCommand`；从 `--project` 指向目标之外运行时才直接删除并回读。

- [ ] **Step 4: 更新四个 Skill（技能）说明**

在各自现有参数/恢复段落只增加三条事实，不复制设计：默认保留工作树；`--remove-worktree` 仅在安全收尾完成后删除且从不强制；内部调用时按输出的外部重试命令完成删除。hotfix（热修复）明确回读失败或目标变化时不删除、无需 PR（拉取请求）。

- [ ] **Step 5: 运行清理、完整流程和打包测试并确认 GREEN（通过）**

Run: `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py -k "cleanup or complete or tweak or hotfix or package"`

Expected: PASS（通过）；所有 worktree remove（删除工作树）调用均无 `--force`。

- [ ] **Step 6: 提交此独立交付**

```powershell
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py plugins/pr-flow/skills/pr-flow-complete/SKILL.md plugins/pr-flow/skills/pr-flow-tweak/SKILL.md plugins/pr-flow/skills/pr-flow-cleanup/SKILL.md plugins/pr-flow/skills/pr-flow-hotfix/SKILL.md
git commit -m "实现 PR Flow 工作树安全清理"
```

### Task 5: 真实双工作树端到端回归与完整验证

**Files:**
- Modify: `tests/test_pr_flow_cli.py`

**Interfaces:**
- Consumes: Tasks 1–4 的完整命令入口和现有 `init_complete_project` 裸仓库夹具。
- Produces: 复用 `init_complete_project` 的双工作树独立子进程端到端回归；不新增生产接口、测试模块或事件控制框架。

- [ ] **Step 1: 扩展现有裸仓库夹具并写入失败的并行端到端测试**

复用 `init_complete_project` 创建两个关联工作树和两个源分支，从两个独立 `subprocess.Popen`（子进程）启动真实 CLI（命令行入口），断言两个 complete（完整流程）均完成、状态互不覆盖并停在同一最新目标提交。远端推进、失败、冲突、分支占用和显式删除复用 Tasks 1–4 的定向回归，不重复构建并发事件框架。

- [ ] **Step 2: 运行端到端测试并确认 RED（失败）或确认新场景可检出回归**

Run: `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py -k "two_worktrees or linked_worktree"`

Expected: 首次运行至少一个新增场景 FAIL（失败）；完成 Tasks 1–4 后逐项修正测试替身/实现，直至全部 PASS（通过）。

- [ ] **Step 3: 只修正端到端测试暴露的共享实现缺口**

若失败来自生产逻辑，只在 `pr_flow.py` 已有共享函数修正根因；不得增加新模块、依赖、配置、锁层或测试专用生产分支。每次修正后重跑上一步命令，Expected: PASS（通过）。

- [ ] **Step 4: 运行 PR Flow（拉取请求流程）定向测试和 Plugin（插件）打包测试**

Run: `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py`

Expected: 全部 PASS（通过）。

- [ ] **Step 5: 构建本地 Plugin（插件）发布形态**

Run: `python scripts/local_plugin_build.py`

Expected: 命令退出码为 0，PR Flow Plugin（拉取请求流程插件）成功构建且无缺失文件。

- [ ] **Step 6: 运行仓库 Build and Verify（构建与验证）完整模式**

先按 `build-and-verify:build-and-verify`（构建与验证）Skill（技能）读取仓库配置，再执行其 full（完整）验证入口。

Expected: 覆盖用户入口或发布形态的完整业务流程全部 PASS（通过）；若环境阻断，保留原始命令和错误证据，不以定向测试替代。

- [ ] **Step 7: 运行 OpenSpec（开放规格）严格校验**

Run: `openspec validate --all --strict --no-interactive`

Expected: `support-parallel-pr-flow-worktrees` 及全部现行规格校验通过。

- [ ] **Step 8: 对照 OpenSpec（开放规格）任务逐项勾选并提交验证交付**

确认 `openspec/changes/support-parallel-pr-flow-worktrees/tasks.md` 的 1.1–5.3 均有测试或运行证据后再勾选对应项。

```powershell
git add tests/test_pr_flow_cli.py plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py openspec/changes/support-parallel-pr-flow-worktrees/tasks.md
git commit -m "完成 PR Flow 多工作树端到端验证"
```
