# Implementation and Verification（实施与验证）

Load this reference only after `Gate 1 — Start Development（开始开发）` is confirmed.

## Preconditions（前置条件）

- Recheck the registered current worktree, named non-`main` branch, clean state, and fixed verification baseline before any write; failure stops. Keep the worktree and branch unchanged through this route under the parent Global invariants（全局不变量）.
- Before each delegation, apply `subagent-policy`; its validated host-native role and adapter stop rules are authoritative.
- Apply the parent Global invariants（全局不变量） for the sole-writer/serial-dispatch rule: wait for each Implementer return and inspect actual evidence before the next writable call. Read-only Explorer or Reviewer work may run in parallel only while the worktree and branch are stable.

## Red→Green（红灯到绿灯）

For every feature, bug, or integration slice, use `tdd` at the Gate 1-bound target product's highest real user entry. The Red→Green check, final smoke, and behavior acceptance all use that same entry:

1. Write and run the smallest failing check for the observable behavior.
2. Make the minimum implementation change through the Implementer.
3. Rerun the check green, then continue to the next vertical slice.

Use the smallest relevant check for behavior-neutral documentation. Do not replace a failing public check with an implementation-only assertion. Keep the approved ticket immutable; a changed observable requirement returns to the requirements route.

## Evidence route（证据路径）

1. Give the Implementer one self-contained goal, the approved acceptance, public seam, fixed baseline, required checks, smoke path, expected clean Git state, and stop conditions. Make its validated role contract observable before acceptance; use `subagent-policy` for its fields.
2. Inspect the returned worktree rather than trusting the report: verify the focused diff and commit are after the fixed baseline, ownership is limited to the ticket, the assigned worktree is clean, and the main worktree is unchanged.
3. Read and use `build-and-verify` as the only formal verification entry. Run `build-and-verify verify --project <current-worktree> --base <fixed-baseline>` and accept only `status: passed` with a non-empty `checked` result. A skipped or empty result is not evidence of a pass.
4. Run the final smoke through the same Gate 1-bound real user entry and changed main path, including the valid feature-branch path and the zero-write stop paths for `main`, detached state, unproven worktree, and policy mismatch. Save raw sanitized events, output, exit code, and Git before/after state outside the ticket. Internal tests do not replace this smoke.
5. Use `code-review` at the fixed baseline, limited to the actual diff and necessary context. A Reviewer reports findings only. Rework blocking findings through a new serial Implementer call, rerun the affected check and smoke, and review the fix diff.

## Completion（完成标准）

Implementation is accepted only when the exact worktree and branch remain correct, the focused commit and clean diff contain only the approved ticket, every required red→green check passes, the fixed-baseline Build and Verify result is `passed` with non-empty `checked`, the Gate 1-bound real user entry smoke and behavior acceptance pass, and the bounded review has no unresolved blocker. Then load [delivery](delivery.md) for the single `Gate 2 — Specification and Delivery（规格与交付）` confirmation.

The parent Skill（技能）'s sticky-confirmation recovery rule remains in force; do not ask for `开始开发` again after a failed check or review.
