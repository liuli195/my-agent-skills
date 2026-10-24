from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.test_build_and_verify_plugin import (
    FakeRunner, completed, write_runner_config, run_check,
    load_build_and_verify_runner_module, load_build_and_verify_module,
    read_json, write_json, git, command_that_logs,
    run_build_and_verify, run_build_and_verify_subprocess,
    BUILD_AND_VERIFY_SCRIPT, REPO_ROOT,
)
from tests.test_setup_worktree_script import normalize_powershell_output

SCRIPT = REPO_ROOT / "scripts" / "setup-worktree.ps1"


class TestWorkspace:
    def test_build_and_verify_performance_report_replaces_atomically(self, 
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        write_runner_config(
            project,
            verify_checks=[{"id": "verify", "command": ["verify"], "inputs": []}],
        )
        path_type = type(project)
        original_replace = path_type.replace
        replacements: list[tuple[str, str]] = []

        def track_replace(self, target):
            replacements.append((self.name, Path(target).name))
            return original_replace(self, target)

        monkeypatch.setattr(path_type, "replace", track_replace)

        result = run_check(
            project,
            "verify",
            "--full",
            "--performance-report",
            runner=FakeRunner(),
            changed_files=[],
        )

        assert result.returncode == 0
        assert (".performance-report.json.tmp", "performance-report.json") in replacements


    def test_build_and_verify_cache_store_writes_temp_file_before_replace(self, 
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = load_build_and_verify_module()
        runner = module._runner()
        project = tmp_path / "project"
        project.mkdir()
        cache_dir = project / ".build-and-verify" / "cache"
        path_type = type(project)
        original_write_text = path_type.write_text

        def tracking_write_text(self, *args, **kwargs):
            assert self.name != "cache-key.json"
            return original_write_text(self, *args, **kwargs)

        monkeypatch.setattr(path_type, "write_text", tracking_write_text)

        runner._cache_store(project, "cache-key", {"id": "cache-check"})

        assert read_json(cache_dir / "cache-key.json") == {"status": "passed", "id": "cache-check"}


    def test_build_and_verify_non_git_project_uses_filesystem_scan(self, 
        tmp_path: Path,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        (project / "src").mkdir()
        (project / "docs").mkdir()
        (project / "src" / "app.py").write_text("changed\n", encoding="utf-8")
        (project / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
        write_json(
            project / ".build-and-verify" / "config.json",
            {
                "version": 1,
                "build": {"checks": []},
                "verify": {
                    "checks": [
                        {
                            "id": "verify-src",
                            "command": command_that_logs("verify-src"),
                            "paths": ["src/**"],
                            "inputs": ["src"],
                        },
                        {
                            "id": "verify-docs",
                            "command": command_that_logs("verify-docs"),
                            "paths": ["docs/**"],
                            "inputs": ["docs"],
                        },
                    ]
                },
            },
        )

        verify = run_check(project, "verify")

        assert verify.returncode == 0, verify.stdout + verify.stderr
        assert "checked: verify-src, verify-docs" in verify.stdout
        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
            "verify-src",
            "verify-docs",
        ]


    def test_build_and_verify_preparation_reuses_inputs_without_changing_cache_keys(self, 
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()  # Git output is supplied at the process boundary.
        (project / "src").mkdir()
        input_file = project / "src" / "input.txt"
        input_file.write_text("stable", encoding="utf-8")
        write_runner_config(project, verify_checks=[
            {"id": "first", "command": ["first"], "inputs": ["src", "*.txt"]},
            {"id": "second", "command": ["second"], "inputs": [r".\src", "**/*.txt"]},
        ])
        reads: list[Path] = []
        git_queries: list[str] = []
        cache_writes: list[Path] = []
        cache_directory = project / ".build-and-verify/cache"
        original_open = Path.open
        original_replace = Path.replace

        def read(path: Path, mode="r", *args, **kwargs):
            if mode == "rb" and path == input_file:
                reads.append(path)
            return original_open(path, mode, *args, **kwargs)

        def query(command, **kwargs):
            assert command[:2] == ["git", "ls-files"] and kwargs["cwd"] == project
            git_queries.append(command[-1])
            return completed(command, stdout="src/input.txt\0")

        def replace(path: Path, target):
            if Path(target).parent == cache_directory:
                cache_writes.append(Path(target))
            return original_replace(path, target)

        monkeypatch.setattr(Path, "open", read)
        monkeypatch.setattr(Path, "replace", replace)
        monkeypatch.setattr(subprocess, "run", query)
        monkeypatch.setenv("CI", "false")
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        # The unchanged cloud path writes keys without preparation reuse.
        original = run_check(project, "verify", "--execution-context", "cloud",
            changed_files=["src/input.txt"])
        assert original.returncode == 0, original.stdout + original.stderr
        original_keys = list(cache_writes)
        assert len(set(original_keys)) == 2
        assert all(path.is_file() for path in original_keys)
        reads.clear()
        git_queries.clear()
        runner = FakeRunner()
        result = run_check(project, "verify", "--execution-context", "local",
            runner=runner, changed_files=["src/input.txt"])
        assert result.returncode == 0, result.stdout + result.stderr
        output = result.stdout
        assert "cache-hit: first" in output and "cache-hit: second" in output
        assert not runner.calls
        assert cache_writes == original_keys
        assert len(reads) == 3  # One shared directory, two distinct glob inputs.
        assert git_queries == ["src", "."]


    def test_build_and_verify_preparation_snapshot_is_not_reused_for_execution_or_next_call(self, 
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        input_file = project / "input.txt"
        input_file.write_text("first", encoding="utf-8")
        original_stat = input_file.stat()
        write_runner_config(project, verify_checks=[
            {"id": "modify", "command": ["modify"], "inputs": []},
            {"id": "target", "command": ["target"], "inputs": ["input.txt"]},
        ])
        monkeypatch.setenv("CI", "false")
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        commands = FakeRunner()

        def execute(command, **kwargs):
            if command == ["modify"]:
                # All preparation finished before the first check runs.
                input_file.write_text("other", encoding="utf-8")
                os.utime(input_file, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            return commands(command, **kwargs)

        first = run_check(project, "verify", "--execution-context", "local",
            runner=execute, changed_files=["input.txt"])
        second = run_check(project, "verify", "--execution-context", "local",
            runner=execute, changed_files=["input.txt"])
        assert first.returncode == second.returncode == 0
        assert commands.calls == [["modify"], ["target"]]
        assert "cache-hit: target" in second.stdout

        input_file.write_text("third", encoding="utf-8")
        os.utime(input_file, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        third = run_check(project, "verify", "--execution-context", "local",
            runner=execute, changed_files=["input.txt"])
        assert third.returncode == 0, third.stdout + third.stderr
        assert "cache-hit: target" not in third.stdout
        assert commands.calls == [["modify"], ["target"], ["target"]]


    def test_build_and_verify_preparation_does_not_memoize_read_errors(self, 
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        input_file = project / "input.txt"
        input_file.write_text("input", encoding="utf-8")
        write_runner_config(project, verify_checks=[
            {"id": name, "command": [name], "inputs": ["input.txt"]}
            for name in ("first", "second")
        ])
        original_open = Path.open
        reads = []
        cache_writes = []

        def read(path: Path, mode="r", *args, **kwargs):
            if mode == "w" and path.parent == project / ".build-and-verify/cache":
                cache_writes.append(path)
            if path == input_file and mode == "rb":
                reads.append(path)
                raise PermissionError("read denied")
            return original_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(Path, "open", read)
        monkeypatch.setenv("CI", "false")
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        runner = FakeRunner()
        result = run_check(project, "verify", "--execution-context", "local",
            runner=runner, changed_files=["input.txt"])
        assert result.returncode != 0
        assert result.stderr.count("read denied") == 2
        assert len(reads) == 2 and not runner.calls
        assert not cache_writes


    @pytest.mark.parametrize("execution_context", ["cloud", "local"])
    def test_build_and_verify_runner_cache_misses_when_input_is_deleted(self, 
        tmp_path: Path, execution_context: str,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        (project / "src").mkdir()
        input_file = project / "src" / "input.txt"
        input_file.write_text("base\n", encoding="utf-8")
        write_json(
            project / ".build-and-verify" / "config.json",
            {
                "version": 1,
                "build": {"checks": []},
                "verify": {
                    "checks": [
                        {
                            "id": "deleted-input",
                            "command": command_that_logs("deleted-input"),
                            "inputs": ["src/input.txt"],
                        }
                    ]
                },
            },
        )

        input_file.write_text("changed\n", encoding="utf-8")
        first = run_check(project, "verify", execution_context=execution_context, changed_files=["src/input.txt"])
        input_file.unlink()
        second = run_check(project, "verify", execution_context=execution_context, changed_files=["src/input.txt"])

        assert first.returncode == 0, first.stdout + first.stderr
        assert second.returncode == 0, second.stdout + second.stderr
        assert "cache-hit:" not in second.stdout
        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
            "deleted-input",
            "deleted-input",
        ]


    @pytest.mark.parametrize("execution_context", ["cloud", "local"])
    def test_build_and_verify_runner_glob_inputs_track_visible_matching_files(self, 
        tmp_path: Path, execution_context: str,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        tracked = project / "requirements.txt"
        tracked.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "requirements.txt"], cwd=project, check=True)
        write_runner_config(
            project,
            verify_checks=[
                {
                    "id": "glob-inputs",
                    "command": command_that_logs("glob-inputs"),
                    "paths": ["requirements*.txt"],
                    "inputs": ["requirements*.txt"],
                }
            ],
        )

        first = run_check(project, "verify", execution_context=execution_context, changed_files=["requirements.txt"])
        unchanged = run_check(project, "verify", execution_context=execution_context, changed_files=["requirements.txt"])
        tracked.write_text("changed\n", encoding="utf-8")
        changed = run_check(project, "verify", execution_context=execution_context, changed_files=["requirements.txt"])
        added = project / "requirements-dev.txt"
        added.write_text("dev\n", encoding="utf-8")
        addition = run_check(project, "verify", execution_context=execution_context, changed_files=["requirements-dev.txt"])
        tracked.write_text("changed-again\n", encoding="utf-8")
        changed_with_addition = run_check(project, "verify", execution_context=execution_context, changed_files=["requirements.txt"])
        added.unlink()
        deletion = run_check(project, "verify", execution_context=execution_context, changed_files=["requirements.txt"])

        assert all(
            result.returncode == 0
            for result in (first, unchanged, changed, addition, changed_with_addition, deletion)
        )
        assert "cache-hit: glob-inputs" in unchanged.stdout
        assert "cache-hit:" not in changed.stdout
        assert "cache-hit:" not in addition.stdout
        assert "cache-hit:" not in changed_with_addition.stdout
        assert "cache-hit:" not in deletion.stdout
        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
            "glob-inputs",
            "glob-inputs",
            "glob-inputs",
            "glob-inputs",
            "glob-inputs",
        ]


    def test_build_and_verify_runner_accepts_future_glob_inputs(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        (project / "src").mkdir()
        (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
        write_runner_config(
            project,
            verify_checks=[
                {
                    "id": "future-glob-input",
                    "command": command_that_logs("future-glob-input"),
                    "paths": ["src/app.txt"],
                    "inputs": ["future-*.txt"],
                }
            ],
        )

        first = run_check(project, "verify", changed_files=["src/app.txt"])
        unchanged = run_check(project, "verify", changed_files=["src/app.txt"])
        (project / "future-config.txt").write_text("future\n", encoding="utf-8")
        matched = run_check(project, "verify", changed_files=["src/app.txt"])

        assert all(result.returncode == 0 for result in (first, unchanged, matched))
        assert "warning" not in first.stdout + first.stderr
        assert "cache-hit: future-glob-input" in unchanged.stdout
        assert "cache-hit:" not in matched.stdout
        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
            "future-glob-input",
            "future-glob-input",
        ]


    @pytest.mark.parametrize("execution_context", ["cloud", "local"])
    def test_build_and_verify_runner_glob_inputs_ignore_ignored_files_and_normalize_separators(self, 
        tmp_path: Path, execution_context: str,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        (project / ".gitignore").write_text("requirements-ignored.txt\n", encoding="utf-8")
        tracked = project / "requirements.txt"
        tracked.write_text("tracked\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore", "requirements.txt"], cwd=project, check=True)
        visible = project / "requirements-dev.txt"
        ignored = project / "requirements-ignored.txt"
        visible.write_text("visible-v1\n", encoding="utf-8")
        ignored.write_text("ignored-v1\n", encoding="utf-8")
        check = {
            "id": "glob-visible",
            "command": command_that_logs("glob-visible"),
            "paths": ["requirements*.txt"],
            "inputs": [r".\requirements*.txt"],
        }
        write_runner_config(project, verify_checks=[check])

        first = run_check(project, "verify", execution_context=execution_context, changed_files=["requirements.txt"])
        ignored.write_text("ignored-v2\n", encoding="utf-8")
        ignored_change = run_check(project, "verify", execution_context=execution_context, changed_files=["requirements.txt"])
        visible.write_text("visible-v2\n", encoding="utf-8")
        visible_change = run_check(project, "verify", execution_context=execution_context, changed_files=["requirements.txt"])
        check.update(id="literal-ignored", inputs=["requirements-ignored.txt"])
        write_runner_config(project, verify_checks=[check])
        literal_first = run_check(project, "verify", execution_context=execution_context, changed_files=["requirements.txt"])
        ignored.write_text("ignored-v3\n", encoding="utf-8")
        literal_change = run_check(project, "verify", execution_context=execution_context, changed_files=["requirements.txt"])

        assert all(
            result.returncode == 0
            for result in (first, ignored_change, visible_change, literal_first, literal_change)
        )
        assert "cache-hit: glob-visible" in ignored_change.stdout
        assert "cache-hit:" not in visible_change.stdout
        assert "cache-hit:" not in literal_change.stdout
        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
            "glob-visible",
            "glob-visible",
            "glob-visible",
            "glob-visible",
        ]


    def test_build_and_verify_runner_default_cache_key_tracks_glob_path_contents(self, 
        tmp_path: Path,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        (project / "src").mkdir()
        app_path = project / "src" / "app.txt"
        app_path.write_text("first\n", encoding="utf-8")
        write_json(
            project / ".build-and-verify" / "config.json",
            {
                "version": 1,
                "build": {"checks": []},
                "verify": {
                    "checks": [
                        {
                            "id": "glob-default-inputs",
                            "command": command_that_logs("glob-default-inputs"),
                            "paths": ["src/**"],
                        }
                    ]
                },
            },
        )

        first = run_check(project, "verify", changed_files=["src/app.txt"])
        app_path.write_text("second\n", encoding="utf-8")
        second = run_check(project, "verify", changed_files=["src/app.txt"])

        assert first.returncode == 0, first.stdout + first.stderr
        assert second.returncode == 0, second.stdout + second.stderr
        assert "cache-hit: glob-default-inputs" not in second.stdout
        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
            "glob-default-inputs",
            "glob-default-inputs",
        ]


    def test_build_and_verify_pathless_check_skips_clean_git_worktree(self, 
        tmp_path: Path,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        write_json(
            project / ".build-and-verify" / "config.json",
            {
                "version": 1,
                "build": {"checks": []},
                "verify": {
                    "checks": [
                        {
                            "id": "pathless",
                            "command": command_that_logs("pathless"),
                        }
                    ]
                },
            },
        )

        verify = run_check(project, "verify", changed_files=[])

        assert verify.returncode == 0, verify.stdout + verify.stderr
        assert "checked:" in verify.stdout
        assert "checked: pathless" not in verify.stdout
        assert not (project / "run.log").exists()


    def test_build_and_verify_runner_default_check_cache_key_tracks_dirty_file_contents(self, 
        tmp_path: Path,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        dirty_file = project / "dirty.txt"
        dirty_file.write_text("base\n", encoding="utf-8")
        write_json(
            project / ".build-and-verify" / "config.json",
            {
                "version": 1,
                "build": {"checks": []},
                "verify": {
                    "checks": [
                        {
                            "id": "default-dirty-check",
                            "command": command_that_logs("default-dirty-check"),
                        }
                    ]
                },
            },
        )

        dirty_file.write_text("first\n", encoding="utf-8")
        first = run_check(project, "verify", changed_files=["dirty.txt"])
        dirty_file.write_text("second\n", encoding="utf-8")
        second = run_check(project, "verify", changed_files=["dirty.txt"])

        assert first.returncode == 0, first.stdout + first.stderr
        assert second.returncode == 0, second.stdout + second.stderr
        assert "cache-hit: default-dirty-check" not in second.stdout
        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
            "default-dirty-check",
            "default-dirty-check",
        ]


    def test_build_and_verify_runner_ignores_nonmatching_external_glob_links(self, 
        tmp_path: Path,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        (project / "outside-link.txt").symlink_to(outside)
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        (project / "requirements.txt").write_text("requirements\n", encoding="utf-8")
        (project / "src").mkdir()
        (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
        write_runner_config(
            project,
            verify_checks=[
                {
                    "id": "glob-in-project-input",
                    "command": command_that_logs("glob-in-project-input"),
                    "paths": ["src/**"],
                    "inputs": ["requirements*.txt"],
                }
            ],
        )

        result = run_check(project, "verify", changed_files=["src/app.txt"])

        assert result.returncode == 0, result.stdout + result.stderr
        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
            "glob-in-project-input"
        ]


    @pytest.mark.parametrize("execution_context", ["cloud", "local"])
    def test_build_and_verify_runner_rejects_glob_match_outside_project(self, 
        tmp_path: Path, execution_context: str,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        external_link = project / "outside-link.txt"
        external_link.symlink_to(outside)
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        (project / "src").mkdir()
        (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
        write_runner_config(
            project,
            verify_checks=[
                {
                    "id": "glob-outside-input",
                    "command": command_that_logs("glob-outside-input"),
                    "paths": ["src/**"],
                    "inputs": ["*.txt"],
                }
            ],
        )

        result = run_check(project, "verify", execution_context=execution_context, changed_files=["src/app.txt"])

        assert result.returncode != 0
        assert "invalid_input_path: *.txt" in result.stderr
        assert not (project / "run.log").exists()


    @pytest.mark.parametrize(
        "excluded_relative",
        [
            Path(".build-and-verify/cache/noise.txt"),
            Path(".git/noise.txt"),
            Path("src/__pycache__/noise.pyc"),
        ],
    )
    def test_build_and_verify_runner_directory_hash_ignores_generated_paths(self, 
        tmp_path: Path, excluded_relative: Path
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        (project / "src").mkdir()
        (project / "src" / "sample.txt").write_text("changed\n", encoding="utf-8")
        run_log = project / ".build-and-verify" / "cache" / "directory-hash-runs.txt"
        write_json(
            project / ".build-and-verify" / "config.json",
            {
                "version": 1,
                "build": {"checks": []},
                "verify": {
                    "checks": [
                        {
                            "id": "directory-hash",
                            "command": command_that_logs(
                                "directory-hash",
                                ".build-and-verify/cache/directory-hash-runs.txt",
                            ),
                            "paths": ["src/**"],
                            "inputs": ["."],
                        }
                    ]
                },
            },
        )

        first = run_check(project, "verify", changed_files=["src/sample.txt"])
        noise_path = project / excluded_relative
        noise_path.parent.mkdir(parents=True, exist_ok=True)
        noise_path.write_text("ignored\n", encoding="utf-8")
        second = run_check(project, "verify", changed_files=["src/sample.txt"])

        assert first.returncode == 0, first.stdout + first.stderr
        assert second.returncode == 0, second.stdout + second.stderr
        assert "cache-hit: directory-hash" in second.stdout
        assert run_log.read_text(encoding="utf-8").splitlines() == ["directory-hash"]


    @pytest.mark.parametrize("execution_context", ["cloud", "local"])
    def test_build_and_verify_runner_directory_hash_uses_git_visible_files(self, 
        tmp_path: Path, execution_context: str,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        (project / ".gitignore").write_text("src/ignored/\n", encoding="utf-8")
        (project / "src" / "ignored").mkdir(parents=True)
        tracked = project / "src" / "tracked.txt"
        visible = project / "src" / "visible.txt"
        ignored = project / "src" / "ignored" / "dependency.txt"
        tracked.write_text("tracked-v1\n", encoding="utf-8")
        visible.write_text("visible-v1\n", encoding="utf-8")
        ignored.write_text("ignored-v1\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore", "src/tracked.txt"], cwd=project, check=True)
        write_json(
            project / ".build-and-verify" / "config.json",
            {
                "version": 1,
                "build": {"checks": []},
                "verify": {
                    "checks": [
                        {
                            "id": "git-visible-directory",
                            "command": command_that_logs("git-visible-directory"),
                            "paths": ["src/**"],
                            "inputs": ["src"],
                        }
                    ]
                },
            },
        )

        first = run_check(project, "verify", execution_context=execution_context, changed_files=["src/tracked.txt"])
        ignored.write_text("ignored-v2\n", encoding="utf-8")
        ignored_change = run_check(project, "verify", execution_context=execution_context, changed_files=["src/tracked.txt"])
        visible.write_text("visible-v2\n", encoding="utf-8")
        visible_change = run_check(project, "verify", execution_context=execution_context, changed_files=["src/tracked.txt"])
        tracked.write_text("tracked-v2\n", encoding="utf-8")
        tracked_change = run_check(project, "verify", execution_context=execution_context, changed_files=["src/tracked.txt"])
        config = read_json(project / ".build-and-verify" / "config.json")
        config["verify"]["checks"][0].update(
            id="explicit-ignored-file",
            inputs=["src/ignored/dependency.txt"],
        )
        write_json(project / ".build-and-verify" / "config.json", config)
        explicit_first = run_check(project, "verify", execution_context=execution_context, changed_files=["src/tracked.txt"])
        ignored.write_text("ignored-v3\n", encoding="utf-8")
        explicit_change = run_check(project, "verify", execution_context=execution_context, changed_files=["src/tracked.txt"])

        assert first.returncode == 0, first.stdout + first.stderr
        assert ignored_change.returncode == 0, ignored_change.stdout + ignored_change.stderr
        assert "cache-hit: git-visible-directory" in ignored_change.stdout
        assert "cache-hit:" not in visible_change.stdout
        assert "cache-hit:" not in tracked_change.stdout
        assert explicit_first.returncode == 0, explicit_first.stdout + explicit_first.stderr
        assert "cache-hit:" not in explicit_change.stdout
        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
            "git-visible-directory",
            "git-visible-directory",
            "git-visible-directory",
            "git-visible-directory",
            "git-visible-directory",
        ]


    def test_build_and_verify_runner_reads_worktree_changed_files(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert run_build_and_verify("init", "--project", str(project)).returncode == 0
        write_json(
            project / ".build-and-verify" / "config.json",
            {
                "version": 1,
                "build": {"checks": []},
                "verify": {
                    "checks": [
                        {
                            "id": "staged-check",
                            "command": command_that_logs("staged-check"),
                            "paths": ["staged.txt"],
                            "inputs": ["staged.txt"],
                        },
                        {
                            "id": "unstaged-check",
                            "command": command_that_logs("unstaged-check"),
                            "paths": ["unstaged.txt"],
                            "inputs": ["unstaged.txt"],
                        },
                        {
                            "id": "untracked-check",
                            "command": command_that_logs("untracked-check"),
                            "paths": ["untracked.txt"],
                            "inputs": ["untracked.txt"],
                        },
                    ]
                },
            },
        )
        (project / "staged.txt").write_text("base\n", encoding="utf-8")
        (project / "unstaged.txt").write_text("base\n", encoding="utf-8")
        (project / "staged.txt").write_text("staged\n", encoding="utf-8")
        (project / "unstaged.txt").write_text("unstaged\n", encoding="utf-8")
        (project / "untracked.txt").write_text("untracked\n", encoding="utf-8")

        result = run_check(
            project,
            "verify",
            changed_files=["staged.txt", "unstaged.txt", "untracked.txt"],
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert "checked: staged-check, unstaged-check, untracked-check" in result.stdout
        assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
            "staged-check",
            "unstaged-check",
            "untracked-check",
        ]


    def test_build_and_verify_cli_baseline_uses_verification_worktree_and_explicit_range(self, 
        tmp_path: Path,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        assert git(project, "init", "-q").returncode == 0
        initialized = run_build_and_verify_subprocess("init", "--project", str(project))
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        assert git(project, "config", "user.name", "Test").returncode == 0
        assert git(project, "config", "user.email", "test@example.invalid").returncode == 0
        (project / "src").mkdir()
        (project / "src" / "app.py").write_text("base\n", encoding="utf-8")
        command = [
            sys.executable,
            "-c",
            "from pathlib import Path; p=Path('.build-and-verify/runs/baseline.log'); p.parent.mkdir(parents=True, exist_ok=True); p.open('a', encoding='utf-8').write('ran\\n')",
        ]
        write_runner_config(
            project,
            verify_checks=[
                {
                    "id": "verify.src",
                    "command": command,
                    "paths": ["src/**"],
                    "inputs": ["src/app.py"],
                },
                {
                    "id": "verify.base",
                    "command": command,
                    "paths": ["base-only.txt"],
                    "pr": False,
                },
            ],
        )
        assert git(project, "add", ".").returncode == 0
        assert git(project, "commit", "-m", "base").returncode == 0
        baseline = git(project, "rev-parse", "HEAD").stdout.strip()
        assert baseline
        main_branch = git(project, "branch", "--show-current").stdout.strip()
        assert main_branch
        assert git(project, "branch", "baseline", baseline).returncode == 0
        other = tmp_path / "other-worktree"
        assert git(project, "worktree", "add", str(other), "baseline").returncode == 0
        (other / "base-only.txt").write_text("base-only\n", encoding="utf-8")
        assert git(other, "add", "base-only.txt").returncode == 0
        assert git(other, "commit", "-m", "base-only").returncode == 0
        assert git(project, "branch", "side", baseline).returncode == 0
        assert git(project, "checkout", "side").returncode == 0
        (project / "docs").mkdir()
        (project / "docs" / "side.md").write_text("side\n", encoding="utf-8")
        assert git(project, "add", "docs/side.md").returncode == 0
        assert git(project, "commit", "-m", "side").returncode == 0
        assert git(project, "checkout", main_branch).returncode == 0
        (project / "src" / "app.py").write_text("committed change\n", encoding="utf-8")
        assert git(project, "add", "src/app.py").returncode == 0
        assert git(project, "commit", "-m", "change").returncode == 0
        assert git(project, "merge", "--no-ff", "side", "-m", "merge").returncode == 0
        assert git(project, "checkout", "--detach", "HEAD").returncode == 0
        (other / "unrelated.txt").write_text("other worktree\n", encoding="utf-8")

        verified = run_build_and_verify_subprocess(
            "verify",
            "--project",
            str(project),
            "--base",
            "baseline",
        )

        assert verified.returncode == 0, verified.stdout + verified.stderr
        assert "checked: verify.src" in verified.stdout
        assert "verify.base" not in verified.stdout
        assert "status: passed" in verified.stdout
        assert (project / ".build-and-verify" / "runs" / "baseline.log").read_text(
            encoding="utf-8"
        ).splitlines() == ["ran"]

        pr_verified = run_build_and_verify_subprocess(
            "verify", "--project", str(project), "--pr", "--base", "baseline"
        )
        assert pr_verified.returncode == 0, pr_verified.stdout + pr_verified.stderr
        assert "scene: pr" in pr_verified.stdout
        assert "excluded-by-pr: verify.base" in pr_verified.stdout
        assert "checked: verify.src" in pr_verified.stdout

        cached = run_build_and_verify_subprocess(
            "verify",
            "--project",
            str(project),
            "--base",
            "baseline",
        )
        assert cached.returncode == 0, cached.stdout + cached.stderr
        assert "cache-hit: verify.src" in cached.stdout
        assert "checked: verify.src" in cached.stdout
        assert "status: passed" in cached.stdout
        assert (project / ".build-and-verify" / "runs" / "baseline.log").read_text(
            encoding="utf-8"
        ).splitlines() == ["ran"]

        empty_base = git(project, "rev-parse", "HEAD").stdout.strip()
        empty = run_build_and_verify_subprocess(
            "verify", "--project", str(project), "--base", empty_base
        )
        assert empty.returncode == 0, empty.stdout + empty.stderr
        assert "status: skipped" in empty.stdout
        assert "reason: no_changed_files" in empty.stdout
        assert "status: passed" not in empty.stdout

        docs_base = empty_base
        (project / "docs" / "post-merge.md").write_text("docs\n", encoding="utf-8")
        assert git(project, "add", "docs/post-merge.md").returncode == 0
        assert git(project, "commit", "-m", "docs-only").returncode == 0
        unmatched = run_build_and_verify_subprocess(
            "verify", "--project", str(project), "--base", docs_base
        )
        assert unmatched.returncode == 0, unmatched.stdout + unmatched.stderr
        assert "status: skipped" in unmatched.stdout
        assert "reason: no_matching_checks" in unmatched.stdout
        assert "status: passed" not in unmatched.stdout

        invalid = run_build_and_verify_subprocess(
            "verify", "--project", str(project), "--base", "does-not-exist"
        )
        assert invalid.returncode != 0
        assert "invalid_baseline" in invalid.stderr
        assert "status: failed" in invalid.stdout

        full = run_build_and_verify_subprocess(
            "verify", "--project", str(project), "--full", "--base", "baseline"
        )
        assert full.returncode != 0
        assert "baseline_not_allowed_with_full" in full.stderr
        assert "status: failed" in full.stdout

        dirty_path = project / "dirty.txt"
        dirty_path.write_text("dirty\n", encoding="utf-8")
        dirty = run_build_and_verify_subprocess(
            "verify", "--project", str(project), "--base", "baseline"
        )
        assert dirty.returncode != 0
        assert "baseline_worktree_not_clean" in dirty.stderr
        assert "status: failed" in dirty.stdout
        dirty_path.unlink()


    @pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
    @pytest.mark.parametrize("shell_name", ["powershell", "pwsh"])
    def test_setup_worktree_script_links_shared_node_dependencies(self, 
        tmp_path: Path, shell_name: str
    ) -> None:
        shell = shutil.which(shell_name)
        if not shell:
            pytest.skip(f"{shell_name} executable is required")

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

        missing = setup()
        assert missing.returncode != 0
        assert not npm_marker.exists()
        assert not py_marker.exists()
        assert "Shared Node.js dependencies are missing" in normalize_powershell_output(missing)

        shared_node_modules.mkdir()
        stale_node = setup()
        assert stale_node.returncode != 0
        assert not npm_marker.exists()
        assert not py_marker.exists()
        assert "Shared Node.js dependencies are stale" in normalize_powershell_output(stale_node)

        node_fingerprint = "\n".join(
            f"{hashlib.sha256((project / manifest).read_text(encoding='utf-8').replace(chr(13) + chr(10), chr(10)).encode()).hexdigest().upper()} {manifest}"
            for manifest in ("package.json", "package-lock.json")
        )
        (shared_node_modules / ".package-lock.sha256").write_text(node_fingerprint + "\n", encoding="ascii")
        missing_python = setup()
        assert missing_python.returncode != 0
        assert not npm_marker.exists()
        assert not py_marker.exists()
        assert "Shared Python environment is missing" in normalize_powershell_output(missing_python)

        shared_python.parent.mkdir(parents=True)
        shared_python.touch()
        stale_python = setup()
        assert stale_python.returncode != 0
        assert not npm_marker.exists()
        assert not py_marker.exists()
        assert "Shared Python environment is stale" in normalize_powershell_output(stale_python)

        (shared_venv / ".requirements.sha256").write_text(
            f"{fingerprint} requirements-dev.txt\n" + hashlib.sha256((project / nested).read_text().replace("\r\n", "\n").encode()).hexdigest().upper() + f" {nested.as_posix()}\n", encoding="ascii"
        )
        setup(check=True)
        setup(check=True)

        link = worktree / "node_modules"
        assert link.is_junction()
        assert link.resolve() == shared_node_modules.resolve()
        venv_link = worktree / ".venv"
        assert venv_link.is_junction()
        assert venv_link.resolve() == shared_venv.resolve()
        assert not py_marker.exists()

        (worktree / "package.json").write_text("{}", encoding="utf-8")
        result = setup()
        assert result.returncode != 0
        assert not npm_marker.exists()
        assert not py_marker.exists()
        assert "do not match 'package.json'" in normalize_powershell_output(result)

        shutil.copy2(project / "package.json", worktree / "package.json")
        venv_link.rmdir()
        venv_link.mkdir()
        existing = setup()
        assert existing.returncode != 0
        assert not npm_marker.exists()
        assert not py_marker.exists()
        assert venv_link.is_dir() and not venv_link.is_junction()
        assert "already exists and does not link" in normalize_powershell_output(existing)
