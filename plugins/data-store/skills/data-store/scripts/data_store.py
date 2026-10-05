"""One project data root, typed Parquet writes, and logical-table queries."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time


def _duckdb():
    try:
        import duckdb
    except ImportError as error:
        raise RuntimeError("缺少 DuckDB，请使用技能 requirements.txt 准备当前 Python 环境") from error
    return duckdb


def _name(value, *, table=False):
    pattern = r"[A-Za-z_][A-Za-z0-9_]{0,127}" if table else r"[A-Za-z0-9_][A-Za-z0-9_-]{0,127}"
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError("逻辑表名或记录键无效；不可使用路径")
    return value.lower()


def _opaque(structure):
    if isinstance(structure, str):
        return structure == "JSON"
    return any(_opaque(value) for value in (structure.values() if isinstance(structure, dict) else structure))


def write(root, table, key, rows, *, schema=None):
    """Replace one complete logical key. Optional schema uses DuckDB field types."""
    root = Path(root).resolve()
    directory = root / _name(table, table=True)
    key = _name(key)
    if directory.resolve().parent != root:
        raise ValueError("逻辑表目录不能跳出数据根目录")
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) or not row for row in rows):
        raise ValueError("rows 必须是非空记录列表")
    if schema is not None and (not isinstance(schema, dict) or not schema
                               or any(set(row) - set(schema) for row in rows)):
        raise ValueError("记录包含未声明字段，或字段类型定义无效")
    payload = json.dumps(rows, ensure_ascii=False, allow_nan=False)
    with _duckdb().connect(":memory:") as connection:
        structure = (json.dumps([schema]) if schema is not None else
                     connection.execute("SELECT json_structure(?)", [payload]).fetchone()[0])
        if schema is None and _opaque(json.loads(structure)):
            raise ValueError("无法推断有类型的记录，请明确提供字段类型；不回退为不透明 JSON")
        records = connection.sql(
            "SELECT record.* FROM (SELECT unnest(from_json_strict(?, ?)) AS record)",
            params=[payload, structure],
        )
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".write-", dir=directory) as temporary:
            source = Path(temporary) / "data.parquet"
            records.write_parquet(str(source), compression="zstd")
            # Reuse Quant-Research-Lab's bounded Windows publication retry.
            for delay in (0.02, 0.05, 0.1, 0.2, 0.4):
                try:
                    os.replace(source, directory / f"{key}.parquet")
                    break
                except PermissionError:
                    if not source.exists():
                        raise
                    time.sleep(delay)
            else:
                os.replace(source, directory / f"{key}.parquet")
    return len(rows)


def query(root, sql, parameters=None):
    """Return a DuckDB cursor. Consume with fetchmany(n), then close it."""
    root = Path(root).resolve(strict=True)
    duckdb = _duckdb()
    connection = duckdb.connect(":memory:", config={
        "autoinstall_known_extensions": False, "autoload_known_extensions": False,
    })
    try:
        connection.execute("SET allowed_directories = ?", [[str(root) + os.sep]])
        connection.execute("SET enable_external_access = false")
        for directory in sorted(root.iterdir()):
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            table = _name(directory.name, table=True)
            if directory.resolve().parent != root:
                raise ValueError("逻辑表目录不能跳出数据根目录")
            files = sorted(directory.glob("*.parquet"))
            if any(path.is_symlink() for path in files):
                raise ValueError("数据分片不能是符号链接")
            if files:
                connection.read_parquet([str(path) for path in files], union_by_name=True).create_view(table)
        statements = connection.extract_statements(sql)
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise ValueError("query 只接受一条只读 SELECT 查询")
        connection.execute("SET lock_configuration = true")
        return connection.execute(sql, parameters if parameters is not None else [])
    except BaseException:
        connection.close()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Parquet/Zstd 写入与 DuckDB 逻辑表查询")
    parser.add_argument("--root", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    writer = commands.add_parser("write")
    writer.add_argument("table")
    writer.add_argument("key")
    writer.add_argument("--schema", type=json.loads)
    reader = commands.add_parser("query")
    reader.add_argument("sql")
    reader.add_argument("--parameters", type=json.loads, default=[])
    reader.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        if args.command == "write":
            count = write(args.root, args.table, args.key, json.load(sys.stdin), schema=args.schema)
            print(json.dumps({"rows": count}))
        else:
            if args.batch_size < 1:
                raise ValueError("batch-size 必须大于零")
            with query(args.root, args.sql, args.parameters) as cursor:
                names = [column[0] for column in cursor.description]
                while rows := cursor.fetchmany(args.batch_size):
                    for row in rows:
                        print(json.dumps(dict(zip(names, row)), ensure_ascii=False, default=str))
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
