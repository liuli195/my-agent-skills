from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "plugins" / "build-and-verify"
PACK = REPO_ROOT / "plugins" / "tool-lifecycle" / "pack.py"
PACKAGE_VERSION = json.loads((PACKAGE_ROOT / "package.json").read_text(encoding="utf-8"))["version"]


def _tree_snapshot() -> dict[str, bytes]:
    roots = ("plugins/my-spec", "plugins/build-and-verify", "plugins/tool-lifecycle")
    return {
        path.relative_to(REPO_ROOT).as_posix(): path.read_bytes()
        for root in roots
        for path in (REPO_ROOT / root).rglob("*")
        if path.is_file()
    }


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


def _controlled_dev_source(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(REPO_ROOT / ".gitignore", source / ".gitignore")
    for relative in (".agents", ".claude-plugin", "plugins/build-and-verify", "plugins/tool-lifecycle"):
        shutil.copytree(
            REPO_ROOT / relative,
            source / relative,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    launcher = source / "plugins" / "build-and-verify" / "bin" / "build-and-verify.js"
    launcher.chmod(launcher.stat().st_mode | 0o111)
    initialized = subprocess.run(["git", "init"], cwd=source, text=True, capture_output=True, check=False)
    assert initialized.returncode == 0, initialized.stderr
    committed = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "add", "."],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr
    executable = subprocess.run(
        ["git", "update-index", "--chmod=+x", str(launcher.relative_to(source))],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert executable.returncode == 0, executable.stderr
    committed = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "source"],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr
    published = tmp_path / "published.git"
    initialized = subprocess.run(["git", "init", "--bare", published], text=True, capture_output=True, check=False)
    assert initialized.returncode == 0, initialized.stderr
    remote = subprocess.run(["git", "remote", "add", "published", published.as_uri()], cwd=source, text=True, capture_output=True, check=False)
    assert remote.returncode == 0, remote.stderr
    pushed = subprocess.run(["git", "push", "published", "HEAD:main"], cwd=source, text=True, capture_output=True, check=False)
    assert pushed.returncode == 0, pushed.stderr
    removed = subprocess.run(["git", "remote", "remove", "published"], cwd=source, text=True, capture_output=True, check=False)
    assert removed.returncode == 0, removed.stderr
    remote = subprocess.run(["git", "remote", "add", "origin", "git@github.com:liuli195/my-agent-skills.git"], cwd=source, text=True, capture_output=True, check=False)
    assert remote.returncode == 0, remote.stderr
    ssh = tmp_path / "ssh.py"
    ssh.write_text(
        "import subprocess\nimport sys\n"
        f"raise SystemExit(subprocess.run(['git', 'upload-pack', {str(published)!r}]).returncode)\n",
        encoding="utf-8",
    )
    return source, ssh


def test_repository_automation_uses_build_and_verify_cli() -> None:
    commands = [
        (REPO_ROOT / ".github" / "workflows" / "full-verify.yml").read_text(encoding="utf-8"),
        (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"),
        (PACKAGE_ROOT / "skills" / "build-and-verify" / "SKILL.md").read_text(encoding="utf-8"),
        (REPO_ROOT / "plugins" / "pi-tool-display" / "CONTRIBUTING.md").read_text(encoding="utf-8"),
    ]

    assert all("build-and-verify" in command for command in commands)
    assert all(".build-and-verify/runtime/build_and_verify.py" not in command for command in commands)
    assert all("scripts/build_and_verify.py" not in command for command in commands)
    assert "build-and-verify verify --project . --full" not in commands[0]
    assert "build-and-verify verify --project source --full" not in commands[1]


def test_full_verify_is_the_cross_platform_required_gate() -> None:
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "full-verify.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]
    gate = jobs["full-verify-gate"]
    gate_step = gate["steps"][0]
    gate_run = gate_step["run"]

    assert jobs["full-verify"]["name"] == "Linux Full Verify"
    assert jobs["windows-worktree-smoke"]["name"] == "Windows worktree smoke"
    assert gate["name"] == "Full Verify"
    assert set(gate["needs"]) == {"full-verify", "windows-worktree-smoke"}
    assert gate["if"] == "${{ always() }}"
    assert gate_step["env"]["LINUX_RESULT"] == "${{ needs.full-verify.result }}"
    assert gate_step["env"]["WINDOWS_RESULT"] == "${{ needs.windows-worktree-smoke.result }}"
    assert '!= "success"' in gate_run
    assert "exit 1" in gate_run


def test_build_and_verify_package_excludes_legacy_skill_runtime() -> None:
    npm = shutil.which("npm")
    assert npm is not None

    packed = subprocess.run(
        [npm, "pack", "--dry-run", "--json"],
        cwd=PACKAGE_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert packed.returncode == 0, packed.stderr
    files = {entry["path"] for entry in json.loads(packed.stdout)[0]["files"]}
    assert "python/build_and_verify.py" in files
    assert "python/build_and_verify_runner.py" in files
    assert not any(path.startswith("skills/build-and-verify/scripts/") for path in files)


def test_controlled_pack_rejects_unknown_package(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(PACK), "unknown", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_controlled_pack_rejects_repository_output() -> None:
    result = subprocess.run(
        [sys.executable, str(PACK), "build-and-verify", str(REPO_ROOT / ".temporary-pack")],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "output_inside_repository" in result.stderr
    assert not (REPO_ROOT / ".temporary-pack").exists()


def test_packed_build_and_verify_rejects_untrusted_dev_source(tmp_path: Path) -> None:
    npm = shutil.which("npm")
    assert npm is not None
    package_dir = tmp_path / "package"
    packed = subprocess.run(
        [sys.executable, str(PACK), "build-and-verify", str(package_dir)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert packed.returncode == 0, packed.stderr
    prefix = tmp_path / "prefix"
    installed = subprocess.run(
        [npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", packed.stdout.strip()],
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    source = tmp_path / "source"
    for relative in (".agents", ".claude-plugin", "plugins/build-and-verify", "plugins/tool-lifecycle"):
        shutil.copytree(REPO_ROOT / relative, source / relative)
    initialized = subprocess.run(["git", "init"], cwd=source, text=True, capture_output=True, check=False)
    assert initialized.returncode == 0, initialized.stderr
    committed = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "add", "."],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr
    committed = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "source"],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")
    env = _isolated_env(tmp_path, prefix)

    rejected = subprocess.run([executable, "init", "--dev", "--source", source], text=True, capture_output=True, check=False, env=env)

    assert rejected.returncode == 1
    assert "error: invalid_dev_source: official_remote" in rejected.stderr
    assert not (tmp_path / "home" / ".build-and-verify" / "state.json").exists()


def test_packed_build_and_verify_doctor_reports_machine_readable_release_identity(tmp_path: Path) -> None:
    npm = shutil.which("npm")
    assert npm is not None
    before = _tree_snapshot()
    packed = subprocess.run(
        [sys.executable, str(PACK), "build-and-verify", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert packed.returncode == 0, packed.stderr
    assert _tree_snapshot() == before
    tarball = Path(packed.stdout.strip())
    prefix = tmp_path / "prefix"
    installed = subprocess.run(
        [npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", str(tarball)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")
    env = _isolated_env(tmp_path, prefix)
    diagnosed = subprocess.run(
        [executable, "doctor"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report["toolchain"] == {
        "mode": "release",
        "packageName": "@liuli195/build-and-verify",
        "packageVersion": PACKAGE_VERSION,
    }


def test_packed_build_and_verify_update_blocks_legacy_codex_before_writes(tmp_path: Path) -> None:
    npm = shutil.which("npm")
    node = shutil.which("node")
    assert npm is not None and node is not None
    latest = PACKAGE_VERSION
    packed = subprocess.run(
        [sys.executable, str(PACK), "build-and-verify", str(tmp_path / "package")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert packed.returncode == 0, packed.stderr
    prefix = tmp_path / "prefix"
    installed = subprocess.run(
        [npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", packed.stdout.strip()],
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    npm_log = tmp_path / "npm.log"
    codex_log = tmp_path / "codex.log"
    codex_state = tmp_path / "codex-state.json"
    codex_failure_marker = tmp_path / "codex-failure-marker"
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    package_root = subprocess.run(
        [npm, "root", "--global", "--prefix", str(prefix)],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    stable = Path(package_root) / "@liuli195" / "build-and-verify"
    legacy = tmp_path / "legacy-source"
    write = lambda path, value: path.write_text(value, encoding="utf-8")
    write(
        codex_state,
        json.dumps(
            {
                "marketplaces": [
                    {"name": "build-and-verify", "root": str(stable)},
                    {"name": "my-agent-skills-marketplace", "root": str(legacy)},
                ],
                "installed": [
                    {
                        "pluginId": "build-and-verify@build-and-verify",
                        "installed": True,
                    },
                    {
                        "pluginId": "build-and-verify@my-agent-skills-marketplace",
                        "installed": True,
                    },
                ],
                "available": [],
            },
            indent=2,
        ),
    )
    codex_config = codex_home / "config.toml"
    write(
        codex_config,
        '[plugins."build-and-verify@build-and-verify"]\nenabled = true\n'
        '[plugins."build-and-verify@my-agent-skills-marketplace"]\nenabled = true\n',
    )
    codex_before = codex_state.read_bytes(), codex_config.read_bytes()
    write(
        fake_bin / "fake-npm.py",
        "import json, os, subprocess, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['BUILD_NPM_LOG'], 'a', encoding='utf-8') as log:\n"
        "    log.write(json.dumps(args) + '\\n')\n"
        "if args == ['view', '@liuli195/build-and-verify', 'version', '--json']:\n"
        "    print(json.dumps(os.environ['BUILD_NPM_LATEST']))\n"
        "    raise SystemExit(0)\n"
        "if args[:2] == ['install', '--global']:\n"
        "    raise SystemExit(77)\n"
        "real = os.environ['BUILD_REAL_NPM']\n"
        "command = [real, *args]\n"
        "result = subprocess.run(subprocess.list2cmdline(command) if os.name == 'nt' else command, shell=os.name == 'nt')\n"
        "raise SystemExit(result.returncode)\n",
    )
    write(
        fake_bin / "fake-codex.py",
        "import json, os, re, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "state_path = Path(os.environ['BUILD_CODEX_STATE'])\n"
        "state = json.loads(state_path.read_text(encoding='utf-8'))\n"
        "with Path(os.environ['BUILD_CODEX_LOG']).open('a', encoding='utf-8') as log:\n"
        "    log.write(json.dumps(args) + '\\n')\n"
        "def save():\n"
        "    state_path.write_text(json.dumps(state), encoding='utf-8')\n"
        "if args == ['plugin', 'marketplace', 'list', '--json']:\n"
        "    print(json.dumps({'marketplaces': state['marketplaces']}))\n"
        "elif args == ['plugin', 'list', '--json']:\n"
        "    text = Path(os.environ['CODEX_HOME']) / 'config.toml'\n"
        "    config = text.read_text(encoding='utf-8') if text.exists() else ''\n"
        "    installed = []\n"
        "    for item in state['installed']:\n"
        "        current = dict(item)\n"
        "        identifier = re.escape(item['pluginId'])\n"
        "        current['enabled'] = bool(re.search(rf'(?ms)^\\[plugins\\.\"{identifier}\"\\]\\s*\\n.*?^enabled\\s*=\\s*true\\s*$', config))\n"
        "        installed.append(current)\n"
        "    print(json.dumps({'installed': installed, 'available': state['available']}))\n"
        "elif args[:2] == ['plugin', 'remove']:\n"
        "    identifier = args[2]\n"
        "    if identifier == 'build-and-verify@my-agent-skills-marketplace' and not Path(os.environ['BUILD_CODEX_FAIL_MARKER']).exists():\n"
        "        Path(os.environ['BUILD_CODEX_FAIL_MARKER']).write_text('failed', encoding='utf-8')\n"
        "        raise SystemExit(77)\n"
        "    state['installed'] = [item for item in state['installed'] if item['pluginId'] != identifier]\n"
        "    save()\n"
        "elif args == ['plugin', 'add', 'build-and-verify@build-and-verify', '--json']:\n"
        "    state['installed'] = [item for item in state['installed'] if item['pluginId'] != 'build-and-verify@build-and-verify']\n"
        "    state['installed'].append({'pluginId': 'build-and-verify@build-and-verify', 'installed': True, 'version': os.environ['BUILD_PACKAGE_VERSION'], 'source': {'source': 'local', 'path': os.environ['BUILD_STABLE']}})\n"
        "    config_path = Path(os.environ['CODEX_HOME']) / 'config.toml'\n"
        "    config = config_path.read_text(encoding='utf-8') if config_path.exists() else ''\n"
        "    if '[plugins.\"build-and-verify@build-and-verify\"]' not in config:\n"
        "        config_path.write_text(config.rstrip() + '\\n[plugins.\"build-and-verify@build-and-verify\"]\\nenabled = true\\n', encoding='utf-8')\n"
        "    save()\n"
        "else:\n"
        "    raise SystemExit(2)\n",
    )
    for name in ("npm", "codex"):
        script = fake_bin / f"fake-{name}.py"
        launcher = fake_bin / (f"{name}.cmd" if sys.platform == "win32" else name)
        if sys.platform == "win32":
            write(launcher, f'@"{sys.executable}" "{script}" %*\n')
        else:
            write(launcher, f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
            launcher.chmod(0o755)
    env = {
        **os.environ,
        "BUILD_AND_VERIFY_PYTHON": sys.executable,
        "NPM_CONFIG_PREFIX": str(prefix),
        "HOME": str(tmp_path / "home"),
        "USERPROFILE": str(tmp_path / "home"),
        "CODEX_HOME": str(codex_home),
        "BUILD_NPM_LOG": str(npm_log),
        "BUILD_REAL_NPM": str(npm),
        "BUILD_NPM_LATEST": latest,
        "BUILD_CODEX_LOG": str(codex_log),
        "BUILD_CODEX_STATE": str(codex_state),
        "BUILD_CODEX_FAIL_MARKER": str(codex_failure_marker),
        "BUILD_PACKAGE_VERSION": PACKAGE_VERSION,
        "BUILD_STABLE": str(stable),
        "PATH": os.pathsep.join(
            [str(fake_bin), str(Path(sys.executable).parent), str(Path(node).parent)]
        ),
    }
    blocked = subprocess.run(
        [executable, "update"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert blocked.returncode == 1
    assert "error: legacy_source_migration_required" in blocked.stderr
    assert "build-and-verify init --codex" in blocked.stderr
    assert "build-and-verify init --pi" not in blocked.stderr
    assert "build-and-verify init --claude" not in blocked.stderr
    assert not any(json.loads(line)[:2] == ["install", "--global"] for line in npm_log.read_text(encoding="utf-8").splitlines())
    assert not (Path(env["HOME"]) / ".build-and-verify" / "state.json").exists()
    assert "plugin remove" not in codex_log.read_text(encoding="utf-8")
    assert (codex_state.read_bytes(), codex_config.read_bytes()) == codex_before

    failed_migration = subprocess.run(
        [executable, "init", "--codex"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert failed_migration.returncode == 1
    assert "error: codex_plugin_remove_failed:" in failed_migration.stderr

    migrated = subprocess.run(
        [executable, "init", "--codex"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert migrated.returncode == 0, migrated.stderr
    assert not any(
        item["pluginId"] == "build-and-verify@my-agent-skills-marketplace"
        for item in json.loads(codex_state.read_text(encoding="utf-8"))["installed"]
    )

    updated = subprocess.run(
        [executable, "update"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert updated.returncode == 0, updated.stderr
    assert json.loads(updated.stdout)["version"] == PACKAGE_VERSION


def _git(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=project, text=True, capture_output=True, check=False)


def _legacy_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    runtime = project / ".build-and-verify" / "runtime"
    runtime.mkdir(parents=True)
    (project / ".build-and-verify" / "config.json").write_text(
        json.dumps({"version": 1, "build": {"checks": []}, "verify": {"checks": []}}),
        encoding="utf-8",
    )
    (runtime / "build_and_verify.py").write_text("legacy", encoding="utf-8")
    (runtime / "build_and_verify_runner.py").write_text("legacy", encoding="utf-8")
    (runtime / "version.json").write_text(
        json.dumps({"plugin": "build-and-verify", "plugin_version": PACKAGE_VERSION, "runtime_version": PACKAGE_VERSION}),
        encoding="utf-8",
    )
    assert _git(project, "init").returncode == 0
    assert _git(project, "config", "user.name", "test").returncode == 0
    assert _git(project, "config", "user.email", "test@example.invalid").returncode == 0
    assert _git(project, "add", ".").returncode == 0
    committed = _git(project, "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "initial")
    assert committed.returncode == 0, committed.stderr
    return project


def test_packed_build_and_verify_migrates_recognized_runtime_after_fast_verify(tmp_path: Path) -> None:
    npm = shutil.which("npm")
    assert npm is not None
    packed = subprocess.run(
        [sys.executable, str(PACK), "build-and-verify", str(tmp_path / "package")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert packed.returncode == 0, packed.stderr
    prefix = tmp_path / "prefix"
    installed = subprocess.run(
        [npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", packed.stdout.strip()],
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")
    project = _legacy_project(tmp_path)

    migrated = subprocess.run(
        [executable, "verify", "--project", str(project)],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
        env=_isolated_env(tmp_path, prefix),
    )

    assert migrated.returncode == 0, migrated.stderr
    assert not (project / ".build-and-verify" / "runtime").exists()
    assert _git(project, "status", "--porcelain").stdout == ""
    assert _git(project, "show", "--name-only", "--format=").stdout.splitlines() == [
        ".build-and-verify/runtime/build_and_verify.py",
        ".build-and-verify/runtime/build_and_verify_runner.py",
        ".build-and-verify/runtime/version.json",
    ]


def test_packed_build_and_verify_preserves_legacy_runtime_when_verify_fails(tmp_path: Path) -> None:
    npm = shutil.which("npm")
    assert npm is not None
    packed = subprocess.run([sys.executable, str(PACK), "build-and-verify", str(tmp_path / "package")], text=True, capture_output=True, check=False)
    assert packed.returncode == 0, packed.stderr
    prefix = tmp_path / "prefix"
    installed = subprocess.run([npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", packed.stdout.strip()], text=True, capture_output=True, check=False)
    assert installed.returncode == 0, installed.stderr
    project = _legacy_project(tmp_path)
    (project / ".build-and-verify" / "config.json").write_text(
        json.dumps({"version": 1, "build": {"checks": []}, "verify": {"checks": [{"id": "fail", "command": [sys.executable, "-c", "raise SystemExit(1)"], "paths": [".build-and-verify/runtime/"]}]}}),
        encoding="utf-8",
    )
    assert _git(project, "add", ".").returncode == 0
    assert _git(project, "commit", "-m", "failing verify").returncode == 0
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")

    verified = subprocess.run([executable, "verify", "--project", str(project)], cwd=project, text=True, capture_output=True, check=False, env=_isolated_env(tmp_path, prefix))

    assert verified.returncode == 1
    assert (project / ".build-and-verify" / "runtime").is_dir()
    assert _git(project, "status", "--porcelain").stdout == ""


def test_packed_build_and_verify_rejects_unrecognized_legacy_runtime(tmp_path: Path) -> None:
    npm = shutil.which("npm")
    assert npm is not None
    packed = subprocess.run([sys.executable, str(PACK), "build-and-verify", str(tmp_path / "package")], text=True, capture_output=True, check=False)
    assert packed.returncode == 0, packed.stderr
    prefix = tmp_path / "prefix"
    installed = subprocess.run([npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", packed.stdout.strip()], text=True, capture_output=True, check=False)
    assert installed.returncode == 0, installed.stderr
    project = _legacy_project(tmp_path)
    (project / ".build-and-verify" / "runtime" / "unexpected.py").write_text("not legacy", encoding="utf-8")
    assert _git(project, "add", ".").returncode == 0
    assert _git(project, "commit", "-m", "unrecognized runtime").returncode == 0
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")

    verified = subprocess.run([executable, "verify", "--project", str(project)], cwd=project, text=True, capture_output=True, check=False, env=_isolated_env(tmp_path, prefix))

    assert verified.returncode == 1
    assert "unrecognized_runtime" in verified.stderr
    assert (project / ".build-and-verify" / "runtime" / "unexpected.py").is_file()
    assert _git(project, "status", "--porcelain").stdout == ""


def test_packed_build_and_verify_preserves_runtime_when_fast_verify_stages_external_file(tmp_path: Path) -> None:
    npm = shutil.which("npm")
    assert npm is not None
    packed = subprocess.run([sys.executable, str(PACK), "build-and-verify", str(tmp_path / "package")], text=True, capture_output=True, check=False)
    assert packed.returncode == 0, packed.stderr
    prefix = tmp_path / "prefix"
    installed = subprocess.run([npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", packed.stdout.strip()], text=True, capture_output=True, check=False)
    assert installed.returncode == 0, installed.stderr
    project = _legacy_project(tmp_path)
    write_and_stage = "from pathlib import Path; import subprocess; Path('external.txt').write_text('keep'); subprocess.check_call(['git', 'add', 'external.txt'])"
    (project / ".build-and-verify" / "config.json").write_text(
        json.dumps({"version": 1, "build": {"checks": []}, "verify": {"checks": [{"id": "stages-external", "command": [sys.executable, "-c", write_and_stage], "paths": [".build-and-verify/runtime/"]}]}}),
        encoding="utf-8",
    )
    assert _git(project, "add", ".").returncode == 0
    assert _git(project, "commit", "-m", "staging verify").returncode == 0
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")

    verified = subprocess.run([executable, "verify", "--project", str(project)], cwd=project, text=True, capture_output=True, check=False, env=_isolated_env(tmp_path, prefix))

    assert verified.returncode == 1
    assert "git_worktree_not_clean" in verified.stderr
    assert (project / ".build-and-verify" / "runtime").is_dir()
    assert _git(project, "diff", "--cached", "--name-only").stdout == "external.txt\n"


def test_packed_build_and_verify_restores_runtime_when_migration_commit_fails(tmp_path: Path) -> None:
    npm = shutil.which("npm")
    assert npm is not None
    packed = subprocess.run([sys.executable, str(PACK), "build-and-verify", str(tmp_path / "package")], text=True, capture_output=True, check=False)
    assert packed.returncode == 0, packed.stderr
    prefix = tmp_path / "prefix"
    installed = subprocess.run([npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", packed.stdout.strip()], text=True, capture_output=True, check=False)
    assert installed.returncode == 0, installed.stderr
    project = _legacy_project(tmp_path)
    hook = project / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")

    verified = subprocess.run([executable, "verify", "--project", str(project)], cwd=project, text=True, capture_output=True, check=False, env=_isolated_env(tmp_path, prefix))

    assert verified.returncode == 1
    assert "commit_failed" in verified.stderr
    assert (project / ".build-and-verify" / "runtime").is_dir()
    assert _git(project, "status", "--porcelain").stdout == ""


def test_packed_build_and_verify_codex_doctor_resolves_orca_and_explicit_homes(
    tmp_path: Path,
) -> None:
    npm = shutil.which("npm")
    assert npm is not None
    packed = subprocess.run(
        [sys.executable, str(PACK), "build-and-verify", str(tmp_path / "package")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert packed.returncode == 0, packed.stderr
    prefix = tmp_path / "prefix"
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
            packed.stdout.strip(),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    fake_bin = tmp_path / "fake-codex" / "bin"
    fake_bin.mkdir(parents=True)
    env_log = tmp_path / "codex-env.log"
    probe = fake_bin.parent / "codex_probe.py"
    probe.write_text(
        "import json\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['CODEX_ENV_LOG']).open('a', encoding='utf-8').write(os.environ['CODEX_HOME'] + '\\n')\n"
        "if sys.argv[1:] == ['plugin', 'marketplace', 'list', '--json']:\n"
        "    print(json.dumps({'marketplaces': []}))\n"
        "elif sys.argv[1:] == ['plugin', 'list', '--json']:\n"
        "    print(json.dumps({'installed': [], 'available': []}))\n"
        "else:\n"
        "    raise SystemExit(2)\n",
        encoding="utf-8",
    )
    if sys.platform == "win32":
        (fake_bin / "codex.cmd").write_text(
            f'@"{sys.executable}" "{probe}" %*\n',
            encoding="utf-8",
        )
    else:
        launcher = fake_bin / "codex"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{probe}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")
    env = _isolated_env(tmp_path, prefix)
    user_home = Path(env["USERPROFILE"]) / ".codex"
    orca_home = tmp_path / "orca-user-data" / "codex-runtime-home" / "home"
    orca_home.mkdir(parents=True)
    env.update(
        {
            "PATH": os.pathsep.join([str(fake_bin), env["PATH"]]),
            "CODEX_HOME": str(orca_home),
            "ORCA_USER_DATA_PATH": str(tmp_path / "orca-user-data"),
            "CODEX_ENV_LOG": str(env_log),
        }
    )

    inherited = subprocess.run(
        [executable, "doctor", "--codex"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert inherited.returncode == 0, inherited.stderr
    report = json.loads(inherited.stdout)["codex"]
    assert report["codexHome"] == str(user_home)
    assert report["codexHomeSource"] == "orca-user-default"
    assert env_log.read_text(encoding="utf-8").splitlines() == [str(user_home), str(user_home)]

    explicit_home = tmp_path / "custom-codex-home"
    explicit_home.mkdir()
    env_log.write_text("", encoding="utf-8")
    explicit = subprocess.run(
        [executable, "doctor", "--codex", "--codex-home", explicit_home],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert explicit.returncode == 0, explicit.stderr
    report = json.loads(explicit.stdout)["codex"]
    assert report["codexHome"] == str(explicit_home)
    assert report["codexHomeSource"] == "explicit"
    assert env_log.read_text(encoding="utf-8").splitlines() == [str(explicit_home), str(explicit_home)]
    assert env["CODEX_HOME"] == str(orca_home)

    unavailable_home = tmp_path / "not-a-directory"
    unavailable_home.write_text("not a directory", encoding="utf-8")
    env_log.write_text("", encoding="utf-8")
    unavailable = subprocess.run(
        [executable, "doctor", "--codex", "--codex-home", unavailable_home],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert unavailable.returncode == 1
    assert f"error: codex_home_unavailable: {unavailable_home}: not a directory" in unavailable.stderr
    assert env_log.read_text(encoding="utf-8") == ""
    assert env["CODEX_HOME"] == str(orca_home)

    missing_home = tmp_path / "missing-codex-home"
    missing = subprocess.run(
        [executable, "doctor", "--codex", "--codex-home", missing_home],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert missing.returncode == 1
    assert f"error: codex_home_unavailable: {missing_home}: directory does not exist" in missing.stderr


def test_packed_build_and_verify_rejects_dirty_legacy_migration(tmp_path: Path) -> None:
    npm = shutil.which("npm")
    assert npm is not None
    packed = subprocess.run([sys.executable, str(PACK), "build-and-verify", str(tmp_path / "package")], text=True, capture_output=True, check=False)
    assert packed.returncode == 0, packed.stderr
    prefix = tmp_path / "prefix"
    installed = subprocess.run([npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", packed.stdout.strip()], text=True, capture_output=True, check=False)
    assert installed.returncode == 0, installed.stderr
    project = _legacy_project(tmp_path)
    (project / "unrelated.txt").write_text("keep", encoding="utf-8")
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")

    migrated = subprocess.run([executable, "verify", "--project", str(project)], cwd=project, text=True, capture_output=True, check=False, env=_isolated_env(tmp_path, prefix))

    assert migrated.returncode == 1
    assert "git_worktree_not_clean" in migrated.stderr
    assert (project / ".build-and-verify" / "runtime").is_dir()
    assert _git(project, "status", "--porcelain").stdout == "?? unrelated.txt\n"


def test_packed_build_and_verify_accepts_controlled_ssh_dev_source(tmp_path: Path) -> None:
    npm = shutil.which("npm")
    assert npm is not None
    packed = subprocess.run(
        [sys.executable, str(PACK), "build-and-verify", str(tmp_path / "package")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert packed.returncode == 0, packed.stderr
    prefix = tmp_path / "prefix"
    installed = subprocess.run(
        [npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", packed.stdout.strip()],
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    executable = prefix / ("build-and-verify.cmd" if sys.platform == "win32" else "bin/build-and-verify")
    source, ssh = _controlled_dev_source(tmp_path)
    env = _isolated_env(tmp_path, prefix)
    env["GIT_SSH_COMMAND"] = f'"{sys.executable}" "{ssh}"'
    entered = subprocess.run(
        [executable, "init", "--dev", "--source", source],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert entered.returncode == 0, entered.stderr
    report = json.loads(entered.stdout)
    assert report["mode"] == "dev"
    assert report["source"] == str(source)
    assert _git(source, "status", "--porcelain").stdout == ""
