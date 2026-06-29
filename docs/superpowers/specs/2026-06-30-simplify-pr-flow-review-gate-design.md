---
comet_change: simplify-pr-flow-review-gate
role: technical-design
canonical_spec: openspec
---

# Simplify PR Flow Review Gate

## Context

`PR Flow`（拉取请求流程）当前声明四种 review gate（审查门禁）模式：`github`（GitHub 审查）、`local`（本地）、`dual`（双重）和 `skip`（跳过）。

`local`（本地）和 `dual`（双重）依赖旧的 `.pr-flow/review-pass.json`（审查通过文件）和 `diff_fingerprint`（差异指纹）契约。当前 `cross-agent-review`（跨代理审查）已经改为写 Guard evidence（守卫证据）路径，字段也不匹配，因此这两种模式保留了配置入口但不能形成完整可用流程。

## Confirmed Design

采用方案 A：删除 `local`（本地）和 `dual`（双重）运行分支，只保留 `github`（GitHub 审查）和 `skip`（跳过）。

`pr-flow-init`（初始化）不新增问题，继续使用 branch protection（分支保护）问题派生模式：

- 选择一个或多个 protected branch（受保护分支）：写入 `defaults.reviewGate.mode: github`。
- 选择暂不配置远端保护：写入 `defaults.reviewGate.mode: skip`。

`validate`（校验）只接受 `github`（GitHub 审查）和 `skip`（跳过）。`local`（本地）、`dual`（双重）和其他值都报 unsupported（不支持）。

`complete`（收尾）只处理两种模式：

- `github`（GitHub 审查）：继续读取 PR（拉取请求）的 `reviewDecision`（审查结论），在 `CHANGES_REQUESTED`（要求修改）或 `REVIEW_REQUIRED`（需要审查）时阻止合并。
- `skip`（跳过）：跳过 review gate（审查门禁），只依赖 checks（检查）和后续合并约束。

## Implementation Notes

删除 `pr_flow.py`（拉取请求流程脚本）里的本地 evidence（证据）读取和比较函数，避免保留不可达逻辑。

更新 `pr-flow-init`（初始化）参考文档时，只改 branch protection（分支保护）的选择后果和配置草案规则，不新增单独问答步骤。

测试侧删除本地 evidence（证据）通过/过期测试，改为覆盖：

- `validate`（校验）接受 `github`（GitHub 审查）和 `skip`（跳过）。
- `validate`（校验）拒绝 `local`（本地）和 `dual`（双重）。
- `complete`（收尾）在 `skip`（跳过）时忽略 `CHANGES_REQUESTED`（要求修改）。
- `complete`（收尾）在 `github`（GitHub 审查）时继续阻止 `CHANGES_REQUESTED`（要求修改）。
- init（初始化）文档明确保护分支派生 `github`（GitHub 审查），暂不保护派生 `skip`（跳过）。

## Risks

已配置 `local`（本地）或 `dual`（双重）的仓库会在新校验下失败。迁移路径是改为 `github`（GitHub 审查）或 `skip`（跳过）。

如果未来确实需要本地审查门禁，应重新设计一条完整证据契约，而不是恢复当前旧的 `.pr-flow/review-pass.json`（审查通过文件）路径。

## Verification

聚焦验证：

- `pytest tests/test_pr_flow_cli.py`（测试 PR Flow 命令行）。
- `openspec validate simplify-pr-flow-review-gate --strict`（严格校验 OpenSpec 变更）。

完整验证由后续 verify（验证）阶段决定是否运行。
