## Why

PR Flow（拉取请求流程）和 Release Flow（发布流程）已经能识别部分可恢复状态，但真实运行中仍会把已知恢复路径暴露成零散错误或 `EXCEPTION_REQUIRED`（需要异常处理）。同时，远端治理配置和 authorization phrase（授权短语）的人工确认边界需要在 Skill（技能）入口明确禁止越界。

## What Changes

- 将 PR Flow（拉取请求流程）已知可恢复原因收敛到一张恢复矩阵，防止遗漏 `nextAction`（下一步动作）或 `nextCommand`（下一步命令）。
- 让 PR（拉取请求）刚创建后 `gh pr view`（查看拉取请求）短暂不可用时输出可恢复 stop state（停止状态），而不是 `EXCEPTION_REQUIRED`（需要异常处理）。
- 让 Release Flow（发布流程）preflight（发布前检查）在多条错误同时出现时输出一条汇总后的当前状态和处理路径，但不推断最新版本号或下一版本号。
- 在相关 Skill（技能）入口加入最小禁止规则：未获当前确认不得修改 GitHub（代码托管平台）远端治理配置；authorization phrase（授权短语）不得从 memory（记忆）或历史材料中读取复用。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-flow-plugin`: 完善可恢复 PR（拉取请求）查看失败、恢复动作矩阵、远端治理确认边界和 authorization phrase（授权短语）来源边界。
- `release-flow-plugin`: 完善 preflight（发布前检查）多错误汇总输出，保持版本号由用户和 agent（代理）决定。

## Impact

- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- `plugins/pr-flow/skills/pr-flow-hotfix/SKILL.md`
- `plugins/pr-flow/skills/pr-flow-init/SKILL.md`
- `plugins/release-flow/skills/release-flow/SKILL.md`
- PR Flow（拉取请求流程）和 Release Flow（发布流程）相关测试
