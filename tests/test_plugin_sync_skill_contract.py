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
