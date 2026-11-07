"""One public bootstrap smoke without dependency downloads or plugin installs."""
import json
import os
from pathlib import Path
import subprocess

import pytest


class TestBootstrap:
    @pytest.mark.skipif(os.name == 'nt', reason='Real Linux project environment; Windows uses its existing recipe')
    def test_public_bootstrap_prepares_and_reuses_project_environment(self, tmp_path, capsys):
        from tests.test_cloud_bootstrap import entry
        app = entry()
        project = tmp_path / 'project'
        project.mkdir()
        subprocess.run(['git', 'init', str(project)], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(project), 'remote', 'add', 'origin',
                        'https://github.com/owner/project.git'], check=True)
        sentinel = project / 'business.txt'
        sentinel.write_text('existing business data')
        manifest = tmp_path / 'manifest.json'
        manifest.write_text(json.dumps({'projects': {'owner/project': {'requirements': [], 'npm': False}}}))
        arguments = ['--project', str(project), '--manifest', str(manifest)]
        state = project / '.local/project-environment.json'
        python = project / '.venv/bin/python'
        assert app.main(['init', *arguments]) == 0
        assert python.is_file() and state.is_file()
        subprocess.run([str(python), '-c', 'import sys; assert sys.prefix != sys.base_prefix'], check=True)
        output = capsys.readouterr()
        assert 'prepared' in output.out and 'ready' in output.out
        original = (state.read_bytes(), state.stat().st_mtime_ns, python.stat().st_mtime_ns)
        for action in ('init', 'update'):
            assert app.main([action, *arguments]) == 0
            assert (state.read_bytes(), state.stat().st_mtime_ns, python.stat().st_mtime_ns) == original
            output = capsys.readouterr()
            assert 'reused' in output.out and 'ready' in output.out
        assert sentinel.read_text() == 'existing business data'
        assert {path.name for path in tmp_path.iterdir()} == {'project', 'manifest.json'}
        assert {path.name for path in project.iterdir()} == {'.git', '.venv', '.local', 'business.txt'}
        assert {path.name for path in (project / '.local').iterdir()} == {'project-environment.json'}
