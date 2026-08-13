# Requirements（需求）

Load this reference only for the requirements route and `Gate 1 — Start Development（开始开发）`.

## Preconditions（前置条件）

- Prove the current repository root, registered worktree, named non-`main` feature branch, and clean starting state with read-only Git inspection; failure stops before any write, writable dispatch, or formal confirmation. Keep this worktree and branch unchanged through development and verification under the parent Global invariants（全局不变量）.
- If any Skill（技能）required by the current stage is missing or unreadable, stop.
- Before the first delegation, apply `subagent-policy`; its role, host, and adapter validation are authoritative and are not duplicated here.
- Keep this route read-only until the first confirmation; do not create or switch a worktree or branch or publish a requirement change while confirmation is pending.

## Flow Level（流程等级）

Record one level and its evidence at Gate 1:

- **Fast（快速）** applies only when the current session has a reproducible failing check, a verified root cause, one existing public test seam that is also the highest real user entry, one vertical slice, and no unresolved requirement or protected risk.
- **Full（完整）** is the default otherwise. It also applies when Fast evidence becomes invalid, scope expands, a second independent slice appears, or the change involves security, permission, data, migration, release, machine state, cross-system, or destructive risk.

Both levels keep the same two confirmations, Red→Green（红灯到绿灯）, fixed-baseline non-empty Build and Verify（构建与验证）, real-entry smoke, and independent review. Flow Level changes only the requirements legwork: Fast reuses its verified current-session evidence; Full uses the complete route below.

## Route（路由）

1. For Full, use `codebase-design` through a read-only `Architect` selected by the validated policy. Require source locations, uncertainties, the observable result, scope, and the highest public test seam. Accept the result only after checking its evidence; an incomplete, unsupported, or unverifiable result stops the flow. For Fast, verify and reuse the evidence required by its definition.
2. Use `grill-with-docs` and `domain-modeling` only for unresolved decisions or domain terms. Keep one decision at a time and return to the overall design if scope, seam, or risk changes.
3. Use `to-spec` to fix the observable contract and highest public seam, then `to-tickets` to split independently observable vertical tickets when the confirmed request is not already one such ticket. Do not manufacture duplicate requirement artifacts.
4. Record the fixed verification baseline, current worktree and branch, Flow Level and evidence, ticket order, and genuine blocking edges. Read-only investigation can be parallel only while the starting state remains stable.

## Gate 1 completion（门禁一完成标准）

The result is ready only when the Flow Level and evidence, domain terms, observable scope, target product, highest real user entry, observable success result, risk-required failure or recovery paths, public test seam, vertical tickets, fixed baseline, worktree, branch, and blockers are explicit and supported by evidence. Present `Gate 1 — Start Development（开始开发）` with the two output blocks from the parent Skill（技能） and request exactly `开始开发`.

After confirmation, follow the parent Skill（技能）'s sticky-confirmation recovery rule; a changed requirement or seam is a blocker that returns to this route, not permission to silently broaden the ticket.
