"""One project data root, typed Parquet writes, and logical-table queries."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import uuid


DATA_STORE_API_VERSION = 2
DATA_STORE_CAPABILITIES = frozenset({"binary-write-v1", "exact-delete-v1"})


# Only tuning decisions survive a call, never connections, schemas or row data.
_READ_CHOICES = {}


def _parameter_key(value):
    if type(value) in (type(None), bool, int, float, str):
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


def _binary_records(connection, rows, schema):
    """Bind each row's metadata and opaque bytes together, without an order-based join."""
    if (not isinstance(schema, dict) or not schema
            or any(not isinstance(field, str) or not field or "\x00" in field for field in schema)
            or len({field.lower() for field in schema}) != len(schema)
            or any(set(row) != set(schema) for row in rows)):
        raise ValueError("原生二进制写入必须提供非空、无冲突的字段类型，并逐行完整匹配字段")
    blobs = [field for field, kind in schema.items()
             if isinstance(kind, str) and kind.strip().upper() == "BLOB"]
    metadata = {field: kind for field, kind in schema.items() if field not in blobs}
    parameters = []
    for row in rows:
        if any(row[field] is not None and not isinstance(row[field], bytes) for field in blobs):
            raise TypeError("原生 BLOB 字段只接受 bytes 或 None")
        if metadata:
            parameters.append(json.dumps({field: row[field] for field in metadata},
                                         ensure_ascii=False, allow_nan=False))
        parameters.extend(row[field] for field in blobs)
    columns = (["_json"] if metadata else []) + [f"_blob{index}" for index in range(len(blobs))]
    values = ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
    source = f"(VALUES {values}) AS _input({', '.join(columns)})"
    if metadata:
        source = f"(SELECT from_json_strict(_json, ?) AS _record, * FROM {source})"
        parameters.insert(0, json.dumps(metadata))
    projection = []
    for field in schema:
        name = '"' + field.replace('"', '""') + '"'
        projection.append(f"_blob{blobs.index(field)}::BLOB AS {name}" if field in blobs
                          else f"_record.{name}")
    return connection.sql(f"SELECT {', '.join(projection)} FROM {source}", params=parameters)


def write(root, table, key, rows, *, schema=None, binary=False):
    """Replace one complete key; binary=True requires a schema and native top-level BLOBs."""
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
    payload = None if binary else json.dumps(rows, ensure_ascii=False, allow_nan=False)
    with _duckdb().connect(":memory:") as connection:
        if binary:
            records = _binary_records(connection, rows, schema)
        else:
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
    if directory.resolve() != directory:
        raise ValueError("逻辑表目录不能重定向到其他位置")
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
        connection.execute("SET allowed_paths = ?", [[str(path) for path in paths]])
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


def query(root, sql, parameters=None, *, tables):
    """Query explicitly declared logical tables; consume with fetchmany, then close."""
    if not isinstance(tables, (list, tuple)) or not tables:
        raise ValueError("tables 必须是非空逻辑表名列表")
    tables = list(dict.fromkeys(_name(table, table=True) for table in tables))
    duckdb = _duckdb()
    connection = duckdb.connect(":memory:", config={
        "autoinstall_known_extensions": False, "autoload_known_extensions": False,
    })
    try:
        statements = connection.extract_statements(sql)
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise ValueError("query 只接受一条只读 SELECT 查询")
        root = Path(root).resolve(strict=True)
        groups = []
        for table in tables:
            directory = root / table
            if directory.resolve() != directory:
                raise ValueError("逻辑表目录不能重定向到其他位置")
            files = sorted(directory.glob("*.parquet"))
            if any(path.is_symlink() for path in files):
                raise ValueError("数据分片不能是符号链接")
            if files:
                groups.append((table, files))
        connection.execute("SET allowed_paths = ?", [[str(path) for _, files in groups for path in files]])
        connection.execute("SET enable_external_access = false")
        for table, files in groups:
            _register(connection, table, files)
        _choose_read(connection, root, sql, parameters if parameters is not None else [], groups)
        connection.execute("SET lock_configuration = true")
        return connection.execute(sql, parameters if parameters is not None else [])
    except BaseException:
        connection.close()
        raise


class _DeleteSafetyError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _delete_error(error):
    if isinstance(error, _DeleteSafetyError):
        code = error.code
    elif isinstance(error, FileNotFoundError):
        code = "missing"
    elif isinstance(error, PermissionError):
        code = "permission_or_lock"
    elif isinstance(error, OSError) and error.errno in (errno.EBUSY, errno.ETXTBSY):
        code = "locked"
    elif isinstance(error, OSError):
        code = "storage_error"
    else:
        code = "unexpected_error"
    return {"code": code, "type": type(error).__name__, "message": str(error)}


def _directory_identity(path):
    value = path.stat()
    if not stat.S_ISDIR(value.st_mode):
        raise _DeleteSafetyError("not_directory", "维护目标必须是目录")
    return {"device": value.st_dev, "inode": value.st_ino}


def _delete_root(root):
    root = Path(os.path.abspath(root))
    try:
        if root.resolve(strict=True) != root:
            raise _DeleteSafetyError("redirected", "维护数据根不能通过链接重定向")
        return root, {"path": str(root), **_directory_identity(root)}
    except FileNotFoundError as error:
        raise _DeleteSafetyError("root_unavailable", "维护数据根不可用；不等于记录键缺失") from error


def _delete_file_identity(root, target):
    directory = root / target["table"]
    if directory.resolve() != directory:
        raise _DeleteSafetyError("redirected", "维护逻辑表目录不能重定向")
    parent = _directory_identity(directory)
    path = directory / (target["key"] + ".parquet")
    if path.is_symlink() or path.resolve() != path:
        raise _DeleteSafetyError("redirected", "维护分片不能通过链接重定向")
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise _DeleteSafetyError("not_regular_file", "维护目标必须是普通记录组文件")
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    signature = lambda value: [getattr(value, field) for field in fields]
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = signature(os.fstat(stream.fileno()))
        # Some Windows Python versions expose creation time through path.stat,
        # but ChangeTime through fstat. Compare ctime only within its own source.
        if opened[:-1] != signature(before)[:-1]:
            raise _DeleteSafetyError("identity_changed", "分片在核验前发生变化")
        while block := stream.read(1024 * 1024):
            digest.update(block)
        if (signature(os.fstat(stream.fileno())) != opened
                or signature(path.stat()) != signature(before)):
            raise _DeleteSafetyError("identity_changed", "分片在核验中发生变化")
    return parent, dict(zip(("device", "inode", "size", "mtime_ns", "ctime_ns"), signature(before)),
                        sha256=digest.hexdigest())


def _delete_plan_id(plan):
    payload = {key: value for key, value in plan.items() if key != "plan_id"}
    return "sha256:" + hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def plan_delete(root, targets):
    """Read-only exact-key preview. The caller saves and approves the returned plan."""
    if not isinstance(targets, dict) or not targets:
        raise ValueError("删除目标必须是非空的逻辑表与精确键列表映射")
    normalized = []
    for table, keys in targets.items():
        table = _name(table, table=True)
        if not isinstance(keys, (list, tuple)) or not keys:
            raise ValueError("每个删除目标必须明确提供非空精确键列表")
        normalized.extend((table, _name(key)) for key in keys)
    normalized = list(dict.fromkeys(normalized))
    root, identity = _delete_root(root)
    plan = {"format": "data-store-delete-v1", "nonce": uuid.uuid4().hex,
            "root": identity, "targets": []}
    for table, key in normalized:
        target = {"table": table, "key": key}
        target["directory"], target["file"] = _delete_file_identity(root, target)
        plan["targets"].append(target)
    plan["plan_id"] = _delete_plan_id(plan)
    return plan


def _validate_delete_plan(plan):
    if (not isinstance(plan, dict) or set(plan) != {"format", "nonce", "root", "targets", "plan_id"}
            or plan["format"] != "data-store-delete-v1"
            or not isinstance(plan["nonce"], str) or not plan["nonce"]
            or not isinstance(plan["root"], dict) or set(plan["root"]) != {"path", "device", "inode"}
            or not isinstance(plan["root"]["path"], str)
            or not isinstance(plan["targets"], list) or not plan["targets"]):
        raise ValueError("删除计划格式无效")
    seen = set()
    for target in plan["targets"]:
        if not isinstance(target, dict) or set(target) != {"table", "key", "directory", "file"}:
            raise ValueError("删除计划目标格式无效")
        pair = (_name(target["table"], table=True), _name(target["key"]))
        if pair != (target["table"], target["key"]) or pair in seen:
            raise ValueError("删除计划必须使用规范化且无重复的精确目标")
        seen.add(pair)
        if (not isinstance(target["directory"], dict)
                or set(target["directory"]) != {"device", "inode"}
                or not isinstance(target["file"], dict)
                or set(target["file"]) != {"device", "inode", "size", "mtime_ns", "ctime_ns", "sha256"}):
            raise ValueError("删除计划缺少原文件身份")
    if plan["plan_id"] != _delete_plan_id(plan):
        raise ValueError("删除计划内容与计划身份不符；必须重新预演与授权")


def _sync_delete_directory(path):
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _write_delete_log(path, record, *, create=False):
    """Write one bounded status record (or the initial identity header), then sync."""
    payload = (json.dumps(record, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    flags = os.O_WRONLY | (os.O_CREAT | os.O_EXCL if create else os.O_APPEND)
    descriptor = os.open(path, flags, 0o600)
    try:
        while payload:
            written = os.write(descriptor, payload)
            if written <= 0:
                raise OSError("维护回执写入不完整")
            payload = payload[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_delete_log(path, plan):
    with path.open("rb") as stream:
        line = stream.readline()
        header = json.loads(line)
        if (not line.endswith(b"\n") or not isinstance(header, dict)
                or set(header) != {"format", "plan_id", "atomic", "items"}
                or header["format"] != "data-store-delete-log-v1"
                or header["plan_id"] != plan["plan_id"] or header["atomic"] is not False
                or not isinstance(header["items"], list)
                or len(header["items"]) != len(plan["targets"])):
            raise ValueError("回执头不属于此精确计划，或尚未完整写入；不能覆盖或另作恢复")
        for item, target in zip(header["items"], plan["targets"]):
            if (not isinstance(item, dict) or item != {**target, "status": "not_executed"}):
                raise ValueError("回执头的原身份无效")
        receipt = {**header, "format": "data-store-delete-receipt-v1"}
        # Replay once. A torn/invalid tail is evidence to reconcile, never truncate
        # or silently ignore it and risk repeating an uncertain unlink.
        try:
            for line in stream:
                event = json.loads(line)
                if (not line.endswith(b"\n") or not isinstance(event, dict)
                        or not {"item", "status"} <= set(event)
                        or set(event) - {"item", "status", "error", "unlink_returned"}
                        or type(event["item"]) is not int
                        or not 0 <= event["item"] < len(receipt["items"])
                        or event["status"] not in {"deleted", "failed", "not_executed", "uncertain"}
                        or ("unlink_returned" in event and event["unlink_returned"] is not True)):
                    raise ValueError("逐项回执记录无效或不完整")
                item = receipt["items"][event["item"]]
                if item["status"] == "deleted":
                    raise ValueError("回执不能重新执行已可靠完成项")
                for field in ("error", "unlink_returned"):
                    item.pop(field, None)
                item.update({key: value for key, value in event.items() if key != "item"})
        except Exception as error:
            receipt["error"] = {**_delete_error(error), "code": (
                "receipt_log_read_failed" if isinstance(error, OSError) else "receipt_log_invalid")}
        return receipt


def _finish_delete_receipt(receipt):
    receipt["state"] = ("uncertain" if receipt.get("error") or any(
        item["status"] == "uncertain" for item in receipt["items"])
        else "complete" if all(item["status"] == "deleted" for item in receipt["items"])
        else "incomplete")
    return receipt


def execute_delete(root, plan, *, approve, offline=False, receipt_path):
    """Execute/resume one approved offline plan with a caller-owned durable log."""
    _validate_delete_plan(plan)
    if approve != plan["plan_id"] or offline is not True:
        raise ValueError("必须明确授权精确计划身份，并确认无相关活动读写的离线维护状态")
    root_path = Path(os.path.abspath(root))
    if str(root_path) != plan["root"]["path"]:
        raise ValueError("数据根与已授权计划不符")
    path = Path(os.path.abspath(receipt_path))
    if path == root_path or root_path in path.parents:
        raise ValueError("维护回执须由调用项目保存在业务数据根之外")
    if path.resolve() != path or not path.parent.is_dir():
        raise ValueError("维护回执路径不能重定向，且父目录必须已存在")
    receipt = {"format": "data-store-delete-receipt-v1", "plan_id": plan["plan_id"],
               "atomic": False, "items": [{**target, "status": "not_executed"}
                                          for target in plan["targets"]]}
    try:
        _write_delete_log(path, {**receipt, "format": "data-store-delete-log-v1"}, create=True)
    except FileExistsError:
        receipt = _read_delete_log(path, plan)
    if _finish_delete_receipt(receipt)["state"] == "uncertain":
        return receipt
    # Also sync an existing log's directory: a previous attempt may have created
    # and fsynced its header, then failed before this directory entry was durable.
    _sync_delete_directory(path.parent)

    def check(target):
        actual_root, identity = _delete_root(root_path)
        if identity != plan["root"]:
            raise _DeleteSafetyError("root_identity_changed", "数据根身份已变化")
        directory, file = _delete_file_identity(actual_root, target)
        if directory != target["directory"] or file != target["file"]:
            raise _DeleteSafetyError("identity_changed", "目标目录或分片身份已变化；旧计划不能授权新文件")

    def persist(index, item):
        event = {"item": index, **{key: item[key] for key in
                 ("status", "error", "unlink_returned") if key in item}}
        try:
            _write_delete_log(path, event)
        except Exception as error:
            item.update(status="uncertain", error={**_delete_error(error), "code": "receipt_write_failed"})
            return False
        return True

    # Full preflight of every unfinished target, with no business-data mutation.
    for index, item in enumerate(receipt["items"]):
        if item["status"] == "deleted":
            continue
        previous = (item["status"], item.get("error"))
        item["status"] = "not_executed"
        item.pop("error", None)
        try:
            check(item)
        except Exception as error:
            item.update(status="failed", error=_delete_error(error))
        if previous != (item["status"], item.get("error")) and not persist(index, item):
            return _finish_delete_receipt(receipt)
    if any(item["status"] == "failed" for item in receipt["items"]):
        return _finish_delete_receipt(receipt)
    for index, item in enumerate(receipt["items"]):
        if item["status"] == "deleted":
            continue
        # A crash from this durable intent until the result is durable is uncertain.
        item["status"] = "uncertain"
        if not persist(index, item):
            return _finish_delete_receipt(receipt)
        try:
            check(item)
        except Exception as error:
            item.update(status="failed", error=_delete_error(error))
            persist(index, item)
            return _finish_delete_receipt(receipt)
        try:
            target = root_path / item["table"] / (item["key"] + ".parquet")
            target.unlink()
            item["unlink_returned"] = True
            _sync_delete_directory(target.parent)
        except Exception as error:
            item["error"] = _delete_error(error)
            # Only definite unlink failures are retryable; a later directory sync
            # failure or unknown unlink outcome must retain the durable intent.
            if not item.get("unlink_returned") and (isinstance(error, PermissionError) or (
                    isinstance(error, OSError) and error.errno in (errno.EBUSY, errno.ETXTBSY, errno.EROFS))):
                item["status"] = "failed"
        else:
            item["status"] = "deleted"
        if not persist(index, item) or item["status"] != "deleted":
            return _finish_delete_receipt(receipt)
    return _finish_delete_receipt(receipt)


_CLI_BLOB_ERROR = "命令行不能直接输出 BLOB；请选择元数据字段，或在查询中显式编码"


def _contains_blob(kind):
    return kind.id == "blob" or (kind.id in {"list", "array", "map", "struct", "union"}
                                 and any(_contains_blob(child) for _, child in kind.children
                                         if isinstance(child, type(kind))))


def _cli_json_value(value):
    if isinstance(value, bytes):
        raise ValueError(_CLI_BLOB_ERROR)
    return str(value)


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
    reader.add_argument("--tables", type=json.loads, required=True)
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
    planner = commands.add_parser("delete-plan", help="只读预演逻辑表与精确记录键")
    planner.add_argument("--targets", type=json.loads, required=True)
    executor = commands.add_parser("delete-execute", help="执行或沿同一回执恢复精确离线计划")
    executor.add_argument("--plan", type=Path, required=True)
    executor.add_argument("--approve", required=True)
    executor.add_argument("--offline", action="store_true")
    executor.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "delete-plan":
            print(json.dumps(plan_delete(args.root, args.targets), ensure_ascii=True))
        elif args.command == "delete-execute":
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
            receipt = execute_delete(args.root, plan, approve=args.approve, offline=args.offline,
                                     receipt_path=args.receipt)
            print(json.dumps(receipt, ensure_ascii=False))
            return 0 if receipt["state"] == "complete" else 2
        elif args.command == "write":
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
                cursor = query(args.root, args.sql, args.parameters, tables=args.tables)
            with cursor:
                if any(_contains_blob(column[1]) for column in cursor.description):
                    raise ValueError(_CLI_BLOB_ERROR)
                names = [column[0] for column in cursor.description]
                while rows := cursor.fetchmany(args.batch_size):
                    for row in rows:
                        print(json.dumps(dict(zip(names, row)), ensure_ascii=False, default=_cli_json_value))
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
