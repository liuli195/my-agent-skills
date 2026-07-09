## MODIFIED Requirements

### Requirement: Diagnose stop states
系统 MUST 提供 diagnose（诊断）入口，用于解释当前 PR Flow 卡点，并输出固定 stop state（停机状态）。

#### Scenario: Feature branch has no PR yet
- **WHEN** diagnose（诊断）runs on a non-base branch（非目标分支）
- **AND** the branch already has upstream（上游分支）
- **AND** `gh pr view`（查看拉取请求） reports no PR（拉取请求）
- **THEN** diagnose（诊断） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** diagnose（诊断） MUST use `pr_missing` as reason（原因）
- **THEN** diagnose（诊断） MUST provide `complete`（收尾） as the next command（下一步命令）

#### Scenario: Feature branch has no upstream yet
- **WHEN** diagnose（诊断）runs on a non-base branch（非目标分支）
- **AND** the branch has no upstream（上游分支）
- **AND** `complete`（收尾） can own safe auto-push（自动推送） handling
- **THEN** diagnose（诊断） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** diagnose（诊断） MUST use `missing_upstream` as reason（原因）
- **THEN** diagnose（诊断） MUST preserve the missing upstream（缺少上游分支） fact in stop-state details（停止状态详情）
- **THEN** stop-state details（停止状态详情） MUST include `branch`（分支） and `baseBranch`（目标分支）
- **THEN** diagnose（诊断） MUST provide `complete`（收尾） as the next command（下一步命令） using the existing PR body（拉取请求正文） next-command format with `--summary` and `--scope`
- **THEN** diagnose（诊断） MUST NOT present manual `git push`（推送） as the only next step
