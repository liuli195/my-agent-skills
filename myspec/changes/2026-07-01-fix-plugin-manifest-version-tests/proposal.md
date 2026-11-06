## Why

`pr-flow`（拉取请求流程）和 `build-and-verify`（构建与验证）插件测试各自维护第二份 manifest version（清单版本）常量。版本提升时真实 manifest（清单）已更新，但测试常量容易漏改，导致 Full Verify（完整验证）失败。

## What Changes

- `pr-flow`（拉取请求流程）manifest（清单）测试读取真实 Codex（代码助手）和 Claude（代码助手）manifest（清单），断言两份 version（版本）一致。
- `build-and-verify`（构建与验证）manifest（清单）测试使用同样模式。
- 删除测试里的第二份 `PLUGIN_VERSION`（插件版本）常量。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-plugin-build-checks`: local plugin package tests（本地插件包测试） must not duplicate manifest version（清单版本） source of truth（唯一来源）.

## Impact

- Affected tests（受影响测试）: `tests/test_pr_flow_plugin_package.py`, `tests/test_build_and_verify_plugin.py`
- No production code（产品代码） change.
- No spec（规格） behavior change.
- No new dependency（新依赖）.
