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
    'tests/test_pr_flow_cli.py::test_competing_mutation_reports_lock_without_rewriting_status': (
        'covers PR Flow cross-process mutation lock behavior in a real git repository; function=test_competing_mutation_reports_lock_without_rewriting_status'
    ),
    'tests/test_pr_flow_cli.py::test_diagnose_reports_active_lock_without_writing_status': (
        'covers PR Flow read-only diagnosis while a real operation lock is held; function=test_diagnose_reports_active_lock_without_writing_status'
    ),
    'tests/test_pr_flow_cli.py::test_linked_worktrees_use_independent_process_locks_and_status': (
        'covers linked-worktree isolation across real PR Flow processes; function=test_linked_worktrees_use_independent_process_locks_and_status'
    ),
    'tests/test_pr_flow_cli.py::test_linked_worktrees_complete_independently_through_cli': (
        'covers concurrent complete entrypoints across real linked worktrees; function=test_linked_worktrees_complete_independently_through_cli'
    ),
    'tests/test_pr_flow_cli.py::test_write_status_keeps_compatibility_file_and_branch_run': (
        'covers per-worktree PR Flow status paths in a real git repository; function=test_write_status_keeps_compatibility_file_and_branch_run'
    ),
    'tests/test_build_and_verify_plugin.py::test_build_and_verify_init_config_overwrite_e2e_temp_target_repo': (
        'covers packaged init entrypoint and copied runtime fast-verify entrypoint; function=test_build_and_verify_init_config_overwrite_e2e_temp_target_repo'
    ),
    'tests/test_build_and_verify_plugin.py::test_copied_runtime_full_performance_report_e2e_temp_target_repo': (
        'covers copied runtime full-verify performance-report entrypoint; function=test_copied_runtime_full_performance_report_e2e_temp_target_repo'
    ),
    'tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_initialize_another_project': (
        'covers copied repository runtime init entrypoint; function=test_copied_repository_runtime_can_initialize_another_project'
    ),
    'tests/test_build_and_verify_plugin.py::test_build_and_verify_user_level_skill_path_runs_verify_without_git': (
        'covers user-level skill path fast-verify entrypoint without git; function=test_build_and_verify_user_level_skill_path_runs_verify_without_git'
    ),
    'tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_directory_hash_uses_git_visible_files': (
        'covers packaged cache behavior against tracked, visible untracked, and ignored files in a real git repository; function=test_build_and_verify_runner_directory_hash_uses_git_visible_files'
    ),
    'tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_update_itself': (
        'covers copied repository runtime update-runtime entrypoint; function=test_copied_repository_runtime_can_update_itself'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_creates_missing_local_base_end_to_end': (
        'covers pr-flow real git cleanup creation of a missing local base; function=test_cleanup_creates_missing_local_base_end_to_end'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_returns_to_available_local_base_end_to_end': (
        'covers pr-flow real git cleanup synchronization of a stale local base; function=test_cleanup_returns_to_available_local_base_end_to_end'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_keeps_detached_when_synced_base_is_checked_out_elsewhere': (
        'covers pr-flow real git cleanup fallback for a synchronized occupied local base; function=test_cleanup_keeps_detached_when_synced_base_is_checked_out_elsewhere'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_refuses_diverged_local_base_end_to_end': (
        'covers pr-flow real git cleanup protection of divergent local base commits; function=test_cleanup_refuses_diverged_local_base_end_to_end'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_fast_forwards_stale_base_checked_out_elsewhere_end_to_end': (
        'covers pr-flow real git cleanup of an occupied stale local base; function=test_cleanup_fast_forwards_stale_base_checked_out_elsewhere_end_to_end'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_refuses_unsafe_stale_base_worktree_end_to_end': (
        'covers pr-flow real git cleanup protection of unsafe occupied stale local bases; function=test_cleanup_refuses_unsafe_stale_base_worktree_end_to_end'
    ),
    'tests/test_release_flow_cli.py::test_preflight_rejects_stale_build_and_verify_runtime': (
        'covers release-flow real git build-and-verify runtime preflight; function=test_preflight_rejects_stale_build_and_verify_runtime'
    ),
    'tests/test_pr_flow_cli.py::test_project_template_recovers_stale_lock': (
        'covers pr-flow packaged CLI helper-chain contract: test_project_template_recovers_stale_lock; function=test_project_template_recovers_stale_lock'
    ),
    'tests/test_pr_flow_cli.py::test_project_template_recreates_incomplete_template_after_stale_lock': (
        'covers pr-flow packaged CLI helper-chain contract: test_project_template_recreates_incomplete_template_after_stale_lock; function=test_project_template_recreates_incomplete_template_after_stale_lock'
    ),
    'tests/test_my_spec.py::test_packed_myspec_installs_a_working_cli_with_agent_resources': (
        'covers npm Tarball packing, isolated installation, and the installed myspec CLI seam; function=test_packed_myspec_installs_a_working_cli_with_agent_resources'
    ),
    'tests/test_my_spec.py::test_spec_ops_cli_validates_applies_all_delta_operations_and_diffs': (
        'covers the packaged spec_ops CLI validation, all Delta operations, preview, and diff seam; function=test_spec_ops_cli_validates_applies_all_delta_operations_and_diffs'
    ),
    'tests/test_my_spec.py::test_spec_ops_cli_rejects_invalid_specs_and_delta_references': (
        'covers packaged spec_ops CLI trust-boundary failures without tracebacks; function=test_spec_ops_cli_rejects_invalid_specs_and_delta_references'
    ),
    'tests/test_my_spec.py::test_spec_ops_cli_persists_complete_conflicts_and_resumes_in_a_new_process': (
        'covers packaged spec_ops CLI complete conflict persistence and cross-process continuation; function=test_spec_ops_cli_persists_complete_conflicts_and_resumes_in_a_new_process'
    ),
    'tests/test_my_spec.py::test_spec_ops_cli_rejects_incomplete_or_out_of_order_conflict_state': (
        'covers packaged spec_ops CLI conflict-state trust-boundary failures; function=test_spec_ops_cli_rejects_incomplete_or_out_of_order_conflict_state'
    ),
    'tests/test_my_spec.py::test_spec_ops_cli_records_each_supported_conflict_decision': (
        'covers packaged spec_ops CLI decision values and ready transition; function=test_spec_ops_cli_records_each_supported_conflict_decision'
    ),
    'tests/test_my_spec.py::test_spec_ops_cli_initializes_a_new_capability_from_an_empty_spec_library': (
        'covers packaged spec_ops CLI empty-library initialization; function=test_spec_ops_cli_initializes_a_new_capability_from_an_empty_spec_library'
    ),
    'tests/test_my_spec.py::test_spec_ops_preview_auto_merges_identical_duplicate_requirements_but_main_validation_stays_strict': (
        'covers strict validation plus deterministic preview repair for identical duplicates; function=test_spec_ops_preview_auto_merges_identical_duplicate_requirements_but_main_validation_stays_strict'
    ),
    'tests/test_my_spec.py::test_spec_add_deterministic_post_analysis_flow_previews_diffs_and_applies': (
        'covers the packaged spec-add deterministic post-analysis workflow; function=test_spec_add_deterministic_post_analysis_flow_previews_diffs_and_applies'
    ),
    'tests/test_my_spec.py::test_spec_review_deterministic_duplicate_flow_previews_diffs_and_applies': (
        'covers the packaged spec-review deterministic duplicate workflow; function=test_spec_review_deterministic_duplicate_flow_previews_diffs_and_applies'
    ),
    'tests/test_my_spec.py::test_spec_audit_deterministic_post_analysis_flow_previews_diffs_and_applies': (
        'covers the packaged spec-audit deterministic post-analysis workflow; function=test_spec_audit_deterministic_post_analysis_flow_previews_diffs_and_applies'
    ),
    'tests/test_my_spec.py::test_apply_delta_can_atomically_replace_main_after_final_confirmation': (
        'covers packaged spec_ops CLI final atomic replacement and idempotent no-op behavior; function=test_apply_delta_can_atomically_replace_main_after_final_confirmation'
    ),
    'tests/test_my_spec.py::test_myspec_launcher_forwards_sigterm_to_python': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_myspec_launcher_forwards_sigterm_to_python'
    ),
    'tests/test_my_spec.py::test_packed_myspec_claude_reinstall_failure_does_not_report_refreshed': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_claude_reinstall_failure_does_not_report_refreshed'
    ),
    'tests/test_my_spec.py::test_packed_myspec_dev_preflight_rejects_incomplete_source_before_link_or_state': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_dev_preflight_rejects_incomplete_source_before_link_or_state'
    ),
    'tests/test_my_spec.py::test_packed_myspec_disables_only_exact_legacy_pi_sources': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_disables_only_exact_legacy_pi_sources'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_applies_effective_pi_skill_filters_and_manifest': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_doctor_applies_effective_pi_skill_filters_and_manifest'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_does_not_enable_settings_source_missing_from_pi_list': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_doctor_does_not_enable_settings_source_missing_from_pi_list'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_reads_legacy_git_and_npm_manifests_from_pi_list': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_doctor_reads_legacy_git_and_npm_manifests_from_pi_list'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_reports_actual_package_version_mismatch': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_doctor_reports_actual_package_version_mismatch'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_reports_claude_marketplace_source_mismatch_read_only': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_doctor_reports_claude_marketplace_source_mismatch_read_only'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_reports_duplicate_enabled_pi_sources': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_doctor_reports_duplicate_enabled_pi_sources'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_reports_partial_update_read_only': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_doctor_reports_partial_update_read_only'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_uses_actual_installation_not_mode_state': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_doctor_uses_actual_installation_not_mode_state'
    ),
    'tests/test_my_spec.py::test_packed_myspec_explicit_claude_init_refreshes_disabled_stale_plugin': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_explicit_claude_init_refreshes_disabled_stale_plugin'
    ),
    'tests/test_my_spec.py::test_packed_myspec_follows_project_scope_reported_by_pi_list': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_follows_project_scope_reported_by_pi_list'
    ),
    'tests/test_my_spec.py::test_packed_myspec_ignores_project_settings_absent_from_pi_list': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_ignores_project_settings_absent_from_pi_list'
    ),
    'tests/test_my_spec.py::test_packed_myspec_initializes_and_diagnoses_claude_without_deleting_legacy': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_initializes_and_diagnoses_claude_without_deleting_legacy'
    ),
    'tests/test_my_spec.py::test_packed_myspec_initializes_and_diagnoses_codex_without_deleting_legacy': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_initializes_and_diagnoses_codex_without_deleting_legacy'
    ),
    'tests/test_my_spec.py::test_packed_myspec_initializes_and_diagnoses_one_pi_source': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_initializes_and_diagnoses_one_pi_source'
    ),
    'tests/test_my_spec.py::test_packed_myspec_keeps_project_legacy_sources_without_installed_paths': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_keeps_project_legacy_sources_without_installed_paths'
    ),
    'tests/test_my_spec.py::test_packed_myspec_mode_switch_does_not_install_a_disabled_pi_integration': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_mode_switch_does_not_install_a_disabled_pi_integration'
    ),
    'tests/test_my_spec.py::test_packed_myspec_mode_switch_does_not_install_missing_or_disabled_claude': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_mode_switch_does_not_install_missing_or_disabled_claude'
    ),
    'tests/test_my_spec.py::test_packed_myspec_mode_switch_does_not_install_missing_or_disabled_codex': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_mode_switch_does_not_install_missing_or_disabled_codex'
    ),
    'tests/test_my_spec.py::test_packed_myspec_package_contains_single_codex_marketplace_and_four_skills': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_package_contains_single_codex_marketplace_and_four_skills'
    ),
    'tests/test_my_spec.py::test_packed_myspec_pi_git_identity_matches_pi_host_path_semantics': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_pi_git_identity_matches_pi_host_path_semantics'
    ),
    'tests/test_my_spec.py::test_packed_myspec_preserves_lock_when_process_status_is_unknown': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_preserves_lock_when_process_status_is_unknown'
    ),
    'tests/test_my_spec.py::test_packed_myspec_refreshes_enabled_claude_across_global_mode_switches': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_refreshes_enabled_claude_across_global_mode_switches'
    ),
    'tests/test_my_spec.py::test_packed_myspec_refreshes_enabled_codex_across_global_mode_switches': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_refreshes_enabled_codex_across_global_mode_switches'
    ),
    'tests/test_my_spec.py::test_packed_myspec_rejects_invalid_mode_switches': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_rejects_invalid_mode_switches'
    ),
    'tests/test_my_spec.py::test_packed_myspec_release_install_failure_stays_in_dev_and_retries': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_release_install_failure_stays_in_dev_and_retries'
    ),
    'tests/test_my_spec.py::test_packed_myspec_reports_missing_pi_without_installing_it': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_reports_missing_pi_without_installing_it'
    ),
    'tests/test_my_spec.py::test_packed_myspec_requires_explicit_claude_but_all_initializes_detected_claude': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_requires_explicit_claude_but_all_initializes_detected_claude'
    ),
    'tests/test_my_spec.py::test_packed_myspec_requires_explicit_codex_but_all_initializes_detected_codex': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_requires_explicit_codex_but_all_initializes_detected_codex'
    ),
    'tests/test_my_spec.py::test_packed_myspec_requires_release_registration_before_first_codex_dev_init': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_requires_release_registration_before_first_codex_dev_init'
    ),
    'tests/test_my_spec.py::test_packed_myspec_resolves_user_and_project_pi_sources_from_each_settings_file': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_resolves_user_and_project_pi_sources_from_each_settings_file'
    ),
    'tests/test_my_spec.py::test_packed_myspec_serializes_init_and_reports_locks_without_mutating_them': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_serializes_init_and_reports_locks_without_mutating_them'
    ),
    'tests/test_my_spec.py::test_packed_myspec_switches_pi_between_development_and_saved_release': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_switches_pi_between_development_and_saved_release'
    ),
    'tests/test_my_spec.py::test_packed_myspec_update_preflights_installed_clients_before_package_write': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_update_preflights_installed_clients_before_package_write'
    ),
    'tests/test_my_spec.py::test_packed_myspec_update_recovers_external_success_before_bookkeeping': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_update_recovers_external_success_before_bookkeeping'
    ),
    'tests/test_my_spec.py::test_packed_myspec_update_refreshes_disabled_integrations_and_skips_only_missing': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_update_refreshes_disabled_integrations_and_skips_only_missing'
    ),
    'tests/test_my_spec.py::test_packed_myspec_update_rejects_dev_mode_and_forged_resume': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_update_rejects_dev_mode_and_forged_resume'
    ),
    'tests/test_my_spec.py::test_packed_myspec_uses_pi_list_project_scope_over_saved_trust': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_uses_pi_list_project_scope_over_saved_trust'
    ),
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
        "tests/test_build_and_verify_plugin.py::test_copied_runtime_full_performance_report_e2e_temp_target_repo",
        "tests/test_build_and_verify_plugin.py::test_copied_repository_runtime_can_initialize_another_project",
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_user_level_skill_path_runs_verify_without_git",
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_directory_hash_uses_git_visible_files",
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
