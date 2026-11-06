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


def snapshot_source(tmp_path, *, legacy_registry=False):
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
    for arguments in (("init", "-q"), ("add", "plugins"),
                      ("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                       "commit", "-qm", "snapshot source")):
        subprocess.run(["git", "-C", str(project), *arguments], check=True, capture_output=True)
    origin = subprocess.run(["git", "-C", str(REPO_ROOT), "remote", "get-url", "origin"],
                            check=True, text=True, capture_output=True).stdout.strip()
    subprocess.run(["git", "-C", str(project), "remote", "add", "origin", origin],
                   check=True, capture_output=True)
    return project


def run_snapshots(project, output, *arguments):
    return subprocess.run([sys.executable, str(PACK), "snapshots", str(output),
                           "--project", str(project), *arguments], text=True, capture_output=True)


class TestWorkspace:
    def test_account_mode_snapshots_save_through_real_mapping_and_shared_lock(self, tmp_path):
        from tests.test_plugin_sync_skill_contract import NativeSaveClients
        with tempfile.TemporaryDirectory(dir=tmp_path) as temporary:
            root = Path(temporary)
            project = snapshot_source(root)
            snapshots = {}
            for mode in ("DEV", "RELEASE"):
                output = root / mode
                result = run_snapshots(project, output, "--account-mode", mode)
                assert result.returncode == 0, result.stdout + result.stderr
                snapshots[mode] = json.loads((output / "snapshots.json").read_text())["plugins"]
                for name, record in snapshots[mode].items():
                    package = Path(record["pluginPath"])
                    assert record["accountMode"] == mode
                    assert record["packageName"] == name + ("-dev" if mode == "DEV" else "")
                    cloud = json.loads((package / ".codex-plugin/plugin.json").read_text())
                    assert cloud["name"] == record["packageName"]
                    assert cloud["interface"]["displayName"] == name + ("-dev" if mode == "DEV" else "")
                    assert json.loads((package / ".claude-plugin/plugin.json").read_text())["name"] == name
                    assert json.loads((project / "plugins" / name / ".codex-plugin/plugin.json").read_text())["name"] == name
                    if (package / "package.json").exists():
                        assert json.loads((package / "package.json").read_text())["name"] == json.loads((project / "plugins" / name / "package.json").read_text())["name"]
            assert snapshots["DEV"]["plugin-sync"]["inputVersion"] != snapshots["RELEASE"]["plugin-sync"]["inputVersion"]
            reused = run_snapshots(project, root / "DEV", "--account-mode", "DEV")
            assert reused.returncode == 0, reused.stderr
            assert json.loads(reused.stdout)["built"] == []
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"plugins": {"plugin-sync": {"account": {"DEV": {}, "RELEASE": {}}}}, "preserved": [1, 2]}))
            lock = root / "mapping.json.lock"
            class Native(NativeSaveClients):
                def request(self, method, params):
                    if method != "plugin/share/save":
                        return super().request(method, params)
                    assert lock.exists()
                    stored = json.loads(mapping.read_text())["plugins"]
                    assert any(item.get("saveState", {}).get("status") == "pending"
                               for plugin in stored.values() for item in plugin["account"].values())
                    cloud = json.loads((Path(params["pluginPath"]) / ".codex-plugin/plugin.json").read_text())
                    remote_id = params.get("remotePluginId", "Remote_" + cloud["name"])
                    self.writes.append((method, dict(params)))
                    self.objects = [item for item in self.objects if item["remotePluginId"] != remote_id]
                    self.objects.append({"remotePluginId": remote_id, "name": cloud["name"], "version": cloud["version"],
                                         "id": cloud["name"] + "@created-by-me-remote", "installed": False, "enabled": False,
                                         "shareContext": {"remotePluginId": remote_id, "discoverability": "PRIVATE", "sharePrincipals": []}})
                    return {"remotePluginId": remote_id, "shareUrl": ""}
            native = Native()
            entry = runpy.run_path(str(REPO_ROOT / "plugins/plugin-sync/skills/plugin-sync/scripts/plugin_sync.py"))["main"]
            def invoke(mode, *, apply=True, action="save-account", timeout="1", plugin="plugin-sync"):
                output = io.StringIO()
                args = ["--action", action, "--manifest", str(mapping), "--plugin", plugin, "--mode", mode,
                        "--snapshots", str(root / mode / "snapshots.json"), "--expected-sha256", snapshots[mode][plugin]["sha256"],
                        "--cwd", str(project), "--timeout", timeout]
                with patch("subprocess.Popen", side_effect=native.start), contextlib.redirect_stdout(output):
                    code = entry(args + (["--apply"] if apply else []))
                return code, [json.loads(line) for line in output.getvalue().splitlines()]
            original = mapping.read_bytes()
            assert invoke("RELEASE", apply=False)[0] == 0
            assert mapping.read_bytes() == original
            assert invoke("RELEASE")[0] == 0
            assert invoke("DEV")[0] == 0
            stored = json.loads(mapping.read_text())
            assert stored["preserved"] == [1, 2]
            assert stored["plugins"]["plugin-sync"]["account"]["DEV"]["packageName"] == "plugin-sync-dev"
            assert stored["plugins"]["plugin-sync"]["account"]["RELEASE"]["packageName"] == "plugin-sync"
            assert len(native.objects) == 2 and all(not item["installed"] for item in native.objects)
            code, events = invoke("DEV")
            assert code == 0 and events[-1]["operation"] == "update"
            assert native.writes[-1][1] == {"pluginPath": snapshots["DEV"]["plugin-sync"]["pluginPath"], "remotePluginId": "Remote_plugin-sync-dev"}
            updated = json.loads(mapping.read_text())["plugins"]["plugin-sync"]["account"]["DEV"]["saveState"]
            assert updated["privateCreationRequest"] == {"discoverability": "PRIVATE", "shareTargets": []}
            assert updated["permissions"]["status"] == "not_available"
            original = mapping.read_bytes()
            count = len(native.writes)
            native.personal = False
            native.catalog_metadata = {"scope": "WORKSPACE"}
            code, events = invoke("DEV")
            assert code == 1 and "not personal USER" in events[-1]["error"]
            assert mapping.read_bytes() == original and len(native.writes) == count
            assert len(native.objects) == 2
            native.personal = True
            native.catalog_metadata = {}
            legacy = json.loads(mapping.read_text())
            state = legacy["plugins"]["plugin-sync"]["account"]["DEV"]["saveState"]
            state["status"] = "unverified"
            state.pop("privateCreationRequest", None)
            state.pop("responseSchemaVerified")
            mapping.write_text(json.dumps(legacy))
            original = mapping.read_bytes()
            count = len(native.writes)
            assert invoke("DEV", action="reconcile-account", apply=False)[0] == 0
            assert mapping.read_bytes() == original
            code, events = invoke("DEV", action="reconcile-account")
            assert code == 0 and events[-1]["status"] == "reconciled"
            assert events[-1]["after"]["permissions"]["status"] == "not_available"
            assert events[-1]["privateCreationRequest"] == {"status": "not_recorded"}
            assert json.loads(mapping.read_text())["plugins"]["plugin-sync"]["account"]["DEV"]["saveState"]["status"] == "verified"
            assert len(native.writes) == count
            assert invoke("DEV")[0] == 1  # A legacy record without creation evidence is not auto-upgraded.
            lock.write_text("another invocation")
            assert invoke("DEV", action="switch")[0] == 1
            assert invoke("DEV")[0] == 1
            lock.unlink()
            fresh = json.loads(mapping.read_text())
            fresh["plugins"]["dev-flow"] = {"account": {"DEV": {}}}
            mapping.write_text(json.dumps(fresh))
            native.lose_save_response = True
            code, events = invoke("DEV", plugin="dev-flow", timeout="0.1")
            assert code == 1 and events[-1]["status"] == "unknown"
            assert json.loads(mapping.read_text())["plugins"]["dev-flow"]["account"]["DEV"]["saveState"]["status"] == "pending"
            count = len(native.writes)
            assert invoke("RELEASE")[0] == 1
            assert invoke("RELEASE", action="switch")[0] == 1
            assert invoke("DEV", plugin="dev-flow", action="reconcile-account")[0] == 1
            assert len(native.writes) == count
            assert not lock.exists() and not list(root.glob(".plugin-sync-*"))

    def test_release_account_snapshot_rebuilds_after_dirty_source_becomes_clean(self, tmp_path):
        with tempfile.TemporaryDirectory(dir=tmp_path) as temporary:
            root = Path(temporary)
            project = snapshot_source(root)
            note = project / "dirty-note.txt"
            note.write_text("same plugin inputs; initially uncommitted source state")
            output = root / "release"
            first = run_snapshots(project, output, "--account-mode", "RELEASE")
            assert first.returncode == 0, first.stdout + first.stderr
            before = json.loads((output / "snapshots.json").read_text())["plugins"]
            assert all(item["sourceDirty"] for item in before.values())
            for arguments in (("add", "dirty-note.txt"),
                              ("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "clean source")):
                subprocess.run(["git", "-C", str(project), *arguments], check=True, capture_output=True)
            second = run_snapshots(project, output, "--account-mode", "RELEASE")
            assert second.returncode == 0, second.stdout + second.stderr
            after = json.loads((output / "snapshots.json").read_text())["plugins"]
            assert set(json.loads(second.stdout)["built"]) == set(before)
            commit = subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()
            assert all(not item["sourceDirty"] and item["sourceCommit"] == commit for item in after.values())
            assert all(item["inputVersion"] == before[name]["inputVersion"] for name, item in after.items())

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
            "plugin-sync": [sys.executable, "skills/plugin-sync/scripts/plugin_sync.py", "--help"],
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
        changed = run_snapshots(project, output)
        assert changed.returncode == 0, changed.stdout + changed.stderr
        assert json.loads(changed.stdout)["built"] == ["data-store"]
        final = json.loads((output / "snapshots.json").read_text())["plugins"]
        assert final["pr-flow"] == original["pr-flow"]
        with zipfile.ZipFile(output / final["data-store"]["artifact"]) as archive:
            assert archive.read("skills/data-store/SKILL.md").endswith(b"Snapshot update\n")
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
