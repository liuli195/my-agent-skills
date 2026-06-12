import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_USER_GUARD = REPO_ROOT / ".agents" / "skills" / "agent-guard" / "scripts" / "init_user_guard.py"
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
        [sys.executable, str(INIT_USER_GUARD), *args],
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


def test_user_guard_initialization_defaults_to_dry_run(tmp_path: Path) -> None:
    draft = tmp_path / "draft-profile"
    user_root = tmp_path / "user" / ".agents" / "guards"
    shutil.copytree(MINIMAL_PROFILE, draft)

    result = run_init(["--profile", str(draft), "--user-guard-root", str(user_root)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: dry_run" in result.stdout
    assert "authorization: missing" in result.stdout
    assert "project_guard_initialization: not_performed" in result.stdout
    assert "project_hooks: not_installed" in result.stdout
    assert "blocking_mode: not_enabled" in result.stdout
    assert not user_root.exists()


def test_authorized_user_guard_initialization_writes_valid_profile(tmp_path: Path) -> None:
    draft = tmp_path / "draft-profile"
    user_root = tmp_path / "user" / ".agents" / "guards"
    shutil.copytree(MINIMAL_PROFILE, draft)

    result = run_init(
        [
            "--profile",
            str(draft),
            "--user-guard-root",
            str(user_root),
            "--authorize-init",
        ]
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: initialized" in result.stdout
    assert "project_guard_initialization: not_performed" in result.stdout
    profile = user_root / "minimal-sample"
    assert (profile / "GUARD-MANIFEST.yaml").exists()
    assert (profile / "user-scope.md").exists()
    assert not (tmp_path / "target-project" / ".agents").exists()

    validation = run_validator(profile)
    assert validation.returncode == 0, validation.stdout + validation.stderr


def test_user_guard_initialization_requires_blocking_authorization(tmp_path: Path) -> None:
    draft = tmp_path / "draft-profile"
    user_root = tmp_path / "user" / ".agents" / "guards"
    shutil.copytree(MINIMAL_PROFILE, draft)
    manifest = draft / "GUARD-MANIFEST.yaml"
    guard_points = draft / "guard-points.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("mode: warn", "mode: block"), encoding="utf-8")
    guard_points.write_text(
        guard_points.read_text(encoding="utf-8").replace("mode: warn", "mode: block"),
        encoding="utf-8",
    )

    result = run_init(["--profile", str(draft), "--user-guard-root", str(user_root), "--authorize-init"])

    assert result.returncode == 0, result.stdout + result.stderr
    output_manifest = (user_root / "minimal-sample" / "GUARD-MANIFEST.yaml").read_text(encoding="utf-8")
    output_guard_points = (user_root / "minimal-sample" / "guard-points.yaml").read_text(encoding="utf-8")
    assert "mode: warn" in output_manifest
    assert "mode: block" not in output_manifest
    assert "mode: block" not in output_guard_points
