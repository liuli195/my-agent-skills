---
name: pr-flow
description: "诊断 PR Flow（拉取请求流程）当前状态，并输出下一步 stop state（停止状态）。"
---

# PR Flow

## 边界

只诊断 PR Flow 状态，不提交、不推送、不合并，也不修改 MySpec（自有规格）任务。

会读取 `.pr-flow/config.yaml`，检查当前 git branch（分支）、upstream（上游分支）、工作区状态和 GitHub PR 状态，并输出 `PUSH_REQUIRED`、`DISPATCH_REQUIRED`、`REPLY_OR_FIX_REQUIRED` 或 `EXCEPTION_REQUIRED`。

## 初始化入口

`pr-flow-init` 初始化 PR Flow（拉取请求流程）配置：agent（代理）问答、配置草案、只读 validate（校验）和用户确认后本地写入。

## 命令

以本次加载的技能安装目录为基准，使用 `scripts/pr_flow.py`，确认脚本存在。

下方填入本技能安装目录和目标项目目录的绝对路径；`--project` 始终指向用户目标项目，不指向插件目录。不切换当前目录；无法确认路径或脚本不存在时，停止并报告。

```bash
python "<本技能安装目录>/scripts/pr_flow.py" diagnose --project "<目标项目目录>"
```
