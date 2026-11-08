## Why

`PR Flow`（拉取请求流程）的 `local`（本地）和 `dual`（双重）review gate（审查门禁）已经和当前 `cross-agent-review`（跨代理审查）证据输出契约不一致，导致本地门禁路径看似可配置但实际难以跑通。

本次变更把 review gate（审查门禁）收敛为 `github`（GitHub 审查）和 `skip`（跳过），避免保留不可用分支，同时让 init（初始化）继续从 branch protection（分支保护）选择中自动派生默认模式。

## What Changes

- 移除 `local`（本地）和 `dual`（双重）review gate（审查门禁）模式支持。
- `validate`（校验）只接受 `github`（GitHub 审查）和 `skip`（跳过）。
- `complete`（收尾）只执行 `github`（GitHub 审查）或 `skip`（跳过）门禁逻辑，不再读取本地 review evidence（审查证据）。
- `pr-flow-init`（初始化）问答不新增问题：选择一个或多个 protected branch（受保护分支）时派生 `defaults.reviewGate.mode: github`；选择暂不配置远端保护时派生 `defaults.reviewGate.mode: skip`。
- 删除 `.pr-flow/review-pass.json`（审查通过文件）和 `evidencePath`（证据路径）作为 PR Flow（拉取请求流程）本地门禁契约。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `pr-flow-plugin`: 简化 review gate（审查门禁）模式和 init（初始化）派生规则。

## Impact

- 影响 `plugins/pr-flow`（拉取请求流程插件）脚本、`pr-flow-init`（初始化）参考文档、相关测试和 `pr-flow-plugin`（拉取请求流程插件）规格。
- 不改 `cross-agent-review`（跨代理审查）输出契约。
- 不引入新依赖或新远端 GitHub API（GitHub 接口）调用。
