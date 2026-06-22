---
name: pr-flow-hotfix
description: "执行 PR Flow（拉取请求流程）hotfix（热修复）路径，在显式授权后直接推送受保护目标分支。"
---

# PR Flow Hotfix

## 边界

仅用于配置中显式允许 `allowHotfixPush: true` 的目标分支。执行前会校验当前分支等于目标分支、目标分支基线与远端一致、工作区有改动、authorization phrase（授权短语）匹配，并运行 `hotfix.verifyCommand`。

命令会把当前目标分支直接 push（推送）到配置远端。不创建 PR，不合并 PR，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py hotfix --project . --target main --authorization-phrase <phrase>
```
