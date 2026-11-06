from __future__ import annotations

from pathlib import Path
import contextlib
import copy
import io
import json
import queue
import runpy
import subprocess
import threading
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch


PLUGIN_SYNC_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "plugin-sync" / "skills" / "plugin-sync"


def reference_text(name: str) -> str:
    assert PLUGIN_SYNC_ROOT.exists(), f"plugin-sync skill not found: {PLUGIN_SYNC_ROOT}"
    return (PLUGIN_SYNC_ROOT / "references" / name).read_text(encoding="utf-8")


def test_plugin_sync_delegates_build_and_verify_lifecycle() -> None:
    text = reference_text("update-build-and-verify-runtime.md")

    for command in ["build-and-verify doctor", "build-and-verify init", "build-and-verify update"]:
        assert command in text
    assert "explicit user authorization" in text
    for forbidden in ["update-runtime", "runtime_current", "runtime_stale", "PR Flow"]:
        assert forbidden not in text


class PluginSwitchEntryTests(unittest.TestCase):
    """Exercise the public entry; only client and file boundaries are replaced."""

    def test_rejects_shared_dev_release_identity_before_starting_a_client(self) -> None:
        manifest = {
            "plugins": {"example": {"account": {
                "DEV": {"remotePluginId": "same"},
                "RELEASE": {"remotePluginId": "same"},
            }}}
        }
        entry = runpy.run_path(str(PLUGIN_SYNC_ROOT / "scripts" / "plugin_sync.py"))["main"]
        output = io.StringIO()
        with patch.object(Path, "read_text", return_value=json.dumps(manifest)), \
                patch("subprocess.Popen") as client, contextlib.redirect_stdout(output):
            code = entry(["--manifest", "mapping.json", "--plugin", "example", "--mode", "DEV"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "blocked")
        client.assert_not_called()

    def test_pending_save_for_another_plugin_blocks_source_switch(self) -> None:
        native = NativeSwitchClients()
        manifest = switch_manifest()
        manifest["plugins"]["other"] = {"account": {"DEV": {"saveState": {"status": "pending"}}}}
        code, events = invoke_switch(native, apply=True, manifest=manifest)
        self.assertEqual(code, 1)
        self.assertIn("unresolved", events[-1]["error"])
        self.assertEqual(native.starts, 0)
        self.assertEqual(native.writes, [])

    def test_switch_and_save_use_the_same_mapping_lock(self) -> None:
        entry = runpy.run_path(str(PLUGIN_SYNC_ROOT / "scripts" / "plugin_sync.py"))["main"]
        for action in ("switch", "save-account", "reconcile-account"):
            output = io.StringIO()
            with patch.object(Path, "open", side_effect=FileExistsError("mapping.json.lock exists")) as lock, \
                    patch("subprocess.Popen") as client, contextlib.redirect_stdout(output):
                code = entry(["--action", action, "--manifest", "/mapping.json", "--plugin", "example", "--mode", "DEV", "--apply"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())["status"], "blocked")
            self.assertEqual(lock.call_args.args, ("x",))
            client.assert_not_called()

    def test_waits_for_native_skill_identity_then_switches_claude(self) -> None:
        native = NativeSwitchClients()
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 0)
        result = events[-1]
        self.assertEqual(result["status"], "switched")
        self.assertEqual(result["readiness"]["skills"], ["example-dev:entry"])
        self.assertGreater(result["readiness"]["attempts"], 1)
        self.assertTrue(result["after"]["account"]["DEV"]["installed"])
        self.assertFalse(result["after"]["account"]["RELEASE"]["installed"])
        self.assertTrue(result["after"]["claude"]["DEV"]["enabled"])
        self.assertFalse(result["after"]["claude"]["RELEASE"]["enabled"])
        self.assertEqual(events[0]["event"], "before_switch")

    def test_reports_actual_account_state_if_partial_failure_cannot_be_restored(self) -> None:
        native = NativeSwitchClients()
        native.fail_claude_enable = True
        native.fail_restore = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 1)
        result = events[-1]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["recovery"]["status"], "failed")
        self.assertFalse(result["after"]["account"]["DEV"]["installed"])
        self.assertFalse(result["after"]["account"]["RELEASE"]["installed"])
        self.assertTrue(result["after"]["claude"]["RELEASE"]["enabled"])

    def test_check_does_not_change_either_native_client(self) -> None:
        native = NativeSwitchClients()
        code, events = invoke_switch(native)
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["status"], "checked")
        self.assertEqual(native.writes, [])

    def test_partial_claude_failure_restores_both_original_sources(self) -> None:
        native = NativeSwitchClients()
        native.fail_claude_enable = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 1)
        result = events[-1]
        self.assertEqual(result["recovery"]["status"], "restored")
        self.assertEqual(result["after"]["account"], result["before"]["account"])
        self.assertEqual(result["after"]["claude"], result["before"]["claude"])

    def test_resource_failure_restores_release_before_changing_claude(self) -> None:
        native = NativeSwitchClients()
        manifest = switch_manifest()
        manifest["plugins"]["example"]["account"]["DEV"]["resources"] = [
            {"skill": "example-dev:entry", "path": "scripts/tool.py", "sha256": "0" * 64}]
        with patch.object(Path, "read_bytes", return_value=b"wrong content"):
            code, events = invoke_switch(native, apply=True, manifest=manifest)
        self.assertEqual(code, 1)
        self.assertIn("resource hash mismatch", events[-1]["error"])
        self.assertEqual(events[-1]["recovery"]["status"], "restored")
        self.assertEqual(native.enabled, "RELEASE")

    def test_does_not_repeat_install_after_a_terminal_error_with_effect(self) -> None:
        native = NativeSwitchClients()
        native.install_terminal_error_after_effect = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["recovery"]["status"], "restored")
        self.assertEqual(native.writes.count(("plugin/install", "Plugin_DEV")), 1)
        self.assertEqual(native.installed, "RELEASE")

    def test_readiness_timeout_restores_release_instead_of_treating_sleep_as_success(self) -> None:
        native = NativeSwitchClients()
        native.dev_never_ready = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 1)
        self.assertIn("timeout", events[-1]["error"])
        self.assertEqual(events[-1]["recovery"]["status"], "restored")
        self.assertEqual(native.installed, "RELEASE")
        self.assertEqual(native.enabled, "RELEASE")

    def test_blocks_ambiguous_discovery_identity_before_any_write(self) -> None:
        native = NativeSwitchClients()
        native.ambiguous_identity = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["status"], "blocked")
        self.assertEqual(native.writes, [])

    def test_stale_local_package_version_does_not_pass_as_target_version(self) -> None:
        native = NativeSwitchClients()
        native.stale_dev_version = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 1)
        self.assertIn("local version", events[-1]["error"])
        self.assertEqual(events[-1]["recovery"]["status"], "restored")

    def test_does_not_enable_claude_target_when_disable_returns_without_effect(self) -> None:
        native = NativeSwitchClients()
        native.disable_without_effect = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 1)
        self.assertNotIn(("claude/enable", "DEV"), native.writes)
        self.assertEqual(events[-1]["recovery"]["status"], "restored")

    def test_verifies_resource_bytes_under_the_discovered_target_skill(self) -> None:
        manifest = switch_manifest()
        digest = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        manifest["plugins"]["example"]["account"]["DEV"]["resources"] = [
            {"skill": "example-dev:entry", "path": "scripts/tool.py", "sha256": digest}]
        with patch.object(Path, "read_bytes", return_value=b"hello"):
            code, events = invoke_switch(NativeSwitchClients(), apply=True, manifest=manifest)
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["readiness"]["resources"][0]["sha256"], digest)

    def test_recovery_does_not_enable_original_claude_source_if_disable_had_no_effect(self) -> None:
        native = NativeSwitchClients()
        native.claude_enable_response_lost = True
        native.dev_disable_without_effect = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 1)
        self.assertNotIn(("claude/enable", "RELEASE"), native.writes)
        result = events[-1]
        self.assertEqual(result["recovery"]["status"], "failed")
        self.assertTrue(result["after"]["claude"]["DEV"]["enabled"])
        self.assertFalse(result["after"]["claude"]["RELEASE"]["enabled"])

    def test_rejects_stale_loaded_claude_folder_version_even_when_install_version_matches(self) -> None:
        native = NativeSwitchClients()
        native.stale_claude_folder = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["status"], "failed")
        self.assertIn("loaded version", events[-1]["error"])
        self.assertEqual(events[-1]["recovery"]["status"], "restored")

    def test_accepts_missing_folder_fields_for_cache_loaded_claude_source(self) -> None:
        manifest = switch_manifest()
        manifest["plugins"]["example"]["claude"]["RELEASE"].pop("readFromFolder")
        code, events = invoke_switch(NativeSwitchClients(), apply=True, manifest=manifest)
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["after"]["claude"]["DEV"]["folderVersion"], "2")

    def test_blocks_claude_loading_errors_before_writes(self) -> None:
        native = NativeSwitchClients()
        native.claude_loading_errors = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["status"], "blocked")
        self.assertIn("failed to read plugin manifest", events[-1]["error"])
        self.assertEqual(native.writes, [])

    def test_inactive_claude_folder_can_omit_loaded_version_until_enabled(self) -> None:
        native = NativeSwitchClients()
        native.omit_inactive_folder_version = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["after"]["claude"]["DEV"]["folderVersion"], "2")

    def test_recovery_does_not_reinstall_original_account_object_if_target_remains_installed(self) -> None:
        native = NativeSwitchClients()
        native.fail_claude_enable = True
        native.dev_uninstall_without_effect = True
        code, events = invoke_switch(native, apply=True)
        self.assertEqual(code, 1)
        self.assertNotIn(("plugin/install", "Plugin_RELEASE"), native.writes)
        self.assertEqual(events[-1]["recovery"]["status"], "failed")
        self.assertTrue(events[-1]["after"]["account"]["DEV"]["installed"])
        self.assertFalse(events[-1]["after"]["account"]["RELEASE"]["installed"])

    def test_known_uninstallable_target_does_not_remove_working_account_source(self) -> None:
        for metadata in ({"availability": "DISABLED_BY_ADMIN"}, {"installPolicy": "NOT_AVAILABLE"},
                         {"disabledReason": "plan_not_eligible"}):
            with self.subTest(metadata=metadata):
                native = NativeSwitchClients()
                native.account_metadata["DEV"] = metadata
                code, events = invoke_switch(native, apply=True)
                self.assertEqual(code, 1)
                self.assertEqual(events[-1]["status"], "blocked")
                self.assertEqual(native.writes, [])
                self.assertIn(next(iter(metadata.values())), events[-1]["error"])

    def test_unresolved_delayed_install_stops_compensation_even_if_list_would_look_unchanged(self) -> None:
        native = NativeSwitchClients()
        native.defer_dev_install = True
        code, events = invoke_switch(native, apply=True, extra=("--timeout", "0.05"))
        self.assertEqual(code, 1)
        self.assertTrue(native.deferred_done.wait(1))
        self.assertNotIn(("plugin/install", "Plugin_RELEASE"), native.writes)
        result = events[-1]
        self.assertEqual(result["recovery"]["status"], "failed")
        self.assertEqual(result["after"]["account"]["status"], "unknown")
        self.assertEqual(result["after"]["account"]["pendingWrites"][0]["method"], "plugin/install")
        self.assertEqual(native.installed_modes, {"DEV"})


def switch_manifest() -> dict:
    return {"plugins": {"example": {
        "account": {
            "DEV": {"remotePluginId": "Plugin_DEV", "version": "0.0.2", "skills": ["example-dev:entry"]},
            "RELEASE": {"remotePluginId": "Plugin_RELEASE", "version": "0.0.1", "skills": ["example-release:entry"]},
        },
        "claude": {
            "DEV": {"id": "example@dev", "version": "1", "scope": "user", "readFromFolder": "/source/dev", "folderVersion": "2"},
            "RELEASE": {"id": "example@release", "version": "1", "scope": "user", "readFromFolder": None},
        },
    }}}


def invoke_switch(native, *, apply=False, extra=(), manifest=None):
    entry = runpy.run_path(str(PLUGIN_SYNC_ROOT / "scripts" / "plugin_sync.py"))["main"]
    output = io.StringIO()
    args = ["--manifest", "mapping.json", "--plugin", "example", "--mode", "DEV",
            "--ready-timeout", "0.2", "--poll-interval", "0.001", *extra]
    if apply:
        args.append("--apply")
    with patch.object(Path, "read_text", return_value=json.dumps(manifest or switch_manifest())), \
            patch.object(Path, "open", side_effect=lambda *args, **kwargs: io.StringIO()), patch.object(Path, "unlink"), \
            patch("subprocess.Popen", side_effect=native.start), \
            patch("subprocess.run", side_effect=native.claude), contextlib.redirect_stdout(output):
        code = entry(args)
    return code, [json.loads(line) for line in output.getvalue().splitlines()]


class NativeSwitchClients:
    """Native protocol boundary, including distinct install and discovery IDs."""

    def __init__(self):
        self.installed = "RELEASE"
        self.enabled = "RELEASE"
        self.pending_scans = 0
        self.writes = []
        self.starts = 0
        self.fail_claude_enable = False
        self.fail_restore = False
        self.install_terminal_error_after_effect = False
        self.dev_never_ready = False
        self.ambiguous_identity = False
        self.stale_dev_version = False
        self.disable_without_effect = False
        self.claude_enable_response_lost = False
        self.dev_disable_without_effect = False
        self.stale_claude_folder = False
        self.claude_loading_errors = False
        self.omit_inactive_folder_version = False
        self.dev_uninstall_without_effect = False
        self.account_metadata = {}
        self.defer_dev_install = False
        self.deferred_done = threading.Event()

    @property
    def installed(self):
        return next(iter(self.installed_modes)) if len(self.installed_modes) == 1 else None

    @installed.setter
    def installed(self, mode):
        self.installed_modes = {mode} if mode else set()

    @property
    def enabled(self):
        return next(iter(self.enabled_modes)) if len(self.enabled_modes) == 1 else None

    @enabled.setter
    def enabled(self, mode):
        self.enabled_modes = {mode} if mode else set()

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
                if owner.defer_dev_install and request["method"] == "plugin/install" and request["params"]["pluginName"] == "Plugin_DEV":
                    owner.writes.append(("plugin/install", "Plugin_DEV"))
                    def finish_late_write():
                        owner.installed_modes.add("DEV")
                        messages.put(json.dumps({"id": request["id"], "result": {"appsNeedingAuth": []}}) + "\n")
                        owner.deferred_done.set()
                    timer = threading.Timer(0.2, finish_late_write)
                    timer.daemon = True
                    timer.start()
                    return
                try:
                    result = owner.request(request["method"], request["params"])
                    response = {"id": request["id"], "result": result}
                except RuntimeError as error:
                    response = {"id": request["id"], "error": {"message": str(error)}}
                if getattr(owner, "lose_save_response", False) and request["method"] == "plugin/share/save":
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
        if method == "initialize":
            return {}
        if method == "plugin/list":
            return {"marketplaces": [{"plugins": [
                {"id": "ambiguous@created-by-me-remote" if self.ambiguous_identity else f"example-{mode.lower()}@created-by-me-remote", "remotePluginId": f"Plugin_{mode}",
                 "version": "0.0.2" if mode == "DEV" else "0.0.1",
                 "localVersion": ("0.0.2" if mode == "DEV" and not self.stale_dev_version else "0.0.1") if mode in self.installed_modes else None,
                 "installed": mode in self.installed_modes, "enabled": mode in self.installed_modes,
                 "availability": "AVAILABLE", "installPolicy": "AVAILABLE", "disabledReason": None,
                 **self.account_metadata.get(mode, {})}
                for mode in ("DEV", "RELEASE")]}]}
        if method == "plugin/uninstall":
            self.writes.append((method, params["pluginId"]))
            for mode in ("DEV", "RELEASE"):
                if params["pluginId"] == f"Plugin_{mode}" and not (self.dev_uninstall_without_effect and mode == "DEV"):
                    self.installed_modes.discard(mode)
            return {}
        if method == "plugin/install":
            self.writes.append((method, params["pluginName"]))
            if self.fail_restore and params["pluginName"] == "Plugin_RELEASE":
                raise RuntimeError("restore unavailable")
            self.installed_modes.add(params["pluginName"].removeprefix("Plugin_"))
            self.pending_scans = 2
            if self.install_terminal_error_after_effect and self.installed == "DEV":
                raise RuntimeError("terminal install error after effect")
            return {"appsNeedingAuth": [], "authPolicy": "ON_INSTALL"}
        if method == "skills/list":
            if self.dev_never_ready and self.installed == "DEV":
                skills = []
            elif self.pending_scans:
                self.pending_scans -= 1
                skills = []
            else:
                skills = [{"name": f"example-{mode.lower()}:entry", "pluginId": f"example-{mode.lower()}@created-by-me-remote",
                           "enabled": True, "path": f"/cache/{mode.lower()}/skills/entry/SKILL.md"}
                          for mode in self.installed_modes]
            return {"data": [{"cwd": "/repo", "errors": [], "skills": skills}]}
        raise AssertionError(method)

    def claude(self, command, **kwargs):
        args = command[2:]
        if args == ["list", "--json"]:
            # Actual responses are independent of the expected input mapping.
            items = [{"id": "example@dev" if mode == "DEV" else "example@release", "version": "1",
                      "scope": "user", "enabled": mode in self.enabled_modes, "installPath": f"/cache/{mode}"}
                     for mode in ("DEV", "RELEASE")]
            items[0].update(readFromFolder="/source/dev", folderVersion="1" if self.stale_claude_folder else "2")
            if self.omit_inactive_folder_version and "DEV" not in self.enabled_modes:
                items[0].pop("folderVersion")
            if self.claude_loading_errors:
                items[0]["errors"] = ["failed to read plugin manifest"]
            return subprocess.CompletedProcess(command, 0, json.dumps(items), "")
        mode = "DEV" if args[1] == "example@dev" else "RELEASE"
        self.writes.append(("claude/" + args[0], mode))
        if self.fail_claude_enable and args[0] == "enable" and mode == "DEV":
            return subprocess.CompletedProcess(command, 1, "", "enable failed")
        if args[0] == "enable":
            self.enabled_modes.add(mode)
            if self.claude_enable_response_lost and mode == "DEV":
                return subprocess.CompletedProcess(command, 1, "", "response lost after enabling")
        elif not ((self.disable_without_effect and mode == "RELEASE") or (self.dev_disable_without_effect and mode == "DEV")):
            self.enabled_modes.discard(mode)
        return subprocess.CompletedProcess(command, 0, "Successfully updated", "")


class NativeSaveClients(NativeSwitchClients):
    def __init__(self):
        super().__init__()
        self.objects = []
        self.save_result = {"remotePluginId": "Remote_created", "shareUrl": "https://example.test/private"}
        self.lose_save_response = False
        self.save_error = False
        self.post_collision = False
        self.post_hidden = False
        self.last_params = None
        self.personal = True
        self.catalog_metadata = {}
        self.methods = []

    def request(self, method, params):
        self.methods.append(method)
        if method == "initialize":
            return {}
        if method == "plugin/share/list":
            return {"data": [{"plugin": copy.deepcopy(item)} for item in self.objects]}
        if method == "plugin/list":
            values = copy.deepcopy(self.objects)
            for item in values:
                if self.personal:
                    item["shareContext"] = None
                item.update(self.catalog_metadata)
            if self.writes and self.post_collision:
                values.append({**values[0], "remotePluginId": "Unrelated"})
            return {"marketplaces": [{"plugins": [] if self.writes and self.post_hidden else values}]}
        if method == "plugin/share/save":
            self.last_params = params
            self.writes.append((method, params.get("remotePluginId")))
            remote_id = params.get("remotePluginId", "Remote_created")
            self.objects = [item for item in self.objects if item["remotePluginId"] != remote_id]
            self.objects.append(save_object(remote_id))
            if self.save_error:
                raise RuntimeError("save failed after effect")
            return self.save_result
        raise AssertionError(method)


def save_object(remote_id="Remote_created", version="0.0.2"):
    return {"remotePluginId": remote_id, "id": "example-dev@created-by-me-remote", "name": "example-dev",
            "version": version, "installed": False, "enabled": False, "localVersion": None,
            "shareContext": {"remotePluginId": remote_id, "discoverability": "PRIVATE", "sharePrincipals": []}}


def invoke_save(native, *, apply=False, store=None, extra=(), snapshot_error=None, action="save-account"):
    entry = runpy.run_path(str(PLUGIN_SYNC_ROOT / "scripts" / "plugin_sync.py"))["main"]
    store = store if store is not None else {"content": json.dumps({"plugins": {"example": {"account": {"DEV": {}}}}}).encode()}
    output = io.StringIO()
    snapshot = {"sha256": "a" * 64, "inputVersion": "b" * 64, "version": "0.0.2",
                "sourceCommit": "c" * 40, "sourceDirty": True, "metadataSource": {"repository": "owner/repo"},
                "pluginPath": "/snapshots/example", "packageName": "example-dev", "accountMode": "DEV"}
    class Temporary(io.BytesIO):
        name = "/mapping-temp"
        def fileno(self):
            return 0
        def close(self):
            store["temporary"] = self.getvalue()
            super().close()
    def replace(_path, _target):
        store["content"] = store["temporary"]
    args = ["--action", action, "--manifest", "/mapping.json", "--snapshots", "/snapshots.json",
            "--expected-sha256", "a" * 64, "--plugin", "example", "--mode", "DEV", "--timeout", "0.1" if native.lose_save_response else "1", *extra]
    if apply:
        args.append("--apply")
    with patch.object(Path, "read_bytes", side_effect=lambda: store["content"]), \
            patch.object(Path, "open", side_effect=lambda *args, **kwargs: io.StringIO()), \
            patch.object(Path, "replace", replace), patch.object(Path, "exists", return_value=False), \
            patch.object(Path, "unlink"), patch("os.fsync"), \
            patch("tempfile.NamedTemporaryFile", side_effect=lambda **kwargs: Temporary()), \
            patch.dict(entry.__globals__, {"verified_snapshot": lambda *args: snapshot if not snapshot_error else (_ for _ in ()).throw(ValueError(snapshot_error))}), \
            patch("subprocess.Popen", side_effect=native.start), patch("subprocess.run") as claude, \
            contextlib.redirect_stdout(output):
        code = entry(args)
    claude.assert_not_called()
    return code, [json.loads(line) for line in output.getvalue().splitlines()], store


class PluginAccountSaveEntryTests(unittest.TestCase):
    def test_first_save_does_not_require_other_object_or_installed_source(self):
        native = NativeSaveClients()
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 0)
        self.assertEqual(events[0]["event"], "before_account_save")
        self.assertEqual(events[-1]["status"], "saved")
        self.assertEqual(native.last_params, {"pluginPath": "/snapshots/example", "discoverability": "PRIVATE", "shareTargets": []})
        source = json.loads(store["content"])["plugins"]["example"]["account"]["DEV"]
        self.assertEqual(source["remotePluginId"], "Remote_created")
        self.assertEqual(source["saveState"]["status"], "verified")
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
        state = json.loads(store["content"])["plugins"]["example"]["account"]["DEV"]["saveState"]
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
                mapping = {"plugins": {"example": {"account": {"DEV": {"remotePluginId": "Remote_created", "version": "0.0.1"}}}}}
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

    def test_personal_update_with_unavailable_permissions_remains_blocked(self):
        native = NativeSaveClients()
        native.personal = True
        native.objects = [save_object(version="0.0.1")]
        mapping = {"plugins": {"example": {"account": {"DEV": {"remotePluginId": "Remote_created", "version": "0.0.1"}}}}}
        code, events, _ = invoke_save(native, apply=True, store={"content": json.dumps(mapping).encode()})
        self.assertEqual(code, 1)
        self.assertIn("update blocked", events[-1]["error"])
        self.assertEqual(native.writes, [])

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
        state = json.loads(store["content"])["plugins"]["example"]["account"]["DEV"]["saveState"]
        self.assertEqual(state["status"], "verified")
        self.assertEqual(state["permissions"]["status"], "not_available")
        self.assertEqual(len(native.writes), 1)
        self.assertNotIn("plugin/share/list", native.methods)

    def test_reconcile_legacy_success_does_not_invent_creation_or_permission_evidence(self):
        native = NativeSaveClients()
        native.post_hidden = True
        _, _, store = invoke_save(native, apply=True)
        value = json.loads(store["content"])
        state = value["plugins"]["example"]["account"]["DEV"]["saveState"]
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
                mapping["plugins"]["example"]["account"]["DEV"]["saveState"][field] = value
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
        mapping = {"plugins": {"example": {"account": {"DEV": {"remotePluginId": "Remote_created", "version": "0.0.1"}}}}}
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
        code, _, store = invoke_save(native, apply=True)
        self.assertEqual(code, 1)
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
        source = json.loads(store["content"])["plugins"]["example"]["account"]["DEV"]
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
        invoke_save(native, apply=True, store=store)
        self.assertEqual(len(native.writes), 1)

    def test_private_create_accepts_empty_share_url(self):
        native = NativeSaveClients()
        native.save_result["shareUrl"] = ""
        code, events, store = invoke_save(native, apply=True)
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["status"], "saved")
        source = json.loads(store["content"])["plugins"]["example"]["account"]["DEV"]
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
                source = json.loads(store["content"])["plugins"]["example"]["account"]["DEV"]
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
        source = json.loads(store["content"])["plugins"]["example"]["account"]["DEV"]
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
                mapping = {"plugins": {"example": {"account": {"DEV": {"remotePluginId": "Remote_created", "version": "0.0.1"}}}}}
                code, events, _ = invoke_save(native, apply=True, store={"content": json.dumps(mapping).encode()})
                self.assertEqual(code, 1)
                self.assertIn("sharing metadata conflicts", events[-1]["error"])
                self.assertEqual(native.writes, [])

    def test_unexpected_existing_response_id_is_recorded_without_binding_creation(self):
        native = NativeSaveClients()
        native.objects = [{**save_object("Unexpected"), "name": "other", "id": "other@created-by-me-remote"}]
        native.save_result = {"remotePluginId": "Unexpected", "shareUrl": "https://example.test/private"}
        mapping = {"plugins": {"example": {"account": {"DEV": {}}}}}
        code, events, store = invoke_save(native, apply=True, store={"content": json.dumps(mapping).encode()})
        self.assertEqual(code, 1)
        source = json.loads(store["content"])["plugins"]["example"]["account"]["DEV"]
        self.assertNotIn("remotePluginId", source)
        self.assertEqual(source["saveState"]["responseRemotePluginId"], "Unexpected")
        self.assertEqual(events[-1]["status"], "unverified")

    def test_save_preserves_other_plugin_and_source_mapping(self):
        native = NativeSaveClients()
        other = {"remotePluginId": "Other", "version": "1", "skills": ["other:entry"]}
        mapping = {"plugins": {"example": {"account": {"DEV": {}, "RELEASE": copy.deepcopy(other)}, "claude": {"kept": True}},
                               "other": {"account": {"DEV": copy.deepcopy(other)}}}, "kept": [1, 2]}
        code, _, store = invoke_save(native, apply=True, store={"content": json.dumps(mapping).encode()})
        self.assertEqual(code, 0)
        result = json.loads(store["content"])
        self.assertEqual(result["plugins"]["example"]["account"]["RELEASE"], other)
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
    def validate(self, *, corrupt=False, dirty=True, mode="DEV", link=False, expected=None):
        entry = runpy.run_path(str(PLUGIN_SYNC_ROOT / "scripts" / "plugin_sync.py"))["verified_snapshot"]
        package_name = "example-dev" if mode == "DEV" else "example"
        metadata = json.dumps({"name": package_name, "version": "0.0.2"})
        contents = {".codex-plugin/plugin.json": metadata.encode(), "skills/entry/SKILL.md": b"entry", "skills/entry/scripts/tool.py": b"print(1)"}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, content in contents.items():
                archive.writestr(name, content)
        archive_bytes = buffer.getvalue()
        digest = __import__("hashlib").sha256(archive_bytes).hexdigest()
        snapshot = {"sha256": digest, "inputVersion": "b" * 64, "sourceCommit": "c" * 40,
                    "sourceDirty": dirty, "metadataSource": {"repository": "owner/repo"}, "version": "0.0.2",
                    "artifact": "example.zip", "sizeBytes": len(archive_bytes), "pluginPath": "/snapshots/example", "packageName": package_name, "accountMode": mode}
        manifest = json.dumps({"version": 1, "plugins": {"example": snapshot}})
        directory = Path("/snapshots/example")
        files = [directory / name for name in contents]
        def read(path):
            if path.name == "example.zip":
                return archive_bytes
            return b"changed" if corrupt else contents[path.relative_to(directory).as_posix()]
        def stat(path):
            return SimpleNamespace(st_mode=0o644, st_size=len(archive_bytes) if path.name == "example.zip" else len(contents[path.relative_to(directory).as_posix()]))
        original_zip = zipfile.ZipFile
        with patch.object(Path, "resolve", lambda path: path), \
                patch.object(Path, "read_text", lambda path, **kwargs: metadata if path.name == "plugin.json" else manifest), \
                patch.object(Path, "read_bytes", read), patch.object(Path, "is_file", return_value=True), \
                patch.object(Path, "is_dir", return_value=True), patch.object(Path, "is_symlink", lambda path: link and path.name == "tool.py"), \
                patch.object(Path, "rglob", return_value=files), patch.object(Path, "stat", stat), \
                patch("zipfile.ZipFile", side_effect=lambda path: original_zip(io.BytesIO(archive_bytes))):
            return entry("/snapshots/snapshots.json", "example", expected or digest, mode, __import__("time").monotonic() + 30)

    def test_accepts_complete_reviewed_archive_and_matching_directory(self):
        self.assertEqual(self.validate()["pluginPath"], "/snapshots/example")

    def test_rejects_changed_directory_content(self):
        with self.assertRaisesRegex(Exception, "content or executable mode mismatch"):
            self.validate(corrupt=True)

    def test_rejects_symlink_inside_snapshot(self):
        with self.assertRaisesRegex(Exception, "complete archive"):
            self.validate(link=True)

    def test_rejects_unreviewed_digest(self):
        with self.assertRaisesRegex(Exception, "provenance"):
            self.validate(expected="0" * 64)

    def test_dirty_snapshot_cannot_update_release(self):
        with self.assertRaisesRegex(Exception, "development snapshot"):
            self.validate(mode="RELEASE")
        self.assertFalse(self.validate(mode="RELEASE", dirty=False)["sourceDirty"])
