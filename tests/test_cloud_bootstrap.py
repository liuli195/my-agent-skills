"""Project preparation decisions through the public bootstrap entry."""
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def entry():
    spec = importlib.util.spec_from_file_location('cloud_bootstrap', ROOT / 'scripts/cloud_bootstrap.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def project_setup(monkeypatch):
    app = entry()
    state = SimpleNamespace(app=app, project=ROOT, manifest_path=ROOT / '.unit-environment.json',
        manifest={'projects': {'owner/project': {'requirements': ['requirements.txt'], 'npm': True,
                  'windows_setup': ['pwsh', '-File', 'setup.ps1']}}}, commands=[])
    original = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda path, *args, **kwargs:
        json.dumps(state.manifest) if path == state.manifest_path else original(path, *args, **kwargs))

    def run(command, **kwargs):
        state.commands.append((command, kwargs))
        if command == ['git', '-C', state.project, 'remote', 'get-url', 'origin']:
            return 'https://github.com/owner/project.git'
        return 'prepared'

    monkeypatch.setattr(app, 'run', run)
    state.arguments = ['--project', str(state.project), '--manifest', str(state.manifest_path)]
    return state


@pytest.mark.parametrize('action', ['init', 'update'])
@pytest.mark.parametrize('platform', ['posix', 'nt'])
def test_public_entry_prepares_declared_project_without_plugin_resources(project_setup, capsys, monkeypatch, action, platform):
    state = project_setup
    monkeypatch.setattr(state.app, 'os', SimpleNamespace(name=platform))
    assert state.app.main([action, *state.arguments]) == 0
    command, options = state.commands[-1]
    if state.app.os.name == 'nt':
        assert command == ['pwsh', '-File', 'setup.ps1']
    else:
        assert command == [state.app.sys.executable, ROOT / 'scripts/project_environment.py',
                           '--project', ROOT, '--requirement', 'requirements.txt', '--npm']
    assert options == {'cwd': ROOT}
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {'status': 'ready', 'project': str(ROOT)}


@pytest.mark.parametrize('key', ['sources', 'npm', 'optional_skills', 'runtime_packages', 'discovery', 'bindings', 'unknown'])
def test_empty_retired_config_is_rejected_before_preparation(project_setup, capsys, key):
    state = project_setup
    state.manifest[key] = []
    assert state.app.main(['init', *state.arguments]) == 1
    assert key in capsys.readouterr().err
    assert state.commands == []


@pytest.mark.parametrize('key', ['bindings', 'skills', 'runtime', 'unknown'])
def test_retired_recipe_keys_fail_before_preparation(project_setup, capsys, key):
    state = project_setup
    state.manifest['projects']['owner/project'][key] = []
    assert state.app.main(['init', *state.arguments]) == 1
    assert key in capsys.readouterr().err
    assert state.commands == []


@pytest.mark.parametrize('manifest', [[], {}, {'projects': []}, {'projects': {'owner/project': []}},
    {'projects': {'owner/project': {'requirements': 'requirements.txt'}}},
    {'projects': {'owner/project': {'requirements': [None]}}},
    {'projects': {'owner/project': {'npm': 'false'}}},
    {'projects': {'owner/project': {'windows_setup': []}}},
    {'projects': {'owner/project': {'windows_setup': None}}},
    {'projects': {'owner/project': {'windows_setup': 'setup.ps1'}}}])
def test_invalid_manifest_structure_fails_before_preparation(project_setup, manifest):
    state = project_setup
    state.manifest = manifest
    assert state.app.main(['init', *state.arguments]) == 1
    assert state.commands == []


@pytest.mark.parametrize('option', ['--root', '--runtime-manifest', '--latest', '--only', '--skills-dir'])
def test_retired_arguments_are_argparse_errors_before_preparation(project_setup, option, capsys):
    state = project_setup
    with pytest.raises(SystemExit) as error:
        state.app.main(['init', *state.arguments, option, *([] if option == '--latest' else ['unused'])])
    assert error.value.code == 2
    assert 'unrecognized arguments' in capsys.readouterr().err
    assert state.commands == []


def test_project_is_required(capsys):
    with pytest.raises(SystemExit) as error:
        entry().main(['init'])
    assert error.value.code == 2
    assert '--project' in capsys.readouterr().err


def test_unknown_project_fails_without_preparation(project_setup, capsys):
    state = project_setup
    state.manifest['projects'] = {}
    assert state.app.main(['init', *state.arguments]) == 1
    assert len(state.commands) == 1 and state.commands[0][0][0] == 'git'
    output = capsys.readouterr()
    assert 'not declared' in output.err and 'ready' not in output.out


def test_failed_project_preparation_does_not_report_ready(project_setup, monkeypatch, capsys):
    state = project_setup
    original = state.app.run
    def run(command, **kwargs):
        if command[0] == 'git':
            return original(command, **kwargs)
        raise subprocess.CalledProcessError(7, command, output='partial installation')
    monkeypatch.setattr(state.app, 'run', run)
    assert state.app.main(['update', *state.arguments]) == 1
    output = capsys.readouterr()
    assert 'ready' not in output.out
    assert 'partial installation' in output.err


def test_public_entry_checks_python_before_preparation(project_setup, monkeypatch, capsys):
    state = project_setup
    monkeypatch.setattr(state.app.sys, 'version_info', (3, 11))
    assert state.app.main(['init', *state.arguments]) == 1
    assert 'Python 3.12' in capsys.readouterr().err
    assert state.commands == []
