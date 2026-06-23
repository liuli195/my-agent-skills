## Why

Full verification currently takes about 214 seconds on this machine, with PR Flow CLI tests accounting for about 135 seconds. Full verification should remain meaningful, but the current runtime is too slow for a routine pre-merge or release checkpoint.

## What Changes

- Add a performance target for full repository verification: complete in under 60 seconds on the local development machine.
- Refactor the slowest test areas, starting with PR Flow tests, to reduce repeated real Git repository setup, clone/push cycles, fake `gh` process launches, and full Python process restarts.
- Keep a small number of true end-to-end tests for PR Flow lifecycle coverage while moving most branch-state and stop-state checks to faster in-process or shared-fixture tests.
- Preserve existing behavior coverage for complete, cleanup, hotfix, tweak, diagnose, review gate, and audit flows.

## Capabilities

### New Capabilities
- `full-verification-runtime`: full repository verification has an explicit runtime target and keeps behavioral coverage while reducing test overhead.

### Modified Capabilities

## Impact

- Affects test structure and possibly small testability seams in PR Flow script code.
- May later touch release-flow and agent-guard tests if PR Flow optimization alone is not enough.
- Does not change production PR Flow behavior, release behavior, plugin manifests, or user configuration.
