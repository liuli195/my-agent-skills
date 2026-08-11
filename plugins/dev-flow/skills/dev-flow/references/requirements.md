# Requirements（需求）

Load this reference only for the requirements route and `Gate 1 — Start Development（开始开发）`.

## Preconditions（前置条件）

- Prove the current repository root, registered worktree, named non-`main` feature branch, and clean starting state with read-only Git inspection; failure stops before any write, writable dispatch, or formal confirmation. Keep this worktree and branch unchanged through development and verification under the parent Global invariants（全局不变量）.
- If any Skill（技能）required by the current stage is missing or unreadable, stop.
- Before the first delegation, apply `subagent-policy`; its role, host, and adapter validation are authoritative and are not duplicated here.
- Keep this route read-only until the first confirmation; do not create or switch a worktree or branch or publish a requirement change while confirmation is pending.

## Route（路由）

1. For the overall design, use `codebase-design` through a read-only `Architect` selected by the validated policy. Require source locations, uncertainties, the observable result, scope, and the highest public test seam. Accept the result only after checking its evidence; an incomplete, unsupported, or unverifiable result stops the flow.
2. After the evidence-backed direction is clear, use `grill-with-docs` for unresolved decisions and `domain-modeling` for the confirmed domain terms. Keep one decision at a time and return to the overall design if scope, seam, or risk changes.
3. Use `to-spec` to fix the observable contract and highest public seam, then `to-tickets` to split it into independently observable vertical tickets with a runnable check and genuine blockers. Do not replace these Skills（技能） with an informal checklist.
4. Record the fixed verification baseline, the current worktree and branch, ticket order, single-writer plan, and any genuine blocking edge. Read-only investigation can be parallel only while the starting state remains stable.

## Gate 1 completion（门禁一完成标准）

The result is ready only when the domain terms, observable scope, public test seam, vertical tickets, fixed baseline, worktree, branch, and blockers are explicit and supported by evidence. Present `Gate 1 — Start Development（开始开发）` with the two output blocks from the parent Skill（技能） and request exactly `开始开发`.

After confirmation, follow the parent Skill（技能）'s sticky-confirmation recovery rule; a changed requirement or seam is a blocker that returns to this route, not permission to silently broaden the ticket.
