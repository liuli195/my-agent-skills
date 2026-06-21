---
name: pr-flow
description: "诊断 PR Flow（拉取请求流程）状态。Use when 需要查看 PR Flow 当前状态或阻塞原因。"
---

# PR Flow

## 边界

只诊断 PR Flow 状态，不提交、不推送、不合并，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python scripts/pr_flow.py diagnose
```
