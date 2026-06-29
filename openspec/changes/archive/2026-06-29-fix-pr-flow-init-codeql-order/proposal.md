## Why

PR Flow init（拉取请求流程初始化）先询问 PR status checks（拉取请求状态检查），再询问 CodeQL security check（CodeQL 安全检查），容易把 `Analyze Python`、`CodeQL` status check（状态检查）和 `Require code scanning results`（要求代码扫描结果）混在一起。

## What Changes

- 调整问答顺序：先确认 CodeQL security check（CodeQL 安全检查），再确认 PR status checks（拉取请求状态检查）。
- 关闭 CodeQL security check（CodeQL 安全检查）时，不再提示选择 `Analyze Python`。
- 开启 CodeQL security check（CodeQL 安全检查）时，PR status checks（拉取请求状态检查）默认只推荐非安全扫描门禁；`Analyze Python` 只作为额外要求 CodeQL analysis workflow job（CodeQL 分析工作流任务）成功的高级选项。
- 当前仓库远端配置保持 CodeQL code scanning（CodeQL 代码扫描）开启，但 required status checks（必需状态检查）只保留 `Full Verify`。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `pr-flow-plugin`: PR Flow init（拉取请求流程初始化）的 CodeQL（代码扫描工具）和 PR status checks（拉取请求状态检查）问答顺序与选择规则。

## Impact

- `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`
- `tests/test_pr_flow_cli.py`
- `.pr-flow/config.yaml`
- GitHub Rulesets（GitHub 规则集）远端配置
