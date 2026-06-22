---
name: pr-flow-init
description: "初始化 PR Flow（拉取请求流程）本地配置、PR 模板和运行态忽略文件。Use when 需要为仓库启用 PR Flow 配置。"
---

# PR Flow Init

## 边界

只初始化 PR Flow 所需状态，不提交、不推送、不合并，也不修改 OpenSpec（开放规格）任务。

会写入 `.pr-flow/config.yaml`、`.pr-flow/pr-template.md` 和 `.pr-flow/.gitignore`。GitHub Rulesets（GitHub 规则集）只输出配置建议，不自动写远端规则。

## 命令

```bash
python ../pr-flow/scripts/pr_flow.py init --project . --base-branch main
```
