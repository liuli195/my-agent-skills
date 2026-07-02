import contextlib
import importlib.util
import io
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SKILL = REPO_ROOT / "plugins" / "agent-guard" / "skills" / "agent-guard"
INIT_USER_GUARD = PLUGIN_SKILL / "scripts" / "init_user_guard.py"
VALIDATOR = PLUGIN_SKILL / "scripts" / "validate_guard_profile.py"
MINIMAL_PROFILE = PLUGIN_SKILL / "assets" / "templates" / "guard-profile" / "minimal"
_INIT_MODULE = None
_VALIDATOR_MODULE = None


def load_script_module(path: Path, name: str):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_main(module, script: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.chdir(REPO_ROOT), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            returncode = int(module.main(args))
        except SystemExit as error:
            returncode = error.code if isinstance(error.code, int) else 1
    return subprocess.CompletedProcess(
        [sys.executable, str(script), *args],
        returncode,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def init_module():
    global _INIT_MODULE
    if _INIT_MODULE is None:
        _INIT_MODULE = load_script_module(INIT_USER_GUARD, "init_user_guard_for_tests")
    return _INIT_MODULE


def validator_module():
    global _VALIDATOR_MODULE
    if _VALIDATOR_MODULE is None:
        _VALIDATOR_MODULE = load_script_module(VALIDATOR, "validate_guard_profile_for_init_user_tests")
    return _VALIDATOR_MODULE


def run_init(args: list[str]) -> subprocess.CompletedProcess[str]:
    return run_main(init_module(), INIT_USER_GUARD, args)


def run_validator(profile_path: Path) -> subprocess.CompletedProcess[str]:
    return run_main(validator_module(), VALIDATOR, [str(profile_path)])


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
