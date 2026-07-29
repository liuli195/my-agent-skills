from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


PACKAGE_NAME = "@liuli195/myspec"
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


def _canonical_path(path: Path) -> Path:
    return Path(os.path.realpath(os.path.abspath(path)))


def _pi_project_trusted(user_settings: Path) -> bool:
    trust_path = _pi_agent_dir() / "trust.json"
    decisions = _read_json(trust_path) if trust_path.exists() else {}
    if not isinstance(decisions, dict) or not all(
        value is True or value is False or value is None for value in decisions.values()
    ):
        raise ManagementError(f"invalid_pi_trust: {trust_path}")
    current = _canonical_path(Path.cwd())
    while True:
        decision = decisions.get(str(current))
        if isinstance(decision, bool):
            return decision
        if current.parent == current:
            break
        current = current.parent
    return _read_settings(user_settings).get("defaultProjectTrust") == "always"


def _pi_settings_paths() -> tuple[tuple[str, Path], ...]:
    user = _pi_agent_dir() / "settings.json"
    paths = [("user", user)]
    project = Path.cwd() / ".pi" / "settings.json"
    if project.exists() and _pi_project_trusted(user):
        paths.append(("project", project))
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


def _pi_sources() -> list[PiSource]:
    result: list[PiSource] = []
    for scope, path in _pi_settings_paths():
        settings = _read_settings(path)
        packages = settings.get("packages", [])
        if not isinstance(packages, list):
            raise ManagementError(f"invalid_pi_packages: {path}")
        for index, item in enumerate(packages):
            source = _package_source(item)
            if source is not None:
                result.append(PiSource(scope, path, settings, index, item, source, _local_source_path(source, path)))
    return result


def _source_identity(item: PiSource) -> str:
    normalized = item.source.replace("\\", "/").rstrip("/")
    lowered = normalized.lower()
    if item.local_path is not None:
        return "local:" + os.path.normcase(os.path.abspath(item.local_path))
    if lowered.startswith("npm:"):
        spec = normalized[4:]
        match = re.fullmatch(r"(@?[^@]+(?:/[^@]+)?)(?:@.+)?", spec)
        return "npm:" + (match.group(1) if match else spec).lower()
    value = re.sub(r"(?:@[^/]+|#[^/]+)$", "", lowered.removeprefix("git:"))
    value = re.sub(r"^(?:https?|ssh|git)://", "", value)
    return "git:" + value.removesuffix(".git")


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


def _pi_source_listed(item: PiSource, listed: list[dict[str, str]]) -> bool:
    return any(
        record["source"] == item.source
        and (item.local_path is None or _same_path(Path(record["path"]), item.local_path))
        for record in listed
    )


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
    sources = _pi_sources()
    user_stable = [item for item in sources if item.scope == "user" and _myspec_source_kind(item, stable) == "stable"]
    if not user_stable:
        installed = _run("pi", "install", str(stable))
        if installed.returncode != 0:
            raise ManagementError(f"pi_install_failed: {installed.stderr.strip()}")
        sources = _pi_sources()
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
    if not any(_pi_source_listed(item, listed) for item in user_stable):
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


def _init_all() -> dict[str, object]:
    result: dict[str, object] = {}
    for agent in ("pi", "claude", "codex"):
        if shutil.which(agent) is None:
            result[agent] = {"status": "skipped", "reason": f"missing_command: {agent}"}
        elif agent == "pi":
            initialized = _init_pi()
            result[agent] = {"status": "initialized", "source": initialized["source"]}
        else:
            result[agent] = {"status": "skipped", "reason": "integration_not_available"}
    return result


def _mode_state_path() -> Path:
    return Path.home() / ".myspec" / "state.json"


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
        agents_market,
        claude_market,
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
    for path in (package_root / ".claude-plugin" / "plugin.json", package_root / ".codex-plugin" / "plugin.json"):
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


def _resume_after_switch(arguments: list[str], token: str) -> dict[str, object]:
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


def _group_effective_myspec(stable: Path) -> list[tuple[str, str, list[PiSource]]]:
    groups: list[tuple[str, str, list[PiSource]]] = []
    by_identity: dict[str, int] = {}
    for item in _effective_sources(_pi_sources()):
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
        if item.local_path is None or not (item.local_path / "package.json").is_file():
            continue
        skills = _manifest_skills(item.local_path)
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


def _pi_is_configured() -> bool:
    stable = _stable_package_root()
    return any(kind == "stable" and _group_skills(group) for _, kind, group in _group_effective_myspec(stable))


def _refresh_pi() -> str:
    if shutil.which("pi") is None or not _pi_is_configured():
        return "not-installed"
    stable = _stable_package_root()
    listed = _pi_list()
    if not any(
        _myspec_source_kind(item, stable) == "stable" and _pi_source_listed(item, listed)
        for item in _pi_sources()
    ):
        return "not-installed"
    return "refreshed"


def _switch_dev(raw_source: Path | None, token: str | None) -> dict[str, object]:
    source, package_root, commit = _validate_dev_source(raw_source or Path.cwd())
    if token is not None:
        state = _validated_pending("dev", token)
        previous = state.get("previousReleaseVersion")
        if not isinstance(previous, str) or not previous:
            raise ManagementError("missing_previous_release_version")
        pi_status = _refresh_pi()
        state.pop("pendingSwitch")
        _atomic_json(_mode_state_path(), state)
        return {"mode": "dev", "source": str(source), "previousReleaseVersion": previous, "pi": pi_status, "reloadRequired": pi_status == "refreshed"}
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
    return _resume_after_switch(["init", "--dev", "--source", str(source)], switch_token)


def _switch_release(token: str | None) -> dict[str, object]:
    state = _mode_state()
    previous = state.get("previousReleaseVersion")
    if not isinstance(previous, str) or not previous:
        raise ManagementError("missing_previous_release_version")
    if token is not None:
        state = _validated_pending("release", token)
        pi_status = _refresh_pi()
        _atomic_json(_mode_state_path(), {"mode": "release", "previousReleaseVersion": previous})
        return {"mode": "release", "version": previous, "pi": pi_status, "reloadRequired": pi_status == "refreshed"}
    if state["mode"] != "dev":
        raise ManagementError("missing_previous_release_version")
    switch_token = uuid.uuid4().hex
    pending = {**state, "pendingSwitch": {"stage": "release", "token": switch_token}}
    _atomic_json(_mode_state_path(), pending)
    installed = _run("npm", "install", "--global", "--ignore-scripts", "--no-audit", "--no-fund", f"{PACKAGE_NAME}@{previous}")
    if installed.returncode != 0:
        raise ManagementError(f"npm_install_failed: {installed.stderr.strip()}")
    return _resume_after_switch(["init", "--release"], switch_token)


def _pi_list() -> list[dict[str, str]]:
    listed = _run("pi", "list")
    if listed.returncode != 0:
        raise ManagementError(f"pi_list_failed: {listed.stderr.strip()}")
    result: list[dict[str, str]] = []
    pending: str | None = None
    for line in listed.stdout.splitlines():
        if line.startswith("  ") and not line.startswith("    "):
            pending = line.strip().removesuffix(" (filtered)")
        elif pending is not None and line.startswith("    ") and not line.strip().startswith("skills:"):
            result.append({"source": pending, "path": line.strip()})
            pending = None
    return result


def _manifest_version(root: Path) -> str | None:
    path = root / "package.json"
    if not path.is_file():
        return None
    value = _read_json(path)
    return value.get("version") if isinstance(value, dict) and isinstance(value.get("version"), str) else None


def _doctor_pi() -> dict[str, object]:
    stable = _stable_package_root()
    real = Path(os.path.realpath(stable))
    cli_version = _package_version()
    available = shutil.which("pi") is not None
    listed = _pi_list() if available else []
    configured_sources = _pi_sources()
    all_sources = [item for item in configured_sources if _pi_source_listed(item, listed)]
    effective = _effective_sources(all_sources)
    effective_ids = {_source_identity(item) for item in effective}
    records: list[dict[str, object]] = []
    for item in all_sources:
        kind = _myspec_source_kind(item, stable)
        if kind is not None:
            records.append({
                "scope": item.scope,
                "settings": str(item.settings_path),
                "source": item.source,
                "resolvedPath": str(item.local_path) if item.local_path is not None else None,
                "kind": kind,
                "effective": _source_identity(item) in effective_ids and item in effective,
                "enabled": bool(_group_skills([item])),
            })
    groups = _group_effective_myspec(stable)
    enabled_groups = [(kind, group, _group_skills(group)) for _, kind, group in groups]
    stable_skills = next((skills for kind, _, skills in enabled_groups if kind == "stable"), [])
    enabled_sources = [group[0].source for _, group, skills in enabled_groups if skills]
    disabled_sources = [item.source for item in all_sources if _myspec_source_kind(item, stable) is not None and not _group_skills([item])]
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
        "pi": {
            "available": available,
            "registered": bool(stable_skills),
            "enabledSources": enabled_sources,
            "disabledSources": disabled_sources,
            "duplicateEnabledSources": len(enabled_sources) > 1,
            "sources": records,
            "listedSources": listed,
            "skills": stable_skills,
            "reloadRequired": bool(enabled_sources),
        },
    }


def add_management_parsers(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    init_parser = commands.add_parser("init")
    init_target = init_parser.add_mutually_exclusive_group(required=True)
    init_target.add_argument("--pi", action="store_true")
    init_target.add_argument("--all", action="store_true")
    init_target.add_argument("--dev", action="store_true")
    init_target.add_argument("--release", action="store_true")
    init_parser.add_argument("--source", type=Path)
    init_parser.add_argument("--_switch-token", help=argparse.SUPPRESS)
    doctor_parser = commands.add_parser("doctor")
    doctor_parser.add_argument("--pi", action="store_true")


def run_management(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "doctor":
        return _doctor_pi()
    if args.dev:
        return _switch_dev(args.source, args._switch_token)
    if args.release:
        if args.source is not None:
            raise ManagementError("source_only_valid_with_dev")
        return _switch_release(args._switch_token)
    if args.source is not None:
        raise ManagementError("source_only_valid_with_dev")
    if args._switch_token is not None:
        raise ManagementError("invalid_switch_token")
    return _init_all() if args.all else _init_pi()
