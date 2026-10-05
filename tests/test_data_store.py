"""Public write/query contract; the isolated CLI test is the release-shape smoke."""

import json
import importlib.util
import builtins
from pathlib import Path
import shutil
import subprocess
import sys

import duckdb
import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/data-store/skills/data-store"


def load_store():
    spec = importlib.util.spec_from_file_location("data_store", SKILL / "scripts/data_store.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
         "--parameters", "[1]", "--batch-size", "1"],
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


def test_typed_replacement_is_atomic_and_query_is_read_only(tmp_path):
    store = load_store()
    root = tmp_path / "data"
    store.write(root, "custom", "one", [{"amount": "12.50", "valid": True}],
                schema={"amount": "DECIMAL(12,2)", "valid": "BOOLEAN"})
    with pytest.raises(duckdb.Error):
        store.write(root, "custom", "one", [{"amount": "bad", "valid": True}],
                    schema={"amount": "DECIMAL(12,2)", "valid": "BOOLEAN"})
    with store.query(root, "SELECT amount::VARCHAR, valid FROM custom") as cursor:
        assert cursor.fetchmany(1) == [("12.50", True)]
        assert cursor.fetchmany(1) == []
    with pytest.raises(ValueError, match="只读"):
        store.query(root, "COPY custom TO 'copy.csv'")
    with pytest.raises(ValueError, match="只读"):
        store.query(root, "SELECT * FROM custom; DELETE FROM custom")
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
    with store.query(tmp_path, "SELECT payload FROM custom") as cursor:
        assert cursor.fetchone() == ({},)
    store.write(tmp_path, "measurements", "one", [{"score": 5, "metadata": {"label": "a"}}],
                schema={"score": "DOUBLE", "metadata": "JSON"})
    with store.query(tmp_path, "SELECT score, metadata->>'label' FROM measurements") as cursor:
        assert cursor.fetchone() == (5.0, "a")


def test_logical_names_share_duckdb_case_rules(tmp_path):
    store = load_store()
    store.write(tmp_path, "Readings", "First", [{"score": 1}])
    store.write(tmp_path, "readings", "second", [{"score": 2}])
    store.write(tmp_path, "READINGS", "FIRST", [{"score": 3}])
    with store.query(tmp_path, "SELECT score FROM Readings ORDER BY score") as cursor:
        assert cursor.fetchall() == [(2,), (3,)]


def test_cli_reports_missing_dependency(tmp_path, monkeypatch, capsys):
    store = load_store()
    original = builtins.__import__

    def without_duckdb(name, *args, **kwargs):
        if name == "duckdb":
            raise ImportError("missing")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_duckdb)
    assert store.main(["--root", str(tmp_path), "query", "SELECT 1"]) == 2
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
