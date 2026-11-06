"""Bounded, single-plugin account save or source switch through native interfaces.

This entry consumes explicit source mappings. It never performs a public release.
The app-server protocol is experimental; unknown state stops writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tempfile
import time
import uuid
import zipfile


class SwitchError(Exception):
    pass


def remaining_timeout(limit: float, deadline: float) -> float:
    remaining = min(limit, deadline - time.monotonic())
    if remaining <= 0:
        raise SwitchError("operation budget exhausted; no further client writes are allowed")
    return remaining


def unresolved_account_save(manifest: dict) -> dict | None:
    for mapping in manifest["plugins"].values():
        for source in mapping.get("account", {}).values():
            state = source.get("saveState", {})
            if state.get("status") not in (None, "verified"):
                return state
    return None


def load_mapping(path: str, plugin: str) -> tuple[dict, dict]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if unresolved_account_save(manifest):
        raise SwitchError("previous account save is unresolved or unverified; switching is blocked")
    mapping = manifest["plugins"][plugin]
    sources = mapping["account"]
    ids = [sources[mode]["remotePluginId"] for mode in ("DEV", "RELEASE")]
    if not all(isinstance(value, str) and value for value in ids) or ids[0] == ids[1]:
        raise SwitchError("DEV and RELEASE require distinct nonempty remotePluginId values")
    for source in sources.values():
        if not source.get("version") or not source.get("skills"):
            raise SwitchError("each source requires an expected version and skill names")
        if len(source["skills"]) != len(set(source["skills"])):
            raise SwitchError("duplicate expected skill names")
    return manifest, mapping


class AppServer:
    """One owned stdio process for preflight, switching, readiness and recovery."""

    def __init__(self, command: list[str], cwd: str, timeout: float, deadline: float):
        self.timeout = timeout
        self.deadline = deadline
        self.sequence = 0
        self.pending_writes: dict[int, dict] = {}
        self.messages: queue.Queue = queue.Queue()
        self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=None,
                                        text=True, encoding="utf-8", bufsize=1)
        def read() -> None:
            try:
                for line in self.process.stdout:
                    self.messages.put(json.loads(line))
            except (ValueError, OSError) as error:
                self.messages.put(error)
            finally:
                self.messages.put(None)
        threading.Thread(target=read, daemon=True).start()

    def notify(self, method: str, params: dict | None = None) -> None:
        value = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            value["params"] = params
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def call(self, method: str, params: dict, timeout: float | None = None) -> dict:
        deadline = time.monotonic() + remaining_timeout(min(self.timeout, timeout or self.timeout), self.deadline)
        mutating = method in ("plugin/install", "plugin/uninstall", "plugin/share/save")
        if mutating and self.pending_writes:
            raise SwitchError("unresolved account write; no further writes or compensation are allowed")
        self.sequence += 1
        request_id = self.sequence
        if mutating:
            self.pending_writes[request_id] = {"requestId": request_id, "method": method, "params": params}
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id,
                                             "method": method, "params": params}) + "\n")
        self.process.stdin.flush()
        while True:
            try:
                value = self.messages.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty as error:
                raise SwitchError(f"app-server timeout: {method}; " +
                                  ("write outcome unresolved; compensation stopped" if mutating else "response unavailable")) from error
            if value is None or isinstance(value, Exception):
                raise SwitchError(f"app-server unavailable: {method}; outcome unknown")
            if "method" in value and "id" in value:
                raise SwitchError("unexpected server request; no authentication or approval was accepted")
            if isinstance(value.get("result"), dict) or "error" in value:
                self.pending_writes.pop(value.get("id"), None)
            if value.get("id") != request_id:
                continue
            if "error" in value:
                raise SwitchError(f"{method}: {value['error']}")
            if not isinstance(value.get("result"), dict):
                raise SwitchError(f"invalid app-server result: {method}")
            return value["result"]

    def close(self) -> None:
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)


def account_state(server: AppServer, sources: dict) -> dict:
    response = server.call("plugin/list", {"marketplaceKinds": ["created-by-me-remote"], "forceRefetch": True})
    plugins = [plugin for market in response["marketplaces"] for plugin in market["plugins"]]
    state = {}
    for mode, source in sources.items():
        matches = [plugin for plugin in plugins if plugin.get("remotePluginId") == source["remotePluginId"]]
        if len(matches) != 1:
            raise SwitchError(f"expected exactly one account object for {mode}")
        item = matches[0]
        if source.get("packageName") and item.get("name") != source["packageName"]:
            raise SwitchError(f"account package name mismatch for {mode}")
        if item.get("version") != source["version"]:
            raise SwitchError(f"account version mismatch for {mode}: {item.get('version')}")
        state[mode] = {key: item.get(key) for key in
                       ("id", "remotePluginId", "version", "localVersion", "installed", "enabled",
                        "availability", "installPolicy", "disabledReason")}
    identities = [item["id"] for item in state.values()]
    if any(not isinstance(value, str) or not value for value in identities) or len(set(identities)) != len(identities):
        raise SwitchError("account discovery identities are missing or ambiguous")
    return state


def verify_account_installable(item: dict) -> None:
    if (item.get("availability") not in (None, "AVAILABLE", "ENABLED")
            or item.get("installPolicy") == "NOT_AVAILABLE" or item.get("disabledReason")):
        raise SwitchError(f"account source is not installable: {item['remotePluginId']}; "
                          f"availability={item.get('availability')}, installPolicy={item.get('installPolicy')}, "
                          f"disabledReason={item.get('disabledReason')}")


def install(server: AppServer, source: dict) -> None:
    result = server.call("plugin/install", {"remoteMarketplaceName": "created-by-me-remote",
                         "pluginName": source["remotePluginId"], "installAttemptId": str(uuid.uuid4())})
    if result.get("appsNeedingAuth"):
        raise SwitchError("installed plugin requires additional authentication; not accepted")


def uninstall(server: AppServer, source: dict) -> None:
    server.call("plugin/uninstall", {"pluginId": source["remotePluginId"]})


def wait_ready(server: AppServer, sources: dict, identities: dict, mode: str, cwd: str, timeout: float, interval: float) -> dict:
    deadline = time.monotonic() + timeout
    attempts = 0
    last = {}
    target = sources[mode]
    other_mode = "RELEASE" if mode == "DEV" else "DEV"
    while True:
        attempts += 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SwitchError(f"skill readiness timeout after {attempts - 1} scans: {last}")
        response = server.call("skills/list", {"cwds": [cwd], "forceReload": True}, timeout=remaining)
        entries = response["data"]
        skills = [skill for entry in entries for skill in entry["skills"]]
        # Discovery IDs are name@marketplace, not the raw remote IDs used by install.
        target_skills = [skill for skill in skills if skill.get("pluginId") == identities[mode]["id"]]
        other_skills = [skill for skill in skills if skill.get("pluginId") == identities[other_mode]["id"]]
        names = [skill["name"] for skill in target_skills if skill.get("enabled")]
        last = {"target": names, "otherCount": len(other_skills),
                "errors": [error for entry in entries for error in entry.get("errors", [])]}
        if sorted(names) == sorted(target["skills"]) and not other_skills and not last["errors"]:
            verified = []
            for resource in target.get("resources", []):
                matches = [skill for skill in target_skills if skill["name"] == resource["skill"]]
                if len(matches) != 1:
                    raise SwitchError("resource skill is not uniquely discovered")
                skill_path = Path(matches[0]["path"])
                relative = Path(resource["path"])
                if not skill_path.is_absolute() or relative.is_absolute() or ".." in relative.parts:
                    raise SwitchError("resource path is not a supported local child path")
                path = skill_path.parent / relative
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest != resource["sha256"]:
                    raise SwitchError(f"resource hash mismatch: {resource['path']}")
                verified.append({"skill": resource["skill"], "path": resource["path"], "sha256": digest})
            return {"attempts": attempts, "skills": names, "otherCount": 0, "resources": verified}
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SwitchError(f"skill readiness timeout after {attempts} scans: {last}")
        time.sleep(min(interval, remaining))


def claude_call(command: list[str], args: list[str], cwd: str, timeout: float, deadline: float) -> str:
    result = subprocess.run(command + ["plugin"] + args, cwd=cwd, capture_output=True,
                            text=True, encoding="utf-8", timeout=remaining_timeout(timeout, deadline))
    if result.returncode:
        raise SwitchError(f"Claude {' '.join(args)} failed ({result.returncode}): {result.stderr or result.stdout}")
    return result.stdout


def verify_claude_loading(item: dict, source: dict, *, check_loaded: bool = True) -> None:
    if item.get("errors"):
        raise SwitchError(f"Claude loading errors for {source['id']}: {item['errors']}")
    folder = item.get("readFromFolder")
    expected_folder = source.get("readFromFolder")
    if any(value is not None and (not isinstance(value, str) or not value) for value in (folder, expected_folder)):
        raise SwitchError("Claude readFromFolder must be a directory string or absent")
    if item.get("version") != source["version"] or (
            (folder is not None or check_loaded) and folder != expected_folder):
        raise SwitchError(f"Claude source/install version not verified: {source['id']}")
    if not check_loaded:
        return
    if folder is not None:
        expected_version = source.get("folderVersion")
        if not isinstance(expected_version, str) or not expected_version:
            raise SwitchError("Claude folder source requires an explicit expected folderVersion")
        loaded_version = item.get("folderVersion")
    else:
        expected_version = source["version"]
        loaded_version = item.get("version")
    if loaded_version != expected_version:
        raise SwitchError(f"Claude loaded version not verified: {source['id']}: {loaded_version}")


def claude_state(command: list[str], sources: dict, cwd: str, timeout: float, deadline: float, *, verify_loading: bool = True) -> dict:
    items = json.loads(claude_call(command, ["list", "--json"], cwd, timeout, deadline))
    state = {}
    for mode, source in sources.items():
        matches = [item for item in items if item.get("id") == source["id"] and item.get("scope") == source["scope"]]
        if len(matches) != 1:
            raise SwitchError(f"Claude {mode} requires exactly one preinstalled scoped source")
        item = matches[0]
        if verify_loading:
            verify_claude_loading(item, source, check_loaded=bool(item.get("enabled")))
        state[mode] = {key: item.get(key) for key in
                       ("id", "version", "scope", "enabled", "installPath", "readFromFolder", "folderVersion", "projectPath")}
        state[mode]["errors"] = item.get("errors") or []
    return state


def verified_snapshot(path: str, plugin: str, expected: str, mode: str, deadline: float) -> dict:
    """Validate the existing pack.py manifest and exact directory without rebuilding."""
    if not path or not expected or len(expected) != 64:
        raise SwitchError("save-account requires --snapshots and the reviewed --expected-sha256")
    manifest_path = Path(path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1:
        raise SwitchError("unsupported snapshot manifest version")
    snapshot = manifest["plugins"][plugin]
    package_name = snapshot.get("packageName")
    if snapshot.get("accountMode") != mode or package_name != plugin + ("-dev" if mode == "DEV" else ""):
        raise SwitchError("save-account requires an explicitly packaged matching account mode and packageName")
    hashes = ((snapshot["sha256"], 64), (snapshot["inputVersion"], 64), (snapshot["sourceCommit"], 40))
    if (snapshot["sha256"] != expected or any(not isinstance(value, str) or len(value) != size
            or any(character not in "0123456789abcdef" for character in value) for value, size in hashes)
            or not isinstance(snapshot["sourceDirty"], bool)
            or not snapshot.get("metadataSource", {}).get("repository")):
        raise SwitchError("snapshot digest or recorded source provenance is not verified")
    if mode == "RELEASE" and snapshot["sourceDirty"]:
        raise SwitchError("a dirty development snapshot cannot overwrite a RELEASE object")
    root = manifest_path.parent
    artifact = root / snapshot["artifact"]
    directory = Path(snapshot["pluginPath"])
    if (artifact.parent != root or artifact.is_symlink() or not artifact.is_file()
            or not directory.is_absolute() or directory.parent != root
            or directory.is_symlink() or not directory.is_dir()
            or artifact.stat().st_size != snapshot["sizeBytes"]):
        raise SwitchError("snapshot archive or pluginPath is not a verified sibling artifact")
    # Bound compressed and expanded input together below the user's disk budget.
    with zipfile.ZipFile(artifact) as archive:
        if artifact.stat().st_size + sum(item.file_size for item in archive.infolist()) > 500_000_000:
            raise SwitchError("snapshot exceeds the bounded save budget; request user approval")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != expected:
            raise SwitchError("snapshot archive digest mismatch")
        entries = archive.namelist()
        paths = list(directory.rglob("*"))
        files = {item.relative_to(directory).as_posix(): item for item in paths if item.is_file()}
        if (len(entries) != len(set(entries)) or set(files) != set(entries)
                or any(item.is_symlink() for item in paths)):
            raise SwitchError("snapshot directory does not match the complete archive")
        for name, item in files.items():
            remaining_timeout(120, deadline)
            if (item.stat().st_size != archive.getinfo(name).file_size
                    or item.read_bytes() != archive.read(name)
                    or (os.name != "nt" and archive.getinfo(name).create_system == 3
                        and (item.stat().st_mode & 0o111) != ((archive.getinfo(name).external_attr >> 16) & 0o111))):
                raise SwitchError("snapshot directory content or executable mode mismatch")
    metadata = json.loads((directory / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    if metadata.get("name") != package_name or metadata.get("version") != snapshot["version"]:
        raise SwitchError("snapshot plugin identity or version mismatch")
    return snapshot


def account_inventory(server: AppServer) -> tuple[list[dict], list[dict]]:
    shares = [item["plugin"] for item in server.call("plugin/share/list", {})["data"]]
    response = server.call("plugin/list", {"marketplaceKinds": ["created-by-me-remote"], "forceRefetch": True})
    if response.get("marketplaceLoadErrors"):
        raise SwitchError("account inventory is incomplete; marketplace loading failed")
    catalog = [item for market in response["marketplaces"] for item in market["plugins"]]
    return shares, catalog


def private_account_object(shares: list[dict], catalog: list[dict], remote_id: str, plugin: str, version: str) -> dict:
    matches = [item for item in shares if item.get("remotePluginId") == remote_id]
    found = [item for item in catalog if item.get("remotePluginId") == remote_id]
    if len(matches) != 1 or len(found) != 1:
        raise SwitchError("expected exactly one owned account object in both native inventories")
    item, discovered = matches[0], found[0]
    context = item.get("shareContext") or {}
    principals = context.get("sharePrincipals")
    if (context.get("remotePluginId") != remote_id or context.get("discoverability") != "PRIVATE"
            or not isinstance(principals, list) or len(principals) > 1
            or any(value.get("role") != "owner" or value.get("principalType") != "user" for value in principals)):
        raise SwitchError("account object is not verified private and owner-only; sharing was not changed")
    if any(value.get("name") != plugin or value.get("version") != version for value in (item, discovered)):
        raise SwitchError("account object identity or version does not match the explicit mapping")
    identity = discovered.get("id")
    if not isinstance(identity, str) or not identity or any(
            value.get("id") == identity and value.get("remotePluginId") != remote_id for value in catalog):
        raise SwitchError("account discovery identity is missing or conflicts; no rename was attempted")
    return {key: discovered.get(key) for key in
            ("id", "remotePluginId", "name", "version", "installed", "enabled", "localVersion")}


def save_account(args: argparse.Namespace) -> int:
    """One private object per invocation, with a durable no-retry marker before saving."""
    report = {"plugin": args.plugin, "target": args.mode, "action": "save-account", "status": "blocked"}
    server = None
    deadline = time.monotonic() + 600
    try:
        if not 0 < args.timeout <= 120:
            raise SwitchError("request timeout must be positive and <=120s")
        path = Path(args.manifest).resolve()
        original = path.read_bytes()
        manifest = json.loads(original)
        mapping = manifest["plugins"][args.plugin]
        sources = mapping["account"]
        source = sources[args.mode]
        # Stop expansion as well as retries after an unresolved or unverified save.
        pending = unresolved_account_save(manifest)
        if pending:
            report["saveState"] = pending
            raise SwitchError("previous account save is unresolved or unverified; inspect native state before any retry")
        snapshot = verified_snapshot(args.snapshots, args.plugin, args.expected_sha256, args.mode, deadline)
        package_name = snapshot["packageName"]
        if source.get("packageName", package_name) != package_name:
            raise SwitchError("snapshot packageName differs from the authorized account mapping; no rename was attempted")
        remote_id = source.get("remotePluginId")
        if remote_id is not None and (not isinstance(remote_id, str) or not remote_id):
            raise SwitchError("remotePluginId must be a verified nonempty string or absent for first creation")
        if remote_id and any(value.get("remotePluginId") == remote_id for mode, value in sources.items() if mode != args.mode):
            raise SwitchError("DEV and RELEASE cannot share an account object")
        server = AppServer(manifest.get("codexCommand", ["codex", "app-server", "--stdio"]),
                           args.cwd, args.timeout, deadline)
        server.call("initialize", {"clientInfo": {"name": "plugin-sync", "version": "1"},
                                   "capabilities": {"experimentalApi": True}})
        server.notify("initialized")
        shares, catalog = account_inventory(server)
        if remote_id:
            report["before"] = private_account_object(shares, catalog, remote_id, package_name, source["version"])
        elif any(item.get("name") == package_name for item in shares + catalog):
            raise SwitchError("an account object with this package name already exists; verify and map its real ID before creation")
        report["operation"] = "update" if remote_id else "create"
        report["snapshot"] = {key: snapshot[key] for key in
                              ("sha256", "version", "sourceCommit", "sourceDirty", "inputVersion", "metadataSource", "accountMode", "packageName")}
        if not args.apply:
            report["status"] = "checked"
            report["next"] = "review source contents and authorize this exact private save before --apply"
            return 0

        def persist() -> None:
            nonlocal original
            if path.read_bytes() != original:
                raise SwitchError("mapping changed concurrently; no further account writes are allowed")
            payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".plugin-sync-", delete=False) as output:
                    temporary = Path(output.name)
                    output.write(payload)
                    output.flush()
                    os.fsync(output.fileno())
                temporary.replace(path)
                original = payload
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()

        state = {"status": "pending", "operationId": str(uuid.uuid4()), "operation": report["operation"],
                 "remotePluginId": remote_id, "snapshot": report["snapshot"]}
        source["saveState"] = state
        persist()  # A crash after this point blocks repeats even across invocations.
        report["saveState"] = state
        print(json.dumps({"event": "before_account_save", **report}, ensure_ascii=False), flush=True)
        # Recheck the reviewed artifact immediately before transmitting any bytes.
        if verified_snapshot(args.snapshots, args.plugin, args.expected_sha256, args.mode, deadline) != snapshot:
            raise SwitchError("snapshot manifest changed after preflight; account save was not sent")
        params = {"pluginPath": snapshot["pluginPath"]}
        if remote_id:
            params["remotePluginId"] = remote_id
        else:
            params.update(discoverability="PRIVATE", shareTargets=[])
        result = server.call("plugin/share/save", params)
        returned = result.get("remotePluginId")
        if not isinstance(returned, str) or not returned:
            raise SwitchError("save response has no verified remotePluginId; no retry is allowed")
        state.update(status="unverified", responseRemotePluginId=returned)
        persist()  # Retain the real response ID even if the next check fails.
        if ((remote_id and returned != remote_id) or (not remote_id and any(
                item.get("remotePluginId") == returned for item in shares + catalog))):
            raise SwitchError("save returned an unexpected account object; original mapping was not replaced")
        source.update(remotePluginId=returned, version=snapshot["version"], packageName=package_name)
        persist()
        if not isinstance(result.get("shareUrl"), str) or not result["shareUrl"]:
            raise SwitchError("save response is incomplete; object recorded but not verified")
        shares, catalog = account_inventory(server)
        report["after"] = private_account_object(shares, catalog, returned, package_name, snapshot["version"])
        state["status"] = "verified"
        persist()
        report["status"] = "saved"
        report["runtimeVerification"] = "not installed or loaded; source switching and fresh-session checks remain separate"
        return 0
    except (SwitchError, OSError, ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        report["error"] = str(error)
        if report.get("saveState"):
            report["status"] = "unknown" if report["saveState"]["status"] == "pending" else "unverified"
        return 1
    finally:
        try:
            if server:
                server.close()
        except (OSError, subprocess.SubprocessError) as error:
            report["cleanupError"] = str(error)
        print(json.dumps(report, ensure_ascii=False), flush=True)
        if report.get("cleanupError"):
            return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("switch", "save-account"), default="switch")
    parser.add_argument("--snapshots", help="complete snapshot manifest for save-account")
    parser.add_argument("--expected-sha256", help="explicitly reviewed snapshot archive digest")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--mode", choices=("DEV", "RELEASE"), required=True)
    parser.add_argument("--cwd", default=str(Path.cwd()))
    parser.add_argument("--apply", action="store_true", help="apply the explicitly authorized selected action")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--ready-timeout", type=float, default=60)
    parser.add_argument("--poll-interval", type=float, default=1)
    args = parser.parse_args(argv)
    lock = None
    try:
        if args.apply:
            path = Path(args.manifest).resolve()
            lock_path = path.with_name(path.name + ".lock")
            lock = lock_path.open("x", encoding="utf-8")
        return save_account(args) if args.action == "save-account" else switch_sources(args)
    except OSError as error:
        print(json.dumps({"plugin": args.plugin, "target": args.mode, "action": args.action,
                          "status": "blocked", "error": str(error)}, ensure_ascii=False), flush=True)
        return 1
    finally:
        if lock:
            try:
                lock.close()
                lock_path.unlink()
            except OSError as error:
                print(json.dumps({"event": "mapping_lock_cleanup_failed", "status": "failed", "error": str(error)}), flush=True)
                return 1


def switch_sources(args: argparse.Namespace) -> int:
    report = {"plugin": args.plugin, "target": args.mode, "status": "blocked", "before": {}, "after": {}}
    server = None
    changed = False
    deadline = time.monotonic() + 600  # Whole invocation, including recovery, stays below fifteen minutes.
    try:
        if not 0 < args.timeout <= 120 or not 0 < args.ready_timeout <= 300 or not 0 < args.poll_interval <= 10:
            raise SwitchError("timeouts must be positive and bounded (request <=120s, readiness <=300s, poll <=10s)")
        manifest, mapping = load_mapping(args.manifest, args.plugin)
        account = mapping["account"]
        claude = mapping["claude"]
        command = manifest.get("codexCommand", ["codex", "app-server", "--stdio"])
        claude_command = manifest.get("claudeCommand", ["claude"])
        server = AppServer(command, args.cwd, args.timeout, deadline)
        server.call("initialize", {"clientInfo": {"name": "plugin-sync", "version": "1"},
                                   "capabilities": {"experimentalApi": True}})
        server.notify("initialized")
        before = account_state(server, account)
        report["before"] = {"account": before, "claude": claude_state(claude_command, claude, args.cwd, args.timeout, deadline)}
        if sum(bool(item["enabled"]) for item in report["before"]["claude"].values()) != 1:
            raise SwitchError("Claude requires exactly one enabled source before switching")
        old_modes = [mode for mode, item in before.items() if item["installed"]]
        if len(old_modes) != 1 or not before[old_modes[0]]["enabled"]:
            raise SwitchError("account requires exactly one installed, enabled source before switching")
        old = old_modes[0]
        if before[old]["localVersion"] != account[old]["version"]:
            raise SwitchError("installed account local version is not the expected restorable version")
        verify_account_installable(before[args.mode])
        if old != args.mode:
            verify_account_installable(before[old])
        if not args.apply:
            report["status"] = "checked"
            report["next"] = "repeat with --apply only after exact targets and actions are authorized"
            return 0
        # Flush the complete original state before the first external write.
        print(json.dumps({"event": "before_switch", **report}, ensure_ascii=False), flush=True)
        changed = True
        if old != args.mode:
            uninstall(server, account[old])
            removed = account_state(server, account)
            if removed[old]["installed"]:
                raise SwitchError("uninstall returned but old account object is still installed")
            verify_account_installable(removed[args.mode])
            install(server, account[args.mode])
        report["readiness"] = wait_ready(server, account, before, args.mode, args.cwd, args.ready_timeout, args.poll_interval)
        after = account_state(server, account)
        verify_account_installable(after[args.mode])
        if not after[args.mode]["installed"] or not after[args.mode]["enabled"] or any(
                item["installed"] for mode, item in after.items() if mode != args.mode):
            raise SwitchError("account post-switch state did not match the target")
        if after[args.mode]["localVersion"] != account[args.mode]["version"]:
            raise SwitchError("installed account local version did not match the target")
        original_claude = report["before"]["claude"]
        for mode in ("DEV", "RELEASE"):
            if mode != args.mode and original_claude[mode]["enabled"]:
                claude_call(claude_command, ["disable", claude[mode]["id"], "--scope", claude[mode]["scope"]], args.cwd, args.timeout, deadline)
        intermediate_claude = claude_state(claude_command, claude, args.cwd, args.timeout, deadline)
        if any(item["enabled"] for mode, item in intermediate_claude.items() if mode != args.mode):
            raise SwitchError("Claude old source remains enabled; target was not enabled")
        if not original_claude[args.mode]["enabled"]:
            claude_call(claude_command, ["enable", claude[args.mode]["id"], "--scope", claude[args.mode]["scope"]], args.cwd, args.timeout, deadline)
        final_claude = claude_state(claude_command, claude, args.cwd, args.timeout, deadline)
        if not final_claude[args.mode]["enabled"] or any(
                item["enabled"] for mode, item in final_claude.items() if mode != args.mode):
            raise SwitchError("Claude did not enable the target")
        report["after"] = {"account": after, "claude": final_claude}
        report["status"] = "switched"
        report["sessionValidation"] = {"dot": "fresh session still required", "codex": "fresh session still required",
                                       "claude": "native state only; model session not tested"}
        return 0
    except (SwitchError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
        if changed:
            report["status"] = "failed"
            recovery_errors = []
            try:
                if server.pending_writes:
                    raise SwitchError("account write has no terminal response; compensation stopped")
                current = account_state(server, account)
                for mode, item in current.items():
                    if item["installed"] and not before[mode]["installed"]:
                        uninstall(server, account[mode])
                current = account_state(server, account)
                if any(item["installed"] and not before[mode]["installed"] for mode, item in current.items()):
                    raise SwitchError("account recovery uninstall had no effect; original source was not installed")
                for mode, item in before.items():
                    if item["installed"] and not current[mode]["installed"]:
                        verify_account_installable(current[mode])
                        install(server, account[mode])
                restored = account_state(server, account)
                keys = ("id", "remotePluginId", "version", "installed", "enabled")
                if any(any(restored[mode][key] != item[key] for key in keys) for mode, item in before.items()):
                    raise SwitchError("account recovery differs from original state")
                if restored[old]["localVersion"] != before[old]["localVersion"]:
                    raise SwitchError("account recovery local version differs from original state")
                wait_ready(server, account, before, old, args.cwd, args.ready_timeout, args.poll_interval)
                report["after"]["account"] = restored
            except (SwitchError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as recovery:
                recovery_errors.append(f"account: {recovery}")
                if server.pending_writes:
                    report["after"]["account"] = {"status": "unknown", "pendingWrites": list(server.pending_writes.values())}
                else:
                    try:
                        report["after"]["account"] = account_state(server, account)
                    except (SwitchError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as observation:
                        report["after"]["account"] = {"status": "unknown", "error": str(observation)}
            try:
                current = claude_state(claude_command, claude, args.cwd, args.timeout, deadline, verify_loading=False)
                # Recheck effective disable state before any recovery enable.
                for mode, item in report["before"]["claude"].items():
                    if not item["enabled"] and current[mode]["enabled"]:
                        claude_call(claude_command, ["disable", item["id"], "--scope", item["scope"]], args.cwd, args.timeout, deadline)
                current = claude_state(claude_command, claude, args.cwd, args.timeout, deadline, verify_loading=False)
                if any(current[mode]["enabled"] for mode, item in report["before"]["claude"].items() if not item["enabled"]):
                    raise SwitchError("Claude recovery disable had no effect; original source was not enabled")
                for mode, item in report["before"]["claude"].items():
                    if item["enabled"]:
                        verify_claude_loading(current[mode], claude[mode], check_loaded=False)
                        if not current[mode]["enabled"]:
                            claude_call(claude_command, ["enable", item["id"], "--scope", item["scope"]], args.cwd, args.timeout, deadline)
                restored = claude_state(claude_command, claude, args.cwd, args.timeout, deadline, verify_loading=False)
                for mode, item in report["before"]["claude"].items():
                    if item["enabled"]:
                        verify_claude_loading(restored[mode], claude[mode])
                keys = ("id", "version", "scope", "enabled", "installPath", "projectPath", "errors")
                if any(any(restored[mode][key] != item[key] for key in keys) for mode, item in report["before"]["claude"].items()):
                    raise SwitchError("Claude recovery differs from original state")
                report["after"]["claude"] = restored
            except (SwitchError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as recovery:
                recovery_errors.append(f"claude: {recovery}")
                try:
                    report["after"]["claude"] = claude_state(claude_command, claude, args.cwd, args.timeout, deadline, verify_loading=False)
                except (SwitchError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as observation:
                    report["after"]["claude"] = {"status": "unknown", "error": str(observation)}
            report["recovery"] = {"status": "failed" if recovery_errors else "restored", "errors": recovery_errors}
        return 1
    finally:
        if server:
            try:
                server.close()
            except (OSError, subprocess.SubprocessError) as error:
                report["cleanupError"] = str(error)
                report["status"] = "failed"
                print(json.dumps(report, ensure_ascii=False), flush=True)
                return 1
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    sys.exit(main())
