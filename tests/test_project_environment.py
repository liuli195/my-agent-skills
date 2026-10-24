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
