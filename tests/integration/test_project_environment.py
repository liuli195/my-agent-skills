"""Explicit project preparation, installed links and binding recovery scenarios."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins/data-store/skills/data-store"


@pytest.fixture(scope="session")
def bootstrap_installation(tmp_path_factory):
    """Complete installed-shaped source shared by non-destructive link scenarios."""
    target = tmp_path_factory.mktemp("bootstrap-skill") / "data-store"
    shutil.copytree(SKILL, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def entry():
    spec = importlib.util.spec_from_file_location('cloud_bootstrap', ROOT / 'scripts/cloud_bootstrap.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(skill, project, command="connect", *extra):
    return subprocess.run(
        [sys.executable, str(skill / "scripts/project_binding.py"), command,
         "--project", str(project), *map(str, extra)],
        text=True, capture_output=True,
    )


def install(tmp_path, name="installed", *, source):
    # Most scenarios only link to the complete source. Source changes and broken
    # installation scenarios explicitly request a private identity below.
    if name == "installed":
        return source
    target = tmp_path / name
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def prepared_bootstrap_project(tmp_path, *, declared=True, installed=True, installed_source=SKILL):
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
        shutil.copytree(installed_source, skill,
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


class TestBootstrap:
    """No database import or query is needed to prove project preparation."""

    def test_obsolete_link_is_reported_without_deleting_it(self, bootstrap_installation, tmp_path, capsys):
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



    def test_external_managed_stale_link_is_reported(self, bootstrap_installation, tmp_path, capsys):
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



    @pytest.mark.skipif(os.name == 'nt', reason='Linux project entry; Windows uses its existing setup recipe')
    @pytest.mark.parametrize('declared,installed', [(False, True), (True, False)])
    def test_public_bootstrap_leaves_undeclared_or_pending_data_store_unbound(self, bootstrap_installation, tmp_path, declared, installed):
        root, project, skill, arguments = prepared_bootstrap_project(tmp_path, installed_source=bootstrap_installation, declared=declared, installed=installed)
        result = subprocess.run(arguments, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert not (project / '.local/skills/data-store').exists()
        if not installed:
            assert json.loads(result.stdout.splitlines()[-1])['pending'] == ['data-store']
            assert not (root / 'sources').exists()



    @pytest.mark.skipif(os.name == 'nt', reason='Linux project entry; Windows uses its existing setup recipe')
    @pytest.mark.parametrize('conflict', ['directory', 'wrong-source'])
    def test_public_bootstrap_preserves_existing_project_binding_conflicts(self, bootstrap_installation, tmp_path, conflict):
        root, project, skill, arguments = prepared_bootstrap_project(tmp_path, installed_source=bootstrap_installation)
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



    @pytest.mark.skipif(os.name == "nt", reason="Linux project entry; Windows uses its existing setup recipe")
    def test_public_bootstrap_reuses_the_declared_installed_binding(self, bootstrap_installation, tmp_path):
        root, project, skill, arguments = prepared_bootstrap_project(tmp_path, installed_source=bootstrap_installation)
        for _ in range(2):
            result = subprocess.run(arguments, text=True, capture_output=True)
            assert result.returncode == 0, result.stderr
            checked = invoke(root / "skills/data-store", project, "check")
            assert checked.returncode == 0, checked.stderr
            assert Path(json.loads(checked.stdout)["target"]) == skill.resolve()


    @pytest.mark.skipif(os.name == "nt", reason="Linux adapter; Windows uses the setup-worktree entry tests")
    def test_project_setup_reuses_environment_and_detects_nested_change(self, bootstrap_installation, tmp_path, capsys):
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



    def test_update_checks_old_source_and_preserves_sources_and_data(self, bootstrap_installation, tmp_path):
        old = install(tmp_path, "old", source=bootstrap_installation)
        new = install(tmp_path, "new", source=bootstrap_installation)
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
    def test_refuses_conflicts_without_removing_existing_content(self, bootstrap_installation, tmp_path, kind):
        skill = install(tmp_path, "broken" if kind == "missing-install" else "installed", source=bootstrap_installation)
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



    def test_project_connection_stays_out_of_git(self, bootstrap_installation, tmp_path):
        skill = install(tmp_path, source=bootstrap_installation)
        project = tmp_path / "project"
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        assert invoke(skill, project).returncode == 0
        status = subprocess.run(["git", "-C", str(project), "status", "--porcelain"],
                                text=True, capture_output=True, check=True)
        assert status.stdout == ""



    @pytest.mark.parametrize("restore_fails", [False, True])
    def test_update_restores_old_entry_when_filesystem_rename_fails(self, bootstrap_installation, tmp_path, restore_fails):
        old = install(tmp_path, "old", source=bootstrap_installation)
        new = install(tmp_path, "new", source=bootstrap_installation)
        project = tmp_path / "project"
        project.mkdir()
        assert invoke(old, project).returncode == 0
        source = (
            "import runpy, sys\n"
            "from pathlib import Path\n"
            "from unittest.mock import patch\n"
            "api = runpy.run_path(sys.argv[1])\n"
            "sys.argv = sys.argv[1:]\n"
            "original = Path.rename\n"
            "failures = 0\n"
            "def rename(source, target):\n"
            "    global failures\n"
            "    if Path(target).name == 'data-store' and failures < FAIL_LIMIT:\n"
            "        failures += 1\n"
            "        raise OSError('injected filesystem rename failure ' + str(failures))\n"
            "    return original(source, target)\n"
            "with patch.object(Path, 'rename', rename):\n"
            "    raise SystemExit(api['main']())\n"
        ).replace("FAIL_LIMIT", "2" if restore_fails else "1")
        failed = subprocess.run(
            [sys.executable, "-c", source, str(new / "scripts/project_binding.py"),
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



    def test_installed_connection_is_repeatable_and_checks_the_same_source(self, bootstrap_installation, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        for _ in range(2):
            connected = invoke(bootstrap_installation, project)
            assert connected.returncode == 0, connected.stderr
            checked = invoke(bootstrap_installation, project, "check")
            assert checked.returncode == 0, checked.stderr
            assert Path(json.loads(checked.stdout)["target"]) == bootstrap_installation.resolve()
