## Why

PR Flow（拉取请求流程）和 Release Flow（发布流程）已经多次修复单个可恢复错误，但错误分类和恢复提示仍分散在不同出口。新增或相邻失败路径容易再次退回模糊的 `EXCEPTION_REQUIRED`（需要人工处理），让用户无法直接恢复。

## What Changes

- 给 PR Flow（拉取请求流程）和 Release Flow（发布流程）的可恢复失败补齐统一恢复动作要求。
- 让 `gh`（GitHub 命令行）鉴权失败、PR（拉取请求）查询瞬时失败、checks（检查）等待、ruleset（规则集）阻塞和无效 `--fixes` 参数都给出明确 `nextAction`（下一步动作）或 `nextCommand`（下一条命令）。
- 给 Release Flow preflight（发布预检）的现有失败输出补充有序下一步提示。
- 增加仓库级防回归检查，防止已知可恢复原因落回普通异常或缺少恢复动作。

## Capabilities

### New Capabilities

- None

### Modified Capabilities

- `pr-flow-plugin`: 可恢复 stop state（停止状态）必须有稳定分类和恢复动作。
- `release-flow-plugin`: preflight（发布预检）失败必须给出可执行下一步。
- `local-plugin-build-checks`: 仓库检查必须守住可恢复错误输出契约。

## Impact

- 影响 PR Flow（拉取请求流程）脚本、Release Flow（发布流程）脚本和相关测试。
- 不新增依赖。
- 不改变 PR（拉取请求）创建、合并或发布权限边界。
