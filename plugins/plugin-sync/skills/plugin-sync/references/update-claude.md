# Claude Update（Claude 更新）

本通用更新覆盖选定市场的全部请求插件，包括附带命令工具的插件，不按插件名称排除。

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


## 开发来源的完整安装内容

目标市场使用构建产物作为来源时，首次安装或源码变化后先执行该仓库已声明的构建入口，使用本次核验的包内启动器，不从 PATH 换用全局实现。构建失败即停止；保留的旧产物不代表本次成功。市场仍使用原登记，不另建市场。

刷新后核对原生安装路径与本轮产物的实际内容及运行身份，版本号相同也不能跳过此核对。原生更新没有替换内容时，只对获准目标按原完整标识卸载/安装；保留原 scope、启用状态和持久数据，不使用 prune，不改其他插件。重新核对新会话发现及包内命令；任何失败先查实际状态，再按原完整来源恢复，不能手改缓存或用全局命令掩盖失败。

开发包的显式运行诊断必须核验构建来源及真实内容，只有可复现的已发布实现才输出原开发工具链身份；来源缺失、未发布或内容漂移时阻断 PR，不以相同版本号降格为正式包。普通开发命令仍可运行。活跃构建产物保留供后续安装，成功后清理暂存和已替代副本，失败恢复材料报告准确位置。
