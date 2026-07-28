## Why

`cross-agent-review`（跨代理审查）需要明确默认收敛模式和显式无尽模式，避免每轮复审范围不一致，也避免把模式误实现为新的脚本参数。

## What Changes

- 在 Skill（技能）说明中补充模式选择，默认收敛模式，用户明确要求时使用无尽模式。
- 在 reviewer prompt（审查提示词）模板中补充简短模式指引。
- 在 `cross-agent-review`（跨代理审查）规格和参考设计文档中记录模式契约。
- 不修改脚本、命令参数、输出目录、测试或运行时行为。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `cross-agent-review`: 明确 review（审查）模式选择契约。

## Impact

- 影响文件限于 `cross-agent-review`（跨代理审查）Skill（技能）说明、reviewer prompt（审查提示词）模板、OpenSpec（开放规格）规格和参考设计文档。
- 不影响 CLI（命令行接口）、SDK dispatch（开发包派发）、pass marker（通过标记）或测试入口。
