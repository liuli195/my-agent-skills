# Resume（恢复）

Resume from existing facts instead of a parallel workflow state file.

1. Read the change spec, tickets, acceptance and behavior evidence, and relevant domain terms.
2. Inspect Git（版本管理） branches, commits, worktrees, dirty state, and in-progress merge or rebase operations.
3. Inspect the active PR（拉取请求） and PR Flow（拉取请求流程） stop state when delivery has started.
4. Derive the previous passed gate, the current incomplete gate, and the next gate from evidence rather than a parallel workflow state file. Always report each gate by number and name.
5. Present the evidence for that classification and the current gate's complete confirmation output.
6. Before continuing, read the corresponding stage document and its dependencies. “Continue”, “resume”, or a confirmation from another gate is not authorization for the current gate.
7. Continue only after the current gate receives its required confirmation. If a formal entry reports a missing prerequisite, switch to [initialization](initialization.md), then return to the same named gate.

A pause preserves all artifacts and reports the exact change path, previous passed gate, current gate, and next gate by number and name. For cancellation, first inventory committed, integrated, dirty, and unknown content; then wait for explicit abandonment authorization. Non-forcibly clean only traceable work that has not entered the base branch. A merged initialization change remains independent from a cancelled business change.
