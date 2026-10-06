"""Installed project connection, exercised through its public commands."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/data-store/skills/data-store"


def invoke(skill, project, command="connect", *extra):
    return subprocess.run(
        [sys.executable, str(skill / "scripts/project_binding.py"), command,
         "--project", str(project), *map(str, extra)],
        text=True, capture_output=True,
    )


def install(tmp_path, name="installed"):
    target = tmp_path / name
    shutil.copytree(SKILL, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def test_installed_connection_serves_other_commands_and_is_repeatable(tmp_path):
    skill = install(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    connected = invoke(skill, project)
    assert connected.returncode == 0, connected.stderr
    assert invoke(skill, project).returncode == 0
    checked = invoke(skill, project, "check")
    assert checked.returncode == 0, checked.stderr
    assert Path(json.loads(checked.stdout)["target"]) == skill.resolve()
    entry = project / ".local/skills/data-store/scripts/data_store.py"
    data = project / "data"
    written = subprocess.run(
        [sys.executable, str(entry), "--root", str(data), "write", "measurements", "one"],
        input='[{"score":7}]', text=True, capture_output=True,
    )
    assert written.returncode == 0, written.stderr
    read = subprocess.run(
        [sys.executable, str(entry), "--root", str(data), "query", "SELECT score FROM measurements"],
        text=True, capture_output=True,
    )
    assert read.returncode == 0, read.stderr
    assert json.loads(read.stdout) == {"score": 7}


def test_update_checks_old_source_and_preserves_sources_and_data(tmp_path):
    old = install(tmp_path, "old")
    new = install(tmp_path, "new")
    project = tmp_path / "project"
    project.mkdir()
    assert invoke(old, project).returncode == 0
    data = project / "data"
    data.mkdir()
    (data / "keep.txt").write_text("existing data", encoding="utf-8")
    assert invoke(new, project).returncode != 0
    assert invoke(new, project, "update", "--from", tmp_path / "wrong").returncode != 0
    assert invoke(old, project, "check").returncode == 0
    changed = invoke(new, project, "update", "--from", old)
    assert changed.returncode == 0, changed.stderr
    assert invoke(new, project, "check").returncode == 0
    assert (old / "scripts/data_store.py").is_file()
    assert (new / "scripts/data_store.py").is_file()
    assert (data / "keep.txt").read_text(encoding="utf-8") == "existing data"


@pytest.mark.parametrize("kind", ["file", "directory", "missing-install", "redirected-parent"])
def test_refuses_conflicts_without_removing_existing_content(tmp_path, kind):
    skill = install(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    entry = project / ".local/skills/data-store"
    if kind in ("file", "directory"):
        entry.parent.mkdir(parents=True)
        if kind == "file":
            entry.write_text("keep", encoding="utf-8")
        else:
            entry.mkdir()
            (entry / "keep.txt").write_text("keep", encoding="utf-8")
    elif kind == "missing-install":
        (skill / "scripts/data_store.py").unlink()
    else:
        # Use the same native mechanism; the first project is connected correctly.
        other = tmp_path / "other"
        other.mkdir()
        assert invoke(skill, other).returncode == 0
        (other / ".local").rename(project / ".local")
        # The skills parent now points outside the project instead of its data-store child.
        linked = project / ".local/skills/data-store"
        linked.rename(project / ".local/redirect")
        (project / ".local/skills/.gitignore").unlink()
        (project / ".local/skills").rmdir()
        (project / ".local/redirect").rename(project / ".local/skills")
    failed = invoke(skill, project)
    assert failed.returncode != 0
    if kind == "file":
        assert entry.read_text(encoding="utf-8") == "keep"
    elif kind == "directory":
        assert (entry / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert (skill / "SKILL.md").is_file()


def test_project_connection_stays_out_of_git(tmp_path):
    skill = install(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    assert invoke(skill, project).returncode == 0
    status = subprocess.run(["git", "-C", str(project), "status", "--porcelain"],
                            text=True, capture_output=True, check=True)
    assert status.stdout == ""


@pytest.mark.parametrize("restore_fails", [False, True])
def test_update_restores_old_entry_when_filesystem_rename_fails(tmp_path, restore_fails):
    old = install(tmp_path, "old")
    new = install(tmp_path, "new")
    project = tmp_path / "project"
    project.mkdir()
    assert invoke(old, project).returncode == 0
    runner = tmp_path / "fault.py"
    runner.write_text('''import runpy, sys
from pathlib import Path
from unittest.mock import patch
api = runpy.run_path(sys.argv[1])
sys.argv = sys.argv[1:]
original = Path.rename
failures = 0
def rename(source, target):
    global failures
    if Path(target).name == "data-store" and failures < FAIL_LIMIT:
        failures += 1
        raise OSError("injected filesystem rename failure " + str(failures))
    return original(source, target)
with patch.object(Path, "rename", rename):
    raise SystemExit(api["main"]())
'''.replace("FAIL_LIMIT", "2" if restore_fails else "1"), encoding="utf-8")
    failed = subprocess.run(
        [sys.executable, str(runner), str(new / "scripts/project_binding.py"),
         "update", "--project", str(project), "--from", str(old)],
        text=True, capture_output=True,
    )
    assert failed.returncode != 0
    assert "injected filesystem rename failure 1" in failed.stderr
    if restore_fails:
        assert "injected filesystem rename failure 2" in failed.stderr
        assert "旧入口保留在" in failed.stderr
        links = [p for p in (project / ".local/skills").iterdir() if p.is_dir()]
        assert any(p.resolve() == old.resolve() for p in links)
    else:
        assert invoke(old, project, "check").returncode == 0
    assert (old / "scripts/data_store.py").is_file()
    assert (new / "scripts/data_store.py").is_file()
