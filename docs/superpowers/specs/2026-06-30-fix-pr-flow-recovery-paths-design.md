---
comet_change: fix-pr-flow-recovery-paths
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-30-fix-pr-flow-recovery-paths
status: final
---

# Fix PR Flow Recovery Paths

## Context

PR Flow（拉取请求流程）现有实现已经偏保守，但四个可恢复场景缺少直接恢复路径：`gh pr view`（查看拉取请求）偶发 EOF（连接提前结束）、checks（检查）仍运行时 merge（合并）被规则集挡住、旧 `evidencePath`（审查证据路径）残留无提示、已有 PR body（拉取请求正文）与 `--fixes`（关闭引用参数）重复时被迫停止。

## Confirmed Design

使用现有脚本能力做最小修复：

- 只读 `gh pr view`（查看拉取请求）增加有界重试，默认次数用常量，允许环境变量覆盖。重试期间不打印 stop state（停止状态）；重试耗尽后输出 `DISPATCH_REQUIRED / gh_pr_view_transient_failed`（需要外部进展 / 临时查看失败）。
- `ruleset_merge_blocking`（规则集阻塞）后重新读取 PR（拉取请求），复用 `wait_for_checks`（等待检查）和 `wait_config_from_config`（读取等待配置）。如果等待返回 stop state（停止状态），原样停止；只有 checks（检查）不再 pending（等待中）时才重试 merge（合并）。
- 已有正文下，`--fixes`（关闭引用参数）对应的 `Fixes #...`（关闭引用）已存在则继续；缺失则只追加缺失行。优先追加到现有 `Closing References`（关闭引用）章节，否则在末尾追加最小章节。
- `validate_config`（校验配置）发现 `defaults.reviewGate.evidencePath`（审查证据路径）时输出 warning（警告），运行时继续忽略。

## Non-Goals

- 不新增依赖。
- 不新增 `.pr-flow/config.yaml`（配置文件）字段。
- 不启用 GitHub auto-merge（自动合并）。
- 不恢复 local/dual review gate（本地/双重审查门禁）。

## Verification

- 聚焦测试：`python -m pytest tests/test_pr_flow_cli.py -k "transient or ruleset or evidencePath or existing_human_body" -q`
- 完整 PR Flow（拉取请求流程）测试：`python -m pytest tests/test_pr_flow_cli.py -q`
- 规格校验：`openspec validate fix-pr-flow-recovery-paths --strict`
