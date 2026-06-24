from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path


REQUIRED_FILE_ARGS = ["spec_file", "design_file", "tasks_file"]
INPUT_SNAPSHOT_NAMES = {
    "spec_file": "spec.md",
    "design_file": "design.md",
    "tasks_file": "tasks.md",
}
PLACEHOLDER_COMPAT_DISABLE_RISK_REVIEW = "__placeholder_compat__"
REVIEWER_ROLES = [
    "spec-alignment",
    "implementation-correctness",
    "tests-and-edge-cases",
    "risk-review",
]
ROLE_FOCUS = {
    "spec-alignment": "\n".join(
        [
            "Focus for spec-alignment:",
            "- Compare the supplied spec, design, tasks, and changed files for requirement drift.",
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
    "tests-and-edge-cases": "\n".join(
        [
            "Focus for tests-and-edge-cases:",
            "- Review test coverage gaps for changed behavior and required scenarios.",
            "- Review regression protection for previously supported behavior and integration contracts.",
            "- Review edge cases, error paths, boundary inputs, and state transitions implied by the supplied inputs.",
            "- Do not claim tests passed, failed, or were run; no test results are supplied.",
            "- Only create findings for concrete missing coverage, weak regression protection, or unhandled edge cases.",
        ]
    ),
    "risk-review": "\n".join(
        [
            "Focus for risk-review:",
            "- Review operational, security, reliability, and maintainability risks introduced by the change.",
            "- Separate concrete risks from preferences; downgrade speculative concerns to WARNING or SUGGESTION.",
            "- Do not duplicate findings already covered by implementation-correctness unless impact is broader.",
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
READONLY_TOOLS = ["Read", "Glob", "Grep", "Bash(git diff *)", "Bash(git show *)", "Bash(git status *)"]
DISALLOWED_TOOLS = ["Edit", "Write", "NotebookEdit", "TodoWrite", "MultiEdit", "Bash"]
# Individual reviewers time out first; the subprocess gets a wider window to
# aggregate structured timeout findings and write normal outputs.
SDK_DISPATCH_TIMEOUT_SECONDS = 540
SDK_REVIEWER_TIMEOUT_SECONDS = 480
SDK_REVIEWER_ATTEMPTS = 2
BLOCKING_SEVERITIES = {"CRITICAL", "IMPORTANT"}
NON_BLOCKING_SEVERITIES = {"WARNING", "SUGGESTION"}
ALL_SEVERITIES = BLOCKING_SEVERITIES | NON_BLOCKING_SEVERITIES
SEVERITY_ALIASES = {
    "CRITICAL": "CRITICAL",
    "IMPORTANT": "IMPORTANT",
    "WARNING": "WARNING",
    "SUGGESTION": "SUGGESTION",
}


@dataclass(frozen=True)
class ReviewArgs:
    change: str
    base_ref: str
    head_ref: str
    spec_file: Path
    design_file: Path
    tasks_file: Path
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
    run_parser.add_argument("--spec-file", type=Path, required=True)
    run_parser.add_argument("--design-file", type=Path, required=True)
    run_parser.add_argument("--tasks-file", type=Path, required=True)
    run_parser.add_argument("--tests-file", type=Path, help=argparse.SUPPRESS)
    run_parser.add_argument("--output-dir", type=Path)
    run_parser.add_argument("--sdk-python", type=Path)
    run_parser.add_argument("--fake-reviewer-results")
    run_parser.add_argument("--disable-risk-review", nargs="?", const=PLACEHOLDER_COMPAT_DISABLE_RISK_REVIEW)
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
        spec_file=args.spec_file,
        design_file=args.design_file,
        tasks_file=args.tasks_file,
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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def input_reference(label: str, path: Path) -> str:
    content = path.read_bytes()
    return "\n".join(
        [
            f"{label} file: {path}",
            f"{label} bytes: {len(content)}",
            f"{label} sha256: {hashlib.sha256(content).hexdigest()}",
        ]
    )


def diff_path(value: str, prefix: str) -> str:
    return value[len(prefix) :] if value.startswith(prefix) else value


def parse_diff_git_paths(line: str) -> tuple[str, str] | None:
    rest = line.removeprefix("diff --git ")
    if rest.startswith('"'):
        parts = shlex.split(rest)
        if len(parts) >= 2:
            return diff_path(parts[0], "a/"), diff_path(parts[1], "b/")
    separator = rest.rfind(" b/")
    if separator != -1:
        return diff_path(rest[:separator], "a/"), diff_path(rest[separator + 1 :], "b/")
    parts = rest.split(maxsplit=1)
    if len(parts) >= 2:
        return diff_path(parts[0], "a/"), diff_path(parts[1], "b/")
    return None


def changed_file_entries_from_diff(path: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    def append_current() -> None:
        if current is None:
            return
        changed_path = current.get("path") or current.get("new_path") or current.get("old_path")
        if not changed_path:
            return
        entry = {"path": changed_path, "status": current.get("status", "modified")}
        previous_path = current.get("old_path")
        if entry["status"] in {"renamed", "copied"} and previous_path and previous_path != changed_path:
            entry["previous_path"] = previous_path
        if entry not in entries:
            entries.append(entry)

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("diff --git "):
            append_current()
            current = None
            parsed_paths = parse_diff_git_paths(line)
            if parsed_paths is None:
                continue
            old_path, new_path = parsed_paths
            current = {
                "old_path": old_path,
                "new_path": new_path,
                "path": new_path,
                "status": "modified",
            }
            continue
        if current is None:
            continue
        if line.startswith("new file mode "):
            current["status"] = "added"
            current["path"] = current["new_path"]
        elif line.startswith("deleted file mode "):
            current["status"] = "deleted"
            current["path"] = current["old_path"]
        elif line.startswith("rename from "):
            current["status"] = "renamed"
            current["old_path"] = line.removeprefix("rename from ")
        elif line.startswith("rename to "):
            current["status"] = "renamed"
            current["new_path"] = line.removeprefix("rename to ")
            current["path"] = current["new_path"]
        elif line.startswith("copy from "):
            current["status"] = "copied"
            current["old_path"] = line.removeprefix("copy from ")
        elif line.startswith("copy to "):
            current["status"] = "copied"
            current["new_path"] = line.removeprefix("copy to ")
            current["path"] = current["new_path"]
    append_current()
    return entries


def changed_files_from_diff(path: Path, limit: int = 160) -> str:
    files = [entry["path"] for entry in changed_file_entries_from_diff(path)]
    shown = files[:limit]
    lines = ["Changed files:"]
    lines.extend(f"- {item}" for item in shown)
    if len(files) > limit:
        lines.append(f"- ... {len(files) - limit} more")
    return "\n".join(lines)


def input_manifest_path(review_args: ReviewArgs) -> Path:
    return output_dir_for(review_args) / "inputs" / "manifest.json"


def relative_to_output(review_args: ReviewArgs, path: Path) -> str:
    try:
        return path.relative_to(output_dir_for(review_args)).as_posix()
    except ValueError:
        return path.as_posix()


def input_file_metadata(review_args: ReviewArgs, path: Path) -> dict:
    content = path.read_bytes()
    return {
        "path": relative_to_output(review_args, path),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def build_input_manifest(review_args: ReviewArgs) -> dict:
    return {
        "change": review_args.change,
        "base_ref": review_args.base_ref,
        "head_ref": review_args.head_ref,
        "inputs": {
            "spec": input_file_metadata(review_args, review_args.spec_file),
            "design": input_file_metadata(review_args, review_args.design_file),
            "tasks": input_file_metadata(review_args, review_args.tasks_file),
        },
        "changed_files": [],
    }


def write_input_manifest(review_args: ReviewArgs) -> Path:
    path = input_manifest_path(review_args)
    write_json(path, build_input_manifest(review_args))
    return path


def reviewer_prompt(review_args: ReviewArgs, role: str) -> str:
    parts = [
        f"Role: {role}",
        "Return only a single JSON object. Do not use Markdown.",
        "Schema:",
        json.dumps(
            {
                "role": role,
                "status": "completed",
                "findings": [
                    {
                        "severity": "CRITICAL",
                        "location": "path-or-component",
                        "summary": "one-line issue summary",
                        "evidence": "specific evidence from the supplied inputs",
                        "recommendation": "concrete next action",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        "Use only these severity values: CRITICAL, IMPORTANT, WARNING, SUGGESTION.",
        'If there are no issues, return "findings": [].',
        "Do not put pass, aligned, ok, or informational observations in findings.",
        "Do not use severity aliases such as high, medium, low, minor, or info.",
        SEVERITY_RUBRIC,
    ]
    focus = ROLE_FOCUS.get(role)
    if focus:
        parts.append(focus)
    parts.extend(
        [
            f"Change: {review_args.change}",
            f"Base ref: {review_args.base_ref}",
            f"Head ref: {review_args.head_ref}",
            f"Manifest file: {input_manifest_path(review_args)}",
            "Use the referenced input files as the source of truth. Read only the sections needed for this review.",
            "Use git diff/show/status read-only commands if the file references are insufficient.",
            input_reference("Spec", review_args.spec_file),
            input_reference("Design", review_args.design_file),
            input_reference("Tasks", review_args.tasks_file),
        ]
    )
    return "\n\n".join(parts)


def dispatch_reviewers(review_args: ReviewArgs, sdk_python: str) -> list[dict]:
    fake_results = load_fake_reviewer_results(review_args.fake_reviewer_results)
    if review_args.fake_reviewer_results is not None:
        return fake_results
    return run_sdk_dispatch_subprocess(review_args, sdk_python)


def reviewer_failure(role: str, summary: str, evidence: str, recommendation: str) -> dict:
    return {
        "role": role,
        "status": "failed",
        "findings": [
            {
                "severity": "CRITICAL",
                "location": role,
                "summary": summary,
                "evidence": evidence,
                "recommendation": recommendation,
            }
        ],
    }


def timeout_reviewer_results(raw_dir: Path, evidence: str) -> list[dict]:
    reviewers: list[dict] = []
    for role in REVIEWER_ROLES:
        raw_path = raw_dir / f"{role}.txt"
        if raw_path.exists():
            raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
            parsed = parse_reviewer_result(raw_text)
            if parsed is not None:
                reviewers.append(parsed)
                continue
            role_evidence = raw_text or evidence
        else:
            role_evidence = evidence
        reviewers.append(
            reviewer_failure(
                role,
                "Reviewer dispatch timed out",
                role_evidence,
                "Rerun review after checking Claude Agent SDK availability.",
            )
        )
    return reviewers


def run_sdk_dispatch_subprocess(review_args: ReviewArgs, sdk_python: str) -> list[dict]:
    prompts = {role: reviewer_prompt(review_args, role) for role in REVIEWER_ROLES}
    prompts_dir = output_dir_for(review_args) / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for role, prompt in prompts.items():
        (prompts_dir / f"{role}.txt").write_text(prompt, encoding="utf-8")
    raw_dir = output_dir_for(review_args) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "cwd": str(Path.cwd()),
        "roles": REVIEWER_ROLES,
        "readonly_tools": READONLY_TOOLS,
        "prompts": prompts,
        "raw_dir": str(raw_dir),
        "force_exit": True,
    }
    try:
        result = subprocess.run(
            [sdk_python, str(Path(__file__).resolve()), "_sdk-dispatch"],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
            timeout=SDK_DISPATCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
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


def balanced_json_object_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : index + 1])
                    break
        start = text.find("{", start + 1)
    return candidates


def markdown_fence_bodies(text: str) -> list[str]:
    bodies: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        fence = lines[index].strip()
        if not fence.startswith("```"):
            index += 1
            continue
        language = fence[3:].strip().lower()
        end = index + 1
        while end < len(lines) and lines[end].strip() != "```":
            end += 1
        if end < len(lines) and language in {"", "json"}:
            bodies.append("\n".join(lines[index + 1 : end]))
            index = end
        index += 1
    return bodies


def parse_reviewer_result(result_text: str) -> dict | None:
    candidates = [result_text.strip()]
    candidates.extend(markdown_fence_bodies(result_text))
    candidates.extend(balanced_json_object_candidates(result_text))
    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


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
            options = ClaudeAgentOptions(
                cwd=payload["cwd"],
                allowed_tools=payload["readonly_tools"],
                disallowed_tools=DISALLOWED_TOOLS,
            )
            result_text = ""
            async for message in query(prompt=payload["prompts"][role], options=options):
                if hasattr(message, "result"):
                    result_text = message.result
            write_raw(role, result_text)
            parsed = parse_reviewer_result(result_text)
            if parsed is not None:
                return parsed
            return {
                "role": role,
                "status": "failed",
                "findings": [
                    {
                        "severity": "CRITICAL",
                        "location": role,
                        "summary": "Reviewer returned invalid JSON",
                        "evidence": result_text or "<empty reviewer result>",
                        "recommendation": "Rerun review after checking reviewer prompt",
                    }
                ],
            }

        async def run_one(role: str) -> dict:
            last_error: Exception | None = None
            for attempt in range(1, SDK_REVIEWER_ATTEMPTS + 1):
                try:
                    return await asyncio.wait_for(query_one(role), timeout=SDK_REVIEWER_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    return {
                        "role": role,
                        "status": "failed",
                        "findings": [
                            {
                                "severity": "CRITICAL",
                                "location": role,
                                "summary": "Reviewer timed out",
                                "evidence": f"Exceeded {SDK_REVIEWER_TIMEOUT_SECONDS} seconds.",
                                "recommendation": "Rerun review after checking Claude Agent SDK availability.",
                            }
                        ],
                    }
                except Exception as error:
                    last_error = error
                    write_raw(role, f"{type(error).__name__}: {error}")
                    if attempt < SDK_REVIEWER_ATTEMPTS:
                        await asyncio.sleep(1)
                        continue
            return {
                "role": role,
                "status": "failed",
                "findings": [
                    {
                        "severity": "CRITICAL",
                        "location": role,
                        "summary": "Reviewer SDK dispatch failed",
                        "evidence": f"{type(last_error).__name__}: {last_error}",
                        "recommendation": "Rerun review after checking Claude Agent SDK availability.",
                    }
                ],
            }

        return await asyncio.gather(*(run_one(role) for role in payload["roles"]))

    print(json.dumps(asyncio.run(collect()), ensure_ascii=False))
    sys.stdout.flush()
    sys.stderr.flush()
    if payload.get("force_exit"):
        os._exit(0)
    return 0


def short_ref(ref: str) -> str:
    return ref[:12] if len(ref) >= 12 else ref


def output_dir_for(review_args: ReviewArgs) -> Path:
    if review_args.output_dir is not None:
        return review_args.output_dir
    return Path(".local") / "cross-agent-review" / review_args.change / short_ref(review_args.head_ref)


def archive_input_snapshots(review_args: ReviewArgs) -> ReviewArgs:
    inputs_dir = output_dir_for(review_args) / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    replacements: dict[str, Path] = {}
    for field, filename in INPUT_SNAPSHOT_NAMES.items():
        source = getattr(review_args, field)
        target = inputs_dir / filename
        target.write_bytes(source.read_bytes())
        replacements[field] = target
    archived = replace(review_args, **replacements)
    write_input_manifest(archived)
    return archived


def first_text(raw: dict, names: Sequence[str]) -> str:
    for name in names:
        value = raw.get(name)
        if value is not None and value != "":
            return str(value)
    return ""


def finding_location(raw: dict) -> str:
    location = first_text(raw, ["location", "area"])
    if location:
        return location
    file = raw.get("file")
    line = raw.get("line")
    if file is not None and line is not None:
        return f"{file}:{line}"
    return str(file) if file is not None else ""


def normalize_severity(raw: dict) -> str:
    severity = str(raw.get("severity", "")).upper()
    return SEVERITY_ALIASES.get(severity, "")


def invalid_reviewer_finding(role: str, summary: str, raw: object) -> dict:
    location = finding_location(raw) if isinstance(raw, dict) else ""
    return {
        "severity": "CRITICAL",
        "location": location or role,
        "summary": summary,
        "evidence": json.dumps(raw, ensure_ascii=False) if isinstance(raw, dict) else repr(raw),
        "recommendation": "Fix reviewer prompt or rerun review with strict JSON output.",
    }


def normalize_reviewer_findings(role: str, reviewer: dict) -> list[dict]:
    raw_findings = reviewer.get("findings", [])
    if isinstance(raw_findings, list):
        return raw_findings
    if isinstance(raw_findings, dict):
        issues = raw_findings.get("issues")
        if isinstance(issues, list):
            return [issue for issue in issues if isinstance(issue, dict)]
        gaps = raw_findings.get("gaps")
        if isinstance(gaps, list):
            return [gap for gap in gaps if isinstance(gap, dict)]
    return [
        {
            "severity": "CRITICAL",
            "location": role,
            "summary": "Reviewer returned invalid findings",
            "evidence": json.dumps(reviewer, ensure_ascii=False),
            "recommendation": "Rerun review or fix reviewer prompt",
        }
    ]


def normalize_finding(raw: dict) -> dict:
    severity = normalize_severity(raw)
    return {
        "severity": severity,
        "location": finding_location(raw),
        "summary": first_text(raw, ["summary", "description", "message", "issue", "detail"]),
        "evidence": first_text(raw, ["evidence", "detail", "spec_scenario"]),
        "recommendation": first_text(raw, ["recommendation", "suggestion"]),
    }


def aggregate(reviewers: list[dict], skipped: list[dict]) -> dict:
    findings: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for reviewer in reviewers:
        role = str(reviewer.get("role", "unknown"))
        raw_findings = normalize_reviewer_findings(role, reviewer)
        for raw in raw_findings:
            if not isinstance(raw, dict):
                raw = invalid_reviewer_finding(role, "Reviewer returned invalid finding", raw)
            elif "severity" not in raw:
                raw = invalid_reviewer_finding(role, "Reviewer output missing severity", raw)
            elif not normalize_severity(raw):
                raw = invalid_reviewer_finding(role, f"Reviewer output used invalid severity: {raw.get('severity')}", raw)
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
        review_args.spec_file,
        review_args.design_file,
        review_args.tasks_file,
    ]


def output_artifact_paths(review_args: ReviewArgs) -> list[Path]:
    out_dir = output_dir_for(review_args)
    paths = [input_manifest_path(review_args)]
    for directory in (out_dir / "prompts", out_dir / "raw"):
        if directory.is_dir():
            paths.extend(path for path in directory.glob("*.txt") if path.is_file())
    return paths


def write_outputs(review_args: ReviewArgs, summary: dict, extra_allowed_paths: Sequence[Path] = ()) -> int:
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
            [
                *extra_allowed_paths,
                *allowed_input_paths(review_args),
                *output_artifact_paths(review_args),
                report_path,
                results_path,
                pass_path,
            ],
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
        legacy_input_paths = [args.tests_file] if args.tests_file is not None else []
        original_input_paths = allowed_input_paths(review_args)
        ensure_clean_subject(Path.cwd(), review_args.head_ref, [*original_input_paths, *legacy_input_paths])
        review_args = archive_input_snapshots(review_args)
        sdk_python = resolve_sdk_python(
            review_args.sdk_python,
            require_real_sdk=review_args.fake_reviewer_results is None or review_args.sdk_python is not None,
        )
        ensure_clean_subject(
            Path.cwd(),
            review_args.head_ref,
            [
                *original_input_paths,
                *legacy_input_paths,
                *allowed_input_paths(review_args),
                *output_artifact_paths(review_args),
            ],
        )
        reviewers = dispatch_reviewers(review_args, sdk_python)
        skipped = []
        if review_args.disable_risk_review:
            skipped.append({"role": "risk-review", "reason": review_args.disable_risk_review})
            reviewers = [item for item in reviewers if item.get("role") != "risk-review"]
        summary = aggregate(reviewers, skipped)
        status = write_outputs(review_args, summary, [*original_input_paths, *legacy_input_paths])
    except (ValueError, json.JSONDecodeError) as exc:
        print("status: failed")
        print(f"error: {exc}")
        return 1
    print("status: pass" if status == 0 else "status: findings")
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    if parsed.command == "_sdk-dispatch":
        return run_sdk_dispatch()
    if parsed.command == "run":
        return run_review(parsed)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
