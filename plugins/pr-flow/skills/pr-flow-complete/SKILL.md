---
name: pr-flow-complete
description: "执行 PR Flow（拉取请求流程）收尾：创建或同步 PR、等待 checks（检查）、执行 review gate（审查门禁）、合并并清理。"
---

# PR Flow Complete

## 边界

会根据 `.pr-flow/config.yaml` 处理 PR 收尾。命令可能创建或同步 PR、等待 checks（检查）、执行 review gate（审查门禁）、合并 PR，并在合并后调用 cleanup（清理）。

不创建本地提交，不强制推送，也不修改 OpenSpec（开放规格）任务。

默认保留当前 worktree（工作树）。只有显式传入 `--remove-worktree`（删除工作树参数）时，才在合并和安全 cleanup（清理）完成后删除；从待删除目录内运行时，按输出的外部重试命令完成删除，且永不使用强制删除。

## 命令

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py complete --project . --summary "修复 PR Flow 创建空正文 PR" --scope "更新 complete、tweak、diagnose 和测试" --fixes 98
```
