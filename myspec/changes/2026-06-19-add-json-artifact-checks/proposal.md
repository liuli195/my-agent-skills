## Why

Agent Guard can currently require that an artifact exists, but it cannot declaratively inspect JSON artifact content before allowing a state transition. This leaves review and evidence gates weaker than the profile model requires, because a stale or failing JSON marker can look valid if only its file exists.

## What Changes

- Add generic Guard Point checks for JSON artifact content.
- Allow Guard Profiles to declare field existence, equality, numeric comparison, and collection checks against profile-owned JSON artifacts.
- Make invalid JSON, missing fields, unsupported predicates, and unsupported declarations fail clearly.
- Record failed JSON checks in runtime audit output with artifact, field, predicate, expected value, and actual value where available.
- Keep workflow semantics in Guard Profile configuration; Runtime remains generic.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-guard-core`: Guard Point checks can validate JSON artifact content, not only artifact existence.

## Impact

- Affected runtime: `plugins/agent-guard/scripts/guard_runtime/core.py`
- Affected validation: `plugins/agent-guard/skills/agent-guard/scripts/validate_guard_profile.py`
- Affected tests: Agent Guard runtime and profile validation tests
- No breaking changes to existing `artifact_exists` Guard Point declarations.
