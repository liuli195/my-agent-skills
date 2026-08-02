from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


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
