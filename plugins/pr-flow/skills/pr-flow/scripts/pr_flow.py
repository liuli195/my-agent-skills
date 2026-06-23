from __future__ import annotations

import argparse
import ctypes
import hashlib
import hmac
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml


COMMANDS = ("diagnose", "init", "complete", "cleanup", "hotfix", "tweak")
PR_VIEW_FIELDS = "number,state,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup,headRefOid"
BLOCKING_REVIEW_DECISIONS = {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}
PR_TEMPLATE = """## Summary

## Scope

## Verification

## Risk

## Rollback
"""
PR_FLOW_GITIGNORE = "/runs/\n/last-status.json\n"
TWEAK_BODY_TEMPLATE = """## Tweak Path

Review gate skipped for non-bug small change.

Reason: {reason}
"""


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
            "reviewGate": {"mode": "github", "evidencePath": ".pr-flow/review-pass.json"},
            "hotfix": {
                "verifyCommand": "python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full"
            },
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


def command_failure_details(reason: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "reason": reason,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


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
        return shlex.split(command)

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


def find_pr(project: Path) -> dict[str, Any] | None:
    result = gh(project, "pr", "view", "--json", PR_VIEW_FIELDS)
    if result.returncode != 0:
        if gh_pr_not_found(result):
            return None
        details = command_failure_details("gh_pr_view_failed", result)
        raise PrFlowError("gh_pr_view_failed", details)
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


def create_pr(project: Path, config: dict[str, Any]) -> dict[str, Any]:
    result = gh(project, "pr", "create", "--base", base_branch_from_config(config), "--fill")
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
    body_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as body_file:
            body_file.write(body)
            body_path = Path(body_file.name)
        result = gh(project, "pr", "edit", pr_number, "--body-file", str(body_path))
    finally:
        if body_path is not None:
            body_path.unlink(missing_ok=True)
    if result.returncode != 0:
        details = command_failure_details("gh_pr_edit_failed", result)
        details["pr"] = pr_number
        raise PrFlowError("gh_pr_edit_failed", details)


def view_pr_for_cleanup(project: Path, pr_number: str) -> dict[str, Any]:
    fields = "number,state,headRefName,baseRefName,headRepositoryOwner"
    result = gh(project, "pr", "view", pr_number, "--json", fields)
    if result.returncode != 0:
        details = command_failure_details("gh_pr_view_failed", result)
        details["pr"] = pr_number
        raise PrFlowError("gh_pr_view_failed", details)
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


def merge_pr(project: Path, config: dict[str, Any], pr: dict[str, Any]) -> dict[str, Any] | None:
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

    result = gh(project, "pr", "merge", str(pr_number), strategy_flag, "--match-head-commit", current_head_oid)
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
            return stop_state("REPLY_OR_FIX_REQUIRED", "checks_or_review_blocking", details)
        if not has_pending_check(checks):
            return None
        if timeout_seconds <= 0:
            return stop_state("DISPATCH_REQUIRED", "checks_pending", details)

        remaining = timeout_seconds - (time.monotonic() - started_at)
        if remaining <= 0:
            return stop_state("DISPATCH_REQUIRED", "checks_pending", details)
        time.sleep(min(max(poll_seconds, 1), remaining))
        current = sync_pr(project, current)


def review_gate_mode(config: dict[str, Any]) -> str:
    mode = review_gate_config(config).get("mode", "github")
    return mode if isinstance(mode, str) and mode else "github"


def github_review_is_blocking(pr: dict[str, Any]) -> bool:
    return pr.get("reviewDecision") in BLOCKING_REVIEW_DECISIONS


def load_local_review_evidence(project: Path, config: dict[str, Any]) -> dict[str, Any]:
    evidence_path_value = review_gate_config(config).get("evidencePath", ".pr-flow/review-pass.json")
    evidence_path = Path(evidence_path_value) if isinstance(evidence_path_value, str) else Path(".pr-flow/review-pass.json")
    if not evidence_path.is_absolute():
        evidence_path = project / evidence_path
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PrFlowError("local_review_evidence_missing", {"reason": "local_review_evidence_missing", "path": str(evidence_path)}) from exc
    except json.JSONDecodeError as exc:
        raise PrFlowError(
            "local_review_evidence_parse_failed",
            {"reason": "local_review_evidence_parse_failed", "path": str(evidence_path), "error": str(exc)},
        ) from exc
    if not isinstance(evidence, dict):
        raise PrFlowError("local_review_evidence_parse_failed", {"reason": "local_review_evidence_parse_failed", "path": str(evidence_path)})
    return evidence


def current_diff_fingerprint(project: Path, pr: dict[str, Any]) -> str:
    base_ref = pr.get("baseRefName")
    head_ref = pr.get("headRefName")
    details = {
        "reason": "local_review_diff_failed",
        "baseRefName": base_ref,
        "headRefName": head_ref,
    }
    if not isinstance(base_ref, str) or not base_ref or not isinstance(head_ref, str) or not head_ref:
        raise PrFlowError("local_review_diff_failed", details)

    command = ["git", "diff", "--binary", f"{base_ref}...{head_ref}"]
    try:
        result = subprocess.run(command, cwd=project, check=False, capture_output=True)
    except FileNotFoundError as exc:
        details["stderr"] = str(exc)
        raise PrFlowError("local_review_diff_failed", details) from exc
    if result.returncode != 0:
        details.update(
            {
                "returncode": result.returncode,
                "stdout": result.stdout.decode(errors="replace").strip(),
                "stderr": result.stderr.decode(errors="replace").strip(),
            }
        )
        raise PrFlowError("local_review_diff_failed", details)
    return f"sha256:{hashlib.sha256(result.stdout).hexdigest()}"


def local_review_evidence_passes(evidence: dict[str, Any], pr: dict[str, Any], diff_fingerprint: str) -> bool:
    return (
        evidence.get("status") == "pass"
        and evidence.get("base_ref") == pr.get("baseRefName")
        and evidence.get("head_ref") == pr.get("headRefName")
        and evidence.get("diff_fingerprint") == diff_fingerprint
        and evidence.get("blocking_findings") == 0
    )


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
    if mode not in {"github", "local", "dual"}:
        details["reason"] = "unknown_review_gate_mode"
        return stop_state("EXCEPTION_REQUIRED", "unknown_review_gate_mode", details)

    if mode in {"github", "dual"} and github_review_is_blocking(pr):
        return stop_state("REPLY_OR_FIX_REQUIRED", "review_gate_blocking", details)

    if mode in {"local", "dual"}:
        try:
            evidence = load_local_review_evidence(project, config)
            diff_fingerprint = current_diff_fingerprint(project, pr)
        except PrFlowError as exc:
            details.update(exc.details)
            details["reason"] = exc.reason
            return stop_state("REPLY_OR_FIX_REQUIRED", exc.reason, details)
        if not local_review_evidence_passes(evidence, pr, diff_fingerprint):
            details["reason"] = "local_review_evidence_failed"
            return stop_state("REPLY_OR_FIX_REQUIRED", "local_review_evidence_failed", details)

    return None


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
    if upstream_result.returncode != 0 and branch != base_branch:
        details = command_failure_details("missing_upstream", upstream_result)
        details["branch"] = branch
        details["baseBranch"] = base_branch
        return stop(project, args.command, "PUSH_REQUIRED", "push current branch before continuing", details)

    status_result = git(project, "status", "--short")
    if status_result.returncode != 0:
        details = command_failure_details("git_status_failed", status_result)
        details["branch"] = branch
        details["baseBranch"] = base_branch
        details["upstream"] = upstream
        return stop(project, args.command, "EXCEPTION_REQUIRED", details["reason"], details)
    dirty = status_result.stdout.strip()

    pr_result = gh(
        project,
        "pr",
        "view",
        "--json",
        "number,state,isDraft,mergeStateStatus,reviewDecision,headRefName,baseRefName,statusCheckRollup",
    )
    gh_details: dict[str, Any] = {
        "branch": branch,
        "baseBranch": base_branch,
        "upstream": upstream,
        "dirty": dirty,
    }
    if pr_result.returncode != 0:
        gh_details.update(command_failure_details("gh_pr_view_failed", pr_result))
        return stop(project, args.command, "EXCEPTION_REQUIRED", "gh_pr_view_failed", gh_details)

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
    checks = pr_checks(pr)
    if has_pending_check(checks):
        gh_details["reason"] = "checks_pending"
        return stop(project, args.command, "DISPATCH_REQUIRED", "checks_pending", gh_details)
    if has_failing_check(checks) or pr.get("reviewDecision") in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
        gh_details["reason"] = "checks_or_review_blocking"
        return stop(project, args.command, "REPLY_OR_FIX_REQUIRED", "checks_or_review_blocking", gh_details)
    if pr.get("isDraft") is True:
        gh_details["reason"] = "pr_is_draft"
        gh_details["nextCommand"] = "gh pr ready"
        return stop(project, args.command, "DISPATCH_REQUIRED", "pr_is_draft", gh_details)

    gh_details["reason"] = "ready_to_complete"
    gh_details["nextCommand"] = "complete"
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
) -> int:
    try:
        pr = find_pr(project)
        if pr is None:
            pr = create_pr(project, config)
        pr = sync_pr(project, pr)
        if before_checks is not None:
            before_checks(pr)
    except PrFlowError as exc:
        return stop(project, command, "EXCEPTION_REQUIRED", exc.reason, exc.details)

    try:
        check_stop = wait_for_checks(project, pr, wait_config_from_config(config))
    except PrFlowError as exc:
        return stop(project, command, "EXCEPTION_REQUIRED", exc.reason, exc.details)
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
        return stop(project, command, "EXCEPTION_REQUIRED", exc.reason, exc.details)

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
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)
    return run_lifecycle(project, config, args.command)


def run_tweak(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    try:
        config = load_config(project)
    except FileNotFoundError:
        details = {"reason": "missing_config", "path": ".pr-flow/config.yaml"}
        return stop(project, args.command, "EXCEPTION_REQUIRED", "missing_config", details)

    body = TWEAK_BODY_TEMPLATE.format(reason=args.reason)
    return run_lifecycle(
        project,
        config,
        args.command,
        skip_review_gate=True,
        before_checks=lambda pr: update_pr_body(project, pr, body),
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
        return stop(project, args.command, "EXCEPTION_REQUIRED", exc.reason, add_cleanup_recovery(exc.details, str(args.pr)))


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
        if command == "cleanup":
            subparser.add_argument("--project", type=Path, required=True)
            subparser.add_argument("--pr", required=True)
        if command == "hotfix":
            subparser.add_argument("--project", type=Path, required=True)
            subparser.add_argument("--target", required=True)
            subparser.add_argument("--authorization-phrase", required=True)
        if command == "tweak":
            subparser.add_argument("--reason")
        if command == "init":
            subparser.add_argument("--base-branch", default="main")
        subparser.set_defaults(command=command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return run_init(args)
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
