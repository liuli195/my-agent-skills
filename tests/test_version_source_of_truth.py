from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = REPO_ROOT / "tests"
REAL_PLUGIN_VERSION_PATTERN = re.compile(r"(?<![\dv])v?0\.1\.\d+(?!\d)")


def real_plugin_version_literals() -> list[str]:
    literals: list[str] = []
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        if path == Path(__file__).resolve():
            continue
        source = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(source.splitlines(), start=1):
            normalized = line.strip()
            for match in REAL_PLUGIN_VERSION_PATTERN.finditer(line):
                relative = path.relative_to(REPO_ROOT).as_posix()
                literals.append(f"{relative}:{line_number}: {match.group(0)}: {normalized}")
    return literals


def test_tests_do_not_introduce_unreviewed_real_plugin_version_literals() -> None:
    assert real_plugin_version_literals() == []
