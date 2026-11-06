---
name: pr-flow
description: "诊断 PR Flow（拉取请求流程）当前状态，并输出下一步 stop state（停止状态）。"
---

# PR Flow

## 运行前提

脚本需要 Python（编程语言）及本技能 `requirements.txt` 声明的 PyYAML（配置解析库）。复用现有环境，确认本次实际解释器；缺库时由原入口报告解释器和声明位置，只报告缺失，由用户决定是否安装。

Git（版本管理工具）、gh（代码托管命令工具）及认证只在对应仓库或远端操作实际需要时核对。初始化工具链时复用 myspec（自有规格命令）与 build-and-verify（构建验证命令）的既有诊断；Orca（工作区管理器）仅是工作树清理的条件适配，无该工具时遵守既有 Git（版本管理工具）回退规则。项目配置的验证命令按目标项目自身依赖准备，不预先扫描所有插件或安装环境。

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
