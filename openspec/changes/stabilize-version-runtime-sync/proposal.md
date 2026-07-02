## Why

插件版本事实曾因测试中维护第二份硬编码版本而反复回归；build-and-verify（构建与验证）runtime（运行时）发布后也可能和目标仓库快照脱节。需要锁住版本来源，并把 runtime（运行时）同步作为流程闭环，而不是用普通测试强制所有中间态永远一致。

## What Changes

- 禁止仓库测试新增真实 `0.1.x` 版本常量，版本断言必须读取 manifest（清单）或 runtime（运行时）文件。
- 保持 Codex（编码助手）和 Claude（编码助手）manifest（清单）版本一致性检查。
- Release Flow（发布流程）在发布前发现 build-and-verify（构建与验证）runtime（运行时）未同步时输出 `runtime_update_required`，阻止发布并给出更新命令。
- build/verify（构建/验证）发现 runtime（运行时）落后时继续只提示，不自动修改文件。
- plugin-sync（插件同步）负责目标仓库 runtime（运行时）检查、授权更新、更新后 diff（变更）提示 PR Flow（拉取请求流程）。

## Capabilities

### New Capabilities

- `plugin-sync-runtime-sync`: Plugin Sync（插件同步）对 build-and-verify（构建与验证）runtime（运行时）快照的检查、授权更新和 PR Flow（拉取请求流程）提示闭环。

### Modified Capabilities

- `local-plugin-build-checks`: 仓库测试必须防止第二份真实插件版本常量。
- `release-flow-plugin`: 发布前必须检查 build-and-verify（构建与验证）runtime（运行时）同步状态。
- `test-framework-plugin`: build/verify（构建/验证）继续只提示 runtime（运行时）落后，不自动改文件。

## Impact

- 影响版本一致性测试、Release Flow preflight（发布预检）、build-and-verify（构建与验证）runtime（运行时）提示契约。
- plugin-sync（插件同步）源码当前不在本仓库内，实施前需要确认修改用户级 skill（技能）路径或另建仓库内承载位置。
- 不新增版本注册中心。
- 不要求普通开发中间态 runtime（运行时）永远等于 manifest（清单）。
