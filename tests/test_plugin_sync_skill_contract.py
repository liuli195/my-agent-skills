from __future__ import annotations

from pathlib import Path
import contextlib
import io
import json
import queue
import runpy
import subprocess
import threading
import unittest
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
