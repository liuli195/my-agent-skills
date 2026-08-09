# Resume（恢复）

Resume from existing facts instead of a parallel workflow state file.

1. Read the change spec, tickets, acceptance and behavior evidence, and relevant domain terms.
2. Inspect Git（版本管理） branches, commits, worktrees, dirty state, and in-progress merge or rebase operations.
3. Inspect the active PR（拉取请求） and PR Flow（拉取请求流程） stop state when delivery has started.
4. Derive the previous passed gate, the current incomplete gate, and the next gate from evidence rather than a parallel workflow state file. Also derive whether the same gate was already confirmed from session/evidence; never create a parallel state file. Always report each gate by number and name.
5. Present the evidence for that classification. If unconfirmed, present the current gate's confirmation output and request that confirmation exactly once.
6. If confirmed but an action failed, report the exact failed action and resume that exact action without presenting or requesting the gate again. A separate dangerous action requires its own precise authorization.
7. Before continuing, read the corresponding stage document and its dependencies. “Continue”, “resume”, or a confirmation from another gate is not authorization for an unconfirmed current gate. If a formal entry reports a missing prerequisite, switch to [initialization](initialization.md), then return to the same named gate.

A pause preserves all artifacts and reports the exact change path, previous passed gate, current gate, and next gate by number and name. For cancellation, first inventory committed, integrated, dirty, and unknown content; then wait for explicit abandonment authorization. Non-forcibly clean only traceable work that has not entered the base branch. A merged initialization change remains independent from a cancelled business change.
