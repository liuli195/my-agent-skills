"""显式激活项目级 Guard Profile（守卫画像）。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="激活 Guard Profile（守卫画像）。")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目目录，默认当前目录")
    parser.add_argument("--profile", required=True, help="Guard Profile（守卫画像）ID")
    parser.add_argument("--scope", default="current_context", help="激活范围")
    parser.add_argument("--source", default="agent-guard-skill", help="激活来源")
    parser.add_argument("--context-json", help="当前上下文字段 JSON（JSON 格式）")
    parser.add_argument("--subject-json", help="可选 Subject（主体）输入 JSON（JSON 格式）")
    args = parser.parse_args(argv)

    project = args.project.resolve()
    runner = project / ".agents" / "guard-runtime" / "guard_runner.py"
    if not runner.exists():
        print("status: runtime_missing")
        print(f"project: {project}")
        print(f"expected_runner: {runner}")
        print("next: 先用 init_project_guard.py 初始化项目级 Guard Runtime（守卫运行时）。")
        return 2

    command = [
        sys.executable,
        str(runner),
        "activate",
        "--profile",
        args.profile,
        "--scope",
        args.scope,
        "--source",
        args.source,
    ]
    if args.context_json:
        command.extend(["--context-json", args.context_json])
    if args.subject_json:
        command.extend(["--subject-json", args.subject_json])

    completed = subprocess.run(command, cwd=project, text=True, check=False)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
