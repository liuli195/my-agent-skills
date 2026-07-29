from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path


REQUIREMENT = re.compile(r"^### Requirement: (\S.*)$")
SCENARIO = re.compile(r"^#### Scenario: (\S.*)$")
CAPABILITY = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
OPERATIONS = ("RENAMED", "REMOVED", "MODIFIED", "ADDED")
OPERATION_HEADING = re.compile(r"^## (ADDED|MODIFIED|REMOVED|RENAMED) Requirements$")
RUN_STATUSES = ("ANALYZING", "WAITING_DECISION", "READY_TO_APPLY")
DECISIONS = ("accept", "ignore", "accept-modified", "defer")
CONFLICT_FIELDS = ("id", "candidate", "evidence", "reason", "recommendation")


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


def _write_preview(specs: OrderedDict[str, MainSpec], output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for capability, spec in specs.items():
        directory = output_root / capability
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "spec.md").write_text(_render(spec), encoding="utf-8")
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
                    del specs[locations[title]].requirements[title]
                _target(specs, delta).requirements[title] = block
                locations[title] = delta.capability
    return specs


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
    specs = _merged_specs(specs_root, delta_root)
    if output_root.resolve(strict=False) != specs_root.resolve(strict=False):
        if output_root.exists() and any(output_root.iterdir()):
            raise SpecError(f"output_not_empty: {output_root}")
        _write_preview(specs, output_root)
        return

    parent = specs_root.parent
    nonce = uuid.uuid4().hex
    preview = parent / f".my-spec-preview-{nonce}"
    backup = parent / f".my-spec-backup-{nonce}"
    had_specs = specs_root.exists()
    try:
        _write_preview(specs, preview)
        if had_specs:
            specs_root.rename(backup)
        preview.rename(specs_root)
        validate_main(specs_root)
        if backup.exists():
            shutil.rmtree(backup)
        shutil.rmtree(work_root / "current")
        (work_root / "lock").unlink()
        try:
            work_root.rmdir()
        except OSError:
            pass
    except Exception:
        if preview.exists():
            shutil.rmtree(preview)
        if backup.exists():
            if specs_root.exists():
                shutil.rmtree(specs_root)
            backup.rename(specs_root)
        elif not had_specs and specs_root.exists():
            shutil.rmtree(specs_root)
        raise


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


SKILL_NAMES = ("my-spec", "my-spec-add", "my-spec-review", "my-spec-audit")
PACKAGE_NAME = "@liuli195/myspec"


def _package_version() -> str:
    package = _read_json(Path(__file__).resolve().parents[1] / "package.json")
    if not isinstance(package, dict) or not isinstance(package.get("version"), str):
        raise SpecError("invalid_package_version")
    return package["version"]


def _command(command: str, *arguments: str) -> list[str] | str:
    executable = shutil.which(command)
    if executable is None:
        raise SpecError(f"missing_command: {command}")
    values = [executable, *arguments]
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        return subprocess.list2cmdline(values)
    return values


def _run(command: str, *arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    invocation = _command(command, *arguments)
    return subprocess.run(
        invocation,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        shell=isinstance(invocation, str),
    )


def _npm_path(argument: str, error_name: str) -> Path:
    result = _run("npm", argument, "--global")
    if result.returncode != 0:
        raise SpecError(f"{error_name}: {result.stderr.strip()}")
    return Path(result.stdout.strip())


def _stable_package_root() -> Path:
    return _npm_path("root", "npm_root_failed") / "@liuli195" / "myspec"


def _npm_prefix() -> Path:
    return _npm_path("prefix", "npm_prefix_failed")


def _pi_settings_paths() -> tuple[tuple[str, Path], ...]:
    configured = os.environ.get("PI_CODING_AGENT_DIR")
    user = Path(configured) if configured else Path.home() / ".pi" / "agent"
    return (("user", user / "settings.json"), ("project", Path.cwd() / ".pi" / "settings.json"))


def _read_settings(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    value = _read_json(path)
    if not isinstance(value, dict):
        raise SpecError(f"invalid_pi_settings: {path}")
    return value


def _package_source(item: object) -> str | None:
    if isinstance(item, str):
        return item
    if isinstance(item, dict) and isinstance(item.get("source"), str):
        return item["source"]
    return None


def _local_source_path(source: str, settings_path: Path) -> Path | None:
    normalized = source.lower()
    if normalized.startswith(("npm:", "git:", "http://", "https://", "ssh://", "git://")):
        return None
    path = Path(source).expanduser()
    if not path.is_absolute():
        path = settings_path.parent / path
    return Path(os.path.abspath(path))


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


@dataclass
class PiSource:
    scope: str
    settings_path: Path
    settings: dict[str, object]
    index: int
    item: object
    source: str
    local_path: Path | None

    @property
    def disabled(self) -> bool:
        return isinstance(self.item, dict) and self.item.get("skills") == []


def _pi_sources() -> list[PiSource]:
    result: list[PiSource] = []
    for scope, path in _pi_settings_paths():
        settings = _read_settings(path)
        packages = settings.get("packages", [])
        if not isinstance(packages, list):
            raise SpecError(f"invalid_pi_packages: {path}")
        for index, item in enumerate(packages):
            source = _package_source(item)
            if source is not None:
                result.append(
                    PiSource(scope, path, settings, index, item, source, _local_source_path(source, path))
                )
    return result


def _myspec_source_kind(item: PiSource, stable: Path) -> str | None:
    if item.local_path is not None and _same_path(item.local_path, stable):
        return "stable"
    normalized = item.source.replace("\\", "/").lower().rstrip("/")
    if re.fullmatch(r"npm:(?:@liuli195/myspec|pi-my-spec)(?:@[^/]+)?", normalized):
        return "legacy"
    local = item.local_path.as_posix().lower().rstrip("/") if item.local_path else ""
    if local.endswith("/plugins/my-spec") or local.endswith("/pi-my-spec"):
        return "legacy"
    if re.search(r"(?:^|[/:])pi-my-spec(?:\.git)?(?:@[^/]+|#[^/]+)?$", normalized):
        return "legacy"
    return None


def _set_disabled(item: PiSource, disabled: bool) -> None:
    packages = item.settings["packages"]
    assert isinstance(packages, list)
    current = packages[item.index]
    if isinstance(current, str):
        if disabled:
            packages[item.index] = {"source": current, "skills": []}
        return
    if disabled:
        current["skills"] = []
    else:
        current.pop("skills", None)
        current.pop("autoload", None)


def _configure_pi_sources(stable: Path) -> list[str]:
    sources = _pi_sources()
    stable_sources = [item for item in sources if _myspec_source_kind(item, stable) == "stable"]
    if not stable_sources:
        installed = _run("pi", "install", str(stable))
        if installed.returncode != 0:
            raise SpecError(f"pi_install_failed: {installed.stderr.strip()}")
        sources = _pi_sources()
        stable_sources = [item for item in sources if _myspec_source_kind(item, stable) == "stable"]
    if not stable_sources:
        raise SpecError("pi_install_missing_source")

    winner = next((item for item in reversed(stable_sources) if item.scope == "project"), stable_sources[0])
    disabled: list[str] = []
    touched: dict[Path, dict[str, object]] = {}
    for item in sources:
        kind = _myspec_source_kind(item, stable)
        if kind == "stable":
            _set_disabled(item, item is not winner)
            touched[item.settings_path] = item.settings
        elif kind == "legacy":
            disabled.append(item.source)
            _set_disabled(item, True)
            touched[item.settings_path] = item.settings
    for path, settings in touched.items():
        _atomic_json(path, settings)
    return disabled


def _init_pi() -> dict[str, object]:
    if shutil.which("pi") is None:
        raise SpecError("missing_command: pi")
    stable = _stable_package_root()
    disabled = _configure_pi_sources(stable)
    return {
        "pi": "initialized",
        "source": str(stable),
        "disabledLegacySources": disabled,
        "reloadRequired": True,
    }


def _init_all() -> dict[str, object]:
    result: dict[str, object] = {}
    for agent in ("pi", "claude", "codex"):
        if shutil.which(agent) is None:
            result[agent] = {"status": "skipped", "reason": f"missing_command: {agent}"}
        elif agent == "pi":
            initialized = _init_pi()
            result[agent] = {"status": "initialized", "source": initialized["source"]}
        else:
            result[agent] = {"status": "skipped", "reason": "integration_not_available"}
    return result


def _mode_state_path() -> Path:
    return Path.home() / ".myspec" / "state.json"


def _mode_state() -> dict[str, object]:
    path = _mode_state_path()
    if not path.exists():
        return {"mode": "release"}
    value = _read_json(path)
    if not isinstance(value, dict) or value.get("mode") not in {"dev", "release"}:
        raise SpecError(f"invalid_mode_state: {path}")
    return value


def _marketplace_has_myspec(path: Path, *, agents: bool) -> bool:
    value = _read_json(path)
    if not isinstance(value, dict) or not isinstance(value.get("plugins"), list):
        return False
    for plugin in value["plugins"]:
        if not isinstance(plugin, dict) or plugin.get("name") != "my-spec":
            continue
        plugin_source = plugin.get("source")
        if agents:
            return plugin_source == {"source": "local", "path": "./plugins/my-spec"}
        return plugin_source == "./plugins/my-spec"
    return False


def _validate_dev_source(raw_source: Path) -> tuple[Path, Path, str]:
    source = raw_source.resolve()
    agents_market = source / ".agents" / "plugins" / "marketplace.json"
    claude_market = source / ".claude-plugin" / "marketplace.json"
    package_root = source / "plugins" / "my-spec"
    package_path = package_root / "package.json"
    missing = next((path for path in (agents_market, claude_market, package_path) if not path.is_file()), None)
    if missing is not None:
        raise SpecError(f"invalid_dev_source: missing {missing}")
    package = _read_json(package_path)
    if (
        not isinstance(package, dict)
        or package.get("name") != PACKAGE_NAME
        or not isinstance(package.get("version"), str)
        or package.get("pi") != {"skills": ["./skills"]}
    ):
        raise SpecError(f"invalid_dev_source: package_manifest {package_root}")
    if not _marketplace_has_myspec(agents_market, agents=True):
        raise SpecError(f"invalid_dev_source: marketplace {agents_market}")
    if not _marketplace_has_myspec(claude_market, agents=False):
        raise SpecError(f"invalid_dev_source: marketplace {claude_market}")
    root = _run("git", "rev-parse", "--show-toplevel", cwd=source)
    if root.returncode != 0 or not _same_path(Path(root.stdout.strip()), source):
        raise SpecError("invalid_dev_source: git_root")
    commit = _run("git", "rev-parse", "HEAD", cwd=source)
    if commit.returncode != 0:
        raise SpecError(f"invalid_dev_source: git {commit.stderr.strip()}")
    return source, package_root, commit.stdout.strip()


def _exact_command(executable: Path, *arguments: str) -> list[str] | str:
    values = [str(executable), *arguments]
    if os.name == "nt" and executable.suffix.lower() in {".cmd", ".bat"}:
        return subprocess.list2cmdline(values)
    return values


def _stable_cli() -> Path:
    prefix = _npm_prefix()
    return prefix / "myspec.cmd" if os.name == "nt" else prefix / "bin" / "myspec"


def _resume_after_switch(arguments: list[str], token: str) -> dict[str, object]:
    invocation = _exact_command(_stable_cli(), *arguments, "--_switch-token", token)
    result = subprocess.run(
        invocation,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
        shell=isinstance(invocation, str),
    )
    if result.returncode != 0:
        raise SpecError(f"mode_switch_resume_failed: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SpecError("mode_switch_resume_invalid_output") from exc
    if not isinstance(value, dict):
        raise SpecError("mode_switch_resume_invalid_output")
    return value


def _consume_switch(stage: str, token: str | None) -> dict[str, object]:
    state = _mode_state()
    pending = state.get("pendingSwitch")
    if (
        token is None
        or not isinstance(pending, dict)
        or pending.get("stage") != stage
        or pending.get("token") != token
    ):
        raise SpecError("invalid_switch_token")
    state.pop("pendingSwitch")
    _atomic_json(_mode_state_path(), state)
    return state


def _pi_is_configured() -> bool:
    stable = _stable_package_root()
    return any(
        _myspec_source_kind(item, stable) == "stable" and not item.disabled
        for item in _pi_sources()
    )


def _refresh_pi() -> str:
    if shutil.which("pi") is None or not _pi_is_configured():
        return "not-installed"
    listed = _run("pi", "list")
    if listed.returncode != 0:
        raise SpecError(f"pi_list_failed: {listed.stderr.strip()}")
    return "refreshed"


def _switch_dev(raw_source: Path | None, token: str | None) -> dict[str, object]:
    source, package_root, commit = _validate_dev_source(raw_source or Path.cwd())
    if token is not None:
        state = _consume_switch("dev", token)
        previous = state.get("previousReleaseVersion")
        if not isinstance(previous, str) or not previous:
            raise SpecError("missing_previous_release_version")
        pi_status = _refresh_pi()
        return {
            "mode": "dev",
            "source": str(source),
            "previousReleaseVersion": previous,
            "pi": pi_status,
            "reloadRequired": pi_status == "refreshed",
        }
    state = _mode_state()
    previous = state.get("previousReleaseVersion") if state["mode"] == "dev" else _package_version()
    if not isinstance(previous, str) or not previous:
        raise SpecError("missing_previous_release_version")
    switch_token = uuid.uuid4().hex
    _atomic_json(
        _mode_state_path(),
        {
            "mode": "dev",
            "source": str(source),
            "sourceCommit": commit,
            "previousReleaseVersion": previous,
            "pendingSwitch": {"stage": "dev", "token": switch_token},
        },
    )
    linked = _run("npm", "link", cwd=package_root)
    if linked.returncode != 0:
        raise SpecError(f"npm_link_failed: {linked.stderr.strip()}")
    return _resume_after_switch(["init", "--dev", "--source", str(source)], switch_token)


def _switch_release(token: str | None) -> dict[str, object]:
    state = _mode_state()
    previous = state.get("previousReleaseVersion")
    if not isinstance(previous, str) or not previous:
        raise SpecError("missing_previous_release_version")
    if token is not None:
        state = _consume_switch("release", token)
        pi_status = _refresh_pi()
        return {
            "mode": "release",
            "version": previous,
            "pi": pi_status,
            "reloadRequired": pi_status == "refreshed",
        }
    if state["mode"] != "dev":
        raise SpecError("missing_previous_release_version")
    switch_token = uuid.uuid4().hex
    _atomic_json(
        _mode_state_path(),
        {
            "mode": "release",
            "previousReleaseVersion": previous,
            "pendingSwitch": {"stage": "release", "token": switch_token},
        },
    )
    installed = _run(
        "npm",
        "install",
        "--global",
        "--ignore-scripts",
        "--no-audit",
        "--no-fund",
        f"{PACKAGE_NAME}@{previous}",
    )
    if installed.returncode != 0:
        raise SpecError(f"npm_install_failed: {installed.stderr.strip()}")
    return _resume_after_switch(["init", "--release"], switch_token)


def _pi_list() -> list[dict[str, str]]:
    listed = _run("pi", "list")
    if listed.returncode != 0:
        raise SpecError(f"pi_list_failed: {listed.stderr.strip()}")
    result: list[dict[str, str]] = []
    pending: str | None = None
    for line in listed.stdout.splitlines():
        if line.startswith("  ") and not line.startswith("    "):
            pending = line.strip().removesuffix(" (filtered)")
        elif pending is not None and line.startswith("    "):
            result.append({"source": pending, "path": line.strip()})
            pending = None
    return result


def _manifest_version(root: Path) -> str | None:
    path = root / "package.json"
    if not path.is_file():
        return None
    value = _read_json(path)
    return value.get("version") if isinstance(value, dict) and isinstance(value.get("version"), str) else None


def _doctor_pi() -> dict[str, object]:
    stable = _stable_package_root()
    real = stable.resolve(strict=False)
    cli_version = _package_version()
    package_version = _manifest_version(real)
    available = shutil.which("pi") is not None
    listed = _pi_list() if available else []
    sources = _pi_sources()
    records: list[dict[str, object]] = []
    enabled: list[str] = []
    disabled: list[str] = []
    stable_enabled = False
    for item in sources:
        kind = _myspec_source_kind(item, stable)
        if kind is None:
            continue
        record = {
            "scope": item.scope,
            "settings": str(item.settings_path),
            "source": item.source,
            "resolvedPath": str(item.local_path) if item.local_path is not None else None,
            "kind": kind,
            "enabled": not item.disabled,
        }
        records.append(record)
        (disabled if item.disabled else enabled).append(item.source)
        stable_enabled = stable_enabled or (kind == "stable" and not item.disabled)
    linked = not _same_path(stable, real)
    stable_listed = any(
        entry["path"] and _same_path(Path(entry["path"]), real)
        for entry in listed
        if entry["source"] in {item.source for item in sources if _myspec_source_kind(item, stable) == "stable"}
    )
    registered = stable_enabled and (stable_listed or not available)
    skills = [name for name in SKILL_NAMES if (real / "skills" / name / "SKILL.md").is_file()]
    return {
        "cliVersion": cli_version,
        "mode": "dev" if linked else "release",
        "source": str(real if linked else stable),
        "npm": {
            "stablePath": str(stable),
            "realPath": str(real),
            "linked": linked,
            "packageVersion": package_version,
            "versionMismatch": package_version != cli_version,
        },
        "pi": {
            "available": available,
            "registered": registered,
            "enabledSources": enabled,
            "disabledSources": disabled,
            "duplicateEnabledSources": len(enabled) > 1,
            "sources": records,
            "listedSources": listed,
            "skills": skills if registered else [],
            "reloadRequired": bool(enabled),
        },
    }


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
    init_parser = commands.add_parser("init")
    init_target = init_parser.add_mutually_exclusive_group(required=True)
    init_target.add_argument("--pi", action="store_true")
    init_target.add_argument("--all", action="store_true")
    init_target.add_argument("--dev", action="store_true")
    init_target.add_argument("--release", action="store_true")
    init_parser.add_argument("--source", type=Path)
    init_parser.add_argument("--_switch-token", help=argparse.SUPPRESS)
    doctor_parser = commands.add_parser("doctor")
    doctor_parser.add_argument("--pi", action="store_true")
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
        elif args.command == "init":
            if args.dev:
                result = _switch_dev(args.source, args._switch_token)
            elif args.release:
                if args.source is not None:
                    raise SpecError("source_only_valid_with_dev")
                result = _switch_release(args._switch_token)
            else:
                if args.source is not None:
                    raise SpecError("source_only_valid_with_dev")
                if args._switch_token is not None:
                    raise SpecError("invalid_switch_token")
                result = _init_all() if args.all else _init_pi()
            print(json.dumps(result, ensure_ascii=False))
        elif args.command == "doctor":
            print(json.dumps(_doctor_pi(), ensure_ascii=False))
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: filesystem: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
