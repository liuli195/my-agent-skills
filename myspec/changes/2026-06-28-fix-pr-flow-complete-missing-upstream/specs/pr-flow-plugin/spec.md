## MODIFIED Requirements

### Requirement: Complete PR lifecycle
系统 MUST 提供 complete（完整流程），从当前分支创建或同步 PR 到合并后清理。

#### Scenario: Complete stops before creating PR without upstream
- **WHEN** complete（收尾）cannot find an existing PR（拉取请求）
- **AND** the current non-base branch（非目标分支） has no upstream（上游分支）
- **THEN** complete（收尾） MUST output `PUSH_REQUIRED`（需要推送）
- **THEN** complete（收尾） MUST provide a `git push -u` next command（下一步命令）
- **THEN** complete（收尾） MUST NOT call `gh pr create`（创建拉取请求）
