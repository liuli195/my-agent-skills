from __future__ import annotations

import argparse
from collections.abc import Sequence


COMMANDS = ("diagnose", "init", "complete", "cleanup", "hotfix", "tweak")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pr_flow.py",
        description="PR Flow Plugin（拉取请求流程插件）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        subparser = subparsers.add_parser(
            command,
            help=f"{command} command",
            description=f"{command} command",
        )
        subparser.set_defaults(command=command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    print("status: not_implemented")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
