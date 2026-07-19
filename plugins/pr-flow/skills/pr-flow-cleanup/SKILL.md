---
name: pr-flow-cleanup
description: "清理已合并 PR 的 head branch（源分支），同步 base branch（目标分支），并删除本地分支。"
---

# PR Flow Cleanup

## 边界

只处理已合并 PR 的 cleanup（清理）。会校验 PR 已合并、当前工作区干净、当前工作树位于 PR head branch（源分支）或最新远端目标提交的 detached HEAD（分离头），且 head branch 不等于 base branch（目标分支）。

命令会定位到最新远端目标提交的 detached HEAD（分离头），同时将未被其他工作树占用的本地 base branch（目标分支）安全快进到同一提交，再按实时状态安全删除远端和本地 head branch（源分支）。本地目标分支无法安全快进或正以旧提交被其他工作树占用时停止；失败后可直接重试。默认保留 worktree（工作树）；`--remove-worktree`（删除工作树参数）仅在安全收尾后生效，从待删除目录内运行时按输出的外部重试命令删除，且永不强制删除。不合并 PR，不创建提交，也不修改 OpenSpec（开放规格）任务。

cleanup 不查询 GitHub Branch Protection（GitHub 分支保护）或 Rulesets（规则集），也不自动配置远端保护规则；它只保证不删除 base branch。

## 命令

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py cleanup --project . --pr <number>
```
