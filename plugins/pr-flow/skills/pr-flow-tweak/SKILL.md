---
name: pr-flow-tweak
description: "PR Flow（拉取请求流程）tweak（小改）路径，用于非 BUG（缺陷）小改动 PR（拉取请求）。"
---

# PR Flow Tweak

## 边界

用于非 BUG（缺陷）小改动 PR（拉取请求），例如文案、格式、注释或低风险配置微调。

该路径跳过 review gate（审查门禁），但仍保留 checks（检查）、merge（合并）和 cleanup（清理）。

只进入 PR Flow（拉取请求流程）tweak（小改）路径，不修改 OpenSpec（开放规格）任务。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py tweak --project /path/to/project --reason "small docs polish"
```
