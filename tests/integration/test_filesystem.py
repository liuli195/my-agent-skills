"""Minimal real-workspace smoke, plus the Windows junction adapter."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from tests.test_build_and_verify_plugin import (
    REPO_ROOT, command_that_logs, git, run_build_and_verify_subprocess,
    write_runner_config,
)
from tests.test_setup_worktree_script import normalize_powershell_output

SCRIPT = REPO_ROOT / "scripts/setup-worktree.ps1"


class TestWorkspace:
    def test_public_baseline_execution_cache_and_git_visible_inputs(self, tmp_path):
        primary = tmp_path / "primary"
        primary.mkdir()

        def checked_git(project, *arguments):
            result = git(project, *arguments)
            assert result.returncode == 0, result.stdout + result.stderr
            return result.stdout.strip()

        checked_git(primary, "init", "-q")
        checked_git(primary, "config", "user.name", "Test")
        checked_git(primary, "config", "user.email", "test@example.invalid")
        initialized = run_build_and_verify_subprocess("init", "--project", str(primary))
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        (primary / ".gitignore").write_text("src/ignored.txt\n/run.log\n", encoding="utf-8")
        (primary / "src").mkdir()
        (primary / "src/app.py").write_text("base\n", encoding="utf-8")
        write_runner_config(primary, verify_checks=[
            {"id": "source", "command": command_that_logs("source"),
             "paths": ["src/**"], "inputs": ["src"]},
            {"id": "base-only", "command": command_that_logs("base-only"),
             "paths": ["base-only.txt"]},
        ])
        checked_git(primary, "add", ".")
        checked_git(primary, "commit", "-qm", "base")
        baseline = checked_git(primary, "branch", "--show-current")
        project = tmp_path / "worktree"
        checked_git(primary, "worktree", "add", "-b", "smoke", str(project), "HEAD")
        # The base advances independently: a two-point diff would select base-only.
        (primary / "base-only.txt").write_text("only on base\n", encoding="utf-8")
        checked_git(primary, "add", "base-only.txt")
        checked_git(primary, "commit", "-qm", "advance base")
        source = project / "src/app.py"
        source.write_text("changed\n", encoding="utf-8")
        checked_git(project, "add", "src/app.py")
        checked_git(project, "commit", "-qm", "change source")

        def verify():
            result = run_build_and_verify_subprocess(
                "verify", "--project", str(project), "--base", baseline,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            assert "checked: source" in result.stdout
            assert "base-only" not in result.stdout
            return result.stdout

        assert "status: passed" in verify()
        (project / "src/ignored.txt").write_text("ignored change\n", encoding="utf-8")
        assert "cache-hit: source" in verify()
        source.write_text("visible change\n", encoding="utf-8")
        checked_git(project, "add", "src/app.py")
        checked_git(project, "commit", "-qm", "change visible input")
        assert "cache-hit:" not in verify()
        assert (project / "run.log").read_text().splitlines() == [
            "source", "source",
        ]

    @pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
    def test_setup_worktree_script_links_shared_node_dependencies(self,
        tmp_path: Path
    ) -> None:
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if not shell:
            pytest.skip("PowerShell executable is required")

        project = tmp_path / "project"
        project.mkdir()
        (project / "scripts").mkdir()
        shutil.copy2(SCRIPT, project / "scripts" / SCRIPT.name)
        shutil.copy2(REPO_ROOT / "package.json", project / "package.json")
        shutil.copy2(REPO_ROOT / "package-lock.json", project / "package-lock.json")
        shutil.copy2(REPO_ROOT / "requirements-dev.txt", project / "requirements-dev.txt")
        nested = Path("plugins/data-store/skills/data-store/requirements.txt")
        (project / nested).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / nested, project / nested)

        def run(*args: str, cwd: Path = project) -> subprocess.CompletedProcess[str]:
            return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)

        run("git", "init")
        run("git", "config", "user.email", "test@example.invalid")
        run("git", "config", "user.name", "Test")
        run("git", "add", ".")
        run("git", "commit", "-m", "fixture")

        shared_node_modules = project / "node_modules"
        worktree = project / ".worktrees/test"
        run("git", "worktree", "add", "--detach", str(worktree), "HEAD")
        shared_venv = project / ".venv"
        shared_python = shared_venv / "Scripts/python.exe"
        requirements = (project / "requirements-dev.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
        fingerprint = hashlib.sha256(requirements.encode()).hexdigest().upper()

        npm_marker = project / "npm-called"
        py_marker = project / "py-called"
        fake_bin = project / "fake-bin"
        fake_bin.mkdir()
        (fake_bin / "npm.cmd").write_text(
            f'@echo called>>"{npm_marker}"\n@exit /b 99\n', encoding="utf-8"
        )
        (fake_bin / "py.cmd").write_text(
            f'@echo called>>"{py_marker}"\n@exit /b 99\n', encoding="utf-8"
        )
        env = os.environ | {"PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}
        command = [shell, "-NoProfile", "-File", str(worktree / "scripts/setup-worktree.ps1")]

        def setup(*, check: bool = False) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                command,
                cwd=worktree,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=check,
            )

        shared_node_modules.mkdir()
        node_fingerprint = "\n".join(
            f"{hashlib.sha256((project / manifest).read_text(encoding='utf-8').replace(chr(13) + chr(10), chr(10)).encode()).hexdigest().upper()} {manifest}"
            for manifest in ("package.json", "package-lock.json")
        )
        (shared_node_modules / ".package-lock.sha256").write_text(node_fingerprint + "\n", encoding="ascii")
        shared_python.parent.mkdir(parents=True)
        shared_python.touch()
        (shared_venv / ".requirements.sha256").write_text(
            f"{fingerprint} requirements-dev.txt\n" + hashlib.sha256((project / nested).read_text().replace("\r\n", "\n").encode()).hexdigest().upper() + f" {nested.as_posix()}\n", encoding="ascii"
        )
        setup(check=True)

        link = worktree / "node_modules"
        assert link.is_junction()
        assert link.resolve() == shared_node_modules.resolve()
        venv_link = worktree / ".venv"
        assert venv_link.is_junction()
        assert venv_link.resolve() == shared_venv.resolve()
        assert not npm_marker.exists()
        assert not py_marker.exists()
