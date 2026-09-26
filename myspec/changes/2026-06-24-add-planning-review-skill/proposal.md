## Why

规划产物在进入实现前缺少一个轻量但严格的独立审查入口，容易漏掉范围冲突、规则冲突、任务遗漏和不可验证计划。

## What Changes

- 新增 `planning-review` Skill（技能），用于审查规划产物中的冲突、遗漏、范围漂移和不可验证计划。
- 支持默认收敛模式和显式无尽模式。
- 要求通过 1 个只读 subagent（子代理）执行，提示词保持短小，只传身份、审查对象、允许读取材料、本轮范围、检查重点、级别标准和输出格式。
- 固定四级问题分类：`CRITICAL（严重阻断）`、`IMPORTANT（重要阻断）`、`WARNING（警告放行）`、`SUGGESTION（建议放行）`。

## Capabilities

### New Capabilities

- `planning-review-skill`: 定义规划产物审查 Skill（技能）的触发、范围、模式、子代理职责和输出契约。

### Modified Capabilities

- None.

## Impact

- 新增用户级 Skill（技能）目录：`C:\Users\liuli\.agents\skills\planning-review`。
- 不新增脚本，不安装依赖，不绑定任何具体 workflow（工作流）、tool（工具）或 framework（框架）。
