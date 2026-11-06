"""Minimal real-workspace smoke, plus the Windows junction adapter."""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import runpy
import tempfile
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


def snapshot_source(tmp_path, *, legacy_registry=False, release_ref=None, executable_probe=None):
    project = tmp_path / "source"
    shutil.copytree(REPO_ROOT / "plugins", project / "plugins",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if legacy_registry:
        registry = project / "plugins/release-flow/skills/release-flow/scripts/release_flow.py"
        registry.write_text("".join(line for line in registry.read_text().splitlines(keepends=True)
                                    if '"commandTool":' not in line))
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
        with tempfile.TemporaryDirectory(dir=tmp_path) as temporary:
            root = Path(temporary)
            probe = "skills/plugin-sync/references/check.md"
            project = snapshot_source(root, release_ref="v1.0.0", executable_probe="plugins/plugin-sync/" + probe)
            output = root / "RELEASE"
            result = run_snapshots(project, output, "--account-mode", "RELEASE", "--release-ref", "v1.0.0")
            assert result.returncode == 0, result.stdout + result.stderr
            snapshots = json.loads((output / "snapshots.json").read_text())["plugins"]
            commit = subprocess.run(["git", "-C", str(project), "rev-parse", "refs/tags/v1.0.0^{commit}"],
                                    check=True, text=True, capture_output=True).stdout.strip()
            for name, record in snapshots.items():
                package = Path(record["pluginPath"])
                assert record["accountMode"] == "RELEASE"
                assert record["packageName"] == name
                assert record["releaseRef"] == "refs/tags/v1.0.0"
                assert record["sourceCommit"] == commit and record["sourceDirty"] is False
                cloud = json.loads((package / ".codex-plugin/plugin.json").read_text())
                assert cloud["name"] == name and cloud["interface"]["displayName"] == name
                assert json.loads((package / ".claude-plugin/plugin.json").read_text())["name"] == name
                assert json.loads((project / "plugins" / name / ".codex-plugin/plugin.json").read_text())["name"] == name
                if (package / "package.json").exists():
                    assert json.loads((package / "package.json").read_text())["name"] == json.loads((project / "plugins" / name / "package.json").read_text())["name"]
            reused = run_snapshots(project, output, "--account-mode", "RELEASE", "--release-ref", "refs/tags/v1.0.0")
            assert reused.returncode == 0, reused.stderr
            assert json.loads(reused.stdout)["built"] == []
            # One tar transports hidden metadata and executable modes without repairing ZIP contents.
            bundle = root / "dot-release-packages.tar"
            with tarfile.open(bundle, "w") as transport:
                transport.add(output, arcname=".")
            bundle.chmod(0o644)  # Simulate the outer CI artifact's ordinary file permissions.
            shutil.rmtree(output)
            delivery = root / "deliveries"
            delivery.mkdir()
            historical = {"remotePluginId": "Remote_plugin-sync-dev", "packageName": "plugin-sync-dev", "version": "0.0.1"}
            historical_object = {**historical, "name": "plugin-sync-dev", "id": "plugin-sync-dev@created-by-me-remote",
                                 "installed": False, "enabled": False, "shareContext": None}
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"plugins": {"plugin-sync": {"account": {"DEV": historical, "RELEASE": {}}}}, "preserved": [1, 2]}))
            lock = root / "mapping.json.lock"
            class Native(NativeSaveClients):
                def request(self, method, params):
                    if method != "plugin/share/save":
                        return super().request(method, params)
                    self.methods.append(method)
                    assert lock.exists()
                    stored = json.loads(mapping.read_text())["plugins"]
                    assert any(item.get("saveState", {}).get("status") == "pending"
                               for plugin in stored.values() for item in plugin["account"].values())
                    package = Path(params["pluginPath"])
                    assert package.parent.parent == delivery
                    if os.name != "nt":
                        assert package.parent.stat().st_mode & 0o077 == 0
                        if package.name == Path(snapshots["plugin-sync"]["artifact"]).stem:
                            assert (package / probe).stat().st_mode & 0o111 == 0o111
                    cloud = json.loads((package / ".codex-plugin/plugin.json").read_text())
                    remote_id = params.get("remotePluginId", "Remote_" + cloud["name"])
                    self.writes.append((method, dict(params)))
                    self.objects = [item for item in self.objects if item["remotePluginId"] != remote_id]
                    self.objects.append({"remotePluginId": remote_id, "name": cloud["name"], "version": cloud["version"],
                                         "id": cloud["name"] + "@created-by-me-remote", "installed": False, "enabled": False,
                                         "shareContext": {"remotePluginId": remote_id, "discoverability": "PRIVATE", "sharePrincipals": []}})
                    return {"remotePluginId": remote_id, "shareUrl": ""}
            native = Native()
            native.objects = [historical_object]
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
            def invoke(mode="RELEASE", *, apply=True, action="save-account", timeout="1", plugin="plugin-sync", umask=None, bundle_path=None):
                report = io.StringIO()
                command = "deliver-account" if action == "save-account" else "reconcile-account"
                args = [command, "--project", str(project), "--manifest", str(mapping), "--plugin", plugin, "--timeout", timeout]
                if action == "save-account":
                    args.extend(["--bundle", str(bundle_path or bundle), "--delivery-dir", str(delivery), "--expected-sha256", snapshots[plugin]["sha256"]])
                if action == "reconcile-account":
                    args.extend(["--mode", mode])
                elif mode != "RELEASE":
                    args.extend(["--mode", mode])
                previous_umask = os.umask(umask) if os.name != "nt" and umask is not None else None
                try:
                    with patch("subprocess.Popen", side_effect=owned_process), patch("subprocess.run", side_effect=published), \
                            contextlib.redirect_stdout(report):
                        code = entry(args + (["--apply"] if apply else []))
                finally:
                    if previous_umask is not None:
                        os.umask(previous_umask)
                assert set(native.methods) <= {"initialize", "plugin/list", "plugin/share/save"}
                return code, [json.loads(line) for line in report.getvalue().splitlines()]
            original = mapping.read_bytes()
            for member_name, member_type in (("../escaped.txt", tarfile.REGTYPE), ("linked", tarfile.SYMTYPE)):
                unsafe = root / "unsafe.tar"
                member = tarfile.TarInfo(member_name)
                member.type = member_type
                member.linkname = "../escaped.txt"
                with tarfile.open(unsafe, "w") as transport:
                    transport.addfile(member)
                code, events = invoke(bundle_path=unsafe)
                assert code == 1 and events[-1]["status"] == "blocked"
                assert "unsafe path or file type" in events[-1]["error"]
                assert native.starts == 0 and not native.writes
                assert mapping.read_bytes() == original and not (root / "escaped.txt").exists()
                assert not list(delivery.iterdir()) and not lock.exists()
            assert invoke(apply=False)[0] == 0
            assert mapping.read_bytes() == original
            assert not list(delivery.iterdir())
            assert invoke(umask=0o077)[0] == 0
            assert not list(delivery.iterdir())
            stored = json.loads(mapping.read_text())
            assert stored["preserved"] == [1, 2]
            assert stored["plugins"]["plugin-sync"]["account"]["DEV"] == historical
            assert stored["plugins"]["plugin-sync"]["account"]["RELEASE"]["packageName"] == "plugin-sync"
            assert len(native.objects) == 2 and all(not item["installed"] for item in native.objects)
            assert native.objects[0] == historical_object
            code, events = invoke(umask=0o027)
            assert code == 0 and events[-1]["operation"] == "update"
            request = native.writes[-1][1]
            assert set(request) == {"pluginPath", "remotePluginId"} and request["remotePluginId"] == "Remote_plugin-sync"
            assert Path(request["pluginPath"]).name == Path(snapshots["plugin-sync"]["artifact"]).stem
            assert not Path(request["pluginPath"]).exists() and not list(delivery.iterdir())
            updated = json.loads(mapping.read_text())["plugins"]["plugin-sync"]["account"]["RELEASE"]["saveState"]
            assert updated["privateCreationRequest"] == {"discoverability": "PRIVATE", "shareTargets": []}
            assert updated["permissions"]["status"] == "not_available"
            assert updated["snapshot"]["releaseRef"] == "refs/tags/v1.0.0"
            original = mapping.read_bytes()
            count = len(native.writes)
            with pytest.raises(SystemExit) as error, contextlib.redirect_stderr(io.StringIO()):
                invoke("DEV")
            assert error.value.code == 2
            assert mapping.read_bytes() == original and len(native.writes) == count
            native.personal = False
            native.catalog_metadata = {"scope": "WORKSPACE"}
            code, events = invoke()
            assert code == 1 and "not personal USER" in events[-1]["error"]
            assert mapping.read_bytes() == original and len(native.writes) == count
            assert len(native.objects) == 2
            native.personal = True
            native.catalog_metadata = {}
            legacy = json.loads(mapping.read_text())
            state = legacy["plugins"]["plugin-sync"]["account"]["RELEASE"]["saveState"]
            state["status"] = "unverified"
            state.pop("privateCreationRequest", None)
            state.pop("responseSchemaVerified")
            state["snapshot"].pop("releaseRef")
            mapping.write_text(json.dumps(legacy))
            original = mapping.read_bytes()
            count = len(native.writes)
            assert invoke(action="reconcile-account", apply=False)[0] == 0
            assert mapping.read_bytes() == original
            code, events = invoke(action="reconcile-account")
            assert code == 0 and events[-1]["status"] == "reconciled"
            assert events[-1]["after"]["permissions"]["status"] == "not_available"
            assert events[-1]["privateCreationRequest"] == {"status": "not_recorded"}
            assert json.loads(mapping.read_text())["plugins"]["plugin-sync"]["account"]["RELEASE"]["saveState"]["status"] == "verified"
            assert len(native.writes) == count
            assert invoke()[0] == 1  # Missing historical creation evidence is not invented.
            lock.write_text("another invocation")
            assert invoke(action="reconcile-account")[0] == 1
            assert invoke()[0] == 1
            lock.unlink()
            fresh = json.loads(mapping.read_text())
            fresh["plugins"]["dev-flow"] = {"account": {"RELEASE": {}}}
            mapping.write_text(json.dumps(fresh))
            native.lose_save_response = True
            code, events = invoke(plugin="dev-flow", timeout="0.1")
            assert code == 1 and events[-1]["status"] == "unknown"
            retained = Path(events[-1]["retainedDirectory"])
            assert retained.parent == delivery and retained.is_dir()
            assert (retained / "snapshots.json").is_file()
            assert Path(native.writes[-1][1]["pluginPath"]).is_dir()
            assert json.loads(mapping.read_text())["plugins"]["dev-flow"]["account"]["RELEASE"]["saveState"]["status"] == "pending"
            count = len(native.writes)
            assert invoke()[0] == 1
            assert invoke(plugin="dev-flow", action="reconcile-account")[0] == 1
            assert len(native.writes) == count
            assert json.loads(mapping.read_text())["plugins"]["plugin-sync"]["account"]["DEV"] == historical
            assert native.objects[0] == historical_object
            assert not lock.exists() and not list(root.glob(".plugin-sync-*"))

    def test_release_account_snapshots_require_a_clean_matching_tag(self, tmp_path):
        with tempfile.TemporaryDirectory(dir=tmp_path) as temporary:
            root = Path(temporary)
            project = snapshot_source(root, release_ref="v1.0.0")
            output = root / "release"
            for arguments in (("--account-mode", "RELEASE"),
                              ("--account-mode", "RELEASE", "--release-ref", "missing"),
                              ("--account-mode", "RELEASE", "--release-ref", "refs/heads/master"),
                              ("--release-ref", "v1.0.0"), ("--account-mode", "DEV")):
                failed = run_snapshots(project, output, *arguments)
                assert failed.returncode != 0, failed.stdout + failed.stderr
                assert not list(output.glob("*.zip")) and not (output / "snapshots.json").exists()
            note = project / "dirty-note.txt"
            note.write_text("same plugin inputs; initially uncommitted source state")
            dirty = run_snapshots(project, output, "--account-mode", "RELEASE", "--release-ref", "v1.0.0")
            assert dirty.returncode != 0 and "snapshot_release_source_unverified" in dirty.stderr
            assert not list(output.glob("*.zip")) and not (output / "snapshots.json").exists()
            for arguments in (("add", "dirty-note.txt"),
                              ("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "clean source")):
                subprocess.run(["git", "-C", str(project), *arguments], check=True, capture_output=True)
            stale = run_snapshots(project, output, "--account-mode", "RELEASE", "--release-ref", "v1.0.0")
            assert stale.returncode != 0 and "snapshot_release_source_unverified" in stale.stderr
            subprocess.run(["git", "-C", str(project), "tag", "v1.0.1"], check=True, capture_output=True)
            clean = run_snapshots(project, output, "--account-mode", "RELEASE", "--release-ref", "refs/tags/v1.0.1")
            assert clean.returncode == 0, clean.stdout + clean.stderr
            after = json.loads((output / "snapshots.json").read_text())["plugins"]
            commit = subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()
            assert all(not item["sourceDirty"] and item["sourceCommit"] == commit for item in after.values())
            assert all(item["releaseRef"] == "refs/tags/v1.0.1" for item in after.values())
            # An older published source stays valid when that clean tree is explicitly selected.
            subprocess.run(["git", "-C", str(project), "checkout", "--detach", "refs/tags/v1.0.0"],
                           check=True, capture_output=True)
            older_output = root / "older-release"
            older = run_snapshots(project, older_output, "--account-mode", "RELEASE", "--release-ref", "v1.0.0")
            assert older.returncode == 0, older.stdout + older.stderr
            records = json.loads((older_output / "snapshots.json").read_text())["plugins"]
            assert all(item["releaseRef"] == "refs/tags/v1.0.0" and item["sourceCommit"] != commit
                       and not item["sourceDirty"] for item in records.values())

    @pytest.mark.parametrize("plugin", ["release-flow", "pr-flow"])
    def test_python_plugin_entry_reports_its_actual_interpreter_and_missing_pyyaml(self, plugin):
        skill = REPO_ROOT / "plugins" / plugin / "skills" / plugin
        result = subprocess.run([sys.executable, "-S", "-B", str(skill / "scripts" / f"{plugin.replace('-', '_')}.py"),
                                 "--help"], text=True, capture_output=True)
        assert result.returncode != 0
        assert "missing_dependency: PyYAML" in result.stderr
        assert sys.executable in result.stderr
        assert str(skill / "requirements.txt") in result.stderr
        assert "Traceback" not in result.stderr
        assert (skill / "requirements.txt").read_text().strip() == "PyYAML>=6.0,<7.0"

    def test_plugin_snapshots_prepare_native_upload_directories_with_valid_cloud_metadata(self, tmp_path):
        project = snapshot_source(tmp_path)
        output = tmp_path / "snapshots"
        result = run_snapshots(project, output)
        assert result.returncode == 0, result.stdout + result.stderr
        manifest = json.loads((output / "snapshots.json").read_text())
        for name, record in manifest["plugins"].items():
            with zipfile.ZipFile(output / record["artifact"]) as archive:
                cloud = json.loads(archive.read(".codex-plugin/plugin.json"))
            assert cloud["author"] == {"name": "liuli195"}
            interface = cloud["interface"]
            assert interface["displayName"] == name
            assert interface["shortDescription"] == " ".join(cloud["description"].splitlines())
            assert interface["longDescription"] == cloud["description"]
            assert interface["developerName"] == "liuli195"
            assert interface["category"] == "Developer Tools"
            assert interface["capabilities"] == []
            directory = Path(record["pluginPath"])
            assert directory.is_dir() and directory.parent == output
            assert json.loads((directory / ".codex-plugin/plugin.json").read_text()) == cloud
        # Metadata is generated in the build result, not fabricated in source.
        assert "author" not in json.loads((project / "plugins/dev-flow/.codex-plugin/plugin.json").read_text())

    def test_plugin_snapshots_preserve_declared_metadata_and_record_its_source(self, tmp_path):
        project = snapshot_source(tmp_path)
        path = project / "plugins/dev-flow/.codex-plugin/plugin.json"
        source = json.loads(path.read_text())
        source.update({"author": {"name": "Declared source maintainer"},
                       "interface": {"category": "Productivity", "capabilities": ["Declared label"]}})
        path.write_text(json.dumps(source))
        output = tmp_path / "snapshots"
        result = run_snapshots(project, output)
        assert result.returncode == 0, result.stdout + result.stderr
        record = json.loads((output / "snapshots.json").read_text())["plugins"]["dev-flow"]
        cloud = json.loads((Path(record["pluginPath"]) / ".codex-plugin/plugin.json").read_text())
        assert cloud["author"] == source["author"]
        assert cloud["interface"]["developerName"] == source["author"]["name"]
        assert cloud["interface"]["category"] == "Productivity"
        assert cloud["interface"]["capabilities"] == ["Declared label"]
        assert record["metadataSource"]["category"] == ".codex-plugin/plugin.json"
        assert record["metadataSource"]["capabilities"] == ".codex-plugin/plugin.json"

    @pytest.mark.parametrize("metadata", [
        {"author": {"name": ""}},
        {"interface": []},
        {"interface": {"displayName": "x" * 81}},
        {"interface": {"shortDescription": "two\nlines"}},
        {"interface": {"category": "not a category"}},
        {"interface": {"capabilities": ["x" * 121]}},
    ])
    def test_plugin_snapshots_reject_invalid_cloud_metadata_before_exposing_artifacts(self, tmp_path, metadata):
        project = snapshot_source(tmp_path)
        path = project / "plugins/dev-flow/.codex-plugin/plugin.json"
        source = json.loads(path.read_text())
        path.write_text(json.dumps(source | metadata))
        output = tmp_path / "snapshots"
        failed = run_snapshots(project, output)
        assert failed.returncode != 0
        assert json.loads(failed.stderr)["status"] == "failed"
        assert not list(output.glob("*.zip"))
        assert not (output / "snapshots.json").exists()

    @pytest.mark.parametrize("legacy_registry", [False, True], ids=["current", "legacy"])
    def test_plugin_snapshots_build_complete_packages_from_the_shared_registry(self, tmp_path, legacy_registry):
        project = snapshot_source(tmp_path, legacy_registry=legacy_registry)
        output = tmp_path / "snapshots"
        result = run_snapshots(project, output)
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads(result.stdout)
        assert set(report["built"]) == {
            "release-flow", "pr-flow", "dev-flow", "subagent-policy", "plugin-sync",
            "retro-to-issues", "data-store", "my-spec", "build-and-verify",
        }
        assert report["reused"] == []
        manifest = json.loads((output / "snapshots.json").read_text())
        shared = (project / "plugins/tool-lifecycle/python/management.py").read_bytes()
        for name, record in manifest["plugins"].items():
            artifact = output / record["artifact"]
            assert record["sizeBytes"] == artifact.stat().st_size > 0
            assert record["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
            assert record["buildSeconds"] >= 0
            assert record["sourceCommit"]
            assert record["sourceDirty"] is False
            with zipfile.ZipFile(artifact) as archive:
                assert json.loads(archive.read(".codex-plugin/plugin.json"))["name"] == name
                assert json.loads(archive.read(".claude-plugin/plugin.json"))["version"] == record["version"]
                assert any(path.endswith("/SKILL.md") for path in archive.namelist())
                assert not any("__pycache__" in path or path.endswith(".pyc") for path in archive.namelist())
                if name in {"my-spec", "build-and-verify"}:
                    assert archive.read("python/management.py") == shared
                if name in {"release-flow", "pr-flow"}:
                    assert archive.read(f"skills/{name}/requirements.txt") == b"PyYAML>=6.0,<7.0\n"
        with zipfile.ZipFile(output / manifest["plugins"]["data-store"]["artifact"]) as archive:
            assert "skills/data-store/requirements.txt" in archive.namelist()
            assert "skills/data-store/scripts/data_store.py" in archive.namelist()
        for name, command in {
            "release-flow": [sys.executable, "skills/release-flow/scripts/release_flow.py", "--help"],
            "pr-flow": [sys.executable, "skills/pr-flow/scripts/pr_flow.py", "--help"],
            "data-store": [sys.executable, "skills/data-store/scripts/data_store.py", "--help"],
            "my-spec": ["node", "bin/myspec.js", "init", "--help"],
            "build-and-verify": ["node", "bin/build-and-verify.js", "init", "--help"],
        }.items():
            extracted = tmp_path / "installed" / name
            with zipfile.ZipFile(output / manifest["plugins"][name]["artifact"]) as archive:
                archive.extractall(extracted)
            smoke = subprocess.run(command, cwd=extracted, text=True, capture_output=True)
            assert smoke.returncode == 0, smoke.stdout + smoke.stderr
            assert "usage:" in smoke.stdout.lower()
        # Use the existing test interpreter explicitly. This is not a claim
        # about the interpreter selected by a future installed client.
        release = tmp_path / "installed/release-flow/skills/release-flow/scripts/release_flow.py"
        target = tmp_path / "runtime-project"
        for arguments in (("setup", "--authorize-project-files"), ("validate",)):
            runtime = subprocess.run([sys.executable, str(release), *arguments, "--project", str(target)],
                                     text=True, capture_output=True)
            assert runtime.returncode == 0, f"{sys.executable}: {runtime.stdout}{runtime.stderr}"
        assert (target / ".release-flow/config.yaml").is_file()
        store = tmp_path / "installed/data-store/skills/data-store/scripts/data_store.py"
        command = [sys.executable, str(store), "--root", str(tmp_path / "runtime-data")]
        written = subprocess.run([*command, "write", "snapshot_probe", "sample_01"],
                                 input='[{"value": 42}]', text=True, capture_output=True)
        assert written.returncode == 0, f"{sys.executable}: {written.stdout}{written.stderr}"
        assert json.loads(written.stdout) == {"rows": 1}
        read = subprocess.run([*command, "read-key", "snapshot_probe", "sample_01"],
                              text=True, capture_output=True)
        assert read.returncode == 0, read.stdout + read.stderr
        assert json.loads(read.stdout) == {"value": 42}

    @pytest.mark.parametrize("legacy_registry", [False, True], ids=["current", "legacy"])
    def test_plugin_snapshots_reuse_unchanged_artifacts_and_rebuild_complete_affected_plugins(self, tmp_path, legacy_registry):
        project = snapshot_source(tmp_path, legacy_registry=legacy_registry)
        output = tmp_path / "snapshots"
        assert run_snapshots(project, output).returncode == 0
        original = json.loads((output / "snapshots.json").read_text())["plugins"]
        repeated = run_snapshots(project, output)
        assert repeated.returncode == 0, repeated.stdout + repeated.stderr
        assert json.loads(repeated.stdout)["built"] == []
        assert set(json.loads(repeated.stdout)["reused"]) == set(original)
        assert json.loads((output / "snapshots.json").read_text())["plugins"] == original

        shared = project / "plugins/tool-lifecycle/python/management.py"
        shared.write_text(shared.read_text() + "\n# shared snapshot update\n")
        affected = run_snapshots(project, output)
        assert affected.returncode == 0, affected.stdout + affected.stderr
        assert set(json.loads(affected.stdout)["built"]) == {"my-spec", "build-and-verify"}
        updated = json.loads((output / "snapshots.json").read_text())["plugins"]
        for name in ("my-spec", "build-and-verify"):
            assert updated[name]["inputVersion"] != original[name]["inputVersion"]
            assert updated[name]["sourceDirty"] is True
            with zipfile.ZipFile(output / updated[name]["artifact"]) as archive:
                assert archive.read("python/management.py") == shared.read_bytes()

        skill = project / "plugins/data-store/skills/data-store/SKILL.md"
        skill.write_text(skill.read_text() + "\nSnapshot update\n")
        added = skill.with_name("snapshot-added.txt")
        added.write_bytes(b"untracked plugin input\n")
        (project / "unrelated.txt").write_bytes(b"outside every release input\n")
        (project / ".git/info/exclude").write_text("*.ignored\n")
        skill.with_name("snapshot.ignored").write_bytes(b"ignored plugin input\n")
        changed = run_snapshots(project, output)
        assert changed.returncode == 0, changed.stdout + changed.stderr
        assert json.loads(changed.stdout)["built"] == ["data-store"]
        final = json.loads((output / "snapshots.json").read_text())["plugins"]
        assert final["pr-flow"] == original["pr-flow"]
        with zipfile.ZipFile(output / final["data-store"]["artifact"]) as archive:
            assert archive.read("skills/data-store/SKILL.md") == skill.read_bytes()
            assert archive.read("skills/data-store/snapshot-added.txt") == added.read_bytes()
            assert "unrelated.txt" not in archive.namelist()
            assert "skills/data-store/snapshot.ignored" not in archive.namelist()
            assert "skills/data-store/scripts/data_store.py" in archive.namelist()
            assert "skills/data-store/requirements.txt" in archive.namelist()

    def test_plugin_snapshot_failure_keeps_previous_complete_manifest_and_artifacts(self, tmp_path):
        project = snapshot_source(tmp_path)
        output = tmp_path / "snapshots"
        assert run_snapshots(project, output).returncode == 0
        original = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
        (project / "plugins/dev-flow/skills/dev-flow/SKILL.md").unlink()
        failed = run_snapshots(project, output)
        assert failed.returncode != 0
        assert json.loads(failed.stderr)["status"] == "failed"
        assert {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()} == original

    @pytest.mark.parametrize("relative", [
        "plugins/pr-flow/skills/pr-flow-tweak/SKILL.md",
        "plugins/build-and-verify/skills/build-and-verify-review/SKILL.md",
        "plugins/my-spec/skills/my-spec-add/SKILL.md",
    ])
    def test_plugin_snapshots_refuse_a_missing_registered_skill_in_a_multiskill_plugin(self, tmp_path, relative):
        project = snapshot_source(tmp_path)
        (project / relative).unlink()
        output = tmp_path / "snapshots"
        failed = run_snapshots(project, output)
        assert failed.returncode != 0
        assert "snapshot_skill_input_missing" in failed.stderr
        assert not output.exists()

    def test_plugin_snapshots_refuse_corrupt_reuse_and_output_inside_inputs(self, tmp_path):
        project = snapshot_source(tmp_path)
        output = tmp_path / "snapshots"
        assert run_snapshots(project, output).returncode == 0
        manifest_bytes = (output / "snapshots.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        skill = Path(manifest["plugins"]["dev-flow"]["pluginPath"]) / "skills/dev-flow/SKILL.md"
        skill_bytes = skill.read_bytes()
        skill.write_bytes(b"changed local directory")
        failed_directory = run_snapshots(project, output)
        assert failed_directory.returncode != 0
        assert "snapshot_previous_artifact_invalid: dev-flow" in failed_directory.stderr
        assert (output / "snapshots.json").read_bytes() == manifest_bytes
        skill.write_bytes(skill_bytes)
        artifact = output / manifest["plugins"]["dev-flow"]["artifact"]
        artifact.write_bytes(b"not a complete snapshot")
        failed = run_snapshots(project, output)
        assert failed.returncode != 0
        assert "snapshot_previous_artifact_invalid: dev-flow" in failed.stderr
        assert (output / "snapshots.json").read_bytes() == manifest_bytes
        nested = run_snapshots(project, project / "plugins/dev-flow/output")
        assert nested.returncode != 0
        assert not (project / "plugins/dev-flow/output").exists()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX executable permissions")
    def test_plugin_snapshot_reuse_rejects_changed_executable_permissions(self, tmp_path):
        project = snapshot_source(tmp_path)
        output = tmp_path / "snapshots"
        assert run_snapshots(project, output).returncode == 0
        manifest_bytes = (output / "snapshots.json").read_bytes()
        record = json.loads(manifest_bytes)["plugins"]["build-and-verify"]
        script = Path(record["pluginPath"]) / "bin/build-and-verify.js"
        mode = script.stat().st_mode
        assert mode & 0o111
        script.chmod(mode & ~0o111)
        failed = run_snapshots(project, output)
        assert failed.returncode != 0
        assert "snapshot_previous_artifact_invalid: build-and-verify" in failed.stderr
        assert (output / "snapshots.json").read_bytes() == manifest_bytes

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
