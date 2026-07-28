# Brainstorm Summary

- Change: optimize-full-verification-runtime
- Date: 2026-06-23

## Confirmed Facts

- Full verification is currently too slow for routine local use: previous evidence recorded about 214 seconds for full verification and about 135 seconds in `tests/test_pr_flow_cli.py`.
- The first target is PR Flow CLI tests because they repeatedly pay for real Git repository setup, clone/push flows, fake `gh` process scripts, and Python CLI startup.
- The change must preserve behavior coverage for PR Flow complete, cleanup, hotfix, tweak, diagnose, review gate, and audit flows.
- At least one true end-to-end PR Flow path must keep real Git state.
- The initial design preference is to reduce repeated test overhead before considering a new dependency such as pytest-xdist.
- Small test seams are acceptable when they do not change public PR Flow CLI behavior and when true end-to-end coverage remains.
- The optimization must apply across the whole repository test suite, not only PR Flow tests.
- Both the repo-native optimization layer and the pytest-xdist parallelization layer must apply to all configured test checks where safe.
- Repository test writing patterns should be captured, but not under `docs/rules/`.

## 确认的技术方案

- Apply a two-layer optimization to the whole repository test suite, not only `tests/test_pr_flow_cli.py`.
- Layer 1 is repo-native test optimization: reduce repeated Git setup, use shared immutable fixtures/templates, replace fake executable scripts with reusable stubs where process behavior is not under test, and use in-process calls for non-CLI behavior checks.
- Layer 2 is suite-wide parallel execution: coordinate parallel full verification through the Test Framework runner so all configured verify checks can benefit where safe.
- Keep required end-to-end coverage for user-facing workflow paths, especially PR Flow, Release Flow, Agent Guard, cross-agent-review, and Test Framework contracts.
- Do not modify `docs/rules/`. Test-writing guidance for this change stays in OpenSpec artifacts unless the user later confirms another location.

## Broader Alternatives Considered

- Measurement-first: keep using pytest duration reports and grouped timing before each optimization.
- Shared fixture: create a session-level repository template and copy it per test to avoid repeated setup.
- Git-native reuse: consider linked worktrees, local reference clones, or shared bare repositories for tests that must keep real Git state.
- In-process execution: import PR Flow module and call runner functions directly for branch and stop-state tests.
- Command seam: allow tests to inject `git` and `gh` command results while keeping public CLI behavior unchanged.
- Fake command consolidation: replace per-test fake `gh` executable files with a reusable recorder or in-process stub when process behavior is not under test.
- Test layering: keep a small real end-to-end set and convert most matrix branches to faster contract tests.
- Test selection: add markers for local development subsets, but do not use markers to skip required full verification coverage.
- Parallelization: evaluate pytest-xdist only after reducing avoidable serial overhead, because it adds dependency and isolation risk.
- Environment acceleration: RAM disk, antivirus exclusions, or platform changes may help locally but are not repo-native and should not be the primary design.
- Scope reduction: deleting coverage or changing full verification into partial verification is rejected by the spec.

## Quantified Signals

- Measured on 2026-06-23 with current available system Python because this repository has no `.venv`:
  - Python CLI help startup: about 0.11 seconds per call.
  - Importing PR Flow module in-process: about 0.002 seconds per import after warmup.
  - `init_complete_project`: about 5.4 seconds per setup.
  - `init_cleanup_project`: about 3.6 seconds per setup.
  - `init_hotfix_project`: about 2.2 seconds per setup.
  - fake `gh` process call: about 1.28 seconds per call.
- Current `tests/test_pr_flow_cli.py` contains 58 tests:
  - complete: 17 tests.
  - tweak: 4 tests.
  - hotfix: 15 tests.
  - cleanup: 7 tests.
  - diagnose: 9 tests.
- Helper call counts in the file:
  - `init_complete_project`: 16 calls.
  - `init_cleanup_project`: 7 calls.
  - `init_hotfix_project`: 12 calls.
  - `run`: 43 calls.
  - `run_with_path`: 34 calls.
  - `write_fake_gh_sequence`: 21 calls.
- Expected first-version efficiency order:
  1. Reduce repeated Git setup and clone/push flows: largest likely gain, roughly 70-100 seconds if most branch-matrix tests move off fresh real repositories while keeping a small real end-to-end set.
  2. Replace fake `gh` process scripts with in-process stubs where process behavior is not under test: likely 25-50 seconds depending command count.
  3. Avoid Python CLI startup for non-CLI behavior tests: likely 3-6 seconds only, useful but not enough by itself.
  4. Shared Git fixture/template only: likely 25-60 seconds, but may not hit the 60-second full-suite target alone.
  5. pytest-xdist parallelization: potentially large wall-clock gain but dependency and isolation risk, best held as second-stage fallback.

## Pending Confirmation

- User confirmed doing strategies 1-5:
  1. Reduce repeated real Git setup.
  2. Replace fake `gh` process scripts where process behavior is not under test.
  3. Use in-process calls for non-CLI behavior tests.
  4. Add shared Git fixtures/templates.
  5. Add/evaluate pytest-xdist parallelization after serial isolation is safe.
- User added that layers 1 and 2 must both apply to all tests, and that repository testing style/rules must be codified.
- User clarified that `docs/rules/` must not be modified and testing rules must not be stored there.
- User confirmed continuing with this design.

## 关键取舍与风险

- The first implementation should remove serial waste before relying on parallelism, otherwise pytest-xdist may amplify fixture isolation problems.
- Parallel execution must not turn full verification into a subset run; unsafe checks remain in the full run but can stay serial.
- In-process and stubbed tests must not replace all real CLI and Git coverage; they only replace repeated branch-matrix overhead.
- Shared fixtures/templates must be immutable or copied per test to avoid state leakage.

## Risks

- In-process tests can miss argument parsing or process environment problems, so at least one real CLI path remains required.
- Shared fixtures can leak state, so reusable Git state must be copied or treated as immutable.

## Test Strategy

- Re-run baseline full verification timing and pytest durations before implementation.
- Measure grouped PR Flow timing after reducing Git setup and fake CLI process costs.
- Add Test Framework-level verification for suite-wide parallel coordination and serial fallback.
- Re-run full verification before completion and record before/after evidence plus remaining largest contributors.

## Spec Patch

- Completed in `openspec/changes/optimize-full-verification-runtime/specs/full-verification-runtime/spec.md`.
- The delta spec now requires suite-wide repo-native optimization, Test Framework-coordinated parallel execution, full coverage preservation, and no changes under `docs/rules/`.
