from __future__ import annotations

from pathlib import Path, PureWindowsPath
import contextlib
import copy
import io
import json
import os
import queue
import runpy
import subprocess
import tarfile
import unittest
import zipfile

import yaml
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


RELEASE_FLOW_SCRIPT = (Path(__file__).resolve().parents[1] / "plugins/release-flow/skills/release-flow/scripts/release_flow.py")


class PublishedReleaseCommands:
    """Only hosted release reads are simulated; optional local Git reads stay real."""

    def __init__(self, *, project=Path("/repo"), repository="owner/repo", source_commit="c" * 40,
                 release=None, tag_commit=None, annotated=False, failure=None, origin_repository=None, local_run=None):
        self.project = Path(project)
        self.repository = repository
        self.source_commit = source_commit
        self.release = {"tagName": "v1.0.0", "isDraft": False, "isPrerelease": False,
                        "publishedAt": "2026-11-06T00:00:00Z", "url": "https://github.com/owner/repo/releases/tag/v1.0.0"}
        self.release.update(release or {})
        self.tag_commit = tag_commit or source_commit
        self.annotated = annotated
        self.failure = failure
        self.origin_repository = origin_repository or repository
        self.local_run = local_run
        self.calls = []

    def __call__(self, command, **kwargs):
        command = [str(part) for part in command]
        self.calls.append(command)
        assert kwargs.get("check") is False and kwargs.get("text") is True and kwargs.get("capture_output") is True
        origin = ["git", "-C", str(self.project), "config", "--get", "remote.origin.url"]
        if command == origin:
            if self.local_run:
                return self.local_run(command, **kwargs)
            return subprocess.CompletedProcess(command, 0, f"https://github.com/{self.origin_repository}.git\n", "")
        assert 0 < kwargs["timeout"] <= 30
        if PureWindowsPath(command[0]).name.casefold() in {"gh", "gh.exe"}:
            assert kwargs["cwd"] == self.project
            assert command[1:] == ["release", "view", "v1.0.0", "--repo", self.repository,
                                   "--json", "tagName,isDraft,isPrerelease,publishedAt,url"]
            if self.failure == "release-timeout":
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return subprocess.CompletedProcess(command, 1 if self.failure == "missing" else 0,
                                               json.dumps(self.release), "release not found" if self.failure == "missing" else "")
        ref = "refs/tags/v1.0.0"
        assert command == ["git", "-C", str(self.project), "ls-remote", "--tags", "origin", ref, ref + "^{}"]
        if self.failure == "tag-timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        output = f"{self.tag_commit}\t{ref}\n"
        if self.annotated:
            output = f"{'d' * 40}\t{ref}\n{self.tag_commit}\t{ref}^{{}}\n"
        return subprocess.CompletedProcess(command, 1 if self.failure == "tag-query" else 0, output, "query failed")


class NativeSaveClients:
    """In-memory account service with the real stdio request boundary."""

    def __init__(self):
        self.writes = []
        self.starts = 0
        self.objects = []
        self.save_result = {"remotePluginId": "Remote_created", "shareUrl": "https://example.test/private"}
        self.save_version = "0.0.2"
        self.lose_save_response = False
        self.save_error = False
        self.post_collision = False
        self.post_hidden = False
        self.post_missing_reads = 0
        self.post_reads = 0
        self.post_read_error = False
        self.lose_post_list_response = False
        self.last_params = None
        self.personal = True
        self.catalog_metadata = {}
        self.methods = []

    def start(self, *args, **kwargs):
        self.starts += 1
        owner = self
        messages = queue.Queue()
        class Process:
            def __init__(self):
                self.stdin = self
                self.stdout = iter(messages.get, None)
            def write(self, line):
                request = json.loads(line)
                if "id" not in request:
                    return
                try:
                    result = owner.request(request["method"], request["params"])
                    response = {"id": request["id"], "result": result}
                except RuntimeError as error:
                    response = {"id": request["id"], "error": {"message": str(error)}}
                if getattr(owner, "lose_save_response", False) and request["method"] == "plugin/share/save":
                    return
                if getattr(owner, "lose_post_list_response", False) and owner.writes and request["method"] == "plugin/list":
                    return
                messages.put(json.dumps(response) + "\n")
            def flush(self):
                pass
            def close(self):
                messages.put(None)
            def wait(self, timeout):
                return 0
        return Process()

    def request(self, method, params):
        self.methods.append(method)
        if method == "initialize":
            return {}
        if method == "plugin/list":
            if self.writes:
                self.post_reads += 1
                if self.post_read_error:
                    raise RuntimeError("catalog query failed")
            values = copy.deepcopy(self.objects)
            for item in values:
                if self.personal:
                    item["shareContext"] = None
                item.update(self.catalog_metadata)
            if self.writes and self.post_collision:
                values.append({**values[0], "remotePluginId": "Unrelated"})
            hidden = self.writes and (self.post_hidden or self.post_reads <= self.post_missing_reads)
            return {"marketplaces": [{"plugins": [] if hidden else values}]}
        if method == "plugin/share/save":
            self.last_params = params
            self.writes.append((method, params.get("remotePluginId")))
            remote_id = params.get("remotePluginId", "Remote_created")
            self.objects = [item for item in self.objects if item["remotePluginId"] != remote_id]
            self.objects.append(save_object(remote_id, version=self.save_version))
            if self.save_error:
                raise RuntimeError("save failed after effect")
            return self.save_result
        raise AssertionError(method)


def save_object(remote_id="Remote_created", version="0.0.2"):
    return {"remotePluginId": remote_id, "id": "example@created-by-me-remote", "name": "example",
            "version": version, "installed": False, "enabled": False, "localVersion": None,
            "shareContext": {"remotePluginId": remote_id, "discoverability": "PRIVATE", "sharePrincipals": []}}


def invoke_save(native, *, apply=False, store=None, extra=(), snapshot_error=None, action="save-account", version="0.0.2", mode="RELEASE", release_commands=None, unpack_error=None, unpack_function=None):
    entry = runpy.run_path(str(RELEASE_FLOW_SCRIPT))["main"]
    if unpack_function == "real":
        unpack_function = entry.__globals__["unpack_delivery_bundle"]
    store = store if store is not None else {"content": json.dumps({"plugins": {"example": {"account": {"RELEASE": {}}}}}).encode()}
    output = io.StringIO()
    snapshot = {"sha256": "a" * 64, "inputVersion": "b" * 64, "version": version,
                "sourceCommit": "c" * 40, "sourceDirty": False, "metadataSource": {"repository": "owner/repo"},
                "pluginPath": str(Path("/snapshots/example")), "packageName": "example", "accountMode": "RELEASE",
                "releaseRef": "refs/tags/v1.0.0"}
    class Temporary(io.BytesIO):
        name = "/mapping-temp"
        def fileno(self):
            return 0
        def close(self):
            store["temporary"] = self.getvalue()
            super().close()
    def replace(_path, _target):
        store["content"] = store["temporary"]
    command = "deliver-account" if action == "save-account" else "reconcile-account"
    args = [command, "--project", "/repo", "--manifest", "/mapping.json", "--plugin", "example",
            "--timeout", "0.1" if native.lose_save_response else "1",
            "--ready-timeout", "0.02", "--poll-interval", "0.001", *extra]
    if action == "save-account":
        args.extend(["--bundle", "/dot-release-packages.tar", "--delivery-dir", "/delivery", "--expected-sha256", "a" * 64])
    if action == "reconcile-account" or mode != "RELEASE":
        args.extend(["--mode", mode])
    if apply:
        args.append("--apply")
    def unpack(bundle, destination, deadline):
        assert action == "save-account", "reconciliation must not unpack a delivery bundle"
        assert bundle == Path("/dot-release-packages.tar")
        assert destination == Path("/delivery/.release-account-test")
        store["deliveryUnpacked"] = store.get("deliveryUnpacked", 0) + 1
        store["unpackDeadline"] = deadline
        if unpack_error:
            raise ValueError(unpack_error)
        if unpack_function:
            return unpack_function(bundle, destination, deadline)
        return destination / "snapshots.json"
    def verified(*args):
        store.setdefault("snapshotDeadlines", []).append(args[-1])
        if snapshot_error:
            raise ValueError(snapshot_error)
        return snapshot
    replacements = {
        "verified_snapshot": verified,
        "unpack_delivery_bundle": unpack,
    }
    def published(*args):
        assert action == "save-account", "reconciliation must not read hosted release metadata"
        return {"tag": "v1.0.0", "tagCommit": "c" * 40}
    if release_commands is None:
        replacements["published_account_release"] = published
    with patch.object(Path, "read_bytes", side_effect=lambda: store["content"]), \
            patch.object(Path, "open", side_effect=lambda *args, **kwargs: io.StringIO()), \
            patch.object(Path, "replace", replace), patch.object(Path, "exists", return_value=False), \
            patch.object(Path, "unlink"), patch("os.fsync"), \
            patch("tempfile.NamedTemporaryFile", side_effect=lambda **kwargs: Temporary()), \
            patch("tempfile.mkdtemp", return_value=str(Path("/delivery/.release-account-test"))), \
            patch.object(Path, "mkdir"), patch.object(Path, "is_dir", return_value=True), \
            patch("shutil.rmtree", side_effect=lambda path: store.setdefault("deliveryRemoved", []).append(str(path))), \
            patch.dict(entry.__globals__, replacements), \
            patch("subprocess.Popen", side_effect=native.start), \
            patch("subprocess.run", side_effect=release_commands) as commands, \
            contextlib.redirect_stdout(output):
        code = entry(args)
    if release_commands is None:
        commands.assert_not_called()
    assert set(native.methods) <= {"initialize", "plugin/list", "plugin/share/save"}
    return code, [json.loads(line) for line in output.getvalue().splitlines()], store


class PluginAccountEntryTests(unittest.TestCase):
    def test_delivery_rejects_switch_and_legacy_action_or_cwd_flags(self):
        entry = runpy.run_path(str(RELEASE_FLOW_SCRIPT))["main"]
        for arguments in (["switch"], ["deliver-account", "--action", "save-account"],
                          ["deliver-account", "--cwd", "/repo"], ["deliver-account", "--snapshots", "/snapshots.json"]):
            with self.subTest(arguments=arguments), patch("subprocess.Popen") as account, \
                    patch("subprocess.run") as local, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    entry([*arguments, "--project", "/repo", "--manifest", "/mapping.json", "--plugin", "example",
                           "--bundle", "/dot-release-packages.tar", "--delivery-dir", "/delivery", "--expected-sha256", "a" * 64])
                self.assertEqual(error.exception.code, 2)
                account.assert_not_called()
                local.assert_not_called()

    def test_save_and_reconcile_use_the_same_mapping_lock(self):
        entry = runpy.run_path(str(RELEASE_FLOW_SCRIPT))["main"]
        for action in ("deliver-account", "reconcile-account"):
            output = io.StringIO()
            with self.subTest(action=action), \
                    patch.object(Path, "open", side_effect=FileExistsError("mapping.json.lock exists")) as lock, \
                    patch("subprocess.Popen") as client, patch.object(Path, "mkdir"), \
                    patch("tempfile.mkdtemp", return_value=str(Path("/delivery/.release-account-test"))), \
                    patch("shutil.rmtree"), \
                    patch.dict(entry.__globals__, {"unpack_delivery_bundle": lambda *args: Path("/snapshots.json")}), \
                    contextlib.redirect_stdout(output):
                args = [action, "--project", "/repo", "--manifest", "/mapping.json", "--plugin", "example", "--apply"]
                if action == "deliver-account":
                    args.extend(["--bundle", "/dot-release-packages.tar", "--delivery-dir", "/delivery", "--expected-sha256", "a" * 64])
                code = entry(args)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())["status"], "blocked")
            self.assertEqual(lock.call_args.args, ("x",))
            client.assert_not_called()


class PluginAccountSaveEntryTests(unittest.TestCase):
    def test_dev_save_is_rejected_before_starting_an_account_client(self):
        native = NativeSaveClients()
        mapping = {"plugins": {"example": {"account": {"DEV": {}}}}}
        store = {"content": json.dumps(mapping).encode()}
        original = store["content"]
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            invoke_save(native, apply=True, store=store, mode="DEV")
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(native.starts, 0)
        self.assertEqual(native.writes, [])
        self.assertEqual(store["content"], original)

    def test_successful_delivery_cleans_only_its_temporary_directory(self):
        native = NativeSaveClients()
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 0)
        self.assertEqual(store["deliveryRemoved"], [str(Path("/delivery/.release-account-test"))])
        self.assertNotIn("retainedDirectory", events[-1])

    def test_unpack_and_save_share_the_original_deadline_without_resetting_it(self):
        native = NativeSaveClients()
        clock = [1000.0]
        def slow_unpack(bundle, destination, deadline):
            self.assertEqual(deadline, 1600.0)
            clock[0] = 1599.0
            return destination / "snapshots.json"
        with patch("time.monotonic", side_effect=lambda: clock[0]):
            code, _, store = invoke_save(native, apply=True, unpack_function=slow_unpack)
        self.assertEqual(code, 0)
        self.assertEqual(store["unpackDeadline"], 1600.0)
        self.assertEqual(store["snapshotDeadlines"], [1600.0, 1600.0])
        self.assertEqual(len(native.writes), 1)
        self.assertEqual(store["deliveryRemoved"], [str(Path("/delivery/.release-account-test"))])

    def test_expired_extraction_filter_stops_before_account_calls_and_cleans_up(self):
        native = NativeSaveClients()
        clock = [1000.0]
        member = tarfile.TarInfo("snapshots.json")
        archive = MagicMock()
        archive.__enter__.return_value = archive
        archive.getmembers.return_value = [member]
        def expire_before_first_member(destination, *, members, filter):
            self.assertTrue(callable(filter))
            clock[0] = 1601.0
            filter(members[0], str(destination))
            self.fail("expired extraction filter continued")
        archive.extractall.side_effect = expire_before_first_member
        with patch("time.monotonic", side_effect=lambda: clock[0]), \
                patch.object(Path, "is_file", return_value=True), patch.object(Path, "is_symlink", return_value=False), \
                patch.object(Path, "stat", return_value=SimpleNamespace(st_size=10240)), \
                patch("tarfile.open", return_value=archive), patch("tarfile.data_filter") as data_filter:
            code, events, store = invoke_save(native, apply=True, unpack_function="real")
        self.assertEqual(code, 1)
        self.assertIn("budget exhausted", events[-1]["error"])
        self.assertEqual(native.starts, 0)
        self.assertEqual(native.writes, [])
        self.assertEqual(store["deliveryRemoved"], [str(Path("/delivery/.release-account-test"))])
        self.assertNotIn("retainedDirectory", events[-1])
        data_filter.assert_not_called()

    def test_failure_before_account_writes_cleans_its_temporary_directory(self):
        for options in ({"snapshot_error": "invalid reviewed snapshot"}, {"unpack_error": "unsafe delivery member"}):
            with self.subTest(options=options):
                native = NativeSaveClients()
                code, events, store = invoke_save(native, apply=True, **options)
                self.assertEqual(code, 1)
                self.assertEqual(native.writes, [])
                self.assertEqual(store["deliveryRemoved"], [str(Path("/delivery/.release-account-test"))])
                self.assertNotIn("retainedDirectory", events[-1])

    def test_unknown_or_unverified_delivery_retains_the_exact_temporary_directory(self):
        for condition in ("lose_save_response", "post_hidden"):
            with self.subTest(condition=condition):
                native = NativeSaveClients()
                setattr(native, condition, True)
                code, events, store = invoke_save(native, apply=True)
                self.assertEqual(code, 1)
                self.assertIn(events[-1]["status"], {"unknown", "unverified"})
                self.assertEqual(Path(events[-1]["retainedDirectory"]), Path("/delivery/.release-account-test"))
                self.assertNotIn("deliveryRemoved", store)
                self.assertEqual(len(native.writes), 1)

    def test_pending_historical_dev_save_blocks_new_release_save(self):
        native = NativeSaveClients()
        mapping = {"plugins": {"example": {"account": {"RELEASE": {}}},
                               "other": {"account": {"DEV": {"saveState": {"status": "pending"}}}}}}
        store = {"content": json.dumps(mapping).encode()}
        original = store["content"]
        code, events, _ = invoke_save(native, apply=True, store=store)
        self.assertEqual(code, 1)
        self.assertIn("unresolved", events[-1]["error"])
        self.assertEqual(native.starts, 0)
        self.assertEqual(store["content"], original)

    def test_first_save_does_not_require_other_object_or_installed_source(self):
        native = NativeSaveClients()
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 0)
        self.assertEqual(events[0]["event"], "before_account_save")
        self.assertEqual(events[-1]["status"], "saved")
        self.assertEqual(native.last_params, {"pluginPath": str(Path("/snapshots/example")), "discoverability": "PRIVATE", "shareTargets": []})
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertEqual(source["remotePluginId"], "Remote_created")
        self.assertEqual(source["saveState"]["status"], "verified")
        self.assertEqual(source["saveState"]["snapshot"]["releaseRef"], "refs/tags/v1.0.0")
        self.assertFalse(native.objects[0]["installed"])

    def test_personal_create_completes_without_workspace_sharing_metadata(self):
        native = NativeSaveClients()
        native.personal = True
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["status"], "saved")
        self.assertEqual(events[-1]["after"]["permissions"]["status"], "not_available")
        self.assertFalse(events[-1]["after"]["permissions"]["creatorApiQueried"])
        self.assertIsNone(events[-1]["after"]["permissions"]["scope"])
        state = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]["saveState"]
        self.assertEqual(state["privateCreationRequest"], {"discoverability": "PRIVATE", "shareTargets": []})
        self.assertEqual(state["permissions"]["status"], "not_available")
        self.assertNotIn("plugin/share/list", native.methods)

    def test_workspace_or_unknown_scope_sharing_metadata_cannot_authorize_personal_update(self):
        for scope in (None, "WORKSPACE", "USER", "UNKNOWN"):
            with self.subTest(scope=scope):
                native = NativeSaveClients()
                native.personal = False
                if scope is not None:
                    native.catalog_metadata = {"scope": scope}
                native.objects = [save_object(version="0.0.1")]
                mapping = {"plugins": {"example": {"account": {"RELEASE": {"remotePluginId": "Remote_created", "version": "0.0.1"}}}}}
                original = json.dumps(mapping).encode()
                code, events, store = invoke_save(native, apply=True, store={"content": original})
                self.assertEqual(code, 1)
                self.assertEqual(events[-1]["status"], "blocked")
                self.assertEqual(store["content"], original)
                self.assertEqual(native.writes, [])
                self.assertNotIn("plugin/share/list", native.methods)

    def test_explicit_user_scope_does_not_invent_private_audience_verification(self):
        native = NativeSaveClients()
        native.catalog_metadata = {"scope": "USER", "discoverability": "PRIVATE"}
        code, events, _ = invoke_save(native, apply=True)
        self.assertEqual(code, 0)
        permissions = events[-1]["after"]["permissions"]
        self.assertEqual(permissions["scope"], "USER")
        self.assertEqual(permissions["status"], "not_available")

    def test_personal_update_without_private_creation_record_remains_blocked(self):
        native = NativeSaveClients()
        native.personal = True
        native.objects = [save_object(version="0.0.1")]
        mapping = {"plugins": {"example": {"account": {"RELEASE": {"remotePluginId": "Remote_created", "version": "0.0.1"}}}}}
        code, events, _ = invoke_save(native, apply=True, store={"content": json.dumps(mapping).encode()})
        self.assertEqual(code, 1)
        self.assertIn("private creation record", events[-1]["error"])
        self.assertEqual(native.writes, [])

    def test_recorded_personal_creation_can_update_without_faking_audience_verification(self):
        native = NativeSaveClients()
        code, _, store = invoke_save(native, apply=True)
        self.assertEqual(code, 0)
        for version in ("0.0.3", "0.0.4"):
            native.save_version = version
            code, events, store = invoke_save(native, apply=True, store=store, version=version)
            self.assertEqual(code, 0)
            self.assertEqual(events[-1]["operation"], "update")
            self.assertEqual(native.last_params, {"pluginPath": str(Path("/snapshots/example")), "remotePluginId": "Remote_created"})
            self.assertEqual(events[-1]["before"]["permissions"]["status"], "not_available")
            self.assertEqual(events[-1]["after"]["permissions"]["status"], "not_available")
            source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
            self.assertEqual(source["version"], version)
            self.assertEqual(source["saveState"]["privateCreationRequest"], {"discoverability": "PRIVATE", "shareTargets": []})
            self.assertEqual(source["saveState"]["status"], "verified")
        self.assertEqual(len(native.writes), 3)
        self.assertFalse(any(method in native.methods for method in ("plugin/read", "plugin/share/list", "mcpServer/tool/call")))

    def test_verified_legacy_release_record_can_update_with_a_new_release_snapshot(self):
        native = NativeSaveClients()
        _, _, store = invoke_save(native, apply=True)
        mapping = json.loads(store["content"])
        mapping["plugins"]["example"]["account"]["RELEASE"]["saveState"]["snapshot"].pop("releaseRef")
        store["content"] = json.dumps(mapping).encode()
        native.save_version = "0.0.3"
        code, events, _ = invoke_save(native, apply=True, store=store, version="0.0.3")
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["operation"], "update")
        self.assertEqual(native.last_params, {"pluginPath": str(Path("/snapshots/example")), "remotePluginId": "Remote_created"})
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertEqual(source["version"], "0.0.3")
        self.assertEqual(source["saveState"]["snapshot"]["releaseRef"], "refs/tags/v1.0.0")
        self.assertEqual(len(native.writes), 2)

    def test_private_creation_record_does_not_override_identity_or_permission_conflicts(self):
        native = NativeSaveClients()
        _, _, store = invoke_save(native, apply=True)
        original = store["content"]
        for metadata in ({"remotePluginId": "Wrong"}, {"name": "wrong"}, {"version": "wrong"},
                         {"scope": "WORKSPACE"}, {"discoverability": "UNLISTED"}, {"shareContext": {}}):
            with self.subTest(metadata=metadata):
                native.catalog_metadata = metadata
                code, _, _ = invoke_save(native, apply=True, store=store)
                self.assertEqual(code, 1)
                self.assertEqual(store["content"], original)
                self.assertEqual(len(native.writes), 1)

    def test_update_rejects_missing_mismatched_or_nonprivate_creation_record(self):
        native = NativeSaveClients()
        _, _, store = invoke_save(native, apply=True)
        baseline = json.loads(store["content"])
        for field, value in (("privateCreationRequest", None), ("privateCreationRequest", {"status": "not_recorded"}),
                             ("privateCreationRequest", {"discoverability": "UNLISTED", "shareTargets": []}),
                             ("privateCreationRequest", {"discoverability": "PRIVATE", "shareTargets": ["reader"]}),
                             ("responseRemotePluginId", "Wrong"), ("responseSchemaVerified", False)):
            with self.subTest(field=field, value=value):
                mapping = copy.deepcopy(baseline)
                mapping["plugins"]["example"]["account"]["RELEASE"]["saveState"][field] = value
                case = {"content": json.dumps(mapping).encode()}
                original = case["content"]
                code, _, _ = invoke_save(native, apply=True, store=case)
                self.assertEqual(code, 1)
                self.assertEqual(case["content"], original)
                self.assertEqual(len(native.writes), 1)

    def test_update_response_id_conflict_retains_mapping_and_blocks_repeated_save(self):
        native = NativeSaveClients()
        _, _, store = invoke_save(native, apply=True)
        native.save_result["remotePluginId"] = "Unexpected"
        code, events, store = invoke_save(native, apply=True, store=store)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["status"], "unverified")
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertEqual(source["remotePluginId"], "Remote_created")
        self.assertEqual(source["saveState"]["responseRemotePluginId"], "Unexpected")
        invoke_save(native, apply=True, store=store)
        self.assertEqual(len(native.writes), 2)

    def test_update_response_timeout_keeps_creation_evidence_and_blocks_repeated_save(self):
        native = NativeSaveClients()
        _, _, store = invoke_save(native, apply=True)
        native.lose_save_response = True
        code, events, store = invoke_save(native, apply=True, store=store)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["status"], "unknown")
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertEqual(source["remotePluginId"], "Remote_created")
        self.assertEqual(source["saveState"]["status"], "pending")
        self.assertEqual(source["saveState"]["privateCreationRequest"], {"discoverability": "PRIVATE", "shareTargets": []})
        invoke_save(native, apply=True, store=store)
        self.assertEqual(len(native.writes), 2)

    def test_personal_null_context_does_not_override_explicit_nonprivate_or_scope_conflicts(self):
        for metadata in ({"discoverability": "UNLISTED"}, {"scope": "WORKSPACE"}):
            with self.subTest(metadata=metadata):
                native = NativeSaveClients()
                native.personal = True
                native.catalog_metadata = metadata
                code, events, _ = invoke_save(native, apply=True)
                self.assertEqual(code, 1)
                self.assertEqual(events[-1]["status"], "unverified")
                self.assertEqual(len(native.writes), 1)
                self.assertEqual(native.post_reads, 1)

    def test_reconcile_known_personal_success_reads_only_and_can_update_local_state(self):
        native = NativeSaveClients()
        native.personal = True
        native.post_hidden = True
        code, _, store = invoke_save(native, apply=True)
        self.assertEqual(code, 1)
        native.post_hidden = False
        original = store["content"]
        code, events, _ = invoke_save(native, store=store, action="reconcile-account", snapshot_error="must not read snapshots")
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["status"], "checked")
        self.assertEqual(store["content"], original)
        code, events, _ = invoke_save(native, apply=True, store=store, action="reconcile-account")
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["status"], "reconciled")
        self.assertEqual(events[-1]["accountWrites"], 0)
        state = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]["saveState"]
        self.assertEqual(state["status"], "verified")
        self.assertEqual(state["permissions"]["status"], "not_available")
        self.assertEqual(len(native.writes), 1)
        self.assertNotIn("plugin/share/list", native.methods)

    def test_reconcile_legacy_success_does_not_invent_creation_or_permission_evidence(self):
        native = NativeSaveClients()
        native.post_hidden = True
        _, _, store = invoke_save(native, apply=True)
        value = json.loads(store["content"])
        state = value["plugins"]["example"]["account"]["RELEASE"]["saveState"]
        state.pop("responseSchemaVerified")
        state.pop("privateCreationRequest")
        store["content"] = json.dumps(value).encode()
        native.post_hidden = False
        native.personal = True
        code, events, _ = invoke_save(native, apply=True, store=store, action="reconcile-account")
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["privateCreationRequest"], {"status": "not_recorded"})
        self.assertEqual(events[-1]["after"]["permissions"]["status"], "not_available")
        self.assertEqual(len(native.writes), 1)

    def test_reconcile_historical_dev_record_reads_only_without_a_release_snapshot(self):
        native = NativeSaveClients()
        native.post_hidden = True
        _, _, store = invoke_save(native, apply=True)
        mapping = json.loads(store["content"])
        account = mapping["plugins"]["example"]["account"]
        source = account["DEV"] = account.pop("RELEASE")
        source["packageName"] = "example-dev"
        state = source["saveState"]
        state["snapshot"].update(packageName="example-dev", accountMode="DEV", sourceDirty=True)
        state["snapshot"].pop("releaseRef")
        state.pop("responseSchemaVerified")
        state.pop("privateCreationRequest")
        store["content"] = json.dumps(mapping).encode()
        native.objects[0].update(name="example-dev", id="example-dev@created-by-me-remote")
        native.post_hidden = False
        original = store["content"]
        code, events, _ = invoke_save(native, store=store, mode="DEV", action="reconcile-account",
                                      snapshot_error="must not read snapshots")
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["accountWrites"], 0)
        self.assertEqual(store["content"], original)
        code, events, _ = invoke_save(native, apply=True, store=store, mode="DEV", action="reconcile-account",
                                      snapshot_error="must not read snapshots")
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["status"], "reconciled")
        self.assertEqual(events[-1]["privateCreationRequest"], {"status": "not_recorded"})
        source = json.loads(store["content"])["plugins"]["example"]["account"]["DEV"]
        self.assertEqual(source["saveState"]["status"], "verified")
        self.assertNotIn("releaseRef", source["saveState"]["snapshot"])
        self.assertEqual(len(native.writes), 1)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            invoke_save(native, apply=True, store=store, mode="DEV")
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(len(native.writes), 1)

    def test_reconcile_rejects_pending_unknown_or_missing_success_identity(self):
        native = NativeSaveClients()
        native.post_hidden = True
        _, _, store = invoke_save(native, apply=True)
        base = json.loads(store["content"])
        native.post_hidden = False
        for field, value in (("status", "pending"), ("status", "unknown"), ("responseRemotePluginId", ""),
                             ("responseRemotePluginId", "wrong"), ("responseSchemaVerified", False)):
            with self.subTest(field=field, value=value):
                mapping = copy.deepcopy(base)
                mapping["plugins"]["example"]["account"]["RELEASE"]["saveState"][field] = value
                case = {"content": json.dumps(mapping).encode()}
                original = case["content"]
                starts = native.starts
                code, _, _ = invoke_save(native, apply=True, store=case, action="reconcile-account")
                self.assertEqual(code, 1)
                self.assertEqual(case["content"], original)
                self.assertEqual(native.starts, starts)
        self.assertEqual(len(native.writes), 1)

    def test_reconcile_keeps_state_when_catalog_identity_or_permissions_conflict(self):
        native = NativeSaveClients()
        native.post_hidden = True
        _, _, store = invoke_save(native, apply=True)
        native.post_hidden = False
        original = store["content"]
        for metadata in ({"version": "unexpected"}, {"name": "unexpected"}, {"discoverability": "UNLISTED"}, {"scope": "WORKSPACE"}):
            with self.subTest(metadata=metadata):
                native.catalog_metadata = metadata
                code, _, _ = invoke_save(native, apply=True, store=store, action="reconcile-account")
                self.assertEqual(code, 1)
                self.assertEqual(store["content"], original)
        self.assertEqual(len(native.writes), 1)

    def test_check_is_read_only_and_does_not_modify_mapping(self):
        native = NativeSaveClients()
        code, events, store = invoke_save(native)
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["status"], "checked")
        self.assertEqual(native.writes, [])
        self.assertNotIn("temporary", store)

    def test_unknown_personal_scope_cannot_authorize_update(self):
        native = NativeSaveClients()
        native.objects = [save_object(version="0.0.1")]
        mapping = {"plugins": {"example": {"account": {"RELEASE": {"remotePluginId": "Remote_created", "version": "0.0.1"}}}}}
        code, events, _ = invoke_save(native, apply=True, store={"content": json.dumps(mapping).encode()})
        self.assertEqual(code, 1)
        self.assertIsNone(events[-1]["before"]["permissions"]["scope"])
        self.assertEqual(events[-1]["before"]["permissions"]["status"], "not_available")
        self.assertEqual(native.writes, [])

    def test_same_name_existing_object_blocks_creation_without_guessing_id(self):
        native = NativeSaveClients()
        native.objects = [save_object()]
        code, events, _ = invoke_save(native, apply=True)
        self.assertEqual(code, 1)
        self.assertIn("already exists", events[-1]["error"])
        self.assertEqual(native.writes, [])

    def test_response_timeout_persists_pending_and_repeated_invocation_never_retries(self):
        native = NativeSaveClients()
        native.lose_save_response = True
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["status"], "unknown")
        self.assertEqual(events[-1]["saveState"]["status"], "pending")
        code, events, _ = invoke_save(native, apply=True, store=store)
        self.assertEqual(code, 1)
        self.assertEqual(len(native.writes), 1)
        self.assertIn("previous account save", events[-1]["error"])

    def test_terminal_error_after_effect_is_not_retried(self):
        native = NativeSaveClients()
        native.save_error = True
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["publicationStatus"], "published")
        self.assertTrue(events[-1]["partialSuccess"])
        self.assertEqual(events[-1]["status"], "unknown")
        self.assertEqual(len(native.objects), 1)
        invoke_save(native, apply=True, store=store)
        self.assertEqual(len(native.writes), 1)

    def test_collision_after_save_retains_real_id_and_blocks_further_writes(self):
        native = NativeSaveClients()
        native.post_collision = True
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["status"], "unverified")
        self.assertIn("conflicts", events[-1]["error"])
        self.assertEqual(native.post_reads, 1)
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertEqual(source["remotePluginId"], "Remote_created")
        self.assertEqual(source["saveState"]["responseRemotePluginId"], "Remote_created")
        invoke_save(native, apply=True, store=store)
        self.assertEqual(len(native.writes), 1)

    def test_missing_list_item_after_save_is_not_success_or_permission_to_retry(self):
        native = NativeSaveClients()
        native.post_hidden = True
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["status"], "unverified")
        self.assertGreater(native.post_reads, 1)
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertEqual(source["remotePluginId"], "Remote_created")
        self.assertEqual(source["saveState"]["status"], "unverified")
        invoke_save(native, apply=True, store=store)
        self.assertEqual(len(native.writes), 1)

    def test_save_waits_only_for_missing_directory_item_without_repeating_the_write(self):
        native = NativeSaveClients()
        native.post_missing_reads = 2
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["status"], "saved")
        self.assertEqual(events[-1]["directoryReads"], 3)
        self.assertEqual(native.post_reads, 3)
        self.assertEqual(len(native.writes), 1)
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertEqual(source["remotePluginId"], "Remote_created")
        self.assertEqual(source["saveState"]["status"], "verified")

    def test_post_save_query_failure_stops_and_keeps_unverified_id(self):
        native = NativeSaveClients()
        native.post_read_error = True
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 1)
        self.assertIn("catalog query failed", events[-1]["error"])
        self.assertEqual(native.post_reads, 1)
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertEqual(source["remotePluginId"], "Remote_created")
        self.assertEqual(source["saveState"]["status"], "unverified")
        invoke_save(native, apply=True, store=store)
        self.assertEqual(len(native.writes), 1)

    def test_post_save_query_timeout_is_bounded_and_never_retries_the_write(self):
        native = NativeSaveClients()
        native.lose_post_list_response = True
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 1)
        self.assertIn("timeout: plugin/list", events[-1]["error"])
        self.assertEqual(native.post_reads, 1)
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertEqual(source["remotePluginId"], "Remote_created")
        self.assertEqual(source["saveState"]["status"], "unverified")
        invoke_save(native, apply=True, store=store)
        self.assertEqual(len(native.writes), 1)

    def test_private_create_accepts_empty_share_url(self):
        native = NativeSaveClients()
        native.save_result["shareUrl"] = ""
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["status"], "saved")
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertEqual(source["remotePluginId"], "Remote_created")
        self.assertEqual(source["saveState"]["status"], "verified")
        self.assertEqual(len(native.writes), 1)

    def test_private_save_rejects_missing_or_nonstring_share_url_without_retry(self):
        for value in (None, 0, False, []):
            with self.subTest(value=value):
                native = NativeSaveClients()
                if value is None:
                    native.save_result.pop("shareUrl")
                else:
                    native.save_result["shareUrl"] = value
                code, events, store = invoke_save(native, apply=True)
                self.assertEqual(code, 1)
                self.assertEqual(events[-1]["status"], "unverified")
                source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
                self.assertEqual(source["remotePluginId"], "Remote_created")
                self.assertEqual(source["saveState"]["status"], "unverified")
                invoke_save(native, apply=True, store=store)
                self.assertEqual(len(native.writes), 1)

    def test_malformed_save_response_does_not_invent_id_or_retry(self):
        native = NativeSaveClients()
        native.save_result = {}
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["status"], "unknown")
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertNotIn("remotePluginId", source)
        invoke_save(native, apply=True, store=store)
        self.assertEqual(len(native.writes), 1)

    def test_nonprivate_existing_object_blocks_update_without_changing_sharing(self):
        for context in ({"discoverability": "UNLISTED"}, {"sharePrincipals": [{"role": "reader", "principalType": "user"}]}):
            with self.subTest(context=context):
                native = NativeSaveClients()
                native.personal = False
                item = save_object(version="0.0.1")
                item["shareContext"].update(context)
                native.objects = [item]
                mapping = {"plugins": {"example": {"account": {"RELEASE": {"remotePluginId": "Remote_created", "version": "0.0.1"}}}}}
                code, events, _ = invoke_save(native, apply=True, store={"content": json.dumps(mapping).encode()})
                self.assertEqual(code, 1)
                self.assertIn("sharing metadata conflicts", events[-1]["error"])
                self.assertEqual(native.writes, [])

    def test_unexpected_existing_response_id_is_recorded_without_binding_creation(self):
        native = NativeSaveClients()
        native.objects = [{**save_object("Unexpected"), "name": "other", "id": "other@created-by-me-remote"}]
        native.save_result = {"remotePluginId": "Unexpected", "shareUrl": "https://example.test/private"}
        mapping = {"plugins": {"example": {"account": {"RELEASE": {}}}}}
        code, events, store = invoke_save(native, apply=True, store={"content": json.dumps(mapping).encode()})
        self.assertEqual(code, 1)
        source = json.loads(store["content"])["plugins"]["example"]["account"]["RELEASE"]
        self.assertNotIn("remotePluginId", source)
        self.assertEqual(source["saveState"]["responseRemotePluginId"], "Unexpected")
        self.assertEqual(events[-1]["status"], "unverified")

    def test_save_preserves_other_plugin_and_source_mapping(self):
        native = NativeSaveClients()
        other = {"remotePluginId": "Other", "version": "1", "skills": ["other:entry"]}
        mapping = {"plugins": {"example": {"account": {"RELEASE": {}, "DEV": copy.deepcopy(other)}, "claude": {"kept": True}},
                               "other": {"account": {"DEV": copy.deepcopy(other)}}}, "kept": [1, 2]}
        code, _, store = invoke_save(native, apply=True, store={"content": json.dumps(mapping).encode()})
        self.assertEqual(code, 0)
        result = json.loads(store["content"])
        self.assertEqual(result["plugins"]["example"]["account"]["DEV"], other)
        self.assertEqual(result["plugins"]["other"], mapping["plugins"]["other"])
        self.assertEqual(result["plugins"]["example"]["claude"], {"kept": True})
        self.assertEqual(result["kept"], [1, 2])

    def test_unverified_snapshot_stops_before_starting_account_client(self):
        native = NativeSaveClients()
        code, events, _ = invoke_save(native, apply=True, snapshot_error="snapshot archive digest mismatch")
        self.assertEqual(code, 1)
        self.assertIn("digest mismatch", events[-1]["error"])
        self.assertEqual(native.starts, 0)


class SnapshotSaveValidationTests(unittest.TestCase):
    def validate(self, *, corrupt=False, dirty=False, mode="RELEASE", link=False, expected=None,
                 release_ref="refs/tags/v1.0.0", package_name="example",
                 recorded_path="/snapshots/example", directory_exists=True, archive_link=False, directory_link=False, mode_mismatch=False):
        entry = runpy.run_path(str(RELEASE_FLOW_SCRIPT))["verified_snapshot"]
        metadata = json.dumps({"name": package_name, "version": "0.0.2"})
        contents = {".codex-plugin/plugin.json": metadata.encode(), "skills/entry/SKILL.md": b"entry", "skills/entry/scripts/tool.py": b"print(1)"}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, content in contents.items():
                entry_name = zipfile.ZipInfo(name)
                entry_name.create_system = 3
                entry_name.external_attr = (0o100755 if name.endswith("tool.py") else 0o100644) << 16
                archive.writestr(entry_name, content)
        archive_bytes = buffer.getvalue()
        digest = __import__("hashlib").sha256(archive_bytes).hexdigest()
        snapshot = {"sha256": digest, "inputVersion": "b" * 64, "sourceCommit": "c" * 40,
                    "sourceDirty": dirty, "metadataSource": {"repository": "owner/repo"}, "version": "0.0.2",
                    "artifact": "example.zip", "sizeBytes": len(archive_bytes), "pluginPath": recorded_path, "packageName": package_name, "accountMode": mode, "releaseRef": release_ref}
        manifest = json.dumps({"version": 1, "plugins": {"example": snapshot}})
        directory = Path("/snapshots/example")
        files = [directory / name for name in contents]
        def read(path):
            if path.name == "example.zip":
                return archive_bytes
            return b"changed" if corrupt else contents[path.relative_to(directory).as_posix()]
        def stat(path):
            return SimpleNamespace(st_mode=0o755 if path.name == "tool.py" and not mode_mismatch else 0o644,
                                   st_size=len(archive_bytes) if path.name == "example.zip" else len(contents[path.relative_to(directory).as_posix()]))
        original_zip = zipfile.ZipFile
        with patch.object(Path, "resolve", lambda path: path), \
                patch.object(Path, "read_text", lambda path, **kwargs: metadata if path.name == "plugin.json" else manifest), \
                patch.object(Path, "read_bytes", read), patch.object(Path, "is_file", return_value=True), \
                patch.object(Path, "is_dir", return_value=directory_exists), \
                patch.object(Path, "is_symlink", lambda path: (link and path.name == "tool.py")
                             or (archive_link and path.name == "example.zip") or (directory_link and path == directory)), \
                patch.object(Path, "rglob", return_value=files), patch.object(Path, "stat", stat), \
                patch("zipfile.ZipFile", side_effect=lambda path: original_zip(io.BytesIO(archive_bytes))):
            return entry("/snapshots/snapshots.json", "example", expected or digest, mode, __import__("time").monotonic() + 30)

    def test_accepts_complete_reviewed_archive_and_matching_directory(self):
        self.assertEqual(Path(self.validate()["pluginPath"]), Path("/snapshots/example"))

    def test_relocates_unchanged_windows_or_unix_bundle_paths(self):
        for recorded_path in ("/previous-machine/build/example", r"C:\runner\build\example"):
            with self.subTest(recorded_path=recorded_path):
                snapshot = self.validate(recorded_path=recorded_path)
                self.assertEqual(Path(snapshot["pluginPath"]), Path("/snapshots/example"))
                self.assertEqual(snapshot["releaseRef"], "refs/tags/v1.0.0")
                self.assertEqual(snapshot["sourceCommit"], "c" * 40)

    def test_rejects_traversal_or_an_unrelated_recorded_directory(self):
        for recorded_path in ("/builder/../example", r"C:\builder\..\example", "/builder/unrelated", None):
            with self.subTest(recorded_path=recorded_path), self.assertRaisesRegex(Exception, "recorded archive directory"):
                self.validate(recorded_path=recorded_path)

    def test_rejects_archive_or_sibling_directory_symlinks(self):
        for options in ({"archive_link": True}, {"directory_link": True}):
            with self.subTest(options=options), self.assertRaisesRegex(Exception, "verified sibling artifact"):
                self.validate(**options)

    def test_rejects_a_missing_downloaded_sibling_directory(self):
        with self.assertRaises(Exception):
            self.validate(recorded_path="/previous-machine/build/example", directory_exists=False)

    def test_rejects_changed_directory_content(self):
        with self.assertRaisesRegex(Exception, "content or executable mode mismatch"):
            self.validate(corrupt=True)

    @unittest.skipIf(os.name == "nt", "Windows does not expose POSIX executable bits")
    def test_rejects_lost_executable_modes_without_repairing_them(self):
        with patch.object(Path, "chmod") as chmod:
            with self.assertRaisesRegex(Exception, "content or executable mode mismatch"):
                self.validate(mode_mismatch=True)
        chmod.assert_not_called()

    def test_rejects_symlink_inside_snapshot(self):
        with self.assertRaisesRegex(Exception, "complete archive"):
            self.validate(link=True)

    def test_rejects_unreviewed_digest(self):
        with self.assertRaisesRegex(Exception, "provenance"):
            self.validate(expected="0" * 64)

    def test_dirty_snapshot_cannot_update_release(self):
        with self.assertRaisesRegex(Exception, "development snapshot"):
            self.validate(dirty=True)
        self.assertFalse(self.validate()["sourceDirty"])

    def test_rejects_dev_snapshot_or_projected_development_name(self):
        for options in ({"mode": "DEV"}, {"package_name": "example-dev"}):
            with self.subTest(options=options), self.assertRaises(Exception):
                self.validate(**options)

    def test_rejects_missing_or_non_tag_release_reference(self):
        for release_ref in (None, "", "v1.0.0", "refs/heads/main"):
            with self.subTest(release_ref=release_ref), self.assertRaises(Exception):
                self.validate(release_ref=release_ref)


class DeliveryBundleValidationTests(unittest.TestCase):
    def unpack(self, members, *, size=10240, bundle_link=False):
        entry = runpy.run_path(str(RELEASE_FLOW_SCRIPT))["unpack_delivery_bundle"]
        archive = MagicMock()
        archive.__enter__.return_value = archive
        archive.getmembers.return_value = members
        def extract(target, *, members, filter):
            self.assertTrue(callable(filter))
            for member in members:
                self.assertIs(filter(member, str(target)), member)
        archive.extractall.side_effect = extract
        bundle, destination = Path("/dot-release-packages.tar"), Path("/delivery/.stage")
        with patch.object(Path, "is_symlink", lambda path: bundle_link and path == bundle), \
                patch.object(Path, "is_file", return_value=True), \
                patch.object(Path, "stat", return_value=SimpleNamespace(st_size=size)), \
                patch("tarfile.open", return_value=archive) as opened, \
                patch("tarfile.data_filter", side_effect=lambda member, target: member) as data_filter:
            try:
                result = entry(bundle, destination, __import__("time").monotonic() + 30)
            except Exception:
                archive.extractall.assert_not_called()
                raise
        opened.assert_called_once_with(bundle, "r:")
        archive.extractall.assert_called_once()
        self.assertEqual(archive.extractall.call_args.args, (destination,))
        self.assertEqual(archive.extractall.call_args.kwargs["members"], members)
        self.assertTrue(callable(archive.extractall.call_args.kwargs["filter"]))
        self.assertEqual(data_filter.call_count, len(members))
        for call, member in zip(data_filter.call_args_list, members):
            self.assertEqual(call.args, (member, str(destination)))
        return result

    def test_only_regular_members_are_extracted_through_the_data_filter(self):
        directory = tarfile.TarInfo("./package")
        directory.type = tarfile.DIRTYPE
        executable = tarfile.TarInfo("./package/tool.py")
        executable.mode = 0o755
        self.assertEqual(self.unpack([directory, executable]), Path("/delivery/.stage/snapshots.json"))

    def test_rejects_absolute_traversal_windows_or_duplicate_normalized_paths(self):
        cases = [[tarfile.TarInfo(name)] for name in ("/escape", "../escape", "ok/../../escape", r"..\escape", r"C:\escape", "a:b")]
        cases.extend([[tarfile.TarInfo("same"), tarfile.TarInfo("./same")],
                      [tarfile.TarInfo("a//b"), tarfile.TarInfo("a/b")]])
        for members in cases:
            with self.subTest(names=[item.name for item in members]), self.assertRaisesRegex(Exception, "unsafe path or file type"):
                self.unpack(members)

    def test_rejects_links_and_all_special_file_types_before_extraction(self):
        for member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE):
            member = tarfile.TarInfo("unsafe")
            member.type = member_type
            member.linkname = "../outside"
            with self.subTest(member_type=member_type), self.assertRaisesRegex(Exception, "unsafe path or file type"):
                self.unpack([member])

    def test_rejects_negative_sizes_and_combined_input_expansion_over_budget(self):
        member = tarfile.TarInfo("large")
        member.size = -1
        with self.assertRaisesRegex(Exception, "unsafe path or file type"):
            self.unpack([member])
        member.size = 250_000_000
        with self.assertRaisesRegex(Exception, "bounded extraction budget"):
            self.unpack([member], size=250_000_001)
        with self.assertRaisesRegex(Exception, "bounded regular file"):
            self.unpack([], size=500_000_001)
        with self.assertRaisesRegex(Exception, "bounded regular file"):
            self.unpack([], bundle_link=True)


class PublishedAccountReleaseTests(unittest.TestCase):
    def test_missing_or_unpublished_release_never_starts_an_account_client(self):
        for options in ({"failure": "missing"}, {"release": {"isDraft": True}},
                        {"release": {"isPrerelease": True}}, {"release": {"tagName": "v9.9.9"}},
                        {"release": {"publishedAt": ""}}):
            with self.subTest(options=options):
                native = NativeSaveClients()
                store = {"content": json.dumps({"plugins": {"example": {"account": {"RELEASE": {}}}}}).encode()}
                original = store["content"]
                code, events, _ = invoke_save(native, apply=True, store=store, release_commands=PublishedReleaseCommands(**options))
                self.assertEqual(code, 1)
                self.assertEqual(events[-1]["status"], "blocked")
                self.assertNotEqual(events[-1].get("publicationStatus"), "published")
                self.assertFalse(events[-1].get("partialSuccess", False))
                self.assertEqual(native.starts, 0)
                self.assertEqual(native.writes, [])
                self.assertEqual(store["content"], original)

    def test_wrong_repository_tag_or_remote_query_failure_stops_before_account_writes(self):
        for options in ({"origin_repository": "other/repository"}, {"tag_commit": "e" * 40},
                        {"failure": "release-timeout"}, {"failure": "tag-timeout"}, {"failure": "tag-query"}):
            with self.subTest(options=options):
                native = NativeSaveClients()
                code, events, store = invoke_save(native, apply=True, release_commands=PublishedReleaseCommands(**options))
                self.assertEqual(code, 1)
                self.assertEqual(events[-1]["status"], "blocked")
                self.assertNotEqual(events[-1].get("publicationStatus"), "published")
                self.assertFalse(events[-1].get("partialSuccess", False))
                self.assertEqual(native.starts, 0)
                self.assertEqual(native.writes, [])
                self.assertNotIn("temporary", store)

    def test_published_lightweight_or_peeled_tag_can_deliver_without_a_ci_run_id(self):
        for annotated, executable in ((False, "gh"), (True, "gh"), (False, r"C:\Program Files\GitHub CLI\gh.EXE")):
            with self.subTest(annotated=annotated, executable=executable), patch("shutil.which", return_value=executable):
                native = NativeSaveClients()
                commands = PublishedReleaseCommands(annotated=annotated)
                code, events, _ = invoke_save(native, apply=True, release_commands=commands)
                self.assertEqual(code, 0)
                self.assertEqual(events[-1]["status"], "saved")
                self.assertEqual(events[-1]["publicationStatus"], "published")
                self.assertNotIn("partialSuccess", events[-1])
                self.assertEqual(events[-1]["release"]["tagCommit"], "c" * 40)
                self.assertEqual(len(native.writes), 1)
                self.assertFalse(any("run" in command for command in commands.calls))


def test_release_workflow_uploads_complete_packages_after_publication_without_account_access():
    workflow_path = RELEASE_FLOW_SCRIPT.parents[5] / ".github/workflows/release.yml"
    text = workflow_path.read_text(encoding="utf-8")
    steps = yaml.safe_load(text)["jobs"]["publish"]["steps"]
    names = [step.get("name") for step in steps]
    publish = steps[names.index("Publish release channel")]
    build = steps[names.index("Build complete dot release packages")]
    upload = steps[names.index("Upload complete dot release packages")]
    assert names.index(publish["name"]) < names.index(build["name"]) < names.index(upload["name"])
    assert "ci-publish" in publish["run"]
    assert publish["if"] == build["if"] == upload["if"] == "env.FIRST_PUBLISH_REQUIRED != 'true'"
    script = build["run"]
    assert 'git -C source fetch --no-tags origin "refs/tags/$RELEASE_TAG:refs/tags/$RELEASE_TAG"' in script
    assert 'git -C source checkout --detach "refs/tags/$RELEASE_TAG"' in script
    assert 'python source/plugins/tool-lifecycle/pack.py snapshots "$RUNNER_TEMP/dot-release-packages"' in script
    assert '--project source --account-mode RELEASE --release-ref "$RELEASE_TAG"' in script
    assert script.index("fetch") < script.index("checkout --detach") < script.index("pack.py snapshots")
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"]["name"] == "dot-release-packages"
    tar_command = 'tar -cf "$RUNNER_TEMP/dot-release-packages.tar" -C "$RUNNER_TEMP/dot-release-packages" .'
    assert tar_command in script
    assert script.index("pack.py snapshots") < script.index(tar_command)
    assert upload["with"]["path"] == "${{ runner.temp }}/dot-release-packages.tar"
    assert upload["with"]["if-no-files-found"] == "error"
    for forbidden in ("deliver-account", "reconcile-account", "plugin/share/save", "codex app-server",
                      "CODEX_AUTH", "CHATGPT_TOKEN", "OPENAI_API_KEY"):
        assert forbidden not in text
