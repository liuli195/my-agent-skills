"""One healthy public-command sequence per Git workflow.

Failure decisions live in the ordinary in-memory command contracts. These two
smokes retain real installed paths, Git repositories, subprocesses and remotes.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import yaml


def _git(project: Path, *arguments: str) -> str:
    result = subprocess.run(["git", *arguments], cwd=project, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


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

def _pr_write_toolchain_cli(bin_dir: Path, reports: dict[str, dict[str, object]]) -> None:
    bin_dir.mkdir()
    for command, report in reports.items():
        script = bin_dir / f"{command}.py"
        script.write_text(f"import json\nprint(json.dumps({report!r}))\n", encoding="utf-8")
        if os.name == "nt":
            (bin_dir / f"{command}.cmd").write_text(
                f'@echo off\n"{sys.executable}" "%~dp0{command}.py" %*\n', encoding="utf-8")
        else:
            launcher = bin_dir / command
            launcher.write_text(
                f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/{command}.py" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)


class TestPrFlow:
    def test_installed_workflow_syncs_and_completes_independent_worktrees(self, tmp_path: Path) -> None:
        cases = importlib.import_module("tests.test_pr_flow_cli")
        installed = tmp_path / "installed cache" / "pr-flow"
        shutil.copytree(cases.SCRIPT.parents[3], installed, ignore=shutil.ignore_patterns("__pycache__"))
        script = installed / "skills/pr-flow/scripts/pr_flow.py"
        project = tmp_path / "external project"
        project.mkdir()
        _git(project, "init", "--initial-branch=main")
        _git(project, "config", "user.email", "test@example.invalid")
        _git(project, "config", "user.name", "Test")
        config = tmp_path / "confirmed.yaml"
        draft = cases.default_pr_flow_config_for_test()
        config.write_text(yaml.safe_dump(draft, sort_keys=False), encoding="utf-8")
        tools = tmp_path / "tools"
        reports = {name: {"toolchain": {"mode": "release", "packageName": package,
                   "packageVersion": "1.2.3"}}
                   for name, package in (("myspec", "@liuli195/myspec"),
                                         ("build-and-verify", "@liuli195/build-and-verify"))}
        _pr_write_toolchain_cli(tools, reports)
        environment = os.environ | {"PATH": str(tools) + os.pathsep + os.environ.get("PATH", "")}

        def invoke(*arguments: str, env=environment):
            return subprocess.run([sys.executable, str(script), *arguments], cwd=project,
                                  env=env, text=True, capture_output=True)

        initialized = invoke("init", "--project", str(project), "--config", str(config))
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        assert not (installed / ".pr-flow").exists()
        _git(project, "add", ".")
        _git(project, "commit", "-m", "baseline")
        workflow = project / ".github/workflows/pr-flow-toolchain.yml"
        workflow.write_text("stale\n", encoding="utf-8")
        _git(project, "add", ".github/workflows/pr-flow-toolchain.yml")
        _git(project, "commit", "-m", "stale managed workflow")
        stop_bin, _ = _pr_write_fake_gh_sequence(tmp_path / "sync-bin", [{"exit_code": 99}])
        stopped = invoke("complete", "--project", str(project), "--summary", "sync", "--scope", "test",
                         env=environment | {"PATH": str(stop_bin) + os.pathsep + environment["PATH"]})
        assert stopped.returncode == 1, stopped.stdout + stopped.stderr
        assert _git(project, "show", "--format=", "--name-only", "HEAD").splitlines() == [
            ".github/workflows/pr-flow-toolchain.yml"]
        assert "@liuli195/myspec@1.2.3" in workflow.read_text(encoding="utf-8")
        assert _git(project, "diff", "--cached", "--name-only") == ""

        remote = tmp_path / "remote.git"
        _git(tmp_path, "init", "--bare", str(remote))
        _git(project, "remote", "add", "origin", str(remote))
        _git(project, "push", "-u", "origin", "main")
        baseline = _git(project, "rev-parse", "HEAD")
        _git(project, "checkout", "-b", "feature/one")
        _git(project, "push", "-u", "origin", "feature/one")
        second = tmp_path / "second worktree"
        _git(project, "worktree", "add", "-b", "feature/two", str(second), "main")
        _git(second, "push", "-u", "origin", "feature/two")
        processes = []
        try:
            for number, (target, branch) in enumerate(((project, "feature/one"), (second, "feature/two")), 11):
                pr = json.loads(cases.pr_view_json(checks=[{"name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"}],
                                review_decision="APPROVED", head_oid=baseline, base_oid=baseline))
                pr.update(number=number, headRefName=branch)
                snapshot = {"stdout": json.dumps(pr)}
                passed = {"stdout": json.dumps([{"bucket": "pass", "name": "ci", "state": "SUCCESS"}])}
                cleanup_pr = json.loads(cases.cleanup_pr_view_json(head_ref=branch))
                cleanup_pr["number"] = number
                cleanup = {"stdout": json.dumps(cleanup_pr)}
                bin_dir, _ = _pr_write_fake_gh_sequence(tmp_path / f"gh-{number}",
                    [snapshot, snapshot, passed, snapshot, passed, snapshot, {}, cleanup])
                env = environment | {"PATH": str(bin_dir) + os.pathsep + environment["PATH"]}
                processes.append(subprocess.Popen([sys.executable, str(script), "complete", "--project", str(target),
                    "--summary", "parallel worktree", "--scope", "test"], cwd=tmp_path, env=env,
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            for process in processes:
                stdout, stderr = process.communicate(timeout=30)
                assert process.returncode == 0, stdout + stderr
                assert "cleanup_complete" in stdout
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate()
        assert {_git(target, "branch", "--show-current") for target in (project, second)} == {"", "main"}
        for target, branch in ((project, "feature/one"), (second, "feature/two")):
            assert _git(target, "rev-parse", "HEAD") == baseline
            status = json.loads((target / ".pr-flow/last-status.json").read_text(encoding="utf-8"))
            assert status["status"] == "cleanup_complete"
            assert Path(status["details"]["worktreePath"]) == target.resolve()
            assert status["details"]["sourceBranch"] == branch
            run = target / ".pr-flow/runs" / f"{hashlib.sha256(branch.encode()).hexdigest()}.json"
            assert json.loads(run.read_text(encoding="utf-8")) == status


class TestReleaseFlow:
    def test_projects_refreshes_remote_preflight_and_dispatches_release(self, tmp_path: Path) -> None:
        cases = importlib.import_module("tests.test_release_flow_cli")
        project = tmp_path / "project"
        environment = os.environ | {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "liuli195/my-agent-skills"}

        def invoke(*arguments: str, env=environment):
            return subprocess.run([sys.executable, str(cases.SCRIPT), *arguments, "--project", str(project)],
                                  cwd=tmp_path, env=env, text=True, capture_output=True)

        setup = invoke("setup", "--authorize-project-files")
        assert setup.returncode == 0, setup.stdout + setup.stderr
        assert (project / ".github/workflows/release.yml").is_file()
        cases.write_release_flow_files(project)
        for plugin in ("pr-flow", "release-flow"):
            cases.write_plugin_manifests(project, plugin, "9.9.1")
        projected = invoke("project")
        assert projected.returncode == 0, projected.stdout + projected.stderr
        catalog = json.loads((project / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
        assert {plugin["name"] for plugin in catalog["plugins"]} == {"pr-flow", "release-flow"}
        assert catalog["name"] == "my-agent-skills-marketplace"
        _git(project, "init", "--initial-branch=main")
        _git(project, "config", "user.email", "test@example.invalid")
        _git(project, "config", "user.name", "Test")
        _git(project, "add", ".")
        _git(project, "commit", "-m", "baseline")
        baseline = _git(project, "rev-parse", "HEAD")
        remote = tmp_path / "remote.git"
        _git(tmp_path, "init", "--bare", str(remote))
        _git(project, "remote", "add", "origin", str(remote))
        for branch in ("main", "marketplace"):
            _git(project, "push", "origin", f"HEAD:refs/heads/{branch}")
        content = project / "plugins/pr-flow/content.txt"
        content.write_text("remote content\n", encoding="utf-8")
        _git(project, "add", "plugins/pr-flow/content.txt")
        _git(project, "commit", "-m", "remote baseline")
        current = _git(project, "rev-parse", "HEAD")
        for branch in ("main", "marketplace"):
            _git(project, "push", "origin", f"HEAD:refs/heads/{branch}")
            _git(project, "update-ref", f"refs/remotes/origin/{branch}", baseline)
        preflight = invoke("preflight", "--tag", "v9.9.1", "--version", "9.9.1", "--bump-plugins", "")
        assert preflight.returncode == 0, preflight.stdout + preflight.stderr
        assert "preflight_passed" in preflight.stdout
        for branch in ("main", "marketplace"):
            assert _git(project, "rev-parse", f"origin/{branch}") == current
        bin_dir, calls_path = _pr_write_fake_gh_sequence(tmp_path / "publish-bin", [{}])
        published = invoke("publish", "--tag", "v9.9.1", "--version", "9.9.1", "--bump-plugins", "pr-flow",
                           "--authorize-publish", env=environment | {
                               "PATH": str(bin_dir) + os.pathsep + environment.get("PATH", "")})
        assert published.returncode == 0, published.stdout + published.stderr
        assert json.loads(calls_path.read_text(encoding="utf-8")) == [[
            "workflow", "run", ".github/workflows/release.yml", "--ref", "main",
            "-f", "tag=v9.9.1", "-f", "version=9.9.1", "-f", "bumpPlugins=pr-flow"]]
        assert not (project / ".release-flow/releases").exists()
