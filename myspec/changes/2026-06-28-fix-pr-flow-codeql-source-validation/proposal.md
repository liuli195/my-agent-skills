## Why

`pr-flow-init`（拉取请求流程初始化）可以建议配置 `Require code scanning results`（要求代码扫描结果），但 `validate`（校验）没有提示 CodeQL（代码扫描）结果来源缺失，导致 GitHub Rulesets（GitHub 规则集）配置后等待不存在的扫描结果。

## What Changes

- 当配置声明 `setup.github.codeScanning`（代码扫描建议）时，`validate`（校验）检查本地是否存在 CodeQL workflow（代码扫描工作流）。
- 缺少时输出 remote task（远端待办），要求创建或启用 CodeQL（代码扫描）结果来源。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。只补充现有 validate（校验）远端待办。

## Impact

- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- `tests/test_pr_flow_cli.py`
