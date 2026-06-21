---
name: pr-flow-tweak
description: "运行 PR Flow（拉取请求流程）tweak（小改）入口。Use when 需要按 tweak 路径处理 PR Flow。"
---

# PR Flow Tweak

## 边界

只进入 PR Flow tweak 路径，不提交、不推送、不合并，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py tweak
```
