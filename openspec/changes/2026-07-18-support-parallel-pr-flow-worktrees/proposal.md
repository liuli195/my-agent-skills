## Why

PR Flow（拉取请求流程）目前按单一工作树运行，状态、基线门禁和清理都无法安全区分并行 worktree（工作树）。多个 PR（拉取请求）同时推进时，流程可能复用过期结果、争用同一分支，或在清理阶段错误切换和删除分支。

## What Changes

- 为每个工作树与源分支建立独立流程上下文和运行状态；每个工作树只使用一把修改锁，diagnose（诊断）只读报告占用，不覆盖运行状态。
- 在分发前读取最新远端目标提交；源分支落后或冲突时停止并给出恢复方式，不自动 rebase（变基）、merge（合并）或解决冲突。
- 在门禁前固定源/目标提交，并在合并前复核；只接受当前提交上非空、完整且成功的 required checks（必需检查）。
- 让 complete（完整流程）与 tweak（小改）共享相同的基线、检查、合并和清理生命周期；tweak（小改）只跳过 review gate（审查门禁）。
- 让 hotfix（热修复）在验证后、推送前再次确认远端目标提交未变化。
- 将 cleanup（清理）后的工作树定位到最新远端目标提交的 detached HEAD（分离头），避免切换已被其他工作树占用的本地目标分支。
- 清理前检查源分支占用；默认保留工作树，只有显式 `--remove-worktree`（删除工作树参数）且满足安全条件时才删除关联工作树。
- 不新增全局锁、配置项、第三方依赖或共享 Runtime（运行时）能力。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `pr-flow-plugin`（拉取请求流程插件）：增加多工作树隔离、最新目标基线、提交门禁复核和工作树安全清理契约。

## Impact

- 修改 `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py` 及 PR Flow（拉取请求流程）相关 Skill（技能）说明。
- 在现有 `tests/test_pr_flow_cli.py` 中增加真实 Git（版本控制）工作树与并发端到端回归。
- 修改 `openspec/specs/pr-flow-plugin/spec.md` 对应规格；复用现有 `.pr-flow/runs/`，不新增依赖。
