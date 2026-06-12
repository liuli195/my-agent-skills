import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
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


def run_validator(profile_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(profile_path)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_minimal_guard_profile_passes_validation() -> None:
    result = run_validator(MINIMAL_PROFILE)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "通过：Guard Profile（守卫画像）校验" in result.stdout
    for category in [
        "manifest",
        "target_model",
        "activation_model",
        "subject_resolver",
        "execution_model",
        "observation_model",
        "state_machine",
        "guard_points",
        "artifacts",
        "hook_bindings",
        "brief_template",
        "validation_plan",
    ]:
        assert f"已检查：{category}" in result.stdout


def test_missing_required_file_reports_category_and_fix(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "target-model.yaml").unlink()

    result = run_validator(profile)

    assert result.returncode == 1
    assert "失败：Guard Profile（守卫画像）校验未通过" in result.stdout
    assert "category=target_model field=target-model.yaml" in result.stdout
    assert "把 target-model.yaml 添加到 Guard Profile（守卫画像）目录" in result.stdout


def test_activation_initial_state_must_reference_state_machine_state(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    activation_model = profile / "activation-model.yaml"
    activation_model.write_text(
        activation_model.read_text(encoding="utf-8").replace(
            "initial_state: open", "initial_state: missing_state"
        ),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=activation_model field=activation.initial_state" in result.stdout
    assert "引用了 `missing_state`" in result.stdout
    assert "state_machine.states" in result.stdout


def test_guard_point_check_artifact_must_reference_defined_artifact(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "guard-points.yaml").write_text(
        """
guard_points:
  - id: completion_note_present
    description: 引用缺失产物的守卫点。
    mode: warn
    checks:
      - id: missing_artifact_exists
        type: artifact_exists
        artifact: missing_artifact
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=guard_points" in result.stdout
    assert "field=guard_points.completion_note_present.checks.missing_artifact_exists.artifact" in result.stdout
    assert "引用了 `missing_artifact`" in result.stdout
    assert "artifacts" in result.stdout


def test_hook_binding_requires_source_trigger_and_event_type(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    shutil.copytree(MINIMAL_PROFILE, profile)
    (profile / "hook-bindings.yaml").write_text(
        """
hook_bindings:
  - id: manual-close
    transitions:
      - close_after_note
    guard_points:
      - completion_note_present
""".lstrip(),
        encoding="utf-8",
    )

    result = run_validator(profile)

    assert result.returncode == 1
    assert "category=hook_bindings" in result.stdout
    assert "field=hook_bindings.manual-close.source" in result.stdout
    assert "field=hook_bindings.manual-close.trigger_event" in result.stdout
    assert "field=hook_bindings.manual-close.event_type" in result.stdout
