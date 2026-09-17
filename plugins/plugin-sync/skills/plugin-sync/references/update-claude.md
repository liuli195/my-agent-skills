# Claude Update（Claude 更新）

MySpec（自有规格）不适用本通用更新；只有满足主 Skill（技能）的一次性显式例外时，才可执行用户点名的精确原生操作。

Run this only after explicit user authorization.

## Target（目标）

复用检查阶段已解析的 `<claude-target>`（Claude 目标）。未执行检查时，先运行检查流程；刷新、更新和复查不得重新定位客户端。

## Order（顺序）

1. Confirm marketplace（插件市场） and Plugin（插件） names.
2. Refresh marketplace snapshot（刷新市场快照）:

```powershell
<claude-target> plugin marketplace update <marketplace>
```

3. Update installed stale Plugin（过期插件） one by one. Do not run these in parallel:

```powershell
<claude-target> plugin update <plugin>@<marketplace>
```

4. Install missing Plugin（缺失插件） only if the user authorized install（安装）:

```powershell
<claude-target> plugin install <plugin>@<marketplace>
```

5. Enable disabled Plugin（未启用插件） only if the user authorized enable（启用）:

```powershell
<claude-target> plugin enable <plugin>@<marketplace>
```

6. Re-check state:

```powershell
<claude-target> plugin list --json
```

## Skill Root（技能根目录）

Junction（目录联接）形态的条目不走市场命令。仅在用户显式授权后处理，逐条执行：

1. 记录当前 `LinkType`（链接类型）与 `Target`（目标）。
2. 用 `[System.IO.Directory]::Delete($path, $false)` 删除旧条目本身，只删链接，目标内容原样保留。
3. 建立一级 junction（目录联接）:

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\<name>" -Target "<repo>\plugins\<plugin>\skills\<skill>"
```

4. 复查 `Target`（目标）等于仓库路径，且该条目下的 `SKILL.md` 可读。

## Notes（注意）

- Always use `plugin@marketplace`（插件@市场） for this marketplace（插件市场） to avoid ambiguous short names.
- Sequential update（顺序更新） avoids shared marketplace cache（共享市场缓存） contention such as `EBUSY`（目录占用）.
- Claude（代码代理） usually requires restart（重启） after Plugin（插件） update.
- Do not uninstall/remove（卸载/移除） unless explicitly requested.
