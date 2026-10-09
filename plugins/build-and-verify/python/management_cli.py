from __future__ import annotations

import argparse
import json
import sys

from management import ManagementError, add_management_parsers, run_management


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build-and-verify")
    commands = parser.add_subparsers(dest="command", required=True)
    add_management_parsers(commands)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_management(args), ensure_ascii=False))
    except ManagementError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
