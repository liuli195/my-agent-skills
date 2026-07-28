## Why

Full verification currently takes about 214 seconds on this machine, with PR Flow CLI tests accounting for about 135 seconds. Full verification should remain meaningful, but the current runtime is too slow for a routine pre-merge or release checkpoint.

## What Changes

- Add a performance target for full repository verification: complete in under 60 seconds on the local development machine.
- Apply repo-native test optimization across the full configured verification suite, starting with PR Flow tests because they are the measured largest contributor.
- Reduce repeated real Git repository setup, clone/push cycles, fake CLI process launches, and full Python process restarts by using shared fixtures, reusable stubs, in-process calls, and narrow test seams when they preserve the behavior under test.
- Keep representative true end-to-end tests for user-facing workflows while moving high-cost branch-state and stop-state matrices to faster tests.
- Add Test Framework coordinated parallel execution for all configured verify checks where safe, with serial fallback for checks that cannot run in parallel.
- Evaluate pytest-xdist before adoption; enable it only after it is available in the project environment or the user explicitly authorizes dependency installation. In this change, the user authorized installing it into the current system `python` environment before xdist worker settings were wired into verify checks.
- Preserve existing behavior coverage for local build contract, PR Flow, Release Flow, Agent Guard, cross-agent-review, and Test Framework flows, and keep `verify.openspec` validation covered and timed.

## Capabilities

### New Capabilities
- `full-verification-runtime`: full repository verification has an explicit runtime target and keeps behavioral coverage while reducing test overhead.

### Modified Capabilities

## Impact

- Affects test structure across slow verification checks and may add small testability seams where needed.
- Affects Test Framework runner behavior for full verification scheduling and timing reports.
- Does not change production PR Flow behavior, release behavior, plugin manifests, user configuration, or files under `docs/rules/`.
