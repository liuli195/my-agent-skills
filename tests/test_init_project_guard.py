import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SKILL = REPO_ROOT / "plugins" / "agent-guard" / "skills" / "agent-guard"
INIT_PROJECT_GUARD = PLUGIN_SKILL / "scripts" / "init_project_guard.py"
VALIDATOR = PLUGIN_SKILL / "scripts" / "validate_guard_profile.py"
MINIMAL_PROFILE = PLUGIN_SKILL / "assets" / "templates" / "guard-profile" / "minimal"


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


def test_verified_guard_profile_initializes_project_profile_without_runtime_copy(tmp_path: Path) -> None:
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
    assert not runtime_dir.exists()
    assert (profile_dir / "GUARD-MANIFEST.yaml").exists()
    assert (profile_dir / "validation-plan.md").exists()
    assert not (profile_dir / "hook-install-plan.md").exists()

    validation = run_validator(profile_dir)
    assert validation.returncode == 0, validation.stdout + validation.stderr
    assert "plugin_runtime: external_plugin" in result.stdout
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


def test_initialization_rejects_deprecated_manifest_mode(tmp_path: Path) -> None:
    project = tmp_path / "target-project"
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)
    manifest = draft / "GUARD-MANIFEST.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "mode: warn\n", encoding="utf-8")

    result = run_init(["--profile", str(draft), "--project", str(project), "--authorize-init"])

    assert result.returncode == 1
    assert "status: validation_failed" in result.stdout
    assert "category: manifest" in result.stdout
    assert "field: mode" in result.stdout
    assert not (project / ".agents").exists()


def test_initialization_rejects_removed_authorize_blocking_argument(tmp_path: Path) -> None:
    project = tmp_path / "target-project"
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)

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

    assert result.returncode == 2
    assert "unrecognized arguments: --authorize-blocking" in result.stderr


def test_initialization_requires_extra_authorization_for_deny_permissions(tmp_path: Path) -> None:
    project = tmp_path / "target-project"
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)
    state_machine = draft / "state-machine.yaml"
    state_machine.write_text(
        state_machine.read_text(encoding="utf-8").replace(
            "  - id: open\n    description: Guard Profile（守卫画像）已激活，正在等待必需 note（说明记录）。",
            """  - id: open
    description: Guard Profile（守卫画像）已激活，正在等待必需 note（说明记录）。
    permissions:
      default: deny""",
        ),
        encoding="utf-8",
    )

    blocked = run_init(["--profile", str(draft), "--project", str(project), "--authorize-init"])

    assert blocked.returncode == 1
    assert "status: authorization_required" in blocked.stdout
    assert "authorization: deny_permissions_missing" in blocked.stdout
    assert not (project / ".agents").exists()

    allowed = run_init(
        [
            "--profile",
            str(draft),
            "--project",
            str(project),
            "--authorize-init",
            "--authorize-deny-permissions",
        ]
    )

    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert "status: initialized" in allowed.stdout


def test_initialization_defaults_to_dry_run_without_writing_project(tmp_path: Path) -> None:
    project = tmp_path / "target-project"
    draft = tmp_path / "draft-profile"
    shutil.copytree(MINIMAL_PROFILE, draft)

    result = run_init(["--profile", str(draft), "--project", str(project)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "authorization: missing" in result.stdout
    assert "plugin_runtime: external_plugin" in result.stdout
    assert not (project / ".agents").exists()
    assert not (project / ".local").exists()
