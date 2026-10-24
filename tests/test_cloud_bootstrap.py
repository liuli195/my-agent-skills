"""Bootstrap decisions run through main with bounded installation I/O leaves."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def entry():
    spec = importlib.util.spec_from_file_location("cloud_bootstrap", ROOT / "scripts/cloud_bootstrap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def installation(monkeypatch):
    """Only this manifest, state record, package and source have memory I/O."""
    app = entry()
    root = ROOT / ".unit-bootstrap-installation"
    manifest_path = ROOT / ".unit-bootstrap-manifest.json"
    discovery = root / "skills"
    destination = root / "sources/sample"
    package = root / "npm/lib/node_modules/example"
    state = SimpleNamespace(
        app=app, root=root, manifest_path=manifest_path, destination=destination,
        manifest={"sources": [], "npm": []}, installed=None, version=None,
        source_exists=False, source_ready=False, skill_ready=False,
        saved=[], commands=[], directories=[],
    )
    original_read = Path.read_text
    original_exists = Path.exists
    original_file = Path.is_file
    original_iterdir = Path.iterdir
    original_glob = Path.glob
    original_rglob = Path.rglob

    def read_text(path, *args, **kwargs):
        if path == manifest_path:
            return json.dumps(state.manifest)
        if path == root / "installed.json":
            assert state.installed is not None
            return json.dumps(state.installed)
        if path == package / "package.json":
            assert state.version is not None
            return json.dumps({"version": state.version})
        assert not path.is_relative_to(root), f"unexpected installation read: {path}"
        return original_read(path, *args, **kwargs)

    def exists(path):
        if path == root / "installed.json":
            return state.installed is not None
        if path == package / "package.json":
            return state.version is not None
        if path == destination:
            return state.source_exists
        if path == destination / "skill":
            return state.source_ready
        assert not path.is_relative_to(root), f"unexpected installation probe: {path}"
        return original_exists(path)

    def is_file(path):
        if path == discovery / "data-store/SKILL.md":
            return state.skill_ready
        assert not path.is_relative_to(root), f"unexpected installation file probe: {path}"
        return original_file(path)

    def mkdir(path, *args, **kwargs):
        assert path in {root, discovery, destination.parent}, f"unexpected installation write: {path}"
        state.directories.append(path)

    def iterdir(path):
        if path == discovery:
            return iter(())
        assert not path.is_relative_to(root), f"unexpected installation enumeration: {path}"
        return original_iterdir(path)

    def glob(path, pattern):
        if path == package / "skills":
            assert pattern == "*/SKILL.md"
            return iter(())
        assert not path.is_relative_to(root), f"unexpected package enumeration: {path}"
        return original_glob(path, pattern)

    def rglob(path, pattern):
        if path == destination:
            assert pattern == "SKILL.md"
            return iter([destination / "skill/SKILL.md"] if state.source_ready else [])
        assert not path.is_relative_to(root), f"unexpected source enumeration: {path}"
        return original_rglob(path, pattern)

    def save(path, value):
        assert path == root / "installed.json", f"unexpected state write: {path}"
        state.installed = copy.deepcopy(value)
        state.saved.append(copy.deepcopy(value))

    def link(path, target):
        assert (path, target) == (discovery / "skill", destination / "skill")

    def unexpected_command(command, **kwargs):
        pytest.fail(f"unexpected external command: {command}")

    def unexpected_github(path):
        pytest.fail(f"unexpected GitHub request: {path}")

    for name, operation in {"read_text": read_text, "exists": exists, "is_file": is_file,
                            "mkdir": mkdir, "iterdir": iterdir, "glob": glob, "rglob": rglob}.items():
        monkeypatch.setattr(Path, name, operation)
    monkeypatch.setattr(app, "save", save)
    monkeypatch.setattr(app, "link", link)
    monkeypatch.setattr(app, "run", unexpected_command)
    monkeypatch.setattr(app, "github", unexpected_github)
    state.arguments = ["--manifest", str(manifest_path), "--root", str(root)]
    return state


def test_empty_install_can_be_reused_and_optional_skill_is_nonblocking(installation):
    state = installation
    state.manifest["optional_skills"] = ["data-store"]
    for _ in range(2):
        assert state.app.main(["init", *state.arguments]) == 0
    assert state.installed == {"sources": {}, "npm": {}, "pending": ["data-store"]}


@pytest.mark.parametrize("arguments", [["update", "--latest"], ["init", "--latest", "--only", "example"]])
def test_unscoped_or_nonupdate_latest_is_rejected_before_install(installation, arguments):
    state = installation
    assert state.app.main([*arguments, *state.arguments]) == 1
    assert state.directories == []
    assert state.saved == []


def test_unknown_selection_is_rejected_before_install(installation, capsys):
    state = installation
    assert state.app.main(["update", *state.arguments, "--only", "unknown"]) == 1
    assert "Unknown update selection" in capsys.readouterr().err
    assert state.directories == []
    assert state.saved == []


def test_failed_install_does_not_record_success(installation, monkeypatch):
    state = installation
    state.manifest["npm"] = [{"name": "example", "version": "1.0.0"}]

    def fail_install(command, **kwargs):
        assert command[0:3] == ["npm", "install", "--global"]
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(state.app, "run", fail_install)
    assert state.app.main(["init", *state.arguments]) == 1
    assert state.installed is None
    assert state.saved == []


def test_declared_version_sync_reuses_install_and_latest_is_explicit(installation, monkeypatch):
    state = installation
    state.manifest["npm"] = [{"name": "example", "version": "1.0.0"}]

    def execute(command, **kwargs):
        state.commands.append(command)
        if command == ["npm", "view", "example", "version", "--json"]:
            return '"3.0.0"'
        assert command[:-1] == ["npm", "install", "--global", "--prefix", state.root / "npm",
                                "--cache", state.root / "cache/npm", "--ignore-scripts", "--no-audit", "--no-fund"]
        assert command[-1] in {"example@1.0.0", "example@2.0.0", "example@3.0.0"}
        state.version = command[-1].split("@")[-1]
        return ""

    monkeypatch.setattr(state.app, "run", execute)
    assert state.app.main(["init", *state.arguments]) == 0
    assert state.app.main(["init", *state.arguments]) == 0
    assert len(state.commands) == 1
    state.manifest["npm"] = [{"name": "example", "version": "2.0.0"}]
    assert state.app.main(["update", *state.arguments]) == 0
    assert state.installed["npm"] == {"example": "2.0.0"}
    state.manifest["npm"] = [{"name": "example"}]
    assert state.app.main(["update", *state.arguments, "--latest", "--only", "example"]) == 0
    assert state.installed["npm"] == {"example": "3.0.0"}
    assert [command[-1] for command in state.commands if command[1] == "install"] == [
        "example@1.0.0", "example@2.0.0", "example@3.0.0"]


def test_missing_source_restores_recorded_commit(installation, monkeypatch):
    state = installation
    state.installed = {"sources": {"sample": {"repo": "owner/repo", "ref": "v1", "commit": "abc"}}, "npm": {}}
    state.manifest["sources"] = [{"name": "sample", "repo": "owner/repo", "paths": ["skill"]}]
    expected = [
        (["git", "clone", "--filter=blob:none", "--sparse", "--no-checkout", "https://github.com/owner/repo.git", state.destination], ""),
        (["git", "-C", state.destination, "remote", "get-url", "origin"], "https://github.com/owner/repo.git"),
        (["git", "-C", state.destination, "status", "--porcelain"], ""),
        (["git", "-C", state.destination, "fetch", "--depth", "1", "origin", "abc"], ""),
        (["git", "-C", state.destination, "checkout", "--detach", "FETCH_HEAD"], ""),
        (["git", "-C", state.destination, "sparse-checkout", "set", "skill"], ""),
        (["git", "-C", state.destination, "rev-parse", "HEAD"], "abc"),
    ]

    def execute(command, **kwargs):
        wanted, output = expected.pop(0)
        assert command == wanted
        if command[1] == "clone":
            state.source_exists = True
        if "checkout" in command:
            state.source_ready = True
        return output

    monkeypatch.setattr(state.app, "run", execute)
    assert state.app.main(["init", *state.arguments]) == 0
    assert expected == []
    assert state.installed["sources"]["sample"]["commit"] == "abc"


@pytest.mark.parametrize("declared,ready", [(False, True), (True, False), (True, True)])
def test_project_binding_follows_only_declared_ready_skill(installation, monkeypatch, declared, ready):
    state = installation
    project = ROOT
    recipe = {"requirements": [], "npm": False, "skills": ["data-store"] if declared else [],
              "windows_setup": ["powershell", "-NoProfile", "-Command", "Write-Output reused"]}
    state.manifest.update(optional_skills=["data-store"], projects={"owner/project": recipe})
    state.skill_ready = ready
    setup = (recipe["windows_setup"] if state.app.os.name == "nt" else
             [state.app.sys.executable, ROOT / "scripts/project_environment.py", "--project", project])
    expected = [
        (["git", "-C", project, "remote", "get-url", "origin"], "https://github.com/owner/project.git"),
        (setup, "reused"),
    ]
    if declared and ready:
        expected.extend(([state.app.sys.executable, state.root / "skills/data-store/scripts/project_binding.py",
                          action, "--project", project], "checked") for action in ("connect", "check"))

    def execute(command, **kwargs):
        wanted, output = expected.pop(0)
        assert command == wanted
        return output

    monkeypatch.setattr(state.app, "run", execute)
    assert state.app.main(["init", *state.arguments, "--project", str(project)]) == 0
    assert expected == []
    assert state.installed["pending"] == ([] if ready else ["data-store"])


def test_public_entry_checks_python_before_installing(capsys):
    app = entry()
    from unittest.mock import patch
    with patch.object(app.sys, "version_info", (3, 11)):
        assert app.main(["init", "--root", str(ROOT / "unused-managed")]) == 1
    assert "Python 3.12" in capsys.readouterr().err


def test_public_bootstrap_requires_installation_root(capsys):
    with pytest.raises(SystemExit) as error:
        entry().main(["init"])
    assert error.value.code == 2
    assert "--root" in capsys.readouterr().err
