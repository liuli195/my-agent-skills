---
change: stabilize-cross-agent-review-evidence
design-doc: docs/superpowers/specs/2026-07-10-cross-agent-review-evidence-design.md
base-ref: 41f635b98ee2c4db0e06bfff658c4379cae49adc
---

# Cross Agent Review（跨代理审查）稳定化与通用证据写入实施计划

> **For agentic workers（给代理执行者）：** REQUIRED SUB-SKILL（必需子技能）：使用 `superpowers:subagent-driven-development`（超级能力子代理驱动开发，推荐）或 `superpowers:executing-plans`（超级能力执行计划）逐项实施。所有步骤使用 checkbox（复选框）跟踪。

**Goal（目标）：** 在不修改 Comet（双星工作流）内部的前提下，降低跨代理审查噪音、保存逐角色结果、严格复用机械变化，并把通过证据写入统一迁移到 Agent Guard（代理守卫）的通用入口。

**Architecture（架构）：** Cross Agent Review（跨代理审查）继续使用现有单脚本和提示词模板，在其中增加文件投影、原子状态、独立并发角色、`retry`（重试）与 `revalidate`（重新校验）。Agent Guard（代理守卫）复用现有 `artifacts.yaml`（产物注册文件）加载、模板渲染和安全路径解析，在现有 Runtime CLI（运行时命令行）增加 `record-evidence`（记录证据），不新增运行时模块或证据版本。

**Tech Stack（技术栈）：** Python 3（脚本语言）、标准库 `argparse/json/hashlib/tempfile/os/concurrent.futures/subprocess`、Git（版本控制）、现有 PyYAML（配置解析）、pytest（测试框架）、OpenSpec（开放规格）、Build and Verify（构建与验证）。

## Global Constraints（全局约束）

- 不修改 `C:\Users\liuli\.codex\skills\comet` 或仓库内任何 Comet（双星工作流）技能、阶段脚本和推进逻辑。
- 不按扩展名、文件大小、目录或 Comet（双星工作流）名称隐式过滤审查文件；未分类文件默认 `full_review`（完整审查）。
- Cross Agent Review（跨代理审查）只输出事实，不解析 finding（发现项）决定通过，也不包含 Agent Guard（代理守卫）画像、产物、路径或证据字段知识。
- Agent Guard（代理守卫）只在主代理显式调用时机械写入 `owner: agent-guard`（代理守卫拥有）的 JSON（数据）产物；不得自主作出通过结论。
- 保持完整 `HEAD`（提交头）、12 位短提交目录和 `guard-evidence/v1`（守卫证据第一版）。
- 只支持 `checkbox-only`（仅复选框）和 `mapping-fields-only`（仅映射字段），禁止链式复用。
- 不新增第三方依赖、运行时模块、数据库、配置框架或证据版本。
- 所有实现按 TDD（测试驱动开发）先红后绿；提交步骤只有在用户另行明确授权 Git commit（版本提交）后才能执行，否则记录 `commit_skipped_not_authorized`。

---

### Task 1: 文件投影与原子状态基础

**Files（文件）：**
- Modify（修改）：`plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py:18-247`
- Test（测试）：`tests/test_cross_agent_review_cli.py`

**Interfaces（接口）：**
- Consumes（输入）：现有 `ReviewInput`（审查输入）、`git_output_bytes()`、`write_review_input()` 测试助手。
- Produces（输出）：`SummaryOnly`、`RevalidationPolicy`、扩展后的 `ReviewInput`、`changed_file_entries()`、`classify_files()`、`initial_review_state()`、`atomic_write_json()`。

- [x] **Step 1: 写输入分类失败测试**

在 `tests/test_cross_agent_review_cli.py` 增加精确用例，使用现有 `payload_overrides`：

```python
def test_review_input_classifies_context_summary_and_default_full(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)
    base = git(project, "rev-parse", "HEAD")
    write_file(project / "spec.md", "spec body\n")
    write_file(project / "design.md", "design body\n")
    write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    write_file(project / "src" / "app.py", "print('ok')\n")
    write_file(project / "docs" / "process.md", "generated plan\n")
    git(project, "add", ".")
    git(project, "commit", "-m", "review subject")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(
        project,
        base,
        head,
        payload_overrides={
            "summary_only": [
                {"path": "docs/process.md", "reason": "过程文档仅供按需核对"}
            ]
        },
    )

    module = load_script_module()
    review_input = module.load_review_input(argparse.Namespace(input_file=input_file, debug=False, sdk_python=None))
    state = module.initial_review_state(review_input)

    by_path = {item["path"]: item for item in state["files"]}
    assert by_path["spec.md"]["classification"] == "authoritative_context"
    assert by_path["spec.md"]["reason"] is None
    assert by_path["src/app.py"]["classification"] == "full_review"
    assert by_path["docs/process.md"]["classification"] == "summary_only"
    assert by_path["docs/process.md"]["reason"] == "过程文档仅供按需核对"
    assert "spec.md" in state["roles"]["spec-alignment"]["scope"]["authoritative_context"]
```

同时参数化以下拒绝：重复路径、空理由、绝对路径、`..`、非变更路径、权威上下文与 `summary_only`（仅摘要）重叠。

- [x] **Step 2: 运行分类测试并确认失败**

Run（运行）：

```powershell
python -m pytest -q -p no:cacheprovider tests/test_cross_agent_review_cli.py -k "classifies_context_summary or summary_only_rejects"
```

Expected（预期）：FAIL（失败），提示 `initial_review_state` 或新输入字段尚不存在。

- [x] **Step 3: 实现最小输入与分类函数**

在现有脚本中增加以下结构和函数；路径只做精确匹配：

```python
@dataclass(frozen=True)
class SummaryOnly:
    path: str
    reason: str


@dataclass(frozen=True)
class RevalidationPolicy:
    path: str
    validator: str
    format: str | None = None
    fields: tuple[str, ...] = ()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def project_relative_path(raw: str, project: Path) -> str:
    path = Path(raw)
    windows = PureWindowsPath(raw)
    if path.is_absolute() or windows.is_absolute() or windows.drive or windows.root:
        raise ValueError(f"path_outside_project: {raw}")
    resolved = (project / path).resolve()
    try:
        relative = resolved.relative_to(project.resolve())
    except ValueError as exc:
        raise ValueError(f"path_outside_project: {raw}") from exc
    return relative.as_posix()


def classify_files(review_input: ReviewInput, entries: list[dict]) -> list[dict]:
    contexts = {
        review_input.spec_file.resolve().relative_to(Path.cwd().resolve()).as_posix(),
        review_input.design_file.resolve().relative_to(Path.cwd().resolve()).as_posix(),
        review_input.plan_file.resolve().relative_to(Path.cwd().resolve()).as_posix(),
    }
    summaries = {item.path: item.reason for item in review_input.summary_only}
    changed = {item["path"] for item in entries}
    unknown = sorted(set(summaries) - changed)
    if unknown:
        raise ValueError(f"invalid_summary_only: not_changed={','.join(unknown)}")
    if contexts & set(summaries):
        raise ValueError("classification_overlap")
    return [
        {
            **entry,
            "classification": (
                "authoritative_context"
                if entry["path"] in contexts
                else "summary_only"
                if entry["path"] in summaries
                else "full_review"
            ),
            "reason": summaries.get(entry["path"]),
        }
        for entry in entries
    ]
```

扩展 `load_review_input()` 严格解析数组、拒绝重复，并用 `git diff --name-status -z --find-renames --find-copies-harder` 构建 entry（条目）。

- [x] **Step 4: 增加原子状态测试并确认失败**

```python
def test_initial_state_records_subject_context_hashes_and_role_scopes(tmp_path: Path) -> None:
    project, base, head, input_file = committed_review_subject(tmp_path)
    module = load_script_module()
    review_input = module.load_review_input(argparse.Namespace(input_file=input_file, debug=False, sdk_python=None))

    state = module.initial_review_state(review_input)
    module.atomic_write_json(review_input.output_dir / "review-state.json", state)
    saved = json.loads((review_input.output_dir / "review-state.json").read_text(encoding="utf-8"))

    assert saved["schema_version"] == "cross-agent-review-state/v1"
    assert saved["subject"]["input_hash"].startswith("sha256:")
    assert set(saved["subject"]["contexts"]) == {"spec", "design", "plan"}
    assert saved["roles"]["spec-alignment"]["attempts"] == []
    assert "status" not in saved["roles"]["spec-alignment"]
```

- [x] **Step 5: 实现状态初始化和原子写入**

```python
def atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)
```

`initial_review_state()` 写入 schema、subject、三份 context hash（上下文哈希）、分类清单和两个角色 scope（范围），不写未完成状态。

同时把 `output_dir / "review-state.json"` 加入现有 `runtime_allowed_paths()`；这样首次状态写入后，派发前第二次 clean-worktree（干净工作区）检查仍只放行本次输入、报告、状态和 debug（调试）产物，不放行其他变更。

- [x] **Step 6: 运行 Task 1 定向测试**

Run（运行）：

```powershell
python -m pytest -q -p no:cacheprovider tests/test_cross_agent_review_cli.py -k "summary_only or initial_state or classification"
```

Expected（预期）：PASS（通过）。

- [x] **Step 7: 提交 Task 1 检查点（仅获授权时）**

```powershell
git add plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py tests/test_cross_agent_review_cli.py
git commit -m "实现跨代理审查输入投影和状态基础"
```

没有当前明确提交授权时不运行，记录 `commit_skipped_not_authorized`。

### Task 2: 角色限定输入与逐角色持久化

**Files（文件）：**
- Modify（修改）：`plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py:315-563`
- Modify（修改）：`plugins/cross-agent-review/skills/cross-agent-review/assets/templates/reviewer-prompt.md`
- Test（测试）：`tests/test_cross_agent_review_cli.py`

**Interfaces（接口）：**
- Consumes（输入）：Task 1 的 `initial_review_state()`、`atomic_write_json()` 和角色 scope（范围）。
- Produces（输出）：`render_role_input()`、`run_sdk_role_subprocess()`、`dispatch_roles()`、`record_role_result()`。

- [x] **Step 1: 写 role-input（角色输入）范围测试**

```python
def test_role_input_contains_only_full_review_diff_and_summary_stats(tmp_path: Path, capsys) -> None:
    project, input_file = review_subject_with_full_and_summary_files(tmp_path)
    module = load_script_module()
    with contextlib.chdir(project):
        assert module.main(["_role-input", "--input-file", str(input_file), "--role", "implementation-correctness"]) == 0
    output = capsys.readouterr().out
    assert "+print('behavior')" in output
    assert "generated process body" not in output
    assert "docs/process.md" in output
    assert "过程文档仅供按需核对" in output
```

更新 prompt（提示词）测试，断言不存在无路径 `git diff <base>...<head>`，存在 `_role-input` 命令、input path（输入路径）和 state path（状态路径）。

- [x] **Step 2: 运行新测试并确认失败**

Run（运行）：

```powershell
python -m pytest -q -p no:cacheprovider tests/test_cross_agent_review_cli.py -k "role_input or reviewer_prompt"
```

Expected（预期）：FAIL（失败），旧 prompt（提示词）仍包含完整差异命令。

- [x] **Step 3: 实现内部 role-input（角色输入）命令**

```python
def render_role_input(review_input: ReviewInput, state: dict, role: str) -> str:
    role_state = state["roles"][role]
    full_paths = role_state["scope"]["full_review"]
    sections = [render_context_index(state), render_summary_stats(review_input, state)]
    if full_paths:
        sections.append(git_output(["diff", f"{review_input.base_ref}...{review_input.head_ref}", "--", *full_paths], Path.cwd()))
    return "\n\n".join(part for part in sections if part).rstrip() + "\n"
```

`_role-input` 必须重新校验 input hash（输入哈希）、state subject（状态对象）和完整 `HEAD`（提交头）；不接受任意 path 参数（路径参数）。模板只渲染 role、input path、state path、role-input command、role focus 和 severity rubric。

- [x] **Step 4: 写逐角色完成与超时测试**

```python
def test_completed_role_is_saved_before_sibling_timeout(tmp_path: Path, monkeypatch) -> None:
    project, input_file = committed_review_input(tmp_path)
    module = load_script_module()

    def fake_role(_review_input, _python, role):
        if role == "spec-alignment":
            return "completed", "# Review Result\n## Findings\nNone\n"
        failure = module.reviewer_failure(role, "Reviewer timed out", "Exceeded 480 seconds.", "Retry")
        return "timed_out", failure["text"]

    monkeypatch.setattr(module, "run_sdk_role_subprocess", fake_role)
    result = run(*review_args_from_input(input_file), cwd=project)
    state = json.loads((input_file.parent.parent / "review-state.json").read_text(encoding="utf-8"))

    assert result.returncode == 0
    assert state["roles"]["spec-alignment"]["status"] == "completed"
    assert state["roles"]["implementation-correctness"]["status"] == "timed_out"
```

- [x] **Step 5: 实现独立并发派发与状态归并**

先扩展内部 `_sdk-dispatch`（开发包内部派发）结果契约，使执行状态与 Markdown（标记文本）分离：

```python
def markdown_review(role: str, text: str, execution_status: str = "completed") -> dict:
    return {
        "role": role,
        "execution_status": execution_status,
        "text": text.strip() + "\n",
    }
```

`query_one()` 非空结果返回 `completed`（完成）；空结果和 SDK（开发包）异常返回 `failed`（失败）；`asyncio.TimeoutError` 返回 `timed_out`（超时）。外层 540 秒超时也为每个未返回角色生成 `execution_status: timed_out`，不得只靠 CRITICAL（严重阻断）文本反推状态。

```python
def dispatch_roles(review_input: ReviewInput, sdk_python: str, state: dict, roles: Sequence[str]) -> dict:
    state_path = review_input.output_dir / "review-state.json"
    with ThreadPoolExecutor(max_workers=len(roles)) as executor:
        futures = {
            executor.submit(run_sdk_role_subprocess, review_input, sdk_python, role): role
            for role in roles
        }
        for future in as_completed(futures):
            role = futures[future]
            try:
                status, output = future.result()
            except Exception as error:
                status = "failed"
                failure = reviewer_failure(role, "Reviewer SDK dispatch failed", f"{type(error).__name__}: {error}", "Retry")
                output = failure["text"]
            record_role_result(state, role, status, output)
            atomic_write_json(state_path, state)
    return state
```

`run_sdk_role_subprocess()` 复用现有 `_sdk-dispatch`（开发包内部派发），但 payload（载荷）只含一个角色；它严格要求返回对象的 `role` 与请求角色一致，且 `execution_status` 属于 `completed/failed/timed_out`（完成/失败/超时），否则映射为 `failed`（失败）。保留 480/540 秒边界。`record_role_result()` 追加 attempt（尝试），保存 Markdown（标记文本）原文和 SHA-256（安全哈希）。

补四个经过真实 `run_sdk_dispatch()`（开发包内部派发）路径的测试：非空结果为 `completed`（完成）、空结果为 `failed`（失败）、query（查询）抛异常为 `failed`（失败）、480 秒等待超时为 `timed_out`（超时）。测试通过替换 `claude_agent_sdk.query`（开发包查询）和 `asyncio.wait_for`（异步等待）触发路径，不直接伪造父进程状态。

另补父进程 future（异步结果）直接抛异常的测试，断言对应角色 `status == "failed"`、`output` 是 Markdown（标记文本）字符串，且 `output_hash == sha256_bytes(output.encode("utf-8"))`；不得把 `reviewer_failure()` 返回的数据对象直接写入状态。

- [x] **Step 6: 从状态生成报告并运行 Task 2 测试**

`render_report()` 改为读取 state（状态）的两个角色输出；报告写完后计算文件字节哈希并再次原子更新 state（状态）。

Run（运行）：

```powershell
python -m pytest -q -p no:cacheprovider tests/test_cross_agent_review_cli.py -k "role_input or reviewer_prompt or completed_role_is_saved or sdk_dispatch"
```

Expected（预期）：PASS（通过）。

- [x] **Step 7: 提交 Task 2 检查点（仅获授权时）**

```powershell
git add plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py plugins/cross-agent-review/skills/cross-agent-review/assets/templates/reviewer-prompt.md tests/test_cross_agent_review_cli.py
git commit -m "保存跨代理审查逐角色结果"
```

### Task 3: 失败角色 retry（重试）

**Files（文件）：**
- Modify（修改）：`plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- Test（测试）：`tests/test_cross_agent_review_cli.py`

**Interfaces（接口）：**
- Consumes（输入）：Task 2 的 `dispatch_roles()` 和状态格式。
- Produces（输出）：`retryable_roles()`、`run_retry()` 和 `retry`（重试）CLI（命令行）入口。

- [x] **Step 1: 写只重试失败角色测试**

```python
def test_retry_dispatches_only_failed_role_and_preserves_success(tmp_path: Path, monkeypatch) -> None:
    project, input_file, original_state = review_state_with_one_timeout(tmp_path)
    module = load_script_module()
    calls: list[list[str]] = []

    def fake_dispatch(review_input, sdk_python, state, roles):
        calls.append(list(roles))
        module.record_role_result(state, roles[0], "completed", "# Review Result\n## Findings\nNone\n")
        module.atomic_write_json(review_input.output_dir / "review-state.json", state)
        return state

    monkeypatch.setattr(module, "dispatch_roles", fake_dispatch)
    result = run("retry", "--input-file", str(input_file), cwd=project)
    state = json.loads((input_file.parent.parent / "review-state.json").read_text(encoding="utf-8"))

    assert result.returncode == 0
    assert calls == [["implementation-correctness"]]
    assert state["roles"]["spec-alignment"] == original_state["roles"]["spec-alignment"]
    assert len(state["roles"]["implementation-correctness"]["attempts"]) == 2
```

另加两个成功角色返回 `no_retryable_roles` 且 dispatch（派发）未调用的测试。

- [x] **Step 2: 运行 Task 3 测试并确认失败**

```powershell
python -m pytest -q -p no:cacheprovider tests/test_cross_agent_review_cli.py -k "retry_dispatches or no_retryable_roles"
```

Expected（预期）：FAIL（失败），`retry`（重试）子命令不存在。

- [x] **Step 3: 实现最小 retry（重试）入口**

```python
def retryable_roles(state: dict) -> list[str]:
    return [
        role
        for role in REVIEWER_ROLES
        if state["roles"][role].get("status") in {"failed", "timed_out"}
    ]


def run_retry(args: argparse.Namespace) -> int:
    review_input = load_review_input(args)
    ensure_clean_subject(Path.cwd(), review_input.head_ref, runtime_allowed_paths(review_input))
    state = load_bound_state(review_input)
    roles = retryable_roles(state)
    if not roles:
        print("status: no_retryable_roles")
        return 1
    sdk_python = resolve_sdk_python(review_input.sdk_python, require_real_sdk=True)
    dispatch_roles(review_input, sdk_python, state, roles)
    write_report_from_state(review_input, state)
    return 0
```

parser（参数解析器）复用 `run`（运行）的 `--input-file/--debug/--sdk-python` 参数，不添加路径缩放参数；scope（范围）只从原状态读取。

- [x] **Step 4: 运行 retry（重试）与完整 Cross Agent Review（跨代理审查）测试**

```powershell
python -m pytest -q -p no:cacheprovider tests/test_cross_agent_review_cli.py
```

Expected（预期）：PASS（通过）。

- [x] **Step 5: 提交 Task 3 检查点（仅获授权时）**

```powershell
git add plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py tests/test_cross_agent_review_cli.py
git commit -m "支持只重试失败审查角色"
```

### Task 4: 严格 revalidate（重新校验）

**Files（文件）：**
- Modify（修改）：`plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- Test（测试）：`tests/test_cross_agent_review_cli.py`

**Interfaces（接口）：**
- Consumes（输入）：Task 1 的策略、Task 2 的状态与报告哈希。
- Produces（输出）：`validate_checkbox_only()`、`validate_mapping_fields_only()`、`validate_reuse_source()`、`run_revalidate()`。

- [x] **Step 1: 写两个允许校验器的失败测试**

```python
@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("- [ ] one\n- [x] two\n", "- [x] one\n- [x] two\n"),
        ("* [X] one\n", "* [ ] one\n"),
    ],
)
def test_checkbox_only_accepts_only_checkbox_state(before: str, after: str) -> None:
    module = load_script_module()
    assert module.validate_checkbox_only(before.encode(), after.encode()) is None


def test_mapping_fields_only_accepts_declared_yaml_field() -> None:
    module = load_script_module()
    before = b"phase: build\nname: demo\n"
    after = b"phase: verify\nname: demo\n"
    assert module.validate_mapping_fields_only(before, after, "yaml", ("phase",)) is None
```

- [x] **Step 2: 写拒绝矩阵测试**

参数化验证：普通文字变化、行数变化、未声明映射字段、YAML（配置）重复键、非映射、未知格式、未声明文件、策略重叠、A/D/R/C/T/U 状态、规格变化、设计变化、脏工作区、input/report/output hash（输入/报告/输出哈希）不匹配、上一角色 `reused`（复用）。每个用例断言稳定 reason token（原因标识）。

- [x] **Step 3: 运行校验器测试并确认失败**

```powershell
python -m pytest -q -p no:cacheprovider tests/test_cross_agent_review_cli.py -k "checkbox_only or mapping_fields_only or revalidate_rejects"
```

Expected（预期）：FAIL（失败），校验器不存在。

- [x] **Step 4: 实现两个纯校验器**

```python
CHECKBOX = re.compile(r"^(?P<prefix>\s*[-*+]\s+\[)[ xX](?P<suffix>\].*)$")


def validate_checkbox_only(before: bytes, after: bytes) -> str | None:
    try:
        before_lines = before.decode("utf-8").splitlines(keepends=True)
        after_lines = after.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return "checkbox_not_utf8"
    if len(before_lines) != len(after_lines):
        return "checkbox_line_count_changed"
    normalize = lambda line: CHECKBOX.sub(r"\g<prefix> \g<suffix>", line)
    return None if [normalize(x) for x in before_lines] == [normalize(x) for x in after_lines] else "checkbox_content_changed"


def validate_mapping_fields_only(before: bytes, after: bytes, format_name: str, fields: tuple[str, ...]) -> str | None:
    before_map = parse_declared_mapping(before, format_name)
    after_map = parse_declared_mapping(after, format_name)
    changed = {key for key in set(before_map) | set(after_map) if before_map.get(key, MISSING) != after_map.get(key, MISSING)}
    if not changed <= set(fields):
        return "mapping_undeclared_field_changed"
    reduced_before = {key: value for key, value in before_map.items() if key not in fields}
    reduced_after = {key: value for key, value in after_map.items() if key not in fields}
    return None if reduced_before == reduced_after else "mapping_structure_changed"
```

YAML（配置）使用 `yaml.SafeLoader` 的自定义 mapping constructor（映射构造器）拒绝重复键；不执行任意 tag（标签）或脚本。

- [x] **Step 5: 实现复用来源校验和当前提交输出**

```python
def run_revalidate(args: argparse.Namespace) -> int:
    current = load_review_input(args)
    ensure_clean_subject(Path.cwd(), current.head_ref, runtime_allowed_paths(current))
    previous_state = load_previous_state(args.previous_state)
    validate_reuse_source(current, previous_state)
    changes = incremental_changes(previous_state["subject"]["head_ref"], current.head_ref)
    validations = validate_declared_changes(current, changes)
    state = reused_state(current, previous_state, validations)
    atomic_write_json(current.output_dir / "review-state.json", state)
    write_report_from_state(current, state)
    print("status: review_revalidated")
    return 0
```

`git show <ref>:<path>` 读取 blob（文件版本），不 checkout（签出）。任一拒绝返回非零且不调用 `resolve_sdk_python()` 或 dispatch（派发）。

- [x] **Step 6: 运行 revalidate（重新校验）和全部 Cross Agent Review（跨代理审查）测试**

```powershell
python -m pytest -q -p no:cacheprovider tests/test_cross_agent_review_cli.py tests/test_cross_agent_review_plugin_package.py
```

Expected（预期）：PASS（通过）。

- [x] **Step 7: 提交 Task 4 检查点（仅获授权时）**

```powershell
git add plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py tests/test_cross_agent_review_cli.py
git commit -m "支持机械变化重新校验"
```

### Task 5: 共享 Agent Guard（代理守卫）产物契约

**Files（文件）：**
- Modify（修改）：`plugins/agent-guard/scripts/guard_runtime/global_command_guards.py:98-265`
- Modify（修改）：`plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py:408-425`
- Test（测试）：`tests/test_agent_guard_runtime_router.py`
- Test（测试）：`tests/test_validate_guard_profile.py`

**Interfaces（接口）：**
- Consumes（输入）：现有 `render_template()`、`_resolve_artifact_path()`、`_load_profile_artifacts()`。
- Produces（输出）：公开的 `resolve_artifact_path()`、`load_profile_artifacts()`，以及 guard-defined artifact（守卫定义产物）静态校验。

- [x] **Step 1: 写完整产物声明加载测试**

```python
def test_load_profile_artifacts_preserves_owner_type_and_path(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    profile.mkdir()
    write_cross_agent_review_artifacts(profile)
    module = load_global_command_guards_module()

    artifacts = module.load_profile_artifacts(profile)

    assert artifacts["cross_agent_review_pass"] == {
        "id": "cross_agent_review_pass",
        "type": "json",
        "owner": "agent-guard",
        "required_for": ["produce_cross_agent_review_pass_marker"],
        "path": ".local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json",
        "reuse_policy": "deny",
    }
```

- [x] **Step 2: 写 Guard Profile（守卫画像）校验测试**

增加用例：`owner: agent-guard` + 非 JSON（数据）失败；缺失标准路径变量失败；标准声明通过；`owner: guard`（守卫拥有）的现有 minimal（最小）模板继续通过。

- [x] **Step 3: 运行 Task 5 测试并确认失败**

```powershell
python -m pytest -q -p no:cacheprovider tests/test_agent_guard_runtime_router.py tests/test_validate_guard_profile.py -k "load_profile_artifacts or guard_defined"
```

Expected（预期）：FAIL（失败），加载器仍只返回路径。

- [x] **Step 4: 提升现有函数而不新增模块**

```python
def load_profile_artifacts(profile_dir: Path) -> dict[str, dict[str, Any]]:
    artifacts_path = profile_dir / "artifacts.yaml"
    data = yaml.safe_load(artifacts_path.read_text(encoding="utf-8")) or {}
    items = data.get("artifacts") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            continue
        artifact_id = item["id"]
        if artifact_id in result:
            raise ValueError(f"artifact_id_duplicate: {artifact_id}")
        result[artifact_id] = dict(item)
    return result


def resolve_artifact_path(project: Path, user_home: Path, runtime_scope: str, rendered: str) -> Path:
    path = Path(rendered)
    windows_path = PureWindowsPath(rendered)
    if path.is_absolute() or windows_path.is_absolute() or windows_path.drive or windows_path.root:
        raise UnsafeEvidencePath("unsafe_evidence_path")
    base = project if runtime_scope == "project" else (user_home / ".agents" / "guard")
    candidate = (base / path).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise UnsafeEvidencePath("unsafe_evidence_path") from exc
    return candidate
```

把 Global Command Guard（全局命令守卫点）现有读取改为 `artifacts[id]["path"]`；不要保留第二份 path-only loader（仅路径加载器）。

在 `evaluate_global_command_guards()`（评估全局命令守卫）加载注册文件处捕获 `OSError`、`yaml.YAMLError` 和 `ValueError`，把缺失或非法注册表转换为 deny（拒绝）详情 `artifact_registry_invalid`，避免 hook router（钩子路由器）异常退出。增加重复 artifact id（产物编号）与非法 YAML（配置）均稳定拒绝的测试。

- [x] **Step 5: 增加 guard-defined artifact（守卫定义产物）校验**

在 `validate_artifact_contract()` 中，当 `owner == "agent-guard"` 时要求：

```python
DEFAULT_GUARD_EVIDENCE_PATH = ".local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json"

if artifact.get("owner") == "agent-guard":
    if artifact.get("type") != "json":
        issues.append(ValidationIssue("artifacts", f"artifacts.{artifact_id}.type", "必须是 `json`。", "改为 `type: json`。"))
    if artifact.get("path") != DEFAULT_GUARD_EVIDENCE_PATH:
        issues.append(ValidationIssue("artifacts", f"artifacts.{artifact_id}.path", "必须使用 guard-defined evidence 默认路径。", f"改为 `{DEFAULT_GUARD_EVIDENCE_PATH}`。"))
```

- [x] **Step 6: 运行 Agent Guard（代理守卫）读取与校验测试**

```powershell
python -m pytest -q -p no:cacheprovider tests/test_agent_guard_runtime_router.py tests/test_validate_guard_profile.py
```

Expected（预期）：PASS（通过）。

- [x] **Step 7: 提交 Task 5 检查点（仅获授权时）**

```powershell
git add plugins/agent-guard/scripts/guard_runtime/global_command_guards.py plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py tests/test_agent_guard_runtime_router.py tests/test_validate_guard_profile.py
git commit -m "统一代理守卫产物注册契约"
```

### Task 6: 通用 record-evidence（记录证据）

**Files（文件）：**
- Modify（修改）：`plugins/agent-guard/scripts/guard_runtime/cli.py:1-158`
- Modify（修改）：`plugins/agent-guard/skills/agent-guard-run/SKILL.md`
- Modify（修改）：`plugins/agent-guard/skills/agent-guard-run/references/events.md`
- Test（测试）：`tests/test_agent_guard_plugin_runtime_e2e.py`
- Test（测试）：`tests/test_agent_guard_skill_entrypoints.py`

**Interfaces（接口）：**
- Consumes（输入）：Task 5 的 `load_profile_artifacts()`、`render_template()`、`resolve_artifact_path()`；现有 `profile_dir()`、`now_iso()`、`print_json()`。
- Produces（输出）：`RESERVED_EVIDENCE_FIELDS`、`safe_segment()`、`git_head_and_clean()`、`atomic_write_evidence()`、`record_evidence()`、CLI（命令行）子命令。

- [ ] **Step 1: 写成功入口端到端失败测试**

```python
def test_record_evidence_writes_current_head_guard_owned_artifact(tmp_path: Path) -> None:
    project = init_git_project(tmp_path / "project")
    user_home = tmp_path / "home"
    profile = user_home / ".agents" / "guards" / "demo-gate"
    profile.mkdir(parents=True)
    write_guard_defined_artifact(profile, "review_pass")
    fields = write_payload(tmp_path / "fields.json", {"blocking_findings": 0, "report": "inline:review"})

    result = run([
        str(RUNTIME_CLI), "record-evidence",
        "--project", str(project),
        "--user-home", str(user_home),
        "--profile-source", "user",
        "--profile", "demo-gate",
        "--artifact", "review_pass",
        "--subject-type", "change",
        "--subject-id", "demo",
        "--producer", "reviewer",
        "--business-fields-file", str(fields),
    ])

    assert result.returncode == 0, result.stdout + result.stderr
    body = output_json(result)
    evidence = json.loads((project / body["path"]).read_text(encoding="utf-8"))
    assert evidence["schema_version"] == "guard-evidence/v1"
    assert evidence["head_ref"] == git(project, "rev-parse", "HEAD")
    assert evidence["blocking_findings"] == 0
```

- [ ] **Step 2: 写安全拒绝矩阵**

参数化：未知画像、另一个 source scope（来源范围）才存在、未知产物、`owner != agent-guard`、`type != json`、绝对路径、Windows drive path（驱动器路径）、`..` 逃逸、缺失变量、非 Git（版本控制）仓库、脏工作区、非法 JSON（数据）、非对象、十个保留字段冲突、包含斜杠的 profile/artifact/subject（画像/产物/对象）编号。

- [ ] **Step 3: 运行入口测试并确认失败**

```powershell
python -m pytest -q -p no:cacheprovider tests/test_agent_guard_plugin_runtime_e2e.py -k "record_evidence"
```

Expected（预期）：FAIL（失败），CLI（命令行）没有 `record-evidence`（记录证据）。

- [ ] **Step 4: 实现标准字段、仓库校验和原子写入**

```python
RESERVED_EVIDENCE_FIELDS = {
    "schema_version", "status", "producer", "profile_id", "artifact_id",
    "subject_type", "subject_id", "head_ref", "head_ref_short", "created_at",
}


def git_head_and_clean(project: Path) -> str:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, capture_output=True, check=False)
    if head.returncode != 0 or not head.stdout.strip():
        raise ValueError("git_repository_required")
    status = subprocess.run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=project, capture_output=True, check=False)
    if status.returncode != 0:
        raise ValueError("git_status_failed")
    if status.stdout:
        raise ValueError("dirty_worktree")
    return head.stdout.strip()


def atomic_write_evidence(path: Path, body: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(body, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)
```

- [ ] **Step 5: 实现 record_evidence（记录证据）**

```python
def record_evidence(args: argparse.Namespace) -> int:
    project = args.project.resolve()
    user_home = args.user_home.resolve()
    for value in (args.profile, args.artifact, args.subject_id):
        safe_segment(value)
    profile = profile_dir(project, args.profile, user_home, args.profile_source)
    if not profile.is_dir():
        raise ValueError("profile_not_found")
    registry = profile / "artifacts.yaml"
    if not registry.is_file():
        raise ValueError("artifact_registry_missing")
    try:
        artifacts = load_profile_artifacts(profile)
    except yaml.YAMLError as error:
        raise ValueError("artifact_registry_invalid") from error
    artifact = artifacts.get(args.artifact)
    if artifact is None:
        raise ValueError("artifact_not_found")
    if artifact.get("owner") != "agent-guard" or artifact.get("type") != "json":
        raise ValueError("artifact_not_guard_defined")
    head = git_head_and_clean(project)
    values = {
        "profile_id": args.profile,
        "artifact_id": args.artifact,
        "subject_id": args.subject_id,
        "git_head": head,
        "git_head_short": head[:12],
    }
    rendered, missing = render_template(str(artifact.get("path", "")), values)
    if missing:
        raise ValueError(f"evidence_path_template_value_missing: {','.join(missing)}")
    path = resolve_artifact_path(project, user_home, "project", rendered)
    fields = load_business_fields(args.business_fields_file)
    conflicts = sorted(RESERVED_EVIDENCE_FIELDS & set(fields))
    if conflicts:
        raise ValueError(f"reserved_field_conflict: {','.join(conflicts)}")
    body = {
        "schema_version": "guard-evidence/v1", "status": "pass",
        "producer": args.producer, "profile_id": args.profile,
        "artifact_id": args.artifact, "subject_type": args.subject_type,
        "subject_id": args.subject_id, "head_ref": head,
        "head_ref_short": head[:12], "created_at": now_iso(), **fields,
    }
    atomic_write_evidence(path, body)
    print_json({"status": "evidence_recorded", "head_ref": head, "head_ref_short": head[:12], "path": path.relative_to(project).as_posix()})
    return 0
```

`main()` 捕获 `ValueError/JSONDecodeError/OSError/YAMLError`，输出 `{"status":"failed","reason":str(error)}` 对应的实际 JSON（数据）并返回 1。

安全拒绝矩阵必须额外包含：重复 artifact id（产物编号）返回 `artifact_id_duplicate`、画像目录缺失返回 `profile_not_found`、`artifacts.yaml`（产物注册文件）缺失返回 `artifact_registry_missing`、非法 YAML（配置）返回 `artifact_registry_invalid`；这些失败发生在路径渲染和证据写入前。

- [ ] **Step 6: 更新通用 Skill（技能）说明**

在 Agent Guard Run Skill（代理守卫运行技能）只说明参数、保留字段和“主代理先完成语义判断”；示例使用 `demo-profile/demo-pass`，不出现 Comet（双星工作流）、Cross Agent Review（跨代理审查）或 Planning Review（规划审查）固定编号。

- [ ] **Step 7: 运行 Agent Guard（代理守卫）定向测试**

```powershell
python -m pytest -q -p no:cacheprovider tests/test_agent_guard_plugin_runtime_e2e.py tests/test_agent_guard_skill_entrypoints.py tests/test_agent_guard_runtime_router.py tests/test_validate_guard_profile.py
```

Expected（预期）：PASS（通过）。

- [ ] **Step 8: 提交检查点（仅获授权时）**

```powershell
git add plugins/agent-guard/scripts/guard_runtime/cli.py plugins/agent-guard/scripts/guard_runtime/global_command_guards.py plugins/agent-guard/skills/agent-guard-run tests/test_agent_guard_plugin_runtime_e2e.py tests/test_agent_guard_skill_entrypoints.py
git commit -m "增加通用守卫证据记录入口"
```

### Task 7: 删除 mark-pass（标记通过）并更新调用契约

**Files（文件）：**
- Modify（修改）：`plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- Modify（修改）：`plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`
- Modify（修改）：`tests/test_cross_agent_review_cli.py`
- Modify（修改）：`tests/test_cross_agent_review_plugin_package.py`
- Test（测试）：`tests/test_agent_guard_plugin_runtime_e2e.py`

**Interfaces（接口）：**
- Consumes（输入）：Task 2-4 的报告/状态，Task 6 的 `record-evidence`（记录证据）。
- Produces（输出）：只包含 `run/retry/revalidate`（运行/重试/重新校验）的 Cross Agent Review（跨代理审查）发布契约，以及两个审查来源到同一证据入口的集成夹具。

- [ ] **Step 1: 先反转旧 package（包）与 CLI（命令行）测试**

```python
def test_mark_pass_is_not_a_command() -> None:
    result = run("mark-pass")
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_cross_agent_review_package_has_no_agent_guard_evidence_knowledge() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in CROSS_PLUGIN_ROOT.rglob("*")
        if path.is_file() and path.suffix in {".py", ".md"}
    )
    for forbidden in ["mark-pass", "comet-review-gate", "cross_agent_review_pass", ".local/guard/evidence", "guard-evidence/v1"]:
        assert forbidden not in text
```

- [ ] **Step 2: 运行测试并确认失败**

```powershell
python -m pytest -q -p no:cacheprovider tests/test_cross_agent_review_cli.py tests/test_cross_agent_review_plugin_package.py -k "mark_pass or no_agent_guard"
```

Expected（预期）：FAIL（失败），旧命令与文档仍存在。

- [ ] **Step 3: 删除专用证据代码**

删除 `DEFAULT_PROFILE_ID`、`DEFAULT_ARTIFACT_ID`、`DEFAULT_SUBJECT_TYPE`、mark parser（标记参数解析器）、`guard_pass_path()`、`mark_pass_allowed_paths()`、`run_mark_pass()` 和 main dispatch（主分派）分支。保留报告字节哈希函数供 state（状态）和调用方使用，但不得保留 Agent Guard（代理守卫）字段常量。

- [ ] **Step 4: 更新 Cross Agent Review Skill（跨代理审查技能）**

文档写清：

```text
run/retry/revalidate 只生成 review-report.md 和 review-state.json。
主代理读取两者并作出语义结论；如外部 workflow（工作流）需要证据，调用该 workflow 自己声明的通用证据入口。
本 Skill 不知道 Guard Profile、artifact id、证据路径或证据 schema。
```

补充 `summary_only`（仅摘要）与 `revalidation_policy`（重新校验策略）的精确 JSON（数据）示例和失败回退说明。

- [ ] **Step 5: 增加 Planning Review（规划审查）规范哈希集成测试**

在 Agent Guard（代理守卫）端测试夹具构造：

```python
review = {
    "mode": "convergence",
    "scope": ["proposal.md", "design.md", "tasks.md"],
    "blocking": 0,
    "findings": [],
    "decision": "PASS",
}
canonical = json.dumps(review, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
fields = {
    "review": review,
    "blocking_findings": 0,
    "scope": review["scope"],
    "report": "inline:review",
    "report_hash": "sha256:" + hashlib.sha256(canonical).hexdigest(),
}
```

调用 Task 6 同一 Runtime CLI（运行时命令行），再通过现有 hook router（钩子路由器）断言 planning gate（规划门禁）允许；不导入或修改 Planning Review Skill（规划审查技能）。

- [ ] **Step 6: 运行两个插件完整定向测试**

```powershell
python -m pytest -q -p no:cacheprovider tests/test_cross_agent_review_cli.py tests/test_cross_agent_review_plugin_package.py tests/test_agent_guard_runtime_router.py tests/test_agent_guard_plugin_runtime_e2e.py tests/test_validate_guard_profile.py tests/test_agent_guard_skill_entrypoints.py
```

Expected（预期）：PASS（通过）。

- [ ] **Step 7: 提交原子迁移检查点（仅获授权时）**

```powershell
git add plugins/cross-agent-review plugins/agent-guard tests/test_cross_agent_review_cli.py tests/test_cross_agent_review_plugin_package.py tests/test_agent_guard_runtime_router.py tests/test_agent_guard_plugin_runtime_e2e.py tests/test_validate_guard_profile.py tests/test_agent_guard_skill_entrypoints.py
git commit -m "迁移审查通过证据所有权"
```

### Task 8: 发布形态端到端回归与完成验证

**Files（文件）：**
- Modify if needed（按需修改）：`tests/test_agent_guard_plugin_runtime_e2e.py`
- Modify（修改）：`openspec/changes/stabilize-cross-agent-review-evidence/tasks.md`
- Verify（验证）：所有本变更文件

**Interfaces（接口）：**
- Consumes（输入）：Task 1-7 全部用户入口。
- Produces（输出）：两条完整业务链回归、OpenSpec（开放规格）严格通过和仓库 full（完整）验证结果。

- [ ] **Step 1: 完成 Cross Agent Review（跨代理审查）到门禁的发布形态回归**

测试必须从脚本文件入口执行，而不是直接调用内部函数：

```text
cross_agent_review.py run
→ review-state.json + review-report.md
→ timeout 时 cross_agent_review.py retry，或机械提交时 revalidate
→ 主代理业务字段 JSON
→ guard_runtime/cli.py record-evidence
→ hook_router.py PreToolUse
→ status=allow
```

SDK（开发包）测试替身只能作为可导入的测试环境模块进入真实 `_sdk-dispatch`（内部派发）路径，生产 `run`（运行）不得新增 fake result flag（伪结果参数）。

- [ ] **Step 2: 完成 Planning Review（规划审查）到门禁的发布形态回归**

从五字段 JSON（数据）构造规范哈希，执行同一个 `record-evidence`（记录证据）和 hook router（钩子路由器）入口，断言 `planning_review_pass`（规划审查通过标记）匹配当前完整 `HEAD`（提交头）并放行；测试后断言没有 Planning Review Skill（规划审查技能）产物写入。

- [ ] **Step 3: 运行 OpenSpec（开放规格）严格校验**

```powershell
openspec validate stabilize-cross-agent-review-evidence --strict
```

Expected（预期）：`Change 'stabilize-cross-agent-review-evidence' is valid`。

- [ ] **Step 4: 运行插件定向验证**

```powershell
python -m pytest -q -p no:cacheprovider tests/test_cross_agent_review_cli.py tests/test_cross_agent_review_plugin_package.py
python -m pytest -q -p no:cacheprovider tests/test_agent_guard_runtime_session_focus.py tests/test_agent_guard_runtime_brief.py tests/test_agent_guard_skill_entrypoints.py tests/test_agent_guard_runtime_router.py tests/test_agent_guard_plugin_installer.py tests/test_agent_guard_plugin_runtime_e2e.py tests/test_agent_guard_plugin_package.py tests/test_agent_guard_prd_full_e2e.py tests/test_extract_guard_model.py tests/test_validate_guard_profile.py tests/test_init_user_guard.py tests/test_init_project_guard.py
```

Expected（预期）：两条命令均 PASS（通过）。

- [ ] **Step 5: 运行 package（包）和 full verification（完整验证）**

先按 Build and Verify（构建与验证）Skill（技能）定位仓库入口，再执行 full（完整）模式。若仓库入口等价命令为当前配置中的 runner（运行器），预期最终 `status: passed`。

- [ ] **Step 6: 复核差异边界**

```powershell
git diff --name-only
git diff --check
git status --short
```

人工断言：没有修改 Comet（双星工作流）技能/脚本、没有写用户级 Plugin（插件）或 Guard Profile（守卫画像）、没有新第三方依赖、没有残留临时文件。

- [ ] **Step 7: 更新 OpenSpec tasks（开放规格任务）**

只在对应实现和验证真实通过后，把 `openspec/changes/stabilize-cross-agent-review-evidence/tasks.md` 中的复选框逐项改为 `[x]`；不得预先勾选。

- [ ] **Step 8: 最终提交（仅获授权时）**

```powershell
git add plugins/cross-agent-review plugins/agent-guard tests openspec/changes/stabilize-cross-agent-review-evidence docs/superpowers/specs/2026-07-10-cross-agent-review-evidence-design.md docs/superpowers/plans/2026-07-10-cross-agent-review-evidence.md
git commit -m "稳定跨代理审查与守卫证据写入"
```

没有当前明确提交授权时不执行；把验证完成但未提交作为明确 stop state（停止状态）报告。
