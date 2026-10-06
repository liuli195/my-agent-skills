"""Exercise the same public project setup entry as bootstrap, without downloads."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def test_project_setup_reuses_environment_and_detects_nested_change(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location('project_environment', ROOT/'scripts/project_environment.py')
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    (tmp_path/'requirements.txt').write_text('-r skill.txt\n')
    (tmp_path/'skill.txt').write_text('example==1\n')
    def execute(args, **kwargs):
        if args[0] == 'git':
            return subprocess.CompletedProcess(args,0,str(tmp_path/'.git')+'\n')
        if '-c' in args:
            return subprocess.CompletedProcess(args,0,f'{sys.version_info.major}.{sys.version_info.minor}\n')
        if 'venv' in args:
            python=tmp_path/'.venv/bin/python'
            python.parent.mkdir(parents=True)
            python.touch()
        return subprocess.CompletedProcess(args,0,'')
    with patch.object(app.subprocess,'run',side_effect=execute):
        assert app.main(['--project',str(tmp_path),'--requirement','requirements.txt']) == 0
        assert capsys.readouterr().out.strip() == 'prepared'
        assert app.main(['--project',str(tmp_path),'--requirement','requirements.txt']) == 0
        assert capsys.readouterr().out.strip() == 'reused'
        (tmp_path/'skill.txt').write_text('example==2\n')
        assert app.main(['--project',str(tmp_path),'--requirement','requirements.txt']) == 0
        assert capsys.readouterr().out.strip() == 'prepared'
