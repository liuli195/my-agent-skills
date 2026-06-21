---
name: pr-flow-complete
description: "完成 PR Flow（拉取请求流程）。Use when 需要收尾 PR Flow。"
---

# PR Flow Complete

## 边界

只处理 PR Flow 收尾检查，不提交、不推送、不合并，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py complete
```
