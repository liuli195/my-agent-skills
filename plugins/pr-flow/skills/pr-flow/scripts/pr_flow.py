from __future__ import annotations

import argparse
import ctypes
import hashlib
import hmac
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml


COMMANDS = ("diagnose", "init", "validate", "complete", "cleanup", "hotfix", "tweak")
PR_BODY_REQUIRED_SECTIONS = ("Summary", "Scope", "Closing References")
PR_VIEW_FIELDS = "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid,body"
BLOCKING_REVIEW_DECISIONS = {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}
SUPPORTED_REVIEW_GATE_MODES = {"github", "skip"}
DEFAULT_GH_PR_VIEW_RETRIES = 3
GH_PR_VIEW_RETRIES_ENV = "PR_FLOW_GH_PR_VIEW_RETRIES"
PR_TEMPLATE = """## Summary

<!-- 用一句话说明本次 PR 的目的和主要变化。 -->

## Scope

<!-- 列出本次 PR 的影响范围，例如代码、测试、文档或配置。 -->

## Closing References

<!-- 写 Fixes #123；没有关闭的问题单时写 None。 -->
"""
PR_FLOW_GITIGNORE = "/runs/\n/last-status.json\n"
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)



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
            "hotfix": {
                "verifyCommand": "python .build-and-verify/runtime/build_and_verify.py verify --project . --full"
            },
            "wait": {"timeoutSeconds": 600, "pollSeconds": 15},
            "pr": {
                "bodyTemplatePath": ".pr-flow/pr-template.md",
                "requiredSections": list(PR_BODY_REQUIRED_SECTIONS),
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


def load_config_path(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config_path_for_validation(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    try:
        config = load_config_path(path)
    except yaml.YAMLError as exc:
        return {}, [{"level": "error", "message": f"config YAML parse failed: {exc.problem or exc.__class__.__name__}"}]
    if not isinstance(config, dict):
        return {}, [{"level": "error", "message": "config must be a mapping"}]
    return config, []


def add_issue(issues: list[dict[str, str]], level: str, message: str) -> None:
    issues.append({"level": level, "message": message})


def validation_has_errors(issues: list[dict[str, str]]) -> bool:
    return any(issue["level"] == "error" for issue in issues)


def setup_github_from_config(config: dict[str, Any]) -> dict[str, Any]:
    setup = config.get("setup")
    github = setup.get("github") if isinstance(setup, dict) else None
    return github if isinstance(github, dict) else {}


def positive_int(value: Any) -> bool:
    return isinstance(value, int) and value > 0


def validate_config(config: dict[str, Any], project: Path | None = None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(config, dict):
        add_issue(issues, "error", "config must be a mapping")
        return issues

    defaults = defaults_from_config(config)
    if not defaults.get("baseBranch"):
        add_issue(issues, "error", "defaults.baseBranch missing")

    branches = config.get("branches")
    if not isinstance(branches, dict) or not branches:
        add_issue(issues, "error", "branches must contain at least one branch")

    merge_strategy = defaults.get("mergeStrategy", "merge")
    if merge_strategy and merge_strategy not in {"merge", "squash", "rebase"}:
        add_issue(issues, "error", f"defaults.mergeStrategy unsupported: {merge_strategy}")
    elif isinstance(merge_strategy, str) and merge_strategy:
        add_issue(issues, "remote task", f"enable GitHub merge method: {merge_strategy}")

    review_gate = defaults.get("reviewGate")
    review_gate = review_gate if isinstance(review_gate, dict) else {}
    review_mode = review_gate["mode"] if "mode" in review_gate else "github"
    if not isinstance(review_mode, str) or review_mode not in SUPPORTED_REVIEW_GATE_MODES:
        add_issue(issues, "error", f"defaults.reviewGate.mode unsupported: {review_mode}")
    elif review_mode == "github":
        add_issue(issues, "remote task", "configure GitHub required review")
    if "evidencePath" in review_gate:
        add_issue(issues, "warning", "defaults.reviewGate.evidencePath is deprecated and is not read")
    wait = defaults.get("wait")
    if wait is not None and not isinstance(wait, dict):
        add_issue(issues, "error", "defaults.wait must be a mapping")
    elif isinstance(wait, dict):
        for key in ("timeoutSeconds", "pollSeconds"):
            if key in wait and not positive_int(wait[key]):
                add_issue(issues, "error", f"defaults.wait.{key} must be a positive integer")

    github = setup_github_from_config(config)
    if github.get("requiredChecks"):
        add_issue(issues, "remote task", "configure GitHub Rulesets required checks")
    if github.get("codeScanning"):
        add_issue(issues, "remote task", "enable CodeQL Default setup")
        add_issue(issues, "remote task", "configure GitHub Rulesets CodeQL code scanning")
    if github.get("requiredReview") is True or github.get("requiredReviews") is True:
        add_issue(issues, "remote task", "tweak cannot bypass GitHub required review")
    if github.get("autoDeleteHeadBranch") is True:
        add_issue(issues, "warning", "GitHub auto-delete head branch overlaps with pr-flow cleanup")

    authorization = config.get("authorization")
    authorization = authorization if isinstance(authorization, dict) else {}
    for branch_name, branch in branches.items() if isinstance(branches, dict) else []:
        branch = branch if isinstance(branch, dict) else {}
        if branch.get("allowHotfixPush") is not True:
            continue
        merged_branch = branch_config_for_target(config, str(branch_name))
        if authorization.get("phraseHashAlgorithm") != "md5":
            add_issue(issues, "error", "authorization.phraseHashAlgorithm must be md5")
        if not authorization.get("phraseHash"):
            add_issue(issues, "error", "authorization.phraseHash missing")
        hotfix = merged_branch.get("hotfix")
        verify_command = hotfix.get("verifyCommand") if isinstance(hotfix, dict) else None
        if not verify_command:
            add_issue(issues, "error", f"branches.{branch_name}.hotfix.verifyCommand missing")
        if not branch.get("remote"):
            add_issue(issues, "error", f"branches.{branch_name}.remote missing")
        add_issue(issues, "remote task", f"configure GitHub Rulesets bypass for {branch_name}")

    return issues


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
    command = ["git", *args]
    try:
        return subprocess.run(
            command,
            cwd=project,
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(command, 127, "", str(exc))


def gh(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("gh") or "gh"
    command = [executable, *args]
    try:
        return subprocess.run(
            command,
            cwd=project,
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(command, 127, "", str(exc))


class PrFlowError(RuntimeError):
    def __init__(self, reason: str, details: dict[str, Any]) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details


def stop(project: Path, command: str, status: str, message: str, details: dict[str, Any]) -> int:
    write_status(project, command, status, details)
    print_stop(status, message)
    return 1


GH_AUTH_REQUIRED_MARKERS = (
    "gh auth login",
    "not logged into any github hosts",
    "authentication required",
    "requires authentication",
    "bad credentials",
    "http 401",
)

RECOVERABLE_NEXT_ACTIONS = {
    "checks_pending": {
        "nextAction": "Wait for GitHub checks to finish, then rerun the same PR Flow command.",
    },
    "checks_or_review_blocking": {
        "nextAction": "Fix failing checks or requested changes, then rerun the same PR Flow command.",
    },
    "ruleset_merge_blocking": {
        "nextAction": "Wait for ruleset requirements to pass or enable auto-merge, then rerun the same PR Flow command.",
    },
    "gh_auth_required": {
        "nextCommand": "gh auth status",
    },
}


def gh_auth_required(result: subprocess.CompletedProcess[str]) -> bool:
    text = f"{result.stdout}\n{result.stderr}".lower()
    return any(marker in text for marker in GH_AUTH_REQUIRED_MARKERS)


def classify_command_failure(reason: str, result: subprocess.CompletedProcess[str]) -> str:
    if reason.startswith("gh_") and gh_auth_required(result):
        return "gh_auth_required"
    return reason


def add_recovery_action(details: dict[str, Any], next_command: str | None = None) -> dict[str, Any]:
    reason = str(details.get("reason") or "")
    if next_command and reason in {"gh_pr_view_transient_failed", "checks_pending", "ruleset_merge_blocking"}:
        details.setdefault("nextCommand", next_command)
    for key, value in RECOVERABLE_NEXT_ACTIONS.get(reason, {}).items():
        details.setdefault(key, value)
    return details


def command_failure_details(reason: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    classified_reason = classify_command_failure(reason, result)
    return add_recovery_action({
        "reason": classified_reason,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    })


def transient_pr_view_category(result: subprocess.CompletedProcess[str]) -> str:
    text = f"{result.stdout}\n{result.stderr}".lower()
    return "eof" if "eof" in text else ""


def gh_pr_view_retries() -> int:
    raw = os.environ.get(GH_PR_VIEW_RETRIES_ENV)
    if raw is None:
        return DEFAULT_GH_PR_VIEW_RETRIES
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_GH_PR_VIEW_RETRIES


def gh_pr_view(project: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], str, int]:
    result = gh(project, *args)
    category = transient_pr_view_category(result) if result.returncode != 0 else ""
    retry_attempts = 0
    for _ in range(gh_pr_view_retries()):
        if result.returncode == 0 or not category:
            break
        retry_attempts += 1
        result = gh(project, *args)
        category = transient_pr_view_category(result) if result.returncode != 0 else ""
    return result, category, retry_attempts


def pr_view_failure_details(
    result: subprocess.CompletedProcess[str],
    transient_category: str,
    retry_attempts: int,
    *,
    pr: str | None = None,
    next_command: str | None = None,
) -> tuple[str, dict[str, Any]]:
    reason = "gh_pr_view_transient_failed" if transient_category else "gh_pr_view_failed"
    details = command_failure_details(reason, result)
    reason = str(details["reason"])
    if pr is not None:
        details["pr"] = pr
    if transient_category:
        details["transientCategory"] = transient_category
        details["retryAttempts"] = retry_attempts
    add_recovery_action(details, next_command)
    return reason, details


def error_status(reason: str) -> str:
    if reason in {"gh_auth_required", "gh_pr_view_transient_failed", "checks_pending", "ruleset_merge_blocking"}:
        return "DISPATCH_REQUIRED"
    if reason in {"checks_or_review_blocking", "invalid_fixes"}:
        return "REPLY_OR_FIX_REQUIRED"
    return "EXCEPTION_REQUIRED"


def add_default_next_command(details: dict[str, Any], next_command: str | None) -> dict[str, Any]:
    return add_recovery_action(details, next_command)


def command_next_command(command: str, project: Path, args: argparse.Namespace | None = None) -> str:
    command_args = [
        sys.executable,
        "plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py",
        command,
        "--project",
        str(project),
    ]
    if command == "cleanup" and args is not None:
        command_args.extend(["--pr", str(getattr(args, "pr", "<number>"))])
    return " ".join(shlex.quote(part) for part in command_args)


def pr_body_next_command(command: str, project: Path, args: argparse.Namespace) -> str:
    command_args = [
        sys.executable,
        "plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py",
        command,
        "--project",
        str(project),
    ]
    if command == "tweak":
        command_args.extend(["--reason", str(getattr(args, "reason", "") or "small docs polish")])
    command_args.extend(["--summary", str(getattr(args, "summary", "") or "说明本次 PR 的主要变化")])
    command_args.extend(["--scope", str(getattr(args, "scope", "") or "列出本次 PR 的影响范围")])
    for issue in getattr(args, "fixes", []) or []:
        command_args.extend(["--fixes", str(issue)])
    return " ".join(shlex.quote(part) for part in command_args)


def require_pr_body_args(project: Path, command: str, args: argparse.Namespace) -> tuple[str, str, list[str]]:
    summary = str(getattr(args, "summary", "") or "").strip()
    scope = str(getattr(args, "scope", "") or "").strip()
    fixes = [str(issue).strip() for issue in (getattr(args, "fixes", None) or []) if str(issue).strip()]
    invalid_fixes = [issue for issue in fixes if not issue.isdecimal() or int(issue) <= 0]
    if invalid_fixes:
        next_action = "Pass each issue number separately, for example --fixes 41 --fixes 43 --fixes 44."
        if any(issue.lower() == "none" for issue in invalid_fixes):
            next_action = "Remove --fixes when there is no issue to close."
        raise PrFlowError(
            "invalid_fixes",
            {
                "reason": "invalid_fixes",
                "invalidFixes": invalid_fixes,
                "nextAction": next_action,
            },
        )
    missing = []
    if not summary:
        missing.append("--summary")
    if not scope:
        missing.append("--scope")
    if missing:
        raise PrFlowError(
            "pr_body_required",
            {
                "reason": "pr_body_required",
                "missingArgs": missing,
                "nextCommand": pr_body_next_command(command, project, args),
            },
        )
    return summary, scope, fixes


def pr_body_config(config: dict[str, Any]) -> dict[str, Any]:
    pr_config = defaults_from_config(config).get("pr")
    return pr_config if isinstance(pr_config, dict) else {}


def pr_body_template_path(project: Path, config: dict[str, Any]) -> Path:
    value = pr_body_config(config).get("bodyTemplatePath", ".pr-flow/pr-template.md")
    path = Path(value) if isinstance(value, str) and value else Path(".pr-flow/pr-template.md")
    return path if path.is_absolute() else project / path


def strip_html_comments(value: Any) -> str:
    text = value if isinstance(value, str) else ""
    return HTML_COMMENT_RE.sub("", text).strip()


def render_pr_body(project: Path, config: dict[str, Any], summary: str, scope: str, fixes: Sequence[str]) -> str:
    template_path = pr_body_template_path(project, config)
    configured_sections = pr_body_config(config).get("requiredSections")
    configured_sections = configured_sections if isinstance(configured_sections, list) else []
    template = template_path.read_text(encoding="utf-8") if template_path.exists() else ""
    missing_sections = [
        section
        for section in PR_BODY_REQUIRED_SECTIONS
        if section not in configured_sections or f"## {section}" not in template
    ]
    if not template.strip() or missing_sections:
        raise PrFlowError(
            "pr_body_required",
            {
                "reason": "pr_body_required",
                "templatePath": str(template_path),
                "missingSections": missing_sections,
                "nextAction": "Add ## Summary, ## Scope, and ## Closing References to the PR body template.",
            },
        )
    references = "\n".join(f"Fixes #{issue}" for issue in fixes) if fixes else "None"
    # The template is a validation contract and authoring guide; rendering stays deterministic here.
    return f"## Summary\n\n{summary}\n\n## Scope\n\n{scope}\n\n## Closing References\n\n{references}\n"


def base_branch_from_config(config: dict[str, Any]) -> str:
    defaults = config.get("defaults")
    if not isinstance(defaults, dict):
        return "main"
    base_branch = defaults.get("baseBranch")
    return base_branch if isinstance(base_branch, str) and base_branch else "main"


def remote_for_base_branch(config: dict[str, Any], base_branch: str) -> str:
    branches = config.get("branches")
    if not isinstance(branches, dict):
        return "origin"
    branch_config = branches.get(base_branch)
    if not isinstance(branch_config, dict):
        return "origin"
    remote = branch_config.get("remote")
    return remote if isinstance(remote, str) and remote else "origin"


def require_authorization_phrase_configured(config: dict[str, Any]) -> None:
    authorization = config.get("authorization")
    if not isinstance(authorization, dict):
        raise PrFlowError("authorization_phrase_missing", {"reason": "authorization_phrase_missing"})

    algorithm = authorization.get("phraseHashAlgorithm")
    expected_hash = authorization.get("phraseHash")
    if algorithm != "md5":
        raise PrFlowError(
            "authorization_phrase_unsupported",
            {
                "reason": "authorization_phrase_unsupported",
                "phraseHashAlgorithm": algorithm,
            },
        )
    if not isinstance(expected_hash, str) or not expected_hash:
        raise PrFlowError("authorization_phrase_missing", {"reason": "authorization_phrase_missing"})


def verify_authorization_phrase(config: dict[str, Any], phrase: str) -> None:
    require_authorization_phrase_configured(config)
    expected_hash = config["authorization"]["phraseHash"]

    actual_hash = hashlib.md5(phrase.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(actual_hash, expected_hash):
        raise PrFlowError("authorization_phrase_mismatch", {"reason": "authorization_phrase_mismatch"})


def defaults_from_config(config: dict[str, Any]) -> dict[str, Any]:
    defaults = config.get("defaults")
    return defaults if isinstance(defaults, dict) else {}


def branch_config_for_target(config: dict[str, Any], target: str) -> dict[str, Any]:
    defaults = defaults_from_config(config)
    branches = config.get("branches")
    branch_config = branches.get(target) if isinstance(branches, dict) else None
    branch_config = branch_config if isinstance(branch_config, dict) else {}

    merged = dict(defaults)
    merged.update(branch_config)

    default_hotfix = defaults.get("hotfix")
    branch_hotfix = branch_config.get("hotfix")
    hotfix_config: dict[str, Any] = {}
    if isinstance(default_hotfix, dict):
        hotfix_config.update(default_hotfix)
    if isinstance(branch_hotfix, dict):
        hotfix_config.update(branch_hotfix)
    if hotfix_config:
        merged["hotfix"] = hotfix_config
    return merged


def target_explicitly_allows_hotfix_push(config: dict[str, Any], target: str) -> bool:
    branches = config.get("branches")
    branch_config = branches.get(target) if isinstance(branches, dict) else None
    if not isinstance(branch_config, dict):
        return False
    return branch_config.get("allowHotfixPush") is True


def hotfix_remote(branch_config: dict[str, Any]) -> str:
    remote = branch_config.get("remote")
    return remote if isinstance(remote, str) and remote else "origin"


def hotfix_verify_command(branch_config: dict[str, Any]) -> str:
    hotfix_config = branch_config.get("hotfix")
    verify_command = hotfix_config.get("verifyCommand") if isinstance(hotfix_config, dict) else None
    if not isinstance(verify_command, str) or not verify_command:
        raise PrFlowError("hotfix_verify_command_missing", {"reason": "hotfix_verify_command_missing"})
    return verify_command


def split_hotfix_verify_command(command: str) -> list[str]:
    if os.name != "nt":
        if "\\" not in command:
            return shlex.split(command)
        placeholder = "\0"
        return [part.replace(placeholder, "\\") for part in shlex.split(command.replace("\\", placeholder))]

    argc = ctypes.c_int()
    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32
    shell32.CommandLineToArgvW.argtypes = (ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int))
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel32.LocalFree.restype = ctypes.c_void_p

    argv = shell32.CommandLineToArgvW(command, ctypes.byref(argc))
    if not argv:
        raise ValueError("windows_command_line_parse_failed")
    try:
        return [argv[index] for index in range(argc.value)]
    finally:
        kernel32.LocalFree(ctypes.cast(argv, ctypes.c_void_p))


def wait_config_from_config(config: dict[str, Any]) -> dict[str, Any]:
    wait_config = defaults_from_config(config).get("wait")
    return wait_config if isinstance(wait_config, dict) else {}


def review_gate_config(config: dict[str, Any]) -> dict[str, Any]:
    review_gate = defaults_from_config(config).get("reviewGate")
    return review_gate if isinstance(review_gate, dict) else {"mode": "github"}


def merge_strategy_flag(config: dict[str, Any]) -> str:
    strategy = defaults_from_config(config).get("mergeStrategy", "merge")
    flags = {
        "merge": "--merge",
        "squash": "--squash",
        "rebase": "--rebase",
    }
    if not isinstance(strategy, str) or strategy not in flags:
        raise PrFlowError(
            "unknown_merge_strategy",
            {
                "reason": "unknown_merge_strategy",
                "mergeStrategy": strategy,
            },
        )
    return flags[strategy]


def stop_state(status: str, message: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"status": status, "message": message, "details": details}


def stop_from_state(project: Path, command: str, state: dict[str, Any]) -> int:
    return stop(project, command, state["status"], state["message"], state["details"])


def check_value(check: dict[str, Any], key: str) -> str:
    value = check.get(key)
    return value.upper() if isinstance(value, str) else ""


def pr_checks(pr: dict[str, Any]) -> list[Any]:
    checks = pr.get("statusCheckRollup")
    return checks if isinstance(checks, list) else []


def has_pending_check(checks: list[Any]) -> bool:
    pending_values = {"PENDING", "IN_PROGRESS", "QUEUED", "REQUESTED", "WAITING", "EXPECTED"}
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check_value(check, "status") in pending_values or check_value(check, "state") in pending_values:
            return True
    return False


def has_failing_check(checks: list[Any]) -> bool:
    failing_values = {"FAILURE", "FAILED", "ERROR", "TIMED_OUT", "CANCELLED", "STARTUP_FAILURE"}
    for check in checks:
        if not isinstance(check, dict):
            continue
        if (
            check_value(check, "conclusion") in failing_values
            or check_value(check, "status") in failing_values
            or check_value(check, "state") in failing_values
        ):
            return True
    return False


def parse_pr_result(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        pr = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        details = command_failure_details("gh_pr_view_parse_failed", result)
        details["error"] = str(exc)
        raise PrFlowError("gh_pr_view_parse_failed", details) from exc
    if not isinstance(pr, dict):
        details = command_failure_details("gh_pr_view_parse_failed", result)
        raise PrFlowError("gh_pr_view_parse_failed", details)
    return pr


def gh_pr_not_found(result: subprocess.CompletedProcess[str]) -> bool:
    text = f"{result.stdout}\n{result.stderr}".lower()
    return "no pull request" in text or "no pull requests" in text


def gh_pr_merge_policy_blocked(result: subprocess.CompletedProcess[str]) -> bool:
    text = f"{result.stdout}\n{result.stderr}".lower()
    return "base branch policy prohibits the merge" in text


def gh_pr_merge_auto_suggested(result: subprocess.CompletedProcess[str]) -> bool:
    text = f"{result.stdout}\n{result.stderr}".lower()
    return "add the --auto flag" in text or "add --auto" in text


def auto_push_current_branch_if_needed(
    project: Path,
    config: dict[str, Any],
    next_command: str | None = None,
) -> dict[str, Any] | None:
    base_branch = base_branch_from_config(config)
    branch_result = git(project, "branch", "--show-current")
    if branch_result.returncode != 0 or not branch_result.stdout.strip():
        details = command_failure_details("git_current_branch_failed", branch_result)
        return stop_state("EXCEPTION_REQUIRED", details["reason"], details)
    branch = branch_result.stdout.strip()

    upstream_result = git(project, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream_result.returncode == 0:
        ahead_result = git(project, "rev-list", "--count", "@{u}..HEAD")
        if ahead_result.returncode != 0:
            details = command_failure_details("git_ahead_check_failed", ahead_result)
            details.update({"branch": branch, "baseBranch": base_branch, "upstream": upstream_result.stdout.strip()})
            return stop_state("EXCEPTION_REQUIRED", details["reason"], details)
        try:
            ahead_count = int(ahead_result.stdout.strip() or "0")
        except ValueError:
            details = {
                "reason": "git_ahead_check_invalid",
                "branch": branch,
                "baseBranch": base_branch,
                "upstream": upstream_result.stdout.strip(),
                "stdout": ahead_result.stdout,
            }
            return stop_state("EXCEPTION_REQUIRED", "git_ahead_check_invalid", details)
        behind_result = git(project, "rev-list", "--count", "HEAD..@{u}")
        if behind_result.returncode != 0:
            details = command_failure_details("git_behind_check_failed", behind_result)
            details.update(
                {
                    "branch": branch,
                    "baseBranch": base_branch,
                    "upstream": upstream_result.stdout.strip(),
                }
            )
            return stop_state("EXCEPTION_REQUIRED", details["reason"], details)
        try:
            behind_count = int(behind_result.stdout.strip() or "0")
        except ValueError:
            details = {
                "reason": "git_behind_check_invalid",
                "branch": branch,
                "baseBranch": base_branch,
                "upstream": upstream_result.stdout.strip(),
                "stdout": behind_result.stdout,
            }
            return stop_state("EXCEPTION_REQUIRED", "git_behind_check_invalid", details)
        if behind_count > 0:
            details = {
                "reason": "upstream_branch_diverged",
                "branch": branch,
                "baseBranch": base_branch,
                "upstream": upstream_result.stdout.strip(),
                "aheadCount": ahead_count,
                "behindCount": behind_count,
                "syncCommand": "git pull --rebase",
            }
            if next_command:
                details["nextCommand"] = next_command
            return stop_state("EXCEPTION_REQUIRED", "sync upstream before pushing", details)
        if ahead_count <= 0:
            return None
        push_args = ("push",)
        next_command = "git push"
    else:
        if branch == base_branch:
            return None
        remote = remote_for_base_branch(config, base_branch)
        push_args = ("push", "-u", remote, branch)
        next_command = f"git push -u {remote} {branch}"

    details = {"reason": "auto_push_required", "branch": branch, "baseBranch": base_branch, "nextCommand": next_command}
    if branch == base_branch:
        details["reason"] = "protected_branch_auto_push_blocked"
        return stop_state("EXCEPTION_REQUIRED", "protected_branch_auto_push_blocked", details)

    status_result = git(project, "status", "--porcelain")
    if status_result.returncode != 0:
        error_details = command_failure_details("git_status_failed", status_result)
        error_details.update(details)
        error_details["reason"] = "git_status_failed"
        return stop_state("EXCEPTION_REQUIRED", "git_status_failed", error_details)
    dirty_files = [line for line in status_result.stdout.splitlines() if line]
    if dirty_files:
        dirty_details = dict(details)
        dirty_details["reason"] = "worktree_dirty"
        dirty_details["dirtyFiles"] = dirty_files
        return stop_state("EXCEPTION_REQUIRED", "worktree_dirty", dirty_details)

    branch_rules_endpoint = f"repos/{{owner}}/{{repo}}/rules/branches/{quote(branch, safe='')}"
    rules_result = gh(project, "api", branch_rules_endpoint, "--jq", "length")
    if rules_result.returncode != 0:
        error_details = command_failure_details("remote_branch_rules_lookup_failed", rules_result)
        error_details.update(details)
        error_details["reason"] = "remote_branch_rules_lookup_failed"
        return stop_state("EXCEPTION_REQUIRED", "remote_branch_rules_lookup_failed", error_details)
    try:
        rule_count = int(rules_result.stdout.strip() or "0")
    except ValueError:
        invalid_details = dict(details)
        invalid_details["reason"] = "remote_branch_rules_lookup_invalid"
        invalid_details["stdout"] = rules_result.stdout
        return stop_state("EXCEPTION_REQUIRED", "remote_branch_rules_lookup_invalid", invalid_details)
    if rule_count > 0:
        protected_details = dict(details)
        protected_details["reason"] = "protected_branch_auto_push_blocked"
        protected_details["activeRules"] = rule_count
        return stop_state("EXCEPTION_REQUIRED", "protected_branch_auto_push_blocked", protected_details)

    push_result = git(project, *push_args)
    if push_result.returncode != 0:
        push_details = command_failure_details("git_push_failed", push_result)
        push_details.update(details)
        push_details["reason"] = "git_push_failed"
        return stop_state("PUSH_REQUIRED", "push current branch before continuing", push_details)
    return None


def find_pr(project: Path) -> dict[str, Any] | None:
    result, transient_category, retry_attempts = gh_pr_view(project, "pr", "view", "--json", PR_VIEW_FIELDS)
    if result.returncode != 0:
        if gh_pr_not_found(result):
            return None
        reason, details = pr_view_failure_details(result, transient_category, retry_attempts)
        raise PrFlowError(reason, details)
    return parse_pr_result(result)


def sync_pr(project: Path, pr: dict[str, Any]) -> dict[str, Any]:
    current = find_pr(project)
    if current is None:
        raise PrFlowError(
            "gh_pr_view_failed",
            {
                "reason": "gh_pr_view_failed",
                "pr": pr.get("number"),
                "headRefName": pr.get("headRefName"),
                "stderr": "PR disappeared during sync.",
            },
        )
    return current


def confirm_remote_branch_deleted(project: Path, remote: str, branch: str) -> None:
    result = git(project, "ls-remote", "--heads", remote, branch)
    if result.returncode != 0:
        details = command_failure_details("git_remote_delete_readback_failed", result)
        details.update({"remote": remote, "headRefName": branch})
        raise PrFlowError("git_remote_delete_readback_failed", details)
    if result.stdout.strip():
        raise PrFlowError(
            "git_remote_delete_readback_failed",
            {
                "reason": "git_remote_delete_readback_failed",
                "remote": remote,
                "headRefName": branch,
                "stdout": result.stdout.strip(),
            },
        )


def gh_with_body_file(project: Path, args: Sequence[str], body: str) -> subprocess.CompletedProcess[str]:
    body_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as body_file:
            body_file.write(body)
            body_path = Path(body_file.name)
        return gh(project, *args, "--body-file", str(body_path))
    finally:
        if body_path is not None:
            body_path.unlink(missing_ok=True)


def create_pr(project: Path, config: dict[str, Any], body: str | None = None) -> dict[str, Any]:
    args = ("pr", "create", "--base", base_branch_from_config(config), "--fill")
    result = gh_with_body_file(project, args, body) if body is not None else gh(project, *args)
    if result.returncode != 0:
        details = command_failure_details("gh_pr_create_failed", result)
        raise PrFlowError("gh_pr_create_failed", details)
    pr = find_pr(project)
    if pr is None:
        details = command_failure_details("gh_pr_create_missing_pr", result)
        raise PrFlowError("gh_pr_create_missing_pr", details)
    return pr


def pr_number_for_command(pr: dict[str, Any]) -> str:
    pr_number = pr.get("number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, (int, str)) or str(pr_number) == "":
        raise PrFlowError(
            "invalid_pr_number",
            {
                "reason": "invalid_pr_number",
                "pr": pr_number,
            },
        )
    return str(pr_number)


def update_pr_body(project: Path, pr: dict[str, Any], body: str) -> None:
    pr_number = pr_number_for_command(pr)
    result = gh_with_body_file(project, ("pr", "edit", pr_number), body)
    if result.returncode != 0:
        details = command_failure_details("gh_pr_edit_failed", result)
        details["pr"] = pr_number
        raise PrFlowError("gh_pr_edit_failed", details)


def closing_references_for_fixes(fixes: Sequence[str]) -> list[str]:
    return [f"Fixes #{issue}" for issue in fixes]


def has_closing_reference(body: str, issue: str) -> bool:
    issue_ref = re.escape(str(issue))
    return re.search(rf"(?:^|[^\w#])Fixes\s+#{issue_ref}(?![\w-])", body, re.IGNORECASE) is not None


def append_closing_references(body: str, missing_references: Sequence[str]) -> str:
    text = body.rstrip()
    references = "\n".join(missing_references)
    if "## Closing References" in text:
        return f"{text}\n{references}\n"
    return f"{text}\n\n## Closing References\n\n{references}\n"


def reconcile_existing_pr_body(project: Path, pr: dict[str, Any], body: str, fixes: Sequence[str]) -> None:
    if not strip_html_comments(pr.get("body")):
        update_pr_body(project, pr, body)
        return
    if fixes:
        existing_body = pr.get("body") if isinstance(pr.get("body"), str) else ""
        missing_references = [
            reference for issue, reference in zip(fixes, closing_references_for_fixes(fixes))
            if not has_closing_reference(existing_body, str(issue))
        ]
        if missing_references:
            update_pr_body(project, pr, append_closing_references(existing_body, missing_references))


def view_pr_for_cleanup(project: Path, pr_number: str) -> dict[str, Any]:
    fields = "number,state,headRefName,baseRefName,headRepositoryOwner"
    next_command = command_next_command("cleanup", project, argparse.Namespace(pr=pr_number))
    result, transient_category, retry_attempts = gh_pr_view(project, "pr", "view", pr_number, "--json", fields)
    if result.returncode != 0:
        reason, details = pr_view_failure_details(
            result,
            transient_category,
            retry_attempts,
            pr=pr_number,
            next_command=next_command,
        )
        raise PrFlowError(reason, details)
    return parse_pr_result(result)


def require_git_success(project: Path, reason: str, *args: str) -> subprocess.CompletedProcess[str]:
    result = git(project, *args)
    if result.returncode != 0:
        details = command_failure_details(reason, result)
        details["gitArgs"] = list(args)
        raise PrFlowError(reason, details)
    return result


def head_oid(project: Path) -> str:
    return require_git_success(project, "git_head_oid_failed", "rev-parse", "HEAD").stdout.strip()


def merge_pr(project: Path, config: dict[str, Any], pr: dict[str, Any], *, auto: bool = False) -> dict[str, Any] | None:
    pr_number = pr.get("number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, (int, str)) or str(pr_number) == "":
        raise PrFlowError(
            "invalid_pr_number",
            {
                "reason": "invalid_pr_number",
                "pr": pr_number,
            },
        )

    expected_head_oid = pr.get("headRefOid")
    if not isinstance(expected_head_oid, str) or not expected_head_oid:
        raise PrFlowError(
            "missing_head_ref_oid",
            {
                "reason": "missing_head_ref_oid",
                "pr": pr_number,
                "headRefName": pr.get("headRefName"),
            },
        )

    strategy_flag = merge_strategy_flag(config)
    current_head_oid = head_oid(project)
    if current_head_oid != expected_head_oid:
        raise PrFlowError(
            "head_moved",
            {
                "reason": "head_moved",
                "pr": pr_number,
                "headRefName": pr.get("headRefName"),
                "headRefOid": expected_head_oid,
                "currentHeadOid": current_head_oid,
            },
        )

    merge_args = ["pr", "merge", str(pr_number), strategy_flag, "--match-head-commit", current_head_oid]
    if auto:
        merge_args.append("--auto")
    result = gh(project, *merge_args)
    if result.returncode != 0:
        details = command_failure_details("gh_pr_merge_failed", result)
        details.update(
            {
                "pr": pr_number,
                "headRefName": pr.get("headRefName"),
                "headRefOid": expected_head_oid,
                "mergeStrategy": defaults_from_config(config).get("mergeStrategy", "merge"),
            }
        )
        if gh_pr_merge_policy_blocked(result):
            details["reason"] = "ruleset_merge_blocking"
            details["autoMergeSuggested"] = gh_pr_merge_auto_suggested(result)
            raise PrFlowError("ruleset_merge_blocking", add_recovery_action(details))
        raise PrFlowError("gh_pr_merge_failed", details)
    return None


def require_cleanup_pr_fields(pr: dict[str, Any]) -> tuple[str, str]:
    head_ref = pr.get("headRefName")
    base_ref = pr.get("baseRefName")
    if not isinstance(head_ref, str) or not head_ref or not isinstance(base_ref, str) or not base_ref:
        raise PrFlowError(
            "invalid_pr_branch",
            {
                "reason": "invalid_pr_branch",
                "pr": pr.get("number"),
                "headRefName": head_ref,
                "baseRefName": base_ref,
            },
        )
    return head_ref, base_ref


def wait_for_checks(
    project: Path,
    pr: dict[str, Any],
    wait_config: dict[str, Any],
) -> dict[str, Any] | None:
    timeout_seconds = int(wait_config.get("timeoutSeconds", 600))
    poll_seconds = int(wait_config.get("pollSeconds", 15))
    started_at = time.monotonic()
    current = pr

    while True:
        checks = pr_checks(current)
        details = {
            "reason": "checks_pending",
            "pr": current.get("number"),
            "headRefName": current.get("headRefName"),
            "baseRefName": current.get("baseRefName"),
        }
        if has_failing_check(checks):
            details["reason"] = "checks_or_review_blocking"
            return stop_state("REPLY_OR_FIX_REQUIRED", "checks_or_review_blocking", add_recovery_action(details))
        if not has_pending_check(checks):
            return None
        if timeout_seconds <= 0:
            return stop_state("DISPATCH_REQUIRED", "checks_pending", add_recovery_action(details))

        remaining = timeout_seconds - (time.monotonic() - started_at)
        if remaining <= 0:
            return stop_state("DISPATCH_REQUIRED", "checks_pending", add_recovery_action(details))
        time.sleep(min(max(poll_seconds, 1), remaining))
        current = sync_pr(project, current)


def retry_merge_after_ruleset_block(
    project: Path,
    config: dict[str, Any],
    pr: dict[str, Any],
    merge_details: dict[str, Any],
) -> dict[str, Any] | None:
    current = sync_pr(project, pr)
    check_stop = wait_for_checks(project, current, wait_config_from_config(config))
    if check_stop is not None:
        return check_stop
    try:
        merge_pr(project, config, current, auto=merge_details.get("autoMergeSuggested") is True)
    except PrFlowError as exc:
        if exc.reason == "ruleset_merge_blocking" and exc.details.get("autoMergeSuggested") is True:
            merge_pr(project, config, current, auto=True)
            return None
        raise
    return None


def review_gate_mode(config: dict[str, Any]) -> Any:
    review_gate = review_gate_config(config)
    return review_gate["mode"] if "mode" in review_gate else "github"


def github_review_is_blocking(pr: dict[str, Any]) -> bool:
    return pr.get("reviewDecision") in BLOCKING_REVIEW_DECISIONS


def check_review_gate(project: Path, config: dict[str, Any], pr: dict[str, Any]) -> dict[str, Any] | None:
    mode = review_gate_mode(config)
    details = {
        "reason": "review_gate_blocking",
        "reviewGateMode": mode,
        "reviewDecision": pr.get("reviewDecision"),
        "pr": pr.get("number"),
        "headRefName": pr.get("headRefName"),
        "baseRefName": pr.get("baseRefName"),
    }
    if mode == "skip":
        return None
    if mode != "github":
        details["reason"] = "unknown_review_gate_mode"
        return stop_state("EXCEPTION_REQUIRED", "unknown_review_gate_mode", details)

    if github_review_is_blocking(pr):
        return stop_state("REPLY_OR_FIX_REQUIRED", "review_gate_blocking", details)

    return None


def run_init(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    pr_flow_dir = project / ".pr-flow"

    if args.config is None:
        print("status: confirmed_config_required")
        if getattr(args, "base_branch", None):
            print("confirmed config required: --base-branch no longer generates defaults")
        print("confirmed config required: use pr-flow-init Skill to create YAML with defaults and branches, then pass --config <path>")
        return 2

    config, issues = load_config_path_for_validation(args.config)
    if not issues:
        issues = validate_config(config, args.project)
    if validation_has_errors(issues):
        print("status: validation_failed")
        for issue in issues:
            print(f"{issue['level']}: {issue['message']}")
        return 1

    config_text = yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
    pr_flow_dir.mkdir(parents=True, exist_ok=True)
    (pr_flow_dir / "config.yaml").write_text(config_text, encoding="utf-8")
    write_text_if_missing(pr_flow_dir / "pr-template.md", PR_TEMPLATE)
    write_text_if_missing(pr_flow_dir / ".gitignore", PR_FLOW_GITIGNORE)

    print("status: initialized")
    for issue in issues:
        if issue["level"] == "warning":
            print(f"warning: {issue['message']}")
        elif issue["level"] == "remote task":
            print(f"GitHub remote task: {issue['message']}")
    return 0


def run_validate(args: argparse.Namespace) -> int:
    config, issues = load_config_path_for_validation(args.config)
    if not issues:
        issues = validate_config(config, args.project)
    if validation_has_errors(issues):
        print("status: validation_failed")
    else:
        print("status: validation_passed")
    for issue in issues:
        print(f"{issue['level']}: {issue['message']}")
    return 1 if validation_has_errors(issues) else 0


def run_diagnose(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    try:
        config = load_config(project)
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)

    base_branch = base_branch_from_config(config)
    branch_result = git(project, "branch", "--show-current")
    if branch_result.returncode != 0 or not branch_result.stdout.strip():
        details = command_failure_details("git_current_branch_failed", branch_result)
        return stop(project, args.command, "EXCEPTION_REQUIRED", details["reason"], details)
    branch = branch_result.stdout.strip()

    upstream_result = git(project, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    upstream = upstream_result.stdout.strip() if upstream_result.returncode == 0 else ""

    status_result = git(project, "status", "--short")
    if status_result.returncode != 0:
        details = command_failure_details("git_status_failed", status_result)
        details["branch"] = branch
        details["baseBranch"] = base_branch
        details["upstream"] = upstream
        return stop(project, args.command, "EXCEPTION_REQUIRED", details["reason"], details)
    dirty = status_result.stdout.strip()

    if upstream_result.returncode != 0 and branch != base_branch:
        details = command_failure_details("missing_upstream", upstream_result)
        details.update(
            {
                "branch": branch,
                "baseBranch": base_branch,
                "upstream": "",
                "dirty": dirty,
                "reason": "missing_upstream",
                "nextCommand": pr_body_next_command(
                    "complete",
                    project,
                    argparse.Namespace(summary="", scope="", fixes=[]),
                ),
                "optionalFixesArg": "--fixes 98",
            }
        )
        return stop(project, args.command, "DISPATCH_REQUIRED", "missing_upstream", details)

    pr_result, transient_category, retry_attempts = gh_pr_view(project, "pr", "view", "--json", PR_VIEW_FIELDS)
    gh_details: dict[str, Any] = {
        "branch": branch,
        "baseBranch": base_branch,
        "upstream": upstream,
        "dirty": dirty,
    }
    if pr_result.returncode != 0:
        reason, failure_details = pr_view_failure_details(
            pr_result,
            transient_category,
            retry_attempts,
            next_command=command_next_command(args.command, project),
        )
        gh_details.update(failure_details)
        if not transient_category and gh_pr_not_found(pr_result) and branch != base_branch:
            gh_details["reason"] = "pr_missing"
            gh_details["nextCommand"] = pr_body_next_command(
                "complete",
                project,
                argparse.Namespace(summary="", scope="", fixes=[]),
            )
            gh_details["optionalFixesArg"] = "--fixes 98"
            return stop(project, args.command, "DISPATCH_REQUIRED", "pr_missing", gh_details)
        return stop(project, args.command, error_status(reason), reason, gh_details)

    try:
        pr = json.loads(pr_result.stdout)
    except json.JSONDecodeError as exc:
        gh_details.update({"reason": "gh_pr_view_parse_failed", "error": str(exc), "stdout": pr_result.stdout.strip()})
        return stop(project, args.command, "EXCEPTION_REQUIRED", "gh_pr_view_parse_failed", gh_details)
    if not isinstance(pr, dict):
        gh_details.update({"reason": "gh_pr_view_parse_failed", "stdout": pr_result.stdout.strip()})
        return stop(project, args.command, "EXCEPTION_REQUIRED", "gh_pr_view_parse_failed", gh_details)

    gh_details.update(
        {
            "reason": "pr_state",
            "pr": pr.get("number"),
            "reviewDecision": pr.get("reviewDecision"),
            "mergeStateStatus": pr.get("mergeStateStatus"),
            "isDraft": pr.get("isDraft"),
            "headRefName": pr.get("headRefName"),
            "baseRefName": pr.get("baseRefName"),
        }
    )
    if not strip_html_comments(pr.get("body")):
        gh_details["reason"] = "pr_body_required"
        gh_details["nextCommand"] = pr_body_next_command(
            "complete",
            project,
            argparse.Namespace(summary="", scope="", fixes=[]),
        )
        gh_details["optionalFixesArg"] = "--fixes 98"
        return stop(project, args.command, "EXCEPTION_REQUIRED", "pr_body_required", gh_details)
    checks = pr_checks(pr)
    if has_pending_check(checks):
        gh_details["reason"] = "checks_pending"
        return stop(
            project,
            args.command,
            "DISPATCH_REQUIRED",
            "checks_pending",
            add_recovery_action(gh_details, command_next_command(args.command, project)),
        )
    if has_failing_check(checks) or pr.get("reviewDecision") in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
        gh_details["reason"] = "checks_or_review_blocking"
        return stop(project, args.command, "REPLY_OR_FIX_REQUIRED", "checks_or_review_blocking", add_recovery_action(gh_details))
    if pr.get("isDraft") is True:
        gh_details["reason"] = "pr_is_draft"
        gh_details["nextCommand"] = "gh pr ready"
        return stop(project, args.command, "DISPATCH_REQUIRED", "pr_is_draft", gh_details)

    gh_details["reason"] = "ready_to_complete"
    gh_details["nextCommand"] = pr_body_next_command(
        "complete",
        project,
        argparse.Namespace(summary="", scope="", fixes=[]),
    )
    gh_details["optionalFixesArg"] = "--fixes 98"
    write_status(project, args.command, "ready", gh_details)
    print("status: ready")
    print("ready_to_complete")
    return 0


def run_lifecycle(
    project: Path,
    config: dict[str, Any],
    command: str,
    *,
    skip_review_gate: bool = False,
    before_checks: Any | None = None,
    pr_body: str | None = None,
    fixes: Sequence[str] = (),
    next_command: str | None = None,
) -> int:
    try:
        pr = find_pr(project)
        existing_pr = pr is not None
        if command in {"complete", "tweak"}:
            push_stop = auto_push_current_branch_if_needed(project, config, next_command)
            if push_stop is not None:
                return stop_from_state(project, command, push_stop)
        if pr is None:
            pr = create_pr(project, config, pr_body)
        pr = sync_pr(project, pr)
        if pr_body is not None and existing_pr:
            reconcile_existing_pr_body(project, pr, pr_body, fixes)
        if before_checks is not None:
            before_checks(pr)
    except PrFlowError as exc:
        return stop(project, command, error_status(exc.reason), exc.reason, add_default_next_command(exc.details, next_command))

    try:
        check_stop = wait_for_checks(project, pr, wait_config_from_config(config))
    except PrFlowError as exc:
        return stop(project, command, error_status(exc.reason), exc.reason, add_default_next_command(exc.details, next_command))
    if check_stop is not None:
        return stop_from_state(project, command, check_stop)

    if not skip_review_gate:
        review_stop = check_review_gate(project, config, pr)
        if review_stop is not None:
            return stop_from_state(project, command, review_stop)

    current_branch = require_git_success(project, "git_current_branch_failed", "branch", "--show-current").stdout.strip()
    head_ref = pr.get("headRefName")
    if current_branch != head_ref:
        details = {
            "reason": "current_branch_mismatch",
            "currentBranch": current_branch,
            "headRefName": head_ref,
            "pr": pr.get("number"),
        }
        return stop(project, command, "EXCEPTION_REQUIRED", "current_branch_mismatch", details)

    try:
        merge_pr(project, config, pr)
    except PrFlowError as exc:
        if exc.reason == "ruleset_merge_blocking":
            try:
                recovery_stop = retry_merge_after_ruleset_block(project, config, pr, exc.details)
            except PrFlowError as recovery_exc:
                return stop(
                    project,
                    command,
                    error_status(recovery_exc.reason),
                    recovery_exc.reason,
                    add_default_next_command(recovery_exc.details, next_command),
                )
            if recovery_stop is not None:
                return stop_from_state(project, command, recovery_stop)
        else:
            return stop(project, command, error_status(exc.reason), exc.reason, exc.details)

    print("status: merge_complete")
    print(f"pr: {pr_number_for_command(pr)}")
    cleanup_args = argparse.Namespace(command="cleanup", project=project, pr=str(pr.get("number")))
    return run_cleanup(cleanup_args)


def add_cleanup_recovery(details: dict[str, Any], pr_number: str | None = None) -> dict[str, Any]:
    recovery_pr = str(details.get("pr") or pr_number or "<number>")
    completed_steps = details.get("completedCleanupSteps")
    if isinstance(completed_steps, list) and "remote_head_deleted" in completed_steps:
        details.setdefault(
            "recovery",
            "Remote head branch was already deleted. Sync the base branch, then delete the local head branch manually; "
            f"do not rerun full `pr-flow-cleanup --project . --pr {recovery_pr}` until local state is reconciled.",
        )
        return details
    details.setdefault(
        "recovery",
        "Resolve the reported condition, then run "
        f"`pr-flow-cleanup --project . --pr {recovery_pr}`. "
        "If the remote head branch was already deleted, sync the base branch and delete the local head branch manually.",
    )
    return details


def run_complete(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    try:
        config = load_config(project)
        summary, scope, fixes = require_pr_body_args(project, args.command, args)
        body = render_pr_body(project, config, summary, scope, fixes)
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)
    except PrFlowError as exc:
        return stop(project, args.command, error_status(exc.reason), exc.reason, add_recovery_action(exc.details))
    return run_lifecycle(
        project,
        config,
        args.command,
        pr_body=body,
        fixes=fixes,
        next_command=pr_body_next_command(args.command, project, args),
    )


def run_tweak(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    try:
        config = load_config(project)
        summary, scope, fixes = require_pr_body_args(project, args.command, args)
        body = render_pr_body(project, config, summary, scope, fixes)
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)
    except PrFlowError as exc:
        return stop(project, args.command, error_status(exc.reason), exc.reason, add_recovery_action(exc.details))

    return run_lifecycle(
        project,
        config,
        args.command,
        skip_review_gate=True,
        pr_body=body,
        fixes=fixes,
        next_command=pr_body_next_command(args.command, project, args),
    )


def run_hotfix_verify_command(project: Path, command: str) -> subprocess.CompletedProcess[str]:
    try:
        command_args = split_hotfix_verify_command(command)
    except ValueError as exc:
        raise PrFlowError(
            "hotfix_verify_command_parse_failed",
            {
                "reason": "hotfix_verify_command_parse_failed",
                "command": command,
                "error": str(exc),
            },
        ) from exc
    if not command_args:
        raise PrFlowError("hotfix_verify_command_missing", {"reason": "hotfix_verify_command_missing"})

    try:
        result = subprocess.run(
            command_args,
            cwd=project,
            check=False,
            text=True,
            capture_output=True,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise PrFlowError(
            "hotfix_verify_failed",
            {
                "reason": "hotfix_verify_failed",
                "command": command,
                "returncode": 127,
                "stdout": "",
                "stderr": str(exc),
            },
        ) from exc

    if result.returncode != 0:
        details = command_failure_details("hotfix_verify_failed", result)
        details["command"] = command
        raise PrFlowError("hotfix_verify_failed", details)
    return result


def git_config_value(project: Path, key: str) -> str:
    result = git(project, "config", "--get", key)
    return result.stdout.strip() if result.returncode == 0 else ""


def hotfix_actor(project: Path) -> dict[str, str]:
    return {
        "name": git_config_value(project, "user.name"),
        "email": git_config_value(project, "user.email"),
    }


def write_hotfix_audit(
    project: Path,
    *,
    target: str,
    remote: str,
    before_commit: str,
    after_commit: str,
    remote_after: str,
    verification: subprocess.CompletedProcess[str],
    verify_command: str,
) -> Path:
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    filename_timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    runs_dir = project / ".pr-flow" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    audit_path = runs_dir / f"hotfix-{filename_timestamp}-{after_commit[:12]}.json"
    payload = {
        "command": "hotfix",
        "targetBranch": target,
        "remote": remote,
        "beforeCommit": before_commit,
        "afterCommit": after_commit,
        "readback": {
            "remote": remote,
            "targetBranch": target,
            "remoteAfter": remote_after,
            "matchedHead": remote_after == after_commit,
        },
        "actor": hotfix_actor(project),
        "timestamp": timestamp,
        "verification": {
            "command": verify_command,
            "returncode": verification.returncode,
            "stdout": verification.stdout.strip(),
            "stderr": verification.stderr.strip(),
            "status": "passed",
        },
    }
    audit_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit_path


def confirm_hotfix_remote_readback(project: Path, remote: str, target: str, expected_head: str) -> str:
    require_git_success(project, "git_fetch_target_readback_failed", "fetch", remote, target)
    remote_ref = f"{remote}/{target}"
    remote_after = require_git_success(project, "git_remote_target_readback_failed", "rev-parse", remote_ref).stdout.strip()
    if remote_after != expected_head:
        raise PrFlowError(
            "hotfix_readback_mismatch",
            {
                "reason": "hotfix_readback_mismatch",
                "targetBranch": target,
                "remote": remote,
                "currentHead": expected_head,
                "remoteAfter": remote_after,
            },
        )
    return remote_after


def run_hotfix(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    target = args.target
    try:
        config = load_config(project)
        branch_config = branch_config_for_target(config, target)
        remote = hotfix_remote(branch_config)
        details: dict[str, Any] = {
            "targetBranch": target,
            "remote": remote,
        }

        if not target_explicitly_allows_hotfix_push(config, target):
            details["reason"] = "hotfix_push_not_allowed"
            return stop(project, args.command, "EXCEPTION_REQUIRED", "hotfix_push_not_allowed", details)

        require_git_success(project, "git_fetch_target_failed", "fetch", remote, target)
        remote_ref = f"{remote}/{target}"
        remote_head = require_git_success(project, "git_remote_target_head_failed", "rev-parse", remote_ref).stdout.strip()
        current_head = head_oid(project)
        merge_base = require_git_success(project, "git_merge_base_failed", "merge-base", "HEAD", remote_ref).stdout.strip()
        details.update(
            {
                "remoteHead": remote_head,
                "currentHead": current_head,
                "mergeBase": merge_base,
            }
        )
        if merge_base != remote_head:
            details["reason"] = "hotfix_base_mismatch"
            return stop(project, args.command, "EXCEPTION_REQUIRED", "hotfix_base_mismatch", details)

        status_result = require_git_success(project, "git_status_failed", "status", "--short")
        dirty = status_result.stdout.strip()
        if dirty:
            details["reason"] = "dirty_worktree"
            details["dirty"] = dirty
            return stop(project, args.command, "EXCEPTION_REQUIRED", "dirty_worktree", details)

        require_authorization_phrase_configured(config)
        verify_command = hotfix_verify_command(branch_config)
        verification = run_hotfix_verify_command(project, verify_command)
        verify_authorization_phrase(config, args.authorization_phrase)

        require_git_success(project, "git_hotfix_push_failed", "push", remote, f"HEAD:refs/heads/{target}")
        try:
            remote_after = confirm_hotfix_remote_readback(project, remote, target, current_head)
        except PrFlowError as exc:
            if exc.reason != "hotfix_readback_mismatch":
                raise
            remote_after = str(exc.details.get("remoteAfter") or "")
            audit_path = write_hotfix_audit(
                project,
                target=target,
                remote=remote,
                before_commit=remote_head,
                after_commit=current_head,
                remote_after=remote_after,
                verification=verification,
                verify_command=verify_command,
            )
            exc.details["auditPath"] = str(audit_path.relative_to(project))
            raise
        audit_path = write_hotfix_audit(
            project,
            target=target,
            remote=remote,
            before_commit=remote_head,
            after_commit=current_head,
            remote_after=remote_after,
            verification=verification,
            verify_command=verify_command,
        )

        details.update(
            {
                "reason": "hotfix_complete",
                "auditPath": str(audit_path.relative_to(project)),
                "remoteAfter": remote_after,
            }
        )
        write_status(project, args.command, "hotfix_complete", details)
        print("status: hotfix_complete")
        print(f"target: {target}")
        print(f"after: {current_head}")
        return 0
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)
    except PrFlowError as exc:
        return stop(project, args.command, "EXCEPTION_REQUIRED", exc.reason, exc.details)


def run_cleanup(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    completed_cleanup_steps: list[str] = []
    try:
        config = load_config(project)
        pr = view_pr_for_cleanup(project, str(args.pr))
        head_ref, base_ref = require_cleanup_pr_fields(pr)

        details = {
            "reason": "cleanup",
            "pr": pr.get("number"),
            "state": pr.get("state"),
            "headRefName": head_ref,
            "baseRefName": base_ref,
            "headRepositoryOwner": pr.get("headRepositoryOwner"),
        }
        if pr.get("state") != "MERGED":
            details["reason"] = "pr_not_merged"
            return stop(project, args.command, "EXCEPTION_REQUIRED", "pr_not_merged", add_cleanup_recovery(details, str(args.pr)))

        status_result = require_git_success(project, "git_status_failed", "status", "--short")
        dirty = status_result.stdout.strip()
        if dirty:
            details["reason"] = "dirty_worktree"
            details["dirty"] = dirty
            return stop(project, args.command, "EXCEPTION_REQUIRED", "dirty_worktree", add_cleanup_recovery(details, str(args.pr)))

        branch_result = require_git_success(project, "git_current_branch_failed", "branch", "--show-current")
        current_branch = branch_result.stdout.strip()
        if current_branch != head_ref:
            details["reason"] = "current_branch_mismatch"
            details["currentBranch"] = current_branch
            return stop(project, args.command, "EXCEPTION_REQUIRED", "current_branch_mismatch", add_cleanup_recovery(details, str(args.pr)))
        if head_ref == base_ref:
            details["reason"] = "protected_base_branch"
            details["currentBranch"] = current_branch
            return stop(project, args.command, "EXCEPTION_REQUIRED", "protected_base_branch", add_cleanup_recovery(details, str(args.pr)))

        remote = remote_for_base_branch(config, base_ref)
        details["remote"] = remote
        require_git_success(project, "git_push_delete_failed", "push", remote, "--delete", head_ref)
        completed_cleanup_steps.append("remote_head_deleted")
        confirm_remote_branch_deleted(project, remote, head_ref)
        completed_cleanup_steps.append("remote_delete_confirmed")
        require_git_success(project, "git_checkout_base_failed", "checkout", base_ref)
        completed_cleanup_steps.append("base_checked_out")
        require_git_success(project, "git_pull_ff_only_failed", "pull", "--ff-only", remote, base_ref)
        completed_cleanup_steps.append("base_synced")
        require_git_success(project, "git_branch_delete_failed", "branch", "-d", head_ref)
        completed_cleanup_steps.append("local_head_deleted")

        final_branch = require_git_success(project, "git_current_branch_failed", "branch", "--show-current").stdout.strip()
        details["reason"] = "cleanup_complete"
        details["currentBranch"] = final_branch
        write_status(project, args.command, "cleanup_complete", details)
        print("status: cleanup_complete")
        print(f"branch: {final_branch}")
        print(f"deleted: {head_ref}")
        return 0
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)
    except PrFlowError as exc:
        if completed_cleanup_steps:
            exc.details["completedCleanupSteps"] = completed_cleanup_steps
        return stop(project, args.command, error_status(exc.reason), exc.reason, add_cleanup_recovery(exc.details, str(args.pr)))


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
        if command in {"diagnose", "init", "complete", "tweak"}:
            subparser.add_argument("--project", type=Path, required=True)
        if command == "validate":
            subparser.add_argument("--project", type=Path, default=Path("."))
            subparser.add_argument("--config", type=Path, required=True)
        if command == "cleanup":
            subparser.add_argument("--project", type=Path, required=True)
            subparser.add_argument("--pr", required=True)
        if command == "hotfix":
            subparser.add_argument("--project", type=Path, required=True)
            subparser.add_argument("--target", required=True)
            subparser.add_argument("--authorization-phrase", required=True)
        if command in {"complete", "tweak"}:
            subparser.add_argument("--summary")
            subparser.add_argument("--scope")
            subparser.add_argument(
                "--fixes",
                action="append",
                default=[],
                help="Issue number to close; repeat for multiple issues, for example --fixes 41 --fixes 43.",
            )
        if command == "tweak":
            subparser.add_argument("--reason")
        if command == "init":
            subparser.add_argument("--base-branch", default=None)
            subparser.add_argument("--config", type=Path)
        subparser.set_defaults(command=command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return run_init(args)
    if args.command == "validate":
        return run_validate(args)
    if args.command == "diagnose":
        return run_diagnose(args)
    if args.command == "complete":
        return run_complete(args)
    if args.command == "cleanup":
        return run_cleanup(args)
    if args.command == "hotfix":
        return run_hotfix(args)
    if args.command == "tweak" and (args.reason is None or not args.reason.strip()):
        print_stop("tweak_requires_reason", "tweak_requires_reason: --reason")
        return 2
    if args.command == "tweak":
        return run_tweak(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
