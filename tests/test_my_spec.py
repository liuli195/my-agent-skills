from __future__ import annotations

import contextlib
import hashlib
import io
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.support.command_stubs import CommandStub, completed
from tests.support.myspec_cases import bumped_patch, main_spec, npm_prefix_for, requirement


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "my-spec"
PLUGIN_SYNC_ROOT = REPO_ROOT / "plugins" / "plugin-sync" / "skills" / "plugin-sync"
SPEC_OPS = PLUGIN_ROOT / "python" / "spec_ops.py"
SKILL_NAMES = ("my-spec", "my-spec-add", "my-spec-review", "my-spec-audit")
PACKAGE_VERSION = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
SOURCE_CASES = json.loads(
    (REPO_ROOT / "tests" / "fixtures" / "myspec_source_cases.json").read_text(encoding="utf-8")
)
SOURCE_FIELDS = (
    "installed",
    "registered",
    "enabled",
    "effective",
    "sourceKind",
    "sourceMismatch",
)
_in_process_spec_ops: dict[Path, object] = {}


def _load_in_process_spec_ops(spec_ops_path: Path):
    spec_ops_path = spec_ops_path.resolve()
    cached = _in_process_spec_ops.get(spec_ops_path)
    if cached is not None:
        return cached

    module_id = hashlib.sha256(str(spec_ops_path).encode()).hexdigest()[:16]
    management_name = "management"
    previous_management = sys.modules.get(management_name)
    try:
        management_spec = importlib.util.spec_from_file_location(
            f"myspec_management_{module_id}", spec_ops_path.with_name("management.py")
        )
        assert management_spec is not None and management_spec.loader is not None
        management = importlib.util.module_from_spec(management_spec)
        sys.modules[management_spec.name] = management
        sys.modules[management_name] = management
        exec(compile(spec_ops_path.with_name("management.py").read_text(encoding="utf-8"), str(spec_ops_path.with_name("management.py")), "exec"), management.__dict__)

        spec_ops_spec = importlib.util.spec_from_file_location(
            f"myspec_spec_ops_{module_id}", spec_ops_path
        )
        assert spec_ops_spec is not None and spec_ops_spec.loader is not None
        module = importlib.util.module_from_spec(spec_ops_spec)
        sys.modules[spec_ops_spec.name] = module
        exec(compile(spec_ops_path.read_text(encoding="utf-8"), str(spec_ops_path), "exec"), module.__dict__)
    finally:
        if previous_management is None:
            sys.modules.pop(management_name, None)
        else:
            sys.modules[management_name] = previous_management
    _in_process_spec_ops[spec_ops_path] = module
    return module


PREVIOUS_VERSION = bumped_patch(PACKAGE_VERSION, -1)
NEXT_VERSION = bumped_patch(PACKAGE_VERSION)


def run_python(script, *args):
    assert script == SPEC_OPS, f"unexpected_python_command: {script}"
    return invoke_main(_load_in_process_spec_ops(SPEC_OPS), *args)


class ManagementDocuments:
    """Only lifecycle JSON/config leaves and exact external command responses.

    This is not a filesystem: there is no mkdir/open/rename/copy emulation.
    Physical installation, locking, aliases and rollback stay in TestMySpec.
    """

    def __init__(self, module, monkeypatch):
        self.module = module
        self.management = sys.modules[module.run_management.__module__]
        self.monkeypatch = monkeypatch
        self.root = REPO_ROOT / "__myspec_documents__"
        self.prefix = self.root / "prefix"
        self.stable = self.prefix / ("node_modules" if os.name == "nt" else "lib/node_modules") / "@liuli195" / "myspec"
        self.cache = self.root / "client-cache"
        self.home = self.root / "home"
        self.codex_home = self.home / ".codex"
        self.state_path = self.home / ".myspec" / "state.json"
        self.config_path = self.codex_home / "config.toml"
        manifest = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))
        self.documents = {self.stable / "package.json": manifest, self.cache / "package.json": dict(manifest)}
        self.texts = {}
        self.config_paths = {self.config_path}
        self.realpaths = {}
        self.sdk_environments = []
        self.writes = []
        self.lock_calls = []
        self.available = set()
        self.stub = CommandStub(consume=True)
        self.directories = {self.stable, self.cache, self.codex_home}
        self.files = {self.stable / "package.json", self.cache / "package.json",
                      self.prefix / ("myspec.cmd" if os.name == "nt" else "bin/myspec")}
        self.files.update(root / "skills" / skill / "SKILL.md" for root in (self.stable, self.cache) for skill in SKILL_NAMES)
        original_exists, original_is_dir, original_is_file = Path.exists, Path.is_dir, Path.is_file
        monkeypatch.setattr(Path, "exists", lambda path: path in self.documents or path in self.texts or path in self.files or path in self.directories or (False if path.is_relative_to(self.root) else original_exists(path)))
        monkeypatch.setattr(Path, "is_dir", lambda path: path in self.directories if path.is_relative_to(self.root) else original_is_dir(path))
        monkeypatch.setattr(Path, "is_file", lambda path: path in self.documents or path in self.files if path.is_relative_to(self.root) else original_is_file(path))
        original_access = os.access
        monkeypatch.setattr(os, "access", lambda path, mode: True if Path(path) in self.directories else original_access(path, mode))
        original_read_json, original_text = self.management._read_json, self.management._text
        monkeypatch.setattr(self.management, "_read_json", lambda path: json.loads(json.dumps(self.documents[path])) if path in self.documents else original_read_json(path))
        monkeypatch.setattr(self.management, "_text", lambda path: self.texts[path] if path in self.texts else original_text(path))
        monkeypatch.setattr(self.management, "_atomic_json", self.save_json)
        monkeypatch.setattr(self.management, "_atomic_text", self.save_text)
        self.real_run = self.management._run
        monkeypatch.setattr(self.management, "_run", self.stub)
        original_realpath = os.path.realpath
        monkeypatch.setattr(os.path, "realpath", lambda path, **kwargs: str(self.realpaths.get(Path(path), Path(original_realpath(path, **kwargs)))))
        monkeypatch.setattr(self.management, "_RUNNING_PACKAGE_ROOT", self.stable)
        monkeypatch.setattr(self.management, "_acquire_install_lock", lambda command: self.lock_calls.append(("acquire", command)) or "operation")
        monkeypatch.setattr(self.management, "_claim_install_lock", lambda token: self.lock_calls.append(("claim", token)) or "operation")
        monkeypatch.setattr(self.management, "_release_install_lock", lambda operation: self.lock_calls.append(("release", operation)))
        monkeypatch.setattr(self.management, "_lock_report", lambda: None)
        monkeypatch.setattr(shutil, "which", lambda command, **kwargs: str(self.root / "bin" / command) if command in self.available else None)
        for key, value in {"HOME": self.home, "USERPROFILE": self.home, "CODEX_HOME": self.codex_home, "NPM_CONFIG_PREFIX": self.prefix}.items():
            monkeypatch.setenv(key, str(value))
        for key in ("ORCA_CODEX_HOME", "ORCA_USER_DATA_PATH"):
            monkeypatch.delenv(key, raising=False)

    def save_json(self, path, value):
        assert path == self.state_path, f"unexpected_lifecycle_json_write: {path}"
        self.documents[path] = json.loads(json.dumps(value))
        self.writes.append((path, json.loads(json.dumps(value))))

    def save_text(self, path, value):
        assert path in self.config_paths, f"unexpected_lifecycle_text_write: {path}"
        self.texts[path] = value
        self.writes.append((path, value))

    def response(self, command, value=None, *, stdout=None, stderr="", code=0, once=False):
        key = tuple(command)
        output = json.dumps(value) if stdout is None and value is not None else stdout or ""
        result = completed(key, stdout=output, stderr=stderr, returncode=code)
        if once:
            self.stub.responses.append((key, result))
        else:
            self.stub.defaults = [(args, previous) for args, previous in self.stub.defaults if args != key]
            self.stub.defaults.append((key, result))

    def records(self, client, marketplaces, plugins):
        self.available.add(client)
        if client == "claude":
            self.response((client, "plugin", "marketplace", "list", "--json"), marketplaces)
            self.response((client, "plugin", "list", "--json"), plugins)
        else:
            self.response((client, "plugin", "marketplace", "list", "--json"), {"marketplaces": marketplaces})
            self.response((client, "plugin", "list", "--json"), {"installed": plugins, "available": []})

    def marketplace(self, client, *, legacy=False, mismatch=False):
        name = "my-agent-skills-marketplace" if legacy else "myspec"
        source = self.root / "wrong-source" if mismatch else self.stable
        return ({"name": name, "source": "directory", "path": str(source), "installLocation": str(source)}
                if client == "claude" else
                {"name": name, "root": str(source), "marketplaceSource": {"sourceType": "local", "source": str(source)}})

    def plugin(self, client, *, legacy=False, enabled=True, installed=True, version=None):
        identifier = "my-spec@my-agent-skills-marketplace" if legacy else "my-spec@myspec"
        path = self.cache if installed else self.root / "missing-client-cache"
        if client == "claude":
            return {"id": identifier, "version": version or PACKAGE_VERSION, "scope": "user",
                    "enabled": enabled, "installPath": str(path)}
        return {"pluginId": identifier, "name": "my-spec", "marketplaceName": identifier.split("@", 1)[1],
                "version": version or PACKAGE_VERSION, "installed": True, "enabled": enabled,
                "source": {"source": "local", "path": str(path)}}

    def queue_plugins(self, client, values):
        for value in values:
            payload = value if client == "claude" else {"installed": value, "available": []}
            self.response((client, "plugin", "list", "--json"), payload, once=True)

    def release_input(self, version):
        # Input for the post-install runtime. The actual install/handoff is
        # independently exercised in TestMySpec, never mocked as main success.
        for path in (self.stable / "package.json", self.cache / "package.json"):
            self.documents[path]["version"] = version
        self.monkeypatch.setattr(self.management, "_RUNNING_PACKAGE_VERSION", version)

    def source_documents(self):
        source = self.root / "source"
        package = source / "plugins" / "my-spec"
        paths = [
            "package.json", "python/lifecycle_profile.json", "bin/myspec.js",
            "python/spec_ops.py", "python/management.py",
            ".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json",
            ".claude-plugin/plugin.json", ".codex-plugin/plugin.json",
            *(f"skills/{skill}/SKILL.md" for skill in SKILL_NAMES),
        ]
        for relative in paths:
            target = package / relative
            self.files.add(target)
            if target.suffix == ".json":
                self.documents[target] = json.loads((PLUGIN_ROOT / relative).read_text(encoding="utf-8"))
        for relative in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
            self.documents[source / relative] = json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))
        self.files.add(source / "plugins/tool-lifecycle/python/management.py")
        self.directories.update((source, package))
        commit = "a" * 40
        for command, stdout in (
            (("git", "rev-parse", "--show-toplevel"), str(source)),
            (("git", "diff", "--quiet", "--exit-code"), ""),
            (("git", "diff", "--cached", "--quiet", "--exit-code"), ""),
            (("git", "ls-files", "--others", "--exclude-standard"), ""),
            (("git", "remote", "get-url", "origin"), "https://github.com/liuli195/my-agent-skills.git"),
            (("git", "rev-parse", "HEAD"), commit),
            (("git", "ls-remote", "origin"), commit + "\trefs/heads/main\n"),
        ):
            self.response(command, stdout=stdout)
        return source, package

    def switch_input(self, stage, source):
        token = "memory-switch-token"
        self.documents[self.state_path] = {
            "mode": "dev", "source": str(source), "previousReleaseVersion": PACKAGE_VERSION,
            "pendingSwitch": {"stage": stage, "token": token},
        }
        return token

    def capture_sdk_environments(self):
        # Preserve the real _run selection/argument/environment behavior while
        # replacing only subprocess.run at the external program boundary.
        self.monkeypatch.setattr(self.management, "_run", self.real_run)
        def execute(invocation, **kwargs):
            assert isinstance(invocation, list), f"unexpected_sdk_shell_command: {invocation}"
            command = Path(invocation[0]).name
            self.sdk_environments.append((command, dict(kwargs.get("env") or {})))
            return self.stub(command, *invocation[1:])
        self.monkeypatch.setattr(subprocess, "run", execute)

    def run(self, *args):
        return invoke_main(self.module, *args)


def queue_client_init(runtime, client, *, legacy=False, existing=False, enabled=True,
                      reported_version=None, removal="success", others=()):
    """Declare exact client replies; do not execute or model a client program."""
    stable = runtime.plugin(client, enabled=enabled, version=reported_version)
    legacy_plugin = runtime.plugin(client, legacy=True, enabled=False, version=PREVIOUS_VERSION)
    initial = ([runtime.plugin(client, enabled=False, version=PREVIOUS_VERSION)] if existing else []) + ([legacy_plugin] if legacy else []) + list(others)
    current = [stable, *([legacy_plugin] if legacy else []), *others]
    final = [runtime.plugin(client), *([legacy_plugin] if removal == "noop" else []), *others]
    runtime.records(client, [runtime.marketplace(client)], final)
    def plugin_reply(value):
        payload = value if client == "claude" else {"installed": value, "available": []}
        runtime.response((client, "plugin", "list", "--json"), payload, once=True)
    plugin_reply(initial)
    if client == "claude":
        if existing:
            runtime.response((client, "plugin", "marketplace", "update", "myspec"))
            runtime.response((client, "plugin", "update", "my-spec@myspec", "--scope", "user"))
        else:
            runtime.response((client, "plugin", "install", "my-spec@myspec", "--scope", "user"))
    else:
        if existing:
            runtime.response((client, "plugin", "remove", "my-spec@myspec", "--json"))
        runtime.response((client, "plugin", "add", "my-spec@myspec", "--json"))
    plugin_reply(current)
    if client == "claude" and not enabled:
        runtime.response((client, "plugin", "enable", "my-spec@myspec", "--scope", "user"))
        current = [{**stable, "enabled": True}, *([legacy_plugin] if legacy else []), *others]
        plugin_reply(current)
    if legacy and reported_version in (None, PACKAGE_VERSION):
        command = ((client, "plugin", "uninstall", "my-spec@my-agent-skills-marketplace", "--scope", "user", "--keep-data")
                   if client == "claude" else (client, "plugin", "remove", "my-spec@my-agent-skills-marketplace", "--json"))
        runtime.response(command, code=1 if removal == "interrupted" else 0,
                         stderr="simulated interruption after removal" if removal == "interrupted" else "")
    return final


def assert_initializes_and_removes_legacy(runtime, client):
    other = {"id": "unrelated@market", "enabled": True} if client == "claude" else {"pluginId": "unrelated@market", "installed": True}
    queue_client_init(runtime, client, legacy=True, others=[other])
    initialized = runtime.run("init", f"--{client}")
    assert initialized.returncode == 0, initialized.stderr
    report = json.loads(initialized.stdout)
    assert report[client] == "initialized"
    assert report["removedLegacyPlugins"] == ["my-spec@my-agent-skills-marketplace"]
    assert report["source"] == str(runtime.stable)
    assert runtime.writes == []
    assert runtime.lock_calls[-1] == ("release", "operation")
    # Observe the command boundary, not the canned client response itself.
    assert not any("unrelated@market" in command for command in runtime.stub.calls)


def assert_wrong_stable_version_keeps_legacy(runtime, client):
    queue_client_init(runtime, client, legacy=True, reported_version="0.0.0")
    result = runtime.run("init", f"--{client}")
    assert result.returncode == 1
    assert f"{client}_plugin_verify_failed" in result.stderr
    legacy_id = "my-spec@my-agent-skills-marketplace"
    assert not any(legacy_id in command and command[1:3] in {("plugin", "remove"), ("plugin", "uninstall")} for command in runtime.stub.calls)
    assert runtime.writes == []


def assert_retry_legacy_removal(runtime, client, removal):
    queue_client_init(runtime, client, legacy=True, removal=removal)
    failed = runtime.run("init", f"--{client}")
    assert failed.returncode == 1
    error = (f"{client}_plugin_" + ("uninstall" if client == "claude" else "remove") +
             ("_incomplete" if removal == "noop" else "_failed: simulated interruption after removal"))
    assert error in failed.stderr
    queue_client_init(runtime, client, legacy=removal == "noop", existing=True)
    retried = runtime.run("init", f"--{client}")
    assert retried.returncode == 0, retried.stderr
    expected = ["my-spec@my-agent-skills-marketplace"] if removal == "noop" else []
    assert json.loads(retried.stdout)["removedLegacyPlugins"] == expected
    assert runtime.writes == []


def assert_explicit_client_and_detected_all(runtime, client):
    missing = runtime.run("init", f"--{client}")
    assert missing.returncode == 1
    assert f"missing_command: {client}" in missing.stderr
    queue_client_init(runtime, client)
    result = runtime.run("init", "--all")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    other = "codex" if client == "claude" else "claude"
    assert report[client]["status"] == "initialized"
    assert report[client]["removedLegacyPlugins"] == []
    assert report[other] == {"status": "skipped", "reason": f"missing_command: {other}"}


@pytest.fixture
def management_documents(monkeypatch):
    return ManagementDocuments(_load_in_process_spec_ops(SPEC_OPS), monkeypatch)


class SpecDocuments:
    """Finite spec/session document leaves, not a physical filesystem emulator.

    Real parsing, merging, rendering, hashing and main are unchanged. There are
    deliberately no open, rename, unlink, symlink, stat or rollback operations.
    Those assertions live in TestMySpec.
    """

    def __init__(self, module, monkeypatch):
        self.module = module
        self.root = REPO_ROOT / "__myspec_spec_documents__"
        self.texts = {}
        self.directories = {self.root}
        self.management = sys.modules[module.run_management.__module__]
        self.stub = CommandStub()
        monkeypatch.setattr(self.management, "_run", self.stub)
        original_text = module._text
        monkeypatch.setenv("NPM_CONFIG_PREFIX", str(self.root / "prefix"))
        monkeypatch.setattr(module, "_text", lambda path: self.texts[path].replace("\r\n", "\n") if self.owns(path) else original_text(path))
        monkeypatch.setattr(module, "_atomic_json", self.save_json)
        original_exists, original_dir, original_file = Path.exists, Path.is_dir, Path.is_file
        original_read, original_bytes = Path.read_text, Path.read_bytes
        original_rglob, original_iterdir = Path.rglob, Path.iterdir
        monkeypatch.setattr(Path, "exists", lambda path: path in self.texts or path in self.directories if self.owns(path) else original_exists(path))
        monkeypatch.setattr(Path, "is_dir", lambda path: path in self.directories if self.owns(path) else original_dir(path))
        monkeypatch.setattr(Path, "is_file", lambda path: path in self.texts if self.owns(path) else original_file(path))
        monkeypatch.setattr(Path, "read_text", lambda path, *args, **kwargs: self.texts[path] if self.owns(path) else original_read(path, *args, **kwargs))
        monkeypatch.setattr(Path, "read_bytes", lambda path: self.texts[path].encode("utf-8") if self.owns(path) else original_bytes(path))
        monkeypatch.setattr(Path, "write_text", lambda path, value, *args, **kwargs: self.store(path, value) if self.owns(path) else self.unexpected_write(path))
        monkeypatch.setattr(Path, "write_bytes", lambda path, value: self.store(path, value.decode("utf-8")) if self.owns(path) else self.unexpected_write(path))
        monkeypatch.setattr(Path, "mkdir", lambda path, *args, **kwargs: self.directory(path) if self.owns(path) else self.unexpected_write(path))
        monkeypatch.setattr(Path, "rglob", lambda path, pattern: iter(sorted(p for p in self.texts if p.is_relative_to(path) and (pattern == "*" or p.match(pattern)))) if self.owns(path) else original_rglob(path, pattern))
        monkeypatch.setattr(Path, "iterdir", lambda path: iter(sorted({path / p.relative_to(path).parts[0] for p in (*self.texts, *self.directories) if p != path and p.is_relative_to(path)})) if self.owns(path) else original_iterdir(path))
        monkeypatch.setattr(shutil, "copyfile", lambda source, destination, **kwargs: self.store(destination, self.texts[source]) if self.owns(source) and self.owns(destination) else self.unexpected_write(destination))

    def unexpected_write(self, path):
        raise AssertionError(f"unexpected_spec_write: {path}")

    def owns(self, path):
        return Path(path).is_relative_to(self.root)

    def directory(self, path):
        assert self.owns(path), f"unexpected_spec_directory: {path}"
        self.directories.update(parent for parent in (path, *path.parents) if self.owns(parent))

    def store(self, path, value):
        assert self.owns(path), f"unexpected_spec_document: {path}"
        self.directory(path.parent)
        self.texts[path] = value
        return len(value)

    def write(self, path, value):
        self.store(path, value.rstrip() + "\n")

    def save_json(self, path, value):
        assert path.name == "state.json" and path.parent.name == "current", f"unexpected_spec_json_write: {path}"
        self.store(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def seed_state(self, work, command="add"):
        # An already-created session is an input document. Creating and owning
        # its real lock is covered by TestMySpec, not mocked as main success.
        self.save_json(work / "current" / "state.json", {
            "command": command, "sessionId": "memory-session", "applicationPhase": "PREVIEW_ONLY",
            "status": "ANALYZING", "specsFingerprint": "specs-fingerprint", "inputFingerprint": "input-fingerprint",
            "currentConflict": 0, "conflicts": [], "decisions": [], "workRoot": str(work), "targetWorktree": None,
            "specsRoot": None, "deltaRoot": None, "previewRoot": None, "specsContentFingerprint": None,
            "deltaContentFingerprint": None, "previewContentFingerprint": None,
            "implementationIdentity": "release:" + PACKAGE_VERSION,
        })

    def ready_state(self, cli, root, command="add"):
        assert cli == SPEC_OPS
        work = root / ".local" / "spec-work"
        self.seed_state(work, command)
        conflicts = root / "no-conflicts.json"
        self.write(conflicts, "[]")
        stored = run_python(cli, "state-set-conflicts", work, conflicts, "specs-fingerprint", "input-fingerprint")
        assert stored.returncode == 0, stored.stderr
        return work

    def apply(self, cli, specs, delta, output, work):
        return run_python(cli, "apply-delta", specs, delta, output, work, "specs-fingerprint", "input-fingerprint")


@pytest.fixture
def spec_documents(monkeypatch):
    return SpecDocuments(_load_in_process_spec_ops(SPEC_OPS), monkeypatch)


def invoke_main(module, *args):
    """Exercise the real public parser/main, without a process or cwd change."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            code = module.main([str(arg) for arg in args])
        except SystemExit as error:
            code = error.code
    return subprocess.CompletedProcess(["myspec", *map(str, args)], code, stdout.getvalue(), stderr.getvalue())


@pytest.mark.parametrize("client", ("claude", "codex"))
def test_packed_myspec_clients_run_shared_source_cases(management_documents, client: str) -> None:
    runtime = management_documents
    cases = [*SOURCE_CASES, {"id": "stable-unregistered-plugin", "scenario": "stable-unregistered-plugin", "expectedSources": [
        {"installed": True, "registered": False, "enabled": True, "effective": False,
         "sourceKind": "stable", "sourceMismatch": False}]}]
    for case in cases:
        scenario = case["scenario"]
        legacy = scenario == "legacy-enabled"
        marketplaces = [] if scenario in {"no-source", "stable-unregistered-plugin"} else [runtime.marketplace(client, legacy=legacy, mismatch=scenario == "stable-source-mismatch")]
        plugins = [] if scenario == "no-source" else [runtime.plugin(client, legacy=legacy, enabled=scenario != "stable-disabled", installed=scenario != "stable-missing-directory")]
        runtime.records(client, marketplaces, plugins)
        runtime.stub.calls.clear()
        diagnosed = runtime.run("doctor", f"--{client}")
        assert diagnosed.returncode == 0, diagnosed.stderr
        report = json.loads(diagnosed.stdout)[client]
        assert [{field: source[field] for field in SOURCE_FIELDS} for source in report["sources"]] == case["expectedSources"], case["id"]
        assert {"enabledSources", "disabledSources", "duplicateEnabledSources"} <= report.keys()
        assert runtime.stub.calls == [(client, "plugin", "marketplace", "list", "--json"), (client, "plugin", "list", "--json")]
        assert runtime.writes == []


@pytest.mark.parametrize(('platform', 'relative_layout'), [('linux', ('lib', 'node_modules')), ('windows', ('node_modules',))])
def test_npm_prefix_for_supported_platform_layouts(platform: str, relative_layout: tuple[str, ...]) -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    prefix = tmp_path / platform / 'npm-prefix'
    installed_package = prefix.joinpath(*relative_layout, '@liuli195', 'myspec')
    assert npm_prefix_for(installed_package) == prefix


def test_packed_myspec_update_preflights_installed_clients_before_package_write(management_documents):
    runtime = management_documents
    runtime.records("codex", [], [runtime.plugin("codex")])
    runtime.response(("codex", "plugin", "marketplace", "list", "--json"), {"marketplaces": "broken"})
    package_before = json.loads(json.dumps(runtime.documents[runtime.stable / "package.json"]))
    failed = runtime.run("update")
    assert failed.returncode == 1
    assert "error: codex_marketplace_list_failed: invalid_output" in failed.stderr
    assert runtime.documents[runtime.stable / "package.json"] == package_before
    assert runtime.state_path not in runtime.documents
    assert not any(call[:3] == ("npm", "install", "--global") for call in runtime.stub.calls)
    runtime.response(("codex", "plugin", "list", "--json"), {"installed": [], "available": []})
    runtime.stub.calls.clear()
    runtime.response(("npm", "view", "@liuli195/myspec", "version", "--json"), PACKAGE_VERSION)
    skipped = runtime.run("update")
    assert skipped.returncode == 0, skipped.stderr
    assert "codex" not in json.loads(skipped.stdout)
    assert ("codex", "plugin", "marketplace", "list", "--json") not in runtime.stub.calls


def test_packed_myspec_update_blocks_enabled_legacy_sources_before_writes(management_documents):
    runtime = management_documents
    for client in ("claude", "codex"):
        runtime.records(client, [runtime.marketplace(client), runtime.marketplace(client, legacy=True)],
                        [runtime.plugin(client), runtime.plugin(client, legacy=True)])
    runtime.texts[runtime.config_path] = '[plugins."my-spec@myspec"]\nenabled = true\n[plugins."my-spec@my-agent-skills-marketplace"]\nenabled = true\n'
    before = dict(runtime.texts)
    blocked = runtime.run("update", "--codex-home", runtime.codex_home)
    assert blocked.returncode == 1
    assert "error: legacy_source_migration_required" in blocked.stderr
    assert "claude: run myspec init --claude" in blocked.stderr
    arguments = ["myspec", "init", "--codex", "--codex-home", str(runtime.codex_home)]
    codex_command = subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)
    assert f"codex: run {codex_command}" in blocked.stderr
    assert not any(call[:3] == ("npm", "install", "--global") for call in runtime.stub.calls)
    assert runtime.state_path not in runtime.documents
    assert runtime.writes == []
    assert runtime.texts == before
    assert runtime.stub.calls == [(client, "plugin", "list", "--json") for client in ("claude", "codex")]
    for client in ("claude", "codex"):
        queue_client_init(runtime, client, legacy=True)
    migrated = runtime.run("init", "--all")
    assert migrated.returncode == 0, migrated.stderr
    # The new runtime is an input, not a fake successful package installation.
    runtime.release_input(NEXT_VERSION)
    for client in ("claude", "codex"):
        runtime.records(client, [runtime.marketplace(client)], [runtime.plugin(client, version=NEXT_VERSION)])
    runtime.response(("npm", "view", "@liuli195/myspec", "version", "--json"), NEXT_VERSION)
    updated = runtime.run("update")
    assert updated.returncode == 0, updated.stderr
    assert json.loads(updated.stdout)["version"] == NEXT_VERSION


def test_packed_myspec_update_refreshes_disabled_integrations_and_skips_only_missing(management_documents):
    runtime = management_documents
    runtime.release_input(NEXT_VERSION)
    old = {client: runtime.plugin(client, enabled=False, version=PACKAGE_VERSION) for client in ("claude", "codex")}
    new = {client: runtime.plugin(client, enabled=True, version=NEXT_VERSION) for client in ("claude", "codex")}
    disabled = {client: runtime.plugin(client, enabled=False, version=NEXT_VERSION) for client in ("claude", "codex")}
    for client in ("claude", "codex"):
        runtime.records(client, [runtime.marketplace(client)], [old[client]])
    runtime.documents[runtime.state_path] = {"mode": "release", "pendingOperation": {
        "command": "update", "targetVersion": NEXT_VERSION, "integrations": ["claude", "codex"],
        "scopes": {"claude": "user"}, "enabled": {"claude": False, "codex": False},
        "completed": ["preflight", "npm"],
    }}
    runtime.queue_plugins("claude", [[old["claude"]], [old["claude"]], [], [new["claude"]]])
    runtime.response(("claude", "plugin", "uninstall", "my-spec@myspec", "--scope", "user", "--keep-data"))
    runtime.response(("claude", "plugin", "install", "my-spec@myspec", "--scope", "user"))
    runtime.response(("claude", "plugin", "disable", "my-spec@myspec", "--scope", "user"), code=1,
                     stderr="simulated interruption after enabled state")
    interrupted = runtime.run("update")
    assert interrupted.returncode == 1
    assert "claude_plugin_disable_failed: simulated interruption after enabled state" in interrupted.stderr
    assert runtime.documents[runtime.state_path]["pendingOperation"]["lastError"] == "claude_plugin_disable_failed: simulated interruption after enabled state"
    # The SDK's next observed state records the external effect before failure.
    runtime.records("claude", [runtime.marketplace("claude")], [disabled["claude"]])
    runtime.records("codex", [runtime.marketplace("codex")], [disabled["codex"]])
    runtime.queue_plugins("codex", [[old["codex"]], [old["codex"]], [], [new["codex"]], [disabled["codex"]]])
    runtime.response(("codex", "plugin", "remove", "my-spec@myspec", "--json"))
    runtime.response(("codex", "plugin", "add", "my-spec@myspec", "--json"))
    updated = runtime.run("update")
    assert updated.returncode == 0, updated.stderr
    output = json.loads(updated.stdout)
    assert output["version"] == NEXT_VERSION
    assert output["claude"] == "refreshed"
    assert output["codex"] == "refreshed"
    for client in ("claude", "codex"):
        assert output["doctor"][client]["enabled"] is False
        stable_source = next(source for source in output["doctor"][client]["sources"] if source["sourceKind"] == "stable")
        assert stable_source["enabled"] is False
        assert output["doctor"][client]["version"] == NEXT_VERSION
    assert ("claude", "plugin", "uninstall", "my-spec@myspec", "--scope", "user", "--keep-data") in runtime.stub.calls
    assert ("claude", "plugin", "install", "my-spec@myspec", "--scope", "user") in runtime.stub.calls
    assert runtime.stub.calls.count(("claude", "plugin", "disable", "my-spec@myspec", "--scope", "user")) == 1
    assert ("codex", "plugin", "remove", "my-spec@myspec", "--json") in runtime.stub.calls
    assert ("codex", "plugin", "add", "my-spec@myspec", "--json") in runtime.stub.calls
    assert 'enabled = false' in runtime.texts[runtime.config_path]


def test_packed_myspec_doctor_reports_partial_update_read_only(management_documents):
    runtime = management_documents
    runtime.documents[runtime.stable / "package.json"]["version"] = NEXT_VERSION
    pending = {"command": "update", "targetVersion": NEXT_VERSION, "integrations": ["pi", "claude"],
               "completed": ["preflight", "npm", "pi"], "lastError": "claude_plugin_install_failed: original failure", "tokenHash": "secret"}
    runtime.documents[runtime.state_path] = {"mode": "release", "pendingOperation": pending}
    before = json.loads(json.dumps(runtime.documents[runtime.state_path]))
    diagnosed = runtime.run("doctor", "--all")
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report["npm"]["versionMismatch"] is True
    assert report["installation"]["pendingOperation"] == {
        "command": "update", "targetVersion": NEXT_VERSION, "integrations": ["pi", "claude"],
        "completed": ["preflight", "npm", "pi"], "lastError": "claude_plugin_install_failed: original failure",
    }
    assert report["installation"]["lock"] is None
    assert runtime.documents[runtime.state_path] == before
    assert runtime.writes == []
    token = "resume-secret"
    runtime.documents[runtime.state_path] = {"mode": "release", "pendingOperation": {
        "command": "update", "targetVersion": NEXT_VERSION, "integrations": [], "scopes": {}, "enabled": {},
        "completed": ["preflight", "npm"], "tokenHash": hashlib.sha256(token.encode()).hexdigest(),
    }}
    forged = runtime.run("update", "--_update-token", token)
    assert forged.returncode == 1
    assert "error: update_runtime_mismatch:" in forged.stderr
    assert runtime.documents[runtime.state_path]["pendingOperation"]["completed"] == ["preflight", "npm"]
    assert runtime.lock_calls == []


def test_packed_myspec_update_rejects_dev_mode_and_forged_resume(management_documents):
    runtime = management_documents
    runtime.documents[runtime.state_path] = {"mode": "dev", "source": str(runtime.root / "source"), "previousReleaseVersion": PACKAGE_VERSION}
    rejected = runtime.run("update")
    forged = runtime.run("update", "--_update-token", "forged")
    assert rejected.returncode == 1
    assert "update_requires_release_mode: run 'myspec init --release' first" in rejected.stderr
    assert forged.returncode == 1
    assert "error: invalid_update_token" in forged.stderr
    assert runtime.lock_calls[-1] == ("release", "operation")
    assert runtime.writes == []


def test_packed_myspec_initializes_and_removes_claude_legacy_plugin(management_documents):
    assert_initializes_and_removes_legacy(management_documents, "claude")


def test_packed_myspec_claude_init_keeps_legacy_when_stable_version_is_wrong(management_documents):
    assert_wrong_stable_version_keeps_legacy(management_documents, "claude")


def test_packed_myspec_claude_init_retries_incomplete_legacy_uninstall(management_documents):
    assert_retry_legacy_removal(management_documents, "claude", "noop")


def test_packed_myspec_claude_init_retries_interrupted_legacy_uninstall(management_documents):
    assert_retry_legacy_removal(management_documents, "claude", "interrupted")


def test_packed_myspec_doctor_reports_claude_marketplace_source_mismatch_read_only(management_documents):
    runtime = management_documents
    runtime.records("claude", [runtime.marketplace("claude", mismatch=True)], [runtime.plugin("claude")])
    diagnosed = runtime.run("doctor", "--claude")
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)["claude"]
    assert report["marketplaceSourceMismatch"] is True
    assert report["marketplaceRegistered"] is False
    assert report["sources"][0]["effective"] is False
    assert runtime.stub.calls == [("claude", "plugin", "marketplace", "list", "--json"), ("claude", "plugin", "list", "--json")]
    assert runtime.writes == []


def test_packed_myspec_explicit_claude_init_refreshes_disabled_stale_plugin(management_documents):
    runtime = management_documents
    queue_client_init(runtime, "claude", existing=True, enabled=False)
    result = runtime.run("init", "--claude")
    assert result.returncode == 0, result.stderr
    assert ("claude", "plugin", "update", "my-spec@myspec", "--scope", "user") in runtime.stub.calls
    assert ("claude", "plugin", "enable", "my-spec@myspec", "--scope", "user") in runtime.stub.calls
    assert runtime.writes == []


def test_packed_myspec_requires_explicit_claude_but_all_initializes_detected_claude(management_documents):
    assert_explicit_client_and_detected_all(management_documents, "claude")


def test_packed_myspec_initializes_and_removes_codex_legacy_plugin(management_documents):
    assert_initializes_and_removes_legacy(management_documents, "codex")


def test_packed_myspec_codex_init_keeps_legacy_when_stable_version_is_wrong(management_documents):
    assert_wrong_stable_version_keeps_legacy(management_documents, "codex")


def test_packed_myspec_codex_init_retries_incomplete_legacy_removal(management_documents):
    assert_retry_legacy_removal(management_documents, "codex", "noop")


def test_packed_myspec_codex_init_retries_interrupted_legacy_removal(management_documents):
    assert_retry_legacy_removal(management_documents, "codex", "interrupted")


def test_packed_myspec_requires_explicit_codex_but_all_initializes_detected_codex(management_documents):
    assert_explicit_client_and_detected_all(management_documents, "codex")


def test_packed_myspec_init_all_removes_legacy_plugins_and_doctor_reports_stable_sources(management_documents):
    runtime = management_documents
    for client in ("claude", "codex"):
        queue_client_init(runtime, client, legacy=True)
    initialized = runtime.run("init", "--all")
    assert initialized.returncode == 0, initialized.stderr
    for client, report in json.loads(initialized.stdout).items():
        assert report["removedLegacyPlugins"] == ["my-spec@my-agent-skills-marketplace"]
    diagnosed = runtime.run("doctor", "--all")
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    for client in ("claude", "codex"):
        assert [source["sourceKind"] for source in report[client]["sources"]] == ["stable"]
        assert report[client]["disabledSources"] == []
    assert runtime.writes == []


def test_packed_myspec_package_contains_single_codex_marketplace_and_four_skills() -> None:
    installed_package = PLUGIN_ROOT
    marketplace = json.loads((installed_package / '.agents' / 'plugins' / 'marketplace.json').read_text(encoding='utf-8'))
    assert marketplace == {'name': 'myspec', 'interface': {'displayName': 'MySpec'}, 'plugins': [{'name': 'my-spec', 'source': {'source': 'local', 'path': './'}, 'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Developer Tools'}]}
    assert [path.parent.name for path in sorted((installed_package / 'skills').glob('*/SKILL.md'))] == sorted(SKILL_NAMES)


def test_packed_myspec_requires_release_registration_before_first_codex_dev_init(management_documents):
    runtime = management_documents
    runtime.records("codex", [], [])
    # A linked installation is a path observation, not a simulated link action.
    runtime.realpaths[runtime.stable] = runtime.root / "source/plugins/my-spec"
    blocked = runtime.run("init", "--codex")
    assert blocked.returncode == 1
    assert blocked.stdout == ""
    assert "error: codex_dev_marketplace_unregistered: run 'myspec init --release', then 'myspec init --codex', then 'myspec init --dev'" in blocked.stderr
    assert runtime.stub.calls == [("codex", "plugin", "marketplace", "list", "--json")]
    assert runtime.writes == []
    # A registered release source is the valid input for explicit initialization;
    # actual release/dev installation transitions remain in TestMySpec.
    runtime.realpaths.clear()
    queue_client_init(runtime, "codex")
    initialized = runtime.run("init", "--codex")
    assert initialized.returncode == 0, initialized.stderr
    runtime.realpaths[runtime.stable] = runtime.root / "source/plugins/my-spec"
    runtime.stub.calls.clear()
    queue_client_init(runtime, "codex", existing=True)
    initialized_again = runtime.run("init", "--codex")
    assert initialized_again.returncode == 0, initialized_again.stderr
    assert not any(call[:4] == ("codex", "plugin", "marketplace", "add") for call in runtime.stub.calls)
    assert json.loads(initialized_again.stdout)["source"] == str(runtime.stable)


@pytest.mark.parametrize('disabled', [False, True])
def test_packed_myspec_mode_switch_does_not_install_missing_or_disabled_codex(management_documents, disabled: bool):
    runtime = management_documents
    plugins = [runtime.plugin("codex", enabled=False)] if disabled else []
    marketplaces = [runtime.marketplace("codex")] if disabled else []
    runtime.records("codex", marketplaces, plugins)
    if disabled:
        runtime.texts[runtime.config_path] = '[plugins."my-spec@myspec"]\nenabled = false\n'
    before = dict(runtime.texts)
    source, _ = runtime.source_documents()
    for stage in ("dev", "release"):
        token = runtime.switch_input(stage, source)
        args = ["init", f"--{stage}", "--_switch-token", token]
        if stage == "dev":
            args.extend(["--source", source])
        result = runtime.run(*args)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["codex"] == "not-installed"
    assert not any(call[:3] in {("codex", "plugin", "add"), ("codex", "plugin", "remove")} for call in runtime.stub.calls)
    assert runtime.texts == before
    assert runtime.stub.responses == []


@pytest.mark.parametrize('disabled', [False, True])
def test_packed_myspec_mode_switch_does_not_install_missing_or_disabled_claude(management_documents, disabled: bool):
    runtime = management_documents
    plugins = [runtime.plugin("claude", enabled=False)] if disabled else []
    marketplaces = [runtime.marketplace("claude")] if disabled else []
    runtime.records("claude", marketplaces, plugins)
    source, _ = runtime.source_documents()
    for stage in ("dev", "release"):
        token = runtime.switch_input(stage, source)
        args = ["init", f"--{stage}", "--_switch-token", token]
        if stage == "dev":
            args.extend(["--source", source])
        result = runtime.run(*args)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["claude"] == "not-installed"
    assert not any(call[:3] in {("claude", "plugin", "install"), ("claude", "plugin", "enable")} or call[:4] == ("claude", "plugin", "marketplace", "add") for call in runtime.stub.calls)
    assert runtime.stub.responses == []


def test_packed_myspec_claude_reinstall_failure_does_not_report_refreshed(management_documents):
    runtime = management_documents
    runtime.records("claude", [runtime.marketplace("claude")], [runtime.plugin("claude")])
    runtime.response(("claude", "plugin", "marketplace", "update", "myspec"))
    runtime.response(("claude", "plugin", "uninstall", "my-spec@myspec", "--scope", "user", "--keep-data"))
    runtime.response(("claude", "plugin", "install", "my-spec@myspec", "--scope", "user"), code=1, stderr="simulated install failure")
    source, _ = runtime.source_documents()
    token = runtime.switch_input("dev", source)
    failed = runtime.run("init", "--dev", "--source", source, "--_switch-token", token)
    assert failed.returncode == 1
    assert failed.stdout == ""
    assert "claude_plugin_install_failed: simulated install failure" in failed.stderr
    assert "refreshed" not in failed.stderr
    assert ("claude", "plugin", "uninstall", "my-spec@myspec", "--scope", "user", "--keep-data") in runtime.stub.calls
    assert ("claude", "plugin", "install", "my-spec@myspec", "--scope", "user") in runtime.stub.calls
    assert ("claude", "plugin", "enable", "my-spec@myspec", "--scope", "user") not in runtime.stub.calls


def test_packed_myspec_doctor_uses_actual_installation_not_mode_state(management_documents):
    runtime = management_documents
    runtime.documents[runtime.state_path] = {"mode": "dev", "source": "C:/not-the-package", "previousReleaseVersion": "9.9.9"}
    before = dict(runtime.documents[runtime.state_path])
    diagnosed = runtime.run("doctor")
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report["mode"] == "release"
    assert report["toolchain"] == {"mode": "release", "packageName": "@liuli195/myspec", "packageVersion": PACKAGE_VERSION}
    assert report["source"] == str(runtime.stable)
    assert report["npm"]["linked"] is False
    assert report["npm"]["versionMismatch"] is False
    assert not {"pi", "claude", "codex"}.intersection(report)
    assert runtime.documents[runtime.state_path] == before
    assert runtime.writes == []
    all_agents = runtime.run("doctor", "--all")
    assert all_agents.returncode == 0, all_agents.stderr
    assert "pi" not in json.loads(all_agents.stdout)


def test_packed_myspec_doctor_reports_actual_package_version_mismatch(management_documents):
    runtime = management_documents
    runtime.documents[runtime.stable / "package.json"]["version"] = NEXT_VERSION
    diagnosed = runtime.run("doctor")
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report["cliVersion"] == PACKAGE_VERSION
    assert report["npm"]["packageVersion"] == NEXT_VERSION
    assert report["npm"]["versionMismatch"] is True
    assert runtime.writes == []


def test_packed_myspec_rejects_invalid_mode_switches(management_documents):
    runtime = management_documents
    invalid_source = runtime.run("init", "--dev", "--source", runtime.root / "missing")
    assert invalid_source.returncode == 1
    assert "error: invalid_dev_source: missing" in invalid_source.stderr
    assert runtime.state_path not in runtime.documents
    source, package = runtime.source_documents()
    runtime.response(("git", "rev-parse", "--show-toplevel"), stdout=str(source.parent))
    borrowed_root = runtime.run("init", "--dev", "--source", source)
    assert borrowed_root.returncode == 1
    assert "error: invalid_dev_source: git_root" in borrowed_root.stderr
    marketplace = runtime.documents[package / ".agents/plugins/marketplace.json"]
    marketplace["plugins"][0]["source"]["path"] = "../wrong"
    malformed = runtime.run("init", "--dev", "--source", source)
    assert malformed.returncode == 1
    assert "error: invalid_dev_source: marketplace" in malformed.stderr
    marketplace["plugins"][0]["source"]["path"] = "./"
    runtime.documents[package / "package.json"]["name"] = "@liuli195/myspec-helper"
    invalid_package = runtime.run("init", "--dev", "--source", source)
    assert invalid_package.returncode == 1
    assert "error: invalid_dev_source: package_manifest" in invalid_package.stderr
    result = runtime.run("init", "--release")
    assert result.returncode == 1
    assert "error: missing_previous_release_version" in result.stderr
    assert runtime.writes == []


@pytest.mark.parametrize('case', ['package-name', 'package-version', 'bin-entry', 'bin-file', 'python-entry', 'management-entry', 'skill-file', 'codex-marketplace', 'claude-marketplace', 'self-claude-marketplace', 'plugin-manifest'])
def test_packed_myspec_dev_preflight_rejects_incomplete_source_before_link_or_state(management_documents, case: str):
    runtime = management_documents
    source, package = runtime.source_documents()
    manifest = runtime.documents[package / "package.json"]
    if case == "package-name":
        manifest["name"] = "@liuli195/not-myspec"
    elif case == "package-version":
        manifest["version"] = ""
    elif case == "bin-entry":
        manifest["bin"] = {"myspec": "./bin/other.js"}
    elif case in {"bin-file", "python-entry", "management-entry", "skill-file"}:
        relative = {"bin-file": "bin/myspec.js", "python-entry": "python/spec_ops.py", "management-entry": "python/management.py", "skill-file": "skills/my-spec-audit/SKILL.md"}[case]
        runtime.files.remove(package / relative)
    elif case == "codex-marketplace":
        runtime.documents[package / ".agents/plugins/marketplace.json"]["plugins"][0]["source"]["path"] = "../wrong"
    elif case in {"claude-marketplace", "self-claude-marketplace"}:
        runtime.documents[package / ".claude-plugin/marketplace.json"]["plugins"][0]["source"] = "../wrong"
    else:
        runtime.documents[package / ".codex-plugin/plugin.json"]["version"] = "9.9.9"
    rejected = runtime.run("init", "--dev", "--source", source)
    assert rejected.returncode == 1
    assert "error: invalid_dev_source:" in rejected.stderr
    assert runtime.state_path not in runtime.documents
    assert ("npm", "link") not in runtime.stub.calls
    assert runtime.writes == []


def windows_py_launcher() -> Path:
    base_executable = Path(getattr(sys, "_base_executable", sys.executable))
    candidates = (
        base_executable.parent.parent / "Launcher" / "py.exe",
        Path(os.environ.get("SystemRoot", "C:/Windows")) / "py.exe",
        Path(shutil.which("py") or ""),
    )
    launcher = next(
        (path for path in candidates if path.is_file() and "WindowsApps" not in path.parts),
        None,
    )
    assert launcher is not None
    return launcher


def test_windows_py_launcher_uses_base_interpreter_from_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    base_python = tmp_path / 'Python312' / 'python.exe'
    launcher = tmp_path / 'Launcher' / 'py.exe'
    original_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda path: path == launcher or original_is_file(path))
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'venv' / 'Scripts' / 'python.exe'))
    monkeypatch.setattr(sys, '_base_executable', str(base_python))
    assert windows_py_launcher() == launcher


def test_spec_ops_preview_preserves_modified_requirement_order(spec_documents) -> None:
    documents = spec_documents
    tmp_path = documents.root
    write, ready_state, apply_ready = documents.write, documents.ready_state, documents.apply
    titles = ('首部', '中部', '尾部')

    def preview_delta(root: Path, specs: Path, delta: Path) -> tuple[Path, Path]:
        preview = root / 'preview'
        work = root / 'work'
        conflicts = root / 'conflicts.json'
        write(conflicts, '[]')
        documents.seed_state(work)
        for result in (run_python(SPEC_OPS, 'state-set-conflicts', work, conflicts, 'specs-fingerprint', 'input-fingerprint'), run_python(SPEC_OPS, 'validate-delta', delta, specs), run_python(SPEC_OPS, 'apply-delta', specs, delta, preview, work, 'specs-fingerprint', 'input-fingerprint')):
            assert result.returncode == 0, result.stderr
        return (preview, work)
    for target in titles:
        root = tmp_path / target
        specs = root / 'specs'
        delta = root / 'delta'
        write(specs / 'accounts' / 'spec.md', main_spec('Accounts', *(requirement(title, f'保留{title}') for title in titles)))
        write(delta / 'accounts' / 'spec.md', f'## MODIFIED Requirements\n\n### Requirement: {target}\n\n系统 MUST 更新{target}。\n\n#### Scenario: 修改{target}\n\n- **WHEN** 用户修改{target}\n- **THEN** 系统保留需求顺序\n')
        preview, work = preview_delta(root, specs, delta)
        preview_text = (preview / 'accounts' / 'spec.md').read_text(encoding='utf-8')
        assert [line.removeprefix('### Requirement: ') for line in preview_text.splitlines() if line.startswith('### Requirement: ')] == list(titles)
        assert f'系统 MUST 更新{target}。' in preview_text
        assert f'系统 MUST 保留{target}。' not in preview_text
        diff = run_python(SPEC_OPS, 'diff', specs, preview)
        assert diff.returncode == 0, diff.stderr
        assert f'-### Requirement: {target}' not in diff.stdout
        assert f'+### Requirement: {target}' not in diff.stdout
        repeated_preview, _ = preview_delta(root / 'repeat', preview, delta)
        assert (repeated_preview / 'accounts' / 'spec.md').read_bytes() == (preview / 'accounts' / 'spec.md').read_bytes()
        repeated_diff = run_python(SPEC_OPS, 'diff', preview, repeated_preview)
        assert repeated_diff.returncode == 0, repeated_diff.stderr
        assert repeated_diff.stdout == ''
    root = tmp_path / 'cross-capability'
    specs = root / 'specs'
    delta = root / 'delta'
    write(specs / 'source' / 'spec.md', main_spec('Source', requirement('移动项', '留在来源')))
    write(specs / 'target' / 'spec.md', main_spec('Target', requirement('现有项', '留在目标')))
    write(delta / 'target' / 'spec.md', '## MODIFIED Requirements\n\n### Requirement: 移动项\n\n系统 MUST 移入目标能力。\n\n#### Scenario: 跨能力修改\n\n- **WHEN** 用户修改其他能力中的需求\n- **THEN** 系统把需求移入目标能力\n')
    preview, work = preview_delta(root, specs, delta)
    assert '### Requirement: 移动项' not in (preview / 'source' / 'spec.md').read_text(encoding='utf-8')
    target_text = (preview / 'target' / 'spec.md').read_text(encoding='utf-8')
    assert target_text.index('### Requirement: 现有项') < target_text.index('### Requirement: 移动项')


def test_spec_ops_cli_validates_previews_all_delta_operations_and_diffs(spec_documents) -> None:
    documents = spec_documents
    tmp_path = documents.root
    write, ready_state, apply_ready = documents.write, documents.ready_state, documents.apply
    specs = tmp_path / 'specs'
    delta = tmp_path / 'delta'
    preview = tmp_path / 'preview'
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('旧登录', '允许登录'), requirement('旧导出', '允许导出'), requirement('个人资料', '显示姓名')))
    write(delta / 'accounts' / 'spec.md', '# Accounts\n\n## Purpose\n\n描述 Accounts 的外部行为。\n\n## RENAMED Requirements\n\nFROM: 旧登录\nTO: 密码登录\n\n## REMOVED Requirements\n\n### Requirement: 旧导出\n\n## MODIFIED Requirements\n\n### Requirement: 个人资料\n\n系统 SHALL 显示姓名和头像。\n\n#### Scenario: 查看资料\n\n- **WHEN** 用户打开个人资料\n- **THEN** 系统显示姓名和头像\n\n## ADDED Requirements\n\n### Requirement: 注销\n\n系统 MUST 允许用户注销。\n\n#### Scenario: 主动注销\n\n- **WHEN** 用户选择注销\n- **THEN** 系统结束会话\n')
    work = ready_state(SPEC_OPS, tmp_path / 'state')
    assert run_python(SPEC_OPS, 'validate-main', specs).returncode == 0
    assert run_python(SPEC_OPS, 'validate-delta', delta, specs).returncode == 0
    applied = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert applied.returncode == 0, applied.stderr
    assert run_python(SPEC_OPS, 'validate-main', preview).returncode == 0
    merged = (preview / 'accounts' / 'spec.md').read_text(encoding='utf-8')
    assert '### Requirement: 密码登录' in merged
    assert '### Requirement: 旧登录' not in merged
    assert '### Requirement: 旧导出' not in merged
    assert '系统 SHALL 显示姓名和头像。' in merged
    assert '### Requirement: 注销' in merged
    diff = run_python(SPEC_OPS, 'diff', specs, preview)
    assert diff.returncode == 0
    assert '-### Requirement: 旧登录' in diff.stdout
    assert '+### Requirement: 密码登录' in diff.stdout
    assert '旧导出' in diff.stdout
    assert '+### Requirement: 注销' in diff.stdout
    repeated_work = ready_state(SPEC_OPS, tmp_path / 'repeated-state')
    repeated_preview = tmp_path / 'repeated-preview'
    # The rendered result is the next merge's input; physical replacement and
    # repeated final apply remain covered by TestMySpec.
    repeated = apply_ready(SPEC_OPS, preview, delta, repeated_preview, repeated_work)
    assert repeated.returncode == 0, repeated.stderr
    assert (repeated_preview / 'accounts' / 'spec.md').read_bytes() == (preview / 'accounts' / 'spec.md').read_bytes()
    repeated_diff = run_python(SPEC_OPS, 'diff', preview, repeated_preview)
    assert repeated_diff.returncode == 0, repeated_diff.stderr
    assert repeated_diff.stdout == ''


def test_spec_add_deterministic_post_analysis_flow_previews_and_diffs(spec_documents) -> None:
    documents = spec_documents
    root = documents.root / 'add'
    specs, delta, preview = root / 'specs', root / 'delta', root / 'preview'
    login = requirement('登录', '允许用户登录')
    documents.write(specs / 'accounts' / 'spec.md', main_spec('Accounts', login))
    documents.write(delta / 'accounts' / 'spec.md', '## ADDED Requirements\n\n### Requirement: 注销\n\n系统 MUST 允许用户注销。\n\n#### Scenario: 主动注销\n\n- **WHEN** 用户选择注销\n- **THEN** 系统结束会话\n')
    work = documents.ready_state(SPEC_OPS, root)
    validated = run_python(SPEC_OPS, 'validate-delta', delta, specs)
    assert validated.returncode == 0, validated.stderr
    generated = documents.apply(SPEC_OPS, specs, delta, preview, work)
    assert generated.returncode == 0, generated.stderr
    assert run_python(SPEC_OPS, 'validate-main', preview).returncode == 0
    diff = run_python(SPEC_OPS, 'diff', specs, preview)
    assert diff.returncode == 0, diff.stderr
    assert '+### Requirement: 注销' in diff.stdout
    merged = (preview / 'accounts' / 'spec.md').read_text(encoding='utf-8')
    assert '### Requirement: 注销' in merged
    assert login.strip() in merged


def test_spec_ops_cli_rejects_invalid_specs_and_delta_references(spec_documents) -> None:
    documents = spec_documents
    tmp_path = documents.root
    write, ready_state, apply_ready = documents.write, documents.ready_state, documents.apply
    specs = tmp_path / 'specs'
    delta = tmp_path / 'delta'
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('登录', '允许登录').replace('MUST', '必须')))
    invalid_main = run_python(SPEC_OPS, 'validate-main', specs)
    assert invalid_main.returncode != 0
    assert 'missing_must_or_shall: 登录' in invalid_main.stderr
    assert 'Traceback' not in invalid_main.stderr
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('登录', '允许登录')))
    write(delta / 'accounts' / 'spec.md', '## MODIFIED Requirements\n\n### Requirement: 不存在的需求\n\n系统 MUST 返回结果。\n\n#### Scenario: 正常流程\n\n- **WHEN** 用户执行操作\n- **THEN** 系统返回结果\n')
    invalid_delta = run_python(SPEC_OPS, 'validate-delta', delta, specs)
    assert invalid_delta.returncode != 0
    assert 'modified_source_missing: 不存在的需求' in invalid_delta.stderr
    assert 'Traceback' not in invalid_delta.stderr


def test_spec_ops_cli_rejects_incomplete_or_out_of_order_conflict_state(spec_documents) -> None:
    documents = spec_documents
    tmp_path = documents.root
    write, ready_state, apply_ready = documents.write, documents.ready_state, documents.apply
    work = tmp_path / 'fresh-session' / '.local' / 'spec-work'
    documents.seed_state(work, 'audit')
    count_only = tmp_path / 'count-only.json'
    write(count_only, '{"count": 13}')
    incomplete = run_python(SPEC_OPS, 'state-set-conflicts', work, count_only, 'specs-fingerprint', 'input-fingerprint')
    assert incomplete.returncode != 0
    assert 'conflicts_must_be_array' in incomplete.stderr
    duplicate_file = tmp_path / 'duplicates.json'
    duplicate = {'id': 'same', 'candidate': '候选', 'evidence': ['spec.md:1'], 'reason': '冲突', 'recommendation': '采用建议'}
    write(duplicate_file, json.dumps([duplicate, duplicate], ensure_ascii=False))
    duplicates = run_python(SPEC_OPS, 'state-set-conflicts', work, duplicate_file, 'specs-fingerprint', 'input-fingerprint')
    assert duplicates.returncode != 0
    assert 'duplicate_conflict_id: same' in duplicates.stderr
    missing_evidence_file = tmp_path / 'missing-evidence.json'
    write(missing_evidence_file, json.dumps([{**duplicate, 'id': 'missing', 'evidence': []}], ensure_ascii=False))
    missing = run_python(SPEC_OPS, 'state-set-conflicts', work, missing_evidence_file, 'specs-fingerprint', 'input-fingerprint')
    assert missing.returncode != 0
    assert 'invalid_conflict_field: missing: evidence' in missing.stderr
    premature = run_python(SPEC_OPS, 'state-decide', work, 'same', 'accept', 'specs-fingerprint', 'input-fingerprint')
    assert premature.returncode != 0
    assert 'invalid_state: expected_WAITING_DECISION' in premature.stderr
    valid_file = tmp_path / 'valid.json'
    write(valid_file, json.dumps([duplicate], ensure_ascii=False))
    assert run_python(SPEC_OPS, 'state-set-conflicts', work, valid_file, 'specs-fingerprint', 'input-fingerprint').returncode == 0
    stale = run_python(SPEC_OPS, 'state-current', work, 'changed-specs', 'input-fingerprint')
    assert stale.returncode != 0
    assert 'specs_fingerprint_changed' in stale.stderr
    specs = tmp_path / 'specs'
    delta = tmp_path / 'delta'
    preview = tmp_path / 'preview'
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('登录', '允许登录')))
    delta.mkdir()
    blocked = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert blocked.returncode != 0
    assert 'invalid_state: expected_READY_TO_APPLY' in blocked.stderr
    state_path = work / 'current' / 'state.json'
    inconsistent = json.loads(state_path.read_text(encoding='utf-8'))
    inconsistent['status'] = 'READY_TO_APPLY'
    state_path.write_text(json.dumps(inconsistent), encoding='utf-8')
    tampered = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert tampered.returncode != 0
    assert 'invalid_state_document' in tampered.stderr


def test_spec_ops_cli_records_each_supported_conflict_decision(spec_documents) -> None:
    documents = spec_documents
    tmp_path = documents.root
    write, ready_state, apply_ready = documents.write, documents.ready_state, documents.apply
    work = tmp_path / '.local' / 'spec-work'
    conflicts_file = tmp_path / 'conflicts.json'
    conflicts = [{'id': f'conflict-{index}', 'candidate': f'候选 {index}', 'evidence': [f'spec.md:{index}'], 'reason': '需要决定', 'recommendation': '采用建议'} for index in range(4)]
    write(conflicts_file, json.dumps(conflicts, ensure_ascii=False))
    documents.seed_state(work)
    assert run_python(SPEC_OPS, 'state-set-conflicts', work, conflicts_file, 'specs-fingerprint', 'input-fingerprint').returncode == 0
    assert run_python(SPEC_OPS, 'state-decide', work, 'conflict-0', 'accept', 'specs-fingerprint', 'input-fingerprint').returncode == 0
    repeated = run_python(SPEC_OPS, 'state-decide', work, 'conflict-0', 'accept', 'specs-fingerprint', 'input-fingerprint')
    assert repeated.returncode != 0
    assert 'unexpected_conflict_id: expected_conflict-1: conflict-0' in repeated.stderr
    assert run_python(SPEC_OPS, 'state-decide', work, 'conflict-1', 'ignore', 'specs-fingerprint', 'input-fingerprint').returncode == 0
    modified = run_python(SPEC_OPS, 'state-decide', work, 'conflict-2', 'accept-modified', 'specs-fingerprint', 'input-fingerprint', '--modified-content', '修改后的完整候选')
    assert modified.returncode == 0, modified.stderr
    final = run_python(SPEC_OPS, 'state-decide', work, 'conflict-3', 'defer', 'specs-fingerprint', 'input-fingerprint')
    assert final.returncode == 0, final.stderr
    assert json.loads(final.stdout) == {'status': 'READY_TO_APPLY', 'total': 4, 'decided': 4, 'remaining': 0}
    state = json.loads((work / 'current' / 'state.json').read_text(encoding='utf-8'))
    assert [item['decision'] for item in state['decisions']] == ['accept', 'ignore', 'accept-modified', 'defer']
    assert state['decisions'][2]['modifiedContent'] == '修改后的完整候选'


def test_spec_ops_cli_initializes_a_new_capability_from_an_empty_spec_library(spec_documents) -> None:
    documents = spec_documents
    tmp_path = documents.root
    write, ready_state, apply_ready = documents.write, documents.ready_state, documents.apply
    specs = tmp_path / 'missing-specs'
    delta = tmp_path / 'delta'
    preview = tmp_path / 'preview'
    write(delta / 'notifications' / 'spec.md', '# Notifications\n\n## Purpose\n\n描述通知的外部行为。\n\n## ADDED Requirements\n\n### Requirement: 接收通知\n\n系统 MUST 向订阅用户发送通知。\n\n#### Scenario: 新消息\n\n- **WHEN** 新消息到达\n- **THEN** 系统向订阅用户发送通知\n')
    work = ready_state(SPEC_OPS, tmp_path / 'state')
    validated = run_python(SPEC_OPS, 'validate-delta', delta, specs)
    assert validated.returncode == 0, validated.stderr
    applied = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert applied.returncode == 0, applied.stderr
    assert run_python(SPEC_OPS, 'validate-main', preview).returncode == 0
    assert '### Requirement: 接收通知' in (preview / 'notifications' / 'spec.md').read_text(encoding='utf-8')


@pytest.mark.parametrize('duplicate_location', ('same-file', 'cross-file'))
def test_spec_ops_preview_auto_merges_identical_duplicate_requirements_but_main_validation_stays_strict(spec_documents, duplicate_location: str) -> None:
    documents = spec_documents
    tmp_path = documents.root
    write, ready_state, apply_ready = documents.write, documents.ready_state, documents.apply
    specs = tmp_path / 'specs'
    delta = tmp_path / 'delta'
    preview = tmp_path / 'preview'
    duplicate = requirement('登录', '允许用户登录')
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', duplicate, *([duplicate] if duplicate_location == 'same-file' else [])))
    if duplicate_location == 'cross-file':
        write(specs / 'sessions' / 'spec.md', main_spec('Sessions', duplicate))
    delta.mkdir()
    strict = run_python(SPEC_OPS, 'validate-main', specs)
    assert strict.returncode != 0
    expected_error = 'duplicate_requirement: 登录' if duplicate_location == 'same-file' else 'duplicate_requirement_global: 登录'
    assert expected_error in strict.stderr
    work = ready_state(SPEC_OPS, tmp_path / 'state', 'review')
    merged = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert merged.returncode == 0, merged.stderr
    assert run_python(SPEC_OPS, 'validate-main', preview).returncode == 0
    assert (preview / 'accounts' / 'spec.md').read_text(encoding='utf-8').count('### Requirement: 登录') == 1
    diff = run_python(SPEC_OPS, 'diff', specs, preview)
    assert diff.returncode == 0
    assert '-### Requirement: 登录' in diff.stdout


@pytest.mark.parametrize('evidence,error', [
    ('no-confirmation', 'no_active_session_confirmation_required'),
    ('legacy-no-baseline', 'abort_specs_baseline_mismatch'),
    ('legacy-no-path', 'invalid_state_context'),
    ('legacy-unknown-status', 'invalid_state_document'),
    ('unknown-phase', 'application_recovery_required'),
])
def test_myspec_recovery_rejects_incomplete_state_documents(spec_documents, monkeypatch, evidence: str, error: str) -> None:
    documents = spec_documents
    target = documents.root
    work = documents.ready_state(SPEC_OPS, target)
    specs = target / 'myspec' / 'specs'
    delta = work / 'current' / 'delta'
    preview = work / 'current' / 'preview'
    documents.write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('登录', '允许登录')))
    documents.write(delta / 'accounts' / 'spec.md', '## MODIFIED Requirements\n\n' + requirement('登录', '允许密码登录'))
    previewed = documents.apply(SPEC_OPS, specs, delta, preview, work)
    assert previewed.returncode == 0, previewed.stderr
    state_path = work / 'current' / 'state.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    state.update(targetWorktree=str(target), sessionId='a' * 32)
    lock = work / 'lock'
    documents.write(lock, json.dumps({'command': 'add', 'sessionId': state['sessionId'], 'workRoot': str(work)}))
    if evidence.startswith('legacy-'):
        state.pop('sessionId')
        state.pop('applicationPhase')
        documents.write(lock, 'add')
    if evidence == 'legacy-no-baseline':
        state['specsContentFingerprint'] = None
    elif evidence == 'legacy-no-path':
        state.pop('previewRoot')
    elif evidence == 'legacy-unknown-status':
        state['status'] = 'UNRECOGNIZED'
    elif evidence == 'unknown-phase':
        state['applicationPhase'] = 'UNRECOGNIZED'
    documents.save_json(state_path, state)
    for command, stdout in ((('git', 'rev-parse', '--show-toplevel'), str(target)),
                            (('git', 'rev-parse', 'HEAD'), 'a' * 40)):
        documents.stub.defaults.append((command, completed(command, stdout=stdout)))

    def state_identity(path):
        # Only the saved-state observation is reached by these refusals. Lock
        # inode identity and archive/rename operations stay in TestMySpec.
        assert path == state_path
        return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    monkeypatch.setattr(documents.module, '_file_identity', state_identity)
    state_bytes, lock_bytes = state_path.read_bytes(), lock.read_bytes()
    draft_path = delta / 'accounts' / 'spec.md'
    draft = draft_path.read_bytes()
    before, directories = dict(documents.texts), set(documents.directories)
    arguments = ['state-abort', work, target, specs, delta, preview,
                 hashlib.sha256(state_bytes).hexdigest(), 'add', '--lock-identity', '0' * 64]
    if evidence != 'no-confirmation':
        arguments.append('--confirm-no-active-session')
    refused = run_python(SPEC_OPS, *arguments)
    assert refused.returncode != 0
    assert error in refused.stderr
    assert state_path.read_bytes() == state_bytes
    assert lock.read_bytes() == lock_bytes
    assert draft_path.read_bytes() == draft
    assert documents.texts == before
    assert documents.directories == directories
    assert not (work / 'aborted').exists()


def test_skill_entries_route_add_review_and_audit_with_safe_boundaries() -> None:
    skill = (PLUGIN_ROOT / "skills" / "my-spec" / "SKILL.md").read_text(encoding="utf-8")
    assert "name: my-spec" in skill
    assert "my-spec-add" in skill and "references/add-document.md" in skill
    assert "my-spec-review" in skill and "references/review.md" in skill
    assert "my-spec-audit" in skill and "references/audit.md" in skill

    for name in SKILL_NAMES:
        entry = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert f"name: {name}" in entry
    for name in SKILL_NAMES[1:]:
        entry = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "../my-spec/SKILL.md" in entry
        assert "myspec ..." in entry
        assert "spec_ops.py" not in entry

    assert not (PLUGIN_ROOT / "skills" / "my-spec" / "scripts").exists()

    add = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "add-document.md").read_text(encoding="utf-8")
    review = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "review.md").read_text(encoding="utf-8")
    audit = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "audit.md").read_text(encoding="utf-8")
    rules = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "myspec-rules.md").read_text(encoding="utf-8")
    for procedure in (add, review, audit):
        assert "一次只展示一条" in procedure
        assert "完整差异" in procedure
        assert "最终确认" in procedure
        assert "myspec " in procedure
        assert "spec_ops.py" not in procedure
    assert "只读取 `myspec/specs/`" in review
    assert "不得读取仓库其他文件" in review
    assert "git ls-files --cached --others --exclude-standard" in audit
    assert ".local/spec-work/" in skill and ".local/spec-work/" in audit and ".local/spec-work/" in rules
    assert ".spec-work/" not in skill + audit + rules
    assert "Agent" in add and "相关证据" in add
    assert "指定文档" not in add
    for procedure in (add, review, audit):
        assert "state-set-conflicts" in procedure
        assert "首次展示" in procedure
        assert "禁止重新" in procedure
    assert "<conflicts-file>" in rules
    assert "<conflicts-json>" not in rules
    assert "accept-modified" in rules
    assert "--modified-content <完整候选正文>" in rules


def test_plugin_sync_delegates_all_myspec_lifecycle_work_to_myspec_cli() -> None:
    root = PLUGIN_SYNC_ROOT
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    references = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted((root / "references").glob("*.md"))
    }

    for command in (
        "myspec doctor --all",
        "myspec init --claude",
        "myspec init --codex",
        "myspec init --all",
        "myspec init --dev",
        "myspec init --release",
        "myspec update",
    ):
        assert f"`{command}`" in skill
    assert "CLI（命令行程序）拥有" in skill
    assert "If the request only contains MySpec（自有规格）" in skill
    assert "remaining non-MySpec（自有规格） scope" in skill
    for name in ("check.md", "update-claude.md", "update-codex.md"):
        assert "MySpec（自有规格）不适用" in references[name]
    assert "spec_ops.py" not in skill + "\n".join(references.values())


def test_plugin_uses_host_native_skill_paths() -> None:
    assert not (PLUGIN_ROOT / "scripts").exists()
    assert not (PLUGIN_ROOT / "extensions").exists()

    package = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["name"] == "@liuli195/myspec"
    assert package["bin"] == {"myspec": "./bin/myspec.js"}
    assert package["publishConfig"] == {"access": "public"}
    assert package["repository"] == {
        "type": "git",
        "url": "https://github.com/liuli195/my-agent-skills",
        "directory": "plugins/my-spec",
    }
    assert "pi" not in package
    assert "peerDependencies" not in package
    assert "dependencies" not in package


def test_my_spec_plugin_is_discoverable_by_claude_and_codex() -> None:
    package_version = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    spec = (REPO_ROOT / "myspec" / "specs" / "my-spec" / "spec.md").read_text(encoding="utf-8")
    assert "/my-spec:my-spec-add" in spec
    assert "$my-spec-add" in spec
    for host in (".claude-plugin", ".codex-plugin"):
        manifest = json.loads((PLUGIN_ROOT / host / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["name"] == "my-spec"
        assert manifest["version"] == package_version
        assert manifest["skills"] == "./skills"

    claude_marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    codex_marketplace = json.loads((REPO_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    assert all(plugin["name"] != "my-spec" for plugin in claude_marketplace["plugins"])
    assert all(plugin["name"] != "my-spec" for plugin in codex_marketplace["plugins"])


def test_myspec_final_apply_requires_the_confirmed_preview(spec_documents) -> None:
    documents = spec_documents
    tmp_path = documents.root
    write, ready_state, apply_ready = documents.write, documents.ready_state, documents.apply
    specs = tmp_path / 'specs'
    delta = tmp_path / 'delta'
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('登录', '允许登录')))
    write(delta / 'accounts' / 'spec.md', '## MODIFIED Requirements\n\n### Requirement: 登录\n\n系统 MUST 允许密码登录。\n\n#### Scenario: 密码正确\n\n- **WHEN** 用户提交正确密码\n- **THEN** 系统创建会话\n')
    work = ready_state(SPEC_OPS, tmp_path / 'state')
    before = (specs / 'accounts' / 'spec.md').read_bytes()
    applied = apply_ready(SPEC_OPS, specs, delta, specs, work)
    assert applied.returncode != 0
    assert 'preview_missing' in applied.stderr
    assert (specs / 'accounts' / 'spec.md').read_bytes() == before


def test_myspec_final_apply_rejects_bound_content_drift_after_preview(spec_documents) -> None:
    documents = spec_documents
    tmp_path = documents.root
    write, ready_state, apply_ready = documents.write, documents.ready_state, documents.apply
    for changed, expected_error in (('specs', 'specs_content_changed'), ('delta', 'input_content_changed'), ('preview', 'preview_content_changed')):
        root = tmp_path / changed
        specs = root / 'specs'
        delta = root / 'delta'
        preview = root / 'preview'
        spec_path = specs / 'accounts' / 'spec.md'
        delta_path = delta / 'accounts' / 'spec.md'
        write(spec_path, main_spec('Accounts', requirement('登录', '允许登录')))
        write(delta_path, '## MODIFIED Requirements\n\n### Requirement: 登录\n\n系统 MUST 允许密码登录。\n\n#### Scenario: 密码正确\n\n- **WHEN** 用户提交正确密码\n- **THEN** 系统创建会话\n')
        work = ready_state(SPEC_OPS, root / 'state')
        previewed = apply_ready(SPEC_OPS, specs, delta, preview, work)
        assert previewed.returncode == 0, previewed.stderr
        if changed == 'specs':
            write(spec_path, main_spec('Accounts', requirement('登录', '允许其他登录')))
        elif changed == 'delta':
            write(delta_path, delta_path.read_text(encoding='utf-8').replace('密码登录', '其他登录', 1))
        else:
            preview_path = preview / 'accounts' / 'spec.md'
            write(preview_path, preview_path.read_text(encoding='utf-8').replace('密码登录', '其他登录', 1))
        expected_specs = spec_path.read_bytes()
        applied = apply_ready(SPEC_OPS, specs, delta, specs, work)
        assert applied.returncode != 0
        assert expected_error in applied.stderr
        assert spec_path.read_bytes() == expected_specs


def test_myspec_final_apply_rejects_unconfirmed_implementation_identity(spec_documents) -> None:
    documents = spec_documents
    tmp_path = documents.root
    write, ready_state, apply_ready = documents.write, documents.ready_state, documents.apply
    specs = tmp_path / 'specs'
    delta = tmp_path / 'delta'
    preview = tmp_path / 'preview'
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('登录', '允许登录')))
    write(delta / 'accounts' / 'spec.md', '## MODIFIED Requirements\n\n### Requirement: 登录\n\n系统 MUST 允许密码登录。\n\n#### Scenario: 密码正确\n\n- **WHEN** 用户提交正确密码\n- **THEN** 系统创建会话\n')
    work = ready_state(SPEC_OPS, tmp_path / 'state')
    previewed = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert previewed.returncode == 0, previewed.stderr
    state_path = work / 'current' / 'state.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    state['implementationIdentity'] = None
    state_path.write_text(json.dumps(state), encoding='utf-8')
    before = (specs / 'accounts' / 'spec.md').read_bytes()
    applied = apply_ready(SPEC_OPS, specs, delta, specs, work)
    assert applied.returncode != 0
    assert 'invalid_state_context' in applied.stderr
    assert (specs / 'accounts' / 'spec.md').read_bytes() == before


def test_myspec_final_apply_rejects_missing_bound_content_fingerprints(spec_documents) -> None:
    documents = spec_documents
    tmp_path = documents.root
    write, ready_state, apply_ready = documents.write, documents.ready_state, documents.apply
    specs = tmp_path / 'specs'
    delta = tmp_path / 'delta'
    preview = tmp_path / 'preview'
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('登录', '允许登录')))
    write(delta / 'accounts' / 'spec.md', '## MODIFIED Requirements\n\n### Requirement: 登录\n\n系统 MUST 允许密码登录。\n\n#### Scenario: 密码正确\n\n- **WHEN** 用户提交正确密码\n- **THEN** 系统创建会话\n')
    work = ready_state(SPEC_OPS, tmp_path / 'state')
    previewed = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert previewed.returncode == 0, previewed.stderr
    state_path = work / 'current' / 'state.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    state['specsContentFingerprint'] = None
    state['deltaContentFingerprint'] = None
    state_path.write_text(json.dumps(state), encoding='utf-8')
    before = (specs / 'accounts' / 'spec.md').read_bytes()
    applied = apply_ready(SPEC_OPS, specs, delta, specs, work)
    assert applied.returncode != 0
    assert 'invalid_state_context' in applied.stderr
    assert (specs / 'accounts' / 'spec.md').read_bytes() == before


def test_packed_myspec_codex_doctor_uses_user_home_when_orca_home_is_inherited(management_documents):
    runtime = management_documents
    runtime.records("codex", [], [])
    user_home = runtime.home / ".codex"
    orca_home = runtime.root / "orca-user-data/codex-runtime-home/home"
    runtime.directories.add(orca_home)
    runtime.monkeypatch.setenv("CODEX_HOME", str(orca_home))
    runtime.monkeypatch.setenv("ORCA_USER_DATA_PATH", str(runtime.root / "orca-user-data"))
    runtime.capture_sdk_environments()
    diagnosed = runtime.run("doctor", "--codex")
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)["codex"]
    assert report["codexHome"] == str(user_home)
    assert report["codexHomeSource"] == "orca-user-default"
    assert [env["CODEX_HOME"] for command, env in runtime.sdk_environments] == [str(user_home), str(user_home)]
    assert os.environ["CODEX_HOME"] == str(orca_home)
    explicit_home = runtime.root / "custom-codex-home"
    runtime.directories.add(explicit_home)
    runtime.config_paths.add(explicit_home / "config.toml")
    runtime.sdk_environments.clear()
    explicit = runtime.run("doctor", "--codex", "--codex-home", explicit_home)
    assert explicit.returncode == 0, explicit.stderr
    report = json.loads(explicit.stdout)["codex"]
    assert report["codexHome"] == str(explicit_home)
    assert report["codexHomeSource"] == "explicit"
    assert [env["CODEX_HOME"] for command, env in runtime.sdk_environments] == [str(explicit_home), str(explicit_home)]
    assert os.environ["CODEX_HOME"] == str(orca_home)
    queue_client_init(runtime, "codex")
    initialized = runtime.run("init", "--codex", "--codex-home", explicit_home)
    assert initialized.returncode == 0, initialized.stderr
    assert os.environ["CODEX_HOME"] == str(orca_home)
    assert all(env["CODEX_HOME"] == str(explicit_home) for command, env in runtime.sdk_environments)


def test_packed_myspec_explicit_codex_home_errors_without_codex(management_documents):
    runtime = management_documents
    missing_home = runtime.root / "missing-codex-home"
    diagnosed = runtime.run("doctor", "--codex", "--codex-home", missing_home)
    assert diagnosed.returncode == 1
    assert f"error: codex_home_unavailable: {missing_home}: directory does not exist" in diagnosed.stderr
    assert runtime.writes == []


def test_packed_myspec_bare_doctor_does_not_require_codex_home(management_documents):
    runtime = management_documents
    runtime.records("codex", [], [])
    bad_home = runtime.root / "invalid-codex-home"
    runtime.files.add(bad_home)
    runtime.monkeypatch.setenv("CODEX_HOME", str(bad_home))
    runtime.response(("codex", "plugin", "marketplace", "list", "--json"), {"marketplaces": "broken"})
    diagnosed = runtime.run("doctor")
    assert diagnosed.returncode == 0, diagnosed.stderr
    assert not {"pi", "claude", "codex"}.intersection(json.loads(diagnosed.stdout))
    assert runtime.stub.calls == []
    assert runtime.writes == []


@pytest.fixture
def lifecycle_management(monkeypatch):
    module = _load_in_process_spec_ops(SPEC_OPS)
    management = sys.modules[module.run_management.__module__]
    monkeypatch.setattr(management.shutil, "which", lambda command: command)
    return management


def _git_batch_object(content, kind=b"blob"):
    return b"a" * 40 + b" " + kind + b" " + str(len(content)).encode() + b"\n" + content + b"\n"


def test_lifecycle_git_batch_preserves_binary_bytes_and_whole_spaced_paths(lifecycle_management, monkeypatch):
    management = lifecycle_management
    root = REPO_ROOT / "__identity_source__"
    specs = ["a" * 40 + ":" + path for path in ("a file", "tab\tfile", "空文件")]
    contents = [b"text\r\nnext\n", b"\x00\xff\r\n", b""]
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, b"".join(_git_batch_object(content) for content in contents), b"")

    monkeypatch.setattr(management.subprocess, "run", run)
    assert management._git_blobs(root, specs) == contents
    request = "\n".join(specs) + "\n"
    assert calls == [(["git", "cat-file", "--batch"], {
        "input": request.encode("utf-8") if os.name == "nt" else os.fsencode(request),
        "cwd": root, "check": False, "capture_output": True, "shell": False,
    })]


def test_lifecycle_git_batch_uses_utf8_on_windows_even_with_legacy_filesystem_encoding(lifecycle_management, monkeypatch):
    management = lifecycle_management
    monkeypatch.setattr(management, "os", SimpleNamespace(
        name="nt", fsencode=lambda _value: pytest.fail("Windows Git input must not use the legacy filesystem encoding"),
    ))

    def run(command, **kwargs):
        assert command == ["git", "cat-file", "--batch"]
        assert kwargs["input"] == b"a" * 40 + b":\xe7\xa9\xba\xe6\x96\x87\xe4\xbb\xb6\n"
        return subprocess.CompletedProcess(command, 0, _git_batch_object(b"content"), b"")

    monkeypatch.setattr(management.subprocess, "run", run)
    assert management._git_blobs(REPO_ROOT, ["a" * 40 + ":空文件"]) == [b"content"]


@pytest.mark.parametrize("output,code", [
    (b"", 0),
    (b"ref:path missing\n", 0),
    (b"ref:path ambiguous\n", 0),
    (b"invalid blob 1\nx\n", 0),
    (b"a" * 40 + b" blob invalid\n", 0),
    (b"a" * 40 + b" blob 4\nabc", 0),
    (_git_batch_object(b"abc")[:-1], 0),
    (_git_batch_object(b"abc")[:-1] + b"x", 0),
    (_git_batch_object(b"abc") + b"unexpected\n", 0),
    (_git_batch_object(b"abc"), 1),
    (None, 0),
])
def test_lifecycle_git_batch_never_returns_a_partial_closure(lifecycle_management, monkeypatch, output, code):
    management = lifecycle_management

    def run(command, **kwargs):
        if output is None:
            raise FileNotFoundError("git")
        return subprocess.CompletedProcess(command, code, _git_batch_object(b"first") + output, b"failed")

    monkeypatch.setattr(management.subprocess, "run", run)
    monkeypatch.setattr(management, "_git_blob", lambda *_args: pytest.fail("failed batches must not fall back or partially succeed"))
    assert management._git_blobs(REPO_ROOT, ["a:first", "a:second"]) is None


@pytest.mark.parametrize("special_path", ["line\nbreak", "trailing\r"])
@pytest.mark.parametrize("failed_path", [None, "special", "tree"])
def test_lifecycle_git_batch_keeps_git_show_for_cr_lf_and_non_blob_paths(lifecycle_management, monkeypatch, special_path, failed_path):
    management = lifecycle_management
    paths = ["a file", special_path, "tree"]
    specs = ["a" * 40 + ":" + path for path in paths]
    calls = []
    fallback = {specs[1]: b"newline\x00\xff", specs[2]: b"tree listing\r\n"}

    def run(command, **kwargs):
        calls.append(command)
        if command[1:] == ["cat-file", "--batch"]:
            assert kwargs["input"] == os.fsencode(specs[0] + "\n" + specs[2] + "\n")
            return subprocess.CompletedProcess(command, 0, _git_batch_object(b"normal") + _git_batch_object(b"raw tree", b"tree"), b"")
        assert command[1] == "show" and command[2] in fallback
        assert "input" not in kwargs
        failed = (failed_path == "special" and command[2] == specs[1]) or (failed_path == "tree" and command[2] == specs[2])
        return subprocess.CompletedProcess(command, int(failed), fallback[command[2]], b"")

    monkeypatch.setattr(management.subprocess, "run", run)
    result = management._git_blobs(REPO_ROOT, specs)
    assert result == ([b"normal", fallback[specs[1]], fallback[specs[2]]] if failed_path is None else None)
    expected = [["git", "cat-file", "--batch"], ["git", "show", specs[1]]]
    if failed_path != "special":
        expected.append(["git", "show", specs[2]])
    assert calls == expected
    if failed_path is None:
        calls.clear()
        assert management._git_blobs(REPO_ROOT, [specs[1]]) == [fallback[specs[1]]]
        assert calls == [["git", "show", specs[1]]]


def test_lifecycle_source_commit_batches_complete_candidates_in_history_order(lifecycle_management, monkeypatch):
    management = lifecycle_management
    root = REPO_ROOT / "__identity_source__"
    package = root / "plugins/my-spec"
    files = [("package.json", b"{}\r\n"), ("python/management.py", b"\x00\xff"), ("tool-lifecycle/pack.py", b"pack\n")]
    commits = [letter * 40 for letter in "abcde"]
    paths = [management._implementation_source_path(Path("plugins/my-spec"), relative) for relative, _content in files]
    commands = CommandStub(consume=True)
    commands.add(("git", "remote", "get-url", "origin"), stdout="https://github.com/liuli195/my-agent-skills.git\n")
    commands.add(("git", "log", "--format=%H", "--all", "--", *sorted(paths)), stdout="invalid\n" + "\n".join(commits) + "\n")
    batches, published, dirty_paths = [], [], []

    def run(command, **kwargs):
        assert command == ["git", "cat-file", "--batch"] and kwargs["cwd"] == root
        commit = kwargs["input"][:40].decode()
        assert kwargs["input"] == os.fsencode("".join(f"{commit}:{path}\n" for path in paths))
        batches.append(commit)
        contents = [content for _relative, content in files]
        if commit == commits[0]:
            output = _git_batch_object(contents[0]) + b"missing:path missing\n"
        else:
            if commit == commits[1]:
                contents[0] = b"different"
            output = b"".join(_git_batch_object(content) for content in contents)
        return subprocess.CompletedProcess(command, 0, output, b"")

    monkeypatch.setattr(management, "_implementation_files", lambda path: files if path == package else pytest.fail("unexpected package"))
    monkeypatch.setattr(management, "_git_paths_dirty", lambda source, closure: dirty_paths.append((source, closure)) or False)
    monkeypatch.setattr(management, "_run", commands)
    monkeypatch.setattr(management, "_source_commit_is_published", lambda source, commit: published.append((source, commit)) or commit == commits[3])
    monkeypatch.setattr(management.subprocess, "run", run)
    identity = management._implementation_identity_for_files(files)
    assert management._implementation_source_commit(package, identity) == commits[3]
    assert batches == commits[:4]
    assert published == [(root, commits[2]), (root, commits[3])]
    assert dirty_paths == [(root, sorted(paths))]
    assert commands.responses == []
