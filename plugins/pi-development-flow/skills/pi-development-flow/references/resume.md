# Resume（恢复）

Resume from existing facts instead of a parallel workflow state file.

1. Read the change spec, tickets, acceptance and behavior evidence, and relevant domain terms.
2. Inspect Git（版本管理） branches, commits, worktrees, dirty state, and in-progress merge or rebase operations.
3. Inspect the active PR（拉取请求） and PR Flow（拉取请求流程） stop state when delivery has started.
4. Identify the first incomplete gate and present the evidence for that classification.
5. Continue from that gate. If a formal entry reports a missing prerequisite, switch to [initialization](initialization.md).

A pause preserves all artifacts and reports the exact change path and next gate. For cancellation, first inventory committed, integrated, dirty, and unknown content; then wait for explicit abandonment authorization. Non-forcibly clean only traceable work that has not entered the base branch. A merged initialization change remains independent from a cancelled business change.
