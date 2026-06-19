from __future__ import annotations

import argparse
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
    if not path.exists():
        return False
    result = subprocess.run(
        [str(path), "-c", "import claude_agent_sdk"],
        check=False,
        text=True,
        capture_output=True,
    )
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
    return [item for item in data if isinstance(item, dict)]


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


def write_review_results(review_args: ReviewArgs, reviewers: list[dict]) -> None:
    out_dir = output_dir_for(review_args)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "reviewers": reviewers,
        "readonly_tools": READONLY_TOOLS,
    }
    (out_dir / "review-results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_review(args: argparse.Namespace) -> int:
    if args.disable_risk_review == PLACEHOLDER_COMPAT_DISABLE_RISK_REVIEW:
        print("status: not_implemented")
        return 2
    try:
        review_args = parse_review_args(args)
        ensure_clean_subject(
            Path.cwd(),
            review_args.head_ref,
            [
                review_args.diff_file,
                review_args.spec_file,
                review_args.design_file,
                review_args.tasks_file,
                review_args.tests_file,
            ],
        )
        sdk_python = resolve_sdk_python(
            review_args.sdk_python,
            require_real_sdk=review_args.fake_reviewer_results is None or review_args.sdk_python is not None,
        )
        reviewers = dispatch_reviewers(review_args, sdk_python)
        write_review_results(review_args, reviewers)
    except (ValueError, json.JSONDecodeError) as exc:
        print("status: failed")
        print(f"error: {exc}")
        return 1
    print("status: ready")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    if parsed.command == "run":
        return run_review(parsed)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
