## ADDED Requirements

### Requirement: Repository checks enforce recoverable stop action contract
Repository-owned checks（仓库检查） MUST guard the recoverable stop-state contract for local plugin scripts.

#### Scenario: Recoverable stop states include recovery details
- **WHEN** repository tests inspect local plugin scripts or their reason（原因） tables
- **THEN** every known recoverable `DISPATCH_REQUIRED`（需要外部进展）, `PUSH_REQUIRED`（需要推送） or `REPLY_OR_FIX_REQUIRED`（需要回复或修复） stop state MUST include `nextAction`（下一步动作） or `nextCommand`（下一条命令）

#### Scenario: Known recoverable reasons do not become generic exceptions
- **WHEN** repository tests cover known recoverable reasons（原因） such as GitHub authentication, transient PR view failure, pending checks, ruleset blocking, and invalid user input
- **THEN** those reasons（原因） MUST NOT be reported only as generic `EXCEPTION_REQUIRED`（需要人工处理）
