## Why

Issue #127 暴露了 release-flow（发布流程）CLI（命令行接口）对重复 `--bump-plugins` 的处理不符合常见命令习惯：`argparse`（参数解析器）静默保留最后一次参数。

用户重复传多个插件时，前面的插件被丢弃，后续 preflight（发布前检查）会误报 `plugin_requires_bump`，问题可绕过但提示不直接。

## What Changes

- 让 `preflight`（发布前检查）、`publish`（发布）和 `ci-publish`（CI 发布）一致处理重复 `--bump-plugins`。
- 保留现有逗号分隔写法和 `--bump-plugins ""` 空列表语义。
- 重复参数合并为同一个 `bumpPlugins`（提升插件列表），不新增配置或依赖。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release-flow-plugin`: CLI（命令行接口）不得静默丢弃重复 `--bump-plugins` 值。

## Impact

- Affected code: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`.
- Affected tests: `tests/test_release_flow_cli.py`.
- Dependencies: none added.
