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


@pytest.mark.parametrize("kind", [stat.S_IFREG, stat.S_IFDIR])
def test_connect_preserves_entry_occupied_by_regular_content(monkeypatch, capsys, kind):
    app = entry()
    project_entry = ROOT / ".local/skills/data-store"
    original_lstat, original_lexists = Path.lstat, app.os.path.lexists
    monkeypatch.setattr(Path, "lstat", lambda path:
                        SimpleNamespace(st_mode=kind) if path == project_entry else original_lstat(path))
    monkeypatch.setattr(app.os.path, "lexists", lambda path:
                        True if path == project_entry else original_lexists(path))
    assert invoke(app, monkeypatch, "connect", "--project", ROOT) == 1
    assert "保留原内容" in capsys.readouterr().err


@pytest.mark.parametrize("parent,kind", [
    (".local", stat.S_IFLNK), (".local/skills", stat.S_IFLNK),
    (".local", stat.S_IFREG), (".local/skills", stat.S_IFREG),
])
def test_project_binding_rejects_redirected_or_file_parent(monkeypatch, parent, kind):
    app = entry()
    blocked = ROOT / parent
    original_lstat, original_exists, original_is_dir = Path.lstat, Path.exists, Path.is_dir
    monkeypatch.setattr(Path, "lstat", lambda path:
                        SimpleNamespace(st_mode=kind) if path == blocked else original_lstat(path))
    monkeypatch.setattr(Path, "exists", lambda path:
                        True if path == blocked else original_exists(path))
    monkeypatch.setattr(Path, "is_dir", lambda path:
                        False if path == blocked else original_is_dir(path))
    with pytest.raises(ValueError, match="父目录"):
        app.project_entry(ROOT)


@pytest.mark.parametrize("restore_fails", [False, True])
def test_update_retains_old_link_when_switch_or_restore_fails(monkeypatch, capsys, restore_fails):
    app = entry()
    binding, old, new = ROOT / ".unit-binding", ROOT / "old-source", ROOT / "new-source"
    links = {binding: old}  # Only the current, staged and saved link identities.
    failures = 0
    original_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        if path in links:
            return links[path]
        if path in (old, new):
            return path
        return original_resolve(path, *args, **kwargs)

    def make_link(path, target):
        assert path.name.startswith(".data-store-new-")
        links[path] = target

    def rename(path, target):
        nonlocal failures
        assert path in links
        if target == binding and failures < (2 if restore_fails else 1):
            failures += 1
            raise OSError(f"injected rename failure {failures}")
        links[target] = links.pop(path)

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(Path, "rename", rename)
    monkeypatch.setattr(app, "is_link", lambda path: path in links)
    monkeypatch.setattr(app, "make_link", make_link)
    monkeypatch.setattr(app, "remove_link", links.pop)
    monkeypatch.setattr(app.os.path, "lexists", lambda path: path in links)
    with pytest.raises(OSError, match="injected rename failure 1"):
        app.update_link(binding, new, old)
    assert list(links.values()) == [old]
    if restore_fails:
        assert next(iter(links)).name.startswith(".data-store-old-")
        assert "旧入口保留在" in capsys.readouterr().err
    else:
        assert links == {binding: old}
