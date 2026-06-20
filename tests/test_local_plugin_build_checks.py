import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check.py"


def load_check_module():
    spec = importlib.util.spec_from_file_location("repo_check", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_plugin(root: Path, name: str) -> Path:
    plugin = root / "plugins" / name
    write_json(
        plugin / ".claude-plugin" / "plugin.json",
        {
            "name": name,
            "version": "0.1.0",
            "description": f"{name} plugin",
            "skills": "./skills",
        },
    )
    write_json(
        plugin / ".codex-plugin" / "plugin.json",
        {
            "name": name,
            "version": "0.1.0",
            "description": f"{name} plugin",
            "skills": "./skills",
        },
    )
    (plugin / "skills" / name).mkdir(parents=True)
    (plugin / "skills" / name / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name}\n---\n",
        encoding="utf-8",
    )
    return plugin


def make_marketplace(root: Path, names: list[str]) -> None:
    write_json(
        root / ".claude-plugin" / "marketplace.json",
        {
            "name": "test-marketplace",
            "owner": {"name": "Test"},
            "plugins": [
                {
                    "name": name,
                    "source": f"./plugins/{name}",
                    "description": f"{name} plugin",
                }
                for name in names
            ],
        },
    )


def make_projection(root: Path, names: list[str]) -> None:
    projection = "\n".join(
        [
            "version: 1",
            "",
            "generators:",
            "  - path: .agents/plugins/marketplace.json",
            "    type: codex-marketplace",
            "    identity: codex",
            "    plugins:",
            *[f"      - {name}" for name in names],
            "",
        ]
    )
    (root / ".release-flow").mkdir(parents=True)
    (root / ".release-flow" / "projection.yaml").write_text(projection, encoding="utf-8")


def test_build_runs_claude_validation_for_marketplace_and_each_plugin(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_plugin(tmp_path, "beta")
    make_marketplace(tmp_path, ["alpha", "beta"])
    make_projection(tmp_path, ["alpha", "beta"])

    calls: list[tuple[list[str], Path]] = []

    def fake_run(command, cwd, text, capture_output, check):
        calls.append((command, cwd))
        return subprocess.CompletedProcess(command, 0, "ok", "")

    errors = module.run_build(tmp_path, runner=fake_run)

    assert errors == []
    assert calls == [
        (["claude", "plugin", "validate", "."], tmp_path),
        (["claude", "plugin", "validate", str(tmp_path / "plugins" / "alpha")], tmp_path),
        (["claude", "plugin", "validate", str(tmp_path / "plugins" / "beta")], tmp_path),
    ]
    assert all(cwd == tmp_path for _command, cwd in calls)
    assert all("--strict" not in command for command, _cwd in calls)


def test_build_rejects_marketplace_source_outside_repo(tmp_path: Path) -> None:
    module = load_check_module()
    make_marketplace(tmp_path, ["escape"])
    data = json.loads((tmp_path / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    data["plugins"][0]["source"] = "../outside"
    write_json(tmp_path / ".claude-plugin" / "marketplace.json", data)

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("source_outside_repo" in error for error in errors)


def test_build_reports_missing_claude_command(tmp_path: Path) -> None:
    module = load_check_module()
    make_projection(tmp_path, [])
    make_marketplace(tmp_path, [])

    def missing_claude(*args, **kwargs):
        raise FileNotFoundError("claude")

    errors = module.run_build(tmp_path, runner=missing_claude)

    assert any("missing_command: claude" in error for error in errors)


def test_build_reports_invalid_marketplace_entry(tmp_path: Path) -> None:
    module = load_check_module()
    make_projection(tmp_path, [])
    write_json(
        tmp_path / ".claude-plugin" / "marketplace.json",
        {
            "name": "test-marketplace",
            "owner": {"name": "Test"},
            "plugins": ["not-a-plugin"],
        },
    )

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("invalid_marketplace_entry" in error for error in errors)


def test_build_reports_duplicate_marketplace_plugin_name(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha", "alpha"])
    make_projection(tmp_path, ["alpha"])

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("duplicate_marketplace_plugin: alpha" in error for error in errors)


def test_build_reports_missing_pyyaml_dependency(tmp_path: Path) -> None:
    module = load_check_module()
    make_marketplace(tmp_path, [])
    make_projection(tmp_path, [])
    module.yaml = None

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("missing_dependency: PyYAML" in error for error in errors)


def test_build_reports_manifest_name_mismatch(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha"])
    write_json(
        tmp_path / "plugins" / "alpha" / ".claude-plugin" / "plugin.json",
        {
            "name": "wrong",
            "version": "0.1.0",
            "description": "wrong plugin",
            "skills": "./skills",
        },
    )

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("claude_manifest_name_mismatch" in error for error in errors)


def test_build_reports_missing_codex_manifest_path(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha"])
    codex_manifest = tmp_path / "plugins" / "alpha" / ".codex-plugin" / "plugin.json"
    data = json.loads(codex_manifest.read_text(encoding="utf-8"))
    data["hooks"] = "./missing-hooks"
    write_json(codex_manifest, data)

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("missing_manifest_path" in error for error in errors)


def test_build_reports_projection_plugin_mismatch(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha", "missing"])

    errors = module.run_build(tmp_path, runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""))

    assert any("projection_plugins_mismatch" in error for error in errors)


def test_build_reports_projection_missing_marketplace_plugin(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_plugin(tmp_path, "beta")
    make_marketplace(tmp_path, ["alpha", "beta"])
    make_projection(tmp_path, ["alpha"])

    errors = module.run_build(tmp_path, runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""))

    assert any("projection_plugins_mismatch" in error for error in errors)


def test_build_reports_duplicate_projection_plugin(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "alpha")
    make_marketplace(tmp_path, ["alpha"])
    make_projection(tmp_path, ["alpha", "alpha"])

    errors = module.run_build(tmp_path, runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""))

    assert any("duplicate_projection_plugin" in error for error in errors)


def guard_profile_template_dirs(root: Path) -> tuple[Path, Path]:
    left = root / "plugins" / "agent-guard" / "assets" / "templates" / "guard-profile"
    right = (
        root
        / "plugins"
        / "agent-guard"
        / "skills"
        / "agent-guard"
        / "assets"
        / "templates"
        / "guard-profile"
    )
    return left, right


def make_guard_profile_mirrors(root: Path, content: str = "schema_version: guard-profile/v1\n") -> None:
    left, right = guard_profile_template_dirs(root)
    template_files = [
        ".gitkeep",
        "confirmed-notes.yaml",
        "minimal/GUARD-MANIFEST.yaml",
        "minimal/activation-model.yaml",
        "minimal/artifacts.yaml",
        "minimal/brief-template.md",
        "minimal/execution-model.yaml",
        "minimal/global-command-guards.yaml",
        "minimal/guard-points.yaml",
        "minimal/observation-model.yaml",
        "minimal/state-machine.yaml",
        "minimal/target-model.yaml",
        "minimal/validation-plan.md",
        "comet-review-gate/GUARD-MANIFEST.yaml",
        "comet-review-gate/activation-model.yaml",
        "comet-review-gate/artifacts.yaml",
        "comet-review-gate/brief-template.md",
        "comet-review-gate/execution-model.yaml",
        "comet-review-gate/global-command-guards.yaml",
        "comet-review-gate/guard-points.yaml",
        "comet-review-gate/observation-model.yaml",
        "comet-review-gate/state-machine.yaml",
        "comet-review-gate/target-model.yaml",
        "comet-review-gate/validation-plan.md",
    ]
    for template_file in template_files:
        file_content = "" if template_file == ".gitkeep" else f"# {template_file}\n{content}"
        for base in (left, right):
            path = base / template_file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(file_content, encoding="utf-8")


def test_build_accepts_matching_guard_profile_mirrors(tmp_path: Path) -> None:
    module = load_check_module()
    make_guard_profile_mirrors(tmp_path)

    errors = module.check_guard_profile_template_mirrors(tmp_path)

    assert errors == []


def test_build_reports_guard_profile_mirror_mismatch(tmp_path: Path) -> None:
    module = load_check_module()
    make_guard_profile_mirrors(tmp_path)
    _left, right = guard_profile_template_dirs(tmp_path)
    right_file = right / "comet-review-gate" / "GUARD-MANIFEST.yaml"
    right_file.write_text("schema_version: changed\n", encoding="utf-8")

    errors = module.check_guard_profile_template_mirrors(tmp_path)

    assert any("guard_profile_template_mismatch" in error for error in errors)


def test_build_reports_guard_profile_mirror_file_set_mismatch(tmp_path: Path) -> None:
    module = load_check_module()
    make_guard_profile_mirrors(tmp_path)
    _left, right = guard_profile_template_dirs(tmp_path)
    (right / "EXTRA.yaml").write_text("extra: true\n", encoding="utf-8")

    errors = module.check_guard_profile_template_mirrors(tmp_path)

    assert any("guard_profile_template_files_mismatch" in error for error in errors)


def test_run_build_reports_guard_profile_mirror_mismatch(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "agent-guard")
    make_marketplace(tmp_path, ["agent-guard"])
    make_projection(tmp_path, ["agent-guard"])
    make_guard_profile_mirrors(tmp_path)
    _left, right = guard_profile_template_dirs(tmp_path)
    (right / "comet-review-gate" / "GUARD-MANIFEST.yaml").write_text("schema_version: changed\n", encoding="utf-8")

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("guard_profile_template_mismatch" in error for error in errors)


def test_run_build_reports_guard_profile_mirror_file_set_mismatch(tmp_path: Path) -> None:
    module = load_check_module()
    make_plugin(tmp_path, "agent-guard")
    make_marketplace(tmp_path, ["agent-guard"])
    make_projection(tmp_path, ["agent-guard"])
    make_guard_profile_mirrors(tmp_path)
    _left, right = guard_profile_template_dirs(tmp_path)
    (right / "EXTRA.yaml").write_text("extra: true\n", encoding="utf-8")

    errors = module.run_build(
        tmp_path,
        runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert any("guard_profile_template_files_mismatch" in error for error in errors)
