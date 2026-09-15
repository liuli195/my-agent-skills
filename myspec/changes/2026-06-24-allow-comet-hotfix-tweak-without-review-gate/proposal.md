## Why

当前 Comet review gate（Comet 审查门禁）会拦截所有 `build -> verify`（构建到验证）推进命令，导致 hotfix（热修复）和 tweak（小改）流程也必须产出 cross-agent-review（跨代理审查）通过标记。

hotfix（热修复）和 tweak（小改）流程本身是轻量路径，不应被该跨代理审查门禁阻断。

## What Changes

- 为 Global Command Guard（全局命令守卫）增加声明式 `skip_when`（跳过条件）配置。
- 更新内置 `comet-review-gate`（Comet 审查门禁）画像，让 `workflow: hotfix` 和 `workflow: tweak` 时跳过 cross-agent-review（跨代理审查）检查。
- 保持 full（完整）Comet 流程在缺少有效 pass marker（通过标记）时继续被阻断。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `agent-guard-plugin-runtime`: Global Command Guard（全局命令守卫）支持声明式跳过条件。
- `comet-agent-review-gate`: Comet review gate（Comet 审查门禁）仅要求 full（完整）流程提供 cross-agent-review（跨代理审查）通过标记。

## Impact

- 影响 `plugins/agent-guard/scripts/guard_runtime/global_command_guards.py`。
- 影响 Agent Guard（代理守卫）画像校验器和 `comet-review-gate`（Comet 审查门禁）模板。
- 影响用户级 `C:\Users\liuli\.agents\guards\comet-review-gate` 配置同步。
