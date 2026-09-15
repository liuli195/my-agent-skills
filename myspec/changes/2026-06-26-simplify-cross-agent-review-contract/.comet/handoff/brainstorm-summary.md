# Brainstorm Summary

- Change: simplify-cross-agent-review-contract
- Date: 2026-06-26

## 确认的事实

- `prepared-inputs` remains a hard contract.
- Startup input is simplified to one `review-input.json`.
- `review-input.json` contains `change`, `mode`, `base_ref`, `head_ref`, `spec_file`, `design_file`, and `plan_file`.
- `plan_file` replaces `tasks_file` and points to `docs/superpowers/plans/`.
- `convergence` and `endless` modes both remain.
- `convergence` is enforced by changing `base_ref` and `head_ref` between runs.
- Default reviewers are reduced to `spec-alignment` and `implementation-correctness`.
- `tests-and-edge-cases` and `risk-review` are removed from the default review workflow.
- Default outputs are reduced to `review-report.md` and pass-only `review-pass.json`.
- Prompt, raw response, and input debug artifacts move behind explicit debug mode.
- Input snapshots are not copied by default.

## 确认的技术方案

### 一次性收敛契约和实现

Update the CLI, input loader, reviewer roles, prompt template, output writer, Skill docs, and tests in one coordinated change.

Why: the old fields and outputs are tightly coupled. Keeping both old and new contracts would preserve the noisy path this change is meant to remove.

### 放弃的备选方案：兼容旧 CLI

Add `--input-file` while keeping `--spec-file`, `--design-file`, and `--tasks-file` temporarily.

Tradeoff: smaller migration risk, but more code and tests; old prompt/output behavior remains easier to accidentally use.

### 放弃的备选方案：只加开关

Keep the current script and add switches for two reviewers, simplified output, and no snapshots.

Tradeoff: smallest local edit, but default behavior remains wrong and convergence mode still depends on caller discipline instead of the main contract.

## 推荐取舍

Use the coordinated breaking change. This matches the confirmed requirement to simplify the contract, remove two review modes/roles, and make convergence effective through `base_ref` / `head_ref`.

## 测试策略

- Update CLI tests to build a `prepared-inputs/review-input.json`.
- Add validation tests for missing fields, missing referenced files, invalid mode, invalid base ref, and head mismatch.
- Update role tests to assert exactly two reviewers.
- Update prompt tests to assert prompts reference `review-input.json` and do not inline manifest, changed files, or large context.
- Update output tests to assert default artifacts omit `review-results.json`, `inputs/manifest.json`, `prompts/`, and `raw/`.
- Add debug-mode tests for `debug/review-input.json`, `debug/prompts/<role>.txt`, and `debug/raw/<role>.txt`.

## Spec Patch

Planning review found blocking gaps and the delta spec was patched:

- `--debug` is the explicit debug mode switch.
- Debug artifacts are MUST when `--debug` is enabled and MUST NOT be default output.
- `prepared-inputs` must contain only `review-input.json`.
- Runtime clean-worktree checks may allow only the current `review-input.json` and current output directory.
- Tasks now include `review-pass.json.mode`, caller migration, debug tests, and prepared-inputs extra-file tests.

## 确认状态

- User confirmed using the coordinated breaking change without a compatibility layer for old CLI arguments.
