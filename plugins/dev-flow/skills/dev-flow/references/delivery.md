# Specification and Delivery（规格与交付）

Load this reference only after implementation, verification, and the fixed-baseline review are accepted.

## Gate 2 — Specification and Delivery（规格与交付）

1. Use the official MySpec route, including `my-spec-add` when a specification change is needed, to prepare the complete formal-specification preview from the verified behavior. Recheck the preview, requirement counts, and exact delivery actions before asking for confirmation. Do not apply a specification difference early.
2. Present the two parent output blocks with the formal-specification summary, verification evidence, known risks, and exact PR actions. Request exactly `规格与交付`; this one confirmation authorizes both specification application and the selected complete PR Flow（拉取请求流程）.
3. After confirmation, recheck the cited state, apply and validate the approved specification through MySpec, then invoke `pr-flow-complete` automatically. Do not ask for a second delivery confirmation. If application or delivery fails, preserve the state and resume the failed action under the same sticky confirmation.
4. Only after this confirmation may complete PR Flow switch branches, merge, synchronize the base, and perform safe non-forced cleanup. Treat every PR Flow stop state as incomplete and resumable, not as final completion.

## Completion Check（完成检查）

Report the actual final state after delivery: specification validity, merged PR, synchronized base, removed branches and worktrees, and temporary artifacts. Completion Check is a report, not a third authorization. If a physical worktree directory remains, report its exact path, reason, and evidence; request separate explicit authorization only for force-cleaning that exact residue.
