from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cross_agent_review.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--change")
    run_parser.add_argument("--base-ref")
    run_parser.add_argument("--head-ref")
    run_parser.add_argument("--diff-file")
    run_parser.add_argument("--spec-file")
    run_parser.add_argument("--design-file")
    run_parser.add_argument("--tasks-file")
    run_parser.add_argument("--tests-file")
    run_parser.add_argument("--output-dir")
    run_parser.add_argument("--sdk-python")
    run_parser.add_argument("--fake-reviewer-results")
    run_parser.add_argument("--disable-risk-review", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    print("status: not_implemented")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
