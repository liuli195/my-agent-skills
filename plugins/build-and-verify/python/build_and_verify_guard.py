"""Python test adapter, not a security sandbox for hostile/native code.

PYTEST_DONT_REWRITE. Only the verification runner launches this file. Audit hooks are process-wide,
including threads; evidence is independent of the test's exception handling.
"""
from __future__ import annotations

import sys

# -S prevents site/.pth/project hooks before protection. Import our standard
# library dependencies without consulting project/PYTHONPATH entries first.
_startup_path = sys.path[:]
if __name__ == "__main__":
    sys.path[:] = [p for p in sys.path if p.startswith(sys.base_prefix + "/")
                   or p.startswith(sys.base_prefix + "\\")]

import atexit
import itertools
import json
import os
import platform
from pathlib import Path
import re
import runpy
import shlex
import threading
import time


ADAPTER_VERSION = "python-audit-v2+node-preload-v2"


def protected_command(command, evidence: Path):
    """Adapt known runtime segments only; unknown wrappers never run unguarded."""
    guard = str(Path(__file__).resolve())
    if isinstance(command, list):
        return _runtime_command(command, guard, str(evidence), "0"), 1
    # This is deliberately not a shell interpreter: only success chaining and
    # environment assignments are accepted. All other shell syntax fails closed.
    if "$(" in command or "`" in command:
        raise ValueError("runtime_guard_uncovered_command: shell substitution")
    segments = []
    cursor = 0
    quote = None
    start = 0
    while cursor < len(command):
        char = command[cursor]
        if char in "\"'":
            quote = None if quote == char else (char if quote is None else quote)
        elif quote is None:
            if command[cursor:cursor + 2] == "&&":
                segments.append(command[start:cursor])
                cursor += 2
                start = cursor
                continue
            if char in ";|<>`\n&":
                raise ValueError("runtime_guard_uncovered_command: unsupported shell syntax")
        cursor += 1
    if quote is not None:
        raise ValueError("runtime_guard_uncovered_command: unclosed quote")
    segments.append(command[start:])
    adapted = []
    count = 0
    for segment in segments:
        raw = segment.strip()
        if re.fullmatch(r"set\s+[A-Za-z_][A-Za-z0-9_]*=.*", raw, re.I):
            adapted.append(segment)
            continue
        prefix = re.match(r"(?:[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|[^\s]+)\s+)*", raw).group()
        rest = raw[len(prefix):]
        # Locate just the executable, leaving every test argument byte-for-byte.
        match = re.match(r'''("[^"]*"|'[^']*'|[^\s]+)(.*)''', rest, re.S)
        if match is None:
            raise ValueError("runtime_guard_uncovered_command: missing executable")
        executable = match[1].strip("\"'")
        launch = _runtime_command([executable], guard, str(evidence), str(count))
        encoded = __import__("subprocess").list2cmdline(launch) if os.name == "nt" else shlex.join(launch)
        adapted.append(prefix + encoded + match[2])
        count += 1
    if not count:
        raise ValueError("runtime_guard_uncovered_command: no protected test segment")
    # In cmd.exe a space before && becomes part of an unquoted `set` value.
    return "&&".join(adapted), count


def _runtime_command(tokens, guard, evidence, segment):
    executable = str(tokens[0])
    name = executable.replace("\\", "/").rsplit("/", 1)[-1]
    if re.fullmatch(r"node(?:\.exe)?", name, re.I):
        return [sys.executable, "-S", "-B", guard, evidence, segment, platform.platform(), "--node", *tokens]
    if not re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?", name, re.I):
        raise ValueError(f"runtime_guard_uncovered_command: {executable}; Python or Node adapter required")
    return [executable, "-S", "-B", guard, evidence, segment, platform.platform(), *tokens[1:]]


def _run_node(evidence, segment, args):
    # NODE_OPTIONS preloads precede command-line preloads. Put protection first,
    # retaining the user's options and the native command/argument semantics.
    import subprocess
    preload = Path(__file__).resolve().parent.parent / "bin/build-and-verify-node-guard.cjs"
    env = {**os.environ, "BUILD_AND_VERIFY_GUARD_EVIDENCE": evidence,
           "BUILD_AND_VERIFY_GUARD_SEGMENT": segment}
    env["NODE_OPTIONS"] = "--require=" + json.dumps(str(preload), ensure_ascii=False) + " " + env.get("NODE_OPTIONS", "")
    return subprocess.call(args, env=env)


def _evidence_records(path: Path):
    files = sorted(path.parent.glob(path.name + ".unit-*.jsonl"))
    if not files:
        raise FileNotFoundError(path)
    return [json.loads(line) for file in files for line in file.read_text(encoding="utf-8").splitlines()]


def evidence_error(path: Path, segments: int) -> str | None:
    try:
        records = _evidence_records(path)
    except (OSError, ValueError):
        return "runtime_guard_evidence_missing"
    if not all(isinstance(item, dict) and isinstance(item.get("pid"), int)
            and isinstance(item.get("time"), (int, float))
            and ("unit" not in item or isinstance(item["unit"], str))
            and ("childUnit" not in item or isinstance(item["childUnit"], str))
            and item.get("event") in {"start", "finish", "worker", "violation"}
            and (item.get("event") != "worker" or isinstance(item.get("child"), int))
            and (item.get("event") != "violation" or isinstance(item.get("operation"), str))
            for item in records):
        return "runtime_guard_evidence_incomplete"
    violations = [item for item in records if item.get("event") == "violation"]
    errors = []
    if violations:
        errors.append("runtime_guard_violation: " + ", ".join(sorted({item["operation"] + " " + item.get("target", "") for item in violations})))
    started = {item.get("unit", str(item["pid"])) for item in records if item.get("event") == "start"}
    finished = {item.get("unit", str(item["pid"])) for item in records if item.get("event") == "finish"}
    workers = {item.get("childUnit", str(item["child"])) for item in records if item.get("event") == "worker"}
    worker_starts = {item.get("unit", str(item["pid"])) for item in records
                     if item.get("event") == "start" and item.get("role") == "worker"}
    roots = {item.get("segment") for item in records if item.get("event") == "start" and item.get("role") == "root"}
    if not started or started != finished or workers != worker_starts or roots != {str(i) for i in range(segments)}:
        errors.append(f"runtime_guard_evidence_incomplete: starts={len(started)} finishes={len(finished)} "
                      f"workers={len(workers)} worker_starts={len(worker_starts)} roots={len(roots)}/{segments}")
    return "; ".join(errors) if errors else None


def evidence_summary(path: Path):
    records = _evidence_records(path)
    return {"adapter": ADAPTER_VERSION,
        "workers": len({item.get("unit", str(item["pid"])) for item in records if item.get("event") == "start" and item.get("role") == "worker"}),
        "started": min(item["time"] for item in records), "finished": max(item["time"] for item in records)}


def _write_evidence(write, fd, data):
    while data:
        written = write(fd, data)
        if written <= 0:
            raise OSError("runtime_guard_evidence_write_failed")
        data = data[written:]


def _run(evidence: str, segment: str, platform_info: str, args: list[str]) -> int:
    # Each process owns its evidence file; Windows append is not interprocess-atomic.
    # No project code has run yet. Do not expose a general pause/allow switch.
    pid = os.getpid()
    fd = os.open(f"{evidence}.unit-{segment}-python-{pid}.jsonl",
                 os.O_APPEND | os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    write = os.write
    write_evidence = _write_evidence
    role = "worker" if len(args) == 2 and args[0] == "--worker" else "root"
    # Windows venv launchers and their interpreter children have different PIDs.
    unit = args[1] if role == "worker" else str(pid)
    violated = False
    record_lock = threading.Lock()
    def record(event, **fields):
        nonlocal violated
        data = (json.dumps({"event": event, "pid": pid, "unit": unit, "time": time.monotonic(), **fields}) + "\n").encode()
        with record_lock:
            violated = violated or event == "violation"
            write_evidence(write, fd, data)
    record("start", role=role, segment=segment, adapter=ADAPTER_VERSION)
    def finish():
        record("finish")
        os.close(fd)
        if violated:
            # The shell must not start a later && segment after a swallowed
            # violation. atexit also handles a project's SystemExit(0).
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)
    atexit.register(finish)
    # xdist's informational platform string must not invoke `uname -p` from a
    # guarded worker. The parent has already resolved this same OS metadata.
    platform._platform_cache[False, False] = platform_info
    launch = threading.local()
    capture_fds = set()
    denied = {"os.system", "os.startfile", "os.startfile/2", "os.fork", "os.forkpty", "os.posix_spawn", "os.exec",
              "os.spawn", "pty.spawn", "socket.__new__", "socket.connect", "socket.bind",
              "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
              "os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.link", "os.symlink",
              "os.truncate", "os.chmod", "os.chown", "os.utime", "os.setxattr", "os.removexattr",
              "sqlite3.load_extension"}
    def audit(event, values):
        if getattr(launch, "operation", None) == (event, values[0] if values else None):
            launch.operation = None
            return
        if event == "subprocess.Popen":
            expected = getattr(launch, "command", None)
            if expected is not None and (values[1] if isinstance(values[1], str) else list(values[1])) == expected:
                launch.command = None
                return
        elif event == "open":
            path, mode, flags = values
            writing = flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC)
            # Character sink and existing standard/piped descriptors are not real
            # file mutation. execnet rebinds its standard streams through them.
            # Windows abspath(devnull) uses this exact, case-insensitive device.
            if (not writing or path == os.devnull or isinstance(path, int)
                    or (os.name == "nt" and isinstance(path, str) and path.lower() == r"\\.\nul")):
                return
        elif event == "sqlite3.connect":
            if os.fsdecode(values[0]) == ":memory:" or getattr(launch, "sqlite_target", None) == values[0]:
                launch.sqlite_target = None
                return
        elif event == "sqlite3.connect/handle":
            sqlite_guard(values[0], initialize=False)
            return
        elif event == "sqlite3.enable_load_extension":
            if not values[1]:
                return
        elif event == "os.truncate" and values[0] in capture_fds:
            return
        elif event not in denied:
            return
        record("violation", operation=event, target=repr(values[0]) if values else "")
        raise PermissionError(f"runtime_guard_violation: {event}")
    sys.addaudithook(audit)
    # CPython does not emit audit events for these public creation APIs.
    def blocked_creation(operation):
        def blocked(path, *args, **kwargs):
            record("violation", operation=operation, target=repr(path))
            raise PermissionError(f"runtime_guard_violation: {operation}")
        return blocked
    for name in ("mkfifo", "mknod"):
        if hasattr(os, name):
            setattr(os, name, blocked_creation("os." + name))
    sqlite_guard = _adapt_sqlite(record, launch)
    class UnsupportedNativeFinder:
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".", 1)[0] in {"duckdb", "_duckdb"}:
                record("violation", operation="runtime_guard_uncovered_native", target=fullname)
                raise ImportError("runtime_guard_uncovered_native: DuckDB requires a focused explicit real check")
            return None
    sys.meta_path.insert(0, UnsupportedNativeFinder())
    sys.dont_write_bytecode = True
    sys.path[:] = _startup_path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import site
    site.main()
    sys.modules["build_and_verify_guard"] = sys.modules[__name__]
    if role == "worker" or args[:2] == ["-m", "pytest"]:
        _adapt_pytest_files(launch, capture_fds, evidence)
    if role == "worker":
        # execnet's normal fixed stdin bootstrap, with protection already on.
        exec(eval(sys.stdin.readline()), {"__name__": "__main__"})
    else:
        sys.path.insert(0, os.getcwd() if args[:1] == ["-m"] else str(Path(args[0]).resolve().parent))
        if args[:2] == ["-m", "pytest"]:
            _adapt_pytest(launch, record, evidence, segment)
            import pytest
            return int(pytest.main(["-p", "build_and_verify_guard", *args[2:]]))
        sys.argv = args[:]
        if args[:1] == ["-m"] and len(args) >= 2:
            sys.argv = args[1:]
            runpy.run_module(args[1], run_name="__main__", alter_sys=True)
        elif args[:1] == ["-c"] and len(args) >= 2:
            sys.argv = ["-c", *args[2:]]
            exec(args[1], {"__name__": "__main__"})
        elif args and not args[0].startswith("-"):
            runpy.run_path(args[0], run_name="__main__")
        else:
            raise ValueError("runtime_guard_uncovered_command: unsupported Python launch")
    return 0


def _adapt_sqlite(record, launch):
    import sqlite3
    import sqlite3.dbapi2 as dbapi
    from urllib.parse import parse_qs, unquote, urlsplit
    base = sqlite3.Connection
    connect = sqlite3.connect
    def reject(operation, target):
        record("violation", operation=operation, target=str(target))
    writes = {getattr(sqlite3, "SQLITE_" + name) for name in (
        "INSERT UPDATE DELETE CREATE_INDEX CREATE_TABLE CREATE_TEMP_INDEX CREATE_TEMP_TABLE CREATE_TEMP_TRIGGER "
        "CREATE_TEMP_VIEW CREATE_TRIGGER CREATE_VIEW DROP_INDEX DROP_TABLE DROP_TEMP_INDEX DROP_TEMP_TABLE "
        "DROP_TEMP_TRIGGER DROP_TEMP_VIEW DROP_TRIGGER DROP_VIEW ALTER_TABLE REINDEX ANALYZE CREATE_VTABLE DROP_VTABLE").split()}
    write_pragmas = {"application_id", "user_version", "schema_version", "default_cache_size", "auto_vacuum",
        "page_size", "journal_mode", "journal_size_limit", "locking_mode", "secure_delete", "writable_schema", "wal_checkpoint"}
    def readonly_uri(value):
        parsed = urlsplit(os.fsdecode(value))
        return parsed.scheme == "file" and parse_qs(parsed.query).get("mode") == ["ro"]
    def reject_wal_uri(value):
        path = urlsplit(os.fsdecode(value)).path
        if os.name == "nt":
            from nturl2path import url2pathname
            path = url2pathname(path)
        else:
            path = unquote(path)
        with open(path, "rb") as database:
            header = database.read(20)
        if header[:16] == b"SQLite format 3\x00" and 2 in header[18:20]:
            reject("runtime_guard_uncovered_native", "SQLite WAL: " + os.fsdecode(value))
            raise PermissionError("runtime_guard_uncovered_native: SQLite WAL requires an explicit real check")
    def authorize(connection, action, first, second, database, trigger):
        if ((action == sqlite3.SQLITE_ATTACH and first != ":memory:")
                or (action == sqlite3.SQLITE_PRAGMA and first.lower() in {"temp_store", "temp_store_directory"}
                    and second is not None and (first.lower() != "temp_store" or second.upper() not in {"MEMORY", "2"}))
                or (action == sqlite3.SQLITE_FUNCTION and second == "load_extension")
                or (connection._bav_readonly and action in writes and (database == "main" or first == "main"))
                or (connection._bav_readonly and action == sqlite3.SQLITE_PRAGMA and first.lower() in write_pragmas
                    and (second is not None or first.lower() == "wal_checkpoint"))):
            reject("sqlite3.authorizer", first if action != sqlite3.SQLITE_FUNCTION else second)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    class ProtectedConnection:
        def __init__(self, *args, **kwargs):
            target = args[0] if args else kwargs.get("database")
            uri = args[7] if len(args) > 7 else kwargs.get("uri", False)
            self._bav_readonly = bool(uri and readonly_uri(target))
            if self._bav_readonly:
                reject_wal_uri(target)
            launch.sqlite_target = target if self._bav_readonly else None
            try:
                super().__init__(*args, **kwargs)
                protect(self)
            finally:
                launch.sqlite_target = None
        def set_authorizer(self, callback):
            def combined(*args):
                decision = authorize(self, *args)
                return decision if decision != sqlite3.SQLITE_OK or callback is None else callback(*args)
            return super().set_authorizer(combined)
    def guarded_connect(*args, **kwargs):
        factory = args[5] if len(args) > 5 else kwargs.get("factory", base)
        if factory is base:
            factory = guarded_base
        if not isinstance(factory, type) or not issubclass(factory, ProtectedConnection):
            reject("runtime_guard_uncovered_native", "sqlite3 unsupported factory")
            raise TypeError("runtime_guard_uncovered_native: SQLite factory must derive from the protected public Connection class; use an explicit real check otherwise")
        if len(args) > 5:
            args = (*args[:5], factory, *args[6:])
        else:
            kwargs["factory"] = factory
        return connect(*args, **kwargs)
    guarded_base = type("GuardedSQLiteConnection", (ProtectedConnection, base), {})
    sqlite3.connect = dbapi.connect = guarded_connect
    sqlite3.Connection = dbapi.Connection = guarded_base
    def protect(connection, initialize=True):
        if not isinstance(connection, ProtectedConnection):
            reject("runtime_guard_uncovered_native", "sqlite3 unadapted connection")
            raise TypeError("runtime_guard_uncovered_native: SQLite connection factory is not protected")
        if initialize:
            base.execute(connection, "PRAGMA temp_store=MEMORY")
            connection.set_authorizer(None)
    return protect


def _adapt_pytest(launch, record, evidence, segment):
    try:
        import execnet.gateway_io as gateway_io
        from xdist.workermanage import NodeManager
    except ImportError:
        return
    worker_units = itertools.count()
    worker_lock = threading.Lock()
    setup = NodeManager.setup_node
    def setup_node(manager, spec, putevent):
        if not any(spec is registered for registered in manager.specs):
            record("violation", operation="runtime_guard_uncovered_worker", target="unregistered xdist worker")
            raise PermissionError("runtime_guard_uncovered_worker: unregistered xdist worker")
        launch.spec = spec
        try:
            return setup(manager, spec, putevent)
        finally:
            launch.spec = None
    NodeManager.setup_node = setup_node
    def create_io(spec, execmodel):
        if getattr(launch, "spec", None) is not spec:
            record("violation", operation="runtime_guard_uncovered_worker", target="unregistered execnet launch")
            raise PermissionError("runtime_guard_uncovered_worker: only registered xdist work units may start")
        launch.spec = None
        if not spec.popen or any(getattr(spec, key, None) for key in ("ssh", "socket", "via", "chdir", "env", "python")):
            raise ValueError("runtime_guard_uncovered_command: only local default xdist workers are supported")
        with worker_lock:
            worker_unit = f"python:{segment}:{os.getpid()}:{next(worker_units)}"
        command = [sys.executable, "-S", "-B", "-u", str(Path(__file__).resolve()), evidence, segment, platform.platform(), "--worker", worker_unit]
        # CPython audits argv as the serialized command line on Windows.
        launch.command = execmodel.subprocess.list2cmdline(command) if os.name == "nt" else command
        try:
            io = gateway_io.Popen2IOMaster(command, execmodel)
            record("worker", child=io.popen.pid, childUnit=worker_unit)
            return io
        finally:
            launch.command = None
    gateway_io.create_io = create_io


def _adapt_pytest_files(launch, capture_fds, evidence):
    import _pytest.capture as capture
    import _pytest.cacheprovider as cacheprovider
    from _pytest.tmpdir import TempPathFactory
    sequence = iter(range(1_000_000))
    def capture_file(*, buffering=-1):
        # Fixed internal sink, never a caller-provided pathname or permission.
        name = f"{evidence}.capture-{os.getpid()}-{next(sequence)}"
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_TEMPORARY", 0)
        launch.operation = ("open", name)
        try:
            fd = os.open(name, flags, 0o600)
            capture_fds.add(fd)
            if os.name != "nt":
                launch.operation = ("os.remove", name)
                os.unlink(name)
            return os.fdopen(fd, "w+b", buffering=buffering)
        finally:
            launch.operation = None
    capture.TemporaryFile = capture_file
    cache = {}
    read = cacheprovider.Cache.get
    def get(self, key, default):
        return cache[(id(self), key)] if (id(self), key) in cache else read(self, key, default)
    def put(self, key, value):
        cache[id(self), key] = value
    cacheprovider.Cache.get = get
    cacheprovider.Cache.set = put
    # xdist needs only a pathname here. Business tmp_path creation/writes remain
    # prohibited; no creation, cleanup or lock is needed for an unused pathname.
    TempPathFactory.getbasetemp = lambda self: self._given_basetemp or Path(evidence).parent / "pytest-tmp"


if __name__ == "__main__":
    try:
        raise SystemExit(_run_node(sys.argv[1], sys.argv[2], sys.argv[5:]) if sys.argv[4:5] == ["--node"]
                         else _run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]))
    except Exception as error:
        print(f"runtime_guard_error: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
