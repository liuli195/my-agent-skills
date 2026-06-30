---
comet_change: fix-governance-flow-recovery-and-help
role: technical-design
canonical_spec: openspec
---

# Governance Flow Recovery and Help Design

## Context

本次变更修复三个治理流程中的可恢复问题，并删除一个不再需要的发布试运行入口：

- `PR Flow`（拉取请求流程）已经有 `gh pr view`（查看拉取请求）的 EOF（连接提前结束）有界重试，但缺少创建 PR（拉取请求）后同步查看的回归测试。
- `PR Flow`（拉取请求流程）已识别无效 `--fixes`（修复问题编号），但用户可见输出仍像是缺少 PR body（拉取请求正文）。
- `Release Flow`（发布流程）正式 `publish`（发布）直接调用 `gh workflow run`（触发工作流），没有吸收 GitHub（代码托管平台）短暂 EOF（连接提前结束）。
- `cross-agent-review`（跨代理审查）实际使用 `head_ref[:12]`（头引用前 12 位）生成路径，但文档和输出没有把规则讲清楚。
- `release-flow publish --dry-run`（发布试运行）要删除；其他仍有价值的 dry-run（试运行）入口不动。

## Technical Approach

采用最小局部修复，不新增依赖，不新增跨插件公共框架。

### PR Flow

`gh_pr_view`（查看拉取请求辅助函数）已经被 `find_pr`（查找拉取请求）和 `sync_pr`（同步拉取请求）复用，所以创建 PR（拉取请求）后的 EOF（连接提前结束）恢复路径应先用测试锁住。如果测试暴露缺口，再在同一个 `gh_pr_view`（查看拉取请求辅助函数）入口修复。

`--fixes`（修复问题编号）校验改为先于 `--summary`（摘要）/`--scope`（范围）缺失判断。无效值时使用独立原因，例如 `invalid_fixes`（无效修复编号），并保留 `invalidFixes`（无效修复编号列表）。输出给出可复制形式：

```text
--fixes 41 --fixes 43 --fixes 44
```

`argparse`（参数解析器）的 help（帮助）直接描述重复传参形式，避免新增 `help`（帮助）子命令。

无效值范围覆盖逗号分隔值、`#123`（带井号前缀）、非数字值和小于等于 0 的值。空值仍按现有参数收集逻辑处理，不引入新的解析器。

### Release Flow

删除 `publish.add_argument("--dry-run", ...)` 和 `run_publish`（执行发布）里的 dry-run（试运行）分支。`publish --dry-run`（发布试运行）由现有 CLI（命令行接口）参数解析拒绝。

同步更新 Release Flow（发布流程）文档和 help（帮助），避免继续展示已删除入口。迁移说明只指向现有能力：`preflight`（发布前检查）用于发布前验证，`publish --authorize-publish`（授权发布）用于实际触发。

正式发布路径保留 `--authorize-publish`（授权发布）门禁。`gh workflow run`（触发工作流）改为列表参数执行，不再依赖 `command.split()`（字符串拆分）。在 `run_publish`（执行发布）附近增加一个小 helper（辅助函数）：

- 执行 `gh workflow run ...`
- 如果 stdout（标准输出）或 stderr（标准错误）包含 EOF（连接提前结束）且返回非 0，最多重试固定次数
- 最后一次结果原样决定返回码；重试耗尽时保留最终 GitHub CLI（GitHub 命令行）输出，不能误报成功

该 helper（辅助函数）只服务 `publish`（发布）；不扩展到 preflight（发布前检查）或文档中的手工 `gh issue`（GitHub 议题）命令。

### Cross-Agent Review

保留当前路径算法：`short_ref(ref) = ref[:12]`。改动只做显性化：

- Skill（技能）文档说明 `<head_ref_short>`（短头引用）是 `head_ref`（头引用）前 12 位。
- `run`（运行）成功后打印 `head_ref_short`（短头引用）和实际 `review-input.json`（审查输入文件）路径。
- `mark-pass`（标记通过）继续打印 evidence path（证据路径），并补充同一个 `head_ref_short`（短头引用）。

## Testing Strategy

使用现有 pytest（测试）和命令桩，不访问真实 GitHub（代码托管平台）。端到端回归必须从插件 CLI（命令行接口）用户入口启动，在临时本地仓库中跑完整主流程；GitHub（代码托管平台）边界用命令桩模拟，避免真实发布、合并或远端写入副作用。最终验证报告必须明确说明 live GitHub（真实代码托管平台）副作用没有执行。

- `tests/test_pr_flow_cli.py`：
  - 逗号分隔、`#123`、非数字和小于等于 0 的 `--fixes`（修复问题编号）被拒绝，并显示重复参数示例。
  - 合法重复 `--fixes`（修复问题编号）继续生成多个 `Fixes #...`。
  - 创建 PR（拉取请求）后同步 `gh pr view`（查看拉取请求）第一次 EOF（连接提前结束）、第二次成功时流程继续。
- `tests/test_release_flow_cli.py`：
  - `publish --dry-run`（发布试运行）被 CLI（命令行接口）拒绝。
  - `publish --authorize-publish`（授权发布）遇到 `gh workflow run`（触发工作流）EOF（连接提前结束）后重试成功。
  - `publish --authorize-publish`（授权发布）EOF（连接提前结束）重试耗尽后返回失败并保留输出。
- `tests/test_cross_agent_review_cli.py` 和 package docs tests（包文档测试）：
  - `run`（运行）输出 `review-input.json`（审查输入文件）路径和 12 位短引用。
  - `mark-pass`（标记通过）输出同一 12 位短引用和 evidence path（证据路径）。
  - Skill（技能）文档包含 12 位规则。
- CLI end-to-end regression（命令行端到端回归）：
  - `PR Flow complete`（拉取请求流程收尾）从命令入口覆盖参数校验、PR 创建后同步和后续生命周期。
  - `Release Flow publish`（发布流程发布）从命令入口覆盖授权发布触发和 EOF（连接提前结束）重试。
  - `cross-agent-review run`（跨代理审查运行）加 `mark-pass`（标记通过）从命令入口覆盖报告和证据输出。
- `openspec validate fix-governance-flow-recovery-and-help --strict`。

## Risks

- `publish --dry-run`（发布试运行）删除是 breaking change（破坏性变更）。这是用户确认的目标，迁移路径是使用 `preflight`（发布前检查）和 `publish --authorize-publish`（授权发布）。
- Release Flow（发布流程）局部 EOF（连接提前结束）重试会和 PR Flow（拉取请求流程）存在少量重复。接受该重复，避免为单一发布边界引入公共框架。
- `invalid_fixes`（无效修复编号）可能改变既有断言。测试会同步更新，并保留 `invalidFixes`（无效修复编号列表）便于状态文件诊断。

## Spec Patch

无。当前 delta spec（增量规格）已覆盖实现所需验收场景。
