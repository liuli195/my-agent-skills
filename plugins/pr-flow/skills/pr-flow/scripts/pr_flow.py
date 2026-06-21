from __future__ import annotations

import argparse
import json
import subprocess
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


def load_config(project: Path) -> dict:
    config_path = project / ".pr-flow" / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(config_path)
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def write_status(project: Path, command: str, status: str, details: dict) -> None:
    status_path = project / ".pr-flow" / "last-status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "command": command,
        "details": details,
    }
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_stop(status: str, message: str) -> None:
    print(f"status: {status}")
    print(message)


def git(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )


def gh(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )


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


def run_diagnose(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    try:
        load_config(project)
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        write_status(project, args.command, "EXCEPTION_REQUIRED", details)
        print_stop("EXCEPTION_REQUIRED", "missing_config")
        return 1
    details = {"reason": "diagnose_not_implemented"}
    write_status(project, args.command, "EXCEPTION_REQUIRED", details)
    print_stop("EXCEPTION_REQUIRED", "diagnose_not_implemented")
    return 1


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
        if command in {"diagnose", "init"}:
            subparser.add_argument("--project", type=Path)
        if command == "init":
            subparser.add_argument("--base-branch", default="main")
        subparser.set_defaults(command=command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init" and args.project is not None:
        return run_init(args)
    if args.command == "diagnose" and args.project is not None:
        return run_diagnose(args)
    print("status: not_implemented")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
