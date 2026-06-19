## 1. Review Contract

- [ ] 1.1 Define the review input package schema.
- [ ] 1.2 Define the reviewer result schema with severity, location, summary, evidence, and recommendation fields.
- [ ] 1.3 Define the final report format and `review-pass.json` format.

## 2. Review Execution

- [ ] 2.1 Add tests for missing required input fields.
- [ ] 2.2 Add tests for no findings, non-blocking findings, and blocking findings.
- [ ] 2.3 Implement reviewer role dispatch for spec alignment, implementation correctness, tests and edge cases, and optional risk review.
- [ ] 2.4 Implement aggregation that deduplicates findings and calculates `blocking_findings`.

## 3. Outputs

- [ ] 3.1 Generate a review report for every completed review run.
- [ ] 3.2 Generate `review-pass.json` only when `blocking_findings` is 0.
- [ ] 3.3 Include `change`, `base_ref`, `head_ref`, `report`, `report_hash`, and `blocking_findings` in the pass marker.
- [ ] 3.4 Run focused review workflow tests and full repository tests.
