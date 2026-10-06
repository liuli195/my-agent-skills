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


# Only tuning decisions survive a call, never connections, schemas or row data.
_READ_CHOICES = {}


def _parameter_key(value):
    if type(value) in (type(None), bool, int, float, str, bytes):
        return (type(value).__name__, value)
    if type(value) in (list, tuple):
        return (type(value).__name__, tuple(_parameter_key(item) for item in value))
    if type(value) is dict and all(type(key) is str for key in value):
        return ("dict", tuple(sorted((key, _parameter_key(item)) for key, item in value.items())))
    raise TypeError("参数类型不适合缓存配置")


def _files_identity(paths):
    identity = []
    for path in paths:
        stat = path.stat()
        identity.append((str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino))
    return tuple(identity)


def _register(connection, table, paths):
    literal = "[" + ",".join("'" + str(path).replace("'", "''") + "'" for path in paths) + "]"
    name = '"' + table.replace('"', '""') + '"'
    connection.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet({literal}, union_by_name=true)")


def _choose_read(connection, root, sql, parameters, groups):
    """A conservative heuristic: estimated small scans of unambiguous nested columns."""
    try:
        key = (str(root), sql, _parameter_key(parameters),
               _files_identity(path for _, paths in groups for path in paths))
    except TypeError:
        key = None  # Other valid DuckDB parameter types still work without memoization.
    decision = _READ_CHOICES.get(key) if key is not None else None
    if decision is None:
        try:
            parsed = json.loads(connection.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()[0])
            if parsed.get("error"):
                return
            sources = set()
            aliases = set()
            pending = [parsed]
            while pending:
                item = pending.pop()
                if isinstance(item, dict):
                    if item.get("type") == "TABLE_FUNCTION":
                        return  # Direct file/table functions are not registered logical sources.
                    if item.get("type") == "BASE_TABLE":
                        if item.get("catalog_name") or item.get("schema_name") not in ("", "main"):
                            return
                        sources.add(item["table_name"].lower())
                    aliases.update(entry["key"].lower() for entry in item.get("cte_map", {}).get("map", []))
                    pending.extend(item.values())
                elif isinstance(item, list):
                    pending.extend(item)
        except (ValueError, _duckdb().Error):
            return
        if aliases & {table for table, _ in groups}:
            return  # Shadowed logical names require scope resolution; keep the default.
        sources -= aliases
        if not sources or not sources <= {table for table, _ in groups}:
            return
        types = {}
        for table, _ in groups:
            if table not in sources:
                continue
            name = '"' + table.replace('"', '""') + '"'
            for column in connection.execute(f"DESCRIBE {name}").fetchall():
                types.setdefault(column[0].lower(), []).append(column[1])
        try:
            plan = json.loads(connection.execute("EXPLAIN (FORMAT JSON) " + sql, parameters).fetchone()[1])
        except (ValueError, _duckdb().Error):
            return  # Tuning is optional; execute the original query with its normal errors.

        def small_complex(nodes):
            pending = list(nodes)
            complex_projection = False
            while pending:
                node = pending.pop()
                name = node.get("name", "").strip()
                info = node.get("extra_info", {})
                if name in ("READ_PARQUET", "PARQUET_SCAN"):
                    try:
                        small = 0 <= int(info.get("Estimated Cardinality", -1)) <= 512
                    except (ValueError, TypeError):
                        small = False
                    if not small:
                        return False  # A small nested side must not serialize a large join.
                    columns = info.get("Projections", [])
                    if isinstance(columns, str):
                        columns = [columns]
                    for column in columns:
                        # A dotted real field and a nested path can coincide. Do not guess.
                        candidates = [values for name, values in types.items()
                                      if column.lower() == name or column.lower().startswith(name + ".")]
                        if small and len(candidates) == 1 and len(candidates[0]) == 1:
                            if any(marker in candidates[0][0] for marker in ("STRUCT(", "[]", "MAP(")):
                                complex_projection = True
                        elif any(marker in value for values in candidates for value in values
                                 for marker in ("STRUCT(", "[]", "MAP(")):
                            return False
                elif "SCAN" in name or info.get("Function"):
                    return False  # Unknown source sizes and table functions keep the default.
                pending.extend(node.get("children", []))
            return complex_projection

        decision = small_complex(plan)
        if key is not None:
            if len(_READ_CHOICES) >= 128:
                _READ_CHOICES.pop(next(iter(_READ_CHOICES), None), None)
            _READ_CHOICES[key] = decision
    if decision:
        connection.execute("SET threads = 1")


class CorruptDataError(ValueError):
    """The selected stored record group has an invalid Parquet envelope."""


class MissingKeyError(FileNotFoundError):
    """The data root exists, but the selected logical record group is absent."""


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
        transform = "from_json_strict" if schema is not None else "from_json"
        records = connection.sql(
            f"SELECT record.* FROM (SELECT unnest({transform}(?, ?)) AS record)",
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


def _check_key(path):
    if path.is_symlink():
        raise ValueError("数据分片不能是符号链接")
    # Check only this file's envelope, not a hash or a second full report read.
    # OS errors stay OS errors; DuckDB uses IOException for both these and corruption.
    try:
        stream = path.open("rb")
    except FileNotFoundError as error:
        raise MissingKeyError("目标记录键不存在") from error
    with stream:
        header = stream.read(4)
        size = stream.seek(0, os.SEEK_END)
        if size < 12 or header != b"PAR1":
            raise CorruptDataError("目标数据分片不是完整 Parquet 文件")
        stream.seek(-8, os.SEEK_END)
        footer = stream.read(8)
        if footer[4:] != b"PAR1" or int.from_bytes(footer[:4], "little") > size - 12:
            raise CorruptDataError("目标数据分片的 Parquet 页脚损坏")


def read_key(root, table, key, *, columns=None, filters=None):
    """Read the complete record group written under one logical key."""
    return read_keys(root, table, [key], columns=columns, filters=filters)


def read_keys(root, table, keys, *, columns=None, filters=None):
    """Read selected logical keys once, optionally projecting top-level columns."""
    root = Path(root).resolve(strict=True)
    directory = root / _name(table, table=True)
    if directory.resolve().parent != root:
        raise ValueError("逻辑表目录不能跳出数据根目录")
    if not isinstance(keys, (list, tuple)) or not keys:
        raise ValueError("记录键必须是非空列表")
    paths = [directory / f"{key}.parquet" for key in dict.fromkeys(_name(key) for key in keys)]
    projection = "*"
    if columns is not None:
        if (not isinstance(columns, (list, tuple)) or not columns
                or any(not isinstance(column, str) or not column or "\x00" in column for column in columns)
                or len({column.lower() for column in columns}) != len(columns)):
            raise ValueError("字段必须是非空、无重复的顶层字段名列表")
        projection = ", ".join('_records."' + column.replace('"', '""') + '"' for column in columns)
    parameters = []
    predicate = ""
    if filters is not None:
        if (not isinstance(filters, dict) or not filters
                or any(not isinstance(field, str) or not field or "\x00" in field for field in filters)
                or len({field.lower() for field in filters}) != len(filters)
                or any(value is not None and not isinstance(value, (str, int, float, bool))
                       for value in filters.values())):
            raise ValueError("筛选必须是非空、无重复的顶层字段与单个值的映射")
        predicate = " WHERE " + " AND ".join(
            '_records."' + field.replace('"', '""') + '" IS NOT DISTINCT FROM ?'
            for field in filters)
        parameters = list(filters.values())
    for path in paths:
        _check_key(path)
    connection = _duckdb().connect(":memory:", config={
        "autoinstall_known_extensions": False, "autoload_known_extensions": False,
    })
    try:
        connection.execute("SET allowed_directories = ?", [[str(root) + os.sep]])
        connection.execute("SET enable_external_access = false")
        if len(paths) == 1 and filters is None:
            # Single-file reads already perform well; avoid planning/setup overhead.
            connection.execute("SET lock_configuration = true")
            return connection.execute(f"SELECT {projection} FROM read_parquet(?) AS _records", [str(paths[0])])
        _register(connection, "_records", paths)
        sql = f"SELECT {projection} FROM _records{predicate}"
        _choose_read(connection, root, sql, parameters, [("_records", paths)])
        connection.execute("SET lock_configuration = true")
        return connection.execute(sql, parameters)
    except BaseException:
        connection.close()
        raise


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
        groups = []
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
                _register(connection, table, files)
                groups.append((table, files))
        statements = connection.extract_statements(sql)
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise ValueError("query 只接受一条只读 SELECT 查询")
        _choose_read(connection, root, sql, parameters if parameters is not None else [], groups)
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
    point_reader = commands.add_parser("read-key")
    point_reader.add_argument("table")
    point_reader.add_argument("key")
    point_reader.add_argument("--columns", type=json.loads)
    point_reader.add_argument("--filters", type=json.loads)
    point_reader.add_argument("--batch-size", type=int, default=1000)
    batch_reader = commands.add_parser("read-keys")
    batch_reader.add_argument("table")
    batch_reader.add_argument("keys", nargs="+")
    batch_reader.add_argument("--columns", type=json.loads)
    batch_reader.add_argument("--filters", type=json.loads)
    batch_reader.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        if args.command == "write":
            count = write(args.root, args.table, args.key, json.load(sys.stdin), schema=args.schema)
            print(json.dumps({"rows": count}))
        else:
            if args.batch_size < 1:
                raise ValueError("batch-size 必须大于零")
            if args.command == "read-key":
                cursor = read_key(args.root, args.table, args.key, columns=args.columns, filters=args.filters)
            elif args.command == "read-keys":
                cursor = read_keys(args.root, args.table, args.keys, columns=args.columns, filters=args.filters)
            else:
                cursor = query(args.root, args.sql, args.parameters)
            with cursor:
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
