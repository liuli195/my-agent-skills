## Why

`pr-flow-init`（拉取请求流程初始化）最终写入确认仍是旧的 yes/no（是/否）语义，不能表达“先由 agent（代理）完成 GitHub（代码托管平台）远端待办，再写入本地配置”的安全路径。

## What Changes

- 将最终写入确认改为 3 个固定选项：放弃、不写远端只写本地、先完成远端待办再写本地。
- 明确 GitHub（代码托管平台）配置由 agent（代理）执行。
- 明确插件不提供 GitHub（代码托管平台）配置脚本能力。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `pr-flow-plugin`: `pr-flow-init`（拉取请求流程初始化）最终写入确认选项。

## Impact

- 修改 `plugins/pr-flow/skills/pr-flow-init/references/questionnaire.md`（问答模板）。
- 修改 `tests/test_pr_flow_cli.py`（契约测试）。
