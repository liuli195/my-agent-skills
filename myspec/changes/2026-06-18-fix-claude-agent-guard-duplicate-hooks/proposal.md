## Why

Claude 安装 `agent-guard` 0.1.3 后报错：`.claude-plugin/plugin.json` 显式声明 `./hooks/hooks.json`，而 Claude 会自动加载标准 `hooks/hooks.json`，导致同一个 hooks 文件被重复加载。

## What Changes

- 从 Agent Guard Claude manifest 中移除 `hooks` 字段，避免重复声明标准 hooks 文件。
- 保留 Codex manifest 的 `hooks` 字段；Codex 0.140.0 当前需要并接受该字段。
- 保留 `plugins/agent-guard/hooks/hooks.json`，插件包仍提供 `SessionStart` 和 `PreToolUse` lifecycle hooks。
- 补 package 测试，固定 Codex/Claude manifest 的平台差异。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `agent-guard-plugin-runtime`: 明确 Codex 和 Claude manifest 对标准 hooks 文件的声明差异，避免 Claude 重复加载。

## Impact

- 影响 `plugins/agent-guard/.claude-plugin/plugin.json`。
- 影响 `tests/test_agent_guard_plugin_package.py`。
- 不改变 runtime、hook router、hook payload 或 marketplace catalog 语义。
