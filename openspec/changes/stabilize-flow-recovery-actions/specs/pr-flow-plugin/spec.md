## ADDED Requirements

### Requirement: Recoverable PR Flow failures expose recovery actions
PR Flow（拉取请求流程） MUST classify known recoverable failures through a shared contract and MUST include a recovery action in stop-state details（停止状态详情）.

#### Scenario: GitHub authentication failure is actionable
- **WHEN** a `gh`（GitHub 命令行） operation fails because authentication is missing, expired, or unauthorized
- **THEN** PR Flow（拉取请求流程） MUST NOT report the failure as a generic `EXCEPTION_REQUIRED`（需要人工处理）
- **THEN** stop-state details（停止状态详情） MUST use a stable reason（原因） for GitHub authentication recovery
- **THEN** stop-state details（停止状态详情） MUST include a `nextAction`（下一步动作） or `nextCommand`（下一条命令） that tells the user how to check or refresh GitHub authentication

#### Scenario: Transient PR view failure remains recoverable
- **WHEN** a read-only `gh pr view`（查看拉取请求） call exhausts bounded retries for a known transient（临时） failure
- **THEN** PR Flow（拉取请求流程） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** stop-state details（停止状态详情） MUST use `gh_pr_view_transient_failed` as reason（原因）
- **THEN** stop-state details（停止状态详情） MUST include retry evidence and a command（命令） to retry the same PR Flow operation

#### Scenario: Pending checks and ruleset blocks preserve next steps
- **WHEN** PR Flow（拉取请求流程） stops because checks（检查） are pending（等待中） or ruleset（规则集） blocks merge（合并）
- **THEN** stop-state details（停止状态详情） MUST include the current reason（原因）
- **THEN** stop-state details（停止状态详情） MUST include a `nextAction`（下一步动作） or `nextCommand`（下一条命令） for waiting and rerunning the lifecycle

#### Scenario: Invalid fixes none gives direct retry guidance
- **WHEN** 用户运行 `complete`（收尾）或 `tweak`（小改）并传入 `--fixes None`
- **THEN** PR Flow（拉取请求流程） MUST stop before auto-push（自动推送）、PR create（创建拉取请求）、sync（同步） or merge（合并）
- **THEN** stop-state details（停止状态详情） MUST identify `None` as invalid `--fixes`（修复问题编号） input
- **THEN** output（输出） MUST tell the user to remove `--fixes` when there is no issue（问题单） to close
