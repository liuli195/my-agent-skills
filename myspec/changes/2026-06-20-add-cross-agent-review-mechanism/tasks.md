## 1. Review Contract

- [x] 1.1 Define the minimal CLI input contract.
- [x] 1.2 Define the reviewer result schema with severity, location, summary, evidence, and recommendation fields.
- [x] 1.3 Define the final report format and `review-pass.json` format.
- [x] 1.4 Define clean commit subject binding and SDK resolution failure behavior.

## 2. Review Execution

- [x] 2.1 Add tests for missing required input fields.
- [x] 2.2 Add tests for missing input files, dirty worktree, and head ref mismatch.
- [x] 2.3 Implement reviewer role dispatch for spec alignment, implementation correctness, tests and edge cases, and optional risk review.
- [x] 2.4 Add tests for no findings, non-blocking findings, blocking findings, invalid reviewer JSON, and reviewer timeout.
- [x] 2.5 Implement aggregation that deduplicates findings and calculates `blocking_findings`.
- [x] 2.6 Enforce read-only reviewer tool permissions.

## 3. Outputs

- [x] 3.1 Generate a review report for every completed review run.
- [x] 3.2 Generate `review-pass.json` only when `blocking_findings` is 0.
- [x] 3.3 Include `change`, `base_ref`, `head_ref`, `report`, `report_hash`, and `blocking_findings` in the pass marker.
- [x] 3.4 Verify `report_hash`, default output directory, and `--output-dir` override.
- [x] 3.5 Run focused review workflow tests and full repository tests.
