---
name: dev-flow
description: Orchestrate one development change in the same Git worktree and non-main feature branch; use when a change must run through requirements, serial implementation, verification, review, and PR delivery.
---

# Development Flow（开发流程）

This is a pure Skill（技能） route. It depends on `subagent-policy` and composes the repository's existing Skills（技能） instead of copying their procedures.

## Run（运行）

1. Prove the invocation is in a registered Git worktree on a named, non-`main` feature branch. If the branch is `main`, detached, the worktree cannot be proven, or the effective role/model policy cannot be proven, stop before any write, writable dispatch, or formal confirmation.
2. Read [requirements](references/requirements.md) for the requirements route and `Gate 1 — Start Development（开始开发）`.
3. After the first confirmation, read [implementation](references/implementation.md) and complete implementation, verification, and review in the same worktree and branch.
4. When implementation evidence is accepted, read [delivery](references/delivery.md) for `Gate 2 — Specification and Delivery（规格与交付）`, then apply the confirmed specification and run the authorized delivery.
5. Run Completion Check（完成检查） as a final report. It is not a third authorization gate.

## Global invariants（全局不变量）

- There are exactly two formal confirmations: `开始开发` and `规格与交付`.
- A confirmation is sticky through the confirmed action and its failure recovery; resume the failed action without asking for that confirmation again.
- During development and verification, keep the invocation's Git worktree and feature branch unchanged. Do not create or switch a worktree or branch.
- The Implementer is the only writer and writable calls are strictly serial. The main Agent（代理） orchestrates and accepts actual evidence; it does not write Git-visible implementation files. Read-only investigation may run in parallel only while the repository is stable.
- Functional, bug, and integration behavior uses `tdd` red→green. Verification uses `build-and-verify`, requires `status: passed` and non-empty `checked`, and includes a real Pi entry smoke. Review is bounded by the fixed baseline and the actual diff.
- Final delivery may use the complete PR Flow（拉取请求流程）; only that delivery phase may switch branches and perform safe cleanup.
- Claude and Codex may discover this Skill（技能）, but without the host adapter supplied by `subagent-policy` the flow stops explicitly before delegation.

## Output（输出）

Every formal confirmation and every recovery result has exactly these two blocks and no extra output blocks:

### 核心摘要

State the current gate, the observable result, the evidence or blocker, and the exact confirmation when one is required.

### 确认后进入的下一步

State the single next route. A confirmed gate resumes its failed action after recovery; Completion Check only reports final completion or the precise residue.
