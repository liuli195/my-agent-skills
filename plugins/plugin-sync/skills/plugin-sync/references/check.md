# Check Flow（检查流程）

MySpec（自有规格）不适用本通用检查；除主 Skill（技能）的一次性显式例外要求保存和复查精确目标状态外，只委托 `myspec doctor --all` 或对应单 Agent（代理）命令。

This flow is read-only（只读）. It must not refresh（刷新）, update（更新）, install（安装）, enable（启用）, remove（移除）, or delete（删除） anything.

## Inputs（输入）

- marketplace（插件市场） name, default `my-agent-skills-marketplace`.
- Plugin（插件） names, default all installed plugins from that marketplace（插件市场）.
- Optional repository path if remote marketplace（远端市场） comparison is needed.

## Client Target（客户端目标）

按主 Skill（技能）的 Client Target（客户端目标）规则定位 Codex（代码代理）和 Claude（代码代理）。同一客户端的所有检查复用该目标；输出程序路径、来源及客户端返回的市场目录或安装路径。

下文的 `<codex-target>`（Codex 目标）和 `<claude-target>`（Claude 目标）表示已解析的客户端调用，不得重新从当前会话定位。

## Codex（代码代理） Checks（检查）

1. Check marketplace subscription（市场订阅）:

```powershell
<codex-target> plugin marketplace list --json
```

2. Check installed and available Plugin（插件） state for the marketplace（插件市场）:

```powershell
<codex-target> plugin list --marketplace <marketplace> --available --json
```

3. If the marketplace root（市场目录） is reported, inspect snapshot metadata（快照元数据） only if the file exists:

```text
<marketplace-root>/.codex-marketplace-install.json
```

4. If needed, inspect local snapshot manifest（本地快照清单） versions:

```text
<marketplace-root>/plugins/<plugin>/.codex-plugin/plugin.json
```

## Claude（代码代理） Checks（检查）

1. Check marketplace subscription（市场订阅）:

```powershell
<claude-target> plugin marketplace list
```

2. Check installed Plugin（已安装插件） state:

```powershell
<claude-target> plugin list --json
```

3. Use `--available --json` only when installed state is not enough; the output can be large:

```powershell
<claude-target> plugin list --available --json
```

4. If needed, inspect local snapshot manifest（本地快照清单） versions:

```text
<marketplace-root>/plugins/<plugin>/.claude-plugin/plugin.json
```

## Skill Root（技能根目录） Checks（检查）

Junction（目录联接）形态的 Plugin（插件）不出现于市场命令的输出，必须单独列技能根目录核对。对每个客户端运行一次：

```powershell
Get-ChildItem "$env:USERPROFILE\.agents\skills" -Force | Select-Object Name, LinkType, @{n='Target';e={$_.Target -join ';'}}
Get-ChildItem "$env:USERPROFILE\.claude\skills" -Force | Select-Object Name, LinkType, @{n='Target';e={$_.Target -join ';'}}
```

判定每条：

- `LinkType` 为空的是第三方真实目录，不属于本仓库，跳过。
- `Target` 等于 `<repo>/plugins/<plugin>/skills/<skill>` → `skill_link_current`。
- `Target` 落在另一个技能根目录下 → `skill_link_chained`，报出中间那一跳。
- 条目只在一个客户端出现 → `skill_link_missing`，报出缺失端。
- 对每条 `skill_link_current`，确认 `<root>/<name>/SKILL.md` 可读，确认联接没有指向已被删除的目标。

`realpath`（真实路径）会一路解析到仓库，看不出层级；只有客户端的链接视图（`LinkType` 与 `Target`）能给出真实跳数。

## Remote（远端） Check（检查）

If a repository path is available and remote comparison is useful, prefer no-write remote checks:

```powershell
git -C <repo> ls-remote origin refs/heads/marketplace
```

Do not fetch（拉取远端引用） unless the user authorizes a local Git（版本管理） metadata update or the repository already has the needed ref.

## Result（结果）

Classify each Plugin（插件） with `status-taxonomy.md`. If update is needed, report the exact command as a suggested next step, but do not run it without authorization.
