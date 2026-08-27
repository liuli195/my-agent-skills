---
name: pr-flow-tweak
description: "PR Flow（拉取请求流程）tweak（小改）路径，用于非 BUG（缺陷）小改动 PR（拉取请求）。"
---

# PR Flow Tweak

## 边界

用于非 BUG（缺陷）小改动 PR（拉取请求），例如文案、格式、注释或低风险配置微调。

该路径跳过 review gate（审查门禁），但仍保留 checks（检查）、merge（合并）和 cleanup（清理）。开发模式身份来自工具公开诊断的实现闭包和可由 CI（持续集成）检出的精确实现提交；源码工作树可以同时作为当前目标工作树。缺少可复现提交时，命令会在任何工具链文件或 PR 操作前安全停止。

只进入 PR Flow（拉取请求流程）tweak（小改）路径，不修改 MySpec（自有规格）任务。`--reason` 只说明为什么使用 tweak（小改）路径，不写入 PR body（拉取请求正文）。

默认保留当前 worktree（工作树）。`--remove-worktree`（删除工作树参数）只在合并和安全 cleanup（清理）完成后生效。工作树身份来自 Git worktree registration（Git 工作树登记），不依赖 `main` 名称、路径名或宿主：primary worktree（主工作树）收到该参数时不删除，完成后检出实际 target/base branch（目标/基础分支）的最新提交；registered linked non-primary worktree（已登记关联非主工作树）仅在 active Agent session（活跃代理会话）位于其中时保留在该提交的 detached HEAD（分离头），从外部调用该关联工作树仍删除。任何需要切换提交且 active cwd（活跃当前目录）在目标提交中不存在又未被 Git（版本管理）忽略时，必须在切换前停止。保留路径以 `cleanup_complete`（清理完成）和 active-session retention（活跃会话保留）作为成功终态，不留下 `removeWorktreePending`（工作树删除待处理）或外部 `nextCommand`（下一命令）；且永不强制删除。

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
