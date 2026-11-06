## 1. Contract and Validation

- [x] 1.1 Add validator tests for valid `json_artifact` declarations.
- [x] 1.2 Add validator tests for missing artifact id, unknown artifact id, missing predicate, and unsupported predicate.
- [x] 1.3 Extend `validate_guard_profile.py` to validate `json_artifact` check shape and references.

## 2. Runtime Evaluation

- [x] 2.1 Add runtime tests for `exists`, `equals`, `number_lte`, `number_gte`, `array_none`, and `array_all`.
- [x] 2.2 Add runtime tests for missing field, invalid JSON, missing artifact, and unsupported check cases.
- [x] 2.3 Add JSON artifact path resolution and safe JSON loading helpers in `guard_runtime/core.py`.
- [x] 2.4 Extend Guard Point evaluation to handle `json_artifact` without changing `artifact_exists`.

## 3. Audit and Regression

- [x] 3.1 Include JSON check failure details in runtime audit output.
- [x] 3.2 Run focused Agent Guard runtime and validator tests.
- [x] 3.3 Run full repository test suite before marking the change complete.
