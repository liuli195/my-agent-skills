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
    'tests/test_build_and_verify_cli.py::test_controlled_pack_rejects_unknown_package': (
        'covers the controlled package CLI rejecting an unknown package; function=test_controlled_pack_rejects_unknown_package'
    ),
    'tests/test_build_and_verify_cli.py::test_controlled_pack_rejects_repository_output': (
        'covers the controlled package CLI rejecting repository output; function=test_controlled_pack_rejects_repository_output'
    ),
    'tests/test_build_and_verify_cli.py::test_build_and_verify_package_excludes_legacy_skill_runtime': (
        'covers npm package contents excluding the removed legacy skill runtime; function=test_build_and_verify_package_excludes_legacy_skill_runtime'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_rejects_untrusted_dev_source': (
        'covers the isolated Build and Verify CLI rejecting an untrusted development source; function=test_packed_build_and_verify_rejects_untrusted_dev_source'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_doctor_reports_machine_readable_release_identity': (
        'covers the isolated Build and Verify npm package through its public doctor CLI; function=test_packed_build_and_verify_doctor_reports_machine_readable_release_identity'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_update_blocks_legacy_codex_before_writes': (
        'covers the installed Build and Verify update CLI blocking legacy Codex migration before package, state, or client writes; function=test_packed_build_and_verify_update_blocks_legacy_codex_before_writes'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_codex_doctor_resolves_orca_and_explicit_homes': (
        'covers the installed Build and Verify CLI selecting an Orca-safe Codex profile and preserving explicit overrides; function=test_packed_build_and_verify_codex_doctor_resolves_orca_and_explicit_homes'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_accepts_controlled_ssh_dev_source': (
        'covers the packaged Build and Verify development-mode entrypoint with an official SSH remote and published commit; function=test_packed_build_and_verify_accepts_controlled_ssh_dev_source'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_dev_identity_controls_public_verify_cache': (
        'covers packaged Build and Verify doctor and fast/full verify cache invalidation for development identity changes; function=test_packed_build_and_verify_dev_identity_controls_public_verify_cache'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_migrates_recognized_runtime_after_fast_verify': (
        'covers the installed Build and Verify CLI fast-verify migration in a clean temporary git repository; function=test_packed_build_and_verify_migrates_recognized_runtime_after_fast_verify'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_preserves_legacy_runtime_when_verify_fails': (
        'covers the installed Build and Verify CLI preserving a legacy runtime after verification failure; function=test_packed_build_and_verify_preserves_legacy_runtime_when_verify_fails'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_rejects_unrecognized_legacy_runtime': (
        'covers the installed Build and Verify CLI refusing an unrecognized legacy runtime before verification; function=test_packed_build_and_verify_rejects_unrecognized_legacy_runtime'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_preserves_runtime_when_fast_verify_stages_external_file': (
        'covers the installed Build and Verify CLI preserving its legacy runtime when fast verification stages an external file; function=test_packed_build_and_verify_preserves_runtime_when_fast_verify_stages_external_file'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_restores_runtime_when_migration_commit_fails': (
        'covers the installed Build and Verify CLI restoring a legacy runtime after its migration commit fails; function=test_packed_build_and_verify_restores_runtime_when_migration_commit_fails'
    ),
    'tests/test_build_and_verify_cli.py::test_packed_build_and_verify_rejects_dirty_legacy_migration': (
        'covers the installed Build and Verify CLI rejecting legacy migration in a dirty temporary git repository; function=test_packed_build_and_verify_rejects_dirty_legacy_migration'
    ),
    'tests/test_pr_flow_cli.py::test_competing_mutation_reports_lock_without_rewriting_status': (
        'covers PR Flow cross-process mutation lock behavior in a real git repository; function=test_competing_mutation_reports_lock_without_rewriting_status'
    ),
    'tests/test_pr_flow_cli.py::test_diagnose_reports_active_lock_without_writing_status': (
        'covers PR Flow read-only diagnosis while a real operation lock is held; function=test_diagnose_reports_active_lock_without_writing_status'
    ),
    'tests/test_pr_flow_cli.py::test_pi_tool_runs_packaged_complete_through_merge_and_cleanup': (
        'covers the packaged Pi pr_flow tool through a real process, temporary git repository, merge, and cleanup; function=test_pi_tool_runs_packaged_complete_through_merge_and_cleanup'
    ),
    'tests/test_pr_flow_cli.py::test_linked_worktrees_use_independent_process_locks_and_status': (
        'covers linked-worktree isolation across real PR Flow processes; function=test_linked_worktrees_use_independent_process_locks_and_status'
    ),
    'tests/test_pr_flow_cli.py::test_linked_worktrees_complete_independently_through_cli': (
        'covers concurrent complete entrypoints across real linked worktrees; function=test_linked_worktrees_complete_independently_through_cli'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_handles_windows_long_paths_through_cli': (
        'covers the public cleanup CLI removing a real Windows long-path worktree with generated state; function=test_cleanup_handles_windows_long_paths_through_cli'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_removes_junction_residue_without_shared_targets': (
        'covers the public cleanup CLI removing a real Windows junction-backed worktree without deleting shared dependencies; function=test_cleanup_removes_junction_residue_without_shared_targets'
    ),
    'tests/test_pr_flow_cli.py::test_remove_worktree_prefers_matched_orca_worktree': (
        'covers the Orca worktree removal adapter with real Windows junctions while preserving shared dependencies; function=test_remove_worktree_prefers_matched_orca_worktree'
    ),
    'tests/test_pr_flow_cli.py::test_write_status_keeps_compatibility_file_and_branch_run': (
        'covers per-worktree PR Flow status paths in a real git repository; function=test_write_status_keeps_compatibility_file_and_branch_run'
    ),
    'tests/test_pr_flow_cli.py::test_complete_commits_only_changed_managed_file_through_public_cli': (
        'covers the public complete CLI committing only the changed managed toolchain workflow; function=test_complete_commits_only_changed_managed_file_through_public_cli'
    ),
    'tests/test_pr_flow_cli.py::test_complete_refuses_dirty_tree_without_staging_managed_files_through_public_cli': (
        'covers the public complete CLI rejecting dirty toolchain synchronization without staged files; function=test_complete_refuses_dirty_tree_without_staging_managed_files_through_public_cli'
    ),
    'tests/test_pr_flow_cli.py::test_complete_restores_toolchain_files_and_index_when_commit_fails_through_public_cli': (
        'covers the public complete CLI restoring its managed files and index after a toolchain commit failure; function=test_complete_restores_toolchain_files_and_index_when_commit_fails_through_public_cli'
    ),
    'tests/test_pr_flow_cli.py::test_complete_rereads_the_new_baseline_with_bounded_toolchain_retries': (
        'covers the public complete CLI bounded toolchain identity retries from each new commit baseline; function=test_complete_rereads_the_new_baseline_with_bounded_toolchain_retries'
    ),
    'tests/test_pr_flow_cli.py::test_init_accepts_same_worktree_with_stable_toolchain_identities': (
        'covers the public init CLI accepting a same-worktree development binding with stable toolchain identities; function=test_init_accepts_same_worktree_with_stable_toolchain_identities'
    ),
    'tests/test_pr_flow_cli.py::test_init_fails_closed_when_dev_implementation_commit_is_unavailable': (
        'covers the public init CLI failing closed when no CI-reproducible development implementation commit is reported; function=test_init_fails_closed_when_dev_implementation_commit_is_unavailable'
    ),
    'tests/test_pr_flow_cli.py::test_lifecycle_syncs_same_worktree_toolchain_before_remote_flow': (
        'covers public complete and tweak synchronization continuing from a same-worktree development binding; function=test_lifecycle_syncs_same_worktree_toolchain_before_remote_flow'
    ),
    'tests/test_pr_flow_cli.py::test_toolchain_sync_converges_for_independent_and_shared_tool_changes': (
        'covers public PR Flow synchronization convergence for independent plugin and shared lifecycle identity updates; function=test_toolchain_sync_converges_for_independent_and_shared_tool_changes'
    ),
    'tests/test_pr_flow_cli.py::test_init_uses_target_project_as_toolchain_doctor_cwd': (
        'covers the public init CLI running tool diagnostics in the target project directory; function=test_init_uses_target_project_as_toolchain_doctor_cwd'
    ),
    'tests/test_pr_flow_cli.py::test_init_validates_release_and_dev_toolchain_identities_through_public_cli': (
        'covers the public init CLI accepting fixed release and trusted source toolchain identities; function=test_init_validates_release_and_dev_toolchain_identities_through_public_cli'
    ),
    'tests/test_pr_flow_cli.py::test_init_rejects_untrusted_toolchain_identity_through_public_cli': (
        'covers the public init CLI rejecting non-fixed or untrusted toolchain identities; function=test_init_rejects_untrusted_toolchain_identity_through_public_cli'
    ),
    'tests/test_pr_flow_cli.py::test_legacy_repositories_keep_flow_behavior_with_upgrade_prompt': (
        'covers public diagnose complete and tweak CLI upgrade prompts for legacy repositories; function=test_legacy_repositories_keep_flow_behavior_with_upgrade_prompt'
    ),
    'tests/test_setup_worktree_script.py::test_setup_worktree_script_links_shared_node_dependencies': (
        'covers the PowerShell setup entrypoint against a real linked worktree and Windows junction; function=test_setup_worktree_script_links_shared_node_dependencies'
    ),
    'tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_directory_hash_uses_git_visible_files': (
        'covers packaged cache behavior against tracked, visible untracked, and ignored files in a real git repository; function=test_build_and_verify_runner_directory_hash_uses_git_visible_files'
    ),
    'tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_glob_inputs_track_visible_matching_files': (
        'covers glob cache behavior against tracked and visible untracked files in a real git repository; function=test_build_and_verify_runner_glob_inputs_track_visible_matching_files'
    ),
    'tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_glob_inputs_ignore_ignored_files_and_normalize_separators': (
        'covers glob cache behavior for ignored files, literal ignored inputs, and Windows separators in a real git repository; function=test_build_and_verify_runner_glob_inputs_ignore_ignored_files_and_normalize_separators'
    ),
    'tests/test_build_and_verify_plugin.py::test_build_and_verify_cli_baseline_uses_verification_worktree_and_explicit_range': (
        'covers the real Build and Verify fast-verify CLI using a fixed baseline and linked worktree isolation; function=test_build_and_verify_cli_baseline_uses_verification_worktree_and_explicit_range'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_creates_missing_local_base_end_to_end': (
        'covers pr-flow real git cleanup creation of a missing local base; function=test_cleanup_creates_missing_local_base_end_to_end'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_returns_to_available_local_base_end_to_end': (
        'covers pr-flow real git cleanup synchronization of a stale local base; function=test_cleanup_returns_to_available_local_base_end_to_end'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_retains_active_worktree_detached_after_branch_cleanup': (
        'covers pr-flow cleanup retaining the active target worktree detached after deleting source branches; function=test_cleanup_retains_active_worktree_detached_after_branch_cleanup'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_retains_active_worktree_when_project_is_directory_alias': (
        'covers pr-flow cleanup retaining an active worktree when project uses a directory alias; function=test_cleanup_retains_active_worktree_when_project_is_directory_alias'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_retains_active_worktree_when_cwd_uses_directory_alias': (
        'covers pr-flow cleanup retaining an active worktree when cwd uses a directory alias; function=test_cleanup_retains_active_worktree_when_cwd_uses_directory_alias'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_retains_active_worktree_with_ignored_cwd_after_branch_cleanup': (
        'covers pr-flow cleanup preserving an ignored active cwd while retaining the worktree; function=test_cleanup_retains_active_worktree_with_ignored_cwd_after_branch_cleanup'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_retains_active_worktree_when_active_cwd_is_inside_ignored_directory_link': (
        'covers pr-flow cleanup retaining an active worktree from a real directory link without deleting shared target contents; function=test_cleanup_retains_active_worktree_when_active_cwd_is_inside_ignored_directory_link'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_stops_before_detaching_when_active_cwd_is_untracked_and_not_ignored': (
        'covers pr-flow cleanup refusing an untracked non-ignored active cwd before target checkout; function=test_cleanup_stops_before_detaching_when_active_cwd_is_untracked_and_not_ignored'
    ),
    'tests/test_pr_flow_cli.py::test_cleanup_stops_before_detaching_when_active_cwd_disappears_on_base_checkout': (
        'covers pr-flow cleanup preserving an active source-only cwd before target checkout; function=test_cleanup_stops_before_detaching_when_active_cwd_disappears_on_base_checkout'
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
    'tests/test_release_flow_cli.py::test_ci_publish_rejects_metadata_before_candidate_release_tree_is_built': (
        'covers release-flow CI publish stopping on selected npm metadata before building the candidate tree; function=test_ci_publish_rejects_metadata_before_candidate_release_tree_is_built'
    ),
    'tests/test_release_flow_cli.py::test_preflight_checks_repository_metadata_only_for_selected_npm_plugin': (
        'covers release-flow preflight checking metadata only for the selected npm plugin; function=test_preflight_checks_repository_metadata_only_for_selected_npm_plugin'
    ),
    'tests/test_release_flow_cli.py::test_publish_accepts_valid_selected_npm_metadata_and_dispatches': (
        'covers release-flow publish dispatching after selected npm metadata passes; function=test_publish_accepts_valid_selected_npm_metadata_and_dispatches'
    ),
    'tests/test_release_flow_cli.py::test_publish_rejects_metadata_before_triggering_remote_workflow': (
        'covers release-flow publish stopping on invalid npm metadata before remote workflow dispatch; function=test_publish_rejects_metadata_before_triggering_remote_workflow'
    ),
    'tests/test_release_flow_cli.py::test_release_workflows_compare_packed_repository_metadata': (
        'covers the release workflow command comparing source and packed npm repository metadata through Node; function=test_release_workflows_compare_packed_repository_metadata'
    ),
    'tests/test_release_flow_cli.py::test_validate_accepts_supported_github_repository_urls': (
        'covers release-flow validate parsing supported GitHub repository URL forms; function=test_validate_accepts_supported_github_repository_urls'
    ),
    'tests/test_release_flow_cli.py::test_validate_checks_all_existing_registered_npm_packages': (
        'covers release-flow validate checking every existing registered npm package; function=test_validate_checks_all_existing_registered_npm_packages'
    ),
    'tests/test_release_flow_cli.py::test_validate_rejects_conflicting_github_actions_repository_identity': (
        'covers release-flow validate failing closed on conflicting GitHub Actions identity sources; function=test_validate_rejects_conflicting_github_actions_repository_identity'
    ),
    'tests/test_release_flow_cli.py::test_validate_uses_origin_outside_github_actions': (
        'covers release-flow validate ignoring an untrusted GitHub repository environment value outside Actions; function=test_validate_uses_origin_outside_github_actions'
    ),
    'tests/test_release_flow_cli.py::test_validate_rejects_missing_npm_repository_metadata': (
        'covers release-flow validate reporting missing npm repository metadata and recovery; function=test_validate_rejects_missing_npm_repository_metadata'
    ),
    'tests/test_release_flow_cli.py::test_validate_requires_repository_identity_in_github_actions': (
        'covers release-flow validate failing closed when GitHub Actions omits its repository identity; function=test_validate_requires_repository_identity_in_github_actions'
    ),
    'tests/test_release_flow_cli.py::test_validate_reports_stable_npm_repository_errors': (
        'covers release-flow validate reporting stable npm repository URL errors; function=test_validate_reports_stable_npm_repository_errors'
    ),
    'tests/test_release_flow_cli.py::test_validate_reports_wrong_existing_npm_repository_directory': (
        'covers release-flow validate reporting an incorrect existing npm repository directory; function=test_validate_reports_wrong_existing_npm_repository_directory'
    ),
    'tests/test_release_flow_cli.py::test_preflight_ignores_legacy_build_and_verify_runtime': (
        'covers release-flow preflight ignoring a legacy build-and-verify runtime; function=test_preflight_ignores_legacy_build_and_verify_runtime'
    ),
    'tests/test_release_flow_cli.py::test_preflight_rejects_changed_marketplace_input_without_bump': (
        'covers release-flow preflight rejecting changed marketplace input without a selected bump; function=test_preflight_rejects_changed_marketplace_input_without_bump'
    ),
    'tests/test_release_flow_cli.py::test_preflight_refreshes_remote_baseline_before_comparing': (
        'covers release-flow preflight refreshing the remote release baseline; function=test_preflight_refreshes_remote_baseline_before_comparing'
    ),
    'tests/test_release_flow_cli.py::test_preflight_rejects_changed_unprojected_marketplace_input_without_bump': (
        'covers release-flow preflight checking an unprojected marketplace target; function=test_preflight_rejects_changed_unprojected_marketplace_input_without_bump'
    ),
    'tests/test_release_flow_cli.py::test_preflight_rejects_changed_npm_input_without_bump_when_not_in_projection': (
        'covers release-flow preflight checking an NPM target omitted from the marketplace projection; function=test_preflight_rejects_changed_npm_input_without_bump_when_not_in_projection'
    ),
    'tests/test_release_flow_cli.py::test_preflight_rejects_shared_npm_input_when_only_one_npm_plugin_is_selected': (
        'covers release-flow preflight associating shared NPM inputs with every affected target; function=test_preflight_rejects_shared_npm_input_when_only_one_npm_plugin_is_selected'
    ),
    'tests/test_release_flow_cli.py::test_preflight_rejects_npm_metadata_drift_without_bump': (
        'covers release-flow preflight rejecting NPM metadata drift without a selected bump; function=test_preflight_rejects_npm_metadata_drift_without_bump'
    ),
    'tests/test_release_flow_cli.py::test_preflight_rejects_selected_content_without_version_advancement': (
        'covers release-flow preflight rejecting selected content without a baseline version advancement; function=test_preflight_rejects_selected_content_without_version_advancement'
    ),
    'tests/test_release_flow_cli.py::test_preflight_accepts_semver_prerelease_advancement': (
        'covers release-flow preflight comparing valid SemVer prerelease advancement; function=test_preflight_accepts_semver_prerelease_advancement'
    ),
    'tests/test_release_flow_cli.py::test_preflight_rejects_selected_version_downgrade': (
        'covers release-flow preflight rejecting selected version downgrade; function=test_preflight_rejects_selected_version_downgrade'
    ),
    'tests/test_release_flow_cli.py::test_preflight_accepts_selected_npm_plugin_with_all_versions_advanced': (
        'covers release-flow preflight accepting a selected NPM target with consistent advanced versions; function=test_preflight_accepts_selected_npm_plugin_with_all_versions_advanced'
    ),
    'tests/test_release_flow_cli.py::test_preflight_checks_npm_package_version_with_plugin_manifests': (
        'covers release-flow preflight checking NPM package metadata alongside plugin manifests; function=test_preflight_checks_npm_package_version_with_plugin_manifests'
    ),
    'tests/test_release_flow_cli.py::test_preflight_accepts_projection_only_change_without_plugin_input_drift': (
        'covers release-flow preflight accepting projection-only changes without plugin input drift; function=test_preflight_accepts_projection_only_change_without_plugin_input_drift'
    ),
    'tests/test_release_flow_cli.py::test_preflight_rejects_shared_npm_packer_input_when_only_one_npm_plugin_is_selected': (
        'covers release-flow preflight associating shared NPM packer input with every affected target; function=test_preflight_rejects_shared_npm_packer_input_when_only_one_npm_plugin_is_selected'
    ),
    'tests/test_release_flow_cli.py::test_release_workflows_publish_only_verified_selected_npm_packages': (
        'covers release workflow Node manifest loading through the exact relative candidate paths; function=test_release_workflows_publish_only_verified_selected_npm_packages'
    ),
    'tests/test_pr_flow_cli.py::test_project_template_recovers_stale_lock': (
        'covers pr-flow packaged CLI helper-chain contract: test_project_template_recovers_stale_lock; function=test_project_template_recovers_stale_lock'
    ),
    'tests/test_pr_flow_cli.py::test_project_template_recreates_incomplete_template_after_stale_lock': (
        'covers pr-flow packaged CLI helper-chain contract: test_project_template_recreates_incomplete_template_after_stale_lock; function=test_project_template_recreates_incomplete_template_after_stale_lock'
    ),
    'tests/test_local_plugin_build_checks.py::test_my_spec_candidate_path_reaches_real_xdist_workers': (
        'covers four real pytest-xdist workers inheriting one absolute MySpec candidate Tarball path; function=test_my_spec_candidate_path_reaches_real_xdist_workers'
    ),
    'tests/test_my_spec.py::test_packed_myspec_installs_a_working_cli_with_agent_resources': (
        'covers npm Tarball packing, isolated installation, and the installed myspec CLI seam; function=test_packed_myspec_installs_a_working_cli_with_agent_resources'
    ),
    'tests/test_my_spec.py::test_my_spec_candidate_tarball_is_shared_by_isolated_installs': (
        'covers one run-scoped MySpec candidate Tarball reused by isolated installations; function=test_my_spec_candidate_tarball_is_shared_by_isolated_installs'
    ),
    'tests/test_my_spec.py::test_packed_myspec_preserves_modified_requirement_order': (
        'covers the installed myspec CLI preserving same-capability Requirement order while retaining cross-capability moves; function=test_packed_myspec_preserves_modified_requirement_order'
    ),
    'tests/test_my_spec.py::test_spec_ops_cli_validates_applies_all_delta_operations_and_diffs': (
        'covers the packaged spec_ops CLI validation, all Delta operations, preview, and diff seam; function=test_spec_ops_cli_validates_applies_all_delta_operations_and_diffs'
    ),
    'tests/test_my_spec.py::test_myspec_cli_preserves_untouched_lf_and_crlf_bytes_for_preview_and_apply': (
        'covers the public myspec CLI preserving untouched LF and CRLF bytes across preview, atomic apply, and repeat apply; function=test_myspec_cli_preserves_untouched_lf_and_crlf_bytes_for_preview_and_apply'
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
    'tests/test_my_spec.py::test_myspec_final_apply_requires_the_confirmed_preview': (
        'covers MySpec final application refusing to replace a target without a confirmed preview; function=test_myspec_final_apply_requires_the_confirmed_preview'
    ),
    'tests/test_my_spec.py::test_myspec_final_apply_rejects_bound_content_drift_after_preview': (
        'covers MySpec final application stopping on specification, input, or preview drift after confirmation; function=test_myspec_final_apply_rejects_bound_content_drift_after_preview'
    ),
    'tests/test_my_spec.py::test_myspec_final_apply_rejects_unconfirmed_implementation_identity': (
        'covers MySpec final application stopping when the persisted implementation identity cannot be confirmed; function=test_myspec_final_apply_rejects_unconfirmed_implementation_identity'
    ),
    'tests/test_my_spec.py::test_myspec_final_apply_rejects_missing_bound_content_fingerprints': (
        'covers MySpec final application stopping when persisted specification or input content fingerprints are missing; function=test_myspec_final_apply_rejects_missing_bound_content_fingerprints'
    ),
    'tests/test_my_spec.py::test_myspec_launcher_forwards_sigterm_to_python': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_myspec_launcher_forwards_sigterm_to_python'
    ),
    'tests/test_my_spec.py::test_packed_myspec_clients_run_shared_source_cases': (
        'covers all shared source-state cases through the installed MySpec npm package, native client substitutes, and public doctor CLI; function=test_packed_myspec_clients_run_shared_source_cases'
    ),
    'tests/test_my_spec.py::test_packed_myspec_bare_cli_uses_isolated_package_before_host_commands': (
        'covers the installed MySpec Tarball through a bare PATH CLI and a complete isolated specification workflow; function=test_packed_myspec_bare_cli_uses_isolated_package_before_host_commands'
    ),
    'tests/test_my_spec.py::test_packed_myspec_codex_doctor_uses_user_home_when_orca_home_is_inherited': (
        'covers the installed MySpec CLI selecting the user Codex profile when Orca inherits a temporary profile; function=test_packed_myspec_codex_doctor_uses_user_home_when_orca_home_is_inherited'
    ),
    'tests/test_my_spec.py::test_packed_myspec_bare_doctor_does_not_require_codex_home': (
        'covers the installed MySpec CLI preserving the bare doctor default when Codex home is invalid; function=test_packed_myspec_bare_doctor_does_not_require_codex_home'
    ),
    'tests/test_my_spec.py::test_packed_myspec_explicit_codex_home_errors_without_codex': (
        'covers the installed MySpec CLI rejecting an explicit unavailable Codex profile even when Codex is absent; function=test_packed_myspec_explicit_codex_home_errors_without_codex'
    ),
    'tests/test_my_spec.py::test_packed_myspec_claude_init_keeps_legacy_when_stable_version_is_wrong': (
        'covers packaged Claude cleanup preserving legacy state when stable verification fails; function=test_packed_myspec_claude_init_keeps_legacy_when_stable_version_is_wrong'
    ),
    'tests/test_my_spec.py::test_packed_myspec_claude_init_retries_incomplete_legacy_uninstall': (
        'covers packaged Claude cleanup detecting incomplete uninstall and converging on retry; function=test_packed_myspec_claude_init_retries_incomplete_legacy_uninstall'
    ),
    'tests/test_my_spec.py::test_packed_myspec_claude_init_retries_interrupted_legacy_uninstall': (
        'covers packaged Claude cleanup converging after an interrupted uninstall; function=test_packed_myspec_claude_init_retries_interrupted_legacy_uninstall'
    ),
    'tests/test_my_spec.py::test_packed_myspec_codex_init_keeps_legacy_when_stable_version_is_wrong': (
        'covers packaged Codex cleanup preserving legacy state when stable verification fails; function=test_packed_myspec_codex_init_keeps_legacy_when_stable_version_is_wrong'
    ),
    'tests/test_my_spec.py::test_packed_myspec_codex_init_retries_incomplete_legacy_removal': (
        'covers packaged Codex cleanup detecting incomplete removal and converging on retry; function=test_packed_myspec_codex_init_retries_incomplete_legacy_removal'
    ),
    'tests/test_my_spec.py::test_packed_myspec_codex_init_retries_interrupted_legacy_removal': (
        'covers packaged Codex cleanup converging after an interrupted removal; function=test_packed_myspec_codex_init_retries_interrupted_legacy_removal'
    ),
    'tests/test_my_spec.py::test_packed_myspec_init_all_removes_legacy_plugins_and_doctor_reports_stable_sources': (
        'covers packaged all-client cleanup and stable-only diagnosis through public CLI entrypoints; function=test_packed_myspec_init_all_removes_legacy_plugins_and_doctor_reports_stable_sources'
    ),
    'tests/test_my_spec.py::test_packed_myspec_pi_init_enables_a_verified_stable_duplicate_before_cleanup': (
        'covers packaged Pi cleanup selecting a verified stable duplicate before removal; function=test_packed_myspec_pi_init_enables_a_verified_stable_duplicate_before_cleanup'
    ),
    'tests/test_my_spec.py::test_packed_myspec_pi_init_keeps_legacy_source_when_stable_source_is_unresolved': (
        'covers packaged Pi cleanup preserving legacy state when stable resolution fails; function=test_packed_myspec_pi_init_keeps_legacy_source_when_stable_source_is_unresolved'
    ),
    'tests/test_my_spec.py::test_packed_myspec_pi_init_retries_failed_legacy_removal': (
        'covers packaged Pi cleanup converging after a failed removal; function=test_packed_myspec_pi_init_retries_failed_legacy_removal'
    ),
    'tests/test_my_spec.py::test_packed_myspec_pi_init_retries_incomplete_legacy_removal': (
        'covers packaged Pi cleanup detecting incomplete removal and converging on retry; function=test_packed_myspec_pi_init_retries_incomplete_legacy_removal'
    ),
    'tests/test_my_spec.py::test_packed_myspec_claude_reinstall_failure_does_not_report_refreshed': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_claude_reinstall_failure_does_not_report_refreshed'
    ),
    'tests/test_my_spec.py::test_packed_myspec_dev_preflight_rejects_incomplete_source_before_link_or_state': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_dev_preflight_rejects_incomplete_source_before_link_or_state'
    ),
    'tests/test_my_spec.py::test_packed_myspec_removes_only_exact_user_legacy_pi_sources': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_removes_only_exact_user_legacy_pi_sources'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_applies_effective_pi_skill_filters_and_manifest': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_doctor_applies_effective_pi_skill_filters_and_manifest'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_does_not_enable_pi_source_for_unrelated_autoload_delta': (
        'covers packaged Pi diagnosis excluding an unrelated autoload delta from enabled intent; function=test_packed_myspec_doctor_does_not_enable_pi_source_for_unrelated_autoload_delta'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_keeps_enabled_intent_for_missing_pi_source_with_exclusion': (
        'covers packaged Pi diagnosis preserving enabled intent for a registered source with no installed path; function=test_packed_myspec_doctor_keeps_enabled_intent_for_missing_pi_source_with_exclusion'
    ),
    'tests/test_my_spec.py::test_packed_myspec_doctor_keeps_enabled_intent_for_settings_source_missing_from_pi_list': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_doctor_keeps_enabled_intent_for_settings_source_missing_from_pi_list'
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
    'tests/test_my_spec.py::test_packed_myspec_initializes_and_removes_claude_legacy_plugin': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_initializes_and_removes_claude_legacy_plugin'
    ),
    'tests/test_my_spec.py::test_packed_myspec_initializes_and_removes_codex_legacy_plugin': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_initializes_and_removes_codex_legacy_plugin'
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
    'tests/test_my_spec.py::test_packed_myspec_reuses_confirmation_when_implementation_diff_is_unchanged': (
        'covers the installed MySpec CLI reusing confirmation when a development implementation changes without changing the observable diff; function=test_packed_myspec_reuses_confirmation_when_implementation_diff_is_unchanged'
    ),
    'tests/test_my_spec.py::test_packed_myspec_dev_doctor_keeps_published_ancestor_for_unrelated_commit': (
        'covers the installed MySpec CLI retaining a CI-reproducible published ancestor after an unrelated source commit; function=test_packed_myspec_dev_doctor_keeps_published_ancestor_for_unrelated_commit'
    ),
    'tests/test_my_spec.py::test_packed_myspec_dev_doctor_drops_commit_after_closure_branch_removed': (
        'covers the installed MySpec CLI dropping a source commit after its implementation-closure branch is removed remotely; function=test_packed_myspec_dev_doctor_drops_commit_after_closure_branch_removed'
    ),
    'tests/test_my_spec.py::test_packed_myspec_reconfirms_when_in_process_identity_changes_preview': (
        'covers in-process MySpec preview regeneration requiring confirmation when an implementation identity changes the observable diff; function=test_packed_myspec_reconfirms_when_in_process_identity_changes_preview'
    ),
    'tests/test_my_spec.py::test_packed_myspec_dev_binding_allows_cross_worktree_apply_with_target_context': (
        'covers the installed MySpec CLI canonical development binding and target-worktree context through two isolated git worktrees; function=test_packed_myspec_dev_binding_allows_cross_worktree_apply_with_target_context'
    ),
    'tests/test_my_spec.py::test_packed_myspec_update_preflights_installed_clients_before_package_write': (
        'covers the installed MySpec npm package through its public CLI and isolated client boundary; function=test_packed_myspec_update_preflights_installed_clients_before_package_write'
    ),
    'tests/test_my_spec.py::test_packed_myspec_update_blocks_enabled_legacy_sources_before_writes': (
        'covers the installed MySpec update CLI blocking all enabled legacy client sources before package, state, or client writes; function=test_packed_myspec_update_blocks_enabled_legacy_sources_before_writes'
    ),
    'tests/test_my_spec.py::test_packed_myspec_update_preserves_pi_effective_state_under_project_override': (
        'covers packaged update and doctor preserving Pi effective state under a trusted project override; function=test_packed_myspec_update_preserves_pi_effective_state_under_project_override'
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


def format_allowlist_mismatches(
    stale_entries: list[str], missing_hits: list[RuntimeHit]
) -> str:
    sections: list[str] = []
    if stale_entries:
        sections.append("stale allowlist entries:\n" + "\n".join(stale_entries))
    if missing_hits:
        sections.append(
            "missing allowlist entries:\n" + "\n".join(format_hit(hit) for hit in missing_hits)
        )
    return "\n\n".join(sections)


def test_allowlist_mismatch_reports_stale_and_missing_entries() -> None:
    message = format_allowlist_mismatches(
        ["tests/test_removed.py::test_removed"],
        [
            RuntimeHit(
                "tests/test_added.py::test_added",
                "subprocess",
                1,
                "subprocess.run",
            )
        ],
    )

    assert "stale allowlist entries:" in message
    assert "tests/test_removed.py::test_removed" in message
    assert "missing allowlist entries:" in message
    assert "tests/test_added.py::test_added:1:" in message


def test_e2e_allowlist_entries_match_current_runtime_hits() -> None:
    hits = scan_repository_tests()
    hit_identities = {hit.identity for hit in hits}
    stale_entries = sorted(set(E2E_ALLOWLIST) - hit_identities)
    missing_hits = [hit for hit in hits if hit.identity not in E2E_ALLOWLIST]

    assert not stale_entries and not missing_hits, format_allowlist_mismatches(
        stale_entries, missing_hits
    )


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
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_directory_hash_uses_git_visible_files",
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_glob_inputs_track_visible_matching_files",
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_runner_glob_inputs_ignore_ignored_files_and_normalize_separators",
        "tests/test_build_and_verify_plugin.py::test_build_and_verify_cli_baseline_uses_verification_worktree_and_explicit_range",
    ]
    assert init_entries == []
    assert fast_verify_entries == []
