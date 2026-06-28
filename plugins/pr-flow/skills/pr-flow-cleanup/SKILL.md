---
name: pr-flow-cleanup
description: "清理已合并 PR 的 head branch（源分支），同步 base branch（目标分支），并删除本地分支。"
---

# PR Flow Cleanup

## 边界

只处理已合并 PR 的 cleanup（清理）。会校验 PR 已合并、当前工作区干净、当前分支等于 PR head branch（源分支），且 head branch 不等于 base branch（目标分支）。

命令会删除远端 head branch（源分支）、切回并同步 base branch（目标分支）、删除本地 head branch（源分支）。不合并 PR，不创建提交，也不修改 OpenSpec（开放规格）任务。

cleanup 不查询 GitHub Branch Protection（GitHub 分支保护）或 Rulesets（规则集），也不自动配置远端保护规则；它只保证不删除 base branch。

## 命令

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py cleanup --project . --pr <number>
```
