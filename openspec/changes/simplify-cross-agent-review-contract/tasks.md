# Tasks

## 1. Spec and Skill Contract

- [ ] Update `cross-agent-review` Skill docs to describe `prepared-inputs/review-input.json` as the only startup input.
- [ ] Document that `prepared-inputs` contains only one review input file: `review-input.json`.
- [ ] Replace `tasks_file` wording with `plan_file` and require Superpowers plan references.
- [ ] Document `convergence` and `endless` mode through `base_ref` / `head_ref`.

## 2. CLI and Input Loading

- [ ] Replace the old required `--spec-file`, `--design-file`, and `--tasks-file` startup path with `--input-file`.
- [ ] Validate required `review-input.json` fields and referenced files.
- [ ] Reject unexpected extra files in `prepared-inputs`.
- [ ] Validate clean worktree, allowing only the current `review-input.json` and current output directory as runtime artifacts.
- [ ] Validate `head_ref` and valid `base_ref` before reviewer dispatch.
- [ ] Add explicit `--debug` to enable debug artifacts.

## 3. Reviewer Dispatch

- [ ] Reduce default reviewers to `spec-alignment` and `implementation-correctness`.
- [ ] Remove `tests-and-edge-cases`, `risk-review`, and `--disable-risk-review` behavior.
- [ ] Keep reviewer workspaces read-only.

## 4. Prompt and Output

- [ ] Simplify reviewer prompt template so it references `review-input.json` instead of inlining large context.
- [ ] Stop writing copied input snapshots and `inputs/manifest.json`.
- [ ] Stop writing `review-results.json` by default.
- [ ] Write `review-report.md` by default and `review-pass.json` only on pass.
- [ ] Include `mode` in `review-pass.json`.
- [ ] When `--debug` is enabled, write `debug/review-input.json`, `debug/prompts/<role>.txt`, and `debug/raw/<role>.txt`.

## 5. Tests and Verification

- [ ] Update CLI tests for the single input file contract.
- [ ] Add tests that `prepared-inputs` rejects extra regular files.
- [ ] Add tests for `convergence` and `endless` inputs and `review-pass.json.mode`.
- [ ] Update role and prompt tests for two reviewers.
- [ ] Update output tests for simplified default artifacts and debug artifacts.
- [ ] Add tests for clean worktree runtime artifact exceptions.
- [ ] Search and update repository callers that invoke old `spec_file` / `design_file` / `tasks_file` arguments.
- [ ] Run the repository verification path that covers the cross-agent-review plugin.
