# Requirements（需求）

Load this reference only for the requirements route and `Gate 1 — Start Development（开始开发）`.

## Preconditions（前置条件）

- Prove the current repository root, registered worktree, named branch, and clean starting state with read-only Git inspection. The branch must be a non-`main` feature branch and the worktree must remain the same for development and verification. A failed precondition stops before any write, writable dispatch, or formal confirmation.
- Before the first delegation, read and use `subagent-policy`. Validate its effective configuration once per session: role, model, thinking level, capabilities, prompt mode, prompt, and host adapter must match. A difference or an unprovable field stops the flow before delegation. Pi uses the policy-validated native Agent mapping; Claude and Codex have no adapter in this delivery, so stop explicitly after discovery and before delegation.
- Keep this route read-only until the first confirmation. Do not create or switch a worktree or branch, and do not publish a requirement change while the confirmation is pending.

## Route（路由）

1. For the overall design, use `codebase-design` through a read-only `Architect` selected by the validated policy. Require source locations, uncertainties, the observable result, scope, and the highest public test seam. Accept the result only after checking its evidence; an incomplete, unsupported, or unverifiable result stops the flow.
2. After the evidence-backed direction is clear, use `grill-with-docs` for unresolved decisions and `domain-modeling` for the confirmed domain terms. Keep one decision at a time and return to the overall design if scope, seam, or risk changes.
3. Use `to-spec` to fix the observable contract and highest public seam, then `to-tickets` to split it into independently observable vertical tickets with a runnable check and genuine blockers. Do not replace these Skills（技能） with an informal checklist.
4. Record the fixed verification baseline, the current worktree and branch, ticket order, single-writer plan, and any genuine blocking edge. Read-only investigation can be parallel only while the starting state remains stable.

## Gate 1 completion（门禁一完成标准）

The result is ready only when the domain terms, observable scope, public test seam, vertical tickets, fixed baseline, worktree, branch, and blockers are explicit and supported by evidence. Present `Gate 1 — Start Development（开始开发）` with the two output blocks from the parent Skill（技能） and request exactly `开始开发`.

Once confirmed, the confirmation is sticky through requirement recovery and permits the confirmed implementation route. If the action fails, preserve the evidence and resume that action without asking for `开始开发` again. A changed requirement or seam is a requirements blocker, not permission to silently broaden the ticket.
