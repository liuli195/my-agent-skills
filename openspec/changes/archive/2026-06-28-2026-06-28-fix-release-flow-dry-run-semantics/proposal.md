## Why

Release Flow（发布流程）的 dry-run（试运行）语义混用了三件事：本地发布记录、发布命令预览和发布后 marketplace（市场分支）漂移检查。

这导致三个用户可见问题：

- `release-init --dry-run`（发布初始化试运行）会写入本地 release plan（发布计划），但名称像是不落盘。
- `preflight --channel-tree`（发布前检查通道树）把旧 `marketplace`（市场分支）与待发布投影对比，误报正常待发布差异。
- `publish --dry-run`（发布试运行）输出两个 `tag`（标签）字段，含义分别是 release tag（发布标签）和 Git tag（Git 标签）创建状态。

## What Changes

- 删除 `release-init --dry-run`（发布初始化试运行）和 release plan（发布计划）里的 `dryRun`（试运行标记）。
- 删除 `ci-publish --dry-run`（持续集成发布试运行）和 `preflight --channel-tree`（发布前检查通道树）入口。
- 让 `preflight`（发布前检查）在临时目录中验证 projection（发布投影）可生成。
- 保留 `publish --dry-run`（发布试运行），只把输出字段改成明确名称。
- 同步 Release Flow（发布流程）OpenSpec（开放规格）合同。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `release-flow-plugin`（发布流程插件）：收紧 dry-run（试运行）语义，发布前检查不再阻断待发布市场差异。

## Impact

- `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- `tests/test_release_flow_cli.py`
- `openspec/specs/release-flow-plugin/spec.md`
