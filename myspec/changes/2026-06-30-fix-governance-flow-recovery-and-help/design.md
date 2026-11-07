## Context

This change covers three small governance-flow failures found during real use:

- `PR Flow` already retries transient EOF for read-only `gh pr view`, but the post-create sync path lacks a dedicated regression test.
- `PR Flow` validates invalid `--fixes` values, but reports them through the generic `pr_body_required` stop message.
- `Release Flow` triggers `gh workflow run` directly and still exposes `publish --dry-run`.
- `cross-agent-review` uses `head_ref[:12]` for local paths and guard evidence, but user-facing docs and output do not make that convention explicit.

The repo constraints favor deletion, reuse, and existing CLI behavior over new abstractions.

## Goals / Non-Goals

**Goals:**

- Keep fixes local to the three affected plugin scripts, specs, docs, and focused tests.
- Reuse the existing `PR Flow` bounded EOF retry behavior as the model for `Release Flow` publish.
- Make invalid `--fixes` input obvious in stop output and help text.
- Make `head_ref_short` copyable and documented as the first 12 characters of `head_ref`.
- Remove only `publish --dry-run`; keep other dry-run commands that still serve configuration or install previews.

**Non-Goals:**

- No new dependencies.
- No cross-plugin GitHub CLI framework.
- No retry coverage for every manual `gh issue` command in documentation.
- No changes to `configure-github --dry-run` or other plugin dry-run commands.

## Decisions

1. Keep PR Flow retry code unchanged unless the new post-create sync test exposes a gap.

   The current `gh_pr_view` helper already retries EOF and feeds `find_pr`, `sync_pr`, `diagnose`, and cleanup. A focused test is the cheapest way to lock the intended path without rewriting working code.

2. Add a tiny Release Flow publish retry helper near `run_publish`.

   `release-flow publish` has one failing GitHub boundary: `gh workflow run`. A local helper can retry EOF, preserve stdout/stderr, return success when a retry succeeds, and return the final failure when retries are exhausted. A shared package would be more code and more maintenance than this problem needs.

3. Treat invalid `--fixes` as its own user-facing input error.

   The parser already collects repeated `--fixes` values. The fix is to validate comma-separated values, `#` prefixes, non-numeric values, and values less than or equal to 0 before missing body fields hide the real problem, then print a direct message plus a repeated-argument example.

4. Document the existing 12-character rule instead of changing path math.

   Code, tests, and guard evidence already agree on `head_ref[:12]`. Changing that would migrate paths for no benefit. The useful change is to expose the rule in specs, skill docs, and command output.

5. Delete `publish --dry-run`.

   The preview path duplicates the real workflow command without proving publish success. Authorized publish and existing preflight/configuration previews cover the useful workflow with less surface area.

## Risks / Trade-offs

- Removing `publish --dry-run` may break old scripts that call it. Mitigation: mark it as a breaking removal in the proposal and update tests/docs.
- A local release retry helper duplicates a small part of PR Flow retry logic. Mitigation: keep it tiny and scoped to `gh workflow run`; do not create an abstraction until a second Release Flow GitHub boundary needs it.
- More direct `--fixes` errors change stop reason expectations. Mitigation: update focused tests and keep `invalidFixes` in state details.
- End-to-end regression cannot use live GitHub side effects for merge, release, or workflow dispatch in routine local verification. Mitigation: run plugin CLI entrypoints against local repositories and command stubs, then record live GitHub behavior as not exercised in the verification report.

## Migration Plan

- Users who previously ran `publish --dry-run` should use `preflight` for release validation and `publish --authorize-publish` for the actual workflow trigger.
- No data migration is required.
- Existing cross-agent-review output paths remain valid because the 12-character rule is unchanged.
