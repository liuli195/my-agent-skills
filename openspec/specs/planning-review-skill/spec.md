# planning-review-skill Specification

## Purpose
TBD - created by archiving change add-planning-review-skill. Update Purpose after archive.
## Requirements
### Requirement: Skill 触发和目标

系统 MUST 提供 `planning-review` Skill（技能），用于审查规划产物。

#### Scenario: 审查规划产物

- **WHEN** 用户要求 review（审查）方案、设计、计划、需求、规格、任务、约束、风险、例外或验收标准
- **THEN** agent（代理）MUST 使用 `planning-review` Skill（技能）
- **AND** 审查重点 MUST 是冲突、遗漏、范围漂移和不可验证计划
- **AND** Skill（技能）MUST NOT 运行脚本、安装依赖、修改文件或推进状态

### Requirement: 审查模式

系统 MUST 支持默认收敛模式和显式无尽模式。

#### Scenario: 默认收敛模式

- **WHEN** 用户没有明确要求无尽模式
- **THEN** agent（代理）MUST 使用收敛模式
- **AND** 每次重复 review（审查）MUST 逐步收窄到上一轮阻断问题、相关修改和必要上下文
- **AND** 直到不再发现 `CRITICAL（严重阻断）` 或 `IMPORTANT（重要阻断）`

#### Scenario: 显式无尽模式

- **WHEN** 用户明确要求无尽模式
- **THEN** agent（代理）MUST 每轮都审查完整规划产物集合和必要关联材料
- **AND** 直到不再发现 `CRITICAL（严重阻断）` 或 `IMPORTANT（重要阻断）`

### Requirement: 子代理审查契约

系统 MUST 使用只读 subagent（子代理），并约束身份、范围和输出格式。

#### Scenario: 派发单个 subagent

- **WHEN** agent（代理）启动 review（审查）
- **THEN** 它 MUST 默认派发 1 个 readonly subagent（只读子代理）
- **AND** subagent prompt（子代理提示词）MUST 只包含身份、审查对象、允许读取材料、本轮范围、检查重点、问题级别和输出格式
- **AND** subagent prompt（子代理提示词）MUST NOT 包含模式说明或放行规则
- **AND** subagent prompt（子代理提示词）MUST NOT 内联大 diff（差异）或完整大型文档

### Requirement: 问题级别和放行规则

系统 MUST 使用四级问题分类，其中前两级阻断，后两级放行。

#### Scenario: 阻断问题

- **WHEN** subagent（子代理）返回 `CRITICAL（严重阻断）` 或 `IMPORTANT（重要阻断）`
- **THEN** 主 agent（代理）MUST 要求修复或明确例外
- **AND** MUST 按当前模式重新 review（审查）到无阻断问题

#### Scenario: 放行问题

- **WHEN** subagent（子代理）只返回 `WARNING（警告放行）` 或 `SUGGESTION（建议放行）`
- **THEN** 主 agent（代理）MAY 放行
- **AND** MUST 汇总剩余风险

