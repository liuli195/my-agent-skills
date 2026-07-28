from __future__ import annotations

import argparse
import difflib
import re
import shutil
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


def apply_delta(specs_root: Path, delta_root: Path, output_root: Path) -> None:
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
    except Exception:
        if preview.exists():
            shutil.rmtree(preview)
        if specs_root.exists() and backup.exists():
            shutil.rmtree(specs_root)
            backup.rename(specs_root)
        elif not had_specs and specs_root.exists():
            shutil.rmtree(specs_root)
        raise


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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic OpenSpec operations")
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
    diff_parser = commands.add_parser("diff")
    diff_parser.add_argument("old_dir", type=Path)
    diff_parser.add_argument("new_dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-main":
            validate_main(args.specs_dir)
        elif args.command == "validate-delta":
            validate_delta(args.delta_dir, args.specs_dir)
        elif args.command == "apply-delta":
            apply_delta(args.specs_dir, args.delta_dir, args.output_dir)
        elif args.command == "diff":
            sys.stdout.write(diff_dirs(args.old_dir, args.new_dir))
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: filesystem: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
