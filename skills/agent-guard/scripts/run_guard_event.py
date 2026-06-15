"""把标准事件交给项目级 Guard Runtime（守卫运行时）处理。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="为一个标准事件运行 Guard Runtime（守卫运行时）。")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目目录，默认当前目录")
    parser.add_argument("--event", type=Path, required=True, help="标准事件 envelope（信封）文件")
    args = parser.parse_args(argv)

    project = args.project.resolve()
    runner = project / ".agents" / "guard-runtime" / "guard_runner.py"
    if not runner.exists():
        print("status: runtime_missing")
        print(f"project: {project}")
        print(f"expected_runner: {runner}")
        print("next: 先用 init_project_guard.py 初始化项目级 Guard Runtime（守卫运行时）。")
        return 2

    completed = subprocess.run(
        [sys.executable, str(runner), "run", "--event", str(args.event.resolve())],
        cwd=project,
        text=True,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
