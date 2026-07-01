## 1. PR Flow

- [x] 1.1 Add focused tests for invalid `--fixes` values including comma-separated values, `#123`, non-numeric values, values less than or equal to 0, valid repeated `--fixes`, and post-create PR sync EOF retry.
- [x] 1.2 Update `pr_flow.py` so invalid `--fixes` is reported directly with invalid values and a repeated-argument example.
- [x] 1.3 Update PR Flow help text or command description so agents can discover the correct repeated `--fixes` form.

## 2. Release Flow

- [x] 2.1 Replace the existing `publish --dry-run` test with a rejection test and add authorized publish EOF retry success and retry exhaustion tests.
- [x] 2.2 Remove `publish --dry-run` from the publish parser and dry-run branch.
- [x] 2.3 Add a small bounded EOF retry around the `gh workflow run` publish trigger without adding dependencies or a shared framework.
- [x] 2.4 Update Release Flow help and docs so `publish --dry-run` is not advertised, and document migration to `preflight` plus `publish --authorize-publish`.

## 3. Cross-Agent Review

- [x] 3.1 Add tests that `run` and `mark-pass` output copyable paths and the 12-character `head_ref_short`.
- [x] 3.2 Update `cross_agent_review.py` output to print the accepted `review-input.json` path and reused evidence path convention.
- [x] 3.3 Update cross-agent-review docs to define `<head_ref_short>` as the first 12 characters of `head_ref`.

## 4. Verification

- [x] 4.1 Run focused pytest coverage for PR Flow, Release Flow, and cross-agent-review.
- [x] 4.2 Run CLI end-to-end regression from user entrypoints for the affected main flows: PR Flow `complete`, Release Flow `publish`, and cross-agent-review `run` plus `mark-pass`, using local repos and command stubs instead of live GitHub side effects.
- [x] 4.3 Run OpenSpec validation for `fix-governance-flow-recovery-and-help`.
- [x] 4.4 Update task checkboxes and record verification results, including any live GitHub behavior that was intentionally not exercised.
