# Comet Spec Context

- Change: add-build-verify-performance-reporting
- Phase: design
- Mode: beta
- Context hash: 634327d7954afb32d10efc79f027d86bef9db065ee4e34443a63f6bd0d0d2a8f

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This beta context pack verbatim-projects spec files and references supporting artifacts by hash, not an agent-authored summary.

## Source References

- Source: openspec/changes/add-build-verify-performance-reporting/proposal.md
- SHA256: c363e0ac134e66de8175c90a65865c4bacebf2aa22e154078f1944ba9f977470
- Source: openspec/changes/add-build-verify-performance-reporting/design.md
- SHA256: a25b2c40da4ff8c6d850a39a7dafb7c14d8c5b00b4023be56a49789e4e9bf149
- Source: openspec/changes/add-build-verify-performance-reporting/tasks.md
- SHA256: 8fff0eefa977c5f586c8bd2ba0d675af5dc294993ef7cc14042522840eaae3a9
- Source: openspec/changes/add-build-verify-performance-reporting/specs/test-framework-plugin/spec.md
- SHA256: dc219026398b708ea5866c1ee76ba29c4f7694f99eb75fc3bedff0258f4b8c50

## Acceptance Projection

## openspec/changes/add-build-verify-performance-reporting/specs/test-framework-plugin/spec.md

- Source: openspec/changes/add-build-verify-performance-reporting/specs/test-framework-plugin/spec.md
- Lines: 1-81
- SHA256: dc219026398b708ea5866c1ee76ba29c4f7694f99eb75fc3bedff0258f4b8c50

```md
## ADDED Requirements

### Requirement: Full verify provides non-blocking total performance warnings
Build and Verify（构建与验证） MUST allow a target repository to declare an optional positive integer `verify.fullBudgetSeconds`（完整验证预算秒数） for full verification wall time, and the performance result MUST NOT replace or change functional verification status.

#### Scenario: Full verify finishes before budget
- **WHEN** a user runs `verify --full`（完整验证） with a valid `verify.fullBudgetSeconds`
- **AND** all configured checks finish within that budget
- **THEN** the system MUST complete all configured checks
- **THEN** the system MUST NOT output `performance-warning`（性能警告）
- **THEN** the exit status MUST remain determined by functional verification results

#### Scenario: Full verify exceeds budget
- **WHEN** a user runs `verify --full`（完整验证） with a valid `verify.fullBudgetSeconds`
- **AND** total full verification wall time exceeds that budget
- **THEN** the system MUST complete all configured checks before evaluating the budget result
- **THEN** the system MUST output `performance-warning`（性能警告） with total time, budget, exceeded time, and exceeded percentage
- **THEN** the performance warning MUST NOT change the exit status determined by functional verification results

#### Scenario: Functional failure remains authoritative
- **WHEN** one or more configured checks fail during full verification
- **THEN** the system MUST report functional verification failure using its existing exit status
- **THEN** an under-budget or over-budget result MUST NOT replace that functional result

#### Scenario: Invalid full budget is rejected
- **WHEN** `.build-and-verify/config.json` declares `verify.fullBudgetSeconds`
- **AND** the value is not a positive integer
- **THEN** configuration validation MUST fail before configured checks run
- **THEN** the system MUST report the invalid field

### Requirement: Full verify records a fixed performance report on demand or over budget
Build and Verify（构建与验证） MUST support `verify --full --performance-report`（完整验证性能报告） and MUST conditionally record one fixed-format report without coupling to repository business test output.

#### Scenario: Explicit report is written within budget
- **WHEN** a user runs `verify --full --performance-report`
- **AND** full verification does not exceed its configured budget or has no configured budget
- **THEN** the system MUST write `.build-and-verify/runs/performance-report.json`
- **THEN** the exit status MUST remain determined by functional verification results

#### Scenario: Over-budget run writes report automatically
- **WHEN** full verification exceeds `verify.fullBudgetSeconds`
- **THEN** the system MUST write `.build-and-verify/runs/performance-report.json` whether or not `--performance-report` was provided
- **THEN** the system MUST output the report path

#### Scenario: Unrequested under-budget run leaves no current report
- **WHEN** full verification does not exceed its configured budget or has no configured budget
- **AND** `--performance-report` was not provided
- **THEN** the system MUST NOT create a report for that run
- **THEN** the system MUST remove an existing fixed report so it cannot be mistaken for the current run

#### Scenario: Report schema is stable
- **WHEN** the system writes the performance report
- **THEN** the report MUST contain `schemaVersion`, `mode`, `runtimeVersion`, `startedAt`, `finishedAt`, `totalSeconds`, `budgetSeconds`, `overBudget`, `verificationStatus`, `checks`, and `slowestChecks`
- **THEN** `mode` MUST be `full`
- **THEN** `budgetSeconds` and `overBudget` MUST be `null` when no budget is configured
- **THEN** `checks` MUST record every configured check in configuration order with its id, status, and duration
- **THEN** `slowestChecks` MUST contain at most five checks ordered by descending duration

#### Scenario: Report failure does not block verification
- **WHEN** the performance report cannot be written or a stale fixed report cannot be removed
- **THEN** the system MUST output `performance-report-warning`（性能报告警告）
- **THEN** the report failure MUST NOT change the exit status determined by functional verification results

#### Scenario: Performance report requires full mode
- **WHEN** a user provides `--performance-report` without `--full`
- **THEN** argument validation MUST fail before configured checks run
- **THEN** the system MUST explain that performance reporting requires full verification

### Requirement: Guided initialization supports optional full verification budget
Build and Verify Init（构建与验证初始化） MUST allow a user to opt into the generic full verification budget without supplying a repository-specific default.

#### Scenario: User enables full verification budget
- **WHEN** a user chooses to configure a full verification budget during guided initialization
- **THEN** the questionnaire MUST explain that exceeding the budget only warns and records a report
- **THEN** the generated config MUST contain the user-confirmed positive integer `verify.fullBudgetSeconds`
- **THEN** the final confirmation summary and post-write validation MUST show the configured value

#### Scenario: User leaves full verification budget disabled
- **WHEN** a user does not choose a full verification budget during guided initialization
- **THEN** the generated config MUST omit `verify.fullBudgetSeconds`
- **THEN** the plugin template MUST NOT impose a repository-specific performance target

```

Full source files remain canonical. If a required heading or scenario is missing here, regenerate the handoff or read the source spec directly. Supporting files (proposal, design, tasks) are referenced by hash only.