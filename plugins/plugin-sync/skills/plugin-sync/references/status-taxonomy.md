# Status Taxonomy（状态分类）

Use these status（状态） names consistently.

## Marketplace（插件市场）

- `marketplace_not_subscribed`（未订阅市场）: the marketplace（插件市场） is not configured for Codex（代码代理） or Claude（代码代理）.
- `snapshot_missing`（快照缺失）: subscription（订阅） exists but local snapshot（本地快照） root is absent or unreadable.
- `snapshot_stale`（快照过期）: local snapshot（本地快照） revision or manifest（清单） is older than the expected source.
- `snapshot_current`（快照已最新）: local snapshot（本地快照） matches expected evidence.

## Plugin（插件）

- `plugin_not_installed`（插件未安装）: Plugin（插件） exists in marketplace（插件市场） but is not installed.
- `plugin_stale`（插件过期）: installed version（已安装版本） is older than snapshot（快照） or expected version（期望版本）.
- `plugin_current`（插件已最新）: installed version（已安装版本） matches snapshot（快照） or expected version（期望版本）.
- `plugin_disabled`（插件未启用）: Plugin（插件） is installed but disabled（未启用）.
- `restart_required`（需要重启）: update completed but client restart（客户端重启） or new session（新会话） is needed.

## Output Pattern（输出格式）

Use compact lines:

```text
status: plugin_stale
target: codex build-and-verify@my-agent-skills-marketplace
installed: 0.1.32
snapshot: 0.1.33
next: codex plugin add build-and-verify@my-agent-skills-marketplace --json
```

For authorized updates:

```text
updated: claude pr-flow@my-agent-skills-marketplace 0.1.33
restart: required
```
