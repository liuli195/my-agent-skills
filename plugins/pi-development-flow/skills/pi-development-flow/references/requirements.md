# Requirements（需求）

## Flow Level（流程等级）

Recommend a level from observable risk, then let the user confirm it.

| Level | Use for | Minimum path |
| --- | --- | --- |
| Lightweight | Documentation, wording, formatting, or low-risk configuration with no changed runtime behavior | Short confirmation, relevant check, real smoke only when a user path changed, `pr-flow-tweak` |
| Standard | Features, bugs, and integrations | Requirements, isolated implementation, TDD, bounded overall review, user-entry smoke, `pr-flow-complete` |
| High risk | Security, data migration, release, machine state, or broad public contracts | Deep requirements, risk-specific checks, critical-ticket review, overall review, `pr-flow-complete` |

Security, data integrity, migration, release, and other protected work stays high risk. Missing information defaults to standard. The user may raise any level; lowering a protected level requires changing the scope rather than skipping its controls.

## Discussion route（讨论路径）

Choose by decision scale:

- Use `grill-with-docs` when the destination and boundaries can be resolved in one session.
- Use `wayfinder` when dependent decisions, research, or prototypes require multiple sessions. Its individual discussion tickets still use grilling and domain modeling.
- For an already precise lightweight change, confirm the observable result and test seam without manufacturing an interview.

During discussion, retain confirmed domain terms in the conversation. Publish them with the spec and tickets instead of editing the base checkout mid-discussion.

## Publish one change（发布单项变更）

1. Confirm the highest public test seam through `to-spec`.
2. Use `to-tickets` to draft tracer-bullet vertical slices. Every ticket has an independently observable result, runnable verification, and only genuine blockers.
3. Show the spec and ticket breakdown. After approval, create an ASCII-named change branch in `.worktrees/<change>/`, run the repository worktree initializer, and publish:
   - confirmed terms to the repository domain glossary;
   - the spec to `myspec/changes/<change>/spec.md`;
   - implementation tickets to `myspec/changes/<change>/issues/`.
4. Commit these requirement artifacts before presenting the implementation plan.

For multi-session wayfinding, keep the intermediate map at `myspec/changes/<change>/wayfinder.md` and its decision tickets under `decisions/`. Decision tickets guide the final spec; implementation tickets remain separate.

Completion requires a clean change worktree containing the committed, user-approved requirement artifacts. Stop before implementation authorization.
