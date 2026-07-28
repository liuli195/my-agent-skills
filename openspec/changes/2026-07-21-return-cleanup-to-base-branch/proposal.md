## Why

PR Flow（拉取请求流程）cleanup（清理）在目标分支未被其他 worktree（工作树）占用时，仍会刻意保留当前工作树的 detached HEAD（分离头）。已合并变更的维护者必须再手动切回目标分支，且无法从完成状态确认本地目标分支已与远端快照一致。

## What Changes

- 当本地目标分支未被其他 worktree（工作树）占用时，cleanup（清理）在安全更新并删除源分支后切回该目标分支，并回读确认当前 `HEAD`、本地目标分支和本次获取的远端目标提交一致。
- 当本地目标分支被其他 worktree（工作树）占用且已等于本次远端目标提交时，cleanup（清理）仍完成源分支清理；当前工作树保留 detached HEAD（分离头），并在完成状态记录无法切回的明确原因。
- 保持现有的安全拒绝：被占用的目标分支落后于远端快照时，在删除任一源分支前停止；不强制删除工作树、不执行 `git pull`（拉取）且不修改其他工作树。
- 更新 cleanup（清理）技能说明与回归测试，覆盖可安全切回、目标分支被占用时的降级结果，以及提交一致性回读。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `pr-flow-plugin`：修改已合并 PR（拉取请求）cleanup（清理）完成后的当前工作树分支状态和占用目标分支时的完成状态契约。

## Impact

- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py` 的 cleanup（清理）收尾逻辑和状态详情。
- `plugins/pr-flow/skills/pr-flow-cleanup/SKILL.md` 的用户入口说明。
- `tests/test_pr_flow_cli.py` 的 Git（版本管理）工作树回归场景。
- `openspec/specs/pr-flow-plugin/spec.md` 的 cleanup（清理）验收场景。
