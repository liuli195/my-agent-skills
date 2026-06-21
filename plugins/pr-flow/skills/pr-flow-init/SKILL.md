---
name: pr-flow-init
description: "初始化 PR Flow（拉取请求流程）。Use when 需要开始 PR Flow。"
---

# PR Flow Init

## 边界

只初始化 PR Flow 所需状态，不提交、不推送、不合并，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py init
```
