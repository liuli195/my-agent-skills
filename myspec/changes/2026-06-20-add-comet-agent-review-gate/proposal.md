## Why

Comet should support a review gate between build and verify without changing its core phase model. The gate must use Agent Guard Global Command Guard, the Agent Guard artifact registration layer, and the cross-agent review pass marker while keeping Comet, Agent Guard, and Agent Review decoupled.

## What Changes

- Add a user-level Global Command Guard that blocks Comet build completion before the change enters verify.
- Match the build completion boundary at `comet-guard.sh <change> build --apply`.
- Register the cross-agent review pass marker through Agent Guard `artifacts.yaml` and reference it from Global Command Guard.
- Validate the registered `review-pass.json` with JSON predicate checks before allowing build completion.
- Keep cross-agent-review output behavior unchanged: default output remains `.local/cross-agent-review/<change>/<head_ref>/`.
- Update Agent Guard skill entry docs and shared references so global command guard setup, synchronization, deny handling, and troubleshooting are discoverable from the skills.

## Capabilities

### New Capabilities

- `comet-agent-review-gate`: Defines the integration contract for Comet build-to-verify review gating.

### Modified Capabilities

- `agent-guard-plugin-runtime`: Extends Global Command Guard evidence checks to use artifact references from `artifacts.yaml`.
- `agent-guard-skill-entrypoints`: Updates Agent Guard skill entrypoint documentation and references for Global Command Guard.

## Impact

- New user-level Agent Guard Profile sample for Comet review gating
- Global Command Guard support for artifact-registered review evidence, without copying cross-agent-review output to `.local/guard/evidence`
- Agent Guard skill entry documentation for Global Command Guard
- Deny output guidance that exposes reason, next, suggestion, captures, failing guards, and artifact/evidence details without implementing the review flow
- Integration tests covering build completion block, review fail as missing or invalid pass marker, review pass marker allow, stale pass marker, and command pattern variants
- No changes to Comet `open -> design -> build -> verify -> archive` phase semantics.
