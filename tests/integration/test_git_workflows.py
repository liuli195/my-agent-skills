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
import pytest


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
    @pytest.mark.parametrize("external_link", [False, True])
    def test_projects_refreshes_remote_preflight_and_dispatches_release(self, tmp_path: Path, external_link) -> None:
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
        if external_link:
            if os.name == "nt":
                pytest.skip("file symlinks require explicit Windows host privileges")
            outside = tmp_path / "external-content.txt"
            outside.write_text("existing ordinary project content\n", encoding="utf-8")
            (project / "linked.txt").symlink_to(outside)
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
        bin_dir, calls_path = _pr_write_fake_gh_sequence(tmp_path / "publish-bin", [{}, {}])
        published = invoke("publish", "--tag", "v9.9.1", "--version", "9.9.1", "--bump-plugins", "pr-flow",
                           "--authorize-publish", env=environment | {
                               "PATH": str(bin_dir) + os.pathsep + environment.get("PATH", "")})
        assert published.returncode == 0, published.stdout + published.stderr
        assert json.loads(calls_path.read_text(encoding="utf-8")) == [[
            "workflow", "run", ".github/workflows/release.yml", "--ref", "main",
            "-f", "tag=v9.9.1", "-f", "version=9.9.1", "-f", "bumpPlugins=pr-flow"]]
        assert not (project / ".release-flow/releases").exists()

        published_ci = invoke("ci-publish", "--tag", "v9.9.1", "--version", "9.9.1", "--bump-plugins", "",
                              "--authorize-ci-publish", env=environment | {
                                  "PATH": str(bin_dir) + os.pathsep + environment.get("PATH", "")})
        assert published_ci.returncode == 0, published_ci.stdout + published_ci.stderr
        assert "status: ci_published" in published_ci.stdout
        if external_link:
            checkout = tmp_path / "ordinary-checkout"
            _git(tmp_path, "clone", "--branch", "marketplace", str(remote), str(checkout))
            assert (checkout / "linked.txt").read_text(encoding="utf-8") == "existing ordinary project content\n"

    @pytest.mark.parametrize("fault", [None, "missing-shared", "wrong-package", "escaped-shared", "escaped-target"])
    def test_formal_marketplace_command_tools_run_without_sibling_plugins(self, tmp_path: Path, monkeypatch, fault) -> None:
        cases = importlib.import_module("tests.test_release_flow_cli")
        project = tmp_path / "source"
        cases.write_release_flow_files(project, cases.marketplace_identity_projection().replace("      - pr-flow\n      - release-flow", "      - my-spec\n      - build-and-verify"))
        for plugin in ("my-spec", "build-and-verify", "tool-lifecycle"):
            shutil.copytree(cases.REPO_ROOT / "plugins" / plugin, project / "plugins" / plugin,
                            ignore=shutil.ignore_patterns("__pycache__"))
        _git(project, "init", "--initial-branch=main")
        _git(project, "config", "user.email", "test@example.invalid")
        _git(project, "config", "user.name", "Test")
        _git(project, "add", ".")
        _git(project, "commit", "-m", "source")
        # Public projection remains safe to run in-place: source wrappers stay wrappers.
        wrappers = {name: (project / "plugins" / name / "python/management.py").read_bytes()
                    for name in ("my-spec", "build-and-verify")}
        projected = subprocess.run([sys.executable, str(cases.SCRIPT), "project", "--project", str(project)],
                                   env=os.environ | {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "liuli195/my-agent-skills"},
                                   text=True, capture_output=True)
        assert projected.returncode == 0, projected.stdout + projected.stderr
        assert all((project / "plugins" / name / "python/management.py").read_bytes() == content
                   for name, content in wrappers.items())
        _git(project, "add", ".")
        _git(project, "commit", "-m", "project metadata")
        remote = tmp_path / "remote.git"
        _git(tmp_path, "init", "--bare", str(remote))
        _git(project, "remote", "add", "origin", str(remote))
        _git(project, "push", "origin", "HEAD:refs/heads/marketplace")
        current_versions = [
            tuple(map(int, json.loads((project / "plugins" / plugin / "package.json").read_text(encoding="utf-8"))["version"].split(".")))
            for plugin in ("my-spec", "build-and-verify")
        ]
        major, minor, patch = max(current_versions)
        version = f"{major}.{minor}.{patch + 1}"
        tag = f"v{version}"
        for plugin in ("my-spec", "build-and-verify"):
            for relative in ("package.json", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
                manifest = project / "plugins" / plugin / relative
                metadata = json.loads(manifest.read_text(encoding="utf-8"))
                metadata["version"] = version
                manifest.write_text(json.dumps(metadata), encoding="utf-8")
        _git(project, "add", ".")
        _git(project, "commit", "-m", "advance selected tools")
        _git(project, "push", "origin", "HEAD:refs/heads/main")
        before = _git(project, "status", "--porcelain")
        bin_dir, _calls = _pr_write_fake_gh_sequence(tmp_path / "gh-bin", [
            {"stdout": f"https://example.invalid/release/{tag}\n"},
            {"stdout": f"https://example.invalid/release/{tag}\n"}])
        monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        environment = os.environ | {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "liuli195/my-agent-skills"}
        command = [sys.executable, str(cases.SCRIPT), "ci-publish", "--project", str(project),
                   "--tag", tag, "--version", version, "--bump-plugins", "my-spec,build-and-verify",
                   "--authorize-ci-publish"]
        if fault:
            if fault == "missing-shared":
                (project / "plugins/tool-lifecycle/python/management.py").unlink()
            elif fault == "wrong-package":
                path = project / "plugins/my-spec/package.json"
                value = json.loads(path.read_text(encoding="utf-8"))
                value["name"] = "@other/incorrect"
                path.write_text(json.dumps(value), encoding="utf-8")
            else:
                if os.name == "nt":
                    pytest.skip("directory symlinks require explicit Windows host privileges")
                outside = tmp_path / "outside.py"
                outside.write_text("# outside source\n", encoding="utf-8")
                path = project / ("plugins/tool-lifecycle/python/management.py" if fault == "escaped-shared"
                                  else "plugins/my-spec/python/management.py")
                path.unlink()
                path.symlink_to(outside)
            channel = _git(project, "ls-remote", "origin", "refs/heads/marketplace")
            refused = subprocess.run(command, env=environment, text=True, capture_output=True)
            assert refused.returncode == 1, refused.stdout + refused.stderr
            assert _git(project, "ls-remote", "origin", "refs/heads/marketplace") == channel
            assert not _git(project, "ls-remote", "origin", f"refs/tags/{tag}")
            assert json.loads(_calls.read_text(encoding="utf-8")) == []
            return
        for _attempt in range(2):
            published = subprocess.run(command, env=environment, text=True, capture_output=True)
            assert published.returncode == 0, published.stdout + published.stderr
            assert "status: ci_published" in published.stdout
        checkout = tmp_path / "checkout"
        _git(tmp_path, "clone", "--branch", "marketplace", str(remote), str(checkout))
        for plugin, command in (("my-spec", "myspec"), ("build-and-verify", "build-and-verify")):
            isolated = tmp_path / plugin
            shutil.copytree(checkout / "plugins" / plugin, isolated)
            result = subprocess.run(["node", str(isolated / "bin" / f"{command}.js"), "--help"],
                                    cwd=tmp_path, text=True, capture_output=True)
            assert result.returncode == 0, result.stdout + result.stderr
            home = tmp_path / "home"
            home.mkdir(exist_ok=True)
            environment = os.environ | {"HOME": str(home), "USERPROFILE": str(home),
                "MYSPEC_PYTHON": sys.executable, "BUILD_AND_VERIFY_PYTHON": sys.executable}
            cli = ["node", str(isolated / "bin" / f"{command}.js")]
            diagnosed = subprocess.run([*cli, "doctor", "--running"], cwd=tmp_path, env=environment,
                                       text=True, capture_output=True)
            assert diagnosed.returncode == 0, diagnosed.stdout + diagnosed.stderr
            report = json.loads(diagnosed.stdout)
            assert report["mode"] == "release"
            assert report["runtime"]["packageRoot"] == str(isolated)
            consumer = tmp_path / (plugin + "-consumer")
            if plugin == "my-spec":
                from tests.support.myspec_cases import main_spec, requirement
                specs = consumer / "specs/accounts"
                specs.mkdir(parents=True)
                (specs / "spec.md").write_text(main_spec("accounts", requirement("Login", "allow login")), encoding="utf-8")
                validated = subprocess.run([*cli, "validate-main", str(specs.parent)], cwd=tmp_path,
                                           env=environment, text=True, capture_output=True)
                assert validated.returncode == 0, validated.stdout + validated.stderr
            else:
                initialized = subprocess.run([*cli, "init", "--project", str(consumer)], cwd=tmp_path,
                                             env=environment, text=True, capture_output=True)
                assert initialized.returncode == 0, initialized.stdout + initialized.stderr
                config = consumer / ".build-and-verify/config.json"
                config.write_text(json.dumps({"version": 2, "build": {"checks": [
                    {"id": "formal-build", "command": [sys.executable, "-c", "print('FORMAL_BUILD_OK')"]}]},
                    "verify": {"checks": [], "realChecks": []}}), encoding="utf-8")
                built = subprocess.run([*cli, "build", "--project", str(consumer)], cwd=tmp_path,
                                       env=environment, text=True, capture_output=True)
                assert built.returncode == 0, built.stdout + built.stderr
                assert "FORMAL_BUILD_OK" in built.stdout and "checked: formal-build" in built.stdout
        assert _git(project, "status", "--porcelain") == before

    def test_preflight_requires_bump_for_legacy_unassembled_command_tool(self, tmp_path: Path) -> None:
        cases = importlib.import_module("tests.test_release_flow_cli")
        project = tmp_path / "source"
        cases.write_release_flow_files(project, cases.marketplace_identity_projection().replace("      - pr-flow\n      - release-flow", "      - my-spec\n      - build-and-verify"))
        for plugin in ("my-spec", "build-and-verify", "tool-lifecycle"):
            shutil.copytree(cases.REPO_ROOT / "plugins" / plugin, project / "plugins" / plugin,
                            ignore=shutil.ignore_patterns("__pycache__"))
        (project / ".gitattributes").write_text("*.py text eol=lf\n", encoding="utf-8")
        _git(project, "init", "--initial-branch=main")
        _git(project, "config", "user.email", "test@example.invalid")
        _git(project, "config", "user.name", "Test")
        _git(project, "add", ".")
        _git(project, "commit", "-m", "legacy marketplace")
        remote = tmp_path / "remote.git"
        _git(tmp_path, "init", "--bare", str(remote))
        _git(project, "remote", "add", "origin", str(remote))
        for branch in ("main", "marketplace"):
            _git(project, "push", "origin", f"HEAD:refs/heads/{branch}")
        result = subprocess.run([sys.executable, str(cases.SCRIPT), "preflight", "--project", str(project),
                                 "--tag", "v9.9.1", "--version", "9.9.1", "--bump-plugins", ""],
                                text=True, capture_output=True)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "plugin_requires_bump: my-spec" in result.stdout
        assert "plugin_requires_bump: build-and-verify" in result.stdout
        # A real assembled orphan channel is the baseline, not a reassembled channel.
        flow = cases.load_release_flow_module()
        released = tmp_path / "released"
        shutil.copytree(project, released, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        flow.prepare_formal_release_tree(released, flow.read_projection(released))
        _git(released, "init", "--initial-branch=marketplace")
        _git(released, "config", "user.email", "test@example.invalid")
        _git(released, "config", "user.name", "Test")
        _git(released, "add", ".")
        _git(released, "commit", "-m", "assembled marketplace")
        _git(released, "remote", "add", "origin", str(remote))
        _git(released, "push", "--force", "origin", "HEAD:refs/heads/marketplace")

        def preflight():
            return subprocess.run([sys.executable, str(cases.SCRIPT), "preflight", "--project", str(project),
                                   "--tag", "v9.9.1", "--version", "9.9.1", "--bump-plugins", ""],
                                  text=True, capture_output=True)

        healthy = preflight()
        assert healthy.returncode == 0, healthy.stdout + healthy.stderr
        shared = project / "plugins/tool-lifecycle/python/management.py"
        original = shared.read_bytes()
        shared.write_bytes(original.replace(b"\n", b"\r\n"))
        normalized = preflight()
        assert normalized.returncode == 0, normalized.stdout + normalized.stderr

        # Real source changes and wrapper drift cannot hide behind the injection rule.
        shared.write_bytes(original + b"\n# changed implementation\n")
        changed = preflight()
        assert "plugin_requires_bump: my-spec" in changed.stdout
        shared.write_bytes(original)
        wrapper = project / "plugins/my-spec/python/management.py"
        wrapper_bytes = wrapper.read_bytes()
        wrapper.write_bytes(wrapper_bytes + b"\n# source drift\n")
        changed = preflight()
        assert "plugin_requires_bump: my-spec" in changed.stdout
        wrapper.write_bytes(wrapper_bytes)
        bundled = released / "plugins/my-spec/python/management.py"
        bundled.write_bytes(original + b"\n# corrupt released implementation\n")
        _git(released, "add", ".")
        _git(released, "commit", "-m", "corrupt bundled management")
        _git(released, "push", "origin", "HEAD:refs/heads/marketplace")
        corrupted = preflight()
        assert "plugin_requires_bump: my-spec" in corrupted.stdout
        bundled.write_bytes(original)
        if os.name != "nt":
            bundled.chmod(0o755)
            _git(released, "add", ".")
            _git(released, "commit", "-m", "change published executable mode")
            _git(released, "push", "origin", "HEAD:refs/heads/marketplace")
            wrong_mode = preflight()
            assert "plugin_requires_bump: my-spec" in wrong_mode.stdout
            bundled.chmod(0o644)
        _git(released, "add", ".")
        _git(released, "commit", "-m", "restore bundled management")
        _git(released, "push", "origin", "HEAD:refs/heads/marketplace")
        restored = preflight()
        assert restored.returncode == 0, restored.stdout + restored.stderr
        if os.name != "nt":
            _git(project, "config", "core.filemode", "false")
            shared.chmod(0o755)
            changed_mode = preflight()
            assert "plugin_requires_bump: my-spec" in changed_mode.stdout
            shared.chmod(0o644)
        shared.write_bytes(original.replace(b"\n", b"\r\n"))
        # Current and channel agree, but source-ref attributes still produce LF.
        attributes = "*.py text eol=lf\nplugins/my-spec/python/management.py -text\nplugins/build-and-verify/python/management.py -text\n"
        (project / ".gitattributes").write_text(attributes, encoding="utf-8")
        (released / ".gitattributes").write_text(attributes, encoding="utf-8")
        for plugin in ("my-spec", "build-and-verify"):
            (released / "plugins" / plugin / "python/management.py").write_bytes(original.replace(b"\n", b"\r\n"))
        _git(released, "add", ".")
        _git(released, "commit", "-m", "destination-specific attributes")
        _git(released, "push", "origin", "HEAD:refs/heads/marketplace")
        drifted = preflight()
        assert drifted.returncode == 1, drifted.stdout + drifted.stderr
        assert "plugin_requires_bump: my-spec" in drifted.stdout
        # A ref's shared checkout conversion happens before its destination conversion.
        (project / ".gitattributes").write_text(
            attributes + "plugins/tool-lifecycle/python/management.py text eol=crlf\n", encoding="utf-8")
        _git(project, "add", ".gitattributes")
        _git(project, "commit", "-m", "source-specific checkout attributes")
        _git(project, "push", "origin", "HEAD:refs/heads/main")
        checkout_normalized = preflight()
        assert checkout_normalized.returncode == 0, checkout_normalized.stdout + checkout_normalized.stderr
