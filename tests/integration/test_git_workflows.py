"""Explicit real Git and filesystem boundaries for PR and release workflows.

Each selected class imports only its own case helpers lazily. Ordinary test
modules never request this integration setup.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import importlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
import pytest
import yaml
from tests.support.git_templates import copy_template, remove_template

def _pr_cases():
    return importlib.import_module('tests.test_pr_flow_cli')

def _release_cases():
    return importlib.import_module('tests.test_release_flow_cli')

def _package_cases():
    return importlib.import_module('tests.test_pr_flow_plugin_package')
_PR_TEMPLATE_ROOT = None
_PR_TEMPLATE_CACHE_KEY = None
_PR_TEMPLATE_LOCK_TIMEOUT_SECONDS = 30
_PR_TEMPLATE_LOCK_STALE_SECONDS = 30

def _pr_template_cache_key(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(_pr_cases().REPO_ROOT)).encode('utf-8'))
        digest.update(b'\x00')
        digest.update(path.read_bytes())
        digest.update(b'\x00')
    return digest.hexdigest()[:12]

def _pr_run_with_path(path: Path, *args: str, cwd: Path | None=None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env['PATH'] = str(path) + os.pathsep + env.get('PATH', '')
    return _pr_cases().run(*args, cwd=cwd, env=env)

def _pr_git(project: Path, *args: str) -> str:
    result = subprocess.run(['git', *args], cwd=project, check=False, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()

def _pr_init_repo(project: Path) -> str:
    project.mkdir()
    _pr_git(project, 'init')
    _pr_git(project, 'branch', '-M', 'main')
    _pr_git(project, 'config', 'user.email', 'test@example.com')
    _pr_git(project, 'config', 'user.name', 'Test User')
    (project / 'README.md').write_text('# Test Project\n', encoding='utf-8')
    _pr_git(project, 'add', 'README.md')
    _pr_git(project, 'commit', '-m', 'init')
    return _pr_git(project, 'branch', '--show-current')

def _pr_init_feature_branch(project: Path) -> None:
    assert _pr_init_repo(project) == 'main'
    _pr_git(project, 'checkout', '-b', 'feature/example')
    (project / 'README.md').write_text('# Test Project\n\nFeature change\n', encoding='utf-8')
    _pr_git(project, 'add', 'README.md')
    _pr_git(project, 'commit', '-m', 'feature')

def _pr_write_fake_gh(bin_dir: Path, *, stdout: str='', stderr: str='', exit_code: int=0, calls_path: Path | None=None) -> Path:
    bin_dir.mkdir(exist_ok=True)
    fake_script = bin_dir / 'gh_fake.py'
    lines = ['import sys', f'sys.stdout.write({stdout!r})', f'sys.stderr.write({stderr!r})']
    if calls_path is not None:
        lines.append(f"open({str(calls_path)!r}, 'a', encoding='utf-8').close()")
    lines.extend([f'raise SystemExit({exit_code})', ''])
    fake_script.write_text('\n'.join(lines), encoding='utf-8')
    if os.name == 'nt':
        launcher = bin_dir / 'gh.cmd'
        launcher.write_text(f'@echo off\n"{sys.executable}" "%~dp0gh_fake.py" %*\nexit /b %ERRORLEVEL%\n', encoding='utf-8')
    else:
        launcher = bin_dir / 'gh'
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/gh_fake.py" "$@"\n', encoding='utf-8')
        launcher.chmod(493)
    return bin_dir

def _pr_write_fake_gh_sequence(bin_dir: Path, responses: list[dict[str, object]]) -> tuple[Path, Path]:
    bin_dir.mkdir()
    responses_path = bin_dir / 'responses.json'
    calls_path = bin_dir / 'calls.json'
    body_files_path = bin_dir / 'body_files.json'
    responses_path.write_text(json.dumps(responses), encoding='utf-8')
    calls_path.write_text('[]', encoding='utf-8')
    body_files_path.write_text('[]', encoding='utf-8')
    fake_script = bin_dir / 'gh_fake_sequence.py'
    fake_script.write_text('\n'.join(['import json', 'import sys', 'from pathlib import Path', f'responses_path = Path({str(responses_path)!r})', f'calls_path = Path({str(calls_path)!r})', f'body_files_path = Path({str(body_files_path)!r})', "responses = json.loads(responses_path.read_text(encoding='utf-8'))", "calls = json.loads(calls_path.read_text(encoding='utf-8'))", "body_files = json.loads(body_files_path.read_text(encoding='utf-8'))", 'index = len(calls)', 'calls.append(sys.argv[1:])', "calls_path.write_text(json.dumps(calls, indent=2), encoding='utf-8')", "if '--body-file' in sys.argv[1:]:", "    body_index = sys.argv.index('--body-file') + 1", '    body_path = Path(sys.argv[body_index])', "    body_files.append({'args': sys.argv[1:], 'body': body_path.read_text(encoding='utf-8')})", "    body_files_path.write_text(json.dumps(body_files, indent=2), encoding='utf-8')", 'if index >= len(responses):', "    sys.stderr.write('unexpected gh call: ' + ' '.join(sys.argv[1:]) + '\\n')", '    raise SystemExit(99)', 'response = responses[index]', "sys.stdout.write(str(response.get('stdout', '')))", "sys.stderr.write(str(response.get('stderr', '')))", "raise SystemExit(int(response.get('exit_code', 0)))", '']), encoding='utf-8')
    if os.name == 'nt':
        launcher = bin_dir / 'gh.cmd'
        launcher.write_text(f'@echo off\n"{sys.executable}" "%~dp0gh_fake_sequence.py" %*\nexit /b %ERRORLEVEL%\n', encoding='utf-8')
    else:
        launcher = bin_dir / 'gh'
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/gh_fake_sequence.py" "$@"\n', encoding='utf-8')
        launcher.chmod(493)
    return (bin_dir, calls_path)

def _pr_git_bare(remote: Path, *args: str) -> str:
    result = subprocess.run(['git', '--git-dir', str(remote), *args], check=False, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()

def _pr_git_bare_result(remote: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['git', '--git-dir', str(remote), *args], check=False, text=True, capture_output=True)

def _pr_copy_project_remote_template(template_dir: Path, tmp_path: Path) -> tuple[Path, Path]:
    remote = copy_template(template_dir / 'remote.git', tmp_path / 'remote.git')
    project = copy_template(template_dir / 'project', tmp_path / 'project')
    _pr_git(project, 'remote', 'set-url', 'origin', str(remote))
    return (project, remote)

def _pr_remove_template_lock(lock_dir: Path) -> None:
    for _ in range(5):
        shutil.rmtree(lock_dir, ignore_errors=True)
        if not lock_dir.exists():
            return
        time.sleep(0.05)

def _pr_ensure_project_remote_template(template_name: str, tmp_path: Path, creator) -> tuple[Path, Path]:
    template_dir = _PR_TEMPLATE_ROOT / template_name
    ready = template_dir / '.ready'
    lock_dir = _PR_TEMPLATE_ROOT / f'{template_name}.lock'
    if ready.exists():
        if lock_dir.exists():
            _pr_remove_template_lock(lock_dir)
        return _pr_copy_project_remote_template(template_dir, tmp_path)
    deadline = time.monotonic() + _PR_TEMPLATE_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock_dir.mkdir(parents=True)
            break
        except FileExistsError:
            try:
                lock_age = time.time() - lock_dir.stat().st_mtime
            except FileNotFoundError:
                continue
            if lock_age > _PR_TEMPLATE_LOCK_STALE_SECONDS:
                _pr_remove_template_lock(lock_dir)
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f'template_lock_timeout: {lock_dir}')
            time.sleep(0.05)
    try:
        if not ready.exists():
            if template_dir.exists():
                remove_template(template_dir)
            template_dir.mkdir(parents=True, exist_ok=True)
            creator(template_dir)
            ready.write_text('ok\n', encoding='utf-8')
    finally:
        _pr_remove_template_lock(lock_dir)
    return _pr_copy_project_remote_template(template_dir, tmp_path)

def _pr__create_minimal_project_remote_template(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / 'remote.git'
    remote_init = subprocess.run(['git', 'init', '--bare', str(remote)], check=False, text=True, capture_output=True)
    assert remote_init.returncode == 0, remote_init.stdout + remote_init.stderr
    project = tmp_path / 'project'
    assert _pr_init_repo(project) == 'main'
    _pr_git(project, 'remote', 'add', 'origin', str(remote))
    _pr_git(project, 'push', '-u', 'origin', 'main')
    return (project, remote)

def _pr_fake_project_remote_template(template_dir: Path) -> None:
    (template_dir / 'project').mkdir()
    (template_dir / 'remote.git').mkdir()

def _pr_fake_copy_project_remote_template(template_dir: Path, tmp_path: Path) -> tuple[Path, Path]:
    remote = copy_template(template_dir / 'remote.git', tmp_path / 'remote.git')
    project = copy_template(template_dir / 'project', tmp_path / 'project')
    return (project, remote)

def _pr_init_cleanup_project(tmp_path: Path, *, base_ref: str='main', head_ref: str='feature/example') -> tuple[Path, Path]:
    template_name = f'cleanup-{base_ref}-{head_ref}'.replace('/', '_').replace('\\', '_').replace(':', '_')
    return _pr_ensure_project_remote_template(template_name, tmp_path, lambda template_dir: _pr__create_cleanup_project(template_dir, base_ref=base_ref, head_ref=head_ref))

def _pr__create_cleanup_project(tmp_path: Path, *, base_ref: str='main', head_ref: str='feature/example') -> tuple[Path, Path]:
    remote = tmp_path / 'remote.git'
    remote_init = subprocess.run(['git', 'init', '--bare', str(remote)], check=False, text=True, capture_output=True)
    assert remote_init.returncode == 0, remote_init.stdout + remote_init.stderr
    project = tmp_path / 'project'
    assert _pr_init_repo(project) == 'main'
    _pr_git(project, 'branch', '-M', base_ref)
    _pr_cases().write_confirmed_pr_flow_config(project, _pr_cases().default_pr_flow_config_for_test(base_ref))
    _pr_git(project, 'add', '.pr-flow')
    _pr_git(project, 'commit', '-m', 'configure pr flow')
    _pr_git(project, 'remote', 'add', 'origin', str(remote))
    _pr_git(project, 'push', '-u', 'origin', base_ref)
    _pr_git(project, 'checkout', '-b', head_ref)
    (project / 'README.md').write_text('# Test Project\n\nFeature change\n', encoding='utf-8')
    _pr_git(project, 'add', 'README.md')
    _pr_git(project, 'commit', '-m', 'feature')
    _pr_git(project, 'push', '-u', 'origin', head_ref)
    integrator = tmp_path / 'integrator'
    clone_result = subprocess.run(['git', 'clone', str(remote), str(integrator)], check=False, text=True, capture_output=True)
    assert clone_result.returncode == 0, clone_result.stdout + clone_result.stderr
    _pr_git(integrator, 'config', 'user.email', 'test@example.com')
    _pr_git(integrator, 'config', 'user.name', 'Test User')
    _pr_git(integrator, 'checkout', '-B', base_ref, f'origin/{base_ref}')
    _pr_git(integrator, 'merge', '--ff-only', f'origin/{head_ref}')
    _pr_git(integrator, 'push', 'origin', base_ref)
    _pr_git(project, 'checkout', head_ref)
    return (project, remote)

def _pr_init_complete_project(tmp_path: Path, *, review_mode: str='github', merge_strategy: str='merge', evidence_path: str | None=None) -> tuple[Path, Path]:
    key = f"complete-{review_mode}-{merge_strategy}-{evidence_path or 'default'}".replace(os.sep, '_').replace(':', '_')
    return _pr_ensure_project_remote_template(key, tmp_path, lambda template_dir: _pr__create_complete_project(template_dir, review_mode=review_mode, merge_strategy=merge_strategy, evidence_path=evidence_path))

def _pr__create_complete_project(tmp_path: Path, *, review_mode: str='github', merge_strategy: str='merge', evidence_path: str | None=None) -> tuple[Path, Path]:
    remote = tmp_path / 'remote.git'
    remote_init = subprocess.run(['git', 'init', '--bare', str(remote)], check=False, text=True, capture_output=True)
    assert remote_init.returncode == 0, remote_init.stdout + remote_init.stderr
    project = tmp_path / 'project'
    assert _pr_init_repo(project) == 'main'
    _pr_configure_complete(project, review_mode=review_mode, merge_strategy=merge_strategy, evidence_path=evidence_path)
    _pr_git(project, 'add', '.pr-flow')
    _pr_git(project, 'commit', '-m', 'configure pr flow')
    _pr_git(project, 'remote', 'add', 'origin', str(remote))
    _pr_git(project, 'push', '-u', 'origin', 'main')
    _pr_git(project, 'checkout', '-b', 'feature/example')
    (project / 'README.md').write_text('# Test Project\n\nFeature change\n', encoding='utf-8')
    _pr_git(project, 'add', 'README.md')
    _pr_git(project, 'commit', '-m', 'feature')
    _pr_git(project, 'push', '-u', 'origin', 'feature/example')
    integrator = tmp_path / 'integrator'
    clone_result = subprocess.run(['git', 'clone', str(remote), str(integrator)], check=False, text=True, capture_output=True)
    assert clone_result.returncode == 0, clone_result.stdout + clone_result.stderr
    _pr_git(integrator, 'config', 'user.email', 'test@example.com')
    _pr_git(integrator, 'config', 'user.name', 'Test User')
    _pr_git(integrator, 'checkout', '-B', 'main', 'origin/main')
    _pr_git(integrator, 'merge', '--ff-only', 'origin/feature/example')
    _pr_git(integrator, 'push', 'origin', 'main')
    _pr_git(project, 'checkout', 'feature/example')
    return (project, remote)

def _pr_passing_pr_view_json(project: Path, *, review_decision: str='APPROVED') -> str:
    return _pr_cases().pr_view_json(checks=[{'name': 'ci', 'status': 'COMPLETED', 'conclusion': 'SUCCESS'}], review_decision=review_decision, head_oid=_pr_git(project, 'rev-parse', 'HEAD'))

def _pr_captured_body_files(fake_bin: Path) -> list[dict[str, str]]:
    return json.loads((fake_bin / 'body_files.json').read_text(encoding='utf-8'))

def _pr_configure_complete(project: Path, *, review_mode: str, merge_strategy: str='merge', evidence_path: str | None=None) -> None:
    _pr_cases().write_confirmed_pr_flow_config(project)
    config_path = project / '.pr-flow' / 'config.yaml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    config['defaults']['wait'] = {'timeoutSeconds': 0, 'pollSeconds': 0}
    config['defaults']['mergeStrategy'] = merge_strategy
    config['defaults']['reviewGate'] = {'mode': review_mode}
    if evidence_path is not None:
        config['defaults']['reviewGate']['evidencePath'] = evidence_path
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')

def _pr_configure_hotfix(project: Path, *, target: str='main', allow_hotfix: bool=True, verify_command: str='git rev-parse HEAD') -> None:
    _pr_cases().write_confirmed_pr_flow_config(project)
    config_path = project / '.pr-flow' / 'config.yaml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    config.setdefault('authorization', {})
    config['authorization']['phraseHashAlgorithm'] = 'md5'
    config['authorization']['phraseHash'] = hashlib.md5(_pr_cases().HOTFIX_PHRASE.encode('utf-8')).hexdigest()
    config['defaults']['remote'] = 'origin'
    config['defaults']['hotfix'] = {'verifyCommand': verify_command}
    config.setdefault('branches', {}).setdefault(target, {})
    config['branches'][target]['allowHotfixPush'] = allow_hotfix
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')

def _pr_init_hotfix_project(tmp_path: Path, *, allow_hotfix: bool=True, verify_command: str='git rev-parse HEAD') -> tuple[Path, Path, str]:
    key = f'hotfix-{allow_hotfix}-{verify_command}'.replace(os.sep, '_').replace(':', '_').replace(' ', '_')
    project, remote = _pr_ensure_project_remote_template(key, tmp_path, lambda template_dir: _pr__create_hotfix_project(template_dir, allow_hotfix=allow_hotfix, verify_command=verify_command))
    before_commit = _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
    return (project, remote, before_commit)

def _pr__create_hotfix_project(tmp_path: Path, *, allow_hotfix: bool=True, verify_command: str='git rev-parse HEAD') -> tuple[Path, Path, str]:
    remote = tmp_path / 'remote.git'
    remote_init = subprocess.run(['git', 'init', '--bare', str(remote)], check=False, text=True, capture_output=True)
    assert remote_init.returncode == 0, remote_init.stdout + remote_init.stderr
    project = tmp_path / 'project'
    assert _pr_init_repo(project) == 'main'
    _pr_configure_hotfix(project, allow_hotfix=allow_hotfix, verify_command=verify_command)
    _pr_git(project, 'add', '.pr-flow')
    _pr_git(project, 'commit', '-m', 'configure pr flow')
    _pr_git(project, 'remote', 'add', 'origin', str(remote))
    _pr_git(project, 'push', '-u', 'origin', 'main')
    before_commit = _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
    _pr_git(project, 'checkout', '-b', 'hotfix/example', 'origin/main')
    (project / 'README.md').write_text('# Test Project\n\nHotfix change\n', encoding='utf-8')
    _pr_git(project, 'add', 'README.md')
    _pr_git(project, 'commit', '-m', 'hotfix')
    return (project, remote, before_commit)

def _pr_write_toolchain_cli(bin_dir: Path, reports: dict[str, dict[str, object]], *, cwd_log: Path | None=None) -> None:
    bin_dir.mkdir(exist_ok=True)
    for command, report in reports.items():
        script = bin_dir / f'{command}.py'
        lines = ['import json', 'from pathlib import Path']
        if cwd_log is not None:
            lines.extend([f"with Path({str(cwd_log)!r}).open('a', encoding='utf-8') as handle:", "    handle.write(str(Path.cwd()) + '\\n')"])
        lines.extend([f'reports = {report!r}', 'reports = reports if isinstance(reports, list) else [reports]', "state = Path(__file__).with_suffix('.count')", "index = int(state.read_text() if state.exists() else '0')", 'state.write_text(str(index + 1))', 'print(json.dumps(reports[min(index, len(reports) - 1)]))', ''])
        script.write_text('\n'.join(lines), encoding='utf-8')
        if os.name == 'nt':
            (bin_dir / f'{command}.cmd').write_text(f'@echo off\n"{sys.executable}" "%~dp0{command}.py" %*\n', encoding='utf-8')
        else:
            launcher = bin_dir / command
            launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/{command}.py" "$@"\n', encoding='utf-8')
            launcher.chmod(493)

def _pr_run_public_pr_flow(bin_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ | {'PATH': str(bin_dir) + os.pathsep + os.environ.get('PATH', '')}
    return subprocess.run([sys.executable, str(_pr_cases().SCRIPT), *args], check=False, text=True, capture_output=True, env=env)

def _pr_initialized_toolchain_project(tmp_path: Path, bin_dir: Path) -> Path:
    project = tmp_path / 'project'
    project.mkdir()
    for args in (['init'], ['config', 'user.email', 'test@example.invalid'], ['config', 'user.name', 'Test']):
        assert subprocess.run(['git', *args], cwd=project, check=False).returncode == 0
    config = tmp_path / 'config.yaml'
    config.write_text(yaml.safe_dump(_pr_cases().default_pr_flow_config_for_test(), sort_keys=False), encoding='utf-8')
    assert _pr_run_public_pr_flow(bin_dir, 'init', '--project', str(project), '--config', str(config)).returncode == 0
    assert subprocess.run(['git', 'add', '.'], cwd=project, check=False).returncode == 0
    assert subprocess.run(['git', 'commit', '-m', 'baseline'], cwd=project, check=False).returncode == 0
    return project

def _pr_sync_through_public_complete(bin_dir: Path, project: Path) -> subprocess.CompletedProcess[str]:
    return _pr_run_public_pr_flow(bin_dir, 'complete', '--project', str(project), '--summary', 's', '--scope', 's')

def _pr_dev_toolchain_reports(project: Path, *, worktree_match: bool, complete_identity: bool=True) -> dict[str, dict[str, object]]:
    source_worktree = project if worktree_match else project.parent / 'tool-source'
    binding = {'sourceWorktree': str(source_worktree), 'sourceCommit': 'a' * 40, 'targetWorktree': str(project), 'targetCommit': 'b' * 40, 'worktreeMatch': worktree_match}
    reports: dict[str, dict[str, object]] = {}
    for key, (_, package_name, package_directory) in _pr_cases().load_pr_flow_module().TOOLCHAIN_TOOLS.items():
        toolchain: dict[str, object] = {'mode': 'dev', 'packageName': package_name}
        if complete_identity:
            toolchain.update({'sourceRepository': 'https://github.com/liuli195/my-agent-skills', 'sourceCommit': 'a' * 40, 'packageDirectory': package_directory, 'implementationIdentity': 'sha256:' + '0' * 64})
        reports[key] = {'toolchain': toolchain, 'binding': binding}
    return reports

def _pr_run_cleanup_with_real_git(project: Path, monkeypatch, *, remove_worktree: bool=False, pr_stdout: str | None=None) -> subprocess.CompletedProcess[str]:
    from tests.support.command_stubs import CommandStub
    from tests.support.pr_flow_invocation import invoke_pr_flow
    module = _pr_cases().load_pr_flow_module()
    gh_stub = CommandStub()
    gh_stub.add(['pr', 'view', '12', '--json', 'number,state,headRefName,baseRefName,headRepositoryOwner'], stdout=pr_stdout or _pr_cases().cleanup_pr_view_json())
    monkeypatch.setattr(module, 'gh', gh_stub)
    args = ['cleanup', '--project', str(project), '--pr', '12']
    if remove_worktree:
        args.append('--remove-worktree')
    return invoke_pr_flow(args, module=module)

class TestPrFlow:

    @pytest.fixture(autouse=True)
    def _toolchain_identities(self, monkeypatch):
        global _PR_TEMPLATE_ROOT, _PR_TEMPLATE_CACHE_KEY
        cases = _pr_cases()
        _PR_TEMPLATE_CACHE_KEY = _pr_template_cache_key(Path(__file__), Path(cases.__file__), cases.SCRIPT)
        _PR_TEMPLATE_ROOT = Path(tempfile.gettempdir()) / f'pr-flow-test-templates-{_PR_TEMPLATE_CACHE_KEY}'
        monkeypatch.setattr(cases.load_pr_flow_module(), 'toolchain_identities', lambda _project: {'myspec': {'mode': 'release', 'packageName': '@liuli195/myspec', 'packageVersion': cases.MYSPEC_VERSION}, 'build-and-verify': {'mode': 'release', 'packageName': '@liuli195/build-and-verify', 'packageVersion': cases.BUILD_AND_VERIFY_VERSION}})

    def test_write_status_keeps_compatibility_file_and_branch_run(self, tmp_path: Path) -> None:
        module = _pr_cases().load_pr_flow_module()
        project = tmp_path / 'project'
        _pr_init_repo(project)
        module.write_status(project, 'complete', 'ready', {'sourceBranch': 'feature/one'})
        latest = json.loads((project / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        runs = list((project / '.pr-flow/runs').glob('*.json'))
        assert len(runs) == 1
        assert json.loads(runs[0].read_text(encoding='utf-8')) == latest
        assert latest['details']['sourceBranch'] == 'feature/one'
        assert Path(latest['details']['worktreePath']) == project.resolve()
        assert latest['details']['commonGitDir']

    def test_competing_mutation_reports_lock_without_rewriting_status(self, tmp_path: Path, capsys) -> None:
        module = _pr_cases().load_pr_flow_module()
        project = tmp_path / 'project'
        _pr_init_repo(project)
        module.write_status(project, 'complete', 'ready', {'sourceBranch': 'feature/one'})
        before = (project / '.pr-flow/last-status.json').read_bytes()
        with module.operation_lock(project, 'complete', argparse.Namespace(project=project)):
            result = module.main(['cleanup', '--project', str(project), '--pr', '12'])
        assert result == 1
        assert 'flow_locked' in capsys.readouterr().out
        assert (project / '.pr-flow/last-status.json').read_bytes() == before

    def test_diagnose_reports_active_lock_without_writing_status(self, tmp_path: Path, capsys) -> None:
        module = _pr_cases().load_pr_flow_module()
        project = tmp_path / 'project'
        _pr_init_repo(project)
        with module.operation_lock(project, 'complete', argparse.Namespace(project=project)):
            assert module.main(['diagnose', '--project', str(project)]) == 1
        output = capsys.readouterr().out
        assert 'flow_locked' in output
        assert 'actor' in output
        assert 'nextCommand' in output
        assert not (project / '.pr-flow/last-status.json').exists()

    def test_linked_worktrees_use_independent_process_locks_and_status(self, tmp_path: Path) -> None:
        project = tmp_path / 'first'
        assert _pr_init_repo(project) == 'main'
        _pr_cases().write_minimal_pr_flow_config(project)
        _pr_git(project, 'add', '.pr-flow')
        _pr_git(project, 'commit', '-m', 'configure pr flow')
        _pr_git(project, 'checkout', '-b', 'feature/one')
        other = tmp_path / 'second'
        _pr_git(project, 'worktree', 'add', '-b', 'feature/two', str(other), 'main')
        ready = tmp_path / 'ready'
        release = tmp_path / 'release'
        holder_code = '\nimport argparse\nimport importlib.util\nimport pathlib\nimport sys\nimport time\nspec = importlib.util.spec_from_file_location("pr_flow_holder", sys.argv[1])\nmodule = importlib.util.module_from_spec(spec)\nsys.modules[spec.name] = module\nspec.loader.exec_module(module)\nproject = pathlib.Path(sys.argv[2])\nwith module.operation_lock(project, "complete", argparse.Namespace(project=project)):\n    pathlib.Path(sys.argv[3]).write_text("ready", encoding="utf-8")\n    while not pathlib.Path(sys.argv[4]).exists():\n        time.sleep(0.02)\n'
        holder = subprocess.Popen([sys.executable, '-c', holder_code, str(_pr_cases().SCRIPT), str(project), str(ready), str(release)], cwd=_pr_cases().REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert ready.exists(), holder.communicate(timeout=1)
            independent = subprocess.run([sys.executable, str(_pr_cases().SCRIPT), 'diagnose', '--project', str(other)], cwd=_pr_cases().REPO_ROOT, check=False, text=True, capture_output=True)
            competing = subprocess.run([sys.executable, str(_pr_cases().SCRIPT), 'cleanup', '--project', str(project), '--pr', '12'], cwd=_pr_cases().REPO_ROOT, check=False, text=True, capture_output=True)
            assert 'flow_locked' not in independent.stdout
            assert (other / '.pr-flow/last-status.json').exists()
            assert 'flow_locked' in competing.stdout
            assert not (project / '.pr-flow/last-status.json').exists()
        finally:
            release.touch()
            holder.communicate(timeout=10)

    def test_linked_worktrees_complete_independently_through_cli(self, tmp_path: Path) -> None:
        first, _remote = _pr_init_complete_project(tmp_path)
        _pr_git(first, 'fetch', 'origin', 'main')
        _pr_git(first, 'checkout', '-B', 'main', 'origin/main')
        base_oid = _pr_git(first, 'rev-parse', 'HEAD')
        _pr_git(first, 'checkout', '-b', 'feature/one')
        _pr_git(first, 'push', '-u', 'origin', 'feature/one')
        first_oid = _pr_git(first, 'rev-parse', 'HEAD')
        second = tmp_path / 'second'
        _pr_git(first, 'worktree', 'add', '-b', 'feature/two', str(second), 'main')
        _pr_git(second, 'push', '-u', 'origin', 'feature/two')
        second_oid = _pr_git(second, 'rev-parse', 'HEAD')

        def responses(branch: str, head_oid: str, number: int) -> list[dict[str, object]]:
            pr = json.loads(_pr_cases().pr_view_json(checks=[{'name': 'ci', 'status': 'COMPLETED', 'conclusion': 'SUCCESS'}], review_decision='APPROVED', head_oid=head_oid, base_oid=base_oid))
            pr.update({'number': number, 'headRefName': branch})
            pr_text = json.dumps(pr) + '\n'
            cleanup = json.dumps({'number': number, 'state': 'MERGED', 'headRefName': branch, 'baseRefName': 'main', 'headRepositoryOwner': {'login': 'test-owner'}}) + '\n'
            checks = {'stdout': json.dumps([{'bucket': 'pass', 'name': 'ci', 'state': 'SUCCESS'}])}
            return [{'stdout': pr_text}, {'stdout': pr_text}, checks, {'stdout': pr_text}, checks, {'stdout': pr_text}, {}, {'stdout': cleanup}]
        first_bin, _ = _pr_write_fake_gh_sequence(tmp_path / 'first-bin', responses('feature/one', first_oid, 11))
        second_bin, _ = _pr_write_fake_gh_sequence(tmp_path / 'second-bin', responses('feature/two', second_oid, 12))

        def command(project: Path, fake_bin: Path) -> tuple[list[str], dict[str, str]]:
            env = os.environ.copy()
            env['PATH'] = str(fake_bin) + os.pathsep + env.get('PATH', '')
            return ([sys.executable, str(_pr_cases().SCRIPT), 'complete', '--project', str(project), '--summary', 'parallel worktree', '--scope', 'test'], env)
        first_command, first_env = command(first, first_bin)
        second_command, second_env = command(second, second_bin)
        first_process = subprocess.Popen(first_command, cwd=_pr_cases().REPO_ROOT, env=first_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        second_process = subprocess.Popen(second_command, cwd=_pr_cases().REPO_ROOT, env=second_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        first_stdout, first_stderr = first_process.communicate(timeout=30)
        second_stdout, second_stderr = second_process.communicate(timeout=30)
        assert first_process.returncode == 0, first_stdout + first_stderr
        assert second_process.returncode == 0, second_stdout + second_stderr
        assert 'cleanup_complete' in first_stdout
        assert 'cleanup_complete' in second_stdout
        assert {_pr_git(first, 'branch', '--show-current'), _pr_git(second, 'branch', '--show-current')} == {'', 'main'}
        assert _pr_git(first, 'rev-parse', 'HEAD') == base_oid
        assert _pr_git(second, 'rev-parse', 'HEAD') == base_oid

    def test_pr_flow_installed_skill_command_runs_from_external_project(self, tmp_path: Path) -> None:
        installed = tmp_path / 'installed cache' / 'pr-flow'
        shutil.copytree(_package_cases().PLUGIN_ROOT, installed)
        target = tmp_path / 'external project'
        target.mkdir()
        skill_path = installed / 'skills' / 'pr-flow' / 'SKILL.md'
        skill_text = skill_path.read_text(encoding='utf-8')
        command_text = skill_text.split('```bash\n', 1)[1].split('\n```', 1)[0]
        command = shlex.split(command_text.replace('<本技能安装目录>', str(skill_path.parent)).replace('<目标项目目录>', str(target)))
        command[0] = sys.executable
        result = subprocess.run(command, cwd=target, text=True, capture_output=True, check=False)
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'EXCEPTION_REQUIRED' in result.stdout and 'missing_config' in result.stdout
        assert (target / '.pr-flow' / 'last-status.json').is_file()
        assert not (installed / '.pr-flow').exists()
        assert not (target / 'plugins' / 'pr-flow').exists()
        for name, subcommand in _package_cases().ENTRYPOINT_COMMANDS.items():
            if name == 'pr-flow-init':
                continue
            text = (installed / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8')
            resource = 'scripts/pr_flow.py' if name == 'pr-flow' else '../pr-flow/scripts/pr_flow.py'
            assert f'python "<本技能安装目录>/{resource}" {subcommand}' in text
            assert '--project "<目标项目目录>"' in text
            assert '本次加载的技能安装目录' in text and '停止并报告' in text

    def test_pr_flow_template_cache_key_includes_script_contents(self) -> None:
        assert _PR_TEMPLATE_CACHE_KEY == _pr_template_cache_key(Path(__file__), Path(_pr_cases().__file__), _pr_cases().SCRIPT)

    def test_remove_worktree_uses_native_non_forced_remove(self, tmp_path: Path, monkeypatch) -> None:
        from tests.support.command_stubs import CommandStub
        module = _pr_cases().load_pr_flow_module()
        main = tmp_path / 'main'
        target = tmp_path / 'feature one'
        main.mkdir()
        target.mkdir()
        before = f'worktree {main}\x00HEAD aaaa\x00branch refs/heads/main\x00\x00worktree {target}\x00HEAD bbbb\x00detached\x00\x00'
        after = f'worktree {main}\x00HEAD aaaa\x00branch refs/heads/main\x00\x00'
        git_stub = CommandStub(consume=True)
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=before)
        git_stub.add(['status', '--short'], stdout='')
        remove_args = [] if os.name != 'nt' else ['-c', 'core.longpaths=true']
        remove_args += ['worktree', 'remove', str(target.resolve())]
        git_stub.add(remove_args)
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=after)
        monkeypatch.setattr(module, 'git', git_stub)
        module.remove_worktree(target, target)
        assert tuple(remove_args) in git_stub.calls
        assert not any(('--force' in call for call in git_stub.calls))

    def test_remove_worktree_deletes_physical_residue_after_registration_removal(self, tmp_path: Path, monkeypatch) -> None:
        from tests.support.command_stubs import CommandStub
        module = _pr_cases().load_pr_flow_module()
        main = tmp_path / 'main'
        target = tmp_path / 'feature one'
        main.mkdir()
        target.mkdir()
        (target / 'residue.txt').write_text('orphaned\n', encoding='utf-8')
        before = f'worktree {main}\x00HEAD aaaa\x00branch refs/heads/main\x00\x00worktree {target}\x00HEAD bbbb\x00detached\x00\x00'
        after = f'worktree {main}\x00HEAD aaaa\x00branch refs/heads/main\x00\x00'
        git_stub = CommandStub(consume=True)
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=before)
        git_stub.add(['status', '--short'], stdout='')
        remove_args = [] if os.name != 'nt' else ['-c', 'core.longpaths=true']
        remove_args += ['worktree', 'remove', str(target.resolve())]
        git_stub.add(remove_args)
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=after)
        monkeypatch.setattr(module, 'git', git_stub)
        monkeypatch.setattr(module, 'find_orca_worktree_id', lambda *_args: None)
        module.remove_worktree(target, target)
        assert not target.exists()

    def test_remove_worktree_does_not_delete_target_while_registration_remains(self, tmp_path: Path, monkeypatch) -> None:
        from tests.support.command_stubs import CommandStub
        module = _pr_cases().load_pr_flow_module()
        main = tmp_path / 'main'
        target = tmp_path / 'feature one'
        main.mkdir()
        target.mkdir()
        (target / 'residue.txt').write_text('keep\n', encoding='utf-8')
        worktrees = f'worktree {main}\x00HEAD aaaa\x00branch refs/heads/main\x00\x00worktree {target}\x00HEAD bbbb\x00detached\x00\x00'
        git_stub = CommandStub(consume=True)
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=worktrees)
        git_stub.add(['status', '--short'], stdout='')
        remove_args = [] if os.name != 'nt' else ['-c', 'core.longpaths=true']
        remove_args += ['worktree', 'remove', str(target.resolve())]
        git_stub.add(remove_args)
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=worktrees)
        monkeypatch.setattr(module, 'git', git_stub)
        monkeypatch.setattr(module, 'find_orca_worktree_id', lambda *_args: None)
        monkeypatch.setattr(module.shutil, 'rmtree', lambda *_args: pytest.fail('physical deletion must wait'))
        with pytest.raises(module.PrFlowError, match='git_worktree_remove_failed'):
            module.remove_worktree(target, target)
        assert target.exists()
        assert (target / 'residue.txt').exists()

    @pytest.mark.skipif(os.name != 'nt', reason='Windows long-path behavior')
    def test_cleanup_handles_windows_long_paths_through_cli(self, tmp_path: Path, monkeypatch) -> None:
        controller = tmp_path / 'controller'
        remote = tmp_path / 'remote.git'
        target = tmp_path / 'target'
        _pr_init_repo(controller)
        _pr_cases().write_confirmed_pr_flow_config(controller)
        (controller / '.gitignore').write_text('.local/\n', encoding='utf-8')
        _pr_git(controller, 'add', '.gitignore', '.pr-flow')
        _pr_git(controller, 'commit', '-m', 'configure cleanup')
        bare = subprocess.run(['git', 'init', '--bare', str(remote)], check=False, text=True, capture_output=True)
        assert bare.returncode == 0, bare.stdout + bare.stderr
        _pr_git(controller, 'remote', 'add', 'origin', str(remote))
        _pr_git(controller, 'push', '-u', 'origin', 'main')
        _pr_git(controller, 'checkout', '-b', 'feature/example')
        (controller / 'README.md').write_text('feature\n', encoding='utf-8')
        _pr_git(controller, 'add', 'README.md')
        _pr_git(controller, 'commit', '-m', 'feature')
        _pr_git(controller, 'push', '-u', 'origin', 'feature/example')
        _pr_git(controller, 'checkout', 'main')
        _pr_git(controller, 'merge', '--ff-only', 'feature/example')
        _pr_git(controller, 'push', 'origin', 'main')
        _pr_git(controller, 'worktree', 'add', str(target), 'feature/example')
        deep = target / '.local' / 'spec-work'
        for _ in range(20):
            deep /= 'segment-' + 'x' * 12
        deep.mkdir(parents=True)
        artifact = deep / ('artifact-' + 'y' * 30 + '.json')
        artifact.write_text('{}\n', encoding='utf-8')
        assert len(str(artifact)) > 260
        remote_base = _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
        main_before = _pr_git(controller, 'rev-parse', 'HEAD')
        assert main_before == remote_base
        module = _pr_cases().load_pr_flow_module()
        monkeypatch.setattr(module, 'find_orca_worktree_id', lambda *_: None)
        result = _pr_run_cleanup_with_real_git(target, monkeypatch, remove_worktree=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'status: cleanup_complete' in result.stdout
        assert not target.exists()
        assert 'target' not in _pr_git(controller, 'worktree', 'list', '--porcelain')
        assert _pr_git(controller, 'branch', '--show-current') == 'main'
        assert _pr_git(controller, 'rev-parse', 'HEAD') == main_before
        core_longpaths = subprocess.run(['git', 'config', '--local', '--get', 'core.longpaths'], cwd=controller, check=False, text=True, capture_output=True)
        assert core_longpaths.returncode == 1
        assert not core_longpaths.stdout.strip()

    @pytest.mark.skipif(os.name != 'nt', reason='Windows junction behavior')
    def test_cleanup_removes_junction_residue_without_shared_targets(self, tmp_path: Path, monkeypatch) -> None:
        controller = tmp_path / 'controller'
        remote = tmp_path / 'remote.git'
        target = tmp_path / 'target'
        _pr_init_repo(controller)
        _pr_cases().write_confirmed_pr_flow_config(controller)
        (controller / '.gitignore').write_text('node_modules/\n.venv/\n', encoding='utf-8')
        _pr_git(controller, 'add', '.gitignore', '.pr-flow')
        _pr_git(controller, 'commit', '-m', 'configure cleanup')
        bare = subprocess.run(['git', 'init', '--bare', str(remote)], check=False, text=True, capture_output=True)
        assert bare.returncode == 0, bare.stdout + bare.stderr
        _pr_git(controller, 'remote', 'add', 'origin', str(remote))
        _pr_git(controller, 'push', '-u', 'origin', 'main')
        _pr_git(controller, 'checkout', '-b', 'feature/example')
        (controller / 'README.md').write_text('feature\n', encoding='utf-8')
        _pr_git(controller, 'add', 'README.md')
        _pr_git(controller, 'commit', '-m', 'feature')
        _pr_git(controller, 'push', '-u', 'origin', 'feature/example')
        _pr_git(controller, 'checkout', 'main')
        _pr_git(controller, 'merge', '--ff-only', 'feature/example')
        _pr_git(controller, 'push', 'origin', 'main')
        _pr_git(controller, 'worktree', 'add', str(target), 'feature/example')
        shared_node_modules = controller / 'node_modules'
        shared_venv = controller / '.venv'
        shared_node_modules.mkdir()
        shared_venv.mkdir()
        node_sentinel = shared_node_modules / 'shared-sentinel.txt'
        venv_sentinel = shared_venv / 'shared-sentinel.txt'
        node_sentinel.write_text('keep\n', encoding='utf-8')
        venv_sentinel.write_text('keep\n', encoding='utf-8')
        powershell = shutil.which('powershell')
        if not powershell:
            pytest.skip('PowerShell is required to create junctions')
        for link, shared in ((target / 'node_modules', shared_node_modules), (target / '.venv', shared_venv)):
            junction = subprocess.run([powershell, '-NoProfile', '-Command', f'New-Item -ItemType Junction -Path "{link}" -Target "{shared}"'], check=False, capture_output=True)
            assert junction.returncode == 0, junction.stdout.decode(errors='replace') + junction.stderr.decode(errors='replace')
        module = _pr_cases().load_pr_flow_module()
        monkeypatch.setattr(module, 'find_orca_worktree_id', lambda *_args: None)
        result = _pr_run_cleanup_with_real_git(target, monkeypatch, remove_worktree=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'status: cleanup_complete' in result.stdout
        assert not target.exists()
        assert 'target' not in _pr_git(controller, 'worktree', 'list', '--porcelain')
        assert node_sentinel.read_text(encoding='utf-8') == 'keep\n'
        assert venv_sentinel.read_text(encoding='utf-8') == 'keep\n'

    def test_remove_worktree_prefers_matched_orca_worktree(self, tmp_path: Path, monkeypatch) -> None:
        from tests.support.command_stubs import CommandStub
        module = _pr_cases().load_pr_flow_module()
        main = tmp_path / 'main'
        target = tmp_path / 'feature one'
        main.mkdir()
        target.mkdir()
        (target / 'residue.txt').write_text('orphaned\n', encoding='utf-8')
        shared_sentinels: dict[str, Path] = {}
        if os.name == 'nt':
            powershell = shutil.which('powershell')
            if not powershell:
                pytest.skip('PowerShell is required to create junctions')
            for name in ('.venv', 'node_modules'):
                shared = main / name
                shared.mkdir()
                sentinel = shared / 'shared-sentinel.txt'
                sentinel.write_text('keep\n', encoding='utf-8')
                shared_sentinels[name] = sentinel
                junction = subprocess.run([powershell, '-NoProfile', '-Command', f'New-Item -ItemType Junction -Path "{target / name}" -Target "{shared}"'], check=False, capture_output=True)
                assert junction.returncode == 0, junction.stdout.decode(errors='replace') + junction.stderr.decode(errors='replace')
        before, after = _pr_cases().worktree_removal_records(main, target)
        git_stub = CommandStub(consume=True)
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=before)
        git_stub.add(['status', '--short'], stdout='')
        git_stub.add(['worktree', 'remove', str(target.resolve())])
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=after)
        orca_stub = CommandStub(consume=True)
        orca_path = str(target).replace('\\', '/')
        if os.name == 'nt':
            orca_path = orca_path.upper()
        orca_payload = {'result': {'worktrees': [{'path': orca_path, 'worktreeId': 'repo::target'}]}}
        orca_stub.add(['worktree', 'ps', '--json'], stdout=json.dumps(orca_payload))
        orca_stub.add(['worktree', 'rm', '--worktree', 'id:repo::target', '--json'])
        monkeypatch.setattr(module, 'git', git_stub)
        monkeypatch.setattr(module, 'orca', orca_stub, raising=False)
        module.remove_worktree(target, target)
        assert ('worktree', 'rm', '--worktree', 'id:repo::target', '--json') in orca_stub.calls
        assert not any((call[:2] == ('worktree', 'remove') for call in git_stub.calls))
        assert not any(('--force' in call for call in orca_stub.calls))
        assert not target.exists()
        for sentinel in shared_sentinels.values():
            assert sentinel.read_text(encoding='utf-8') == 'keep\n'

    @pytest.mark.parametrize(('returncode', 'stdout', 'stderr'), [(0, '{"result":{"worktrees":[]}}', ''), (127, '', 'orca not found'), (0, 'not-json', '')])
    def test_remove_worktree_falls_back_to_git_when_orca_is_unavailable_or_unmatched(self, tmp_path: Path, monkeypatch, returncode: int, stdout: str, stderr: str) -> None:
        from tests.support.command_stubs import CommandStub
        module = _pr_cases().load_pr_flow_module()
        main = tmp_path / 'main'
        target = tmp_path / 'feature one'
        main.mkdir()
        target.mkdir()
        before, after = _pr_cases().worktree_removal_records(main, target)
        git_stub = CommandStub(consume=True)
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=before)
        git_stub.add(['status', '--short'], stdout='')
        remove_args = [] if os.name != 'nt' else ['-c', 'core.longpaths=true']
        remove_args += ['worktree', 'remove', str(target.resolve())]
        git_stub.add(remove_args)
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=after)
        orca_stub = CommandStub(consume=True)
        orca_stub.add(['worktree', 'ps', '--json'], returncode=returncode, stdout=stdout, stderr=stderr)
        monkeypatch.setattr(module, 'git', git_stub)
        monkeypatch.setattr(module, 'orca', orca_stub, raising=False)
        module.remove_worktree(target, target)
        assert tuple(remove_args) in git_stub.calls
        assert not any((call[:2] == ('worktree', 'rm') for call in orca_stub.calls))

    def test_remove_worktree_stops_when_matched_orca_removal_fails(self, tmp_path: Path, monkeypatch) -> None:
        from tests.support.command_stubs import CommandStub
        module = _pr_cases().load_pr_flow_module()
        main = tmp_path / 'main'
        target = tmp_path / 'feature one'
        main.mkdir()
        target.mkdir()
        before, after = _pr_cases().worktree_removal_records(main, target)
        git_stub = CommandStub(consume=True)
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=before)
        git_stub.add(['status', '--short'], stdout='')
        git_stub.add(['worktree', 'remove', str(target.resolve())])
        git_stub.add(['worktree', 'list', '--porcelain', '-z'], stdout=after)
        orca_stub = CommandStub(consume=True)
        orca_stub.add(['worktree', 'ps', '--json'], stdout=_pr_cases().orca_worktree_ps_json(target, 'repo::target'))
        orca_stub.add(['worktree', 'rm', '--worktree', 'id:repo::target', '--json'], stderr='permission denied', returncode=1)
        monkeypatch.setattr(module, 'git', git_stub)
        monkeypatch.setattr(module, 'orca', orca_stub, raising=False)
        with pytest.raises(module.PrFlowError, match='orca_worktree_remove_failed') as error:
            module.remove_worktree(target, target)
        assert error.value.details['stderr'] == 'permission denied'
        assert not any((call[:2] == ('worktree', 'remove') for call in git_stub.calls))

    def test_project_template_recovers_stale_lock(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(sys.modules[__name__], '_pr_copy_project_remote_template', _pr_fake_copy_project_remote_template)
        template_name = f'stale-lock-{tmp_path.name}'
        lock_dir = _PR_TEMPLATE_ROOT / f'{template_name}.lock'
        lock_dir.mkdir(parents=True, exist_ok=True)
        stale_time = time.time() - _PR_TEMPLATE_LOCK_STALE_SECONDS - 1
        os.utime(lock_dir, (stale_time, stale_time))
        project, remote = _pr_ensure_project_remote_template(template_name, tmp_path, _pr_fake_project_remote_template)
        assert project.is_dir()
        assert remote.is_dir()
        assert not lock_dir.exists()

    def test_project_template_recreates_incomplete_template_after_stale_lock(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(sys.modules[__name__], '_pr_copy_project_remote_template', _pr_fake_copy_project_remote_template)
        template_name = f'incomplete-template-{os.getpid()}-{time.monotonic_ns()}'
        template_dir = _PR_TEMPLATE_ROOT / template_name
        lock_dir = _PR_TEMPLATE_ROOT / f'{template_name}.lock'
        template_dir.mkdir(parents=True)
        (template_dir / 'partial.txt').write_text('partial\n', encoding='utf-8')
        (template_dir / 'partial.txt').chmod(292)
        lock_dir.mkdir(parents=True, exist_ok=True)
        stale_time = time.time() - _PR_TEMPLATE_LOCK_STALE_SECONDS - 1
        os.utime(lock_dir, (stale_time, stale_time))
        project, remote = _pr_ensure_project_remote_template(template_name, tmp_path, _pr_fake_project_remote_template)
        assert project.is_dir()
        assert remote.is_dir()
        assert (template_dir / '.ready').is_file()
        assert not (template_dir / 'partial.txt').exists()
        assert not lock_dir.exists()

    def test_cleanup_returns_to_available_local_base_end_to_end(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        remote_base = _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
        assert _pr_git(project, 'rev-parse', 'main') != remote_base
        result = _pr_run_cleanup_with_real_git(project, monkeypatch)
        assert result.returncode == 0, result.stdout + result.stderr
        assert _pr_git(project, 'branch', '--show-current') == 'main'
        assert _pr_git(project, 'rev-parse', 'HEAD') == remote_base
        assert _pr_git(project, 'rev-parse', 'main') == remote_base
        status = json.loads((project / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        assert status['details']['currentBranch'] == 'main'
        assert status['details']['baseCheckout'] == {'status': 'checked_out'}

    def test_cleanup_retains_primary_worktree_on_arbitrary_base_branch(self, tmp_path: Path, monkeypatch) -> None:
        base_ref = 'trunk'
        head_ref = 'topic/317'
        project, remote = _pr_init_cleanup_project(tmp_path, base_ref=base_ref, head_ref=head_ref)
        remote_base = _pr_git_bare(remote, 'rev-parse', f'refs/heads/{base_ref}')
        with contextlib.chdir(project):
            result = _pr_run_cleanup_with_real_git(project, monkeypatch, remove_worktree=True, pr_stdout=_pr_cases().cleanup_pr_view_json(head_ref=head_ref, base_ref=base_ref))
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'status: cleanup_complete' in result.stdout
        assert project.is_dir()
        assert _pr_git(project, 'branch', '--show-current') == base_ref
        assert _pr_git(project, 'rev-parse', 'HEAD') == remote_base
        assert _pr_git(project, 'rev-parse', f'refs/heads/{base_ref}') == remote_base
        assert subprocess.run(['git', 'show-ref', '--verify', '--quiet', f'refs/heads/{head_ref}'], cwd=project, check=False).returncode == 1
        assert _pr_git_bare_result(remote, 'show-ref', '--verify', f'refs/heads/{head_ref}').returncode != 0
        worktrees = _pr_cases().load_pr_flow_module().parse_worktrees(_pr_git(project, 'worktree', 'list', '--porcelain', '-z'))
        assert Path(worktrees[0]['path']).resolve() == project.resolve()
        assert worktrees[0]['branch'] == f'refs/heads/{base_ref}'
        status = json.loads((project / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        assert status['details']['worktreeRetention'] == {'status': 'retained', 'reason': 'primary_worktree'}
        assert status['details']['currentBranch'] == base_ref
        assert 'nextCommand' not in status['details']

    def test_cleanup_stops_before_primary_checkout_when_active_cwd_would_disappear(self, tmp_path: Path, monkeypatch) -> None:
        base_ref = 'trunk'
        head_ref = 'topic/317'
        project, remote = _pr_init_cleanup_project(tmp_path, base_ref=base_ref, head_ref=head_ref)
        source_only = project / 'source-only' / 'nested'
        source_only.mkdir(parents=True)
        (source_only / 'sentinel.txt').write_text('source only\n', encoding='utf-8')
        _pr_git(project, 'add', 'source-only')
        _pr_git(project, 'commit', '-m', 'source-only directory')
        _pr_git(project, 'push', 'origin', head_ref)
        with contextlib.chdir(source_only):
            result = _pr_run_cleanup_with_real_git(project, monkeypatch, remove_worktree=True, pr_stdout=_pr_cases().cleanup_pr_view_json(head_ref=head_ref, base_ref=base_ref))
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'active_cwd_would_disappear' in result.stdout
        assert source_only.is_dir()
        assert _pr_git(project, 'branch', '--show-current') == head_ref
        assert _pr_git_bare_result(remote, 'show-ref', '--verify', f'refs/heads/{head_ref}').returncode == 0
        worktrees = _pr_cases().load_pr_flow_module().parse_worktrees(_pr_git(project, 'worktree', 'list', '--porcelain', '-z'))
        assert Path(worktrees[0]['path']).resolve() == project.resolve()
        assert worktrees[0]['branch'] == f'refs/heads/{head_ref}'

    def test_cleanup_stops_before_checkout_when_active_cwd_would_disappear_without_remove_worktree(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        source_only = project / 'source-only' / 'nested'
        source_only.mkdir(parents=True)
        (source_only / 'sentinel.txt').write_text('source only\n', encoding='utf-8')
        _pr_git(project, 'add', 'source-only')
        _pr_git(project, 'commit', '-m', 'source-only directory')
        source_head = _pr_git(project, 'rev-parse', 'HEAD')
        _pr_git(project, 'push', 'origin', 'feature/example')
        with contextlib.chdir(source_only):
            result = _pr_run_cleanup_with_real_git(project, monkeypatch)
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'active_cwd_would_disappear' in result.stdout
        assert source_only.is_dir()
        assert _pr_git(project, 'branch', '--show-current') == 'feature/example'
        assert _pr_git(project, 'rev-parse', 'HEAD') == source_head
        assert _pr_git_bare_result(remote, 'show-ref', '--verify', 'refs/heads/feature/example').returncode == 0
        status = json.loads((project / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        assert status['details']['reason'] == 'active_cwd_would_disappear'

    def test_cleanup_stops_primary_worktree_when_base_branch_is_occupied(self, tmp_path: Path, monkeypatch) -> None:
        base_ref = 'trunk'
        head_ref = 'topic/317'
        project, remote = _pr_init_cleanup_project(tmp_path, base_ref=base_ref, head_ref=head_ref)
        occupied = tmp_path / 'base-worktree'
        _pr_git(project, 'worktree', 'add', str(occupied), base_ref)
        before = (_pr_git(project, 'rev-parse', 'HEAD'), _pr_git(project, 'branch', '--show-current'), _pr_git(project, 'show-ref'))
        with contextlib.chdir(project):
            result = _pr_run_cleanup_with_real_git(project, monkeypatch, remove_worktree=True, pr_stdout=_pr_cases().cleanup_pr_view_json(head_ref=head_ref, base_ref=base_ref))
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'base_branch_checked_out' in result.stdout
        assert (_pr_git(project, 'rev-parse', 'HEAD'), _pr_git(project, 'branch', '--show-current'), _pr_git(project, 'show-ref')) == before
        assert _pr_git(occupied, 'branch', '--show-current') == base_ref
        assert _pr_git_bare_result(remote, 'show-ref', '--verify', f'refs/heads/{head_ref}').returncode == 0
        status = json.loads((project / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        assert status['details']['reason'] == 'base_branch_checked_out'
        assert Path(occupied).resolve() in [Path(path).resolve() for path in status['details']['occupiedWorktrees']]

    def test_cleanup_stops_primary_worktree_when_base_branch_is_occupied_without_remove_worktree(self, tmp_path: Path, monkeypatch) -> None:
        base_ref = 'trunk'
        head_ref = 'topic/317'
        project, remote = _pr_init_cleanup_project(tmp_path, base_ref=base_ref, head_ref=head_ref)
        occupied = tmp_path / 'base-worktree'
        _pr_git(project, 'worktree', 'add', str(occupied), base_ref)
        before = (_pr_git(project, 'rev-parse', 'HEAD'), _pr_git(project, 'branch', '--show-current'), _pr_git(project, 'show-ref'))
        with contextlib.chdir(project):
            result = _pr_run_cleanup_with_real_git(project, monkeypatch, pr_stdout=_pr_cases().cleanup_pr_view_json(head_ref=head_ref, base_ref=base_ref))
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'base_branch_checked_out' in result.stdout
        assert (_pr_git(project, 'rev-parse', 'HEAD'), _pr_git(project, 'branch', '--show-current'), _pr_git(project, 'show-ref')) == before
        assert _pr_git(occupied, 'branch', '--show-current') == base_ref
        assert _pr_git_bare_result(remote, 'show-ref', '--verify', f'refs/heads/{head_ref}').returncode == 0

    def test_cleanup_stops_before_occupied_base_merge_when_active_cwd_would_disappear(self, tmp_path: Path, monkeypatch) -> None:
        base_ref = 'trunk'
        head_ref = 'topic/317'
        project, remote = _pr_init_cleanup_project(tmp_path, base_ref=base_ref, head_ref=head_ref)
        _pr_git(project, 'checkout', base_ref)
        current_only = project / 'current-only' / 'nested'
        current_only.mkdir(parents=True)
        (current_only / 'sentinel.txt').write_text('current only\n', encoding='utf-8')
        _pr_git(project, 'add', 'current-only')
        _pr_git(project, 'commit', '-m', 'base-only directory')
        _pr_git(project, 'push', '--force', 'origin', base_ref)
        _pr_git(project, 'checkout', '-b', 'controller')
        occupied = tmp_path / 'base-worktree'
        _pr_git(project, 'worktree', 'add', str(occupied), base_ref)
        integrator = tmp_path / 'base-integrator'
        clone_result = subprocess.run(['git', 'clone', str(remote), str(integrator)], check=False, text=True, capture_output=True)
        assert clone_result.returncode == 0, clone_result.stdout + clone_result.stderr
        _pr_git(integrator, 'config', 'user.email', 'test@example.com')
        _pr_git(integrator, 'config', 'user.name', 'Test User')
        _pr_git(integrator, 'checkout', '-B', base_ref, f'origin/{base_ref}')
        shutil.rmtree(integrator / 'current-only')
        _pr_git(integrator, 'add', '-u', 'current-only')
        _pr_git(integrator, 'commit', '-m', 'remove base-only directory')
        _pr_git(integrator, 'push', 'origin', base_ref)
        _pr_git(project, 'checkout', head_ref)
        (project / '.gitignore').write_text('current-only/\n', encoding='utf-8')
        _pr_git(project, 'add', '.gitignore')
        _pr_git(project, 'commit', '-m', 'ignore current-only on head')
        _pr_git(project, 'push', 'origin', head_ref)
        _pr_git(project, 'checkout', 'controller')
        target = tmp_path / 'target'
        _pr_git(project, 'worktree', 'add', str(target), head_ref)
        target_ignored = subprocess.run(['git', 'check-ignore', '--quiet', '--', 'current-only/nested'], cwd=target, check=False)
        occupied_not_ignored = subprocess.run(['git', 'check-ignore', '--quiet', '--', 'current-only/nested'], cwd=occupied, check=False)
        assert target_ignored.returncode == 0
        assert occupied_not_ignored.returncode != 0
        active_cwd = occupied / 'current-only' / 'nested'
        assert active_cwd.is_dir()
        before_target = (_pr_git(target, 'rev-parse', 'HEAD'), _pr_git(target, 'branch', '--show-current'))
        before_occupied = (_pr_git(occupied, 'rev-parse', 'HEAD'), _pr_git(occupied, 'branch', '--show-current'))
        before_local_head = _pr_git(target, 'show-ref', '--verify', f'refs/heads/{head_ref}')
        before_remote_head = _pr_git_bare(remote, 'show-ref', '--verify', f'refs/heads/{head_ref}')
        with contextlib.chdir(active_cwd):
            result = _pr_run_cleanup_with_real_git(target, monkeypatch, pr_stdout=_pr_cases().cleanup_pr_view_json(head_ref=head_ref, base_ref=base_ref))
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'active_cwd_would_disappear' in result.stdout
        assert (_pr_git(target, 'rev-parse', 'HEAD'), _pr_git(target, 'branch', '--show-current')) == before_target
        assert (_pr_git(occupied, 'rev-parse', 'HEAD'), _pr_git(occupied, 'branch', '--show-current')) == before_occupied
        assert _pr_git(target, 'show-ref', '--verify', f'refs/heads/{head_ref}') == before_local_head
        assert _pr_git_bare(remote, 'show-ref', '--verify', f'refs/heads/{head_ref}') == before_remote_head
        status = json.loads((target / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        assert status['details']['reason'] == 'active_cwd_would_disappear'

    def test_cleanup_retains_active_worktree_detached_after_branch_cleanup(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        target = tmp_path / 'target'
        _pr_git(project, 'checkout', 'main')
        stale_base = _pr_git(project, 'rev-parse', 'HEAD')
        _pr_git(project, 'checkout', '-b', 'controller')
        other = tmp_path / 'base-worktree'
        _pr_git(project, 'worktree', 'add', str(other), 'main')
        _pr_git(project, 'worktree', 'add', str(target), 'feature/example')
        remote_base = _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
        assert stale_base != remote_base
        with contextlib.chdir(target):
            result = _pr_run_cleanup_with_real_git(target, monkeypatch, remove_worktree=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'status: cleanup_complete' in result.stdout
        assert target.exists()
        assert _pr_git(target, 'branch', '--show-current') == ''
        assert _pr_git(target, 'rev-parse', 'HEAD') == remote_base
        assert _pr_git(other, 'branch', '--show-current') == 'main'
        assert _pr_git(other, 'rev-parse', 'HEAD') == remote_base
        worktrees = _pr_cases().load_pr_flow_module().parse_worktrees(_pr_git(target, 'worktree', 'list', '--porcelain', '-z'))
        target_record = next((item for item in worktrees if Path(item['path']).resolve() == target.resolve()))
        assert target_record['detached'] is True
        assert subprocess.run(['git', 'show-ref', '--verify', '--quiet', 'refs/heads/feature/example'], cwd=target, check=False).returncode == 1
        assert subprocess.run(['git', '--git-dir', str(remote), 'show-ref', '--verify', '--quiet', 'refs/heads/feature/example'], check=False).returncode == 1
        status = json.loads((target / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        assert status['status'] == 'cleanup_complete'
        assert status['details']['worktreeRetention'] == {'status': 'retained', 'reason': 'active_session'}
        assert 'removeWorktreePending' not in status['details']
        assert 'nextCommand' not in status['details']

    @pytest.mark.parametrize('cwd_relative', [None, Path('.pr-flow')], ids=['root', 'subdirectory'])
    def test_cleanup_retains_active_worktree_when_project_is_directory_alias(self, tmp_path: Path, monkeypatch, cwd_relative: Path | None) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        _pr_git(project, 'checkout', 'main')
        _pr_git(project, 'checkout', '-b', 'controller')
        target = tmp_path / 'target'
        _pr_git(project, 'worktree', 'add', str(target), 'feature/example')
        alias = tmp_path / 'target-alias'
        if os.name == 'nt':
            powershell = shutil.which('powershell')
            if not powershell:
                pytest.skip('PowerShell is required to create a junction')
            junction = subprocess.run([powershell, '-NoProfile', '-Command', f'New-Item -ItemType Junction -Path "{alias}" -Target "{target}"'], check=False, capture_output=True)
            if junction.returncode != 0:
                pytest.skip('Windows junction creation is unavailable: ' + junction.stderr.decode(errors='replace'))
        else:
            try:
                alias.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                pytest.skip(f'directory symlink creation is unavailable: {exc}')
        active_cwd = target if cwd_relative is None else target / cwd_relative
        with contextlib.chdir(active_cwd):
            result = _pr_run_cleanup_with_real_git(alias, monkeypatch, remove_worktree=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'status: cleanup_complete' in result.stdout
        assert target.is_dir()
        assert alias.is_dir()
        assert _pr_git(target, 'branch', '--show-current') == ''
        assert _pr_git(target, 'rev-parse', 'HEAD') == _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
        status = json.loads((target / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        assert status['details']['worktreeRetention'] == {'status': 'retained', 'reason': 'active_session'}

    def test_cleanup_retains_active_worktree_when_cwd_uses_directory_alias(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        _pr_git(project, 'checkout', 'main')
        _pr_git(project, 'checkout', '-b', 'controller')
        target = tmp_path / 'target'
        _pr_git(project, 'worktree', 'add', str(target), 'feature/example')
        alias = tmp_path / 'target-alias'
        if os.name == 'nt':
            powershell = shutil.which('powershell')
            if not powershell:
                pytest.skip('PowerShell is required to create a junction')
            junction = subprocess.run([powershell, '-NoProfile', '-Command', f'New-Item -ItemType Junction -Path "{alias}" -Target "{target}"'], check=False, capture_output=True)
            if junction.returncode != 0:
                pytest.skip('Windows junction creation is unavailable: ' + junction.stderr.decode(errors='replace'))
        else:
            try:
                alias.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                pytest.skip(f'directory symlink creation is unavailable: {exc}')
        with contextlib.chdir(alias):
            module = _pr_cases().load_pr_flow_module()
            cwd_key = module.lexical_path(Path.cwd())
            alias_key = module.lexical_path(alias)
            try:
                cwd_uses_alias = os.path.commonpath([cwd_key, alias_key]) == alias_key
            except ValueError:
                cwd_uses_alias = False
            if not cwd_uses_alias:
                pytest.skip('platform resolves directory links in cwd')
            result = _pr_run_cleanup_with_real_git(target, monkeypatch, remove_worktree=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'status: cleanup_complete' in result.stdout
        assert target.is_dir()
        assert alias.is_dir()
        assert _pr_git(target, 'branch', '--show-current') == ''
        assert _pr_git(target, 'rev-parse', 'HEAD') == _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
        status = json.loads((target / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        assert status['details']['worktreeRetention'] == {'status': 'retained', 'reason': 'active_session'}

    def test_cleanup_retains_active_worktree_with_ignored_cwd_after_branch_cleanup(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        (project / '.gitignore').write_text('.local/\n', encoding='utf-8')
        _pr_git(project, 'add', '.gitignore')
        _pr_git(project, 'commit', '-m', 'ignore local worktree state')
        _pr_git(project, 'push', 'origin', 'feature/example')
        integrator = tmp_path / 'integrator'
        clone_result = subprocess.run(['git', 'clone', str(remote), str(integrator)], check=False, text=True, capture_output=True)
        assert clone_result.returncode == 0, clone_result.stdout + clone_result.stderr
        _pr_git(integrator, 'config', 'user.email', 'test@example.com')
        _pr_git(integrator, 'config', 'user.name', 'Test User')
        _pr_git(integrator, 'fetch', 'origin', 'feature/example')
        _pr_git(integrator, 'checkout', '-B', 'main', 'origin/main')
        _pr_git(integrator, 'merge', '--ff-only', 'origin/feature/example')
        _pr_git(integrator, 'push', 'origin', 'main')
        _pr_git(project, 'checkout', 'main')
        _pr_git(project, 'checkout', '-b', 'controller')
        target = tmp_path / 'target'
        _pr_git(project, 'worktree', 'add', str(target), 'feature/example')
        active_cwd = target / '.local' / 'spec-work'
        active_cwd.mkdir(parents=True)
        ignored = subprocess.run(['git', 'check-ignore', '--quiet', '--', '.local/spec-work'], cwd=target, check=False)
        assert ignored.returncode == 0
        with contextlib.chdir(active_cwd):
            result = _pr_run_cleanup_with_real_git(target, monkeypatch, remove_worktree=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'status: cleanup_complete' in result.stdout
        assert target.is_dir()
        assert active_cwd.is_dir()
        assert _pr_git(target, 'branch', '--show-current') == ''
        assert _pr_git(target, 'rev-parse', 'HEAD') == _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
        assert subprocess.run(['git', 'show-ref', '--verify', '--quiet', 'refs/heads/feature/example'], cwd=target, check=False).returncode == 1
        assert _pr_git_bare_result(remote, 'show-ref', '--verify', 'refs/heads/feature/example').returncode != 0
        status = json.loads((target / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        assert status['status'] == 'cleanup_complete'
        assert status['details']['worktreeRetention'] == {'status': 'retained', 'reason': 'active_session'}

    def test_cleanup_retains_active_worktree_when_active_cwd_is_inside_ignored_directory_link(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        (project / '.gitignore').write_text('.local/\n', encoding='utf-8')
        _pr_git(project, 'add', '.gitignore')
        _pr_git(project, 'commit', '-m', 'ignore linked runtime state')
        _pr_git(project, 'push', 'origin', 'feature/example')
        integrator = tmp_path / 'integrator'
        clone_result = subprocess.run(['git', 'clone', str(remote), str(integrator)], check=False, text=True, capture_output=True)
        assert clone_result.returncode == 0, clone_result.stdout + clone_result.stderr
        _pr_git(integrator, 'config', 'user.email', 'test@example.com')
        _pr_git(integrator, 'config', 'user.name', 'Test User')
        _pr_git(integrator, 'fetch', 'origin', 'feature/example')
        _pr_git(integrator, 'checkout', '-B', 'main', 'origin/main')
        _pr_git(integrator, 'merge', '--ff-only', 'origin/feature/example')
        _pr_git(integrator, 'push', 'origin', 'main')
        _pr_git(project, 'checkout', 'main')
        _pr_git(project, 'checkout', '-b', 'controller')
        target = tmp_path / 'target'
        _pr_git(project, 'worktree', 'add', str(target), 'feature/example')
        shared = tmp_path / 'shared-runtime'
        (shared / 'nested').mkdir(parents=True)
        sentinel = shared / 'sentinel.txt'
        sentinel.write_text('keep\n', encoding='utf-8')
        link = target / '.local' / 'spec-work'
        link.parent.mkdir()
        if os.name == 'nt':
            powershell = shutil.which('powershell')
            if not powershell:
                pytest.skip('PowerShell is required to create a junction')
            junction = subprocess.run([powershell, '-NoProfile', '-Command', f'New-Item -ItemType Junction -Path "{link}" -Target "{shared}"'], check=False, capture_output=True)
            if junction.returncode != 0:
                pytest.skip('Windows junction creation is unavailable: ' + junction.stderr.decode(errors='replace'))
        else:
            try:
                link.symlink_to(shared, target_is_directory=True)
            except OSError as exc:
                pytest.skip(f'directory symlink creation is unavailable: {exc}')
        active_cwd = link / 'nested'
        ignored = subprocess.run(['git', 'check-ignore', '--quiet', '--', '.local/spec-work'], cwd=target, check=False)
        assert ignored.returncode == 0
        with contextlib.chdir(active_cwd):
            cwd_key = os.path.normcase(os.path.abspath(os.fspath(Path.cwd())))
            target_key = os.path.normcase(os.path.abspath(os.fspath(target)))
            try:
                logical_cwd_is_inside_target = os.path.commonpath([cwd_key, target_key]) == target_key
            except ValueError:
                logical_cwd_is_inside_target = False
            if not logical_cwd_is_inside_target:
                pytest.skip('platform resolves directory links in cwd and cannot preserve the logical path')
            result = _pr_run_cleanup_with_real_git(target, monkeypatch, remove_worktree=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'status: cleanup_complete' in result.stdout
        assert target.is_dir()
        assert active_cwd.is_dir()
        assert sentinel.read_text(encoding='utf-8') == 'keep\n'
        assert _pr_git(target, 'branch', '--show-current') == ''
        assert _pr_git(target, 'rev-parse', 'HEAD') == _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
        worktrees = _pr_cases().load_pr_flow_module().parse_worktrees(_pr_git(target, 'worktree', 'list', '--porcelain', '-z'))
        target_record = next((item for item in worktrees if Path(item['path']).resolve() == target.resolve()))
        assert target_record['detached'] is True
        assert subprocess.run(['git', 'show-ref', '--verify', '--quiet', 'refs/heads/feature/example'], cwd=target, check=False).returncode == 1
        assert _pr_git_bare_result(remote, 'show-ref', '--verify', 'refs/heads/feature/example').returncode != 0

    def test_cleanup_stops_before_detaching_when_active_cwd_is_untracked_and_not_ignored(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        integrator = tmp_path / 'integrator'
        clone_result = subprocess.run(['git', 'clone', str(remote), str(integrator)], check=False, text=True, capture_output=True)
        assert clone_result.returncode == 0, clone_result.stdout + clone_result.stderr
        _pr_git(integrator, 'config', 'user.email', 'test@example.com')
        _pr_git(integrator, 'config', 'user.name', 'Test User')
        _pr_git(integrator, 'fetch', 'origin', 'feature/example')
        _pr_git(integrator, 'checkout', '-B', 'main', 'origin/main')
        _pr_git(integrator, 'merge', '--ff-only', 'origin/feature/example')
        (integrator / 'BASE_ONLY.md').write_text('base only\n', encoding='utf-8')
        _pr_git(integrator, 'add', 'BASE_ONLY.md')
        _pr_git(integrator, 'commit', '-m', 'base-only change')
        _pr_git(integrator, 'push', 'origin', 'main')
        _pr_git(project, 'checkout', 'main')
        _pr_git(project, 'checkout', '-b', 'controller')
        target = tmp_path / 'target'
        _pr_git(project, 'worktree', 'add', str(target), 'feature/example')
        active_cwd = target / 'untracked' / 'nested'
        active_cwd.mkdir(parents=True)
        not_ignored = subprocess.run(['git', 'check-ignore', '--quiet', '--', 'untracked/nested'], cwd=target, check=False)
        assert not_ignored.returncode != 0
        with contextlib.chdir(active_cwd):
            result = _pr_run_cleanup_with_real_git(target, monkeypatch, remove_worktree=True)
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'cleanup_complete' not in result.stdout
        assert target.is_dir()
        assert active_cwd.is_dir()
        assert _pr_git(target, 'branch', '--show-current') == 'feature/example'
        assert _pr_git_bare_result(remote, 'show-ref', '--verify', 'refs/heads/feature/example').returncode == 0
        status = json.loads((target / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        assert status['details']['reason'] == 'active_cwd_would_disappear'

    def test_cleanup_stops_before_detaching_when_active_cwd_disappears_on_base_checkout(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        source_only = project / 'source-only' / 'nested'
        source_only.mkdir(parents=True)
        (source_only / 'sentinel.txt').write_text('source only\n', encoding='utf-8')
        _pr_git(project, 'add', 'source-only')
        _pr_git(project, 'commit', '-m', 'source-only directory')
        source_head = _pr_git(project, 'rev-parse', 'HEAD')
        _pr_git(project, 'push', 'origin', 'feature/example')
        integrator = tmp_path / 'integrator'
        clone_result = subprocess.run(['git', 'clone', str(remote), str(integrator)], check=False, text=True, capture_output=True)
        assert clone_result.returncode == 0, clone_result.stdout + clone_result.stderr
        _pr_git(integrator, 'config', 'user.email', 'test@example.com')
        _pr_git(integrator, 'config', 'user.name', 'Test User')
        _pr_git(integrator, 'fetch', 'origin', 'feature/example')
        _pr_git(integrator, 'checkout', '-B', 'main', 'origin/main')
        _pr_git(integrator, 'merge', '--ff-only', 'origin/feature/example')
        shutil.rmtree(integrator / 'source-only')
        _pr_git(integrator, 'add', '-u', 'source-only')
        _pr_git(integrator, 'commit', '-m', 'remove source-only directory from base')
        _pr_git(integrator, 'push', 'origin', 'main')
        assert not (integrator / 'source-only').exists()
        _pr_git(project, 'checkout', 'main')
        _pr_git(project, 'checkout', '-b', 'controller')
        target = tmp_path / 'target'
        _pr_git(project, 'worktree', 'add', str(target), 'feature/example')
        active_cwd = target / 'source-only' / 'nested'
        assert active_cwd.is_dir()
        assert not (target / 'source-only').exists() or source_head == _pr_git(target, 'rev-parse', 'HEAD')
        with contextlib.chdir(active_cwd):
            result = _pr_run_cleanup_with_real_git(target, monkeypatch, remove_worktree=True)
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'cleanup_complete' not in result.stdout
        assert target.is_dir()
        assert active_cwd.is_dir()
        assert _pr_git(target, 'branch', '--show-current') == 'feature/example'
        assert _pr_git(target, 'rev-parse', 'HEAD') == source_head
        assert _pr_git_bare(remote, 'show-ref', '--verify', 'refs/heads/feature/example')
        status = json.loads((target / '.pr-flow/last-status.json').read_text(encoding='utf-8'))
        assert status['status'] == 'EXCEPTION_REQUIRED'
        assert status['details']['reason'] == 'active_cwd_would_disappear'
        assert status['details']['nextCommand']

    def test_cleanup_keeps_detached_when_synced_base_is_checked_out_elsewhere(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        remote_base = _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
        _pr_git(project, 'branch', '-f', 'main', remote_base)
        other = tmp_path / 'base-worktree'
        _pr_git(project, 'worktree', 'add', str(other), 'main')
        before = (_pr_git(project, 'rev-parse', 'HEAD'), _pr_git(project, 'branch', '--show-current'), _pr_git(project, 'show-ref'))
        before_remote_refs = _pr_git_bare(remote, 'show-ref')
        result = _pr_run_cleanup_with_real_git(project, monkeypatch)
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'base_branch_checked_out' in result.stdout
        assert (_pr_git(project, 'rev-parse', 'HEAD'), _pr_git(project, 'branch', '--show-current'), _pr_git(project, 'show-ref')) == before
        assert _pr_git(other, 'branch', '--show-current') == 'main'
        assert _pr_git(other, 'rev-parse', 'HEAD') == remote_base
        assert _pr_git_bare(remote, 'show-ref') == before_remote_refs
        status = json.loads((project / '.pr-flow' / 'last-status.json').read_text(encoding='utf-8'))
        assert status['details']['reason'] == 'base_branch_checked_out'
        assert other.resolve() in [Path(path).resolve() for path in status['details']['occupiedWorktrees']]

    def test_cleanup_creates_missing_local_base_end_to_end(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        remote_base = _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
        _pr_git(project, 'branch', '-D', 'main')
        result = _pr_run_cleanup_with_real_git(project, monkeypatch)
        local_base = subprocess.run(['git', 'rev-parse', 'main'], cwd=project, check=False, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert local_base.returncode == 0, local_base.stdout + local_base.stderr
        assert local_base.stdout.strip() == remote_base
        assert _pr_git(project, 'branch', '--show-current') == 'main'
        status = json.loads((project / '.pr-flow' / 'last-status.json').read_text(encoding='utf-8'))
        assert status['details']['baseCheckout'] == {'status': 'checked_out'}

    def test_cleanup_refuses_diverged_local_base_end_to_end(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        _pr_git(project, 'checkout', 'main')
        (project / 'LOCAL.md').write_text('local only\n', encoding='utf-8')
        _pr_git(project, 'add', 'LOCAL.md')
        _pr_git(project, 'commit', '-m', 'local only')
        _pr_git(project, 'checkout', 'feature/example')
        result = _pr_run_cleanup_with_real_git(project, monkeypatch)
        assert result.returncode == 1
        status = json.loads((project / '.pr-flow' / 'last-status.json').read_text(encoding='utf-8'))
        assert status['details']['reason'] == 'local_base_not_fast_forward'
        assert _pr_git_bare(remote, 'show-ref', '--verify', 'refs/heads/feature/example')

    def test_cleanup_fast_forwards_stale_base_checked_out_elsewhere_end_to_end(self, tmp_path: Path, monkeypatch) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        remote_base = _pr_git_bare(remote, 'rev-parse', 'refs/heads/main')
        other = tmp_path / 'base-worktree'
        _pr_git(project, 'worktree', 'add', str(other), 'main')
        before = (_pr_git(project, 'rev-parse', 'HEAD'), _pr_git(project, 'branch', '--show-current'), _pr_git(project, 'show-ref'))
        before_remote_refs = _pr_git_bare(remote, 'show-ref')
        result = _pr_run_cleanup_with_real_git(project, monkeypatch)
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'base_branch_checked_out' in result.stdout
        assert (_pr_git(project, 'rev-parse', 'HEAD'), _pr_git(project, 'branch', '--show-current'), _pr_git(project, 'show-ref')) == before
        assert _pr_git(other, 'branch', '--show-current') == 'main'
        assert _pr_git(other, 'rev-parse', 'HEAD') == _pr_git(project, 'rev-parse', 'main')
        assert _pr_git(other, 'rev-parse', 'HEAD') != remote_base
        assert _pr_git_bare(remote, 'show-ref') == before_remote_refs
        status = json.loads((project / '.pr-flow' / 'last-status.json').read_text(encoding='utf-8'))
        assert status['details']['reason'] == 'base_branch_checked_out'
        assert other.resolve() in [Path(path).resolve() for path in status['details']['occupiedWorktrees']]

    @pytest.mark.parametrize('unsafe_state', ['dirty', 'rebase'])
    def test_cleanup_refuses_unsafe_stale_base_worktree_end_to_end(self, tmp_path: Path, monkeypatch, unsafe_state: str) -> None:
        project, remote = _pr_init_cleanup_project(tmp_path)
        stale_base = _pr_git(project, 'rev-parse', 'main')
        other = tmp_path / 'base-worktree'
        _pr_git(project, 'worktree', 'add', str(other), 'main')
        if unsafe_state == 'dirty':
            (other / 'DIRTY.md').write_text('dirty\n', encoding='utf-8')
        else:
            git_path = Path(_pr_git(other, 'rev-parse', '--git-path', 'rebase-merge'))
            git_path.mkdir(parents=True)
        result = _pr_run_cleanup_with_real_git(project, monkeypatch)
        assert result.returncode == 1
        assert _pr_git(other, 'rev-parse', 'HEAD') == stale_base
        assert _pr_git_bare(remote, 'show-ref', '--verify', 'refs/heads/feature/example')
        status = json.loads((project / '.pr-flow' / 'last-status.json').read_text(encoding='utf-8'))
        assert status['details']['reason'] == 'base_branch_checked_out'

    def test_init_accepts_same_worktree_with_stable_toolchain_identities(self, tmp_path: Path) -> None:
        project = tmp_path / 'project'
        project.mkdir()
        config = tmp_path / 'config.yaml'
        config.write_text(yaml.safe_dump(_pr_cases().default_pr_flow_config_for_test(), sort_keys=False), encoding='utf-8')
        bin_dir = tmp_path / 'bin'
        reports = _pr_dev_toolchain_reports(project, worktree_match=True)
        for report in reports.values():
            report['toolchain']['implementationIdentity'] = 'sha256:' + '1' * 64
        _pr_write_toolchain_cli(bin_dir, reports)
        result = _pr_run_public_pr_flow(bin_dir, 'init', '--project', str(project), '--config', str(config))
        assert result.returncode == 0, result.stdout + result.stderr
        tools = json.loads((project / '.pr-flow' / 'toolchain.json').read_text(encoding='utf-8'))['tools']
        assert tools['myspec']['sourceCommit'] == 'a' * 40
        assert tools['myspec']['implementationIdentity'] == 'sha256:' + '1' * 64
        assert tools['build-and-verify']['sourceCommit'] == 'a' * 40

    @pytest.mark.parametrize(('command', 'extra'), [('complete', ['--summary', 's', '--scope', 's']), ('tweak', ['--reason', 'r', '--summary', 's', '--scope', 's'])])
    def test_lifecycle_syncs_same_worktree_toolchain_before_remote_flow(self, tmp_path: Path, command: str, extra: list[str]) -> None:
        init_bin = tmp_path / 'init-bin'
        release_reports = {'myspec': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/myspec', 'packageVersion': '1.2.3'}}, 'build-and-verify': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/build-and-verify', 'packageVersion': '1.2.3'}}}
        _pr_write_toolchain_cli(init_bin, release_reports)
        project = _pr_initialized_toolchain_project(tmp_path, init_bin)
        before_head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=project, check=True, text=True, capture_output=True).stdout.strip()
        run_bin = tmp_path / 'run-bin'
        _pr_write_toolchain_cli(run_bin, _pr_dev_toolchain_reports(project, worktree_match=True))
        _pr_write_fake_gh(run_bin, exit_code=99)
        result = _pr_run_public_pr_flow(run_bin, command, '--project', str(project), *extra)
        assert result.returncode == 1
        assert 'toolchain_same_worktree_unsupported' not in result.stdout
        assert 'toolchain_source_commit_unavailable' not in result.stdout
        after_head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=project, check=True, text=True, capture_output=True).stdout.strip()
        assert after_head != before_head
        tools = json.loads((project / '.pr-flow' / 'toolchain.json').read_text(encoding='utf-8'))['tools']
        assert tools['myspec']['implementationIdentity'] == 'sha256:' + '0' * 64

    def test_init_fails_closed_when_dev_implementation_commit_is_unavailable(self, tmp_path: Path) -> None:
        project = tmp_path / 'project'
        project.mkdir()
        config = tmp_path / 'config.yaml'
        config.write_text(yaml.safe_dump(_pr_cases().default_pr_flow_config_for_test(), sort_keys=False), encoding='utf-8')
        bin_dir = tmp_path / 'bin'
        reports = _pr_dev_toolchain_reports(project, worktree_match=True)
        del reports['myspec']['toolchain']['sourceCommit']
        _pr_write_toolchain_cli(bin_dir, reports)
        result = _pr_run_public_pr_flow(bin_dir, 'init', '--project', str(project), '--config', str(config))
        assert result.returncode == 1
        assert 'status: toolchain_source_commit_unavailable' in result.stdout
        assert 'Publish the exact implementation commit' in result.stdout
        assert not (project / '.pr-flow' / 'toolchain.json').exists()

    def test_toolchain_sync_converges_for_independent_and_shared_tool_changes(self, tmp_path: Path) -> None:
        init_bin = tmp_path / 'init-bin'
        release_reports = {'myspec': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/myspec', 'packageVersion': '1.2.3'}}, 'build-and-verify': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/build-and-verify', 'packageVersion': '1.2.3'}}}
        _pr_write_toolchain_cli(init_bin, release_reports)
        project = _pr_initialized_toolchain_project(tmp_path, init_bin)
        baseline = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=project, check=True, text=True, capture_output=True).stdout.strip()
        run_bin = tmp_path / 'run-bin'
        reports = _pr_dev_toolchain_reports(project, worktree_match=True)
        _pr_write_toolchain_cli(run_bin, reports)
        _pr_write_fake_gh(run_bin, exit_code=99)
        first = _pr_sync_through_public_complete(run_bin, project)
        assert first.returncode == 1
        assert subprocess.run(['git', 'rev-list', '--count', f'{baseline}..HEAD'], cwd=project, check=True, text=True, capture_output=True).stdout.strip() == '1'
        first_record = json.loads((project / '.pr-flow/toolchain.json').read_text(encoding='utf-8'))
        first_workflow = (project / '.github/workflows/pr-flow-toolchain.yml').read_bytes()
        second = _pr_sync_through_public_complete(run_bin, project)
        assert second.returncode == 1
        assert subprocess.run(['git', 'rev-list', '--count', f'{baseline}..HEAD'], cwd=project, check=True, text=True, capture_output=True).stdout.strip() == '1'
        assert (project / '.github/workflows/pr-flow-toolchain.yml').read_bytes() == first_workflow
        reports['myspec']['toolchain']['sourceCommit'] = 'b' * 40
        reports['myspec']['toolchain']['implementationIdentity'] = 'sha256:' + '2' * 64
        _pr_write_toolchain_cli(run_bin, reports)
        third = _pr_sync_through_public_complete(run_bin, project)
        assert third.returncode == 1
        assert subprocess.run(['git', 'rev-list', '--count', f'{baseline}..HEAD'], cwd=project, check=True, text=True, capture_output=True).stdout.strip() == '2'
        updated = json.loads((project / '.pr-flow/toolchain.json').read_text(encoding='utf-8'))
        assert updated['tools']['myspec']['implementationIdentity'] == 'sha256:' + '2' * 64
        assert updated['tools']['build-and-verify'] == first_record['tools']['build-and-verify']
        assert 'checkout --detach ' + 'a' * 40 in (project / '.github/workflows/pr-flow-toolchain.yml').read_text(encoding='utf-8')
        reports['myspec']['toolchain'].update(sourceCommit='c' * 40, implementationIdentity='sha256:' + '3' * 64)
        reports['build-and-verify']['toolchain'].update(sourceCommit='c' * 40, implementationIdentity='sha256:' + '4' * 64)
        _pr_write_toolchain_cli(run_bin, reports)
        shared = _pr_sync_through_public_complete(run_bin, project)
        assert shared.returncode == 1
        assert subprocess.run(['git', 'rev-list', '--count', f'{baseline}..HEAD'], cwd=project, check=True, text=True, capture_output=True).stdout.strip() == '3'
        shared_record = json.loads((project / '.pr-flow/toolchain.json').read_text(encoding='utf-8'))
        assert shared_record['tools']['myspec']['implementationIdentity'] == 'sha256:' + '3' * 64
        assert shared_record['tools']['build-and-verify']['implementationIdentity'] == 'sha256:' + '4' * 64

    def test_init_uses_target_project_as_toolchain_doctor_cwd(self, tmp_path: Path) -> None:
        project = tmp_path / 'project'
        project.mkdir()
        config = tmp_path / 'config.yaml'
        config.write_text(yaml.safe_dump(_pr_cases().default_pr_flow_config_for_test(), sort_keys=False), encoding='utf-8')
        bin_dir = tmp_path / 'bin'
        cwd_log = tmp_path / 'doctor-cwd.log'
        _pr_write_toolchain_cli(bin_dir, _pr_dev_toolchain_reports(project, worktree_match=False), cwd_log=cwd_log)
        result = _pr_run_public_pr_flow(bin_dir, 'init', '--project', str(project), '--config', str(config))
        assert result.returncode == 0, result.stdout + result.stderr
        assert cwd_log.read_text(encoding='utf-8').splitlines() == [str(project.resolve())] * 2
        assert 'checkout --detach ' + 'a' * 40 in (project / '.github' / 'workflows' / 'pr-flow-toolchain.yml').read_text(encoding='utf-8')

    def test_complete_commits_only_changed_managed_file_through_public_cli(self, tmp_path: Path) -> None:
        bin_dir = tmp_path / 'bin'
        reports = {'myspec': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/myspec', 'packageVersion': '1.2.3'}}, 'build-and-verify': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/build-and-verify', 'packageVersion': '1.2.3'}}}
        _pr_write_toolchain_cli(bin_dir, reports)
        project = _pr_initialized_toolchain_project(tmp_path, bin_dir)
        workflow = project / '.github/workflows/pr-flow-toolchain.yml'
        workflow.write_text('stale\n', encoding='utf-8')
        assert subprocess.run(['git', 'add', str(workflow.relative_to(project))], cwd=project, check=False).returncode == 0
        assert subprocess.run(['git', 'commit', '-m', 'stale workflow'], cwd=project, check=False).returncode == 0
        _pr_sync_through_public_complete(bin_dir, project)
        changed = subprocess.run(['git', 'show', '--format=', '--name-only', 'HEAD'], cwd=project, check=False, text=True, capture_output=True)
        assert changed.stdout.splitlines() == ['.github/workflows/pr-flow-toolchain.yml']
        assert subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=project, check=False).returncode == 0

    def test_complete_refuses_dirty_tree_without_staging_managed_files_through_public_cli(self, tmp_path: Path) -> None:
        bin_dir = tmp_path / 'bin'
        reports = {'myspec': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/myspec', 'packageVersion': '1.2.3'}}, 'build-and-verify': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/build-and-verify', 'packageVersion': '1.2.3'}}}
        _pr_write_toolchain_cli(bin_dir, reports)
        project = _pr_initialized_toolchain_project(tmp_path, bin_dir)
        (project / '.pr-flow/toolchain.json').write_text('stale\n', encoding='utf-8')
        (project / 'unrelated.txt').write_text('dirty\n', encoding='utf-8')
        result = _pr_sync_through_public_complete(bin_dir, project)
        assert 'toolchain_sync_dirty' in result.stdout
        assert subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=project, check=False).returncode == 0
        assert (project / '.pr-flow/toolchain.json').read_text(encoding='utf-8') == 'stale\n'

    def test_complete_restores_toolchain_files_and_index_when_commit_fails_through_public_cli(self, tmp_path: Path) -> None:
        bin_dir = tmp_path / 'bin'
        reports = {'myspec': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/myspec', 'packageVersion': '1.2.3'}}, 'build-and-verify': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/build-and-verify', 'packageVersion': '1.2.3'}}}
        _pr_write_toolchain_cli(bin_dir, reports)
        project = _pr_initialized_toolchain_project(tmp_path, bin_dir)
        record = project / '.pr-flow/toolchain.json'
        record.write_text('stale\n', encoding='utf-8')
        assert subprocess.run(['git', 'add', str(record.relative_to(project))], cwd=project, check=False).returncode == 0
        assert subprocess.run(['git', 'commit', '-m', 'stale record'], cwd=project, check=False).returncode == 0
        assert subprocess.run(['git', 'config', 'user.email', ''], cwd=project, check=False).returncode == 0
        assert subprocess.run(['git', 'config', 'user.name', ''], cwd=project, check=False).returncode == 0
        result = _pr_sync_through_public_complete(bin_dir, project)
        assert 'git_toolchain_commit_failed' in result.stdout
        assert subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=project, check=False).returncode == 0
        assert record.read_text(encoding='utf-8') == 'stale\n'

    def test_complete_rereads_the_new_baseline_with_bounded_toolchain_retries(self, tmp_path: Path) -> None:
        bin_dir = tmp_path / 'bin'
        reports = {'myspec': [{'toolchain': {'mode': 'release', 'packageName': '@liuli195/myspec', 'packageVersion': '1.0.0'}}, {'toolchain': {'mode': 'release', 'packageName': '@liuli195/myspec', 'packageVersion': '1.0.1'}}, {'toolchain': {'mode': 'release', 'packageName': '@liuli195/myspec', 'packageVersion': '1.0.2'}}], 'build-and-verify': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/build-and-verify', 'packageVersion': '1.0.0'}}}
        _pr_write_toolchain_cli(bin_dir, reports)
        project = _pr_initialized_toolchain_project(tmp_path, bin_dir)
        baseline = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=project, check=False, text=True, capture_output=True).stdout.strip()
        result = _pr_sync_through_public_complete(bin_dir, project)
        commits = subprocess.run(['git', 'rev-list', '--count', f'{baseline}..HEAD'], cwd=project, check=False, text=True, capture_output=True)
        assert commits.stdout.strip() == '2', result.stdout + result.stderr
        assert '1.0.2' in (project / '.pr-flow/toolchain.json').read_text(encoding='utf-8')

    def test_init_validates_release_and_dev_toolchain_identities_through_public_cli(self, tmp_path: Path) -> None:
        config = tmp_path / 'config.yaml'
        config.write_text(yaml.safe_dump(_pr_cases().default_pr_flow_config_for_test(), sort_keys=False), encoding='utf-8')
        reports = {'myspec': {'toolchain': {'mode': 'release', 'packageName': '@liuli195/myspec', 'packageVersion': '1.2.3-rc.1+build.9'}}, 'build-and-verify': {'toolchain': {'mode': 'dev', 'packageName': '@liuli195/build-and-verify', 'sourceRepository': 'https://github.com/liuli195/my-agent-skills', 'sourceCommit': 'a' * 40, 'packageDirectory': 'plugins/build-and-verify', 'implementationIdentity': 'sha256:' + '0' * 64}}}
        bin_dir = tmp_path / 'bin'
        _pr_write_toolchain_cli(bin_dir, reports)
        result = _pr_run_public_pr_flow(bin_dir, 'init', '--project', str(tmp_path / 'project'), '--config', str(config))
        assert result.returncode == 0, result.stdout + result.stderr
        workflow = (tmp_path / 'project' / '.github/workflows/pr-flow-toolchain.yml').read_text(encoding='utf-8')
        assert '@liuli195/myspec@1.2.3-rc.1+build.9' in workflow
        assert 'checkout --detach ' + 'a' * 40 in workflow

    @pytest.mark.parametrize('command, extra', [('diagnose', []), ('complete', ['--summary', 's', '--scope', 's']), ('tweak', ['--reason', 'r', '--summary', 's', '--scope', 's'])])
    def test_legacy_repositories_keep_flow_behavior_with_upgrade_prompt(self, tmp_path: Path, command: str, extra: list[str]) -> None:
        project = tmp_path / 'project'
        project.mkdir()
        assert subprocess.run(['git', 'init'], cwd=project, check=False).returncode == 0
        _pr_cases().write_complete_pr_flow_config(project)
        result = subprocess.run([sys.executable, str(_pr_cases().SCRIPT), command, '--project', str(project), *extra], check=False, text=True, capture_output=True)
        assert 'upgrade available: rerun pr-flow-init to record the managed toolchain' in result.stdout

    def test_cleanup_physical_failure_persists_status_in_controller(self, tmp_path: Path, monkeypatch) -> None:
        module = _pr_cases().load_pr_flow_module()

        def fail_rmtree(_target: Path) -> None:
            raise OSError('directory is still in use')
        monkeypatch.setattr(module, 'find_orca_worktree_id', lambda *_args: None)
        monkeypatch.setattr(module.shutil, 'rmtree', fail_rmtree)
        project, result = _pr_cases().run_cleanup_in_process(tmp_path, monkeypatch, pr_stdout=_pr_cases().cleanup_pr_view_json(), remove_worktree=True)
        assert result.returncode == 1
        assert 'cleanup_complete' not in result.stdout
        status = json.loads((tmp_path / 'controller' / '.pr-flow' / 'last-status.json').read_text(encoding='utf-8'))
        assert status['details']['reason'] == 'physical_worktree_remove_failed'
        assert status['details']['registrationRemoved'] is True
        assert status['details']['nextAction']
        assert status['details']['nextCommand']
        expected_recovery_command = 'rmdir' if os.name == 'nt' else 'rm -rf'
        assert expected_recovery_command in status['details']['nextCommand']
        assert status['details']['recovery'] == status['details']['nextAction']



# Real release preparation, loaded only by TestReleaseFlow.
_RELEASE_TEMPLATE_ROOT = None
_RELEASE_TEMPLATE_LOCK_TIMEOUT_SECONDS = 30
_RELEASE_TEMPLATE_LOCK_STALE_SECONDS = 30

def _release_run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.setdefault('GITHUB_ACTIONS', 'true')
    environment.setdefault('GITHUB_REPOSITORY', 'liuli195/my-agent-skills')
    return subprocess.run([sys.executable, str(_release_cases().SCRIPT), *args], cwd=_release_cases().REPO_ROOT, env=environment, text=True, capture_output=True, check=False)

def _release_init_release_input_project(project: Path, remote: Path, version: str='1.0.0') -> None:
    _release_cases().write_release_flow_files(project)
    for plugin in ('release-flow', 'pr-flow', 'build-and-verify', 'my-spec'):
        _release_cases().write_plugin_manifests(project, plugin, version)
        (project / 'plugins' / plugin / 'content.txt').parent.mkdir(parents=True, exist_ok=True)
        (project / 'plugins' / plugin / 'content.txt').write_text('baseline\n', encoding='utf-8')
    for plugin in ('build-and-verify', 'my-spec'):
        _release_cases().write_npm_package(project, plugin, version=version)
    for path in (project / 'plugins' / 'tool-lifecycle' / 'pack.py', project / 'plugins' / 'tool-lifecycle' / 'python' / 'management.py'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('baseline\n', encoding='utf-8')
    _release_init_project_with_remote(project, remote)

def _release_advance_plugin_version_on_source_ref(project: Path, plugin: str, version: str) -> None:
    _release_cases().write_plugin_manifests(project, plugin, version)
    if plugin in {'build-and-verify', 'my-spec'}:
        _release_cases().write_npm_package(project, plugin, version=version)
    assert _release_git(project, 'add', f'plugins/{plugin}').returncode == 0
    assert _release_git(project, 'commit', '-m', f'bump {plugin}').returncode == 0
    assert _release_git(project, 'push', 'origin', 'HEAD:refs/heads/main').returncode == 0
    assert _release_git(project, 'fetch', 'origin', 'main').returncode == 0

def _release_git(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['git', '-C', str(project), *args], check=False, text=True, capture_output=True)

def _release_project_tree_cache_key(project: Path) -> str:
    digest = hashlib.sha256()
    digest.update(Path(__file__).read_bytes())
    digest.update(Path(_release_cases().__file__).read_bytes())
    for path in sorted(project.rglob('*')):
        if not path.is_file() or '.git' in path.parts:
            continue
        digest.update(path.relative_to(project).as_posix().encode('utf-8'))
        digest.update(b'\x00')
        digest.update(path.read_bytes())
        digest.update(b'\x00')
    return digest.hexdigest()[:16]

def _release_remove_template_lock(lock_dir: Path) -> None:
    for _ in range(5):
        shutil.rmtree(lock_dir, ignore_errors=True)
        if not lock_dir.exists():
            return
        time.sleep(0.05)

def _release_copy_project_remote_template(template_dir: Path, project: Path, remote: Path) -> None:
    copy_template(template_dir / 'remote.git', remote)
    copy_template(template_dir / 'project', project)
    assert _release_git(project, 'remote', 'set-url', 'origin', str(remote)).returncode == 0

def _release__init_project_with_remote_uncached(project: Path, remote: Path) -> None:
    subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(remote)], check=True, capture_output=True, text=True)
    assert _release_git(project, 'init').returncode == 0
    assert _release_git(project, 'config', 'user.email', 'test@example.com').returncode == 0
    assert _release_git(project, 'config', 'user.name', 'Test').returncode == 0
    assert _release_git(project, 'add', '.').returncode == 0
    assert _release_git(project, 'commit', '-m', 'baseline').returncode == 0
    assert _release_git(project, 'remote', 'add', 'origin', str(remote)).returncode == 0
    assert _release_git(project, 'push', 'origin', 'HEAD:refs/heads/main').returncode == 0
    assert _release_git(project, 'push', 'origin', 'HEAD:refs/heads/marketplace').returncode == 0
    assert _release_git(project, 'fetch', 'origin', 'marketplace').returncode == 0

def _release_init_project_with_remote(project: Path, remote: Path) -> None:
    template_dir = _RELEASE_TEMPLATE_ROOT / _release_project_tree_cache_key(project)
    ready = template_dir / '.ready'
    lock_dir = _RELEASE_TEMPLATE_ROOT / f'{template_dir.name}.lock'
    if ready.exists():
        if lock_dir.exists():
            _release_remove_template_lock(lock_dir)
        _release_copy_project_remote_template(template_dir, project, remote)
        return
    deadline = time.monotonic() + _RELEASE_TEMPLATE_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock_dir.mkdir(parents=True)
            break
        except FileExistsError:
            try:
                lock_age = time.time() - lock_dir.stat().st_mtime
            except FileNotFoundError:
                continue
            if lock_age > _RELEASE_TEMPLATE_LOCK_STALE_SECONDS:
                _release_remove_template_lock(lock_dir)
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f'template_lock_timeout: {lock_dir}')
            time.sleep(0.05)
    try:
        if not ready.exists():
            if template_dir.exists():
                remove_template(template_dir)
            template_dir.mkdir(parents=True, exist_ok=True)
            template_project = copy_template(project, template_dir / 'project')
            template_remote = template_dir / 'remote.git'
            _release__init_project_with_remote_uncached(template_project, template_remote)
            ready.write_text('ok\n', encoding='utf-8')
    finally:
        _release_remove_template_lock(lock_dir)
    _release_copy_project_remote_template(template_dir, project, remote)

def _release_fake_gh_for_publish(bin_dir: Path, calls: Path, *, always_eof: bool=False) -> Path:
    bin_dir.mkdir()
    seen = calls.with_name('gh-seen.txt')
    if os.name == 'nt':
        gh = bin_dir / 'gh.cmd'
        eof_line = 'echo Get ""https://api.github.com/repos/x/actions/workflows/release.yml"": EOF 1>&2'
        if always_eof:
            body = f'@echo off\r\necho %*>>"{calls}"\r\n{eof_line}\r\nexit /b 1\r\n'
        else:
            body = f'@echo off\r\necho %*>>"{calls}"\r\nif not exist "{seen}" (echo seen>"{seen}" & {eof_line} & exit /b 1)\r\nexit /b 0\r\n'
        gh.write_text(body, encoding='utf-8')
        return gh
    gh = bin_dir / 'gh'
    if always_eof:
        body = f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{calls}"\nprintf "%s\\n" "Get \\"https://api.github.com/repos/x/actions/workflows/release.yml\\": EOF" >&2\nexit 1\n'
    else:
        body = f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{calls}"\nif [ ! -f "{seen}" ]; then touch "{seen}"; printf "%s\\n" "Get \\"https://api.github.com/repos/x/actions/workflows/release.yml\\": EOF" >&2; exit 1; fi\nexit 0\n'
    gh.write_text(body, encoding='utf-8')
    gh.chmod(493)
    return gh


class TestReleaseFlow:
    @pytest.fixture(autouse=True)
    def _real_release_preparation(self):
        global _RELEASE_TEMPLATE_ROOT
        _RELEASE_TEMPLATE_ROOT = Path(tempfile.gettempdir()) / "release-flow-test-templates-v3"

    def test_repository_projection_validates_and_generates_real_catalogs(self, tmp_path: Path) -> None:
        cases = _release_cases()
        project = tmp_path / "project"
        for name in ("config.yaml", "projection.yaml"):
            target = project / ".release-flow" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((cases.REPO_ROOT / ".release-flow" / name).read_bytes())
        cases.write_json(project / ".claude-plugin/marketplace.json", {
            "name": "placeholder", "owner": {"name": "placeholder"}, "plugins": [],
        })
        validated = cases.run("validate", "--project", str(cases.REPO_ROOT))
        assert validated.returncode == 0, validated.stdout + validated.stderr
        projected = cases.run("project", "--project", str(project))
        assert projected.returncode == 0, projected.stdout + projected.stderr
        assert "status: projected" in projected.stdout
        expected = {"release-flow", "pr-flow", "dev-flow", "subagent-policy", "plugin-sync", "retro-to-issues", "data-store"}
        codex = json.loads((project / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
        claude = json.loads((project / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        assert {plugin["name"] for plugin in codex["plugins"]} == expected
        assert codex["name"] == claude["name"] == "my-agent-skills-marketplace"
        assert codex["interface"]["displayName"] == claude["owner"]["name"] == "My Agent Skills Marketplace"


    def test_setup_authorized_writes_only_config_projection_gitignore_and_workflow(self, tmp_path: Path) -> None:
        project = tmp_path / 'project'
        result = _release_cases().run('setup', '--project', str(project), '--authorize-project-files')
        assert result.returncode == 0
        assert 'status: setup_complete' in result.stdout
        assert (project / '.release-flow' / 'config.yaml').is_file()
        assert (project / '.release-flow' / 'projection.yaml').is_file()
        assert not (project / '.release-flow' / '.gitignore').exists()
        assert (project / '.github' / 'workflows' / 'release.yml').is_file()
        assert not (project / '.release-flow' / 'releases').exists()
        assert not (project / 'scripts' / 'release-flow').exists()

    def test_release_flow_local_e2e(self, tmp_path: Path, monkeypatch) -> None:
        release_flow = _release_cases().load_release_flow_module()
        project = tmp_path / 'project'
        setup = _release_cases().run('setup', '--project', str(project), '--authorize-project-files')
        assert setup.returncode == 0, setup.stdout + setup.stderr
        _release_cases().write_plugin_manifests(project, 'pr-flow', '9.9.1')
        _release_cases().write_plugin_manifests(project, 'release-flow', '9.9.1')
        _release_cases().write_json(project / '.claude-plugin' / 'marketplace.json', {'name': 'local-dev', 'owner': {'name': 'Local Dev'}})
        preflight_calls = []

        def fake_preflight(project_arg, tag, version, bump_plugins, config, projection):
            preflight_calls.append((project_arg, tag, version, bump_plugins, config.release_channel_branch, projection.path))
            return []
        monkeypatch.setattr(release_flow, 'preflight_errors', fake_preflight)
        preflight = _release_cases().run('preflight', '--project', str(project), '--tag', 'v9.9.1', '--version', '9.9.1', '--bump-plugins', 'pr-flow')
        assert preflight.returncode == 0, preflight.stdout + preflight.stderr
        assert preflight_calls == [(project.resolve(), 'v9.9.1', '9.9.1', ['pr-flow'], 'marketplace', project.resolve() / '.release-flow' / 'projection.yaml')]
        calls = tmp_path / 'gh-calls.txt'
        bin_dir = tmp_path / 'bin'
        _release_fake_gh_for_publish(bin_dir, calls)
        env = os.environ.copy()
        env['PATH'] = str(bin_dir) + os.pathsep + env.get('PATH', '')
        publish = _release_cases().run('publish', '--project', str(project), '--tag', 'v9.9.1', '--version', '9.9.1', '--bump-plugins', 'pr-flow', '--authorize-publish', env=env)
        assert publish.returncode == 0, publish.stdout + publish.stderr
        assert calls.read_text(encoding='utf-8').count('workflow run') == 2
        assert not (project / '.release-flow' / '.gitignore').exists()
        assert not (project / '.release-flow' / 'releases').exists()

    def test_preflight_refreshes_remote_baseline_before_comparing(self, tmp_path: Path) -> None:
        project = tmp_path / 'project'
        remote = tmp_path / 'remote.git'
        _release_init_release_input_project(project, remote)
        old_main = _release_git(project, 'rev-parse', 'origin/main').stdout.strip()
        old_marketplace = _release_git(project, 'rev-parse', 'origin/marketplace').stdout.strip()
        (project / 'plugins' / 'pr-flow' / 'content.txt').write_text('remote\n', encoding='utf-8')
        assert _release_git(project, 'add', 'plugins/pr-flow/content.txt').returncode == 0
        assert _release_git(project, 'commit', '-m', 'remote marketplace content').returncode == 0
        assert _release_git(project, 'push', 'origin', 'HEAD:refs/heads/main').returncode == 0
        assert _release_git(project, 'push', 'origin', 'HEAD:refs/heads/marketplace').returncode == 0
        assert _release_git(project, 'update-ref', 'refs/remotes/origin/main', old_main).returncode == 0
        assert _release_git(project, 'update-ref', 'refs/remotes/origin/marketplace', old_marketplace).returncode == 0
        result = _release_run_cli('preflight', '--project', str(project), '--tag', 'v1.0.0', '--version', '1.0.0', '--bump-plugins', '')
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'status: preflight_passed' in result.stdout

    def test_copy_template_replaces_target_with_readonly_file(self, tmp_path: Path) -> None:
        source = tmp_path / 'source'
        source.mkdir()
        (source / 'new.txt').write_text('new\n', encoding='utf-8')
        target = tmp_path / 'target'
        target.mkdir()
        old = target / 'old-object'
        old.write_text('old\n', encoding='utf-8')
        old.chmod(292)
        copy_template(source, target)
        assert not old.exists()
        assert (target / 'new.txt').read_text(encoding='utf-8') == 'new\n'

    @pytest.mark.parametrize('failure', ['writable', 'other-error', 'directory'])
    def test_copy_template_preserves_unrelated_delete_errors(self, tmp_path: Path, monkeypatch, failure: str) -> None:
        source = tmp_path / 'source'
        source.mkdir()
        target = tmp_path / 'target'
        target.mkdir()
        old = target / 'old-object'
        old.write_text('old\n', encoding='utf-8')
        if failure != 'writable':
            old.chmod(292)
        error = OSError('storage failure') if failure == 'other-error' else PermissionError('blocked')
        operation = os.rmdir if failure == 'directory' else os.unlink

        def fail_rmtree(path, *, onerror=None):
            if onerror is None:
                raise error
            onerror(operation, str(old), (type(error), error, None))
        monkeypatch.setattr(shutil, 'rmtree', fail_rmtree)
        try:
            with pytest.raises(type(error)) as caught:
                copy_template(source, target)
            assert caught.value is error
        finally:
            old.chmod(420)

    @pytest.mark.skipif(sys.platform != 'win32', reason='Windows readonly-file deletion recovery')
    def test_copy_template_preserves_readonly_delete_retry_failure(self, tmp_path: Path, monkeypatch) -> None:
        source = tmp_path / 'source'
        source.mkdir()
        target = tmp_path / 'target'
        target.mkdir()
        old = target / 'old-object'
        old.write_text('old\n', encoding='utf-8')
        old.chmod(292)
        original = PermissionError('readonly')
        retry = PermissionError('retry blocked')

        def fail_unlink(path):
            raise retry

        def fail_rmtree(path, *, onerror=None):
            if onerror is None:
                raise original
            onerror(os.unlink, str(old), (type(original), original, None))
        monkeypatch.setattr(os, 'unlink', fail_unlink)
        monkeypatch.setattr(shutil, 'rmtree', fail_rmtree)
        try:
            with pytest.raises(PermissionError) as caught:
                copy_template(source, target)
            assert caught.value is retry
        finally:
            old.chmod(420)

    def test_release_template_recreates_incomplete_readonly_template(self, tmp_path: Path, monkeypatch) -> None:
        module = sys.modules[__name__]
        monkeypatch.setattr(module, '_RELEASE_TEMPLATE_ROOT', tmp_path / 'templates')
        project = tmp_path / 'project'
        project.mkdir()
        (project / 'source.txt').write_text('source\n', encoding='utf-8')
        remote = tmp_path / 'remote.git'
        template_dir = _RELEASE_TEMPLATE_ROOT / _release_project_tree_cache_key(project)
        template_dir.mkdir(parents=True)
        old = template_dir / 'old-object'
        old.write_text('old\n', encoding='utf-8')
        old.chmod(292)

        def fake_git_command(command, **kwargs):
            if command[0] == 'git' and command[1] == 'init' and ('--bare' in command):
                Path(command[-1]).mkdir()
            return subprocess.CompletedProcess(command, 0, '', '')
        monkeypatch.setattr(subprocess, 'run', fake_git_command)
        initialize_release_template = _release_init_project_with_remote
        initialize_release_template(project, remote)
        assert not old.exists()
        assert (template_dir / '.ready').is_file()
        assert (project / 'source.txt').read_text(encoding='utf-8') == 'source\n'
        assert remote.is_dir()
        assert not (_RELEASE_TEMPLATE_ROOT / f'{template_dir.name}.lock').exists()

    @pytest.mark.parametrize(('changed_field', 'expected_returncode'), [(None, 0), ('url', 1), ('directory', 1)])
    def test_release_workflows_compare_packed_repository_metadata(self, tmp_path: Path, changed_field: str | None, expected_returncode: int) -> None:
        source = {'name': '@liuli195/myspec', 'repository': {'type': 'git', 'url': 'https://github.com/liuli195/my-agent-skills', 'directory': 'plugins/my-spec'}}
        packed = json.loads(json.dumps(source))
        if changed_field:
            packed['repository'][changed_field] = 'changed'
        source_path = tmp_path / 'source.json'
        packed_path = tmp_path / 'packed.json'
        _release_cases().write_json(source_path, source)
        _release_cases().write_json(packed_path, packed)
        for workflow_path in (_release_cases().REPO_ROOT / '.github' / 'workflows' / 'release.yml', _release_cases().REPO_ROOT / 'plugins' / 'release-flow' / 'skills' / 'release-flow' / 'assets' / 'templates' / 'github' / 'workflows' / 'release.yml'):
            workflow = workflow_path.read_text(encoding='utf-8')
            match = re.search('node -e \'([^\']+)\' \\./source/plugins/my-spec/package.json "\\$prefix/lib/node_modules/\\$package_name/package.json" "\\$package_name"', workflow)
            assert match is not None
            result = subprocess.run(['node', '-e', match.group(1), str(source_path), str(packed_path), source['name']], text=True, capture_output=True, check=False)
            assert result.returncode == expected_returncode, result.stderr

    def test_existing_release_must_match_the_current_projection_tree(self, tmp_path: Path, monkeypatch) -> None:
        release_flow = _release_cases().load_release_flow_module()
        project = tmp_path / 'project'
        _release_cases().write_release_flow_files(project)
        config = release_flow.read_config(project)
        projection = release_flow.read_projection(project)
        tree_ids = iter(['expected-tree', 'different-remote-tree'])
        monkeypatch.setattr(release_flow, 'remote_ref_oid', lambda *_args: 'same-commit')
        monkeypatch.setattr(release_flow, 'run_checked', lambda *_args: None)
        monkeypatch.setattr(release_flow, 'copy_git_auth_config', lambda *_args: None)
        monkeypatch.setattr(release_flow, 'origin_url', lambda *_args: 'https://example.invalid/repo.git')
        monkeypatch.setattr(release_flow, 'git_output', lambda *_args: next(tree_ids))
        error = release_flow.existing_release_ref_error(project, config, projection, 'v9.9.1')
        assert error == 'release_projection_mismatch: v9.9.1'

    def test_workflow_package_paths_are_loadable_in_node(self, tmp_path: Path) -> None:
        for workflow_path in (
            _release_cases().REPO_ROOT / ".github/workflows/release.yml",
            _release_cases().REPO_ROOT / "plugins/release-flow/skills/release-flow/assets/templates/github/workflows/release.yml",
        ):
            workflow = workflow_path.read_text(encoding="utf-8")
            for plugin in ("my-spec", "build-and-verify"):
                manifest = f"./source/plugins/{plugin}/package.json"
                assert workflow.count(manifest) == 3
                path = tmp_path / manifest.removeprefix("./")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")
                loaded = subprocess.run(["node", "-e", "require(process.argv[1])", manifest], cwd=tmp_path, text=True, capture_output=True, check=False)
                assert loaded.returncode == 0, loaded.stderr
