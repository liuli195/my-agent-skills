---
name: pr-flow
description: "诊断 PR Flow（拉取请求流程）当前状态，并输出下一步 stop state（停止状态）。"
---

# PR Flow

## 边界

只诊断 PR Flow 状态，不提交、不推送、不合并，也不修改 OpenSpec（开放规格）任务。

会读取 `.pr-flow/config.yaml`，检查当前 git branch（分支）、upstream（上游分支）、工作区状态和 GitHub PR 状态，并输出 `PUSH_REQUIRED`、`DISPATCH_REQUIRED`、`REPLY_OR_FIX_REQUIRED` 或 `EXCEPTION_REQUIRED`。

## 初始化入口

`pr-flow-init` 初始化 PR Flow（拉取请求流程）配置：agent（代理）问答、配置草案、只读 validate（校验）和用户确认后本地写入。

## Pi 入口

在 Pi（编码助手）中，调用 `pr_flow`（PR Flow 工具）：

```json
{"argv":["diagnose","--project","."]}
```

## 命令

源码仓库维护者或其他宿主继续使用：

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py diagnose --project .
```
