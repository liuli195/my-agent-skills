from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import TextIO
from urllib.parse import urlsplit


PACKAGE_NAME = "@liuli195/myspec"
CLAUDE_MARKETPLACE = "myspec"
CLAUDE_PLUGIN = f"my-spec@{CLAUDE_MARKETPLACE}"
CLAUDE_LEGACY_PLUGIN = "my-spec@my-agent-skills-marketplace"
CODEX_MARKETPLACE = "myspec"
CODEX_PLUGIN = f"my-spec@{CODEX_MARKETPLACE}"
CODEX_LEGACY_PLUGIN = "my-spec@my-agent-skills-marketplace"
SKILL_NAMES = ("my-spec", "my-spec-add", "my-spec-review", "my-spec-audit")
SKILL_PATHS = tuple(f"./skills/{name}" for name in SKILL_NAMES)


class ManagementError(ValueError):
    pass


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeError) as exc:
        raise ManagementError(f"cannot_read: {path}: {exc}") from exc


def _read_json(path: Path) -> object:
    try:
        return json.loads(_text(path))
    except json.JSONDecodeError as exc:
        raise ManagementError(f"invalid_json: {path}: {exc.msg}") from exc


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _command(command: str, *arguments: str) -> list[str] | str:
    executable = shutil.which(command)
    if executable is None:
        raise ManagementError(f"missing_command: {command}")
    values = [executable, *arguments]
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        return subprocess.list2cmdline(values)
    return values


def _run(command: str, *arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    invocation = _command(command, *arguments)
    return subprocess.run(
        invocation,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        shell=isinstance(invocation, str),
    )


def _npm_path(argument: str, error_name: str) -> Path:
    result = _run("npm", argument, "--global")
    if result.returncode != 0:
        raise ManagementError(f"{error_name}: {result.stderr.strip()}")
    return Path(result.stdout.strip())


def _stable_package_root() -> Path:
    return _npm_path("root", "npm_root_failed") / "@liuli195" / "myspec"


def _npm_prefix() -> Path:
    return _npm_path("prefix", "npm_prefix_failed")


def _package_version() -> str:
    package = _read_json(Path(__file__).parent.parent / "package.json")
    if not isinstance(package, dict) or not isinstance(package.get("version"), str):
        raise ManagementError("invalid_package_version")
    return package["version"]


def _pi_agent_dir() -> Path:
    configured = os.environ.get("PI_CODING_AGENT_DIR")
    return Path(configured) if configured else Path.home() / ".pi" / "agent"


def _pi_settings_paths(listed: list[dict[str, str]]) -> tuple[tuple[str, Path], ...]:
    paths = [("user", _pi_agent_dir() / "settings.json")]
    if any(record["scope"] == "project" for record in listed):
        paths.append(("project", Path.cwd() / ".pi" / "settings.json"))
    return tuple(paths)


def _read_settings(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    value = _read_json(path)
    if not isinstance(value, dict):
        raise ManagementError(f"invalid_pi_settings: {path}")
    return value


def _package_source(item: object) -> str | None:
    if isinstance(item, str):
        return item
    if isinstance(item, dict) and isinstance(item.get("source"), str):
        return item["source"]
    return None


def _local_source_path(source: str, settings_path: Path) -> Path | None:
    if source.lower().startswith(("npm:", "git:", "http://", "https://", "ssh://", "git://")):
        return None
    path = Path(source).expanduser()
    if not path.is_absolute():
        path = settings_path.parent / path
    return Path(os.path.abspath(path))


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


@dataclass
class PiSource:
    scope: str
    settings_path: Path
    settings: dict[str, object]
    index: int
    item: object
    source: str
    local_path: Path | None
    installed_path: Path | None

    @property
    def autoload_delta(self) -> bool:
        return isinstance(self.item, dict) and self.item.get("autoload") is False

    @property
    def skill_filter(self) -> list[str] | None:
        if not isinstance(self.item, dict) or "skills" not in self.item:
            return None
        value = self.item["skills"]
        if not isinstance(value, list) or not all(isinstance(entry, str) for entry in value):
            raise ManagementError(f"invalid_pi_skills_filter: {self.settings_path}")
        return value


def _pi_sources(listed: list[dict[str, str]]) -> list[PiSource]:
    result: list[PiSource] = []
    for scope, path in _pi_settings_paths(listed):
        settings = _read_settings(path)
        packages = settings.get("packages", [])
        if not isinstance(packages, list):
            raise ManagementError(f"invalid_pi_packages: {path}")
        for index, item in enumerate(packages):
            source = _package_source(item)
            if source is None:
                continue
            local_path = _local_source_path(source, path)
            installed_path = next(
                (
                    Path(record["path"])
                    for record in listed
                    if record["scope"] == scope
                    and record["source"] == source
                    and "path" in record
                    and (local_path is None or _same_path(Path(record["path"]), local_path))
                ),
                None,
            )
            result.append(PiSource(scope, path, settings, index, item, source, local_path, installed_path))
    return result


def _git_host_path(source: str) -> tuple[str, str] | None:
    trimmed = source.strip()
    has_git_prefix = trimmed.startswith("git:")
    value = trimmed[4:].strip() if has_git_prefix else trimmed
    if not has_git_prefix and re.match(r"^(?:https?|ssh|git)://", value, re.IGNORECASE) is None:
        return None

    scp = re.fullmatch(r"git@([^:]+):(.+)", value)
    if scp is not None:
        host, path = scp.groups()
    elif "://" in value:
        try:
            parsed = urlsplit(value)
        except ValueError:
            return None
        host, path = parsed.hostname or "", parsed.path.lstrip("/")
    else:
        aliases = {
            "github": "github.com",
            "gitlab": "gitlab.com",
            "bitbucket": "bitbucket.org",
        }
        alias = re.fullmatch(r"([^:]+):(.+)", value)
        if alias is not None and alias.group(1).lower() in aliases:
            host, path = aliases[alias.group(1).lower()], alias.group(2)
        else:
            host, separator, path = value.partition("/")
            if not separator or ("." not in host and host != "localhost"):
                return None

    path = path.split("@", 1)[0].lstrip("/").removesuffix(".git")
    if not host or len(path.split("/")) < 2 or "\\" in host or "\\" in path:
        return None
    if host.startswith("/") or path.startswith("/") or ".." in path.split("/"):
        return None
    return host.lower(), path


def _source_identity(item: PiSource) -> str:
    normalized = item.source.replace("\\", "/").rstrip("/")
    lowered = normalized.lower()
    if item.local_path is not None:
        return "local:" + os.path.normcase(os.path.abspath(item.local_path))
    if lowered.startswith("npm:"):
        spec = normalized[4:]
        match = re.fullmatch(r"(@?[^@]+(?:/[^@]+)?)(?:@.+)?", spec)
        return "npm:" + (match.group(1) if match else spec).lower()
    git_source = _git_host_path(item.source)
    return f"git:{git_source[0]}/{git_source[1]}" if git_source else "source:" + normalized


def _effective_sources(sources: list[PiSource]) -> list[PiSource]:
    ordered = [item for item in sources if item.scope == "project"] + [item for item in sources if item.scope == "user"]
    result: list[PiSource] = []
    positions: dict[str, int] = {}
    for item in ordered:
        identity = _source_identity(item)
        index = positions.get(identity)
        if index is None:
            positions[identity] = len(result)
            result.append(item)
        elif result[index].scope == "project" and item.scope == "user":
            if result[index].autoload_delta:
                result.append(item)
        elif item.scope == "project":
            result[index] = item
    return result


def _myspec_source_kind(item: PiSource, stable: Path) -> str | None:
    if item.local_path is not None and _same_path(item.local_path, stable):
        return "stable"
    normalized = item.source.replace("\\", "/").lower().rstrip("/")
    if re.fullmatch(r"npm:(?:@liuli195/myspec|pi-my-spec)(?:@[^/]+)?", normalized):
        return "legacy"
    local = item.local_path.as_posix().lower().rstrip("/") if item.local_path else ""
    if local.endswith("/plugins/my-spec") or local.endswith("/pi-my-spec"):
        return "legacy"
    if re.search(r"(?:^|[/:])pi-my-spec(?:\.git)?(?:@[^/]+|#[^/]+)?$", normalized):
        return "legacy"
    return None


def _set_disabled(item: PiSource, disabled: bool) -> None:
    packages = item.settings["packages"]
    assert isinstance(packages, list)
    current = packages[item.index]
    if isinstance(current, str):
        if disabled:
            packages[item.index] = {"source": current, "skills": []}
        return
    if disabled:
        current["skills"] = []
    else:
        current.pop("skills", None)
        current.pop("autoload", None)


def _configure_pi_sources(stable: Path) -> list[str]:
    listed = _pi_list()
    sources = _pi_sources(listed)
    user_stable = [item for item in sources if item.scope == "user" and _myspec_source_kind(item, stable) == "stable"]
    if not user_stable:
        installed = _run("pi", "install", str(stable))
        if installed.returncode != 0:
            raise ManagementError(f"pi_install_failed: {installed.stderr.strip()}")
        listed = _pi_list()
        sources = _pi_sources(listed)
        user_stable = [item for item in sources if item.scope == "user" and _myspec_source_kind(item, stable) == "stable"]
    if not user_stable:
        raise ManagementError("pi_install_missing_source")

    disabled: list[str] = []
    touched: dict[Path, dict[str, object]] = {}
    for index, item in enumerate(user_stable):
        _set_disabled(item, index > 0)
        touched[item.settings_path] = item.settings
    for item in sources:
        if _myspec_source_kind(item, stable) == "legacy":
            disabled.append(item.source)
            _set_disabled(item, True)
            touched[item.settings_path] = item.settings
    for path, settings in touched.items():
        _atomic_json(path, settings)
    listed = _pi_list()
    if not any(item.installed_path is not None for item in _pi_sources(listed) if item.scope == "user" and _myspec_source_kind(item, stable) == "stable"):
        raise ManagementError("pi_install_missing_source")
    return disabled


def _init_pi() -> dict[str, object]:
    if shutil.which("pi") is None:
        raise ManagementError("missing_command: pi")
    stable = _stable_package_root()
    return {
        "pi": "initialized",
        "source": str(stable),
        "disabledLegacySources": _configure_pi_sources(stable),
        "reloadRequired": True,
    }


def _claude_json(arguments: tuple[str, ...], error_name: str) -> list[dict[str, object]]:
    result = _run("claude", *arguments)
    if result.returncode != 0:
        raise ManagementError(f"{error_name}: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ManagementError(f"{error_name}: invalid_json") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ManagementError(f"{error_name}: invalid_output")
    return value


def _claude_marketplaces() -> list[dict[str, object]]:
    return _claude_json(("plugin", "marketplace", "list", "--json"), "claude_marketplace_list_failed")


def _claude_plugins() -> list[dict[str, object]]:
    return _claude_json(("plugin", "list", "--json"), "claude_plugin_list_failed")


def _claude_marketplace_path(item: dict[str, object]) -> Path | None:
    source = item.get("source")
    candidates = [item.get("path")]
    if isinstance(source, dict):
        candidates.append(source.get("path"))
    return next((Path(value) for value in candidates if isinstance(value, str) and value), None)


def _named_claude_marketplace(
    marketplaces: list[dict[str, object]],
) -> dict[str, object] | None:
    matches = [item for item in marketplaces if item.get("name") == CLAUDE_MARKETPLACE]
    if not matches:
        return None
    if len(matches) != 1:
        raise ManagementError("claude_marketplace_duplicate")
    return matches[0]


def _claude_marketplace(
    stable: Path,
    marketplaces: list[dict[str, object]],
) -> dict[str, object] | None:
    marketplace = _named_claude_marketplace(marketplaces)
    if marketplace is None:
        return None
    source = _claude_marketplace_path(marketplace)
    if source is None or not _same_path(source, stable):
        raise ManagementError("claude_marketplace_source_mismatch")
    return marketplace


def _run_claude(error_name: str, *arguments: str) -> None:
    result = _run("claude", *arguments)
    if result.returncode != 0:
        raise ManagementError(f"{error_name}: {result.stderr.strip()}")


def _init_claude() -> dict[str, object]:
    if shutil.which("claude") is None:
        raise ManagementError("missing_command: claude")
    stable = _stable_package_root()
    if _claude_marketplace(stable, _claude_marketplaces()) is None:
        _run_claude("claude_marketplace_add_failed", "plugin", "marketplace", "add", str(stable))
        if _claude_marketplace(stable, _claude_marketplaces()) is None:
            raise ManagementError("claude_marketplace_add_missing")

    plugins = _claude_plugins()
    target = next((item for item in plugins if item.get("id") == CLAUDE_PLUGIN), None)
    if target is None:
        _run_claude("claude_plugin_install_failed", "plugin", "install", CLAUDE_PLUGIN, "--scope", "user")
    else:
        scope = target.get("scope") if isinstance(target.get("scope"), str) else "user"
        _run_claude(
            "claude_marketplace_update_failed",
            "plugin",
            "marketplace",
            "update",
            CLAUDE_MARKETPLACE,
        )
        _run_claude("claude_plugin_update_failed", "plugin", "update", CLAUDE_PLUGIN, "--scope", scope)
    _run_claude(
        "claude_plugin_enable_failed",
        "plugin",
        "enable",
        CLAUDE_PLUGIN,
        "--scope",
        "user",
    )
    enabled = _claude_plugins()
    if not any(item.get("id") == CLAUDE_PLUGIN and item.get("enabled") is True for item in enabled):
        raise ManagementError("claude_plugin_enable_missing")

    disabled: list[str] = []
    for item in enabled:
        if item.get("id") == CLAUDE_LEGACY_PLUGIN and item.get("enabled") is True:
            scope = item.get("scope") if isinstance(item.get("scope"), str) else "user"
            _run_claude(
                "claude_plugin_disable_failed",
                "plugin",
                "disable",
                CLAUDE_LEGACY_PLUGIN,
                "--scope",
                scope,
            )
            disabled.append(CLAUDE_LEGACY_PLUGIN)
    return {
        "claude": "initialized",
        "marketplace": CLAUDE_MARKETPLACE,
        "source": str(stable),
        "disabledLegacyPlugins": disabled,
        "reloadRequired": True,
    }


def _codex_json(arguments: tuple[str, ...], key: str, error_name: str) -> list[dict[str, object]]:
    result = _run("codex", *arguments)
    if result.returncode != 0:
        raise ManagementError(f"{error_name}: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ManagementError(f"{error_name}: invalid_json") from exc
    items = value.get(key) if isinstance(value, dict) else None
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise ManagementError(f"{error_name}: invalid_output")
    return items


def _codex_marketplaces() -> list[dict[str, object]]:
    return _codex_json(("plugin", "marketplace", "list", "--json"), "marketplaces", "codex_marketplace_list_failed")


def _codex_plugins() -> list[dict[str, object]]:
    result = _run("codex", "plugin", "list", "--json")
    if result.returncode != 0:
        raise ManagementError(f"codex_plugin_list_failed: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ManagementError("codex_plugin_list_failed: invalid_json") from exc
    installed = value.get("installed") if isinstance(value, dict) else None
    available = value.get("available") if isinstance(value, dict) else None
    if (
        not isinstance(installed, list)
        or not all(isinstance(item, dict) for item in installed)
        or not isinstance(available, list)
        or not all(isinstance(item, dict) for item in available)
    ):
        raise ManagementError("codex_plugin_list_failed: invalid_output")
    return installed


def _named_codex_marketplace(marketplaces: list[dict[str, object]]) -> dict[str, object] | None:
    matches = [item for item in marketplaces if item.get("name") == CODEX_MARKETPLACE]
    if not matches:
        return None
    if len(matches) != 1:
        raise ManagementError("codex_marketplace_duplicate")
    return matches[0]


def _codex_marketplace(stable: Path, marketplaces: list[dict[str, object]]) -> dict[str, object] | None:
    marketplace = _named_codex_marketplace(marketplaces)
    if marketplace is None:
        return None
    root = marketplace.get("root")
    if not isinstance(root, str) or not _same_path(Path(root), stable):
        raise ManagementError("codex_marketplace_source_mismatch")
    return marketplace


def _run_codex(error_name: str, *arguments: str) -> None:
    result = _run("codex", *arguments)
    if result.returncode != 0:
        raise ManagementError(f"{error_name}: {result.stderr.strip()}")


def _codex_config_path() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"


def _set_codex_plugin_enabled(identifier: str, enabled: bool) -> None:
    path = _codex_config_path()
    text = _text(path) if path.exists() else ""
    header = rf'^\[plugins\."{re.escape(identifier)}"\][ \t]*\n'
    match = re.search(header, text, re.MULTILINE)
    value = "true" if enabled else "false"
    if match is None:
        addition = f'[plugins."{identifier}"]\nenabled = {value}\n'
        updated = text.rstrip() + ("\n\n" if text.strip() else "") + addition
    else:
        end_match = re.search(r"^\[", text[match.end():], re.MULTILINE)
        end = match.end() + end_match.start() if end_match is not None else len(text)
        body = text[match.end():end]
        if re.search(r"^enabled\s*=", body, re.MULTILINE):
            body = re.sub(r"^enabled\s*=.*$", f"enabled = {value}", body, count=1, flags=re.MULTILINE)
        else:
            body = f"enabled = {value}\n" + body
        updated = text[:match.end()] + body + text[end:]
    _atomic_text(path, updated)


def _refresh_codex_plugin() -> None:
    plugins = _codex_plugins()
    if any(item.get("pluginId") == CODEX_PLUGIN and item.get("installed") is True for item in plugins):
        _run_codex("codex_plugin_remove_failed", "plugin", "remove", CODEX_PLUGIN, "--json")
    _run_codex("codex_plugin_add_failed", "plugin", "add", CODEX_PLUGIN, "--json")


def _init_codex() -> dict[str, object]:
    if shutil.which("codex") is None:
        raise ManagementError("missing_command: codex")
    stable = _stable_package_root()
    marketplaces = _codex_marketplaces()
    marketplace = _named_codex_marketplace(marketplaces)
    root = marketplace.get("root") if marketplace is not None else None
    linked = not _same_path(stable, Path(os.path.realpath(stable)))
    if linked and (not isinstance(root, str) or not _same_path(Path(root), stable)):
        raise ManagementError(
            "codex_dev_marketplace_unregistered: run 'myspec init --release', "
            "then 'myspec init --codex', then 'myspec init --dev'"
        )
    if _codex_marketplace(stable, marketplaces) is None:
        _run_codex("codex_marketplace_add_failed", "plugin", "marketplace", "add", str(stable), "--json")
        if _codex_marketplace(stable, _codex_marketplaces()) is None:
            raise ManagementError("codex_marketplace_add_missing")
    _refresh_codex_plugin()
    plugins = _codex_plugins()
    target = next((item for item in plugins if item.get("pluginId") == CODEX_PLUGIN), None)
    if target is None or target.get("installed") is not True or target.get("enabled") is not True:
        raise ManagementError("codex_plugin_enable_missing")
    disabled: list[str] = []
    legacy = next((item for item in plugins if item.get("pluginId") == CODEX_LEGACY_PLUGIN), None)
    if legacy is not None and legacy.get("enabled") is True:
        _set_codex_plugin_enabled(CODEX_LEGACY_PLUGIN, False)
        disabled.append(CODEX_LEGACY_PLUGIN)
    return {
        "codex": "initialized",
        "marketplace": CODEX_MARKETPLACE,
        "source": str(stable),
        "disabledLegacyPlugins": disabled,
        "newSessionRequired": True,
    }


def _init_all() -> dict[str, object]:
    result: dict[str, object] = {}
    initializers = {"pi": _init_pi, "claude": _init_claude, "codex": _init_codex}
    for agent in ("pi", "claude", "codex"):
        if shutil.which(agent) is None:
            result[agent] = {"status": "skipped", "reason": f"missing_command: {agent}"}
        else:
            initialized = initializers[agent]()
            result[agent] = {"status": "initialized", "source": initialized["source"]}
            if initialized.get("newSessionRequired") is True:
                result[agent]["newSessionRequired"] = True
    return result


def _mode_state_path() -> Path:
    return Path.home() / ".myspec" / "state.json"


def _install_lock_path() -> Path:
    return Path.home() / ".myspec" / "install.lock"


_INSTALL_LOCK_HANDLES: dict[str, TextIO] = {}


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            return ctypes.windll.kernel32.GetLastError() != 87
        try:
            exit_code = ctypes.c_ulong()
            return bool(ctypes.windll.kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code))) and exit_code.value == 259
        finally:
            ctypes.windll.kernel32.CloseHandle(process)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _lock_file(handle: TextIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_file(handle: TextIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _locked_value(handle: TextIO) -> dict[str, object]:
    handle.seek(0)
    text = handle.read().strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManagementError(f"invalid_install_lock: {_install_lock_path()}") from exc
    if not isinstance(value, dict):
        raise ManagementError(f"invalid_install_lock: {_install_lock_path()}")
    return value


def _write_lock(handle: TextIO, value: dict[str, object]) -> None:
    handle.seek(0)
    handle.truncate()
    json.dump(value, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
    handle.flush()


def _open_locked() -> TextIO:
    path = _install_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    if path.stat().st_size == 0:
        handle.write(" ")
        handle.flush()
    try:
        _lock_file(handle)
    except OSError:
        handle.close()
        raise ManagementError("install_lock_busy")
    return handle


def _lock_value() -> dict[str, object]:
    path = _install_lock_path()
    value = _read_json(path)
    if not isinstance(value, dict) or not isinstance(value.get("pid"), int):
        raise ManagementError(f"invalid_install_lock: {path}")
    return value


def _acquire_install_lock(command: str) -> str:
    try:
        handle = _open_locked()
    except ManagementError as exc:
        if str(exc) != "install_lock_busy":
            raise
        current = _lock_value()
        raise ManagementError(
            f"install_locked: pid={current.get('pid')} startedAt={current.get('startedAt')} command={current.get('command')}"
        ) from exc
    current = _locked_value(handle)
    pid = current.get("pid")
    if current and current.get("released") is not True and isinstance(pid, int) and _pid_alive(pid):
        _unlock_file(handle)
        handle.close()
        raise ManagementError(
            f"install_locked: pid={pid} startedAt={current.get('startedAt')} command={current.get('command')}"
        )
    operation_id = uuid.uuid4().hex
    _write_lock(
        handle,
        {
            "pid": os.getpid(),
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "operationId": operation_id,
        },
    )
    _INSTALL_LOCK_HANDLES[operation_id] = handle
    return operation_id


def _release_install_lock(operation_id: str) -> None:
    handle = _INSTALL_LOCK_HANDLES.pop(operation_id, None)
    if handle is None:
        return
    value = _locked_value(handle)
    if value.get("operationId") == operation_id and value.get("pid") == os.getpid():
        value["released"] = True
        _write_lock(handle, value)
    _unlock_file(handle)
    handle.close()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _prepare_lock_handoff(operation_id: str, token: str) -> None:
    handle = _INSTALL_LOCK_HANDLES.pop(operation_id, None)
    if handle is None:
        raise ManagementError("invalid_install_lock_owner")
    value = _locked_value(handle)
    if value.get("operationId") != operation_id or value.get("pid") != os.getpid():
        raise ManagementError("invalid_install_lock_owner")
    value["handoffTokenHash"] = _token_hash(token)
    _write_lock(handle, value)
    _unlock_file(handle)
    handle.close()


def _claim_install_lock(token: str) -> str:
    try:
        handle = _open_locked()
    except ManagementError as exc:
        raise ManagementError("invalid_install_lock_handoff") from exc
    value = _locked_value(handle)
    if value.get("handoffTokenHash") != _token_hash(token):
        _unlock_file(handle)
        handle.close()
        raise ManagementError("invalid_install_lock_handoff")
    operation_id = value.get("operationId")
    if not isinstance(operation_id, str):
        _unlock_file(handle)
        handle.close()
        raise ManagementError("invalid_install_lock_handoff")
    value["pid"] = os.getpid()
    value.pop("handoffTokenHash", None)
    _write_lock(handle, value)
    _INSTALL_LOCK_HANDLES[operation_id] = handle
    return operation_id


def _lock_report() -> dict[str, object] | None:
    path = _install_lock_path()
    if not path.exists():
        return None
    value = _lock_value()
    if value.get("released") is True:
        return None
    pid = value["pid"]
    assert isinstance(pid, int)
    return {
        "pid": pid,
        "startedAt": value.get("startedAt"),
        "command": value.get("command"),
        "active": _pid_alive(pid),
    }


def _mode_state() -> dict[str, object]:
    path = _mode_state_path()
    if not path.exists():
        return {"mode": "release"}
    value = _read_json(path)
    if not isinstance(value, dict) or value.get("mode") not in {"dev", "release"}:
        raise ManagementError(f"invalid_mode_state: {path}")
    return value


def _marketplace_has_myspec(path: Path, *, agents: bool) -> bool:
    value = _read_json(path)
    if not isinstance(value, dict) or not isinstance(value.get("name"), str) or not isinstance(value.get("plugins"), list):
        return False
    matches = [plugin for plugin in value["plugins"] if isinstance(plugin, dict) and plugin.get("name") == "my-spec"]
    if len(matches) != 1:
        return False
    plugin_source = matches[0].get("source")
    expected: object = {"source": "local", "path": "./plugins/my-spec"} if agents else "./plugins/my-spec"
    return plugin_source == expected


def _validate_self_claude_marketplace(path: Path) -> bool:
    value = _read_json(path)
    plugins = value.get("plugins") if isinstance(value, dict) else None
    return (
        isinstance(value, dict)
        and value.get("name") == CLAUDE_MARKETPLACE
        and isinstance(plugins, list)
        and len(plugins) == 1
        and isinstance(plugins[0], dict)
        and plugins[0].get("name") == "my-spec"
        and plugins[0].get("source") == "./"
    )


def _validate_self_codex_marketplace(path: Path) -> bool:
    value = _read_json(path)
    plugins = value.get("plugins") if isinstance(value, dict) else None
    return (
        isinstance(value, dict)
        and value.get("name") == CODEX_MARKETPLACE
        and isinstance(plugins, list)
        and len(plugins) == 1
        and isinstance(plugins[0], dict)
        and plugins[0].get("name") == "my-spec"
        and plugins[0].get("source") == {"source": "local", "path": "./"}
    )


def _validate_plugin_manifest(path: Path, version: str) -> bool:
    value = _read_json(path)
    return (
        isinstance(value, dict)
        and value.get("name") == "my-spec"
        and value.get("version") == version
        and value.get("skills") == "./skills"
    )


def _validate_dev_source(raw_source: Path) -> tuple[Path, Path, str]:
    source = raw_source.resolve()
    package_root = source / "plugins" / "my-spec"
    package_path = package_root / "package.json"
    agents_market = source / ".agents" / "plugins" / "marketplace.json"
    claude_market = source / ".claude-plugin" / "marketplace.json"
    required = (
        package_path,
        package_root / "bin" / "myspec.js",
        package_root / "python" / "spec_ops.py",
        package_root / "python" / "management.py",
        agents_market,
        claude_market,
        package_root / ".agents" / "plugins" / "marketplace.json",
        package_root / ".claude-plugin" / "marketplace.json",
        package_root / ".claude-plugin" / "plugin.json",
        package_root / ".codex-plugin" / "plugin.json",
    )
    missing = next((path for path in required if not path.is_file()), None)
    if missing is not None:
        raise ManagementError(f"invalid_dev_source: missing {missing}")
    package = _read_json(package_path)
    version = package.get("version") if isinstance(package, dict) else None
    if (
        not isinstance(package, dict)
        or package.get("name") != PACKAGE_NAME
        or not isinstance(version, str)
        or not version
        or package.get("bin") != {"myspec": "./bin/myspec.js"}
        or not isinstance(package.get("pi"), dict)
        or package["pi"].get("skills") != list(SKILL_PATHS)
    ):
        raise ManagementError(f"invalid_dev_source: package_manifest {package_root}")
    missing_skill = next((package_root / path[2:] / "SKILL.md" for path in SKILL_PATHS if not (package_root / path[2:] / "SKILL.md").is_file()), None)
    if missing_skill is not None:
        raise ManagementError(f"invalid_dev_source: missing {missing_skill}")
    if not _marketplace_has_myspec(agents_market, agents=True):
        raise ManagementError(f"invalid_dev_source: marketplace {agents_market}")
    if not _marketplace_has_myspec(claude_market, agents=False):
        raise ManagementError(f"invalid_dev_source: marketplace {claude_market}")
    self_claude_market = package_root / ".claude-plugin" / "marketplace.json"
    if not _validate_self_claude_marketplace(self_claude_market):
        raise ManagementError(f"invalid_dev_source: marketplace {self_claude_market}")
    self_codex_market = package_root / ".agents" / "plugins" / "marketplace.json"
    if not _validate_self_codex_marketplace(self_codex_market):
        raise ManagementError(f"invalid_dev_source: marketplace {self_codex_market}")
    for path in (
        package_root / ".claude-plugin" / "plugin.json",
        package_root / ".codex-plugin" / "plugin.json",
    ):
        if not _validate_plugin_manifest(path, version):
            raise ManagementError(f"invalid_dev_source: plugin_manifest {path}")
    root = _run("git", "rev-parse", "--show-toplevel", cwd=source)
    if root.returncode != 0 or not _same_path(Path(root.stdout.strip()), source):
        raise ManagementError("invalid_dev_source: git_root")
    commit = _run("git", "rev-parse", "HEAD", cwd=source)
    if commit.returncode != 0:
        raise ManagementError(f"invalid_dev_source: git {commit.stderr.strip()}")
    return source, package_root, commit.stdout.strip()


def _exact_command(executable: Path, *arguments: str) -> list[str] | str:
    values = [str(executable), *arguments]
    if os.name == "nt" and executable.suffix.lower() in {".cmd", ".bat"}:
        return subprocess.list2cmdline(values)
    return values


def _stable_cli() -> Path:
    prefix = _npm_prefix()
    return prefix / "myspec.cmd" if os.name == "nt" else prefix / "bin" / "myspec"


def _resume_after_switch(arguments: list[str], token: str, operation_id: str) -> dict[str, object]:
    _prepare_lock_handoff(operation_id, token)
    invocation = _exact_command(_stable_cli(), *arguments, "--_switch-token", token)
    result = subprocess.run(
        invocation,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
        shell=isinstance(invocation, str),
    )
    if result.returncode != 0:
        raise ManagementError(f"mode_switch_resume_failed: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ManagementError("mode_switch_resume_invalid_output") from exc
    if not isinstance(value, dict):
        raise ManagementError("mode_switch_resume_invalid_output")
    return value


def _validated_pending(stage: str, token: str | None) -> dict[str, object]:
    state = _mode_state()
    pending = state.get("pendingSwitch")
    if token is None or not isinstance(pending, dict) or pending.get("stage") != stage or pending.get("token") != token:
        raise ManagementError("invalid_switch_token")
    return state


def _group_effective_myspec(
    stable: Path,
    sources: list[PiSource],
) -> list[tuple[str, str, list[PiSource]]]:
    groups: list[tuple[str, str, list[PiSource]]] = []
    by_identity: dict[str, int] = {}
    for item in _effective_sources(sources):
        kind = _myspec_source_kind(item, stable)
        if kind is None:
            continue
        identity = _source_identity(item)
        if identity not in by_identity:
            by_identity[identity] = len(groups)
            groups.append((identity, kind, [item]))
        else:
            groups[by_identity[identity]][2].append(item)
    return groups


def _matches(path: str, name: str, pattern: str) -> bool:
    normalized = pattern.replace("\\", "/").removeprefix("./")
    parent = str(PurePosixPath(path).parent)
    return any(
        fnmatch.fnmatchcase(candidate, normalized) or PurePosixPath(candidate).match(normalized)
        for candidate in (path, "SKILL.md", parent, name)
    )


def _exact_match(path: str, name: str, pattern: str) -> bool:
    normalized = pattern.replace("\\", "/").removeprefix("./")
    return normalized in {path, str(PurePosixPath(path).parent), name}


def _manifest_skills(root: Path) -> dict[str, str]:
    package = _read_json(root / "package.json")
    pi = package.get("pi") if isinstance(package, dict) else None
    entries = pi.get("skills") if isinstance(pi, dict) else None
    if not isinstance(entries, list) or not all(isinstance(entry, str) for entry in entries):
        return {}
    skills: dict[str, str] = {}
    for entry in entries:
        if entry.startswith(("!", "+", "-")):
            continue
        target = root / entry.removeprefix("./")
        candidates = [target] if target.is_file() else sorted(target.rglob("SKILL.md")) if target.is_dir() else []
        for candidate in candidates:
            if candidate.name == "SKILL.md":
                skills[candidate.relative_to(root).as_posix()] = candidate.parent.name
    overrides = [entry for entry in entries if entry.startswith(("!", "+", "-"))]
    return {path: name for path, name in skills.items() if _pattern_enabled(path, name, overrides)}


def _pattern_enabled(path: str, name: str, patterns: list[str]) -> bool:
    includes = [pattern for pattern in patterns if not pattern.startswith(("!", "+", "-"))]
    enabled = not includes or any(_matches(path, name, pattern) for pattern in includes)
    if any(_matches(path, name, pattern[1:]) for pattern in patterns if pattern.startswith("!")):
        enabled = False
    if any(_exact_match(path, name, pattern[1:]) for pattern in patterns if pattern.startswith("+")):
        enabled = True
    if any(_exact_match(path, name, pattern[1:]) for pattern in patterns if pattern.startswith("-")):
        enabled = False
    return enabled


def _group_skills(group: list[PiSource]) -> list[str]:
    states: dict[str, tuple[str, bool]] = {}
    order: list[str] = []
    for item in group:
        root = item.installed_path
        if root is None or not (root / "package.json").is_file():
            continue
        skills = _manifest_skills(root)
        order.extend(path for path in skills if path not in order)
        patterns = item.skill_filter
        if item.autoload_delta:
            updates: dict[str, tuple[str, bool]] = {}
            for pattern in patterns or []:
                marker = pattern[:1]
                target = pattern[1:] if marker in {"!", "+", "-"} else pattern
                enabled = marker not in {"!", "-"}
                exact = marker in {"+", "-"}
                for path, name in skills.items():
                    if (exact and _exact_match(path, name, target)) or (not exact and _matches(path, name, target)):
                        updates[path] = (name, enabled)
            for path, value in updates.items():
                states.setdefault(path, value)
            continue
        for path, name in skills.items():
            enabled = patterns is None or (bool(patterns) and _pattern_enabled(path, name, patterns))
            states.setdefault(path, (name, enabled))
    return [states[path][0] for path in order if path in states and states[path][1]]


def _pi_is_configured(listed: list[dict[str, str]]) -> bool:
    stable = _stable_package_root()
    installed = [item for item in _pi_sources(listed) if item.installed_path is not None]
    return any(
        kind == "stable" and _group_skills(group)
        for _, kind, group in _group_effective_myspec(stable, installed)
    )


def _refresh_pi() -> str:
    if shutil.which("pi") is None:
        return "not-installed"
    return "refreshed" if _pi_is_configured(_pi_list()) else "not-installed"


def _refresh_claude() -> str:
    if shutil.which("claude") is None:
        return "not-installed"
    stable = _stable_package_root()
    marketplace = _claude_marketplace(stable, _claude_marketplaces())
    plugins = _claude_plugins()
    target = next((item for item in plugins if item.get("id") == CLAUDE_PLUGIN), None)
    if marketplace is None or target is None or target.get("enabled") is not True:
        return "not-installed"
    scope = target.get("scope") if isinstance(target.get("scope"), str) else "user"
    _run_claude(
        "claude_marketplace_update_failed",
        "plugin",
        "marketplace",
        "update",
        CLAUDE_MARKETPLACE,
    )
    _run_claude(
        "claude_plugin_uninstall_failed",
        "plugin",
        "uninstall",
        CLAUDE_PLUGIN,
        "--scope",
        scope,
        "--keep-data",
    )
    _run_claude(
        "claude_plugin_install_failed",
        "plugin",
        "install",
        CLAUDE_PLUGIN,
        "--scope",
        scope,
    )
    _run_claude(
        "claude_plugin_enable_failed",
        "plugin",
        "enable",
        CLAUDE_PLUGIN,
        "--scope",
        scope,
    )
    refreshed = _claude_plugins()
    if not any(item.get("id") == CLAUDE_PLUGIN and item.get("enabled") is True for item in refreshed):
        raise ManagementError("claude_plugin_refresh_missing")
    return "refreshed"


def _refresh_codex() -> str:
    if shutil.which("codex") is None:
        return "not-installed"
    stable = _stable_package_root()
    marketplace = _codex_marketplace(stable, _codex_marketplaces())
    target = next((item for item in _codex_plugins() if item.get("pluginId") == CODEX_PLUGIN), None)
    if marketplace is None or target is None or target.get("installed") is not True or target.get("enabled") is not True:
        return "not-installed"
    _refresh_codex_plugin()
    refreshed = next((item for item in _codex_plugins() if item.get("pluginId") == CODEX_PLUGIN), None)
    if refreshed is None or refreshed.get("installed") is not True or refreshed.get("enabled") is not True:
        raise ManagementError("codex_plugin_refresh_missing")
    return "refreshed"


def _refresh_integrations() -> dict[str, object]:
    pi_status = _refresh_pi()
    result: dict[str, object] = {"pi": pi_status}
    reload_required = pi_status == "refreshed"
    if shutil.which("claude") is not None:
        claude_status = _refresh_claude()
        result["claude"] = claude_status
        reload_required = reload_required or claude_status == "refreshed"
    if shutil.which("codex") is not None:
        codex_status = _refresh_codex()
        result["codex"] = codex_status
        if codex_status == "refreshed":
            result["newSessionRequired"] = True
    result["reloadRequired"] = reload_required
    return result


def _switch_dev(raw_source: Path | None, token: str | None, operation_id: str) -> dict[str, object]:
    source, package_root, commit = _validate_dev_source(raw_source or Path.cwd())
    if token is not None:
        state = _validated_pending("dev", token)
        previous = state.get("previousReleaseVersion")
        if not isinstance(previous, str) or not previous:
            raise ManagementError("missing_previous_release_version")
        refreshed = _refresh_integrations()
        state.pop("pendingSwitch")
        _atomic_json(_mode_state_path(), state)
        return {
            "mode": "dev",
            "source": str(source),
            "previousReleaseVersion": previous,
            **refreshed,
        }
    state = _mode_state()
    previous = state.get("previousReleaseVersion") if state["mode"] == "dev" else _package_version()
    if not isinstance(previous, str) or not previous:
        raise ManagementError("missing_previous_release_version")
    switch_token = uuid.uuid4().hex
    _atomic_json(
        _mode_state_path(),
        {"mode": "dev", "source": str(source), "sourceCommit": commit, "previousReleaseVersion": previous, "pendingSwitch": {"stage": "dev", "token": switch_token}},
    )
    linked = _run("npm", "link", cwd=package_root)
    if linked.returncode != 0:
        raise ManagementError(f"npm_link_failed: {linked.stderr.strip()}")
    return _resume_after_switch(["init", "--dev", "--source", str(source)], switch_token, operation_id)


def _switch_release(token: str | None, operation_id: str) -> dict[str, object]:
    state = _mode_state()
    previous = state.get("previousReleaseVersion")
    if not isinstance(previous, str) or not previous:
        raise ManagementError("missing_previous_release_version")
    if token is not None:
        state = _validated_pending("release", token)
        refreshed = _refresh_integrations()
        _atomic_json(_mode_state_path(), {"mode": "release", "previousReleaseVersion": previous})
        return {"mode": "release", "version": previous, **refreshed}
    if state["mode"] != "dev":
        raise ManagementError("missing_previous_release_version")
    switch_token = uuid.uuid4().hex
    pending = {**state, "pendingSwitch": {"stage": "release", "token": switch_token}}
    _atomic_json(_mode_state_path(), pending)
    installed = _run("npm", "install", "--global", "--ignore-scripts", "--no-audit", "--no-fund", f"{PACKAGE_NAME}@{previous}")
    if installed.returncode != 0:
        raise ManagementError(f"npm_install_failed: {installed.stderr.strip()}")
    return _resume_after_switch(["init", "--release"], switch_token, operation_id)


def _pi_list() -> list[dict[str, str]]:
    listed = _run("pi", "list")
    if listed.returncode != 0:
        raise ManagementError(f"pi_list_failed: {listed.stderr.strip()}")
    result: list[dict[str, str]] = []
    scope: str | None = None
    pending: dict[str, str] | None = None
    for line in listed.stdout.splitlines():
        if line == "User packages:":
            scope, pending = "user", None
        elif line == "Project packages:":
            scope, pending = "project", None
        elif scope is not None and line.startswith("  ") and not line.startswith("    "):
            pending = {"scope": scope, "source": line.strip().removesuffix(" (filtered)")}
            result.append(pending)
        elif pending is not None and line.startswith("    "):
            pending["path"] = line.strip()
            pending = None
    return result


def _manifest_version(root: Path) -> str | None:
    path = root / "package.json"
    if not path.is_file():
        return None
    value = _read_json(path)
    return value.get("version") if isinstance(value, dict) and isinstance(value.get("version"), str) else None


def _doctor_package() -> dict[str, object]:
    stable = _stable_package_root()
    real = Path(os.path.realpath(stable))
    cli_version = _package_version()
    linked = not _same_path(stable, real)
    return {
        "cliVersion": cli_version,
        "mode": "dev" if linked else "release",
        "source": str(real if linked else stable),
        "npm": {
            "stablePath": str(stable),
            "realPath": str(real),
            "linked": linked,
            "packageVersion": _manifest_version(stable),
            "versionMismatch": _manifest_version(stable) != cli_version,
        },
    }


def _doctor_pi() -> dict[str, object]:
    stable = _stable_package_root()
    report = _doctor_package()
    available = shutil.which("pi") is not None
    listed = _pi_list() if available else []
    configured_sources = _pi_sources(listed)
    installed_sources = [item for item in configured_sources if item.installed_path is not None]
    effective = _effective_sources(installed_sources)
    records: list[dict[str, object]] = []
    for item in configured_sources:
        kind = _myspec_source_kind(item, stable)
        if kind is not None:
            installed = item in installed_sources
            is_effective = item in effective
            records.append({
                "scope": item.scope,
                "settings": str(item.settings_path),
                "source": item.source,
                "resolvedPath": str(item.installed_path) if item.installed_path is not None else None,
                "kind": kind,
                "installed": installed,
                "effective": installed and is_effective,
                "enabled": installed and is_effective and bool(_group_skills([item])),
            })
    groups = _group_effective_myspec(stable, installed_sources)
    enabled_groups = [(kind, group, _group_skills(group)) for _, kind, group in groups]
    stable_skills = next((skills for kind, _, skills in enabled_groups if kind == "stable"), [])
    enabled_sources = [group[0].source for _, group, skills in enabled_groups if skills]
    disabled_sources = [
        item.source
        for item in installed_sources
        if _myspec_source_kind(item, stable) is not None and not _group_skills([item])
    ]
    report["pi"] = {
        "available": available,
        "registered": bool(stable_skills),
        "enabledSources": enabled_sources,
        "disabledSources": disabled_sources,
        "duplicateEnabledSources": len(enabled_sources) > 1,
        "sources": records,
        "listedSources": listed,
        "skills": stable_skills,
        "reloadRequired": bool(enabled_sources),
    }
    return report


def _plugin_skills(root: Path | None) -> list[str]:
    if root is None or not root.is_dir():
        return []
    return [name for name in SKILL_NAMES if (root / "skills" / name / "SKILL.md").is_file()]


def _doctor_claude() -> dict[str, object]:
    report = _doctor_package()
    stable = _stable_package_root()
    available = shutil.which("claude") is not None
    marketplaces = _claude_marketplaces() if available else []
    plugins = _claude_plugins() if available else []
    marketplace = _named_claude_marketplace(marketplaces) if available else None
    marketplace_path = _claude_marketplace_path(marketplace) if marketplace is not None else None
    marketplace_registered = marketplace_path is not None and _same_path(marketplace_path, stable)
    relevant = [
        item
        for item in plugins
        if isinstance(item.get("id"), str) and str(item["id"]).startswith("my-spec@")
    ]
    target = next((item for item in relevant if item.get("id") == CLAUDE_PLUGIN), None)
    enabled_sources = [str(item["id"]) for item in relevant if item.get("enabled") is True]
    disabled_sources = [str(item["id"]) for item in relevant if item.get("enabled") is False]
    install_path = Path(target["installPath"]) if isinstance(target, dict) and isinstance(target.get("installPath"), str) else None
    report["claude"] = {
        "available": available,
        "marketplace": marketplace,
        "marketplaceRegistered": marketplace_registered,
        "marketplaceSourceMismatch": marketplace is not None and not marketplace_registered,
        "source": str(marketplace_path) if marketplace_path is not None else None,
        "version": target.get("version") if isinstance(target, dict) else None,
        "versionMismatch": not isinstance(target, dict) or target.get("version") != _package_version(),
        "enabled": isinstance(target, dict) and target.get("enabled") is True,
        "enabledSources": enabled_sources,
        "disabledSources": disabled_sources,
        "duplicateEnabledSources": len(enabled_sources) > 1,
        "plugins": relevant,
        "skills": _plugin_skills(install_path),
        "reloadRequired": bool(enabled_sources),
    }
    return report


def _doctor_codex() -> dict[str, object]:
    report = _doctor_package()
    stable = _stable_package_root()
    available = shutil.which("codex") is not None
    marketplaces = _codex_marketplaces() if available else []
    plugins = _codex_plugins() if available else []
    marketplace = _named_codex_marketplace(marketplaces) if available else None
    root = Path(marketplace["root"]) if isinstance(marketplace, dict) and isinstance(marketplace.get("root"), str) else None
    marketplace_registered = root is not None and _same_path(root, stable)
    relevant = [item for item in plugins if isinstance(item.get("pluginId"), str) and str(item["pluginId"]).startswith("my-spec@")]
    target = next((item for item in relevant if item.get("pluginId") == CODEX_PLUGIN), None)
    enabled_sources = [str(item["pluginId"]) for item in relevant if item.get("enabled") is True]
    disabled_sources = [str(item["pluginId"]) for item in relevant if item.get("enabled") is False]
    source = target.get("source") if isinstance(target, dict) else None
    install_path = Path(source["path"]) if isinstance(source, dict) and isinstance(source.get("path"), str) else None
    report["codex"] = {
        "available": available,
        "marketplace": marketplace,
        "marketplaceRegistered": marketplace_registered,
        "marketplaceSourceMismatch": marketplace is not None and not marketplace_registered,
        "source": str(root) if root is not None else None,
        "version": target.get("version") if isinstance(target, dict) else None,
        "versionMismatch": not isinstance(target, dict) or target.get("version") != _package_version(),
        "enabled": isinstance(target, dict) and target.get("enabled") is True,
        "enabledSources": enabled_sources,
        "disabledSources": disabled_sources,
        "duplicateEnabledSources": len(enabled_sources) > 1,
        "plugins": relevant,
        "skills": _plugin_skills(install_path),
        "newSessionRequired": bool(enabled_sources),
    }
    return report


def _latest_version() -> str:
    result = _run("npm", "view", PACKAGE_NAME, "version", "--json")
    if result.returncode != 0:
        raise ManagementError(f"npm_latest_failed: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ManagementError("npm_latest_failed: invalid_json") from exc
    if not isinstance(value, str) or not value.strip():
        raise ManagementError("npm_latest_failed: invalid_version")
    return value


def _preflight_integrations() -> tuple[list[str], dict[str, str]]:
    integrations: list[str] = []
    scopes: dict[str, str] = {}
    if shutil.which("pi") is not None and _pi_is_configured(_pi_list()):
        integrations.append("pi")
    if shutil.which("claude") is not None:
        stable = _stable_package_root()
        marketplace = _claude_marketplace(stable, _claude_marketplaces())
        target = next((item for item in _claude_plugins() if item.get("id") == CLAUDE_PLUGIN), None)
        if marketplace is not None and target is not None and target.get("enabled") is True:
            integrations.append("claude")
            scopes["claude"] = target.get("scope") if isinstance(target.get("scope"), str) else "user"
    if shutil.which("codex") is not None:
        stable = _stable_package_root()
        marketplace = _codex_marketplace(stable, _codex_marketplaces())
        target = next((item for item in _codex_plugins() if item.get("pluginId") == CODEX_PLUGIN), None)
        if marketplace is not None and target is not None and target.get("installed") is True and target.get("enabled") is True:
            integrations.append("codex")
    return integrations, scopes


def _update_pending(state: dict[str, object]) -> dict[str, object] | None:
    pending = state.get("pendingOperation")
    if pending is None:
        return None
    if not isinstance(pending, dict) or pending.get("command") != "update":
        raise ManagementError("another_operation_pending")
    if not isinstance(pending.get("targetVersion"), str):
        raise ManagementError("invalid_update_state")
    if not isinstance(pending.get("integrations"), list) or not all(
        item in {"pi", "claude", "codex"} for item in pending["integrations"]
    ):
        raise ManagementError("invalid_update_state")
    if not isinstance(pending.get("completed"), list) or not all(
        isinstance(item, str) for item in pending["completed"]
    ):
        raise ManagementError("invalid_update_state")
    return pending


def _save_update_step(state: dict[str, object], pending: dict[str, object], step: str) -> None:
    completed = pending["completed"]
    assert isinstance(completed, list)
    if step not in completed:
        completed.append(step)
    pending.pop("lastError", None)
    _atomic_json(_mode_state_path(), state)


def _update_claude_steps(
    state: dict[str, object], pending: dict[str, object], scope: str
) -> None:
    completed = pending["completed"]
    assert isinstance(completed, list)
    stable = _stable_package_root()
    if _claude_marketplace(stable, _claude_marketplaces()) is None:
        raise ManagementError("update_integration_unavailable: claude")
    if "claude-marketplace" not in completed:
        _run_claude("claude_marketplace_update_failed", "plugin", "marketplace", "update", CLAUDE_MARKETPLACE)
        _save_update_step(state, pending, "claude-marketplace")
    if "claude-uninstall" not in completed:
        target = next((item for item in _claude_plugins() if item.get("id") == CLAUDE_PLUGIN), None)
        if target is not None:
            _run_claude(
                "claude_plugin_uninstall_failed",
                "plugin",
                "uninstall",
                CLAUDE_PLUGIN,
                "--scope",
                scope,
                "--keep-data",
            )
        _save_update_step(state, pending, "claude-uninstall")
    if "claude-install" not in completed:
        _run_claude("claude_plugin_install_failed", "plugin", "install", CLAUDE_PLUGIN, "--scope", scope)
        _save_update_step(state, pending, "claude-install")
    if "claude-enable" not in completed:
        _run_claude("claude_plugin_enable_failed", "plugin", "enable", CLAUDE_PLUGIN, "--scope", scope)
        _save_update_step(state, pending, "claude-enable")
    if not any(item.get("id") == CLAUDE_PLUGIN and item.get("enabled") is True for item in _claude_plugins()):
        raise ManagementError("claude_plugin_refresh_missing")


def _update_codex_steps(state: dict[str, object], pending: dict[str, object]) -> None:
    completed = pending["completed"]
    assert isinstance(completed, list)
    stable = _stable_package_root()
    if _codex_marketplace(stable, _codex_marketplaces()) is None:
        raise ManagementError("update_integration_unavailable: codex")
    if "codex-remove" not in completed:
        target = next((item for item in _codex_plugins() if item.get("pluginId") == CODEX_PLUGIN), None)
        if target is not None and target.get("installed") is True:
            _run_codex("codex_plugin_remove_failed", "plugin", "remove", CODEX_PLUGIN, "--json")
        _save_update_step(state, pending, "codex-remove")
    if "codex-add" not in completed:
        _run_codex("codex_plugin_add_failed", "plugin", "add", CODEX_PLUGIN, "--json")
        _save_update_step(state, pending, "codex-add")
    refreshed = next((item for item in _codex_plugins() if item.get("pluginId") == CODEX_PLUGIN), None)
    if refreshed is None or refreshed.get("installed") is not True or refreshed.get("enabled") is not True:
        raise ManagementError("codex_plugin_refresh_missing")


def _save_update_error(state: dict[str, object], pending: dict[str, object], error: ManagementError) -> None:
    try:
        latest_state = _mode_state()
        latest_pending = _update_pending(latest_state)
        if latest_pending is not None:
            state, pending = latest_state, latest_pending
        pending["lastError"] = str(error)
        _atomic_json(_mode_state_path(), state)
    except (OSError, ManagementError):
        pass


def _resume_after_update(token: str, operation_id: str) -> dict[str, object]:
    _prepare_lock_handoff(operation_id, token)
    invocation = _exact_command(_stable_cli(), "update", "--_update-token", token)
    result = subprocess.run(
        invocation,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
        shell=isinstance(invocation, str),
    )
    if result.returncode != 0:
        message = result.stderr.strip()
        if message.startswith("error: "):
            message = message[7:]
        raise ManagementError(message or "update_resume_failed")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ManagementError("update_resume_invalid_output") from exc
    if not isinstance(value, dict):
        raise ManagementError("update_resume_invalid_output")
    return value


def _doctor_all() -> dict[str, object]:
    report = _doctor_package()
    report["pi"] = _doctor_pi()["pi"]
    report["claude"] = _doctor_claude()["claude"]
    report["codex"] = _doctor_codex()["codex"]
    return report


def _run_update(token: str | None, operation_id: str) -> dict[str, object]:
    state = _mode_state()
    if state.get("mode") == "dev" or _doctor_package()["mode"] == "dev":
        raise ManagementError("update_requires_release_mode: run 'myspec init --release' first")
    pending = _update_pending(state)
    if token is not None:
        if pending is None or pending.get("tokenHash") != _token_hash(token):
            raise ManagementError("invalid_update_token")
    elif pending is None:
        target = _latest_version()
        integrations, scopes = _preflight_integrations()
        pending = {
            "command": "update",
            "targetVersion": target,
            "integrations": integrations,
            "scopes": scopes,
            "completed": ["preflight"],
        }
        state["mode"] = "release"
        state["pendingOperation"] = pending
        _atomic_json(_mode_state_path(), state)

    assert pending is not None
    target = pending["targetVersion"]
    integrations = pending["integrations"]
    completed = pending["completed"]
    assert isinstance(target, str) and isinstance(integrations, list) and isinstance(completed, list)
    try:
        installed_now = False
        if "npm" not in completed:
            installed = _run(
                "npm",
                "install",
                "--global",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
                f"{PACKAGE_NAME}@{target}",
            )
            if installed.returncode != 0:
                raise ManagementError(f"npm_install_failed: {installed.stderr.strip()}")
            _save_update_step(state, pending, "npm")
            installed_now = True
        if token is None and (installed_now or _package_version() != target):
            resume_token = uuid.uuid4().hex
            pending["tokenHash"] = _token_hash(resume_token)
            _atomic_json(_mode_state_path(), state)
            return _resume_after_update(resume_token, operation_id)

        scopes = pending.get("scopes") if isinstance(pending.get("scopes"), dict) else {}
        result: dict[str, object] = {"version": target}
        for integration in integrations:
            if integration not in completed:
                if integration == "pi":
                    if _refresh_pi() != "refreshed":
                        raise ManagementError("update_integration_unavailable: pi")
                elif integration == "claude":
                    _update_claude_steps(state, pending, str(scopes.get("claude", "user")))
                else:
                    _update_codex_steps(state, pending)
                _save_update_step(state, pending, integration)
            result[integration] = "refreshed"
        result["reloadRequired"] = any(item in integrations for item in ("pi", "claude"))
        if "codex" in integrations:
            result["newSessionRequired"] = True
        report = _doctor_all()
        _save_update_step(state, pending, "doctor")
        result["doctor"] = report
        state.pop("pendingOperation", None)
        state["previousReleaseVersion"] = target
        _atomic_json(_mode_state_path(), state)
        return result
    except ManagementError as exc:
        _save_update_error(state, pending, exc)
        raise


def _doctor_operation(report: dict[str, object]) -> dict[str, object]:
    state = _mode_state()
    pending = state.get("pendingOperation")
    operation: dict[str, object] | None = None
    if isinstance(pending, dict):
        operation = {
            key: pending[key]
            for key in ("command", "targetVersion", "integrations", "completed", "lastError")
            if key in pending
        }
    report["installation"] = {"lock": _lock_report(), "pendingOperation": operation}
    return report


def add_management_parsers(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    init_parser = commands.add_parser("init")
    init_target = init_parser.add_mutually_exclusive_group(required=True)
    init_target.add_argument("--pi", action="store_true")
    init_target.add_argument("--claude", action="store_true")
    init_target.add_argument("--codex", action="store_true")
    init_target.add_argument("--all", action="store_true")
    init_target.add_argument("--dev", action="store_true")
    init_target.add_argument("--release", action="store_true")
    init_parser.add_argument("--source", type=Path)
    init_parser.add_argument("--_switch-token", help=argparse.SUPPRESS)
    doctor_parser = commands.add_parser("doctor")
    doctor_target = doctor_parser.add_mutually_exclusive_group()
    doctor_target.add_argument("--pi", action="store_true")
    doctor_target.add_argument("--claude", action="store_true")
    doctor_target.add_argument("--codex", action="store_true")
    doctor_target.add_argument("--all", action="store_true")
    update_parser = commands.add_parser("update")
    update_parser.add_argument("--_update-token", help=argparse.SUPPRESS)


def _management_command(args: argparse.Namespace) -> str:
    if args.command == "update":
        return "myspec update"
    target = next(
        (name for name in ("pi", "claude", "codex", "all", "dev", "release") if getattr(args, name, False)),
        "",
    )
    source = f" --source {args.source}" if args.source is not None else ""
    return f"myspec init --{target}{source}"


def run_management(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "doctor":
        if args.all:
            report = _doctor_all()
        elif args.claude:
            report = _doctor_claude()
        else:
            report = _doctor_codex() if args.codex else _doctor_pi()
        return _doctor_operation(report)

    internal_token = args._update_token if args.command == "update" else args._switch_token
    if internal_token is not None:
        if args.command == "update":
            pending = _update_pending(_mode_state())
            if pending is None or pending.get("tokenHash") != _token_hash(internal_token):
                raise ManagementError("invalid_update_token")
        else:
            stage = "dev" if args.dev else "release" if args.release else ""
            _validated_pending(stage, internal_token)
        operation_id = _claim_install_lock(internal_token)
    else:
        operation_id = _acquire_install_lock(_management_command(args))
    try:
        if args.command == "update":
            return _run_update(args._update_token, operation_id)
        if args.dev:
            return _switch_dev(args.source, args._switch_token, operation_id)
        if args.release:
            if args.source is not None:
                raise ManagementError("source_only_valid_with_dev")
            return _switch_release(args._switch_token, operation_id)
        if args.source is not None:
            raise ManagementError("source_only_valid_with_dev")
        if args._switch_token is not None:
            raise ManagementError("invalid_switch_token")
        if args.all:
            return _init_all()
        if args.claude:
            return _init_claude()
        return _init_codex() if args.codex else _init_pi()
    finally:
        _release_install_lock(operation_id)
