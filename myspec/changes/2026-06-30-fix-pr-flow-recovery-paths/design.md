## Context

本次修复来自 PR Flow（拉取请求流程）真实运行中的四类问题：GitHub（代码托管平台）只读查询偶发 EOF（连接提前结束）、checks（检查）仍运行时 merge（合并）提示不直接、旧 `evidencePath`（审查证据路径）残留误导、已有 PR body（拉取请求正文）和 `--fixes`（关闭引用参数）重复时恢复路径不顺。

现有脚本已经有 `gh`（GitHub 命令行）封装、`wait_for_checks`（等待检查）、`update_pr_body`（更新正文）、`validate_config`（校验配置）和 stop state（停止状态）写入能力。本设计只复用这些能力。

## Goals / Non-Goals

**Goals:**

- 只对只读 PR（拉取请求）查看增加 transient（临时失败）重试。
- `ruleset_merge_blocking`（规则集阻塞）后复用现有 checks（检查）等待。
- 已有正文下无感追加缺失 closing references（关闭引用）。
- 对废弃 `evidencePath`（审查证据路径）输出 warning（警告）。

**Non-Goals:**

- 不新增依赖。
- 不新增配置文件字段。
- 不启用 GitHub auto-merge（自动合并）。
- 不恢复 local/dual review gate（本地/双重审查门禁）。
- 不重写人工 PR body（拉取请求正文）。

## Decisions

1. `gh pr view`（查看拉取请求）重试只包只读路径。

   `find_pr`（查找拉取请求）、`view_pr_for_cleanup`（清理前查看拉取请求）和 `diagnose`（诊断）使用同一个轻量 helper（辅助函数）。默认重试次数放脚本常量，环境变量可覆盖，重试期间不打印。重试耗尽后输出 `DISPATCH_REQUIRED / gh_pr_view_transient_failed`（需要外部进展 / 临时查看失败），details（详情）包含 transient category（临时失败类别）、retry count（重试次数）和 next command（下一步命令）。

2. checks（检查）等待直接复用 `wait_for_checks`（等待检查）。

   `merge_pr`（合并拉取请求）仍负责识别 `ruleset_merge_blocking`（规则集阻塞）。生命周期入口捕获后重新读取 PR（拉取请求），调用现有 `wait_for_checks(project, pr, wait_config_from_config(config))`（等待检查）。如果等待返回 stop state（停止状态），原样停止；只有 checks（检查）已不再 pending（等待中）时才按原合并逻辑重试。

3. 已有正文只追加缺失 `Fixes #...`（关闭引用）。

   通过现有 `strip_html_comments`（去掉注释）判断正文非空后，检查调用方给出的 `Fixes #...` 是否已存在。已存在则继续；缺失则调用现有 `update_pr_body`（更新正文）追加缺失行。若已有 `Closing References`（关闭引用）章节，追加到该章节；否则在正文末尾追加最小 `Closing References`（关闭引用）章节。

4. `evidencePath`（审查证据路径）只提示废弃。

   `validate_config`（校验配置）输出 warning（警告），运行时继续忽略该字段，不读取本地证据。

## Risks / Trade-offs

- [Risk] 只读查询重试可能掩盖短暂 GitHub（代码托管平台）不稳定。Mitigation: 重试次数有界，最终失败仍写入 details（详情）。
- [Risk] 自动追加 closing references（关闭引用）会编辑已有正文。Mitigation: 只追加缺失 `Fixes #...` 行，不改已有内容。
- [Risk] 合并失败后再次等待会延长命令运行时间。Mitigation: 完全复用已有 `defaults.wait`（默认等待配置），不引入第二套等待规则。
