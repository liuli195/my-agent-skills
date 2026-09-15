# Codex Update（Codex 更新）

MySpec（自有规格）不适用本通用更新；只有满足主 Skill（技能）的一次性显式例外时，才可执行用户点名的精确原生操作。

Run this only after explicit user authorization.

## Target（目标）

复用检查阶段已解析的 `<codex-target>`（Codex 目标）。未执行检查时，先运行检查流程；刷新、更新和复查不得重新定位客户端。

## Order（顺序）

1. Confirm marketplace（插件市场） and Plugin（插件） names.
2. Refresh marketplace snapshot（刷新市场快照）:

```powershell
<codex-target> plugin marketplace upgrade <marketplace> --json
```

3. For each missing or stale Plugin（缺失或过期插件）, install/update with `add`（添加）:

```powershell
<codex-target> plugin add <plugin>@<marketplace> --json
```

4. Re-check state:

```powershell
<codex-target> plugin list --marketplace <marketplace> --available --json
```

## Notes（注意）

- `add`（添加） is the Codex（代码代理） path for install/update from a configured marketplace snapshot（已配置市场快照）.
- Do not remove（移除） any Plugin（插件） unless explicitly requested.
- Current Codex（代码代理） sessions may need a new session before newly loaded Skill（技能） or Plugin（插件） content is visible.
