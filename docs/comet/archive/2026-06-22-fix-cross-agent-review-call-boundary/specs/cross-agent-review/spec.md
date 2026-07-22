## ADDED Requirements

### Requirement: Skill invocation boundary

系统 MUST 限制 `cross-agent-review`（跨代理审查）Skill（技能）的自动调用场景，避免在验证或通用审查阶段重复运行。

#### Scenario: 允许的调用场景

- **WHEN** 当前流程处于 Comet build completion（构建完成）阶段、PR Flow local review（本地审查）阶段，或用户显式调用 `cross-agent-review`
- **THEN** agent（代理）MAY 调用 `cross-agent-review` Skill

#### Scenario: 禁止的自动调用场景

- **WHEN** 当前流程处于 Comet verify（验证）阶段或通用 code review（代码审查）阶段
- **THEN** agent（代理）MUST NOT 自动调用 `cross-agent-review` Skill
