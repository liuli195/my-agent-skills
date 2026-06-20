---
comet_change: add-cross-agent-review-mechanism
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-20-add-cross-agent-review-mechanism
status: final
---

# Cross-Agent Review Design

## Goal

This change adds an independent `cross-agent-review` plugin and skill. It provides a small review runner that dispatches focused reviewer agents, aggregates their findings, and produces a report plus a machine-readable pass marker.

The mechanism stays separate from Comet and Agent Guard. It does not run build or test commands, does not update `.comet.yaml`, and does not advance Comet phases. Later changes may let Agent Guard consume `review-pass.json` before Comet verify, but this change only creates the review mechanism and output contract.

## Scope

The first version is intentionally small:

- One plugin root: `plugins/cross-agent-review`
- One skill: `cross-agent-review`
- One Python runner script
- Fixed reviewer roles
- Claude Agent SDK only
- No CLI fallback
- No runner framework
- No automatic SDK install

The runner accepts explicit CLI arguments for the review subject and context files. It does not introduce a separate input package file.

## Review Subject

Review is bound to a clean Git commit, not to an uncommitted workspace.

The runner must verify all of the following before dispatch, immediately before reviewer execution, and immediately before writing `review-pass.json`:

- `git status --short` is empty.
- `git rev-parse HEAD` equals the provided `head_ref`.

If either check fails, the runner exits without producing `review-pass.json`.

If review finds a blocking issue, the main agent must fix it, commit the fix, and run review again against the new `head_ref`. Uncommitted fixes can be tested locally, but they cannot satisfy review.

## Inputs

The runner uses minimal CLI file inputs:

```text
cross_agent_review.py run \
  --change <change-id> \
  --base-ref <base-ref> \
  --head-ref <head-ref> \
  --diff-file <path> \
  --spec-file <path> \
  --design-file <path> \
  --tasks-file <path> \
  --tests-file <path>
```

`--output-dir` may override the default output directory. `--sdk-python` or an environment variable may point to a Python interpreter that has `claude_agent_sdk` installed.

Required inputs are validated before reviewer dispatch. Missing required parameters or missing files fail fast.

## SDK Resolution

The runner uses Claude Agent SDK as a hard dependency. It must not install packages.

Resolution order:

1. If `--sdk-python` is provided, it must point to a Python interpreter that can import `claude_agent_sdk`; otherwise resolution fails.
2. Current Python can import `claude_agent_sdk`.
3. An environment variable points to a Python interpreter that can import `claude_agent_sdk`.
4. A known Claude SDK venv path exists, such as `~/.claude/security/agent-sdk-venv/Scripts/python.exe`.

If no valid SDK Python is found, the runner reports a clear error and does not dispatch reviewers.

## Reviewer Roles

The runner dispatches fixed reviewer roles:

- `spec-alignment`: checks whether the implementation matches OpenSpec, the design context, and tasks.
- `implementation-correctness`: checks logic, integration behavior, and regression risks.
- `tests-and-edge-cases`: checks whether the supplied test results and coverage are enough for the change.
- `risk-review`: checks security, destructive behavior, release risk, and operational risk.

`risk-review` may be explicitly disabled. When disabled, the report records the role as skipped and includes the reason.

Reviewer agents may inspect the workspace with read-only tools. They must not write files or modify Git state. SDK options should allow only read-only file/search/shell behavior and must not allow write tools such as `Edit` or `Write`.

## Reviewer Result Contract

Each reviewer returns structured JSON:

```json
{
  "role": "spec-alignment",
  "status": "completed",
  "findings": [
    {
      "severity": "IMPORTANT",
      "location": "path/to/file.py:123",
      "summary": "Short finding summary",
      "evidence": "Concrete evidence",
      "recommendation": "Concrete next step"
    }
  ]
}
```

Allowed severities:

- `CRITICAL`
- `IMPORTANT`
- `WARNING`
- `SUGGESTION`

`CRITICAL` and `IMPORTANT` are blocking. `WARNING` and `SUGGESTION` are recorded but do not block pass marker generation.

If a reviewer times out or returns invalid JSON, the aggregator records that role as a `CRITICAL` finding.

## Aggregation

Aggregation stays simple:

- Validate reviewer result shape.
- Normalize severity names.
- Deduplicate exact duplicates by `severity + location + summary`.
- Count blocking findings.
- Write outputs.

The runner does not attempt semantic deduplication in the first version.

## Outputs

Default output directory:

```text
.local/cross-agent-review/<change>/<head_ref>/
```

Each completed run writes:

- `review-report.md`
- `review-results.json`

Only a passing run writes:

- `review-pass.json`

`review-pass.json` contains:

```json
{
  "status": "pass",
  "change": "change-id",
  "base_ref": "base-sha",
  "head_ref": "head-sha",
  "blocking_findings": 0,
  "report": "review-report.md",
  "report_hash": "sha256-of-report"
}
```

The pass marker must not be generated when blocking findings exist, the worktree is dirty, or current `HEAD` no longer matches `head_ref`.

## Comet Boundary

Cross-agent review is review evidence, not Comet verification.

The runner consumes test result files but does not run build or test commands. Comet verify remains responsible for deterministic checks, OpenSpec verification, verification reports, and branch handling.

The repository's `.comet/build-check.sh` is a project-specific quick regression entrypoint. It is not generated by Comet and is not owned by this review mechanism. When this plugin adds tests, the repository verification entrypoint should be updated separately so Comet verify can cover the new tests.

## Test Strategy

Tests should keep implementation minimal while covering the contract thoroughly:

- CLI required arguments and missing files.
- SDK resolution success and SDK missing failure.
- Read-only reviewer tool configuration.
- Dirty worktree and `HEAD != head_ref` rejection at each subject check.
- Reviewer outcomes: no findings, non-blocking findings, blocking findings, timeout, invalid JSON.
- Aggregation and exact deduplication.
- Report and result generation for all completed runs.
- Pass marker generation only for clean passing runs.
- `report_hash` matches `review-report.md`.
- Default output directory and `--output-dir` override.
- Risk review disabled records skipped role and reason.
