# Agent Plugin and Skill Development

This context defines the roles used to delegate work while developing and maintaining the repository's Agent Plugins（代理插件）and Skills（技能）.

## Language

**Subagent role（子代理角色）**:
A named responsibility selected for one delegated task after the main Agent（代理）has decided to delegate.
_Avoid_: Profile, mode

**Explorer（探索者）**:
The Subagent role（子代理角色）that investigates existing information without changing it and returns evidence.
_Avoid_: Scout, researcher

**Implementer（实施者）**:
The Subagent role（子代理角色）that changes code or documentation from confirmed requirements and verifies the result.
_Avoid_: Worker, coder

**Reviewer（审查者）**:
The Subagent role（子代理角色）that independently evaluates code or documentation and reports evidenced findings.
_Avoid_: Auditor, critic

**Development Flow（开发流程）**:
The end-to-end orchestration of one repository development change from requirement confirmation through implementation, PR（拉取请求）delivery, and cleanup.
_Avoid_: Product lifecycle, release flow

**Flow Level（流程等级）**:
The risk-based classification that selects the cost and gates applied within a Development Flow（开发流程）.
_Avoid_: Complexity level, task size
