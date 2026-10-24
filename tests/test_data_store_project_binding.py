"""Binding parser and source decisions without physical links or child commands."""

import importlib.util
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/data-store/skills/data-store"


def entry():
    spec = importlib.util.spec_from_file_location("project_binding", SKILL / "scripts/project_binding.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(app, monkeypatch, *arguments):
    monkeypatch.setattr(sys, "argv", [str(SKILL / "scripts/project_binding.py"), *map(str, arguments)])
    return app.main()


@pytest.mark.parametrize("arguments", [
    ["connect", "--from", "old"], ["check", "--from", "old"], ["update"],
])
def test_original_source_is_required_only_for_update(monkeypatch, capsys, arguments):
    app = entry()
    with pytest.raises(SystemExit) as error:
        invoke(app, monkeypatch, *arguments, "--project", ROOT)
    assert error.value.code == 2
    assert "--from" in capsys.readouterr().err


def test_project_is_required_before_source_or_link_access(monkeypatch, capsys):
    with pytest.raises(SystemExit) as error:
        invoke(entry(), monkeypatch, "check")
    assert error.value.code == 2
    assert "--project" in capsys.readouterr().err


def test_incomplete_installed_source_is_reported_before_project_access(monkeypatch, capsys):
    app = entry()
    original = Path.is_file

    def is_file(path):
        if path == SKILL / "scripts/data_store.py":
            return False
        return original(path)

    monkeypatch.setattr(Path, "is_file", is_file)
    assert invoke(app, monkeypatch, "check", "--project", ROOT) == 1
    assert "安装不完整" in capsys.readouterr().err


def test_non_directory_project_is_rejected_without_creating_an_entry(monkeypatch, capsys):
    assert invoke(entry(), monkeypatch, "connect", "--project", SKILL / "SKILL.md") == 1
    assert "项目必须是现有目录" in capsys.readouterr().err


def test_check_reports_an_unconnected_project_without_writes(monkeypatch, capsys):
    app = entry()
    project_entry = ROOT / ".local/skills/data-store"
    original = app.os.path.lexists

    def lexists(path):
        if path == project_entry:
            return False
        return original(path)

    monkeypatch.setattr(app.os.path, "lexists", lexists)
    assert invoke(app, monkeypatch, "check", "--project", ROOT) == 1
    assert "项目尚未接入" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["connect", "check", "update"])
def test_wrong_source_requires_explicit_matching_update(monkeypatch, capsys, command):
    app = entry()
    project_entry = ROOT / ".local/skills/data-store"
    actual = ROOT / "different-installed-source"
    expected = ROOT / "expected-installed-source"
    original_lstat = Path.lstat
    original_resolve = Path.resolve
    original_lexists = app.os.path.lexists

    def lstat(path):
        if path == project_entry:
            return SimpleNamespace(st_mode=stat.S_IFLNK)
        return original_lstat(path)

    def resolve(path, *args, **kwargs):
        if path == project_entry:
            return actual
        return original_resolve(path, *args, **kwargs)

    def lexists(path):
        return True if path == project_entry else original_lexists(path)

    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(app.os.path, "lexists", lexists)
    extra = ["--from", expected] if command == "update" else []
    assert invoke(app, monkeypatch, command, "--project", ROOT, *extra) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--from" in captured.err if command == "update" else "入口来源不同" in captured.err
