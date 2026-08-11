# Implementation and Verification（实施与验证）

Load this reference only after `Gate 1 — Start Development（开始开发）` is confirmed.

## Preconditions（前置条件）

- Recheck the exact current worktree, branch, clean state, and fixed verification baseline. The worktree must be registered and the branch must still be the same named non-`main` feature branch. Any main branch, detached state, unprovable directory, or changed branch/worktree stops before a write.
- Before each decision to delegate, read and use `subagent-policy`; validate its effective configuration once per session and select only its exact host-native role. Pi uses Policy-validated Agent dispatch. This flow does not use a Pi-specific dispatch extension. Claude and Codex stop before delegation because their host adapters are not provided here.
- The Implementer is the only writer. Dispatch at most one Implementer at a time, wait for its return and inspect actual evidence before the next writable call. The main Agent（代理） and Reviewer（审查者） do not write Git-visible implementation files; a review fix returns to the same serial Implementer path. Read-only Explorer or Reviewer work may be parallel only while the worktree and branch are stable.

## Red→Green（红灯到绿灯）

For every feature, bug, or integration slice, use `tdd` at the agreed public seam:

1. Write and run the smallest failing check for the observable behavior.
2. Make the minimum implementation change through the Implementer.
3. Rerun the check green, then continue to the next vertical slice.

Use the smallest relevant check for behavior-neutral documentation. Do not replace a failing public check with an implementation-only assertion. Keep the approved ticket immutable; a changed observable requirement returns to the requirements route.

## Evidence route（证据路径）

1. Give the Implementer one self-contained goal, the approved acceptance, public seam, fixed baseline, required checks, smoke path, expected clean Git state, and stop conditions. Its actual role, model, thinking level, capabilities, prompt mode, prompt, current worktree, and branch must be observable before acceptance.
2. Inspect the returned worktree rather than trusting the report: verify the focused diff and commit are after the fixed baseline, ownership is limited to the ticket, the assigned worktree is clean, and the main worktree is unchanged.
3. Read and use `build-and-verify` as the only formal verification entry. Run `build-and-verify verify --project <current-worktree> --base <fixed-baseline>` and accept only `status: passed` with a non-empty `checked` result. A skipped or empty result is not evidence of a pass.
4. Run the real Pi Skill（技能） entry smoke through the changed main path, including the valid feature-branch path and the zero-write stop paths for `main`, detached state, unproven worktree, and policy mismatch. Save raw sanitized events, output, exit code, and Git before/after state outside the ticket. Internal tests do not replace this smoke.
5. Use `code-review` at the fixed baseline, limited to the actual diff and necessary context. A Reviewer reports findings only. Rework blocking findings through a new serial Implementer call, rerun the affected check and smoke, and review the fix diff.

## Completion（完成标准）

Implementation is accepted only when the exact worktree and branch remain correct, the focused commit and clean diff contain only the approved ticket, every required red→green check passes, the fixed-baseline Build and Verify result is `passed` with non-empty `checked`, the real Pi entry smoke passes, and the bounded review has no unresolved blocker. Then load [delivery](delivery.md) for the single `Gate 2 — Specification and Delivery（规格与交付）` confirmation.

The first confirmation remains valid during all implementation and verification recovery. Do not ask for `开始开发` again after a failed check or review; resume the failed action and preserve its evidence.
