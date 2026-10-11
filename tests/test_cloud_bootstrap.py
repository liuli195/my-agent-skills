"""Public bootstrap entry: small fixtures, no real downloads in repository checks."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]

def entry():
    spec = importlib.util.spec_from_file_location('cloud_bootstrap', ROOT / 'scripts/cloud_bootstrap.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_empty_install_can_be_reused_and_optional_skill_is_nonblocking(tmp_path):
    config = tmp_path / 'environment.json'
    config.write_text(json.dumps({'sources': [], 'npm': [], 'optional_skills': ['data-store']}))
    args = ['init', '--manifest', str(config), '--root', str(tmp_path/'managed')]
    app = entry()
    assert app.main(args) == 0
    assert app.main(args) == 0
    state = json.loads((tmp_path/'managed/installed.json').read_text())
    assert state['pending'] == ['data-store']

def test_unknown_or_unscoped_upgrade_is_rejected_before_install(tmp_path):
    app = entry()
    assert app.main(['update', '--root', str(tmp_path/'managed'), '--latest']) == 1
    assert not (tmp_path/'managed').exists()

def test_failed_install_does_not_record_success(tmp_path):
    import subprocess
    config = tmp_path/'environment.json'
    config.write_text(json.dumps({'sources': [], 'npm': [{'name': 'example', 'version':'1.0.0'}]}))
    app = entry()
    with patch.object(app.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'npm')):
        assert app.main(['init', '--manifest', str(config), '--root', str(tmp_path/'managed')]) == 1
    assert not (tmp_path/'managed/installed.json').exists()

def test_declared_version_sync_reuses_install_and_latest_is_explicit(tmp_path):
    import subprocess
    app = entry()
    config = tmp_path/'environment.json'
    root = tmp_path/'managed'
    package = root/'npm/lib/node_modules/example/package.json'
    config.write_text(json.dumps({'sources': [], 'npm': [{'name':'example','version':'1.0.0'}]}))
    calls = []
    def command(args, **kwargs):
        calls.append(args)
        if 'view' in args:
            return subprocess.CompletedProcess(args, 0, '"3.0.0"')
        package.parent.mkdir(parents=True, exist_ok=True)
        package.write_text(json.dumps({'version': args[-1].split('@')[-1]}))
        return subprocess.CompletedProcess(args, 0, '')
    base = ['--manifest',str(config),'--root',str(root)]
    with patch.object(app.subprocess,'run',side_effect=command):
        assert app.main(['init',*base]) == 0
        assert app.main(['init',*base]) == 0
        assert len(calls) == 1
        config.write_text(json.dumps({'sources': [], 'npm':[{'name':'example','version':'2.0.0'}]}))
        assert app.main(['update',*base]) == 0
        assert json.loads(package.read_text())['version'] == '2.0.0'
        config.write_text(json.dumps({'sources': [], 'npm':[{'name':'example'}]}))
        assert app.main(['update',*base,'--latest','--only','example']) == 0
        assert json.loads(package.read_text())['version'] == '3.0.0'

def test_missing_source_restores_recorded_commit(tmp_path):
    import subprocess
    app = entry()
    root = tmp_path/'managed'
    root.mkdir()
    (root/'installed.json').write_text(json.dumps({'sources':{'sample':{'repo':'owner/repo','ref':'v1','commit':'abc'}},'npm':{}}))
    config=tmp_path/'environment.json'
    config.write_text(json.dumps({'sources':[{'name':'sample','repo':'owner/repo','paths':['skill']}],'npm':[]}))
    fetched=[]
    def execute(args, **kwargs):
        if 'clone' in args:
            (root/'sources/sample/.git').mkdir(parents=True)
        if 'fetch' in args:
            fetched.append(args[-1])
        if 'checkout' in args:
            skill=root/'sources/sample/skill'
            skill.mkdir()
            (skill/'SKILL.md').write_text('skill')
        output='https://github.com/owner/repo.git' if 'remote' in args else 'abc' if 'rev-parse' in args else ''
        return subprocess.CompletedProcess(args,0,output)
    with patch.object(app.subprocess,'run',side_effect=execute):
        assert app.main(['init','--manifest',str(config),'--root',str(root)]) == 0
    assert fetched == ['abc']

def test_obsolete_link_is_reported_without_deleting_it(tmp_path, capsys):
    app=entry()
    root=tmp_path/'managed'
    (root/'skills').mkdir(parents=True)
    stale=root/'skills/old-skill'
    stale.symlink_to(root/'missing')
    config=tmp_path/'environment.json'
    config.write_text('{"sources":[],"npm":[]}')
    assert app.main(['update','--manifest',str(config),'--root',str(root)]) == 1
    assert 'obsolete' in capsys.readouterr().err
    assert stale.is_symlink()

def test_external_managed_stale_link_is_reported(tmp_path, capsys):
    app=entry()
    root=tmp_path/'managed'
    discovery=tmp_path/'user-skills'
    discovery.mkdir()
    stale=discovery/'old-skill'
    stale.symlink_to(root/'skills/old-skill')
    config=tmp_path/'environment.json'
    config.write_text('{"sources":[],"npm":[]}')
    assert app.main(['update','--manifest',str(config),'--root',str(root),'--skills-dir',str(discovery)]) == 1
    assert 'obsolete' in capsys.readouterr().err
    assert stale.is_symlink()

def test_public_entry_checks_python_before_installing(tmp_path, capsys):
    app=entry()
    config=tmp_path/'environment.json'
    config.write_text('{"sources":[],"npm":[]}')
    with patch.object(app.sys,'version_info',(3,11)):
        assert app.main(['init','--root',str(tmp_path/'managed'),'--manifest',str(config)]) == 1
    assert 'Python 3.12' in capsys.readouterr().err
    assert not (tmp_path/'managed').exists()


def prepared_bootstrap_project(tmp_path, *, declared=True, installed=True):
    """Tiny recorded release fixture and ready project environment, without downloads."""
    root = tmp_path / 'managed'
    project = tmp_path / 'project'
    project.mkdir()
    subprocess.run(['git', 'init', '-q', str(project)], check=True)
    subprocess.run(['git', '-C', str(project), 'remote', 'add', 'origin',
                    'https://github.com/owner/project.git'], check=True)
    python = project / '.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    (project / '.local').mkdir()
    (project / '.local/project-environment.json').write_text(json.dumps({
        'inputs': {}, 'python': f'{sys.version_info.major}.{sys.version_info.minor}',
    }))
    source = root / 'sources/own-skills'
    skill = source / 'plugins/data-store/skills/data-store'
    sources = []
    if installed:
        shutil.copytree(ROOT / 'plugins/data-store/skills/data-store', skill,
                        ignore=shutil.ignore_patterns('__pycache__'))
        subprocess.run(['git', 'init', '-q', str(source)], check=True)
        subprocess.run(['git', '-C', str(source), 'remote', 'add', 'origin',
                        'https://github.com/liuli195/my-agent-skills.git'], check=True)
        subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(source), '-c', 'user.name=Fixture',
                        '-c', 'user.email=fixture@example.com', 'commit', '-qm', 'fixture'], check=True)
        commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        (root / 'installed.json').write_text(json.dumps({'sources': {'own-skills': {
            'repo': 'liuli195/my-agent-skills', 'ref': 'vfixture', 'commit': commit,
        }}, 'npm': {}}))
        sources = [{'name': 'own-skills', 'repo': 'liuli195/my-agent-skills',
                    'ref': 'vfixture', 'paths': ['plugins/data-store']}]
    recipe = {'requirements': [], 'npm': False}
    if declared:
        recipe['skills'] = ['data-store']
    manifest = tmp_path / 'environment.json'
    manifest.write_text(json.dumps({'sources': sources, 'npm': [], 'optional_skills': ['data-store'],
                                    'projects': {'owner/project': recipe}}))
    arguments = [sys.executable, str(ROOT / 'scripts/cloud_bootstrap.py'), 'init',
                 '--root', str(root), '--manifest', str(manifest), '--project', str(project)]
    return root, project, skill, arguments


@pytest.mark.skipif(os.name == 'nt', reason='Linux project entry; Windows uses its existing setup recipe')
def test_public_bootstrap_connects_declared_data_store_and_reuses_it(tmp_path):
    root, project, skill, arguments = prepared_bootstrap_project(tmp_path)
    for _ in range(2):
        result = subprocess.run(arguments, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        checked = subprocess.run(
            [sys.executable, str(root / 'skills/data-store/scripts/project_binding.py'),
             'check', '--project', str(project)], text=True, capture_output=True,
        )
        assert checked.returncode == 0, checked.stderr
        assert Path(json.loads(checked.stdout)['target']) == skill.resolve()
    script = project / '.local/skills/data-store/scripts/data_store.py'
    data = project / 'data'
    written = subprocess.run([sys.executable, str(script), '--root', str(data),
                              'write', 'readings', 'one'], input='[{"value":7}]',
                             text=True, capture_output=True)
    assert written.returncode == 0, written.stderr
    queried = subprocess.run([sys.executable, str(script), '--root', str(data),
                              'query', 'SELECT value FROM readings', '--tables', '["readings"]'],
                             text=True, capture_output=True)
    assert queried.returncode == 0, queried.stderr
    assert json.loads(queried.stdout) == {'value': 7}


@pytest.mark.skipif(os.name == 'nt', reason='Linux project entry; Windows uses its existing setup recipe')
@pytest.mark.parametrize('declared,installed', [(False, True), (True, False)])
def test_public_bootstrap_leaves_undeclared_or_pending_data_store_unbound(tmp_path, declared, installed):
    root, project, skill, arguments = prepared_bootstrap_project(tmp_path, declared=declared, installed=installed)
    result = subprocess.run(arguments, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert not (project / '.local/skills/data-store').exists()
    if not installed:
        assert json.loads(result.stdout.splitlines()[-1])['pending'] == ['data-store']
        assert not (root / 'sources').exists()


@pytest.mark.skipif(os.name == 'nt', reason='Linux project entry; Windows uses its existing setup recipe')
@pytest.mark.parametrize('conflict', ['directory', 'wrong-source'])
def test_public_bootstrap_preserves_existing_project_binding_conflicts(tmp_path, conflict):
    root, project, skill, arguments = prepared_bootstrap_project(tmp_path)
    binding = project / '.local/skills/data-store'
    binding.parent.mkdir(parents=True)
    if conflict == 'directory':
        binding.mkdir()
        (binding / 'keep.txt').write_text('existing content')
    else:
        other = tmp_path / 'other-install'
        shutil.copytree(skill, other)
        binding.symlink_to(other, target_is_directory=True)
    result = subprocess.run(arguments, text=True, capture_output=True)
    assert result.returncode == 1, result.stdout
    if conflict == 'directory':
        assert (binding / 'keep.txt').read_text() == 'existing content'
    else:
        assert binding.resolve() == other.resolve()
    assert (skill / 'scripts/data_store.py').is_file()


def test_public_bootstrap_requires_installation_root(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/cloud_bootstrap.py'), 'init'],
                            text=True, capture_output=True, cwd=tmp_path)
    assert result.returncode == 2
    assert '--root' in result.stderr
