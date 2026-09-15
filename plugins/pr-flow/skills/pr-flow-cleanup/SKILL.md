---
name: pr-flow-cleanup
description: "清理已合并 PR 的 head branch（源分支），同步 base branch（目标分支），并删除本地分支。"
---

# PR Flow Cleanup

## 边界

只处理已合并 PR 的 cleanup（清理）。会校验 PR 已合并、当前工作区干净、当前工作树位于 PR head branch（源分支）或最新远端目标提交的 detached HEAD（分离头），且 head branch 不等于 base branch（目标分支）。

命令会定位到最新远端目标提交，并将本地 base branch（目标分支）安全快进到同一提交；随后安全同步当前工作树与目标分支状态，再按实时状态删除远端和本地 head branch（源分支）。若其他工作树已检出目标分支，cleanup（清理）仅在该工作树仍检出目标分支、工作区和暂存区干净、无进行中的 Git（版本管理）操作、提交未变化且本地提交是远端提交祖先时，才在该工作树执行 `git merge --ff-only`（仅快进合并）；随后刷新本地 remote-tracking branch（远端跟踪分支）副本，并确认该副本、本地目标分支和当前提交均等于本轮最新远端目标提交；一致后，当前工作树保留在该提交的 detached HEAD（分离头），完成源分支清理并记录跳过切回的原因。若 primary worktree（主工作树）遇到 target/base branch（目标/基础分支）被其他 worktree（工作树）占用，无论是否传入 `--remove-worktree`（删除工作树参数），都必须在任何 Git 状态改变前停止；只有 linked non-primary target（关联非主目标工作树）可在安全条件下快进 occupied base（被占用的基础分支），并在切换前保护 occupied worktree（被占用工作树）的 active cwd（活跃当前目录）。工作树身份只按 Git worktree registration（Git 工作树登记）判定，不依赖 `main` 名称、路径名或宿主：`--remove-worktree`（删除工作树参数）作用于 primary worktree（主工作树）时不删除，完成后检出实际 target/base branch（目标/基础分支）的最新提交；registered linked non-primary worktree（已登记关联非主工作树）仅在 active session（活跃会话）位于其中时保留在该提交的 detached HEAD（分离头），从外部调用该关联工作树仍删除。任何需要切换提交且 active cwd（活跃当前目录）在目标提交中不存在又未被 Git（版本管理）忽略时，必须在切换前停止。任一检查、快进或一致性回读失败都会安全停止。若目标分支在检出时才被占用，命令会重新读取工作树清单并采用相同降级或停止规则。失败后可直接重试。默认保留 worktree（工作树）；`--remove-worktree`（删除工作树参数）仅在安全收尾后生效。从 registered linked non-primary worktree（已登记关联非主工作树）外运行时，若显式删除工作树，仍先完成登记删除和实体目录核验；从被保留的关联工作树内运行时不要求外部交接，且永不强制删除；primary worktree（主工作树）不执行删除。若目标工作树由 Orca（工作区管理器）登记，命令优先使用 Orca（工作区管理器）的非强制删除；Orca（工作区管理器）未登记或不可用时回退 Git（版本管理）删除。已登记目标的 Orca（工作区管理器）删除失败时停止并保留诊断，不回退 Git（版本管理）删除。不合并 PR，不创建提交，也不修改 MySpec（自有规格）任务。

cleanup 不查询 GitHub Branch Protection（GitHub 分支保护）或 Rulesets（规则集），也不自动配置远端保护规则；它只保证不删除 base branch。

## Pi 入口

在 Pi（编码助手）中，调用 `pr_flow`（PR Flow 工具）：

```json
{"argv":["cleanup","--project",".","--pr","<number>"]}
```

## 命令

源码仓库维护者或其他宿主继续使用：

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py cleanup --project . --pr <number>
```
