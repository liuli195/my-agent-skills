import asyncio
import json
import io
import importlib.util
import subprocess
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "cross-agent-review"
    / "skills"
    / "cross-agent-review"
    / "scripts"
    / "cross_agent_review.py"
)


def load_script_module():
    spec = importlib.util.spec_from_file_location("cross_agent_review", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd or REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def write_file(path: Path, text: str = "content\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_required_args_fail() -> None:
    result = run("run", "--change", "demo")

    assert result.returncode == 2
    assert "error:" in result.stderr


def test_missing_input_file_fails(tmp_path: Path) -> None:
    result = run(
        "run",
        "--change",
        "demo",
        "--base-ref",
        "base",
        "--head-ref",
        "head",
        "--diff-file",
        str(tmp_path / "missing.diff"),
        "--spec-file",
        str(write_file(tmp_path / "spec.md")),
        "--design-file",
        str(write_file(tmp_path / "design.md")),
        "--tasks-file",
        str(write_file(tmp_path / "tasks.md")),
        "--tests-file",
        str(write_file(tmp_path / "tests.txt")),
        "--fake-reviewer-results",
        "[]",
    )

    assert result.returncode == 1
    assert "missing_file" in result.stdout


def git(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def init_repo(project: Path) -> str:
    project.mkdir()
    git(project, "init")
    git(project, "config", "user.email", "test@example.invalid")
    git(project, "config", "user.name", "Test User")
    write_file(project / "app.txt", "one\n")
    git(project, "add", "app.txt")
    git(project, "commit", "-m", "initial")
    return git(project, "rev-parse", "HEAD")


def review_args(project: Path, head: str, output_dir: Path) -> list[str]:
    return [
        "run",
        "--change",
        "demo",
        "--base-ref",
        head,
        "--head-ref",
        head,
        "--diff-file",
        str(write_file(project / "diff.patch")),
        "--spec-file",
        str(write_file(project / "spec.md")),
        "--design-file",
        str(write_file(project / "design.md")),
        "--tasks-file",
        str(write_file(project / "tasks.md")),
        "--tests-file",
        str(write_file(project / "tests.txt")),
        "--output-dir",
        str(output_dir),
        "--fake-reviewer-results",
        "[]",
    ]


def make_review_args_for_module(module, tmp_path: Path):
    return module.ReviewArgs(
        change="demo",
        base_ref="base",
        head_ref="head",
        diff_file=write_file(tmp_path / "diff.patch"),
        spec_file=write_file(tmp_path / "spec.md"),
        design_file=write_file(tmp_path / "design.md"),
        tasks_file=write_file(tmp_path / "tasks.md"),
        tests_file=write_file(tmp_path / "tests.txt"),
        output_dir=tmp_path / "out",
        sdk_python=None,
        fake_reviewer_results=None,
        disable_risk_review=None,
    )


def test_dirty_worktree_rejects_before_dispatch(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    write_file(tmp_path / "repo" / "dirty.txt", "dirty\n")

    result = run(*review_args(tmp_path / "repo", head, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 1
    assert "dirty_worktree" in result.stdout
    assert not (tmp_path / "out" / "review-pass.json").exists()


def test_untracked_input_files_in_space_directory_are_allowed(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_dir = project / "review inputs"

    result = run(
        "run",
        "--change",
        "demo",
        "--base-ref",
        head,
        "--head-ref",
        head,
        "--diff-file",
        str(write_file(input_dir / "change diff.patch")),
        "--spec-file",
        str(write_file(input_dir / "spec file.md")),
        "--design-file",
        str(write_file(input_dir / "design file.md")),
        "--tasks-file",
        str(write_file(input_dir / "tasks file.md")),
        "--tests-file",
        str(write_file(input_dir / "tests file.txt")),
        "--output-dir",
        str(tmp_path / "out"),
        "--fake-reviewer-results",
        "[]",
        cwd=project,
    )

    assert result.returncode == 0
    assert "status: pass" in result.stdout


def test_head_mismatch_rejects_before_dispatch(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(*review_args(tmp_path / "repo", "0" * 40, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 1
    assert "head_ref_mismatch" in result.stdout
    assert head != "0" * 40


def test_sdk_missing_reports_clear_error(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    missing_python = tmp_path / "missing-python.exe"

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--sdk-python",
        str(missing_python),
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert "sdk_unavailable" in result.stdout


def test_sdk_python_directory_reports_clear_error_without_traceback(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    sdk_dir = tmp_path / "not-python"
    sdk_dir.mkdir()

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--sdk-python",
        str(sdk_dir),
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert "sdk_unavailable" in result.stdout
    assert "Traceback" not in result.stderr


def test_sdk_python_invalid_file_reports_clear_error_without_traceback(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    invalid_python = write_file(tmp_path / "not-python.exe", "not a real executable\n")

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--sdk-python",
        str(invalid_python),
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert "sdk_unavailable" in result.stdout
    assert "Traceback" not in result.stderr


def test_fake_reviewer_results_bypass_real_sdk_for_tests(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(*review_args(tmp_path / "repo", head, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 0, result.stdout + result.stderr


def test_run_archives_review_input_snapshots_under_output_dir(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    head = init_repo(project)
    input_dir = project / "review inputs"
    output_dir = tmp_path / "out"
    diff_file = write_file(input_dir / "change diff.patch", "diff body\n")
    spec_file = write_file(input_dir / "spec file.md", "spec body\n")
    design_file = write_file(input_dir / "design file.md", "design body\n")
    tasks_file = write_file(input_dir / "tasks file.md", "tasks body\n")
    tests_file = write_file(input_dir / "tests file.txt", "tests body\n")

    result = run(
        "run",
        "--change",
        "demo",
        "--base-ref",
        head,
        "--head-ref",
        head,
        "--diff-file",
        str(diff_file),
        "--spec-file",
        str(spec_file),
        "--design-file",
        str(design_file),
        "--tasks-file",
        str(tasks_file),
        "--tests-file",
        str(tests_file),
        "--output-dir",
        str(output_dir),
        "--fake-reviewer-results",
        "[]",
        cwd=project,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    inputs_dir = output_dir / "inputs"
    assert (inputs_dir / "diff.patch").read_text(encoding="utf-8") == "diff body\n"
    assert (inputs_dir / "spec.md").read_text(encoding="utf-8") == "spec body\n"
    assert (inputs_dir / "design.md").read_text(encoding="utf-8") == "design body\n"
    assert (inputs_dir / "tasks.md").read_text(encoding="utf-8") == "tasks body\n"
    assert (inputs_dir / "tests.txt").read_text(encoding="utf-8") == "tests body\n"


def test_prompt_contains_review_context(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    args = review_args(tmp_path / "repo", head, tmp_path / "out")
    result = run(*args, "--fake-reviewer-results", "[]", cwd=tmp_path / "repo")

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path / "out" / "review-results.json").read_text(encoding="utf-8"))
    assert data["readonly_tools"]


def test_reviewer_prompt_includes_all_review_inputs(tmp_path: Path) -> None:
    module = load_script_module()
    project = tmp_path / "repo"
    head = init_repo(project)
    diff_file = write_file(project / "diff.patch", "diff --git a/app.txt b/app.txt\n")
    spec_file = write_file(project / "spec.md", "Spec body\n")
    design_file = write_file(project / "design.md", "Design body\n")
    tasks_file = write_file(project / "tasks.md", "Tasks body\n")
    tests_file = write_file(project / "tests.txt", "Tests body\n")
    review = module.ReviewArgs(
        change="demo-change",
        base_ref=head,
        head_ref=head,
        diff_file=diff_file,
        spec_file=spec_file,
        design_file=design_file,
        tasks_file=tasks_file,
        tests_file=tests_file,
        output_dir=tmp_path / "out",
        sdk_python=None,
        fake_reviewer_results=None,
        disable_risk_review=None,
    )

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert "Role: spec-alignment" in prompt
    assert "Return only a single JSON object. Do not use Markdown." in prompt
    assert "Change: demo-change" in prompt
    assert f"Base ref: {head}" in prompt
    assert f"Head ref: {head}" in prompt
    assert "Diff:\ndiff --git a/app.txt b/app.txt\n" in prompt
    assert "Spec:\nSpec body\n" in prompt
    assert "Design:\nDesign body\n" in prompt
    assert "Tasks:\nTasks body\n" in prompt
    assert "Tests:\nTests body\n" in prompt


def test_reviewer_prompt_requires_strict_json_contract(tmp_path: Path) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)

    prompt = module.reviewer_prompt(review, "spec-alignment")

    assert "Return only a single JSON object. Do not use Markdown." in prompt
    assert "Use only these severity values: CRITICAL, IMPORTANT, WARNING, SUGGESTION." in prompt
    assert 'If there are no issues, return "findings": []' in prompt
    assert "Do not put pass, aligned, ok, or informational observations in findings." in prompt
    assert "Do not use severity aliases such as high, medium, low, minor, or info." in prompt


def test_fake_reviewer_results_reject_non_dict_items(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        json.dumps(["not a reviewer"]),
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert "invalid_fake_reviewer_results" in result.stdout


def test_fake_reviewer_results_reject_missing_required_fields(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        json.dumps([{"role": "spec-alignment", "status": "completed"}]),
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert "invalid_fake_reviewer_results" in result.stdout


def test_reviewer_roles_are_recorded_in_results(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    fake = json.dumps(
        [
            {"role": "spec-alignment", "status": "completed", "findings": []},
            {"role": "implementation-correctness", "status": "completed", "findings": []},
            {"role": "tests-and-edge-cases", "status": "completed", "findings": []},
            {"role": "risk-review", "status": "completed", "findings": []},
        ]
    )

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        fake,
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path / "out" / "review-results.json").read_text(encoding="utf-8"))
    assert [item["role"] for item in data["reviewers"]] == [
        "spec-alignment",
        "implementation-correctness",
        "tests-and-edge-cases",
        "risk-review",
    ]
    assert "Edit" not in data["readonly_tools"]
    assert "Write" not in data["readonly_tools"]


def test_sdk_dispatch_disallows_write_and_execution_tools(monkeypatch, capsys) -> None:
    module = load_script_module()
    captured_options = []

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            captured_options.append(kwargs)

    async def fake_query(*, prompt, options):
        class Message:
            result = json.dumps({"role": "spec-alignment", "status": "completed", "findings": []})

        yield Message()

    fake_sdk = types.SimpleNamespace(ClaudeAgentOptions=FakeClaudeAgentOptions, query=fake_query)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "cwd": str(REPO_ROOT),
                    "roles": ["spec-alignment"],
                    "readonly_tools": ["Read", "Grep"],
                    "prompts": {"spec-alignment": "prompt"},
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    capsys.readouterr()
    assert captured_options
    disallowed = set(captured_options[0]["disallowed_tools"])
    assert {"Edit", "Write", "NotebookEdit", "TodoWrite", "Bash"} <= disallowed


def test_sdk_dispatch_accepts_json_wrapped_in_markdown_fence(monkeypatch, capsys) -> None:
    module = load_script_module()

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            pass

    async def fake_query(*, prompt, options):
        class Message:
            result = (
                "```json\n"
                + json.dumps({"role": "spec-alignment", "status": "completed", "findings": []})
                + "\n```"
            )

        yield Message()

    fake_sdk = types.SimpleNamespace(ClaudeAgentOptions=FakeClaudeAgentOptions, query=fake_query)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "cwd": str(REPO_ROOT),
                    "roles": ["spec-alignment"],
                    "readonly_tools": ["Read", "Grep"],
                    "prompts": {"spec-alignment": "prompt"},
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    data = json.loads(capsys.readouterr().out)
    assert data == [{"role": "spec-alignment", "status": "completed", "findings": []}]


def test_sdk_dispatch_reports_reviewer_timeout(monkeypatch, capsys) -> None:
    module = load_script_module()

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            pass

    async def fake_query(*, prompt, options):
        class Message:
            result = json.dumps({"role": "spec-alignment", "status": "completed", "findings": []})

        yield Message()

    async def fake_wait_for(awaitable, timeout):
        assert timeout == 480
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise asyncio.TimeoutError

    fake_sdk = types.SimpleNamespace(ClaudeAgentOptions=FakeClaudeAgentOptions, query=fake_query)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "cwd": str(REPO_ROOT),
                    "roles": ["spec-alignment"],
                    "readonly_tools": ["Read", "Grep"],
                    "prompts": {"spec-alignment": "prompt"},
                }
            )
        ),
    )

    assert module.run_sdk_dispatch() == 0

    data = json.loads(capsys.readouterr().out)
    assert data == [
        {
            "role": "spec-alignment",
            "status": "failed",
            "findings": [
                {
                    "severity": "CRITICAL",
                    "location": "spec-alignment",
                    "summary": "Reviewer timed out",
                    "evidence": "Exceeded 480 seconds.",
                    "recommendation": "Rerun review after checking Claude Agent SDK availability.",
                }
            ],
        }
    ]


def test_sdk_dispatch_subprocess_timeout_reports_clear_error(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)
    captured_timeout = None

    def fake_run(*args, **kwargs):
        nonlocal captured_timeout
        captured_timeout = kwargs["timeout"]
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    try:
        module.run_sdk_dispatch_subprocess(review, sys.executable)
    except ValueError as exc:
        assert "sdk_dispatch_timeout" in str(exc)
    else:
        raise AssertionError("expected sdk_dispatch_timeout")
    assert captured_timeout == 600


def test_sdk_dispatch_subprocess_invalid_stdout_reports_clear_error(tmp_path: Path, monkeypatch) -> None:
    module = load_script_module()
    review = make_review_args_for_module(module, tmp_path)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="not json", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    try:
        module.run_sdk_dispatch_subprocess(review, sys.executable)
    except ValueError as exc:
        assert "sdk_dispatch_invalid_output" in str(exc)
        assert "stdout was not valid JSON" in str(exc)
    else:
        raise AssertionError("expected sdk_dispatch_invalid_output")


def test_non_blocking_findings_generate_pass_marker(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    fake = json.dumps(
        [
            {
                "role": "spec-alignment",
                "status": "completed",
                "findings": [
                    {
                        "severity": "WARNING",
                        "location": "app.txt:1",
                        "summary": "Minor issue",
                        "evidence": "Evidence",
                        "recommendation": "Recommendation",
                    }
                ],
            }
        ]
    )

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        fake,
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "out" / "review-report.md").is_file()
    assert (tmp_path / "out" / "review-results.json").is_file()
    assert (tmp_path / "out" / "review-pass.json").is_file()


def test_blocking_findings_do_not_generate_pass_marker(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    fake = json.dumps(
        [
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
        ]
    )

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        fake,
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    assert (tmp_path / "out" / "review-report.md").is_file()
    assert (tmp_path / "out" / "review-results.json").is_file()
    assert not (tmp_path / "out" / "review-pass.json").exists()


def test_blocking_findings_remove_stale_pass_marker_from_reused_output_dir(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    output_dir = tmp_path / "out"
    head = init_repo(project)

    clean_result = run(*review_args(project, head, output_dir), cwd=project)

    assert clean_result.returncode == 0, clean_result.stdout + clean_result.stderr
    assert (output_dir / "review-pass.json").is_file()

    blocking_fake = json.dumps(
        [
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
        ]
    )

    blocking_result = run(
        *review_args(project, head, output_dir),
        "--fake-reviewer-results",
        blocking_fake,
        cwd=project,
    )

    assert blocking_result.returncode == 1
    assert not (output_dir / "review-pass.json").exists()


def test_report_hash_matches_report(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    result = run(*review_args(tmp_path / "repo", head, tmp_path / "out"), cwd=tmp_path / "repo")

    assert result.returncode == 0, result.stdout + result.stderr
    report = (tmp_path / "out" / "review-report.md").read_bytes()
    marker = json.loads((tmp_path / "out" / "review-pass.json").read_text(encoding="utf-8"))
    import hashlib

    assert marker["report_hash"] == hashlib.sha256(report).hexdigest()
    assert marker["head_ref"] == head


def test_duplicate_findings_are_counted_once(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    finding = {
        "severity": "IMPORTANT",
        "location": "app.txt:1",
        "summary": "Duplicate",
        "evidence": "Evidence",
        "recommendation": "Fix",
    }
    fake = json.dumps(
        [
            {"role": "spec-alignment", "status": "completed", "findings": [finding]},
            {"role": "implementation-correctness", "status": "completed", "findings": [finding]},
        ]
    )

    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--fake-reviewer-results",
        fake,
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 1
    data = json.loads((tmp_path / "out" / "review-results.json").read_text(encoding="utf-8"))
    assert data["blocking_findings"] == 1


def test_aggregate_blocks_findings_without_severity() -> None:
    module = load_script_module()

    summary = module.aggregate(
        [
            {
                "role": "implementation-correctness",
                "status": "pass",
                "findings": [
                    {
                        "location": "app.txt:1",
                        "issue": None,
                        "detail": "Reviewed behavior matches the spec.",
                    }
                ],
            }
        ],
        [],
    )

    assert summary["blocking_findings"] == 1
    assert summary["findings"][0]["severity"] == "CRITICAL"
    assert summary["findings"][0]["summary"] == "Reviewer output missing severity"


def test_aggregate_blocks_aligned_records_inside_findings() -> None:
    module = load_script_module()

    summary = module.aggregate(
        [
            {
                "role": "spec-alignment",
                "status": "aligned",
                "findings": [
                    {
                        "requirement": "Plugin package",
                        "status": "aligned",
                        "evidence": "Manifest and skill entrypoints match the spec.",
                    }
                ],
            }
        ],
        [],
    )

    assert summary["blocking_findings"] == 1
    assert summary["findings"][0]["severity"] == "CRITICAL"
    assert summary["findings"][0]["summary"] == "Reviewer output missing severity"


def test_aggregate_blocks_severity_aliases() -> None:
    module = load_script_module()

    summary = module.aggregate(
        [
            {
                "role": "tests-and-edge-cases",
                "status": "pass-with-findings",
                "findings": [
                    {"severity": "minor", "area": "docs", "description": "Tiny wording note."},
                    {"severity": "medium", "area": "tests", "description": "Add an edge test.", "suggestion": "Cover the boundary."},
                    {"severity": "low", "area": "docs", "description": "Clarify wording.", "suggestion": "Tighten the text."},
                    {"severity": "info", "file": "app.py", "line": 3, "message": "No risk."},
                ],
            }
        ],
        [],
    )

    assert summary["blocking_findings"] == 4
    assert [finding["severity"] for finding in summary["findings"]] == ["CRITICAL", "CRITICAL", "CRITICAL", "CRITICAL"]
    assert {finding["summary"] for finding in summary["findings"]} == {
        "Reviewer output used invalid severity: minor",
        "Reviewer output used invalid severity: medium",
        "Reviewer output used invalid severity: low",
        "Reviewer output used invalid severity: info",
    }


def test_aggregate_treats_pass_dict_findings_with_no_issues_as_non_blocking() -> None:
    module = load_script_module()

    summary = module.aggregate(
        [
            {
                "role": "implementation-correctness",
                "status": "pass",
                "findings": {
                    "spec_compliance": {"verdict": "pass", "details": "Matches spec."},
                    "issues": [],
                },
            }
        ],
        [],
    )

    assert summary["blocking_findings"] == 0
    assert summary["findings"] == []


def test_aggregate_blocks_dict_gaps_with_severity_aliases() -> None:
    module = load_script_module()

    summary = module.aggregate(
        [
            {
                "role": "tests-and-edge-cases",
                "status": "pass_with_gaps",
                "findings": {
                    "summary": "Coverage is acceptable with gaps.",
                    "gaps": [
                        {
                            "severity": "medium",
                            "area": "manifest",
                            "detail": "Missing required-field tests.",
                            "recommendation": "Add one regression test.",
                        },
                        {
                            "severity": "low",
                            "area": "cli",
                            "detail": "Unknown command path is not covered.",
                        },
                    ],
                },
            }
        ],
        [],
    )

    assert summary["blocking_findings"] == 2
    assert [finding["severity"] for finding in summary["findings"]] == ["CRITICAL", "CRITICAL"]
    assert {finding["summary"] for finding in summary["findings"]} == {
        "Reviewer output used invalid severity: medium",
        "Reviewer output used invalid severity: low",
    }


def test_risk_review_skip_is_recorded(tmp_path: Path) -> None:
    head = init_repo(tmp_path / "repo")
    result = run(
        *review_args(tmp_path / "repo", head, tmp_path / "out"),
        "--disable-risk-review",
        "low-risk-doc-only",
        cwd=tmp_path / "repo",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path / "out" / "review-results.json").read_text(encoding="utf-8"))
    assert data["skipped_reviewers"] == [{"role": "risk-review", "reason": "low-risk-doc-only"}]
