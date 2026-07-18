# Brainstorm Summary

- Change: optimize-pr-flow-init-template
- Date: 2026-06-28

## 确认的技术方案

采用最小模板修正：只改 `pr-flow-init` reference（参考文件）和已有文档契约测试，不改 `pr_flow.py`（拉取请求流程脚本）运行逻辑。

实现必须采用本轮最新模拟流程：

1. 自动检查仓库和 GitHub（代码托管平台）当前状态。
2. 询问默认 PR target branch（拉取请求目标分支）。
3. 询问哪些分支通过 GitHub Rulesets（GitHub 规则集）做 branch protection（分支保护），并表达为 `Require a pull request before merging`（合并前要求拉取请求）和 `required_approving_review_count: 0`。
4. 询问 PR status checks（拉取请求状态检查），没有具体 check name（检查名称）时只记录待新增或待识别。
5. 询问 CodeQL security check（CodeQL 安全检查），只允许“开启”和“不开启”；开启时远端待办配置 `Require code scanning results`（要求代码扫描结果）并选择 `CodeQL`。
6. 询问 hotfix（热修复）直推；仅允许后再询问授权短语是复用还是新设。
7. 询问 merge methods（合并方式）。
8. 先展示用户可读摘要，再展示 YAML（配置格式）细节；远端待办必须清楚到 agent（代理）可执行。
9. GitHub access（GitHub 访问权限）、`gh` CLI（GitHub 命令行工具）或 network（网络）不可用时，显示 `not inspected`（未检查）或 `no access`（无权限），不得把推荐配置写成已确认远端状态。

## 候选方案

已确认推荐方案：只改 `pr-flow-init` reference（参考文件）和已有文档契约测试，不改运行脚本。

可选方案：

1. 最小模板修正：更新 `questionnaire.md`、`config-draft.md`、`validation.md` 和 `tests/test_pr_flow_cli.py` 中的契约断言。
2. 脚本建模扩展：给 `setup.github` 增加更细的 GitHub Rulesets（规则集）结构字段。
3. 拆分初始化向导引擎：把问答流程从文档迁到可执行脚本。

## 关键取舍与风险

- 采用方案 1，避免把文档模板优化扩大成运行时重构。
- 保留 plugin entrypoint（插件入口）路由验收，但不把 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 和 `skills/pr-flow/SKILL.md`（总入口）列为计划源码修改，除非文案冲突。
- 风险：纯关键词测试不足以保证交互质量；用固定问题、官方规则名和摘要结构断言降低风险。
- 风险：GitHub（代码托管平台）远端配置仍是人工待办；本变更只让待办可执行，不自动写远端。

## 测试策略

- 先新增失败测试锁定五问流程、官方 GitHub（代码托管平台）规则名、用户可读摘要和结构化远端待办。
- 通过后再更新三个 reference（参考文件）到最小可读模板。
- 最后运行 focused PR Flow（拉取请求流程）测试和 OpenSpec（开放规格）严格校验。

## Spec Patch

本变更已有 OpenSpec delta（开放规格增量）：新增 GitHub（代码托管平台）可执行远端待办要求，并修改 PR Flow init（拉取请求流程初始化）的渐进式模板契约。实现阶段不需要额外回写新的 Spec Patch（规格补丁），除非发现验收场景仍缺失。
