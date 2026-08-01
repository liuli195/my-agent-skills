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

**Gate 3 — Enter Delivery（进入交付）**:
The final confirmation in `my-spec-add`（新增自有规格）that authorizes its validated atomic application of the formal MySpec（自有规格）difference; it passes only after that application succeeds.
_Avoid_: Delivery-plan confirmation

**Flow Level（流程等级）**:
The risk-based classification that selects the cost and gates applied within a Development Flow（开发流程）.
_Avoid_: Complexity level, task size

**Future Input（未来输入）**:
A Build and Verify（构建与验证） glob input（通配符输入） that currently matches no files but remains valid so future matching files can invalidate the cache.
_Avoid_: Missing input, invalid glob

**Glob Input（通配符输入）**:
A Build and Verify（构建与验证） cache input pattern that expands to a stable Git-visible file set.
_Avoid_: Literal input, directory input

**Legacy MySpec Source（旧 MySpec 来源）**:
A source record that registers a MySpec（自有规格）plugin from the former shared marketplace or a legacy source path. A shared marketplace registration without an installed MySpec plugin record is not a Legacy MySpec Source.
_Avoid_: Legacy marketplace, duplicate marketplace
