from __future__ import annotations

import ast
import functools
import textwrap
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = REPO_ROOT / "tests"


@dataclass(frozen=True)
class RuntimeHit:
    identity: str
    category: str
    line: int
    detail: str


CLI_HELPER_NAMES = {
    "run",
    "run_cli",
    "run_hook",
    "run_hook_stdin",
    "run_installer",
    "run_build_and_verify",
    "run_build_and_verify_subprocess",
    "run_check",
}

GIT_HELPER_NAMES = {"git", "run_git", "git_project", "bare_remote_template"}

CLI_HELPER_DEFINITION_MARKERS = tuple(
    f"def {helper_name}(" for helper_name in CLI_HELPER_NAMES
)

RUNTIME_SCAN_MARKERS = (
    "subprocess",
    "git(",
    "run_git(",
    "bare_remote_template(",
    ".glob(",
    ".rglob(",
    *CLI_HELPER_DEFINITION_MARKERS,
)


@dataclass(frozen=True)
class FunctionInfo:
    name: str
    line: int
    args: tuple[str, ...]
    calls: tuple[tuple[str, int, str], ...]
    fixtures: tuple[str, ...]


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def literal_text(node: ast.AST, source: str) -> str:
    return ast.get_source_segment(source, node) or ""


def call_needs_literal_text(name: str) -> bool:
    short_name = name.rsplit(".", 1)[-1]
    return name in {
        "subprocess.run",
        "subprocess.check_call",
        "subprocess.check_output",
        "Path.glob",
        "Path.rglob",
    } or short_name in {"glob", "rglob"}


def function_identity(path: Path, name: str) -> str:
    return f"{path.as_posix()}::{name}"


def function_infos(source: str) -> dict[str, FunctionInfo]:
    normalized = textwrap.dedent(source)
    tree = ast.parse(normalized)
    infos: dict[str, FunctionInfo] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        calls: list[tuple[str, int, str]] = []
        fixtures: list[str] = []
        for decorator in node.decorator_list:
            name = call_name(decorator)
            if name == "pytest.fixture" or name.endswith(".fixture"):
                fixtures.append(node.name)
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = call_name(child.func)
                call_text = literal_text(child, normalized) if call_needs_literal_text(name) else ""
                calls.append((name, child.lineno, call_text))
        infos[node.name] = FunctionInfo(
            node.name,
            node.lineno,
            tuple(arg.arg for arg in node.args.args),
            tuple(calls),
            tuple(fixtures),
        )
    return infos


def classify_call(name: str, call_text: str) -> tuple[str, str] | None:
    if name in {"subprocess.run", "subprocess.check_call", "subprocess.check_output"}:
        if ('"git"' in call_text or "'git'" in call_text) and (
            '"init"' in call_text or "'init'" in call_text
        ):
            return "temporary-git", f"{name} git init"
        return "subprocess", name
    short_name = name.rsplit(".", 1)[-1]
    if short_name in GIT_HELPER_NAMES:
        return "temporary-git", short_name
    if name in {"Path.glob", "Path.rglob"} or short_name in {"glob", "rglob"}:
        if ".build-and-verify/cache" in call_text:
            return "broad-cache-scan", "Path.glob over .build-and-verify/cache"
    return None


def risky_function_names(infos: dict[str, FunctionInfo]) -> frozenset[str]:
    risky: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, info in infos.items():
            if name in risky:
                continue
            for call, _line, call_text in info.calls:
                short_name = call.rsplit(".", 1)[-1]
                if classify_call(call, call_text) is not None or short_name in risky:
                    risky.add(name)
                    changed = True
                    break
    return frozenset(risky)


def collect_function_hits(
    path: Path,
    source: str,
    infos: dict[str, FunctionInfo],
    risky_names: frozenset[str],
    name: str,
    *,
    line_override: int | None = None,
    prefix: str = "",
    seen: frozenset[str] = frozenset(),
) -> list[RuntimeHit]:
    if name in seen or name not in infos:
        return []
    info = infos[name]
    hits: list[RuntimeHit] = []
    for call, line, call_text in info.calls:
        short_name = call.rsplit(".", 1)[-1]
        if short_name in infos and short_name in risky_names:
            nested_hits = collect_function_hits(
                path,
                source,
                infos,
                risky_names,
                short_name,
                line_override=line_override or info.line,
                prefix=f"{prefix}{short_name} -> ",
                seen=seen | {name},
            )
            if nested_hits:
                hits.extend(
                    RuntimeHit(
                        function_identity(path, name),
                        "cli-entrypoint" if short_name in CLI_HELPER_NAMES else hit.category,
                        hit.line,
                        hit.detail,
                    )
                    for hit in nested_hits
                )
                continue
        classified = classify_call(call, call_text)
        if classified is not None:
            category, detail = classified
            hits.append(
                RuntimeHit(
                    function_identity(path, name),
                    category,
                    line_override or line,
                    f"{prefix}{detail}",
                )
            )
    return hits


def scan_source(path: Path, source: str, shared_fixtures: dict[str, FunctionInfo]) -> list[RuntimeHit]:
    infos = function_infos(source)
    risky_names = risky_function_names(infos)
    fixtures = {
        fixture_name: info
        for info in infos.values()
        for fixture_name in info.fixtures
    }
    fixtures.update(shared_fixtures)
    hits: list[RuntimeHit] = []
    for name, info in infos.items():
        if not name.startswith("test_"):
            continue
        hits.extend(collect_function_hits(path, source, infos, risky_names, name))
        for arg in info.args:
            if arg in fixtures:
                fixture_infos = {arg: fixtures[arg], **infos}
                fixture_hits = collect_function_hits(
                    path,
                    source,
                    fixture_infos,
                    risky_function_names(fixture_infos),
                    arg,
                    prefix=f"fixture {arg} -> ",
                )
                hits.extend(
                    RuntimeHit(
                        function_identity(path, name),
                        hit.category,
                        info.line,
                        hit.detail,
                    )
                    for hit in fixture_hits
                )
    return sorted(set(hits), key=lambda hit: (hit.line, hit.identity, hit.category, hit.detail))


def may_contain_runtime_hit(source: str, shared_fixtures: dict[str, FunctionInfo]) -> bool:
    if any(marker in source for marker in RUNTIME_SCAN_MARKERS):
        return True
    return any(fixture_name in source for fixture_name in shared_fixtures)


def test_scan_source_flags_direct_subprocess() -> None:
    source = """
import subprocess

def test_real_process():
    subprocess.run(["python", "--version"], check=False)
"""

    hits = scan_source(Path("tests/test_sample.py"), source, {})

    assert hits == [
        RuntimeHit(
            "tests/test_sample.py::test_real_process",
            "subprocess",
            5,
            "subprocess.run",
        )
    ]


def test_scan_source_follows_helper_and_fixture_runtime_paths() -> None:
    source = """
import pytest
import subprocess

def run_cli(*args):
    return subprocess.run(["python", "tool.py", *args], check=False)

@pytest.fixture
def git_project(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=False)
    return tmp_path

def test_helper_path():
    run_cli("verify")

def test_fixture_path(git_project):
    assert git_project.exists()
"""

    hits = scan_source(Path("tests/test_sample.py"), source, {})

    assert hits == [
        RuntimeHit(
            "tests/test_sample.py::test_helper_path",
            "cli-entrypoint",
            13,
            "run_cli -> subprocess.run",
        ),
        RuntimeHit(
            "tests/test_sample.py::test_fixture_path",
            "temporary-git",
            16,
            "fixture git_project -> subprocess.run git init",
        ),
    ]


def test_scan_source_allows_run_check_test_helper() -> None:
    source = (
        "def run_check(project, *args):\n"
        "    return None\n"
        "\n"
        "def test_branch_path(project):\n"
        "    run_check(project, \"verify\")\n"
    )

    hits = scan_source(Path("tests/test_sample.py"), source, {})

    assert hits == []


def test_scan_source_allows_run_check_with_fake_runner() -> None:
    source = (
        "def run_check(project, *args, runner=None):\n"
        "    return None\n"
        "\n"
        "def test_branch_path(project):\n"
        "    fake = object()\n"
        "    run_check(project, \"verify\", runner=fake)\n"
    )

    hits = scan_source(Path("tests/test_sample.py"), source, {})

    assert hits == []


def test_scan_source_flags_generic_run_helper_subprocess_path() -> None:
    source = (
        "import subprocess\n"
        "\n"
        "def run(*args):\n"
        "    return subprocess.run([\"tool\", *args], check=False)\n"
        "\n"
        "def test_package_contract():\n"
        "    run(\"help\")\n"
    )

    hits = scan_source(Path("tests/test_sample.py"), source, {})

    assert hits == [
        RuntimeHit(
            "tests/test_sample.py::test_package_contract",
            "cli-entrypoint",
            6,
            "run -> subprocess.run",
        )
    ]


def test_scan_source_follows_intermediate_helper_to_runtime_path() -> None:
    source = (
        "import subprocess\n"
        "\n"
        "def run(*args):\n"
        "    return subprocess.run([\"tool\", *args], check=False)\n"
        "\n"
        "def setup_project():\n"
        "    run(\"init\")\n"
        "\n"
        "def test_indirect_helper():\n"
        "    setup_project()\n"
    )

    hits = scan_source(Path("tests/test_sample.py"), source, {})

    assert hits == [
        RuntimeHit(
            "tests/test_sample.py::test_indirect_helper",
            "cli-entrypoint",
            9,
            "setup_project -> run -> subprocess.run",
        )
    ]


def test_scan_source_flags_broad_runtime_cache_scan() -> None:
    source = '''
from pathlib import Path

def test_cache_scan():
    cache_files = list(Path(".build-and-verify/cache").glob("*.json"))
    assert cache_files == []
'''

    hits = scan_source(Path("tests/test_sample.py"), source, {})

    assert hits == [
        RuntimeHit(
            "tests/test_sample.py::test_cache_scan",
            "broad-cache-scan",
            5,
            "Path.glob over .build-and-verify/cache",
        )
    ]


E2E_ALLOWLIST: dict[str, str] = {
    "tests/test_pr_flow_cli.py::test_competing_mutation_reports_lock_without_rewriting_status": (
        "covers PR Flow cross-process mutation lock behavior in a real git repository"
    ),
    "tests/test_pr_flow_cli.py::test_diagnose_reports_active_lock_without_writing_status": (
        "covers PR Flow read-only diagnosis while a real operation lock is held"
    ),
    "tests/test_pr_flow_cli.py::test_linked_worktrees_use_independent_process_locks_and_status": (
        "covers linked-worktree isolation across real PR Flow processes"
    ),
    "tests/test_pr_flow_cli.py::test_write_status_keeps_compatibility_file_and_branch_run": (
        "covers per-worktree PR Flow status paths in a real git repository"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_authorized_install_is_repeatable_and_updates_marketplaces": (
        "covers packaged agent-guard installer repeatable write entrypoint"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_dry_run_lists_codex_and_claude_targets_without_writing": (
        "covers packaged agent-guard installer dry-run entrypoint"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_install_rejects_invalid_marketplace_plugins_without_overwriting": (
        "covers packaged agent-guard installer invalid marketplace protection"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_install_requires_explicit_target_and_authorization": (
        "covers packaged agent-guard installer authorization boundary"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_installer_rejects_profile_argument": (
        "covers packaged agent-guard installer argument contract"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_verify_checks_package_and_marketplace_entries": (
        "covers packaged agent-guard verifier entrypoint"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_verify_default_scope_does_not_require_repo_marketplace": (
        "covers packaged agent-guard verifier default scope"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_verify_rejects_legacy_hook_config_shape": (
        "covers packaged agent-guard verifier legacy hook rejection"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_verify_rejects_legacy_marketplace_entry": (
        "covers packaged agent-guard verifier legacy marketplace rejection"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_verify_rejects_marketplace_catalog_identity_mismatch": (
        "covers packaged agent-guard verifier identity mismatch"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_verify_reports_invalid_marketplace_plugin_entry": (
        "covers packaged agent-guard verifier invalid plugin entry"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_verify_reports_invalid_marketplace_plugins_shape": (
        "covers packaged agent-guard verifier invalid plugin shape"
    ),
    "tests/test_agent_guard_plugin_installer.py::test_verify_target_codex_only_requires_codex_manifest": (
        "covers packaged agent-guard verifier target-specific manifest contract"
    ),
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_stale_head_ref_from_git_head": (
        "covers guard runtime against a real git head boundary"
    ),
    "tests/test_agent_guard_runtime_router.py::test_hook_router_blocks_claude_stdin_hook_with_exit_code_2": (
        "covers packaged hook router stdin behavior"
    ),
    "tests/test_agent_guard_runtime_router.py::test_hook_router_blocks_codex_stdin_hook_with_native_deny_output": (
        "covers packaged hook router native deny output"
    ),
    "tests/test_agent_guard_runtime_session_focus.py::test_activate_can_switch_and_close_instances_without_closing_previous_focus": (
        "covers packaged session focus CLI lifecycle"
    ),
    "tests/test_agent_guard_runtime_session_focus.py::test_hook_adapter_converts_codex_and_claude_lifecycle_payloads": (
        "covers packaged lifecycle hook adapter behavior"
    ),
    "tests/test_agent_guard_runtime_session_focus.py::test_session_start_writes_observation_and_missing_observation_blocks_activation": (
        "covers packaged session start CLI observation flow"
    ),
    "tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo": (
        "covers packaged init entrypoint and copied runtime fast-verify entrypoint"
    ),
    "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_initialize_another_project": (
        "covers copied repository runtime init entrypoint"
    ),
    "tests/test_build_and_verify_plugin.py::test_build_and_verify_user_level_skill_path_runs_verify_without_git": (
        "covers user-level skill path fast-verify entrypoint without git"
    ),
    "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_update_itself": (
        "covers copied repository runtime update-runtime entrypoint"
    ),
    "tests/test_cross_agent_review_plugin_package.py::test_cross_agent_review_rejects_removed_cli_options": (
        "covers packaged cross-agent-review CLI compatibility rejection"
    ),
    "tests/test_cross_agent_review_cli.py::test_copied_tracked_file_into_runtime_artifacts_rejects_before_dispatch": (
        "covers cross-agent-review real git tracked-file protection"
    ),
    "tests/test_cross_agent_review_cli.py::test_renamed_tracked_file_into_runtime_artifacts_rejects_before_dispatch": (
        "covers cross-agent-review real git rename protection"
    ),
    "tests/test_cross_agent_review_cli.py::test_reviewer_prompt_does_not_inline_large_diff_or_context": (
        "covers cross-agent-review real git prompt input sizing"
    ),
    "tests/test_cross_agent_review_cli.py::test_reviewer_prompt_references_review_input_file_only": (
        "covers cross-agent-review real git prompt file reference"
    ),
    "tests/test_cross_agent_review_cli.py::test_reviewer_prompt_references_review_input_not_diff_file": (
        "covers cross-agent-review real git diff handling"
    ),
    "tests/test_pr_flow_plugin_package.py::test_pr_flow_bare_commands_report_stable_contract": (
        "covers packaged pr-flow bare command contract"
    ),
    "tests/test_pr_flow_plugin_package.py::test_pr_flow_cli_command_help_includes_command_name": (
        "covers packaged pr-flow command help contract"
    ),
    "tests/test_pr_flow_plugin_package.py::test_pr_flow_package_passes_repo_build_checks": (
        "covers packaged pr-flow repository build check contract"
    ),
    "tests/test_pr_flow_cli.py::test_cleanup_merged_pr_checks_out_base_pulls_and_deletes_branches": (
        "covers pr-flow real git cleanup lifecycle"
    ),
    "tests/test_pr_flow_cli.py::test_complete_creates_pr_when_none_exists_then_merges_and_cleans_up": (
        "covers pr-flow real git complete lifecycle"
    ),
    "tests/test_pr_flow_cli.py::test_complete_full_flow_uses_configured_squash_strategy": (
        "covers pr-flow real git merge strategy"
    ),
    "tests/test_pr_flow_cli.py::test_diagnose_outputs_dispatch_required_without_upstream": (
        "covers pr-flow real git upstream diagnosis"
    ),
    "tests/test_pr_flow_cli.py::test_hotfix_pushes_head_to_target_and_writes_audit_record": (
        "covers pr-flow real git hotfix push lifecycle"
    ),
    "tests/test_release_flow_cli.py::test_ci_publish_authorized_pushes_channel_tag_and_creates_release": (
        "covers release-flow real git ci publish lifecycle"
    ),
    "tests/test_release_flow_cli.py::test_ci_publish_copies_checkout_git_auth_config_to_release_tree": (
        "covers release-flow real git auth config copy"
    ),
    "tests/test_release_flow_cli.py::test_origin_is_github_uses_exact_host": (
        "covers release-flow real git remote host parsing"
    ),
    "tests/test_release_flow_cli.py::test_preflight_accepts_partial_plugin_bump": (
        "covers release-flow real git partial bump preflight"
    ),
    "tests/test_release_flow_cli.py::test_preflight_fetches_missing_channel_branch_for_actions_checkout": (
        "covers release-flow real git channel branch fetch"
    ),
    "tests/test_release_flow_cli.py::test_preflight_merges_repeated_bump_plugins": (
        "covers release-flow real git repeated bump preflight"
    ),
    "tests/test_release_flow_cli.py::test_preflight_rejects_remote_tag_that_already_exists": (
        "covers release-flow real git remote tag rejection"
    ),
    "tests/test_release_flow_cli.py::test_preflight_rejects_stale_build_and_verify_runtime": (
        "covers release-flow real git build-and-verify runtime preflight"
    ),
    "tests/test_release_flow_cli.py::test_release_flow_local_e2e": (
        "covers release-flow real git local end-to-end lifecycle"
    ),
}

E2E_ALLOWLIST.update(
    {
        identity: f"covers agent-guard packaged CLI end-to-end regression: {identity.rsplit('::', 1)[1]}"
        for identity in [
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_plugin_runtime_e2e_from_verify_to_state_completed",
            "tests/test_agent_guard_prd_full_e2e.py::test_agent_guard_plugin_prd_full_end_to_end_regression",
            "tests/test_agent_guard_runtime_brief.py::test_run_guard_event_surfaces_brief_required_instead_of_hidden_read_and_advance",
            "tests/test_agent_guard_runtime_brief.py::test_skill_render_guard_brief_delegates_to_plugin_runtime",
            "tests/test_agent_guard_runtime_brief.py::test_state_completed_refreshes_latest_guard_brief",
            "tests/test_agent_guard_runtime_brief.py::test_state_completed_requires_current_guard_brief_to_be_read",
        ]
    }
)

E2E_ALLOWLIST.update(
    {
        identity: f"covers cross-agent-review packaged CLI contract: {identity.rsplit('::', 1)[1]}"
        for identity in [
            "tests/test_cross_agent_review_cli.py::test_change_path_traversal_rejects_input_location",
            "tests/test_cross_agent_review_cli.py::test_debug_extra_file_rejects_before_dispatch",
            "tests/test_cross_agent_review_cli.py::test_dirty_worktree_outside_runtime_artifacts_rejects_before_dispatch",
            "tests/test_cross_agent_review_cli.py::test_dirty_worktree_rejects_before_dispatch",
            "tests/test_cross_agent_review_cli.py::test_head_mismatch_rejects_before_dispatch",
            "tests/test_cross_agent_review_cli.py::test_input_file_must_be_named_review_input_json_under_prepared_inputs",
            "tests/test_cross_agent_review_cli.py::test_input_file_must_be_under_change_and_head_runtime_dir",
            "tests/test_cross_agent_review_cli.py::test_invalid_base_ref_fails_before_dispatch",
            "tests/test_cross_agent_review_cli.py::test_invalid_mode_fails",
            "tests/test_cross_agent_review_cli.py::test_missing_input_file_fails",
            "tests/test_cross_agent_review_cli.py::test_missing_referenced_plan_file_fails",
            "tests/test_cross_agent_review_cli.py::test_missing_required_args_fail",
            "tests/test_cross_agent_review_cli.py::test_missing_required_review_input_field_fails",
            "tests/test_cross_agent_review_cli.py::test_output_dir_root_extra_file_rejects_before_dispatch",
            "tests/test_cross_agent_review_cli.py::test_prepared_inputs_rejects_extra_directory",
            "tests/test_cross_agent_review_cli.py::test_prepared_inputs_rejects_extra_regular_file",
            "tests/test_cross_agent_review_cli.py::test_run_rejects_fake_reviewer_results_argument",
            "tests/test_cross_agent_review_cli.py::test_run_rejects_legacy_tests_file_argument",
            "tests/test_cross_agent_review_cli.py::test_runtime_artifact_file_path_directory_children_reject_before_dispatch",
            "tests/test_cross_agent_review_cli.py::test_sdk_missing_reports_clear_error",
            "tests/test_cross_agent_review_cli.py::test_sdk_python_directory_reports_clear_error_without_traceback",
            "tests/test_cross_agent_review_cli.py::test_sdk_python_invalid_file_reports_clear_error_without_traceback",
        ]
    }
)

E2E_ALLOWLIST.update(
    {
        identity: f"covers pr-flow packaged CLI contract: {identity.rsplit('::', 1)[1]}"
        for identity in [
            "tests/test_pr_flow_cli.py::test_bare_tweak_requires_project",
            "tests/test_pr_flow_cli.py::test_hotfix_missing_git_is_not_reported_as_missing_config",
            "tests/test_pr_flow_cli.py::test_hotfix_requires_target_for_bare_command",
            "tests/test_pr_flow_cli.py::test_hotfix_requires_target_when_project_and_authorization_are_supplied",
            "tests/test_pr_flow_cli.py::test_init_creates_config_template_and_gitignore",
            "tests/test_pr_flow_cli.py::test_init_does_not_call_gh_api",
            "tests/test_pr_flow_cli.py::test_init_rejects_removed_review_gate_modes",
            "tests/test_pr_flow_cli.py::test_init_validation_errors_block_all_writes",
            "tests/test_pr_flow_cli.py::test_init_without_confirmed_config_does_not_write_defaults",
            "tests/test_pr_flow_cli.py::test_missing_config_reports_exception_required",
            "tests/test_pr_flow_cli.py::test_pr_flow_cli_argparse_errors_cover_core_commands",
            "tests/test_pr_flow_cli.py::test_pr_flow_init_end_to_end_from_skill_to_confirmed_write",
            "tests/test_pr_flow_cli.py::test_tweak_requires_reason",
            "tests/test_pr_flow_cli.py::test_validate_accepts_supported_review_gate_modes",
            "tests/test_pr_flow_cli.py::test_validate_dependency_matrix",
            "tests/test_pr_flow_cli.py::test_validate_reads_only_provided_config_and_reports_suggestions",
            "tests/test_pr_flow_cli.py::test_validate_rejects_invalid_review_gate_mode_values",
            "tests/test_pr_flow_cli.py::test_validate_rejects_removed_review_gate_modes",
            "tests/test_pr_flow_cli.py::test_validate_reports_bad_yaml_as_structured_error",
            "tests/test_pr_flow_cli.py::test_validate_reports_codeql_default_setup_even_with_existing_codeql_workflow",
            "tests/test_pr_flow_cli.py::test_validate_reports_codeql_default_setup_tasks",
            "tests/test_pr_flow_cli.py::test_validate_reports_errors_for_invalid_wait_shape",
            "tests/test_pr_flow_cli.py::test_validate_reports_errors_for_invalid_wait_values",
            "tests/test_pr_flow_cli.py::test_validate_reports_errors_for_missing_core_shape",
            "tests/test_pr_flow_cli.py::test_validate_warns_when_supported_review_gate_keeps_deprecated_evidencePath",
        ]
    }
)

E2E_ALLOWLIST.update(
    {
        identity: f"covers release-flow packaged CLI contract: {identity.rsplit('::', 1)[1]}"
        for identity in [
            "tests/test_release_flow_cli.py::test_ci_publish_rejects_dry_run_argument",
            "tests/test_release_flow_cli.py::test_ci_publish_rejects_vars_file_argument",
            "tests/test_release_flow_cli.py::test_ci_publish_requires_authorization_without_dry_run",
            "tests/test_release_flow_cli.py::test_configure_github_dry_run_does_not_print_marketplace_identity_variables",
            "tests/test_release_flow_cli.py::test_configure_github_dry_run_prints_manual_steps",
            "tests/test_release_flow_cli.py::test_configure_github_requires_authorization",
            "tests/test_release_flow_cli.py::test_current_repo_projection_does_not_register_marketplace_variables",
            "tests/test_release_flow_cli.py::test_current_repo_release_flow_files_are_valid",
            "tests/test_release_flow_cli.py::test_github_plan_does_not_print_marketplace_identity_variables",
            "tests/test_release_flow_cli.py::test_github_plan_outputs_expected_settings",
            "tests/test_release_flow_cli.py::test_preflight_accepts_empty_bump_plugins_when_versions_do_not_drift",
            "tests/test_release_flow_cli.py::test_preflight_checks_projection_without_channel_tree",
            "tests/test_release_flow_cli.py::test_preflight_rejects_bump_not_merged_to_source_ref",
            "tests/test_release_flow_cli.py::test_preflight_rejects_channel_tree_argument",
            "tests/test_release_flow_cli.py::test_preflight_rejects_github_vars_file_argument",
            "tests/test_release_flow_cli.py::test_preflight_rejects_missing_bump_plugins",
            "tests/test_release_flow_cli.py::test_preflight_rejects_unbumped_manifest_drift",
            "tests/test_release_flow_cli.py::test_preflight_rejects_unknown_bump_plugin",
            "tests/test_release_flow_cli.py::test_project_adds_missing_final_dict_key",
            "tests/test_release_flow_cli.py::test_project_applies_json_env_transform",
            "tests/test_release_flow_cli.py::test_project_applies_json_env_transform_inside_list",
            "tests/test_release_flow_cli.py::test_project_generates_codex_marketplace_from_projection_identity",
            "tests/test_release_flow_cli.py::test_project_rejects_negative_json_pointer_list_index",
            "tests/test_release_flow_cli.py::test_project_rejects_transform_path_outside_project",
            "tests/test_release_flow_cli.py::test_project_rejects_vars_file_argument",
            "tests/test_release_flow_cli.py::test_publish_rejects_dry_run_argument",
            "tests/test_release_flow_cli.py::test_publish_reports_last_eof_after_workflow_run_retries_exhausted",
            "tests/test_release_flow_cli.py::test_publish_requires_authorization_without_dry_run",
            "tests/test_release_flow_cli.py::test_publish_retries_workflow_run_eof_then_succeeds",
            "tests/test_release_flow_cli.py::test_removed_commands_are_not_registered",
            "tests/test_release_flow_cli.py::test_setup_authorized_writes_only_config_projection_gitignore_and_workflow",
            "tests/test_release_flow_cli.py::test_setup_dry_run_does_not_write_project_files",
            "tests/test_release_flow_cli.py::test_validate_rejects_invalid_branch_mode",
            "tests/test_release_flow_cli.py::test_validate_rejects_projection_variable_values",
        ]
    }
)

E2E_ALLOWLIST.update(
    {
        identity: f"covers agent-guard runtime packaged CLI contract: {identity.rsplit('::', 1)[1]}"
        for identity in [
            "tests/test_agent_guard_runtime_brief.py::test_activation_writes_latest_guard_brief_for_session_focus_instance",
            "tests/test_agent_guard_runtime_brief.py::test_brief_injection_dedupes_by_session_and_brief_hash",
            "tests/test_agent_guard_runtime_router.py::test_explicit_user_runtime_scope_uses_user_guard_runtime",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_allow_does_not_bypass_session_focus_deny",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_blocking_review_findings",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_missing_required_capture",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_stale_review_pass_for_build_gate",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_stale_review_pass_with_short_head_artifact_path",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_unknown_artifact_reference",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_when_any_matching_guard_fails",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_when_artifact_missing",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_without_session_focus",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_pass_does_not_change_comet_phase",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_passes_with_artifact",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_passes_with_short_head_artifact_path",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_passes_with_valid_evidence",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_rejects_absolute_evidence_path",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_rejects_capture_path_traversal_outside_evidence_root",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_reports_skipped_and_failing_guards_together",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_reports_unreadable_evidence_separately_from_invalid_json",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_skip_when_falls_back_when_yaml_condition_does_not_match",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_skip_when_unsafe_path_falls_back_to_evidence",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_skip_when_uses_later_matching_condition",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_skips_when_yaml_condition_matches",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_uses_named_capture_value_from_json_check",
            "tests/test_agent_guard_runtime_router.py::test_global_command_guard_uses_parameters_command_and_audits_command",
            "tests/test_agent_guard_runtime_router.py::test_hook_router_preserves_top_level_command_for_global_command_guard",
            "tests/test_agent_guard_runtime_router.py::test_invalid_and_multiple_focus_bindings_error_without_permission_deny",
            "tests/test_agent_guard_runtime_router.py::test_missing_or_closed_instance_is_treated_as_no_focus",
            "tests/test_agent_guard_runtime_router.py::test_planning_review_guard_allows_with_valid_pass_marker",
            "tests/test_agent_guard_runtime_router.py::test_planning_review_guard_denies_invalid_pass_marker_fields",
            "tests/test_agent_guard_runtime_router.py::test_planning_review_guard_denies_stale_pass_marker",
            "tests/test_agent_guard_runtime_router.py::test_planning_review_guard_denies_without_pass_marker",
            "tests/test_agent_guard_runtime_router.py::test_planning_review_guard_matches_direct_path_env_and_wrapped_commands",
            "tests/test_agent_guard_runtime_router.py::test_pre_tool_use_missing_session_id_returns_error_without_focus_audit",
            "tests/test_agent_guard_runtime_router.py::test_pre_tool_use_without_focus_allows_and_audits",
            "tests/test_agent_guard_runtime_router.py::test_pre_tool_use_without_global_command_guard_match_keeps_existing_session_focus_behavior",
            "tests/test_agent_guard_runtime_router.py::test_profile_level_override_does_not_allow_missing_guard_point",
            "tests/test_agent_guard_runtime_router.py::test_project_comet_command_ignores_user_runtime_evidence",
            "tests/test_agent_guard_runtime_router.py::test_run_guard_event_preserves_standard_payload_command_for_global_command_guard",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_advances_current_focus_and_lock_timeout_audits",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_allows_guard_point_failure_with_valid_override",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_allows_json_artifact_equals_check",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_allows_profile_level_override",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_invalid_json_artifact",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_array_all_predicate_failure",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_array_all_where_without_value",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_array_none_predicate_failure",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_array_none_where_with_legacy_expected_config_key",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_artifact_absolute_path_outside_runtime_artifacts_without_leak",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_artifact_equals_check_failure",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_missing_field",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_not_equals_predicate_failure",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_not_equals_with_legacy_expected_config_key",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_not_equals_without_value",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_json_number_predicate_failure",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_missing_json_artifact",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_blocks_unsupported_json_artifact_predicate",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_does_not_accept_expected_config_key_for_json_value",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_evaluates_guard_points_before_advancing",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_rejects_ambiguous_transition_matches",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_reports_supported_guard_point_check_types",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_supports_json_array_all_predicate",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_supports_json_array_none_predicate",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_supports_json_array_where_exists_when_value_is_null",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_supports_json_exists_and_value_predicates",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_supports_json_not_equals_predicate",
            "tests/test_agent_guard_runtime_router.py::test_state_completed_supports_json_number_predicates",
            "tests/test_agent_guard_runtime_router.py::test_user_global_command_guard_uses_project_runtime_for_artifact_scope",
            "tests/test_agent_guard_runtime_router.py::test_user_global_command_guard_uses_project_runtime_for_project_command",
            "tests/test_agent_guard_runtime_router.py::test_valid_focus_evaluates_allow_ask_deny_and_incompatible_version",
            "tests/test_agent_guard_runtime_session_focus.py::test_activate_can_write_user_scope_focus_binding",
            "tests/test_agent_guard_runtime_session_focus.py::test_activate_creates_opaque_instance_and_session_focus_binding",
            "tests/test_agent_guard_runtime_session_focus.py::test_activate_wrapper_does_not_create_without_explicit_create_or_selection",
        ]
    }
)

E2E_ALLOWLIST.update(
    {
        identity: f"covers cross-agent-review packaged CLI contract through helper chain: {identity.rsplit('::', 1)[1]}"
        for identity in [
            "tests/test_cross_agent_review_cli.py::test_clean_worktree_checks_reuse_runtime_allowlist",
            "tests/test_cross_agent_review_cli.py::test_debug_writes_input_prompts_and_raw_under_debug",
            "tests/test_cross_agent_review_cli.py::test_default_run_does_not_archive_context_snapshots_or_git_manifest",
            "tests/test_cross_agent_review_cli.py::test_diff_file_argument_is_not_required",
            "tests/test_cross_agent_review_cli.py::test_internal_dispatch_injection_generates_report_without_results_file",
            "tests/test_cross_agent_review_cli.py::test_prompt_contains_review_context",
            "tests/test_cross_agent_review_cli.py::test_run_accepts_single_review_input_file",
            "tests/test_cross_agent_review_cli.py::test_run_can_be_exercised_with_internal_dispatch_injection",
            "tests/test_cross_agent_review_cli.py::test_run_removes_stale_legacy_pass_marker_from_reused_output_dir",
        ]
    }
)

E2E_ALLOWLIST.update(
    {
        identity: f"covers agent-guard installer packaged CLI contract: {identity.rsplit('::', 1)[1]}"
        for identity in [
            "tests/test_extract_guard_model.py::test_confirmed_notes_generate_valid_guard_profile",
            "tests/test_extract_guard_model.py::test_deny_permissions_require_extra_authorization_before_generation",
            "tests/test_extract_guard_model.py::test_generation_does_not_modify_guarded_target_file",
            "tests/test_extract_guard_model.py::test_generation_includes_guard_point_implementation_plan",
            "tests/test_extract_guard_model.py::test_missing_required_field_reports_needs_confirmation_without_full_profile",
            "tests/test_extract_guard_model.py::test_profile_ref_mismatch_reports_needs_confirmation",
            "tests/test_init_project_guard.py::test_existing_guard_profile_aborts_without_overwriting",
            "tests/test_init_project_guard.py::test_initialization_defaults_to_dry_run_without_writing_project",
            "tests/test_init_project_guard.py::test_initialization_rejects_deprecated_manifest_mode",
            "tests/test_init_project_guard.py::test_initialization_rejects_removed_authorize_blocking_argument",
            "tests/test_init_project_guard.py::test_initialization_requires_extra_authorization_for_deny_permissions",
            "tests/test_init_project_guard.py::test_verified_guard_profile_initializes_project_profile_without_runtime_copy",
            "tests/test_init_user_guard.py::test_authorized_user_guard_initialization_writes_valid_profile",
            "tests/test_init_user_guard.py::test_user_guard_initialization_defaults_to_dry_run",
            "tests/test_init_user_guard.py::test_user_guard_initialization_rejects_deprecated_manifest_mode",
            "tests/test_init_user_guard.py::test_user_guard_initialization_requires_extra_authorization_for_deny_permissions",
        ]
    }
)

E2E_ALLOWLIST.update(
    {
        identity: f"covers pr-flow packaged CLI helper-chain contract: {identity.rsplit('::', 1)[1]}"
        for identity in [
            "tests/test_pr_flow_cli.py::test_project_template_recovers_stale_lock",
            "tests/test_pr_flow_cli.py::test_project_template_recreates_incomplete_template_after_stale_lock",
            "tests/test_pr_flow_cli.py::test_status_file_is_written_for_stop_state",
        ]
    }
)

E2E_ALLOWLIST.update(
    {
        identity: f"covers guard-profile validator packaged CLI contract: {identity.rsplit('::', 1)[1]}"
        for identity in [
            "tests/test_validate_guard_profile.py::test_artifact_reuse_policy_must_be_allow_or_deny",
            "tests/test_validate_guard_profile.py::test_business_specific_builtin_comet_source_is_rejected",
            "tests/test_validate_guard_profile.py::test_empty_global_command_guards_list_does_not_skip_session_focus_required_files",
            "tests/test_validate_guard_profile.py::test_empty_global_command_guards_mapping_does_not_skip_session_focus_required_files",
            "tests/test_validate_guard_profile.py::test_global_command_guard_accepts_git_head_short_context_value",
            "tests/test_validate_guard_profile.py::test_global_command_guard_allows_profile_without_session_focus_config",
            "tests/test_validate_guard_profile.py::test_global_command_guard_duplicate_id_in_same_file_fails",
            "tests/test_validate_guard_profile.py::test_global_command_guard_invalid_skip_when_yaml_config_fails",
            "tests/test_validate_guard_profile.py::test_global_command_guard_missing_command_patterns_fails",
            "tests/test_validate_guard_profile.py::test_global_command_guard_missing_evidence_path_fails",
            "tests/test_validate_guard_profile.py::test_global_command_guard_missing_required_capture_value_fails",
            "tests/test_validate_guard_profile.py::test_global_command_guard_rejects_illegal_value_from",
            "tests/test_validate_guard_profile.py::test_global_command_guard_rejects_unsupported_json_predicate",
            "tests/test_validate_guard_profile.py::test_global_command_guard_unknown_artifact_reference_fails",
            "tests/test_validate_guard_profile.py::test_global_command_guard_valid_config_passes",
            "tests/test_validate_guard_profile.py::test_global_command_guard_valid_skip_when_yaml_config_passes",
            "tests/test_validate_guard_profile.py::test_global_command_guard_with_artifact_reference_passes",
            "tests/test_validate_guard_profile.py::test_global_command_guards_template_file_is_allowed",
            "tests/test_validate_guard_profile.py::test_grill_with_docs_source_requires_confirmed_status",
            "tests/test_validate_guard_profile.py::test_guard_point_check_artifact_must_reference_defined_artifact",
            "tests/test_validate_guard_profile.py::test_guard_point_trigger_field_is_rejected",
            "tests/test_validate_guard_profile.py::test_initial_state_must_reference_state_machine_state",
            "tests/test_validate_guard_profile.py::test_json_artifact_guard_point_check_accepts_defined_artifact_and_predicate",
            "tests/test_validate_guard_profile.py::test_json_artifact_guard_point_check_artifact_must_reference_defined_artifact",
            "tests/test_validate_guard_profile.py::test_json_artifact_guard_point_check_rejects_unknown_predicate",
            "tests/test_validate_guard_profile.py::test_json_artifact_guard_point_check_requires_artifact",
            "tests/test_validate_guard_profile.py::test_json_artifact_guard_point_check_requires_predicate",
            "tests/test_validate_guard_profile.py::test_json_artifact_guard_point_check_requires_string_field",
            "tests/test_validate_guard_profile.py::test_json_artifact_guard_point_check_requires_value_for_comparison_predicate",
            "tests/test_validate_guard_profile.py::test_json_artifact_guard_point_check_requires_where_for_array_predicate",
            "tests/test_validate_guard_profile.py::test_legacy_contract_tokens_are_rejected",
            "tests/test_validate_guard_profile.py::test_legacy_hook_bindings_file_is_rejected",
            "tests/test_validate_guard_profile.py::test_legacy_subject_resolver_file_is_rejected",
            "tests/test_validate_guard_profile.py::test_manifest_mode_is_rejected",
            "tests/test_validate_guard_profile.py::test_manifest_requires_runtime_api_version",
            "tests/test_validate_guard_profile.py::test_minimal_guard_profile_passes_new_session_focus_contract",
            "tests/test_validate_guard_profile.py::test_missing_required_file_reports_category_and_fix",
            "tests/test_validate_guard_profile.py::test_permissions_rules_must_be_a_list",
            "tests/test_validate_guard_profile.py::test_state_completed_transition_conditions_cannot_use_payload",
            "tests/test_validate_guard_profile.py::test_state_transition_on_event_must_be_state_completed",
            "tests/test_validate_guard_profile.py::test_target_environment_guard_profile_source_is_allowed",
        ]
    }
)

E2E_ALLOWLIST.update(
    {
        "tests/test_agent_guard_plugin_runtime_e2e.py::test_cross_agent_review_public_cli_records_evidence_and_unlocks_guard": (
            "covers cross-agent-review run and retry through agent-guard evidence and hook gate"
        ),
        "tests/test_agent_guard_plugin_runtime_e2e.py::test_planning_review_uses_generic_evidence_entry_and_existing_hook_router": (
            "covers planning-review fields through agent-guard evidence and hook gate"
        ),
    }
)

E2E_ALLOWLIST.update(
    {
        identity: f"covers packaged agent-guard record-evidence CLI boundary: {identity.rsplit('::', 1)[1]}"
        for identity in [
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_atomically_replaces_hardlink_without_mutating_target",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_does_not_accept_caller_head_override",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_does_not_fall_back_to_other_profile_source",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_each_reserved_business_field",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_guard_root_alias_inside_source_anchor",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_guard_root_alias_outside_source_anchor",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_invalid_business_fields",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_invalid_profile_registry_or_artifact",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_non_segment_identifiers",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_nonstandard_template_before_git",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_profile_alias_outside_source_root",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_symlink_without_mutating_target",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_symlinked_artifact_registry",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_requires_clean_worktree",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_requires_git_repository",
            "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_writes_current_head_guard_owned_artifact",
        ]
    }
)

E2E_ALLOWLIST.update(
    {
        identity: f"covers cross-agent-review real git runtime boundary: {identity.rsplit('::', 1)[1]}"
        for identity in [
            "tests/test_cross_agent_review_cli.py::test_changed_file_entries_preserves_rename_and_copy_sources",
            "tests/test_cross_agent_review_cli.py::test_changed_file_entries_rejects_malformed_name_status",
            "tests/test_cross_agent_review_cli.py::test_completed_role_is_saved_before_sibling_timeout",
            "tests/test_cross_agent_review_cli.py::test_default_outputs_are_report_and_state_only",
            "tests/test_cross_agent_review_cli.py::test_initial_state_records_subject_context_hashes_and_role_scopes",
            "tests/test_cross_agent_review_cli.py::test_parent_future_exception_is_saved_as_failed_markdown",
            "tests/test_cross_agent_review_cli.py::test_report_is_rebuilt_only_from_state_and_top_level_hash_is_saved",
            "tests/test_cross_agent_review_cli.py::test_retry_dispatches_only_failed_role_and_preserves_success",
            "tests/test_cross_agent_review_cli.py::test_retry_parser_does_not_accept_scope_or_path_arguments",
            "tests/test_cross_agent_review_cli.py::test_retry_rejects_attempt_history_time_reversal_before_dispatch",
            "tests/test_cross_agent_review_cli.py::test_retry_rejects_malformed_state_as_state_mismatch",
            "tests/test_cross_agent_review_cli.py::test_retry_rejects_report_not_bound_to_state_before_dispatch",
            "tests/test_cross_agent_review_cli.py::test_retry_rejects_state_not_bound_to_current_input_and_repository",
            "tests/test_cross_agent_review_cli.py::test_retry_with_no_retryable_roles_does_not_dispatch",
            "tests/test_cross_agent_review_cli.py::test_revalidate_accepts_declared_yaml_mapping_field",
            "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_changed_review_contract",
            "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_ignored_context_missing_from_commits",
            "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_invalid_source_before_writes_or_sdk",
            "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_previous_state_output_collision",
            "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_same_head_before_incremental_work",
            "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_tampered_context_hash",
            "tests/test_cross_agent_review_cli.py::test_revalidate_replaces_linked_report_without_changing_target",
            "tests/test_cross_agent_review_cli.py::test_revalidate_writes_current_reused_state_without_sdk",
            "tests/test_cross_agent_review_cli.py::test_review_input_classifies_context_summary_and_default_full",
            "tests/test_cross_agent_review_cli.py::test_role_input_contains_only_full_review_diff_and_summary_stats",
            "tests/test_cross_agent_review_cli.py::test_sdk_role_subprocess_uses_plugin_owned_timeout",
            "tests/test_cross_agent_review_cli.py::test_summary_only_rejects_invalid_entries",
            "tests/test_cross_agent_review_cli.py::test_summary_only_reports_sorted_classification_overlap_paths",
        ]
    }
)

CURRENT_E2E_ALLOWLIST_IDENTITIES = {
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_cross_agent_review_public_cli_records_evidence_and_unlocks_guard",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_planning_review_uses_generic_evidence_entry_and_existing_hook_router",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_plugin_runtime_e2e_from_verify_to_state_completed",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_atomically_replaces_hardlink_without_mutating_target",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_does_not_accept_caller_head_override",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_does_not_fall_back_to_other_profile_source",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_each_reserved_business_field",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_guard_root_alias_inside_source_anchor",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_guard_root_alias_outside_source_anchor",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_invalid_business_fields",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_invalid_profile_registry_or_artifact",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_non_segment_identifiers",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_nonstandard_template_before_git",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_profile_alias_outside_source_root",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_symlink_without_mutating_target",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_rejects_symlinked_artifact_registry",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_requires_clean_worktree",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_requires_git_repository",
    "tests/test_agent_guard_plugin_runtime_e2e.py::test_record_evidence_writes_current_head_guard_owned_artifact",
    "tests/test_agent_guard_prd_full_e2e.py::test_agent_guard_plugin_prd_full_end_to_end_regression",
    "tests/test_agent_guard_runtime_brief.py::test_activation_writes_latest_guard_brief_for_session_focus_instance",
    "tests/test_agent_guard_runtime_brief.py::test_brief_injection_dedupes_by_session_and_brief_hash",
    "tests/test_agent_guard_runtime_brief.py::test_run_guard_event_surfaces_brief_required_instead_of_hidden_read_and_advance",
    "tests/test_agent_guard_runtime_brief.py::test_skill_render_guard_brief_delegates_to_plugin_runtime",
    "tests/test_agent_guard_runtime_brief.py::test_state_completed_refreshes_latest_guard_brief",
    "tests/test_agent_guard_runtime_brief.py::test_state_completed_requires_current_guard_brief_to_be_read",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_blocking_review_findings",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_stale_head_ref_from_git_head",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_stale_review_pass_for_build_gate",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_stale_review_pass_with_short_head_artifact_path",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_unknown_artifact_reference",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_denies_when_artifact_missing",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_pass_does_not_change_comet_phase",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_passes_with_artifact",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_passes_with_short_head_artifact_path",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_reports_skipped_and_failing_guards_together",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_skip_when_falls_back_when_yaml_condition_does_not_match",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_skip_when_unsafe_path_falls_back_to_evidence",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_skip_when_uses_later_matching_condition",
    "tests/test_agent_guard_runtime_router.py::test_global_command_guard_skips_when_yaml_condition_matches",
    "tests/test_agent_guard_runtime_router.py::test_planning_review_guard_allows_with_valid_pass_marker",
    "tests/test_agent_guard_runtime_router.py::test_planning_review_guard_denies_invalid_pass_marker_fields",
    "tests/test_agent_guard_runtime_router.py::test_planning_review_guard_denies_stale_pass_marker",
    "tests/test_agent_guard_runtime_router.py::test_planning_review_guard_denies_without_pass_marker",
    "tests/test_agent_guard_runtime_router.py::test_planning_review_guard_matches_direct_path_env_and_wrapped_commands",
    "tests/test_agent_guard_runtime_router.py::test_run_guard_event_preserves_standard_payload_command_for_global_command_guard",
    "tests/test_agent_guard_runtime_router.py::test_user_global_command_guard_uses_project_runtime_for_artifact_scope",
    "tests/test_agent_guard_runtime_session_focus.py::test_activate_can_switch_and_close_instances_without_closing_previous_focus",
    "tests/test_agent_guard_runtime_session_focus.py::test_activate_can_write_user_scope_focus_binding",
    "tests/test_agent_guard_runtime_session_focus.py::test_activate_creates_opaque_instance_and_session_focus_binding",
    "tests/test_agent_guard_runtime_session_focus.py::test_activate_wrapper_does_not_create_without_explicit_create_or_selection",
    "tests/test_agent_guard_runtime_session_focus.py::test_hook_adapter_converts_codex_and_claude_lifecycle_payloads",
    "tests/test_agent_guard_runtime_session_focus.py::test_session_start_writes_observation_and_missing_observation_blocks_activation",
    "tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo",
    "tests/test_build_and_verify_plugin.py::test_build_and_verify_user_level_skill_path_runs_verify_without_git",
    "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_initialize_another_project",
    "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_update_itself",
    "tests/test_release_flow_cli.py::test_preflight_rejects_stale_build_and_verify_runtime",
    "tests/test_cross_agent_review_cli.py::test_change_path_traversal_rejects_input_location",
    "tests/test_cross_agent_review_cli.py::test_clean_worktree_checks_reuse_runtime_allowlist",
    "tests/test_cross_agent_review_cli.py::test_copied_tracked_file_into_runtime_artifacts_rejects_before_dispatch",
    "tests/test_cross_agent_review_cli.py::test_changed_file_entries_preserves_rename_and_copy_sources",
    "tests/test_cross_agent_review_cli.py::test_changed_file_entries_rejects_malformed_name_status",
    "tests/test_cross_agent_review_cli.py::test_completed_role_is_saved_before_sibling_timeout",
    "tests/test_cross_agent_review_cli.py::test_debug_extra_file_rejects_before_dispatch",
    "tests/test_cross_agent_review_cli.py::test_debug_writes_input_prompts_and_raw_under_debug",
    "tests/test_cross_agent_review_cli.py::test_default_outputs_are_report_and_state_only",
    "tests/test_cross_agent_review_cli.py::test_default_run_does_not_archive_context_snapshots_or_git_manifest",
    "tests/test_cross_agent_review_cli.py::test_diff_file_argument_is_not_required",
    "tests/test_cross_agent_review_cli.py::test_dirty_worktree_outside_runtime_artifacts_rejects_before_dispatch",
    "tests/test_cross_agent_review_cli.py::test_dirty_worktree_rejects_before_dispatch",
    "tests/test_cross_agent_review_cli.py::test_head_mismatch_rejects_before_dispatch",
    "tests/test_cross_agent_review_cli.py::test_input_file_must_be_named_review_input_json_under_prepared_inputs",
    "tests/test_cross_agent_review_cli.py::test_input_file_must_be_under_change_and_head_runtime_dir",
    "tests/test_cross_agent_review_cli.py::test_internal_dispatch_injection_generates_report_without_results_file",
    "tests/test_cross_agent_review_cli.py::test_initial_state_records_subject_context_hashes_and_role_scopes",
    "tests/test_cross_agent_review_cli.py::test_invalid_base_ref_fails_before_dispatch",
    "tests/test_cross_agent_review_cli.py::test_invalid_mode_fails",
    "tests/test_cross_agent_review_cli.py::test_missing_input_file_fails",
    "tests/test_cross_agent_review_cli.py::test_missing_referenced_plan_file_fails",
    "tests/test_cross_agent_review_cli.py::test_missing_required_review_input_field_fails",
    "tests/test_cross_agent_review_cli.py::test_output_dir_root_extra_file_rejects_before_dispatch",
    "tests/test_cross_agent_review_cli.py::test_prepared_inputs_rejects_extra_directory",
    "tests/test_cross_agent_review_cli.py::test_prepared_inputs_rejects_extra_regular_file",
    "tests/test_cross_agent_review_cli.py::test_parent_future_exception_is_saved_as_failed_markdown",
    "tests/test_cross_agent_review_cli.py::test_prompt_contains_review_context",
    "tests/test_cross_agent_review_cli.py::test_renamed_tracked_file_into_runtime_artifacts_rejects_before_dispatch",
    "tests/test_cross_agent_review_cli.py::test_reviewer_prompt_does_not_inline_large_diff_or_context",
    "tests/test_cross_agent_review_cli.py::test_reviewer_prompt_references_review_input_file_only",
    "tests/test_cross_agent_review_cli.py::test_reviewer_prompt_references_review_input_not_diff_file",
    "tests/test_cross_agent_review_cli.py::test_report_is_rebuilt_only_from_state_and_top_level_hash_is_saved",
    "tests/test_cross_agent_review_cli.py::test_retry_dispatches_only_failed_role_and_preserves_success",
    "tests/test_cross_agent_review_cli.py::test_retry_parser_does_not_accept_scope_or_path_arguments",
    "tests/test_cross_agent_review_cli.py::test_retry_rejects_attempt_history_time_reversal_before_dispatch",
    "tests/test_cross_agent_review_cli.py::test_retry_rejects_malformed_state_as_state_mismatch",
    "tests/test_cross_agent_review_cli.py::test_retry_rejects_report_not_bound_to_state_before_dispatch",
    "tests/test_cross_agent_review_cli.py::test_retry_rejects_state_not_bound_to_current_input_and_repository",
    "tests/test_cross_agent_review_cli.py::test_retry_with_no_retryable_roles_does_not_dispatch",
    "tests/test_cross_agent_review_cli.py::test_run_accepts_single_review_input_file",
    "tests/test_cross_agent_review_cli.py::test_run_can_be_exercised_with_internal_dispatch_injection",
    "tests/test_cross_agent_review_cli.py::test_run_rejects_fake_reviewer_results_argument",
    "tests/test_cross_agent_review_cli.py::test_run_rejects_legacy_tests_file_argument",
    "tests/test_cross_agent_review_cli.py::test_run_removes_stale_legacy_pass_marker_from_reused_output_dir",
    "tests/test_cross_agent_review_cli.py::test_runtime_artifact_file_path_directory_children_reject_before_dispatch",
    "tests/test_cross_agent_review_cli.py::test_revalidate_accepts_declared_yaml_mapping_field",
    "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_changed_review_contract",
    "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_ignored_context_missing_from_commits",
    "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_invalid_source_before_writes_or_sdk",
    "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_previous_state_output_collision",
    "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_same_head_before_incremental_work",
    "tests/test_cross_agent_review_cli.py::test_revalidate_rejects_tampered_context_hash",
    "tests/test_cross_agent_review_cli.py::test_revalidate_replaces_linked_report_without_changing_target",
    "tests/test_cross_agent_review_cli.py::test_revalidate_writes_current_reused_state_without_sdk",
    "tests/test_cross_agent_review_cli.py::test_review_input_classifies_context_summary_and_default_full",
    "tests/test_cross_agent_review_cli.py::test_role_input_contains_only_full_review_diff_and_summary_stats",
    "tests/test_cross_agent_review_cli.py::test_sdk_role_subprocess_uses_plugin_owned_timeout",
    "tests/test_cross_agent_review_cli.py::test_sdk_missing_reports_clear_error",
    "tests/test_cross_agent_review_cli.py::test_sdk_python_directory_reports_clear_error_without_traceback",
    "tests/test_cross_agent_review_cli.py::test_sdk_python_invalid_file_reports_clear_error_without_traceback",
    "tests/test_cross_agent_review_cli.py::test_summary_only_rejects_invalid_entries",
    "tests/test_cross_agent_review_cli.py::test_summary_only_reports_sorted_classification_overlap_paths",
    "tests/test_pr_flow_cli.py::test_project_template_recovers_stale_lock",
    "tests/test_pr_flow_cli.py::test_project_template_recreates_incomplete_template_after_stale_lock",
    "tests/test_pr_flow_cli.py::test_competing_mutation_reports_lock_without_rewriting_status",
    "tests/test_pr_flow_cli.py::test_diagnose_reports_active_lock_without_writing_status",
    "tests/test_pr_flow_cli.py::test_linked_worktrees_use_independent_process_locks_and_status",
    "tests/test_pr_flow_cli.py::test_write_status_keeps_compatibility_file_and_branch_run",
}

E2E_ALLOWLIST = {
    identity: f"{reason}; function={identity.rsplit('::', 1)[1]}"
    for identity, reason in E2E_ALLOWLIST.items()
    if identity in CURRENT_E2E_ALLOWLIST_IDENTITIES
}


def shared_fixture_infos() -> dict[str, FunctionInfo]:
    conftest = TESTS_ROOT / "conftest.py"
    if not conftest.exists():
        return {}
    infos = function_infos(conftest.read_text(encoding="utf-8"))
    return {
        fixture_name: info
        for info in infos.values()
        for fixture_name in info.fixtures
    }


@functools.lru_cache(maxsize=1)
def scan_repository_tests() -> tuple[RuntimeHit, ...]:
    fixtures = shared_fixture_infos()
    hits: list[RuntimeHit] = []
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        relative = path.relative_to(REPO_ROOT)
        source = path.read_text(encoding="utf-8")
        if not may_contain_runtime_hit(source, fixtures):
            continue
        hits.extend(scan_source(relative, source, fixtures))
    return tuple(
        sorted(set(hits), key=lambda hit: (hit.identity, hit.category, hit.line, hit.detail))
    )


def format_hit(hit: RuntimeHit) -> str:
    suggestion = {
        "subprocess": "use in-process call or fake runner",
        "cli-entrypoint": "move branch coverage to in-process call or add focused E2E allowlist reason",
        "temporary-git": "fake git output unless this proves packaged git behavior",
        "broad-cache-scan": "scope cache assertion to one known path",
    }[hit.category]
    return f"{hit.identity}:{hit.line}: {hit.category}: {hit.detail}; {suggestion}"


def test_e2e_allowlist_uses_function_identity_and_reasons() -> None:
    for identity, reason in E2E_ALLOWLIST.items():
        assert identity.startswith("tests/")
        assert "::" in identity
        assert identity.split("::", 1)[1].startswith("test_")
        assert reason.strip()


def test_e2e_allowlist_entries_match_current_runtime_hits() -> None:
    hits = scan_repository_tests()
    hit_identities = {hit.identity for hit in hits}
    violations = [
        format_hit(hit)
        for hit in hits
        if hit.identity not in E2E_ALLOWLIST
    ]

    assert sorted(set(E2E_ALLOWLIST) - hit_identities) == []
    assert violations == []


def test_build_and_verify_keeps_focused_real_entrypoint_coverage() -> None:
    build_and_verify_entries = [
        identity
        for identity in E2E_ALLOWLIST
        if identity.startswith("tests/test_build_and_verify_plugin.py::")
    ]
    init_entries = [
        identity
        for identity, reason in E2E_ALLOWLIST.items()
        if identity.startswith("tests/test_build_and_verify_plugin.py::")
        and "init entrypoint" in reason
    ]
    fast_verify_entries = [
        identity
        for identity, reason in E2E_ALLOWLIST.items()
        if identity.startswith("tests/test_build_and_verify_plugin.py::")
        and "fast-verify entrypoint" in reason
    ]

    assert build_and_verify_entries == [
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo",
        "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_initialize_another_project",
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_user_level_skill_path_runs_verify_without_git",
        "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_update_itself",
    ]
    assert init_entries == [
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo",
        "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_initialize_another_project",
    ]
    assert fast_verify_entries == [
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo",
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_user_level_skill_path_runs_verify_without_git",
    ]
