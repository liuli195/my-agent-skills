"""One installed data-store smoke: typed reads, native isolation and deletion."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins/data-store/skills/data-store"


class TestDataStore:
    def test_installed_data_store_smoke(self, tmp_path):
        import duckdb

        installed = tmp_path / "installed/data-store"
        shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
        project = tmp_path / "project"
        project.mkdir()
        binding_script = installed / "scripts/project_binding.py"
        def binding(*arguments):
            return subprocess.run([sys.executable, str(binding_script), *map(str, arguments)],
                                  text=True, capture_output=True, cwd=tmp_path)
        connected = binding("connect", "--project", project)
        assert connected.returncode == 0, connected.stdout + connected.stderr
        stable = binding("resolve", "--project", project)
        explicit = binding("resolve", "--runtime", installed)
        assert stable.returncode == explicit.returncode == 0, stable.stderr + explicit.stderr
        assert json.loads(stable.stdout) == json.loads(explicit.stdout)
        failed = binding("resolve", "--runtime", tmp_path / "missing-runtime")
        assert failed.returncode != 0
        assert (project / ".local/skills/data-store").resolve() == installed.resolve()
        # CLI writes use the stable choice; the loaded read interface uses the explicit choice.
        script = Path(json.loads(stable.stdout)["script"])
        spec = importlib.util.spec_from_file_location("installed_data_store", json.loads(explicit.stdout)["script"])
        store = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(store)
        data = tmp_path / "data"

        def cli(*arguments, rows=None):
            result = subprocess.run(
                [sys.executable, str(script), "--root", str(data), *map(str, arguments)],
                input=None if rows is None else json.dumps(rows),
                text=True, capture_output=True, cwd=tmp_path,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            return [json.loads(line) for line in result.stdout.splitlines()]

        rows = [{"label": "001", "score": 1.25, "parts": [{"amount": 4}]}]
        assert cli("write", "measurements", "first", rows=rows) == [{"rows": 1}]
        assert cli("write", "measurements", "second", rows=[
            {"label": "002", "score": 2.5, "parts": [{"amount": 8}]},
        ]) == [{"rows": 1}]
        assert cli("query", "SELECT label, parts[1].amount AS amount FROM measurements "
                   "WHERE score > ? ORDER BY label", "--tables", '["measurements"]',
                   "--parameters", "[1]", "--batch-size", "1") == [
            {"label": "001", "amount": 4}, {"label": "002", "amount": 8},
        ]
        assert cli("read-key", "Measurements", "FIRST", "--batch-size", "1") == rows
        with store.read_key(data, "measurements", "first") as cursor:
            assert cursor.fetchone()[:2] == ("001", 1.25)
        assert cli("read-keys", "measurements", "first", "second", "first",
                   "--columns", '["label"]', "--filters", '{"label":"002"}',
                   "--batch-size", "1") == [{"label": "002"}]

        assert store.write(data, "binary", "one", [{"payload": b"\x00\xff\x80"}],
                           schema={"payload": "BLOB"}, binary=True) == 1
        with store.read_key(data, "binary", "one") as cursor:
            assert cursor.fetchall() == [(b"\x00\xff\x80",)]
            with pytest.raises(duckdb.PermissionException):
                cursor.execute("SELECT * FROM read_parquet(?)",
                               [str(data / "measurements/first.parquet")])

        plan = cli("delete-plan", "--targets", '{"Measurements":["FIRST","second","first"]}')[0]
        assert [item["key"] for item in plan["targets"]] == ["first", "second"]
        first = data / "measurements/first.parquet"
        assert first.is_file()  # Preview did not mutate storage.
        plan_path, receipt_path = tmp_path / "plan.json", tmp_path / "receipt.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        arguments = ("delete-execute", "--plan", plan_path, "--approve", plan["plan_id"],
                     "--offline", "--receipt", receipt_path)
        receipt = cli(*arguments)[0]
        assert receipt["state"] == "complete" and receipt["atomic"] is False
        assert [item["status"] for item in receipt["items"]] == ["deleted", "deleted"]
        assert not first.exists() and not (data / "measurements/second.parquet").exists()
        records = [json.loads(line) for line in receipt_path.read_text().splitlines()]
        assert records[0]["plan_id"] == plan["plan_id"]
        assert [(record["item"], record["status"]) for record in records[1:]] == [
            (0, "uncertain"), (0, "deleted"), (1, "uncertain"), (1, "deleted"),
        ]
        first.write_bytes(b"new file created after the completed deletion")
        assert cli(*arguments)[0]["state"] == "complete"
        assert first.read_bytes() == b"new file created after the completed deletion"
        assert (data / "binary/one.parquet").is_file()
