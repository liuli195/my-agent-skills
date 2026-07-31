from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "my-spec"
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


def load_management_module():
    path = PLUGIN_ROOT / "python" / "management.py"
    spec = importlib.util.spec_from_file_location("myspec_management_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def bumped_patch(version: str, amount: int = 1) -> str:
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + amount}"


PREVIOUS_VERSION = bumped_patch(PACKAGE_VERSION, -1)
NEXT_VERSION = bumped_patch(PACKAGE_VERSION)
LATER_VERSION = bumped_patch(PACKAGE_VERSION, 2)


def run_python(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *(str(arg) for arg in args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def requirement(title: str, behavior: str, scenario: str = "正常流程") -> str:
    return f"""### Requirement: {title}

系统 MUST {behavior}。

#### Scenario: {scenario}

- **WHEN** 用户执行操作
- **THEN** 系统返回结果
"""


def main_spec(capability: str, *requirements: str) -> str:
    return f"""# {capability}

## Purpose

描述 {capability} 的外部行为。

## Requirements

{"\n".join(requirements)}"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def ready_state(cli: Path, root: Path, command: str = "add") -> Path:
    work = root / ".local" / "spec-work"
    conflicts = root / "no-conflicts.json"
    write(conflicts, "[]")
    initialized = run_python(
        cli, "state-init", work, command, "specs-fingerprint", "input-fingerprint"
    )
    assert initialized.returncode == 0, initialized.stderr
    stored = run_python(
        cli,
        "state-set-conflicts",
        work,
        conflicts,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert stored.returncode == 0, stored.stderr
    return work


def apply_ready(
    cli: Path,
    specs: Path,
    delta: Path,
    output: Path,
    work: Path,
) -> subprocess.CompletedProcess[str]:
    return run_python(
        cli,
        "apply-delta",
        specs,
        delta,
        output,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )


def run_confirmed_workflow(
    cli: Path,
    specs: Path,
    delta: Path,
    preview: Path,
    *expected_diff: str,
) -> str:
    work = ready_state(cli, preview.parent)
    validated = run_python(cli, "validate-delta", delta, specs)
    assert validated.returncode == 0, validated.stderr
    generated = run_python(
        cli,
        "apply-delta",
        specs,
        delta,
        preview,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert generated.returncode == 0, generated.stderr
    assert run_python(cli, "validate-main", preview).returncode == 0
    diff = run_python(cli, "diff", specs, preview)
    assert diff.returncode == 0, diff.stderr
    for fragment in expected_diff:
        assert fragment in diff.stdout
    applied = run_python(
        cli,
        "apply-delta",
        specs,
        delta,
        specs,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert applied.returncode == 0, applied.stderr
    assert run_python(cli, "validate-main", specs).returncode == 0
    assert run_python(cli, "diff", specs, preview).stdout == ""
    return diff.stdout


def install_packed_myspec(tmp_path: Path) -> tuple[Path, Path]:
    npm = shutil.which("npm")
    assert npm is not None
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    supplied_tarball = os.environ.get("MYSPEC_TEST_TARBALL")
    if supplied_tarball:
        source_tarball = Path(supplied_tarball).resolve()
        assert source_tarball.is_file()
        tarball = package_dir / source_tarball.name
        shutil.copy2(source_tarball, tarball)
    else:
        packed = subprocess.run(
            [npm, "pack", "--json", "--pack-destination", str(package_dir)],
            cwd=PLUGIN_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert packed.returncode == 0, packed.stderr
        package = json.loads(packed.stdout)[0]
        assert package["name"] == "@liuli195/myspec"
        tarball = package_dir / package["filename"]

    prefix = tmp_path / "npm-prefix"
    installed = subprocess.run(
        [
            npm,
            "install",
            "--global",
            "--prefix",
            str(prefix),
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
            str(tarball),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    executable = prefix / ("myspec.cmd" if sys.platform == "win32" else "bin/myspec")
    assert executable.is_file()
    npm_root = subprocess.run(
        [npm, "root", "--global", "--prefix", str(prefix)],
        text=True,
        capture_output=True,
        check=True,
    )
    return executable, Path(npm_root.stdout.strip()) / "@liuli195" / "myspec"


def npm_prefix_for(installed_package: Path) -> Path:
    node_modules = installed_package.parents[1]
    return node_modules.parent.parent if node_modules.parent.name == "lib" else node_modules.parent


def pack_myspec_version(tmp_path: Path, version: str, marker: Path | None = None) -> Path:
    source = tmp_path / f"myspec-{version}"
    shutil.copytree(PLUGIN_ROOT, source)
    for relative in ("package.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        path = source / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        value["version"] = version
        write(path, json.dumps(value, indent=2))
    if marker is not None:
        launcher = source / "bin" / "myspec.js"
        text = launcher.read_text(encoding="utf-8")
        text = text.replace(
            'const path = require("node:path");',
            'const path = require("node:path");\n'
            'require("node:fs").appendFileSync(process.env.MYSPEC_REEXEC_MARKER, `${process.pid}\\n`);',
        )
        write(launcher, text)
    package_dir = tmp_path / f"package-{version}"
    package_dir.mkdir()
    packed = subprocess.run(
        [shutil.which("npm") or "npm", "pack", "--json", "--pack-destination", str(package_dir)],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert packed.returncode == 0, packed.stderr
    return package_dir / json.loads(packed.stdout)[0]["filename"]


def run_cli(
    executable: Path,
    *args: object,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(executable), *(str(arg) for arg in args)],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def install_fake_pi(root: Path) -> tuple[Path, Path]:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    script = root / "fake_pi.py"
    log = root / "pi.log"
    write(
        script,
        """import json
import os
import sys
from pathlib import Path

agent_dir = Path(os.environ["PI_CODING_AGENT_DIR"])
user_settings = agent_dir / "settings.json"
project_settings = Path.cwd() / ".pi" / "settings.json"

def load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def canonical(path):
    return Path(os.path.realpath(os.path.abspath(path)))

def project_trusted():
    override = os.environ.get("MYSPEC_PI_PROJECT_TRUST_OVERRIDE")
    if override is not None:
        return override == "true"
    decisions = load(agent_dir / "trust.json")
    current = canonical(Path.cwd())
    while True:
        decision = decisions.get(str(current))
        if isinstance(decision, bool):
            return decision
        if current.parent == current:
            break
        current = current.parent
    return load(user_settings).get("defaultProjectTrust") == "always"

def source(item):
    return item if isinstance(item, str) else item.get("source")

def resolved(raw, settings_path):
    mapped = json.loads(os.environ.get("MYSPEC_PI_INSTALLED_PATHS", "{}"))
    if raw in mapped:
        return Path(mapped[raw])
    path = Path(raw).expanduser()
    return Path(os.path.abspath(path if path.is_absolute() else settings_path.parent / path))

with Path(os.environ["MYSPEC_PI_LOG"]).open("a", encoding="utf-8") as log:
    log.write(json.dumps({"args": sys.argv[1:], "cwd": str(Path.cwd())}) + "\\n")
if sys.argv[1:2] == ["install"]:
    settings = load(user_settings)
    packages = settings.setdefault("packages", [])
    raw = sys.argv[2]
    if not any(source(item) == raw for item in packages):
        packages.append(raw)
    user_settings.parent.mkdir(parents=True, exist_ok=True)
    user_settings.write_text(json.dumps(settings, indent=2) + "\\n", encoding="utf-8")
    raise SystemExit(0)
if sys.argv[1:2] == ["list"]:
    paths = [("User packages:", user_settings)]
    if project_trusted():
        paths.append(("Project packages:", project_settings))
    shown = False
    for label, path in paths:
        packages = load(path).get("packages", [])
        if not packages:
            continue
        if shown:
            print()
        print(label)
        shown = True
        for item in packages:
            raw = source(item)
            if not isinstance(raw, str):
                continue
            omitted = json.loads(os.environ.get("MYSPEC_PI_LIST_OMIT_SOURCES", "[]"))
            if raw in omitted:
                continue
            package = resolved(raw, path)
            print("  " + raw + (" (filtered)" if isinstance(item, dict) else ""))
            source_only = json.loads(os.environ.get("MYSPEC_PI_LIST_SOURCE_ONLY", "[]"))
            if raw not in source_only:
                print("    " + str(package))
    if not shown:
        print("No packages installed.")
    raise SystemExit(0)
raise SystemExit(2)
""",
    )
    if sys.platform == "win32":
        launcher = bin_dir / "pi.cmd"
        write(launcher, f'@"{sys.executable}" "{script}" %*')
    else:
        launcher = bin_dir / "pi"
        write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
        launcher.chmod(0o755)
    return bin_dir, log


def install_fake_claude(root: Path) -> tuple[Path, Path, Path]:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    script = root / "fake_claude.py"
    log = root / "claude.log"
    state = root / "claude-state.json"
    write(
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
        write(launcher, f'@"{sys.executable}" "{script}" %*')
    else:
        launcher = bin_dir / "claude"
        write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
        launcher.chmod(0o755)
    return bin_dir, log, state


def install_fake_codex(root: Path) -> tuple[Path, Path, Path]:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    script = root / "fake_codex.py"
    log = root / "codex.log"
    state = root / "codex-state.json"
    write(
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
    target = Path(os.environ["CODEX_HOME"]) / "plugins" / "cache" / current["marketplaceName"] / current["name"] / current["version"]
    if target.exists():
        shutil.rmtree(target)
    state["installed"].remove(current)
    remove_config(arguments[2])
    save()
    print(json.dumps({"pluginId": arguments[2]}))
else:
    raise SystemExit(2)
''',
    )
    if sys.platform == "win32":
        launcher = bin_dir / "codex.cmd"
        write(launcher, f'@"{sys.executable}" "{script}" %*')
    else:
        launcher = bin_dir / "codex"
        write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
        launcher.chmod(0o755)
    return bin_dir, log, state


def install_fake_npm(root: Path, release_tarball: Path) -> tuple[Path, Path]:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    script = root / "fake_npm.py"
    log = root / "npm.log"
    npm = shutil.which("npm")
    assert npm is not None
    write(
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
if arguments[:2] == ["install", "--global"]:
    if os.environ.get("MYSPEC_NPM_FAIL_INSTALL") == "1":
        print("simulated install failure", file=sys.stderr)
        raise SystemExit(1)
    arguments[-1] = os.environ["MYSPEC_RELEASE_TARBALL"]
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
        write(launcher, f'@"{sys.executable}" "{script}" %*')
    else:
        launcher = bin_dir / "npm"
        write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"')
        launcher.chmod(0o755)
    return bin_dir, log


def isolated_myspec_env(
    tmp_path: Path,
    prefix: Path,
    *extra_paths: Path,
) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    path_entries = [str(path) for path in extra_paths]
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
        "MYSPEC_PACKAGE_VERSION": PACKAGE_VERSION,
        "PATH": os.pathsep.join(path_entries),
    }


def source_case_report(
    client: str,
    case: dict[str, object],
    root: Path,
    executable: Path,
    installed_package: Path,
    prefix: Path,
) -> dict[str, object]:
    scenario = str(case["scenario"])
    enabled = scenario != "stable-disabled"
    installed = scenario != "stable-missing-directory"
    legacy = scenario == "legacy-enabled"
    mismatch = scenario == "stable-source-mismatch"
    source_root = root / ("legacy" if legacy else "wrong-source" if mismatch else "source")
    if legacy:
        source_root = source_root / "plugins" / "my-spec"
    if installed and scenario != "no-source":
        shutil.copytree(installed_package, source_root)

    if client == "pi":
        client_bin, log = install_fake_pi(root / "fake-pi")
        env = isolated_myspec_env(root, prefix, client_bin)
        env["MYSPEC_PI_LOG"] = str(log)
        stable_source = str(installed_package)
        raw_source = str(source_root) if legacy else stable_source
        item: object = {"source": raw_source, "skills": []} if not enabled else raw_source
        if scenario == "no-source":
            item = str(root / "unrelated")
        write(
            Path(env["PI_CODING_AGENT_DIR"]) / "settings.json",
            json.dumps({"packages": [item]}, indent=2),
        )
        if not installed and scenario != "no-source":
            env["MYSPEC_PI_LIST_SOURCE_ONLY"] = json.dumps([raw_source])
        if mismatch:
            env["MYSPEC_PI_INSTALLED_PATHS"] = json.dumps({raw_source: str(source_root)})
    elif client == "claude":
        client_bin, log, state_path = install_fake_claude(root / "fake-claude")
        env = isolated_myspec_env(root, prefix, client_bin)
        env.update(
            {
                "MYSPEC_CLAUDE_LOG": str(log),
                "MYSPEC_CLAUDE_STATE": str(state_path),
                "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
            }
        )
        identifier = "my-spec@my-agent-skills-marketplace" if legacy else "my-spec@myspec"
        marketplaces = []
        plugins = []
        if scenario == "no-source":
            plugins.append(
                {
                    "id": "other@other-marketplace",
                    "version": "1.0.0",
                    "scope": "user",
                    "enabled": True,
                    "installPath": str(root / "unrelated"),
                }
            )
        else:
            market_name = "my-agent-skills-marketplace" if legacy else "myspec"
            market_path = source_root if mismatch else installed_package
            if scenario != "stable-unregistered-plugin":
                marketplaces.append(
                    {
                        "name": market_name,
                        "source": "directory",
                        "path": str(market_path),
                        "installLocation": str(market_path),
                    }
                )
            plugins.append(
                {
                    "id": identifier,
                    "version": PACKAGE_VERSION,
                    "scope": "user",
                    "enabled": enabled,
                    "installPath": str(source_root),
                }
            )
        write(state_path, json.dumps({"marketplaces": marketplaces, "plugins": plugins}, indent=2))
    else:
        client_bin, log, state_path = install_fake_codex(root / "fake-codex")
        env = isolated_myspec_env(root, prefix, client_bin)
        codex_home = Path(env["HOME"]) / ".codex"
        env.update(
            {
                "CODEX_HOME": str(codex_home),
                "MYSPEC_CODEX_LOG": str(log),
                "MYSPEC_CODEX_STATE": str(state_path),
            }
        )
        identifier = "my-spec@my-agent-skills-marketplace" if legacy else "my-spec@myspec"
        marketplaces = []
        plugins = []
        if scenario == "no-source":
            plugins.append(
                {
                    "pluginId": "other@other-marketplace",
                    "name": "other",
                    "marketplaceName": "other-marketplace",
                    "version": "1.0.0",
                    "installed": True,
                    "source": {"source": "local", "path": str(root / "unrelated")},
                }
            )
            identifier = "other@other-marketplace"
        else:
            market_name = "my-agent-skills-marketplace" if legacy else "myspec"
            market_root = source_root if mismatch else installed_package
            if scenario != "stable-unregistered-plugin":
                marketplaces.append(
                    {
                        "name": market_name,
                        "root": str(market_root),
                        "marketplaceSource": {"sourceType": "local", "source": str(market_root)},
                    }
                )
            plugins.append(
                {
                    "pluginId": identifier,
                    "name": "my-spec",
                    "marketplaceName": market_name,
                    "version": PACKAGE_VERSION,
                    "installed": True,
                    "source": {"source": "local", "path": str(source_root)},
                }
            )
        write(state_path, json.dumps({"marketplaces": marketplaces, "installed": plugins, "available": []}, indent=2))
        write(codex_home / "config.toml", f'[plugins."{identifier}"]\nenabled = {str(enabled).lower()}\n')

    diagnosed = run_cli(executable, "doctor", f"--{client}", env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    return json.loads(diagnosed.stdout)[client]


@pytest.mark.parametrize("client", ("pi", "claude", "codex"))
def test_packed_myspec_clients_run_shared_source_cases(tmp_path: Path, client: str) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    seen = []

    for case in SOURCE_CASES:
        seen.append(case["id"])
        report = source_case_report(
            client,
            case,
            tmp_path / str(case["id"]),
            executable,
            installed_package,
            prefix,
        )
        actual = [
            {field: source[field] for field in SOURCE_FIELDS}
            for source in report["sources"]
        ]
        assert actual == case["expectedSources"], case["id"]
        if case["id"] == "legacy-enabled":
            assert report["enabled"] is True
        assert {"enabledSources", "disabledSources", "duplicateEnabledSources"} <= report.keys()

    assert seen == [case["id"] for case in SOURCE_CASES]

    if client in {"claude", "codex"}:
        report = source_case_report(
            client,
            {"scenario": "stable-unregistered-plugin"},
            tmp_path / "stable-unregistered-plugin",
            executable,
            installed_package,
            prefix,
        )
        assert [
            {field: source[field] for field in SOURCE_FIELDS}
            for source in report["sources"]
        ] == [
            {
                "installed": True,
                "registered": False,
                "enabled": True,
                "effective": False,
                "sourceKind": "stable",
                "sourceMismatch": False,
            }
        ]


def test_packed_myspec_update_preflights_installed_clients_before_package_write(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    old_tarball = next((installed / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", old_tarball)
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / "fake-codex")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, codex_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(old_tarball),
            "MYSPEC_NPM_LATEST": NEXT_VERSION,
            "CODEX_HOME": str(Path(env["HOME"]) / ".codex"),
            "MYSPEC_CODEX_LOG": str(codex_log),
            "MYSPEC_CODEX_STATE": str(codex_state),
        }
    )
    write(
        codex_state,
        json.dumps(
            {
                "marketplaces": "broken",
                "installed": [
                    {
                        "pluginId": "my-spec@myspec",
                        "version": PACKAGE_VERSION,
                        "installed": True,
                    }
                ],
                "available": [],
            }
        ),
    )
    package_before = (installed_package / "package.json").read_bytes()

    failed = run_cli(executable, "update", env=env)

    assert failed.returncode == 1
    assert "error: codex_marketplace_list_failed: invalid_output" in failed.stderr
    assert (installed_package / "package.json").read_bytes() == package_before
    assert not (Path(env["HOME"]) / ".myspec" / "state.json").exists()
    calls = [json.loads(line) for line in npm_log.read_text(encoding="utf-8").splitlines()]
    assert not any(call[:2] == ["install", "--global"] for call in calls)

    write(codex_state, json.dumps({"marketplaces": "broken", "installed": [], "available": []}))
    skipped = run_cli(executable, "update", env={**env, "MYSPEC_NPM_LATEST": PACKAGE_VERSION})
    assert skipped.returncode == 0, skipped.stderr
    assert "codex" not in json.loads(skipped.stdout)


def test_packed_myspec_update_refreshes_disabled_integrations_and_skips_only_missing(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    old_tarball = next((installed / "package").glob("*.tgz"))
    new_tarball = pack_myspec_version(tmp_path, NEXT_VERSION)
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", old_tarball)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / "fake-claude")
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / "fake-codex")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, pi_bin, claude_bin, codex_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(new_tarball),
            "MYSPEC_NPM_LATEST": NEXT_VERSION,
            "MYSPEC_PI_LOG": str(pi_log),
            "MYSPEC_CLAUDE_LOG": str(claude_log),
            "MYSPEC_CLAUDE_STATE": str(claude_state),
            "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
            "CODEX_HOME": str(Path(env["HOME"]) / ".codex"),
            "MYSPEC_CODEX_LOG": str(codex_log),
            "MYSPEC_CODEX_STATE": str(codex_state),
        }
    )
    write(
        Path(env["PI_CODING_AGENT_DIR"]) / "settings.json",
        json.dumps(
            {"packages": [{"source": str(installed_package), "skills": []}, str(PLUGIN_ROOT)]},
            indent=2,
        ),
    )
    write(
        claude_state,
        json.dumps(
            {
                "marketplaces": [
                    {
                        "name": "myspec",
                        "source": "directory",
                        "path": str(installed_package),
                        "installLocation": str(installed_package),
                    },
                    {
                        "name": "my-agent-skills-marketplace",
                        "source": "directory",
                        "path": str(PLUGIN_ROOT),
                        "installLocation": str(PLUGIN_ROOT),
                    },
                ],
                "plugins": [
                    {
                        "id": "my-spec@myspec",
                        "version": PACKAGE_VERSION,
                        "scope": "user",
                        "enabled": False,
                        "installPath": str(tmp_path / "disabled-claude"),
                    },
                    {
                        "id": "my-spec@my-agent-skills-marketplace",
                        "version": PACKAGE_VERSION,
                        "scope": "user",
                        "enabled": True,
                        "installPath": str(PLUGIN_ROOT),
                    },
                ],
            },
            indent=2,
        ),
    )
    write(
        codex_state,
        json.dumps(
            {
                "marketplaces": [
                    {
                        "name": "myspec",
                        "root": str(installed_package),
                        "marketplaceSource": {"sourceType": "local", "source": str(installed_package)},
                    },
                    {
                        "name": "my-agent-skills-marketplace",
                        "root": str(PLUGIN_ROOT),
                        "marketplaceSource": {"sourceType": "local", "source": str(PLUGIN_ROOT)},
                    },
                ],
                "installed": [
                    {
                        "pluginId": "my-spec@myspec",
                        "name": "my-spec",
                        "marketplaceName": "myspec",
                        "version": PACKAGE_VERSION,
                        "installed": True,
                        "source": {"source": "local", "path": str(installed_package)},
                    },
                    {
                        "pluginId": "my-spec@my-agent-skills-marketplace",
                        "name": "my-spec",
                        "marketplaceName": "my-agent-skills-marketplace",
                        "version": PACKAGE_VERSION,
                        "installed": True,
                        "source": {"source": "local", "path": str(PLUGIN_ROOT)},
                    },
                ],
                "available": [],
            },
            indent=2,
        ),
    )
    write(
        Path(env["CODEX_HOME"]) / "config.toml",
        '[plugins."my-spec@myspec"]\nenabled = false\n'
        '[plugins."my-spec@my-agent-skills-marketplace"]\nenabled = true\n',
    )
    pi_before = (Path(env["PI_CODING_AGENT_DIR"]) / "settings.json").read_bytes()

    interrupted = run_cli(
        executable,
        "update",
        env={**env, "MYSPEC_CLAUDE_FAIL_AFTER_ENABLED": "false"},
    )
    assert interrupted.returncode == 1
    assert "claude_plugin_disable_failed: simulated interruption after enabled state" in interrupted.stderr

    updated = run_cli(executable, "update", env=env)

    assert updated.returncode == 0, updated.stderr
    output = json.loads(updated.stdout)
    assert output["version"] == NEXT_VERSION
    assert output["pi"] == "refreshed"
    assert output["claude"] == "refreshed"
    assert output["codex"] == "refreshed"
    assert output["doctor"]["pi"]["enabled"] is True
    assert output["doctor"]["claude"]["enabled"] is True
    assert output["doctor"]["codex"]["enabled"] is True
    for client in ("pi", "claude", "codex"):
        stable_source = next(
            source
            for source in output["doctor"][client]["sources"]
            if source["sourceKind"] == "stable"
        )
        assert stable_source["enabled"] is False
    assert output["doctor"]["claude"]["version"] == NEXT_VERSION
    assert output["doctor"]["codex"]["version"] == NEXT_VERSION
    assert (Path(env["PI_CODING_AGENT_DIR"]) / "settings.json").read_bytes() == pi_before
    claude_calls = [json.loads(line) for line in claude_log.read_text(encoding="utf-8").splitlines()]
    assert ["plugin", "uninstall", "my-spec@myspec", "--scope", "user", "--keep-data"] in claude_calls
    assert ["plugin", "install", "my-spec@myspec", "--scope", "user"] in claude_calls
    assert claude_calls.count(["plugin", "disable", "my-spec@myspec", "--scope", "user"]) == 1
    codex_calls = [json.loads(line) for line in codex_log.read_text(encoding="utf-8").splitlines()]
    assert ["plugin", "remove", "my-spec@myspec", "--json"] in codex_calls
    assert ["plugin", "add", "my-spec@myspec", "--json"] in codex_calls


def test_packed_myspec_update_preserves_pi_effective_state_under_project_override(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    old_tarball = next((installed / "package").glob("*.tgz"))
    new_tarball = pack_myspec_version(tmp_path, NEXT_VERSION)
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", old_tarball)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, pi_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(new_tarball),
            "MYSPEC_NPM_LATEST": NEXT_VERSION,
            "MYSPEC_PI_LOG": str(pi_log),
            "MYSPEC_PI_PROJECT_TRUST_OVERRIDE": "true",
        }
    )
    project = tmp_path / "consumer"
    project.mkdir()
    user_settings = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    project_settings = project / ".pi" / "settings.json"
    write(user_settings, json.dumps({"packages": [str(installed_package)]}, indent=2))
    write(
        project_settings,
        json.dumps(
            {"packages": [{"source": str(installed_package), "skills": []}]},
            indent=2,
        ),
    )
    user_before = user_settings.read_bytes()
    project_before = project_settings.read_bytes()

    diagnosed = run_cli(executable, "doctor", "--pi", env=env, cwd=project)

    assert diagnosed.returncode == 0, diagnosed.stderr
    before = json.loads(diagnosed.stdout)["pi"]
    assert before["enabled"] is True
    assert before["skills"] == []
    assert [
        (source["scope"], source["enabled"], source["effective"])
        for source in before["sources"]
        if source["sourceKind"] == "stable"
    ] == [("user", True, False), ("project", False, False)]

    updated = run_cli(executable, "update", env=env, cwd=project)

    assert updated.returncode == 0, updated.stderr
    output = json.loads(updated.stdout)
    assert output["pi"] == "refreshed"
    after = output["doctor"]["pi"]
    assert after["enabled"] is True
    assert after["skills"] == []
    assert [
        (source["scope"], source["enabled"], source["effective"])
        for source in after["sources"]
        if source["sourceKind"] == "stable"
    ] == [("user", True, False), ("project", False, False)]
    assert user_settings.read_bytes() == user_before
    assert project_settings.read_bytes() == project_before


def test_packed_myspec_update_recovers_external_success_before_bookkeeping(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    old_tarball = next((installed / "package").glob("*.tgz"))
    marker = tmp_path / "new-cli.log"
    new_tarball = pack_myspec_version(tmp_path, NEXT_VERSION, marker)
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", old_tarball)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / "fake-claude")
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / "fake-codex")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, pi_bin, claude_bin, codex_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(old_tarball),
            "MYSPEC_NPM_LATEST": NEXT_VERSION,
            "MYSPEC_REEXEC_MARKER": str(marker),
            "MYSPEC_PI_LOG": str(pi_log),
            "MYSPEC_CLAUDE_LOG": str(claude_log),
            "MYSPEC_CLAUDE_STATE": str(claude_state),
            "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
            "CODEX_HOME": str(Path(env["HOME"]) / ".codex"),
            "MYSPEC_CODEX_LOG": str(codex_log),
            "MYSPEC_CODEX_STATE": str(codex_state),
        }
    )
    write(claude_state, json.dumps({"marketplaces": [], "plugins": []}, indent=2))
    write(codex_state, json.dumps({"marketplaces": [], "installed": [], "available": []}, indent=2))
    assert run_cli(executable, "init", "--all", env=env).returncode == 0
    for log in (npm_log, claude_log, codex_log):
        log.write_text("", encoding="utf-8")
    env["MYSPEC_RELEASE_TARBALL"] = str(new_tarball)

    failures = [
        ("MYSPEC_NPM_FAIL_AFTER_INSTALL", "npm_install_failed: simulated interruption after npm install"),
        ("MYSPEC_CLAUDE_FAIL_AFTER_UNINSTALL", "claude_plugin_uninstall_failed: simulated interruption after uninstall"),
        ("MYSPEC_CLAUDE_FAIL_AFTER_INSTALL", "claude_plugin_install_failed: simulated interruption after install"),
        ("MYSPEC_CODEX_FAIL_AFTER_ADD", "codex_plugin_add_failed: simulated interruption after add"),
    ]
    for failure_variable, expected_error in failures:
        failed = run_cli(executable, "update", env={**env, failure_variable: "1"})
        assert failed.returncode == 1
        assert f"error: {expected_error}" in failed.stderr

    retried = run_cli(executable, "update", env=env)

    assert retried.returncode == 0, retried.stderr
    output = json.loads(retried.stdout)
    assert output["version"] == NEXT_VERSION
    assert output["doctor"]["cliVersion"] == NEXT_VERSION
    assert output["doctor"]["pi"]["version"] == NEXT_VERSION
    assert output["doctor"]["claude"]["version"] == NEXT_VERSION
    assert output["doctor"]["codex"]["version"] == NEXT_VERSION
    assert marker.read_text(encoding="utf-8").strip()
    npm_calls = [json.loads(line) for line in npm_log.read_text(encoding="utf-8").splitlines()]
    claude_calls = [json.loads(line) for line in claude_log.read_text(encoding="utf-8").splitlines()]
    codex_calls = [json.loads(line) for line in codex_log.read_text(encoding="utf-8").splitlines()]
    assert npm_calls.count(
        ["install", "--global", "--ignore-scripts", "--no-audit", "--no-fund", f"@liuli195/myspec@{NEXT_VERSION}"]
    ) == 1
    assert claude_calls.count(
        ["plugin", "uninstall", "my-spec@myspec", "--scope", "user", "--keep-data"]
    ) == 1
    assert claude_calls.count(["plugin", "install", "my-spec@myspec", "--scope", "user"]) == 1
    assert codex_calls.count(["plugin", "add", "my-spec@myspec", "--json"]) == 1
    state_path = Path(env["HOME"]) / ".myspec" / "state.json"
    assert "pendingOperation" not in json.loads(state_path.read_text(encoding="utf-8"))

    wrong_version_tarball = pack_myspec_version(tmp_path, LATER_VERSION)
    mismatch = run_cli(
        executable,
        "update",
        env={
            **env,
            "MYSPEC_RELEASE_TARBALL": str(wrong_version_tarball),
            "MYSPEC_NPM_LATEST": LATER_VERSION,
            "MYSPEC_CLAUDE_REPORTED_VERSION": "0.0.0",
        },
    )
    expected_error = "claude_plugin_refresh_version_mismatch"
    assert mismatch.returncode == 1
    assert f"error: {expected_error}" in mismatch.stderr
    pending = json.loads(state_path.read_text(encoding="utf-8"))["pendingOperation"]
    assert pending["targetVersion"] == LATER_VERSION
    assert pending["lastError"] == expected_error
    assert "doctor" not in pending["completed"]


def test_packed_myspec_preserves_lock_when_process_status_is_unknown(tmp_path: Path) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((tmp_path / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    process_probe = tmp_path / "unknown-process-probe"
    write(
        process_probe / "sitecustomize.py",
        """import ctypes
import os

if os.name == "nt":
    real_kernel32 = ctypes.windll.kernel32

    class UnknownKernel32:
        def OpenProcess(self, *_args):
            return 0

        def GetLastError(self):
            return 5

        def __getattr__(self, name):
            return getattr(real_kernel32, name)

    ctypes.windll.kernel32 = UnknownKernel32()
else:
    def unknown_process_status(_pid, _signal):
        raise PermissionError("simulated process query permission error")

    os.kill = unknown_process_status
""",
    )
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, pi_bin)
    env.update(
        {
            "PYTHONPATH": str(process_probe),
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            "MYSPEC_PI_LOG": str(pi_log),
        }
    )
    lock_path = Path(env["HOME"]) / ".myspec" / "install.lock"
    lock = {
        "pid": 424242,
        "startedAt": "2000-01-01T00:00:00+00:00",
        "command": "myspec update",
        "operationId": "unknown-process",
    }

    for command in (("init", "--pi"), ("update",)):
        write(lock_path, json.dumps(lock, indent=2))
        before = lock_path.read_bytes()
        npm_log.write_text("", encoding="utf-8")
        pi_log.write_text("", encoding="utf-8")

        rejected = run_cli(executable, *command, env=env)

        assert rejected.returncode == 1
        assert "error: install_lock_process_unknown: pid=424242" in rejected.stderr
        assert lock_path.read_bytes() == before
        assert npm_log.read_text(encoding="utf-8") == ""
        assert pi_log.read_text(encoding="utf-8") == ""


def test_packed_myspec_serializes_init_and_reports_locks_without_mutating_them(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    env = isolated_myspec_env(tmp_path, npm_prefix_for(installed_package))
    lock_path = Path(env["HOME"]) / ".myspec" / "install.lock"
    for malformed in ({"command": "myspec update"}, {"pid": True}, {"pid": "123"}, {"pid": 0}):
        write(lock_path, json.dumps(malformed))
        malformed_before = lock_path.read_bytes()
        rejected = run_cli(executable, "init", "--all", env=env)
        assert rejected.returncode == 1
        assert f"error: invalid_install_lock: {lock_path}" in rejected.stderr
        assert lock_path.read_bytes() == malformed_before

    active = {
        "pid": os.getpid(),
        "startedAt": "2000-01-01T00:00:00+00:00",
        "command": "myspec update",
        "operationId": "active",
    }
    write(lock_path, json.dumps(active, indent=2))
    before = lock_path.read_bytes()

    diagnosed = run_cli(executable, "doctor", env=env)
    blocked = run_cli(executable, "init", "--all", env=env)

    assert diagnosed.returncode == 0, diagnosed.stderr
    assert json.loads(diagnosed.stdout)["installation"]["lock"] == {
        "pid": os.getpid(),
        "startedAt": active["startedAt"],
        "command": "myspec update",
        "active": True,
    }
    assert blocked.returncode == 1
    assert f"error: install_locked: pid={os.getpid()}" in blocked.stderr
    assert lock_path.read_bytes() == before

    stale = {**active, "pid": 99999999, "operationId": "stale"}
    write(lock_path, json.dumps(stale, indent=2))
    recovered = run_cli(executable, "init", "--all", env=env)
    assert recovered.returncode == 0, recovered.stderr
    assert json.loads(lock_path.read_text(encoding="utf-8"))["released"] is True


def test_packed_myspec_doctor_reports_partial_update_read_only(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    executable, _ = install_packed_myspec(first)
    _, installed_package = install_packed_myspec(second)
    env = isolated_myspec_env(tmp_path, npm_prefix_for(installed_package))
    package_path = installed_package / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = NEXT_VERSION
    write(package_path, json.dumps(package, indent=2))
    state_path = Path(env["HOME"]) / ".myspec" / "state.json"
    write(
        state_path,
        json.dumps(
            {
                "mode": "release",
                "pendingOperation": {
                    "command": "update",
                    "targetVersion": NEXT_VERSION,
                    "integrations": ["pi", "claude"],
                    "completed": ["preflight", "npm", "pi"],
                    "lastError": "claude_plugin_install_failed: original failure",
                    "tokenHash": "secret",
                },
            },
            indent=2,
        ),
    )
    before = state_path.read_bytes()

    diagnosed = run_cli(executable, "doctor", "--all", env=env)

    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report["npm"]["versionMismatch"] is True
    assert report["installation"]["pendingOperation"] == {
        "command": "update",
        "targetVersion": NEXT_VERSION,
        "integrations": ["pi", "claude"],
        "completed": ["preflight", "npm", "pi"],
        "lastError": "claude_plugin_install_failed: original failure",
    }
    assert report["installation"]["lock"] is None
    assert state_path.read_bytes() == before

    token = "resume-secret"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    write(
        state_path,
        json.dumps(
            {
                "mode": "release",
                "pendingOperation": {
                    "command": "update",
                    "targetVersion": NEXT_VERSION,
                    "integrations": [],
                    "scopes": {},
                    "enabled": {},
                    "completed": ["preflight", "npm"],
                    "tokenHash": token_hash,
                },
            },
            indent=2,
        ),
    )
    write(
        Path(env["HOME"]) / ".myspec" / "install.lock",
        json.dumps(
            {
                "pid": os.getpid(),
                "startedAt": "2000-01-01T00:00:00+00:00",
                "command": "myspec update",
                "operationId": "resume-operation",
                "handoffTokenHash": token_hash,
            },
            indent=2,
        ),
    )
    forged = run_cli(executable, "update", "--_update-token", token, env=env)
    assert forged.returncode == 1
    assert "error: update_runtime_mismatch:" in forged.stderr
    assert json.loads(state_path.read_text(encoding="utf-8"))["pendingOperation"]["completed"] == [
        "preflight",
        "npm",
    ]


def test_packed_myspec_update_rejects_dev_mode_and_forged_resume(tmp_path: Path) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((tmp_path / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    env = isolated_myspec_env(tmp_path, prefix, npm_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
        }
    )
    entered = run_cli(executable, "init", "--dev", "--source", REPO_ROOT, env=env)
    assert entered.returncode == 0, entered.stderr

    rejected = run_cli(executable, "update", env=env)
    forged = run_cli(executable, "update", "--_update-token", "forged", env=env)

    assert rejected.returncode == 1
    assert "update_requires_release_mode: run 'myspec init --release' first" in rejected.stderr
    assert forged.returncode == 1
    assert "error: invalid_update_token" in forged.stderr
    lock = json.loads((Path(env["HOME"]) / ".myspec" / "install.lock").read_text(encoding="utf-8"))
    assert lock["released"] is True


def test_packed_myspec_initializes_and_diagnoses_one_pi_source(tmp_path: Path) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    settings_path = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    legacy = str(REPO_ROOT / "plugins" / "my-spec")
    write(
        settings_path,
        json.dumps(
            {
                "packages": [
                    legacy,
                    {"source": str(installed_package), "skills": [], "autoload": False},
                ]
            },
            indent=2,
        ),
    )

    initialized = run_cli(executable, "init", "--pi", env=env)
    assert initialized.returncode == 0, initialized.stderr
    result = json.loads(initialized.stdout)
    assert result == {
        "pi": "initialized",
        "source": str(installed_package),
        "disabledLegacySources": [legacy],
        "reloadRequired": True,
    }
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["packages"] == [
        {"source": legacy, "skills": []},
        {"source": str(installed_package)},
    ]

    settings_before = settings_path.read_bytes()
    diagnosed = run_cli(executable, "doctor", "--pi", env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report["cliVersion"] == PACKAGE_VERSION
    assert report["mode"] == "release"
    assert report["source"] == str(installed_package)
    assert report["npm"] == {
        "stablePath": str(installed_package),
        "realPath": str(installed_package),
        "linked": False,
        "packageVersion": PACKAGE_VERSION,
        "versionMismatch": False,
    }
    assert report["pi"]["registered"] is True
    assert report["pi"]["enabledSources"] == [str(installed_package)]
    assert report["pi"]["disabledSources"] == [legacy]
    assert report["pi"]["duplicateEnabledSources"] is False
    assert report["pi"]["skills"] == list(SKILL_NAMES)
    assert report["pi"]["listedSources"]
    assert settings_path.read_bytes() == settings_before
    assert [json.loads(line)["args"] for line in pi_log.read_text(encoding="utf-8").splitlines()] == [
        ["list"],
        ["list"],
        ["list"],
    ]

    shutil.rmtree(installed_package / "skills" / "my-spec-audit")
    broken = run_cli(executable, "doctor", "--pi", env=env)
    assert broken.returncode == 0, broken.stderr
    assert json.loads(broken.stdout)["pi"]["skills"] == list(SKILL_NAMES[:-1])

    shutil.rmtree(installed_package / "skills")
    incomplete = run_cli(executable, "doctor", "--pi", env=env)
    assert incomplete.returncode == 0, incomplete.stderr
    incomplete_report = json.loads(incomplete.stdout)["pi"]
    assert incomplete_report["skills"] == []
    stable_source = next(
        source for source in incomplete_report["sources"] if source["sourceKind"] == "stable"
    )
    assert stable_source["enabled"] is True


def test_packed_myspec_doctor_keeps_enabled_intent_for_settings_source_missing_from_pi_list(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    env["MYSPEC_PI_LIST_OMIT_SOURCES"] = json.dumps([str(installed_package)])
    settings_path = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    write(settings_path, json.dumps({"packages": [str(installed_package)]}, indent=2))

    diagnosed = run_cli(executable, "doctor", "--pi", env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)["pi"]
    assert report["registered"] is False
    assert report["enabledSources"] == [str(installed_package)]
    assert report["skills"] == []
    assert report["reloadRequired"] is True
    assert report["listedSources"] == []
    assert len(report["sources"]) == 1
    assert report["sources"][0]["source"] == str(installed_package)
    assert report["sources"][0]["installed"] is False
    assert report["sources"][0]["effective"] is False
    assert report["sources"][0]["enabled"] is True
    assert report["enabled"] is True


def test_packed_myspec_doctor_keeps_enabled_intent_for_missing_pi_source_with_exclusion(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, npm_prefix_for(installed_package), pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    env["MYSPEC_PI_LIST_SOURCE_ONLY"] = json.dumps([str(installed_package)])
    write(
        Path(env["PI_CODING_AGENT_DIR"]) / "settings.json",
        json.dumps(
            {"packages": [{"source": str(installed_package), "skills": ["!my-spec-audit"]}]},
            indent=2,
        ),
    )

    diagnosed = run_cli(executable, "doctor", "--pi", env=env)

    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)["pi"]
    assert report["enabled"] is True
    assert {field: report["sources"][0][field] for field in SOURCE_FIELDS} == {
        "installed": False,
        "registered": True,
        "enabled": True,
        "effective": False,
        "sourceKind": "stable",
        "sourceMismatch": False,
    }
    assert report["enabledSources"] == [str(installed_package)]


def test_packed_myspec_doctor_does_not_enable_pi_source_for_unrelated_autoload_delta(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, npm_prefix_for(installed_package), pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    write(
        Path(env["PI_CODING_AGENT_DIR"]) / "settings.json",
        json.dumps(
            {
                "packages": [
                    {
                        "source": str(installed_package),
                        "autoload": False,
                        "skills": ["+unrelated"],
                    }
                ]
            },
            indent=2,
        ),
    )

    diagnosed = run_cli(executable, "doctor", "--pi", env=env)

    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)["pi"]
    assert report["enabled"] is False
    assert report["enabledSources"] == []
    assert report["disabledSources"] == [str(installed_package)]
    assert report["sources"][0]["enabled"] is False
    assert report["reloadRequired"] is False


@pytest.mark.parametrize(
    ("trust", "default_trust", "expected_skills"),
    [
        ({}, "ask", SKILL_NAMES),
        ({"project": True}, "ask", ()),
        ({"parent": True}, "ask", ()),
        ({"parent": True, "project": False}, "always", SKILL_NAMES),
        ({}, "always", ()),
    ],
    ids=("untrusted", "trusted-project", "trusted-parent", "explicit-false", "default-always"),
)
def test_packed_myspec_follows_project_scope_reported_by_pi_list(
    tmp_path: Path,
    trust: dict[str, bool],
    default_trust: str,
    expected_skills: tuple[str, ...],
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    agent_dir = Path(env["PI_CODING_AGENT_DIR"])
    project_parent = tmp_path / "consumer"
    project = project_parent / "nested"
    project.mkdir(parents=True)
    user_settings = agent_dir / "settings.json"
    project_settings = project / ".pi" / "settings.json"
    trust_path = agent_dir / "trust.json"
    write(
        user_settings,
        json.dumps(
            {"defaultProjectTrust": default_trust, "packages": [str(installed_package)]},
            indent=2,
        ),
    )
    write(
        project_settings,
        json.dumps(
            {"packages": [{"source": str(installed_package), "skills": []}]},
            indent=2,
        ),
    )
    decisions = {
        str(Path(os.path.realpath(path))): decision
        for name, decision in trust.items()
        for path in (project if name == "project" else project_parent,)
    }
    write(trust_path, json.dumps(decisions, indent=2))

    project_before = project_settings.read_bytes()
    initialized = run_cli(executable, "init", "--pi", env=env, cwd=project)
    assert initialized.returncode == 0, initialized.stderr
    assert project_settings.read_bytes() == project_before
    user_before = user_settings.read_bytes()
    trust_before = trust_path.read_bytes()

    diagnosed = run_cli(executable, "doctor", "--pi", env=env, cwd=project)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report["pi"]["skills"] == list(expected_skills)
    assert report["pi"]["registered"] is True
    assert report["pi"]["listedSources"] == (
        [
            {"scope": "user", "source": str(installed_package), "path": str(installed_package)},
            {"scope": "project", "source": str(installed_package), "path": str(installed_package)},
        ]
        if not expected_skills
        else [{"scope": "user", "source": str(installed_package), "path": str(installed_package)}]
    )
    assert user_settings.read_bytes() == user_before
    assert project_settings.read_bytes() == project_before
    assert trust_path.read_bytes() == trust_before


def test_packed_myspec_uses_pi_list_project_scope_over_saved_trust(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    env["MYSPEC_PI_PROJECT_TRUST_OVERRIDE"] = "true"
    project = tmp_path / "consumer"
    project.mkdir()
    user_settings = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    project_settings = project / ".pi" / "settings.json"
    write(user_settings, json.dumps({"packages": [str(installed_package)]}, indent=2))
    write(
        Path(env["PI_CODING_AGENT_DIR"]) / "trust.json",
        json.dumps({str(Path(os.path.realpath(project))): False}, indent=2),
    )
    write(
        project_settings,
        json.dumps(
            {"packages": [{"source": str(installed_package), "skills": []}]},
            indent=2,
        ),
    )

    report = json.loads(run_cli(executable, "doctor", "--pi", env=env, cwd=project).stdout)["pi"]
    assert report["registered"] is True
    assert report["skills"] == []
    assert report["listedSources"] == [
        {"scope": "user", "source": str(installed_package), "path": str(installed_package)},
        {"scope": "project", "source": str(installed_package), "path": str(installed_package)},
    ]


def test_packed_myspec_ignores_project_settings_absent_from_pi_list(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    env["MYSPEC_PI_PROJECT_TRUST_OVERRIDE"] = "false"
    project = tmp_path / "consumer"
    project.mkdir()
    user_settings = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    write(user_settings, json.dumps({"packages": [str(installed_package)]}, indent=2))
    write(
        Path(env["PI_CODING_AGENT_DIR"]) / "trust.json",
        json.dumps({str(Path(os.path.realpath(project))): True}, indent=2),
    )
    write(
        project / ".pi" / "settings.json",
        json.dumps(
            {"packages": [{"source": str(installed_package), "skills": []}]},
            indent=2,
        ),
    )

    report = json.loads(run_cli(executable, "doctor", "--pi", env=env, cwd=project).stdout)["pi"]
    assert report["registered"] is True
    assert report["skills"] == list(SKILL_NAMES)
    assert report["listedSources"] == [
        {"scope": "user", "source": str(installed_package), "path": str(installed_package)}
    ]


def test_packed_myspec_resolves_user_and_project_pi_sources_from_each_settings_file(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    project = tmp_path / "consumer"
    user_settings = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    project_settings = project / ".pi" / "settings.json"
    legacy_package = project / "vendor" / "plugins" / "my-spec"
    shutil.copytree(PLUGIN_ROOT, legacy_package)
    stable_relative = os.path.relpath(installed_package, user_settings.parent)
    legacy_relative = os.path.relpath(legacy_package, project_settings.parent)
    stable_project_relative = os.path.relpath(installed_package, project_settings.parent)
    write(user_settings, json.dumps({"packages": [stable_relative]}, indent=2))
    write(
        Path(env["PI_CODING_AGENT_DIR"]) / "trust.json",
        json.dumps({str(Path(os.path.realpath(project))): True}, indent=2),
    )
    write(
        project_settings,
        json.dumps(
            {
                "packages": [
                    {"source": stable_project_relative, "skills": []},
                    legacy_relative,
                ]
            },
            indent=2,
        ),
    )

    initialized = run_cli(executable, "init", "--pi", env=env, cwd=project)
    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(user_settings.read_text(encoding="utf-8"))["packages"] == [stable_relative]
    assert json.loads(project_settings.read_text(encoding="utf-8"))["packages"] == [
        {"source": stable_project_relative, "skills": []},
        {"source": legacy_relative, "skills": []},
    ]
    calls = (
        [json.loads(line)["args"] for line in pi_log.read_text(encoding="utf-8").splitlines()]
        if pi_log.exists()
        else []
    )
    assert not any(call[:1] == ["install"] for call in calls)

    report = json.loads(run_cli(executable, "doctor", "--pi", env=env, cwd=project).stdout)
    assert report["pi"]["registered"] is True
    assert report["pi"]["duplicateEnabledSources"] is False
    assert report["pi"]["skills"] == []

    outside = json.loads(run_cli(executable, "doctor", "--pi", env=env, cwd=tmp_path).stdout)
    assert outside["pi"]["registered"] is True
    assert outside["pi"]["duplicateEnabledSources"] is False
    assert outside["pi"]["skills"] == list(SKILL_NAMES)


def test_packed_myspec_pi_git_identity_matches_pi_host_path_semantics(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    project = tmp_path / "consumer"
    project.mkdir()
    user_settings = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    project_settings = project / ".pi" / "settings.json"
    user_https = "https://github.com/example/pi-my-spec.git@main"
    different_host = "https://gitlab.com/example/pi-my-spec.git@main"
    different_path = "https://github.com/other/pi-my-spec.git@main"
    project_ssh = "git:git@github.com:example/pi-my-spec.git@feature"
    env["MYSPEC_PI_INSTALLED_PATHS"] = json.dumps(
        {
            source: str(installed_package)
            for source in (user_https, different_host, different_path, project_ssh)
        }
    )
    write(
        user_settings,
        json.dumps(
            {"packages": [user_https, different_host, different_path]}, indent=2
        ),
    )
    write(
        Path(env["PI_CODING_AGENT_DIR"]) / "trust.json",
        json.dumps({str(Path(os.path.realpath(project))): True}, indent=2),
    )
    write(project_settings, json.dumps({"packages": [project_ssh]}, indent=2))

    diagnosed = run_cli(executable, "doctor", "--pi", env=env, cwd=project)
    assert diagnosed.returncode == 0, diagnosed.stderr
    sources = {
        source["source"]: source
        for source in json.loads(diagnosed.stdout)["pi"]["sources"]
    }
    assert sources[user_https]["installed"] is True
    assert sources[user_https]["effective"] is False
    assert sources[project_ssh]["installed"] is True
    assert sources[project_ssh]["effective"] is True
    assert sources[different_host]["installed"] is True
    assert sources[different_host]["effective"] is True
    assert sources[different_path]["installed"] is True
    assert sources[different_path]["effective"] is True


def test_packed_myspec_doctor_applies_effective_pi_skill_filters_and_manifest(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    user_settings = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    project = tmp_path / "consumer"
    project.mkdir()
    project_settings = project / ".pi" / "settings.json"
    write(user_settings, json.dumps({"packages": [str(installed_package)]}, indent=2))
    write(
        Path(env["PI_CODING_AGENT_DIR"]) / "trust.json",
        json.dumps({str(Path(os.path.realpath(project))): True}, indent=2),
    )

    manifest_path = installed_package / "package.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pi"]["skills"].append("./skills/my-spec-extra")
    write(manifest_path, json.dumps(manifest, indent=2))
    write(installed_package / "skills" / "my-spec-extra" / "SKILL.md", "# extra")

    extra = json.loads(run_cli(executable, "doctor", "--pi", env=env, cwd=project).stdout)
    assert extra["pi"]["registered"] is True
    assert extra["pi"]["skills"] == [*SKILL_NAMES, "my-spec-extra"]

    write(
        project_settings,
        json.dumps(
            {
                "packages": [
                    {
                        "source": str(installed_package),
                        "autoload": False,
                        "skills": [
                            "!my-spec-audit",
                            "+skills/my-spec-audit",
                            "-skills/my-spec-review",
                            "!my-spec-extra",
                        ],
                    }
                ]
            },
            indent=2,
        ),
    )
    filtered = json.loads(run_cli(executable, "doctor", "--pi", env=env, cwd=project).stdout)
    assert filtered["pi"]["duplicateEnabledSources"] is False
    assert filtered["pi"]["skills"] == ["my-spec", "my-spec-add", "my-spec-audit"]


def test_packed_myspec_disables_only_exact_legacy_pi_sources(tmp_path: Path) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    settings_path = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    sources = [
        str(installed_package),
        "npm:@liuli195/myspec-helper@latest",
        f"npm:@liuli195/myspec@{PREVIOUS_VERSION}",
        "npm:pi-my-spec@next",
        f"git:github.com/example/pi-my-spec@v{PREVIOUS_VERSION}",
        "https://github.com/example/pi-my-spec.git#abc123",
        str(tmp_path / "plugins" / "myspec-helper"),
    ]
    write(settings_path, json.dumps({"packages": sources}, indent=2))

    result = run_cli(executable, "init", "--pi", env=env)
    assert result.returncode == 0, result.stderr
    packages = json.loads(settings_path.read_text(encoding="utf-8"))["packages"]
    assert packages[:2] == sources[:2]
    assert packages[-1] == sources[-1]
    assert packages[2:-1] == [
        {"source": source, "skills": []} for source in sources[2:-1]
    ]


def test_packed_myspec_doctor_reports_duplicate_enabled_pi_sources(tmp_path: Path) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    settings_path = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    write(
        settings_path,
        json.dumps({"packages": [str(installed_package), str(PLUGIN_ROOT)]}, indent=2),
    )

    report = json.loads(run_cli(executable, "doctor", "--pi", env=env).stdout)
    assert report["pi"]["duplicateEnabledSources"] is True
    assert report["pi"]["enabledSources"] == [str(installed_package), str(PLUGIN_ROOT)]
    assert [source["kind"] for source in report["pi"]["sources"]] == ["stable", "legacy"]


def test_packed_myspec_doctor_reads_legacy_git_and_npm_manifests_from_pi_list(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    npm_source = f"npm:pi-my-spec@{PREVIOUS_VERSION}"
    git_source = f"git:github.com/example/pi-my-spec@v{PREVIOUS_VERSION}"
    npm_package = tmp_path / "pi-installs" / "npm" / "pi-my-spec"
    git_package = tmp_path / "pi-installs" / "git" / "example" / "pi-my-spec"
    shutil.copytree(PLUGIN_ROOT, npm_package)
    shutil.copytree(PLUGIN_ROOT, git_package)
    env["MYSPEC_PI_INSTALLED_PATHS"] = json.dumps(
        {npm_source: str(npm_package), git_source: str(git_package)}
    )
    settings_path = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    write(
        settings_path,
        json.dumps(
            {"packages": [str(installed_package), npm_source, git_source]},
            indent=2,
        ),
    )

    report = json.loads(run_cli(executable, "doctor", "--pi", env=env).stdout)["pi"]
    assert report["duplicateEnabledSources"] is True
    assert report["enabledSources"] == [str(installed_package), npm_source, git_source]
    legacy = [source for source in report["sources"] if source["kind"] == "legacy"]
    assert [source["resolvedPath"] for source in legacy] == [str(npm_package), str(git_package)]
    assert all(source["enabled"] for source in legacy)


def test_packed_myspec_keeps_project_legacy_sources_without_installed_paths(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    project = tmp_path / "consumer"
    project.mkdir()
    npm_source = f"npm:pi-my-spec@{PREVIOUS_VERSION}"
    git_source = f"git:github.com/example/pi-my-spec@v{PREVIOUS_VERSION}"
    env["MYSPEC_PI_LIST_SOURCE_ONLY"] = json.dumps([npm_source, git_source])
    user_settings = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    project_settings = project / ".pi" / "settings.json"
    write(user_settings, json.dumps({"packages": [str(installed_package)]}, indent=2))
    write(
        Path(env["PI_CODING_AGENT_DIR"]) / "trust.json",
        json.dumps({str(Path(os.path.realpath(project))): True}, indent=2),
    )
    write(
        project_settings,
        json.dumps({"packages": [npm_source, git_source]}, indent=2),
    )

    initialized = run_cli(executable, "init", "--pi", env=env, cwd=project)
    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(project_settings.read_text(encoding="utf-8"))["packages"] == [
        {"source": npm_source, "skills": []},
        {"source": git_source, "skills": []},
    ]
    calls = [json.loads(line)["args"] for line in pi_log.read_text(encoding="utf-8").splitlines()]
    assert not any(call[:1] == ["install"] for call in calls)

    report = json.loads(run_cli(executable, "doctor", "--pi", env=env, cwd=project).stdout)["pi"]
    assert report["listedSources"] == [
        {"scope": "user", "source": str(installed_package), "path": str(installed_package)},
        {"scope": "project", "source": npm_source},
        {"scope": "project", "source": git_source},
    ]
    assert report["enabledSources"] == [str(installed_package)]
    assert report["duplicateEnabledSources"] is False
    sources = {source["source"]: source for source in report["sources"]}
    for source in (npm_source, git_source):
        assert sources[source]["scope"] == "project"
        assert sources[source]["resolvedPath"] is None
        assert sources[source]["installed"] is False
        assert sources[source]["effective"] is False
        assert sources[source]["enabled"] is False


def test_packed_myspec_initializes_and_diagnoses_claude_without_deleting_legacy(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / "fake-claude")
    env = isolated_myspec_env(tmp_path, prefix, claude_bin)
    env.update(
        {
            "MYSPEC_CLAUDE_LOG": str(claude_log),
            "MYSPEC_CLAUDE_STATE": str(claude_state),
            "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
        }
    )
    legacy_market = {
        "name": "my-agent-skills-marketplace",
        "source": "github",
        "repo": "liuli195/my-agent-skills",
        "installLocation": str(tmp_path / "legacy-market"),
    }
    unrelated_market = {
        "name": "other-marketplace",
        "source": "github",
        "repo": "example/other",
        "installLocation": str(tmp_path / "other-market"),
    }
    legacy_plugin = {
        "id": "my-spec@my-agent-skills-marketplace",
        "version": PREVIOUS_VERSION,
        "scope": "user",
        "enabled": True,
        "installPath": str(tmp_path / "legacy-plugin"),
    }
    unrelated_plugin = {
        "id": "other@other-marketplace",
        "version": "1.0.0",
        "scope": "user",
        "enabled": True,
        "installPath": str(tmp_path / "other-plugin"),
    }
    write(
        claude_state,
        json.dumps(
            {
                "marketplaces": [legacy_market, unrelated_market],
                "plugins": [legacy_plugin, unrelated_plugin],
            },
            indent=2,
        ),
    )

    initialized = run_cli(executable, "init", "--claude", env=env)
    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(initialized.stdout) == {
        "claude": "initialized",
        "marketplace": "myspec",
        "source": str(installed_package),
        "disabledLegacyPlugins": ["my-spec@my-agent-skills-marketplace"],
        "reloadRequired": True,
    }
    state = json.loads(claude_state.read_text(encoding="utf-8"))
    assert state["marketplaces"][:2] == [legacy_market, unrelated_market]
    assert len(state["marketplaces"]) == 3
    assert state["marketplaces"][2]["name"] == "myspec"
    plugins = {plugin["id"]: plugin for plugin in state["plugins"]}
    assert plugins[legacy_plugin["id"]]["enabled"] is False
    assert plugins[unrelated_plugin["id"]] == unrelated_plugin
    assert plugins["my-spec@myspec"]["enabled"] is True
    assert plugins["my-spec@myspec"]["version"] == PACKAGE_VERSION

    state_before = claude_state.read_bytes()
    claude_log.write_text("", encoding="utf-8")
    diagnosed = run_cli(executable, "doctor", "--claude", env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)["claude"]
    assert report["available"] is True
    assert report["marketplaceRegistered"] is True
    assert report["marketplaceSourceMismatch"] is False
    assert report["source"] == str(installed_package)
    assert report["version"] == PACKAGE_VERSION
    assert report["enabled"] is True
    assert report["duplicateEnabledSources"] is False
    assert report["enabledSources"] == ["my-spec@myspec"]
    assert report["disabledSources"] == ["my-spec@my-agent-skills-marketplace"]
    assert report["skills"] == list(SKILL_NAMES)
    assert report["reloadRequired"] is True
    assert claude_state.read_bytes() == state_before
    assert [json.loads(line) for line in claude_log.read_text(encoding="utf-8").splitlines()] == [
        ["plugin", "marketplace", "list", "--json"],
        ["plugin", "list", "--json"],
    ]

    state["plugins"][0]["enabled"] = True
    write(claude_state, json.dumps(state, indent=2))
    duplicate = json.loads(run_cli(executable, "doctor", "--claude", env=env).stdout)["claude"]
    assert duplicate["duplicateEnabledSources"] is True
    assert duplicate["enabledSources"] == [
        "my-spec@my-agent-skills-marketplace",
        "my-spec@myspec",
    ]


def test_packed_myspec_doctor_reports_claude_marketplace_source_mismatch_read_only(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / "fake-claude")
    env = isolated_myspec_env(tmp_path, prefix, claude_bin)
    env.update(
        {
            "MYSPEC_CLAUDE_LOG": str(claude_log),
            "MYSPEC_CLAUDE_STATE": str(claude_state),
            "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
        }
    )
    wrong_source = tmp_path / "wrong-source"
    write(
        claude_state,
        json.dumps(
            {
                "marketplaces": [
                    {
                        "name": "myspec",
                        "source": "directory",
                        "path": str(wrong_source),
                        "installLocation": str(wrong_source),
                    }
                ],
                "plugins": [],
            },
            indent=2,
        ),
    )
    before = claude_state.read_bytes()

    diagnosed = run_cli(executable, "doctor", "--claude", env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)["claude"]
    assert report["source"] == str(wrong_source)
    assert report["marketplaceRegistered"] is False
    assert report["marketplaceSourceMismatch"] is True
    assert claude_state.read_bytes() == before


def test_packed_myspec_explicit_claude_init_refreshes_disabled_stale_plugin(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / "fake-claude")
    env = isolated_myspec_env(tmp_path, prefix, claude_bin)
    env.update(
        {
            "MYSPEC_CLAUDE_LOG": str(claude_log),
            "MYSPEC_CLAUDE_STATE": str(claude_state),
            "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
        }
    )
    write(
        claude_state,
        json.dumps(
            {
                "marketplaces": [
                    {
                        "name": "myspec",
                        "source": "directory",
                        "path": str(installed_package),
                        "installLocation": str(installed_package),
                    }
                ],
                "plugins": [
                    {
                        "id": "my-spec@myspec",
                        "version": PREVIOUS_VERSION,
                        "scope": "user",
                        "enabled": False,
                        "installPath": str(tmp_path / "stale-plugin"),
                    }
                ],
            },
            indent=2,
        ),
    )

    initialized = run_cli(executable, "init", "--claude", env=env)
    assert initialized.returncode == 0, initialized.stderr
    plugin = json.loads(claude_state.read_text(encoding="utf-8"))["plugins"][0]
    assert plugin["version"] == PACKAGE_VERSION
    assert plugin["enabled"] is True
    calls = [json.loads(line) for line in claude_log.read_text(encoding="utf-8").splitlines()]
    assert ["plugin", "update", "my-spec@myspec", "--scope", "user"] in calls


def test_packed_myspec_requires_explicit_claude_but_all_initializes_detected_claude(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    missing_env = isolated_myspec_env(tmp_path, prefix)
    missing = run_cli(executable, "init", "--claude", env=missing_env)
    assert missing.returncode == 1
    assert missing.stdout == ""
    assert "error: missing_command: claude" in missing.stderr

    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / "fake-claude")
    env = isolated_myspec_env(tmp_path, prefix, claude_bin)
    env.update(
        {
            "MYSPEC_CLAUDE_LOG": str(claude_log),
            "MYSPEC_CLAUDE_STATE": str(claude_state),
            "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
        }
    )
    write(claude_state, json.dumps({"marketplaces": [], "plugins": []}, indent=2))
    initialized = run_cli(executable, "init", "--all", env=env)
    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(initialized.stdout) == {
        "pi": {"status": "skipped", "reason": "missing_command: pi"},
        "claude": {"status": "initialized", "source": str(installed_package)},
        "codex": {"status": "skipped", "reason": "missing_command: codex"},
    }
    assert any(
        plugin["id"] == "my-spec@myspec"
        for plugin in json.loads(claude_state.read_text(encoding="utf-8"))["plugins"]
    )


def test_packed_myspec_initializes_and_diagnoses_codex_without_deleting_legacy(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / "fake-codex")
    env = isolated_myspec_env(tmp_path, prefix, codex_bin)
    codex_home = Path(env["HOME"]) / ".codex"
    env.update(
        {
            "CODEX_HOME": str(codex_home),
            "MYSPEC_CODEX_LOG": str(codex_log),
            "MYSPEC_CODEX_STATE": str(codex_state),
        }
    )
    legacy_market_root = tmp_path / "legacy-market"
    unrelated_market_root = tmp_path / "other-market"
    legacy_cache = tmp_path / "legacy-cache"
    unrelated_cache = tmp_path / "other-cache"
    write(legacy_cache / "kept.txt", "legacy cache")
    write(unrelated_cache / "kept.txt", "other cache")
    legacy_market = {
        "name": "my-agent-skills-marketplace",
        "root": str(legacy_market_root),
        "marketplaceSource": {
            "sourceType": "git",
            "source": "https://github.com/liuli195/my-agent-skills.git",
        },
    }
    unrelated_market = {
        "name": "other-marketplace",
        "root": str(unrelated_market_root),
        "marketplaceSource": {"sourceType": "git", "source": "https://example.invalid/other.git"},
    }
    legacy_plugin = {
        "pluginId": "my-spec@my-agent-skills-marketplace",
        "name": "my-spec",
        "marketplaceName": "my-agent-skills-marketplace",
        "version": PREVIOUS_VERSION,
        "installed": True,
        "source": {"source": "local", "path": str(legacy_cache)},
    }
    unrelated_plugin = {
        "pluginId": "other@other-marketplace",
        "name": "other",
        "marketplaceName": "other-marketplace",
        "version": "1.0.0",
        "installed": True,
        "source": {"source": "local", "path": str(unrelated_cache)},
    }
    write(
        codex_state,
        json.dumps(
            {
                "marketplaces": [legacy_market, unrelated_market],
                "installed": [legacy_plugin, unrelated_plugin],
                "available": [],
            },
            indent=2,
        ),
    )
    write(
        codex_home / "config.toml",
        '''model = "gpt-test"

[plugins."my-spec@my-agent-skills-marketplace"]
enabled = true

[plugins."other@other-marketplace"]
enabled = true
''',
    )

    initialized = run_cli(executable, "init", "--codex", env=env)
    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(initialized.stdout) == {
        "codex": "initialized",
        "marketplace": "myspec",
        "source": str(installed_package),
        "disabledLegacyPlugins": ["my-spec@my-agent-skills-marketplace"],
        "newSessionRequired": True,
    }
    state = json.loads(codex_state.read_text(encoding="utf-8"))
    assert state["marketplaces"][:2] == [legacy_market, unrelated_market]
    assert state["marketplaces"][2]["name"] == "myspec"
    plugins = {plugin["pluginId"]: plugin for plugin in state["installed"]}
    assert plugins[unrelated_plugin["pluginId"]]["source"] == unrelated_plugin["source"]
    assert plugins["my-spec@myspec"]["version"] == PACKAGE_VERSION
    config = (codex_home / "config.toml").read_text(encoding="utf-8")
    assert '[plugins."my-spec@my-agent-skills-marketplace"]\nenabled = false' in config
    assert '[plugins."my-spec@myspec"]\nenabled = true' in config
    assert '[plugins."other@other-marketplace"]\nenabled = true' in config
    assert (legacy_cache / "kept.txt").is_file()
    assert (unrelated_cache / "kept.txt").is_file()

    before_state = codex_state.read_bytes()
    before_config = (codex_home / "config.toml").read_bytes()
    codex_log.write_text("", encoding="utf-8")
    diagnosed = run_cli(executable, "doctor", "--codex", env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)["codex"]
    assert report["available"] is True
    assert report["marketplaceRegistered"] is True
    assert report["source"] == str(installed_package)
    assert report["version"] == PACKAGE_VERSION
    assert report["enabled"] is True
    assert report["duplicateEnabledSources"] is False
    assert report["enabledSources"] == ["my-spec@myspec"]
    assert report["disabledSources"] == ["my-spec@my-agent-skills-marketplace"]
    assert report["skills"] == list(SKILL_NAMES)
    assert report["newSessionRequired"] is True
    assert "reloadRequired" not in report
    assert codex_state.read_bytes() == before_state
    assert (codex_home / "config.toml").read_bytes() == before_config
    assert [json.loads(line) for line in codex_log.read_text(encoding="utf-8").splitlines()] == [
        ["plugin", "marketplace", "list", "--json"],
        ["plugin", "list", "--json"],
    ]


def test_packed_myspec_requires_explicit_codex_but_all_initializes_detected_codex(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    missing_env = isolated_myspec_env(tmp_path, prefix)
    missing = run_cli(executable, "init", "--codex", env=missing_env)
    assert missing.returncode == 1
    assert missing.stdout == ""
    assert "error: missing_command: codex" in missing.stderr

    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / "fake-codex")
    env = isolated_myspec_env(tmp_path, prefix, codex_bin)
    env.update(
        {
            "CODEX_HOME": str(Path(env["HOME"]) / ".codex"),
            "MYSPEC_CODEX_LOG": str(codex_log),
            "MYSPEC_CODEX_STATE": str(codex_state),
        }
    )
    write(codex_state, json.dumps({"marketplaces": [], "installed": [], "available": []}, indent=2))
    initialized = run_cli(executable, "init", "--all", env=env)
    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(initialized.stdout) == {
        "pi": {"status": "skipped", "reason": "missing_command: pi"},
        "claude": {"status": "skipped", "reason": "missing_command: claude"},
        "codex": {
            "status": "initialized",
            "source": str(installed_package),
            "newSessionRequired": True,
        },
    }


def test_packed_myspec_package_contains_single_codex_marketplace_and_four_skills(
    tmp_path: Path,
) -> None:
    _, installed_package = install_packed_myspec(tmp_path)
    marketplace = json.loads(
        (installed_package / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert marketplace == {
        "name": "myspec",
        "interface": {"displayName": "MySpec"},
        "plugins": [
            {
                "name": "my-spec",
                "source": {"source": "local", "path": "./"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Developer Tools",
            }
        ],
    }
    assert [
        path.parent.name
        for path in sorted((installed_package / "skills").glob("*/SKILL.md"))
    ] == sorted(SKILL_NAMES)


def test_packed_myspec_reports_missing_pi_without_installing_it(tmp_path: Path) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    env = isolated_myspec_env(tmp_path, prefix)

    explicit = run_cli(executable, "init", "--pi", env=env)
    assert explicit.returncode == 1
    assert explicit.stdout == ""
    assert "error: missing_command: pi" in explicit.stderr

    all_agents = run_cli(executable, "init", "--all", env=env)
    assert all_agents.returncode == 0, all_agents.stderr
    assert json.loads(all_agents.stdout) == {
        "pi": {"status": "skipped", "reason": "missing_command: pi"},
        "claude": {"status": "skipped", "reason": "missing_command: claude"},
        "codex": {"status": "skipped", "reason": "missing_command: codex"},
    }
    assert not (Path(env["PI_CODING_AGENT_DIR"]) / "settings.json").exists()


def test_packed_myspec_switches_pi_between_development_and_saved_release(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((tmp_path / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, pi_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            "MYSPEC_PI_LOG": str(pi_log),
        }
    )

    assert run_cli(executable, "init", "--pi", env=env).returncode == 0
    entered = run_cli(executable, "init", "--dev", env=env, cwd=REPO_ROOT)
    assert entered.returncode == 0, entered.stderr
    assert json.loads(entered.stdout) == {
        "mode": "dev",
        "source": str(REPO_ROOT),
        "previousReleaseVersion": PACKAGE_VERSION,
        "pi": "refreshed",
        "reloadRequired": True,
    }
    state_path = Path(env["HOME"]) / ".myspec" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["mode"] == "dev"
    assert state["source"] == str(REPO_ROOT)
    assert state["previousReleaseVersion"] == PACKAGE_VERSION
    assert state["sourceCommit"] == subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    dev_report = run_cli(executable, "doctor", "--pi", env=env)
    dev_diagnosis = json.loads(dev_report.stdout)
    assert dev_diagnosis["source"] == str(PLUGIN_ROOT)
    assert dev_diagnosis["mode"] == "dev"
    assert dev_diagnosis["pi"]["skills"] == list(SKILL_NAMES)
    assert dev_diagnosis["pi"]["registered"] is True
    assert dev_diagnosis["pi"]["listedSources"] == [
        {"scope": "user", "source": str(installed_package), "path": str(installed_package)}
    ]
    settings_path = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    assert json.loads(settings_path.read_text(encoding="utf-8"))["packages"] == [
        str(installed_package)
    ]

    restored = run_cli(executable, "init", "--release", env=env)
    assert restored.returncode == 0, restored.stderr
    assert json.loads(restored.stdout) == {
        "mode": "release",
        "version": PACKAGE_VERSION,
        "pi": "refreshed",
        "reloadRequired": True,
    }
    assert json.loads(state_path.read_text(encoding="utf-8"))["mode"] == "release"
    report = json.loads(run_cli(executable, "doctor", "--pi", env=env).stdout)
    assert report["mode"] == "release"
    assert report["source"] == str(installed_package)
    assert report["pi"]["enabledSources"] == [str(installed_package)]
    assert report["pi"]["skills"] == list(SKILL_NAMES)
    assert report["pi"]["listedSources"] == [
        {"scope": "user", "source": str(installed_package), "path": str(installed_package)}
    ]

    npm_calls = [json.loads(line) for line in npm_log.read_text(encoding="utf-8").splitlines()]
    assert ["link"] in npm_calls
    assert ["install", "--global", "--ignore-scripts", "--no-audit", "--no-fund", f"@liuli195/myspec@{PACKAGE_VERSION}"] in npm_calls
    pi_calls = [json.loads(line)["args"] for line in pi_log.read_text(encoding="utf-8").splitlines()]
    assert pi_calls.count(["install", str(installed_package)]) == 1

    explicit = run_cli(executable, "init", "--dev", "--source", REPO_ROOT, env=env, cwd=tmp_path)
    assert explicit.returncode == 0, explicit.stderr
    assert json.loads(explicit.stdout)["source"] == str(REPO_ROOT)


def test_packed_myspec_requires_release_registration_before_first_codex_dev_init(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((installed / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / "fake-codex")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, codex_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            "CODEX_HOME": str(Path(env["HOME"]) / ".codex"),
            "MYSPEC_CODEX_LOG": str(codex_log),
            "MYSPEC_CODEX_STATE": str(codex_state),
        }
    )
    write(codex_state, json.dumps({"marketplaces": [], "installed": [], "available": []}, indent=2))

    entered = run_cli(executable, "init", "--dev", "--source", REPO_ROOT, env=env)
    assert entered.returncode == 0, entered.stderr
    before = codex_state.read_bytes()
    codex_log.write_text("", encoding="utf-8")

    blocked = run_cli(executable, "init", "--codex", env=env)
    assert blocked.returncode == 1
    assert blocked.stdout == ""
    assert (
        "error: codex_dev_marketplace_unregistered: run 'myspec init --release', "
        "then 'myspec init --codex', then 'myspec init --dev'"
    ) in blocked.stderr
    assert codex_state.read_bytes() == before
    blocked_calls = [json.loads(line) for line in codex_log.read_text(encoding="utf-8").splitlines()]
    assert blocked_calls == [["plugin", "marketplace", "list", "--json"]]

    restored = run_cli(executable, "init", "--release", env=env)
    assert restored.returncode == 0, restored.stderr
    initialized = run_cli(executable, "init", "--codex", env=env)
    assert initialized.returncode == 0, initialized.stderr
    registered = json.loads(codex_state.read_text(encoding="utf-8"))["marketplaces"]
    assert registered == [
        {
            "name": "myspec",
            "root": str(installed_package),
            "marketplaceSource": {"sourceType": "local", "source": str(installed_package)},
        }
    ]

    codex_log.write_text("", encoding="utf-8")
    entered_again = run_cli(executable, "init", "--dev", "--source", REPO_ROOT, env=env)
    assert entered_again.returncode == 0, entered_again.stderr
    calls = [json.loads(line) for line in codex_log.read_text(encoding="utf-8").splitlines()]
    assert not any(call[:3] == ["plugin", "marketplace", "add"] for call in calls)
    assert json.loads(codex_state.read_text(encoding="utf-8"))["marketplaces"] == registered


def test_packed_myspec_refreshes_enabled_codex_across_global_mode_switches(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((installed / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / "fake-codex")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, codex_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            "CODEX_HOME": str(Path(env["HOME"]) / ".codex"),
            "MYSPEC_CODEX_LOG": str(codex_log),
            "MYSPEC_CODEX_STATE": str(codex_state),
        }
    )
    write(codex_state, json.dumps({"marketplaces": [], "installed": [], "available": []}, indent=2))
    assert run_cli(executable, "init", "--codex", env=env).returncode == 0
    codex_log.write_text("", encoding="utf-8")

    source = tmp_path / "source"
    shutil.copytree(REPO_ROOT / ".agents", source / ".agents")
    shutil.copytree(REPO_ROOT / ".claude-plugin", source / ".claude-plugin")
    shutil.copytree(PLUGIN_ROOT, source / "plugins" / "my-spec")
    marker = source / "plugins" / "my-spec" / "skills" / "my-spec" / "dev-marker.txt"
    write(marker, "development source")
    assert subprocess.run(["git", "init"], cwd=source, capture_output=True).returncode == 0
    assert subprocess.run(["git", "add", "."], cwd=source, capture_output=True).returncode == 0
    committed = subprocess.run(
        [
            "git",
            "-c",
            "user.name=MySpec Test",
            "-c",
            "user.email=myspec@example.invalid",
            "commit",
            "-m",
            "development source",
        ],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr

    entered = run_cli(executable, "init", "--dev", "--source", source, env=env)
    assert entered.returncode == 0, entered.stderr
    entered_output = json.loads(entered.stdout)
    assert entered_output["codex"] == "refreshed"
    assert entered_output["newSessionRequired"] is True
    assert entered_output["reloadRequired"] is False
    state = json.loads(codex_state.read_text(encoding="utf-8"))
    plugin = next(item for item in state["installed"] if item["pluginId"] == "my-spec@myspec")
    assert plugin["source"] == {"source": "local", "path": str(source / "plugins" / "my-spec")}
    dev_cache = Path(env["CODEX_HOME"]) / "plugins" / "cache" / "myspec" / "my-spec" / PACKAGE_VERSION
    assert (dev_cache / "skills" / "my-spec" / "dev-marker.txt").read_text(
        encoding="utf-8"
    ) == "development source\n"

    restored = run_cli(executable, "init", "--release", env=env)
    assert restored.returncode == 0, restored.stderr
    restored_output = json.loads(restored.stdout)
    assert restored_output["codex"] == "refreshed"
    assert restored_output["newSessionRequired"] is True
    assert restored_output["reloadRequired"] is False
    state = json.loads(codex_state.read_text(encoding="utf-8"))
    plugin = next(item for item in state["installed"] if item["pluginId"] == "my-spec@myspec")
    assert plugin["source"] == {"source": "local", "path": str(installed_package)}
    assert not (dev_cache / "skills" / "my-spec" / "dev-marker.txt").exists()
    calls = [json.loads(line) for line in codex_log.read_text(encoding="utf-8").splitlines()]
    assert calls.count(["plugin", "remove", "my-spec@myspec", "--json"]) == 2
    assert calls.count(["plugin", "add", "my-spec@myspec", "--json"]) == 2
    assert not any(call[:3] == ["plugin", "marketplace", "upgrade"] for call in calls)


@pytest.mark.parametrize("disabled", [False, True])
def test_packed_myspec_mode_switch_does_not_install_missing_or_disabled_codex(
    tmp_path: Path,
    disabled: bool,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((installed / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    codex_bin, codex_log, codex_state = install_fake_codex(tmp_path / "fake-codex")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, codex_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            "CODEX_HOME": str(Path(env["HOME"]) / ".codex"),
            "MYSPEC_CODEX_LOG": str(codex_log),
            "MYSPEC_CODEX_STATE": str(codex_state),
        }
    )
    initial_state: dict[str, object] = {"marketplaces": [], "installed": [], "available": []}
    if disabled:
        cache = tmp_path / "disabled-cache"
        shutil.copytree(installed_package, cache)
        initial_state = {
            "marketplaces": [
                {
                    "name": "myspec",
                    "root": str(installed_package),
                    "marketplaceSource": {"sourceType": "local", "source": str(installed_package)},
                }
            ],
            "installed": [
                {
                    "pluginId": "my-spec@myspec",
                    "name": "my-spec",
                    "marketplaceName": "myspec",
                    "version": PACKAGE_VERSION,
                    "installed": True,
                    "source": {"source": "local", "path": str(cache)},
                }
            ],
            "available": [],
        }
        write(
            Path(env["CODEX_HOME"]) / "config.toml",
            '[plugins."my-spec@myspec"]\nenabled = false\n',
        )
    write(codex_state, json.dumps(initial_state, indent=2))

    entered = run_cli(executable, "init", "--dev", "--source", REPO_ROOT, env=env)
    assert entered.returncode == 0, entered.stderr
    assert json.loads(entered.stdout)["codex"] == "not-installed"
    restored = run_cli(executable, "init", "--release", env=env)
    assert restored.returncode == 0, restored.stderr
    assert json.loads(restored.stdout)["codex"] == "not-installed"
    calls = [json.loads(line) for line in codex_log.read_text(encoding="utf-8").splitlines()]
    assert not any(call[:2] == ["plugin", "add"] for call in calls)
    assert not any(call[:2] == ["plugin", "remove"] for call in calls)
    assert json.loads(codex_state.read_text(encoding="utf-8")) == initial_state


def test_packed_myspec_refreshes_enabled_claude_across_global_mode_switches(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((installed / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / "fake-claude")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, claude_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            "MYSPEC_CLAUDE_LOG": str(claude_log),
            "MYSPEC_CLAUDE_STATE": str(claude_state),
            "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
        }
    )
    write(claude_state, json.dumps({"marketplaces": [], "plugins": []}, indent=2))
    assert run_cli(executable, "init", "--claude", env=env).returncode == 0
    claude_log.write_text("", encoding="utf-8")

    source = tmp_path / "source"
    shutil.copytree(REPO_ROOT / ".agents", source / ".agents")
    shutil.copytree(REPO_ROOT / ".claude-plugin", source / ".claude-plugin")
    shutil.copytree(PLUGIN_ROOT, source / "plugins" / "my-spec")
    marker = source / "plugins" / "my-spec" / "skills" / "my-spec" / "dev-marker.txt"
    write(marker, "development source")
    initialized_git = subprocess.run(
        ["git", "init"], cwd=source, text=True, capture_output=True, check=False
    )
    assert initialized_git.returncode == 0, initialized_git.stderr
    committed = subprocess.run(
        [
            "git",
            "-c",
            "user.name=MySpec Test",
            "-c",
            "user.email=myspec@example.invalid",
            "add",
            ".",
        ],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr
    committed = subprocess.run(
        [
            "git",
            "-c",
            "user.name=MySpec Test",
            "-c",
            "user.email=myspec@example.invalid",
            "commit",
            "-m",
            "development source",
        ],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr

    entered = run_cli(executable, "init", "--dev", "--source", source, env=env)
    assert entered.returncode == 0, entered.stderr
    assert json.loads(entered.stdout)["claude"] == "refreshed"
    state = json.loads(claude_state.read_text(encoding="utf-8"))
    plugin = next(item for item in state["plugins"] if item["id"] == "my-spec@myspec")
    dev_cache = Path(plugin["installPath"])
    assert (dev_cache / "skills" / "my-spec" / "dev-marker.txt").read_text(
        encoding="utf-8"
    ) == "development source\n"

    restored = run_cli(executable, "init", "--release", env=env)
    assert restored.returncode == 0, restored.stderr
    assert json.loads(restored.stdout)["claude"] == "refreshed"
    state = json.loads(claude_state.read_text(encoding="utf-8"))
    plugin = next(item for item in state["plugins"] if item["id"] == "my-spec@myspec")
    assert not (Path(plugin["installPath"]) / "skills" / "my-spec" / "dev-marker.txt").exists()
    calls = [json.loads(line) for line in claude_log.read_text(encoding="utf-8").splitlines()]
    assert calls.count(["plugin", "marketplace", "update", "myspec"]) == 2
    assert calls.count(["plugin", "uninstall", "my-spec@myspec", "--scope", "user", "--keep-data"]) == 2
    assert calls.count(["plugin", "install", "my-spec@myspec", "--scope", "user"]) == 2
    assert calls.count(["plugin", "enable", "my-spec@myspec", "--scope", "user"]) == 0
    assert not any(call[:2] == ["plugin", "update"] for call in calls)


@pytest.mark.parametrize("disabled", [False, True])
def test_packed_myspec_mode_switch_does_not_install_missing_or_disabled_claude(
    tmp_path: Path,
    disabled: bool,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((installed / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / "fake-claude")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, claude_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            "MYSPEC_CLAUDE_LOG": str(claude_log),
            "MYSPEC_CLAUDE_STATE": str(claude_state),
            "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
        }
    )
    initial_state = {"marketplaces": [], "plugins": []}
    if disabled:
        initial_state = {
            "marketplaces": [
                {
                    "name": "myspec",
                    "source": "directory",
                    "path": str(installed_package),
                    "installLocation": str(installed_package),
                }
            ],
            "plugins": [
                {
                    "id": "my-spec@myspec",
                    "version": PACKAGE_VERSION,
                    "scope": "user",
                    "enabled": False,
                    "installPath": str(tmp_path / "disabled-plugin-cache"),
                }
            ],
        }
    write(claude_state, json.dumps(initial_state, indent=2))

    entered = run_cli(executable, "init", "--dev", "--source", REPO_ROOT, env=env)
    assert entered.returncode == 0, entered.stderr
    assert json.loads(entered.stdout)["claude"] == "not-installed"
    restored = run_cli(executable, "init", "--release", env=env)
    assert restored.returncode == 0, restored.stderr
    assert json.loads(restored.stdout)["claude"] == "not-installed"
    calls = [json.loads(line) for line in claude_log.read_text(encoding="utf-8").splitlines()]
    assert not any(call[:3] == ["plugin", "marketplace", "add"] for call in calls)
    assert not any(call[:2] == ["plugin", "install"] for call in calls)
    assert not any(call[:2] == ["plugin", "enable"] for call in calls)
    assert json.loads(claude_state.read_text(encoding="utf-8")) == initial_state


def test_packed_myspec_claude_reinstall_failure_does_not_report_refreshed(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    executable, installed_package = install_packed_myspec(installed)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((installed / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    claude_bin, claude_log, claude_state = install_fake_claude(tmp_path / "fake-claude")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, claude_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            "MYSPEC_CLAUDE_LOG": str(claude_log),
            "MYSPEC_CLAUDE_STATE": str(claude_state),
            "MYSPEC_CLAUDE_HOME": str(Path(env["HOME"]) / ".claude"),
        }
    )
    write(claude_state, json.dumps({"marketplaces": [], "plugins": []}, indent=2))
    assert run_cli(executable, "init", "--claude", env=env).returncode == 0
    claude_log.write_text("", encoding="utf-8")

    failed = run_cli(
        executable,
        "init",
        "--dev",
        "--source",
        REPO_ROOT,
        env={**env, "MYSPEC_CLAUDE_FAIL_INSTALL": "1"},
    )
    assert failed.returncode == 1
    assert failed.stdout == ""
    assert "claude_plugin_install_failed: simulated install failure" in failed.stderr
    assert "refreshed" not in failed.stderr
    calls = [json.loads(line) for line in claude_log.read_text(encoding="utf-8").splitlines()]
    assert ["plugin", "uninstall", "my-spec@myspec", "--scope", "user", "--keep-data"] in calls
    assert ["plugin", "install", "my-spec@myspec", "--scope", "user"] in calls
    assert ["plugin", "enable", "my-spec@myspec", "--scope", "user"] not in calls


def test_packed_myspec_release_install_failure_stays_in_dev_and_retries(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((tmp_path / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    env = isolated_myspec_env(tmp_path, prefix, npm_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
        }
    )

    entered = run_cli(executable, "init", "--dev", env=env, cwd=REPO_ROOT)
    assert entered.returncode == 0, entered.stderr
    state_path = Path(env["HOME"]) / ".myspec" / "state.json"

    failed_env = {**env, "MYSPEC_NPM_FAIL_INSTALL": "1"}
    failed = run_cli(executable, "init", "--release", env=failed_env)
    assert failed.returncode == 1
    assert "error: npm_install_failed: simulated install failure" in failed.stderr
    failed_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert failed_state["mode"] == "dev"
    assert failed_state["previousReleaseVersion"] == PACKAGE_VERSION

    retried = run_cli(executable, "init", "--release", env=env)
    assert retried.returncode == 0, retried.stderr
    assert json.loads(state_path.read_text(encoding="utf-8"))["mode"] == "release"


def test_packed_myspec_mode_switch_does_not_install_a_disabled_pi_integration(
    tmp_path: Path,
) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((tmp_path / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, npm_bin, pi_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
            "MYSPEC_PI_LOG": str(pi_log),
            "MYSPEC_SWITCH_STAGE": "dev",
        }
    )
    settings_path = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    write(
        settings_path,
        json.dumps({"packages": [{"source": str(installed_package), "skills": []}]}, indent=2),
    )

    forged = run_cli(
        executable,
        "init",
        "--dev",
        "--source",
        REPO_ROOT,
        "--_switch-token",
        "forged",
        env=env,
    )
    assert forged.returncode == 1
    assert "error: invalid_switch_token" in forged.stderr

    entered = run_cli(executable, "init", "--dev", "--source", REPO_ROOT, env=env)
    assert entered.returncode == 0, entered.stderr
    assert json.loads(entered.stdout)["pi"] == "not-installed"
    restored = run_cli(executable, "init", "--release", env=env)
    assert restored.returncode == 0, restored.stderr
    assert json.loads(restored.stdout)["pi"] == "not-installed"
    assert json.loads(settings_path.read_text(encoding="utf-8"))["packages"] == [
        {"source": str(installed_package), "skills": []}
    ]
    pi_calls = (
        [json.loads(line)["args"] for line in pi_log.read_text(encoding="utf-8").splitlines()]
        if pi_log.exists()
        else []
    )
    assert not any(call[:1] == ["install"] for call in pi_calls)
    npm_calls = [json.loads(line) for line in npm_log.read_text(encoding="utf-8").splitlines()]
    assert ["link"] in npm_calls
    report = json.loads(run_cli(executable, "doctor", "--pi", env=env).stdout)
    assert report["pi"]["registered"] is True
    assert report["pi"]["skills"] == []


def test_packed_myspec_doctor_uses_actual_installation_not_mode_state(tmp_path: Path) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    prefix = npm_prefix_for(installed_package)
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, prefix, pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    settings_path = Path(env["PI_CODING_AGENT_DIR"]) / "settings.json"
    write(settings_path, json.dumps({"packages": [str(installed_package)]}, indent=2))
    write(
        Path(env["HOME"]) / ".myspec" / "state.json",
        json.dumps({"mode": "dev", "source": "C:/not-the-package", "previousReleaseVersion": "9.9.9"}),
    )

    settings_before = settings_path.read_bytes()
    state_before = (Path(env["HOME"]) / ".myspec" / "state.json").read_bytes()
    diagnosed = run_cli(executable, "doctor", env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report["mode"] == "release"
    assert report["source"] == str(installed_package)
    assert report["npm"]["linked"] is False
    assert report["npm"]["versionMismatch"] is False
    assert report["pi"]["listedSources"] == [
        {"scope": "user", "source": str(installed_package), "path": str(installed_package)}
    ]
    assert settings_path.read_bytes() == settings_before
    assert (Path(env["HOME"]) / ".myspec" / "state.json").read_bytes() == state_before

    all_agents = run_cli(executable, "doctor", "--all", env=env)
    assert all_agents.returncode == 0, all_agents.stderr
    assert json.loads(all_agents.stdout)["pi"]["listedSources"] == report["pi"]["listedSources"]


def test_packed_myspec_doctor_reports_actual_package_version_mismatch(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    executable, _ = install_packed_myspec(first)
    _, installed_package = install_packed_myspec(second)
    package_path = installed_package / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = NEXT_VERSION
    write(package_path, json.dumps(package, indent=2))
    pi_bin, pi_log = install_fake_pi(tmp_path / "fake-pi")
    env = isolated_myspec_env(tmp_path, npm_prefix_for(installed_package), pi_bin)
    env["MYSPEC_PI_LOG"] = str(pi_log)
    write(
        Path(env["PI_CODING_AGENT_DIR"]) / "settings.json",
        json.dumps({"packages": [str(installed_package)]}, indent=2),
    )

    diagnosed = run_cli(executable, "doctor", "--pi", env=env)
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report["cliVersion"] == PACKAGE_VERSION
    assert report["npm"]["packageVersion"] == NEXT_VERSION
    assert report["npm"]["versionMismatch"] is True


def test_packed_myspec_rejects_invalid_mode_switches(tmp_path: Path) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    env = isolated_myspec_env(tmp_path, npm_prefix_for(installed_package))

    invalid_source = run_cli(executable, "init", "--dev", "--source", tmp_path, env=env)
    assert invalid_source.returncode == 1
    assert "error: invalid_dev_source: missing" in invalid_source.stderr
    assert not (Path(env["HOME"]) / ".myspec" / "state.json").exists()

    checkout = tmp_path / "checkout"
    nested = checkout / "nested"
    shutil.copytree(REPO_ROOT / ".agents", nested / ".agents")
    shutil.copytree(REPO_ROOT / ".claude-plugin", nested / ".claude-plugin")
    shutil.copytree(PLUGIN_ROOT, nested / "plugins" / "my-spec")
    initialized_git = subprocess.run(
        ["git", "init"], cwd=checkout, text=True, capture_output=True, check=False
    )
    assert initialized_git.returncode == 0, initialized_git.stderr
    borrowed_root = run_cli(executable, "init", "--dev", "--source", nested, env=env)
    assert borrowed_root.returncode == 1
    assert "error: invalid_dev_source: git_root" in borrowed_root.stderr

    malformed = tmp_path / "malformed"
    shutil.copytree(REPO_ROOT / ".agents", malformed / ".agents")
    shutil.copytree(REPO_ROOT / ".claude-plugin", malformed / ".claude-plugin")
    shutil.copytree(PLUGIN_ROOT, malformed / "plugins" / "my-spec")
    market_path = malformed / ".agents" / "plugins" / "marketplace.json"
    market = json.loads(market_path.read_text(encoding="utf-8"))
    next(plugin for plugin in market["plugins"] if plugin["name"] == "my-spec")["source"]["path"] = "../wrong"
    write(market_path, json.dumps(market, indent=2))
    malformed_result = run_cli(executable, "init", "--dev", "--source", malformed, env=env)
    assert malformed_result.returncode == 1
    assert "error: invalid_dev_source: marketplace" in malformed_result.stderr

    next(plugin for plugin in market["plugins"] if plugin["name"] == "my-spec")["source"]["path"] = "./plugins/my-spec"
    write(market_path, json.dumps(market, indent=2))
    package_path = malformed / "plugins" / "my-spec" / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["name"] = "@liuli195/myspec-helper"
    write(package_path, json.dumps(package, indent=2))
    package_result = run_cli(executable, "init", "--dev", "--source", malformed, env=env)
    assert package_result.returncode == 1
    assert "error: invalid_dev_source: package_manifest" in package_result.stderr

    result = run_cli(executable, "init", "--release", env=env)
    assert result.returncode == 1
    assert "error: missing_previous_release_version" in result.stderr


@pytest.mark.parametrize(
    "case",
    [
        "package-name",
        "package-version",
        "bin-entry",
        "bin-file",
        "python-entry",
        "management-entry",
        "pi-skills",
        "skill-file",
        "codex-marketplace",
        "claude-marketplace",
        "self-claude-marketplace",
        "plugin-manifest",
    ],
)
def test_packed_myspec_dev_preflight_rejects_incomplete_source_before_link_or_state(
    tmp_path: Path,
    case: str,
) -> None:
    (tmp_path / "installed").mkdir()
    executable, installed_package = install_packed_myspec(tmp_path / "installed")
    prefix = npm_prefix_for(installed_package)
    release_tarball = next((tmp_path / "installed" / "package").glob("*.tgz"))
    npm_bin, npm_log = install_fake_npm(tmp_path / "fake-npm", release_tarball)
    env = isolated_myspec_env(tmp_path, prefix, npm_bin)
    env.update(
        {
            "MYSPEC_NPM_LOG": str(npm_log),
            "MYSPEC_REAL_NPM": str(shutil.which("npm")),
            "MYSPEC_RELEASE_TARBALL": str(release_tarball),
        }
    )
    source = tmp_path / "source"
    shutil.copytree(REPO_ROOT / ".agents", source / ".agents")
    shutil.copytree(REPO_ROOT / ".claude-plugin", source / ".claude-plugin")
    shutil.copytree(PLUGIN_ROOT, source / "plugins" / "my-spec")
    initialized = subprocess.run(
        ["git", "init"], cwd=source, text=True, capture_output=True, check=False
    )
    assert initialized.returncode == 0, initialized.stderr
    committed = subprocess.run(
        [
            "git",
            "-c",
            "user.name=MySpec Test",
            "-c",
            "user.email=myspec@example.invalid",
            "add",
            ".",
        ],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr
    committed = subprocess.run(
        [
            "git",
            "-c",
            "user.name=MySpec Test",
            "-c",
            "user.email=myspec@example.invalid",
            "commit",
            "-m",
            "test source",
        ],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr
    package_path = source / "plugins" / "my-spec" / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))

    if case == "package-name":
        package["name"] = "@liuli195/not-myspec"
    elif case == "package-version":
        package["version"] = ""
    elif case == "bin-entry":
        package["bin"] = {"myspec": "./bin/other.js"}
    elif case == "bin-file":
        (source / "plugins" / "my-spec" / "bin" / "myspec.js").unlink()
    elif case == "python-entry":
        (source / "plugins" / "my-spec" / "python" / "spec_ops.py").unlink()
    elif case == "management-entry":
        (source / "plugins" / "my-spec" / "python" / "management.py").unlink()
    elif case == "pi-skills":
        package["pi"]["skills"].append("./skills/my-spec-extra")
    elif case == "skill-file":
        (source / "plugins" / "my-spec" / "skills" / "my-spec-audit" / "SKILL.md").unlink()
    elif case == "codex-marketplace":
        market_path = source / ".agents" / "plugins" / "marketplace.json"
        market = json.loads(market_path.read_text(encoding="utf-8"))
        next(plugin for plugin in market["plugins"] if plugin["name"] == "my-spec")["source"]["path"] = "../wrong"
        write(market_path, json.dumps(market, indent=2))
    elif case == "claude-marketplace":
        market_path = source / ".claude-plugin" / "marketplace.json"
        market = json.loads(market_path.read_text(encoding="utf-8"))
        next(plugin for plugin in market["plugins"] if plugin["name"] == "my-spec")["source"] = "../wrong"
        write(market_path, json.dumps(market, indent=2))
    elif case == "self-claude-marketplace":
        market_path = source / "plugins" / "my-spec" / ".claude-plugin" / "marketplace.json"
        market = json.loads(market_path.read_text(encoding="utf-8"))
        market["plugins"][0]["source"] = "../wrong"
        write(market_path, json.dumps(market, indent=2))
    else:
        plugin_path = source / "plugins" / "my-spec" / ".codex-plugin" / "plugin.json"
        plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
        plugin["version"] = "9.9.9"
        write(plugin_path, json.dumps(plugin, indent=2))
    write(package_path, json.dumps(package, indent=2))

    rejected = run_cli(executable, "init", "--dev", "--source", source, env=env)
    assert rejected.returncode == 1
    assert "error: invalid_dev_source:" in rejected.stderr
    assert not (Path(env["HOME"]) / ".myspec" / "state.json").exists()
    calls = (
        [json.loads(line) for line in npm_log.read_text(encoding="utf-8").splitlines()]
        if npm_log.exists()
        else []
    )
    assert ["link"] not in calls


def windows_py_launcher() -> Path:
    candidates = (
        Path(sys.executable).parent.parent / "Launcher" / "py.exe",
        Path(os.environ.get("SystemRoot", "C:/Windows")) / "py.exe",
        Path(shutil.which("py") or ""),
    )
    launcher = next(
        (path for path in candidates if path.is_file() and "WindowsApps" not in path.parts),
        None,
    )
    assert launcher is not None
    return launcher


def run_launcher_selection(
    executable: Path,
    root: Path,
    versions: dict[str, str],
    override_version: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[Path], dict[str, Path]]:
    candidates = root / "candidates"
    candidates.mkdir(parents=True)
    paths: dict[str, Path] = {}
    reported_versions: dict[str, str] = {}
    for name, version in versions.items():
        if name == "py":
            source = windows_py_launcher()
        else:
            source = sys.executable
        path = candidates / (f"{name}.exe" if sys.platform == "win32" else name)
        shutil.copy2(source, path)
        paths[name] = path.resolve()
        if version == "3.11":
            reported_versions[os.path.normcase(str(paths[name]))] = version

    env = {
        **os.environ,
        "PATH": os.pathsep.join(
            (
                str(candidates),
                str(Path(shutil.which("node") or "").parent),
                str(Path(sys.executable).parent),
            )
        ),
        "PYTHONPATH": str(root),
        "MYSPEC_TEST_MARKER": str(root / "selected.txt"),
    }
    env.pop("MYSPEC_PYTHON", None)
    if override_version is not None:
        override = root / ("override.exe" if sys.platform == "win32" else "override")
        shutil.copy2(sys.executable, override)
        env["MYSPEC_PYTHON"] = str(override)
        paths["MYSPEC_PYTHON"] = override.resolve()
        if override_version == "3.11":
            reported_versions[os.path.normcase(str(paths["MYSPEC_PYTHON"]))] = override_version
    if sys.platform == "win32" and versions.get("py") == "3.11":
        reported_versions[os.path.normcase(str(Path(sys.executable).resolve()))] = "3.11"
    env["MYSPEC_TEST_VERSIONS"] = json.dumps(reported_versions)
    write(
        root / "sitecustomize.py",
        """import json
import os
import sys
from pathlib import Path

executable = Path(sys.executable).resolve()
with Path(os.environ["MYSPEC_TEST_MARKER"]).open("a", encoding="utf-8") as marker:
    marker.write(str(executable) + "\\n")
version = json.loads(os.environ["MYSPEC_TEST_VERSIONS"]).get(os.path.normcase(str(executable)))
if version:
    major, minor = map(int, version.split("."))
    sys.version_info = type("VersionInfo", (), {"major": major, "minor": minor})()
""",
    )
    result = run_cli(executable, "--help", env=env)
    marker = Path(env["MYSPEC_TEST_MARKER"])
    observed = (
        [Path(line) for line in marker.read_text(encoding="utf-8").splitlines()]
        if marker.exists()
        else []
    )
    return result, observed, paths


def test_atomic_management_write_retries_windows_sharing_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    management = load_management_module()
    target = tmp_path / "settings.json"
    target.write_text("{}\n", encoding="utf-8")
    attempts = 0

    def transient_replace(source: Path, destination: Path) -> Path:
        nonlocal attempts
        attempts += 1
        raise PermissionError("simulated file watcher sharing violation")

    monkeypatch.setattr(management.os, "name", "nt")
    monkeypatch.setattr(Path, "replace", transient_replace)
    monkeypatch.setattr(management.time, "sleep", lambda _seconds: None)

    management._atomic_json(target, {"packages": ["myspec"]})

    assert attempts == 5
    assert json.loads(target.read_text(encoding="utf-8")) == {"packages": ["myspec"]}


def test_packed_myspec_installs_a_working_cli_with_agent_resources(tmp_path: Path) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    assert not list(installed_package.rglob("__pycache__"))
    assert not list(installed_package.rglob("*.pyc"))
    path_candidates = {"python3.12": "3.12", "python3": "3.12", "python": "3.12"}
    if sys.platform == "win32":
        path_candidates["py"] = "3.12"

    override, observed, paths = run_launcher_selection(
        executable,
        tmp_path / "override-case",
        path_candidates,
        override_version="3.12",
    )
    assert override.returncode == 0, override.stderr
    assert observed[-1] == paths["MYSPEC_PYTHON"]

    cases = [
        ({**path_candidates}, "python3.12"),
        ({**path_candidates, "python3.12": "3.11"}, "python3"),
        ({**path_candidates, "python3.12": "3.11", "python3": "3.11"}, "python"),
    ]
    if sys.platform == "win32":
        cases.append(({name: "3.11" for name in path_candidates} | {"py": "3.12"}, "py"))
    for index, (versions, expected) in enumerate(cases):
        result, observed, paths = run_launcher_selection(
            executable,
            tmp_path / f"priority-case-{index}",
            versions,
            override_version="3.11" if index == 0 else None,
        )
        assert result.returncode == 0, result.stderr
        if expected == "py":
            assert observed[-1] not in paths.values()
        else:
            assert observed[-1] == paths[expected]

    ineligible_versions = {name: "3.11" for name in path_candidates}
    ineligible, _, _ = run_launcher_selection(
        executable,
        tmp_path / "ineligible-case",
        ineligible_versions,
        override_version="3.11",
    )
    assert ineligible.returncode != 0
    assert "error: Python 3.12 or newer is required" in ineligible.stderr
    assert ineligible.stderr.count("(3.11)") == len(ineligible_versions) + 1

    help_result = run_cli(executable, "--help")
    assert help_result.returncode == 0
    assert help_result.stdout.startswith("usage: myspec ")
    for command in (
        "state-init",
        "state-set-conflicts",
        "state-current",
        "state-decide",
        "state-status",
        "validate-main",
        "validate-delta",
        "apply-delta",
        "diff",
    ):
        assert command in help_result.stdout

    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    work = tmp_path / "work"
    conflicts_file = tmp_path / "conflicts.json"
    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
    write(
        delta / "accounts" / "spec.md",
        """## ADDED Requirements

### Requirement: 注销

系统 MUST 允许用户注销。

#### Scenario: 主动注销

- **WHEN** 用户选择注销
- **THEN** 系统结束会话
""",
    )
    conflict = {
        "id": "conflict-1",
        "candidate": "新增注销",
        "evidence": ["accounts/spec.md:1"],
        "reason": "需要确认",
        "recommendation": "接受",
    }
    write(conflicts_file, json.dumps([conflict], ensure_ascii=False))

    for command in (
        run_cli(executable, "validate-main", specs),
        run_cli(executable, "validate-delta", delta, specs),
        run_cli(executable, "state-init", work, "add", "specs-fingerprint", "input-fingerprint"),
    ):
        assert command.returncode == 0, command.stderr
        assert command.stdout == ""
        assert command.stderr == ""

    stored = run_cli(
        executable,
        "state-set-conflicts",
        work,
        conflicts_file,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert stored.returncode == 0, stored.stderr
    assert json.loads(stored.stdout) == {"status": "WAITING_DECISION", "total": 1, "remaining": 1}
    current = run_cli(executable, "state-current", work, "specs-fingerprint", "input-fingerprint")
    assert current.returncode == 0, current.stderr
    assert json.loads(current.stdout) == {"index": 0, "total": 1, "conflict": conflict}

    wrong_decision = run_cli(
        executable,
        "state-decide",
        work,
        "wrong-conflict",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert wrong_decision.returncode == 1
    assert "error: unexpected_conflict_id: expected_conflict-1: wrong-conflict" in wrong_decision.stderr
    decided = run_cli(
        executable,
        "state-decide",
        work,
        "conflict-1",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert decided.returncode == 0, decided.stderr
    expected_ready = {"status": "READY_TO_APPLY", "total": 1, "decided": 1, "remaining": 0}
    assert json.loads(decided.stdout) == expected_ready
    status = run_cli(executable, "state-status", work, "specs-fingerprint", "input-fingerprint")
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout) == expected_ready

    applied = run_cli(
        executable,
        "apply-delta",
        specs,
        delta,
        preview,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert applied.returncode == 0, applied.stderr
    assert applied.stdout == ""
    assert run_cli(executable, "validate-main", preview).returncode == 0
    assert "### Requirement: 注销" in (preview / "accounts" / "spec.md").read_text(encoding="utf-8")
    diff = run_cli(executable, "diff", specs, preview)
    assert diff.returncode == 0, diff.stderr
    assert "+### Requirement: 注销" in diff.stdout

    final_apply = run_cli(
        executable,
        "apply-delta",
        specs,
        delta,
        specs,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert final_apply.returncode == 0, final_apply.stderr
    assert final_apply.stdout == ""
    assert run_cli(executable, "validate-main", specs).returncode == 0
    assert run_cli(executable, "diff", specs, preview).stdout == ""
    assert (specs / "accounts" / "spec.md").read_bytes() == (
        preview / "accounts" / "spec.md"
    ).read_bytes()
    assert not (work / "current").exists()
    assert not (work / "lock").exists()
    assert not work.exists()
    assert not any(path.name.startswith(".my-spec-") for path in specs.parent.iterdir())

    write(
        specs / "accounts" / "spec.md",
        main_spec("Accounts", requirement("登录", "允许登录")).replace("MUST", "必须"),
    )
    invalid = run_cli(executable, "validate-main", specs)
    assert invalid.returncode == 1
    assert "error: missing_must_or_shall: 登录" in invalid.stderr
    assert "Traceback" not in invalid.stderr
    missing_argument = run_cli(executable, "state-init", work)
    assert missing_argument.returncode == 2
    assert "usage: myspec state-init" in missing_argument.stderr

    node = shutil.which("node")
    assert node is not None
    no_python = run_cli(
        executable,
        "validate-main",
        specs,
        env={**os.environ, "PATH": str(Path(node).parent), "MYSPEC_PYTHON": "not-a-python"},
    )
    assert no_python.returncode != 0
    assert "error: Python 3.12 or newer is required" in no_python.stderr
    assert (
        "checked not-a-python (unavailable), python3.12 (unavailable), "
        "python3 (unavailable), python (unavailable)"
    ) in no_python.stderr

    assert {path.name for path in (installed_package / "skills").iterdir()} == set(SKILL_NAMES)
    assert (installed_package / ".claude-plugin" / "plugin.json").is_file()
    claude_marketplace = json.loads(
        (installed_package / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert claude_marketplace["name"] == "myspec"
    assert claude_marketplace["description"] == "Self-contained MySpec plugin marketplace"
    assert claude_marketplace["plugins"] == [
        {
            "name": "my-spec",
            "source": "./",
            "description": "MySpec audit, review, and document-to-delta Skill（开放规格审计、审查与文档增量技能）",
        }
    ]
    claude_manifest = json.loads(
        (installed_package / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert claude_manifest["author"] == {"name": "liuli195"}
    assert (installed_package / ".codex-plugin" / "plugin.json").is_file()
    assert [path.relative_to(installed_package).as_posix() for path in installed_package.rglob("spec_ops.py")] == [
        "python/spec_ops.py",
    ]
    skill_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((installed_package / "skills").rglob("*.md"))
    )
    assert "spec_ops.py" not in skill_text
    rules = (installed_package / "skills" / "my-spec" / "references" / "myspec-rules.md").read_text(
        encoding="utf-8"
    )
    for command in (
        "state-init",
        "state-set-conflicts",
        "state-current",
        "state-decide",
        "state-status",
        "validate-main",
        "validate-delta",
        "apply-delta",
        "diff",
    ):
        assert f"myspec {command}" in rules


def test_myspec_launcher_forwards_sigterm_to_python(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("Windows cannot deliver a catchable SIGTERM to another process")
    executable, installed_package = install_packed_myspec(tmp_path)
    marker = tmp_path / "signal.txt"
    ready = tmp_path / "ready.txt"
    (installed_package / "python" / "spec_ops.py").write_text(
        """import os
import signal
import sys
import time
from pathlib import Path

marker = Path(sys.argv[1])
ready = Path(sys.argv[2])
parent = os.getppid()

def stop(signum, _frame):
    marker.write_text(str(signum), encoding="utf-8")
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop)
ready.write_text("ready", encoding="utf-8")
while os.getppid() == parent:
    time.sleep(0.01)
""",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [str(executable), str(marker), str(ready)],
        env={**os.environ, "MYSPEC_PYTHON": sys.executable},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 10
    while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ready.exists(), "Python child did not start"

    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=10) == 0
    assert marker.read_text(encoding="utf-8") == str(signal.SIGTERM)


def test_spec_ops_cli_validates_applies_all_delta_operations_and_diffs(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    write(
        specs / "accounts" / "spec.md",
        main_spec(
            "Accounts",
            requirement("旧登录", "允许登录"),
            requirement("旧导出", "允许导出"),
            requirement("个人资料", "显示姓名"),
        ),
    )
    write(
        delta / "accounts" / "spec.md",
        """# Accounts

## Purpose

描述 Accounts 的外部行为。

## RENAMED Requirements

FROM: 旧登录
TO: 密码登录

## REMOVED Requirements

### Requirement: 旧导出

## MODIFIED Requirements

### Requirement: 个人资料

系统 SHALL 显示姓名和头像。

#### Scenario: 查看资料

- **WHEN** 用户打开个人资料
- **THEN** 系统显示姓名和头像

## ADDED Requirements

### Requirement: 注销

系统 MUST 允许用户注销。

#### Scenario: 主动注销

- **WHEN** 用户选择注销
- **THEN** 系统结束会话
""",
    )

    work = ready_state(SPEC_OPS, tmp_path / "state")
    assert run_python(SPEC_OPS, "validate-main", specs).returncode == 0
    assert run_python(SPEC_OPS, "validate-delta", delta, specs).returncode == 0
    applied = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert applied.returncode == 0, applied.stderr
    assert run_python(SPEC_OPS, "validate-main", preview).returncode == 0

    merged = (preview / "accounts" / "spec.md").read_text(encoding="utf-8")
    assert "### Requirement: 密码登录" in merged
    assert "### Requirement: 旧登录" not in merged
    assert "### Requirement: 旧导出" not in merged
    assert "系统 SHALL 显示姓名和头像。" in merged
    assert "### Requirement: 注销" in merged

    diff = run_python(SPEC_OPS, "diff", specs, preview)
    assert diff.returncode == 0
    assert "-### Requirement: 旧登录" in diff.stdout
    assert "+### Requirement: 密码登录" in diff.stdout
    assert "旧导出" in diff.stdout
    assert "注销" in diff.stdout

    first_apply = apply_ready(SPEC_OPS, specs, delta, specs, work)
    assert first_apply.returncode == 0, first_apply.stderr
    before_repeat = (specs / "accounts" / "spec.md").read_bytes()
    repeated_validation = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert repeated_validation.returncode == 0, repeated_validation.stderr
    repeated_work = ready_state(SPEC_OPS, tmp_path / "repeated-state")
    repeated_apply = apply_ready(SPEC_OPS, specs, delta, specs, repeated_work)
    assert repeated_apply.returncode == 0, repeated_apply.stderr
    assert (specs / "accounts" / "spec.md").read_bytes() == before_repeat


def test_spec_ops_cli_rejects_invalid_specs_and_delta_references(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    write(
        specs / "accounts" / "spec.md",
        main_spec("Accounts", requirement("登录", "允许登录").replace("MUST", "必须")),
    )

    invalid_main = run_python(SPEC_OPS, "validate-main", specs)
    assert invalid_main.returncode != 0
    assert "missing_must_or_shall: 登录" in invalid_main.stderr
    assert "Traceback" not in invalid_main.stderr

    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
    write(
        delta / "accounts" / "spec.md",
        """## MODIFIED Requirements

### Requirement: 不存在的需求

系统 MUST 返回结果。

#### Scenario: 正常流程

- **WHEN** 用户执行操作
- **THEN** 系统返回结果
""",
    )
    invalid_delta = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert invalid_delta.returncode != 0
    assert "modified_source_missing: 不存在的需求" in invalid_delta.stderr
    assert "Traceback" not in invalid_delta.stderr


def test_spec_ops_cli_persists_complete_conflicts_and_resumes_in_a_new_process(
    tmp_path: Path,
) -> None:
    work = tmp_path / ".local" / "spec-work"
    conflicts_file = tmp_path / "conflicts.json"
    conflicts = [
        {
            "id": f"conflict-{index:02d}",
            "candidate": f"候选 {index}",
            "evidence": [f"spec.md:{index}"],
            "reason": "语义冲突",
            "recommendation": "采用建议",
        }
        for index in range(1, 14)
    ]
    write(conflicts_file, json.dumps(conflicts, ensure_ascii=False))

    initialized = run_python(
        SPEC_OPS,
        "state-init",
        work,
        "review",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert initialized.returncode == 0, initialized.stderr
    stored = run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        conflicts_file,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert stored.returncode == 0, stored.stderr
    assert json.loads(stored.stdout) == {"status": "WAITING_DECISION", "total": 13, "remaining": 13}

    first = json.loads(
        run_python(
            SPEC_OPS, "state-current", work, "specs-fingerprint", "input-fingerprint"
        ).stdout
    )
    assert first["index"] == 0
    assert first["total"] == 13
    assert first["conflict"] == conflicts[0]

    decided = run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-01",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert decided.returncode == 0, decided.stderr
    second = json.loads(
        run_python(
            SPEC_OPS, "state-current", work, "specs-fingerprint", "input-fingerprint"
        ).stdout
    )
    assert second["index"] == 1
    assert second["total"] == 13
    assert second["conflict"] == conflicts[1]
    assert json.loads(
        run_python(SPEC_OPS, "state-status", work, "specs-fingerprint", "input-fingerprint").stdout
    ) == {
        "status": "WAITING_DECISION",
        "total": 13,
        "decided": 1,
        "remaining": 12,
    }


def test_spec_ops_cli_rejects_incomplete_or_out_of_order_conflict_state(tmp_path: Path) -> None:
    work = tmp_path / ".local" / "spec-work"
    stale_delta = work / "current" / "delta" / "stale" / "spec.md"
    write(stale_delta, "stale")
    assert run_python(
        SPEC_OPS, "state-init", work, "audit", "specs-fingerprint", "input-fingerprint"
    ).returncode == 0
    assert not stale_delta.exists()

    count_only = tmp_path / "count-only.json"
    write(count_only, '{"count": 13}')
    incomplete = run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        count_only,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert incomplete.returncode != 0
    assert "conflicts_must_be_array" in incomplete.stderr

    duplicate_file = tmp_path / "duplicates.json"
    duplicate = {
        "id": "same",
        "candidate": "候选",
        "evidence": ["spec.md:1"],
        "reason": "冲突",
        "recommendation": "采用建议",
    }
    write(duplicate_file, json.dumps([duplicate, duplicate], ensure_ascii=False))
    duplicates = run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        duplicate_file,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert duplicates.returncode != 0
    assert "duplicate_conflict_id: same" in duplicates.stderr

    missing_evidence_file = tmp_path / "missing-evidence.json"
    write(
        missing_evidence_file,
        json.dumps([{**duplicate, "id": "missing", "evidence": []}], ensure_ascii=False),
    )
    missing = run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        missing_evidence_file,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert missing.returncode != 0
    assert "invalid_conflict_field: missing: evidence" in missing.stderr

    premature = run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "same",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert premature.returncode != 0
    assert "invalid_state: expected_WAITING_DECISION" in premature.stderr

    valid_file = tmp_path / "valid.json"
    write(valid_file, json.dumps([duplicate], ensure_ascii=False))
    assert run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        valid_file,
        "specs-fingerprint",
        "input-fingerprint",
    ).returncode == 0
    stale = run_python(
        SPEC_OPS, "state-current", work, "changed-specs", "input-fingerprint"
    )
    assert stale.returncode != 0
    assert "specs_fingerprint_changed" in stale.stderr

    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
    delta.mkdir()
    blocked = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert blocked.returncode != 0
    assert "invalid_state: expected_READY_TO_APPLY" in blocked.stderr

    state_path = work / "current" / "state.json"
    inconsistent = json.loads(state_path.read_text(encoding="utf-8"))
    inconsistent["status"] = "READY_TO_APPLY"
    state_path.write_text(json.dumps(inconsistent), encoding="utf-8")
    tampered = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert tampered.returncode != 0
    assert "invalid_state_document" in tampered.stderr


def test_spec_ops_cli_records_each_supported_conflict_decision(tmp_path: Path) -> None:
    work = tmp_path / ".local" / "spec-work"
    conflicts_file = tmp_path / "conflicts.json"
    conflicts = [
        {
            "id": f"conflict-{index}",
            "candidate": f"候选 {index}",
            "evidence": [f"spec.md:{index}"],
            "reason": "需要决定",
            "recommendation": "采用建议",
        }
        for index in range(4)
    ]
    write(conflicts_file, json.dumps(conflicts, ensure_ascii=False))
    assert run_python(
        SPEC_OPS, "state-init", work, "add", "specs-fingerprint", "input-fingerprint"
    ).returncode == 0
    assert run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        conflicts_file,
        "specs-fingerprint",
        "input-fingerprint",
    ).returncode == 0

    assert run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-0",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    ).returncode == 0
    repeated = run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-0",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert repeated.returncode != 0
    assert "unexpected_conflict_id: expected_conflict-1: conflict-0" in repeated.stderr
    assert run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-1",
        "ignore",
        "specs-fingerprint",
        "input-fingerprint",
    ).returncode == 0
    modified = run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-2",
        "accept-modified",
        "specs-fingerprint",
        "input-fingerprint",
        "--modified-content",
        "修改后的完整候选",
    )
    assert modified.returncode == 0, modified.stderr
    final = run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-3",
        "defer",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert final.returncode == 0, final.stderr
    assert json.loads(final.stdout) == {
        "status": "READY_TO_APPLY",
        "total": 4,
        "decided": 4,
        "remaining": 0,
    }
    state = json.loads((work / "current" / "state.json").read_text(encoding="utf-8"))
    assert [item["decision"] for item in state["decisions"]] == [
        "accept",
        "ignore",
        "accept-modified",
        "defer",
    ]
    assert state["decisions"][2]["modifiedContent"] == "修改后的完整候选"


def test_spec_ops_cli_initializes_a_new_capability_from_an_empty_spec_library(tmp_path: Path) -> None:
    specs = tmp_path / "missing-specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    write(
        delta / "notifications" / "spec.md",
        """# Notifications

## Purpose

描述通知的外部行为。

## ADDED Requirements

### Requirement: 接收通知

系统 MUST 向订阅用户发送通知。

#### Scenario: 新消息

- **WHEN** 新消息到达
- **THEN** 系统向订阅用户发送通知
""",
    )

    work = ready_state(SPEC_OPS, tmp_path / "state")
    validated = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert validated.returncode == 0, validated.stderr
    applied = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert applied.returncode == 0, applied.stderr
    assert run_python(SPEC_OPS, "validate-main", preview).returncode == 0
    assert "### Requirement: 接收通知" in (preview / "notifications" / "spec.md").read_text(encoding="utf-8")


def test_spec_ops_preview_auto_merges_identical_duplicate_requirements_but_main_validation_stays_strict(
    tmp_path: Path,
) -> None:
    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    duplicate = requirement("登录", "允许用户登录")
    write(specs / "accounts" / "spec.md", main_spec("Accounts", duplicate))
    write(specs / "sessions" / "spec.md", main_spec("Sessions", duplicate))
    delta.mkdir()

    strict = run_python(SPEC_OPS, "validate-main", specs)
    assert strict.returncode != 0
    assert "duplicate_requirement_global: 登录" in strict.stderr

    work = ready_state(SPEC_OPS, tmp_path / "state", "review")
    merged = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert merged.returncode == 0, merged.stderr
    assert run_python(SPEC_OPS, "validate-main", preview).returncode == 0
    assert (preview / "accounts" / "spec.md").read_text(encoding="utf-8").count(
        "### Requirement: 登录"
    ) == 1
    diff = run_python(SPEC_OPS, "diff", specs, preview)
    assert diff.returncode == 0
    assert "-### Requirement: 登录" in diff.stdout


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


@pytest.mark.skipif(
    "PLUGIN_SYNC_SKILL_ROOT" not in os.environ,
    reason="external plugin-sync source is verified only when explicitly supplied",
)
def test_plugin_sync_delegates_all_myspec_lifecycle_work_to_myspec_cli() -> None:
    root = Path(os.environ["PLUGIN_SYNC_SKILL_ROOT"])
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    references = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted((root / "references").glob("*.md"))
    }

    for command in (
        "myspec doctor --all",
        "myspec init --pi",
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


def test_plugin_uses_host_native_skill_paths_without_custom_pi_routing() -> None:
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
    assert package["pi"] == {"skills": [f"./skills/{name}" for name in SKILL_NAMES]}
    assert "peerDependencies" not in package
    assert "dependencies" not in package


def test_spec_add_deterministic_post_analysis_flow_previews_diffs_and_applies(
    tmp_path: Path,
) -> None:
    cli = SPEC_OPS
    specs = tmp_path / "add" / "specs"
    delta = tmp_path / "add" / "delta"
    preview = tmp_path / "add" / "preview"
    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许用户登录")))
    write(
        delta / "accounts" / "spec.md",
        """## ADDED Requirements

### Requirement: 注销

系统 MUST 允许用户注销。

#### Scenario: 主动注销

- **WHEN** 用户选择注销
- **THEN** 系统结束会话
""",
    )

    run_confirmed_workflow(cli, specs, delta, preview, "+### Requirement: 注销")
    assert "### Requirement: 注销" in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")


def test_spec_review_deterministic_duplicate_flow_previews_diffs_and_applies(
    tmp_path: Path,
) -> None:
    cli = SPEC_OPS
    specs = tmp_path / "review" / "specs"
    delta = tmp_path / "review" / "delta"
    preview = tmp_path / "review" / "preview"
    duplicate = requirement("登录", "允许用户登录")
    write(specs / "accounts" / "spec.md", main_spec("Accounts", duplicate, duplicate))
    delta.mkdir(parents=True)

    run_confirmed_workflow(cli, specs, delta, preview, "-### Requirement: 登录")
    assert (specs / "accounts" / "spec.md").read_text(encoding="utf-8").count(
        "### Requirement: 登录"
    ) == 1


def test_spec_audit_deterministic_post_analysis_flow_previews_diffs_and_applies(
    tmp_path: Path,
) -> None:
    cli = SPEC_OPS
    specs = tmp_path / "audit" / "missing-specs"
    delta = tmp_path / "audit" / "delta"
    preview = tmp_path / "audit" / "preview"
    write(
        delta / "notifications" / "spec.md",
        """# Notifications

## Purpose

描述通知的外部行为。

## ADDED Requirements

### Requirement: 接收通知

系统 MUST 向订阅用户发送通知。

#### Scenario: 新消息

- **WHEN** 新消息到达
- **THEN** 系统发送通知
""",
    )

    run_confirmed_workflow(cli, specs, delta, preview, "+### Requirement: 接收通知")
    assert (specs / "notifications" / "spec.md").is_file()


def test_my_spec_plugin_is_discoverable_by_pi_claude_and_codex() -> None:
    package_version = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    spec = (REPO_ROOT / "myspec" / "specs" / "my-spec" / "spec.md").read_text(encoding="utf-8")
    assert "/skill:my-spec-add" in spec
    assert "/my-spec:my-spec-add" in spec
    assert "$my-spec-add" in spec
    for host in (".claude-plugin", ".codex-plugin"):
        manifest = json.loads((PLUGIN_ROOT / host / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["name"] == "my-spec"
        assert manifest["version"] == package_version
        assert manifest["skills"] == "./skills"

    claude_marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    codex_marketplace = json.loads((REPO_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    assert any(plugin["name"] == "my-spec" for plugin in claude_marketplace["plugins"])
    assert any(plugin["name"] == "my-spec" for plugin in codex_marketplace["plugins"])


def test_apply_delta_can_atomically_replace_main_after_final_confirmation(tmp_path: Path) -> None:
    specs = tmp_path / "myspec" / "specs"
    delta = tmp_path / "delta"
    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
    write(
        delta / "accounts" / "spec.md",
        """## MODIFIED Requirements

### Requirement: 登录

系统 MUST 允许密码登录。

#### Scenario: 密码正确

- **WHEN** 用户提交正确密码
- **THEN** 系统创建会话
""",
    )

    work = ready_state(SPEC_OPS, tmp_path / "state")
    applied = apply_ready(SPEC_OPS, specs, delta, specs, work)
    assert applied.returncode == 0, applied.stderr
    assert "系统 MUST 允许密码登录。" in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")
    assert not any(path.name.startswith(".my-spec-") for path in specs.parent.iterdir())
    assert not work.exists()
    assert run_python(SPEC_OPS, "validate-main", specs).returncode == 0

    before = (specs / "accounts" / "spec.md").read_bytes()
    repeated_validation = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert repeated_validation.returncode == 0, repeated_validation.stderr
    repeated_work = ready_state(SPEC_OPS, tmp_path / "repeated-state")
    repeated = apply_ready(SPEC_OPS, specs, delta, specs, repeated_work)
    assert repeated.returncode == 0, repeated.stderr
    assert (specs / "accounts" / "spec.md").read_bytes() == before
