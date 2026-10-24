"""Explicit native-data scenarios: DuckDB, Parquet and durable maintenance."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins/data-store/skills/data-store"


@pytest.fixture(scope="session")
def data_store_installation(tmp_path_factory):
    """One complete installed-shaped skill, read-only to the scenarios using it."""
    target = tmp_path_factory.mktemp("native-data-skill") / "data-store"
    shutil.copytree(SKILL, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def load_store(skill=SKILL):
    spec = importlib.util.spec_from_file_location("data_store", skill / "scripts/data_store.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _delete_fixture(tmp_path, installed, count=3):
    store = load_store(installed)
    data = tmp_path / "data"
    for index in range(count):
        store.write(data, "readings", str(index), [{"value": index}])
    # The installed CLI preview is proved once below. Maintenance failure cases
    # reuse the public Python preview instead of starting a redundant CLI child.
    plan = store.plan_delete(data, {"readings": [str(index) for index in range(count)]})
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    arguments = [str(installed / "scripts/data_store.py"), "--root", str(data),
                 "delete-execute", "--plan", str(plan_path), "--approve", plan["plan_id"],
                 "--offline", "--receipt", str(receipt)]
    return store, data, plan_path, receipt, arguments


def _execute_delete_cli(tmp_path, arguments, fault=""):
    # Fault only an OS boundary in this isolated child, then run the real installed
    # script and argument parser. No production-only test hooks or fake state machine.
    source = "import errno, json, os, runpy, sys\nfrom pathlib import Path\n" + fault
    source += "\nsys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name='__main__')\n"
    return subprocess.run([sys.executable, "-c", source, *arguments],
                          text=True, capture_output=True, cwd=tmp_path)


class TestDataStore:
    """All native database behavior belongs to the explicit real-data check."""

    @pytest.fixture(autouse=True)
    def native_engine(self):
        # Import only after the explicit real selector starts executing tests.
        global duckdb
        import duckdb as engine
        duckdb = engine

    def test_installed_cli_query_prepares_only_declared_logical_tables(self, data_store_installation, tmp_path):
        installed = data_store_installation
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



    def test_installed_cli_query_cannot_read_undeclared_parquet_or_sqlite(self, data_store_installation, tmp_path):
        installed = data_store_installation
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
    def test_key_cursors_allow_only_selected_files_and_lock_configuration(self, data_store_installation, tmp_path, batch):
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
    def test_installed_readers_reject_same_root_table_redirection(self, data_store_installation, tmp_path, command):
        installed = data_store_installation
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



    def test_installed_cli_filters_one_row_within_a_logical_group(self, data_store_installation, tmp_path):
        script = data_store_installation / "scripts/data_store.py"
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



    def test_independent_skill_python_binary_write_round_trips_bytes(self, data_store_installation, tmp_path):
        installed = data_store_installation
        store = load_store(installed)
        data = tmp_path / "shared-data"
        assert store.write(data, "readings", "one", [{"payload": b"\x00\xff\x80"}],
                           schema={"payload": "BLOB"}, binary=True) == 1
        with store.read_key(data, "readings", "one") as cursor:
            assert cursor.fetchall() == [(b"\x00\xff\x80",)]
        assert store.DATA_STORE_API_VERSION == 2
        assert "binary-write-v1" in store.DATA_STORE_CAPABILITIES



    @pytest.mark.parametrize("command", ["query", "read-key", "read-keys"])
    def test_independent_binary_cli_outputs_metadata_and_refuses_blob(self, data_store_installation, tmp_path, command):
        installed = data_store_installation
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



    def test_binary_write_preserves_legacy_json_conversion_and_blob_strings(self, data_store_installation, tmp_path):
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
        ([{"payload": "text"}], {"payload": "BLOB"}, TypeError),
        ([{"payload": b"new", "id": "bad"}], {"payload": "BLOB", "id": "INTEGER"}, "Error"),
        ([{"payload": b"new", "id": 1}], {"payload": "BLOB", "id": "INTEGER); DROP TABLE readings; --"}, "Error"),
    ])
    def test_binary_write_rejects_invalid_records_without_replacing_old_key(self, data_store_installation, tmp_path, rows, schema, error):
        store = load_store()
        store.write(tmp_path, "readings", "one", [{"payload": b"old", "id": 1}],
                    schema={"payload": "BLOB", "id": "INTEGER"}, binary=True)
        with pytest.raises(getattr(duckdb, error) if isinstance(error, str) else error):
            store.write(tmp_path, "readings", "one", rows, schema=schema, binary=True)
        with store.read_key(tmp_path, "readings", "one") as cursor:
            assert cursor.fetchall() == [(b"old", 1)]
        assert [path.name for path in (tmp_path / "readings").iterdir()] == ["one.parquet"]


    def test_binary_fields_use_names_and_keep_each_row_paired_with_its_metadata(self, data_store_installation, tmp_path):
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
    def test_binary_write_failure_keeps_old_complete_key(self, data_store_installation, tmp_path, monkeypatch, failure):
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



    def test_binary_write_retries_temporary_publication_lock_and_reads_fresh_data(self, data_store_installation, tmp_path, monkeypatch):
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



    def test_binary_queries_accept_native_scalar_and_nested_parameters(self, data_store_installation, tmp_path):
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



    def test_query_rejects_nonreadonly_or_invalid_sql_before_filesystem_access(self, data_store_installation, tmp_path):
        store = load_store()
        unavailable = tmp_path / "unavailable-root"
        for sql in ("", "CREATE TABLE x AS SELECT 1", "SELECT 1; SELECT 2"):
            with pytest.raises(ValueError, match="只读"):
                store.query(unavailable, sql, tables=["readings"])
        with pytest.raises(duckdb.ParserException):
            store.query(unavailable, "SELECT FROM", tables=["readings"])


    def test_absent_and_empty_declared_tables_are_absent_in_catalog(self, data_store_installation, tmp_path):
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
    def test_readers_reject_links_outside_declared_table(self, data_store_installation, tmp_path, redirect):
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



    def test_query_locks_selected_files_and_preserves_engine_spill_exception(self, data_store_installation, tmp_path):
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



    def test_independent_skill_cli_writes_and_queries_typed_rows(self, data_store_installation, tmp_path):
        installed = data_store_installation
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



    def test_typed_replacement_is_atomic_and_query_is_read_only(self, data_store_installation, tmp_path):
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



    def test_untyped_json_fallback_requires_caller_schema(self, data_store_installation, tmp_path):
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



    def test_logical_names_share_duckdb_case_rules(self, data_store_installation, tmp_path):
        store = load_store()
        store.write(tmp_path, "Readings", "First", [{"score": 1}])
        store.write(tmp_path, "readings", "second", [{"score": 2}])
        store.write(tmp_path, "READINGS", "FIRST", [{"score": 3}])
        with store.query(tmp_path, "SELECT score FROM Readings ORDER BY score", tables=["Readings"]) as cursor:
            assert cursor.fetchall() == [(2,), (3,)]



    def test_key_read_distinguishes_missing_corrupt_and_unavailable(self, data_store_installation, tmp_path, monkeypatch):
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



    def test_batch_reader_preserves_types_failures_and_current_data(self, data_store_installation, tmp_path, monkeypatch):
        store = load_store()
        store.write(tmp_path, "readings", "one", [{"id": 1, "parts": [{"n": 2}]}])
        store.write(tmp_path, "readings", "two", [{"id": 2, "parts": [{"n": 3}], "extra": True}])
        with store.read_keys(tmp_path, "readings", ["one", "two"]) as cursor:
            assert [str(column[1]) for column in cursor.description] == [
                "UBIGINT", "STRUCT(n UBIGINT)[]", "BOOLEAN"]
            assert sorted(cursor.fetchall()) == [(1, [{"n": 2}], None), (2, [{"n": 3}], True)]
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



    def test_key_readers_keep_projected_fields_and_scalar_filters(self, data_store_installation, tmp_path):
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
        with pytest.raises(duckdb.BinderException):
            store.read_keys(tmp_path, "readings", ["one"], filters={"unknown": 1})



    def test_queries_preserve_generic_tables_and_fresh_data(self, data_store_installation, tmp_path):
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



    def test_projected_fields_cannot_be_replaced_by_implicit_whole_rows(self, data_store_installation, tmp_path):
        store = load_store()
        store.write(tmp_path, "custom", "one", [{"id": 1}])
        with pytest.raises(duckdb.BinderException):
            store.read_keys(tmp_path, "custom", ["one"], columns=["_records"])



    def test_mixed_large_and_small_reads_keep_engine_default(self, data_store_installation, tmp_path):
        store = load_store()
        with duckdb.connect() as connection:
            default = connection.execute("SELECT current_setting('threads')").fetchone()[0]
        store.write(tmp_path, "small", "one", [{"report": {"parts": [1, 2]}}])
        store.write(tmp_path, "flat", "many", [{"id": i} for i in range(2048)])
        sql = "SELECT report, current_setting('threads') FROM small CROSS JOIN flat LIMIT 1"
        with store.query(tmp_path, sql, tables=["small", "flat"]) as cursor:
            assert cursor.fetchone() == ({"parts": [1, 2]}, default)



    def test_unregistered_file_scan_does_not_borrow_logical_table_types(self, data_store_installation, tmp_path):
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



    def test_small_complex_logical_read_automatically_uses_one_worker(self, data_store_installation, tmp_path):
        store = load_store()
        store.write(tmp_path, "custom", "one", [{"report": {"parts": [1, 2]}}])
        for _ in range(2):
            with store.query(tmp_path, "SELECT report, current_setting('threads') FROM custom", tables=["custom"]) as cursor:
                assert cursor.fetchone() == ({"parts": [1, 2]}, 1)



    def test_installed_cli_plans_and_deletes_exact_record_groups(self, data_store_installation, tmp_path):
        installed = data_store_installation
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



    @pytest.mark.parametrize("change,code", [
        ("replace", "identity_changed"), ("content", "identity_changed"), ("missing", "missing"),
        ("redirect", "redirected"), ("permission", "permission_or_lock"), ("lock", "locked"),
        ("root", "root_identity_changed"), ("root-missing", "root_unavailable"),
    ])
    def test_installed_delete_full_preflight_changes_nothing(self, data_store_installation, tmp_path, change, code):
        store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path, data_store_installation)
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



    def test_installed_delete_partial_failure_resumes_only_original_unfinished_items(self, data_store_installation, tmp_path):
        store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path, data_store_installation)
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
    def test_installed_delete_uncertain_outcome_never_blindly_retries(self, data_store_installation, tmp_path, failure):
        store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path, data_store_installation)
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



    def test_installed_delete_rechecks_identity_after_full_preflight(self, data_store_installation, tmp_path):
        store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path, data_store_installation)
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



    @pytest.mark.parametrize("change", ["approval", "plan", "root", "receipt-in-data", "receipt-other-plan"])
    def test_installed_delete_rejects_wrong_authority_and_receipt(self, data_store_installation, tmp_path, change):
        store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path, data_store_installation)
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



    def test_installed_delete_disappearance_before_unlink_is_not_our_deletion(self, data_store_installation, tmp_path):
        store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path, data_store_installation)
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



    @pytest.mark.parametrize("entrypoint", ["python", "cli"])
    def test_installed_delete_accepts_distinct_stable_fd_ctime(self, data_store_installation, tmp_path, monkeypatch, entrypoint):
        store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path, data_store_installation)
        if entrypoint == "python":
            original_fstat = store.os.fstat

            class FdStat:
                def __init__(self, actual):
                    self.actual = actual

                def __getattr__(self, field):
                    value = getattr(self.actual, field)
                    return value + 123456 if field == "st_ctime_ns" else value

            monkeypatch.setattr(store.os, "fstat", lambda descriptor: FdStat(original_fstat(descriptor)))
            plan = store.plan_delete(data, {"readings": ["0", "1", "2"]})
            result = store.execute_delete(data, plan, approve=plan["plan_id"], offline=True,
                                          receipt_path=receipt_path)
            assert result["state"] == "complete"
        else:
            fault = ("original_fstat = os.fstat\n"
                     "class FdStat:\n"
                     "    def __init__(self, actual):\n"
                     "        self.actual = actual\n"
                     "    def __getattr__(self, field):\n"
                     "        value = getattr(self.actual, field)\n"
                     "        return value + 123456 if field == 'st_ctime_ns' else value\n"
                     "os.fstat = lambda descriptor: FdStat(original_fstat(descriptor))\n")
            planned = _execute_delete_cli(tmp_path, arguments[:3] + ["delete-plan", "--targets",
                                          '{"readings":["0","1","2"]}'], fault)
            assert planned.returncode == 0, planned.stderr
            plan_path.write_text(planned.stdout)
            arguments[arguments.index("--approve") + 1] = json.loads(planned.stdout)["plan_id"]
            executed = _execute_delete_cli(tmp_path, arguments, fault)
            assert executed.returncode == 0, executed.stderr
            assert json.loads(executed.stdout)["state"] == "complete"



    @pytest.mark.skipif(os.name == "nt", reason="目录 fsync 只适用于支持该操作的平台")
    def test_installed_delete_resume_syncs_existing_receipt_directory_before_unlink(self, data_store_installation, tmp_path):
        store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path, data_store_installation)
        fault = ("import stat\n"
                 "original_fsync = os.fsync\n"
                 "def fail_directory_sync(descriptor):\n"
                 "    if stat.S_ISDIR(os.fstat(descriptor).st_mode):\n"
                 "        raise OSError('injected receipt directory sync failure')\n"
                 "    return original_fsync(descriptor)\n"
                 "os.fsync = fail_directory_sync\n")
        first = _execute_delete_cli(tmp_path, arguments, fault)
        assert first.returncode == 2
        assert receipt_path.exists()
        header = receipt_path.read_bytes()
        assert len(header.splitlines()) == 1
        second = _execute_delete_cli(tmp_path, arguments, fault)
        assert second.returncode == 2
        assert receipt_path.read_bytes() == header
        for index in range(3):
            assert (data / "readings" / f"{index}.parquet").is_file()
        resumed = _execute_delete_cli(tmp_path, arguments)
        assert resumed.returncode == 0, resumed.stderr
        assert json.loads(resumed.stdout)["state"] == "complete"



    @pytest.mark.parametrize("source", ["path", "fd"])
    def test_installed_delete_rejects_source_local_ctime_drift(self, data_store_installation, tmp_path, source):
        store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path, data_store_installation)
        fault = ("class ChangedStat:\n"
                 "    def __init__(self, actual, change):\n"
                 "        self.actual, self.change = actual, change\n"
                 "    def __getattr__(self, field):\n"
                 "        value = getattr(self.actual, field)\n"
                 "        return value + self.change if field == 'st_ctime_ns' else value\n"
                 "calls = 0\n")
        if source == "fd":
            fault += ("original_fstat = os.fstat\n"
                      "def changed_fstat(descriptor):\n"
                      "    global calls\n"
                      "    calls += 1\n"
                      "    return ChangedStat(original_fstat(descriptor), calls)\n"
                      "os.fstat = changed_fstat\n")
        else:
            fault += ("original_stat = Path.stat\n"
                      "def changed_stat(path, *args, **kwargs):\n"
                      "    global calls\n"
                      "    actual = original_stat(path, *args, **kwargs)\n"
                      "    if path.name == '0.parquet' and kwargs.get('follow_symlinks', True):\n"
                      "        calls += 1\n"
                      "        return ChangedStat(actual, calls)\n"
                      "    return actual\n"
                      "Path.stat = changed_stat\n")
        executed = _execute_delete_cli(tmp_path, arguments, fault)
        assert executed.returncode == 2, executed.stderr
        receipt = json.loads(executed.stdout)
        assert receipt["items"][0]["error"]["code"] == "identity_changed"
        assert not any(item["status"] == "deleted" for item in receipt["items"])
        assert all((data / "readings" / f"{index}.parquet").exists() for index in range(3))



    def test_installed_delete_plan_round_trips_chinese_root_through_cp936_stdout(self, data_store_installation, tmp_path):
        store, data, plan_path, receipt_path, arguments = _delete_fixture(tmp_path / "中文资料", data_store_installation)
        planned = subprocess.run([sys.executable, *arguments[:3], "delete-plan", "--targets",
                                  '{"readings":["0","1","2"]}'],
                                 capture_output=True, cwd=tmp_path,
                                 env={**os.environ, "PYTHONIOENCODING": "cp936"})
        assert planned.returncode == 0, planned.stderr
        # Preserve the exact bytes a shell pipeline/redirection would save.
        plan_path.write_bytes(planned.stdout)
        arguments[arguments.index("--approve") + 1] = json.loads(planned.stdout.decode("cp936"))["plan_id"]
        executed = _execute_delete_cli(tmp_path, arguments)
        assert executed.returncode == 0, executed.stderr
        assert json.loads(executed.stdout)["state"] == "complete"
        assert all(value < 128 for value in planned.stdout)



    @pytest.mark.skipif(os.name == "nt", reason="Linux project entry; Windows uses its existing setup recipe")
    def test_public_bootstrap_binding_serves_real_installed_data_commands(self, data_store_installation, tmp_path):
        from tests.integration.test_project_environment import prepared_bootstrap_project, invoke

        root, project, skill, arguments = prepared_bootstrap_project(tmp_path, installed_source=data_store_installation)
        for _ in range(2):
            result = subprocess.run(arguments, text=True, capture_output=True)
            assert result.returncode == 0, result.stderr
            checked = invoke(root / "skills/data-store", project, "check")
            assert checked.returncode == 0, checked.stderr
            assert Path(json.loads(checked.stdout)["target"]) == skill.resolve()
        script = project / ".local/skills/data-store/scripts/data_store.py"
        data = project / "data"
        written = subprocess.run([sys.executable, str(script), "--root", str(data),
                                  "write", "readings", "one"], input='[{"value":7}]',
                                 text=True, capture_output=True)
        assert written.returncode == 0, written.stderr
        queried = subprocess.run([sys.executable, str(script), "--root", str(data),
                                  "query", "SELECT value FROM readings", "--tables", '["readings"]'],
                                 text=True, capture_output=True)
        assert queried.returncode == 0, queried.stderr
        assert json.loads(queried.stdout) == {"value": 7}
