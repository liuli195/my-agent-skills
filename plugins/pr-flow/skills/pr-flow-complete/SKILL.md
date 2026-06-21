---
name: pr-flow-complete
description: "PR Flow（拉取请求流程）完成骨架入口；当前命令返回 status: not_implemented。"
---

# PR Flow Complete

## 边界

当前为骨架入口；命令只会输出 `status: not_implemented`，并以返回码 2 结束。

只处理 PR Flow 收尾检查，不提交、不推送、不合并，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py complete
```
