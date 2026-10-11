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


def load_store():
    spec = importlib.util.spec_from_file_location("data_store", SKILL / "scripts/data_store.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
