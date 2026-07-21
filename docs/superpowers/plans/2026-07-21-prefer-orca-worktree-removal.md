---
change: prefer-orca-worktree-removal
base-ref: ed3e37ec7236e53016ad93b3774b1ac44c4c67f6
archived-with: 2026-07-21-prefer-orca-worktree-removal
---

# Prefer Orca Worktree Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让 PR Flow（拉取请求流程）优先通过 Orca（工作区管理器）删除其已登记的安全关联工作树，并保持普通 Git（版本管理）工作树的现有非强制删除行为。

**Architecture:** `remove_worktree()`（删除工作树）继续承担主工作树与脏工作树的安全预检。预检通过后，新增的 Orca（工作区管理器）探测器以规范化路径匹配 `worktree ps --json`（工作树列表）结果；匹配时仅调用 Orca（工作区管理器）删除，未匹配或不可用时调用现有 Git（版本管理）删除。两条成功路径共用 Git（版本管理）工作树清单回读。

**Tech Stack:** Python 3.12（编程语言）、标准库 `json`（数据格式）、`subprocess`（子进程）、Pytest（测试框架）、现有 `CommandStub`（命令桩）、OpenSpec（开放规格）。

## Global Constraints

- 不新增依赖、配置或 Orca（工作区管理器）安装步骤。
- 不删除 main worktree（主工作树）、不删除脏工作树、不传递 `--force`（强制参数）、不关闭 Orca（工作区管理器）终端。
- Orca（工作区管理器）探测不可用、失败、无效 JSON（数据格式）或无路径匹配时，必须使用现有 Git（版本管理）删除。
- Orca（工作区管理器）已匹配但删除失败时，必须返回 `orca_worktree_remove_failed`（Orca 工作树删除失败），不得回退 Git（版本管理）删除。
- 构建和验证只使用 build-and-verify（构建与验证）Skill（技能）入口；不执行 `git pull`（拉取）。

---

### Task 1: 写出删除器选择的失败测试

**Files:**
- Modify: `tests/test_pr_flow_cli.py:490`
- Reference: `tests/support/command_stubs.py:1`

**Interfaces:**
- Consumes: 现有 `module.remove_worktree(project, target)`（删除工作树）和 `CommandStub`（命令桩）。
- Produces: 对 `module.orca(project, *args)`（Orca 命令封装）和 `module.find_orca_worktree_id(project, target)`（Orca 工作树标识探测）的测试契约。

- [x] **Step 1: 在现有原生删除测试后写入 Orca（工作区管理器）优先删除的失败测试**

```python
def worktree_removal_records(main: Path, target: Path) -> tuple[str, str]:
    before = (
        f"worktree {main}\0HEAD aaaa\0branch refs/heads/main\0\0"
        f"worktree {target}\0HEAD bbbb\0detached\0\0"
    )
    after = f"worktree {main}\0HEAD aaaa\0branch refs/heads/main\0\0"
    return before, after


def orca_worktree_ps_json(target: Path, worktree_id: str) -> str:
    return json.dumps({"result": {"worktrees": [{"path": str(target), "worktreeId": worktree_id}]}})


def test_remove_worktree_prefers_matched_orca_worktree(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub

    module = load_pr_flow_module()
    main = tmp_path / "main"
    target = tmp_path / "feature one"
    main.mkdir()
    target.mkdir()
    before, after = worktree_removal_records(main, target)
    git_stub = CommandStub(consume=True)
    git_stub.add(["worktree", "list", "--porcelain", "-z"], stdout=before)
    git_stub.add(["status", "--short"], stdout="")
    git_stub.add(["worktree", "remove", str(target.resolve())])
    git_stub.add(["worktree", "list", "--porcelain", "-z"], stdout=after)
    orca_stub = CommandStub(consume=True)
    orca_stub.add(["worktree", "ps", "--json"], stdout=orca_worktree_ps_json(target, "repo::target"))
    orca_stub.add(["worktree", "rm", "--worktree", "id:repo::target", "--json"])
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "orca", orca_stub, raising=False)

    module.remove_worktree(target, target)

    assert ("worktree", "rm", "--worktree", "id:repo::target", "--json") in orca_stub.calls
    assert not any(call[:2] == ("worktree", "remove") for call in git_stub.calls)
    assert not any("--force" in call for call in orca_stub.calls)
```

- [x] **Step 2: 运行测试确认当前实现失败**

Run: `python -m pytest tests/test_pr_flow_cli.py::test_remove_worktree_prefers_matched_orca_worktree -q`

Expected: FAIL，断言 Orca（工作区管理器）命令已被调用时失败；现有实现仍调用已桩化的 Git（版本管理）删除，因此测试以断言失败而非异常变红。

- [x] **Step 3: 增加无匹配、命令不可用和无效 JSON（数据格式）的 Git（版本管理）回退测试**

```python
@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr"),
    [
        (0, '{"result":{"worktrees":[]}}', ""),
        (127, "", "orca not found"),
        (0, "not-json", ""),
    ],
)
def test_remove_worktree_falls_back_to_git_when_orca_is_unavailable_or_unmatched(
    tmp_path: Path, monkeypatch, returncode: int, stdout: str, stderr: str
) -> None:
    from tests.support.command_stubs import CommandStub

    module = load_pr_flow_module()
    main = tmp_path / "main"
    target = tmp_path / "feature one"
    main.mkdir()
    target.mkdir()
    before, after = worktree_removal_records(main, target)
    git_stub = CommandStub(consume=True)
    git_stub.add(["worktree", "list", "--porcelain", "-z"], stdout=before)
    git_stub.add(["status", "--short"], stdout="")
    git_stub.add(["worktree", "remove", str(target.resolve())])
    git_stub.add(["worktree", "list", "--porcelain", "-z"], stdout=after)
    orca_stub = CommandStub(consume=True)
    orca_stub.add(["worktree", "ps", "--json"], returncode=returncode, stdout=stdout, stderr=stderr)
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "orca", orca_stub, raising=False)

    module.remove_worktree(target, target)

    assert ("worktree", "remove", str(target.resolve())) in git_stub.calls
    assert not any(call[:2] == ("worktree", "rm") for call in orca_stub.calls)
```

- [x] **Step 4: 增加 Orca（工作区管理器）删除失败且不回退的测试**

```python
def test_remove_worktree_stops_when_matched_orca_removal_fails(tmp_path: Path, monkeypatch) -> None:
    from tests.support.command_stubs import CommandStub

    module = load_pr_flow_module()
    main = tmp_path / "main"
    target = tmp_path / "feature one"
    main.mkdir()
    target.mkdir()
    before, after = worktree_removal_records(main, target)
    git_stub = CommandStub(consume=True)
    git_stub.add(["worktree", "list", "--porcelain", "-z"], stdout=before)
    git_stub.add(["status", "--short"], stdout="")
    git_stub.add(["worktree", "remove", str(target.resolve())])
    git_stub.add(["worktree", "list", "--porcelain", "-z"], stdout=after)
    orca_stub = CommandStub(consume=True)
    orca_stub.add(["worktree", "ps", "--json"], stdout=orca_worktree_ps_json(target, "repo::target"))
    orca_stub.add(
        ["worktree", "rm", "--worktree", "id:repo::target", "--json"],
        stderr="permission denied",
        returncode=1,
    )
    monkeypatch.setattr(module, "git", git_stub)
    monkeypatch.setattr(module, "orca", orca_stub, raising=False)

    with pytest.raises(module.PrFlowError, match="orca_worktree_remove_failed"):
        module.remove_worktree(target, target)

    assert not any(call[:2] == ("worktree", "remove") for call in git_stub.calls)
```

- [x] **Step 5: 运行新测试确认它们都失败于缺失行为**

Run: `python -m pytest tests/test_pr_flow_cli.py -k "remove_worktree and orca" -q`

Expected: Orca（工作区管理器）优先与失败不回退测试 FAIL；Git（版本管理）回退兼容测试 PASS，因为它描述既有行为。

- [x] **Step 6: 保留绿色测试与实现同一提交**

不要提交红灯测试；在任务 2 通过绿色验证后，将测试和生产代码一并提交，保证每个提交可独立验证。

### Task 2: 实现 Orca（工作区管理器）探测和删除器选择

**Files:**
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:254`
- Modify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py:1188`
- Test: `tests/test_pr_flow_cli.py:490`

**Interfaces:**
- Consumes: `normalized_path(path)`（规范化路径）、`command_failure_details(reason, result)`（命令失败详情）和现有 `git(project, *args)`（Git 命令封装）。
- Produces: `orca(project, *args) -> subprocess.CompletedProcess[str]`（Orca 命令封装）、`find_orca_worktree_id(project, target) -> str | None`（Orca 工作树标识探测）、更新后的 `remove_worktree(project, target)`（删除工作树）。

- [x] **Step 1: 实现最小 Orca（工作区管理器）命令封装**

```python
def orca_executable() -> str:
    if configured := os.environ.get("ORCA_CLI_COMMAND"):
        return configured
    if os.environ.get("ORCA_DEV_REPO_ROOT"):
        return "orca-dev"
    return "orca-ide" if sys.platform.startswith("linux") else "orca"


def orca(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    command = [orca_executable(), *args]
    try:
        return subprocess.run(command, cwd=project, check=False, text=True, capture_output=True)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(command, 127, "", str(exc))
```

- [x] **Step 2: 实现仅返回匹配标识或 `None`（无匹配）的探测器**

```python
def find_orca_worktree_id(project: Path, target: Path) -> str | None:
    result = orca(project, "worktree", "ps", "--json")
    if result.returncode != 0:
        return None
    try:
        worktrees = json.loads(result.stdout)["result"]["worktrees"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    target_key = normalized_path(target)
    for item in worktrees:
        if isinstance(item, dict) and isinstance(item.get("path"), str) and normalized_path(item["path"]) == target_key:
            worktree_id = item.get("worktreeId")
            return worktree_id if isinstance(worktree_id, str) and worktree_id else None
    return None
```

- [x] **Step 3: 在现有安全预检之后接入唯一删除器**

```python
orca_worktree_id = find_orca_worktree_id(controller, target)
if orca_worktree_id:
    result = orca(controller, "worktree", "rm", "--worktree", f"id:{orca_worktree_id}", "--json")
    if result.returncode != 0:
        raise PrFlowError(
            "orca_worktree_remove_failed",
            command_failure_details("orca_worktree_remove_failed", result),
        )
else:
    require_git_success(controller, "git_worktree_remove_failed", "worktree", "remove", str(target.resolve()))
```

保留这段之后已有的 Git（版本管理）工作树清单回读；不要为 Orca（工作区管理器）路径添加 `--force`（强制参数）或 Git（版本管理）回退。

- [x] **Step 4: 运行新增测试确认通过**

Run: `python -m pytest tests/test_pr_flow_cli.py -k "remove_worktree" -q`

Expected: PASS，包括现有原生删除回归和新增 Orca（工作区管理器）选择回归。

- [x] **Step 5: 运行格式与相关 PR Flow（拉取请求流程）回归**

Run: `python -m pytest tests/test_pr_flow_cli.py -q`

Expected: PASS，无失败或跳过的新增测试。

- [x] **Step 6: 提交实现**

```bash
git add plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tests/test_pr_flow_cli.py
git commit -m "支持 Orca 工作树安全删除"
```

### Task 3: 更新删除工作树的用户说明

**Files:**
- Modify: `plugins/pr-flow/skills/pr-flow-cleanup/SKILL.md:12`
- Modify: `plugins/pr-flow/skills/pr-flow-complete/SKILL.md:14`
- Modify: `plugins/pr-flow/skills/pr-flow-hotfix/SKILL.md:18`
- Reference: `openspec/changes/prefer-orca-worktree-removal/specs/pr-flow-plugin/spec.md`

**Interfaces:**
- Consumes: `--remove-worktree`（删除工作树参数）的既有安全契约。
- Produces: 三个入口一致的 Orca（工作区管理器）优先删除说明。

- [x] **Step 1: 在三份技能的删除工作树段落中加入相同的行为说明**

```markdown
若目标工作树由 Orca（工作区管理器）登记，命令优先使用 Orca（工作区管理器）的非强制删除；Orca（工作区管理器）未登记或不可用时回退 Git（版本管理）删除。已登记目标的 Orca（工作区管理器）删除失败时停止并保留诊断，不回退 Git（版本管理）删除。
```

- [x] **Step 2: 核对说明未承诺关闭终端、强制删除或修改 Orca（工作区管理器）配置**

Run: `rg -n "Orca|--force|强制" plugins/pr-flow/skills/pr-flow-{cleanup,complete,hotfix}/SKILL.md`

Expected: 所有 Orca（工作区管理器）说明均保留“非强制删除”和失败停止边界。

- [x] **Step 3: 提交说明更新**

```bash
git add plugins/pr-flow/skills/pr-flow-cleanup/SKILL.md plugins/pr-flow/skills/pr-flow-complete/SKILL.md plugins/pr-flow/skills/pr-flow-hotfix/SKILL.md
git commit -m "说明 Orca 工作树删除边界"
```

### Task 4: 运行规格和发布形态验证

**Files:**
- Verify: `openspec/changes/prefer-orca-worktree-removal/`
- Verify: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Verify: `tests/test_pr_flow_cli.py`

**Interfaces:**
- Consumes: 完成的 OpenSpec（开放规格）任务、PR Flow（拉取请求流程）回归和 build-and-verify（构建与验证）运行时。
- Produces: 可审计的 build（构建）与 verify（验证）证据。

- [x] **Step 1: 运行严格 OpenSpec（开放规格）校验和差异检查**

Run:

```bash
openspec validate prefer-orca-worktree-removal --strict --no-interactive
git diff --check
```

Expected: change（变更）有效，且无空白错误。

- [x] **Step 2: 运行 PR Flow（拉取请求流程）用户入口回归**

Run: `python -m pytest tests/test_pr_flow_cli.py -q`

Expected: PASS，覆盖 `--remove-worktree`（删除工作树参数）的 Orca（工作区管理器）优先、Git（版本管理）回退和失败停止行为。

- [x] **Step 3: 使用标准入口运行构建检查**

Run: `python .build-and-verify/runtime/build_and_verify.py build --project .`

Expected: `status: passed`。

- [x] **Step 4: 使用已获用户确认的完整验证运行标准入口**

Run: `python .build-and-verify/runtime/build_and_verify.py verify --project . --full`

Expected: `status: passed`；如出现既有 Windows（视窗）编码警告，在验证报告中单独记录但不掩盖失败。

- [x] **Step 5: 提交验证产物（如有）并记录 Comet（彗星流程）检查证据**

```bash
git status --short
comet state record-check prefer-orca-worktree-removal build --command "python .build-and-verify/runtime/build_and_verify.py build --project ." --exit-code 0
```
