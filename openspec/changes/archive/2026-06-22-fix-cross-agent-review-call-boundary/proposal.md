## Why

`cross-agent-review`（跨代理审查）Skill（技能）当前没有足够强的调用边界说明，agent（代理）可能在 Comet verify（验证）或通用 code review（代码审查）中重复调用它。

本次修复把调用边界写进 Skill 入口文档，降低重复审查和流程误用风险。

## What Changes

- 在 `cross-agent-review` Skill 文档中加入强制调用边界。
- 明确 ONLY ALLOWED 和 STRICTLY FORBIDDEN 场景。
- 增加包级测试，防止发布内容漏掉该边界说明。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `cross-agent-review`: Skill invocation boundary is explicit and limited to approved scenarios.

## Impact

- Affected files: `plugins/cross-agent-review/skills/cross-agent-review/SKILL.md` and package tests.
- No runtime behavior, API, schema, or output contract changes.
