"""升级项目级 Guard Runtime（守卫运行时）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from init_project_guard import RUNTIME_VERSION, dump_yaml, guard_runner_template, runtime_readme


RUNTIME_RELATIVE = Path(".agents") / "guard-runtime"
TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "assets" / "templates" / "guard-runtime"
RUNTIME_SUBDIRS = ["engine", "adapters", "checks", "schemas"]


def runtime_dir(project: Path) -> Path:
    return project / RUNTIME_RELATIVE


def relative_target(project: Path, path: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return str(path)


def read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def read_current_version(runtime: Path) -> str:
    version_path = runtime / "VERSION"
    if version_path.exists():
        version = version_path.read_text(encoding="utf-8").strip()
        if version:
            return version
    manifest = read_yaml_mapping(runtime / "RUNTIME-MANIFEST.yaml")
    version = manifest.get("runtime_version")
    return version if isinstance(version, str) and version else "unknown"


def runtime_manifest(existing_manifest: dict[str, Any]) -> dict[str, Any]:
    hook_installation = existing_manifest.get("hook_installation", "not_installed")
    if not isinstance(hook_installation, str):
        hook_installation = "not_installed"
    return {
        "schema_version": "guard-runtime/v1",
        "runtime_version": RUNTIME_VERSION,
        "generated_by": "agent-guard",
        "entrypoints": {
            "activate": "guard_runner.py activate --profile <id> --scope current_context",
            "run": "guard_runner.py run --event <event-file>",
            "brief": "guard_runner.py brief --profile <id> --subject <subject-key-hash> --format json",
        },
        "runtime_paths": {
            "profiles": ".agents/guards",
            "state": ".local/guard/state",
            "runs": ".local/guard/runs",
            "overrides": ".local/guard/overrides",
            "confirmations": ".local/guard/confirmations",
            "latest": ".local/guard/latest",
            "injections": ".local/guard/injections",
        },
        "hook_installation": hook_installation,
    }


def validate_existing_runtime(project: Path) -> tuple[bool, str]:
    runtime = runtime_dir(project)
    if not runtime.exists() or not runtime.is_dir():
        return False, "missing_runtime_dir"
    if not (runtime / "guard_runner.py").exists():
        return False, "missing_guard_runner"
    return True, "ok"


def planned_runtime_files(runtime: Path) -> list[tuple[Path, str]]:
    files = [
        (runtime / "VERSION", "would_write"),
        (runtime / "requirements.txt", "would_write"),
        (runtime / "RUNTIME-MANIFEST.yaml", "would_write"),
        (runtime / "README.md", "would_write"),
        (runtime / "guard_runner.py", "would_write"),
    ]
    adapter = runtime / "hook_event_adapter.py"
    files.append((adapter, "would_update" if adapter.exists() else "skip_absent"))
    return files


def print_upgrade_plan(project: Path) -> None:
    runtime = runtime_dir(project)
    print("status: dry_run")
    print("authorization: missing")
    print(f"project: {project}")
    print(f"runtime: {runtime}")
    print(f"current_version: {read_current_version(runtime)}")
    print(f"target_version: {RUNTIME_VERSION}")
    print("changes:")
    for path, action in planned_runtime_files(runtime):
        print(f"  - target: {relative_target(project, path)}")
        print(f"    action: {action}")
    print("profiles: preserved")
    print("hooks: preserved")
    print("next: 加 --authorize-upgrade 才会升级项目级 Guard Runtime（守卫运行时）。")


def write_runtime(project: Path) -> dict[str, str]:
    runtime = runtime_dir(project)
    for relative_dir in RUNTIME_SUBDIRS:
        directory = runtime / relative_dir
        directory.mkdir(parents=True, exist_ok=True)
        gitkeep = directory / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")

    existing_manifest = read_yaml_mapping(runtime / "RUNTIME-MANIFEST.yaml")
    (runtime / "VERSION").write_text(f"{RUNTIME_VERSION}\n", encoding="utf-8")
    (runtime / "requirements.txt").write_text("PyYAML\njsonschema\n", encoding="utf-8")
    dump_yaml(runtime / "RUNTIME-MANIFEST.yaml", runtime_manifest(existing_manifest))
    (runtime / "README.md").write_text(runtime_readme(), encoding="utf-8")
    (runtime / "guard_runner.py").write_text(guard_runner_template(), encoding="utf-8")

    adapter = runtime / "hook_event_adapter.py"
    adapter_action = "absent"
    if adapter.exists():
        adapter.write_text((TEMPLATE_ROOT / "hook_event_adapter.py").read_text(encoding="utf-8"), encoding="utf-8")
        adapter_action = "updated"
    return {"hook_adapter": adapter_action}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="升级已生成的 Guard Runtime（守卫运行时）。")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目路径，默认当前目录")
    parser.add_argument("--authorize-upgrade", action="store_true", help="明确授权覆盖项目级 Guard Runtime（守卫运行时）文件")
    args = parser.parse_args(argv)

    project = args.project.resolve()
    ok, reason = validate_existing_runtime(project)
    if not ok:
        print("status: not_initialized")
        print(f"project: {project}")
        print(f"runtime: {runtime_dir(project)}")
        print(f"reason: {reason}")
        print("next: 先使用 init_project_guard.py 初始化项目级 Guard Runtime（守卫运行时）。")
        return 1

    if not args.authorize_upgrade:
        print_upgrade_plan(project)
        return 0

    runtime = runtime_dir(project)
    from_version = read_current_version(runtime)
    result = write_runtime(project)
    print("status: upgraded")
    print(f"project: {project}")
    print(f"runtime: {runtime}")
    print(f"from_version: {from_version}")
    print(f"to_version: {RUNTIME_VERSION}")
    print(f"hook_adapter: {result['hook_adapter']}")
    print("profiles: preserved")
    print("hooks: preserved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
