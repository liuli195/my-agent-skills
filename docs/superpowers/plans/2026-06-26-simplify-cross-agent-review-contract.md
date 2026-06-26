---
change: simplify-cross-agent-review-contract
design-doc: docs/superpowers/specs/2026-06-26-simplify-cross-agent-review-contract-design.md
base-ref: 204be94d39500d38fe3193657876fcc23258d65e
---

# Simplify Cross-Agent Review Contract Implementation Plan

> **For agentic workers（代理执行者）:** REQUIRED SUB-SKILL（必需子技能）: Use superpowers:subagent-driven-development（子代理驱动开发，推荐） or superpowers:executing-plans（执行计划） to implement this plan task-by-task（逐任务执行）. Steps use checkbox（复选框） syntax for tracking.

**Goal（目标）:** 将 `cross-agent-review`（跨代理审查）收敛为单一 `review-input.json`（审查输入文件）启动契约，默认只产出报告和通过标记，并删除旧输入、旧 reviewer（审查代理）和默认排障产物。

**Architecture（架构）:** 以 `prepared-inputs/review-input.json`（预备输入目录中的审查输入文件）作为唯一入口，脚本从该文件派生 review subject（审查对象）、上下文文件、输出目录、模式和 reviewer（审查代理）派发信息。默认路径不复制输入快照、不写 manifest（清单）、不写 prompt/raw（提示词/原始输出），只在 `--debug`（排障开关）显式启用时写入 `debug/`（排障目录）。

**Tech Stack（技术栈）:** Python（Python 语言）标准库、argparse（命令行参数解析）、pytest（Python 测试运行器）、Git（版本控制）、Claude Agent SDK（Claude 代理开发包）、OpenSpec（开放规格）。

---

## Context Read（已读上下文）

- `docs/superpowers/specs/2026-06-26-simplify-cross-agent-review-contract-design.md`
- `openspec/changes/simplify-cross-agent-review-contract/tasks.md`
- `openspec/changes/simplify-cross-agent-review-contract/specs/cross-agent-review/spec.md`
- `openspec/changes/simplify-cross-agent-review-contract/.comet/handoff/brainstorm-summary.md`
- `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- `plugins/cross-agent-review/skills/cross-agent-review/assets/templates/reviewer-prompt.md`
- `tests/test_cross_agent_review_cli.py`
- `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`
- `tests/test_cross_agent_review_plugin_package.py`
- `.build-and-verify/config.json`

## File Structure（文件结构）

- Modify（修改）: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
  - 负责 `--input-file`（输入文件参数）解析、`ReviewInput`（审查输入）模型、`prepared-inputs`（预备输入目录）校验、clean worktree（干净工作区）允许清单、Git（版本控制）引用校验、reviewer（审查代理）派发、debug（排障）产物和默认输出。
- Modify（修改）: `plugins/cross-agent-review/skills/cross-agent-review/assets/templates/reviewer-prompt.md`
  - 只引用 `review-input.json`（审查输入文件），不再内联 manifest（清单）、changed files（变更文件）清单、上下文正文或长命令块。
- Modify（修改）: `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`
  - 文档化单一输入文件、`plan_file`（计划文件）、两种模式、两个 reviewer（审查代理）、默认输出和 debug（排障）输出。
- Modify（修改）: `tests/test_cross_agent_review_cli.py`
  - 覆盖 CLI（命令行接口）输入契约、模式、Git（版本控制）范围、工作区校验、reviewer（审查代理）派发、prompt（提示词）和输出契约。
- Modify（修改）: `tests/test_cross_agent_review_plugin_package.py`
  - 覆盖 Skill（技能）文档、包内模板、移除旧 CLI（命令行接口）选项和旧输出说明。

Active old caller search（现有旧调用方搜索）结果：

- 旧启动参数 `--spec-file`、`--design-file`、`--tasks-file`、`--disable-risk-review` 当前只在以下活跃文件中出现：
  - `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
  - `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`
  - `tests/test_cross_agent_review_cli.py`
  - `tests/test_cross_agent_review_plugin_package.py`
- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`、`plugins/release-flow/skills/release-flow/scripts/release_flow.py` 和 Agent Guard（代理守卫）相关文件只引用 `review-pass.json`（通过标记）或插件目录，不调用旧参数；保留并做回归检查。
- 历史 plans（计划）、reports（报告）和 archive（归档）目录中的旧描述不是活跃调用方，本计划不要求改写历史记录。

## Task 1: Single Input File Loader（单一输入文件加载）

**Files（文件）:**
- Modify（修改）: `tests/test_cross_agent_review_cli.py`
- Modify（修改）: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`

- [ ] **Step 1: Write failing tests（先写失败测试）**

Add helper functions near the existing `review_args` helper in `tests/test_cross_agent_review_cli.py`:

```python
def write_review_input(
    project: Path,
    base: str,
    head: str,
    *,
    mode: str = "convergence",
    change: str = "demo",
    payload_overrides: dict | None = None,
) -> Path:
    output_dir = project / ".local" / "cross-agent-review" / change / head[:12]
    prepared_dir = output_dir / "prepared-inputs"
    spec_file = write_file(project / "spec.md", "spec body\n")
    design_file = write_file(project / "design.md", "design body\n")
    plan_file = write_file(project / "docs" / "superpowers" / "plans" / "demo.md", "plan body\n")
    payload = {
        "change": change,
        "mode": mode,
        "base_ref": base,
        "head_ref": head,
        "spec_file": str(spec_file.relative_to(project)),
        "design_file": str(design_file.relative_to(project)),
        "plan_file": str(plan_file.relative_to(project)),
    }
    if payload_overrides:
        payload.update(payload_overrides)
    input_file = prepared_dir / "review-input.json"
    write_file(input_file, json.dumps(payload, ensure_ascii=False) + "\n")
    return input_file


def review_args(project: Path, head: str, *, mode: str = "convergence") -> list[str]:
    return [
        "run",
        "--input-file",
        str(write_review_input(project, head, head, mode=mode)),
        "--fake-reviewer-results",
        "[]",
    ]
```

Add these tests:

```python
def test_run_accepts_single_review_input_file(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)

    result = run(*review_args(project, head), cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: pass" in result.stdout
    assert (project / ".local" / "cross-agent-review" / "demo" / head[:12] / "review-report.md").is_file()


def test_missing_input_file_fails(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    init_repo(project)

    result = run("run", "--input-file", str(project / ".local" / "missing" / "review-input.json"), cwd=project)

    assert result.returncode == 1
    assert "missing_file" in result.stdout


def test_missing_required_review_input_field_fails(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head, payload_overrides={"plan_file": None})
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    del payload["plan_file"]
    input_file.write_text(json.dumps(payload), encoding="utf-8")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "missing_field: plan_file" in result.stdout


def test_missing_referenced_plan_file_fails(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head, payload_overrides={"plan_file": "docs/superpowers/plans/missing.md"})

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "missing_file" in result.stdout
    assert "missing.md" in result.stdout


def test_invalid_mode_fails(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head, mode="wide")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "invalid_mode: wide" in result.stdout
```

- [ ] **Step 2: Run failing tests（确认失败）**

Run:

```powershell
python -m pytest -q tests/test_cross_agent_review_cli.py::test_run_accepts_single_review_input_file tests/test_cross_agent_review_cli.py::test_missing_input_file_fails tests/test_cross_agent_review_cli.py::test_missing_required_review_input_field_fails tests/test_cross_agent_review_cli.py::test_missing_referenced_plan_file_fails tests/test_cross_agent_review_cli.py::test_invalid_mode_fails
```

Expected（预期）: FAIL（失败） because `--input-file`（输入文件参数） and `plan_file`（计划文件） are not implemented.

- [ ] **Step 3: Implement minimal loader（实现最小加载器）**

In `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`:

- Replace `REQUIRED_FILE_ARGS`（必需文件参数） with:

```python
REQUIRED_INPUT_FIELDS = ["change", "mode", "base_ref", "head_ref", "spec_file", "design_file", "plan_file"]
VALID_MODES = {"convergence", "endless"}
```

- Replace `ReviewArgs`（审查参数） with a model that carries the loaded input and derived output directory:

```python
@dataclass(frozen=True)
class ReviewInput:
    change: str
    mode: str
    base_ref: str
    head_ref: str
    spec_file: Path
    design_file: Path
    plan_file: Path
    input_file: Path
    output_dir: Path
    debug: bool
    sdk_python: Path | None
    fake_reviewer_results: str | None
```

- Update `build_parser()`（构建参数解析器） so `run` accepts only these runtime options:

```python
run_parser.add_argument("--input-file", type=Path, required=True)
run_parser.add_argument("--debug", action="store_true")
run_parser.add_argument("--sdk-python", type=Path)
run_parser.add_argument("--fake-reviewer-results")
```

- Add `load_review_input(args: argparse.Namespace) -> ReviewInput`:
  - `args.input_file` missing -> `ValueError(f"missing_file: {path}")`
  - invalid JSON（数据文件格式） -> existing `json.JSONDecodeError` path
  - missing field -> `ValueError(f"missing_field: {field}")`
  - invalid mode -> `ValueError(f"invalid_mode: {mode}")`
  - context paths are resolved relative to `Path.cwd()` unless already absolute
  - missing `spec_file` / `design_file` / `plan_file` -> `ValueError(f"missing_file: {path}")`
  - `output_dir` is `input_file.parent.parent`

- Rename call sites from `ReviewArgs`（审查参数） to `ReviewInput`（审查输入） only where touched in this task.

- [ ] **Step 4: Run passing tests（确认通过）**

Run the same command from Step 2.

Expected（预期）: PASS（通过） for the five new tests.

**Acceptance（验收）:**
- `--input-file`（输入文件参数） starts a review（审查）。
- `plan_file`（计划文件） replaces `tasks_file`（任务文件） in the loaded input.
- Missing input, missing field, missing referenced file, and invalid mode all fail before reviewer（审查代理） dispatch.

## Task 2: Prepared Inputs and Clean Worktree（预备输入与干净工作区）

**Files（文件）:**
- Modify（修改）: `tests/test_cross_agent_review_cli.py`
- Modify（修改）: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`

- [ ] **Step 1: Write failing tests（先写失败测试）**

Add tests:

```python
def test_prepared_inputs_rejects_extra_regular_file(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head)
    write_file(input_file.parent / "plan.md", "old snapshot\n")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "unexpected_prepared_input" in result.stdout
    assert "plan.md" in result.stdout


def test_input_file_must_be_named_review_input_json_under_prepared_inputs(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head)
    wrong_file = input_file.parent / "input.json"
    wrong_file.write_text(input_file.read_text(encoding="utf-8"), encoding="utf-8")
    input_file.unlink()

    result = run("run", "--input-file", str(wrong_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "invalid_input_file_location" in result.stdout


def test_invalid_base_ref_fails_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, "0" * 40, head)

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "base_ref_mismatch" in result.stdout


def test_dirty_worktree_outside_runtime_artifacts_rejects_before_dispatch(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head)
    write_file(project / "dirty.txt", "dirty\n")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (input_file.parent.parent / "review-pass.json").exists()


def test_clean_worktree_checks_reuse_runtime_allowlist(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head)
    parsed = module.build_parser().parse_args([
        "run",
        "--input-file",
        str(input_file),
        "--fake-reviewer-results",
        "[]",
    ])
    calls = []

    def fake_ensure_clean_subject(cwd, head_ref, allowed_dirty_paths=()):
        calls.append([Path(path).resolve() for path in allowed_dirty_paths])

    monkeypatch.setattr(module, "ensure_clean_subject", fake_ensure_clean_subject)
    monkeypatch.chdir(project)

    assert module.run_review(parsed) == 0

    assert len(calls) == 3
    assert calls[0] == calls[1] == calls[2]
    assert input_file.resolve() in calls[0]
    assert input_file.parent.parent.resolve() in calls[0]
```

- [ ] **Step 2: Run failing tests（确认失败）**

Run:

```powershell
python -m pytest -q tests/test_cross_agent_review_cli.py::test_prepared_inputs_rejects_extra_regular_file tests/test_cross_agent_review_cli.py::test_input_file_must_be_named_review_input_json_under_prepared_inputs tests/test_cross_agent_review_cli.py::test_invalid_base_ref_fails_before_dispatch tests/test_cross_agent_review_cli.py::test_dirty_worktree_outside_runtime_artifacts_rejects_before_dispatch tests/test_cross_agent_review_cli.py::test_clean_worktree_checks_reuse_runtime_allowlist
```

Expected（预期）: FAIL（失败） because prepared input（预备输入） and shared allowlist（允许清单） checks are not implemented.

- [ ] **Step 3: Implement validation（实现校验）**

In `cross_agent_review.py`:

- Add `validate_input_file_location(input_file: Path) -> None`:
  - require `input_file.name == "review-input.json"`
  - require `input_file.parent.name == "prepared-inputs"`
  - error: `invalid_input_file_location: {input_file}`
- Add `validate_prepared_inputs_dir(input_file: Path) -> None`:
  - collect regular files with `path.is_file()`
  - require exactly `[input_file.resolve()]`
  - error: `unexpected_prepared_input: {path}`
- Add `runtime_allowed_paths(review_input: ReviewInput) -> list[Path]`:

```python
return [review_input.input_file, review_input.output_dir]
```

- Update `ensure_clean_subject()`（确保干净审查对象） so an allowed directory covers descendants:

```python
def path_is_allowed(path: Path, allowed: set[Path]) -> bool:
    resolved = path.resolve()
    for item in allowed:
        if resolved == item:
            return True
        if item.is_dir():
            try:
                resolved.relative_to(item)
                return True
            except ValueError:
                pass
    return False
```

- Add `validate_base_ref(cwd: Path, base_ref: str) -> None` using:

```python
git_output(["rev-parse", "--verify", f"{base_ref}^{{commit}}"], cwd)
```

Raise `ValueError(f"base_ref_mismatch: {base_ref}")` when Git（版本控制） rejects it.

- Call `ensure_clean_subject(Path.cwd(), review_input.head_ref, runtime_allowed_paths(review_input))` exactly three times:
  - after input and Git（版本控制） validation
  - immediately before reviewer（审查代理） dispatch
  - immediately before writing `review-pass.json`（通过标记）

- [ ] **Step 4: Run passing tests（确认通过）**

Run the same command from Step 2.

Expected（预期）: PASS（通过）.

**Acceptance（验收）:**
- `prepared-inputs`（预备输入目录） contains only one regular file: `review-input.json`（审查输入文件）。
- `base_ref`（基准引用） and `head_ref`（当前提交引用） are validated before reviewer（审查代理） dispatch.
- The same runtime artifact（运行产物） allowlist（允许清单） is used at startup, before dispatch, and before pass marker（通过标记） generation.

## Task 3: Plan File and Prompt Contract（计划文件与提示词契约）

**Files（文件）:**
- Modify（修改）: `tests/test_cross_agent_review_cli.py`
- Modify（修改）: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- Modify（修改）: `plugins/cross-agent-review/skills/cross-agent-review/assets/templates/reviewer-prompt.md`

- [ ] **Step 1: Write failing tests（先写失败测试）**

Update `make_review_args_for_module()` to return a loaded `ReviewInput`（审查输入） object, not the old `ReviewArgs`（审查参数）:

```python
def make_review_input_for_module(module, tmp_path: Path):
    input_file = write_review_input(tmp_path, "base", "head")
    return module.load_review_input(
        types.SimpleNamespace(
            input_file=input_file,
            debug=False,
            sdk_python=None,
            fake_reviewer_results=None,
        )
    )
```

Add tests:

```python
def test_reviewer_prompt_references_review_input_file_only(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "two\n")
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "feature")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(project, base, head)
    monkeypatch.chdir(project)
    review_input = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None, fake_reviewer_results=None)
    )

    prompt = module.reviewer_prompt(review_input, "spec-alignment")

    assert f"Read: {input_file}" in prompt
    assert "Review only base_ref...head_ref from the input file." in prompt
    assert "Use spec_file, design_file, and plan_file as requirements context." in prompt
    assert "Manifest file:" not in prompt
    assert "Changed files:" not in prompt
    assert "Spec bytes:" not in prompt
    assert "Design file:" not in prompt
    assert "Tasks file:" not in prompt
    assert "git diff" not in prompt
    assert "spec body" not in prompt
    assert "plan body" not in prompt


def test_reviewer_prompt_template_uses_limited_variables(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review_input = make_review_input_for_module(module, tmp_path)
    template = write_file(
        tmp_path / "reviewer-prompt.md",
        "Role={{ role }} Input={{ input_file_path }} Focus={{ role_focus }} Rubric={{ severity_rubric }} Schema={{ schema_json }}\n",
    )
    monkeypatch.setattr(module, "REVIEWER_PROMPT_TEMPLATE", template, raising=False)

    prompt = module.reviewer_prompt(review_input, "implementation-correctness")

    assert "Role=implementation-correctness" in prompt
    assert f"Input={review_input.input_file}" in prompt
    assert "{{ change }}" not in prompt
    assert "{{ manifest_path }}" not in prompt
    assert "{{ changed_files }}" not in prompt
```

- [ ] **Step 2: Run failing tests（确认失败）**

Run:

```powershell
python -m pytest -q tests/test_cross_agent_review_cli.py::test_reviewer_prompt_references_review_input_file_only tests/test_cross_agent_review_cli.py::test_reviewer_prompt_template_uses_limited_variables
```

Expected（预期）: FAIL（失败） because prompt（提示词） still references manifest（清单）、changed files（变更文件） and tasks（任务）.

- [ ] **Step 3: Implement prompt simplification（实现提示词简化）**

In `cross_agent_review.py`:

- Remove `context_file_references()`（上下文文件引用）、`input_reference()`（输入引用）、`input_manifest_path()`（输入清单路径）、`build_input_manifest()`（构建输入清单） and `write_input_manifest()`（写输入清单） from the live path.
- Keep `review_subject_commands()`（审查对象命令） for internal report/debug use only; do not pass command blocks into the prompt（提示词）。
- Update `reviewer_prompt()`（审查代理提示词） to pass only:

```python
{
    "role": role,
    "input_file_path": str(review_input.input_file),
    "schema_json": schema_json,
    "severity_rubric": SEVERITY_RUBRIC,
    "role_focus": ROLE_FOCUS.get(role, ""),
}
```

Replace `reviewer-prompt.md` with the compact contract:

```markdown
Role: {{ role }}

Read: {{ input_file_path }}

Use read-only inspection. Do not edit files.
Review only base_ref...head_ref from the input file.
Use spec_file, design_file, and plan_file as requirements context.

Focus:
{{ role_focus }}

{{ severity_rubric }}

Return only a single JSON object. Do not use Markdown.

Schema:

{{ schema_json }}

Use only these severity values: CRITICAL, IMPORTANT, WARNING, SUGGESTION.
If there are no issues, return "findings": [].
Do not put pass, aligned, ok, or informational observations in findings.
Do not use severity aliases such as high, medium, low, minor, or info.
```

- [ ] **Step 4: Run passing tests（确认通过）**

Run the same command from Step 2.

Expected（预期）: PASS（通过）.

**Acceptance（验收）:**
- Prompt（提示词） references only `review-input.json`（审查输入文件） as the entry context.
- Prompt（提示词） does not inline diff（差异）、context file（上下文文件） body、manifest（清单）、changed files（变更文件） or long Git（版本控制） commands.
- `plan_file`（计划文件） is the requirements context instead of `tasks_file`（任务文件）。

## Task 4: Two Reviewers and Removed Risk Behavior（两个审查代理与删除风险行为）

**Files（文件）:**
- Modify（修改）: `tests/test_cross_agent_review_cli.py`
- Modify（修改）: `tests/test_cross_agent_review_plugin_package.py`
- Modify（修改）: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`

- [ ] **Step 1: Write failing tests（先写失败测试）**

Update or add tests:

```python
def test_reviewer_roles_are_two_default_roles(tmp_path: Path) -> None:
    module = load_script_module()

    assert module.REVIEWER_ROLES == ["spec-alignment", "implementation-correctness"]
    assert set(module.ROLE_FOCUS) == {"spec-alignment", "implementation-correctness"}


def test_sdk_dispatch_subprocess_uses_only_two_roles(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review_input = make_review_input_for_module(module, tmp_path)
    captured_payload = None

    def fake_run(*args, **kwargs):
        nonlocal captured_payload
        captured_payload = json.loads(kwargs["input"])
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps([
                {"role": "spec-alignment", "status": "completed", "findings": []},
                {"role": "implementation-correctness", "status": "completed", "findings": []},
            ]),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    results = module.run_sdk_dispatch_subprocess(review_input, sys.executable)

    assert [item["role"] for item in results] == ["spec-alignment", "implementation-correctness"]
    assert captured_payload["roles"] == ["spec-alignment", "implementation-correctness"]


def test_removed_disable_risk_review_option_is_rejected(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "run",
            "--input-file",
            str(tmp_path / "review-input.json"),
            "--disable-risk-review",
        ],
        cwd=PLUGIN_ROOT / "skills" / "cross-agent-review",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--disable-risk-review" in result.stderr
```

Update old tests that use removed roles:

- Replace `tests-and-edge-cases`（测试和边界） invalid severity cases with `spec-alignment`（规格一致性）.
- Replace `risk-review`（风险审查） timeout fixture with `implementation-correctness`（实现正确性）.
- Delete the positive skip test for `--disable-risk-review`（关闭风险审查） and keep only the rejection test above.

- [ ] **Step 2: Run failing tests（确认失败）**

Run:

```powershell
python -m pytest -q tests/test_cross_agent_review_cli.py::test_reviewer_roles_are_two_default_roles tests/test_cross_agent_review_cli.py::test_sdk_dispatch_subprocess_uses_only_two_roles tests/test_cross_agent_review_plugin_package.py::test_removed_disable_risk_review_option_is_rejected
```

Expected（预期）: FAIL（失败） because four roles and `--disable-risk-review`（关闭风险审查） still exist.

- [ ] **Step 3: Implement role reduction（实现角色缩减）**

In `cross_agent_review.py`:

- Set:

```python
REVIEWER_ROLES = ["spec-alignment", "implementation-correctness"]
```

- Remove `tests-and-edge-cases`（测试和边界） and `risk-review`（风险审查） entries from `ROLE_FOCUS`（角色重点）。
- Remove `PLACEHOLDER_COMPAT_DISABLE_RISK_REVIEW`（占位兼容关闭风险审查）。
- Remove parser registration for `--disable-risk-review`（关闭风险审查）。
- Remove `disable_risk_review`（关闭风险审查） from the input dataclass（数据结构）。
- Remove skipped reviewer（跳过审查代理） handling from `run_review()`（运行审查）.
- Keep `aggregate(reviewers, skipped)`（汇总结果） unchanged only if existing report rendering still needs an empty skipped list. Pass `[]` from `run_review()`（运行审查）.

- [ ] **Step 4: Run passing tests（确认通过）**

Run the same command from Step 2.

Expected（预期）: PASS（通过）.

**Acceptance（验收）:**
- Only `spec-alignment`（规格一致性） and `implementation-correctness`（实现正确性） are dispatched.
- `tests-and-edge-cases`（测试和边界）, `risk-review`（风险审查） and `--disable-risk-review`（关闭风险审查） are removed from live behavior.

## Task 5: Default Output and Debug Artifacts（默认输出与排障产物）

**Files（文件）:**
- Modify（修改）: `tests/test_cross_agent_review_cli.py`
- Modify（修改）: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`

- [ ] **Step 1: Write failing tests（先写失败测试）**

Add tests:

```python
def test_default_outputs_are_report_and_pass_marker_only(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output_dir / "review-report.md").is_file()
    assert (output_dir / "review-pass.json").is_file()
    assert not (output_dir / "review-results.json").exists()
    assert not (output_dir / "inputs").exists()
    assert not (output_dir / "prompts").exists()
    assert not (output_dir / "raw").exists()
    assert not (output_dir / "debug").exists()


def test_blocking_findings_write_report_without_results_or_pass_marker(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head)
    output_dir = input_file.parent.parent
    fake = json.dumps([
        {
            "role": "implementation-correctness",
            "status": "completed",
            "findings": [
                {
                    "severity": "IMPORTANT",
                    "location": "app.txt:1",
                    "summary": "Wrong behavior",
                    "evidence": "Evidence",
                    "recommendation": "Fix behavior",
                }
            ],
        }
    ])

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", fake, cwd=project)

    assert result.returncode == 1
    assert (output_dir / "review-report.md").is_file()
    assert not (output_dir / "review-pass.json").exists()
    assert not (output_dir / "review-results.json").exists()
    assert not (output_dir / "inputs").exists()


def test_debug_writes_input_prompts_and_raw_under_debug(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    head = init_repo(project)
    input_file = write_review_input(project, head, head)
    review_input = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=True, sdk_python=None, fake_reviewer_results=None)
    )

    def fake_run(*args, **kwargs):
        payload = json.loads(kwargs["input"])
        raw_dir = Path(payload["raw_dir"])
        raw_dir.mkdir(parents=True, exist_ok=True)
        for role in payload["roles"]:
            (raw_dir / f"{role}.txt").write_text(
                json.dumps({"role": role, "status": "completed", "findings": []}),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=json.dumps([]), stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.chdir(project)

    module.run_sdk_dispatch_subprocess(review_input, sys.executable)

    debug_dir = input_file.parent.parent / "debug"
    assert json.loads((debug_dir / "review-input.json").read_text(encoding="utf-8"))["mode"] == "convergence"
    assert {path.name for path in (debug_dir / "prompts").iterdir()} == {
        "spec-alignment.txt",
        "implementation-correctness.txt",
    }
    assert {path.name for path in (debug_dir / "raw").iterdir()} == {
        "spec-alignment.txt",
        "implementation-correctness.txt",
    }
```

- [ ] **Step 2: Run failing tests（确认失败）**

Run:

```powershell
python -m pytest -q tests/test_cross_agent_review_cli.py::test_default_outputs_are_report_and_pass_marker_only tests/test_cross_agent_review_cli.py::test_blocking_findings_write_report_without_results_or_pass_marker tests/test_cross_agent_review_cli.py::test_debug_writes_input_prompts_and_raw_under_debug
```

Expected（预期）: FAIL（失败） because default output still writes `review-results.json`（结构化结果）、`inputs/manifest.json`（输入清单）、`prompts/`（提示词目录） and `raw/`（原始输出目录）.

- [ ] **Step 3: Implement output split（实现输出拆分）**

In `cross_agent_review.py`:

- Remove `archive_input_snapshots()`（归档输入快照） from `run_review()`（运行审查）。
- Remove default `write_json(results_path, summary)`（写结构化结果）。
- Write only:
  - `review-report.md`（审查报告）
  - `review-pass.json`（通过标记） when `blocking_findings == 0`
- Add `debug_dir_for(review_input: ReviewInput) -> Path`:

```python
return review_input.output_dir / "debug"
```

- In `run_sdk_dispatch_subprocess()`（运行 SDK 派发子进程）:
  - always build prompts in memory
  - when `review_input.debug` is true, write:
    - `debug/review-input.json`
    - `debug/prompts/<role>.txt`
    - `debug/raw/<role>.txt`
  - when `review_input.debug` is false, do not create `debug/`（排障目录）, `prompts/`（提示词目录） or `raw/`（原始输出目录）
  - send `raw_dir` in the subprocess payload only when debug（排障） is enabled

- Update timeout handling:
  - when debug（排障） is enabled, read partial raw（原始输出） from `debug/raw/`
  - when debug（排障） is disabled, synthesize failures for both roles without reading files

- [ ] **Step 4: Run passing tests（确认通过）**

Run the same command from Step 2.

Expected（预期）: PASS（通过）.

**Acceptance（验收）:**
- Default output does not include `review-results.json`（结构化结果）、`inputs/manifest.json`（输入清单）、`inputs/`（输入目录）、`prompts/`（提示词目录）、`raw/`（原始输出目录） or input snapshots（输入快照）。
- `--debug`（排障开关） is the only path that writes `debug/review-input.json`、`debug/prompts/<role>.txt` and `debug/raw/<role>.txt`.

## Task 6: Mode Semantics and Pass Marker（模式语义与通过标记）

**Files（文件）:**
- Modify（修改）: `tests/test_cross_agent_review_cli.py`
- Modify（修改）: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`

- [ ] **Step 1: Write failing tests（先写失败测试）**

Add mode-focused tests:

```python
def test_convergence_pass_marker_records_mode_and_refs(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "two\n")
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "feature")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(project, base, head, mode="convergence")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    marker = json.loads((input_file.parent.parent / "review-pass.json").read_text(encoding="utf-8"))
    assert marker["mode"] == "convergence"
    assert marker["base_ref"] == base
    assert marker["head_ref"] == head


def test_endless_pass_marker_records_mode_and_refs(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "two\n")
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "feature")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(project, base, head, mode="endless")

    result = run("run", "--input-file", str(input_file), "--fake-reviewer-results", "[]", cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    marker = json.loads((input_file.parent.parent / "review-pass.json").read_text(encoding="utf-8"))
    assert marker["mode"] == "endless"
    assert marker["base_ref"] == base
    assert marker["head_ref"] == head


def test_review_subject_commands_use_input_base_and_head_refs(tmp_path: Path) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "two\n")
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "feature")
    head = git(project, "rev-parse", "HEAD")
    input_file = write_review_input(project, base, head, mode="endless")
    review_input = module.load_review_input(
        types.SimpleNamespace(input_file=input_file, debug=False, sdk_python=None, fake_reviewer_results=None)
    )

    commands = module.review_subject_commands(review_input)

    assert commands["diff_command"] == f"git diff {base}...{head}"
    assert commands["commit_list_command"] == f"git log {base}..{head} --oneline"
    assert commands["changed_files_command"] == f"git diff --name-status --find-renames --find-copies-harder {base}...{head}"
```

- [ ] **Step 2: Run failing tests（确认失败）**

Run:

```powershell
python -m pytest -q tests/test_cross_agent_review_cli.py::test_convergence_pass_marker_records_mode_and_refs tests/test_cross_agent_review_cli.py::test_endless_pass_marker_records_mode_and_refs tests/test_cross_agent_review_cli.py::test_review_subject_commands_use_input_base_and_head_refs
```

Expected（预期）: FAIL（失败） because `review-pass.json`（通过标记） does not include `mode`（模式） and old helper fields still use `tasks_file`（任务文件）.

- [ ] **Step 3: Implement mode recording（实现模式记录）**

In `cross_agent_review.py`:

- Add `"mode": review_input.mode` to the `review-pass.json`（通过标记） payload.
- Ensure `review_subject_commands(review_input)`（审查对象命令） uses only `review_input.base_ref` and `review_input.head_ref`.
- Keep both `convergence`（收敛） and `endless`（无尽） behavior as data-driven by the caller-provided refs:
  - script validates and records the mode
  - script does not change range by mode
  - reviewer prompt（审查提示词） tells reviewer（审查代理） to use `base_ref...head_ref` from input

- [ ] **Step 4: Run passing tests（确认通过）**

Run the same command from Step 2.

Expected（预期）: PASS（通过）.

**Acceptance（验收）:**
- `convergence`（收敛） and `endless`（无尽） both work through `base_ref`（基准引用） and `head_ref`（当前提交引用）。
- `review-pass.json`（通过标记） contains `mode`（模式）。

## Task 7: Skill Docs and Old Caller Cleanup（技能文档与旧调用清理）

**Files（文件）:**
- Modify（修改）: `tests/test_cross_agent_review_plugin_package.py`
- Modify（修改）: `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`
- Verify（验证）: `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- Verify（验证）: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- Verify（验证）: `plugins/agent-guard/**`

- [ ] **Step 1: Write failing tests（先写失败测试）**

Update package tests:

```python
def test_cross_agent_review_skill_documents_single_review_input_contract() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert ".local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json" in text
    assert "--input-file" in text
    assert "plan_file" in text
    assert "tasks_file" not in text
    assert "--spec-file" not in text
    assert "--design-file" not in text
    assert "--tasks-file" not in text


def test_cross_agent_review_skill_documents_default_and_debug_outputs() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "review-report.md" in text
    assert "review-pass.json" in text
    assert "review-results.json" not in text
    assert "inputs/manifest.json" not in text
    assert "inputs/spec.md" not in text
    assert "inputs/design.md" not in text
    assert "inputs/tasks.md" not in text
    assert "debug/review-input.json" in text
    assert "debug/prompts/<role>.txt" in text
    assert "debug/raw/<role>.txt" in text


def test_cross_agent_review_skill_documents_two_reviewers_only() -> None:
    skill = PLUGIN_ROOT / "skills" / "cross-agent-review" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    assert "spec-alignment" in text
    assert "implementation-correctness" in text
    assert "tests-and-edge-cases" not in text
    assert "risk-review" not in text
```

Replace the old placeholder CLI（命令行接口） test with:

```python
def test_cross_agent_review_rejects_removed_cli_options(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "run",
            "--input-file",
            str(tmp_path / "review-input.json"),
            "--spec-file",
            str(tmp_path / "spec.md"),
            "--design-file",
            str(tmp_path / "design.md"),
            "--tasks-file",
            str(tmp_path / "tasks.md"),
            "--disable-risk-review",
        ],
        cwd=PLUGIN_ROOT / "skills" / "cross-agent-review",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
```

- [ ] **Step 2: Run failing docs tests（确认失败）**

Run:

```powershell
python -m pytest -q tests/test_cross_agent_review_plugin_package.py::test_cross_agent_review_skill_documents_single_review_input_contract tests/test_cross_agent_review_plugin_package.py::test_cross_agent_review_skill_documents_default_and_debug_outputs tests/test_cross_agent_review_plugin_package.py::test_cross_agent_review_skill_documents_two_reviewers_only tests/test_cross_agent_review_plugin_package.py::test_cross_agent_review_rejects_removed_cli_options
```

Expected（预期）: FAIL（失败） because Skill（技能） docs still describe old arguments and old artifacts.

- [ ] **Step 3: Update docs and caller references（更新文档与调用引用）**

In `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`:

- Replace the command block with:

```bash
python scripts/cross_agent_review.py run \
  --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

- Add debug（排障） form:

```bash
python scripts/cross_agent_review.py run \
  --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json \
  --debug
```

- Document `review-input.json`（审查输入文件） fields:
  - `change`
  - `mode`
  - `base_ref`
  - `head_ref`
  - `spec_file`
  - `design_file`
  - `plan_file`
- State that `prepared-inputs`（预备输入目录） contains only one regular file: `review-input.json`（审查输入文件）。
- State that default reviewer（审查代理） roles are only:
  - `spec-alignment`（规格一致性）
  - `implementation-correctness`（实现正确性）
- State that default outputs are only:
  - `review-report.md`（审查报告）
  - `review-pass.json`（通过标记） when passing
- State that debug（排障） outputs exist only with `--debug`（排障开关）:
  - `debug/review-input.json`
  - `debug/prompts/<role>.txt`
  - `debug/raw/<role>.txt`

Do not update historical files under:

- `docs/superpowers/plans/`
- `docs/superpowers/reports/`
- `openspec/changes/archive/`

They are historical records, not active callers.

- [ ] **Step 4: Search for active old callers（搜索活跃旧调用方）**

Run:

```powershell
rg -n -- "--spec-file|--design-file|--tasks-file|--disable-risk-review" plugins tests
```

Expected（预期）: only the rejection test in `tests/test_cross_agent_review_plugin_package.py` contains removed option strings.

Run:

```powershell
rg -n -- "tasks_file|tests-and-edge-cases|risk-review|review-results\\.json|inputs/manifest\\.json|prompts/|raw/" plugins tests
```

Expected（预期）:
- no matches in `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- no matches in `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`
- remaining matches in tests are negative assertions or renamed debug path assertions

- [ ] **Step 5: Run passing docs tests（确认通过）**

Run:

```powershell
python -m pytest -q tests/test_cross_agent_review_plugin_package.py
```

Expected（预期）: PASS（通过）.

**Acceptance（验收）:**
- Skill（技能） docs match the new single input contract.
- Old active callers are removed or converted.
- PR Flow（拉取请求流程）, Release Flow（发布流程） and Agent Guard（代理守卫） references to `review-pass.json`（通过标记） stay valid.

## Task 8: Regression and Verification（回归与验证）

**Files（文件）:**
- Verify（验证）: all files touched in Tasks 1-7
- Verify（验证）: `.build-and-verify/config.json`
- Verify（验证）: `openspec/changes/simplify-cross-agent-review-contract/specs/cross-agent-review/spec.md`

- [ ] **Step 1: Run focused cross-agent review tests（运行重点测试）**

Run:

```powershell
python -m pytest -q -n 8 -p no:cacheprovider tests/test_cross_agent_review_cli.py tests/test_cross_agent_review_plugin_package.py
```

Expected（预期）: PASS（通过）.

- [ ] **Step 2: Run caller-adjacent regression（运行相邻调用方回归）**

Run:

```powershell
python -m pytest -q -n auto -p no:cacheprovider tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py
```

Expected（预期）: PASS（通过）; verifies PR Flow（拉取请求流程） still handles review gate（审查门禁） pass marker（通过标记） paths.

Run:

```powershell
python -m pytest -q -n 8 -p no:cacheprovider tests/test_release_flow_cli.py tests/test_release_flow_plugin_package.py
```

Expected（预期）: PASS（通过）; verifies Release Flow（发布流程） package projection（包投影） still includes `cross-agent-review`（跨代理审查）.

Run:

```powershell
python -m pytest -q -n 8 -p no:cacheprovider tests/test_agent_guard_runtime_router.py tests/test_agent_guard_skill_entrypoints.py tests/test_agent_guard_plugin_package.py
```

Expected（预期）: PASS（通过）; verifies Agent Guard（代理守卫） still reads `review-pass.json`（通过标记） from the same default output directory.

- [ ] **Step 3: Run repository configured checks（运行仓库配置检查）**

Run:

```powershell
python scripts/local_plugin_build.py
```

Expected（预期）: PASS（通过）.

Run:

```powershell
openspec validate --all --strict --no-interactive
```

Expected（预期）: PASS（通过）.

- [ ] **Step 4: Final search checks（最终搜索检查）**

Run:

```powershell
rg -n -- "--spec-file|--design-file|--tasks-file|--disable-risk-review" plugins tests
rg -n -- "tests-and-edge-cases|risk-review|review-results\\.json|inputs/manifest\\.json|inputs/spec\\.md|inputs/design\\.md|inputs/tasks\\.md" plugins tests
```

Expected（预期）:
- no active old CLI（命令行接口） caller remains
- no live implementation or Skill（技能） docs describe removed reviewers（审查代理） or removed default artifacts（默认产物）
- retained matches are negative tests or debug（排障） path assertions only

**Acceptance（验收）:**
- All focused tests and adjacent regressions pass.
- OpenSpec（开放规格） validation passes.
- The new default contract is covered by failing-first tests.

## Requirement Coverage（要求覆盖）

- Single `--input-file`（输入文件参数） and `prepared-inputs/review-input.json`（预备输入目录审查输入文件）: Tasks 1, 2, 7.
- `prepared-inputs`（预备输入目录） only allows one regular file（普通文件）: Task 2.
- `plan_file`（计划文件） replaces `tasks_file`（任务文件）: Tasks 1, 3, 7.
- `convergence`（收敛） / `endless`（无尽） use `base_ref`（基准引用） / `head_ref`（当前提交引用）: Tasks 2, 6.
- Only `spec-alignment`（规格一致性） and `implementation-correctness`（实现正确性） reviewers（审查代理） remain: Task 4.
- Removed `tests-and-edge-cases`（测试和边界）, `risk-review`（风险审查）, and `--disable-risk-review`（关闭风险审查）: Tasks 4, 7.
- Default no `review-results.json`（结构化结果）, `inputs/manifest.json`（输入清单）, `prompts/`（提示词目录）, `raw/`（原始输出目录）, or input snapshots（输入快照）: Task 5.
- `--debug`（排障开关） writes `debug/review-input.json`, `debug/prompts/<role>.txt`, and `debug/raw/<role>.txt`: Task 5.
- `review-pass.json`（通过标记） includes `mode`（模式） and tests cover `convergence`（收敛） / `endless`（无尽）: Task 6.
- Clean worktree（干净工作区） allowlist（允许清单） remains consistent at startup, before dispatch, and before pass marker（通过标记）: Task 2.
- Search and update old callers（旧调用方）: Task 7.
- TDD（测试驱动开发） order: every implementation task starts with failing tests, then implementation, then targeted tests.

## Self-Review Checklist（自查清单）

- Spec coverage（规格覆盖）: each OpenSpec（开放规格） scenario maps to at least one task above.
- Placeholder scan（占位扫描）: plan contains concrete files, commands, test names and expected outcomes.
- Type consistency（类型一致性）: later tasks use `ReviewInput`（审查输入）, `plan_file`（计划文件）, `input_file`（输入文件）, `output_dir`（输出目录）, `mode`（模式）, `base_ref`（基准引用） and `head_ref`（当前提交引用） consistently.
- Scope control（范围控制）: implementation changes only active plugin, Skill（技能） docs and tests; historical records stay unchanged.
