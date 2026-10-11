# Tasks

## 1. Spec and Skill Contract

- [x] Update `cross-agent-review` Skill docs to describe `prepared-inputs/review-input.json` as the only startup input.
- [x] Document that `prepared-inputs` contains only one review input file: `review-input.json`.
- [x] Replace `tasks_file` wording with `plan_file` and require Superpowers plan references.
- [x] Document `convergence` and `endless` mode through `base_ref` / `head_ref`.

## 2. CLI and Input Loading

- [x] Replace the old required `--spec-file`, `--design-file`, and `--tasks-file` startup path with `--input-file`.
- [x] Validate required `review-input.json` fields and referenced files.
- [x] Reject unexpected extra files in `prepared-inputs`.
- [x] Validate clean worktree, allowing only the current `review-input.json` and current output directory as runtime artifacts.
- [x] Validate `head_ref` and valid `base_ref` before reviewer dispatch.
- [x] Add explicit `--debug` to enable debug artifacts.

## 3. Reviewer Dispatch

- [x] Reduce default reviewers to `spec-alignment` and `implementation-correctness`.
- [x] Remove `tests-and-edge-cases`, `risk-review`, and `--disable-risk-review` behavior.
- [x] Keep reviewer workspaces read-only.

## 4. Prompt and Output

- [x] Simplify reviewer prompt template so it references `review-input.json` instead of inlining large context.
- [x] Stop writing copied input snapshots and `inputs/manifest.json`.
- [x] Stop writing `review-results.json` by default.
- [x] Write `review-report.md` by default and `review-pass.json` only on pass.
- [x] Include `mode` in `review-pass.json`.
- [x] When `--debug` is enabled, write `debug/review-input.json`, `debug/prompts/<role>.txt`, and `debug/raw/<role>.txt`.

## 5. Tests and Verification

- [x] Update CLI tests for the single input file contract.
- [x] Add tests that `prepared-inputs` rejects extra regular files.
- [x] Add tests for `convergence` and `endless` inputs and `review-pass.json.mode`.
- [x] Update role and prompt tests for two reviewers.
- [x] Update output tests for simplified default artifacts and debug artifacts.
- [x] Add tests for clean worktree runtime artifact exceptions.
- [x] Search and update repository callers that invoke old `spec_file` / `design_file` / `tasks_file` arguments.
- [x] Run the repository verification path that covers the cross-agent-review plugin.
