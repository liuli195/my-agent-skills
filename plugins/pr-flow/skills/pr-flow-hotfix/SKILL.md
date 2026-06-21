---
name: pr-flow-hotfix
description: "运行 PR Flow（拉取请求流程）hotfix（热修复）入口。Use when 需要按 hotfix 路径处理 PR Flow。"
---

# PR Flow Hotfix

## 边界

只进入 PR Flow hotfix 路径，不提交、不推送、不合并，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py hotfix
```
