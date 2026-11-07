from pathlib import Path


PLUGIN_SYNC_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "plugin-sync" / "skills" / "plugin-sync"


def test_plugin_sync_delegates_build_and_verify_lifecycle() -> None:
    text = (PLUGIN_SYNC_ROOT / "references/update-build-and-verify-runtime.md").read_text(encoding="utf-8")
    for command in ["build-and-verify doctor", "build-and-verify init", "build-and-verify update"]:
        assert command in text
    assert "explicit user authorization" in text
    for forbidden in ["update-runtime", "runtime_current", "runtime_stale", "PR Flow"]:
        assert forbidden not in text


def test_plugin_sync_prepares_one_creator_update_without_a_network_client():
    import runpy
    import pytest
    api = runpy.run_path(str(PLUGIN_SYNC_ROOT / "scripts/plugin_sync.py"))
    snapshot = {"packageName": "example", "version": "1.1.0", "sha256": "a" * 64,
                "artifact": "example.zip", "pluginPath": "/prepared/example"}
    current = {"plugin_id": "plugins_existing", "name": "example", "version": "1.0.0",
               "scope": "USER", "discoverability": "PRIVATE", "current_release_id": "release_old"}
    remote = {"skills/entry/SKILL.md": "b" * 64, "obsolete.txt": "c" * 64}
    target = {"skills/entry/SKILL.md": "a" * 64}
    plan = api["prepare_plan"](snapshot, current, remote, target, managed_files=list(remote), inventory_complete=True)
    assert plan["tool"] == "update_plugin"
    assert plan["params"] == {"archive": str(Path("/prepared/example.zip")), "plugin_id": "plugins_existing",
                              "expected_release_id": "release_old", "delete_paths": ["obsolete.txt"]}
    assert plan["accountWrites"] == 0
    with pytest.raises(ValueError, match="same version"):
        api["prepare_plan"]({**snapshot, "version": "1.0.0"}, current, remote, target,
                            managed_files=list(remote), inventory_complete=True)


    state = {"plugins": {"example": {"account": {"DEV": {"kept": True}}, "clientSource": "unchanged"}}}
    api["transition"](state, plan)
    with pytest.raises(ValueError, match="already exists"):
        api["transition"](state, plan)
    receipt = {"status": "updated", "plugin_id": "plugins_existing", "version": "1.1.0",
               "scope": "USER", "discoverability": "PRIVATE", "release_id": "release_new"}
    after = {"complete": True, "plugin_id": "plugins_existing", "version": "1.1.0", "scope": "USER",
             "discoverability": "PRIVATE", "current_release_id": "release_new", "files": target,
             "name": "example"}
    api["transition"](state, plan, receipt={"status": "unknown"})
    assert state["operations"][plan["operationId"]]["status"] == "unknown"
    api["transition"](state, plan, readback=after)
    assert state["operations"][plan["operationId"]]["status"] == "verified"
    assert state["operations"][plan["operationId"]]["installed"] == "not_verified"

    assert state["plugins"]["example"]["account"]["DEV"] == {"kept": True}
    assert state["plugins"]["example"]["clientSource"] == "unchanged"
    before = repr(state)
    with pytest.raises(ValueError, match="already exists"):
        api["transition"](state, plan)
    assert repr(state) == before

    import hashlib
    import json
    another = api["prepare_plan"](snapshot, current, remote, target, managed_files=list(remote), inventory_complete=True)
    pending = {}
    api["transition"](pending, another)
    error = {"isError": True, "message": "The expected release changed; no update was applied."}
    proof = {"operationId": another["operationId"], "planSha256": another["planSha256"],
             "tool": "update_plugin", "remotePluginId": "plugins_existing", "classification": "explicit_not_applied",
             "officialError": error, "officialErrorSha256": hashlib.sha256(json.dumps(error, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
             "notAppliedQuote": "no update was applied", "readAt": pending["operations"][another["operationId"]]["recordedAt"], "currentReadback": current}
    api["transition"](pending, another, rejection=proof)
    assert pending["operations"][another["operationId"]]["status"] == "rejected"
    api["transition"](pending, plan)
    old = {"status": "unverified", "operation": "create", "responseRemotePluginId": "plugins_existing",
           "snapshot": {"packageName": "example", "version": "1.1.0", "sha256": "a" * 64}}
    history = {"plugins": {"example": {"account": {"RELEASE": {"remotePluginId": "plugins_existing", "version": "1.1.0", "saveState": old}}}}}
    api["reconcile_legacy"](history, "example", "RELEASE", {"remotePluginId": "plugins_existing", "shareUrl": ""}, {**after, "artifactSha256": "a" * 64})
    assert old["status"] == "unverified" and old["resolution"]["status"] == "verified"
    old["status"] = "pending"
    with pytest.raises(ValueError, match="not proven"):
        api["reconcile_legacy"](history, "example", "RELEASE", {"remotePluginId": "plugins_existing", "shareUrl": ""}, {**after, "artifactSha256": "a" * 64})


def test_record_reconciles_only_exact_accepted_wrapper_differences(capsys):
    import copy, hashlib, json, runpy
    from unittest.mock import patch
    api = runpy.run_path(str(PLUGIN_SYNC_ROOT / "scripts/plugin_sync.py"))
    encode = lambda value: json.dumps(value, ensure_ascii=False)
    sha = lambda text: hashlib.sha256(text.encode()).hexdigest()
    source = {"name": "example", "version": "1.3.2", "author": {"name": "Upstream", "url": "https://example.test"},
              "interface": {"developerName": "Upstream"}, "skills": "./skills"}
    observed = copy.deepcopy(source)
    observed["author"].update(name="Account", email="owner@example.test")
    observed["interface"]["developerName"] = "Account"
    source_raw, observed_raw = encode(source), encode(observed)
    path = ".codex-plugin/plugin.json"
    target = {path: sha(source_raw), "LICENSE": sha("license"), "skills/entry/SKILL.md": sha("skill")}
    snapshot = {"packageName": "example", "version": "1.3.2", "sha256": "a" * 64, "artifact": "example.zip", "pluginPath": "/prepared/example"}
    plan = api["prepare_plan"](snapshot, None, {}, target, inventory_complete=True, personal_context=True, owned_plugins=[])
    receipt = {"status": "created", "plugin_id": "plugins_created", "release_id": "release_current", "version": "1.3.2", "scope": "USER", "discoverability": "PRIVATE"}
    readback = {"name": "example", "plugin_id": receipt["plugin_id"], "current_release_id": receipt["release_id"], "version": "1.3.2", "scope": "USER", "discoverability": "PRIVATE", "complete": True,
                "files": {**target, path: sha(observed_raw)}}
    state = {}; api["transition"](state, plan); api["transition"](state, plan, receipt=receipt, readback=readback)
    assert state["operations"][plan["operationId"]]["status"] == "unverified"
    proof = {"operationId": plan["operationId"], "planSha256": plan["planSha256"], "archiveSha256": plan["sha256"],
             "plugin_id": receipt["plugin_id"], "release_id": receipt["release_id"], "version": "1.3.2",
             "sourceManifest": source_raw, "observedManifest": observed_raw,
             "acceptance": {"accepted": True, "reference": "explicit user decision for this operation"},
             "owned": {"plugins": [{**readback}], "next_cursor": None},
             "changes": [{"path": "/author/name", "action": "replace", "before": {"present": True, "value": "Upstream"}, "after": {"present": True, "value": "Account"}},
                         {"path": "/author/email", "action": "add", "before": {"present": False}, "after": {"present": True, "value": "owner@example.test"}},
                         {"path": "/interface/developerName", "action": "replace", "before": {"present": True, "value": "Upstream"}, "after": {"present": True, "value": "Account"}}]}
    def record(evidence, current=readback):
        saved = []; fixtures = {"plan": plan, "receipt": receipt, "readback": current}
        args = ["record", "--state", "state", "--plan", "plan", "--receipt", "receipt", "--readback", "readback"]
        if evidence is not None: args += ["--accepted-metadata", "proof"]
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "read_bytes", return_value=encode(state).encode()), \
             patch.object(Path, "read_text", return_value=encode(evidence)), \
             patch.dict(api["main"].__globals__, {"read_json": lambda p: copy.deepcopy(fixtures[p]), "atomic_json": lambda p, value, old: saved.append(copy.deepcopy(value))}):
            code = api["main"](args)
        capsys.readouterr()
        return code, saved
    code, saved = record(proof)
    assert code == 0 and len(saved) == 1
    operation = saved[0]["operations"][plan["operationId"]]
    assert operation["status"] == "verified" and operation["verificationMethod"] == "accepted_wrapper_metadata"
    assert operation["plan"] == plan and operation["receipt"] == receipt
    assert saved[0]["plugins"]["example"]["managedFiles"] == readback["files"]
    assert saved[0]["plugins"]["example"]["sourceFiles"] == target
    current = {k: v for k, v in readback.items() if k not in ("files", "complete")}
    unchanged = api["prepare_plan"](snapshot, current, readback["files"], target,
        inventory_complete=True, verified_operation=operation)
    assert unchanged["status"] == "unchanged" and unchanged["tool"] is None
    with __import__("pytest").raises(ValueError, match="same version"):
        api["prepare_plan"](snapshot, {**current, "current_release_id": "different_release"}, readback["files"], target,
            inventory_complete=True, verified_operation=operation)
    with __import__("pytest").raises(ValueError, match="same version"):
        api["prepare_plan"]({**snapshot, "sha256": "f" * 64}, current, readback["files"], target,
            inventory_complete=True, verified_operation=operation)
    with __import__("pytest").raises(ValueError, match="no matching"):
        api["transition"]({}, plan, accepted_metadata={})
    with patch.object(Path, "read_text", return_value="null"):
        assert api["main"](["record", "--state", "state", "--plan", "plan", "--accepted-metadata", "proof", "--readback", "readback"]) == 1
    with patch.object(Path, "read_text", return_value="{}"):
        assert api["main"](["record", "--state", "state", "--plan", "plan", "--accepted-metadata", "proof"]) == 1
    assert record(None)[1][0]["operations"][plan["operationId"]]["status"] == "unverified"
    for bad in ({**proof, "release_id": "wrong"}, {**proof, "changes": []}, {**proof, "sourceManifest": source_raw + "\n"}):
        assert record(bad) == (1, [])
    modified = {**readback, "files": {**readback["files"], "LICENSE": sha("tampered")}}
    assert record(proof, modified) == (1, [])
    for altered in (encode({**observed, "description": "unapproved"}), observed_raw[:-1] + ',"version":"1.3.2"}'):
        bad = {**proof, "observedManifest": altered}
        assert record(bad, {**readback, "files": {**readback["files"], path: sha(altered)}}) == (1, [])
    with __import__("pytest").raises(ValueError, match="already exists"):
        api["transition"](saved[0], plan)
