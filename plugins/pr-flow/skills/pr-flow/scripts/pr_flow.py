from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import yaml


COMMANDS = ("diagnose", "init", "complete", "cleanup", "hotfix", "tweak")
PR_TEMPLATE = """## Summary

## Scope

## Verification

## Risk

## Rollback
"""
PR_FLOW_GITIGNORE = "/runs/\n/last-status.json\n"


def resolve_project(path: Path) -> Path:
    return path.expanduser().resolve()


def write_text_if_missing(path: Path, text: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def default_config(base_branch: str) -> dict:
    return {
        "defaults": {
            "baseBranch": base_branch,
            "mergeStrategy": "merge",
            "reviewGate": {"mode": "github"},
            "wait": {"timeoutSeconds": 600, "pollSeconds": 15},
            "pr": {
                "bodyTemplatePath": ".pr-flow/pr-template.md",
                "requiredSections": ["Summary", "Scope", "Verification", "Risk", "Rollback"],
            },
        },
        "branches": {
            base_branch: {
                "remote": "origin",
                "allowHotfixPush": False,
            },
        },
    }


def run_init(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    pr_flow_dir = project / ".pr-flow"

    config_text = yaml.safe_dump(default_config(args.base_branch), allow_unicode=True, sort_keys=False)
    write_text_if_missing(pr_flow_dir / "config.yaml", config_text)
    write_text_if_missing(pr_flow_dir / "pr-template.md", PR_TEMPLATE)
    write_text_if_missing(pr_flow_dir / ".gitignore", PR_FLOW_GITIGNORE)

    print("status: initialized")
    print(f"GitHub Rulesets suggestion: protect {args.base_branch} with pull request review and passing checks.")
    return 0


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
        if command == "init":
            subparser.add_argument("--project", type=Path)
            subparser.add_argument("--base-branch", default="main")
        subparser.set_defaults(command=command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init" and args.project is not None:
        return run_init(args)
    print("status: not_implemented")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
