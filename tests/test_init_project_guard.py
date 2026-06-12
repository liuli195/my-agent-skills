import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PROJECT_GUARD = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "init_project_guard.py"
VALIDATOR = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "validate_guard_profile.py"
MINIMAL_PROFILE = (
    REPO_ROOT
    / ".agents"
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


def run_validator(profile_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(profile_path)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_verified_guard_profile_initializes_project_runtime_and_profile(tmp_path: Path) -> None:
    project = tmp_path / "target-project"
    project.mkdir()
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)

    guarded_target = project / "guarded-workflow.md"
    guarded_target.write_text("# 被守卫流程\n\n原文保持不变。\n", encoding="utf-8")
    before = guarded_target.read_text(encoding="utf-8")
    target_model = draft / "target-model.yaml"
    target_model.write_text(
        target_model.read_text(encoding="utf-8").replace("source: bundled-template", f"source: {guarded_target}"),
        encoding="utf-8",
    )

    result = run_init(["--profile", str(draft), "--project", str(project), "--authorize-init"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: initialized" in result.stdout
    assert guarded_target.read_text(encoding="utf-8") == before

    runtime_dir = project / ".agents" / "guard-runtime"
    profile_dir = project / ".agents" / "guards" / "minimal-sample"
    assert (runtime_dir / "VERSION").exists()
    assert (runtime_dir / "RUNTIME-MANIFEST.yaml").exists()
    assert (runtime_dir / "requirements.txt").exists()
    assert (runtime_dir / "guard_runner.py").exists()
    assert (runtime_dir / "README.md").exists()
    assert (profile_dir / "GUARD-MANIFEST.yaml").exists()
    assert (profile_dir / "validation-plan.md").exists()
    assert (profile_dir / "hook-install-plan.md").exists()

    validation = run_validator(profile_dir)
    assert validation.returncode == 0, validation.stdout + validation.stderr
    assert not (project / ".codex" / "hooks.json").exists()
    assert not (project / ".githooks").exists()
    assert not (project / ".local").exists()


def test_existing_guard_profile_aborts_without_overwriting(tmp_path: Path) -> None:
    project = tmp_path / "target-project"
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)

    first = run_init(["--profile", str(draft), "--project", str(project), "--authorize-init"])
    assert first.returncode == 0, first.stdout + first.stderr

    profile_manifest = project / ".agents" / "guards" / "minimal-sample" / "GUARD-MANIFEST.yaml"
    profile_manifest.write_text("manual edit\n", encoding="utf-8")

    second = run_init(["--profile", str(draft), "--project", str(project), "--authorize-init"])

    assert second.returncode == 1
    assert "status: exists" in second.stdout
    assert "action: abort" in second.stdout
    assert profile_manifest.read_text(encoding="utf-8") == "manual edit\n"


def test_initialization_does_not_enable_blocking_mode_by_default(tmp_path: Path) -> None:
    project = tmp_path / "target-project"
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)
    manifest = draft / "GUARD-MANIFEST.yaml"
    guard_points = draft / "guard-points.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("mode: warn", "mode: block"),
        encoding="utf-8",
    )
    guard_points.write_text(
        guard_points.read_text(encoding="utf-8")
        .replace("mode: warn", "mode: block")
        .replace("on_fail: warn", "on_fail: block"),
        encoding="utf-8",
    )

    result = run_init(["--profile", str(draft), "--project", str(project), "--authorize-init"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "blocking_mode: not_enabled" in result.stdout
    output_manifest = (project / ".agents" / "guards" / "minimal-sample" / "GUARD-MANIFEST.yaml").read_text(
        encoding="utf-8"
    )
    output_guard_points = (project / ".agents" / "guards" / "minimal-sample" / "guard-points.yaml").read_text(
        encoding="utf-8"
    )
    assert "mode: warn" in output_manifest
    assert "mode: block" not in output_manifest
    assert "mode: block" not in output_guard_points
    assert "on_fail: block" not in output_guard_points
    assert "on_error: block" not in output_guard_points


def test_initialization_can_enable_blocking_mode_with_explicit_authorization(tmp_path: Path) -> None:
    project = tmp_path / "target-project"
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)
    manifest = draft / "GUARD-MANIFEST.yaml"
    guard_points = draft / "guard-points.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("mode: warn", "mode: block"),
        encoding="utf-8",
    )
    guard_points.write_text(
        guard_points.read_text(encoding="utf-8").replace("mode: warn", "mode: block"),
        encoding="utf-8",
    )

    result = run_init(
        [
            "--profile",
            str(draft),
            "--project",
            str(project),
            "--authorize-init",
            "--authorize-blocking",
        ]
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "blocking_mode: enabled" in result.stdout
    output_manifest = (project / ".agents" / "guards" / "minimal-sample" / "GUARD-MANIFEST.yaml").read_text(
        encoding="utf-8"
    )
    output_guard_points = (project / ".agents" / "guards" / "minimal-sample" / "guard-points.yaml").read_text(
        encoding="utf-8"
    )
    assert "mode: block" in output_manifest
    assert "mode: block" in output_guard_points


def test_initialization_defaults_to_dry_run_without_writing_project(tmp_path: Path) -> None:
    project = tmp_path / "target-project"
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)

    result = run_init(["--profile", str(draft), "--project", str(project)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "authorization: missing" in result.stdout
    assert "hook_installation: not_installed" in result.stdout
    assert "blocking_mode: not_enabled" in result.stdout
    assert not (project / ".agents").exists()
    assert not (project / ".local").exists()
