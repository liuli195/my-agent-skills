## Context

当前 `PR Flow`（拉取请求流程）同时声明 `github`（GitHub 审查）、`local`（本地）、`dual`（双重）和 `skip`（跳过）四种 review gate（审查门禁）模式。

`local`（本地）和 `dual`（双重）依赖 `.pr-flow/review-pass.json`（审查通过文件）与 `diff_fingerprint`（差异指纹），但当前 `cross-agent-review`（跨代理审查）实际输出已经转为 Guard evidence（守卫证据）路径，字段也不匹配。保留这两种模式会让配置看似可用，实际阻断收尾流程。

## Goals / Non-Goals

**Goals:**
- 只保留 `github`（GitHub 审查）和 `skip`（跳过）review gate（审查门禁）模式。
- 让 `validate`（校验）尽早拒绝 `local`（本地）和 `dual`（双重）。
- 让 `complete`（收尾）不再读取本地 review evidence（审查证据）。
- 让 `pr-flow-init`（初始化）继续通过 branch protection（分支保护）选择派生模式：保护分支为 `github`，暂不保护为 `skip`。

**Non-Goals:**
- 不修复或桥接 `cross-agent-review`（跨代理审查）到 PR Flow（拉取请求流程）的本地 evidence（证据）。
- 不新增 init（初始化）问答问题。
- 不改变 checks（检查）等待与失败判定。
- 不调用 GitHub API（GitHub 接口）写入远端设置。

## Decisions

1. 删除本地 evidence（证据）分支，而不是修复路径。

   `local`（本地）和 `dual`（双重）需要跨 `pr-flow`（拉取请求流程）、`cross-agent-review`（跨代理审查）和 Guard evidence（守卫证据）统一契约。当前需求只需要保留有用门禁，删除不可用分支是更小的修复。

2. 初始化不新增问题。

   继续复用 branch protection（分支保护）问题：选择保护分支表示远端 PR（拉取请求）规则参与合并控制，派生 `github`（GitHub 审查）；选择暂不配置远端保护，派生 `skip`（跳过）。这样不增加用户问答负担。

3. `evidencePath`（证据路径）不再作为运行配置。

   配置中若仍出现 `evidencePath`（证据路径），运行时忽略；后续 init（初始化）草案不再写入它。`reviewGate.mode`（审查门禁模式）只接受 `github`（GitHub 审查）和 `skip`（跳过）。

## Risks / Trade-offs

- [Risk] 已配置 `local`（本地）或 `dual`（双重）的仓库升级后会校验失败。Mitigation: `validate`（校验）给出明确 unsupported（不支持）错误，用户改为 `github`（GitHub 审查）或 `skip`（跳过）。
- [Risk] 删除本地门禁降低可扩展性。Mitigation: 后续如真的需要本地门禁，应重新设计一条完整证据契约，而不是保留当前半连接状态。
