# plugin-sync-runtime-sync Specification

## Purpose

TBD - created by archiving change stabilize-version-runtime-sync. Update Purpose after archive.

## Requirements

### Requirement: Plugin Sync delegates MySpec lifecycle management

Plugin Sync（插件同步）MUST 将 MySpec（自有规格）的初始化、诊断、机器级模式切换和更新委托给 `myspec` CLI（命令行程序），不得复制 MySpec 的路径、市场、模式或版本规则。

#### Scenario: 用户通过 Plugin Sync 管理 MySpec

- **WHEN** 用户要求 Plugin Sync 检查、初始化、切换或更新 MySpec
- **THEN** Plugin Sync MUST 调用适用的 `myspec init`、`myspec doctor` 或 `myspec update`
- **THEN** Plugin Sync MUST NOT 自行推断 MySpec 的包路径、客户端市场、模式或目标版本
### Requirement: Plugin Sync delegates Build and Verify lifecycle management
Plugin Sync（插件同步）MUST 将 Build and Verify（构建与验证）的诊断、初始化和更新委托给 `build-and-verify` CLI（命令行程序），不得维护或同步目标仓库的运行时快照。

#### Scenario: 用户通过 Plugin Sync 管理 Build and Verify
- **WHEN** 用户要求 Plugin Sync 检查、初始化或更新 Build and Verify
- **THEN** Plugin Sync MUST 调用适用的 `build-and-verify doctor`、`build-and-verify init` 或 `build-and-verify update`
- **THEN** Plugin Sync MUST NOT 读取、刷新、提交或报告 `.build-and-verify/runtime/`
