"""Public write/query contract; the isolated CLI test is the release-shape smoke."""

import json
import importlib.util
import builtins
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import duckdb
import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/data-store/skills/data-store"


def test_installed_cli_query_prepares_only_declared_logical_tables(tmp_path):
    installed = tmp_path / "installed"
    shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
    script = installed / "scripts/data_store.py"
    data = tmp_path / "data"
    written = subprocess.run(
        [sys.executable, str(script), "--root", str(data), "write", "measurements", "one"],
        input='[{"score":7}]', text=True, capture_output=True, cwd=tmp_path,
    )
    assert written.returncode == 0, written.stderr
    (data / "history").mkdir()
    (data / "history" / "broken.parquet").write_bytes(b"not parquet")
    (data / "invalid-table-name").mkdir()
    selected = subprocess.run(
        [sys.executable, str(script), "--root", str(data), "query", "SELECT score FROM measurements",
         "--tables", '["Measurements","measurements"]', "--batch-size", "1"],
        text=True, capture_output=True, cwd=tmp_path,
    )
    assert selected.returncode == 0, selected.stderr
    assert [json.loads(line) for line in selected.stdout.splitlines()] == [{"score": 7}]


def test_installed_cli_query_cannot_read_undeclared_parquet_or_sqlite(tmp_path):
    installed = tmp_path / "installed"
    shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
    script = installed / "scripts/data_store.py"
    data = tmp_path / "data"
    for table in ("selected", "private"):
        written = subprocess.run(
            [sys.executable, str(script), "--root", str(data), "write", table, "one"],
            input='[{"value":7}]', text=True, capture_output=True, cwd=tmp_path,
        )
        assert written.returncode == 0, written.stderr
    database = data / "private.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE secret(value)")
        connection.execute("INSERT INTO secret VALUES (99)")
    for sql, parameters in [
        ("SELECT * FROM private", []),
        ("SELECT * FROM read_parquet(?)", [str(data / "private" / "one.parquet")]),
        ("SELECT * FROM read_blob(?)", [str(database)]),
    ]:
        denied = subprocess.run(
            [sys.executable, str(script), "--root", str(data), "query", sql,
             "--tables", '["selected"]', "--parameters", json.dumps(parameters)],
            text=True, capture_output=True, cwd=tmp_path,
        )
        assert denied.returncode == 2, denied.stdout
        assert denied.stdout == ""


@pytest.mark.parametrize("batch", [False, True])
def test_key_cursors_allow_only_selected_files_and_lock_configuration(tmp_path, batch):
    store = load_store()
    store.write(tmp_path, "readings", "one", [{"value": 7}])
    store.write(tmp_path, "readings", "private", [{"value": 99}])
    reader = store.read_keys(tmp_path, "readings", ["one"]) if batch else store.read_key(tmp_path, "readings", "one")
    with reader as cursor:
        assert cursor.fetchone() == (7,)
        with pytest.raises(duckdb.PermissionException):
            cursor.execute("SELECT * FROM read_parquet(?)", [str(tmp_path / "readings" / "private.parquet")])
        with pytest.raises(duckdb.InvalidInputException):
            cursor.execute("SET allowed_paths = []")


@pytest.mark.parametrize("command", ["query", "read-key"])
def test_installed_readers_reject_same_root_table_redirection(tmp_path, command):
    installed = tmp_path / "installed"
    shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
    script = installed / "scripts/data_store.py"
    data = tmp_path / "data"
    written = subprocess.run(
        [sys.executable, str(script), "--root", str(data), "write", "private", "one"],
        input='[{"value":99}]', text=True, capture_output=True, cwd=tmp_path,
    )
    assert written.returncode == 0, written.stderr
    (data / "selected").symlink_to(data / "private", target_is_directory=True)
    arguments = (["query", "SELECT * FROM selected", "--tables", '["selected"]']
                 if command == "query" else ["read-key", "selected", "one"])
    denied = subprocess.run(
        [sys.executable, str(script), "--root", str(data), *arguments],
        text=True, capture_output=True, cwd=tmp_path,
    )
    assert denied.returncode == 2, denied.stdout
    assert "目录" in denied.stderr
    assert denied.stdout == ""


def test_installed_cli_filters_one_row_within_a_logical_group(tmp_path):
    script = tmp_path / "data_store.py"
    shutil.copy2(SKILL / "scripts/data_store.py", script)
    data = tmp_path / "data"
    rows = [{"label": "001", "score": 1.25, "parts": [{"amount": 4}]},
            {"label": "002", "score": 2.5, "parts": [{"amount": 8}]}]
    written = subprocess.run(
        [sys.executable, str(script), "--root", str(data), "write", "measurements", "group_01"],
        input=json.dumps(rows), text=True, capture_output=True, cwd=tmp_path,
    )
    assert written.returncode == 0, written.stderr
    selected = subprocess.run(
        [sys.executable, str(script), "--root", str(data), "read-key", "measurements", "group_01",
         "--filters", '{"label":"002"}', "--columns", '["label","parts"]', "--batch-size", "1"],
        text=True, capture_output=True, cwd=tmp_path,
    )
    assert selected.returncode == 0, selected.stderr
    assert [json.loads(line) for line in selected.stdout.splitlines()] == [
        {"label": "002", "parts": [{"amount": 8}]},
    ]


def load_store(skill=SKILL):
    spec = importlib.util.spec_from_file_location("data_store", skill / "scripts/data_store.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_independent_skill_python_binary_write_round_trips_bytes(tmp_path):
    installed = tmp_path / "installed-skill"
    shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
    store = load_store(installed)
    data = tmp_path / "shared-data"
    assert store.write(data, "readings", "one", [{"payload": b"\x00\xff\x80"}],
                       schema={"payload": "BLOB"}, binary=True) == 1
    with store.read_key(data, "readings", "one") as cursor:
        assert cursor.fetchall() == [(b"\x00\xff\x80",)]
    assert store.DATA_STORE_API_VERSION == 2
    assert "binary-write-v1" in store.DATA_STORE_CAPABILITIES


@pytest.mark.parametrize("command", ["query", "read-key", "read-keys"])
def test_independent_binary_cli_outputs_metadata_and_refuses_blob(tmp_path, command):
    installed = tmp_path / "installed-skill"
    shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
    store = load_store(installed)
    data = tmp_path / "shared-data"
    store.write(data, "readings", "one", [
        {"id": "1", "payload": b"\x00\xff", "other": b""},
        {"id": 2, "payload": b"", "other": None},
        {"id": 3, "payload": None, "other": b"third"},
    ], schema={"payload": "BLOB", "id": "INTEGER", "other": "blob"}, binary=True)
    with store.read_key(data, "readings", "one") as cursor:
        assert cursor.fetchall() == [(b"\x00\xff", 1, b""), (b"", 2, None), (None, 3, b"third")]
    with store.read_keys(data, "readings", ["one"], columns=["id", "other"], filters={"id": 3}) as cursor:
        assert cursor.fetchall() == [(3, b"third")]
    with store.query(data, "SELECT id, payload FROM readings WHERE id = ?", [2], tables=["readings"]) as cursor:
        assert cursor.fetchall() == [(2, b"")]
    script = installed / "scripts/data_store.py"
    prefix = [sys.executable, str(script), "--root", str(data)]
    metadata_args = (["query", "SELECT id FROM readings ORDER BY id", "--tables", '["readings"]']
                     if command == "query" else [command, "readings", "one", "--columns", '["id"]'])
    metadata = subprocess.run(prefix + metadata_args, text=True, capture_output=True, cwd=tmp_path)
    assert metadata.returncode == 0, metadata.stderr
    assert [json.loads(line) for line in metadata.stdout.splitlines()] == [{"id": 1}, {"id": 2}, {"id": 3}]
    blob_args = (["query", "SELECT payload FROM readings", "--tables", '["readings"]']
                 if command == "query" else [command, "readings", "one", "--columns", '["payload"]'])
    refused = subprocess.run(prefix + blob_args, text=True, capture_output=True, cwd=tmp_path)
    assert refused.returncode == 2
    assert refused.stdout == ""
    assert "BLOB" in refused.stderr and "元数据" in refused.stderr and "编码" in refused.stderr
    if command == "query":
        ordinary = subprocess.run(prefix + ["query", "SELECT [1, 2]::INTEGER[2] AS values", "--tables", '["readings"]'],
                                  text=True, capture_output=True, cwd=tmp_path)
        assert ordinary.returncode == 0, ordinary.stderr
        assert json.loads(ordinary.stdout) == {"values": [1, 2]}
        for projection in ("payload", "[payload]", "[payload]::BLOB[1]",
                           "struct_pack(value := payload)", "map([payload], ['tag'])"):
            sql = f"SELECT {projection} AS output FROM readings WHERE id = 1"
            nested = subprocess.run(prefix + ["query", sql, "--tables", '["readings"]'],
                                    text=True, capture_output=True, cwd=tmp_path)
            assert nested.returncode == 2
            assert nested.stdout == ""
            assert "BLOB" in nested.stderr and "编码" in nested.stderr
        encoded = subprocess.run(prefix + ["query", "SELECT hex(payload) AS text FROM readings WHERE id = 1",
                                           "--tables", '["readings"]'],
                                 text=True, capture_output=True, cwd=tmp_path)
        assert encoded.returncode == 0, encoded.stderr
        assert json.loads(encoded.stdout) == {"text": "00FF"}


def test_binary_write_preserves_legacy_json_conversion_and_blob_strings(tmp_path):
    store = load_store()
    metadata = {"label": "VARCHAR", "count": "INTEGER", "enabled": "BOOLEAN",
                "amount": "DECIMAL(12,2)", "parts": [{"n": "INTEGER"}], "detail": "JSON"}
    row = {"label": 12, "count": "7", "enabled": "true", "amount": "12.50",
           "parts": [{"n": "3"}], "detail": {"text": "value"}}
    store.write(tmp_path, "readings", "legacy", [row], schema=metadata)
    store.write(tmp_path, "readings", "binary", [dict(row, payload=b"\xff")],
                schema=dict(metadata, payload="BLOB"), binary=True)
    fields = ["label", "count", "enabled", "amount", "parts", "detail"]
    with store.read_key(tmp_path, "readings", "legacy", columns=fields) as original:
        with store.read_key(tmp_path, "readings", "binary", columns=fields) as current:
            assert current.description == original.description
            assert current.fetchall() == original.fetchall()
    for binary in (False, True):
        with pytest.raises(duckdb.Error, match="Failed to cast"):
            store.write(tmp_path, "readings", "bad", [{"count": "invalid"}],
                        schema={"count": "INTEGER"}, binary=binary)
    store.write(tmp_path, "legacy_blobs", "one", [{"payload": "\\x00\\xFF"}], schema={"payload": "BLOB"})
    with store.read_key(tmp_path, "legacy_blobs", "one") as cursor:
        assert cursor.fetchall() == [(b"\\x00\\xFF",)]
    with pytest.raises(TypeError):
        store.write(tmp_path, "legacy_blobs", "one", [{"payload": b"new"}], schema={"payload": "BLOB"})
    with store.read_key(tmp_path, "legacy_blobs", "one") as cursor:
        assert cursor.fetchall() == [(b"\\x00\\xFF",)]


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
    ([{"payload": b"new", "id": "bad"}], {"payload": "BLOB", "id": "INTEGER"}, duckdb.Error),
    ([{"payload": b"new", "id": 1}], {"payload": "BLOB", "id": "INTEGER); DROP TABLE readings; --"}, duckdb.Error),
])
def test_binary_write_rejects_invalid_records_without_replacing_old_key(tmp_path, rows, schema, error):
    store = load_store()
    store.write(tmp_path, "readings", "one", [{"payload": b"old", "id": 1}],
                schema={"payload": "BLOB", "id": "INTEGER"}, binary=True)
    with pytest.raises(error):
        store.write(tmp_path, "readings", "one", rows, schema=schema, binary=True)
    with store.read_key(tmp_path, "readings", "one") as cursor:
        assert cursor.fetchall() == [(b"old", 1)]
    assert [path.name for path in (tmp_path / "readings").iterdir()] == ["one.parquet"]


def test_binary_fields_use_names_and_keep_each_row_paired_with_its_metadata(tmp_path):
    store = load_store()
    blob_name, id_name = 'blob"; --', 'select'
    rows = [{blob_name: b"second", id_name: 2, "another": None},
            {blob_name: None, id_name: 1, "another": b"\x00\xff"},
            {blob_name: b"", id_name: 3, "another": b"third"}]
    schema = {blob_name: "BLOB", id_name: "INTEGER", "another": "BLOB"}
    store.write(tmp_path, "readings", "one", rows, schema=schema, binary=True)
    with store.read_key(tmp_path, "readings", "one", columns=[id_name, blob_name, "another"]) as cursor:
        assert sorted(cursor.fetchall()) == [(1, None, b"\x00\xff"), (2, b"second", None), (3, b"", b"third")]
    with pytest.raises(duckdb.BinderException):
        store.read_key(tmp_path, "readings", "one", columns=["unknown"])
    with duckdb.connect() as connection:
        assert connection.execute("SELECT DISTINCT compression FROM parquet_metadata(?)",
                                  [str(tmp_path / "readings/one.parquet")]).fetchall() == [("ZSTD",)]


@pytest.mark.parametrize("failure", ["temporary-write", "publication"])
def test_binary_write_failure_keeps_old_complete_key(tmp_path, monkeypatch, failure):
    store = load_store()
    schema = {"payload": "BLOB", "id": "INTEGER"}
    store.write(tmp_path, "readings", "one", [{"payload": b"old", "id": 1}], schema=schema, binary=True)

    def fail_write(relation, path, **kwargs):
        Path(path).write_bytes(b"incomplete")
        raise OSError("injected temporary write failure")

    def fail_replace(source, target):
        raise PermissionError("injected publication failure")

    with monkeypatch.context() as patch:
        if failure == "temporary-write":
            patch.setattr(duckdb.DuckDBPyRelation, "write_parquet", fail_write)
        else:
            patch.setattr(store.os, "replace", fail_replace)
            patch.setattr(store.time, "sleep", lambda delay: None)
        with pytest.raises(OSError, match="injected"):
            store.write(tmp_path, "readings", "one", [{"payload": b"new", "id": 2}], schema=schema, binary=True)
    with store.read_key(tmp_path, "readings", "one") as cursor:
        assert cursor.fetchall() == [(b"old", 1)]
    assert [path.name for path in (tmp_path / "readings").iterdir()] == ["one.parquet"]


def test_binary_write_retries_temporary_publication_lock_and_reads_fresh_data(tmp_path, monkeypatch):
    store = load_store()
    schema = {"payload": "BLOB"}
    store.write(tmp_path, "readings", "one", [{"payload": b"old"}], schema=schema, binary=True)
    store.write(tmp_path, "readings", "other", [{"payload": b"other"}], schema=schema, binary=True)
    replace = store.os.replace
    attempts = 0

    def transient_lock(source, target):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("injected temporary lock")
        return replace(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(store.os, "replace", transient_lock)
        patch.setattr(store.time, "sleep", lambda delay: None)
        store.write(tmp_path, "readings", "one", [{"payload": b"new"}], schema=schema, binary=True)
    with store.read_key(tmp_path, "readings", "one") as cursor:
        assert cursor.fetchall() == [(b"new",)]
    with store.read_keys(tmp_path, "readings", ["one", "other"]) as cursor:
        assert sorted(cursor.fetchall()) == [(b"new",), (b"other",)]
    with store.query(tmp_path, "SELECT payload FROM readings ORDER BY payload", tables=["readings"]) as cursor:
        assert cursor.fetchall() == [(b"new",), (b"other",)]


def test_binary_queries_accept_native_scalar_and_nested_parameters(tmp_path):
    store = load_store()
    store.write(tmp_path, "readings", "one", [{"payload": b"\x00\xff"}, {"payload": b""}, {"payload": None}],
                schema={"payload": "BLOB"}, binary=True)
    for sql, parameters in [
        ("SELECT payload FROM readings WHERE payload = ?", [b"\x00\xff"]),
        ("SELECT payload FROM readings WHERE payload = $value", {"value": b"\x00\xff"}),
        ("SELECT payload FROM readings WHERE payload IN (SELECT unnest(?))", [[b"\x00\xff"]]),
    ]:
        for _ in range(2):
            with store.query(tmp_path, sql, parameters, tables=["readings"]) as cursor:
                assert cursor.fetchall() == [(b"\x00\xff",)]


def test_query_requires_explicit_scope_and_read_only_sql_before_filesystem_access(tmp_path):
    store = load_store()
    assert store.DATA_STORE_API_VERSION == 2
    unavailable = tmp_path / "unavailable-root"
    with pytest.raises(TypeError, match="tables"):
        store.query(unavailable, "SELECT 1")
    for tables in (None, [], (), "readings", {"readings"}, ["../readings"], ["readings", None]):
        with pytest.raises(ValueError):
            store.query(unavailable, "SELECT 1", tables=tables)
    for sql in ("", "CREATE TABLE x AS SELECT 1", "SELECT 1; SELECT 2"):
        with pytest.raises(ValueError, match="只读"):
            store.query(unavailable, sql, tables=["readings"])
    with pytest.raises(duckdb.ParserException):
        store.query(unavailable, "SELECT FROM", tables=["readings"])
    script = SKILL / "scripts/data_store.py"
    missing_scope = subprocess.run(
        [sys.executable, str(script), "--root", str(unavailable), "query", "SELECT 1"],
        text=True, capture_output=True,
    )
    assert missing_scope.returncode == 2
    assert "--tables" in missing_scope.stderr
    for invalid in ("[]", "null", '"readings"', '["../readings"]'):
        rejected = subprocess.run(
            [sys.executable, str(script), "--root", str(unavailable), "query", "SELECT 1", "--tables", invalid],
            text=True, capture_output=True,
        )
        assert rejected.returncode == 2
        assert "tables" in rejected.stderr or "路径" in rejected.stderr
        assert rejected.stdout == ""


def test_absent_and_empty_declared_tables_are_absent_in_catalog(tmp_path):
    store = load_store()
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty" / ".unfinished").write_bytes(b"incomplete write")
    for table in ("missing", "empty"):
        with store.query(tmp_path, "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
                         [table], tables=[table]) as cursor:
            assert cursor.fetchall() == []
        with pytest.raises(duckdb.CatalogException):
            store.query(tmp_path, f"SELECT * FROM {table}", tables=[table])


@pytest.mark.parametrize("redirect", ["directory", "shard"])
def test_readers_reject_links_outside_declared_table(tmp_path, redirect):
    store = load_store()
    root = tmp_path / "data"
    outside = tmp_path / "outside"
    store.write(outside, "private", "one", [{"value": 99}])
    root.mkdir()
    if redirect == "directory":
        (root / "selected").symlink_to(outside / "private", target_is_directory=True)
    else:
        (root / "selected").mkdir()
        (root / "selected" / "one.parquet").symlink_to(outside / "private" / "one.parquet")
    with pytest.raises(ValueError):
        store.query(root, "SELECT * FROM selected", tables=("selected",))
    with pytest.raises(ValueError):
        store.read_keys(root, "selected", ["one"])


def test_query_locks_selected_files_and_preserves_engine_spill_exception(tmp_path):
    store = load_store()
    with duckdb.connect(":memory:") as original:
        original.execute("SET enable_external_access = false")
        directories, temporary = original.execute(
            "SELECT current_setting('allowed_directories'), current_setting('temp_directory')").fetchone()
    store.write(tmp_path, "selected", "one", [{"value": 7}])
    with store.query(tmp_path, "SELECT * FROM selected", tables=["selected"]) as cursor:
        assert cursor.fetchone() == (7,)
        allowed_paths, *settings = cursor.execute(
            "SELECT current_setting('allowed_paths'), current_setting('allowed_directories'), "
            "current_setting('enable_external_access'), current_setting('autoinstall_known_extensions'), "
            "current_setting('autoload_known_extensions'), current_setting('temp_directory')").fetchone()
        assert [Path(path) for path in allowed_paths] == [tmp_path / "selected" / "one.parquet"]
        assert settings == [directories, False, False, False, temporary]
        with pytest.raises(duckdb.InvalidInputException):
            cursor.execute("SET enable_external_access = true")


def test_independent_skill_cli_writes_and_queries_typed_rows(tmp_path):
    installed = tmp_path / "installed-skill"
    if SKILL.exists():
        shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
    script = installed / "scripts/data_store.py"
    data = tmp_path / "shared-data"
    rows = [{"label": "001", "score": 1.25, "parts": [{"amount": 4}, {}]},
            {"label": "002", "score": 2.5, "parts": [{"amount": 8}]}]
    written = subprocess.run(
        [sys.executable, str(script), "--root", str(data), "write", "measurements", "first"],
        input=json.dumps(rows), text=True, capture_output=True, cwd=tmp_path,
    )
    assert written.returncode == 0, written.stderr
    queried = subprocess.run(
        [sys.executable, str(script), "--root", str(data), "query",
         "SELECT label, score, parts[1].amount AS amount, parts[2].amount AS missing_amount "
         "FROM measurements WHERE score > ? ORDER BY label",
         "--tables", '["measurements"]', "--parameters", "[1]", "--batch-size", "1"],
        text=True, capture_output=True, cwd=tmp_path,
    )
    assert queried.returncode == 0, queried.stderr
    assert [json.loads(line) for line in queried.stdout.splitlines()] == [
        {"label": "001", "score": 1.25, "amount": 4, "missing_amount": None},
        {"label": "002", "score": 2.5, "amount": 8, "missing_amount": None},
    ]
    # A known key remains readable even when an unrelated shard is damaged.
    (data / "measurements" / "unrelated.parquet").write_bytes(b"not parquet")
    pointed = subprocess.run(
        [sys.executable, str(script), "--root", str(data), "read-key",
         "Measurements", "FIRST", "--batch-size", "1"],
        text=True, capture_output=True, cwd=tmp_path,
    )
    assert pointed.returncode == 0, pointed.stderr
    assert [json.loads(line) for line in pointed.stdout.splitlines()] == [
        {"label": "001", "score": 1.25, "parts": [{"amount": 4}, {"amount": None}]},
        {"label": "002", "score": 2.5, "parts": [{"amount": 8}]},
    ]
    second = subprocess.run(
        [sys.executable, str(script), "--root", str(data), "write", "measurements", "second"],
        input=json.dumps([{"label": "003", "score": 3.25, "parts": [{"amount": 9}]}]),
        text=True, capture_output=True, cwd=tmp_path,
    )
    assert second.returncode == 0, second.stderr
    batch = subprocess.run(
        [sys.executable, str(script), "--root", str(data), "read-keys", "Measurements",
         "FIRST", "second", "first", "--columns", '["label", "score"]', "--batch-size", "1"],
        text=True, capture_output=True, cwd=tmp_path,
    )
    assert batch.returncode == 0, batch.stderr
    assert sorted((json.loads(line) for line in batch.stdout.splitlines()),
                  key=lambda row: row["label"]) == [
        {"label": "001", "score": 1.25}, {"label": "002", "score": 2.5},
        {"label": "003", "score": 3.25},
    ]


def test_typed_replacement_is_atomic_and_query_is_read_only(tmp_path):
    store = load_store()
    root = tmp_path / "data"
    store.write(root, "custom", "one", [{"amount": "12.50", "valid": True}],
                schema={"amount": "DECIMAL(12,2)", "valid": "BOOLEAN"})
    with pytest.raises(duckdb.Error):
        store.write(root, "custom", "one", [{"amount": "bad", "valid": True}],
                    schema={"amount": "DECIMAL(12,2)", "valid": "BOOLEAN"})
    with store.query(root, "SELECT amount::VARCHAR, valid FROM custom", tables=["custom"]) as cursor:
        assert cursor.fetchmany(1) == [("12.50", True)]
        assert cursor.fetchmany(1) == []
    with pytest.raises(ValueError, match="只读"):
        store.query(root, "COPY custom TO 'copy.csv'", tables=["custom"])
    with pytest.raises(ValueError, match="只读"):
        store.query(root, "SELECT * FROM custom; DELETE FROM custom", tables=["custom"])
    with pytest.raises(ValueError, match="路径"):
        store.write(root, "../outside", "one", [{"x": 1}])
    with pytest.raises(ValueError, match="字段"):
        store.write(root, "custom", "one", [{"amount": 1, "unexpected": 2}],
                    schema={"amount": "INTEGER"})
    files = list(root.rglob("*.parquet"))
    with duckdb.connect() as connection:
        assert connection.execute("SELECT DISTINCT compression FROM parquet_metadata(?)", [str(files[0])]).fetchall() == [("ZSTD",)]
    assert len(files) == 1


def test_untyped_json_fallback_requires_caller_schema(tmp_path):
    store = load_store()
    with pytest.raises(ValueError, match="类型"):
        store.write(tmp_path, "custom", "one", [{"payload": {}}])
    store.write(tmp_path, "custom", "one", [{"payload": {}}],
                schema={"payload": "MAP(VARCHAR, VARCHAR)"})
    with store.query(tmp_path, "SELECT payload FROM custom", tables=["custom"]) as cursor:
        assert cursor.fetchone() == ({},)
    store.write(tmp_path, "measurements", "one", [{"score": 5, "metadata": {"label": "a"}}],
                schema={"score": "DOUBLE", "metadata": "JSON"})
    with store.query(tmp_path, "SELECT score, metadata->>'label' FROM measurements", tables=["measurements"]) as cursor:
        assert cursor.fetchone() == (5.0, "a")


def test_logical_names_share_duckdb_case_rules(tmp_path):
    store = load_store()
    store.write(tmp_path, "Readings", "First", [{"score": 1}])
    store.write(tmp_path, "readings", "second", [{"score": 2}])
    store.write(tmp_path, "READINGS", "FIRST", [{"score": 3}])
    with store.query(tmp_path, "SELECT score FROM Readings ORDER BY score", tables=["Readings"]) as cursor:
        assert cursor.fetchall() == [(2,), (3,)]


def test_cli_reports_missing_dependency(tmp_path, monkeypatch, capsys):
    store = load_store()
    original = builtins.__import__

    def without_duckdb(name, *args, **kwargs):
        if name == "duckdb":
            raise ImportError("missing")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_duckdb)
    assert store.main(["--root", str(tmp_path), "query", "SELECT 1", "--tables", '["readings"]']) == 2
    assert "缺少 DuckDB" in capsys.readouterr().err


def test_key_read_distinguishes_missing_corrupt_and_unavailable(tmp_path, monkeypatch):
    store = load_store()
    store.write(tmp_path, "readings", "first", [{"value": 7}])
    with pytest.raises(store.MissingKeyError):
        store.read_key(tmp_path, "readings", "missing")
    target = tmp_path / "readings" / "first.parquet"
    target.write_bytes(b"not parquet")
    with pytest.raises(store.CorruptDataError):
        store.read_key(tmp_path, "readings", "first")
    store.write(tmp_path, "readings", "first", [{"value": 8}])
    with store.read_key(tmp_path, "READINGS", "FIRST") as cursor:
        assert cursor.fetchmany(1) == [(8,)]
        assert cursor.fetchmany(1) == []
    original = Path.open

    def unavailable(path, *args, **kwargs):
        if path == target:
            raise PermissionError("storage unavailable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", unavailable)
    with pytest.raises(PermissionError, match="storage unavailable"):
        store.read_key(tmp_path, "readings", "first")


def test_batch_reader_preserves_types_failures_and_current_data(tmp_path, monkeypatch):
    store = load_store()
    store.write(tmp_path, "readings", "one", [{"id": 1, "parts": [{"n": 2}]}])
    store.write(tmp_path, "readings", "two", [{"id": 2, "parts": [{"n": 3}], "extra": True}])
    with store.read_keys(tmp_path, "readings", ["one", "two"]) as cursor:
        assert [str(column[1]) for column in cursor.description] == [
            "UBIGINT", "STRUCT(n UBIGINT)[]", "BOOLEAN"]
        assert sorted(cursor.fetchall()) == [(1, [{"n": 2}], None), (2, [{"n": 3}], True)]
    for keys, columns in [([], None), ("one", None), (["one"], []),
                          (["one"], ["id", "ID"]), (["one"], ["\x00"]),
                          (["../one"], None)]:
        with pytest.raises(ValueError):
            store.read_keys(tmp_path, "readings", keys, columns=columns)
    with pytest.raises(duckdb.BinderException):
        store.read_keys(tmp_path, "readings", ["one"], columns=["not a column"])
    with pytest.raises(store.MissingKeyError):
        store.read_keys(tmp_path, "readings", ["one", "missing"])
    target = tmp_path / "readings" / "two.parquet"
    target.write_bytes(b"broken")
    with pytest.raises(store.CorruptDataError):
        store.read_keys(tmp_path, "readings", ["one", "two"])
    store.write(tmp_path, "readings", "two", [{"id": 3}])
    with store.read_keys(tmp_path, "readings", ["two"], columns=["id"]) as cursor:
        assert cursor.fetchmany(1) == [(3,)]
        assert cursor.fetchmany(1) == []
    store.write(tmp_path, "names", "one", [{"odd field": 1, 'a"b': 2, "a.b": 3, "_records": 4}])
    with store.read_keys(tmp_path, "names", ["one"], columns=["a.b", 'a"b', "odd field", "_records"]) as cursor:
        assert cursor.fetchall() == [(3, 2, 1, 4)]
    original = Path.open

    def unavailable(path, *args, **kwargs):
        if path == target:
            raise PermissionError("storage unavailable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", unavailable)
    with pytest.raises(PermissionError, match="storage unavailable"):
        store.read_keys(tmp_path, "readings", ["one", "two"])


def test_key_readers_keep_projected_fields_and_scalar_filters(tmp_path):
    store = load_store()
    store.write(tmp_path, "readings", "one", [
        {"label": "002", "score": 7, "active": True, "optional": None, "parts": [{"n": 2}]},
        {"label": "001", "score": 3, "active": False, "optional": "set", "parts": [{"n": 1}]},
    ])
    store.write(tmp_path, "readings", "two", [
        {"label": "002", "score": 7, "active": True, "optional": None, "parts": [{"n": 4}]},
    ])
    filters = {"label": "002", "score": 7, "active": True, "optional": None}
    with store.read_key(tmp_path, "readings", "one", columns=["label", "parts"], filters=filters) as cursor:
        assert cursor.fetchmany(1) == [("002", [{"n": 2}])]
        assert cursor.fetchmany(1) == []
    with store.read_keys(tmp_path, "readings", ["one", "TWO", "two"],
                         columns=["parts"], filters=filters) as cursor:
        assert sorted(cursor.fetchall(), key=lambda row: row[0][0]["n"]) == [([{"n": 2}],), ([{"n": 4}],)]
    for invalid in ({}, {"label": []}, {"label": "002", "LABEL": "002"}):
        with pytest.raises(ValueError, match="筛选"):
            store.read_key(tmp_path, "readings", "one", filters=invalid)
    with pytest.raises(duckdb.BinderException):
        store.read_keys(tmp_path, "readings", ["one"], filters={"unknown": 1})


def test_queries_preserve_generic_tables_and_fresh_data(tmp_path):
    store = load_store()
    root = tmp_path / "data"
    store.write(root, "select", "physical_one", [{"logical.identity": "business-1",
                "report": {"parts": [{"n": 2}]}, "report.x": 7}])
    store.write(root, "custom", "one", [{"id": "business-1", "amount": 4}])
    (root / "select" / "physical_one.parquet").rename(root / "select" / "renamed.parquet")
    sql = ('WITH chosen AS (SELECT * FROM "select" WHERE "logical.identity" = $id) '
           'SELECT report.parts[1].n, "report.x", amount FROM chosen '
           'JOIN custom ON "logical.identity" = id')
    for _ in range(2):
        with store.query(root, sql, {"id": "business-1"}, tables=["select", "custom"]) as cursor:
            assert cursor.fetchall() == [(2, 7, 4)]
    store.write(root, "custom", "one", [{"id": "business-1", "amount": 8}])
    with store.query(root, sql, {"id": "business-1"}, tables=["select", "custom"]) as cursor:
        assert cursor.fetchall() == [(2, 7, 8)]
    store.write(root, "custom", "two", [{"id": "business-1", "amount": 9}])
    with store.query(root, sql, {"id": "business-1"}, tables=["select", "custom"]) as cursor:
        assert sorted(cursor.fetchall()) == [(2, 7, 8), (2, 7, 9)]
    (root / "custom" / "two.parquet").unlink()
    with store.query(root, sql, {"id": "business-1"}, tables=["select", "custom"]) as cursor:
        assert cursor.fetchall() == [(2, 7, 8)]
    (root / "custom" / "one.parquet").write_bytes(b"bad")
    with store.query(root, 'SELECT * FROM "select"', tables=["select"]) as cursor:
        assert cursor.fetchone() == ("business-1", {"parts": [{"n": 2}]}, 7)
    with pytest.raises(duckdb.Error):
        store.query(root, 'SELECT * FROM custom', tables=["custom"])


def test_projected_fields_cannot_be_replaced_by_implicit_whole_rows(tmp_path):
    store = load_store()
    store.write(tmp_path, "custom", "one", [{"id": 1}])
    with pytest.raises(duckdb.BinderException):
        store.read_keys(tmp_path, "custom", ["one"], columns=["_records"])


def test_mixed_large_and_small_reads_keep_engine_default(tmp_path):
    store = load_store()
    with duckdb.connect() as connection:
        default = connection.execute("SELECT current_setting('threads')").fetchone()[0]
    store.write(tmp_path, "small", "one", [{"report": {"parts": [1, 2]}}])
    store.write(tmp_path, "flat", "many", [{"id": i} for i in range(2048)])
    sql = "SELECT report, current_setting('threads') FROM small CROSS JOIN flat LIMIT 1"
    with store.query(tmp_path, sql, tables=["small", "flat"]) as cursor:
        assert cursor.fetchone() == ({"parts": [1, 2]}, default)


def test_unregistered_file_scan_does_not_borrow_logical_table_types(tmp_path):
    store = load_store()
    with duckdb.connect() as connection:
        default = connection.execute("SELECT current_setting('threads')").fetchone()[0]
        connection.execute("COPY (SELECT 'plain' AS payload) TO ? (FORMAT PARQUET)",
                           [str(tmp_path / "loose.parquet")])
    store.write(tmp_path, "custom", "one", [{"payload": {"nested": [1, 2]}}])
    sql = "SELECT payload, current_setting('threads') FROM read_parquet(?)"
    for _ in range(2):
        with pytest.raises(duckdb.PermissionException):
            store.query(tmp_path, sql, [str(tmp_path / "loose.parquet")], tables=["custom"])
        with store.query(tmp_path, sql, [str(tmp_path / "custom" / "one.parquet")], tables=["custom"]) as cursor:
            assert cursor.fetchone() == ({"nested": [1, 2]}, default)


def test_small_complex_logical_read_automatically_uses_one_worker(tmp_path):
    store = load_store()
    store.write(tmp_path, "custom", "one", [{"report": {"parts": [1, 2]}}])
    for _ in range(2):
        with store.query(tmp_path, "SELECT report, current_setting('threads') FROM custom", tables=["custom"]) as cursor:
            assert cursor.fetchone() == ({"parts": [1, 2]}, 1)


def test_installed_cli_plans_and_deletes_exact_record_groups(tmp_path):
    installed = tmp_path / "installed-maintenance"
    shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
    store = load_store(installed)
    data = tmp_path / "data"
    for key in ("one", "two", "keep"):
        store.write(data, "readings", key, [{"value": key}])
    unrelated = data / "history"
    unrelated.mkdir()
    (unrelated / "broken.parquet").write_bytes(b"not parquet")
    script = installed / "scripts/data_store.py"
    prefix = [sys.executable, str(script), "--root", str(data)]
    planned = subprocess.run(prefix + ["delete-plan", "--targets",
                             '{"Readings":["ONE","two","one"]}'],
                             text=True, capture_output=True, cwd=tmp_path)
    assert planned.returncode == 0, planned.stderr
    plan = json.loads(planned.stdout)
    assert [(item["table"], item["key"]) for item in plan["targets"]] == [
        ("readings", "one"), ("readings", "two")]
    assert (data / "readings/one.parquet").is_file()
    plan_path = tmp_path / "delete-plan.json"
    plan_path.write_text(planned.stdout)
    receipt_path = tmp_path / "delete-receipt.json"
    denied = subprocess.run(prefix + ["delete-execute", "--plan", str(plan_path),
                            "--approve", plan["plan_id"], "--receipt", str(receipt_path)],
                            text=True, capture_output=True, cwd=tmp_path)
    assert denied.returncode == 2
    assert (data / "readings/one.parquet").is_file()
    executed = subprocess.run(prefix + ["delete-execute", "--plan", str(plan_path),
                              "--approve", plan["plan_id"], "--offline", "--receipt", str(receipt_path)],
                              text=True, capture_output=True, cwd=tmp_path)
    assert executed.returncode == 0, executed.stderr
    receipt = json.loads(executed.stdout)
    assert receipt["atomic"] is False
    assert [item["status"] for item in receipt["items"]] == ["deleted", "deleted"]
    records = [json.loads(line) for line in receipt_path.read_text().splitlines()]
    assert records[0]["format"] == "data-store-delete-log-v1"
    assert records[0]["plan_id"] == plan["plan_id"]
    assert [(record["item"], record["status"]) for record in records[1:]] == [
        (0, "uncertain"), (0, "deleted"), (1, "uncertain"), (1, "deleted")]
    assert all("file" not in record and "items" not in record for record in records[1:])
    assert (unrelated / "broken.parquet").read_bytes() == b"not parquet"
    with store.read_key(data, "readings", "keep") as cursor:
        assert cursor.fetchall() == [("keep",)]
    store.write(data, "readings", "one", [{"value": "rebuilt"}])
    resumed = subprocess.run(prefix + ["delete-execute", "--plan", str(plan_path),
                             "--approve", plan["plan_id"], "--offline", "--receipt", str(receipt_path)],
                             text=True, capture_output=True, cwd=tmp_path)
    assert resumed.returncode == 0, resumed.stderr
    with store.read_key(data, "readings", "one") as cursor:
        assert cursor.fetchall() == [("rebuilt",)]


def _delete_fixture(tmp_path, count=3):
    installed = tmp_path / "installed-maintenance"
    shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
    store = load_store(installed)
    data = tmp_path / "data"
    for index in range(count):
        store.write(data, "readings", str(index), [{"value": index}])
    prefix = [sys.executable, str(installed / "scripts/data_store.py"), "--root", str(data)]
    planned = subprocess.run(prefix + ["delete-plan", "--targets",
                             json.dumps({"readings": [str(index) for index in range(count)]})],
                             text=True, capture_output=True, cwd=tmp_path)
    assert planned.returncode == 0, planned.stderr
    plan = json.loads(planned.stdout)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(planned.stdout)
    receipt = tmp_path / "receipt.json"
    arguments = prefix[1:] + ["delete-execute", "--plan", str(plan_path), "--approve", plan["plan_id"],
                              "--offline", "--receipt", str(receipt)]
    return store, data, plan_path, receipt, arguments


def _execute_delete_cli(tmp_path, arguments, fault=""):
    # Fault only an OS boundary in this isolated child, then run the real installed
    # script and argument parser. No production-only test hooks or fake state machine.
    source = "import errno, json, os, runpy, sys\nfrom pathlib import Path\n" + fault
    source += "\nsys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name='__main__')\n"
    return subprocess.run([sys.executable, "-c", source, *arguments],
                          text=True, capture_output=True, cwd=tmp_path)


@pytest.mark.parametrize("change,code", [
    ("replace", "identity_changed"), ("content", "identity_changed"), ("missing", "missing"),
    ("redirect", "redirected"), ("permission", "permission_or_lock"), ("lock", "locked"),
    ("root", "root_identity_changed"), ("root-missing", "root_unavailable"),
])
def test_installed_delete_full_preflight_changes_nothing(tmp_path, change, code):
    store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path)
    first = data / "readings/0.parquet"
    target = data / "readings/1.parquet"
    original = first.read_bytes()
    fault = ""
    if change == "replace":
        replacement = target.with_suffix(".new")
        replacement.write_bytes(target.read_bytes())
        replacement.replace(target)
    elif change == "content":
        payload = bytearray(target.read_bytes())
        payload[4] ^= 1
        target.write_bytes(payload)
    elif change == "missing":
        target.unlink()
    elif change == "redirect":
        target.unlink()
        target.symlink_to(first)
    elif change in ("permission", "lock"):
        failure = 'PermissionError("injected permission")' if change == "permission" else 'OSError(errno.EBUSY, "injected lock")'
        fault = ("original_open = Path.open\n"
                 "def fail_open(path, *args, **kwargs):\n"
                 "    if path.name == '1.parquet':\n"
                 f"        raise {failure}\n"
                 "    return original_open(path, *args, **kwargs)\n"
                 "Path.open = fail_open\n")
    else:
        data.rename(tmp_path / "original-data")
        if change == "root":
            data.mkdir()
            shutil.copytree(tmp_path / "original-data/readings", data / "readings")
    executed = _execute_delete_cli(tmp_path, arguments, fault)
    assert executed.returncode == 2, executed.stdout
    receipt = json.loads(executed.stdout)
    assert receipt["state"] == "incomplete"
    assert not any(item["status"] == "deleted" for item in receipt["items"])
    assert any(item.get("error", {}).get("code") == code for item in receipt["items"])
    assert (tmp_path / "original-data/readings/0.parquet" if change.startswith("root") else first).read_bytes() == original


def test_installed_delete_partial_failure_resumes_only_original_unfinished_items(tmp_path):
    store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path)
    fault = ("original_unlink = Path.unlink\n"
             "def fail_unlink(path, *args, **kwargs):\n"
             "    if path.name == '1.parquet':\n"
             "        raise PermissionError('injected delete lock')\n"
             "    return original_unlink(path, *args, **kwargs)\n"
             "Path.unlink = fail_unlink\n")
    partial = _execute_delete_cli(tmp_path, arguments, fault)
    assert partial.returncode == 2, partial.stderr
    receipt = json.loads(partial.stdout)
    assert [item["status"] for item in receipt["items"]] == ["deleted", "failed", "not_executed"]
    assert receipt["items"][1]["error"]["code"] == "permission_or_lock"
    assert not (data / "readings/0.parquet").exists()
    store.write(data, "readings", "0", [{"value": "later rebuild"}])
    resumed = _execute_delete_cli(tmp_path, arguments)
    assert resumed.returncode == 0, resumed.stderr
    assert [item["status"] for item in json.loads(resumed.stdout)["items"]] == ["deleted"] * 3
    with store.read_key(data, "readings", "0") as cursor:
        assert cursor.fetchall() == [("later rebuild",)]
    assert not (data / "readings/1.parquet").exists()
    assert not (data / "readings/2.parquet").exists()


@pytest.mark.parametrize("failure", ["receipt", "unlink-outcome", "truncated-log"])
def test_installed_delete_uncertain_outcome_never_blindly_retries(tmp_path, failure):
    store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path)
    if failure in ("receipt", "truncated-log"):
        partial_write = "original_write(descriptor, payload[:len(payload)//2])" if failure == "truncated-log" else "pass"
        fault = ("original_write = os.write\n"
                 "def fail_write(descriptor, payload):\n"
                 "    if not Path('data/readings/0.parquet').exists():\n"
                 f"        {partial_write}\n"
                 "        raise OSError('injected receipt failure after unlink')\n"
                 "    return original_write(descriptor, payload)\n"
                 "os.write = fail_write\n")
    else:
        fault = ("original_unlink = Path.unlink\n"
                 "def fail_unlink(path, *args, **kwargs):\n"
                 "    result = original_unlink(path, *args, **kwargs)\n"
                 "    if path.name == '0.parquet':\n"
                 "        raise OSError('injected unknown unlink outcome')\n"
                 "    return result\n"
                 "Path.unlink = fail_unlink\n")
    uncertain = _execute_delete_cli(tmp_path, arguments, fault)
    assert uncertain.returncode == 2, uncertain.stderr
    output = json.loads(uncertain.stdout)
    assert output["state"] == "uncertain"
    assert [item["status"] for item in output["items"]] == ["uncertain", "not_executed", "not_executed"]
    lines = receipt_path.read_text().splitlines()
    assert json.loads(lines[0])["format"] == "data-store-delete-log-v1"
    assert json.loads(lines[1])["status"] == "uncertain"
    if failure == "receipt":
        assert output["items"][0]["error"]["code"] == "receipt_write_failed"
    assert not (data / "readings/0.parquet").exists()
    store.write(data, "readings", "0", [{"value": "later rebuild"}])
    resumed = _execute_delete_cli(tmp_path, arguments)
    assert resumed.returncode == 2
    assert json.loads(resumed.stdout)["state"] == "uncertain"
    with store.read_keys(data, "readings", ["0", "1", "2"]) as cursor:
        assert len(cursor.fetchall()) == 3


def test_installed_delete_rechecks_identity_after_full_preflight(tmp_path):
    store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path)
    fault = ("original_unlink = Path.unlink\n"
             "def change_after_first(path, *args, **kwargs):\n"
             "    result = original_unlink(path, *args, **kwargs)\n"
             "    if path.name == '0.parquet':\n"
             "        target = path.with_name('1.parquet')\n"
             "        replacement = target.with_suffix('.new')\n"
             "        replacement.write_bytes(target.read_bytes())\n"
             "        os.replace(replacement, target)\n"
             "    return result\n"
             "Path.unlink = change_after_first\n")
    partial = _execute_delete_cli(tmp_path, arguments, fault)
    assert partial.returncode == 2, partial.stderr
    receipt = json.loads(partial.stdout)
    assert [item["status"] for item in receipt["items"]] == ["deleted", "failed", "not_executed"]
    assert receipt["items"][1]["error"]["code"] == "identity_changed"
    assert (data / "readings/1.parquet").is_file()
    assert (data / "readings/2.parquet").is_file()


@pytest.mark.parametrize("targets", [None, {}, [], {"readings": []}, {"readings": "one"},
                                      {"readings": [""]}, {"readings": ["*"]},
                                      {"../outside": ["one"]}, {"readings": ["../one"]}])
def test_installed_delete_plan_rejects_nonexact_targets_before_root_access(tmp_path, targets):
    script = SKILL / "scripts/data_store.py"
    planned = subprocess.run([sys.executable, str(script), "--root", str(tmp_path / "absent"),
                              "delete-plan", "--targets", json.dumps(targets)],
                             text=True, capture_output=True, cwd=tmp_path)
    assert planned.returncode == 2
    assert planned.stdout == ""
    assert "数据根不可用" not in planned.stderr
    assert "No such file" not in planned.stderr


@pytest.mark.parametrize("change", ["approval", "plan", "root", "receipt-in-data", "receipt-other-plan"])
def test_installed_delete_rejects_wrong_authority_and_receipt(tmp_path, change):
    store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path)
    if change == "approval":
        arguments[arguments.index("--approve") + 1] = "another-plan"
    elif change == "plan":
        plan = json.loads(plan_path.read_text())
        plan["targets"][0]["key"] = "unapproved"
        plan_path.write_text(json.dumps(plan))
    elif change == "root":
        arguments[arguments.index("--root") + 1] = str(tmp_path / "another-root")
    elif change == "receipt-in-data":
        arguments[arguments.index("--receipt") + 1] = str(data / "receipt.json")
    else:
        receipt_path.write_text('{"format":"unrelated","important":"keep me"}')
    executed = _execute_delete_cli(tmp_path, arguments)
    assert executed.returncode == 2
    assert executed.stdout == ""
    for index in range(3):
        with store.read_key(data, "readings", str(index)) as cursor:
            assert cursor.fetchall() == [(index,)]
    if change == "receipt-other-plan":
        assert json.loads(receipt_path.read_text())["important"] == "keep me"


def test_installed_delete_disappearance_before_unlink_is_not_our_deletion(tmp_path):
    store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path)
    fault = ("original_write = os.write\n"
             "def remove_before_final_check(descriptor, payload):\n"
             "    record = json.loads(payload)\n"
             "    result = original_write(descriptor, payload)\n"
             "    if record.get('item') == 0 and record.get('status') == 'uncertain':\n"
             "        Path('data/readings/0.parquet').unlink()\n"
             "    return result\n"
             "os.write = remove_before_final_check\n")
    partial = _execute_delete_cli(tmp_path, arguments, fault)
    assert partial.returncode == 2, partial.stderr
    receipt = json.loads(partial.stdout)
    assert [item["status"] for item in receipt["items"]] == ["failed", "not_executed", "not_executed"]
    assert receipt["items"][0]["error"]["code"] == "missing"
    assert (data / "readings/1.parquet").is_file()
