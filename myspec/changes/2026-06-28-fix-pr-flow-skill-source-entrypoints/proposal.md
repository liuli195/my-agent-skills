## Why

`pr-flow` Skill（技能）总入口在源码仓库内给出的诊断命令指向不存在的 `scripts/pr_flow.py`，维护者按文档运行会直接失败。

## What Changes

- 修正 `pr-flow` 总入口文档，让源码仓库运行方式指向真实脚本路径。
- 增加文档回归测试，防止总入口再次写成不存在路径。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。只修复 Skill（技能）文档入口，不改变 PR Flow（拉取请求流程）规格行为。

## Impact

- `plugins/pr-flow/skills/pr-flow/SKILL.md`
- `tests/test_pr_flow_cli.py`
