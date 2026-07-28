# Brainstorm Summary

- Change: fix-governance-flow-recovery-and-help
- Date: 2026-07-01

## 确认的技术方案

用户已确认采用最小局部修复方案。

- `PR Flow`（拉取请求流程）：保留现有 `gh_pr_view`（查看拉取请求）重试逻辑，只补 post-create sync（创建后同步）EOF（连接提前结束）回归测试；把 invalid `--fixes`（无效修复编号，包括逗号分隔、`#123`、非数字和小于等于 0）提前报告为独立输入错误，并在 help（帮助）和 stop output（停止输出）中给出重复参数示例。
- `Release Flow`（发布流程）：删除 `publish --dry-run`（发布试运行）；在 `publish`（发布）正式触发 `gh workflow run`（触发工作流）时加一个脚本内小型 EOF（连接提前结束）有界重试，并覆盖重试成功和耗尽失败。
- `cross-agent-review`（跨代理审查）：不改路径算法，继续使用 `head_ref[:12]`；只在规格、Skill（技能）文档和命令输出中显式打印 `head_ref_short`（短头引用）和可复制路径。

## 关键取舍与风险

- 删除 `publish --dry-run`（发布试运行）是 breaking change（破坏性变更），但用户已明确要求删除。
- `Release Flow`（发布流程）局部重试会和 `PR Flow`（拉取请求流程）存在少量重复代码；接受原因是避免新增跨插件框架。
- `invalid --fixes`（无效修复编号）改变 stop reason（停止原因）可能需要更新既有测试断言；接受原因是用户可见提示必须指向真实错误。
- live GitHub（真实代码托管平台）发布、合并和 workflow dispatch（工作流触发）有远端副作用；本地端到端回归通过插件 CLI（命令行接口）入口和命令桩覆盖主流程，最终验证报告记录未执行真实远端副作用。

## 测试策略

- 聚焦 CLI（命令行接口）测试：所有无效 `--fixes`、有效重复 `--fixes`、post-create sync EOF（创建后同步连接提前结束）。
- 聚焦 Release Flow（发布流程）测试：`publish --dry-run`（发布试运行）被拒绝、`gh workflow run`（触发工作流）EOF 后重试成功、重试耗尽后失败。
- 聚焦 cross-agent-review（跨代理审查）测试：`run`（运行）和 `mark-pass`（标记通过）输出路径和 12 位 `head_ref_short`（短头引用）。
- CLI end-to-end regression（命令行端到端回归）：从 PR Flow `complete`、Release Flow `publish`、cross-agent-review `run`/`mark-pass` 用户入口跑主流程，使用本地仓库和命令桩避免真实 GitHub（代码托管平台）副作用。
- OpenSpec（开放规格）严格校验和相关 pytest（测试）文件。

## Spec Patch

无。当前 OpenSpec delta spec（开放规格增量规格）已覆盖验收场景，不需要再回写额外规格。
