## Why

PR Flow（拉取请求流程）的 `tweak`（小改）理论上应与 `complete`（收尾）共用完整 PR lifecycle（拉取请求生命周期），唯一差异是跳过 review gate（审查门禁）。当前实现让 `tweak`（小改）在未推送分支上走旧的 `PUSH_REQUIRED`（需要推送）路径，且 ruleset（规则集）阻塞时不能复用 GitHub CLI（GitHub 命令行）的 `--auto`（自动合并）能力，导致用户执行机械命令。

## What Changes

- 让 `tweak`（小改）复用 `complete`（收尾）已有 safe auto-push（安全自动推送）能力。
- 保留 `tweak`（小改）唯一差异：`skip_review_gate=True`（跳过审查门禁）。
- 在 GitHub CLI（GitHub 命令行）明确建议 `--auto`（自动合并）时，复用现有 merge（合并）命令追加 `--auto`（自动合并）重试一次。
- 不新增依赖、不新增配置字段、不使用 `--admin`（管理员绕过）。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-flow-plugin`: 调整 `tweak`（小改）与 `complete`（收尾）的生命周期一致性，并明确 ruleset（规则集）阻塞下的 `--auto`（自动合并）恢复路径。

## Impact

- 代码：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- 测试：`tests/test_pr_flow_cli.py`
- 规格：`openspec/specs/pr-flow-plugin/spec.md`
- 依赖：无新增
