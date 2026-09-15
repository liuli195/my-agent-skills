# pi-my-theme 完整目标规格

## 目标

仓库提供名为 `pi-my-theme` 的本地 Pi（编码代理）主题扩展，并由同一个扩展公开两套主题。

## 扩展身份与加载

- 扩展目录必须为 `plugins/pi-my-theme`。
- `package.json` 的包名必须为 `pi-my-theme`。
- 扩展必须继续使用 Pi（编码代理）原生主题目录加载方式公开 `themes` 目录内的所有主题。
- Pi（编码代理）用户配置的本地包路径必须指向 `D:\My Project\my-agent-skills\plugins\pi-my-theme`。

## 主题

### blue-nobkgd

- 名称必须为 `blue-nobkgd`。
- 配置以当前 `blue-mocha` 为基准。
- `userMessageBg`、`toolPendingBg`、`toolSuccessBg`、`toolErrorBg` 必须为空字符串。
- `customMessageBg` 必须保留 `surface0`；上下文压缩摘要、分支摘要、技能调用和默认自定义消息继续显示背景。
- `selectedBg` 必须保留 `surface0`，用于菜单和选中项高亮，不视为消息块背景。
- 其他颜色保持当前值。

### blue-moch-new

- 名称必须严格为用户指定的 `blue-moch-new`。
- 配置必须与提交 `abb118b` 的父提交中的原始 `blue-mocha` 相同，仅名称不同。
- `userMessageBg`、`toolPendingBg`、`toolSuccessBg`、`toolErrorBg` 必须为 `mantle`。

## 用户配置

- 当前主题必须从更名后不存在的 `blue-mocha` 切换为 `blue-nobkgd`，保持当前无用户消息和工具背景色的显示效果。
- 除扩展路径和当前主题外，不改变用户配置。

## 验收

1. 扩展路径、包名和用户配置路径均使用 `pi-my-theme`。
2. 两份主题文件可解析，名称分别为 `blue-nobkgd` 与 `blue-moch-new`。
3. 两套主题仅在名称及指定背景色上存在预期差异。
4. 用户配置引用存在的扩展路径和主题名。
