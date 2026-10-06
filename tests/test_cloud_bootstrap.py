"""Public bootstrap entry: small fixtures, no real downloads in repository checks."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

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
