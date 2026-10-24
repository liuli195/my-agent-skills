"""One public bootstrap/binding smoke, without dependency downloads."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins/data-store/skills/data-store"


class TestBootstrap:
    @pytest.mark.skipif(os.name == "nt", reason="Linux bootstrap; Windows has its junction adapter")
    def test_public_bootstrap_reuses_binding_and_updates_source_without_losing_data(self, tmp_path):
        root, project = tmp_path / "managed", tmp_path / "project"
        project.mkdir()

        def git(directory, *arguments):
            result = subprocess.run(["git", "-C", str(directory), *arguments],
                                    text=True, capture_output=True)
            assert result.returncode == 0, result.stdout + result.stderr
            return result.stdout.strip()

        git(project, "init", "-q")
        git(project, "remote", "add", "origin", "https://github.com/owner/project.git")
        (project / ".gitignore").write_text(".venv/\n.local/project-environment.json\ndata/\n")
        git(project, "add", ".gitignore")
        git(project, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.com",
            "commit", "-qm", "fixture")
        python = project / ".venv/bin/python"
        python.parent.mkdir(parents=True)
        python.symlink_to(sys.executable)
        (project / ".local").mkdir()
        (project / ".local/project-environment.json").write_text(json.dumps({
            "inputs": {}, "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        }))
        data = project / "data/keep.txt"
        data.parent.mkdir()
        data.write_text("existing business data", encoding="utf-8")
        source = root / "sources/own-skills"
        installed = source / "plugins/data-store/skills/data-store"
        shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
        git(source, "init", "-q")
        git(source, "remote", "add", "origin", "https://github.com/liuli195/my-agent-skills.git")
        git(source, "add", ".")
        git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.com",
            "commit", "-qm", "fixture")
        (root / "installed.json").write_text(json.dumps({"sources": {"own-skills": {
            "repo": "liuli195/my-agent-skills", "ref": "vfixture",
            "commit": git(source, "rev-parse", "HEAD"),
        }}, "npm": {}}))
        manifest = tmp_path / "environment.json"
        manifest.write_text(json.dumps({
            "sources": [{"name": "own-skills", "repo": "liuli195/my-agent-skills", "ref": "vfixture",
                         "paths": ["plugins/data-store"]}],
            "npm": [], "optional_skills": ["data-store"],
            "projects": {"owner/project": {"requirements": [], "npm": False, "skills": ["data-store"]}},
        }))
        arguments = [sys.executable, str(ROOT / "scripts/cloud_bootstrap.py"), "init",
                     "--root", str(root), "--manifest", str(manifest), "--project", str(project)]
        binding = project / ".local/skills/data-store"
        for _ in range(2):
            result = subprocess.run(arguments, text=True, capture_output=True)
            assert result.returncode == 0, result.stdout + result.stderr
            assert "reused" in result.stdout
            assert binding.resolve() == installed.resolve()
        replacement = tmp_path / "new/data-store"
        shutil.copytree(installed, replacement, ignore=shutil.ignore_patterns("__pycache__"))
        result = subprocess.run(
            [sys.executable, str(replacement / "scripts/project_binding.py"), "update",
             "--project", str(project), "--from", str(installed)],
            text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert binding.resolve() == replacement.resolve()
        assert (installed / "scripts/data_store.py").is_file()
        assert (replacement / "scripts/data_store.py").is_file()
        assert data.read_text(encoding="utf-8") == "existing business data"
        assert git(project, "status", "--porcelain") == ""
