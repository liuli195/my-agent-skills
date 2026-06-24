---
change: refactor-cross-agent-review-input-contract
design-doc: docs/superpowers/specs/2026-06-24-cross-agent-review-input-contract-design.md
base-ref: a8fdccea5ddfdc70d55dadb7028815401d1953ad
---

# Cross-Agent Review Input Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `cross-agent-review`（跨代理审查）的核心输入从 `diff.patch`（差异补丁）改成 review subject（审查对象）契约，并把 `reviewer prompt`（审查提示词）抽到可复用模板。

**Architecture:** Python（脚本）仍是调用入口和渲染入口。`base_ref`（基线引用）和 `head_ref`（头引用）定义审查范围；脚本生成 `manifest.json`（清单）里的 git commands（命令）、commit list（提交列表）和 changed files（变更文件），复制 `spec/design/tasks`（规格/设计/任务）快照，不再生成 `diff.patch`（差异补丁）。`reviewer prompt`（审查提示词）正文移到插件内模板文件，脚本只填充变量并写出 prompt artifact（提示词产物）。

**Tech Stack:** Python 3.12 standard library（标准库）、pytest（测试工具）、Git（版本控制）、Claude Agent SDK（开发包）子进程入口。

---

## File Structure

- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
  - 删除核心 `diff_file`（差异文件）参数。
  - 从 git commands（命令）生成 review subject（审查对象）和 manifest（清单）。
  - 从独立模板渲染 reviewer prompt（审查提示词）。
- Create: `plugins/cross-agent-review/skills/cross-agent-review/assets/templates/reviewer-prompt.md`
  - 保存可修改、可复用的 reviewer prompt（审查提示词）正文。
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`
  - 更新命令示例、输入准备、超时说明和禁止外层短 timeout（超时）包装。
- Modify: `tests/test_cross_agent_review_cli.py`
  - 按 TDD（测试驱动开发）更新 CLI（命令行接口）、manifest（清单）、prompt（提示词）和 timeout（超时）契约测试。
- Modify: `openspec/changes/refactor-cross-agent-review-input-contract/tasks.md`
  - 每个实现任务验证通过后勾选。

## Task 1: CLI No Longer Requires Diff File

**Files:**
- Modify: `tests/test_cross_agent_review_cli.py`
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`

- [x] **Step 1: Write the failing CLI test**

Update `review_args(...)` in `tests/test_cross_agent_review_cli.py` so it no longer passes `--diff-file`:

```python
def review_args(project: Path, head: str, output_dir: Path) -> list[str]:
    return [
        "run",
        "--change",
        "demo",
        "--base-ref",
        head,
        "--head-ref",
        head,
        "--spec-file",
        str(write_file(project / "spec.md")),
        "--design-file",
        str(write_file(project / "design.md")),
        "--tasks-file",
        str(write_file(project / "tasks.md")),
        "--output-dir",
        str(output_dir),
        "--fake-reviewer-results",
        "[]",
    ]
```

Add a focused test:

```python
def test_diff_file_argument_is_not_required(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)

    result = run(*review_args(project, head, tmp_path / "out"), cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_diff_file_argument_is_not_required -q
```

Expected before implementation: FAIL because `--diff-file`（差异文件） is still required by argparse（参数解析器） or `ReviewArgs`（审查参数）。

- [x] **Step 3: Remove `diff_file` from the CLI contract**

In `cross_agent_review.py`:

- Change `REQUIRED_FILE_ARGS` to:

```python
REQUIRED_FILE_ARGS = ["spec_file", "design_file", "tasks_file"]
```

- Change `INPUT_SNAPSHOT_NAMES` to:

```python
INPUT_SNAPSHOT_NAMES = {
    "spec_file": "spec.md",
    "design_file": "design.md",
    "tasks_file": "tasks.md",
}
```

- Remove `diff_file: Path` from `ReviewArgs`.
- Remove `run_parser.add_argument("--diff-file", type=Path, required=True)`.
- Remove `diff_file=args.diff_file` from `parse_review_args`.
- Remove `review_args.diff_file` from `allowed_input_paths`.

- [x] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_diff_file_argument_is_not_required -q
```

Expected after implementation: PASS.

## Task 2: Manifest Uses Git Commands Instead of Diff Patch

**Files:**
- Modify: `tests/test_cross_agent_review_cli.py`
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`

- [x] **Step 1: Write failing manifest test**

Replace `test_run_archives_review_input_snapshots_under_output_dir` with:

```python
def test_run_archives_context_snapshots_and_git_manifest_under_output_dir(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "one\ntwo\n")
    write_file(project / "new file.txt", "new\n")
    git(project, "add", "app.txt", "new file.txt")
    git(project, "commit", "-m", "change app")
    head = git(project, "rev-parse", "HEAD")
    input_dir = project / "review inputs"
    output_dir = tmp_path / "out"
    spec_file = write_file(input_dir / "spec file.md", "spec body\n")
    design_file = write_file(input_dir / "design file.md", "design body\n")
    tasks_file = write_file(input_dir / "tasks file.md", "tasks body\n")

    result = run(
        "run",
        "--change",
        "demo",
        "--base-ref",
        base,
        "--head-ref",
        head,
        "--spec-file",
        str(spec_file),
        "--design-file",
        str(design_file),
        "--tasks-file",
        str(tasks_file),
        "--output-dir",
        str(output_dir),
        "--fake-reviewer-results",
        "[]",
        cwd=project,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    inputs_dir = output_dir / "inputs"
    assert {path.name for path in inputs_dir.iterdir()} == {
        "manifest.json",
        "spec.md",
        "design.md",
        "tasks.md",
    }
    assert not (inputs_dir / "diff.patch").exists()
    manifest = json.loads((inputs_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["change"] == "demo"
    assert manifest["base_ref"] == base
    assert manifest["head_ref"] == head
    assert manifest["review_subject"]["diff_command"] == f"git diff {base}...{head}"
    assert manifest["review_subject"]["commit_list_command"] == f"git log {base}..{head} --oneline"
    assert manifest["review_subject"]["changed_files_command"] == f"git diff --name-status --find-renames --find-copies-harder {base}...{head}"
    assert manifest["review_subject"]["path_diff_command_template"] == f"git diff {base}...{head} -- <path>"
    assert manifest["review_subject"]["merge_base"] == base
    assert manifest["commits"] == [{"sha": head[:7], "summary": "change app"}]
    assert {"path": "app.txt", "status": "modified"} in manifest["changed_files"]
    assert {"path": "new file.txt", "status": "added"} in manifest["changed_files"]
    assert manifest["inputs"]["spec"]["path"] == "inputs/spec.md"
```

- [x] **Step 2: Run the manifest test to verify it fails**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_run_archives_context_snapshots_and_git_manifest_under_output_dir -q
```

Expected before implementation: FAIL because the old manifest still expects `diff.patch`（差异补丁）。

- [x] **Step 3: Implement git-based review subject helpers**

In `cross_agent_review.py`, add:

```python
STATUS_MAP = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
}


def git_command_text(args: Sequence[str]) -> str:
    return "git " + " ".join(shlex.quote(arg) for arg in args)


def review_subject_commands(review_args: ReviewArgs) -> dict[str, str]:
    base = review_args.base_ref
    head = review_args.head_ref
    return {
        "diff_command": git_command_text(["diff", f"{base}...{head}"]),
        "commit_list_command": git_command_text(["log", f"{base}..{head}", "--oneline"]),
        "changed_files_command": git_command_text(["diff", "--name-status", "--find-renames", "--find-copies-harder", f"{base}...{head}"]),
        "path_diff_command_template": git_command_text(["diff", f"{base}...{head}", "--", "<path>"]),
    }


def merge_base(review_args: ReviewArgs, cwd: Path) -> str:
    return git_output(["merge-base", review_args.base_ref, review_args.head_ref], cwd)
```

Add changed file parsing from `git diff --name-status --find-renames --find-copies-harder -z`:

```python
def changed_file_entries_from_git(review_args: ReviewArgs, cwd: Path) -> list[dict[str, str]]:
    output = git_output_bytes(["diff", "--name-status", "--find-renames", "--find-copies-harder", "-z", f"{review_args.base_ref}...{review_args.head_ref}"], cwd)
    parts = [part.decode("utf-8", errors="surrogateescape") for part in output.split(b"\0") if part]
    entries: list[dict[str, str]] = []
    index = 0
    while index < len(parts):
        status_token = parts[index]
        index += 1
        code = status_token[:1]
        status = STATUS_MAP.get(code, "modified")
        if code in {"R", "C"}:
            previous_path = parts[index]
            path = parts[index + 1]
            index += 2
            entries.append({"path": path, "status": status, "previous_path": previous_path})
            continue
        path = parts[index]
        index += 1
        entries.append({"path": path, "status": status})
    return entries
```

Add commit list parsing:

```python
def commit_entries(review_args: ReviewArgs, cwd: Path) -> list[dict[str, str]]:
    output = git_output(["log", f"{review_args.base_ref}..{review_args.head_ref}", "--oneline"], cwd)
    entries: list[dict[str, str]] = []
    for line in output.splitlines():
        sha, _, summary = line.partition(" ")
        if sha:
            entries.append({"sha": sha, "summary": summary})
    return entries
```

- [x] **Step 4: Update `build_input_manifest`**

Change `build_input_manifest(review_args)` to:

```python
def build_input_manifest(review_args: ReviewArgs) -> dict:
    cwd = Path.cwd()
    commands = review_subject_commands(review_args)
    return {
        "change": review_args.change,
        "base_ref": review_args.base_ref,
        "head_ref": review_args.head_ref,
        "review_subject": {
            **commands,
            "merge_base": merge_base(review_args, cwd),
        },
        "inputs": {
            "spec": input_file_metadata(review_args, review_args.spec_file),
            "design": input_file_metadata(review_args, review_args.design_file),
            "tasks": input_file_metadata(review_args, review_args.tasks_file),
        },
        "commits": commit_entries(review_args, cwd),
        "changed_files": changed_file_entries_from_git(review_args, cwd),
    }
```

- [x] **Step 5: Run the manifest test to verify it passes**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_run_archives_context_snapshots_and_git_manifest_under_output_dir -q
```

Expected after implementation: PASS.

## Task 3: Changed Files Cover Rename/Delete/Copy/Spaces

**Files:**
- Modify: `tests/test_cross_agent_review_cli.py`
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`

- [x] **Step 1: Replace diff parser test with git parser test**

Replace `test_changed_file_entries_from_diff_reports_file_statuses` with:

```python
def test_changed_file_entries_from_git_reports_file_statuses(tmp_path: Path) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "changed\n")
    write_file(project / "path with space.txt", "space\n")
    git(project, "mv", "app.txt", "renamed app.txt")
    write_file(project / "removed.txt", "removed\n")
    git(project, "add", "removed.txt")
    git(project, "commit", "-m", "prepare removal")
    removal_base = git(project, "rev-parse", "HEAD")
    (project / "removed.txt").unlink()
    write_file(project / "created.txt", "created\n")
    git(project, "add", "-A")
    git(project, "commit", "-m", "mixed changes")
    head = git(project, "rev-parse", "HEAD")
    review = module.ReviewArgs(
        change="demo",
        base_ref=removal_base,
        head_ref=head,
        spec_file=write_file(project / "spec.md"),
        design_file=write_file(project / "design.md"),
        tasks_file=write_file(project / "tasks.md"),
        output_dir=tmp_path / "out",
        sdk_python=None,
        fake_reviewer_results=None,
        disable_risk_review=None,
    )

    assert module.changed_file_entries_from_git(review, project) == [
        {"path": "created.txt", "status": "added"},
        {"path": "removed.txt", "status": "deleted"},
    ]
```

Add a second focused rename test:

```python
def test_changed_file_entries_from_git_reports_renames_and_spaces(tmp_path: Path) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    base = init_repo(project)
    git(project, "mv", "app.txt", "renamed app.txt")
    write_file(project / "path with space.txt", "space\n")
    git(project, "add", "-A")
    git(project, "commit", "-m", "rename and space")
    head = git(project, "rev-parse", "HEAD")
    review = module.ReviewArgs(
        change="demo",
        base_ref=base,
        head_ref=head,
        spec_file=write_file(project / "spec.md"),
        design_file=write_file(project / "design.md"),
        tasks_file=write_file(project / "tasks.md"),
        output_dir=tmp_path / "out",
        sdk_python=None,
        fake_reviewer_results=None,
        disable_risk_review=None,
    )

    assert module.changed_file_entries_from_git(review, project) == [
        {"path": "renamed app.txt", "status": "renamed", "previous_path": "app.txt"},
        {"path": "path with space.txt", "status": "added"},
    ]
```

- [x] **Step 2: Run changed-file tests**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_changed_file_entries_from_git_reports_file_statuses tests/test_cross_agent_review_cli.py::test_changed_file_entries_from_git_reports_renames_and_spaces -q
```

Expected: FAIL until `changed_file_entries_from_git` exists and correctly parses `-z` output; PASS after Task 2 implementation is corrected.

## Task 4: Extract Reviewer Prompt Template

**Files:**
- Create: `plugins/cross-agent-review/skills/cross-agent-review/assets/templates/reviewer-prompt.md`
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`
- Modify: `tests/test_cross_agent_review_cli.py`

- [x] **Step 1: Write failing template source test**

Add:

```python
def test_reviewer_prompt_template_is_loaded_from_file(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)
    template = tmp_path / "reviewer-prompt.md"
    template.write_text("Template marker: {{ role }} / {{ manifest_path }}\n", encoding="utf-8")
    monkeypatch.setattr(module, "REVIEWER_PROMPT_TEMPLATE", template)

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert f"Template marker: spec-alignment / {review.output_dir / 'inputs' / 'manifest.json'}" in prompt
```

- [x] **Step 2: Run template source test**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_reviewer_prompt_template_is_loaded_from_file -q
```

Expected before implementation: FAIL because `reviewer_prompt`（审查提示词） is hardcoded.

- [x] **Step 3: Add template file**

Create `plugins/cross-agent-review/skills/cross-agent-review/assets/templates/reviewer-prompt.md`:

```markdown
Role: {{ role }}

Return only a single JSON object. Do not use Markdown.

Schema:
{{ schema_json }}

Use only these severity values: CRITICAL, IMPORTANT, WARNING, SUGGESTION.
If there are no issues, return "findings": [].
Do not put pass, aligned, ok, or informational observations in findings.
Do not use severity aliases such as high, medium, low, minor, or info.

{{ severity_rubric }}

{{ role_focus }}

Change: {{ change }}
Base ref: {{ base_ref }}
Head ref: {{ head_ref }}
Manifest file: {{ manifest_path }}

Review subject commands:
{{ review_subject_commands }}

Changed files:
{{ changed_files }}

Context files:
{{ context_files }}

Use the manifest and referenced context files as the source of truth.
Do not read a complete diff output. For implementation review, use changed files and path-scoped commands such as:
{{ path_diff_command_template }}

Use git diff/show/status read-only commands if the file references are insufficient.
```

- [x] **Step 4: Implement simple template rendering**

In `cross_agent_review.py`, add constants:

```python
SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
REVIEWER_PROMPT_TEMPLATE = SKILL_ROOT / "assets" / "templates" / "reviewer-prompt.md"
```

Add:

```python
def render_template(path: Path, values: dict[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{ " + key + " }}", value)
    return text
```

Refactor `reviewer_prompt` to build values and call `render_template(...)`.

- [x] **Step 5: Run template source test**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_reviewer_prompt_template_is_loaded_from_file -q
```

Expected after implementation: PASS.

## Task 5: Prompt Uses Manifest Commands and Does Not Inline Diff Output

**Files:**
- Modify: `tests/test_cross_agent_review_cli.py`
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/scripts/cross_agent_review.py`

- [x] **Step 1: Update prompt tests**

Replace `test_reviewer_prompt_includes_all_review_inputs` with:

```python
def test_reviewer_prompt_includes_review_subject_commands_not_diff_file(tmp_path: Path) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "one\ntwo\n")
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "change app")
    head = git(project, "rev-parse", "HEAD")
    review = module.ReviewArgs(
        change="demo-change",
        base_ref=base,
        head_ref=head,
        spec_file=write_file(project / "spec.md", "Spec body\n"),
        design_file=write_file(project / "design.md", "Design body\n"),
        tasks_file=write_file(project / "tasks.md", "Tasks body\n"),
        output_dir=tmp_path / "out",
        sdk_python=None,
        fake_reviewer_results=None,
        disable_risk_review=None,
    )

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert "Role: spec-alignment" in prompt
    assert "Return only a single JSON object. Do not use Markdown." in prompt
    assert "Change: demo-change" in prompt
    assert f"Base ref: {base}" in prompt
    assert f"Head ref: {head}" in prompt
    assert f"git diff {base}...{head}" in prompt
    assert f"git log {base}..{head} --oneline" in prompt
    assert f"git diff --name-status --find-renames --find-copies-harder {base}...{head}" in prompt
    assert f"git diff {base}...{head} -- <path>" in prompt
    assert "Diff file:" not in prompt
    assert "diff.patch" not in prompt
    assert "Spec body" not in prompt
    assert "Tasks:" not in prompt
```

Replace `test_reviewer_prompt_does_not_inline_large_inputs` with:

```python
def test_reviewer_prompt_does_not_inline_large_diff_or_context(tmp_path: Path) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    base = init_repo(project)
    write_file(project / "app.txt", "one\n" + ("changed\n" * 2000))
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "large change")
    head = git(project, "rev-parse", "HEAD")
    review = module.ReviewArgs(
        change="demo-change",
        base_ref=base,
        head_ref=head,
        spec_file=write_file(project / "spec.md", "Spec body\n" * 1000),
        design_file=write_file(project / "design.md", "Design body\n" * 1000),
        tasks_file=write_file(project / "tasks.md", "Tasks body\n" * 1000),
        output_dir=tmp_path / "out",
        sdk_python=None,
        fake_reviewer_results=None,
        disable_risk_review=None,
    )

    prompt = module.reviewer_prompt(review, "implementation-correctness")

    assert "changed\nchanged\n" not in prompt
    assert "Spec body" not in prompt
    assert "Design body" not in prompt
    assert "Tasks body" not in prompt
    assert "diff.patch" not in prompt
    assert len(prompt) < 5000
```

- [x] **Step 2: Run prompt tests**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_reviewer_prompt_includes_review_subject_commands_not_diff_file tests/test_cross_agent_review_cli.py::test_reviewer_prompt_does_not_inline_large_diff_or_context -q
```

Expected before prompt refactor completion: FAIL. Expected after Task 4 and values update: PASS.

- [x] **Step 3: Update prompt value helpers**

Add:

```python
def changed_files_prompt(review_args: ReviewArgs, limit: int = 160) -> str:
    entries = changed_file_entries_from_git(review_args, Path.cwd())
    shown = entries[:limit]
    lines = []
    for entry in shown:
        prefix = entry["status"]
        previous = f" (from {entry['previous_path']})" if entry.get("previous_path") else ""
        lines.append(f"- {prefix}: {entry['path']}{previous}")
    if len(entries) > limit:
        lines.append(f"- ... {len(entries) - limit} more")
    return "\n".join(lines) if lines else "- <none>"
```

Add:

```python
def context_file_references(review_args: ReviewArgs) -> str:
    return "\n".join(
        [
            input_reference("Spec", review_args.spec_file),
            input_reference("Design", review_args.design_file),
            input_reference("Tasks", review_args.tasks_file),
        ]
    )
```

Use these helpers in `reviewer_prompt`.

## Task 6: Skill Documentation and Timeout Contract

**Files:**
- Modify: `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md`
- Modify: `tests/test_cross_agent_review_cli.py`

- [x] **Step 1: Write failing documentation contract test**

Add:

```python
def test_skill_docs_describe_review_subject_and_no_outer_timeout() -> None:
    text = (
        REPO_ROOT
        / "plugins"
        / "cross-agent-review"
        / "skills"
        / "cross-agent-review"
        / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert "--diff-file" not in text
    assert "diff.patch" not in text
    assert "git diff <base-ref>...<head-ref>" in text
    assert "git log <base-ref>..<head-ref> --oneline" in text
    assert "不得再包装外部短 `timeout`" in text
    assert "480 秒" in text
    assert "540 秒" in text
```

- [x] **Step 2: Run documentation test**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_skill_docs_describe_review_subject_and_no_outer_timeout -q
```

Expected before docs update: FAIL because docs still show `--diff-file`（差异文件）.

- [x] **Step 3: Update `SKILL.md`**

Update command example to remove `--diff-file` and add:

```markdown
## Review Subject（审查对象）

`--base-ref` 是调用方明确提供的 fixed point（固定点），可以是 commit（提交）、branch（分支）、tag（标签）、`main` 或 `HEAD~5`。如果调用方没有明确 fixed point（固定点），先询问用户，不得自行猜测。

审查范围由以下命令复现：

```bash
git diff <base-ref>...<head-ref>
git log <base-ref>..<head-ref> --oneline
git diff --name-status --find-renames --find-copies-harder <base-ref>...<head-ref>
git diff <base-ref>...<head-ref> -- <path>
```

系统不生成、不保存、不传递 `diff.patch`（差异补丁）。
```

Add timeout section:

```markdown
## 超时边界

插件内部脚本管理 timeout（超时）：

- 单个 reviewer（审查者）：480 秒。
- 整体 SDK dispatch（开发包派发）：540 秒。

主 agent（代理）调用本插件时必须直接等待 Python（脚本）返回，不得再包装外部短 `timeout`（超时）、watchdog（看门等待）或等价提前终止逻辑。
```

- [x] **Step 4: Run documentation test**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py::test_skill_docs_describe_review_subject_and_no_outer_timeout -q
```

Expected after docs update: PASS.

## Task 7: Full Regression and OpenSpec Task Closure

**Files:**
- Modify: `openspec/changes/refactor-cross-agent-review-input-contract/tasks.md`

- [x] **Step 1: Run focused cross-agent-review tests**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_cli.py -q
```

Expected: PASS.

- [x] **Step 2: Run package test for included template asset**

Run:

```powershell
python -m pytest tests/test_cross_agent_review_plugin_package.py tests/test_cross_agent_review_cli.py -q
```

Expected: PASS. If package tests do not yet assert template packaging, add a focused assertion that `assets/templates/reviewer-prompt.md` exists.

- [x] **Step 3: Run OpenSpec validation**

Run:

```powershell
openspec validate refactor-cross-agent-review-input-contract --strict
```

Expected: `Change 'refactor-cross-agent-review-input-contract' is valid`.

- [x] **Step 4: Check off OpenSpec tasks**

After the tests and validation above pass, update `openspec/changes/refactor-cross-agent-review-input-contract/tasks.md` so each completed `- [ ]` becomes `- [x]`.

- [x] **Step 5: Run build check if available**

Run:

```powershell
bash .comet/build-check.sh
```

Expected: PASS.

## Self-Review

- Spec coverage: Tasks 1-3 cover review subject（审查对象）、manifest（清单） and no `diff.patch`（差异补丁）. Tasks 4-5 cover prompt template（提示词模板） and no inline diff/context. Task 6 covers timeout（超时） and skill docs（技能说明）. Task 7 covers validation and closure.
- Placeholder scan: Plan uses concrete file paths, test names, commands, expected failures and expected passes.
- Type consistency: `ReviewArgs`（审查参数） no longer includes `diff_file`（差异文件）; helpers consistently use `base_ref`（基线引用）、`head_ref`（头引用） and context file paths.
