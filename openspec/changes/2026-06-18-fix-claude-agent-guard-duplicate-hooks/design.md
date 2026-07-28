## Root Cause

Claude 当前会自动加载插件包内的标准 `hooks/hooks.json`。Agent Guard Claude manifest 同时声明 `"hooks": "./hooks/hooks.json"`，使 Claude 解析到已经自动加载过的同一个文件并报 `Duplicate hooks file detected`。

Codex 当前表现不同：`codex plugin list` 能正常加载 `agent-guard@my-agent-skills-marketplace` 0.1.3，`codex doctor` 没有 hook 加载失败，`~/.codex/config.toml` 只记录同一个 hooks 文件下的两个事件 trust state。因此本次只调整 Claude manifest。

## Fix

删除 `plugins/agent-guard/.claude-plugin/plugin.json` 中的 `hooks` 字段。

保留：

- `plugins/agent-guard/.codex-plugin/plugin.json` 的 `hooks` 字段。
- `plugins/agent-guard/hooks/hooks.json` 文件。
- hook command 和 runtime router 行为。

## Test Strategy

- 先更新 package 测试，要求 Codex manifest 继续声明 `./hooks/hooks.json`，Claude manifest 不声明标准 hooks 文件。
- 运行该测试确认当前 0.1.3 行为失败。
- 修改 Claude manifest 后确认测试通过。
- 运行 release-flow 相关回归、OpenSpec specs strict validation 和 diff 检查。

## Spec Delta

更新 `agent-guard-plugin-runtime` 的固定生命周期钩子集合要求，补充平台 manifest 差异：Codex manifest 继续声明 `./hooks/hooks.json`，Claude manifest 不声明标准 hooks 文件，由 Claude 自动加载。
