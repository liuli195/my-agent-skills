"""Minimal real-workspace smoke, plus the Windows junction adapter."""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import runpy
import subprocess
import sys
import tarfile
import zipfile
from unittest.mock import patch

import pytest

from tests.test_build_and_verify_plugin import (
    REPO_ROOT, command_that_logs, git, run_build_and_verify_subprocess,
    write_runner_config,
)
from tests.test_setup_worktree_script import normalize_powershell_output

SCRIPT = REPO_ROOT / "scripts/setup-worktree.ps1"
PACK = REPO_ROOT / "plugins/tool-lifecycle/pack.py"


def snapshot_source(tmp_path, *, release_ref=None, executable_probe=None):
    project = tmp_path / "source"
    shutil.copytree(REPO_ROOT / "plugins", project / "plugins",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # Detect accidental injection from the packer's own checkout instead of --project.
    shared = project / "plugins/tool-lifecycle/python/management.py"
    shared.write_text(shared.read_text() + "\n# Isolated snapshot source\n")
    if executable_probe and os.name != "nt":
        (project / executable_probe).chmod(0o755)
    for arguments in (("init", "-q"), ("add", "plugins"),
                      ("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                       "commit", "-qm", "snapshot source")):
        subprocess.run(["git", "-C", str(project), *arguments], check=True, capture_output=True)
    if release_ref:
        # Fixture-only tag: this does not verify a real hosted release.
        subprocess.run(["git", "-C", str(project), "tag", release_ref], check=True, capture_output=True)
    origin = subprocess.run(["git", "-C", str(REPO_ROOT), "remote", "get-url", "origin"],
                            check=True, text=True, capture_output=True).stdout.strip()
    subprocess.run(["git", "-C", str(project), "remote", "add", "origin", origin],
                   check=True, capture_output=True)
    return project


def run_snapshots(project, output, *arguments):
    return subprocess.run([sys.executable, str(PACK), "snapshots", str(output),
                           "--project", str(project), *arguments], text=True, capture_output=True)


class TestWorkspace:
    def test_release_snapshots_save_through_real_mapping_and_shared_lock(self, tmp_path):
        from tests.test_release_flow_account_delivery import NativeSaveClients, PublishedReleaseCommands
        probe = "skills/plugin-sync/references/check.md"
        project = snapshot_source(tmp_path, release_ref="v1.0.0", executable_probe="plugins/plugin-sync/" + probe)
        output = tmp_path / "RELEASE"
        result = run_snapshots(project, output, "--account-mode", "RELEASE", "--release-ref", "v1.0.0")
        assert result.returncode == 0, result.stdout + result.stderr
        snapshots = json.loads((output / "snapshots.json").read_text())["plugins"]
        assert len(snapshots) == 9
        commit = subprocess.run(["git", "-C", str(project), "rev-parse", "refs/tags/v1.0.0^{commit}"],
                                check=True, text=True, capture_output=True).stdout.strip()
        shared = (project / "plugins/tool-lifecycle/python/management.py").read_bytes()
        for name, record in snapshots.items():
            package = Path(record["pluginPath"])
            assert record["accountMode"] == "RELEASE" and record["packageName"] == name
            assert record["releaseRef"] == "refs/tags/v1.0.0"
            assert record["sourceCommit"] == commit and record["sourceDirty"] is False
            artifact = output / record["artifact"]
            assert hashlib.sha256(artifact.read_bytes()).hexdigest() == record["sha256"]
            with zipfile.ZipFile(artifact) as archive:
                cloud = json.loads(archive.read(".codex-plugin/plugin.json"))
                assert cloud["name"] == name and cloud["interface"]["displayName"] == name
                assert json.loads(archive.read(".claude-plugin/plugin.json"))["version"] == record["version"]
                assert any(path.endswith("/SKILL.md") for path in archive.namelist())
                if (package / "package.json").exists():
                    assert archive.read("python/management.py") == shared
                    for marketplace in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
                        assert (project / "plugins" / name / marketplace).is_file()
                        assert marketplace not in archive.namelist()
                        assert not (package / marketplace).exists()
        # The one packaged runtime route exercises its included templates, not source assets.
        release = Path(snapshots["release-flow"]["pluginPath"]) / "skills/release-flow/scripts/release_flow.py"
        target = tmp_path / "runtime-project"
        for arguments in (("setup", "--authorize-project-files"), ("validate",)):
            runtime = subprocess.run([sys.executable, str(release), *arguments, "--project", str(target)],
                                     text=True, capture_output=True)
            assert runtime.returncode == 0, runtime.stdout + runtime.stderr
        # Keep one real source-provenance rejection, without rebuilding another fixture.
        note = project / "dirty-note.txt"
        note.write_text("uncommitted source")
        rejected = run_snapshots(project, output, "--account-mode", "RELEASE", "--release-ref", "v1.0.0")
        assert rejected.returncode != 0 and "snapshot_release_source_unverified" in rejected.stderr
        note.unlink()
        bundle = tmp_path / "dot-release-packages.tar"
        with tarfile.open(bundle, "w") as transport:
            transport.add(output, arcname=".")
        bundle.chmod(0o644)
        shutil.rmtree(output)
        delivery = tmp_path / "deliveries"
        delivery.mkdir()
        historical = {"remotePluginId": "Remote_plugin-sync-dev", "packageName": "plugin-sync-dev", "version": "0.0.1"}
        mapping = tmp_path / "mapping.json"
        mapping.write_text(json.dumps({"plugins": {"plugin-sync": {"account": {"DEV": historical, "RELEASE": {}}}}, "preserved": [1, 2]}))
        lock = mapping.with_name(mapping.name + ".lock")
        class Native(NativeSaveClients):
            def request(self, method, params):
                if method != "plugin/share/save":
                    return super().request(method, params)
                self.methods.append(method)
                assert lock.exists()
                source = json.loads(mapping.read_text())["plugins"]["plugin-sync"]["account"]["RELEASE"]
                assert source["saveState"]["status"] == "pending"
                package = Path(params["pluginPath"])
                assert package.parent.parent == delivery
                if os.name != "nt":
                    assert package.parent.stat().st_mode & 0o077 == 0
                    assert (package / probe).stat().st_mode & 0o111 == 0o111
                cloud = json.loads((package / ".codex-plugin/plugin.json").read_text())
                remote_id = params.get("remotePluginId", "Remote_" + cloud["name"])
                self.writes.append((method, dict(params)))
                self.objects = [{"remotePluginId": remote_id, "name": cloud["name"], "version": cloud["version"],
                                 "id": cloud["name"] + "@created-by-me-remote", "installed": False, "enabled": False,
                                 "shareContext": None}]
                return {"remotePluginId": remote_id, "shareUrl": ""}
        native = Native()
        published = PublishedReleaseCommands(project=project,
                                             repository=snapshots["plugin-sync"]["metadataSource"]["repository"],
                                             source_commit=commit, local_run=subprocess.run)
        entry = runpy.run_path(str(REPO_ROOT / "plugins/release-flow/skills/release-flow/scripts/release_flow.py"))["main"]
        process = subprocess.Popen
        def owned_process(command, *args, **kwargs):
            if command == ["codex", "app-server", "--stdio"]:
                return native.start(command, *args, **kwargs)
            assert command == ["git", "-C", str(project), "config", "--get", "remote.origin.url"]
            return process(command, *args, **kwargs)
        def invoke(umask):
            report = io.StringIO()
            args = ["deliver-account", "--project", str(project), "--manifest", str(mapping), "--plugin", "plugin-sync",
                    "--bundle", str(bundle), "--delivery-dir", str(delivery), "--expected-sha256", snapshots["plugin-sync"]["sha256"], "--apply"]
            previous_umask = os.umask(umask) if os.name != "nt" else None
            try:
                with patch("subprocess.Popen", side_effect=owned_process), patch("subprocess.run", side_effect=published), \
                        contextlib.redirect_stdout(report):
                    code = entry(args)
            finally:
                if previous_umask is not None:
                    os.umask(previous_umask)
            assert code == 0, report.getvalue()
            assert not lock.exists() and not list(delivery.iterdir())
            return json.loads(report.getvalue().splitlines()[-1])
        assert invoke(0o077)["operation"] == "create"
        assert native.writes[0][1]["discoverability"] == "PRIVATE" and native.writes[0][1]["shareTargets"] == []
        assert invoke(0o027)["operation"] == "update"
        assert native.writes[-1][1].keys() == {"pluginPath", "remotePluginId"}
        assert native.writes[-1][1]["remotePluginId"] == "Remote_plugin-sync"
        stored = json.loads(mapping.read_text())
        assert stored["preserved"] == [1, 2]
        assert stored["plugins"]["plugin-sync"]["account"]["DEV"] == historical
        source = stored["plugins"]["plugin-sync"]["account"]["RELEASE"]
        assert source["remotePluginId"] == "Remote_plugin-sync" and source["saveState"]["status"] == "verified"
        assert source["saveState"]["privateCreationRequest"] == {"discoverability": "PRIVATE", "shareTargets": []}
        assert source["saveState"]["permissions"]["status"] == "not_available"
        assert len(native.writes) == 2 and not native.objects[0]["installed"]
        assert set(native.methods) <= {"initialize", "plugin/list", "plugin/share/save"}

    def test_public_baseline_execution_cache_and_git_visible_inputs(self, tmp_path):
        primary = tmp_path / "primary"
        primary.mkdir()

        def checked_git(project, *arguments):
            result = git(project, *arguments)
            assert result.returncode == 0, result.stdout + result.stderr
            return result.stdout.strip()

        checked_git(primary, "init", "-q")
        checked_git(primary, "config", "user.name", "Test")
        checked_git(primary, "config", "user.email", "test@example.invalid")
        initialized = run_build_and_verify_subprocess("init", "--project", str(primary))
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        (primary / ".gitignore").write_text("src/ignored.txt\n/run.log\n", encoding="utf-8")
        (primary / "src").mkdir()
        (primary / "src/app.py").write_text("base\n", encoding="utf-8")
        write_runner_config(primary, verify_checks=[
            {"id": "source", "command": command_that_logs("source"),
             "paths": ["src/**"], "inputs": ["src"]},
            {"id": "base-only", "command": command_that_logs("base-only"),
             "paths": ["base-only.txt"]},
        ])
        checked_git(primary, "add", ".")
        checked_git(primary, "commit", "-qm", "base")
        baseline = checked_git(primary, "branch", "--show-current")
        project = tmp_path / "worktree"
        checked_git(primary, "worktree", "add", "-b", "smoke", str(project), "HEAD")
        # The base advances independently: a two-point diff would select base-only.
        (primary / "base-only.txt").write_text("only on base\n", encoding="utf-8")
        checked_git(primary, "add", "base-only.txt")
        checked_git(primary, "commit", "-qm", "advance base")
        source = project / "src/app.py"
        source.write_text("changed\n", encoding="utf-8")
        checked_git(project, "add", "src/app.py")
        checked_git(project, "commit", "-qm", "change source")

        def verify():
            result = run_build_and_verify_subprocess(
                "verify", "--project", str(project), "--base", baseline,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            assert "checked: source" in result.stdout
            assert "base-only" not in result.stdout
            return result.stdout

        assert "status: passed" in verify()
        (project / "src/ignored.txt").write_text("ignored change\n", encoding="utf-8")
        assert "cache-hit: source" in verify()
        source.write_text("visible change\n", encoding="utf-8")
        checked_git(project, "add", "src/app.py")
        checked_git(project, "commit", "-qm", "change visible input")
        assert "cache-hit:" not in verify()
        assert (project / "run.log").read_text().splitlines() == [
            "source", "source",
        ]

    @pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
    def test_setup_worktree_script_links_shared_node_dependencies(self,
        tmp_path: Path
    ) -> None:
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if not shell:
            pytest.skip("PowerShell executable is required")

        project = tmp_path / "project"
        project.mkdir()
        (project / "scripts").mkdir()
        shutil.copy2(SCRIPT, project / "scripts" / SCRIPT.name)
        shutil.copy2(REPO_ROOT / "package.json", project / "package.json")
        shutil.copy2(REPO_ROOT / "package-lock.json", project / "package-lock.json")
        shutil.copy2(REPO_ROOT / "requirements-dev.txt", project / "requirements-dev.txt")
        nested = Path("plugins/data-store/skills/data-store/requirements.txt")
        (project / nested).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / nested, project / nested)

        def run(*args: str, cwd: Path = project) -> subprocess.CompletedProcess[str]:
            return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)

        run("git", "init")
        run("git", "config", "user.email", "test@example.invalid")
        run("git", "config", "user.name", "Test")
        run("git", "add", ".")
        run("git", "commit", "-m", "fixture")

        shared_node_modules = project / "node_modules"
        worktree = project / ".worktrees/test"
        run("git", "worktree", "add", "--detach", str(worktree), "HEAD")
        shared_venv = project / ".venv"
        shared_python = shared_venv / "Scripts/python.exe"
        requirements = (project / "requirements-dev.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
        fingerprint = hashlib.sha256(requirements.encode()).hexdigest().upper()

        npm_marker = project / "npm-called"
        py_marker = project / "py-called"
        fake_bin = project / "fake-bin"
        fake_bin.mkdir()
        (fake_bin / "npm.cmd").write_text(
            f'@echo called>>"{npm_marker}"\n@exit /b 99\n', encoding="utf-8"
        )
        (fake_bin / "py.cmd").write_text(
            f'@echo called>>"{py_marker}"\n@exit /b 99\n', encoding="utf-8"
        )
        env = os.environ | {"PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}
        command = [shell, "-NoProfile", "-File", str(worktree / "scripts/setup-worktree.ps1")]

        def setup(*, check: bool = False) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                command,
                cwd=worktree,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=check,
            )

        shared_node_modules.mkdir()
        node_fingerprint = "\n".join(
            f"{hashlib.sha256((project / manifest).read_text(encoding='utf-8').replace(chr(13) + chr(10), chr(10)).encode()).hexdigest().upper()} {manifest}"
            for manifest in ("package.json", "package-lock.json")
        )
        (shared_node_modules / ".package-lock.sha256").write_text(node_fingerprint + "\n", encoding="ascii")
        shared_python.parent.mkdir(parents=True)
        shared_python.touch()
        (shared_venv / ".requirements.sha256").write_text(
            f"{fingerprint} requirements-dev.txt\n" + hashlib.sha256((project / nested).read_text().replace("\r\n", "\n").encode()).hexdigest().upper() + f" {nested.as_posix()}\n", encoding="ascii"
        )
        setup(check=True)

        link = worktree / "node_modules"
        assert link.is_junction()
        assert link.resolve() == shared_node_modules.resolve()
        venv_link = worktree / ".venv"
        assert venv_link.is_junction()
        assert venv_link.resolve() == shared_venv.resolve()
        assert not npm_marker.exists()
        assert not py_marker.exists()
