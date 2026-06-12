"""读取项目级 Guard Runtime（守卫运行时）生成的 latest Guard Brief（最新守卫简报）。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="为 Guard Instance（守卫实例）渲染 latest Guard Brief（最新守卫简报）。")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目目录，默认当前目录")
    parser.add_argument("--profile", required=True, help="Guard Profile（守卫画像）ID")
    parser.add_argument("--subject", required=True, help="Subject Key Hash（主体键哈希）")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="输出格式")
    parser.add_argument("--session", help="Codex session（Codex 会话）或调用上下文 ID，用于 brief_hash 去重")
    parser.add_argument("--context-json", help="可选调用上下文字段 JSON（JSON 格式），写入注入记录")
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
        "brief",
        "--profile",
        args.profile,
        "--subject",
        args.subject,
        "--format",
        args.format,
    ]
    if args.session:
        command.extend(["--session", args.session])
    if args.context_json:
        command.extend(["--context-json", args.context_json])

    completed = subprocess.run(command, cwd=project, text=True, check=False)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
