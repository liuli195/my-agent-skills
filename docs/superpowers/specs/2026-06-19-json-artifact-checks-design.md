---
comet_change: add-json-artifact-checks
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-19-add-json-artifact-checks
status: final
---

# JSON Artifact Checks Design

## Context

Agent Guard Runtime currently supports Guard Point checks that prove an artifact exists, but not whether a JSON artifact contains acceptable values. This is enough for simple evidence gates, but too weak for review and approval markers where a file can exist while still saying the gate failed.

The OpenSpec delta requires a generic Runtime feature. Runtime must not know about PR Flow, Comet, review pass markers, or any workflow-specific meaning. Guard Profiles own those rules through declarative configuration.

## Technical Approach

Add a new Guard Point check type:

```yaml
checks:
  - id: review_pass_status
    type: json_artifact
    artifact: review_pass
    field: status
    predicate: equals
    value: pass
```

`json_artifact` remains parallel to `artifact_exists`. It reuses the artifact id declared in `artifacts.yaml`, resolves the artifact path with the existing artifact path logic, loads the file as JSON, reads a simple dot-path field, then evaluates a small fixed set of predicates.

Supported first-version predicates:

- `exists`
- `equals`
- `not_equals`
- `number_lte`
- `number_gte`
- `array_none`
- `array_all`

The implementation should keep predicate evaluation in small helper functions near the existing Guard Point evaluation code. `evaluate_guard_point` should stay as the orchestration layer: locate the guard point, iterate checks, dispatch by check type, and return a structured failure when a check fails.

## Validation

`validate_guard_profile.py` should validate `json_artifact` declarations before a profile can be initialized or synchronized.

Validation rules:

- `type` must be one of the supported check types.
- `json_artifact` must reference `artifact` or `artifact_id`.
- Referenced artifact id must exist in `artifacts.yaml`.
- `predicate` must be present and supported.
- Predicates that require `field` must declare it.
- Predicates that compare values must declare `value`.
- Array predicates must declare a child predicate shape for array elements.

Invalid declarations should fail with the existing `ValidationIssue` style, including `category=guard_points` and a precise `field=...` path.

## Failure Shape and Audit

Runtime failures should continue to return `guard_failed`, so existing transition and override behavior stays consistent.

For JSON failures, the failure detail should include enough data to debug the profile or artifact:

```json
{
  "reason": "guard_failed",
  "failure_reason": "json_artifact_check_failed",
  "guard_point_id": "review_pass_valid",
  "check_id": "review_pass_status",
  "json_check": {
    "artifact": "review_pass",
    "field": "status",
    "predicate": "equals",
    "expected": "pass",
    "actual": "fail"
  }
}
```

The audit entry should preserve the same JSON check detail. Invalid JSON should use a distinct reason such as `invalid_json_artifact` while still being reported as a guard failure.

## Testing Strategy

Add validator tests in `tests/test_validate_guard_profile.py`:

- valid `json_artifact` declaration passes
- missing artifact reference fails
- unknown artifact id fails
- missing predicate fails
- unsupported predicate fails

Add runtime tests in `tests/test_agent_guard_runtime_router.py`:

- `exists` passes and fails
- `equals` passes and fails
- `number_lte` and `number_gte` pass and fail
- `array_none` blocks open P0/P1-style findings
- `array_all` requires all elements to contain expected metadata
- invalid JSON fails with audit detail
- existing `artifact_exists` behavior and override behavior remain unchanged

## Risks

The main risk is overbuilding a query language. The first version should avoid JSONPath, JSON Schema, arbitrary expressions, or script hooks. Simple dot paths and a small predicate set are enough for the known gate scenarios and easier to validate safely.

Another risk is weak debugging output. Tests should assert the failure payload and audit include artifact, field, predicate, expected, actual, and failure reason where available.

## Spec Patch

No OpenSpec patch is needed. The current delta spec already covers the agreed behavior.
