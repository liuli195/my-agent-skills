"""安装或验证 Guard Hook（守卫钩子）入口。"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


CODEX_EVENTS = ["UserPromptSubmit", "SubagentStart", "SubagentStop", "PreToolUse", "PostToolUse"]
PROFILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def repo_skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def template_path(*parts: str) -> Path:
    return repo_skill_root() / "assets" / "templates" / Path(*parts)


def runtime_dir(project: Path) -> Path:
    return project / ".agents" / "guard-runtime"


def profile_dir(project: Path, profile_id: str) -> Path:
    return project / ".agents" / "guards" / profile_id


def validate_profile_id(profile_id: str) -> str:
    normalized = profile_id.strip()
    if not PROFILE_ID_PATTERN.fullmatch(normalized):
        raise ValueError("Guard Profile（守卫画像）ID 只能使用 ASCII 字母、数字、点、下划线和连字符，且不能包含路径分隔符。")
    return normalized


def adapter_path(project: Path) -> Path:
    return runtime_dir(project) / "hook_event_adapter.py"


def relative_target(project: Path, path: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return str(path)


def quote(value: str | Path) -> str:
    text = str(value)
    return '"' + text.replace('"', '\\"') + '"'


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path} 不是有效 YAML（YAML 配置格式）：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是 YAML mapping（YAML 映射）。")
    return data


def load_hook_bindings(project: Path, profile_id: str) -> list[dict[str, Any]]:
    path = profile_dir(project, profile_id) / "hook-bindings.yaml"
    data = load_yaml_mapping(path)
    bindings = data.get("hook_bindings")
    if not isinstance(bindings, list):
        return []
    return [binding for binding in bindings if isinstance(binding, dict)]


def validate_project(project: Path, profile_id: str) -> tuple[bool, str]:
    if not project.exists():
        return False, f"project_not_found: {project}"
    if not (runtime_dir(project) / "guard_runner.py").exists():
        return False, f"runtime_missing: {runtime_dir(project) / 'guard_runner.py'}"
    if not profile_dir(project, profile_id).exists():
        return False, f"profile_missing: {profile_dir(project, profile_id)}"
    if not (profile_dir(project, profile_id) / "hook-bindings.yaml").exists():
        return False, f"hook_bindings_missing: {profile_dir(project, profile_id) / 'hook-bindings.yaml'}"
    return True, "ok"


def codex_command(
    project: Path,
    profile_id: str,
    event_name: str,
    python_command: str,
) -> str:
    parts = [
        quote(python_command),
        quote(adapter_path(project)),
        "codex",
        "--project",
        quote(project),
        "--profile",
        profile_id,
        "--codex-event",
        event_name,
    ]
    return " ".join(parts)


def read_codex_hooks(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"hooks": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} 不是有效 JSON（JSON 格式）：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是 JSON object（JSON 对象）。")
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        data["hooks"] = {}
    return data


def remove_managed_codex_entries(entries: list[Any], profile_id: str) -> list[Any]:
    kept: list[Any] = []
    marker = "hook_event_adapter.py"
    profile_marker = f"--profile {profile_id}"
    for entry in entries:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        hooks = entry.get("hooks")
        if not isinstance(hooks, list):
            kept.append(entry)
            continue
        has_managed_hook = False
        for hook in hooks:
            if not isinstance(hook, dict):
                continue
            command = hook.get("command")
            if isinstance(command, str) and marker in command and profile_marker in command:
                has_managed_hook = True
                break
        if not has_managed_hook:
            kept.append(entry)
    return kept


def build_codex_hooks(project: Path, profile_id: str, python_command: str) -> dict[str, Any]:
    path = project / ".codex" / "hooks.json"
    data = read_codex_hooks(path)
    hooks = data.setdefault("hooks", {})
    assert isinstance(hooks, dict)

    for event_name in CODEX_EVENTS:
        existing = hooks.get(event_name)
        entries = existing if isinstance(existing, list) else []
        entries = remove_managed_codex_entries(entries, profile_id)
        entries.append(
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": codex_command(project, profile_id, event_name, python_command),
                        "statusMessage": f"agent-guard: {event_name}",
                    }
                ]
            }
        )
        hooks[event_name] = entries
    return data


def write_codex_hooks(project: Path, profile_id: str, python_command: str) -> Path:
    path = project / ".codex" / "hooks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = build_codex_hooks(project, profile_id, python_command)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def git_pre_push_script(profile_id: str) -> str:
    template = template_path("git-hooks", "pre-push").read_text(encoding="utf-8")
    return template.replace("{{ guard_profile_id }}", profile_id)


def write_git_pre_push(project: Path, profile_id: str) -> Path:
    path = project / ".githooks" / "pre-push"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(git_pre_push_script(profile_id), encoding="utf-8")
    path.chmod(0o755)
    return path


def git_command(project: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(project), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def is_git_repo(project: Path) -> bool:
    return git_command(project, ["rev-parse", "--git-dir"]).returncode == 0


def configured_hooks_path(project: Path) -> str:
    result = git_command(project, ["config", "--get", "core.hooksPath"])
    return result.stdout.strip() if result.returncode == 0 else ""


def configure_git_hooks_path(project: Path) -> str:
    if not is_git_repo(project):
        return "not_git_repo"
    result = git_command(project, ["config", "core.hooksPath", ".githooks"])
    if result.returncode != 0:
        return f"error:{result.stderr.strip() or result.returncode}"
    return "configured"


def git_hooks_path_present(project: Path) -> tuple[bool, str]:
    if not is_git_repo(project):
        return True, "not_applicable"
    value = configured_hooks_path(project)
    return value.replace("\\", "/").rstrip("/") == ".githooks", value or "missing"


def write_adapter(project: Path) -> Path:
    path = adapter_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template_path("guard-runtime", "hook_event_adapter.py"), path)
    return path


def render_hook_install_record(project: Path, profile_id: str, bindings: list[dict[str, Any]]) -> str:
    lines = [
        "# Hook Install Plan（钩子安装计划）",
        "",
        f"Guard Profile（守卫画像）：{profile_id}",
        "",
        "状态：installed",
        "",
        "## Installed Entries（已安装入口）",
        "",
        "- Codex Hook（Codex 钩子）：`.codex/hooks.json`",
        "- Git pre-push Hook（Git 推送前钩子）：`.githooks/pre-push`",
        "- Git hooksPath（Git 钩子路径）：`core.hooksPath=.githooks`（仅 Git 仓库）。",
        "- Adapter（适配器）：`.agents/guard-runtime/hook_event_adapter.py`",
        "",
        "## Runtime Call（运行时调用）",
        "",
        "Hook（钩子）入口只生成标准事件 envelope（信封），再调用：",
        "",
        "```text",
        "python .agents/guard-runtime/guard_runner.py run --event <event-file>",
        "```",
        "",
        "## Hook Bindings（钩子绑定）",
        "",
    ]
    if bindings:
        for binding in bindings:
            lines.append(
                f"- `{binding.get('id', '<unknown>')}`：source=`{binding.get('source', '<unknown>')}`，"
                f"event_type=`{binding.get('event_type', '<unknown>')}`。"
            )
    else:
        lines.append("- 暂无 Hook Binding（钩子绑定）。")
    lines.extend(
        [
            "",
            "## Rollback（回滚）",
            "",
            "- 从 `.codex/hooks.json` 移除包含 `hook_event_adapter.py` 和当前 profile 的条目。",
            "- 删除 `.githooks/pre-push`。",
            "- 删除 `.agents/guard-runtime/hook_event_adapter.py`。",
            "- 如需回滚 Git hooksPath（Git 钩子路径），恢复或移除 `core.hooksPath`。",
            "",
            "Hook（钩子）不得写业务规则；具体规则只来自 Guard Profile（守卫画像）。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_install_record(project: Path, profile_id: str, bindings: list[dict[str, Any]]) -> Path:
    path = profile_dir(project, profile_id) / "hook-install-plan.md"
    path.write_text(render_hook_install_record(project, profile_id, bindings), encoding="utf-8")
    return path


def print_plan(project: Path, profile_id: str, bindings: list[dict[str, Any]], python_command: str) -> None:
    print("status: dry_run")
    print("authorization: missing")
    print(f"project: {project}")
    print(f"guard_profile_id: {profile_id}")
    print("changes:")
    for target in [
        adapter_path(project),
        project / ".codex" / "hooks.json",
        project / ".githooks" / "pre-push",
        project / ".git" / "config",
        profile_dir(project, profile_id) / "hook-install-plan.md",
    ]:
        print(f"  - target: {relative_target(project, target)}")
        print("    action: would_write")
    print("runtime_call:")
    print(f"  command: {quote(python_command)} .agents/guard-runtime/guard_runner.py run --event <event-file>")
    print("hook_bindings:")
    if bindings:
        for binding in bindings:
            print(
                f"  - id: {binding.get('id', '<unknown>')} source: {binding.get('source', '<unknown>')} "
                f"event_type: {binding.get('event_type', '<unknown>')}"
            )
    else:
        print("  - none")
    print("rollback:")
    print("  - remove managed entries from .codex/hooks.json")
    print("  - remove .githooks/pre-push")
    print("  - remove .agents/guard-runtime/hook_event_adapter.py")
    print("  - restore or remove git config core.hooksPath when it was changed")
    print("risk:")
    print("  - Hook（钩子）入口可能拒绝命令；必须确认 Guard Profile（守卫画像）规则正确。")
    print("next: 加 --authorize-install 才会写入 Hook（钩子）入口，并授权已安装 Hook（钩子）执行 Runtime（运行时）返回的 `deny`。")


def command_contains_managed_profile(command: str, profile_id: str) -> bool:
    return "hook_event_adapter.py" in command and f"--profile {profile_id}" in command


def codex_hook_present(project: Path, profile_id: str) -> bool:
    path = project / ".codex" / "hooks.json"
    if not path.exists():
        return False
    try:
        data = read_codex_hooks(path)
    except ValueError:
        return False
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    for event_name in CODEX_EVENTS:
        entries = hooks.get(event_name)
        if not isinstance(entries, list):
            return False
        found = False
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks", []):
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    if command_contains_managed_profile(hook["command"], profile_id):
                        found = True
                        break
            if found:
                break
        if not found:
            return False
    return True


def git_pre_push_present(project: Path, profile_id: str) -> bool:
    path = project / ".githooks" / "pre-push"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return "hook_event_adapter.py" in text and f'--profile "{profile_id}"' in text


def verify(project: Path, profile_id: str) -> int:
    adapter_ok = adapter_path(project).exists()
    codex_ok = codex_hook_present(project, profile_id)
    git_ok = git_pre_push_present(project, profile_id)
    hooks_path_ok, hooks_path = git_hooks_path_present(project)
    status = "verified" if adapter_ok and codex_ok and git_ok and hooks_path_ok else "missing"
    print(f"status: {status}")
    print(f"adapter: {'present' if adapter_ok else 'missing'}")
    print(f"codex_hook: {'present' if codex_ok else 'missing'}")
    print(f"git_pre_push: {'present' if git_ok else 'missing'}")
    print(f"git_hooks_path: {hooks_path}")
    return 0 if status == "verified" else 1


def install(project: Path, profile_id: str, python_command: str) -> int:
    bindings = load_hook_bindings(project, profile_id)
    adapter = write_adapter(project)
    codex_hooks = write_codex_hooks(project, profile_id, python_command)
    git_hook = write_git_pre_push(project, profile_id)
    hooks_path_status = configure_git_hooks_path(project)
    install_record = write_install_record(project, profile_id, bindings)

    print("status: installed")
    print(f"project: {project}")
    print(f"guard_profile_id: {profile_id}")
    print(f"adapter: {adapter}")
    print(f"codex_hooks: {codex_hooks}")
    print(f"git_pre_push: {git_hook}")
    print(f"git_hooks_path: {hooks_path_status}")
    print(f"install_record: {install_record}")
    print("business_rules: profile_only")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="安装或验证 Guard Hook（守卫钩子）入口。")
    parser.add_argument("--profile", required=True, help="Guard Profile（守卫画像）ID")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="项目路径")
    parser.add_argument(
        "--authorize-install",
        action="store_true",
        help="明确授权写入 Hook（钩子）入口，并授权已安装 Hook（钩子）执行 Runtime（运行时）返回的 deny",
    )
    parser.add_argument("--verify", action="store_true", help="验证 Hook（钩子）入口是否存在")
    parser.add_argument("--python", default=sys.executable, help="Codex Hook（Codex 钩子）使用的 Python 命令")
    args = parser.parse_args(argv)

    project = args.project.resolve()
    try:
        profile_id = validate_profile_id(args.profile)
    except ValueError as exc:
        print("status: error")
        print(f"reason: {exc}")
        return 2

    ok, reason = validate_project(project, profile_id)
    if not ok:
        print("status: error")
        print(f"reason: {reason}")
        return 2

    if args.verify:
        return verify(project, profile_id)

    try:
        bindings = load_hook_bindings(project, profile_id)
    except ValueError as exc:
        print("status: error")
        print(f"reason: {exc}")
        return 2

    if not args.authorize_install:
        print_plan(project, profile_id, bindings, args.python)
        return 0

    return install(project, profile_id, args.python)


if __name__ == "__main__":
    sys.exit(main())
