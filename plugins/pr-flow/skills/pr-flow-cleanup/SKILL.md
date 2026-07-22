---
name: pr-flow-cleanup
description: "清理已合并 PR 的 head branch（源分支），同步 base branch（目标分支），并删除本地分支。"
---

# PR Flow Cleanup

## 边界

只处理已合并 PR 的 cleanup（清理）。会校验 PR 已合并、当前工作区干净、当前工作树位于 PR head branch（源分支）或最新远端目标提交的 detached HEAD（分离头），且 head branch 不等于 base branch（目标分支）。

命令会定位到最新远端目标提交，并将本地 base branch（目标分支）安全快进到同一提交；随后当前工作树会切回该目标分支，回读确认当前 `HEAD`、本地目标分支和远端快照一致后，再按实时状态安全删除远端和本地 head branch（源分支）。若其他工作树已检出目标分支，cleanup（清理）仅在该工作树仍检出目标分支、工作区和暂存区干净、无进行中的 Git（版本管理）操作、提交未变化且本地提交是远端提交祖先时，才在该工作树执行 `git merge --ff-only`（仅快进合并）；随后当前工作树保留在最新目标提交的 detached HEAD（分离头），完成源分支清理并记录跳过切回的原因。任一检查或快进失败都会安全停止。若目标分支在检出时才被占用，命令会重新读取工作树清单并采用相同降级或停止规则。失败后可直接重试。默认保留 worktree（工作树）；`--remove-worktree`（删除工作树参数）仅在安全收尾后生效，从待删除目录内运行时按输出的外部重试命令删除，且永不强制删除。若目标工作树由 Orca（工作区管理器）登记，命令优先使用 Orca（工作区管理器）的非强制删除；Orca（工作区管理器）未登记或不可用时回退 Git（版本管理）删除。已登记目标的 Orca（工作区管理器）删除失败时停止并保留诊断，不回退 Git（版本管理）删除。不合并 PR，不创建提交，也不修改 OpenSpec（开放规格）任务。

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
