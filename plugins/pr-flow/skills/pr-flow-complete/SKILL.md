---
name: pr-flow-complete
description: "执行 PR Flow（拉取请求流程）收尾：创建或同步 PR、等待 checks（检查）、执行 review gate（审查门禁）、合并并清理。"
---

# PR Flow Complete

## 边界

会根据 `.pr-flow/config.yaml` 处理 PR 收尾。命令可能创建或同步 PR、等待 checks（检查）、执行 review gate（审查门禁）、合并 PR，并在合并后调用 cleanup（清理）。

通常不创建本地提交，不强制推送，也不修改 MySpec（自有规格）任务；仅当已初始化的工具链身份变化时，自动提交受管的 `.pr-flow/toolchain.json`（工具链身份记录）和/或 `.github/workflows/pr-flow-toolchain.yml`（工具链工作流）。开发模式身份来自工具公开诊断的实现闭包和可由 CI（持续集成）检出的精确实现提交；源码工作树可以同时作为当前目标工作树。缺少可复现提交时，命令会在任何工具链文件或 PR 操作前安全停止。

默认保留当前 worktree（工作树）。只有显式传入 `--remove-worktree`（删除工作树参数）时，才在合并和安全 cleanup（清理）完成后删除；若当前 active Agent session（活跃代理会话）仍在待删除目标工作树内，cleanup（清理）会将其保留在目标分支最新提交的 detached HEAD（分离头），并以 `cleanup_complete`（清理完成）和 active-session retention（活跃会话保留）作为成功终态，不留下 `removeWorktreePending`（工作树删除待处理）或外部 `nextCommand`（下一命令）。从目标工作树外运行时仍完成登记删除和实体目录核验；任一路径都永不使用强制删除。若目标工作树由 Orca（工作区管理器）登记，命令优先使用 Orca（工作区管理器）的非强制删除；Orca（工作区管理器）未登记或不可用时回退 Git（版本管理）删除。已登记目标的 Orca（工作区管理器）删除失败时停止并保留诊断，不回退 Git（版本管理）删除。

## Pi 入口

在 Pi（编码助手）中，调用 `pr_flow`（PR Flow 工具）：

```json
{"argv":["complete","--project",".","--summary","修复 PR Flow 创建空正文 PR","--scope","更新 complete、tweak、diagnose 和测试","--fixes","98"]}
```

## 命令

源码仓库维护者或其他宿主继续使用：

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py complete --project . --summary "修复 PR Flow 创建空正文 PR" --scope "更新 complete、tweak、diagnose 和测试" --fixes 98
```
