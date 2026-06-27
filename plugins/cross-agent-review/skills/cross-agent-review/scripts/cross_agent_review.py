from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
REVIEWER_PROMPT_TEMPLATE = SKILL_ROOT / "assets" / "templates" / "reviewer-prompt.md"
REQUIRED_INPUT_FIELDS = ["change", "mode", "base_ref", "head_ref", "spec_file", "design_file", "plan_file"]
VALID_MODES = {"convergence", "endless"}
REVIEWER_ROLES = [
    "spec-alignment",
    "implementation-correctness",
]
ROLE_FOCUS = {
    "spec-alignment": "\n".join(
        [
            "Focus for spec-alignment:",
            "- Compare the supplied spec, design, plan, and changed files for requirement drift.",
            "- Report missing required behavior, scope creep, or contradictions between artifacts.",
            "- Do not review implementation style unless it changes the promised behavior.",
        ]
    ),
    "implementation-correctness": "\n".join(
        [
            "Focus for implementation-correctness:",
            "- Review changed implementation paths for concrete correctness bugs.",
            "- Use path-scoped diffs and source reads; do not read large input files wholesale.",
            "- Report only issues with executable behavior, data flow, state handling, or compatibility.",
        ]
    ),
}
SEVERITY_RUBRIC = "\n".join(
    [
        "Severity rubric:",
        "- CRITICAL: likely data loss, security exposure, broken required workflow, or reviewer/tool failure.",
        "- IMPORTANT: concrete regression, missing required scenario, or edge case likely to break normal use.",
        "- WARNING: plausible risk or coverage gap with limited/uncertain impact.",
        "- SUGGESTION: maintainability or clarity improvement that should not block.",
    ]
)
SDK_DISPATCH_TIMEOUT_SECONDS = 540
SDK_REVIEWER_TIMEOUT_SECONDS = 480
DEFAULT_PROFILE_ID = "comet-review-gate"
DEFAULT_ARTIFACT_ID = "cross_agent_review_pass"
DEFAULT_SUBJECT_TYPE = "comet-change"


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


@dataclass(frozen=True)
class StatusEntry:
    xy: str
    path: Path
    old_path: Path | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cross_agent_review.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--input-file", type=Path, required=True)
    run_parser.add_argument("--debug", action="store_true")
    run_parser.add_argument("--sdk-python", type=Path)
    run_parser.add_argument("--fake-reviewer-results")
    mark_parser = subparsers.add_parser("mark-pass")
    mark_parser.add_argument("--input-file", type=Path, required=True)
    mark_parser.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    mark_parser.add_argument("--artifact-id", default=DEFAULT_ARTIFACT_ID)
    mark_parser.add_argument("--subject-id")
    mark_parser.add_argument("--subject-type", default=DEFAULT_SUBJECT_TYPE)
    subparsers.add_parser("_sdk-dispatch")
    return parser


def git_output(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise ValueError(f"git_failed: {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def git_output_bytes(args: list[str], cwd: Path) -> bytes:
    result = subprocess.run(["git", *args], cwd=cwd, check=False, capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"git_failed: {' '.join(args)}: {stderr}")
    return result.stdout


def status_entries(cwd: Path) -> list[StatusEntry]:
    entries_by_status: list[StatusEntry] = []
    output = git_output_bytes(["status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd)
    entries = output.split(b"\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        xy = entry[:2].decode("ascii", errors="replace")
        path_text = entry[3:].decode("utf-8", errors="surrogateescape")
        path = (cwd / path_text).resolve()
        old_path = None
        if entry[:1] in {b"R", b"C"} or entry[1:2] in {b"R", b"C"}:
            if index < len(entries) and entries[index]:
                old_path_text = entries[index].decode("utf-8", errors="surrogateescape")
                old_path = (cwd / old_path_text).resolve()
            index += 1
        entries_by_status.append(StatusEntry(xy=xy, path=path, old_path=old_path))
    return entries_by_status


def status_entry_paths(entry: StatusEntry) -> list[Path]:
    paths = [entry.path]
    if entry.old_path is not None:
        paths.append(entry.old_path)
    return paths


def status_entry_is_allowed(entry: StatusEntry, allowed: set[Path]) -> bool:
    if entry.xy != "??":
        return False
    return all(path_is_allowed(path, allowed) for path in status_entry_paths(entry))


def path_is_allowed(path: Path, allowed: set[Path]) -> bool:
    return path.resolve() in allowed


def ensure_clean_subject(cwd: Path, head_ref: str, allowed_dirty_paths: Sequence[Path] = ()) -> None:
    allowed = {path.resolve() for path in allowed_dirty_paths}
    dirty_entries = [
        entry for entry in status_entries(cwd) if not status_entry_is_allowed(entry, allowed)
    ]
    if dirty_entries:
        raise ValueError("dirty_worktree")
    current_head = git_output(["rev-parse", "HEAD"], cwd)
    if current_head != head_ref:
        raise ValueError(f"head_ref_mismatch: expected={head_ref} actual={current_head}")


def resolve_context_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def validate_path_segment(segment: str, input_file: Path) -> str:
    if (
        not segment
        or segment in {".", ".."}
        or "/" in segment
        or "\\" in segment
        or Path(segment).is_absolute()
    ):
        raise ValueError(f"invalid_input_file_location: {input_file}")
    return segment


def validate_input_file_location(input_file: Path, change: str, head_ref: str) -> None:
    change = validate_path_segment(change, input_file)
    head_ref_short = validate_path_segment(head_ref[:12], input_file)
    expected = (
        Path(".local")
        / "cross-agent-review"
        / change
        / head_ref_short
        / "prepared-inputs"
        / "review-input.json"
    )
    try:
        actual = input_file.resolve().relative_to(Path.cwd().resolve())
    except ValueError as exc:
        raise ValueError(f"invalid_input_file_location: {input_file}") from exc
    if actual != expected:
        raise ValueError(f"invalid_input_file_location: {input_file}")


def validate_prepared_inputs_dir(input_file: Path) -> None:
    expected = input_file.resolve()
    for path in sorted(input_file.parent.iterdir()):
        if path.resolve() != expected or path.is_symlink() or not path.is_file():
            raise ValueError(f"unexpected_prepared_input: {path}")


def validate_base_ref(cwd: Path, base_ref: str) -> None:
    try:
        git_output(["rev-parse", "--verify", f"{base_ref}^{{commit}}"], cwd)
    except ValueError as exc:
        raise ValueError(f"base_ref_mismatch: {base_ref}") from exc


def load_review_input(args: argparse.Namespace) -> ReviewInput:
    input_file = args.input_file if args.input_file.is_absolute() else Path.cwd() / args.input_file
    if not input_file.is_file():
        raise ValueError(f"missing_file: {input_file}")
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    for field in REQUIRED_INPUT_FIELDS:
        if payload.get(field) is None:
            raise ValueError(f"missing_field: {field}")
    validate_input_file_location(input_file, str(payload["change"]), str(payload["head_ref"]))
    validate_prepared_inputs_dir(input_file)
    mode = str(payload["mode"])
    if mode not in VALID_MODES:
        raise ValueError(f"invalid_mode: {mode}")
    spec_file = resolve_context_path(str(payload["spec_file"]))
    design_file = resolve_context_path(str(payload["design_file"]))
    plan_file = resolve_context_path(str(payload["plan_file"]))
    for path in [spec_file, design_file, plan_file]:
        if not path.is_file():
            raise ValueError(f"missing_file: {path}")
    return ReviewInput(
        change=str(payload["change"]),
        mode=mode,
        base_ref=str(payload["base_ref"]),
        head_ref=str(payload["head_ref"]),
        spec_file=spec_file,
        design_file=design_file,
        plan_file=plan_file,
        input_file=input_file,
        output_dir=input_file.parent.parent,
        debug=getattr(args, "debug", False),
        sdk_python=getattr(args, "sdk_python", None),
        fake_reviewer_results=getattr(args, "fake_reviewer_results", None),
    )


def candidate_sdk_pythons(explicit: Path | None) -> list[Path]:
    candidates: list[Path] = []
    env_value = os.environ.get("CROSS_AGENT_REVIEW_SDK_PYTHON")
    if explicit is not None:
        candidates.append(explicit)
    if env_value:
        candidates.append(Path(env_value))
    candidates.append(Path.home() / ".claude" / "security" / "agent-sdk-venv" / "Scripts" / "python.exe")
    candidates.append(Path.home() / ".claude" / "security" / "agent-sdk-venv" / "bin" / "python")
    return candidates


def python_can_import_sdk(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        result = subprocess.run(
            [str(path), "-c", "import claude_agent_sdk"],
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError:
        return False
    return result.returncode == 0


def current_python_can_import_sdk() -> bool:
    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        return False
    return True


def resolve_sdk_python(explicit: Path | None, require_real_sdk: bool) -> str:
    if not require_real_sdk:
        return "fake"
    if explicit is not None:
        if python_can_import_sdk(explicit):
            return str(explicit)
        raise ValueError("sdk_unavailable: install claude-agent-sdk or pass --sdk-python")
    if current_python_can_import_sdk():
        return sys.executable
    for candidate in candidate_sdk_pythons(explicit):
        if python_can_import_sdk(candidate):
            return str(candidate)
    raise ValueError("sdk_unavailable: install claude-agent-sdk or pass --sdk-python")


def markdown_review(role: str, text: str) -> dict:
    return {"role": role, "text": text.strip() + "\n"}


def no_blocking_review(role: str) -> dict:
    return markdown_review(
        role,
        f"""# Review Result: {role}
## Findings
No findings.
""",
    )


def load_fake_reviewer_results(raw: str | None) -> list[dict]:
    if raw is None:
        return []
    if raw.strip() == "[]":
        return [no_blocking_review(role) for role in REVIEWER_ROLES]
    blocks = [block.strip() for block in raw.split("\n--- reviewer ---\n") if block.strip()]
    if not blocks:
        raise ValueError("invalid_fake_reviewer_results")
    if len(blocks) == 1:
        return [markdown_review(role, blocks[0]) for role in REVIEWER_ROLES]
    if len(blocks) != len(REVIEWER_ROLES):
        raise ValueError("invalid_fake_reviewer_results")
    return [markdown_review(role, text) for role, text in zip(REVIEWER_ROLES, blocks, strict=True)]


def render_template(path: Path, values: dict[str, str]) -> str:
    rendered = path.read_text(encoding="utf-8")
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{ {key} }}}}", value)
    return rendered


def git_command_text(args: Sequence[str]) -> str:
    return "git " + " ".join(args)


def reviewer_prompt(review_args: ReviewInput, role: str) -> str:
    diff_range = f"{review_args.base_ref}...{review_args.head_ref}"
    commit_range = f"{review_args.base_ref}..{review_args.head_ref}"
    review_subject_commands = "\n".join(
        [
            f"- {git_command_text(['diff', diff_range])}",
            f"- {git_command_text(['log', commit_range, '--oneline'])}",
            f"- {git_command_text(['diff', '--name-status', '--find-renames', '--find-copies-harder', diff_range])}",
        ]
    )
    return render_template(
        REVIEWER_PROMPT_TEMPLATE,
        {
            "role": role,
            "input_file_path": str(review_args.input_file),
            "review_subject_commands": review_subject_commands,
            "severity_rubric": SEVERITY_RUBRIC,
            "role_focus": ROLE_FOCUS.get(role, ""),
        },
    )


def dispatch_reviewers(review_args: ReviewInput, sdk_python: str) -> list[dict]:
    fake_results = load_fake_reviewer_results(review_args.fake_reviewer_results)
    if review_args.fake_reviewer_results is not None:
        return fake_results
    return run_sdk_dispatch_subprocess(review_args, sdk_python)


def reviewer_failure(role: str, summary: str, evidence: str, recommendation: str) -> dict:
    return markdown_review(
        role,
        f"""# Review Result: {role}
## Findings
- Severity: CRITICAL
  Location: {role}
  Summary: {summary}
  Evidence: {evidence}
  Recommendation: {recommendation}
""",
    )


def timeout_reviewer_results(raw_dir: Path | None, evidence: str) -> list[dict]:
    reviewers: list[dict] = []
    for role in REVIEWER_ROLES:
        raw_path = raw_dir / f"{role}.txt" if raw_dir is not None else None
        if raw_path is not None and raw_path.exists():
            role_evidence = raw_path.read_text(encoding="utf-8", errors="replace") or evidence
        else:
            role_evidence = evidence
            if raw_path is not None:
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_text(role_evidence + "\n", encoding="utf-8")
        reviewers.append(
            reviewer_failure(
                role,
                "Reviewer dispatch timed out",
                role_evidence,
                "Rerun review after checking Claude Agent SDK availability.",
            )
        )
    return reviewers


def write_debug_dispatch_artifacts(review_args: ReviewInput, prompts: dict[str, str]) -> Path:
    debug_dir = debug_dir_for(review_args)
    prompts_dir = debug_dir / "prompts"
    raw_dir = debug_dir / "raw"
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "review-input.json").write_bytes(review_args.input_file.read_bytes())
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for role, prompt in prompts.items():
        (prompts_dir / f"{role}.txt").write_text(prompt, encoding="utf-8")
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


def run_sdk_dispatch_subprocess(review_args: ReviewInput, sdk_python: str) -> list[dict]:
    prompts = {role: reviewer_prompt(review_args, role) for role in REVIEWER_ROLES}
    raw_dir = write_debug_dispatch_artifacts(review_args, prompts) if review_args.debug else None
    payload = {
        "cwd": str(Path.cwd()),
        "roles": REVIEWER_ROLES,
        "prompts": prompts,
        "force_exit": True,
    }
    if raw_dir is not None:
        payload["raw_dir"] = str(raw_dir)
    try:
        result = subprocess.run(
            [sdk_python, str(Path(__file__).resolve()), "_sdk-dispatch"],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
            timeout=SDK_DISPATCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return timeout_reviewer_results(
            raw_dir,
            f"sdk_dispatch_timeout: exceeded {SDK_DISPATCH_TIMEOUT_SECONDS}s",
        )
    if result.returncode != 0:
        raise ValueError(f"sdk_dispatch_failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("sdk_dispatch_invalid_output: stdout was not valid JSON") from exc
    if not isinstance(data, list):
        raise ValueError("sdk_dispatch_invalid_output: stdout JSON was not a list")
    return [item for item in data if isinstance(item, dict)]


def run_sdk_dispatch() -> int:
    import asyncio
    from claude_agent_sdk import ClaudeAgentOptions, query

    payload = json.loads(sys.stdin.read())

    async def collect() -> list[dict]:
        raw_dir = Path(payload["raw_dir"]) if payload.get("raw_dir") else None

        def write_raw(role: str, text: str) -> None:
            if raw_dir is None:
                return
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / f"{role}.txt").write_text(text, encoding="utf-8")

        async def query_one(role: str) -> dict:
            options = ClaudeAgentOptions(cwd=payload["cwd"])
            result_text = ""
            async for message in query(prompt=payload["prompts"][role], options=options):
                if hasattr(message, "result"):
                    result_text = message.result
            write_raw(role, result_text)
            return markdown_review(
                role,
                result_text
                or f"""# Review Result: {role}
## Findings
- Severity: CRITICAL
  Location: {role}
  Summary: Reviewer returned empty output
  Evidence: <empty reviewer result>
  Recommendation: Rerun review after checking reviewer prompt.
""",
            )

        async def run_one(role: str) -> dict:
            try:
                return await asyncio.wait_for(query_one(role), timeout=SDK_REVIEWER_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                evidence = f"Exceeded {SDK_REVIEWER_TIMEOUT_SECONDS} seconds."
                write_raw(role, f"Reviewer timed out\n{evidence}")
                return reviewer_failure(
                    role,
                    "Reviewer timed out",
                    evidence,
                    "Rerun review after checking Claude Agent SDK availability.",
                )
            except Exception as error:
                write_raw(role, f"{type(error).__name__}: {error}")
                return reviewer_failure(
                    role,
                    "Reviewer SDK dispatch failed",
                    f"{type(error).__name__}: {error}",
                    "Rerun review after checking Claude Agent SDK availability.",
                )

        return await asyncio.gather(*(run_one(role) for role in payload["roles"]))

    print(json.dumps(asyncio.run(collect()), ensure_ascii=False))
    sys.stdout.flush()
    sys.stderr.flush()
    if payload.get("force_exit"):
        os._exit(0)
    return 0


def short_ref(ref: str) -> str:
    return ref[:12] if len(ref) >= 12 else ref


def output_dir_for(review_args: ReviewInput) -> Path:
    return review_args.output_dir


def debug_dir_for(review_input: ReviewInput) -> Path:
    return review_input.output_dir / "debug"


def aggregate(reviewers: list[dict]) -> dict:
    return {"reviewers": reviewers}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_report(review_args: ReviewInput, summary: dict) -> str:
    lines = [
        f"# Cross-Agent Review: {review_args.change}",
        "",
        f"- Base ref: `{review_args.base_ref}`",
        f"- Head ref: `{review_args.head_ref}`",
        "",
        "## Reviewer Outputs",
        "",
    ]
    for reviewer in summary["reviewers"]:
        role = str(reviewer.get("role", "unknown"))
        text = str(reviewer.get("text", "")).strip() or f"""# Review Result: {role}
## Findings
- Severity: CRITICAL
  Location: {role}
  Summary: Reviewer returned empty output
  Evidence: <empty reviewer result>
  Recommendation: Rerun review after checking reviewer prompt."""
        lines.extend(
            [
                f"### {role}",
                "",
                text,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def runtime_allowed_paths(review_input: ReviewInput) -> list[Path]:
    output_dir = output_dir_for(review_input)
    debug_dir = debug_dir_for(review_input)
    return [
        review_input.input_file,
        output_dir / "review-report.md",
        output_dir / "review-pass.json",
        debug_dir / "review-input.json",
        *(debug_dir / "prompts" / f"{role}.txt" for role in REVIEWER_ROLES),
        *(debug_dir / "raw" / f"{role}.txt" for role in REVIEWER_ROLES),
    ]


def write_outputs(review_args: ReviewInput, summary: dict) -> int:
    out_dir = output_dir_for(review_args)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_text = render_report(review_args, summary)
    report_path = out_dir / "review-report.md"
    report_path.write_text(report_text, encoding="utf-8")
    (out_dir / "review-pass.json").unlink(missing_ok=True)
    return 0


def guard_pass_path(
    review_args: ReviewInput,
    *,
    profile_id: str,
    artifact_id: str,
    subject_id: str,
) -> Path:
    return (
        Path.cwd()
        / ".local"
        / "guard"
        / "evidence"
        / validate_path_segment(profile_id, review_args.input_file)
        / validate_path_segment(artifact_id, review_args.input_file)
        / validate_path_segment(subject_id, review_args.input_file)
        / validate_path_segment(short_ref(review_args.head_ref), review_args.input_file)
        / "pass.json"
    )


def mark_pass_allowed_paths(review_args: ReviewInput, pass_path: Path) -> list[Path]:
    return [review_args.input_file, output_dir_for(review_args) / "review-report.md", pass_path]


def run_mark_pass(args: argparse.Namespace) -> int:
    try:
        review_args = load_review_input(args)
        subject_id = args.subject_id or review_args.change
        report_path = output_dir_for(review_args) / "review-report.md"
        if not report_path.is_file():
            raise ValueError(f"missing_file: {report_path}")
        pass_path = guard_pass_path(
            review_args,
            profile_id=args.profile_id,
            artifact_id=args.artifact_id,
            subject_id=subject_id,
        )
        ensure_clean_subject(Path.cwd(), review_args.head_ref, mark_pass_allowed_paths(review_args, pass_path))
        report_relative = report_path.relative_to(Path.cwd())
        report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
        write_json(
            pass_path,
            {
                "schema_version": "guard-evidence/v1",
                "status": "pass",
                "producer": "cross-agent-review",
                "profile_id": args.profile_id,
                "artifact_id": args.artifact_id,
                "subject_type": args.subject_type,
                "subject_id": subject_id,
                "change": review_args.change,
                "mode": review_args.mode,
                "base_ref": review_args.base_ref,
                "head_ref": review_args.head_ref,
                "head_ref_short": short_ref(review_args.head_ref),
                "blocking_findings": 0,
                "scope": {
                    "change": review_args.change,
                    "mode": review_args.mode,
                    "base_ref": review_args.base_ref,
                    "report": str(report_relative),
                },
                "report": str(report_relative),
                "report_hash": f"sha256:{report_hash}",
                "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
        )
    except (ValueError, json.JSONDecodeError) as exc:
        print("status: failed")
        print(f"error: {exc}")
        return 1
    print("status: pass_marked")
    print(f"path: {pass_path.relative_to(Path.cwd())}")
    return 0


def run_review(args: argparse.Namespace) -> int:
    try:
        review_args = load_review_input(args)
        validate_base_ref(Path.cwd(), review_args.base_ref)
        allowed_paths = runtime_allowed_paths(review_args)
        ensure_clean_subject(Path.cwd(), review_args.head_ref, allowed_paths)
        sdk_python = resolve_sdk_python(
            review_args.sdk_python,
            require_real_sdk=review_args.fake_reviewer_results is None or review_args.sdk_python is not None,
        )
        ensure_clean_subject(Path.cwd(), review_args.head_ref, allowed_paths)
        reviewers = dispatch_reviewers(review_args, sdk_python)
        summary = aggregate(reviewers)
        status = write_outputs(review_args, summary)
    except (ValueError, json.JSONDecodeError) as exc:
        print("status: failed")
        print(f"error: {exc}")
        return 1
    print("status: review_ready")
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    if parsed.command == "_sdk-dispatch":
        return run_sdk_dispatch()
    if parsed.command == "run":
        return run_review(parsed)
    if parsed.command == "mark-pass":
        return run_mark_pass(parsed)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
