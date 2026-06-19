from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


REQUIRED_FILE_ARGS = ["diff_file", "spec_file", "design_file", "tasks_file", "tests_file"]
PLACEHOLDER_COMPAT_DISABLE_RISK_REVIEW = "__placeholder_compat__"
REVIEWER_ROLES = [
    "spec-alignment",
    "implementation-correctness",
    "tests-and-edge-cases",
    "risk-review",
]
READONLY_TOOLS = ["Read", "Glob", "Grep", "Bash(git diff *)", "Bash(git show *)", "Bash(git status *)"]
BLOCKING_SEVERITIES = {"CRITICAL", "IMPORTANT"}
NON_BLOCKING_SEVERITIES = {"WARNING", "SUGGESTION"}
ALL_SEVERITIES = BLOCKING_SEVERITIES | NON_BLOCKING_SEVERITIES


@dataclass(frozen=True)
class ReviewArgs:
    change: str
    base_ref: str
    head_ref: str
    diff_file: Path
    spec_file: Path
    design_file: Path
    tasks_file: Path
    tests_file: Path
    output_dir: Path | None
    sdk_python: Path | None
    fake_reviewer_results: str | None
    disable_risk_review: str | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cross_agent_review.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--change", required=True)
    run_parser.add_argument("--base-ref", required=True)
    run_parser.add_argument("--head-ref", required=True)
    run_parser.add_argument("--diff-file", type=Path, required=True)
    run_parser.add_argument("--spec-file", type=Path, required=True)
    run_parser.add_argument("--design-file", type=Path, required=True)
    run_parser.add_argument("--tasks-file", type=Path, required=True)
    run_parser.add_argument("--tests-file", type=Path, required=True)
    run_parser.add_argument("--output-dir", type=Path)
    run_parser.add_argument("--sdk-python", type=Path)
    run_parser.add_argument("--fake-reviewer-results")
    run_parser.add_argument("--disable-risk-review", nargs="?", const=PLACEHOLDER_COMPAT_DISABLE_RISK_REVIEW)
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


def status_paths(cwd: Path) -> set[Path]:
    paths: set[Path] = set()
    output = git_output_bytes(["status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd)
    entries = output.split(b"\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        path_text = entry[3:].decode("utf-8", errors="surrogateescape")
        paths.add((cwd / path_text).resolve())
        if entry[:1] in {b"R", b"C"} or entry[1:2] in {b"R", b"C"}:
            index += 1
    return paths


def ensure_clean_subject(cwd: Path, head_ref: str, allowed_dirty_paths: Sequence[Path] = ()) -> None:
    allowed = {path.resolve() for path in allowed_dirty_paths}
    dirty_paths = status_paths(cwd) - allowed
    if dirty_paths:
        raise ValueError("dirty_worktree")
    current_head = git_output(["rev-parse", "HEAD"], cwd)
    if current_head != head_ref:
        raise ValueError(f"head_ref_mismatch: expected={head_ref} actual={current_head}")


def parse_review_args(args: argparse.Namespace) -> ReviewArgs:
    review_args = ReviewArgs(
        change=args.change,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        diff_file=args.diff_file,
        spec_file=args.spec_file,
        design_file=args.design_file,
        tasks_file=args.tasks_file,
        tests_file=args.tests_file,
        output_dir=args.output_dir,
        sdk_python=args.sdk_python,
        fake_reviewer_results=args.fake_reviewer_results,
        disable_risk_review=args.disable_risk_review,
    )
    for name in REQUIRED_FILE_ARGS:
        path = getattr(review_args, name)
        if not path.is_file():
            raise ValueError(f"missing_file: {path}")
    return review_args


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


def load_fake_reviewer_results(raw: str | None) -> list[dict]:
    if raw is None:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("invalid_fake_reviewer_results")
    required_fields = {"role", "status", "findings"}
    for item in data:
        if not isinstance(item, dict) or not required_fields <= item.keys():
            raise ValueError("invalid_fake_reviewer_results")
    return data


def dispatch_reviewers(review_args: ReviewArgs, sdk_python: str) -> list[dict]:
    fake_results = load_fake_reviewer_results(review_args.fake_reviewer_results)
    if review_args.fake_reviewer_results is not None:
        return fake_results
    raise ValueError("real_sdk_dispatch_not_implemented")


def short_ref(ref: str) -> str:
    return ref[:12] if len(ref) >= 12 else ref


def output_dir_for(review_args: ReviewArgs) -> Path:
    if review_args.output_dir is not None:
        return review_args.output_dir
    return Path(".local") / "cross-agent-review" / review_args.change / short_ref(review_args.head_ref)


def normalize_finding(raw: dict) -> dict:
    severity = str(raw.get("severity", "")).upper()
    if severity not in ALL_SEVERITIES:
        severity = "CRITICAL"
    return {
        "severity": severity,
        "location": str(raw.get("location", "")),
        "summary": str(raw.get("summary", "")),
        "evidence": str(raw.get("evidence", "")),
        "recommendation": str(raw.get("recommendation", "")),
    }


def aggregate(reviewers: list[dict], skipped: list[dict]) -> dict:
    findings: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for reviewer in reviewers:
        role = str(reviewer.get("role", "unknown"))
        raw_findings = reviewer.get("findings", [])
        if not isinstance(raw_findings, list):
            raw_findings = [
                {
                    "severity": "CRITICAL",
                    "location": role,
                    "summary": "Reviewer returned invalid findings",
                    "evidence": json.dumps(reviewer, ensure_ascii=False),
                    "recommendation": "Rerun review or fix reviewer prompt",
                }
            ]
        for raw in raw_findings:
            if not isinstance(raw, dict):
                raw = {
                    "severity": "CRITICAL",
                    "location": role,
                    "summary": "Reviewer returned invalid finding",
                    "evidence": repr(raw),
                    "recommendation": "Rerun review or fix reviewer prompt",
                }
            finding = normalize_finding(raw)
            key = (finding["severity"], finding["location"], finding["summary"])
            if key in seen:
                continue
            seen.add(key)
            findings.append(finding)
    blocking = sum(1 for finding in findings if finding["severity"] in BLOCKING_SEVERITIES)
    return {
        "reviewers": reviewers,
        "skipped_reviewers": skipped,
        "findings": findings,
        "blocking_findings": blocking,
        "readonly_tools": READONLY_TOOLS,
    }


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_report(review_args: ReviewArgs, summary: dict) -> str:
    lines = [
        f"# Cross-Agent Review: {review_args.change}",
        "",
        f"- Base ref: `{review_args.base_ref}`",
        f"- Head ref: `{review_args.head_ref}`",
        f"- Blocking findings: `{summary['blocking_findings']}`",
        "",
        "## Findings",
        "",
    ]
    if not summary["findings"]:
        lines.append("No findings.")
    for finding in summary["findings"]:
        lines.extend(
            [
                f"### {finding['severity']}: {finding['summary']}",
                "",
                f"- Location: `{finding['location']}`",
                f"- Evidence: {finding['evidence']}",
                f"- Recommendation: {finding['recommendation']}",
                "",
            ]
        )
    if summary["skipped_reviewers"]:
        lines.extend(["## Skipped Reviewers", ""])
        for skipped in summary["skipped_reviewers"]:
            lines.append(f"- `{skipped['role']}`: {skipped['reason']}")
    return "\n".join(lines).rstrip() + "\n"


def allowed_input_paths(review_args: ReviewArgs) -> list[Path]:
    return [
        review_args.diff_file,
        review_args.spec_file,
        review_args.design_file,
        review_args.tasks_file,
        review_args.tests_file,
    ]


def write_outputs(review_args: ReviewArgs, summary: dict) -> int:
    out_dir = output_dir_for(review_args)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_text = render_report(review_args, summary)
    report_path = out_dir / "review-report.md"
    results_path = out_dir / "review-results.json"
    pass_path = out_dir / "review-pass.json"
    report_path.write_text(report_text, encoding="utf-8")
    write_json(results_path, summary)
    if summary["blocking_findings"] == 0:
        ensure_clean_subject(
            Path.cwd(),
            review_args.head_ref,
            [*allowed_input_paths(review_args), report_path, results_path, pass_path],
        )
        report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
        write_json(
            pass_path,
            {
                "status": "pass",
                "change": review_args.change,
                "base_ref": review_args.base_ref,
                "head_ref": review_args.head_ref,
                "blocking_findings": 0,
                "report": "review-report.md",
                "report_hash": report_hash,
            },
        )
        return 0
    pass_path.unlink(missing_ok=True)
    return 1


def run_review(args: argparse.Namespace) -> int:
    if args.disable_risk_review == PLACEHOLDER_COMPAT_DISABLE_RISK_REVIEW:
        print("status: not_implemented")
        return 2
    try:
        review_args = parse_review_args(args)
        ensure_clean_subject(Path.cwd(), review_args.head_ref, allowed_input_paths(review_args))
        sdk_python = resolve_sdk_python(
            review_args.sdk_python,
            require_real_sdk=review_args.fake_reviewer_results is None or review_args.sdk_python is not None,
        )
        ensure_clean_subject(Path.cwd(), review_args.head_ref, allowed_input_paths(review_args))
        reviewers = dispatch_reviewers(review_args, sdk_python)
        skipped = []
        if review_args.disable_risk_review:
            skipped.append({"role": "risk-review", "reason": review_args.disable_risk_review})
            reviewers = [item for item in reviewers if item.get("role") != "risk-review"]
        summary = aggregate(reviewers, skipped)
        status = write_outputs(review_args, summary)
    except (ValueError, json.JSONDecodeError) as exc:
        print("status: failed")
        print(f"error: {exc}")
        return 1
    print("status: pass" if status == 0 else "status: findings")
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    if parsed.command == "run":
        return run_review(parsed)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
