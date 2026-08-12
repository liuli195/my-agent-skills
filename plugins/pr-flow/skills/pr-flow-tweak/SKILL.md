---
name: pr-flow-tweak
description: "PR Flow（拉取请求流程）tweak（小改）路径，用于非 BUG（缺陷）小改动 PR（拉取请求）。"
---

# PR Flow Tweak

## 边界

用于非 BUG（缺陷）小改动 PR（拉取请求），例如文案、格式、注释或低风险配置微调。

该路径跳过 review gate（审查门禁），但仍保留 checks（检查）、merge（合并）和 cleanup（清理）。开发模式身份来自工具公开诊断的实现闭包和可由 CI（持续集成）检出的精确实现提交；源码工作树可以同时作为当前目标工作树。缺少可复现提交时，命令会在任何工具链文件或 PR 操作前安全停止。

只进入 PR Flow（拉取请求流程）tweak（小改）路径，不修改 MySpec（自有规格）任务。`--reason` 只说明为什么使用 tweak（小改）路径，不写入 PR body（拉取请求正文）。

默认保留当前 worktree（工作树）。`--remove-worktree`（删除工作树参数）只在合并和安全 cleanup（清理）完成后生效；若当前 active Agent session（活跃代理会话）仍在待删除目标工作树内，cleanup（清理）会将其保留在目标分支最新提交的 detached HEAD（分离头），并以 `cleanup_complete`（清理完成）和 active-session retention（活跃会话保留）作为成功终态，不留下 `removeWorktreePending`（工作树删除待处理）或外部 `nextCommand`（下一命令）。从目标工作树外运行时按现有规则删除登记并核验实体目录，且永不强制删除。

## Pi 入口

在 Pi（编码助手）中，调用 `pr_flow`（PR Flow 工具）：

```json
{"argv":["tweak","--project",".","--reason","small docs polish","--summary","更新 PR Flow 文档措辞","--scope","只修改 PR Flow 文档","--fixes","98"]}
```

## 命令

源码仓库维护者或其他宿主继续使用：

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tweak --project . --reason "small docs polish" --summary "更新 PR Flow 文档措辞" --scope "只修改 PR Flow 文档" --fixes 98
```
