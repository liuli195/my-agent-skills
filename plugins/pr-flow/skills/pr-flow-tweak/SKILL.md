---
name: pr-flow-tweak
description: "PR Flow（拉取请求流程）tweak（小改）路径，用于非 BUG（缺陷）小改动 PR（拉取请求）。"
---

# PR Flow Tweak

## 边界

用于非 BUG（缺陷）小改动 PR（拉取请求），例如文案、格式、注释或低风险配置微调。

该路径跳过 review gate（审查门禁），但仍保留 checks（检查）、merge（合并）和 cleanup（清理）。

只进入 PR Flow（拉取请求流程）tweak（小改）路径，不修改 OpenSpec（开放规格）任务。`--reason` 只说明为什么使用 tweak（小改）路径，不写入 PR body（拉取请求正文）。

默认保留当前 worktree（工作树）。`--remove-worktree`（删除工作树参数）只在合并和安全 cleanup（清理）完成后生效；从待删除目录内运行时，按输出的外部重试命令完成删除，且永不强制删除。

## 命令

```bash
python plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py tweak --project . --reason "small docs polish" --summary "更新 PR Flow 文档措辞" --scope "只修改 PR Flow 文档" --fixes 98
```
