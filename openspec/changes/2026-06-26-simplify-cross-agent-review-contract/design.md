# Design: simplify cross-agent-review contract

## Context

The current workflow has two useful parts:

- A hard caller boundary through `prepared-inputs`.
- Independent reviewer agents that produce structured findings.

The inefficient parts are mostly accidental:

- Review input is split across several command arguments and copied snapshots.
- `tasks_file` points to OpenSpec tasks, but the actual implementation guidance is better represented by a Superpowers plan.
- `convergence mode` is described as prompt/context behavior instead of a concrete range contract.
- Four roles overlap, especially `tests-and-edge-cases` and `risk-review`, so reruns cost more while producing repeated findings.
- Normal output writes debugging material that is only useful when the review infrastructure itself fails.

## Goals

- Keep `prepared-inputs` as a strict contract.
- Make one `review-input.json` the only run input.
- Make `convergence mode` work through explicit `base_ref` / `head_ref` narrowing.
- Reduce default reviewer count from four to two.
- Reduce default output to the artifacts needed by callers.
- Keep enough debug information available when explicitly requested.

## Non-Goals

- Do not add test execution to `cross-agent-review`.
- Do not make `cross-agent-review` replace Comet verify.
- Do not preserve copied input snapshots for reproducibility.
- Do not keep a compatibility layer for the old multi-argument input style unless a concrete caller still requires a short migration window.

## Decisions

### Single Input File

The caller writes:

```json
{
  "change": "add-build-and-verify-init-skill",
  "mode": "convergence",
  "base_ref": "d6a1ca3c11e7648678a68186fe76f4ada92a1342",
  "head_ref": "8a2ccd24234d...",
  "spec_file": "openspec/changes/<change>/specs/<capability>/spec.md",
  "design_file": "docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md",
  "plan_file": "docs/superpowers/plans/YYYY-MM-DD-<topic>.md"
}
```

The script runs as:

```powershell
python scripts/cross_agent_review.py run --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

Debug mode is explicitly enabled with:

```powershell
python scripts/cross_agent_review.py run --input-file .local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json --debug
```

The file location is part of the contract:

```text
.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json
```

`prepared-inputs` is intentionally a one-file directory for review input. It must not contain copied `spec.md`, `design.md`, `tasks.md`, `plan.md`, or `manifest.json` files.

### No Snapshot Copy

The script reads the referenced files directly. It does not copy `spec`, `design`, or `plan` into `inputs/`, and it does not write `inputs/manifest.json` by default.

This intentionally trades low-frequency reproducibility for a smaller and more readable contract.

### Plan File Replaces Tasks File

`plan_file` points to the Superpowers implementation plan. OpenSpec `tasks.md` remains the planning artifact for this change workflow, but it is no longer part of the review input contract.

### Mode Semantics

`convergence` and `endless` remain separate modes.

In `convergence` mode:

- First run uses the implementation baseline as `base_ref` and current committed `HEAD` as `head_ref`.
- Rerun after a blocking finding uses the previous failed review's `head_ref` as the new `base_ref`.
- The repaired committed `HEAD` becomes the new `head_ref`.
- Reviewer agents review only `base_ref...head_ref`, unless evidence shows the fix affects a wider range.

In `endless` mode:

- Every run keeps `base_ref` at the full implementation baseline or caller-provided full baseline.
- `head_ref` is the current committed `HEAD`.
- Review always covers the full range.

### Reviewer Roles

Default roles become:

- `spec-alignment`: checks whether the changed implementation satisfies the declared spec, design, and plan.
- `implementation-correctness`: checks concrete implementation errors, compatibility issues, and state/data flow problems in the current diff.

`tests-and-edge-cases` and `risk-review` are removed from the default workflow and tests.

### Prompt Shape

The prompt contains only stable review rules and references `review-input.json`.

It must not inline full file contents, changed file lists, manifest data, or long command blocks. Reviewer agents read the input file and inspect the repository read-only.

### Outputs

Default output:

- `review-report.md`
- `review-pass.json` only when blocking findings are zero

Debug output, only when enabled:

- `debug/review-input.json`
- `debug/prompts/<role>.txt`
- `debug/raw/<role>.txt`

`review-results.json`, `inputs/manifest.json`, `prompts/<role>.txt`, and `raw/<role>.txt` are no longer default outputs.

`review-pass.json` includes `mode` so downstream gates can distinguish `convergence` and `endless` review evidence.

## Risks

- Existing callers using the old CLI contract will fail until updated.
- Removing two roles reduces review breadth; this is accepted because Comet verify still owns build/test validation and this gate is meant to catch spec and implementation mismatches.
- Debug evidence is less visible by default; debug mode keeps it available for infrastructure failures.
