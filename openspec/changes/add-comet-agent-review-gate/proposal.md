## Why

Comet should support a review gate between build and verify without changing its core phase model. The gate must integrate the JSON artifact checks, gate binding, and cross-agent review pass marker while keeping Comet, Agent Guard, and Agent Review decoupled.

## What Changes

- Add a Comet agent-review gate integration that runs after build and before verify.
- Use Gate Binding to bind the `before_verify` gate to a specific Comet change and head revision.
- Use the cross-agent review pass marker as the required gate evidence.
- Use Agent Guard JSON artifact checks to validate the pass marker before allowing verify.
- Add wrapper or documentation for the reviewed flow while leaving the original Comet phase chain unchanged.

## Capabilities

### New Capabilities

- `comet-agent-review-gate`: Defines the integration contract for Comet build-to-verify review gating.

### Modified Capabilities

None.

## Impact

- New or updated Comet-adjacent workflow entrypoint
- New Agent Guard Profile sample for Comet review gating
- Documentation for reviewed Comet flow
- Integration tests covering build complete, review fail, review pass, stale pass marker, and verify handoff
- No changes to Comet `open -> design -> build -> verify -> archive` phase semantics.
