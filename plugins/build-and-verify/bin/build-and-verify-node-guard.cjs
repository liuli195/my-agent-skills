'use strict';

// Runtime adapter for ordinary tests, not a sandbox for hostile/native code.
// This preload always runs before project preloads, imports, or test files.
const fs = require('node:fs');
const threads = require('node:worker_threads');
const unit = `${process.pid}:${threads.threadId}`;
const evidence = process.env.BUILD_AND_VERIFY_GUARD_EVIDENCE;
const segment = process.env.BUILD_AND_VERIFY_GUARD_SEGMENT;
const fd = fs.openSync(process.env.BUILD_AND_VERIFY_GUARD_EVIDENCE, 'a', 0o600);
const write = fs.writeSync;
const close = fs.closeSync;
let violated = false;
const record = (event, fields = {}) => {
  violated ||= event === 'violation';
  write(fd, JSON.stringify({ event, pid: process.pid, unit,
    time: Number(process.hrtime.bigint()) / 1e9, ...fields }) + '\n');
};
const root = threads.isMainThread && !process.env.NODE_TEST_CONTEXT;
record('start', { role: root ? 'root' : 'worker', segment, adapter: 'node-preload-v1' });
// Finalize after every project exit callback, not as an earlier listener whose
// closed evidence descriptor would lose a caught cleanup violation.
const emit = process.emit;
process.emit = function(event, ...args) {
  if (event !== 'exit') return emit.call(this, event, ...args);
  try { return emit.call(this, event, ...args); }
  finally { record('finish'); close(fd); if (violated) process.exitCode = 1; }
};
const blocked = (operation) => (...args) => {
  record('violation', { operation, target: String(args[0] ?? '') });
  const error = new Error(`runtime_guard_violation: ${operation}`);
  error.code = 'ERR_TEST_RUNTIME_GUARD';
  throw error;
};
for (const name of ['appendFile', 'chmod', 'chown', 'copyFile', 'cp', 'fchmod', 'fchown', 'fdatasync',
  'fsync', 'ftruncate', 'futimes', 'lchmod', 'lchown', 'link', 'lutimes', 'mkdir', 'mkdtemp',
  'mkdtempDisposable', 'rename', 'rm', 'rmdir', 'symlink', 'truncate', 'unlink', 'utimes', 'writeFile']) {
  for (const suffix of ['', 'Sync']) {
    const key = name + suffix;
    if (typeof fs[key] === 'function') fs[key] = blocked('fs.' + key);
  }
  if (typeof fs.promises[name] === 'function') {
    fs.promises[name] = async (...args) => blocked('fs.promises.' + name)(...args);
  }
}
const writing = (flags) => typeof flags === 'number'
  ? !!(flags & (fs.constants.O_WRONLY | fs.constants.O_RDWR | fs.constants.O_APPEND |
    fs.constants.O_CREAT | fs.constants.O_TRUNC)) : /[wa+]/.test(flags ?? 'r');
for (const name of ['open', 'openSync']) {
  const original = fs[name];
  fs[name] = (path, flags, ...args) => writing(flags)
    ? blocked('fs.' + name)(path) : original(path, flags, ...args);
}
const open = fs.promises.open;
fs.promises.open = async (path, flags, ...args) => {
  if (writing(flags)) return blocked('fs.promises.open')(path);
  const handle = await open(path, flags, ...args);
  for (const name of ['appendFile', 'chmod', 'chown', 'datasync', 'sync', 'truncate', 'utimes',
    'write', 'writeFile', 'writev', 'createWriteStream']) {
    handle[name] = blocked('fs.FileHandle.' + name);
  }
  return handle;
};
fs.createWriteStream = blocked('fs.createWriteStream');
for (const name of ['write', 'writeSync', 'writev', 'writevSync']) {
  const original = fs[name];
  fs[name] = (descriptor, ...args) => descriptor === 1 || descriptor === 2
    ? original(descriptor, ...args) : blocked('fs.' + name)(descriptor);
}

const cp = require('node:child_process');
const NativeChild = cp.ChildProcess;
const nativeSpawn = NativeChild.prototype.spawn;
// The native --test runner captures spawn before project preloads. Keep only
// that private reference usable, constrained to Node's protected test workers.
// Every public launch path, including ChildProcess itself, remains blocked.
NativeChild.prototype.spawn = function(options) {
  const env = options.envPairs || [];
  if (!root || !process.execArgv.includes('--test') || options.file !== process.execPath ||
      !env.includes('NODE_TEST_CONTEXT=child-v8') ||
      !env.includes('BUILD_AND_VERIFY_GUARD_EVIDENCE=' + evidence) ||
      !env.some(value => value.startsWith('NODE_OPTIONS=--require=' + JSON.stringify(__filename)))) {
    return blocked('runtime_guard_uncovered_worker')(options.file);
  }
  const result = nativeSpawn.call(this, options);
  if (this.pid) {
    record('worker', { child: this.pid, childUnit: `${this.pid}:0` });
    this.once('exit', (code, signal) => {
      if (code !== 0 || signal) record('violation', { operation: 'runtime_guard_worker_failed', target: String(this.pid) });
    });
  }
  return result;
};
for (const name of ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork']) {
  cp[name] = blocked('child_process.' + name);
}
cp.ChildProcess = class extends NativeChild {
  spawn(...args) { return blocked('child_process.ChildProcess.spawn')(...args); }
};
require('node:test').run = blocked('runtime_guard_uncovered_worker');
require('node:cluster').fork = blocked('cluster.fork');
const NativeWorker = threads.Worker;
threads.Worker = class extends NativeWorker {
  constructor(filename, options = {}) {
    const env = options.env === threads.SHARE_ENV ? options.env : {
      ...(options.env || process.env), BUILD_AND_VERIFY_GUARD_EVIDENCE: evidence,
      BUILD_AND_VERIFY_GUARD_SEGMENT: segment,
      NODE_OPTIONS: '--require=' + JSON.stringify(__filename) + ' ' + (options.env?.NODE_OPTIONS || process.env.NODE_OPTIONS || ''),
    };
    super(filename, { ...options, env, ...(options.execArgv ? {
      execArgv: ['--require', __filename, ...options.execArgv],
    } : {}) });
    record('worker', { child: process.pid, childUnit: `${process.pid}:${this.threadId}` });
    this.once('error', error => record('violation', { operation: 'runtime_guard_worker_failed', target: error.message }));
    this.once('exit', code => {
      if (code !== 0) record('violation', { operation: 'runtime_guard_worker_failed', target: String(code) });
    });
  }
};

for (const [module, names] of [
  ['net', ['connect', 'createConnection']], ['tls', ['connect']],
  ['http', ['request', 'get']], ['https', ['request', 'get']], ['http2', ['connect']],
  ['dgram', ['createSocket']], ['dns', ['lookup', 'lookupService', 'resolve', 'resolveAny', 'resolve4',
    'resolve6', 'resolveCaa', 'resolveCname', 'resolveMx', 'resolveNaptr', 'resolveNs', 'resolvePtr',
    'resolveSoa', 'resolveSrv', 'resolveTxt', 'reverse']],
]) {
  const exports = require('node:' + module);
  for (const name of names) exports[name] = blocked(module + '.' + name);
  if (module === 'dns') {
    for (const target of [exports.Resolver.prototype, exports.promises, exports.promises.Resolver.prototype]) {
      for (const name of names) if (typeof target[name] === 'function') target[name] = blocked('dns.' + name);
    }
  }
}
require('node:net').Socket.prototype.connect = blocked('net.Socket.connect');
require('node:net').Server.prototype.listen = blocked('net.Server.listen');
for (const name of ['bind', 'connect', 'send', 'addMembership', 'addSourceSpecificMembership']) {
  require('node:dgram').Socket.prototype[name] = blocked('dgram.Socket.' + name);
}
globalThis.fetch = blocked('fetch');
if (globalThis.WebSocket) globalThis.WebSocket = class { constructor(...args) { blocked('WebSocket')(...args); } };
process.dlopen = blocked('runtime_guard_uncovered_native');
process.kill = blocked('process.kill');
process.abort = blocked('process.abort');
if (process.execve) process.execve = blocked('process.execve');
process.report.writeReport = blocked('process.report.writeReport');
require('node:v8').writeHeapSnapshot = blocked('v8.writeHeapSnapshot');
require('node:inspector').open = blocked('inspector.open');
// Asynchronous loader hooks use a separate, unadapted internal thread. Never
// let project callbacks create one that can load project code unprotected.
require('node:module').register = blocked('runtime_guard_uncovered_worker');
const exit = process.exit;
process.exit = (code) => { record('violation', { operation: 'runtime_guard_abrupt_exit', target: String(code) }); exit(code); };
adaptSQLite();
require('node:module').syncBuiltinESMExports();

function adaptSQLite() {
  if (!require('node:module').builtinModules.some(name => name === 'sqlite' || name === 'node:sqlite')) return;
  const sqlite = require('node:sqlite');
  const Base = sqlite.DatabaseSync;
  const authorizer = Base.prototype.setAuthorizer;
  const state = new WeakMap();
  const c = sqlite.constants;
  const writes = new Set(('INSERT UPDATE DELETE CREATE_INDEX CREATE_TABLE CREATE_TEMP_INDEX CREATE_TEMP_TABLE CREATE_TEMP_TRIGGER ' +
    'CREATE_TEMP_VIEW CREATE_TRIGGER CREATE_VIEW DROP_INDEX DROP_TABLE DROP_TEMP_INDEX DROP_TEMP_TABLE ' +
    'DROP_TEMP_TRIGGER DROP_TEMP_VIEW DROP_TRIGGER DROP_VIEW ALTER_TABLE REINDEX ANALYZE CREATE_VTABLE DROP_VTABLE')
    .split(' ').map(name => c['SQLITE_' + name]));
  const writePragmas = new Set(('application_id user_version schema_version default_cache_size auto_vacuum ' +
    'page_size journal_mode journal_size_limit locking_mode secure_delete writable_schema wal_checkpoint').split(' '));
  function authorize(db, action, first, second, database) {
    const saved = state.get(db);
    const deserializeAttach = action === c.SQLITE_ATTACH && first === 'x' && saved.deserializeAttach;
    if (deserializeAttach) saved.deserializeAttach = false;
    if ((action === c.SQLITE_ATTACH && first !== ':memory:' && !deserializeAttach) ||
        (action === c.SQLITE_PRAGMA && ['temp_store', 'temp_store_directory'].includes(first?.toLowerCase()) &&
          second !== null && (first.toLowerCase() !== 'temp_store' || !['MEMORY', '2'].includes(second.toUpperCase()))) ||
        (action === c.SQLITE_FUNCTION && second === 'load_extension') ||
        (saved.readonly && writes.has(action) && (database === 'main' || first === 'main')) ||
        (saved.readonly && action === c.SQLITE_PRAGMA && writePragmas.has(first?.toLowerCase()) &&
          (second !== null || first.toLowerCase() === 'wal_checkpoint'))) {
      record('violation', { operation: 'sqlite.authorizer', target: String(first ?? second) });
      return c.SQLITE_DENY;
    }
    return c.SQLITE_OK;
  }
  function canOpen(path, options) {
    if (typeof authorizer !== 'function') {
      return blocked('runtime_guard_uncovered_native')('node:sqlite requires its native setAuthorizer interface');
    }
    if (path !== ':memory:' && options.readOnly !== true) return blocked('sqlite.open')(path);
    if (path !== ':memory:') {
      const descriptor = fs.openSync(path, 'r');
      const header = Buffer.alloc(20);
      try { fs.readSync(descriptor, header, 0, header.length, 0); }
      finally { fs.closeSync(descriptor); }
      if (header.subarray(0, 16).equals(Buffer.from('SQLite format 3\0')) &&
          (header[18] === 2 || header[19] === 2)) {
        return blocked('runtime_guard_uncovered_native')('SQLite WAL: ' + String(path));
      }
    }
    if (options.allowExtension === true) return blocked('sqlite.enableLoadExtension')(path);
  }
  function protect(db) {
    Base.prototype.exec.call(db, 'PRAGMA temp_store=MEMORY');
    db.setAuthorizer(state.get(db).callback);
  }
  sqlite.DatabaseSync = class extends Base {
    constructor(path, options = {}) {
      const storedPath = Buffer.isBuffer(path) ? path.toString() : path;
      const storedOptions = { ...options };
      if (storedOptions.open !== false) canOpen(storedPath, storedOptions);
      super(path, options);
      state.set(this, { path: storedPath, options: storedOptions, readonly: storedPath !== ':memory:', callback: null });
      if (storedOptions.open !== false) protect(this);
    }
    open() {
      const saved = state.get(this);
      canOpen(saved.path, saved.options);
      super.open();
      saved.readonly = saved.path !== ':memory:';
      protect(this);
    }
    setAuthorizer(callback) {
      if (callback !== null && typeof callback !== 'function') return authorizer.call(this, callback);
      state.get(this).callback = callback;
      return authorizer.call(this, (...args) => {
        const decision = authorize(this, ...args);
        return decision !== c.SQLITE_OK || callback === null ? decision : callback(...args);
      });
    }
    loadExtension(...args) { return blocked('sqlite.loadExtension')(...args); }
    enableLoadExtension(allow) {
      if (allow) return blocked('sqlite.enableLoadExtension')(allow);
      return super.enableLoadExtension(allow);
    }
  };
  // Deserialization replaces the selected database with memory, not a file.
  // Preserve its allowed computation and reinstall protection on the handle.
  if (Base.prototype.deserialize) {
    sqlite.DatabaseSync.prototype.deserialize = function(buffer, options) {
      const saved = state.get(this);
      saved.deserializeAttach = true;
      try {
        const result = Base.prototype.deserialize.call(this, buffer, options);
        if (!options?.dbName || options.dbName === 'main') saved.readonly = false;
        protect(this);
        return result;
      } finally { saved.deserializeAttach = false; }
    };
  }
  const backup = sqlite.backup;
  sqlite.backup = async (source, target, ...options) => {
    if (target !== ':memory:') return blocked('sqlite.backup')(target);
    return backup(source, target, ...options);
  };
}
