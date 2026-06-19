## 1. Integration Profile

- [ ] 1.1 Add a Comet agent review gate Guard Profile sample or template.
- [ ] 1.2 Configure the profile to use Gate Binding with `gate_id: before_verify`.
- [ ] 1.3 Configure the profile to validate `review-pass.json` with JSON artifact checks.

## 2. Reviewed Flow

- [ ] 2.1 Add wrapper entrypoint or documented command flow for `build -> review -> gate -> verify`.
- [ ] 2.2 Compute the gate subject key from repo identity, Comet change id, and current HEAD.
- [ ] 2.3 Run cross-agent review after build and before verify.
- [ ] 2.4 Submit gate completion only after review pass marker generation.
- [ ] 2.5 Start `/comet-verify` only after Agent Guard gate completion passes.

## 3. Failure and Regression Coverage

- [ ] 3.1 Test review fail prevents verify.
- [ ] 3.2 Test missing `review-pass.json` prevents verify.
- [ ] 3.3 Test stale `head_ref` prevents verify.
- [ ] 3.4 Test review pass allows verify handoff without changing Comet phase semantics.
- [ ] 3.5 Run integration tests and the full repository test suite.
