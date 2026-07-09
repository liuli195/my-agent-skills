---
change: guard-test-runtime-boundaries
design-doc: docs/superpowers/specs/2026-07-02-guard-test-runtime-boundaries-design.md
base-ref: 5b7d6a74bda8d3c7ad09d4a3b2fcbf614770c788
archived-with: 2026-07-02-guard-test-runtime-boundaries
---

# Guard Test Runtime Boundaries（测试运行边界守门）实施计划

> **For agentic workers（给代理执行者）:** REQUIRED SUB-SKILL（必需子技能）: Use superpowers:subagent-driven-development（子代理驱动开发，推荐）or superpowers:executing-plans（计划执行）to implement this plan task-by-task（逐项实施本计划）. Steps（步骤）use checkbox（复选框）`- [ ]` syntax（语法）for tracking（跟踪）.

**Goal（目标）:** 给整个 `tests/`（测试目录）加 AST（语法树）运行边界守门，把重复分支测试收缩到 in-process（进程内）和 fake runner（假执行器），并让 Full（完整验证）整体时间小于等于 30 秒。

**Architecture（方案）:** 新增一个专门的守门测试文件，用 Python AST（Python 语法树）扫描 test function（测试函数）、helper（辅助函数）和 fixture（测试夹具）的真实运行路径。`build-and-verify`（构建与验证）的必要真实入口只按 `file path + qualified test function`（文件路径加限定测试函数）放入 E2E allowlist（端到端白名单），其余分支覆盖直接调用现有 runner（执行器）函数并传入 fake runner（假执行器）。

**Tech Stack（技术栈）:** Python（Python 语言）标准库 `ast`（语法树）、`pathlib`（路径工具）、`subprocess.CompletedProcess`（进程结果对象）、pytest（Python 测试框架）、OpenSpec（开放规格）、build-and-verify（构建与验证）。

archived-with: 2026-07-02-guard-test-runtime-boundaries
---

## File Map（文件地图）

- Create（新增）: `tests/test_test_runtime_boundaries.py`，仓库级 AST（语法树）运行边界守门测试，含 E2E allowlist（端到端白名单）。
- Modify（修改）: `tests/test_build_and_verify_plugin.py`，把重复 runner（执行器）分支测试迁到 in-process（进程内）和 fake runner（假执行器），保留少量真实入口 E2E（端到端测试）。
- Modify（修改）: `tests/test_pr_flow_cli.py`, `tests/test_release_flow_cli.py`, `tests/test_cross_agent_review_cli.py`, `tests/test_agent_guard_*.py`，把非必要真实流程改为模拟运行。
- Modify（修改）: `.build-and-verify/config.json`，把新守门测试加入 `verify.build-and-verify`（构建与验证检查项），固定 `maxParallel=0`，并保持 Pytest（测试工具）worker（工作进程）为 `auto`。
- Create（新增）: `docs/superpowers/reports/2026-07-02-guard-test-runtime-boundaries-runtime.md`，记录 before/after runtime（前后运行时间）。
- Modify（修改）: `openspec/changes/guard-test-runtime-boundaries/tasks.md`，验证完成后勾选对应任务。
- Create（新增）: `openspec/changes/stabilize-flow-recovery-actions/`，按用户授权随本 commit（提交）保存后续 OpenSpec（开放规格）脚手架。
- Create（新增）: `openspec/changes/stabilize-version-runtime-sync/`，按用户授权随本 commit（提交）保存后续 OpenSpec（开放规格）脚手架。

## Bundled Planning Artifacts（随提交规划产物）

`stabilize-flow-recovery-actions` 和 `stabilize-version-runtime-sync` 只作为后续 change（变更）规划草案一起提交；不计入本计划的实现验收任务。

## Commit Policy（提交规则）

仓库规则要求明确授权后才能 commit（提交）。本计划只写验证点，不要求执行者自行 commit（提交）。

archived-with: 2026-07-02-guard-test-runtime-boundaries
---

### Task 1: AST Scanner（语法树扫描器）自测

**Files（文件）:**
- Create（新增）: `tests/test_test_runtime_boundaries.py`

- [x] **Step 1: Write failing scanner tests（写失败扫描器测试）**

Create `tests/test_test_runtime_boundaries.py` with this first section:

```python
from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = REPO_ROOT / "tests"


@dataclass(frozen=True)
class RuntimeHit:
    identity: str
    category: str
    line: int
    detail: str


def test_scan_source_flags_direct_subprocess() -> None:
    source = """
import subprocess

def test_real_process():
    subprocess.run(["python", "--version"], check=False)
"""

    hits = scan_source(Path("tests/test_sample.py"), source, {})

    assert hits == [
        RuntimeHit(
            "tests/test_sample.py::test_real_process",
            "subprocess",
            5,
            "subprocess.run",
        )
    ]


def test_scan_source_follows_helper_and_fixture_runtime_paths() -> None:
    source = """
import pytest
import subprocess

def run_cli(*args):
    return subprocess.run(["python", "tool.py", *args], check=False)

@pytest.fixture
def git_project(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=False)
    return tmp_path

def test_helper_path():
    run_cli("verify")

def test_fixture_path(git_project):
    assert git_project.exists()
"""

    hits = scan_source(Path("tests/test_sample.py"), source, {})

    assert hits == [
        RuntimeHit(
            "tests/test_sample.py::test_helper_path",
            "cli-entrypoint",
            13,
            "run_cli -> subprocess.run",
        ),
        RuntimeHit(
            "tests/test_sample.py::test_fixture_path",
            "temporary-git",
            16,
            "fixture git_project -> subprocess.run git init",
        ),
    ]


def test_scan_source_flags_broad_runtime_cache_scan() -> None:
    source = '''
from pathlib import Path

def test_cache_scan():
    cache_files = list(Path(".build-and-verify/cache").glob("*.json"))
    assert cache_files == []
'''

    hits = scan_source(Path("tests/test_sample.py"), source, {})

    assert hits == [
        RuntimeHit(
            "tests/test_sample.py::test_cache_scan",
            "broad-cache-scan",
            5,
            "Path.glob over .build-and-verify/cache",
        )
    ]
```

- [x] **Step 2: Run scanner tests and verify failure（运行扫描器测试并确认失败）**

Run（运行）:

```bash
python -m pytest -q tests/test_test_runtime_boundaries.py -k "scan_source"
```

Expected（预期）: FAIL（失败） because `scan_source`（扫描源码函数） is not defined.

- [x] **Step 3: Implement scanner helpers（实现扫描辅助函数）**

Append this code above the tests in `tests/test_test_runtime_boundaries.py`:

```python
RISKY_HELPER_NAMES = {
    "run",
    "run_cli",
    "run_hook",
    "run_hook_stdin",
    "run_installer",
    "run_build_and_verify",
    "run_git",
    "git",
}

CLI_HELPER_NAMES = {
    "run",
    "run_cli",
    "run_hook",
    "run_hook_stdin",
    "run_installer",
    "run_build_and_verify",
}

GIT_HELPER_NAMES = {"git", "run_git", "git_project", "bare_remote_template"}


@dataclass(frozen=True)
class FunctionInfo:
    name: str
    args: tuple[str, ...]
    calls: tuple[tuple[str, int, str], ...]
    fixtures: tuple[str, ...]


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def literal_text(node: ast.AST, source: str) -> str:
    return ast.get_source_segment(source, node) or ""


def function_identity(path: Path, name: str) -> str:
    return f"{path.as_posix()}::{name}"


def function_infos(source: str) -> dict[str, FunctionInfo]:
    tree = ast.parse(textwrap.dedent(source))
    infos: dict[str, FunctionInfo] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        calls: list[tuple[str, int, str]] = []
        fixtures: list[str] = []
        for decorator in node.decorator_list:
            name = call_name(decorator)
            if name == "pytest.fixture" or name.endswith(".fixture"):
                fixtures.append(node.name)
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                calls.append((call_name(child.func), child.lineno, literal_text(child, source)))
        infos[node.name] = FunctionInfo(
            node.name,
            tuple(arg.arg for arg in node.args.args),
            tuple(calls),
            tuple(fixtures),
        )
    return infos


def classify_call(name: str, call_text: str) -> tuple[str, str] | None:
    if name in {"subprocess.run", "subprocess.check_call", "subprocess.check_output"}:
        if '"git"' in call_text or "'git'" in call_text:
            if '"init"' in call_text or "'init'" in call_text:
                return "temporary-git", f"{name} git init"
        return "subprocess", name
    short_name = name.rsplit(".", 1)[-1]
    if short_name in CLI_HELPER_NAMES:
        return "cli-entrypoint", short_name
    if short_name in GIT_HELPER_NAMES:
        return "temporary-git", short_name
    if name in {"Path.glob", "Path.rglob"} or short_name in {"glob", "rglob"}:
        if ".build-and-verify/cache" in call_text:
            return "broad-cache-scan", "Path.glob over .build-and-verify/cache"
    return None


def collect_function_hits(
    path: Path,
    source: str,
    infos: dict[str, FunctionInfo],
    name: str,
    *,
    line_override: int | None = None,
    prefix: str = "",
    seen: frozenset[str] = frozenset(),
) -> list[RuntimeHit]:
    if name in seen or name not in infos:
        return []
    info = infos[name]
    hits: list[RuntimeHit] = []
    for call, line, call_text in info.calls:
        classified = classify_call(call, call_text)
        if classified is not None:
            category, detail = classified
            hits.append(
                RuntimeHit(
                    function_identity(path, name),
                    category,
                    line_override or line,
                    f"{prefix}{detail}",
                )
            )
        short_name = call.rsplit(".", 1)[-1]
        if short_name in infos and short_name in RISKY_HELPER_NAMES:
            nested_hits = collect_function_hits(
                path,
                source,
                infos,
                short_name,
                line_override=line_override or line,
                prefix=f"{short_name} -> ",
                seen=seen | {name},
            )
            hits.extend(
                RuntimeHit(function_identity(path, name), hit.category, hit.line, hit.detail)
                for hit in nested_hits
            )
    return hits


def scan_source(path: Path, source: str, shared_fixtures: dict[str, FunctionInfo]) -> list[RuntimeHit]:
    infos = function_infos(source)
    fixtures = {
        fixture_name: info
        for info in infos.values()
        for fixture_name in info.fixtures
    }
    fixtures.update(shared_fixtures)
    hits: list[RuntimeHit] = []
    for name, info in infos.items():
        if not name.startswith("test_"):
            continue
        hits.extend(collect_function_hits(path, source, infos, name))
        for arg in info.args:
            if arg in fixtures:
                fixture_hits = collect_function_hits(
                    path,
                    source,
                    {arg: fixtures[arg], **infos},
                    arg,
                    prefix=f"fixture {arg} -> ",
                )
                hits.extend(
                    RuntimeHit(function_identity(path, name), hit.category, info.calls[0][1] if info.calls else 1, hit.detail)
                    for hit in fixture_hits
                )
    return sorted(set(hits), key=lambda hit: (hit.identity, hit.category, hit.line, hit.detail))
```

- [x] **Step 4: Run scanner tests and verify pass（运行扫描器测试并确认通过）**

Run（运行）:

```bash
python -m pytest -q tests/test_test_runtime_boundaries.py -k "scan_source"
```

Expected（预期）: PASS（通过）.

archived-with: 2026-07-02-guard-test-runtime-boundaries
---

### Task 2: Repository Boundary Guard（仓库边界守门）

**Files（文件）:**
- Modify（修改）: `tests/test_test_runtime_boundaries.py`

- [x] **Step 1: Add repository scan and allowlist shape checks（添加仓库扫描与白名单格式检查）**

Append this code to `tests/test_test_runtime_boundaries.py`:

```python
E2E_ALLOWLIST: dict[str, str] = {
    "tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo": (
        "covers packaged init entrypoint and copied runtime verify entrypoint"
    ),
    "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_initialize_another_project": (
        "covers copied repository runtime init entrypoint"
    ),
    "tests/test_build_and_verify_plugin.py::test_build_and_verify_user_level_skill_path_runs_verify_without_git": (
        "covers user-level skill path verify entrypoint without git"
    ),
    "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_update_itself": (
        "covers copied repository runtime update-runtime entrypoint"
    ),
}


def shared_fixture_infos() -> dict[str, FunctionInfo]:
    conftest = TESTS_ROOT / "conftest.py"
    if not conftest.exists():
        return {}
    infos = function_infos(conftest.read_text(encoding="utf-8"))
    return {
        fixture_name: info
        for info in infos.values()
        for fixture_name in info.fixtures
    }


def scan_repository_tests() -> list[RuntimeHit]:
    fixtures = shared_fixture_infos()
    hits: list[RuntimeHit] = []
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        relative = path.relative_to(REPO_ROOT)
        hits.extend(scan_source(relative, path.read_text(encoding="utf-8"), fixtures))
    return sorted(set(hits), key=lambda hit: (hit.identity, hit.category, hit.line, hit.detail))


def format_hit(hit: RuntimeHit) -> str:
    suggestion = {
        "subprocess": "use in-process call or fake runner",
        "cli-entrypoint": "move branch coverage to in-process call or add focused E2E allowlist reason",
        "temporary-git": "fake git output unless this proves packaged git behavior",
        "broad-cache-scan": "scope cache assertion to one known path",
    }[hit.category]
    return f"{hit.identity}:{hit.line}: {hit.category}: {hit.detail}; {suggestion}"


def test_e2e_allowlist_uses_function_identity_and_reasons() -> None:
    for identity, reason in E2E_ALLOWLIST.items():
        assert identity.startswith("tests/")
        assert "::" in identity
        assert identity.split("::", 1)[1].startswith("test_")
        assert reason.strip()


def test_build_and_verify_keeps_focused_real_entrypoint_coverage() -> None:
    init_entries = [
        identity
        for identity, reason in E2E_ALLOWLIST.items()
        if identity.startswith("tests/test_build_and_verify_plugin.py::")
        and "init entrypoint" in reason
    ]
    verify_entries = [
        identity
        for identity, reason in E2E_ALLOWLIST.items()
        if identity.startswith("tests/test_build_and_verify_plugin.py::")
        and "verify entrypoint" in reason
    ]

    assert init_entries == [
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo",
        "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_initialize_another_project",
    ]
    assert verify_entries == [
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo",
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_user_level_skill_path_runs_verify_without_git",
    ]


def test_repository_tests_do_not_cross_runtime_boundaries_without_allowlist() -> None:
    violations = [
        format_hit(hit)
        for hit in scan_repository_tests()
        if hit.identity not in E2E_ALLOWLIST
    ]

    assert violations == []
```

- [x] **Step 2: Run repository guard and capture current failures（运行仓库守门并记录当前失败）**

Run（运行）:

```bash
python -m pytest -q tests/test_test_runtime_boundaries.py
```

Expected（预期）: FAIL（失败） with `tests/test_build_and_verify_plugin.py` violations for repeated branch tests that still call `run_build_and_verify`（真实构建与验证入口）, `run_check`（进程内命令包装但真实执行命令）, `git`（版本控制） helper（辅助函数）, or broad cache（大范围缓存） glob（文件匹配） without a focused E2E allowlist（端到端白名单） reason.

archived-with: 2026-07-02-guard-test-runtime-boundaries
---

### Task 3: Build-and-Verify Test Helpers（构建与验证测试辅助函数）

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`

- [x] **Step 1: Add in-process fake runner helpers（添加进程内假执行器辅助函数）**

Add these helpers after `write_json()` in `tests/test_build_and_verify_plugin.py`:

```python
def write_runner_config(
    project: Path,
    *,
    build_checks: list[dict[str, Any]] | None = None,
    verify_checks: list[dict[str, Any]] | None = None,
    verify_config: dict[str, Any] | None = None,
) -> None:
    config = {
        "version": 1,
        "build": {"checks": build_checks or []},
        "verify": {"checks": verify_checks or []},
    }
    if verify_config:
        config["verify"].update(verify_config)
    write_json(project / ".build-and-verify" / "config.json", config)
    (project / ".build-and-verify" / "cache").mkdir(parents=True, exist_ok=True)


def completed(
    command: Any,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[Any]:
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


class FakeRunner:
    def __init__(
        self,
        outcomes: dict[Any, subprocess.CompletedProcess[Any]] | None = None,
    ) -> None:
        self.calls: list[Any] = []
        self.outcomes = outcomes or {}

    def __call__(self, command, **_kwargs):
        self.calls.append(command)
        key = tuple(command) if isinstance(command, list) else command
        return self.outcomes.get(key, completed(command))
```

- [x] **Step 2: Run existing build-and-verify tests and verify no helper-only regression（运行现有测试并确认辅助函数未破坏）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py::test_build_and_verify_main_returns_error_without_command
```

Expected（预期）: PASS（通过）.

archived-with: 2026-07-02-guard-test-runtime-boundaries
---

### Task 4: Migrate Repeated Runner Branch Tests（迁移重复执行器分支测试）

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`

- [x] **Step 1: Convert build/default/full branch test（转换构建、快速、完整分支测试）**

Replace `test_build_and_verify_runner_build_verify_and_full_verify()` with:

```python
def test_build_and_verify_runner_build_verify_and_full_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    runner = load_build_and_verify_module()._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "docs").mkdir()
    (project / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
    (project / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        project,
        build_checks=[{"id": "build-main", "command": ["build-main"]}],
        verify_checks=[
            {
                "id": "verify-src",
                "command": ["verify-src"],
                "paths": ["src/**"],
                "inputs": ["src"],
            },
            {
                "id": "verify-docs",
                "command": ["verify-docs"],
                "paths": ["docs/**"],
                "inputs": ["docs"],
            },
        ],
    )
    fake = FakeRunner()
    monkeypatch.setattr(runner, "_changed_files", lambda _project: ["src/app.py", "docs/guide.md"])

    build = runner.run_build(project, runner=fake)
    build_output = capsys.readouterr().out
    verify = runner.run_verify(project, runner=fake)
    verify_output = capsys.readouterr().out
    full_verify = runner.run_verify(project, runner=fake, full=True)
    full_output = capsys.readouterr().out

    assert build == 0
    assert "checked: build-main" in build_output
    assert verify == 0
    assert "checked: verify-src, verify-docs" in verify_output
    assert "full-not-run: true" in verify_output
    assert full_verify == 0
    assert "checked: verify-src, verify-docs" in full_output
    assert "full-not-run: false" in full_output
    assert "cache-hit" not in full_output
    assert fake.calls == [["build-main"], ["verify-src"], ["verify-docs"], ["verify-src"], ["verify-docs"]]
```

- [x] **Step 2: Convert cache branch tests（转换缓存分支测试）**

For these exact functions, remove `run_build_and_verify("init", ...)`, `run_check(...)`, `command_that_logs(...)`, and `run.log` assertions:

```text
test_build_and_verify_runner_uses_passed_result_cache
test_build_and_verify_runner_full_verify_ignores_existing_default_cache
test_build_and_verify_runner_full_verify_refreshes_cache_for_default_verify
test_build_and_verify_runner_cache_miss_does_not_fall_back_to_full
test_build_and_verify_runner_no_check_does_not_fall_back_to_full
test_build_and_verify_runner_does_not_cache_failed_results
```

Use this replacement shape for `test_build_and_verify_runner_uses_passed_result_cache()`:

```python
def test_build_and_verify_runner_uses_passed_result_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    runner = load_build_and_verify_module()._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src" / "cached.py").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        project,
        verify_checks=[
            {
                "id": "cache-check",
                "command": ["cache-check"],
                "paths": ["src/cached.py"],
                "inputs": ["src/cached.py"],
            }
        ],
    )
    fake = FakeRunner()
    monkeypatch.setattr(runner, "_changed_files", lambda _project: ["src/cached.py"])

    first = runner.run_verify(project, runner=fake)
    cache_files = list((project / ".build-and-verify" / "cache").glob("*.json"))
    first_output = capsys.readouterr().out
    second = runner.run_verify(project, runner=fake)
    second_output = capsys.readouterr().out

    assert first == 0
    assert second == 0
    assert "checked: cache-check" in first_output
    assert len(cache_files) == 1
    assert read_json(cache_files[0]) == {"status": "passed", "id": "cache-check"}
    assert "cache-hit: cache-check" in second_output
    assert fake.calls == [["cache-check"]]
```

Use this replacement shape for failed-result caching:

```python
def test_build_and_verify_runner_does_not_cache_failed_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    runner = load_build_and_verify_module()._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src" / "fails.py").write_text("changed\n", encoding="utf-8")
    write_runner_config(
        project,
        verify_checks=[
            {
                "id": "fail-once",
                "command": ["fail-once"],
                "paths": ["src/fails.py"],
                "inputs": ["src/fails.py"],
            }
        ],
    )
    returncodes = [7, 0]

    def fake_runner(command, **_kwargs):
        return completed(command, returncodes.pop(0))

    monkeypatch.setattr(runner, "_changed_files", lambda _project: ["src/fails.py"])

    first = runner.run_verify(project, runner=fake_runner)
    second = runner.run_verify(project, runner=fake_runner)
    output = capsys.readouterr().out

    assert first == 1
    assert second == 0
    assert "cache-hit: fail-once" not in output
    assert returncodes == []
```

- [x] **Step 3: Convert temporary git branch tests（转换临时版本控制分支测试）**

Replace real temporary git（临时版本控制） setup in these exact functions with monkeypatched changed-files（变更文件） output:

```text
test_build_and_verify_runner_cache_misses_when_input_is_deleted
test_build_and_verify_runner_default_cache_key_tracks_changed_files
test_build_and_verify_pathless_check_skips_clean_git_worktree
test_build_and_verify_runner_default_check_cache_key_tracks_dirty_file_contents
test_build_and_verify_runner_reads_worktree_changed_files
```

Use this full replacement for `test_build_and_verify_runner_reads_worktree_changed_files()`:

```python
def test_build_and_verify_runner_reads_worktree_changed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    runner = load_build_and_verify_module()._runner()
    project = tmp_path / "project"
    project.mkdir()
    for name in ["staged.txt", "unstaged.txt", "untracked.txt"]:
        (project / name).write_text(name + "\n", encoding="utf-8")
    write_runner_config(
        project,
        verify_checks=[
            {"id": "staged-check", "command": ["staged-check"], "paths": ["staged.txt"], "inputs": ["staged.txt"]},
            {"id": "unstaged-check", "command": ["unstaged-check"], "paths": ["unstaged.txt"], "inputs": ["unstaged.txt"]},
            {"id": "untracked-check", "command": ["untracked-check"], "paths": ["untracked.txt"], "inputs": ["untracked.txt"]},
        ],
    )
    fake = FakeRunner()
    monkeypatch.setattr(
        runner,
        "_changed_files",
        lambda _project: ["staged.txt", "unstaged.txt", "untracked.txt"],
    )

    result = runner.run_verify(project, runner=fake)
    output = capsys.readouterr().out

    assert result == 0
    assert "checked: staged-check, unstaged-check, untracked-check" in output
    assert fake.calls == [["staged-check"], ["unstaged-check"], ["untracked-check"]]
```

- [x] **Step 4: Convert validation branch tests（转换校验分支测试）**

For these exact functions, replace real init（初始化） with `write_runner_config()`:

```text
test_build_and_verify_runner_reports_missing_list_command_without_traceback
test_build_and_verify_runner_verify_reports_missing_config_without_traceback
test_build_and_verify_runner_rejects_inputs_outside_project
test_build_and_verify_runner_full_verify_rejects_inputs_outside_project
test_build_and_verify_runner_cache_key_changes_with_check_contract
test_build_and_verify_runner_directory_hash_ignores_generated_paths
```

Use this replacement shape for missing config（缺失配置）:

```python
def test_build_and_verify_runner_verify_reports_missing_config_without_traceback(
    tmp_path: Path, capsys
) -> None:
    runner = load_build_and_verify_module()._runner()
    project = tmp_path / "project"
    project.mkdir()

    result = runner.run_verify(project)
    captured = capsys.readouterr()
    output = captured.out + captured.err

    assert result == 1
    assert "missing_config: .build-and-verify/config.json" in output
    assert "status: failed" in captured.out
    assert "Traceback" not in output
```

- [x] **Step 5: Run migrated build-and-verify branch tests（运行迁移后的构建与验证分支测试）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py -k "runner_ or cache_ or pathless"
```

Expected（预期）: PASS（通过）.

archived-with: 2026-07-02-guard-test-runtime-boundaries
---

### Task 5: Narrow E2E Allowlist（收窄端到端白名单）

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`
- Modify（修改）: `tests/test_test_runtime_boundaries.py`

- [x] **Step 1: Convert extra init branch tests to in-process（把额外初始化分支测试改为进程内）**

Keep only these `build-and-verify`（构建与验证） packaged entrypoint（发布形态入口） tests real:

```text
tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo
tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_initialize_another_project
tests/test_build_and_verify_plugin.py::test_build_and_verify_user_level_skill_path_runs_verify_without_git
tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_update_itself
```

For `test_build_and_verify_init_writes_config_gitignore_and_cache()` and `test_build_and_verify_init_copies_repository_runtime()`, replace `run_build_and_verify("init", ...)` with in-process `main()`:

```python
def call_build_and_verify_main(*args: str) -> subprocess.CompletedProcess[str]:
    module = load_build_and_verify_module()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        returncode = int(module.main(list(args)))
    return subprocess.CompletedProcess(
        args=[str(BUILD_AND_VERIFY_SCRIPT), *args],
        returncode=returncode,
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
    )
```

Then use:

```python
result = call_build_and_verify_main("init", "--project", str(project))
```

- [x] **Step 2: Keep allowlist by function identity（按函数身份保留白名单）**

Leave `E2E_ALLOWLIST` in `tests/test_test_runtime_boundaries.py` with exactly these `build-and-verify`（构建与验证） entries and reasons:

```python
E2E_ALLOWLIST: dict[str, str] = {
    "tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo": (
        "covers packaged init entrypoint and copied runtime verify entrypoint"
    ),
    "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_initialize_another_project": (
        "covers copied repository runtime init entrypoint"
    ),
    "tests/test_build_and_verify_plugin.py::test_build_and_verify_user_level_skill_path_runs_verify_without_git": (
        "covers user-level skill path verify entrypoint without git"
    ),
    "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_update_itself": (
        "covers copied repository runtime update-runtime entrypoint"
    ),
}
```

- [x] **Step 3: Run boundary guard（运行边界守门）**

Run（运行）:

```bash
python -m pytest -q tests/test_test_runtime_boundaries.py
```

Expected（预期）: PASS（通过）. If it fails, every failure line must name one `file path + qualified test function`（文件路径加限定测试函数） and one category（类别）.

archived-with: 2026-07-02-guard-test-runtime-boundaries
---

### Task 6: Build-and-Verify Check Wiring（构建与验证检查接线）

**Files（文件）:**
- Modify（修改）: `.build-and-verify/config.json`

- [x] **Step 1: Add boundary guard to verify config（把边界守门加入验证配置）**

In `.build-and-verify/config.json`, update the `verify.build-and-verify`（构建与验证检查项） object.

Add this path to `paths`（路径清单）:

```json
"tests/test_test_runtime_boundaries.py"
```

Change `command`（命令） from:

```json
"python -m pytest -q -p no:cacheprovider tests/test_build_and_verify_plugin.py"
```

to:

```json
"python -m pytest -q -p no:cacheprovider tests/test_build_and_verify_plugin.py tests/test_test_runtime_boundaries.py"
```

Add this input to `inputs`（缓存输入）:

```json
"tests/test_test_runtime_boundaries.py"
```

- [x] **Step 2: Validate JSON（校验 JSON 数据格式）**

Run（运行）:

```bash
python -m json.tool .build-and-verify/config.json > NUL
```

Expected（预期）: exit code（退出码） `0`.

archived-with: 2026-07-02-guard-test-runtime-boundaries
---

### Task 7: Runtime Report（运行时间记录）

**Files（文件）:**
- Create（新增）: `docs/superpowers/reports/2026-07-02-guard-test-runtime-boundaries-runtime.md`

- [x] **Step 1: Capture before runtime（记录修改前运行时间）**

Before the refactor changes in Task 4 are applied, run（运行） and keep the printed `TotalSeconds`（总秒数） value:

```powershell
$before = Measure-Command { python -m pytest -q tests/test_build_and_verify_plugin.py }
$before.TotalSeconds
```

Create `docs/superpowers/reports/2026-07-02-guard-test-runtime-boundaries-runtime.md` with the heading `# Guard Test Runtime Boundaries Runtime（测试运行边界守门运行时间）`, the command `python -m pytest -q tests/test_build_and_verify_plugin.py`, a `Before（修改前）` section, `Date（日期）: 2026-07-02`, `Result（结果）: PASS`, and the numeric `TotalSeconds（总秒数）` value printed by `$before.TotalSeconds`.

- [x] **Step 2: Capture after runtime（记录修改后运行时间）**

After Tasks 4-6 pass, run（运行） and keep the printed `TotalSeconds`（总秒数） value:

```powershell
$after = Measure-Command { python -m pytest -q tests/test_build_and_verify_plugin.py }
$after.TotalSeconds
```

Add an `After（修改后）` section to the same report with `Date（日期）: 2026-07-02`, `Result（结果）: PASS`, and the numeric `TotalSeconds（总秒数）` value printed by `$after.TotalSeconds`. The report must keep both measured numbers from the same command.

archived-with: 2026-07-02-guard-test-runtime-boundaries
---

### Task 8: Verification（验证）

**Files（文件）:**
- Modify（修改）: `openspec/changes/guard-test-runtime-boundaries/tasks.md`

- [x] **Step 1: Run focused tests（运行聚焦测试）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py
python -m pytest -q tests/test_test_runtime_boundaries.py
```

Expected（预期）: both PASS（都通过）.

- [x] **Step 2: Run OpenSpec validation（运行开放规格验证）**

Run（运行）:

```bash
openspec validate guard-test-runtime-boundaries --strict --no-interactive
```

Expected（预期）: PASS（通过）.

- [x] **Step 3: Run fast verification（运行快速验证）**

Run（运行）:

```bash
python .build-and-verify/runtime/build_and_verify.py verify --project "D:\My Project\my-agent-skills"
```

Expected（预期）:

```text
status: passed
full-not-run: true
```

- [x] **Step 4: Run full verification（运行完整验证）**

Run（运行）:

```bash
python .build-and-verify/runtime/build_and_verify.py verify --project "D:\My Project\my-agent-skills" --full
```

Expected（预期）:

```text
status: passed
full-not-run: false
```

- [x] **Step 5: Mark OpenSpec tasks complete（标记开放规格任务完成）**

After Steps 1-4 pass and the runtime report contains before/after（前后） numbers, update `openspec/changes/guard-test-runtime-boundaries/tasks.md` so all checkboxes are checked:

```markdown
## 1. Contract Tests

- [x] 1.1 Add repository-wide Python AST（Python 语法树） test scan for ordinary tests using real subprocess（子进程）, CLI（命令行） entrypoints, temporary git（版本控制）, or broad cache（缓存） scans, including this repository's existing helper（辅助函数） and fixture（测试夹具） shapes.
- [x] 1.2 Add a narrow E2E（端到端测试） allowlist by test function identity（测试函数身份） with documented reasons.
- [x] 1.3 Add focused checks that build-and-verify（构建与验证） keeps one init（初始化） E2E（端到端测试） and one verify（验证） E2E（端到端测试）.

## 2. Minimal Test Refactor

- [x] 2.1 Convert repeated build-and-verify（构建与验证） branch tests from real subprocess（子进程） to in-process（进程内） calls.
- [x] 2.2 Reuse existing command runner（命令执行器） or add the smallest helper needed to fake command execution in tests.
- [x] 2.3 Remove or narrow duplicate E2E（端到端测试） coverage that no longer proves a distinct packaged entrypoint behavior.

## 3. Verification

- [x] 3.1 Run the repository-wide test boundary guard.
- [x] 3.2 Capture focused build-and-verify（构建与验证） runtime baseline before refactor and after refactor with the same command: `python -m pytest -q tests/test_build_and_verify_plugin.py`; completion requires both timings to be recorded and no added duplicate E2E（端到端测试） path.
- [x] 3.3 Run repository build-and-verify（构建与验证） fast verification.
- [x] 3.4 Run repository build-and-verify（构建与验证） full verification.
```

- [x] **Step 6: Confirm changed file scope（确认变更文件范围）**

Run（运行）:

```bash
git diff --name-only
```

Expected（预期）: output is limited to:

```text
.build-and-verify/config.json
docs/superpowers/reports/2026-07-02-guard-test-runtime-boundaries-runtime.md
openspec/changes/guard-test-runtime-boundaries/tasks.md
tests/test_build_and_verify_plugin.py
tests/test_test_runtime_boundaries.py
```

archived-with: 2026-07-02-guard-test-runtime-boundaries
---

## Self Review（自查）

- Spec coverage（规格覆盖）: AST（语法树）守门、helper（辅助函数）/ fixture（测试夹具）真实路径、E2E allowlist（端到端白名单）函数身份格式、build-and-verify（构建与验证）重复分支迁移、before/after runtime（前后运行时间）、fast verification（快速验证）和 full verification（完整验证）均有任务。
- Plan scan（计划扫描）: 没有保留空白任务描述或延后补写说明。
- Minimality（最小化）: 不新增生产代码接口；复用现有 runner（执行器）注入点和 Python AST（Python 语法树）标准库。
