---
name: pr-flow-init
description: "PR Flow（拉取请求流程）初始化骨架入口；当前命令返回 status: not_implemented。"
---

# PR Flow Init

## 边界

当前为骨架入口；命令只会输出 `status: not_implemented`，并以返回码 2 结束。

只初始化 PR Flow 所需状态，不提交、不推送、不合并，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py init
```
