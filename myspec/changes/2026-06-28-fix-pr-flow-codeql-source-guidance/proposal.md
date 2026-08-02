## Why

`pr-flow-init`（拉取请求流程初始化）文档只要求配置 CodeQL（代码扫描）Rulesets（规则集），没有要求确认扫描结果来源。agent（代理）可能只配置规则，导致 PR（拉取请求）等待不存在的 CodeQL（代码扫描）结果。

## What Changes

- 在 questionnaire（问答模板）、config draft（配置草案）和 validation（校验规则）中补充 CodeQL scan producer（代码扫描结果来源）待办。
- 增加文本回归测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。只修复初始化文档说明，不改变运行配置结构。

## Impact

- `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`
- `plugins/pr-flow/skills/pr-flow-init/references/config-draft.md`
- `plugins/pr-flow/skills/pr-flow-init/references/validation.md`
- `tests/test_pr_flow_cli.py`
