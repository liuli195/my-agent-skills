"""Pure interpreter and dependency-content decisions for project preparation."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def entry():
    spec = importlib.util.spec_from_file_location("project_environment", ROOT / "scripts/project_environment.py")
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    return app


def test_unsupported_python_stops_before_environment_writes(capsys):
    app = entry()
    with patch.object(app.sys, "version_info", (3, 11)):
        assert app.main(["--project", str(ROOT)]) == 1
    assert "Python 3.12" in capsys.readouterr().err


def test_nested_dependency_content_changes_identity_without_writing_files(monkeypatch):
    app = entry()
    contents = {ROOT / "requirements.txt": "-r skill.txt\n", ROOT / "skill.txt": "example==1\n"}

    def read_text(path, **kwargs):
        assert kwargs == {"encoding": "utf-8"}
        assert path in contents, f"unexpected dependency read: {path}"
        return contents[path]

    monkeypatch.setattr(Path, "read_text", read_text)
    first = app.dependency_identity(ROOT, ["requirements.txt"])
    assert set(first) == {"requirements.txt", "skill.txt"}
    contents[ROOT / "skill.txt"] = "example==1\r\n"
    assert app.dependency_identity(ROOT, ["requirements.txt"]) == first
    contents[ROOT / "skill.txt"] = "example==2\n"
    changed = app.dependency_identity(ROOT, ["requirements.txt"])
    assert changed["requirements.txt"] == first["requirements.txt"]
    assert changed["skill.txt"] != first["skill.txt"]


def test_nested_dependency_cycles_are_visited_once(monkeypatch):
    app = entry()
    contents = {ROOT / "requirements.txt": "--requirement nested.txt\n-c constraints.txt\n",
                ROOT / "nested.txt": "-r requirements.txt\n",
                ROOT / "constraints.txt": "--constraint nested.txt\n"}
    reads = []

    def read_text(path, **kwargs):
        assert path in contents, f"unexpected dependency read: {path}"
        reads.append(path.name)
        return contents[path]

    monkeypatch.setattr(Path, "read_text", read_text)
    assert set(app.dependency_identity(ROOT, ["requirements.txt"])) == {
        "requirements.txt", "nested.txt", "constraints.txt"}
    assert reads == ["requirements.txt", "nested.txt", "constraints.txt"]


def test_preparation_reuses_environment_until_nested_dependency_changes(monkeypatch):
    app = entry()
    python = ROOT / ".venv/bin/python"
    state_path = ROOT / ".local/project-environment.json"
    contents = {ROOT / "requirements.txt": "-r skill.txt\n", ROOT / "skill.txt": "example==1\n"}
    saved = None
    python_ready = False
    commands = []
    original_exists, original_read = Path.exists, Path.read_text
    original_symlink = Path.is_symlink

    def exists(path):
        if path == python:
            return python_ready
        if path == state_path:
            return saved is not None
        return original_exists(path)

    def read(path, *args, **kwargs):
        if path in contents:
            return contents[path]
        if path == state_path:
            return saved
        return original_read(path, *args, **kwargs)

    def write(path, value, **kwargs):
        nonlocal saved
        assert path == state_path
        saved = value

    def unlink(path, *args, **kwargs):
        nonlocal saved
        assert path == state_path
        saved = None

    def run(command, root):
        nonlocal python_ready
        assert root == ROOT
        commands.append(command)
        if command == [app.sys.executable, "-m", "venv", ROOT / ".venv"]:
            python_ready = True
        else:
            assert command[:4] == [python, "-m", "pip", "install"]
            assert command[-2:] == ["-r", "requirements.txt"]

    def output(command, **kwargs):
        if command == ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]:
            return str(ROOT / ".git")
        assert command == [str(python), "-c", 'import sys; print("%s.%s" % sys.version_info[:2])']
        return f"{app.sys.version_info.major}.{app.sys.version_info.minor}"

    monkeypatch.setattr(Path, "exists", exists)
    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(Path, "write_text", write)
    monkeypatch.setattr(Path, "unlink", unlink)
    def mkdir(path, **kwargs):
        assert path == state_path.parent

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(Path, "is_symlink", lambda path:
                        False if path == ROOT / ".venv" else original_symlink(path))
    monkeypatch.setattr(app, "run", run)
    monkeypatch.setattr(app.subprocess, "check_output", output)
    recipe = {"requirements": ["requirements.txt"]}
    assert app.prepare(ROOT, recipe) == "prepared"
    assert app.prepare(ROOT, recipe) == "reused"
    assert len(commands) == 2
    contents[ROOT / "skill.txt"] = "example==2\n"
    assert app.prepare(ROOT, recipe) == "prepared"
    assert len(commands) == 3
