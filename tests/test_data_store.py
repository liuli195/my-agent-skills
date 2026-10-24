"""Pure data contracts; native database and storage behavior live in integration."""

import builtins
import copy
from decimal import Decimal
import importlib.util
from pathlib import Path

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
