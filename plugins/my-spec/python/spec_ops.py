from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from management import (
    ManagementError,
    add_management_parsers,
    implementation_identity,
    resolve_worktree,
    run_management,
)


REQUIREMENT = re.compile(r"^### Requirement: (\S.*)$")
SCENARIO = re.compile(r"^#### Scenario: (\S.*)$")
CAPABILITY = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
OPERATIONS = ("RENAMED", "REMOVED", "MODIFIED", "ADDED")
OPERATION_HEADING = re.compile(r"^## (ADDED|MODIFIED|REMOVED|RENAMED) Requirements$")
RUN_STATUSES = ("ANALYZING", "WAITING_DECISION", "READY_TO_APPLY")
DECISIONS = ("accept", "ignore", "accept-modified", "defer")
CONFLICT_FIELDS = ("id", "candidate", "evidence", "reason", "recommendation")
CONTEXT_FIELDS = (
    "workRoot",
    "targetWorktree",
    "specsRoot",
    "deltaRoot",
    "previewRoot",
    "specsContentFingerprint",
    "deltaContentFingerprint",
    "previewContentFingerprint",
    "implementationIdentity",
)


class SpecError(ValueError):
    pass


@dataclass
class MainSpec:
    name: str
    purpose: str
    requirements: OrderedDict[str, str] = field(default_factory=OrderedDict)


@dataclass
class DeltaSpec:
    capability: str
    name: str | None
    purpose: str | None
    operations: dict[str, OrderedDict[str, str] | list[tuple[str, str]]]


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeError) as exc:
        raise SpecError(f"cannot_read: {path}: {exc}") from exc


def _spec_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if not root.is_dir():
        raise SpecError(f"not_directory: {root}")
    files = sorted(root.rglob("*.md"))
    for path in files:
        relative = path.relative_to(root)
        if len(relative.parts) != 2 or relative.name != "spec.md":
            raise SpecError(f"invalid_spec_path: {relative.as_posix()}")
        if not CAPABILITY.fullmatch(relative.parent.name):
            raise SpecError(f"invalid_capability_name: {relative.parent.name}")
    return files


def _requirement_blocks(
    lines: list[str], *, allow_empty_body: bool, merge_identical_duplicates: bool = False
) -> OrderedDict[str, str]:
    starts = [index for index, line in enumerate(lines) if REQUIREMENT.fullmatch(line)]
    stray = [line for line in lines if line.startswith("### ") and not REQUIREMENT.fullmatch(line)]
    if stray:
        raise SpecError(f"invalid_requirement_heading: {stray[0]}")
    result: OrderedDict[str, str] = OrderedDict()
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        title = REQUIREMENT.fullmatch(lines[start]).group(1)  # type: ignore[union-attr]
        block = "\n".join(lines[start:end]).strip() + "\n"
        if title in result:
            if merge_identical_duplicates and result[title] == block:
                continue
            raise SpecError(f"duplicate_requirement: {title}")
        if not allow_empty_body:
            _validate_requirement(title, block)
        result[title] = block
    remaining = [line for line in lines[: starts[0] if starts else len(lines)] if line.strip()]
    if remaining:
        raise SpecError(f"content_outside_requirement: {remaining[0]}")
    return result


def _validate_requirement(title: str, block: str) -> None:
    if not re.search(r"\b(?:MUST|SHALL)\b", block):
        raise SpecError(f"missing_must_or_shall: {title}")
    lines = block.splitlines()
    starts = [index for index, line in enumerate(lines) if SCENARIO.fullmatch(line)]
    if not starts:
        raise SpecError(f"missing_scenario: {title}")
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        scenario = lines[start:end]
        if not any(re.fullmatch(r"- \*\*WHEN\*\* \S.*", line) for line in scenario):
            raise SpecError(f"missing_when: {title}: {lines[start]}")
        if not any(re.fullmatch(r"- \*\*THEN\*\* \S.*", line) for line in scenario):
            raise SpecError(f"missing_then: {title}: {lines[start]}")


def _parse_main(path: Path, *, merge_identical_duplicates: bool = False) -> MainSpec:
    lines = _text(path).splitlines()
    if not lines or not re.fullmatch(r"# \S.*", lines[0]):
        raise SpecError(f"missing_capability_heading: {path}")
    if lines.count("## Purpose") != 1 or lines.count("## Requirements") != 1:
        raise SpecError(f"missing_or_duplicate_main_section: {path}")
    purpose_index = lines.index("## Purpose")
    requirements_index = lines.index("## Requirements")
    if not 0 < purpose_index < requirements_index:
        raise SpecError(f"invalid_main_section_order: {path}")
    other_h2 = [line for line in lines if line.startswith("## ") and line not in {"## Purpose", "## Requirements"}]
    if other_h2:
        raise SpecError(f"unknown_main_section: {other_h2[0]}")
    purpose = "\n".join(lines[purpose_index + 1 : requirements_index]).strip()
    if not purpose:
        raise SpecError(f"empty_purpose: {path}")
    requirements = _requirement_blocks(
        lines[requirements_index + 1 :],
        allow_empty_body=False,
        merge_identical_duplicates=merge_identical_duplicates,
    )
    return MainSpec(lines[0][2:].strip(), purpose, requirements)


def _load_main(root: Path, *, merge_identical_duplicates: bool = False) -> OrderedDict[str, MainSpec]:
    specs: OrderedDict[str, MainSpec] = OrderedDict()
    titles: dict[str, tuple[Path, str]] = {}
    for path in _spec_files(root):
        capability = path.parent.name
        spec = _parse_main(path, merge_identical_duplicates=merge_identical_duplicates)
        specs[capability] = spec
        for title, block in list(spec.requirements.items()):
            if title in titles:
                previous_path, previous_block = titles[title]
                if merge_identical_duplicates and previous_block == block:
                    del spec.requirements[title]
                    continue
                raise SpecError(f"duplicate_requirement_global: {title}: {previous_path}: {path}")
            titles[title] = (path, block)
    return specs


def _parse_delta(path: Path) -> DeltaSpec:
    lines = _text(path).splitlines()
    headings = [(index, match.group(1)) for index, line in enumerate(lines) if (match := OPERATION_HEADING.fullmatch(line))]
    unknown_h2 = [line for line in lines if line.startswith("## ") and line != "## Purpose" and not OPERATION_HEADING.fullmatch(line)]
    if unknown_h2:
        raise SpecError(f"unknown_delta_section: {unknown_h2[0]}")
    seen: set[str] = set()
    for _index, operation in headings:
        if operation in seen:
            raise SpecError(f"duplicate_delta_section: {operation}: {path}")
        seen.add(operation)

    first_operation = headings[0][0] if headings else len(lines)
    prefix = lines[:first_operation]
    name = prefix[0][2:].strip() if prefix and re.fullmatch(r"# \S.*", prefix[0]) else None
    purpose = None
    if "## Purpose" in prefix:
        index = prefix.index("## Purpose")
        purpose = "\n".join(prefix[index + 1 :]).strip() or None
    operations: dict[str, OrderedDict[str, str] | list[tuple[str, str]]] = {
        operation: [] if operation == "RENAMED" else OrderedDict() for operation in OPERATIONS
    }
    for position, (start, operation) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        body = lines[start + 1 : end]
        if operation == "RENAMED":
            content = [line.strip().removeprefix("- ") for line in body if line.strip()]
            if len(content) % 2:
                raise SpecError(f"invalid_rename_pairs: {path}")
            pairs: list[tuple[str, str]] = []
            for pair_index in range(0, len(content), 2):
                source, target = content[pair_index : pair_index + 2]
                if not source.startswith("FROM: ") or not target.startswith("TO: "):
                    raise SpecError(f"invalid_rename_pair: {path}")
                pairs.append((source[6:].strip(), target[4:].strip()))
            operations[operation] = pairs
        else:
            operations[operation] = _requirement_blocks(body, allow_empty_body=operation == "REMOVED")
    return DeltaSpec(path.parent.name, name, purpose, operations)


def _load_delta(root: Path) -> list[DeltaSpec]:
    return [_parse_delta(path) for path in _spec_files(root)]


def validate_main(root: Path) -> None:
    _load_main(root)


def validate_delta(delta_root: Path, specs_root: Path) -> None:
    specs = _load_main(specs_root, merge_identical_duplicates=True)
    deltas = _load_delta(delta_root)
    locations = {title: capability for capability, spec in specs.items() for title in spec.requirements}
    contents = {title: block for spec in specs.values() for title, block in spec.requirements.items()}
    touched: set[str] = set()

    for delta in deltas:
        for old, new in delta.operations["RENAMED"]:  # type: ignore[union-attr]
            if not old or not new:
                raise SpecError("empty_rename_title")
            if old in touched or new in touched:
                raise SpecError(f"requirement_used_by_multiple_operations: {old}")
            touched.update((old, new))
            if old in locations and new not in locations:
                locations[new] = delta.capability
                contents[new] = _replace_heading(contents[old], new)
                del locations[old]
                del contents[old]
            elif old not in locations and locations.get(new) == delta.capability:
                continue
            elif new in locations:
                raise SpecError(f"rename_target_exists: {new}")
            else:
                raise SpecError(f"rename_source_missing: {old}")

    for operation in ("REMOVED", "MODIFIED", "ADDED"):
        for delta in deltas:
            blocks = delta.operations[operation]
            assert isinstance(blocks, OrderedDict)
            for title, block in blocks.items():
                if title in touched:
                    raise SpecError(f"requirement_used_by_multiple_operations: {title}")
                touched.add(title)
                if operation == "REMOVED":
                    locations.pop(title, None)
                    contents.pop(title, None)
                    continue
                _validate_requirement(title, block)
                if operation == "MODIFIED":
                    if title not in locations:
                        raise SpecError(f"modified_source_missing: {title}")
                    locations[title] = delta.capability
                    contents[title] = block
                elif title not in locations:
                    locations[title] = delta.capability
                    contents[title] = block
                elif locations[title] != delta.capability or contents[title] != block:
                    raise SpecError(f"added_requirement_exists: {title}")

    existing = set(specs)
    for delta in deltas:
        has_target_content = any(delta.operations[operation] for operation in OPERATIONS if operation != "REMOVED")
        if has_target_content and delta.capability not in existing and not delta.purpose:
            raise SpecError(f"new_capability_requires_purpose: {delta.capability}")


def _replace_heading(block: str, title: str) -> str:
    lines = block.splitlines()
    lines[0] = f"### Requirement: {title}"
    return "\n".join(lines).strip() + "\n"


def _find(specs: OrderedDict[str, MainSpec], title: str) -> tuple[str, str]:
    for capability, spec in specs.items():
        if title in spec.requirements:
            return capability, spec.requirements[title]
    raise SpecError(f"requirement_missing: {title}")


def _target(specs: OrderedDict[str, MainSpec], delta: DeltaSpec) -> MainSpec:
    if delta.capability not in specs:
        if not delta.purpose:
            raise SpecError(f"new_capability_requires_purpose: {delta.capability}")
        specs[delta.capability] = MainSpec(delta.name or delta.capability.replace("-", " ").title(), delta.purpose)
    return specs[delta.capability]


def _render(spec: MainSpec) -> str:
    blocks = "\n".join(block.rstrip() for block in spec.requirements.values())
    suffix = f"\n{blocks}\n" if blocks else "\n"
    return f"# {spec.name}\n\n## Purpose\n\n{spec.purpose.strip()}\n\n## Requirements\n{suffix}"


def _write_preview(
    specs: OrderedDict[str, MainSpec], output_root: Path, source_root: Path
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for capability, spec in specs.items():
        directory = output_root / capability
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / "spec.md"
        source = source_root / capability / "spec.md"
        try:
            unchanged = source.is_file() and _parse_main(source) == spec
        except SpecError:
            unchanged = False
        if unchanged:
            shutil.copyfile(source, destination)
        else:
            destination.write_bytes(_render(spec).encode("utf-8"))
    validate_main(output_root)


def _merged_specs(specs_root: Path, delta_root: Path) -> OrderedDict[str, MainSpec]:
    validate_delta(delta_root, specs_root)
    specs = _load_main(specs_root, merge_identical_duplicates=True)
    deltas = _load_delta(delta_root)
    locations = {title: capability for capability, spec in specs.items() for title in spec.requirements}
    for delta in deltas:
        for old, new in delta.operations["RENAMED"]:  # type: ignore[union-attr]
            if old not in locations:
                continue
            source_capability, block = _find(specs, old)
            del specs[source_capability].requirements[old]
            _target(specs, delta).requirements[new] = _replace_heading(block, new)
            del locations[old]
            locations[new] = delta.capability
    for operation in ("REMOVED", "MODIFIED", "ADDED"):
        for delta in deltas:
            blocks = delta.operations[operation]
            assert isinstance(blocks, OrderedDict)
            for title, block in blocks.items():
                if operation == "REMOVED":
                    if title in locations:
                        del specs[locations.pop(title)].requirements[title]
                    continue
                if title in locations:
                    source = specs[locations[title]].requirements[title]
                    if operation == "ADDED" or (locations[title] == delta.capability and source == block):
                        continue
                    if operation == "MODIFIED" and locations[title] == delta.capability:
                        specs[delta.capability].requirements[title] = block
                        continue
                    del specs[locations[title]].requirements[title]
                _target(specs, delta).requirements[title] = block
                locations[title] = delta.capability
    return specs


def _canonical_path(path: Path) -> Path:
    return Path(os.path.realpath(os.path.abspath(path.expanduser())))


def _tree_fingerprint(root: Path) -> str:
    if not root.exists():
        return "missing"
    if not root.is_dir():
        raise SpecError(f"not_directory: {root}")
    digest = hashlib.sha256()
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def _same_tree(left: Path, right: Path) -> bool:
    if not left.is_dir() or not right.is_dir():
        return False
    left_files = {path.relative_to(left).as_posix(): path for path in left.rglob("*") if path.is_file()}
    right_files = {path.relative_to(right).as_posix(): path for path in right.rglob("*") if path.is_file()}
    if left_files.keys() != right_files.keys():
        return False
    return all(left_files[relative].read_bytes() == right_files[relative].read_bytes() for relative in left_files)


def _validate_context_document(state: dict[str, object]) -> None:
    if any(field not in state for field in CONTEXT_FIELDS):
        raise SpecError("invalid_state_context")
    for field in CONTEXT_FIELDS:
        value = state[field]
        if field == "targetWorktree":
            if value is not None and not isinstance(value, str):
                raise SpecError("invalid_state_context")
        elif field.endswith("Root"):
            if value is not None and not isinstance(value, str):
                raise SpecError("invalid_state_context")
        elif field == "implementationIdentity":
            if not isinstance(value, str) or not value.strip():
                raise SpecError("invalid_state_context")
        elif field.endswith("Fingerprint"):
            if value is not None and not isinstance(value, str):
                raise SpecError("invalid_state_context")


def _state_path_context(
    state: dict[str, object],
    work_root: Path,
    specs_root: Path,
    delta_root: Path,
    output_root: Path,
) -> tuple[Path, Path, Path, Path]:
    _validate_context_document(state)
    work = _canonical_path(work_root)
    specs = _canonical_path(specs_root)
    delta = _canonical_path(delta_root)
    output = _canonical_path(output_root)
    if state["workRoot"] != str(work):
        raise SpecError("work_root_changed")
    target = state["targetWorktree"]
    if isinstance(target, str):
        target_path = _canonical_path(Path(target))
        expected = os.path.normcase(os.path.abspath(str(target_path)))
        paths = [("work", work), ("specs", specs), ("delta", delta), ("output", output)]
        for field, value in (("specsRoot", state["specsRoot"]), ("deltaRoot", state["deltaRoot"]), ("previewRoot", state["previewRoot"])):
            if isinstance(value, str):
                paths.append((field, _canonical_path(Path(value))))
        for label, path in paths:
            resolved = resolve_worktree(path)
            if resolved is None or os.path.normcase(os.path.abspath(str(resolved))) != expected:
                raise SpecError(f"cross_worktree_path: {label}")
    return work, specs, delta, output


def _bind_preview_context(
    state: dict[str, object],
    work_root: Path,
    specs_root: Path,
    delta_root: Path,
    preview_root: Path,
) -> None:
    work, specs, delta, preview = _state_path_context(
        state, work_root, specs_root, delta_root, preview_root
    )
    if state["specsRoot"] is None:
        state.update(
            {
                "workRoot": str(work),
                "specsRoot": str(specs),
                "deltaRoot": str(delta),
                "previewRoot": str(preview),
            }
        )
        return
    if (state["specsRoot"], state["deltaRoot"], state["previewRoot"]) != (
        str(specs),
        str(delta),
        str(preview),
    ):
        raise SpecError("spec_context_changed")


def _assert_bound_content(state: dict[str, object], specs_root: Path, delta_root: Path) -> None:
    expected_specs = state["specsContentFingerprint"]
    expected_delta = state["deltaContentFingerprint"]
    if not isinstance(expected_specs, str) or not expected_specs.strip():
        raise SpecError("invalid_state_context")
    if not isinstance(expected_delta, str) or not expected_delta.strip():
        raise SpecError("invalid_state_context")
    if _tree_fingerprint(specs_root) != expected_specs:
        raise SpecError("specs_content_changed")
    if _tree_fingerprint(delta_root) != expected_delta:
        raise SpecError("input_content_changed")


def _replace_directory(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    source.rename(destination)


def _refresh_preview(
    state: dict[str, object],
    specs: OrderedDict[str, MainSpec],
    specs_root: Path,
    preview_root: Path,
    identity: str,
) -> None:
    if not preview_root.is_dir():
        raise SpecError(f"preview_missing: {preview_root}")
    validate_main(preview_root)
    if state["previewContentFingerprint"] != _tree_fingerprint(preview_root):
        raise SpecError("preview_content_changed")
    if state["implementationIdentity"] == identity:
        return

    temporary = preview_root.parent / f".my-spec-preview-refresh-{uuid.uuid4().hex}"
    try:
        _write_preview(specs, temporary, specs_root)
        if diff_dirs(specs_root, preview_root) != diff_dirs(specs_root, temporary):
            _replace_directory(temporary, preview_root)
            state["implementationIdentity"] = identity
            state["previewContentFingerprint"] = _tree_fingerprint(preview_root)
            _atomic_json(_state_path(Path(state["workRoot"])), state)
            raise SpecError("preview_changed_requires_confirmation")
        _replace_directory(temporary, preview_root)
        state["implementationIdentity"] = identity
        state["previewContentFingerprint"] = _tree_fingerprint(preview_root)
        _atomic_json(_state_path(Path(state["workRoot"])), state)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def apply_delta(
    specs_root: Path,
    delta_root: Path,
    output_root: Path,
    work_root: Path,
    specs_fingerprint: str,
    input_fingerprint: str,
) -> None:
    state = _load_state(work_root)
    _assert_fingerprints(state, specs_fingerprint, input_fingerprint)
    summary = _state_summary(state)
    if summary["status"] != "READY_TO_APPLY" or summary["remaining"] != 0:
        raise SpecError("invalid_state: expected_READY_TO_APPLY")
    identity = implementation_identity()
    output_is_specs = _canonical_path(output_root) == _canonical_path(specs_root)
    if output_is_specs and state.get("previewRoot") is None:
        raise SpecError("preview_missing")

    _state_path_context(state, work_root, specs_root, delta_root, output_root)
    if state["specsRoot"] is not None:
        expected_paths = (
            state["specsRoot"],
            state["deltaRoot"],
            state["specsRoot"] if output_is_specs else state["previewRoot"],
        )
        actual_paths = (
            str(_canonical_path(specs_root)),
            str(_canonical_path(delta_root)),
            str(_canonical_path(output_root)),
        )
        if actual_paths != expected_paths:
            raise SpecError("spec_context_changed")
        _assert_bound_content(state, specs_root, delta_root)
    specs = _merged_specs(specs_root, delta_root)

    if not output_is_specs:
        _bind_preview_context(state, work_root, specs_root, delta_root, output_root)
        if state["previewContentFingerprint"] is None:
            if output_root.exists() and any(output_root.iterdir()):
                raise SpecError(f"output_not_empty: {output_root}")
            _write_preview(specs, output_root, specs_root)
            state["specsContentFingerprint"] = _tree_fingerprint(specs_root)
            state["deltaContentFingerprint"] = _tree_fingerprint(delta_root)
            state["previewContentFingerprint"] = _tree_fingerprint(output_root)
            state["implementationIdentity"] = identity
            _atomic_json(_state_path(work_root), state)
            return
        _refresh_preview(state, specs, specs_root, output_root, identity)
        return

    preview_root = Path(state["previewRoot"])
    if not preview_root.is_dir():
        raise SpecError(f"preview_missing: {preview_root}")
    _assert_bound_content(state, specs_root, delta_root)
    _refresh_preview(state, specs, specs_root, preview_root, identity)
    temporary = specs_root.parent / f".my-spec-preview-{uuid.uuid4().hex}"
    try:
        _write_preview(specs, temporary, specs_root)
        if not _same_tree(temporary, preview_root):
            raise SpecError("preview_content_mismatch")

        parent = specs_root.parent
        backup = parent / f".my-spec-backup-{uuid.uuid4().hex}"
        had_specs = specs_root.exists()
        try:
            if had_specs:
                specs_root.rename(backup)
            temporary.rename(specs_root)
            validate_main(specs_root)
            shutil.rmtree(work_root / "current")
            (work_root / "lock").unlink()
            try:
                work_root.rmdir()
            except OSError:
                pass
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            if backup.exists():
                if specs_root.exists():
                    shutil.rmtree(specs_root)
                backup.rename(specs_root)
            elif not had_specs and specs_root.exists():
                shutil.rmtree(specs_root)
            raise
        if backup.exists():
            try:
                shutil.rmtree(backup)
            except OSError as exc:
                print(f"warning: backup_cleanup_failed: {backup}: {exc}", file=sys.stderr)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _state_path(work_root: Path) -> Path:
    return work_root / "current" / "state.json"


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_json(path: Path) -> object:
    try:
        return json.loads(_text(path))
    except json.JSONDecodeError as exc:
        raise SpecError(f"invalid_json: {path}: {exc.msg}") from exc


def _load_state(work_root: Path) -> dict[str, object]:
    value = _read_json(_state_path(work_root))
    if not isinstance(value, dict):
        raise SpecError("invalid_state_document")
    _validate_context_document(value)
    return value


def _state_summary(state: dict[str, object]) -> dict[str, object]:
    conflicts = state.get("conflicts")
    decisions = state.get("decisions")
    status = state.get("status")
    cursor = state.get("currentConflict")
    if (
        not isinstance(conflicts, list)
        or not isinstance(decisions, list)
        or status not in RUN_STATUSES
        or not isinstance(cursor, int)
        or cursor != len(decisions)
        or cursor > len(conflicts)
    ):
        raise SpecError("invalid_state_document")
    total = len(conflicts)
    decided = len(decisions)
    if (
        (status == "ANALYZING" and (total or decided or cursor))
        or (status == "WAITING_DECISION" and cursor >= total)
        or (status == "READY_TO_APPLY" and cursor != total)
    ):
        raise SpecError("invalid_state_document")
    return {
        "status": status,
        "total": total,
        "decided": decided,
        "remaining": total - decided,
    }


def state_init(
    work_root: Path,
    command: str,
    specs_fingerprint: str,
    input_fingerprint: str,
) -> None:
    if command not in {"add", "review", "audit"}:
        raise SpecError(f"invalid_state_command: {command}")
    if not specs_fingerprint or not input_fingerprint:
        raise SpecError("missing_state_fingerprint")
    identity = implementation_identity()
    target = resolve_worktree(work_root)
    work_root = _canonical_path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    lock = work_root / "lock"
    try:
        with lock.open("x", encoding="utf-8") as handle:
            handle.write(command + "\n")
    except FileExistsError as exc:
        raise SpecError(f"state_locked: {work_root}") from exc
    try:
        current = work_root / "current"
        if current.exists():
            shutil.rmtree(current)
        _atomic_json(
            _state_path(work_root),
            {
                "command": command,
                "status": "ANALYZING",
                "specsFingerprint": specs_fingerprint,
                "inputFingerprint": input_fingerprint,
                "currentConflict": 0,
                "conflicts": [],
                "decisions": [],
                "workRoot": str(work_root),
                "targetWorktree": str(target) if target is not None else None,
                "specsRoot": None,
                "deltaRoot": None,
                "previewRoot": None,
                "specsContentFingerprint": None,
                "deltaContentFingerprint": None,
                "previewContentFingerprint": None,
                "implementationIdentity": identity,
            },
        )
    except Exception:
        lock.unlink(missing_ok=True)
        raise


def _validate_conflicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise SpecError("conflicts_must_be_array")
    result: list[dict[str, object]] = []
    identifiers: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise SpecError("conflict_must_be_object")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise SpecError("invalid_conflict_field: <unknown>: id")
        if identifier in identifiers:
            raise SpecError(f"duplicate_conflict_id: {identifier}")
        identifiers.add(identifier)
        for field_name in CONFLICT_FIELDS[1:]:
            field_value = item.get(field_name)
            valid = (
                isinstance(field_value, str) and bool(field_value.strip())
                if field_name != "evidence"
                else isinstance(field_value, list)
                and bool(field_value)
                and all(isinstance(entry, str) and entry.strip() for entry in field_value)
            )
            if not valid:
                raise SpecError(f"invalid_conflict_field: {identifier}: {field_name}")
        result.append({field_name: item[field_name] for field_name in CONFLICT_FIELDS})
    return result


def _assert_fingerprints(
    state: dict[str, object], specs_fingerprint: str, input_fingerprint: str
) -> None:
    if state.get("specsFingerprint") != specs_fingerprint:
        raise SpecError("specs_fingerprint_changed")
    if state.get("inputFingerprint") != input_fingerprint:
        raise SpecError("input_fingerprint_changed")


def state_set_conflicts(
    work_root: Path,
    conflicts_path: Path,
    specs_fingerprint: str,
    input_fingerprint: str,
) -> dict[str, object]:
    state = _load_state(work_root)
    _assert_fingerprints(state, specs_fingerprint, input_fingerprint)
    if state.get("status") != "ANALYZING":
        raise SpecError("invalid_state: expected_ANALYZING")
    conflicts = _validate_conflicts(_read_json(conflicts_path))
    state["conflicts"] = conflicts
    state["currentConflict"] = 0
    state["decisions"] = []
    state["status"] = "WAITING_DECISION" if conflicts else "READY_TO_APPLY"
    _atomic_json(_state_path(work_root), state)
    summary = _state_summary(state)
    return {"status": summary["status"], "total": summary["total"], "remaining": summary["remaining"]}


def state_current(
    work_root: Path, specs_fingerprint: str, input_fingerprint: str
) -> dict[str, object]:
    state = _load_state(work_root)
    _assert_fingerprints(state, specs_fingerprint, input_fingerprint)
    if state.get("status") != "WAITING_DECISION":
        raise SpecError("invalid_state: expected_WAITING_DECISION")
    conflicts = state["conflicts"]
    index = state["currentConflict"]
    if not isinstance(conflicts, list) or not isinstance(index, int) or not 0 <= index < len(conflicts):
        raise SpecError("invalid_conflict_cursor")
    return {"index": index, "total": len(conflicts), "conflict": conflicts[index]}


def state_decide(
    work_root: Path,
    expected_conflict_id: str,
    decision: str,
    specs_fingerprint: str,
    input_fingerprint: str,
    modified_content: str | None = None,
) -> dict[str, object]:
    state = _load_state(work_root)
    _assert_fingerprints(state, specs_fingerprint, input_fingerprint)
    if state.get("status") != "WAITING_DECISION":
        raise SpecError("invalid_state: expected_WAITING_DECISION")
    if decision not in DECISIONS:
        raise SpecError(f"invalid_decision: {decision}")
    if decision == "accept-modified" and not (modified_content and modified_content.strip()):
        raise SpecError("modified_content_required")
    if decision != "accept-modified" and modified_content is not None:
        raise SpecError("modified_content_not_allowed")
    conflicts = state.get("conflicts")
    decisions = state.get("decisions")
    index = state.get("currentConflict")
    if not isinstance(conflicts, list) or not isinstance(decisions, list) or not isinstance(index, int):
        raise SpecError("invalid_state_document")
    if index != len(decisions) or not 0 <= index < len(conflicts):
        raise SpecError("invalid_conflict_cursor")
    conflict = conflicts[index]
    if not isinstance(conflict, dict) or not isinstance(conflict.get("id"), str):
        raise SpecError("invalid_state_document")
    if conflict["id"] != expected_conflict_id:
        raise SpecError(f"unexpected_conflict_id: expected_{conflict['id']}: {expected_conflict_id}")
    record: dict[str, object] = {"conflictId": conflict["id"], "decision": decision}
    if modified_content is not None:
        record["modifiedContent"] = modified_content
    decisions.append(record)
    state["currentConflict"] = index + 1
    state["status"] = "READY_TO_APPLY" if index + 1 == len(conflicts) else "WAITING_DECISION"
    _atomic_json(_state_path(work_root), state)
    return _state_summary(state)


def diff_dirs(old_root: Path, new_root: Path) -> str:
    if not new_root.is_dir():
        raise SpecError(f"preview_missing: {new_root}")
    old_worktree = resolve_worktree(old_root)
    new_worktree = resolve_worktree(new_root)
    if (old_worktree is None) != (new_worktree is None) or (
        old_worktree is not None
        and new_worktree is not None
        and os.path.normcase(os.path.abspath(str(old_worktree)))
        != os.path.normcase(os.path.abspath(str(new_worktree)))
    ):
        raise SpecError("cross_worktree_path: diff")
    old_files = {path.relative_to(old_root).as_posix(): path for path in _spec_files(old_root)}
    new_files = {path.relative_to(new_root).as_posix(): path for path in _spec_files(new_root)}
    chunks: list[str] = []
    for relative in sorted(old_files.keys() | new_files.keys()):
        old_lines = _text(old_files[relative]).splitlines(keepends=True) if relative in old_files else []
        new_lines = _text(new_files[relative]).splitlines(keepends=True) if relative in new_files else []
        chunks.extend(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{relative}" if old_lines else "/dev/null",
                tofile=f"b/{relative}" if new_lines else "/dev/null",
            )
        )
    return "".join(chunks)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="myspec", description="Deterministic MySpec operations")
    commands = parser.add_subparsers(dest="command", required=True)
    validate_main_parser = commands.add_parser("validate-main")
    validate_main_parser.add_argument("specs_dir", type=Path)
    validate_delta_parser = commands.add_parser("validate-delta")
    validate_delta_parser.add_argument("delta_dir", type=Path)
    validate_delta_parser.add_argument("specs_dir", type=Path)
    apply_parser = commands.add_parser("apply-delta")
    apply_parser.add_argument("specs_dir", type=Path)
    apply_parser.add_argument("delta_dir", type=Path)
    apply_parser.add_argument("output_dir", type=Path)
    apply_parser.add_argument("work_dir", type=Path)
    apply_parser.add_argument("specs_fingerprint")
    apply_parser.add_argument("input_fingerprint")
    diff_parser = commands.add_parser("diff")
    diff_parser.add_argument("old_dir", type=Path)
    diff_parser.add_argument("new_dir", type=Path)
    state_init_parser = commands.add_parser("state-init")
    state_init_parser.add_argument("work_dir", type=Path)
    state_init_parser.add_argument("run_command")
    state_init_parser.add_argument("specs_fingerprint")
    state_init_parser.add_argument("input_fingerprint")
    state_set_parser = commands.add_parser("state-set-conflicts")
    state_set_parser.add_argument("work_dir", type=Path)
    state_set_parser.add_argument("conflicts_file", type=Path)
    state_set_parser.add_argument("specs_fingerprint")
    state_set_parser.add_argument("input_fingerprint")
    state_current_parser = commands.add_parser("state-current")
    state_current_parser.add_argument("work_dir", type=Path)
    state_current_parser.add_argument("specs_fingerprint")
    state_current_parser.add_argument("input_fingerprint")
    state_decide_parser = commands.add_parser("state-decide")
    state_decide_parser.add_argument("work_dir", type=Path)
    state_decide_parser.add_argument("expected_conflict_id")
    state_decide_parser.add_argument("decision")
    state_decide_parser.add_argument("specs_fingerprint")
    state_decide_parser.add_argument("input_fingerprint")
    state_decide_parser.add_argument("--modified-content")
    state_status_parser = commands.add_parser("state-status")
    state_status_parser.add_argument("work_dir", type=Path)
    state_status_parser.add_argument("specs_fingerprint")
    state_status_parser.add_argument("input_fingerprint")
    add_management_parsers(commands)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-main":
            validate_main(args.specs_dir)
        elif args.command == "validate-delta":
            validate_delta(args.delta_dir, args.specs_dir)
        elif args.command == "apply-delta":
            apply_delta(
                args.specs_dir,
                args.delta_dir,
                args.output_dir,
                args.work_dir,
                args.specs_fingerprint,
                args.input_fingerprint,
            )
        elif args.command == "diff":
            sys.stdout.write(diff_dirs(args.old_dir, args.new_dir))
        elif args.command == "state-init":
            state_init(args.work_dir, args.run_command, args.specs_fingerprint, args.input_fingerprint)
        elif args.command == "state-set-conflicts":
            print(
                json.dumps(
                    state_set_conflicts(
                        args.work_dir,
                        args.conflicts_file,
                        args.specs_fingerprint,
                        args.input_fingerprint,
                    ),
                    ensure_ascii=False,
                )
            )
        elif args.command == "state-current":
            print(
                json.dumps(
                    state_current(args.work_dir, args.specs_fingerprint, args.input_fingerprint),
                    ensure_ascii=False,
                )
            )
        elif args.command == "state-decide":
            print(
                json.dumps(
                    state_decide(
                        args.work_dir,
                        args.expected_conflict_id,
                        args.decision,
                        args.specs_fingerprint,
                        args.input_fingerprint,
                        args.modified_content,
                    ),
                    ensure_ascii=False,
                )
            )
        elif args.command == "state-status":
            state = _load_state(args.work_dir)
            _assert_fingerprints(state, args.specs_fingerprint, args.input_fingerprint)
            print(json.dumps(_state_summary(state), ensure_ascii=False))
        elif args.command in {"init", "doctor", "update"}:
            print(json.dumps(run_management(args), ensure_ascii=False))
    except (SpecError, ManagementError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: filesystem: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
