from __future__ import annotations

import contextlib
import hashlib
import io
import importlib.util
import json
import os
import re
import signal
import shlex
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

import pytest

from tests.support.git_templates import copy_template
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
        management_spec.loader.exec_module(management)

        spec_ops_spec = importlib.util.spec_from_file_location(
            f"myspec_spec_ops_{module_id}", spec_ops_path
        )
        assert spec_ops_spec is not None and spec_ops_spec.loader is not None
        module = importlib.util.module_from_spec(spec_ops_spec)
        sys.modules[spec_ops_spec.name] = module
        spec_ops_spec.loader.exec_module(module)
    finally:
        if previous_management is None:
            sys.modules.pop(management_name, None)
        else:
            sys.modules[management_name] = previous_management
    _in_process_spec_ops[spec_ops_path] = module
    return module






























PREVIOUS_VERSION = bumped_patch(PACKAGE_VERSION, -1)
NEXT_VERSION = bumped_patch(PACKAGE_VERSION)
LATER_VERSION = bumped_patch(PACKAGE_VERSION, 2)











































































def physical_preparation_removed(*args, **kwargs):
    # A temporary red assertion while each old scenario is converted below.
    # Never retry tempfile creation or silently execute an unhandled command.
    raise AssertionError("ordinary_scenario_requires_memory_documents: physical preparation was removed")


install_packed_myspec = physical_preparation_removed
pack_myspec_version = physical_preparation_removed
install_fake_claude = physical_preparation_removed
install_fake_codex = physical_preparation_removed
install_fake_npm = physical_preparation_removed
controlled_dev_source = physical_preparation_removed
controlled_dev_env = physical_preparation_removed
write = physical_preparation_removed
ready_state = physical_preparation_removed
apply_ready = physical_preparation_removed
run_confirmed_workflow = physical_preparation_removed
run_cli = physical_preparation_removed
run_public_spec_cli = physical_preparation_removed


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
        self.writes = []
        self.lock_calls = []
        self.available = set()
        self.stub = CommandStub(consume=True)
        self.directories = {self.stable, self.cache, self.codex_home}
        self.files = {self.stable / "package.json", self.cache / "package.json",
                      self.prefix / ("myspec.cmd" if os.name == "nt" else "bin/myspec")}
        self.files.update(root / "skills" / skill / "SKILL.md" for root in (self.stable, self.cache) for skill in SKILL_NAMES)
        original_exists, original_is_dir, original_is_file = Path.exists, Path.is_dir, Path.is_file
        monkeypatch.setattr(Path, "exists", lambda path: path in self.documents or path in self.texts or path in self.files or path in self.directories or (False if path == self.state_path else original_exists(path)))
        monkeypatch.setattr(Path, "is_dir", lambda path: path in self.directories or original_is_dir(path))
        monkeypatch.setattr(Path, "is_file", lambda path: path in self.documents or path in self.files or original_is_file(path))
        original_access = os.access
        monkeypatch.setattr(os, "access", lambda path, mode: True if Path(path) in self.directories else original_access(path, mode))
        original_read_json, original_text = self.management._read_json, self.management._text
        monkeypatch.setattr(self.management, "_read_json", lambda path: json.loads(json.dumps(self.documents[path])) if path in self.documents else original_read_json(path))
        monkeypatch.setattr(self.management, "_text", lambda path: self.texts[path] if path in self.texts else original_text(path))
        monkeypatch.setattr(self.management, "_atomic_json", self.save_json)
        monkeypatch.setattr(self.management, "_atomic_text", self.save_text)
        monkeypatch.setattr(self.management, "_run", self.stub)
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
        assert path == self.config_path, f"unexpected_lifecycle_text_write: {path}"
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




def test_packed_myspec_update_preflights_installed_clients_before_package_write() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    installed = tmp_path / 'installed'
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    old_tarball = next((installed / 'package').glob('*.tgz'))
    npm_bin, npm_log = install_fake_npm(tmp_path / 'fake-npm', old_tarball)
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / 'fake-codex')
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, codex_bin)
    env.update({'MYSPEC_NPM_LOG': str(npm_log), 'MYSPEC_REAL_NPM': str(shutil.which('npm')), 'MYSPEC_RELEASE_TARBALL': str(old_tarball), 'MYSPEC_NPM_LATEST': NEXT_VERSION, 'CODEX_HOME': str(Path(env['HOME']) / '.codex'), 'MYSPEC_CODEX_LOG': str(codex_log), 'MYSPEC_CODEX_STATE': str(codex_state)})
    write(codex_state, json.dumps({'marketplaces': 'broken', 'installed': [{'pluginId': 'my-spec@myspec', 'version': PACKAGE_VERSION, 'installed': True}], 'available': []}))
    package_before = (installed_package / 'package.json').read_bytes()
    failed = run_cli(executable, 'update', env=env)
    assert failed.returncode == 1
    assert 'error: codex_marketplace_list_failed: invalid_output' in failed.stderr
    assert (installed_package / 'package.json').read_bytes() == package_before
    assert not (Path(env['HOME']) / '.myspec' / 'state.json').exists()
    calls = [json.loads(line) for line in npm_log.read_text(encoding='utf-8').splitlines()]
    assert not any((call[:2] == ['install', '--global'] for call in calls))
    write(codex_state, json.dumps({'marketplaces': 'broken', 'installed': [], 'available': []}))
    skipped = run_cli(executable, 'update', env={**env, 'MYSPEC_NPM_LATEST': PACKAGE_VERSION})
    assert skipped.returncode == 0, skipped.stderr
    assert 'codex' not in json.loads(skipped.stdout)


def test_packed_myspec_update_blocks_enabled_legacy_sources_before_writes() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    installed = tmp_path / 'installed'
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    old_tarball = next((installed / 'package').glob('*.tgz'))
    new_tarball = pack_myspec_version(tmp_path, NEXT_VERSION)
    npm_bin, npm_log = install_fake_npm(tmp_path / 'fake-npm', old_tarball)
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / 'fake-claude')
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / 'fake-codex')
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, claude_bin, codex_bin)
    codex_home = tmp_path / 'codex home'
    codex_home.mkdir()
    env.update({'MYSPEC_NPM_LOG': str(npm_log), 'MYSPEC_REAL_NPM': str(shutil.which('npm')), 'MYSPEC_RELEASE_TARBALL': str(new_tarball), 'MYSPEC_NPM_LATEST': NEXT_VERSION, 'MYSPEC_CLAUDE_LOG': str(claude_log), 'MYSPEC_CLAUDE_STATE': str(claude_state), 'MYSPEC_CLAUDE_HOME': str(Path(env['HOME']) / '.claude'), 'CODEX_HOME': str(codex_home), 'MYSPEC_CODEX_LOG': str(codex_log), 'MYSPEC_CODEX_STATE': str(codex_state)})
    legacy_source = str(PLUGIN_ROOT)
    write(claude_state, json.dumps({'marketplaces': [{'name': 'myspec', 'source': 'directory', 'path': str(installed_package), 'installLocation': str(installed_package)}, {'name': 'my-agent-skills-marketplace', 'source': 'directory', 'path': legacy_source, 'installLocation': legacy_source}], 'plugins': [{'id': 'my-spec@myspec', 'version': PACKAGE_VERSION, 'scope': 'user', 'enabled': True, 'installPath': str(installed_package)}, {'id': 'my-spec@my-agent-skills-marketplace', 'version': PACKAGE_VERSION, 'scope': 'user', 'enabled': True, 'installPath': legacy_source}]}, indent=2))
    write(codex_state, json.dumps({'marketplaces': [{'name': 'myspec', 'root': str(installed_package), 'marketplaceSource': {'sourceType': 'local', 'source': str(installed_package)}}, {'name': 'my-agent-skills-marketplace', 'root': legacy_source, 'marketplaceSource': {'sourceType': 'local', 'source': legacy_source}}], 'installed': [{'pluginId': 'my-spec@myspec', 'name': 'my-spec', 'marketplaceName': 'myspec', 'version': PACKAGE_VERSION, 'installed': True, 'source': {'source': 'local', 'path': str(installed_package)}}, {'pluginId': 'my-spec@my-agent-skills-marketplace', 'name': 'my-spec', 'marketplaceName': 'my-agent-skills-marketplace', 'version': PACKAGE_VERSION, 'installed': True, 'source': {'source': 'local', 'path': legacy_source}}], 'available': []}, indent=2))
    codex_config = codex_home / 'config.toml'
    write(codex_config, '[plugins."my-spec@myspec"]\nenabled = true\n[plugins."my-spec@my-agent-skills-marketplace"]\nenabled = true\n')
    before = {'claude': claude_state.read_bytes(), 'codex': codex_state.read_bytes(), 'config': codex_config.read_bytes()}
    blocked = run_cli(executable, 'update', '--codex-home', codex_home, env=env)
    assert blocked.returncode == 1
    assert 'error: legacy_source_migration_required' in blocked.stderr
    assert 'claude: run myspec init --claude' in blocked.stderr
    codex_command = subprocess.list2cmdline(['myspec', 'init', '--codex', '--codex-home', str(codex_home)]) if os.name == 'nt' else shlex.join(['myspec', 'init', '--codex', '--codex-home', str(codex_home)])
    assert f'codex: run {codex_command}' in blocked.stderr
    assert not any((json.loads(line)[:2] == ['install', '--global'] for line in npm_log.read_text(encoding='utf-8').splitlines()))
    assert not (Path(env['HOME']) / '.myspec' / 'state.json').exists()
    assert claude_state.read_bytes() == before['claude']
    assert codex_state.read_bytes() == before['codex']
    assert codex_config.read_bytes() == before['config']
    migrated = run_cli(executable, 'init', '--all', env=env)
    assert migrated.returncode == 0, migrated.stderr
    updated = run_cli(executable, 'update', env=env)
    assert updated.returncode == 0, updated.stderr
    assert json.loads(updated.stdout)['version'] == NEXT_VERSION


def test_packed_myspec_update_refreshes_disabled_integrations_and_skips_only_missing() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    installed = tmp_path / 'installed'
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    old_tarball = next((installed / 'package').glob('*.tgz'))
    new_tarball = pack_myspec_version(tmp_path, NEXT_VERSION)
    npm_bin, npm_log = install_fake_npm(tmp_path / 'fake-npm', old_tarball)
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / 'fake-claude')
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / 'fake-codex')
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, claude_bin, codex_bin)
    env.update({'MYSPEC_NPM_LOG': str(npm_log), 'MYSPEC_REAL_NPM': str(shutil.which('npm')), 'MYSPEC_RELEASE_TARBALL': str(new_tarball), 'MYSPEC_NPM_LATEST': NEXT_VERSION, 'MYSPEC_CLAUDE_LOG': str(claude_log), 'MYSPEC_CLAUDE_STATE': str(claude_state), 'MYSPEC_CLAUDE_HOME': str(Path(env['HOME']) / '.claude'), 'CODEX_HOME': str(Path(env['HOME']) / '.codex'), 'MYSPEC_CODEX_LOG': str(codex_log), 'MYSPEC_CODEX_STATE': str(codex_state)})
    write(claude_state, json.dumps({'marketplaces': [{'name': 'myspec', 'source': 'directory', 'path': str(installed_package), 'installLocation': str(installed_package)}], 'plugins': [{'id': 'my-spec@myspec', 'version': PACKAGE_VERSION, 'scope': 'user', 'enabled': False, 'installPath': str(tmp_path / 'disabled-claude')}]}, indent=2))
    write(codex_state, json.dumps({'marketplaces': [{'name': 'myspec', 'root': str(installed_package), 'marketplaceSource': {'sourceType': 'local', 'source': str(installed_package)}}], 'installed': [{'pluginId': 'my-spec@myspec', 'name': 'my-spec', 'marketplaceName': 'myspec', 'version': PACKAGE_VERSION, 'installed': True, 'source': {'source': 'local', 'path': str(installed_package)}}], 'available': []}, indent=2))
    write(Path(env['CODEX_HOME']) / 'config.toml', '[plugins."my-spec@myspec"]\nenabled = false\n')
    interrupted = run_cli(executable, 'update', env={**env, 'MYSPEC_CLAUDE_FAIL_AFTER_ENABLED': 'false'})
    assert interrupted.returncode == 1
    assert 'claude_plugin_disable_failed: simulated interruption after enabled state' in interrupted.stderr
    updated = run_cli(executable, 'update', env=env)
    assert updated.returncode == 0, updated.stderr
    output = json.loads(updated.stdout)
    assert output['version'] == NEXT_VERSION
    assert output['claude'] == 'refreshed'
    assert output['codex'] == 'refreshed'
    assert output['doctor']['claude']['enabled'] is False
    assert output['doctor']['codex']['enabled'] is False
    for client in ('claude', 'codex'):
        stable_source = next((source for source in output['doctor'][client]['sources'] if source['sourceKind'] == 'stable'))
        assert stable_source['enabled'] is False
    assert output['doctor']['claude']['version'] == NEXT_VERSION
    assert output['doctor']['codex']['version'] == NEXT_VERSION
    claude_calls = [json.loads(line) for line in claude_log.read_text(encoding='utf-8').splitlines()]
    assert ['plugin', 'uninstall', 'my-spec@myspec', '--scope', 'user', '--keep-data'] in claude_calls
    assert ['plugin', 'install', 'my-spec@myspec', '--scope', 'user'] in claude_calls
    assert claude_calls.count(['plugin', 'disable', 'my-spec@myspec', '--scope', 'user']) == 1
    codex_calls = [json.loads(line) for line in codex_log.read_text(encoding='utf-8').splitlines()]
    assert ['plugin', 'remove', 'my-spec@myspec', '--json'] in codex_calls
    assert ['plugin', 'add', 'my-spec@myspec', '--json'] in codex_calls








def test_packed_myspec_doctor_reports_partial_update_read_only() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    first = tmp_path / 'first'
    second = tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    executable, _ = install_packed_myspec(first)
    _, installed_package = install_packed_myspec(second)
    env = isolated_myspec_env(tmp_path, npm_prefix_for(installed_package))
    package_path = installed_package / 'package.json'
    package = json.loads(package_path.read_text(encoding='utf-8'))
    package['version'] = NEXT_VERSION
    write(package_path, json.dumps(package, indent=2))
    state_path = Path(env['HOME']) / '.myspec' / 'state.json'
    write(state_path, json.dumps({'mode': 'release', 'pendingOperation': {'command': 'update', 'targetVersion': NEXT_VERSION, 'integrations': ['pi', 'claude'], 'completed': ['preflight', 'npm', 'pi'], 'lastError': 'claude_plugin_install_failed: original failure', 'tokenHash': 'secret'}}, indent=2))
    before = state_path.read_bytes()
    diagnosed = run_cli(executable, 'doctor', '--all', env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report['npm']['versionMismatch'] is True
    assert report['installation']['pendingOperation'] == {'command': 'update', 'targetVersion': NEXT_VERSION, 'integrations': ['pi', 'claude'], 'completed': ['preflight', 'npm', 'pi'], 'lastError': 'claude_plugin_install_failed: original failure'}
    assert report['installation']['lock'] is None
    assert state_path.read_bytes() == before
    token = 'resume-secret'
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    write(state_path, json.dumps({'mode': 'release', 'pendingOperation': {'command': 'update', 'targetVersion': NEXT_VERSION, 'integrations': [], 'scopes': {}, 'enabled': {}, 'completed': ['preflight', 'npm'], 'tokenHash': token_hash}}, indent=2))
    write(Path(env['HOME']) / '.myspec' / 'install.lock', json.dumps({'pid': os.getpid(), 'startedAt': '2000-01-01T00:00:00+00:00', 'command': 'myspec update', 'operationId': 'resume-operation', 'handoffTokenHash': token_hash}, indent=2))
    forged = run_cli(executable, 'update', '--_update-token', token, env=env)
    assert forged.returncode == 1
    assert 'error: update_runtime_mismatch:' in forged.stderr
    assert json.loads(state_path.read_text(encoding='utf-8'))['pendingOperation']['completed'] == ['preflight', 'npm']


def test_packed_myspec_update_rejects_dev_mode_and_forged_resume() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((tmp_path / 'package').glob('*.tgz'))
    npm_bin, npm_log = install_fake_npm(tmp_path / 'fake-npm', release_tarball)
    env = isolated_myspec_env(tmp_path, prefix, npm_bin)
    env.update({'MYSPEC_NPM_LOG': str(npm_log), 'MYSPEC_REAL_NPM': str(shutil.which('npm')), 'MYSPEC_RELEASE_TARBALL': str(release_tarball)})
    source = controlled_dev_source(tmp_path)
    env = controlled_dev_env(env, source)
    entered = run_cli(executable, 'init', '--dev', '--source', source, env=env)
    assert entered.returncode == 0, entered.stderr
    rejected = run_cli(executable, 'update', env=env)
    forged = run_cli(executable, 'update', '--_update-token', 'forged', env=env)
    assert rejected.returncode == 1
    assert "update_requires_release_mode: run 'myspec init --release' first" in rejected.stderr
    assert forged.returncode == 1
    assert 'error: invalid_update_token' in forged.stderr
    lock = json.loads((Path(env['HOME']) / '.myspec' / 'install.lock').read_text(encoding='utf-8'))
    assert lock['released'] is True


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
    tmp_path = REPO_ROOT / '__myspec_documents__'
    _, installed_package = install_packed_myspec(tmp_path)
    marketplace = json.loads((installed_package / '.agents' / 'plugins' / 'marketplace.json').read_text(encoding='utf-8'))
    assert marketplace == {'name': 'myspec', 'interface': {'displayName': 'MySpec'}, 'plugins': [{'name': 'my-spec', 'source': {'source': 'local', 'path': './'}, 'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Developer Tools'}]}
    assert [path.parent.name for path in sorted((installed_package / 'skills').glob('*/SKILL.md'))] == sorted(SKILL_NAMES)










def test_packed_myspec_reconfirms_when_in_process_identity_changes_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    specs = tmp_path / 'specs'
    delta = tmp_path / 'delta'
    preview = tmp_path / 'preview'
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('登录', '允许登录')))
    write(delta / 'accounts' / 'spec.md', '## MODIFIED Requirements\n\n### Requirement: 登录\n\n系统 MUST 允许密码登录。\n\n#### Scenario: 密码正确\n\n- **WHEN** 用户提交正确密码\n- **THEN** 系统创建会话\n')
    work = ready_state(SPEC_OPS, tmp_path / 'state')
    previewed = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert previewed.returncode == 0, previewed.stderr
    before = (specs / 'accounts' / 'spec.md').read_bytes()
    spec_ops = _load_in_process_spec_ops(SPEC_OPS)
    original_write_preview = spec_ops._write_preview

    def changed_write_preview(merged, output_root, source_root):
        original_write_preview(merged, output_root, source_root)
        path = output_root / 'accounts' / 'spec.md'
        write(path, path.read_text(encoding='utf-8') + '\nimplementation-only change')
    monkeypatch.setattr(spec_ops, 'implementation_identity', lambda: 'changed-implementation')
    monkeypatch.setattr(spec_ops, '_write_preview', changed_write_preview)
    applied = apply_ready(SPEC_OPS, specs, delta, specs, work)
    assert applied.returncode != 0
    assert 'preview_changed_requires_confirmation' in applied.stderr
    assert (specs / 'accounts' / 'spec.md').read_bytes() == before




def test_packed_myspec_requires_release_registration_before_first_codex_dev_init() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    installed = tmp_path / 'installed'
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((installed / 'package').glob('*.tgz'))
    npm_bin, npm_log = install_fake_npm(tmp_path / 'fake-npm', release_tarball)
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / 'fake-codex')
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, codex_bin)
    env.update({'MYSPEC_NPM_LOG': str(npm_log), 'MYSPEC_REAL_NPM': str(shutil.which('npm')), 'MYSPEC_RELEASE_TARBALL': str(release_tarball), 'CODEX_HOME': str(Path(env['HOME']) / '.codex'), 'MYSPEC_CODEX_LOG': str(codex_log), 'MYSPEC_CODEX_STATE': str(codex_state)})
    write(codex_state, json.dumps({'marketplaces': [], 'installed': [], 'available': []}, indent=2))
    source = controlled_dev_source(tmp_path)
    env = controlled_dev_env(env, source)
    entered = run_cli(executable, 'init', '--dev', '--source', source, env=env)
    assert entered.returncode == 0, entered.stderr
    before = codex_state.read_bytes()
    codex_log.write_text('', encoding='utf-8')
    blocked = run_cli(executable, 'init', '--codex', env=env)
    assert blocked.returncode == 1
    assert blocked.stdout == ''
    assert "error: codex_dev_marketplace_unregistered: run 'myspec init --release', then 'myspec init --codex', then 'myspec init --dev'" in blocked.stderr
    assert codex_state.read_bytes() == before
    blocked_calls = [json.loads(line) for line in codex_log.read_text(encoding='utf-8').splitlines()]
    assert blocked_calls == [['plugin', 'marketplace', 'list', '--json']]
    restored = run_cli(executable, 'init', '--release', env=env)
    assert restored.returncode == 0, restored.stderr
    initialized = run_cli(executable, 'init', '--codex', env=env)
    assert initialized.returncode == 0, initialized.stderr
    registered = json.loads(codex_state.read_text(encoding='utf-8'))['marketplaces']
    assert registered == [{'name': 'myspec', 'root': str(installed_package), 'marketplaceSource': {'sourceType': 'local', 'source': str(installed_package)}}]
    codex_log.write_text('', encoding='utf-8')
    entered_again = run_cli(executable, 'init', '--dev', '--source', source, env=env)
    assert entered_again.returncode == 0, entered_again.stderr
    calls = [json.loads(line) for line in codex_log.read_text(encoding='utf-8').splitlines()]
    assert not any((call[:3] == ['plugin', 'marketplace', 'add'] for call in calls))
    assert json.loads(codex_state.read_text(encoding='utf-8'))['marketplaces'] == registered




@pytest.mark.parametrize('disabled', [False, True])
def test_packed_myspec_mode_switch_does_not_install_missing_or_disabled_codex(disabled: bool) -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    installed = tmp_path / 'installed'
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((installed / 'package').glob('*.tgz'))
    npm_bin, npm_log = install_fake_npm(tmp_path / 'fake-npm', release_tarball)
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / 'fake-codex')
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, codex_bin)
    env.update({'MYSPEC_NPM_LOG': str(npm_log), 'MYSPEC_REAL_NPM': str(shutil.which('npm')), 'MYSPEC_RELEASE_TARBALL': str(release_tarball), 'CODEX_HOME': str(Path(env['HOME']) / '.codex'), 'MYSPEC_CODEX_LOG': str(codex_log), 'MYSPEC_CODEX_STATE': str(codex_state)})
    initial_state: dict[str, object] = {'marketplaces': [], 'installed': [], 'available': []}
    if disabled:
        cache = tmp_path / 'disabled-cache'
        shutil.copytree(installed_package, cache)
        initial_state = {'marketplaces': [{'name': 'myspec', 'root': str(installed_package), 'marketplaceSource': {'sourceType': 'local', 'source': str(installed_package)}}], 'installed': [{'pluginId': 'my-spec@myspec', 'name': 'my-spec', 'marketplaceName': 'myspec', 'version': PACKAGE_VERSION, 'installed': True, 'source': {'source': 'local', 'path': str(cache)}}], 'available': []}
        write(Path(env['CODEX_HOME']) / 'config.toml', '[plugins."my-spec@myspec"]\nenabled = false\n')
    write(codex_state, json.dumps(initial_state, indent=2))
    source = controlled_dev_source(tmp_path)
    env = controlled_dev_env(env, source)
    entered = run_cli(executable, 'init', '--dev', '--source', source, env=env)
    assert entered.returncode == 0, entered.stderr
    assert json.loads(entered.stdout)['codex'] == 'not-installed'
    restored = run_cli(executable, 'init', '--release', env=env)
    assert restored.returncode == 0, restored.stderr
    assert json.loads(restored.stdout)['codex'] == 'not-installed'
    calls = [json.loads(line) for line in codex_log.read_text(encoding='utf-8').splitlines()]
    assert not any((call[:2] == ['plugin', 'add'] for call in calls))
    assert not any((call[:2] == ['plugin', 'remove'] for call in calls))
    assert json.loads(codex_state.read_text(encoding='utf-8')) == initial_state




@pytest.mark.parametrize('disabled', [False, True])
def test_packed_myspec_mode_switch_does_not_install_missing_or_disabled_claude(disabled: bool) -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    installed = tmp_path / 'installed'
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((installed / 'package').glob('*.tgz'))
    npm_bin, npm_log = install_fake_npm(tmp_path / 'fake-npm', release_tarball)
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / 'fake-claude')
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, claude_bin)
    env.update({'MYSPEC_NPM_LOG': str(npm_log), 'MYSPEC_REAL_NPM': str(shutil.which('npm')), 'MYSPEC_RELEASE_TARBALL': str(release_tarball), 'MYSPEC_CLAUDE_LOG': str(claude_log), 'MYSPEC_CLAUDE_STATE': str(claude_state), 'MYSPEC_CLAUDE_HOME': str(Path(env['HOME']) / '.claude')})
    initial_state = {'marketplaces': [], 'plugins': []}
    if disabled:
        initial_state = {'marketplaces': [{'name': 'myspec', 'source': 'directory', 'path': str(installed_package), 'installLocation': str(installed_package)}], 'plugins': [{'id': 'my-spec@myspec', 'version': PACKAGE_VERSION, 'scope': 'user', 'enabled': False, 'installPath': str(tmp_path / 'disabled-plugin-cache')}]}
    write(claude_state, json.dumps(initial_state, indent=2))
    source = controlled_dev_source(tmp_path)
    env = controlled_dev_env(env, source)
    entered = run_cli(executable, 'init', '--dev', '--source', source, env=env)
    assert entered.returncode == 0, entered.stderr
    assert json.loads(entered.stdout)['claude'] == 'not-installed'
    restored = run_cli(executable, 'init', '--release', env=env)
    assert restored.returncode == 0, restored.stderr
    assert json.loads(restored.stdout)['claude'] == 'not-installed'
    calls = [json.loads(line) for line in claude_log.read_text(encoding='utf-8').splitlines()]
    assert not any((call[:3] == ['plugin', 'marketplace', 'add'] for call in calls))
    assert not any((call[:2] == ['plugin', 'install'] for call in calls))
    assert not any((call[:2] == ['plugin', 'enable'] for call in calls))
    assert json.loads(claude_state.read_text(encoding='utf-8')) == initial_state


def test_packed_myspec_claude_reinstall_failure_does_not_report_refreshed() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    installed = tmp_path / 'installed'
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((installed / 'package').glob('*.tgz'))
    npm_bin, npm_log = install_fake_npm(tmp_path / 'fake-npm', release_tarball)
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / 'fake-claude')
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, claude_bin)
    env.update({'MYSPEC_NPM_LOG': str(npm_log), 'MYSPEC_REAL_NPM': str(shutil.which('npm')), 'MYSPEC_RELEASE_TARBALL': str(release_tarball), 'MYSPEC_CLAUDE_LOG': str(claude_log), 'MYSPEC_CLAUDE_STATE': str(claude_state), 'MYSPEC_CLAUDE_HOME': str(Path(env['HOME']) / '.claude')})
    write(claude_state, json.dumps({'marketplaces': [], 'plugins': []}, indent=2))
    assert run_cli(executable, 'init', '--claude', env=env).returncode == 0
    claude_log.write_text('', encoding='utf-8')
    source = controlled_dev_source(tmp_path)
    env = controlled_dev_env(env, source)
    failed = run_cli(executable, 'init', '--dev', '--source', source, env={**env, 'MYSPEC_CLAUDE_FAIL_INSTALL': '1'})
    assert failed.returncode == 1
    assert failed.stdout == ''
    assert 'claude_plugin_install_failed: simulated install failure' in failed.stderr
    assert 'refreshed' not in failed.stderr
    calls = [json.loads(line) for line in claude_log.read_text(encoding='utf-8').splitlines()]
    assert ['plugin', 'uninstall', 'my-spec@myspec', '--scope', 'user', '--keep-data'] in calls
    assert ['plugin', 'install', 'my-spec@myspec', '--scope', 'user'] in calls
    assert ['plugin', 'enable', 'my-spec@myspec', '--scope', 'user'] not in calls




def test_packed_myspec_doctor_uses_actual_installation_not_mode_state() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    env = isolated_myspec_env(tmp_path, prefix)
    write(Path(env['HOME']) / '.myspec' / 'state.json', json.dumps({'mode': 'dev', 'source': 'C:/not-the-package', 'previousReleaseVersion': '9.9.9'}))
    state_before = (Path(env['HOME']) / '.myspec' / 'state.json').read_bytes()
    diagnosed = run_cli(executable, 'doctor', env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report['mode'] == 'release'
    assert report['toolchain'] == {'mode': 'release', 'packageName': '@liuli195/myspec', 'packageVersion': PACKAGE_VERSION}
    assert report['source'] == str(installed_package)
    assert report['npm']['linked'] is False
    assert report['npm']['versionMismatch'] is False
    assert not {'pi', 'claude', 'codex'}.intersection(report)
    assert (Path(env['HOME']) / '.myspec' / 'state.json').read_bytes() == state_before
    all_agents = run_cli(executable, 'doctor', '--all', env=env)
    assert all_agents.returncode == 0, all_agents.stderr
    assert 'pi' not in json.loads(all_agents.stdout)


def test_packed_myspec_doctor_reports_actual_package_version_mismatch() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    first = tmp_path / 'first'
    second = tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    executable, _ = install_packed_myspec(first)
    _, installed_package = install_packed_myspec(second)
    package_path = installed_package / 'package.json'
    package = json.loads(package_path.read_text(encoding='utf-8'))
    package['version'] = NEXT_VERSION
    write(package_path, json.dumps(package, indent=2))
    env = isolated_myspec_env(tmp_path, npm_prefix_for(installed_package))
    diagnosed = run_cli(executable, 'doctor', env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report['cliVersion'] == PACKAGE_VERSION
    assert report['npm']['packageVersion'] == NEXT_VERSION
    assert report['npm']['versionMismatch'] is True


def test_packed_myspec_rejects_invalid_mode_switches() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    executable, installed_package = install_packed_myspec(tmp_path)
    env = isolated_myspec_env(tmp_path, npm_prefix_for(installed_package))
    invalid_source = run_cli(executable, 'init', '--dev', '--source', tmp_path, env=env)
    assert invalid_source.returncode == 1
    assert 'error: invalid_dev_source: missing' in invalid_source.stderr
    assert not (Path(env['HOME']) / '.myspec' / 'state.json').exists()
    checkout = tmp_path / 'checkout'
    nested = checkout / 'nested'
    shutil.copytree(REPO_ROOT / '.agents', nested / '.agents')
    shutil.copytree(REPO_ROOT / '.claude-plugin', nested / '.claude-plugin')
    shutil.copytree(PLUGIN_ROOT, nested / 'plugins' / 'my-spec')
    initialized_git = subprocess.run(['git', 'init'], cwd=checkout, text=True, capture_output=True, check=False)
    assert initialized_git.returncode == 0, initialized_git.stderr
    borrowed_root = run_cli(executable, 'init', '--dev', '--source', nested, env=env)
    assert borrowed_root.returncode == 1
    assert 'error: invalid_dev_source: git_root' in borrowed_root.stderr
    malformed = tmp_path / 'malformed'
    shutil.copytree(REPO_ROOT / '.agents', malformed / '.agents')
    shutil.copytree(REPO_ROOT / '.claude-plugin', malformed / '.claude-plugin')
    shutil.copytree(PLUGIN_ROOT, malformed / 'plugins' / 'my-spec')
    market_path = malformed / 'plugins' / 'my-spec' / '.agents' / 'plugins' / 'marketplace.json'
    market = json.loads(market_path.read_text(encoding='utf-8'))
    next((plugin for plugin in market['plugins'] if plugin['name'] == 'my-spec'))['source']['path'] = '../wrong'
    write(market_path, json.dumps(market, indent=2))
    malformed_result = run_cli(executable, 'init', '--dev', '--source', malformed, env=env)
    assert malformed_result.returncode == 1
    assert 'error: invalid_dev_source: marketplace' in malformed_result.stderr
    next((plugin for plugin in market['plugins'] if plugin['name'] == 'my-spec'))['source']['path'] = './'
    write(market_path, json.dumps(market, indent=2))
    package_path = malformed / 'plugins' / 'my-spec' / 'package.json'
    package = json.loads(package_path.read_text(encoding='utf-8'))
    package['name'] = '@liuli195/myspec-helper'
    write(package_path, json.dumps(package, indent=2))
    package_result = run_cli(executable, 'init', '--dev', '--source', malformed, env=env)
    assert package_result.returncode == 1
    assert 'error: invalid_dev_source: package_manifest' in package_result.stderr
    result = run_cli(executable, 'init', '--release', env=env)
    assert result.returncode == 1
    assert 'error: missing_previous_release_version' in result.stderr


@pytest.mark.parametrize('case', ['package-name', 'package-version', 'bin-entry', 'bin-file', 'python-entry', 'management-entry', 'skill-file', 'codex-marketplace', 'claude-marketplace', 'self-claude-marketplace', 'plugin-manifest'])
def test_packed_myspec_dev_preflight_rejects_incomplete_source_before_link_or_state(case: str) -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    (tmp_path / 'installed').mkdir()
    executable, installed_package = install_packed_myspec(tmp_path / 'installed')
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((tmp_path / 'installed' / 'package').glob('*.tgz'))
    npm_bin, npm_log = install_fake_npm(tmp_path / 'fake-npm', release_tarball)
    env = isolated_myspec_env(tmp_path, prefix, npm_bin)
    env.update({'MYSPEC_NPM_LOG': str(npm_log), 'MYSPEC_REAL_NPM': str(shutil.which('npm')), 'MYSPEC_RELEASE_TARBALL': str(release_tarball)})
    source = tmp_path / 'source'
    shutil.copytree(REPO_ROOT / '.agents', source / '.agents')
    shutil.copytree(REPO_ROOT / '.claude-plugin', source / '.claude-plugin')
    shutil.copytree(PLUGIN_ROOT, source / 'plugins' / 'my-spec')
    shutil.copytree(REPO_ROOT / 'plugins' / 'tool-lifecycle', source / 'plugins' / 'tool-lifecycle')
    initialized = subprocess.run(['git', 'init'], cwd=source, text=True, capture_output=True, check=False)
    assert initialized.returncode == 0, initialized.stderr
    committed = subprocess.run(['git', '-c', 'user.name=MySpec Test', '-c', 'user.email=myspec@example.invalid', 'add', '.'], cwd=source, text=True, capture_output=True, check=False)
    assert committed.returncode == 0, committed.stderr
    committed = subprocess.run(['git', '-c', 'user.name=MySpec Test', '-c', 'user.email=myspec@example.invalid', 'commit', '-m', 'test source'], cwd=source, text=True, capture_output=True, check=False)
    assert committed.returncode == 0, committed.stderr
    package_path = source / 'plugins' / 'my-spec' / 'package.json'
    package = json.loads(package_path.read_text(encoding='utf-8'))
    if case == 'package-name':
        package['name'] = '@liuli195/not-myspec'
    elif case == 'package-version':
        package['version'] = ''
    elif case == 'bin-entry':
        package['bin'] = {'myspec': './bin/other.js'}
    elif case == 'bin-file':
        (source / 'plugins' / 'my-spec' / 'bin' / 'myspec.js').unlink()
    elif case == 'python-entry':
        (source / 'plugins' / 'my-spec' / 'python' / 'spec_ops.py').unlink()
    elif case == 'management-entry':
        (source / 'plugins' / 'my-spec' / 'python' / 'management.py').unlink()
    elif case == 'skill-file':
        (source / 'plugins' / 'my-spec' / 'skills' / 'my-spec-audit' / 'SKILL.md').unlink()
    elif case == 'codex-marketplace':
        market_path = source / 'plugins' / 'my-spec' / '.agents' / 'plugins' / 'marketplace.json'
        market = json.loads(market_path.read_text(encoding='utf-8'))
        next((plugin for plugin in market['plugins'] if plugin['name'] == 'my-spec'))['source']['path'] = '../wrong'
        write(market_path, json.dumps(market, indent=2))
    elif case == 'claude-marketplace':
        market_path = source / 'plugins' / 'my-spec' / '.claude-plugin' / 'marketplace.json'
        market = json.loads(market_path.read_text(encoding='utf-8'))
        next((plugin for plugin in market['plugins'] if plugin['name'] == 'my-spec'))['source'] = '../wrong'
        write(market_path, json.dumps(market, indent=2))
    elif case == 'self-claude-marketplace':
        market_path = source / 'plugins' / 'my-spec' / '.claude-plugin' / 'marketplace.json'
        market = json.loads(market_path.read_text(encoding='utf-8'))
        market['plugins'][0]['source'] = '../wrong'
        write(market_path, json.dumps(market, indent=2))
    else:
        plugin_path = source / 'plugins' / 'my-spec' / '.codex-plugin' / 'plugin.json'
        plugin = json.loads(plugin_path.read_text(encoding='utf-8'))
        plugin['version'] = '9.9.9'
        write(plugin_path, json.dumps(plugin, indent=2))
    write(package_path, json.dumps(package, indent=2))
    rejected = run_cli(executable, 'init', '--dev', '--source', source, env=env)
    assert rejected.returncode == 1
    assert 'error: invalid_dev_source:' in rejected.stderr
    assert not (Path(env['HOME']) / '.myspec' / 'state.json').exists()
    calls = [json.loads(line) for line in npm_log.read_text(encoding='utf-8').splitlines()] if npm_log.exists() else []
    assert ['link'] not in calls


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
    base_python.parent.mkdir()
    launcher = tmp_path / 'Launcher' / 'py.exe'
    launcher.parent.mkdir()
    launcher.touch()
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'venv' / 'Scripts' / 'python.exe'))
    monkeypatch.setattr(sys, '_base_executable', str(base_python))
    assert windows_py_launcher() == launcher








def test_packed_myspec_preserves_modified_requirement_order() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    installed = tmp_path / 'installed'
    installed.mkdir()
    executable, _ = install_packed_myspec(installed)
    titles = ('首部', '中部', '尾部')

    def preview_delta(root: Path, specs: Path, delta: Path) -> tuple[Path, Path]:
        preview = root / 'preview'
        work = root / 'work'
        conflicts = root / 'conflicts.json'
        write(conflicts, '[]')
        for result in (run_cli(executable, 'state-init', work, 'add', 'specs-fingerprint', 'input-fingerprint'), run_cli(executable, 'state-set-conflicts', work, conflicts, 'specs-fingerprint', 'input-fingerprint'), run_cli(executable, 'validate-delta', delta, specs), run_cli(executable, 'apply-delta', specs, delta, preview, work, 'specs-fingerprint', 'input-fingerprint')):
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
        diff = run_cli(executable, 'diff', specs, preview)
        assert diff.returncode == 0, diff.stderr
        assert f'-### Requirement: {target}' not in diff.stdout
        assert f'+### Requirement: {target}' not in diff.stdout
        applied = run_cli(executable, 'apply-delta', specs, delta, specs, work, 'specs-fingerprint', 'input-fingerprint')
        assert applied.returncode == 0, applied.stderr
        assert (specs / 'accounts' / 'spec.md').read_bytes() == (preview / 'accounts' / 'spec.md').read_bytes()
        before_repeat = (specs / 'accounts' / 'spec.md').read_bytes()
        repeated_preview, repeated_work = preview_delta(root / 'repeat', specs, delta)
        repeated = run_cli(executable, 'apply-delta', specs, delta, specs, repeated_work, 'specs-fingerprint', 'input-fingerprint')
        assert repeated.returncode == 0, repeated.stderr
        assert (repeated_preview / 'accounts' / 'spec.md').read_bytes() == before_repeat
        assert (specs / 'accounts' / 'spec.md').read_bytes() == before_repeat
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
    applied = run_cli(executable, 'apply-delta', specs, delta, specs, work, 'specs-fingerprint', 'input-fingerprint')
    assert applied.returncode == 0, applied.stderr
    assert (specs / 'source' / 'spec.md').read_bytes() == (preview / 'source' / 'spec.md').read_bytes()
    assert (specs / 'target' / 'spec.md').read_bytes() == (preview / 'target' / 'spec.md').read_bytes()




def test_spec_ops_cli_validates_applies_all_delta_operations_and_diffs() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
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
    assert '注销' in diff.stdout
    first_apply = apply_ready(SPEC_OPS, specs, delta, specs, work)
    assert first_apply.returncode == 0, first_apply.stderr
    before_repeat = (specs / 'accounts' / 'spec.md').read_bytes()
    repeated_validation = run_python(SPEC_OPS, 'validate-delta', delta, specs)
    assert repeated_validation.returncode == 0, repeated_validation.stderr
    repeated_work = ready_state(SPEC_OPS, tmp_path / 'repeated-state')
    shutil.rmtree(preview)
    repeated_preview = apply_ready(SPEC_OPS, specs, delta, preview, repeated_work)
    assert repeated_preview.returncode == 0, repeated_preview.stderr
    repeated_apply = apply_ready(SPEC_OPS, specs, delta, specs, repeated_work)
    assert repeated_apply.returncode == 0, repeated_apply.stderr
    assert (specs / 'accounts' / 'spec.md').read_bytes() == before_repeat




def test_spec_ops_cli_rejects_invalid_specs_and_delta_references() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
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




def test_spec_ops_cli_rejects_incomplete_or_out_of_order_conflict_state() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    work = tmp_path / '.local' / 'spec-work'
    stale_delta = work / 'current' / 'delta' / 'stale' / 'spec.md'
    write(stale_delta, 'stale')
    refused = run_python(SPEC_OPS, 'state-init', work, 'audit', 'specs-fingerprint', 'input-fingerprint')
    assert refused.returncode != 0
    assert 'current_not_empty' in refused.stderr
    assert stale_delta.read_text(encoding='utf-8') == 'stale\n'
    work = tmp_path / 'fresh-session' / '.local' / 'spec-work'
    assert run_python(SPEC_OPS, 'state-init', work, 'audit', 'specs-fingerprint', 'input-fingerprint').returncode == 0
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


def test_spec_ops_cli_records_each_supported_conflict_decision() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    work = tmp_path / '.local' / 'spec-work'
    conflicts_file = tmp_path / 'conflicts.json'
    conflicts = [{'id': f'conflict-{index}', 'candidate': f'候选 {index}', 'evidence': [f'spec.md:{index}'], 'reason': '需要决定', 'recommendation': '采用建议'} for index in range(4)]
    write(conflicts_file, json.dumps(conflicts, ensure_ascii=False))
    assert run_python(SPEC_OPS, 'state-init', work, 'add', 'specs-fingerprint', 'input-fingerprint').returncode == 0
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


def test_spec_ops_cli_initializes_a_new_capability_from_an_empty_spec_library() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
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


def test_spec_ops_preview_auto_merges_identical_duplicate_requirements_but_main_validation_stays_strict() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    specs = tmp_path / 'specs'
    delta = tmp_path / 'delta'
    preview = tmp_path / 'preview'
    duplicate = requirement('登录', '允许用户登录')
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', duplicate))
    write(specs / 'sessions' / 'spec.md', main_spec('Sessions', duplicate))
    delta.mkdir()
    strict = run_python(SPEC_OPS, 'validate-main', specs)
    assert strict.returncode != 0
    assert 'duplicate_requirement_global: 登录' in strict.stderr
    work = ready_state(SPEC_OPS, tmp_path / 'state', 'review')
    merged = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert merged.returncode == 0, merged.stderr
    assert run_python(SPEC_OPS, 'validate-main', preview).returncode == 0
    assert (preview / 'accounts' / 'spec.md').read_text(encoding='utf-8').count('### Requirement: 登录') == 1
    diff = run_python(SPEC_OPS, 'diff', specs, preview)
    assert diff.returncode == 0
    assert '-### Requirement: 登录' in diff.stdout


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


def test_spec_add_deterministic_post_analysis_flow_previews_diffs_and_applies() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    cli = SPEC_OPS
    specs = tmp_path / 'add' / 'specs'
    delta = tmp_path / 'add' / 'delta'
    preview = tmp_path / 'add' / 'preview'
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', requirement('登录', '允许用户登录')))
    write(delta / 'accounts' / 'spec.md', '## ADDED Requirements\n\n### Requirement: 注销\n\n系统 MUST 允许用户注销。\n\n#### Scenario: 主动注销\n\n- **WHEN** 用户选择注销\n- **THEN** 系统结束会话\n')
    run_confirmed_workflow(cli, specs, delta, preview, '+### Requirement: 注销')
    assert '### Requirement: 注销' in (specs / 'accounts' / 'spec.md').read_text(encoding='utf-8')


def test_spec_review_deterministic_duplicate_flow_previews_diffs_and_applies() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    cli = SPEC_OPS
    specs = tmp_path / 'review' / 'specs'
    delta = tmp_path / 'review' / 'delta'
    preview = tmp_path / 'review' / 'preview'
    duplicate = requirement('登录', '允许用户登录')
    write(specs / 'accounts' / 'spec.md', main_spec('Accounts', duplicate, duplicate))
    delta.mkdir(parents=True)
    run_confirmed_workflow(cli, specs, delta, preview, '-### Requirement: 登录')
    assert (specs / 'accounts' / 'spec.md').read_text(encoding='utf-8').count('### Requirement: 登录') == 1


def test_spec_audit_deterministic_post_analysis_flow_previews_diffs_and_applies() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    cli = SPEC_OPS
    specs = tmp_path / 'audit' / 'missing-specs'
    delta = tmp_path / 'audit' / 'delta'
    preview = tmp_path / 'audit' / 'preview'
    write(delta / 'notifications' / 'spec.md', '# Notifications\n\n## Purpose\n\n描述通知的外部行为。\n\n## ADDED Requirements\n\n### Requirement: 接收通知\n\n系统 MUST 向订阅用户发送通知。\n\n#### Scenario: 新消息\n\n- **WHEN** 新消息到达\n- **THEN** 系统发送通知\n')
    run_confirmed_workflow(cli, specs, delta, preview, '+### Requirement: 接收通知')
    assert (specs / 'notifications' / 'spec.md').is_file()


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




def test_myspec_final_apply_requires_the_confirmed_preview() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
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


def test_myspec_final_apply_rejects_bound_content_drift_after_preview() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
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


def test_myspec_final_apply_rejects_unconfirmed_implementation_identity() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
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


def test_myspec_final_apply_rejects_missing_bound_content_fingerprints() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
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


def test_packed_myspec_codex_doctor_uses_user_home_when_orca_home_is_inherited() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / 'fake-codex')
    env = isolated_myspec_env(tmp_path, prefix, codex_bin)
    user_home = Path(env['USERPROFILE']) / '.codex'
    orca_home = tmp_path / 'orca-user-data' / 'codex-runtime-home' / 'home'
    user_home.mkdir(parents=True, exist_ok=True)
    orca_home.mkdir(parents=True, exist_ok=True)
    env.update({'CODEX_HOME': str(orca_home), 'ORCA_USER_DATA_PATH': str(tmp_path / 'orca-user-data'), 'MYSPEC_CODEX_LOG': str(codex_log), 'MYSPEC_CODEX_STATE': str(codex_state), 'MYSPEC_CODEX_ENV_LOG': str(tmp_path / 'codex-env.log')})
    write(codex_state, json.dumps({'marketplaces': [], 'installed': [], 'available': []}, indent=2))
    diagnosed = run_cli(executable, 'doctor', '--codex', env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)['codex']
    assert report['codexHome'] == str(user_home)
    assert report['codexHomeSource'] == 'orca-user-default'
    assert (tmp_path / 'codex-env.log').read_text(encoding='utf-8').splitlines() == [str(user_home), str(user_home)]
    assert env['CODEX_HOME'] == str(orca_home)
    explicit_home = tmp_path / 'custom-codex-home'
    explicit_home.mkdir()
    (tmp_path / 'codex-env.log').write_text('', encoding='utf-8')
    explicit = run_cli(executable, 'doctor', '--codex', '--codex-home', explicit_home, env=env)
    assert explicit.returncode == 0, explicit.stderr
    report = json.loads(explicit.stdout)['codex']
    assert report['codexHome'] == str(explicit_home)
    assert report['codexHomeSource'] == 'explicit'
    assert (tmp_path / 'codex-env.log').read_text(encoding='utf-8').splitlines() == [str(explicit_home), str(explicit_home)]
    assert env['CODEX_HOME'] == str(orca_home)
    initialized = run_cli(executable, 'init', '--codex', '--codex-home', explicit_home, env=env)
    assert initialized.returncode == 0, initialized.stderr
    assert (explicit_home / 'config.toml').is_file()
    assert env['CODEX_HOME'] == str(orca_home)


def test_packed_myspec_explicit_codex_home_errors_without_codex() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    executable, installed_package = install_packed_myspec(tmp_path)
    env = isolated_myspec_env(tmp_path, npm_prefix_for(installed_package))
    missing_home = tmp_path / 'missing-codex-home'
    diagnosed = run_cli(executable, 'doctor', '--codex', '--codex-home', missing_home, env=env)
    assert diagnosed.returncode == 1
    assert f'error: codex_home_unavailable: {missing_home}: directory does not exist' in diagnosed.stderr


def test_packed_myspec_bare_doctor_does_not_require_codex_home() -> None:
    tmp_path = REPO_ROOT / '__myspec_documents__'
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / 'fake-codex')
    env = isolated_myspec_env(tmp_path, prefix, codex_bin)
    bad_codex_home = tmp_path / 'invalid-codex-home'
    bad_codex_home.write_text('not a directory', encoding='utf-8')
    env.update({'CODEX_HOME': str(bad_codex_home), 'MYSPEC_CODEX_LOG': str(codex_log), 'MYSPEC_CODEX_STATE': str(codex_state)})
    env.pop('ORCA_CODEX_HOME', None)
    env.pop('ORCA_USER_DATA_PATH', None)
    write(codex_state, json.dumps({'marketplaces': 'broken', 'installed': [], 'available': []}))
    diagnosed = run_cli(executable, 'doctor', env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    assert not {'pi', 'claude', 'codex'}.intersection(json.loads(diagnosed.stdout))
    assert not codex_log.exists()
