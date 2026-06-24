## Why

Large or sensitive implementation work benefits from independent review perspectives before verification, but the review process should remain separate from Agent Guard and Comet lifecycle semantics. A dedicated cross-agent review mechanism gives the workflow a structured review result without making the guard perform review work.

## What Changes

- Add a cross-agent review mechanism that dispatches focused reviewer agents for spec alignment, implementation correctness, tests and edge cases, and optional risk review.
- Define the review inputs, report format, severity model, pass/fail rules, and machine-readable pass marker.
- Require the review mechanism to produce a report for every run and only produce a pass marker when blocking findings are zero.
- Keep review execution independent from Agent Guard; Agent Guard only consumes the pass marker in later changes.

## Capabilities

### New Capabilities

- `cross-agent-review`: Defines the reusable cross-agent review workflow and its report/pass-marker contract.

### Modified Capabilities

None.

## Impact

- New skill or workflow entrypoint for cross-agent review
- New report and pass marker contract
- Tests for report generation, blocking severity behavior, and pass marker creation
- No changes to Agent Guard Runtime or Comet phase semantics in this change.
