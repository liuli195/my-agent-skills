## MODIFIED Requirements

### Requirement: Complete PR lifecycle
系统 MUST 提供 complete（完整流程），从当前分支创建或同步 PR 到合并后清理。

#### Scenario: Recoverable PR view failure after creation
- **WHEN** `complete`（收尾）成功创建 PR（拉取请求）
- **AND** 随后的 `gh pr view`（查看拉取请求）暂时无法读取同一个 PR（拉取请求）
- **THEN** complete（收尾） MUST NOT output `EXCEPTION_REQUIRED`（需要异常处理）
- **THEN** complete（收尾） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** stop-state details（停止状态详情） MUST use `gh_pr_view_transient_failed` as reason（原因）
- **THEN** stop-state details（停止状态详情） MUST include `transientCategory: post_create_view`（创建后查看分类）
- **THEN** stop-state details（停止状态详情） MUST include a command（命令） to retry the same `complete`（收尾） operation

### Requirement: Recoverable PR Flow failures expose recovery actions
PR Flow（拉取请求流程） MUST classify known recoverable failures through a shared contract and MUST include a recovery action in stop-state details（停止状态详情）.

#### Scenario: Recoverable reasons stay registered
- **WHEN** PR Flow（拉取请求流程） adds or keeps a known recoverable reason（可恢复原因）
- **AND** the reason（原因） is one of `gh_auth_required`, `gh_pr_view_transient_failed`, `checks_pending`, `ruleset_merge_blocking`, `checks_or_review_blocking`, `invalid_fixes`, `pr_missing` or `missing_upstream`
- **THEN** that reason MUST NOT map to `EXCEPTION_REQUIRED`（需要异常处理）
- **THEN** recovery details MUST include `nextAction`（下一步动作） or `nextCommand`（下一步命令）

### Requirement: PR Flow init presents executable GitHub setup guidance
PR Flow init（拉取请求流程初始化）MUST separate local config writes（本地配置写入） from GitHub setup guidance（GitHub 配置建议） and present GitHub guidance as executable manual tasks.

#### Scenario: Remote governance changes require current confirmation
- **WHEN** PR Flow init（拉取请求流程初始化）mentions GitHub Rulesets（GitHub 规则集）、branch protection（分支保护）、workflow variables（工作流变量） or repository settings（仓库设置）
- **THEN** Skill（技能） guidance MUST prohibit modifying those remote settings without explicit confirmation in the current conversation
- **THEN** without confirmation, the Skill（技能） MUST only output remote tasks（远端待办）

### Requirement: Authorization phrase confirmation
系统 MUST 支持仓库共用 authorization phrase，用于替代用户说“我确认”。

#### Scenario: Authorization phrase source boundary
- **WHEN** PR Flow hotfix（拉取请求流程热修复） requires authorization phrase（授权短语）
- **THEN** the Skill（技能） MUST require manual input from the current conversation
- **THEN** the Skill（技能） MUST prohibit reading or reusing authorization phrase（授权短语） from memory（记忆）、history summaries（历史摘要）、logs（日志）、Issue（问题单） or reports（报告）
