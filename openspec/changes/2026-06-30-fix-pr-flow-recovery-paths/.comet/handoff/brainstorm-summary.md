# Brainstorm Summary

- Change: fix-pr-flow-recovery-paths
- Date: 2026-06-30

## 确认的技术方案

- `gh pr view`（查看拉取请求）只读查询增加有界 transient（临时失败）重试，默认次数用脚本常量，允许环境变量轻量覆盖，不写入配置文件。
- `ruleset_merge_blocking`（规则集阻塞）后复用现有 `wait_for_checks`（等待检查），超时和轮询间隔都复用 `defaults.wait`（默认等待配置）。
- 已有 PR body（拉取请求正文）收到 `--fixes`（关闭引用参数）时，已包含全部引用就继续，缺失则只追加缺失 `Fixes #...`（关闭引用）。
- `defaults.reviewGate.evidencePath`（审查证据路径）只输出废弃 warning（警告），不恢复 local review gate（本地审查门禁）。
- EOF（连接提前结束）重试耗尽后输出 `DISPATCH_REQUIRED / gh_pr_view_transient_failed`（需要外部进展 / 临时查看失败）。
- 规则集阻塞后等待 checks（检查）时，若 `wait_for_checks`（等待检查）返回 stop state（停止状态），原样停止，不重试 merge（合并）。

## 关键取舍与风险

- 不新增依赖，不新增配置 schema（配置结构）。
- 不包住有副作用的 GitHub（代码托管平台）命令，避免重复创建、编辑或合并。
- 自动追加正文只允许追加缺失 closing references（关闭引用），不改写人工正文。

## 测试策略

- 先添加失败测试覆盖 EOF（连接提前结束）重试、规则集阻塞后等待、废弃配置 warning（警告）、已有正文追加 `Fixes #...`（关闭引用）。
- 再用最小实现让测试通过。
- 最后运行聚焦测试和 `openspec validate`（开放规格校验）。

## Spec Patch

已回写 `openspec/changes/fix-pr-flow-recovery-paths/specs/pr-flow-plugin/spec.md`（拉取请求流程插件增量规格），并补充 EOF（连接提前结束）耗尽状态、checks（检查）等待阻断处理和 closing references（关闭引用）追加位置。
