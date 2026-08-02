# Outcome

将本地 Pi（编码代理）主题扩展从 `pi-blue-mocha-theme` 更名为 `pi-my-theme`，让一个扩展同时提供两套蓝色主题。

# Scope

- 将目录 `plugins/pi-blue-mocha-theme` 更名为 `plugins/pi-my-theme`。
- 将扩展包名改为 `pi-my-theme`，并调整说明以覆盖多主题用途。
- 将当前无用户消息和工具背景色的 `blue-mocha` 主题更名为 `blue-nobkgd`。
- 新增 `blue-moch-new` 主题，配置恢复为提交 `abb118b` 之前的原始 `blue-mocha`：用户消息与三种工具状态背景均为 `mantle`，其余配置相同。
- 将 `C:\Users\liuli\.pi\agent\settings.json` 中本地扩展路径改为新目录。
- 将当前主题从 `blue-mocha` 更新为 `blue-nobkgd`，避免配置引用不存在的主题并保持当前无背景显示效果。

# Non-goals

- 不新增第三套主题。
- 不改变两套主题除名称及指定背景色之外的颜色。
- 不安装、发布或增加依赖。

# Acceptance examples

- Pi（编码代理）从 `plugins/pi-my-theme` 加载扩展时可发现 `blue-nobkgd` 与 `blue-moch-new` 两套主题。
- `blue-nobkgd` 的 `userMessageBg`、`toolPendingBg`、`toolSuccessBg`、`toolErrorBg` 均为空字符串；`customMessageBg` 暂时保留 `surface0`。
- `blue-moch-new` 的上述四项均为 `mantle`，其他配置与原始 `blue-mocha` 一致。
- 用户配置不再引用旧扩展路径或不存在的主题名。

# Constraints and invariants

- 保留用户明确指定的主题名 `blue-moch-new`，不自行修正为 `blue-mocha-new`。
- 目录名、包名和本地扩展路径统一为 `pi-my-theme`。
- 修改用户配置前保留其余设置不变。

# Decisions

- 扩展允许通过现有 `pi.themes: ["./themes"]` 目录加载机制包含多套主题，无需新增代码。
- `blue-moch-new` 以 Git（版本管理）中提交 `abb118b` 的父提交所保存配置为原始背景色基准。
- 当前 Pi（编码代理）主题切换为 `blue-nobkgd`，保持现有无用户消息和工具背景色的显示效果。
- `blue-nobkgd` 暂不修改 `customMessageBg`；上下文压缩摘要、分支摘要、技能调用及默认自定义消息继续使用 `surface0` 背景。
- `selectedBg` 保持 `surface0`，继续用于菜单和选中项高亮。
- 用户已确认按当前 brief 与完整目标规格实施。

# Open questions

无。

# Verification expectations

- 校验扩展清单与两份主题 JSON（数据文件）语法。
- 核对两套主题名称唯一、指定背景色符合要求、其余颜色与基准一致。
- 核对 Pi（编码代理）用户配置中的扩展路径和当前主题均指向有效的新名称。
- 通过仓库规定的 build-and-verify（构建与验证）入口执行覆盖本次改动的验证。
