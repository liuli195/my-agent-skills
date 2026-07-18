## Why

Release Flow（发布流程）当前只确认本地 manifest（清单）已经提升版本，却没有确认远端 `main`（主干分支）已经通过 PR（拉取请求）拿到同一版本。实际发布时维护者会被引导去直推 `main`（主干分支），然后被 GitHub Rulesets（GitHub 规则集）拦下。

## What Changes

- 扩展现有 `preflight`（发布前检查），在同一检查链路里确认配置的 `sourceRef`（源引用）包含本次 `bumpPlugins`（提升插件列表）的目标版本。
- 当远端 `sourceRef`（源引用）缺少版本提升时，失败并提示先通过 PR（拉取请求）合入版本提交。
- 不新增 Release Flow（发布流程）的 PR（拉取请求）创建能力，不新增 hotfix（热修复）直写能力，不新增依赖。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release-flow-plugin`: `preflight`（发布前检查）必须阻止本地版本提升尚未进入远端 `sourceRef`（源引用）的发布。

## Impact

- `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- `tests/test_release_flow_cli.py`
- `openspec/specs/release-flow-plugin/spec.md`
