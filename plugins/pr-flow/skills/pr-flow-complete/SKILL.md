---
name: pr-flow-complete
description: "执行 PR Flow（拉取请求流程）收尾：创建或同步 PR、等待 checks（检查）、执行 review gate（审查门禁）、合并并清理。"
---

# PR Flow Complete

## 边界

会根据 `.pr-flow/config.yaml` 处理 PR 收尾。命令可能创建或同步 PR、等待 checks（检查）、执行 review gate（审查门禁）、合并 PR，并在合并后调用 cleanup（清理）。

不创建本地提交，不强制推送，也不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py complete --project .
```
