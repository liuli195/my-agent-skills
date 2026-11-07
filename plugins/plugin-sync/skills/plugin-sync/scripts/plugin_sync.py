"""Offline preparation and receipts; Creator calls belong to the host skill."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
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
    if mode != "RELEASE" or snapshot.get("accountMode") != "RELEASE" or package_name != plugin:
        raise SwitchError("save-account requires an explicitly packaged matching account mode and packageName")
    hashes = ((snapshot["sha256"], 64), (snapshot["inputVersion"], 64), (snapshot["sourceCommit"], 40))
    if (snapshot["sha256"] != expected or any(not isinstance(value, str) or len(value) != size
            or any(character not in "0123456789abcdef" for character in value) for value, size in hashes)
            or not isinstance(snapshot["sourceDirty"], bool)
            or not snapshot.get("metadataSource", {}).get("repository")):
        raise SwitchError("snapshot digest or recorded source provenance is not verified")
    if snapshot["sourceDirty"]:
        raise SwitchError("a dirty development snapshot cannot overwrite a RELEASE object")
    release_ref = snapshot.get("releaseRef")
    if not isinstance(release_ref, str) or not release_ref.startswith("refs/tags/") or not release_ref.removeprefix("refs/tags/"):
        raise SwitchError("RELEASE snapshots require the reviewed existing release tag reference")
    root = manifest_path.parent
    artifact = root / snapshot["artifact"]
    recorded_path = snapshot.get("pluginPath")
    if (not isinstance(recorded_path, str) or ".." in recorded_path.replace("\\", "/").split("/")
            or recorded_path.replace("\\", "/").rsplit("/", 1)[-1] != artifact.stem):
        raise SwitchError("snapshot pluginPath is not the recorded archive directory")
    # CI paths are machine-local. Only the verified sibling directory is transmitted.
    directory = root / artifact.stem
    if (artifact.parent != root or artifact.suffix != ".zip" or artifact.is_symlink() or not artifact.is_file()
            or directory.is_symlink() or not directory.is_dir()
            or artifact.stat().st_size != snapshot["sizeBytes"]):
        raise SwitchError("snapshot archive or pluginPath is not a verified sibling artifact")
    snapshot = {**snapshot, "pluginPath": str(directory)}
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


def unpack_delivery_bundle(bundle: Path, destination: Path, deadline: float) -> Path:
    """Unpack one transport container into a newly owned directory, never into user contents."""
    if bundle.is_symlink() or not bundle.is_file() or bundle.stat().st_size > 500_000_000:
        raise SwitchError("delivery bundle is not a bounded regular file")
    with tarfile.open(bundle, "r:") as archive:
        members = archive.getmembers()
        total = bundle.stat().st_size
        seen = set()
        for member in members:
            remaining_timeout(120, deadline)
            relative = PurePosixPath(member.name)
            name = relative.as_posix()
            if (relative.is_absolute() or ".." in relative.parts or "\\" in member.name or ":" in member.name
                    or name in seen or member.size < 0 or not (member.isfile() or member.isdir())):
                raise SwitchError("delivery bundle contains an unsafe path or file type")
            seen.add(name)
            total += member.size
            if total > 500_000_000:
                raise SwitchError("delivery bundle exceeds the bounded extraction budget")
        def bounded_data_filter(member: tarfile.TarInfo, target: str) -> tarfile.TarInfo | None:
            remaining_timeout(120, deadline)
            return tarfile.data_filter(member, target)
        archive.extractall(destination, members=members, filter=bounded_data_filter)
        remaining_timeout(120, deadline)
    manifest = destination / "snapshots.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise SwitchError("delivery bundle has no regular snapshots.json")
    return manifest



def version_key(value):
    match = re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value or "")
    if not match:
        raise ValueError("a strict stable semantic version is required")
    return tuple(map(int, match.groups()))


def safe_files(files):
    if not isinstance(files, dict):
        raise ValueError("file inventory must be a path/digest mapping")
    for path, digest in files.items():
        relative = PurePosixPath(path)
        if (relative.is_absolute() or ".." in relative.parts or "\\" in path
                or relative.as_posix() != path or ":" in path or not relative.parts
                or not re.fullmatch("[0-9a-f]{64}", digest or "")):
            raise ValueError("invalid complete file inventory")
    return files


def prepare_plan(snapshot, current, remote_files, target_files, *, managed_files=(), inventory_complete=False,
                 personal_context=False, owned_plugins=(), verified_operation=None):
    """Public offline seam: reviewed inputs produce exactly one host tool plan."""
    target_files = safe_files(target_files)
    if not inventory_complete or not target_files:
        raise ValueError("complete official file inventory is required")
    archive = str(Path(snapshot["pluginPath"]).parent / snapshot["artifact"])
    plan = {"packageName": snapshot["packageName"], "version": snapshot["version"],
            "sha256": snapshot["sha256"], "files": target_files, "accountWrites": 0}
    version_key(snapshot["version"])
    if current is None:
        if not personal_context:
            raise ValueError("fresh successful official personal account listing is required before create")
        if any(item.get("name") == snapshot["packageName"] for item in owned_plugins):
            raise ValueError("same name object exists; map its exact identity before create")
        plan.update(tool="create_plugin", params={"archive": archive},
                    priorObjectIds=sorted(item["plugin_id"] for item in owned_plugins))
    else:
        if (current.get("scope") != "USER" or current.get("discoverability") != "PRIVATE"
                or current.get("name") != snapshot["packageName"]
                or not current.get("plugin_id") or not current.get("current_release_id")):
            raise ValueError("personal private identity and current release must be explicit")
        remote_files = safe_files(remote_files)
        target_version, current_version = version_key(snapshot["version"]), version_key(current.get("version"))
        if target_version == current_version:
            if remote_files != target_files:
                prior = verified_operation if isinstance(verified_operation, dict) else {}
                old_plan, old_read = prior.get("plan", {}), prior.get("readback", {})
                if (prior.get("status") != "verified" or prior.get("verificationMethod") != "accepted_wrapper_metadata"
                        or old_plan.get("planSha256") != plan_digest(old_plan)
                        or old_plan.get("packageName") != current["name"] or old_plan.get("version") != current["version"]
                        or old_plan.get("sha256") != snapshot["sha256"]
                        or old_plan.get("files") != target_files or old_read.get("files") != remote_files
                        or any(old_read.get(key) != current.get(key) for key in
                               ("plugin_id", "name", "version", "current_release_id", "scope", "discoverability"))):
                    raise ValueError("same version has different content; no automatic patch bump")
                accepted_metadata_record(old_plan, prior.get("receipt"), old_read,
                                         prior.get("verification", {}).get("evidence"))
                plan["verifiedOperationId"] = old_plan["operationId"]
            plan.update(tool=None, status="unchanged", remotePluginId=current["plugin_id"])
            return plan
        if target_version < current_version:
            raise ValueError("target version must be higher")
        removed = set(remote_files) - set(target_files)
        if removed - set(managed_files):
            raise ValueError("unmanaged or generated remote files require explicit resolution")
        plan.update(tool="update_plugin", params={"archive": archive, "plugin_id": current["plugin_id"],
                    "expected_release_id": current["current_release_id"], "delete_paths": sorted(removed)})
    plan["operationId"] = str(uuid.uuid4())
    plan["planSha256"] = plan_digest(plan)
    return plan


def plan_digest(plan):
    return hashlib.sha256(json.dumps({k: v for k, v in plan.items() if k != "planSha256"},
                                    sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def rejection_record(proof, operation_id, digest, tool, remote_id, recorded_at):
    """Validate host-normalized evidence; never invent Creator error codes."""
    error = proof.get("officialError", {})
    raw = json.dumps(error, sort_keys=True, ensure_ascii=False)
    quote = proof.get("notAppliedQuote")
    try:
        fresh = (datetime.fromisoformat(proof.get("readAt", "").replace("Z", "+00:00"))
                 >= datetime.fromisoformat(recorded_at))
    except (ValueError, TypeError):
        fresh = False
    current = proof.get("currentReadback", {})
    if (proof.get("operationId") != operation_id or proof.get("planSha256") != digest
            or proof.get("tool") != tool or proof.get("remotePluginId") != remote_id
            or proof.get("classification") != "explicit_not_applied"
            or not isinstance(error, dict) or error.get("isError") is not True
            or proof.get("officialErrorSha256") != hashlib.sha256(raw.encode()).hexdigest()
            or not isinstance(quote, str) or len(quote) < 10 or quote not in raw
            or not fresh or not isinstance(current, dict)
            or (remote_id and (current.get("plugin_id") != remote_id
                or current.get("scope") != "USER" or current.get("discoverability") != "PRIVATE"
                or not current.get("current_release_id")))):
        raise ValueError("explicit official rejection evidence is incomplete; unknown remains blocked")
    # The host must interpret this verbatim quote; a generic isError/timeout is not proof.
    return {"status": "rejected", "evidence": proof}


def reconcile_legacy(state, plugin, mode, success, readback):
    source = state["plugins"][plugin]["account"][mode]
    old = source["saveState"]
    snapshot = old.get("snapshot", {})
    remote_id = old.get("responseRemotePluginId")
    if (old.get("status") != "unverified" or old.get("operation") not in ("create", "update")
            or not remote_id or source.get("remotePluginId") != remote_id
            or success.get("plugin_id", success.get("remotePluginId")) != remote_id
            or success.get("version", snapshot.get("version")) != snapshot.get("version")
            or not snapshot.get("sha256") or readback.get("artifactSha256") != snapshot["sha256"]
            or not readback.get("complete") or not readback.get("files")
            or readback.get("plugin_id") != remote_id or readback.get("name") != snapshot.get("packageName")
            or source.get("version") != snapshot.get("version")
            or readback.get("version") != snapshot.get("version")
            or readback.get("scope") != "USER" or readback.get("discoverability") != "PRIVATE"
            or not readback.get("current_release_id")):
        raise ValueError("historical success and exact official content are not proven; record retained")
    safe_files(readback["files"])
    old["resolution"] = {"status": "verified", "officialSuccess": success, "readback": readback}
    return state


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("invalid JSON constant")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def manifest_changes(source, observed, prefix=""):
    changes = []
    for key in sorted(set(source) | set(observed)):
        path = prefix + "/" + key.replace("~", "~0").replace("/", "~1")
        if key in source and key in observed and isinstance(source[key], dict) and isinstance(observed[key], dict):
            changes.extend(manifest_changes(source[key], observed[key], path))
        elif (key not in source or key not in observed
              or json.dumps(source[key], sort_keys=True) != json.dumps(observed[key], sort_keys=True)):
            changes.append({"path": path, "action": "replace" if key in source else "add",
                "before": {"present": key in source, **({"value": source[key]} if key in source else {})},
                "after": {"present": key in observed, **({"value": observed[key]} if key in observed else {})}})
    return changes


def accepted_metadata_record(plan, receipt, readback, proof):
    """Audit one explicitly accepted creation result; never infer account identity from display fields."""
    if not isinstance(proof, dict) or not isinstance(receipt, dict) or not isinstance(readback, dict):
        raise ValueError("accepted metadata requires original success and complete readback")
    expected = {"operationId": plan["operationId"], "planSha256": plan["planSha256"], "archiveSha256": plan["sha256"],
                "plugin_id": receipt.get("plugin_id"), "release_id": receipt.get("release_id"), "version": plan["version"]}
    if (plan["tool"] != "create_plugin" or receipt.get("status") != "created"
            or any(proof.get(key) != value or not value for key, value in expected.items())
            or receipt.get("version") != plan["version"]
            or any(item.get("scope") != "USER" or item.get("discoverability") != "PRIVATE" for item in (receipt, readback))
            or readback.get("plugin_id") != receipt.get("plugin_id")
            or readback.get("current_release_id") != receipt.get("release_id")
            or readback.get("name") != plan["packageName"] or readback.get("version") != plan["version"]
            or readback.get("complete") is not True):
        raise ValueError("accepted metadata identity or source binding mismatch")
    acceptance = proof.get("acceptance", {})
    owned = proof.get("owned", {})
    if not isinstance(acceptance, dict) or not isinstance(owned, dict) or not isinstance(owned.get("plugins"), list):
        raise ValueError("invalid acceptance or personal ownership evidence")
    matching = [p for p in owned["plugins"] if isinstance(p, dict) and p.get("plugin_id") == receipt["plugin_id"]]
    if (acceptance.get("accepted") is not True or not isinstance(acceptance.get("reference"), str)
            or not acceptance["reference"].strip() or "next_cursor" not in owned or owned["next_cursor"] is not None
            or len(matching) != 1 or any(matching[0].get(k) != readback.get(k)
                for k in ("plugin_id", "name", "version", "current_release_id", "scope", "discoverability"))):
        raise ValueError("explicit acceptance and official personal ownership evidence required")
    path = ".codex-plugin/plugin.json"  # The release snapshot format already validated by this module.
    target, actual = safe_files(plan["files"]), safe_files(readback["files"])
    if set(target) != set(actual) or path not in target or any(target[k] != actual[k] for k in target if k != path):
        raise ValueError("non-wrapper files must match exactly")
    parsed = []
    for field, digest in (("sourceManifest", target[path]), ("observedManifest", actual[path])):
        text = proof.get(field)
        if not isinstance(text, str) or len(text.encode()) > 1_048_576 or hashlib.sha256(text.encode()).hexdigest() != digest:
            raise ValueError("raw manifest evidence digest mismatch")
        value = strict_json(text)
        if not isinstance(value, dict):
            raise ValueError("manifest must be an object")
        parsed.append(value)
    changes = manifest_changes(*parsed)
    allowed = {"/author/name", "/author/email", "/interface/developerName"}
    if (not changes or len(changes) > 3 or any(c["path"] not in allowed or c["after"].get("present") is not True
            or any(v.get("present") and (not isinstance(v.get("value"), str) or not v["value"].strip())
                   for v in (c["before"], c["after"])) for c in changes)
            or not isinstance(proof.get("changes"), list)
            or sorted(proof["changes"], key=lambda c: c.get("path", "")) != changes):
        raise ValueError("manifest differs outside the exact accepted values and actions")
    return {"method": "accepted_wrapper_metadata", "evidence": proof,
            "sourceManifestSha256": target[path], "observedManifestSha256": actual[path]}


def transition(state, plan, *, receipt=None, readback=None, rejection=None, accepted_metadata=None):
    """Mark before host sends; only exact official readback can resolve a sent plan."""
    if plan.get("planSha256") != plan_digest(plan) or not plan.get("tool"):
        raise ValueError("plan changed or does not require a save")
    for mapping in state.get("plugins", {}).values():
        for source in mapping.get("account", {}).values():
            saved = source.get("saveState", {})
            if (saved.get("status") not in (None, "verified")
                    and saved.get("resolution", {}).get("status") not in ("verified", "rejected")):
                raise ValueError("legacy unresolved save must be reconciled before another send")
    operations = state.setdefault("operations", {})
    operation = operations.get(plan["operationId"])
    if receipt is None and readback is None and rejection is None and accepted_metadata is None:
        if operation is not None:
            raise ValueError("operation already exists; never resend a recorded plan")
        if any(item.get("status") in ("pending", "unknown", "unverified") for item in operations.values()):
            raise ValueError("unresolved save; read back before any new send")
        operations[plan["operationId"]] = {"status": "pending", "plan": plan, "recordedAt": datetime.now(timezone.utc).isoformat()}
        return state
    if not operation or operation.get("plan") != plan or operation.get("status") not in ("pending", "unknown", "unverified"):
        raise ValueError("no matching unresolved operation")
    audit = None
    if accepted_metadata is not None:
        original_receipt = operation.get("receipt", receipt)
        if receipt is not None and original_receipt != receipt:
            raise ValueError("original successful receipt cannot be replaced")
        audit = accepted_metadata_record(plan, original_receipt, readback, accepted_metadata)
        receipt = original_receipt
    if rejection is not None:
        operation["resolution"] = rejection_record(rejection, plan["operationId"], plan["planSha256"],
                                                    plan["tool"], plan["params"].get("plugin_id"), operation["recordedAt"])
        operation["status"] = "rejected"
        return state
    if receipt is not None:
        operation["receipt"] = receipt
    operation["readback"] = readback
    successful_receipt = isinstance(receipt, dict) and receipt.get("status") in ("created", "updated")
    if not successful_receipt and not isinstance(readback, dict):
        operation["status"] = "unknown"
        return state
    remote_id = receipt.get("plugin_id") if successful_receipt else readback.get("plugin_id")
    release_id = receipt.get("release_id") if successful_receipt else readback.get("current_release_id")
    operation.update(status="unverified", remotePluginId=remote_id)
    expected = plan["params"].get("plugin_id")
    files_match = False
    if isinstance(readback, dict):
        try:
            files_match = safe_files(readback.get("files", {})) == plan["files"]
        except ValueError:
            pass
    if audit is not None:
        files_match = True
    owned = readback.get("owned", {}) if isinstance(readback, dict) else {}
    fresh_created = ("next_cursor" in owned and owned["next_cursor"] is None
                     and remote_id not in plan.get("priorObjectIds", [])
                     and len([x for x in owned.get("plugins", []) if x.get("name") == plan["packageName"]
                              and x.get("plugin_id") == remote_id]) == 1)
    if (not remote_id or (expected and expected != remote_id)
            or (not expected and not successful_receipt and not fresh_created)
            or (successful_receipt and (receipt.get("scope") != "USER"
                or receipt.get("discoverability") != "PRIVATE" or receipt.get("version") != plan["version"]))
            or not isinstance(readback, dict) or not readback.get("complete")
            or readback.get("plugin_id") != remote_id or readback.get("version") != plan["version"]
            or readback.get("name") != plan["packageName"]
            or readback.get("scope") != "USER" or readback.get("discoverability") != "PRIVATE"
            or readback.get("current_release_id") != release_id or not release_id
            or not files_match):
        return state
    operation.update(status="verified", currentReleaseId=release_id, reconciledFromReadback=not successful_receipt, installed="not_verified",
                     discovered="not_verified", runtime="not_verified")
    operation["verificationMethod"] = "accepted_wrapper_metadata" if audit else "exact_bytes"
    if audit is not None:
        operation["verification"] = audit
    state.setdefault("plugins", {}).setdefault(plan["packageName"], {}).update({"remotePluginId": remote_id,
        "version": plan["version"], "currentReleaseId": release_id,
        "sha256": plan["sha256"], "managedFiles": readback["files"], "sourceFiles": plan["files"]})
    return state


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value, original=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    with lock.open("x"):
        pass
    temporary = None
    try:
        if (path.read_bytes() if path.exists() else None) != original:
            raise ValueError("local record changed; prepare again")
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".sync-", delete=False) as f:
            temporary = Path(f.name)
            f.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())
            f.flush()
            os.fsync(f.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
        lock.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    prepare = commands.add_parser("prepare")
    for name in ("bundle", "delivery-dir", "plugin", "expected-sha256", "evidence", "output"):
        prepare.add_argument("--" + name, required=True)
    record = commands.add_parser("record")
    for name in ("state", "plan"):
        record.add_argument("--" + name, required=True)
    record.add_argument("--receipt")
    record.add_argument("--readback")
    record.add_argument("--rejection-evidence")
    record.add_argument("--accepted-metadata", help="Exact user-accepted wrapper differences bound to this successful create")
    legacy = commands.add_parser("reconcile-legacy")
    for name in ("state", "plugin", "mode", "success", "readback"):
        legacy.add_argument("--" + name, required=True)
    legacy.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    staging = None
    try:
        if args.action == "prepare":
            evidence = read_json(args.evidence)
            root = Path(args.delivery_dir)
            if root.is_symlink():
                raise ValueError("delivery root must not be a link")
            root.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".creator-package-", dir=root))
            deadline = time.monotonic() + 120
            manifest = unpack_delivery_bundle(Path(args.bundle), staging, deadline)
            snapshot = verified_snapshot(manifest, args.plugin, args.expected_sha256, "RELEASE", deadline)
            release = evidence["release"]
            if (release.get("isDraft") is not False or release.get("isPrerelease") is not False
                    or not release.get("publishedAt") or release.get("tagCommit") != snapshot["sourceCommit"]
                    or snapshot["releaseRef"] != "refs/tags/" + release.get("tagName", "")
                    or release.get("repository") != snapshot["metadataSource"]["repository"]):
                raise ValueError("official published release evidence does not match package")
            directory = Path(snapshot["pluginPath"])
            target = {f.relative_to(directory).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
                      for f in directory.rglob("*") if f.is_file()}
            owned = evidence.get("owned", {})
            personal = "next_cursor" in owned and owned["next_cursor"] is None and isinstance(owned.get("plugins"), list)
            current = evidence.get("current")
            if current and not any(x.get("plugin_id") == current.get("plugin_id") for x in owned.get("plugins", [])):
                raise ValueError("object is not in the complete personal account listing")
            plan = prepare_plan(snapshot, current, evidence.get("files", {}), target,
                managed_files=evidence.get("managedFiles", []), inventory_complete=evidence.get("complete") is True,
                personal_context=personal, owned_plugins=owned.get("plugins", []),
                verified_operation=evidence.get("verifiedOperation"))
            atomic_json(args.output, plan)
            print(json.dumps(plan, ensure_ascii=False))
        elif args.action == "reconcile-legacy":
            path = Path(args.state)
            original = path.read_bytes()
            state = reconcile_legacy(json.loads(original), args.plugin, args.mode,
                                     read_json(args.success), read_json(args.readback))
            if args.apply:
                atomic_json(path, state, original)
            print(json.dumps({"status": "reconciled" if args.apply else "checked", "accountWrites": 0}, ensure_ascii=False))
        else:
            if args.rejection_evidence and (args.receipt or args.readback or args.accepted_metadata):
                raise ValueError("rejection evidence and success/readback modes are exclusive")
            accepted_metadata = None
            if args.accepted_metadata:
                accepted_metadata = strict_json(Path(args.accepted_metadata).read_text(encoding="utf-8"))
                if not isinstance(accepted_metadata, dict) or not args.readback:
                    raise ValueError("accepted metadata requires an object and complete readback")
            plan = read_json(args.plan)
            path = Path(args.state)
            original = path.read_bytes() if path.exists() else None
            state = json.loads(original) if original else {}
            if not args.receipt and not args.readback and not args.rejection_evidence and not args.accepted_metadata:
                archive = Path(plan["params"]["archive"])
                if hashlib.sha256(archive.read_bytes()).hexdigest() != plan["sha256"]:
                    raise ValueError("reviewed archive changed; do not send")
            transition(state, plan, receipt=read_json(args.receipt) if args.receipt else None,
                       readback=read_json(args.readback) if args.readback else None,
                       rejection=read_json(args.rejection_evidence) if args.rejection_evidence else None,
                       accepted_metadata=accepted_metadata)
            atomic_json(path, state, original)
            print(json.dumps(state, ensure_ascii=False))
        return 0
    except (SwitchError, ValueError, KeyError, OSError, TypeError, zipfile.BadZipFile, tarfile.TarError) as error:
        print(json.dumps({"status": "blocked", "error": str(error), "accountWrites": 0, "retainedDirectory": str(staging) if staging else None}, ensure_ascii=False))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
