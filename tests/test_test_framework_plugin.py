import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "test-framework"
CODEX_REPO_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_REPO_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
RELEASE_FLOW_PROJECTION = REPO_ROOT / ".release-flow" / "projection.yaml"
RELEASE_FLOW_CONFIG = REPO_ROOT / ".release-flow" / "config.yaml"
RELEASE_FLOW_SCRIPT = REPO_ROOT / "plugins" / "release-flow" / "skills" / "release-flow" / "scripts" / "release_flow.py"
TEST_FRAMEWORK_SCRIPT = (
    PLUGIN_ROOT / "skills" / "test-framework" / "scripts" / "test_framework.py"
)

PLUGIN_NAME = "test-framework"
PLUGIN_VERSION = "0.1.8"
PLUGIN_DESCRIPTION = "Test Framework Plugin（测试框架插件）"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_test_framework(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TEST_FRAMEWORK_SCRIPT), *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def run_check(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TEST_FRAMEWORK_SCRIPT), *args, "--project", str(project)],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )


def git(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )


def command_that_logs(label: str, log_name: str = "run.log") -> list[str]:
    code = (
        "from pathlib import Path\n"
        f"Path({log_name!r}).open('a', encoding='utf-8').write({label!r} + '\\n')\n"
    )
    return [sys.executable, "-c", code]


def command_that_fails_once(label: str) -> list[str]:
    code = (
        "from pathlib import Path\n"
        "marker = Path('fail-once.marker')\n"
        "Path('run.log').open('a', encoding='utf-8').write(" + repr(label) + " + '\\n')\n"
        "if marker.exists():\n"
        "    raise SystemExit(0)\n"
        "marker.write_text('failed', encoding='utf-8')\n"
        "raise SystemExit(7)\n"
    )
    return [sys.executable, "-c", code]


def plugin_names(catalog: dict) -> list[str]:
    return [plugin["name"] for plugin in catalog["plugins"]]


def plugin_after(names: list[str], left: str) -> str:
    return names[names.index(left) + 1]


def release_projection_plugins() -> list[str]:
    lines = RELEASE_FLOW_PROJECTION.read_text(encoding="utf-8").splitlines()
    in_codex_generator = False
    in_plugins = False
    plugins: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "- path: .agents/plugins/marketplace.json":
            in_codex_generator = True
            continue
        if in_codex_generator and stripped.startswith("- path: ") and plugins:
            break
        if in_codex_generator and stripped == "plugins:":
            in_plugins = True
            continue
        if in_plugins:
            if line.startswith("      - "):
                plugins.append(stripped.removeprefix("- "))
                continue
            if plugins:
                break

    return plugins


def write_release_projection_project(project: Path) -> Path:
    release_flow_dir = project / ".release-flow"
    release_flow_dir.mkdir(parents=True)
    (project / ".agents" / "plugins").mkdir(parents=True)
    (project / ".claude-plugin").mkdir(parents=True)

    (release_flow_dir / "config.yaml").write_text(
        RELEASE_FLOW_CONFIG.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (release_flow_dir / "projection.yaml").write_text(
        RELEASE_FLOW_PROJECTION.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (project / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "placeholder",
                "owner": {"name": "placeholder"},
                "plugins": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    vars_file = project / "release-vars.json"
    vars_file.write_text(
        json.dumps(
            {
                "CODEX_MARKETPLACE_CATALOG_NAME": "my-agent-skills-marketplace",
                "CODEX_MARKETPLACE_DISPLAY_NAME": "My Agent Skills Marketplace",
                "CLAUDE_MARKETPLACE_CATALOG_NAME": "my-agent-skills-marketplace",
                "CLAUDE_MARKETPLACE_OWNER_NAME": "My Agent Skills Marketplace",
                "RELEASE_FLOW_PLUGIN_REPOSITORY": "liuli/my-agent-skills",
                "RELEASE_FLOW_PLUGIN_REF": "main",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return vars_file


def test_test_framework_plugin_has_dual_manifests() -> None:
    expected_manifest = {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "skills": "./skills",
    }

    assert read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json") == expected_manifest
    assert read_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json") == expected_manifest


def test_test_framework_plugin_has_single_skill_entrypoint() -> None:
    skill_root = PLUGIN_ROOT / "skills"
    script_path = skill_root / PLUGIN_NAME / "scripts" / "test_framework.py"
    skill_dirs = [path.name for path in skill_root.iterdir() if path.is_dir()]
    skill_text = (skill_root / PLUGIN_NAME / "SKILL.md").read_text(encoding="utf-8")
    front_matter = skill_text.split("---", 2)[1]

    assert skill_dirs == [PLUGIN_NAME]
    assert script_path.is_file()
    assert skill_text.startswith("---\n")
    assert f"name: {PLUGIN_NAME}" in front_matter
    assert "只初始化测试框架配置产物" in skill_text
    assert "不安装依赖" in skill_text
    assert "不写用户级配置" in skill_text
    assert "不配置 CI（持续集成）" in skill_text
    assert "不内置仓库业务逻辑" in skill_text
    assert "不向目标仓库复制 runner（运行器）" in skill_text
    assert "scripts/test_framework.py init" in skill_text


def test_test_framework_registered_in_marketplaces_and_projection() -> None:
    claude_catalog = read_json(CLAUDE_REPO_MARKETPLACE)
    codex_catalog = read_json(CODEX_REPO_MARKETPLACE)
    claude_names = plugin_names(claude_catalog)
    codex_names = plugin_names(codex_catalog)
    projection_plugins = release_projection_plugins()

    assert plugin_after(claude_names, "pr-flow") == PLUGIN_NAME
    assert claude_catalog["plugins"][claude_names.index(PLUGIN_NAME)] == {
        "name": PLUGIN_NAME,
        "source": "./plugins/test-framework",
        "description": PLUGIN_DESCRIPTION,
    }
    assert plugin_after(codex_names, "pr-flow") == PLUGIN_NAME
    assert codex_catalog["plugins"][codex_names.index(PLUGIN_NAME)] == {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": "./plugins/test-framework"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools",
    }
    assert plugin_after(projection_plugins, "pr-flow") == PLUGIN_NAME


def test_test_framework_release_projection_passes_real_validate() -> None:
    result = subprocess.run(
        [sys.executable, str(RELEASE_FLOW_SCRIPT), "validate", "--project", "."],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_test_framework_release_projection_projects_real_catalogs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    vars_file = write_release_projection_project(project)

    result = subprocess.run(
        [
            sys.executable,
            str(RELEASE_FLOW_SCRIPT),
            "project",
            "--project",
            str(project),
            "--vars-file",
            str(vars_file),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: projected" in result.stdout

    codex_catalog = read_json(project / ".agents" / "plugins" / "marketplace.json")
    codex_names = plugin_names(codex_catalog)
    assert plugin_after(codex_names, "pr-flow") == PLUGIN_NAME
    assert codex_catalog["plugins"][codex_names.index(PLUGIN_NAME)] == {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": "./plugins/test-framework"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools",
    }


def test_test_framework_init_writes_config_gitignore_and_cache(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = run_test_framework("init", "--project", str(project))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: initialized" in result.stdout
    assert (project / ".test-framework" / "config.json").is_file()
    assert (project / ".test-framework" / ".gitignore").is_file()
    assert (project / ".test-framework" / "cache").is_dir()
    assert not (project / "scripts" / "check.py").exists()
    assert read_json(project / ".test-framework" / "config.json") == {
        "version": 1,
        "build": {"checks": []},
        "verify": {"checks": []},
    }
    assert (project / ".test-framework" / ".gitignore").read_text(encoding="utf-8") == "/cache/\n/runs/\n"


@pytest.mark.parametrize(
    "existing",
    [
        Path(".test-framework/config.json"),
        Path(".test-framework/.gitignore"),
    ],
)
def test_test_framework_init_refuses_existing_files_before_writes(
    tmp_path: Path, existing: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    existing_path = project / existing
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text("keep me\n", encoding="utf-8")

    result = run_test_framework("init", "--project", str(project))

    assert result.returncode != 0
    assert f"existing_file: {existing.as_posix()}" in result.stderr
    assert existing_path.read_text(encoding="utf-8") == "keep me\n"
    generated_files = [
        Path(".test-framework/config.json"),
        Path(".test-framework/.gitignore"),
    ]
    for relative in generated_files:
        path = project / relative
        if path != existing_path:
            assert not path.exists()
    assert not (project / ".test-framework" / "cache").exists()


def test_test_framework_runner_build_verify_and_full_verify(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "docs").mkdir()
    (project / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
    (project / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {
                "checks": [
                    {"id": "build-main", "command": command_that_logs("build-main")}
                ]
            },
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

    build = run_check(project, "build")
    verify = run_check(project, "verify")
    full_verify = run_check(project, "verify", "--full")

    assert build.returncode == 0, build.stdout + build.stderr
    assert "checked: build-main" in build.stdout
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "checked: verify-src, verify-docs" in verify.stdout
    assert "full-not-run: true" in verify.stdout
    assert full_verify.returncode == 0, full_verify.stdout + full_verify.stderr
    assert "checked: verify-src, verify-docs" in full_verify.stdout
    assert "full-not-run: false" in full_verify.stdout
    assert "cache-hit" not in full_verify.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "build-main",
        "verify-src",
        "verify-docs",
        "verify-src",
        "verify-docs",
    ]


def test_test_framework_runner_full_verify_allows_empty_checks(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0

    result = run_check(project, "verify", "--full")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "checked:" in result.stdout
    assert "full-not-run: false" in result.stdout
    assert "status: passed" in result.stdout


def test_test_framework_runner_uses_passed_result_cache(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "cached.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "cache-check",
                        "command": command_that_logs("cache-check"),
                        "paths": ["src/cached.py"],
                        "inputs": ["src/cached.py"],
                    }
                ]
            },
        },
    )

    first = run_check(project, "verify")
    second = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: cache-check" in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "cache-check"
    ]


def test_test_framework_runner_full_verify_refreshes_cache_for_default_verify(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "cached.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "full-primes-cache",
                        "command": command_that_logs("full-primes-cache"),
                        "paths": ["src/cached.py"],
                        "inputs": ["src/cached.py"],
                    }
                ]
            },
        },
    )

    full = run_check(project, "verify", "--full")
    default = run_check(project, "verify")

    assert full.returncode == 0, full.stdout + full.stderr
    assert default.returncode == 0, default.stdout + default.stderr
    assert "cache-hit:" not in full.stdout
    assert "cache-hit: full-primes-cache" in default.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "full-primes-cache"
    ]


def test_test_framework_runner_default_cache_key_tracks_glob_path_contents(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    assert git(project, "init").returncode == 0
    (project / "src").mkdir()
    app_path = project / "src" / "app.txt"
    app_path.write_text("first\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
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

    first = run_check(project, "verify")
    app_path.write_text("second\n", encoding="utf-8")
    second = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: glob-default-inputs" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "glob-default-inputs",
        "glob-default-inputs",
    ]


def test_test_framework_runner_default_check_cache_key_tracks_changed_files(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    assert git(project, "init").returncode == 0
    assert git(project, "config", "user.email", "test@example.invalid").returncode == 0
    assert git(project, "config", "user.name", "Test User").returncode == 0
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "default-check",
                        "command": command_that_logs("default-check"),
                    }
                ]
            },
        },
    )
    assert git(project, "add", ".").returncode == 0
    assert git(project, "commit", "-m", "initial").returncode == 0

    (project / "a.txt").write_text("a\n", encoding="utf-8")
    first = run_check(project, "verify")
    (project / "b.txt").write_text("b\n", encoding="utf-8")
    second = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: default-check" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "default-check",
        "default-check",
    ]


def test_test_framework_runner_default_check_cache_key_tracks_dirty_file_contents(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    assert git(project, "init").returncode == 0
    assert git(project, "config", "user.email", "test@example.invalid").returncode == 0
    assert git(project, "config", "user.name", "Test User").returncode == 0
    dirty_file = project / "dirty.txt"
    dirty_file.write_text("base\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
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
    assert git(project, "add", ".").returncode == 0
    assert git(project, "commit", "-m", "initial").returncode == 0

    dirty_file.write_text("first\n", encoding="utf-8")
    first = run_check(project, "verify")
    dirty_file.write_text("second\n", encoding="utf-8")
    second = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: default-dirty-check" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "default-dirty-check",
        "default-dirty-check",
    ]


def test_test_framework_runner_reports_missing_list_command_without_traceback(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "missing-command",
                        "command": ["missing-test-framework-executable"],
                        "paths": ["src/app.txt"],
                        "inputs": ["src/app.txt"],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify")
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "command_not_found: missing-command" in output
    assert "Traceback" not in output


def test_test_framework_runner_verify_reports_missing_config_without_traceback(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / ".test-framework" / "config.json").unlink()

    result = run_check(project, "verify")
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "missing_config: .test-framework/config.json" in output
    assert "status: failed" in result.stdout
    assert "Traceback" not in output


@pytest.mark.parametrize(
    "invalid_input",
    [
        "../outside.txt",
        "{outside}",
    ],
)
def test_test_framework_runner_rejects_inputs_outside_project(
    tmp_path: Path, invalid_input: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "invalid-input",
                        "command": command_that_logs("invalid-input"),
                        "paths": ["src/**"],
                        "inputs": [invalid_input.format(outside=outside)],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify")

    assert result.returncode != 0
    assert "invalid_input_path" in result.stderr
    assert not (project / "run.log").exists()


def test_test_framework_runner_full_verify_rejects_inputs_outside_project(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "app.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "invalid-input",
                        "command": command_that_logs("invalid-input"),
                        "paths": ["src/**"],
                        "inputs": ["../outside.txt"],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify", "--full")

    assert result.returncode != 0
    assert "invalid_input_path: ../outside.txt" in result.stderr
    assert not (project / "run.log").exists()


@pytest.mark.parametrize("mutation", ["check_id", "command", "inputs", "config"])
def test_test_framework_runner_cache_key_changes_with_check_contract(
    tmp_path: Path, mutation: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "inputs").mkdir()
    (project / "src" / "sample.py").write_text("changed\n", encoding="utf-8")
    (project / "inputs" / "v1.txt").write_text("v1\n", encoding="utf-8")
    (project / "inputs" / "v2.txt").write_text("v2\n", encoding="utf-8")

    def config(
        *,
        version: int = 1,
        check_id: str = "cache-contract",
        command: list[str] | None = None,
        inputs: list[str] | None = None,
    ) -> dict:
        return {
            "version": version,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": check_id,
                        "command": command or command_that_logs("base"),
                        "paths": ["src/**"],
                        "inputs": inputs or ["inputs/v1.txt"],
                    }
                ]
            },
        }

    write_json(project / ".test-framework" / "config.json", config())
    first = run_check(project, "verify")
    cached = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert cached.returncode == 0, cached.stdout + cached.stderr
    assert "cache-hit: cache-contract" in cached.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == ["base"]

    changed_config = config()
    expected_checked = "cache-contract"
    expected_log = "base"
    if mutation == "check_id":
        changed_config = config(check_id="cache-contract-renamed")
        expected_checked = "cache-contract-renamed"
    elif mutation == "command":
        changed_config = config(command=command_that_logs("changed-command"))
        expected_log = "changed-command"
    elif mutation == "inputs":
        changed_config = config(inputs=["inputs/v2.txt"])
    elif mutation == "config":
        changed_config = config(version=2)
    else:
        raise AssertionError(f"unsupported mutation: {mutation}")

    write_json(project / ".test-framework" / "config.json", changed_config)
    changed = run_check(project, "verify")

    assert changed.returncode == 0, changed.stdout + changed.stderr
    assert "cache-hit:" not in changed.stdout
    assert f"checked: {expected_checked}" in changed.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "base",
        expected_log,
    ]


def test_test_framework_runner_cache_miss_does_not_fall_back_to_full(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "sample.txt").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "verify.sample",
                        "command": command_that_logs(
                            "verify.sample", "sample-count.txt"
                        ),
                        "paths": ["src/**"],
                        "inputs": ["src/sample.txt"],
                    },
                    {
                        "id": "verify.full-only",
                        "command": command_that_logs(
                            "verify.full-only", "full-ran.txt"
                        ),
                        "paths": ["other/**"],
                        "inputs": ["other"],
                    },
                ]
            },
        },
    )

    result = run_check(project, "verify")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "cache-hit:" not in result.stdout
    assert "checked: verify.sample" in result.stdout
    assert "full-not-run: true" in result.stdout
    assert (project / "sample-count.txt").read_text(encoding="utf-8").splitlines() == [
        "verify.sample"
    ]
    assert not (project / "full-ran.txt").exists()


@pytest.mark.parametrize(
    "excluded_relative",
    [
        Path(".test-framework/cache/noise.txt"),
        Path(".git/noise.txt"),
        Path("src/__pycache__/noise.pyc"),
    ],
)
def test_test_framework_runner_directory_hash_ignores_generated_paths(
    tmp_path: Path, excluded_relative: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "sample.txt").write_text("changed\n", encoding="utf-8")
    run_log = project / ".test-framework" / "cache" / "directory-hash-runs.txt"
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "directory-hash",
                        "command": command_that_logs(
                            "directory-hash",
                            ".test-framework/cache/directory-hash-runs.txt",
                        ),
                        "paths": ["src/**"],
                        "inputs": ["."],
                    }
                ]
            },
        },
    )

    first = run_check(project, "verify")
    noise_path = project / excluded_relative
    noise_path.parent.mkdir(parents=True, exist_ok=True)
    noise_path.write_text("ignored\n", encoding="utf-8")
    second = run_check(project, "verify")

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: directory-hash" in second.stdout
    assert run_log.read_text(encoding="utf-8").splitlines() == ["directory-hash"]


def test_test_framework_cache_key_covers_runtime_and_cache_versions() -> None:
    template = (
        PLUGIN_ROOT / "skills" / "test-framework" / "scripts" / "test_framework_runner.py"
    ).read_text(encoding="utf-8")

    assert '"cache_version": CACHE_VERSION' in template
    assert '"framework_version": FRAMEWORK_VERSION' in template
    assert '"python_version": platform.python_version()' in template


def test_test_framework_runner_does_not_cache_failed_results(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "src").mkdir()
    (project / "src" / "fails.py").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "fail-once",
                        "command": command_that_fails_once("fail-once"),
                        "paths": ["src/fails.py"],
                        "inputs": ["src/fails.py"],
                    }
                ]
            },
        },
    )

    first = run_check(project, "verify")
    second = run_check(project, "verify")

    assert first.returncode != 0
    assert second.returncode == 0, second.stdout + second.stderr
    assert "cache-hit: fail-once" not in second.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "fail-once",
        "fail-once",
    ]


def test_test_framework_runner_no_check_does_not_fall_back_to_full(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    (project / "docs").mkdir()
    (project / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    write_json(
        project / ".test-framework" / "config.json",
        {
            "version": 1,
            "build": {"checks": []},
            "verify": {
                "checks": [
                    {
                        "id": "src-only",
                        "command": command_that_logs("src-only"),
                        "paths": ["src/**"],
                        "inputs": ["src"],
                    }
                ]
            },
        },
    )

    result = run_check(project, "verify")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "checked:" in result.stdout
    assert "full-not-run: true" in result.stdout
    assert not (project / "run.log").exists()


def test_test_framework_runner_reads_worktree_changed_files(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert run_test_framework("init", "--project", str(project)).returncode == 0
    write_json(
        project / ".test-framework" / "config.json",
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
    assert git(project, "init").returncode == 0
    assert git(project, "config", "user.email", "test@example.com").returncode == 0
    assert git(project, "config", "user.name", "Test User").returncode == 0
    assert git(project, "add", ".").returncode == 0
    assert git(project, "commit", "-m", "initial").returncode == 0
    (project / "staged.txt").write_text("staged\n", encoding="utf-8")
    assert git(project, "add", "staged.txt").returncode == 0
    (project / "unstaged.txt").write_text("unstaged\n", encoding="utf-8")
    (project / "untracked.txt").write_text("untracked\n", encoding="utf-8")

    result = run_check(project, "verify")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "checked: staged-check, unstaged-check, untracked-check" in result.stdout
    assert (project / "run.log").read_text(encoding="utf-8").splitlines() == [
        "staged-check",
        "unstaged-check",
        "untracked-check",
    ]
