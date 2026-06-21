---
name: pr-flow-cleanup
description: "清理 PR Flow（拉取请求流程）本地状态。Use when 需要清理 PR Flow 残留状态。"
---

# PR Flow Cleanup

## 边界

只清理 PR Flow 本地状态，不提交、不推送、不合并，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py cleanup
```
