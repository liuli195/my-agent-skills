## Why

PR Flow cleanup（拉取请求流程清理）为支持并行 worktree（工作树），改为在最新远端目标提交上保留 detached HEAD（分离头），但同时移除了本地 base branch（目标分支）的同步，导致清理成功后本地主干仍可能落后远端主干。这违背了 cleanup（清理）应同时完成工作树安全收尾和本地目标分支同步的既有要求。

## What Changes

- cleanup（清理）继续把当前工作树定位到最新远端目标提交的 detached HEAD（分离头）。
- cleanup（清理）同时将未被其他工作树占用的本地 base branch（目标分支）安全快进到同一提交。
- 本地目标分支无法安全快进或正被其他工作树占用且尚未同步时，cleanup（清理）必须停止并给出恢复信息，不得报告完成。
- 增加回归测试，锁定分离头、本地目标分支和远端目标分支三者一致的成功条件。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `pr-flow-plugin`：恢复 cleanup（清理）同步本地目标分支的要求，同时保留并行工作树所需的分离头行为和安全拒绝条件。

## Impact

- `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- `plugins/pr-flow/skills/pr-flow-cleanup/SKILL.md`
- `tests/test_pr_flow_cli.py`
- `openspec/specs/pr-flow-plugin/spec.md` 的 cleanup（清理）验收场景

不新增依赖、配置、命令或公开接口。
