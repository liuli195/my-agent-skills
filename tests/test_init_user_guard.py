import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_USER_GUARD = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "init_user_guard.py"
VALIDATOR = REPO_ROOT / "skills" / "agent-guard" / "scripts" / "validate_guard_profile.py"
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


def test_user_guard_initialization_rejects_deprecated_manifest_mode(tmp_path: Path) -> None:
    draft = tmp_path / "draft-profile"
    user_root = tmp_path / "user" / ".agents" / "guards"
    shutil.copytree(MINIMAL_PROFILE, draft)
    manifest = draft / "GUARD-MANIFEST.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "mode: warn\n", encoding="utf-8")

    result = run_init(["--profile", str(draft), "--user-guard-root", str(user_root), "--authorize-init"])

    assert result.returncode == 1
    assert "status: validation_failed" in result.stdout
    assert "category: manifest" in result.stdout
    assert "field: mode" in result.stdout
    assert not user_root.exists()


def test_user_guard_initialization_requires_extra_authorization_for_deny_permissions(tmp_path: Path) -> None:
    draft = tmp_path / "draft-profile"
    user_root = tmp_path / "user" / ".agents" / "guards"
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

    blocked = run_init(
        [
            "--profile",
            str(draft),
            "--user-guard-root",
            str(user_root),
            "--authorize-init",
        ]
    )

    assert blocked.returncode == 1
    assert "status: authorization_required" in blocked.stdout
    assert "authorization: deny_permissions_missing" in blocked.stdout
    assert not user_root.exists()

    allowed = run_init(
        [
            "--profile",
            str(draft),
            "--user-guard-root",
            str(user_root),
            "--authorize-init",
            "--authorize-deny-permissions",
        ]
    )

    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert "status: initialized" in allowed.stdout
