"""In-memory data contracts and maintenance decisions; native smoke is separate."""

import builtins
import copy
import errno
import io
import json
from decimal import Decimal
import importlib.util
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/data-store/skills/data-store"


def load_store():
    spec = importlib.util.spec_from_file_location("data_store", SKILL / "scripts/data_store.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name,table,expected", [
    ("Readings", True, "readings"), ("_table", True, "_table"),
    ("GROUP-01", False, "group-01"), ("001", False, "001"),
])
def test_logical_names_are_normalized_without_accessing_storage(name, table, expected):
    assert load_store()._name(name, table=table) == expected


@pytest.mark.parametrize("name,table", [
    (None, False), (1, False), ("", False), ("*", False), ("../one", False),
    ("a/b", False), ("a\\b", False), ("x" * 129, False),
    ("1table", True), ("table-name", True), ("a\x00b", True),
])
def test_logical_names_reject_paths_and_unbounded_names(name, table):
    with pytest.raises(ValueError, match="路径"):
        load_store()._name(name, table=table)


@pytest.mark.parametrize("parameters,expected", [
    (None, ("NoneType", None)), (True, ("bool", True)), (1, ("int", 1)),
    ([1, {"b": False, "a": "value"}],
     ("list", (("int", 1), ("dict", (("a", ("str", "value")), ("b", ("bool", False))))))),
    ((1, 2), ("tuple", (("int", 1), ("int", 2)))),
])
def test_parameter_identity_preserves_types_and_normalizes_mapping_order(parameters, expected):
    assert load_store()._parameter_key(parameters) == expected


@pytest.mark.parametrize("parameters", [b"binary", {1: "non-string key"}, {"set"}, Decimal("1.25")])
def test_native_parameters_without_stable_identity_do_not_claim_cache_support(parameters):
    with pytest.raises(TypeError, match="缓存"):
        load_store()._parameter_key(parameters)


@pytest.mark.parametrize("rows,schema,error", [
    ([{"payload": b"new"}], None, ValueError),
    ([{"payload": b"new"}], {}, ValueError),
    ([{"payload": "text"}], {"payload": "BLOB"}, TypeError),
    ([{"payload": bytearray(b"new")}], {"payload": "BLOB"}, TypeError),
    ([{"payload": memoryview(b"new")}], {"payload": "BLOB"}, TypeError),
    ([{"payload": [1, 2]}], {"payload": "BLOB"}, TypeError),
    ([{"payload": b"new", "extra": 1}], {"payload": "BLOB"}, ValueError),
    ([{"payload": b"new"}], {"payload": "BLOB", "id": "INTEGER"}, ValueError),
    ([{"id": 1}], {"payload": "BLOB", "id": "INTEGER"}, ValueError),
    ([{"payload": b"new", "PAYLOAD": b"other"}], {"payload": "BLOB", "PAYLOAD": "BLOB"}, ValueError),
    ([{"": b"new"}], {"": "BLOB"}, ValueError),
    ([{"\x00": b"new"}], {"\x00": "BLOB"}, ValueError),
    ([{1: b"new"}], {1: "BLOB"}, ValueError),
    ([{"payload": b"new", "nested": {"value": b"nested"}}],
     {"payload": "BLOB", "nested": {"value": "BLOB"}}, TypeError),
    ([{"payload": b"new", "nested": [b"nested"]}],
     {"payload": "BLOB", "nested": ["BLOB"]}, TypeError),
    ([{"payload": b"new", "id": float("nan")}], {"payload": "BLOB", "id": "DOUBLE"}, ValueError),
])
def test_binary_fields_are_rejected_before_native_conversion(rows, schema, error):
    # No connection exists: invalid fields must fail before the database leaf.
    with pytest.raises(error):
        load_store()._binary_records(None, rows, schema)


@pytest.mark.parametrize("tables", [None, [], (), "readings", {"readings"}, ["../readings"], ["readings", None]])
def test_query_requires_explicit_valid_scope_before_native_access(tables):
    with pytest.raises(ValueError):
        load_store().query(ROOT / "unavailable-data-root", "SELECT 1", tables=tables)


def test_query_requires_scope_argument():
    with pytest.raises(TypeError, match="tables"):
        load_store().query(ROOT / "unavailable-data-root", "SELECT 1")


@pytest.mark.parametrize("keys,columns", [
    ([], None), ("one", None), (["one"], []),
    (["one"], ["id", "ID"]), (["one"], ["\x00"]), (["../one"], None),
])
def test_selected_key_and_column_validation_precedes_file_reads(keys, columns):
    with pytest.raises(ValueError):
        load_store().read_keys(ROOT, "readings", keys, columns=columns)


@pytest.mark.parametrize("filters", [{}, {"label": []}, {"label": "002", "LABEL": "002"}])
def test_scalar_filter_validation_precedes_file_reads(filters):
    with pytest.raises(ValueError, match="筛选"):
        load_store().read_key(ROOT, "readings", "one", filters=filters)


@pytest.mark.parametrize("tables", ["[]", "null", '"readings"', '["../readings"]'])
def test_cli_rejects_invalid_scope_without_launching_a_child(tables, capsys):
    assert load_store().main(["--root", str(ROOT / "unavailable-data-root"),
                              "query", "SELECT 1", "--tables", tables]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "tables" in captured.err or "路径" in captured.err


def test_cli_requires_scope_before_loading_native_database(capsys):
    with pytest.raises(SystemExit) as error:
        load_store().main(["--root", str(ROOT), "query", "SELECT 1"])
    assert error.value.code == 2
    assert "--tables" in capsys.readouterr().err


@pytest.mark.parametrize("command", [
    ["query", "SELECT 1", "--tables", '["readings"]'],
    ["read-key", "readings", "one"], ["read-keys", "readings", "one"],
])
def test_cli_rejects_invalid_batch_size_before_storage_access(command, capsys):
    assert load_store().main(["--root", str(ROOT), *command, "--batch-size", "0"]) == 2
    assert "batch-size" in capsys.readouterr().err


def test_cli_reports_missing_dependency(monkeypatch, capsys):
    store = load_store()
    original = builtins.__import__

    def without_duckdb(name, *args, **kwargs):
        if name == "duckdb":
            raise ImportError("missing")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_duckdb)
    assert store.main(["--root", str(ROOT), "query", "SELECT 1", "--tables", '["readings"]']) == 2
    assert "缺少 DuckDB" in capsys.readouterr().err


@pytest.mark.parametrize("targets", [None, {}, [], {"readings": []}, {"readings": "one"},
                                      {"readings": [""]}, {"readings": ["*"]},
                                      {"../outside": ["one"]}, {"readings": ["../one"]}])
def test_delete_plan_rejects_nonexact_targets_before_root_access(targets, capsys):
    import json
    assert load_store().main(["--root", str(ROOT / "absent"), "delete-plan",
                              "--targets", json.dumps(targets)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "数据根不可用" not in captured.err
    assert "No such file" not in captured.err


def known_delete_plan():
    return {"format": "data-store-delete-v1", "nonce": "known-plan",
            "root": {"path": "/project/data", "device": 7, "inode": 11},
            "targets": [{"table": "readings", "key": "one", "directory": {"device": 7, "inode": 13},
                         "file": {"device": 7, "inode": 17, "size": 19, "mtime_ns": 23,
                                  "ctime_ns": 29, "sha256": "abc123"}}],
            "plan_id": "sha256:c7a00804fcd660a38029d3223300b141ce80b4177b41eb6c03b3fa43bf9d7075"}


def test_plan_identity_uses_the_complete_canonical_content():
    store = load_store()
    plan = known_delete_plan()
    assert store._delete_plan_id(plan) == plan["plan_id"]
    store._validate_delete_plan(plan)
    changed = copy.deepcopy(plan)
    changed["targets"][0]["file"]["inode"] = 18
    with pytest.raises(ValueError, match="计划身份"):
        store._validate_delete_plan(changed)


@pytest.mark.parametrize("change", ["format", "nonce", "root", "targets", "duplicate", "case", "file"])
def test_delete_plan_rejects_incomplete_or_noncanonical_data(change):
    store = load_store()
    plan = known_delete_plan()
    if change == "format":
        plan["format"] = "unknown"
    elif change == "nonce":
        plan["nonce"] = ""
    elif change == "root":
        del plan["root"]["inode"]
    elif change == "targets":
        plan["targets"] = []
    elif change == "duplicate":
        plan["targets"].append(copy.deepcopy(plan["targets"][0]))
    elif change == "case":
        plan["targets"][0]["table"] = "Readings"
    else:
        del plan["targets"][0]["file"]["sha256"]
    with pytest.raises(ValueError):
        store._validate_delete_plan(plan)


def test_cli_output_preserves_text_conversion_but_never_stringifies_binary():
    store = load_store()
    assert store._cli_json_value(Decimal("12.50")) == "12.50"
    with pytest.raises(ValueError, match="BLOB"):
        store._cli_json_value(b"\x00\xff")


@pytest.fixture
def delete_execution(monkeypatch):
    """Only identity, journal bytes, sync and unlink are replaced, not the algorithm."""
    store = load_store()
    plan = known_delete_plan()
    root, receipt = ROOT / ".unit-delete-data", ROOT / ".unit-delete-receipt"
    plan["root"]["path"] = str(root)
    second = copy.deepcopy(plan["targets"][0])
    second["key"] = "two"
    second["file"]["inode"] += 1
    plan["targets"].append(second)
    plan["plan_id"] = store._delete_plan_id(plan)
    state = SimpleNamespace(store=store, plan=plan, root=root, receipt=receipt,
                            records=[], unlinks=[], syncs=[])

    def identity(actual_root, target):
        assert actual_root == root
        original = next(item for item in plan["targets"] if item["key"] == target["key"])
        return copy.deepcopy(original["directory"]), copy.deepcopy(original["file"])

    def write(path, record, *, create=False):
        assert path == receipt
        if create and state.records:
            raise FileExistsError(path)
        state.records.append((json.dumps(record) + "\n").encode())

    original_open = Path.open

    def read(path, mode="r", *args, **kwargs):
        if path != receipt:
            return original_open(path, mode, *args, **kwargs)
        assert mode == "rb"
        return io.BytesIO(b"".join(state.records))

    def unlink(path, *args, **kwargs):
        assert path.parent == root / "readings"
        state.unlinks.append(path.name)

    original_resolve = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda path, *args, **kwargs:
                        path if path == receipt else original_resolve(path, *args, **kwargs))
    monkeypatch.setattr(Path, "open", read)
    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(store, "_delete_root", lambda path: (root, copy.deepcopy(plan["root"])))
    monkeypatch.setattr(store, "_delete_file_identity", identity)
    monkeypatch.setattr(store, "_write_delete_log", write)
    monkeypatch.setattr(store, "_sync_delete_directory", state.syncs.append)
    state.execute = lambda **changes: store.execute_delete(
        changes.pop("root", root), changes.pop("plan", plan),
        approve=changes.pop("approve", plan["plan_id"]),
        offline=changes.pop("offline", True), receipt_path=changes.pop("receipt_path", receipt), **changes,
    )
    return state


def test_delete_preview_normalizes_exact_targets_without_mutation(delete_execution):
    state = delete_execution
    plan = state.store.plan_delete(state.root, {"Readings": ["ONE", "two", "one"]})
    assert [target["key"] for target in plan["targets"]] == ["one", "two"]
    state.store._validate_delete_plan(plan)
    assert state.records == state.unlinks == state.syncs == []


@pytest.mark.parametrize("change,code", [
    ("identity", "identity_changed"), ("missing", "missing"), ("redirect", "redirected"),
    ("permission", "permission_or_lock"), ("lock", "locked"),
    ("root", "root_identity_changed"), ("root-missing", "root_unavailable"),
])
def test_delete_preflight_failure_never_unlinks_any_item(delete_execution, monkeypatch, change, code):
    state = delete_execution
    store, original = state.store, state.store._delete_file_identity

    def identity(root, target):
        directory, file = original(root, target)
        if target["key"] == "two":
            if change == "identity":
                file["inode"] += 100
            elif change == "missing":
                raise FileNotFoundError("missing target")
            elif change == "redirect":
                raise store._DeleteSafetyError("redirected", "redirected target")
            elif change == "permission":
                raise PermissionError("unavailable target")
            elif change == "lock":
                raise OSError(errno.EBUSY, "locked target")
        return directory, file

    monkeypatch.setattr(store, "_delete_file_identity", identity)
    if change == "root":
        monkeypatch.setattr(store, "_delete_root", lambda root:
                            (root, dict(state.plan["root"], inode=999)))
    elif change == "root-missing":
        def missing_root(root):
            raise store._DeleteSafetyError("root_unavailable", "unavailable root")
        monkeypatch.setattr(store, "_delete_root", missing_root)
    receipt = state.execute()
    assert receipt["state"] == "incomplete"
    assert not state.unlinks
    assert any(item.get("error", {}).get("code") == code for item in receipt["items"])


def test_delete_partial_failure_resumes_only_original_unfinished_item(delete_execution, monkeypatch):
    state = delete_execution
    unlink = Path.unlink

    def locked(path, *args, **kwargs):
        if path.name == "two.parquet":
            raise PermissionError("locked")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", locked)
        receipt = state.execute()
    assert [item["status"] for item in receipt["items"]] == ["deleted", "failed"]
    original = state.store._delete_file_identity

    def unfinished_only(root, target):
        assert target["key"] == "two", "A rebuilt completed key must never be checked or removed"
        return original(root, target)

    monkeypatch.setattr(state.store, "_delete_file_identity", unfinished_only)
    assert state.execute()["state"] == "complete"
    assert state.unlinks == ["one.parquet", "two.parquet"]


@pytest.mark.parametrize("failure", ["receipt-write", "unlink-outcome", "torn-log", "directory-sync"])
def test_delete_uncertain_outcome_never_retries(delete_execution, monkeypatch, failure):
    state = delete_execution
    write, unlink = state.store._write_delete_log, Path.unlink

    def failed_write(path, record, **kwargs):
        if record.get("status") == "deleted":
            if failure == "torn-log":
                state.records.append(b'{"item":0,')
            raise OSError("receipt result not durable")
        return write(path, record, **kwargs)

    def uncertain_unlink(path, *args, **kwargs):
        unlink(path, *args, **kwargs)
        raise OSError("unknown unlink outcome")

    def failed_sync(path):
        if path == state.root / "readings":
            raise OSError("directory sync failed after unlink")

    with monkeypatch.context() as patch:
        if failure in ("receipt-write", "torn-log"):
            patch.setattr(state.store, "_write_delete_log", failed_write)
        elif failure == "unlink-outcome":
            patch.setattr(Path, "unlink", uncertain_unlink)
        else:
            patch.setattr(state.store, "_sync_delete_directory", failed_sync)
        assert state.execute()["state"] == "uncertain"
    assert state.execute()["state"] == "uncertain"
    assert state.unlinks == ["one.parquet"]


@pytest.mark.parametrize("change", ["replacement", "disappearance"])
def test_delete_rechecks_identity_after_preflight(delete_execution, monkeypatch, change):
    state = delete_execution
    original = state.store._delete_file_identity
    calls = 0

    def identity(root, target):
        nonlocal calls
        calls += 1
        directory, file = original(root, target)
        if calls == 3:  # Both preflight checks completed, no unlink yet.
            if change == "disappearance":
                raise FileNotFoundError("disappeared before unlink")
            file["inode"] += 1
        return directory, file

    monkeypatch.setattr(state.store, "_delete_file_identity", identity)
    result = state.execute()
    assert result["state"] == "incomplete"
    assert result["items"][0]["error"]["code"] == (
        "missing" if change == "disappearance" else "identity_changed")
    assert not state.unlinks


@pytest.mark.parametrize("change", ["approval", "offline", "plan", "root", "receipt-in-data", "receipt-other-plan"])
def test_delete_rejects_wrong_authority_without_mutation(delete_execution, change):
    state = delete_execution
    arguments = {}
    if change == "approval":
        arguments["approve"] = "another-plan"
    elif change == "offline":
        arguments["offline"] = False
    elif change == "plan":
        arguments["plan"] = copy.deepcopy(state.plan)
        arguments["plan"]["targets"][0]["key"] = "unapproved"
    elif change == "root":
        arguments["root"] = ROOT / "other-root"
    elif change == "receipt-in-data":
        arguments["receipt_path"] = state.root / "receipt"
    else:
        state.records.append(b'{"format":"unrelated","important":"keep me"}\n')
    before = list(state.records)
    with pytest.raises(ValueError):
        state.execute(**arguments)
    assert not state.unlinks and state.records == before


def test_resuming_delete_syncs_receipt_directory_before_any_unlink(delete_execution, monkeypatch):
    state = delete_execution

    def failed_sync(path):
        assert path == state.receipt.parent
        raise OSError("receipt directory sync failed")

    with monkeypatch.context() as patch:
        patch.setattr(state.store, "_sync_delete_directory", failed_sync)
        for _ in range(2):
            with pytest.raises(OSError, match="receipt directory"):
                state.execute()
            assert len(state.records) == 1 and not state.unlinks
    assert state.execute()["state"] == "complete"
    assert state.syncs[0] == state.receipt.parent


@pytest.mark.parametrize("change", [None, "path", "fd"])
def test_delete_file_identity_compares_ctime_within_each_source(monkeypatch, change):
    store = load_store()
    root = ROOT / ".unit-delete-identity"
    target = root / "readings/one.parquet"
    counts = {"path": 0, "fd": 0}

    def signature(source):
        counts[source] += 1
        return SimpleNamespace(st_mode=stat.S_IFREG, st_dev=7, st_ino=17, st_size=3,
                               st_mtime_ns=23, st_ctime_ns=(29 if source == "path" else 999)
                               + (counts[source] if source == change else 0))

    class Stream(io.BytesIO):
        def fileno(self):
            return 123

    original_resolve = Path.resolve
    original_stat = Path.stat
    original_is_symlink = Path.is_symlink
    original_open, original_fstat = Path.open, store.os.fstat
    monkeypatch.setattr(Path, "resolve", lambda path, *args, **kwargs:
                        path if path in (target, target.parent) else original_resolve(path, *args, **kwargs))
    monkeypatch.setattr(Path, "is_symlink", lambda path:
                        False if path == target else original_is_symlink(path))
    monkeypatch.setattr(Path, "stat", lambda path, *args, **kwargs:
                        signature("path") if path == target else
                        SimpleNamespace(st_mode=stat.S_IFDIR, st_dev=7, st_ino=13)
                        if path == target.parent else original_stat(path, *args, **kwargs))
    monkeypatch.setattr(Path, "open", lambda path, *args, **kwargs:
                        Stream(b"abc") if path == target else original_open(path, *args, **kwargs))
    monkeypatch.setattr(store.os, "fstat", lambda descriptor:
                        signature("fd") if descriptor == 123 else original_fstat(descriptor))
    if change:
        with pytest.raises(store._DeleteSafetyError, match="核验中"):
            store._delete_file_identity(root, {"table": "readings", "key": "one"})
    else:
        _, file = store._delete_file_identity(root, {"table": "readings", "key": "one"})
        assert file["ctime_ns"] == 29


@pytest.mark.parametrize("payload,error", [
    (b"not parquet", "corrupt"), (b"PAR1" + b"\xff" * 4 + b"PAR1", "corrupt"),
    (FileNotFoundError("absent"), "missing"), (PermissionError("storage unavailable"), "permission"),
    (b"PAR1" + b"\x00" * 4 + b"PAR1", None),
])
def test_selected_key_envelope_preserves_missing_corrupt_and_storage_errors(monkeypatch, payload, error):
    store = load_store()
    target = ROOT / ".unit-selected.parquet"
    original_open, original_symlink = Path.open, Path.is_symlink

    def open_key(path, *args, **kwargs):
        if path != target:
            return original_open(path, *args, **kwargs)
        if isinstance(payload, Exception):
            raise payload
        return io.BytesIO(payload)

    monkeypatch.setattr(Path, "is_symlink", lambda path:
                        False if path == target else original_symlink(path))
    monkeypatch.setattr(Path, "open", open_key)
    if error:
        with pytest.raises({"corrupt": store.CorruptDataError,
                            "missing": store.MissingKeyError, "permission": PermissionError}[error]):
            store._check_key(target)
    else:
        store._check_key(target)


@pytest.mark.parametrize("redirect", ["directory", "shard"])
def test_key_reader_rejects_redirection_before_native_access(monkeypatch, redirect):
    store = load_store()
    directory, shard = ROOT / "readings", ROOT / "readings/one.parquet"
    original_resolve, original_symlink = Path.resolve, Path.is_symlink
    monkeypatch.setattr(Path, "resolve", lambda path, *args, **kwargs:
                        ROOT / "other" if redirect == "directory" and path == directory
                        else original_resolve(path, *args, **kwargs))
    monkeypatch.setattr(Path, "is_symlink", lambda path:
                        True if redirect == "shard" and path == shard else original_symlink(path))
    monkeypatch.setattr(store, "_duckdb", lambda: pytest.fail("redirection reached native database"))
    with pytest.raises(ValueError, match="目录|链接"):
        store.read_key(ROOT, "readings", "one")


@pytest.mark.parametrize("container", ["list", "array", "map", "struct", "union"])
def test_cli_rejects_nested_binary_types_without_native_database(container):
    store = load_store()
    blob = SimpleNamespace(id="blob", children=[])
    nested = SimpleNamespace(id=container, children=[("value", blob)])
    assert store._contains_blob(nested)
    nested.children = [("value", SimpleNamespace(id="integer", children=[]))]
    assert not store._contains_blob(nested)


@pytest.mark.parametrize("statements", [[], ["SELECT", "SELECT"], ["CREATE"], ["COPY"]])
def test_query_accepts_only_one_readonly_statement_before_root_access(monkeypatch, statements):
    store = load_store()
    closed = []
    connection = SimpleNamespace(
        extract_statements=lambda sql: [SimpleNamespace(type=kind) for kind in statements],
        close=lambda: closed.append(True),
    )
    engine = SimpleNamespace(connect=lambda *args, **kwargs: connection,
                             StatementType=SimpleNamespace(SELECT="SELECT"))
    monkeypatch.setattr(store, "_duckdb", lambda: engine)
    with pytest.raises(ValueError, match="只读"):
        store.query(ROOT / "unavailable", "SQL extracted by the native parser", tables=["readings"])
    assert closed == [True]
