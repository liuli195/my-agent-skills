---
change: fix-build-and-verify-init-parallel-runtime
design-doc: docs/superpowers/specs/2026-07-02-build-and-verify-init-parallel-runtime-design.md
base-ref: 35717b7e89d2564a2d690733e991bc58d4332b12
---

# Build and Verify Init Parallel Runtime（构建与验证初始化并行运行时）实施计划

> **For agentic workers（给代理执行者）:** REQUIRED SUB-SKILL（必需子技能）: Use superpowers:subagent-driven-development（子代理驱动开发，推荐）or superpowers:executing-plans（计划执行）to implement this plan task-by-task（逐项实施本计划）. Steps（步骤）use checkbox（复选框）`- [x]` syntax（语法）for tracking（跟踪）.

**Goal（目标）:** 让 `build-and-verify`（构建与验证）只通过 `init --config --overwrite`（初始化覆盖命令）写入已确认配置和 runtime（运行时），并把 check（检查项）之间并行与 pytest（Python 测试框架）内部并行拆成 `checkParallel`（检查项间并行）和 `pytestXdistWorkers`（Pytest 工作进程数）。

**Architecture（方案）:** 最小改动集中在现有命令入口、runner（运行器）、初始化 Skill（技能）文案和现有测试文件。`verify`（快速验证）和 `verify --full`（完整验证）共用一个调度器，fast（快速）先做 changed files（变更文件）和 cache（缓存）筛选，full（完整）不读 cache（缓存）跳过。当前仓库只更新 `D:\My Project\my-agent-skills` 的 config（配置）和 runtime（运行时）快照，明确不写入、不初始化 `D:\My Project\Quant-Research-Lab`。

**Tech Stack（技术栈）:** Python（Python 语言）标准库、pytest（Python 测试框架）、pytest-xdist（Pytest 并行插件）、OpenSpec（开放规格）、Markdown（文档格式）、JSON（配置格式）。

---

## File Map（文件地图）

- Modify（修改）: `tests/test_build_and_verify_plugin.py`，添加和更新 build-and-verify（构建与验证）回归测试。
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py`，校验 `checkParallel`（检查项间并行）和 `pytestXdistWorkers`（Pytest 工作进程数），并让 fast/full（快速/完整）共用调度器。
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py`，扩展 `init --config --overwrite`（初始化覆盖命令），执行备份、`.gitignore`（忽略规则）合并、runtime（运行时）复制和 cache（缓存）创建。
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify-init/SKILL.md`，把硬边界和写入流程改成调用 `build_and_verify.py init --config --overwrite`（初始化覆盖命令）。
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify-init/references/config-draft.md`，把 `parallel`（旧并行字段）改成 `checkParallel`（检查项间并行），补充 `pytestXdistWorkers`（Pytest 工作进程数）。
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify-init/references/validation.md`，让依赖检查识别 `pytestXdistWorkers`（Pytest 工作进程数）和缺失 `pytest-xdist`（Pytest 并行插件）。
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify-init/references/questionnaire.md`，Q5/Q6 的运行参数和最终摘要改成新字段。
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify-init/references/ecosystem-detection.md`，已有配置保留项改成新字段，旧 `parallel`（旧并行字段）只作为冲突提示。
- Modify（修改）: `.build-and-verify/config.json`，只在当前仓库把 `parallel`（旧并行字段）迁移到 `checkParallel`（检查项间并行），并把 pytest（Python 测试框架）命令中的 `-n` 参数迁移到 `pytestXdistWorkers`（Pytest 工作进程数）。
- Modify（修改）: `.build-and-verify/runtime/build_and_verify.py`、`.build-and-verify/runtime/build_and_verify_runner.py`、`.build-and-verify/runtime/version.json`，只刷新当前仓库 runtime（运行时）快照。
- Do not touch（不得触碰）: `D:\My Project\Quant-Research-Lab`，不写入、不初始化、不覆盖、不刷新 runtime（运行时）。

---

### Task 1: Runner（运行器）配置字段校验

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py`

- [x] **Step 1: Add failing tests（添加失败测试）**

Add tests near existing runner（运行器）config（配置） tests in `tests/test_build_and_verify_plugin.py`:

```python
def test_build_and_verify_runner_rejects_legacy_parallel_field(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "legacy-parallel",
                        "command": command_that_logs("legacy-parallel"),
                        "parallel": True,
                        "inputs": [],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 1
    assert "parallel is no longer supported; use checkParallel" in result.stderr
    assert "status: failed" in result.stdout


@pytest.mark.parametrize("value", [True, False])
def test_build_and_verify_runner_accepts_check_parallel_bool(
    tmp_path: Path, value: bool
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "check-parallel",
                        "command": command_that_logs("check-parallel"),
                        "checkParallel": value,
                        "inputs": [],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("value", ["true", 1, 0, None])
def test_build_and_verify_runner_rejects_invalid_check_parallel(
    tmp_path: Path, value: object
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "bad-check-parallel",
                        "command": command_that_logs("bad-check-parallel"),
                        "checkParallel": value,
                        "inputs": [],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 1
    assert "checkParallel must be boolean" in result.stderr
```

- [x] **Step 2: Run tests and verify failure（运行测试并确认失败）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_rejects_legacy_parallel_field tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_accepts_check_parallel_bool tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_rejects_invalid_check_parallel
```

Expected（预期）: at least（至少）the legacy `parallel`（旧并行字段） rejection（拒绝） test fails because the runner（运行器） still accepts it.

- [x] **Step 3: Implement minimal validation（实现最小校验）**

In `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py`, inside `_load_config()` check（检查项） loop, add this before existing `paths` / `inputs` validation（校验）:

```python
            if "parallel" in check:
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}].parallel is no longer supported; use checkParallel"
                )
            check_parallel = check.get("checkParallel")
            if check_parallel is not None and not isinstance(check_parallel, bool):
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}].checkParallel must be boolean"
                )
```

- [x] **Step 4: Update old tests to new field（更新旧测试字段）**

In `tests/test_build_and_verify_plugin.py`, replace existing test configs that use:

```python
"parallel": True
"parallel": False
```

with:

```python
"checkParallel": True
"checkParallel": False
```

Do not rename unrelated prose yet; Skill（技能）文案 changes are covered in Task 5.

- [x] **Step 5: Run focused runner field tests（运行聚焦字段测试）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py -k "check_parallel or legacy_parallel or full_verify_runs_parallel"
```

Expected（预期）: PASS（通过）。

---

### Task 2: Pytest Xdist Workers（Pytest 工作进程数）

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py`

- [x] **Step 1: Add failing tests（添加失败测试）**

Add tests near existing `pytest-xdist`（Pytest 并行插件） tests:

```python
@pytest.mark.parametrize("workers", ["auto", 1, 8])
def test_build_and_verify_runner_applies_pytest_xdist_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, workers: object
) -> None:
    module = load_build_and_verify_module()
    runner = module._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "pytest-workers",
                        "command": [sys.executable, "-m", "pytest", "tests"],
                        "pytestXdistWorkers": workers,
                        "inputs": [],
                    }
                ]
            },
        },
    )
    calls = []

    def fake_runner(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runner.importlib.util, "find_spec", lambda name: object() if name == "xdist" else None)

    result = runner.run_verify(project, runner=fake_runner, full=True)

    assert result == 0
    assert calls == [[sys.executable, "-m", "pytest", "-n", str(workers), "tests"]]


@pytest.mark.parametrize("workers", [0, -1, True, "8", ""])
def test_build_and_verify_runner_rejects_invalid_pytest_xdist_workers(
    tmp_path: Path, workers: object
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "bad-workers",
                        "command": [sys.executable, "-m", "pytest"],
                        "pytestXdistWorkers": workers,
                        "inputs": [],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode == 1
    assert "pytestXdistWorkers must be \"auto\" or positive integer" in result.stderr


def test_build_and_verify_runner_requires_xdist_for_pytest_xdist_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    module = load_build_and_verify_module()
    runner = module._runner()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "pytest-workers",
                        "command": [sys.executable, "-m", "pytest"],
                        "pytestXdistWorkers": "auto",
                        "inputs": [],
                    }
                ]
            },
        },
    )
    calls = []

    def fake_runner(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(runner.importlib.util, "find_spec", lambda _name: None)

    result = runner.run_verify(project, runner=fake_runner, full=True)
    captured = capsys.readouterr()

    assert result == 1
    assert calls == []
    assert "missing_dependency: pytest-workers: pytest-xdist is required" in captured.err
```

- [x] **Step 2: Run tests and verify failure（运行测试并确认失败）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py -k "pytest_xdist_workers or requires_xdist"
```

Expected（预期）: FAIL（失败） because `pytestXdistWorkers`（Pytest 工作进程数） is not implemented.

- [x] **Step 3: Implement workers parsing（实现进程数字段解析）**

In `build_and_verify_runner.py`, add helpers near `uses_pytest_xdist()`:

```python
def _uses_pytest(command: Any) -> bool:
    tokens = _command_tokens(command)
    has_pytest = any(token == "pytest" or token.endswith("/pytest") or token.endswith("\\pytest") for token in tokens)
    has_pytest_module = any(
        token == "-m" and index + 1 < len(tokens) and tokens[index + 1] == "pytest"
        for index, token in enumerate(tokens)
    )
    return has_pytest or has_pytest_module


def _pytest_xdist_workers(value: Any) -> str | None:
    if value is None:
        return None
    if value == "auto":
        return "auto"
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError('pytestXdistWorkers must be "auto" or positive integer')
    return str(value)
```

In `_load_config()`, validate（校验） each check（检查项）:

```python
            try:
                _pytest_xdist_workers(check.get("pytestXdistWorkers"))
            except ConfigError as error:
                raise ConfigError(
                    "invalid_config: .build-and-verify/config.json: "
                    f"{section}.checks[{index}].{error}"
                ) from None
```

- [x] **Step 4: Apply workers to pytest commands（把进程数字段应用到 pytest 命令）**

Add helper near `_dependency_error()`:

```python
def _command_with_pytest_xdist_workers(command: Any, workers: str | None) -> Any:
    if workers is None or not _uses_pytest(command) or uses_pytest_xdist(command):
        return command
    if isinstance(command, list):
        tokens = [str(item) for item in command]
        for index, token in enumerate(tokens):
            if token == "pytest" or token.endswith("/pytest") or token.endswith("\\pytest"):
                return tokens[: index + 1] + ["-n", workers] + tokens[index + 1 :]
            if token == "-m" and index + 1 < len(tokens) and tokens[index + 1] == "pytest":
                insert_at = index + 2
                return tokens[:insert_at] + ["-n", workers] + tokens[insert_at:]
    if isinstance(command, str):
        tokens = _command_tokens(command)
        for index, token in enumerate(tokens):
            if token == "pytest" or token.endswith("/pytest") or token.endswith("\\pytest"):
                tokens = tokens[: index + 1] + ["-n", workers] + tokens[index + 1 :]
                return shlex.join(tokens)
            if token == "-m" and index + 1 < len(tokens) and tokens[index + 1] == "pytest":
                insert_at = index + 2
                tokens = tokens[:insert_at] + ["-n", workers] + tokens[insert_at:]
                return shlex.join(tokens)
    return command
```

Change `_dependency_error(check)` so it requires `pytest-xdist`（Pytest 并行插件） when either old command flags already use xdist or `pytestXdistWorkers`（Pytest 工作进程数） is set on a pytest（Python 测试框架） command:

```python
def _dependency_error(check: dict[str, Any]) -> str | None:
    command = check.get("command")
    workers = _pytest_xdist_workers(check.get("pytestXdistWorkers"))
    needs_xdist = uses_pytest_xdist(command) or (workers is not None and _uses_pytest(command))
    if needs_xdist and importlib.util.find_spec("xdist") is None:
        return (
            f"missing_dependency: {check.get('id')}: pytest-xdist is required "
            "for pytest xdist workers; install requirements-dev.txt\n"
        )
    return None
```

In `_run_check()` and `_run_check_result()`, after dependency check（依赖检查） passes and before `use_shell` is computed, replace:

```python
    command = check.get("command")
```

with:

```python
    command = _command_with_pytest_xdist_workers(
        check.get("command"),
        _pytest_xdist_workers(check.get("pytestXdistWorkers")),
    )
```

- [x] **Step 5: Run focused workers tests（运行聚焦工作进程测试）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py -k "pytest_xdist_workers or requires_xdist or missing_xdist"
```

Expected（预期）: PASS（通过）。

---

### Task 3: Shared Fast/Full Scheduler（快速/完整共用调度器）

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py`

- [x] **Step 1: Add failing fast parallel test（添加快速并行失败测试）**

Add a test near full verify（完整验证） parallel tests:

```python
def test_build_and_verify_runner_fast_verify_runs_check_parallel_cache_misses_concurrently(
    tmp_path: Path, capsys
) -> None:
    import threading
    import time

    module = load_build_and_verify_module()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".build-and-verify").mkdir()
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".build-and-verify" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "fast-a",
                        "command": ["fast-a"],
                        "paths": ["src/**"],
                        "inputs": ["src"],
                        "checkParallel": True,
                    },
                    {
                        "id": "fast-b",
                        "command": ["fast-b"],
                        "paths": ["src/**"],
                        "inputs": ["src"],
                        "checkParallel": True,
                    },
                ]
            },
        },
    )
    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_runner(command, **_kwargs):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.2)
        with lock:
            active -= 1
        return subprocess.CompletedProcess(command, 0, stdout=f"{command[0]}\n", stderr="")

    result = module._runner().run_verify(project, runner=fake_runner, full=False)
    captured = capsys.readouterr()

    assert result == 0
    assert max_active > 1
    assert "checked: fast-a, fast-b" in captured.out
    assert "full-not-run: true" in captured.out
```

- [x] **Step 2: Run test and verify failure（运行测试并确认失败）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_fast_verify_runs_check_parallel_cache_misses_concurrently
```

Expected（预期）: FAIL（失败） because fast（快速） currently runs selected checks（检查项） serially.

- [x] **Step 3: Extract shared scheduler（抽出共用调度器）**

In `build_and_verify_runner.py`, add a helper before `run_verify()`:

```python
def _run_verify_checks(
    project: Path,
    config: dict[str, Any],
    selected: list[dict[str, Any]],
    changed_files: list[str],
    runner: Runner,
    *,
    use_cache: bool,
) -> int:
    failures = 0
    cache_hits: set[str] = set()
    runnable: list[tuple[int, dict[str, Any], str | None]] = []

    for index, check in enumerate(selected):
        try:
            key = _cache_key(project, config, check, changed_files)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            failures += 1
            continue
        if use_cache and _cache_load(project, key):
            print(f"cache-hit: {check.get('id')}")
            cache_hits.add(str(check.get("id")))
            continue
        runnable.append((index, check, key))

    parallel_checks = [(index, check) for index, check, _key in runnable if check.get("checkParallel") is True]
    serial_checks = [(index, check) for index, check, _key in runnable if check.get("checkParallel") is not True]
    results: list[CheckResult] = []

    if parallel_checks:
        max_workers = _max_parallel_checks(config, len(parallel_checks))
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        interrupted = False
        try:
            futures = {
                executor.submit(_run_check_result, index, project, check, config, changed_files, runner): (index, check)
                for index, check in parallel_checks
            }
            for future in futures:
                index, check = futures[future]
                try:
                    results.append(future.result())
                except KeyboardInterrupt as error:
                    interrupted = True
                    results.append(
                        CheckResult(
                            index,
                            check,
                            1,
                            stderr=f"parallel_check_interrupted: {check.get('id')}: KeyboardInterrupt: {error}\n",
                        )
                    )
                    break
        finally:
            executor.shutdown(wait=not interrupted, cancel_futures=interrupted)
        if not interrupted:
            results.extend(
                _run_check_result(index, project, check, config, changed_files, runner)
                for index, check in serial_checks
            )
    else:
        results.extend(
            _run_check_result(index, project, check, config, changed_files, runner)
            for index, check in serial_checks
        )

    failed_ids: list[str] = []
    for result in sorted(results, key=lambda item: item.index):
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
    return 1 if failures else 0
```

Then simplify `run_verify()` after `selected`:

```python
    status = _run_verify_checks(
        project,
        config,
        selected,
        changed_files,
        runner,
        use_cache=not full,
    )
    print(f"checked: {_check_ids(selected)}")
    print(f"full-not-run: {str(not full).lower()}")
    if status:
        print("status: failed")
        return 1
    print("status: passed")
    return 0
```

- [x] **Step 4: Remove old duplicate full-only branch（删除旧的完整验证专用分支）**

Delete the old `if full:` branch and the old serial fast（快速） loop from `run_verify()`. Keep cache（缓存） behavior through `_run_verify_checks(..., use_cache=not full)` only.

- [x] **Step 5: Run scheduler tests（运行调度器测试）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py -k "fast_verify_runs_check_parallel or full_verify_runs_parallel or uses_passed_result_cache or full_verify_ignores_existing_default_cache or full_verify_refreshes_cache"
```

Expected（预期）: PASS（通过）。

---

### Task 4: Init Config Overwrite（初始化覆盖）

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py`

- [x] **Step 1: Add failing init tests（添加初始化失败测试）**

Add tests near existing init（初始化） tests:

```python
def test_build_and_verify_init_writes_confirmed_config_with_overwrite(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    build_dir = project / ".build-and-verify"
    build_dir.mkdir()
    old_config = {
        "version": 1,
        "build": {"checks": [{"id": "build.old", "command": command_that_logs("old")}]},
        "verify": {"checks": []},
    }
    write_json(build_dir / "config.json", old_config)
    (build_dir / ".gitignore").write_text("/cache/\n/custom/\n", encoding="utf-8")
    confirmed = tmp_path / "confirmed.json"
    new_config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {
            "checks": [
                {
                    "id": "verify.new",
                    "command": command_that_logs("new"),
                    "checkParallel": True,
                    "inputs": [],
                }
            ]
        },
    }
    write_json(confirmed, new_config)

    result = run_build_and_verify(
        "init",
        "--project",
        str(project),
        "--config",
        str(confirmed),
        "--overwrite",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert read_json(build_dir / "config.json") == new_config
    backups = list((build_dir / "backups").glob("config-*.json"))
    assert len(backups) == 1
    assert read_json(backups[0]) == old_config
    assert (build_dir / ".gitignore").read_text(encoding="utf-8").splitlines() == [
        "/cache/",
        "/custom/",
        "/runs/",
        "/backups/",
    ]
    assert (build_dir / "runtime" / "build_and_verify.py").is_file()
    assert (build_dir / "runtime" / "build_and_verify_runner.py").is_file()
    assert (build_dir / "runtime" / "version.json").is_file()
    assert (build_dir / "cache").is_dir()
    assert "status: initialized" in result.stdout


def test_build_and_verify_init_writes_confirmed_config_without_existing_config(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    confirmed = tmp_path / "confirmed.json"
    new_config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {"checks": [{"id": "verify.new", "command": command_that_logs("new"), "inputs": []}]},
    }
    write_json(confirmed, new_config)

    result = run_build_and_verify(
        "init",
        "--project",
        str(project),
        "--config",
        str(confirmed),
        "--overwrite",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert read_json(project / ".build-and-verify" / "config.json") == new_config
    assert not (project / ".build-and-verify" / "backups").exists()


def test_build_and_verify_init_config_requires_overwrite_for_existing_config(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_build_and_verify("init", "--project", str(project)).returncode == 0
    confirmed = tmp_path / "confirmed.json"
    write_json(confirmed, {"version": 1, "build": {"checks": []}, "verify": {"checks": []}})

    result = run_build_and_verify("init", "--project", str(project), "--config", str(confirmed))

    assert result.returncode == 1
    assert "existing_file: .build-and-verify/config.json" in result.stderr
```

- [x] **Step 2: Run tests and verify failure（运行测试并确认失败）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py -k "init_writes_confirmed_config or init_config_requires_overwrite"
```

Expected（预期）: FAIL（失败） because `--config`（配置参数） and `--overwrite`（覆盖参数） do not exist.

- [x] **Step 3: Add parser arguments（添加命令参数）**

In `build_and_verify.py`, extend init parser（初始化命令解析）:

```python
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--config")
    init_parser.add_argument("--overwrite", action="store_true")
```

Change main（主入口）:

```python
    if args.command == "init":
        return _init_project(Path(args.project).resolve(), config=Path(args.config).resolve() if args.config else None, overwrite=args.overwrite)
```

- [x] **Step 4: Implement overwrite init（实现覆盖初始化）**

In `build_and_verify.py`, add imports and helpers:

```python
from datetime import datetime
```

```python
def _load_config_file(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"missing_config_file: {path}") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid_config_file: {path}: {error.msg}") from None
    if not isinstance(data, dict):
        raise ValueError(f"invalid_config_file: {path}: root must be object")
    return data


def _merge_gitignore(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for entry in DEFAULT_GITIGNORE.splitlines():
        if entry not in lines:
            lines.append(entry)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _backup_config(config_target: Path, project: Path) -> Path:
    backup_dir = project / ".build-and-verify" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"config-{timestamp}.json"
    shutil.copy2(config_target, backup)
    return backup
```

Change `_init_project()` signature and body:

```python
def _init_project(project: Path, *, config: Path | None = None, overwrite: bool = False) -> int:
    config_target = project / ".build-and-verify" / "config.json"
    gitignore_target = project / ".build-and-verify" / ".gitignore"
    runtime_target = _runtime_target(project)
    confirmed_config = DEFAULT_CONFIG if config is None else _load_config_file(config)

    conflict_targets = [config_target, gitignore_target, runtime_target]
    if not overwrite:
        for target in conflict_targets:
            if target.exists():
                print(f"existing_file: {target.relative_to(project).as_posix()}", file=sys.stderr)
                return 1
    elif config is None:
        for target in conflict_targets:
            if target.exists():
                print(f"existing_file: {target.relative_to(project).as_posix()}", file=sys.stderr)
                return 1

    project.mkdir(parents=True, exist_ok=True)
    config_target.parent.mkdir(parents=True, exist_ok=True)
    backup = _backup_config(config_target, project) if config_target.exists() else None
    _merge_gitignore(gitignore_target)
    config_target.write_text(
        json.dumps(confirmed_config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _copy_runtime(project)
    (project / ".build-and-verify" / "cache").mkdir(parents=True, exist_ok=True)
    if backup is not None:
        print(f"backup: {backup.relative_to(project).as_posix()}")
    print("status: initialized")
    return 0
```

- [x] **Step 5: Preserve old init behavior（保留旧初始化行为）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py -k "init_writes_config_gitignore_and_cache or init_refuses_existing_files_before_writes or init_writes_confirmed_config"
```

Expected（预期）: PASS（通过）。

---

### Task 5: Build and Verify Init Skill（构建与验证初始化技能）文案和依赖检查

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify-init/SKILL.md`
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify-init/references/config-draft.md`
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify-init/references/validation.md`
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify-init/references/questionnaire.md`
- Modify（修改）: `plugins/build-and-verify/skills/build-and-verify-init/references/ecosystem-detection.md`

- [x] **Step 1: Add failing docs tests（添加文案失败测试）**

Update existing tests or add these near init Skill（初始化技能） reference tests:

```python
def test_build_and_verify_init_skill_calls_runtime_init_config_overwrite() -> None:
    skill = (INIT_SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    validation = (INIT_REFERENCE_ROOT / "validation.md").read_text(encoding="utf-8")

    assert "init --config --overwrite" in skill
    assert "init --config --overwrite" in validation
    assert "仍只写空模板" not in skill


def test_build_and_verify_init_references_use_check_parallel_and_pytest_workers() -> None:
    text = "\n".join(
        (INIT_SKILL_ROOT / name).read_text(encoding="utf-8")
        for name in [
            "SKILL.md",
            "references/questionnaire.md",
            "references/ecosystem-detection.md",
            "references/config-draft.md",
            "references/validation.md",
        ]
    )

    assert "checkParallel" in text
    assert "pytestXdistWorkers" in text
    assert "`parallel: true`" not in text
    assert "保留 check id（检查项标识）、command（命令）、paths（受影响路径）、inputs（缓存输入）、parallel" not in text
```

Update `test_build_and_verify_init_template_detects_pytest_xdist_dependency()` to use field-driven config（配置）:

```python
    config = {
        "version": 1,
        "build": {"checks": []},
        "verify": {
            "checks": [
                {
                    "id": "verify.pytest-parallel",
                    "command": "python -m pytest",
                    "pytestXdistWorkers": "auto",
                },
                {"id": "verify.pytest-serial", "command": "python -m pytest"},
            ]
        },
    }
```

- [x] **Step 2: Run docs tests and verify failure（运行文案测试并确认失败）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py -k "init_skill_calls_runtime_init_config_overwrite or init_references_use_check_parallel or template_detects_pytest_xdist_dependency or validates_per_check_runtime_tuning"
```

Expected（预期）: FAIL（失败） because references（参考文档） still use old wording.

- [x] **Step 3: Update Skill hard boundaries（更新技能硬边界）**

In `plugins/build-and-verify/skills/build-and-verify-init/SKILL.md`, replace the old hard boundary:

```markdown
- 不新增命令行初始化脚本；`build-and-verify`（构建与验证）现有 `scripts/build_and_verify.py init`（初始化命令）仍只写空模板。
```

with:

```markdown
- 不新增命令行初始化脚本；最终写入必须调用 `build-and-verify`（构建与验证）现有 `scripts/build_and_verify.py init --config --overwrite`（初始化覆盖命令），由 runtime（运行时）负责配置写入、备份、`.gitignore`（忽略规则）合并、runtime（运行时）复制和 cache（缓存）创建。
```

In Required Flow（必需流程） and Output（输出）, state（说明）:

```markdown
- 最终写入时，先把用户确认的草案保存为临时 confirmed config（已确认配置），再调用 `python <build-and-verify-script> init --project <repo> --config <confirmed-config> --overwrite`（初始化覆盖命令）。不得由 agent（代理）直接写 `.build-and-verify/config.json`（配置文件）。
```

- [x] **Step 4: Update reference rules（更新参考规则）**

In `config-draft.md`:

- Replace preserving `parallel`（旧并行字段） with preserving `checkParallel`（检查项间并行） and `pytestXdistWorkers`（Pytest 工作进程数）.
- Replace runtime tuning bullets with:

```markdown
- `checkParallel: true`（检查项间并行）只能在解释 runner（运行器）并行语义并获得用户确认后写入。
- `pytestXdistWorkers`（Pytest 工作进程数）只能在命令是 pytest（Python 测试框架）命令、解释 pytest-xdist（Pytest 并行插件）依赖并获得用户确认后写入；值只能是 `"auto"`（自动）或正整数。
- `parallel`（旧并行字段）不得写入新草案；已有配置含该字段时，必须提示用户重新确认并迁移为 `checkParallel`（检查项间并行）。
```

In `validation.md`, replace command-based xdist（并行插件） requirement with:

```markdown
- 配置包含 `pytestXdistWorkers`（Pytest 工作进程数）且 command（命令）是 pytest（Python 测试框架）命令时，检查 `pytest-xdist`（Pytest 并行插件）是否可用。
- command（命令）已经包含 `-n` 或 `--numprocesses`（进程数参数）时，也检查 `pytest-xdist`（Pytest 并行插件）是否可用，并建议迁移到 `pytestXdistWorkers`（Pytest 工作进程数）。
- `checkParallel: true`（检查项间并行）只说明 build-and-verify（构建与验证）runner（运行器）支持 check（检查项）间并行，不推断 pytest-xdist（Pytest 并行插件）用法。
```

In `questionnaire.md`, Q5/Q6 must name `checkParallel`（检查项间并行） and `pytestXdistWorkers`（Pytest 工作进程数） instead of `parallel: true`（旧并行写法）.

In `ecosystem-detection.md`, existing config（已有配置） scan must preserve `checkParallel`（检查项间并行） and `pytestXdistWorkers`（Pytest 工作进程数），and report old `parallel`（旧并行字段） as migration needed.

- [x] **Step 5: Update test helper validation（更新测试辅助校验）**

In `tests/test_build_and_verify_plugin.py`, update `init_wizard_targeted_dependency_issues()`:

```python
        workers = check.get("pytestXdistWorkers")
        command_uses_pytest_parallel = init_wizard_uses_pytest_parallel(command)
        command_is_pytest = "pytest" in init_wizard_command_tokens(command)
        if ((workers is not None and command_is_pytest) or command_uses_pytest_parallel) and not xdist_available:
            issues.append(
                init_wizard_issue(
                    f"{check_id} 需要 pytest-xdist（Pytest 并行插件），但当前环境不可用",
                    "该 check（检查项）后续 verify（验证）可能失败。",
                    "请安装 pytest-xdist（Pytest 并行插件），或移除 `pytestXdistWorkers`（Pytest 工作进程数）后再运行。",
                )
            )
```

Update `assert_init_wizard_config_structure()` per-check validation（逐检查项校验）:

```python
            assert "parallel" not in check
            check_parallel = check.get("checkParallel")
            assert check_parallel is None or isinstance(check_parallel, bool)
            workers = check.get("pytestXdistWorkers")
            assert workers is None or workers == "auto" or (
                not isinstance(workers, bool) and isinstance(workers, int) and workers > 0
            )
```

Update `test_build_and_verify_init_template_validates_per_check_runtime_tuning()` parameter（参数） list to cover:

```python
        ("checkParallel", True, True),
        ("checkParallel", False, True),
        ("checkParallel", "true", False),
        ("pytestXdistWorkers", "auto", True),
        ("pytestXdistWorkers", 1, True),
        ("pytestXdistWorkers", 0, False),
        ("pytestXdistWorkers", True, False),
        ("parallel", True, False),
```

- [x] **Step 6: Run Skill docs tests（运行技能文案测试）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py -k "build_and_verify_init"
```

Expected（预期）: PASS（通过）。

---

### Task 6: Current Repository Config and Runtime Snapshot（当前仓库配置与运行时快照）

**Files（文件）:**
- Modify（修改）: `.build-and-verify/config.json`
- Modify（修改）: `.build-and-verify/runtime/build_and_verify.py`
- Modify（修改）: `.build-and-verify/runtime/build_and_verify_runner.py`
- Modify（修改）: `.build-and-verify/runtime/version.json`

- [x] **Step 1: Update only current repo config（只更新当前仓库配置）**

In `.build-and-verify/config.json`, for every current verify check（验证检查项） in `D:\My Project\my-agent-skills`:

Replace:

```json
"parallel": true
```

with:

```json
"checkParallel": true
```

For pytest（Python 测试框架） commands that currently include `-n 8`, remove the `-n 8` tokens from `command`（命令） and add:

```json
"pytestXdistWorkers": 8
```

For pytest（Python 测试框架） commands that currently include `-n auto`, remove the `-n auto` tokens from `command`（命令） and add:

```json
"pytestXdistWorkers": "auto"
```

Example（示例）:

```json
{
  "id": "verify.build-and-verify",
  "checkParallel": true,
  "pytestXdistWorkers": 8,
  "command": "python -m pytest -q -p no:cacheprovider tests/test_build_and_verify_plugin.py"
}
```

Do not add（不要新增） or update（更新） any path under `D:\My Project\Quant-Research-Lab`.

- [x] **Step 2: Refresh only current repo runtime snapshot（只刷新当前仓库运行时快照）**

Run（运行） from `D:\My Project\my-agent-skills`:

```bash
python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py update-runtime --project "D:\My Project\my-agent-skills"
```

Expected（预期）:

```text
status: runtime-updated
```

Verify（验证） only these files changed for runtime（运行时）:

```bash
git diff -- .build-and-verify/runtime/build_and_verify.py .build-and-verify/runtime/build_and_verify_runner.py .build-and-verify/runtime/version.json
```

- [x] **Step 3: Check forbidden repository was not touched（检查禁用仓库未被触碰）**

Run（运行）:

```bash
git diff --name-only -- "D:\My Project\Quant-Research-Lab"
```

Expected（预期）: no output（无输出）. If Git（版本管理） refuses the path because it is outside the repository（仓库）, that is also acceptable and confirms this workflow did not stage or diff that path.

---

### Task 7: Temporary Target Repository End-to-End（临时目标仓库端到端回归）

**Files（文件）:**
- Modify（修改）: `tests/test_build_and_verify_plugin.py`

- [x] **Step 1: Add end-to-end regression（添加端到端回归）**

Add this test near init（初始化） runtime tests:

```python
def test_build_and_verify_init_config_overwrite_e2e_temp_target_repo(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target-repo"
    target.mkdir()
    assert git(target, "init").returncode == 0
    assert git(target, "config", "user.email", "test@example.invalid").returncode == 0
    assert git(target, "config", "user.name", "Test User").returncode == 0
    confirmed = tmp_path / "confirmed.json"
    verify_script = "from pathlib import Path; Path('e2e.log').open('a', encoding='utf-8').write('verify\\n')"
    write_json(
        confirmed,
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "verify.e2e",
                        "command": [sys.executable, "-c", verify_script],
                        "paths": ["src/**"],
                        "inputs": ["src"],
                        "checkParallel": True,
                    }
                ]
            },
        },
    )
    (target / "src").mkdir()
    (target / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    init = run_build_and_verify(
        "init",
        "--project",
        str(target),
        "--config",
        str(confirmed),
        "--overwrite",
    )
    repository_script = target / ".build-and-verify" / "runtime" / "build_and_verify.py"
    fast = subprocess.run(
        [sys.executable, str(repository_script), "verify", "--project", str(target)],
        cwd=target,
        check=False,
        text=True,
        capture_output=True,
    )
    full = subprocess.run(
        [sys.executable, str(repository_script), "verify", "--project", str(target), "--full"],
        cwd=target,
        check=False,
        text=True,
        capture_output=True,
    )

    assert init.returncode == 0, init.stdout + init.stderr
    assert (target / ".build-and-verify" / "config.json").is_file()
    assert (target / ".build-and-verify" / "cache").is_dir()
    assert (target / ".build-and-verify" / "runtime" / "build_and_verify.py").is_file()
    assert fast.returncode == 0, fast.stdout + fast.stderr
    assert "full-not-run: true" in fast.stdout
    assert full.returncode == 0, full.stdout + full.stderr
    assert "full-not-run: false" in full.stdout
    assert (target / "e2e.log").read_text(encoding="utf-8").splitlines() == ["verify", "verify"]
```

- [x] **Step 2: Run end-to-end regression（运行端到端回归）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo
```

Expected（预期）: PASS（通过） after Tasks 1-6.

---

### Task 8: Final Verification（最终验证）

**Files（文件）:**
- Verify（验证） only.

- [x] **Step 1: Run build-and-verify plugin tests（运行构建与验证插件测试）**

Run（运行）:

```bash
python -m pytest -q tests/test_build_and_verify_plugin.py
```

Expected（预期）: PASS（通过）.

- [x] **Step 2: Run OpenSpec strict validation（运行开放规格严格校验）**

Run（运行）:

```bash
openspec validate fix-build-and-verify-init-parallel-runtime --strict --no-interactive
```

Expected（预期）: PASS（通过）. If local OpenSpec（开放规格） only supports all-spec validation（全量规格校验）, run:

```bash
openspec validate --all --strict --no-interactive
```

- [x] **Step 3: Run repository fast verification（运行仓库快速验证）**

Run（运行）:

```bash
python .build-and-verify/runtime/build_and_verify.py verify --project "D:\My Project\my-agent-skills"
```

Expected（预期）: `status: passed`.

- [x] **Step 4: Run repository full verification（运行仓库完整验证）**

Run（运行）:

```bash
python .build-and-verify/runtime/build_and_verify.py verify --project "D:\My Project\my-agent-skills" --full
```

Expected（预期）: `status: passed`.

- [x] **Step 5: Confirm scope（确认范围）**

Run（运行）:

```bash
git diff --name-only
```

Expected（预期）: changed files are limited to the File Map（文件地图） above, plus no path under `D:\My Project\Quant-Research-Lab`.

---

## Self Review（自查）

- Spec coverage（规格覆盖）: runner（运行器）配置校验、`checkParallel`（检查项间并行）、`pytestXdistWorkers`（Pytest 工作进程数）、fast/full（快速/完整）共用调度器、`init --config --overwrite`（初始化覆盖命令）、Skill（技能）文案和依赖检查、当前仓库 config/runtime（配置/运行时）快照、临时目标仓库端到端回归、fast/full（快速/完整）验证都已落到任务。
- Placeholder scan（占位扫描）: 本计划不使用 TBD（待定）、TODO（待办）、implement later（稍后实现）或 “similar to”（类似于）步骤。
- Scope guard（范围守卫）: 本计划只允许修改 `D:\My Project\my-agent-skills`，并明确禁止写入或初始化 `D:\My Project\Quant-Research-Lab`。
