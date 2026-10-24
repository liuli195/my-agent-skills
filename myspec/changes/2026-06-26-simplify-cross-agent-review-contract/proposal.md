# Change: simplify-cross-agent-review-contract

## Why

Current `cross-agent-review` has too much ceremony for a low-frequency review gate:

- The input contract still mixes old `diff` / `tasks_file` assumptions with newer prepared-inputs behavior.
- Four reviewer agents create duplicated findings and slow each run.
- Default outputs include prompt, raw response, manifest, result JSON, and copied input snapshots, which makes normal review output noisy.
- `convergence mode` exists in wording, but the current contract does not make base/head narrowing the actual control surface.

This change keeps the useful hard boundary, `prepared-inputs`, while reducing the run contract to one input file and two reviewer agents.

## What Changes

- **BREAKING**: Replace multi-file CLI input with one `--input-file` pointing to `prepared-inputs/review-input.json`.
- Keep `prepared-inputs` as the required caller-prepared directory, but store only file references and review scope there.
- Replace `tasks_file` with `plan_file`, pointing to a Superpowers plan under `docs/superpowers/plans/`.
- Make `mode`, `base_ref`, and `head_ref` explicit fields in `review-input.json`.
- Make `convergence mode` effective by narrowing reruns through `base_ref` and `head_ref`.
- Keep both modes: `convergence` and `endless`.
- Remove the `tests-and-edge-cases` and `risk-review` reviewer roles.
- Keep only `spec-alignment` and `implementation-correctness` reviewers by default.
- Simplify default outputs to `review-report.md` and, on pass only, `review-pass.json`.
- Move prompt/raw/input debug artifacts behind an explicit debug mode.
- Stop copying input snapshots into the output directory.

## Capabilities

- Modified capability: `cross-agent-review`

## Impact

- Update `cross-agent-review` Skill docs, prompt template, CLI script, and tests.
- Update callers that still pass separate `spec_file`, `design_file`, or `tasks_file` arguments.
- Existing consumers of `review-results.json`, `inputs/manifest.json`, `prompts/`, or `raw/` must switch to debug mode or the pass/report outputs.
