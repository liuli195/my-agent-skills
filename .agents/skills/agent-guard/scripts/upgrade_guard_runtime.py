"""后续 Agent Guard（代理守卫）工作的保留 Runtime（运行时）升级命令。"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="升级已生成的 Guard Runtime（守卫运行时）。")
    parser.add_argument("--project", help="项目路径")
    parser.parse_args(argv)
    print("保留命令：upgrade_guard_runtime.py")
    print("Runtime（运行时）升级不属于 MVP（最小可行版本）01。")
    print("请使用：validate_guard_profile.py <guard-profile-dir>。")
    return 2


if __name__ == "__main__":
    sys.exit(main())
