from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml


SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
REVIEWER_PROMPT_TEMPLATE = SKILL_ROOT / "assets" / "templates" / "reviewer-prompt.md"
REQUIRED_INPUT_FIELDS = ["change", "mode", "base_ref", "head_ref", "spec_file", "design_file", "plan_file"]
VALID_MODES = {"convergence", "endless"}
REVIEWER_ROLES = [
    "spec-alignment",
    "implementation-correctness",
]
TERMINAL_ROLE_STATUSES = {"completed", "failed", "timed_out", "reused"}
CHECKBOX = re.compile(r"^(?P<prefix>\s*[-*+]\s+\[)[ xX](?P<suffix>\].*)$")
MISSING = object()
STATE_FIELDS = {"schema_version", "subject", "files", "roles", "report_hash"}
REUSED_STATE_FIELDS = {"source_head_ref", "source_state", "validated_changes"}
ROLE_STATE_FIELDS = {"scope", "attempts", "status", "output", "output_hash"}
ATTEMPT_FIELDS = {
    "number",
    "started_at",
    "finished_at",
    "status",
    "output",
    "output_hash",
}
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
class SummaryOnly:
    path: str
    reason: str


@dataclass(frozen=True)
class RevalidationPolicy:
    path: str
    validator: str
    format: str | None = None
    fields: tuple[str, ...] = ()


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
    summary_only: tuple[SummaryOnly, ...]
    revalidation_policy: tuple[RevalidationPolicy, ...]


@dataclass(frozen=True)
class StatusEntry:
    xy: str
    path: Path
    old_path: Path | None = None


class DuplicateMappingKey(ValueError):
    pass


class StrictSafeLoader(yaml.SafeLoader):
    pass


def construct_strict_mapping(
    loader: StrictSafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict:
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            if key in mapping:
                raise DuplicateMappingKey("mapping_duplicate_key")
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found unhashable key",
                key_node.start_mark,
            ) from exc
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_strict_mapping
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cross_agent_review.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--input-file", type=Path, required=True)
    run_parser.add_argument("--debug", action="store_true")
    run_parser.add_argument("--sdk-python", type=Path)
    retry_parser = subparsers.add_parser("retry")
    retry_parser.add_argument("--input-file", type=Path, required=True)
    retry_parser.add_argument("--debug", action="store_true")
    retry_parser.add_argument("--sdk-python", type=Path)
    revalidate_parser = subparsers.add_parser("revalidate")
    revalidate_parser.add_argument("--input-file", type=Path, required=True)
    revalidate_parser.add_argument("--previous-state", type=Path, required=True)
    mark_parser = subparsers.add_parser("mark-pass")
    mark_parser.add_argument("--input-file", type=Path, required=True)
    mark_parser.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    mark_parser.add_argument("--artifact-id", default=DEFAULT_ARTIFACT_ID)
    mark_parser.add_argument("--subject-id")
    mark_parser.add_argument("--subject-type", default=DEFAULT_SUBJECT_TYPE)
    role_input_parser = subparsers.add_parser("_role-input")
    role_input_parser.add_argument("--input-file", type=Path, required=True)
    role_input_parser.add_argument("--state-file", type=Path, required=True)
    role_input_parser.add_argument("--role", choices=REVIEWER_ROLES, required=True)
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


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


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


def project_relative_path(raw: str, project: Path) -> str:
    path = Path(raw)
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    if (
        path.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or windows.root
        or "\\" in raw
        or any(segment in {"", ".", ".."} for segment in raw.split("/"))
        or raw != posix.as_posix()
    ):
        raise ValueError(f"path_outside_project: {raw}")
    resolved = (project / path).resolve()
    try:
        relative = resolved.relative_to(project.resolve())
    except ValueError as exc:
        raise ValueError(f"path_outside_project: {raw}") from exc
    return relative.as_posix()


def parse_summary_only(value: object, project: Path) -> tuple[SummaryOnly, ...]:
    if not isinstance(value, list):
        raise ValueError("invalid_summary_only: expected_array")
    parsed: list[SummaryOnly] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "reason"}:
            raise ValueError("invalid_summary_only: invalid_entry")
        raw_path = item["path"]
        reason = item["reason"]
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError("invalid_summary_only: invalid_path")
        path = project_relative_path(raw_path, project)
        if path in seen:
            raise ValueError(f"invalid_summary_only: duplicate_path={path}")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"invalid_summary_only: empty_reason={path}")
        seen.add(path)
        parsed.append(SummaryOnly(path=path, reason=reason))
    return tuple(parsed)


def parse_revalidation_policy(value: object, project: Path) -> tuple[RevalidationPolicy, ...]:
    if not isinstance(value, list):
        raise ValueError("invalid_revalidation_policy: expected_array")
    parsed: list[RevalidationPolicy] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("invalid_revalidation_policy: invalid_entry")
        raw_path = item.get("path")
        validator = item.get("validator")
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError("invalid_revalidation_policy: invalid_path")
        path = project_relative_path(raw_path, project)
        if path in seen:
            raise ValueError(f"invalid_revalidation_policy: duplicate_path={path}")
        if not isinstance(validator, str) or validator not in {
            "checkbox-only",
            "mapping-fields-only",
        }:
            raise ValueError(f"invalid_revalidation_policy: invalid_validator={validator}")
        if validator == "checkbox-only":
            if set(item) != {"path", "validator"}:
                raise ValueError(f"invalid_revalidation_policy: invalid_fields={path}")
            policy = RevalidationPolicy(path=path, validator=validator)
        else:
            if set(item) != {"path", "validator", "format", "fields"}:
                if not isinstance(item.get("format"), str) or item.get("format") not in {
                    "json",
                    "yaml",
                }:
                    raise ValueError(f"invalid_revalidation_policy: invalid_format={path}")
                raise ValueError(f"invalid_revalidation_policy: invalid_fields={path}")
            format_name = item["format"]
            fields = item["fields"]
            if not isinstance(format_name, str) or format_name not in {"json", "yaml"}:
                raise ValueError(f"invalid_revalidation_policy: invalid_format={path}")
            if not isinstance(fields, list) or not fields or any(
                not isinstance(field, str) or not field for field in fields
            ):
                raise ValueError(f"invalid_revalidation_policy: invalid_fields={path}")
            if len(fields) != len(set(fields)):
                duplicate = next(field for index, field in enumerate(fields) if field in fields[:index])
                raise ValueError(f"invalid_revalidation_policy: duplicate_field={duplicate}")
            policy = RevalidationPolicy(
                path=path,
                validator=validator,
                format=format_name,
                fields=tuple(fields),
            )
        seen.add(path)
        parsed.append(policy)
    return tuple(parsed)


def validate_checkbox_only(before: bytes, after: bytes) -> str | None:
    try:
        before_lines = before.decode("utf-8").splitlines(keepends=True)
        after_lines = after.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return "checkbox_not_utf8"
    if len(before_lines) != len(after_lines):
        return "checkbox_line_count_changed"

    def normalized(line: str) -> str:
        return CHECKBOX.sub(r"\g<prefix> \g<suffix>", line)

    return (
        None
        if [normalized(line) for line in before_lines]
        == [normalized(line) for line in after_lines]
        else "checkbox_content_changed"
    )


def strict_json_mapping(pairs: list[tuple[str, object]]) -> dict:
    mapping = {}
    for key, value in pairs:
        if key in mapping:
            raise DuplicateMappingKey("mapping_duplicate_key")
        mapping[key] = value
    return mapping


def reject_nonstandard_json_constant(_value: str) -> None:
    raise ValueError("mapping_parse_failed")


def parse_declared_mapping(value: bytes, format_name: str) -> dict:
    if format_name not in {"json", "yaml"}:
        raise ValueError("mapping_unknown_format")
    try:
        text = value.decode("utf-8")
        if format_name == "json":
            parsed = json.loads(
                text,
                object_pairs_hook=strict_json_mapping,
                parse_constant=reject_nonstandard_json_constant,
            )
        else:
            parsed = yaml.load(text, Loader=StrictSafeLoader)
    except DuplicateMappingKey as exc:
        raise ValueError("mapping_duplicate_key") from exc
    except (UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError("mapping_parse_failed") from exc
    if not isinstance(parsed, dict):
        raise ValueError("mapping_not_mapping")
    if any(not isinstance(key, str) for key in parsed):
        raise ValueError("mapping_non_string_key")
    return parsed


def validate_mapping_fields_only(
    before: bytes,
    after: bytes,
    format_name: str,
    fields: tuple[str, ...],
) -> str | None:
    try:
        before_map = parse_declared_mapping(before, format_name)
        after_map = parse_declared_mapping(after, format_name)
    except ValueError as exc:
        return str(exc)
    changed = {
        key
        for key in set(before_map) | set(after_map)
        if before_map.get(key, MISSING) != after_map.get(key, MISSING)
    }
    if not changed <= set(fields):
        return "mapping_undeclared_field_changed"
    reduced_before = {key: value for key, value in before_map.items() if key not in fields}
    reduced_after = {key: value for key, value in after_map.items() if key not in fields}
    return None if reduced_before == reduced_after else "mapping_structure_changed"


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
        git_output(
            ["rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}"],
            cwd,
        )
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
    summary_only = parse_summary_only(payload.get("summary_only", []), Path.cwd())
    revalidation_policy = parse_revalidation_policy(
        payload.get("revalidation_policy", []), Path.cwd()
    )
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
        summary_only=summary_only,
        revalidation_policy=revalidation_policy,
    )


def name_status_entries(diff_range: str) -> list[dict]:
    output = git_output_bytes(
        [
            "diff",
            "--name-status",
            "-z",
            "--find-renames",
            "--find-copies-harder",
            diff_range,
        ],
        Path.cwd(),
    )
    if output and not output.endswith(b"\0"):
        raise ValueError("invalid_changed_file_entries")
    fields = output[:-1].split(b"\0") if output else []
    entries: list[dict] = []
    index = 0
    while index < len(fields):
        try:
            status = fields[index].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("invalid_changed_file_entries") from exc
        index += 1
        if status in {"A", "B", "D", "M", "T", "U", "X"}:
            path_count = 1
        elif (
            len(status) == 4
            and status[0] in {"R", "C"}
            and status[1:].isdigit()
            and int(status[1:]) <= 100
        ):
            path_count = 2
        else:
            raise ValueError("invalid_changed_file_entries")
        if index + path_count > len(fields) or any(
            not field for field in fields[index : index + path_count]
        ):
            raise ValueError("invalid_changed_file_entries")
        paths = [
            field.decode("utf-8", errors="surrogateescape")
            for field in fields[index : index + path_count]
        ]
        index += path_count
        if path_count == 2:
            entries.append(
                {
                    "status": status,
                    "path": project_relative_path(paths[1], Path.cwd()),
                    "old_path": project_relative_path(paths[0], Path.cwd()),
                }
            )
        else:
            entries.append(
                {
                    "status": status,
                    "path": project_relative_path(paths[0], Path.cwd()),
                }
            )
    return entries


def changed_file_entries(review_input: ReviewInput) -> list[dict]:
    return name_status_entries(f"{review_input.base_ref}...{review_input.head_ref}")


def incremental_changes(previous_head: str, current_head: str) -> list[dict]:
    return name_status_entries(f"{previous_head}..{current_head}")


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
    overlap = sorted(contexts & set(summaries))
    if overlap:
        raise ValueError(f"classification_overlap: paths={','.join(overlap)}")
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


def initial_review_state(review_input: ReviewInput) -> dict:
    files = classify_files(review_input, changed_file_entries(review_input))
    contexts = {
        name: {
            "path": path.resolve().relative_to(Path.cwd().resolve()).as_posix(),
            "hash": sha256_bytes(path.read_bytes()),
        }
        for name, path in {
            "spec": review_input.spec_file,
            "design": review_input.design_file,
            "plan": review_input.plan_file,
        }.items()
    }

    def role_scope() -> dict[str, list[str]]:
        return {
            classification: [
                item["path"] for item in files if item["classification"] == classification
            ]
            for classification in ("authoritative_context", "full_review", "summary_only")
        }

    return {
        "schema_version": "cross-agent-review-state/v1",
        "subject": {
            "change": review_input.change,
            "mode": review_input.mode,
            "base_ref": review_input.base_ref,
            "head_ref": review_input.head_ref,
            "head_ref_short": review_input.head_ref[:12],
            "input_file": review_input.input_file.resolve()
            .relative_to(Path.cwd().resolve())
            .as_posix(),
            "input_hash": sha256_bytes(review_input.input_file.read_bytes()),
            "contexts": contexts,
        },
        "files": files,
        "roles": {role: {"attempts": [], "scope": role_scope()} for role in REVIEWER_ROLES},
    }


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


def render_context_index(state: dict) -> str:
    lines = ["## Authoritative context"]
    for name, context in state["subject"]["contexts"].items():
        lines.append(f"- {name}: {context['path']} ({context['hash']})")
    return "\n".join(lines)


def render_summary_stats(review_input: ReviewInput, state: dict) -> str:
    summary_files = [
        item for item in state["files"] if item["classification"] == "summary_only"
    ]
    if not summary_files:
        return ""
    summary_paths = [item["path"] for item in summary_files]
    lines = ["## Summary-only changes"]
    lines.extend(
        f"- {item['path']}: {item['reason']} (status: {item['status']})"
        for item in summary_files
    )
    stats = git_output(
        [
            "diff",
            "--numstat",
            f"{review_input.base_ref}...{review_input.head_ref}",
            "--",
            *summary_paths,
        ],
        Path.cwd(),
    )
    if stats:
        lines.extend(["", stats])
    return "\n".join(lines)


def render_role_input(review_input: ReviewInput, state: dict, role: str) -> str:
    full_paths = state["roles"][role]["scope"]["full_review"]
    sections = [render_context_index(state), render_summary_stats(review_input, state)]
    if full_paths:
        sections.append(
            git_output(
                [
                    "diff",
                    f"{review_input.base_ref}...{review_input.head_ref}",
                    "--",
                    *full_paths,
                ],
                Path.cwd(),
            )
        )
    return "\n\n".join(part for part in sections if part).rstrip() + "\n"


def load_role_state(review_input: ReviewInput, state_file: Path, role: str) -> dict:
    expected_path = review_input.output_dir / "review-state.json"
    if state_file.resolve() != expected_path.resolve():
        raise ValueError(f"invalid_state_file_location: {state_file}")
    if not state_file.is_file():
        raise ValueError(f"missing_file: {state_file}")
    state = json.loads(state_file.read_text(encoding="utf-8"))
    subject = state.get("subject")
    if not isinstance(subject, dict) or subject.get("input_hash") != sha256_bytes(
        review_input.input_file.read_bytes()
    ):
        raise ValueError("input_hash_mismatch")
    current_head = git_output(["rev-parse", "HEAD"], Path.cwd())
    if current_head != review_input.head_ref:
        raise ValueError(
            f"head_ref_mismatch: expected={review_input.head_ref} actual={current_head}"
        )
    expected = initial_review_state(review_input)
    if subject != expected["subject"]:
        raise ValueError("state_subject_mismatch")
    role_state = state.get("roles", {}).get(role)
    if (
        state.get("schema_version") != expected["schema_version"]
        or state.get("files") != expected["files"]
        or not isinstance(role_state, dict)
        or role_state.get("scope") != expected["roles"][role]["scope"]
    ):
        raise ValueError("state_scope_mismatch")
    return state


def validate_reused_state_fields(state: dict) -> None:
    source_head = state.get("source_head_ref")
    source_state = state.get("source_state")
    changes = state.get("validated_changes")
    if (
        not isinstance(source_head, str)
        or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", source_head) is None
        or not isinstance(source_state, str)
        or not isinstance(changes, list)
    ):
        raise ValueError("state_mismatch")
    expected_source = (
        PurePosixPath(".local")
        / "cross-agent-review"
        / str(state["subject"].get("change", ""))
        / source_head[:12]
        / "review-state.json"
    ).as_posix()
    try:
        normalized_source = project_relative_path(source_state, Path.cwd())
    except ValueError as exc:
        raise ValueError("state_mismatch") from exc
    if normalized_source != expected_source:
        raise ValueError("state_mismatch")
    seen: set[str] = set()
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("state_mismatch")
        validator = change.get("validator")
        if validator not in {"checkbox-only", "mapping-fields-only"}:
            raise ValueError("state_mismatch")
        expected_fields = (
            {"path", "validator"}
            if validator == "checkbox-only"
            else {"path", "validator", "format", "fields"}
        )
        if set(change) != expected_fields:
            raise ValueError("state_mismatch")
        try:
            path = project_relative_path(change["path"], Path.cwd())
        except (TypeError, ValueError) as exc:
            raise ValueError("state_mismatch") from exc
        if path in seen:
            raise ValueError("state_mismatch")
        seen.add(path)
        if validator == "mapping-fields-only" and (
            change.get("format") not in {"json", "yaml"}
            or not isinstance(change.get("fields"), list)
            or not change["fields"]
            or any(not isinstance(field, str) or not field for field in change["fields"])
            or len(change["fields"]) != len(set(change["fields"]))
        ):
            raise ValueError("state_mismatch")


def validate_state_records(
    state: object,
    current_statuses: set[str] = TERMINAL_ROLE_STATUSES,
    attempt_statuses: set[str] = TERMINAL_ROLE_STATUSES,
) -> None:
    if (
        not isinstance(state, dict)
        or not isinstance(state.get("subject"), dict)
        or not isinstance(state.get("files"), list)
        or not isinstance(state.get("roles"), dict)
        or set(state["roles"]) != set(REVIEWER_ROLES)
        or not isinstance(state.get("report_hash"), str)
    ):
        raise ValueError("state_mismatch")
    has_reused = any(
        isinstance(state["roles"][role], dict)
        and state["roles"][role].get("status") == "reused"
        for role in REVIEWER_ROLES
    )
    if set(state) != STATE_FIELDS | (REUSED_STATE_FIELDS if has_reused else set()):
        raise ValueError("state_mismatch")
    if has_reused:
        validate_reused_state_fields(state)

    for role in REVIEWER_ROLES:
        role_state = state["roles"][role]
        if (
            not isinstance(role_state, dict)
            or set(role_state) != ROLE_STATE_FIELDS
            or not isinstance(role_state["scope"], dict)
            or not isinstance(role_state["attempts"], list)
            or not role_state["attempts"]
            or not isinstance(role_state["status"], str)
            or role_state["status"] not in current_statuses
            or not isinstance(role_state["output"], str)
            or not role_state["output"].strip()
            or not isinstance(role_state["output_hash"], str)
        ):
            raise ValueError("state_mismatch")
        previous_finished_at = None
        for number, attempt in enumerate(role_state["attempts"], start=1):
            if (
                not isinstance(attempt, dict)
                or set(attempt) != ATTEMPT_FIELDS
                or type(attempt["number"]) is not int
                or attempt["number"] != number
                or not isinstance(attempt["status"], str)
                or attempt["status"] not in attempt_statuses
                or not isinstance(attempt["output"], str)
                or not attempt["output"].strip()
                or not isinstance(attempt["output_hash"], str)
            ):
                raise ValueError("state_mismatch")
            if (role_state["status"] == "reused") != (attempt["status"] == "reused"):
                raise ValueError("state_mismatch")
            if attempt["output_hash"] != sha256_bytes(attempt["output"].encode("utf-8")):
                raise ValueError("output_hash_mismatch")
            timestamps = []
            for key in ("started_at", "finished_at"):
                value = attempt.get(key)
                if not isinstance(value, str) or not value.endswith("Z"):
                    raise ValueError("state_mismatch")
                try:
                    timestamp = datetime.fromisoformat(value[:-1] + "+00:00")
                except ValueError as exc:
                    raise ValueError("state_mismatch") from exc
                if timestamp.utcoffset() != UTC.utcoffset(None):
                    raise ValueError("state_mismatch")
                timestamps.append(timestamp)
            if timestamps[0] > timestamps[1] or (
                previous_finished_at is not None and timestamps[0] < previous_finished_at
            ):
                raise ValueError("state_mismatch")
            previous_finished_at = timestamps[1]
        if role_state["output_hash"] != sha256_bytes(role_state["output"].encode("utf-8")):
            raise ValueError("output_hash_mismatch")
        latest = role_state["attempts"][-1]
        if any(
            role_state[key] != latest[key]
            for key in ("status", "output", "output_hash")
        ):
            raise ValueError("state_mismatch")


def load_bound_state(review_input: ReviewInput) -> dict:
    state_file = review_input.output_dir / "review-state.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("state_mismatch") from exc
    validate_state_records(state)
    if state["subject"].get("input_hash") != sha256_bytes(
        review_input.input_file.read_bytes()
    ):
        raise ValueError("input_hash_mismatch")

    expected = initial_review_state(review_input)
    if (
        state.get("schema_version") != expected["schema_version"]
        or state["subject"] != expected["subject"]
        or state["files"] != expected["files"]
    ):
        raise ValueError("state_mismatch")
    for role in REVIEWER_ROLES:
        if state["roles"][role]["scope"] != expected["roles"][role]["scope"]:
            raise ValueError("retry_scope_mismatch")

    report_bytes = render_report(state).encode("utf-8")
    try:
        saved_report_bytes = (review_input.output_dir / "review-report.md").read_bytes()
    except OSError as exc:
        raise ValueError("output_hash_mismatch") from exc
    if saved_report_bytes != report_bytes or state["report_hash"] != sha256_bytes(report_bytes):
        raise ValueError("output_hash_mismatch")
    return state


def load_previous_state(path: Path) -> dict:
    state_file = path if path.is_absolute() else Path.cwd() / path
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("state_mismatch") from exc
    subject = state.get("subject") if isinstance(state, dict) else None
    if not isinstance(subject, dict):
        raise ValueError("state_mismatch")
    change = subject.get("change")
    head_ref = subject.get("head_ref")
    if not isinstance(change, str) or not isinstance(head_ref, str):
        raise ValueError("state_mismatch")
    expected = (
        Path.cwd()
        / ".local"
        / "cross-agent-review"
        / change
        / head_ref[:12]
        / "review-state.json"
    )
    try:
        state_file.resolve().relative_to(Path.cwd().resolve())
    except ValueError as exc:
        raise ValueError("previous_state_location_mismatch") from exc
    if (
        state_file.is_symlink()
        or state_file.resolve() != expected.resolve()
        or subject.get("head_ref_short") != head_ref[:12]
    ):
        raise ValueError("previous_state_location_mismatch")
    return state


def read_git_blob(ref: str, path: str) -> bytes:
    return git_output_bytes(["show", f"{ref}:{path}"], Path.cwd())


def review_input_from_state(state: dict) -> ReviewInput:
    input_path = state["subject"].get("input_file")
    if not isinstance(input_path, str):
        raise ValueError("state_mismatch")
    expected = (
        PurePosixPath(".local")
        / "cross-agent-review"
        / state["subject"]["change"]
        / state["subject"]["head_ref"][:12]
        / "prepared-inputs"
        / "review-input.json"
    ).as_posix()
    try:
        normalized = project_relative_path(input_path, Path.cwd())
    except ValueError as exc:
        raise ValueError("state_mismatch") from exc
    if normalized != expected:
        raise ValueError("state_mismatch")
    return load_review_input(
        argparse.Namespace(
            input_file=Path.cwd() / normalized,
            debug=False,
            sdk_python=None,
        )
    )


def context_relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path_outside_project: {path}") from exc


def validate_reuse_source(current: ReviewInput, previous_state: dict) -> ReviewInput:
    roles = previous_state.get("roles")
    if not isinstance(roles, dict) or set(roles) != set(REVIEWER_ROLES):
        raise ValueError("state_mismatch")
    statuses = [
        role_state.get("status") if isinstance(role_state, dict) else None
        for role_state in roles.values()
    ]
    if any(status != "completed" for status in statuses):
        raise ValueError("reused_source_not_allowed")
    validate_state_records(
        previous_state,
        current_statuses={"completed"},
        attempt_statuses={"completed", "failed", "timed_out"},
    )
    previous = review_input_from_state(previous_state)
    validate_base_ref(Path.cwd(), previous.base_ref)
    try:
        resolved_head = git_output(
            [
                "rev-parse",
                "--verify",
                "--end-of-options",
                f"{previous.head_ref}^{{commit}}",
            ],
            Path.cwd(),
        )
    except ValueError as exc:
        raise ValueError("state_mismatch") from exc
    if resolved_head != previous.head_ref:
        raise ValueError("state_mismatch")
    if previous_state["subject"].get("input_hash") != sha256_bytes(
        previous.input_file.read_bytes()
    ):
        raise ValueError("input_hash_mismatch")

    expected = initial_review_state(previous)
    contexts = previous_state["subject"].get("contexts")
    if not isinstance(contexts, dict) or set(contexts) != {"spec", "design", "plan"}:
        raise ValueError("state_mismatch")
    for name, expected_context in expected["subject"]["contexts"].items():
        context = contexts[name]
        if (
            not isinstance(context, dict)
            or set(context) != {"path", "hash"}
            or context.get("path") != expected_context["path"]
            or not isinstance(context.get("hash"), str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", context["hash"]) is None
        ):
            raise ValueError("state_mismatch")
    expected["subject"]["contexts"] = contexts
    if (
        previous_state.get("schema_version") != expected["schema_version"]
        or previous_state["subject"] != expected["subject"]
        or previous_state["files"] != expected["files"]
    ):
        raise ValueError("state_mismatch")
    for role in REVIEWER_ROLES:
        if previous_state["roles"][role]["scope"] != expected["roles"][role]["scope"]:
            raise ValueError("state_mismatch")

    report = render_report(previous_state).encode("utf-8")
    try:
        saved_report = (previous.output_dir / "review-report.md").read_bytes()
    except OSError as exc:
        raise ValueError("output_hash_mismatch") from exc
    if saved_report != report or previous_state["report_hash"] != sha256_bytes(report):
        raise ValueError("output_hash_mismatch")

    comparable = {
        "change": (current.change, previous.change),
        "mode": (current.mode, previous.mode),
        "base_ref": (current.base_ref, previous.base_ref),
        "spec_file": (
            context_relative_path(current.spec_file),
            context_relative_path(previous.spec_file),
        ),
        "design_file": (
            context_relative_path(current.design_file),
            context_relative_path(previous.design_file),
        ),
        "plan_file": (
            context_relative_path(current.plan_file),
            context_relative_path(previous.plan_file),
        ),
        "summary_only": (current.summary_only, previous.summary_only),
    }
    mismatch = next((name for name, values in comparable.items() if values[0] != values[1]), None)
    if mismatch is not None:
        raise ValueError(f"reuse_source_mismatch: {mismatch}")
    return previous


def previous_runtime_allowed_paths(state_path: Path) -> list[Path]:
    output_dir = state_path.parent
    debug_dir = output_dir / "debug"
    return [
        output_dir / "prepared-inputs" / "review-input.json",
        output_dir / "review-report.md",
        output_dir / "review-pass.json",
        output_dir / "review-state.json",
        debug_dir / "review-input.json",
        *(debug_dir / "prompts" / f"{role}.txt" for role in REVIEWER_ROLES),
        *(debug_dir / "raw" / f"{role}.txt" for role in REVIEWER_ROLES),
    ]


def validate_declared_changes(
    current: ReviewInput,
    changes: list[dict],
    previous_head: str | None = None,
) -> list[dict]:
    if not current.revalidation_policy:
        raise ValueError("reuse_policy_missing")
    protected = {
        context_relative_path(current.spec_file),
        context_relative_path(current.design_file),
    }
    policies: dict[str, list[RevalidationPolicy]] = {}
    for policy in current.revalidation_policy:
        policies.setdefault(policy.path, []).append(policy)
    validated: list[dict] = []
    for change in changes:
        status = change.get("status")
        path = change.get("path")
        if status != "M":
            raise ValueError(f"unsupported_change_status: {status} path={path}")
        if path in protected:
            raise ValueError(f"validator_failed: protected_context_changed={path}")
        matches = policies.get(path, [])
        if not matches:
            raise ValueError(f"reuse_policy_missing: {path}")
        if len(matches) != 1:
            raise ValueError(f"reuse_policy_overlap: {path}")
        policy = matches[0]
        if previous_head is None:
            raise ValueError("validator_failed: previous_head_missing")
        try:
            before = read_git_blob(previous_head, path)
            after = read_git_blob(current.head_ref, path)
        except ValueError as exc:
            raise ValueError(f"validator_failed: git_blob_unavailable={path}") from exc
        if policy.validator == "checkbox-only":
            reason = validate_checkbox_only(before, after)
            result = {"path": path, "validator": policy.validator}
        else:
            reason = validate_mapping_fields_only(
                before,
                after,
                policy.format or "",
                policy.fields,
            )
            result = {
                "path": path,
                "validator": policy.validator,
                "format": policy.format,
                "fields": list(policy.fields),
            }
        if reason is not None:
            raise ValueError(f"validator_failed: {path}: {reason}")
        validated.append(result)
    return validated


def reused_state(
    current: ReviewInput,
    previous_state: dict,
    validations: list[dict],
    source_state: Path,
) -> dict:
    state = initial_review_state(current)
    state.update(
        {
            "source_head_ref": previous_state["subject"]["head_ref"],
            "source_state": source_state.resolve()
            .relative_to(Path.cwd().resolve())
            .as_posix(),
            "validated_changes": validations,
        }
    )
    for role in REVIEWER_ROLES:
        record_role_result(
            state,
            role,
            "reused",
            previous_state["roles"][role]["output"],
        )
    return state


def run_role_input(args: argparse.Namespace) -> int:
    try:
        review_input = load_review_input(args)
        state = load_role_state(review_input, args.state_file, args.role)
        print(render_role_input(review_input, state, args.role), end="")
    except (ValueError, json.JSONDecodeError) as exc:
        print("status: failed")
        print(f"error: {exc}")
        return 1
    return 0


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


def markdown_review(role: str, text: str, execution_status: str = "completed") -> dict:
    return {
        "role": role,
        "execution_status": execution_status,
        "text": text.strip() + "\n",
    }


def render_template(path: Path, values: dict[str, str]) -> str:
    rendered = path.read_text(encoding="utf-8")
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{ {key} }}}}", value)
    return rendered


def reviewer_prompt(review_args: ReviewInput, role: str) -> str:
    state_file = review_args.output_dir / "review-state.json"
    role_input_command = subprocess.list2cmdline(
        [
            "python",
            str(SCRIPT_PATH),
            "_role-input",
            "--input-file",
            str(review_args.input_file),
            "--state-file",
            str(state_file),
            "--role",
            role,
        ]
    )
    return render_template(
        REVIEWER_PROMPT_TEMPLATE,
        {
            "role": role,
            "input_file_path": str(review_args.input_file),
            "state_file_path": str(state_file),
            "role_input_command": role_input_command,
            "severity_rubric": SEVERITY_RUBRIC,
            "role_focus": ROLE_FOCUS.get(role, ""),
        },
    )


def reviewer_failure(
    role: str,
    summary: str,
    evidence: str,
    recommendation: str,
    execution_status: str = "failed",
) -> dict:
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
        execution_status,
    )


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


def invalid_sdk_role_result(role: str, evidence: str) -> tuple[str, str]:
    failure = reviewer_failure(
        role,
        "Reviewer SDK dispatch failed",
        evidence,
        "Rerun review after checking Claude Agent SDK availability.",
    )
    return "failed", failure["text"]


def run_sdk_role_subprocess(
    review_input: ReviewInput, sdk_python: str, role: str
) -> tuple[str, str]:
    payload = {
        "cwd": str(Path.cwd()),
        "roles": [role],
        "prompts": {role: reviewer_prompt(review_input, role)},
        "force_exit": True,
    }
    if review_input.debug:
        payload["raw_dir"] = str(debug_dir_for(review_input) / "raw")
    try:
        result = subprocess.run(
            [sdk_python, str(SCRIPT_PATH), "_sdk-dispatch"],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
            timeout=SDK_DISPATCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        failure = reviewer_failure(
            role,
            "Reviewer dispatch timed out",
            f"Exceeded {SDK_DISPATCH_TIMEOUT_SECONDS} seconds.",
            "Rerun review after checking Claude Agent SDK availability.",
            "timed_out",
        )
        return "timed_out", failure["text"]
    if result.returncode != 0:
        return invalid_sdk_role_result(
            role, f"sdk_dispatch_failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return invalid_sdk_role_result(role, "sdk_dispatch_invalid_output: stdout was not valid JSON")
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        return invalid_sdk_role_result(role, "sdk_dispatch_invalid_output: expected one result")
    item = data[0]
    status = item.get("execution_status")
    text = item.get("text")
    if (
        item.get("role") != role
        or status not in {"completed", "failed", "timed_out"}
        or not isinstance(text, str)
        or not text.strip()
    ):
        return invalid_sdk_role_result(role, "sdk_dispatch_invalid_output: invalid role result")
    return status, text


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def record_role_result(
    state: dict,
    role: str,
    status: str,
    output: str,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    if not isinstance(output, str) or not output.strip():
        failure = reviewer_failure(
            role,
            "Reviewer returned empty output",
            "<empty reviewer result>",
            "Rerun review after checking reviewer prompt.",
        )
        status, output = "failed", failure["text"]
    output_hash = sha256_bytes(output.encode("utf-8"))
    role_state = state["roles"][role]
    started_at = started_at or utc_now()
    finished_at = finished_at or utc_now()
    previous_finished_at = (
        role_state["attempts"][-1]["finished_at"]
        if role_state["attempts"]
        else started_at
    )
    if datetime.fromisoformat(started_at[:-1] + "+00:00") < datetime.fromisoformat(
        previous_finished_at[:-1] + "+00:00"
    ):
        started_at = previous_finished_at
    if datetime.fromisoformat(finished_at[:-1] + "+00:00") < datetime.fromisoformat(
        started_at[:-1] + "+00:00"
    ):
        finished_at = started_at
    attempt = {
        "number": len(role_state["attempts"]) + 1,
        "started_at": started_at,
        "finished_at": finished_at,
        "status": status,
        "output": output,
        "output_hash": output_hash,
    }
    role_state["attempts"].append(attempt)
    role_state.update(
        {key: attempt[key] for key in ("status", "output", "output_hash")}
    )


def dispatch_roles(
    review_input: ReviewInput,
    sdk_python: str,
    state: dict,
    roles: Sequence[str],
) -> dict:
    state_path = review_input.output_dir / "review-state.json"
    if review_input.debug:
        write_debug_dispatch_artifacts(
            review_input, {role: reviewer_prompt(review_input, role) for role in roles}
        )
    with ThreadPoolExecutor(max_workers=len(roles)) as executor:
        futures = {}
        for role in roles:
            started_at = utc_now()
            future = executor.submit(
                run_sdk_role_subprocess, review_input, sdk_python, role
            )
            futures[future] = (role, started_at)
        for future in as_completed(futures):
            role, started_at = futures[future]
            try:
                status, output = future.result()
            except Exception as error:
                status = "failed"
                failure = reviewer_failure(
                    role,
                    "Reviewer SDK dispatch failed",
                    f"{type(error).__name__}: {error}",
                    "Retry",
                )
                output = failure["text"]
            finished_at = utc_now()
            record_role_result(
                state, role, status, output, started_at, finished_at
            )
            atomic_write_json(state_path, state)
    return state


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
            if isinstance(result_text, str) and result_text.strip():
                result = markdown_review(role, result_text)
            else:
                result = reviewer_failure(
                    role,
                    "Reviewer returned empty output",
                    "<empty reviewer result>",
                    "Rerun review after checking reviewer prompt.",
                )
            write_raw(role, result["text"])
            return result

        async def run_one(role: str) -> dict:
            try:
                return await asyncio.wait_for(query_one(role), timeout=SDK_REVIEWER_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                evidence = f"Exceeded {SDK_REVIEWER_TIMEOUT_SECONDS} seconds."
                failure = reviewer_failure(
                    role,
                    "Reviewer timed out",
                    evidence,
                    "Rerun review after checking Claude Agent SDK availability.",
                    "timed_out",
                )
                write_raw(role, failure["text"])
                return failure
            except Exception as error:
                failure = reviewer_failure(
                    role,
                    "Reviewer SDK dispatch failed",
                    f"{type(error).__name__}: {error}",
                    "Rerun review after checking Claude Agent SDK availability.",
                )
                write_raw(role, failure["text"])
                return failure

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


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_report(state: dict) -> str:
    subject = state["subject"]
    lines = [
        f"# Cross-Agent Review: {subject['change']}",
        "",
        f"- Base ref: `{subject['base_ref']}`",
        f"- Head ref: `{subject['head_ref']}`",
        "",
        "## Reviewer Outputs",
        "",
    ]
    for role in REVIEWER_ROLES:
        text = state["roles"][role].get("output")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"role_output_missing: {role}")
        text = text.strip()
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
        output_dir / "review-state.json",
        debug_dir / "review-input.json",
        *(debug_dir / "prompts" / f"{role}.txt" for role in REVIEWER_ROLES),
        *(debug_dir / "raw" / f"{role}.txt" for role in REVIEWER_ROLES),
    ]


def write_outputs(review_args: ReviewInput, state: dict) -> int:
    out_dir = output_dir_for(review_args)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_bytes = render_report(state).encode("utf-8")
    report_path = out_dir / "review-report.md"
    report_path.write_bytes(report_bytes)
    state["report_hash"] = sha256_bytes(report_bytes)
    atomic_write_json(out_dir / "review-state.json", state)
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
    print(f"head_ref_short: {short_ref(review_args.head_ref)}")
    print(f"path: {pass_path.relative_to(Path.cwd())}")
    return 0


def run_review(args: argparse.Namespace) -> int:
    try:
        review_args = load_review_input(args)
        validate_base_ref(Path.cwd(), review_args.base_ref)
        allowed_paths = runtime_allowed_paths(review_args)
        ensure_clean_subject(Path.cwd(), review_args.head_ref, allowed_paths)
        sdk_python = resolve_sdk_python(review_args.sdk_python, require_real_sdk=True)
        ensure_clean_subject(Path.cwd(), review_args.head_ref, allowed_paths)
        state = initial_review_state(review_args)
        atomic_write_json(review_args.output_dir / "review-state.json", state)
        dispatch_roles(review_args, sdk_python, state, REVIEWER_ROLES)
        status = write_outputs(review_args, state)
    except (ValueError, json.JSONDecodeError) as exc:
        print("status: failed")
        print(f"error: {exc}")
        return 1
    print("status: review_ready")
    print(f"head_ref_short: {short_ref(review_args.head_ref)}")
    print(f"input_file: {review_args.input_file.relative_to(Path.cwd())}")
    return status


def retryable_roles(state: dict) -> list[str]:
    return [
        role
        for role in REVIEWER_ROLES
        if state["roles"][role].get("status") in {"failed", "timed_out"}
    ]


def run_retry(args: argparse.Namespace) -> int:
    try:
        review_input = load_review_input(args)
        allowed_paths = runtime_allowed_paths(review_input)
        ensure_clean_subject(Path.cwd(), review_input.head_ref, allowed_paths)
        state = load_bound_state(review_input)
        roles = retryable_roles(state)
        if not roles:
            print("status: no_retryable_roles")
            return 1
        sdk_python = resolve_sdk_python(review_input.sdk_python, require_real_sdk=True)
        dispatch_roles(review_input, sdk_python, state, roles)
        return write_outputs(review_input, state)
    except (ValueError, json.JSONDecodeError) as exc:
        print("status: failed")
        print(f"error: {exc}")
        return 1


def run_revalidate(args: argparse.Namespace) -> int:
    try:
        current = load_review_input(args)
        validate_base_ref(Path.cwd(), current.base_ref)
        source_path = (
            args.previous_state
            if args.previous_state.is_absolute()
            else Path.cwd() / args.previous_state
        )
        previous_state = load_previous_state(source_path)
        ensure_clean_subject(
            Path.cwd(),
            current.head_ref,
            [*runtime_allowed_paths(current), *previous_runtime_allowed_paths(source_path)],
        )
        previous = validate_reuse_source(current, previous_state)
        changes = incremental_changes(previous.head_ref, current.head_ref)
        validations = validate_declared_changes(current, changes, previous.head_ref)
        state = reused_state(current, previous_state, validations, source_path)
        status = write_outputs(current, state)
    except (ValueError, json.JSONDecodeError, UnicodeError) as exc:
        print("status: failed")
        print(f"error: {exc}")
        return 1
    print("status: review_revalidated")
    print(f"head_ref_short: {short_ref(current.head_ref)}")
    print(f"report: {(current.output_dir / 'review-report.md').relative_to(Path.cwd())}")
    print(f"state: {(current.output_dir / 'review-state.json').relative_to(Path.cwd())}")
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    if parsed.command == "_sdk-dispatch":
        return run_sdk_dispatch()
    if parsed.command == "_role-input":
        return run_role_input(parsed)
    if parsed.command == "run":
        return run_review(parsed)
    if parsed.command == "retry":
        return run_retry(parsed)
    if parsed.command == "revalidate":
        return run_revalidate(parsed)
    if parsed.command == "mark-pass":
        return run_mark_pass(parsed)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
