import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PROJECT_GUARD = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "init_project_guard.py"
UPGRADE_GUARD_RUNTIME = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "upgrade_guard_runtime.py"
MINIMAL_PROFILE = (
    REPO_ROOT
    / "skills"
    / "agent-guard"
    / "assets"
    / "templates"
    / "guard-profile"
    / "minimal"
)


def run_init(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INIT_PROJECT_GUARD), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_upgrade(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(UPGRADE_GUARD_RUNTIME), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def initialized_project(tmp_path: Path) -> Path:
    project = tmp_path / "target-project"
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)
    result = run_init(["--profile", str(draft), "--project", str(project), "--authorize-init"])
    assert result.returncode == 0, result.stdout + result.stderr
    return project


def test_upgrade_requires_existing_project_runtime(tmp_path: Path) -> None:
    project = tmp_path / "target-project"

    result = run_upgrade(["--project", str(project), "--authorize-upgrade"])

    assert result.returncode == 1
    assert "status: not_initialized" in result.stdout
    assert "reason: missing_runtime_dir" in result.stdout


def test_upgrade_defaults_to_dry_run_without_writing_runtime(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    runtime = project / ".agents" / "guard-runtime"
    runner = runtime / "guard_runner.py"
    version = runtime / "VERSION"
    runner.write_text("# old runtime\n", encoding="utf-8")
    version.write_text("0.0.1\n", encoding="utf-8")

    result = run_upgrade(["--project", str(project)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "authorization: missing" in result.stdout
    assert "current_version: 0.0.1" in result.stdout
    assert "target_version: 0.1.0" in result.stdout
    assert runner.read_text(encoding="utf-8") == "# old runtime\n"
    assert version.read_text(encoding="utf-8") == "0.0.1\n"


def test_authorized_upgrade_updates_runtime_and_preserves_profile_and_hooks(tmp_path: Path) -> None:
    project = initialized_project(tmp_path)
    runtime = project / ".agents" / "guard-runtime"
    runner = runtime / "guard_runner.py"
    adapter = runtime / "hook_event_adapter.py"
    version = runtime / "VERSION"
    profile_manifest = project / ".agents" / "guards" / "minimal-sample" / "GUARD-MANIFEST.yaml"
    codex_hooks = project / ".codex" / "hooks.json"

    runner.write_text("# old runtime\n", encoding="utf-8")
    adapter.write_text("# old adapter\n", encoding="utf-8")
    version.write_text("0.0.1\n", encoding="utf-8")
    codex_hooks.parent.mkdir(parents=True)
    codex_hooks.write_text('{"manual": true}\n', encoding="utf-8")
    profile_before = profile_manifest.read_text(encoding="utf-8")

    result = run_upgrade(["--project", str(project), "--authorize-upgrade"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: upgraded" in result.stdout
    assert "from_version: 0.0.1" in result.stdout
    assert "to_version: 0.1.0" in result.stdout
    assert "hook_adapter: updated" in result.stdout
    assert "profiles: preserved" in result.stdout
    assert "def main" in runner.read_text(encoding="utf-8")
    assert "def main" in adapter.read_text(encoding="utf-8")
    assert version.read_text(encoding="utf-8") == "0.1.0\n"
    assert profile_manifest.read_text(encoding="utf-8") == profile_before
    assert codex_hooks.read_text(encoding="utf-8") == '{"manual": true}\n'
