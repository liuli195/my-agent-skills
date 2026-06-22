---
name: pr-flow-cleanup
description: "清理已合并 PR 的 head branch（源分支），同步 base branch（目标分支），并删除本地分支。"
---

# PR Flow Cleanup

## 边界

只处理已合并 PR 的 cleanup（清理）。会校验 PR 已合并、当前工作区干净、当前分支等于 PR head branch（源分支），且 head branch 不等于 base branch（目标分支）。

命令会删除远端 head branch（源分支）、切回并同步 base branch（目标分支）、删除本地 head branch（源分支）。不合并 PR，不创建提交，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py cleanup --project . --pr <number>
```
