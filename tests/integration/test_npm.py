from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.support.npm_candidates import candidate_for, copy_install

REPO_ROOT = Path(__file__).resolve().parents[2]
_MYSPEC_SKILL_NAMES = ("my-spec", "my-spec-add", "my-spec-review", "my-spec-audit")



def _installed_build_and_verify(tmp_path: Path) -> tuple[Path, Path]:
    candidate = candidate_for("build-and-verify")
    prefix = tmp_path / "prefix"
    executable, _ = copy_install(candidate, prefix)
    return prefix, executable


def _budget_run(tmp_path: Path, checks: list[dict]) -> tuple[subprocess.CompletedProcess, Path]:
    project = tmp_path / "project"
    (project / ".build-and-verify").mkdir(parents=True)
    config = {"version": 1, "verify": {"fullBudgetSeconds": 3, "checks": checks}}
    (project / ".build-and-verify/config.json").write_text(json.dumps(config), encoding="utf-8")
    initialized = subprocess.run(["git", "init", str(project)], capture_output=True)
    assert initialized.returncode == 0
    env = {**os.environ, "BUILD_AND_VERIFY_PYTHON": sys.executable,
        "GITHUB_ACTIONS": "false", "CI": "false", "BUILD_AND_VERIFY_EXECUTION_CONTEXT": "local"}
    package = candidate_for("build-and-verify").installed_package
    started = time.monotonic()
    result = subprocess.run([shutil.which("node"), str(package / "bin/build-and-verify.js"),
        "verify", "--project", str(project), "--full"],
        env=env, capture_output=True, text=True, timeout=8)
    result.public_elapsed_seconds = time.monotonic() - started
    return result, project


def _assert_pid_terminated(pid: int) -> None:
    if sys.platform == "win32":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            assert ctypes.get_last_error() == 87, "cannot prove owned descendant terminated"
            return
        code = ctypes.c_ulong()
        try:
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
            assert code.value != 259, f"owned descendant {pid} is still running"
        finally:
            kernel.CloseHandle(handle)
    else:
        # Linux may retain a terminated orphan as a zombie until init reaps it.
        stat = Path(f"/proc/{pid}/stat")
        if sys.platform.startswith("linux") and stat.exists():
            try:
                if stat.read_text().rsplit(")", 1)[1].split()[0] == "Z":
                    return
            except FileNotFoundError:
                return
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def _isolated_env(tmp_path: Path, prefix: Path) -> dict[str, str]:
    home = tmp_path / "home"
    for path in (home, home / "AppData" / "Roaming", home / ".config", home / ".pi" / "agent", home / ".codex", home / ".claude"):
        path.mkdir(parents=True, exist_ok=True)
    return {
        **os.environ,
        "NPM_CONFIG_PREFIX": str(prefix),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "PI_CODING_AGENT_DIR": str(home / ".pi" / "agent"),
        "CODEX_HOME": str(home / ".codex"),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
    }


def _myspec_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _myspec_controlled_git_script(git: str, remote: Path) -> str:
    return (
        "import subprocess\nimport sys\n"
        f"git = {git!r}\n"
        "def run_git(*args):\n"
        "    command = [git, *args]\n"
        "    shell = git.lower().endswith('.cmd')\n"
        "    if shell:\n"
        "        command = subprocess.list2cmdline(command)\n"
        "    return subprocess.run(command, shell=shell)\n"
        "args = sys.argv[1:]\n"
        "if args == ['remote', 'get-url', 'origin']:\n"
        "    print('https://github.com/liuli195/my-agent-skills')\n"
        "    raise SystemExit()\n"
        "if args == ['ls-remote', 'origin']:\n"
        f"    raise SystemExit(run_git('ls-remote', {remote.as_uri()!r}).returncode)\n"
        "raise SystemExit(run_git(*args).returncode)"
    )


def _myspec_real_controlled_dev_source(tmp_path: Path, marker: str | None = None) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    for name in (".gitattributes", ".gitignore"):
        shutil.copy2(REPO_ROOT / name, source / name)
    for relative in (".agents", ".claude-plugin", "plugins/my-spec", "plugins/tool-lifecycle"):
        shutil.copytree(
            REPO_ROOT / relative,
            source / relative,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    if marker is not None:
        _myspec_write(source / "plugins" / "my-spec" / "skills" / "my-spec" / "dev-marker.txt", marker)
    launcher = source / "plugins" / "my-spec" / "bin" / "myspec.js"
    launcher.chmod(launcher.stat().st_mode | 0o111)
    remote = tmp_path / "origin.git"
    for command in (
        ["git", "init", "--bare", remote],
        ["git", "init", source],
        ["git", "-C", source, "add", "."],
        ["git", "-C", source, "-c", "user.name=MySpec Test", "-c", "user.email=myspec@example.invalid", "commit", "-m", "development source"],
        ["git", "-C", source, "checkout-index", "--force", "--", "plugins/my-spec/bin/myspec.js"],
        # Seed before registering origin so Git cannot create a tracking ref.
        ["git", "-C", source, "push", remote.as_uri(), "HEAD:refs/heads/main"],
        ["git", "-C", source, "remote", "add", "origin", "https://github.com/liuli195/my-agent-skills"],
        ["git", "-C", source, "config", f"url.{remote.as_uri()}.insteadOf", "https://github.com/liuli195/my-agent-skills"],
    ):
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stderr
    git = shutil.which("git")
    assert git is not None
    bin_dir = tmp_path / "controlled-git"
    bin_dir.mkdir()
    if os.name == "nt":
        script = bin_dir / "git.py"
        _myspec_write(script, _myspec_controlled_git_script(git, remote))
        python_command = f'@"{sys.executable}" "{script}" %*'
        command = python_command
        if Path(git).suffix.lower() == ".exe":
            command = (
                '@echo off\nsetlocal DisableDelayedExpansion\n'
                'if "%~1"=="remote" goto controlled\n'
                'if "%~1"=="ls-remote" goto controlled\n'
                f'"{Path(git).resolve()}" %*\nexit /b %ERRORLEVEL%\n'
                f':controlled\n{python_command}\nexit /b %ERRORLEVEL%'
            )
        _myspec_write(bin_dir / "git.cmd", command)
    else:
        wrapper = bin_dir / "git"
        _myspec_write(wrapper, f'#!/bin/sh\nif [ "$1" = remote ] && [ "$2" = get-url ] && [ "$3" = origin ]; then echo https://github.com/liuli195/my-agent-skills; exit; fi\nif [ "$1" = ls-remote ] && [ "$2" = origin ]; then exec "{git}" ls-remote "{remote.as_uri()}"; fi\nexec "{git}" "$@"')
        wrapper.chmod(0o755)
    return source


def _myspec_controlled_dev_env(env: dict[str, str], source: Path) -> dict[str, str]:
    path_entries = [str(source.parent / "controlled-git"), env["PATH"]]
    if os.name == "nt":
        # Git for Windows' mingw executable launches its bundled shell.
        git_shell = shutil.which("sh")
        if git_shell is not None:
            path_entries.append(str(Path(git_shell).parent))
    return {**env, "PATH": os.pathsep.join(dict.fromkeys(path_entries))}


def _myspec_install_fake_claude(root: Path) -> tuple[Path, Path, Path]:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    script = root / "fake_claude.py"
    log = root / "claude.log"
    state = root / "claude-state.json"
    _myspec_write(
        script,
        """import json
import os
import shutil
import sys
from pathlib import Path

arguments = sys.argv[1:]
state_path = Path(os.environ["MYSPEC_CLAUDE_STATE"])
state = json.loads(state_path.read_text(encoding="utf-8"))
with Path(os.environ["MYSPEC_CLAUDE_LOG"]).open("a", encoding="utf-8") as log:
    log.write(json.dumps(arguments) + "\\n")

def save():
    state_path.write_text(json.dumps(state, indent=2) + "\\n", encoding="utf-8")

def marketplace(name):
    return next((item for item in state["marketplaces"] if item["name"] == name), None)

def plugin(identifier):
    return next((item for item in state["plugins"] if item["id"] == identifier), None)

def refresh(identifier):
    name, market_name = identifier.split("@", 1)
    market = marketplace(market_name)
    if market is None or market.get("source") != "directory":
        print("missing local marketplace", file=sys.stderr)
        raise SystemExit(1)
    source = Path(market["path"])
    manifest = json.loads((source / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    target = Path(os.environ["MYSPEC_CLAUDE_HOME"]) / "plugins" / "cache" / market_name / name / manifest["version"]
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    current = plugin(identifier)
    record = {
        "id": identifier,
        "version": os.environ.get("MYSPEC_CLAUDE_REPORTED_VERSION", manifest["version"]),
        "scope": "user",
        "enabled": current["enabled"] if current else True,
        "installPath": str(target),
    }
    if current:
        state["plugins"][state["plugins"].index(current)] = record
    else:
        state["plugins"].append(record)
    save()

if arguments == ["plugin", "marketplace", "list", "--json"]:
    print(json.dumps(state["marketplaces"]))
elif arguments == ["plugin", "list", "--json"]:
    print(json.dumps(state["plugins"]))
elif arguments[:3] == ["plugin", "marketplace", "add"] and len(arguments) == 4:
    source = Path(arguments[3])
    manifest = json.loads((source / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    if marketplace(manifest["name"]) is None:
        state["marketplaces"].append({
            "name": manifest["name"],
            "source": "directory",
            "path": str(source),
            "installLocation": str(source),
        })
        save()
elif arguments[:2] == ["plugin", "install"] and arguments[3:] == ["--scope", "user"]:
    if os.environ.get("MYSPEC_CLAUDE_FAIL_INSTALL") == "1":
        print("simulated install failure", file=sys.stderr)
        raise SystemExit(1)
    refresh(arguments[2])
    if os.environ.get("MYSPEC_CLAUDE_FAIL_AFTER_INSTALL") == "1":
        print("simulated interruption after install", file=sys.stderr)
        raise SystemExit(1)
elif arguments[:2] == ["plugin", "update"] and arguments[3:] == ["--scope", "user"]:
    current = plugin(arguments[2])
    name, market_name = arguments[2].split("@", 1)
    source = Path(marketplace(market_name)["path"])
    version = json.loads((source / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    if current is None or current["version"] != version:
        refresh(arguments[2])
elif arguments[:2] == ["plugin", "uninstall"] and arguments[3:] == ["--scope", "user", "--keep-data"]:
    current = plugin(arguments[2])
    if current is None:
        print("missing plugin", file=sys.stderr)
        raise SystemExit(1)
    if os.environ.get("MYSPEC_CLAUDE_UNINSTALL_NOOP") != "1":
        state["plugins"].remove(current)
        save()
    if os.environ.get("MYSPEC_CLAUDE_FAIL_AFTER_UNINSTALL") == "1":
        print("simulated interruption after uninstall", file=sys.stderr)
        raise SystemExit(1)
elif arguments[:2] in (["plugin", "enable"], ["plugin", "disable"]) and arguments[3:] == ["--scope", "user"]:
    current = plugin(arguments[2])
    if current is None:
        print("missing plugin", file=sys.stderr)
        raise SystemExit(1)
    current["enabled"] = arguments[1] == "enable"
    save()
    if os.environ.get("MYSPEC_CLAUDE_FAIL_AFTER_ENABLED") == str(current["enabled"]).lower():
        print("simulated interruption after enabled state", file=sys.stderr)
        raise SystemExit(1)
elif arguments[:3] == ["plugin", "marketplace", "update"] and len(arguments) == 4:
    if marketplace(arguments[3]) is None:
        raise SystemExit(1)
else:
    raise SystemExit(2)
""",
    )
    if sys.platform == "win32":
        launcher = bin_dir / "claude.cmd"
        _myspec_write(launcher, f'@"{sys.executable}" "{script}" %*')
    else:
        launcher = bin_dir / "claude"
        _myspec_write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
        launcher.chmod(0o755)
    return bin_dir, log, state


def _myspec_install_fake_codex(root: Path) -> tuple[Path, Path, Path]:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    script = root / "fake_codex.py"
    log = root / "codex.log"
    state = root / "codex-state.json"
    _myspec_write(
        script,
        '''import json
import os
import re
import shutil
import sys
from pathlib import Path

arguments = sys.argv[1:]
state_path = Path(os.environ["MYSPEC_CODEX_STATE"])
state = json.loads(state_path.read_text(encoding="utf-8"))
config_path = Path(os.environ["CODEX_HOME"]) / "config.toml"
with Path(os.environ["MYSPEC_CODEX_LOG"]).open("a", encoding="utf-8") as log:
    log.write(json.dumps(arguments) + "\\n")
environment_log = os.environ.get("MYSPEC_CODEX_ENV_LOG")
if environment_log:
    with Path(environment_log).open("a", encoding="utf-8") as log:
        log.write(os.environ.get("CODEX_HOME", "") + "\\n")

def save():
    state_path.write_text(json.dumps(state, indent=2) + "\\n", encoding="utf-8")

def marketplace(name):
    return next((item for item in state["marketplaces"] if item["name"] == name), None)

def plugin(identifier):
    return next((item for item in state["installed"] if item["pluginId"] == identifier), None)

def set_enabled(identifier, enabled):
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    header = f'[plugins."{identifier}"]'
    pattern = re.compile(rf'(?ms)^\\[plugins\\."{re.escape(identifier)}"\\]\\s*\\n(?P<body>.*?)(?=^\\[|\\Z)')
    match = pattern.search(text)
    body = f"enabled = {'true' if enabled else 'false'}\\n"
    if match:
        current = match.group("body")
        current = re.sub(r"(?m)^enabled\\s*=.*$", body.rstrip(), current, count=1) if re.search(r"(?m)^enabled\\s*=", current) else body + current
        text = text[:match.start("body")] + current + text[match.end("body"):]
    else:
        text = text.rstrip() + ("\\n\\n" if text.strip() else "") + header + "\\n" + body
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(text, encoding="utf-8")

def remove_config(identifier):
    if not config_path.exists():
        return
    text = config_path.read_text(encoding="utf-8")
    pattern = re.compile(rf'(?ms)^\\[plugins\\."{re.escape(identifier)}"\\]\\s*\\n.*?(?=^\\[|\\Z)')
    config_path.write_text(pattern.sub("", text), encoding="utf-8")

def configured_enabled(identifier):
    if not config_path.exists():
        return False
    text = config_path.read_text(encoding="utf-8")
    pattern = re.compile(rf'(?ms)^\\[plugins\\."{re.escape(identifier)}"\\]\\s*\\n(?P<body>.*?)(?=^\\[|\\Z)')
    match = pattern.search(text)
    return bool(match and re.search(r"(?m)^enabled\\s*=\\s*true\\s*$", match.group("body")))

def install(identifier):
    name, market_name = identifier.split("@", 1)
    market = marketplace(market_name)
    if market is None:
        print("missing marketplace", file=sys.stderr)
        raise SystemExit(1)
    root = Path(market["root"])
    catalog = json.loads((root / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    entry = next((item for item in catalog["plugins"] if item["name"] == name), None)
    if entry is None:
        print("missing plugin", file=sys.stderr)
        raise SystemExit(1)
    relative = entry["source"]["path"]
    source = (root / relative).resolve()
    manifest = json.loads((source / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    target = Path(os.environ["CODEX_HOME"]) / "plugins" / "cache" / market_name / name / manifest["version"]
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    current = plugin(identifier)
    record = {
        "pluginId": identifier,
        "name": name,
        "marketplaceName": market_name,
        "version": os.environ.get("MYSPEC_CODEX_REPORTED_VERSION", manifest["version"]),
        "installed": True,
        "source": {"source": "local", "path": str(source)},
        "marketplaceSource": market.get("marketplaceSource"),
        "installPolicy": "AVAILABLE",
        "authPolicy": "ON_INSTALL",
    }
    if current:
        state["installed"][state["installed"].index(current)] = record
    else:
        state["installed"].append(record)
    set_enabled(identifier, True)
    save()

if arguments == ["plugin", "marketplace", "list", "--json"]:
    print(json.dumps({"marketplaces": state["marketplaces"]}))
elif arguments == ["plugin", "list", "--json"]:
    installed = [{**item, "enabled": configured_enabled(item["pluginId"])} for item in state["installed"]]
    print(json.dumps({"installed": installed, "available": state["available"]}))
elif arguments[:3] == ["plugin", "marketplace", "add"] and arguments[-1:] == ["--json"]:
    requested = Path(arguments[3])
    source = requested.resolve()
    catalog = json.loads((source / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    if marketplace(catalog["name"]) is None:
        state["marketplaces"].append({
            "name": catalog["name"],
            "root": str(source),
            "marketplaceSource": {"sourceType": "local", "source": str(source)},
        })
        save()
    print(json.dumps({"name": catalog["name"], "root": str(source)}))
elif arguments[:2] == ["plugin", "add"] and arguments[-1:] == ["--json"]:
    install(arguments[2])
    if os.environ.get("MYSPEC_CODEX_FAIL_AFTER_ADD") == "1":
        print("simulated interruption after add", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({"pluginId": arguments[2]}))
elif arguments[:2] == ["plugin", "remove"] and arguments[-1:] == ["--json"]:
    current = plugin(arguments[2])
    if current is None:
        print("missing plugin", file=sys.stderr)
        raise SystemExit(1)
    if os.environ.get("MYSPEC_CODEX_REMOVE_NOOP") != "1":
        target = Path(os.environ["CODEX_HOME"]) / "plugins" / "cache" / current["marketplaceName"] / current["name"] / current["version"]
        if target.exists():
            shutil.rmtree(target)
        state["installed"].remove(current)
        remove_config(arguments[2])
        save()
    if os.environ.get("MYSPEC_CODEX_FAIL_AFTER_REMOVE") == "1":
        print("simulated interruption after remove", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({"pluginId": arguments[2]}))
else:
    raise SystemExit(2)
''',
    )
    if sys.platform == "win32":
        launcher = bin_dir / "codex.cmd"
        _myspec_write(launcher, f'@"{sys.executable}" "{script}" %*')
    else:
        launcher = bin_dir / "codex"
        _myspec_write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
        launcher.chmod(0o755)
    return bin_dir, log, state


def _myspec_install_fake_npm(root: Path) -> tuple[Path, Path]:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    script = root / "fake_npm.py"
    log = root / "npm.log"
    log.touch()
    npm = shutil.which("npm")
    assert npm is not None
    _myspec_write(
        script,
        """import json
import os
import subprocess
import sys
from pathlib import Path

arguments = sys.argv[1:]
with Path(os.environ["MYSPEC_NPM_LOG"]).open("a", encoding="utf-8") as log:
    log.write(json.dumps(arguments) + "\\n")
if arguments == ["view", "@liuli195/myspec", "version", "--json"]:
    print(json.dumps(os.environ.get("MYSPEC_NPM_LATEST", os.environ["MYSPEC_PACKAGE_VERSION"])))
    raise SystemExit(0)
if arguments == ["root", "--global"] and os.environ.get("MYSPEC_NPM_FAIL_ROOT") == "1":
    print("simulated npm root failure", file=sys.stderr)
    raise SystemExit(1)
if arguments[:2] == ["install", "--global"]:
    if os.environ.get("MYSPEC_NPM_FAIL_INSTALL") == "1":
        print("simulated install failure", file=sys.stderr)
        raise SystemExit(1)
    arguments[-1] = os.environ["MYSPEC_RELEASE_TARBALL"]
allowed = arguments in (["root", "--global"], ["prefix", "--global"], ["link"]) or (
    arguments[:2] == ["install", "--global"] and len(arguments) == 6
    and arguments[2:5] == ["--ignore-scripts", "--no-audit", "--no-fund"]
)
if not allowed:
    print("unsupported fake npm command", file=sys.stderr)
    raise SystemExit(127)
command = [os.environ["MYSPEC_REAL_NPM"], *arguments]
if os.name == "nt":
    result = subprocess.run(subprocess.list2cmdline(command), shell=True)
else:
    result = subprocess.run(command)
if arguments[:2] == ["install", "--global"] and result.returncode == 0 and os.environ.get("MYSPEC_NPM_FAIL_AFTER_INSTALL") == "1":
    print("simulated interruption after npm install", file=sys.stderr)
    raise SystemExit(1)
raise SystemExit(result.returncode)
""",
    )
    if sys.platform == "win32":
        launcher = bin_dir / "npm.cmd"
        _myspec_write(launcher, f'@"{sys.executable}" "{script}" %*')
    else:
        launcher = bin_dir / "npm"
        _myspec_write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
        launcher.chmod(0o755)
    return bin_dir, log


def _myspec_isolated_myspec_env(
    tmp_path: Path,
    prefix: Path,
    *extra_paths: Path,
) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    package_bin = prefix if os.name == "nt" else prefix / "bin"
    path_entries = [str(package_bin), *(str(path) for path in extra_paths)]
    command_paths = [shutil.which(command) for command in ("node", "npm", "git")]
    if os.name == "nt":
        path_entries.extend(
            str(Path(path).parent) for path in command_paths if path is not None
        )
        path_entries.append(str(Path(sys.executable).parent))
    else:
        command_bin = tmp_path / "system-commands"
        command_bin.mkdir(exist_ok=True)
        for path in command_paths:
            assert path is not None
            link = command_bin / Path(path).name
            if not link.exists():
                link.symlink_to(Path(path).resolve())
        path_entries.append(str(command_bin))
    return {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PI_CODING_AGENT_DIR": str(home / ".pi" / "agent"),
        "NPM_CONFIG_PREFIX": str(prefix),
        "MYSPEC_PYTHON": sys.executable,
        "MYSPEC_PACKAGE_VERSION": os.environ.get("MYSPEC_PACKAGE_VERSION", ""),
        "PATH": os.pathsep.join(path_entries),
    }


def _myspec_run_cli(executable: Path, *args: object, env=None, cwd=None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(executable), *(str(arg) for arg in args)],
                          cwd=cwd, env=env, text=True, capture_output=True, check=False)


def _myspec_install_packed_myspec(tmp_path: Path) -> tuple[Path, Path]:
    return copy_install(candidate_for("myspec"), tmp_path / "npm-prefix")


class TestBuildAndVerify:
    def test_packed_public_init_build_and_python_parallel_protection(self, tmp_path: Path) -> None:
        prefix, executable = _installed_build_and_verify(tmp_path)
        env = {**_isolated_env(tmp_path, prefix), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTEST_ADDOPTS": "-n 2"}
        project = tmp_path / "project"
        initialized = subprocess.run([executable, "init", "--project", str(project)],
            env=env, text=True, capture_output=True, check=False)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        build_dir = project / ".build-and-verify"
        config_path = build_dir / "config.json"
        assert json.loads(config_path.read_text()) == {
            "version": 2, "build": {"checks": []}, "verify": {"realChecks": [], "checks": []}}
        assert (build_dir / ".gitignore").read_text() == "/cache/\n/runs/\n/backups/\n"
        assert (build_dir / "cache").is_dir()
        build_config = {"version": 2, "build": {"checks": [
            {"id": "build", "command": [sys.executable, "-c", "print('PACKED_BUILD_OK')"]}]},
            "verify": {"realChecks": [], "checks": []}}
        config_path.write_text(json.dumps(build_config))
        built = subprocess.run([executable, "build", "--project", str(project)],
            env=env, text=True, capture_output=True, check=False)
        assert built.returncode == 0, built.stdout + built.stderr
        assert "PACKED_BUILD_OK" in built.stdout and "checked: build" in built.stdout
        (project / "test_memory.py").write_text(
            "import sqlite3, unittest, time\n"
            "class Memory(unittest.TestCase):\n"
            " def test_read_and_memory(self):\n"
            "  time.sleep(0.6)\n"
            "  self.assertEqual(open('data.txt').read(), 'READABLE')\n"
            "  self.assertEqual(sqlite3.connect(':memory:').execute('select 42').fetchone(), (42,))\n"
            "def test_second():\n time.sleep(0.6)\n assert sum([1, 2, 3]) == 6\n")
        (project / "conftest.py").write_text(
            "import os, time, pytest\nintervals=[]\n"
            "@pytest.hookimpl(hookwrapper=True)\n"
            "def pytest_runtest_call(item):\n"
            " start=time.monotonic(); yield\n"
            " item.user_properties.append(('execution', (os.getpid(), start, time.monotonic())))\n"
            "def pytest_runtest_logreport(report):\n"
            " if report.when == 'call': intervals.extend(v for k,v in report.user_properties if k == 'execution')\n"
            "def pytest_sessionfinish(session):\n"
            " if not hasattr(session.config, 'workerinput'):\n"
            "  assert len({x[0] for x in intervals}) == 2\n"
            "  assert max(x[1] for x in intervals) < min(x[2] for x in intervals)\n")
        (project / "data.txt").write_text("READABLE")
        config = {"version": 2, "verify": {"realChecks": [], "maxParallel": 2, "checks": [
            {"id": name, "command": [sys.executable, "-m", "pytest", "-q", "-p", "xdist.plugin", "test_memory.py"],
             "checkParallel": True, "inputs": ["test_memory.py", "data.txt", "conftest.py"]}
            for name in ("memory-a", "memory-b")]}}
        config_path = project / ".build-and-verify/config.json"
        config_path.write_text(json.dumps(config))
        def verify():
            return subprocess.run([executable, "verify", "--project", str(project), "--execution-context", "cloud"],
                env=env, text=True, capture_output=True, check=False, timeout=25)
        allowed = verify()
        assert allowed.returncode == 0, allowed.stdout + allowed.stderr
        assert allowed.stdout.count("2 passed") == 2
        proofs = [json.loads(line.removeprefix("runtime-guard: ")) for line in allowed.stdout.splitlines()
                  if line.startswith("runtime-guard: ")]
        assert len(proofs) == 2 and all(proof["workers"] == 2 for proof in proofs)
        assert max(proof["started"] for proof in proofs) < min(proof["finished"] for proof in proofs)

        (project / "conftest.py").write_text("")
        (project / "test_memory.py").write_text(
            "from pathlib import Path\n"
            "def test_protected():\n"
            " try: Path('python-effect').write_text('forbidden')\n"
            " except PermissionError: pass\n")
        blocked = verify()
        assert blocked.returncode == 1, blocked.stdout + blocked.stderr
        assert "runtime_guard_violation" in blocked.stderr
        assert "python-effect" in blocked.stderr
        assert not (project / "python-effect").exists()
        assert "cache-hit:" not in blocked.stdout


    def test_packed_node_parallel_protection(self, tmp_path: Path) -> None:
        prefix, executable = _installed_build_and_verify(tmp_path)
        env = _isolated_env(tmp_path, prefix)
        project = tmp_path / "project"
        (project / ".build-and-verify").mkdir(parents=True)
        (project / "data.txt").write_text("READABLE")
        for name in ("first", "second"):
            (project / f"{name}.test.mjs").write_text(
                "import test from 'node:test'; import assert from 'node:assert/strict';\n"
                "import {readFileSync} from 'node:fs';\n"
                "import {DatabaseSync} from 'node:sqlite';\n"
                "test('memory', async () => {\n"
                " const started=Number(process.hrtime.bigint())/1e9;\n"
                " assert.equal(readFileSync('data.txt','utf8'), 'READABLE');\n"
                " assert.equal(new DatabaseSync(':memory:').prepare('select 42 as v').get().v,42);\n"
                " await new Promise(resolve=>setTimeout(resolve, 600));\n"
                " console.log('NODE_INTERVAL:' + JSON.stringify({pid:process.pid,started,finished:Number(process.hrtime.bigint())/1e9}));\n"
                "});\n")
        (project / "memory-control.cjs").write_text(
            "const {Worker,isMainThread}=require('node:worker_threads');\n"
            "if(isMainThread && !process.env.NODE_TEST_CONTEXT) {\n"
            " new Worker(`require('node:worker_threads').parentPort.postMessage(42)`,{eval:true,env:{}})\n"
            " .on('message',value=>{require('node:assert/strict').equal(value,42);console.log('CONTROL_THREAD_OK');});}\n")
        config = {"version": 2, "verify": {"realChecks": [], "maxParallel": 2, "checks": [
            {"id": name, "command": [shutil.which("node"), "--test", "--test-concurrency=2", "--test-reporter=tap", "--require", "./memory-control.cjs",
                "first.test.mjs", "second.test.mjs"], "checkParallel": True,
             "inputs": ["first.test.mjs", "second.test.mjs", "data.txt", "memory-control.cjs"]} for name in ("node-a", "node-b")]}}
        config_path = project / ".build-and-verify/config.json"
        config_path.write_text(json.dumps(config))
        def verify():
            return subprocess.run([executable, "verify", "--project", str(project), "--execution-context", "cloud"],
                env=env, text=True, capture_output=True, check=False, timeout=25)
        allowed = verify()
        assert allowed.returncode == 0, allowed.stdout + allowed.stderr
        assert allowed.stdout.count("CONTROL_THREAD_OK") == 2
        intervals = [json.loads(line.split("NODE_INTERVAL:", 1)[1]) for line in allowed.stdout.splitlines()
                     if "NODE_INTERVAL:" in line]
        assert len(intervals) == 4 and len({item["pid"] for item in intervals}) == 4
        assert max(item["started"] for item in intervals) < min(item["finished"] for item in intervals)
        proofs = [json.loads(line.removeprefix("runtime-guard: ")) for line in allowed.stdout.splitlines()
                  if line.startswith("runtime-guard: ")]
        assert len(proofs) == 2 and all(proof["workers"] == 3 for proof in proofs)

        (project / "first.test.mjs").write_text(
            "import test from 'node:test'; import {writeFileSync} from 'node:fs';\n"
            "test('protected',()=>{try {writeFileSync('node-effect','forbidden');} catch {}});\n")
        blocked = verify()
        assert blocked.returncode == 1, blocked.stdout + blocked.stderr
        assert "runtime_guard_violation" in blocked.stderr
        assert "node-effect" in blocked.stderr
        assert not (project / "node-effect").exists()
        assert "cache-hit:" not in blocked.stdout


    def test_public_budget_stops_checks_and_owned_descendants(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "descendant.pid"
        child = "import time; time.sleep(10)"
        parent = ("import subprocess,sys,time; from pathlib import Path; "
            f"child=subprocess.Popen([sys.executable,'-S','-c',{child!r}]); "
            f"Path({str(pid_file)!r}).write_text(str(child.pid)); time.sleep(10)")
        result, project = _budget_run(tmp_path, checks=[
            {"id": "tree", "command": [sys.executable, "-S", "-c", parent], "inputs": []},
            {"id": "later", "command": [sys.executable, "-c", "print('LATER_STARTED')"], "inputs": []},
        ])
        assert result.returncode == 1, result.stdout + result.stderr
        assert result.public_elapsed_seconds < 5
        assert "total_budget_timeout" in result.stdout + result.stderr
        assert "LATER_STARTED" not in result.stdout
        assert pid_file.exists(), result.stdout + result.stderr
        _assert_pid_terminated(int(pid_file.read_text()))
        report = json.loads((project / ".build-and-verify/runs/performance-report.json").read_text())
        assert report["verificationStatus"] == "failed"
        assert report["reason"] == "total_budget_timeout"
        assert report["notStarted"] == ["later"]
        assert not list((project / ".build-and-verify/cache").glob("*.json"))



class TestMySpec:
    @pytest.fixture(autouse=True)
    def _package_version(self, npm_candidate, monkeypatch):
        version = json.loads((npm_candidate.installed_package / "package.json").read_text())["version"]
        monkeypatch.setenv("MYSPEC_PACKAGE_VERSION", version)

    def test_packed_bare_cli_confirms_preview_and_preserves_untouched_bytes(self,
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, npm_candidate,
    ) -> None:
        from tests.support.myspec_cases import main_spec, npm_prefix_for, requirement
        executable, package = _myspec_install_packed_myspec(tmp_path)
        assert not list(package.rglob("__pycache__"))
        assert not list(package.rglob("*.pyc"))
        assert {path.name for path in (package / "skills").iterdir()} == set(_MYSPEC_SKILL_NAMES)
        for manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            assert (package / manifest).is_file()
        assert [path.relative_to(package).as_posix() for path in package.rglob("spec_ops.py")] == ["python/spec_ops.py"]
        host = tmp_path / "host-bin"
        host.mkdir()
        marker = tmp_path / "host-myspec.used"
        script = host / "host.py"
        _myspec_write(script, f"from pathlib import Path\nPath({str(marker)!r}).write_text('used')\nraise SystemExit(99)")
        command = host / ("myspec.cmd" if os.name == "nt" else "myspec")
        _myspec_write(command, f'@"{sys.executable}" "{script}" %*' if os.name == "nt"
            else f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
        command.chmod(0o755)
        monkeypatch.setenv("PATH", os.pathsep.join((str(host), os.environ["PATH"])))
        assert Path(shutil.which("myspec")).resolve() == command.resolve()
        env = _myspec_isolated_myspec_env(tmp_path, npm_prefix_for(package))
        assert Path(shutil.which("myspec", path=env["PATH"])).resolve() == executable.resolve()
        project = tmp_path / "consumer"
        specs, delta = project / "myspec/specs", project / "myspec/delta"
        preview, work = project / ".local/preview", project / ".local/spec-work"
        _myspec_write(specs / "accounts/spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
        for name in ("lf", "crlf"):
            untouched = main_spec(name, requirement(name + "资料", "显示姓名"))
            raw = (untouched if name == "lf" else untouched.replace("\n", "\r\n")).encode()
            path = specs / name / "spec.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(raw)
        before = {name: (specs / name / "spec.md").read_bytes() for name in ("lf", "crlf")}
        _myspec_write(delta / "accounts/spec.md", "## MODIFIED Requirements\n\n" + requirement("登录", "允许密码登录"))
        conflict = {"id": "login", "candidate": "密码登录", "evidence": ["request"],
            "reason": "需要确认", "recommendation": "accept"}
        conflicts = project / "conflicts.json"
        _myspec_write(conflicts, json.dumps([conflict], ensure_ascii=False))
        def run(*args):
            return subprocess.run(["myspec", *map(str, args)], cwd=project, env=env,
                text=True, capture_output=True, check=False, shell=os.name == "nt")
        # This also exercises the native Windows command shim and Python launch.
        help_result = run("--help")
        assert help_result.returncode == 0, help_result.stderr
        assert help_result.stdout.startswith("usage: myspec ")
        for args in (("validate-main", specs), ("validate-delta", delta, specs),
                     ("state-init", work, "add", "specs", "input"),
                     ("state-set-conflicts", work, conflicts, "specs", "input")):
            result = run(*args)
            assert result.returncode == 0, result.stderr
        current = run("state-current", work, "specs", "input")
        assert current.returncode == 0, current.stderr
        assert json.loads(current.stdout)["conflict"] == conflict
        decided = run("state-decide", work, "login", "accept", "specs", "input")
        assert decided.returncode == 0, decided.stderr
        assert json.loads(decided.stdout)["status"] == "READY_TO_APPLY"
        previewed = run("apply-delta", specs, delta, preview, work, "specs", "input")
        assert previewed.returncode == 0, previewed.stderr
        difference = run("diff", specs, preview)
        assert difference.returncode == 0, difference.stderr
        assert "允许密码登录" in difference.stdout
        applied = run("apply-delta", specs, delta, specs, work, "specs", "input")
        assert applied.returncode == 0, applied.stderr
        assert "允许密码登录" in (specs / "accounts/spec.md").read_text(encoding="utf-8")
        for name, raw in before.items():
            assert (preview / name / "spec.md").read_bytes() == raw
            assert (specs / name / "spec.md").read_bytes() == raw
        assert not work.exists()
        assert not any(path.name.startswith(".my-spec-") for path in specs.parent.iterdir())
        assert not marker.exists()


    def test_packed_lifecycle_switch_refreshes_both_clients(self, tmp_path: Path, npm_candidate) -> None:
        from tests.support.myspec_cases import npm_prefix_for
        executable, package = _myspec_install_packed_myspec(tmp_path)
        prefix = npm_prefix_for(package)
        npm_bin, npm_log = _myspec_install_fake_npm(tmp_path / "fake-npm")
        claude_bin, claude_log, claude_state = _myspec_install_fake_claude(tmp_path / "fake-claude")
        codex_bin, codex_log, codex_state = _myspec_install_fake_codex(tmp_path / "fake-codex")
        env = _myspec_isolated_myspec_env(tmp_path, prefix, npm_bin, claude_bin, codex_bin)
        codex_home = Path(env["HOME"]) / ".codex"
        codex_home.mkdir()
        env.update(MYSPEC_NPM_LOG=str(npm_log), MYSPEC_REAL_NPM=str(shutil.which("npm")),
            MYSPEC_RELEASE_TARBALL=str(npm_candidate.tarball), MYSPEC_CLAUDE_LOG=str(claude_log),
            MYSPEC_CLAUDE_STATE=str(claude_state), MYSPEC_CLAUDE_HOME=str(Path(env["HOME"]) / ".claude"),
            MYSPEC_CODEX_LOG=str(codex_log), MYSPEC_CODEX_STATE=str(codex_state), CODEX_HOME=str(codex_home))
        _myspec_write(claude_state, '{"marketplaces": [], "plugins": []}')
        _myspec_write(codex_state, '{"marketplaces": [], "installed": [], "available": []}')
        initialized = _myspec_run_cli(executable, "init", "--all", env=env)
        assert initialized.returncode == 0, initialized.stderr
        source = _myspec_real_controlled_dev_source(tmp_path, "development source")
        env = _myspec_controlled_dev_env(env, source)
        entered = _myspec_run_cli(executable, "init", "--dev", "--source", source, env=env)
        assert entered.returncode == 0, entered.stderr
        assert {client: json.loads(entered.stdout)[client] for client in ("claude", "codex")} == {
            "claude": "refreshed", "codex": "refreshed"}
        diagnosed = _myspec_run_cli(executable, "doctor", env=env)
        assert diagnosed.returncode == 0, diagnosed.stderr
        toolchain = json.loads(diagnosed.stdout)["toolchain"]
        published_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source,
            text=True, capture_output=True, check=True).stdout.strip()
        assert toolchain["mode"] == "dev"
        assert toolchain["sourceCommit"] == published_head
        identity = toolchain["implementationIdentity"]
        assert identity.startswith("sha256:")
        digest = identity.removeprefix("sha256:")
        assert len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)
        claude_plugin = next(item for item in json.loads(claude_state.read_text())["plugins"] if item["id"] == "my-spec@myspec")
        claude_cache = Path(claude_plugin["installPath"])
        version = json.loads((package / "package.json").read_text())["version"]
        codex_cache = codex_home / "plugins/cache/myspec/my-spec" / version
        for cache in (claude_cache, codex_cache):
            assert (cache / "skills/my-spec/dev-marker.txt").read_text() == "development source\n"
        restored = _myspec_run_cli(executable, "init", "--release", env=env)
        assert restored.returncode == 0, restored.stderr
        assert {client: json.loads(restored.stdout)[client] for client in ("claude", "codex")} == {
            "claude": "refreshed", "codex": "refreshed"}
        assert json.loads((Path(env["HOME"]) / ".myspec/state.json").read_text())["mode"] == "release"
        for cache in (claude_cache, codex_cache):
            assert not (cache / "skills/my-spec/dev-marker.txt").exists()
        calls = [json.loads(line) for line in npm_log.read_text().splitlines()]
        assert ["link"] in calls
        assert ["install", "--global", "--ignore-scripts", "--no-audit", "--no-fund", f"@liuli195/myspec@{version}"] in calls
        assert subprocess.run(["git", "status", "--porcelain"], cwd=source,
            text=True, capture_output=True, check=True).stdout == ""
