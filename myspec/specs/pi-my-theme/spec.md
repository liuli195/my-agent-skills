# Pi My Theme

## Purpose

本 capability（能力）定义 `pi-my-theme` 本地 Pi（编码代理）主题扩展提供的两套主题及其用户可见背景色行为。

## Requirements

### Requirement: Pi My Theme 扩展身份

系统 MUST 以 `pi-my-theme` 名称加载本地主题扩展，并通过 Pi（编码代理）原生主题加载方式公开扩展中的所有主题。

#### Scenario: Pi 加载主题扩展

- **WHEN** Pi（编码代理）从用户配置的本地扩展路径加载 `pi-my-theme`
- **THEN** 可用主题列表包含该扩展公开的 `blue-nobkgd` 和 `blue-moch-new`
### Requirement: 无消息块背景主题

`blue-nobkgd` 主题 MUST 不显示用户消息及工具等待、成功和失败消息块背景，同时保留自定义消息与选中项背景。

#### Scenario: 显示普通消息和工具状态

- **WHEN** 用户启用 `blue-nobkgd` 并显示用户消息或工具等待、成功、失败状态
- **THEN** 对应消息块不显示背景色

#### Scenario: 显示自定义消息和选中项

- **WHEN** 用户启用 `blue-nobkgd` 并显示上下文压缩摘要、分支摘要、技能调用、默认自定义消息或菜单选中项
- **THEN** 自定义消息和选中项继续使用 `surface0` 背景
### Requirement: 原始消息块背景主题

`blue-moch-new` 主题 MUST 保留原始 `blue-mocha` 的配色，并为用户消息及工具等待、成功和失败消息块使用 `mantle` 背景。

#### Scenario: 显示普通消息和工具状态

- **WHEN** 用户启用 `blue-moch-new` 并显示用户消息或工具等待、成功、失败状态
- **THEN** 对应消息块使用 `mantle` 背景
### Requirement: 当前主题配置有效

用户配置 MUST 引用存在的 `pi-my-theme` 扩展路径和 `blue-nobkgd` 主题，不得继续引用已更名的 `blue-mocha`。

#### Scenario: Pi 启动并读取用户配置

- **WHEN** Pi（编码代理）读取当前扩展路径和主题配置
- **THEN** `pi-my-theme` 能够加载，且当前主题解析为 `blue-nobkgd`
