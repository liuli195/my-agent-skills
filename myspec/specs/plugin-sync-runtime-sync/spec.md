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
### Requirement: Plugin Sync switches one marketplace plugin with native client evidence

Plugin Sync（插件同步）MUST 在用户授权后通过客户端原生操作逐插件切换开发与正式来源，先核对目标和原安装状态，使用完整插件加市场标识；Claude（代码助手）保留原安装范围。切换前后 MUST 核对两个市场、其他插件、实际来源、版本、启用及资源内容。开发修改后按客户端刷新和会话重新加载步骤生效，不把安装或文件可读当作新会话已执行。

#### Scenario: A user switches an installed plugin

- **WHEN** 用户明确选择目标插件与新来源
- **THEN** 同一客户端按完整标识串行切换，两个市场和无关插件保留
- **THEN** 实际来源及资源核对通过才报告已安装；运行中的代理及业务工具需要重新加载时明确提示
### Requirement: Plugin Sync reports failed switches and restores recorded sources accurately

Plugin Sync MUST 对目标缺失、重复来源、安装失败及恢复失败分别报告，保留本次操作的真实错误与可用恢复动作；恢复时核对实际版本，不声称已恢复不可取得的旧版本。数据中心来源变化时 MUST 检查并更新用户明确接入的项目关系，不通过全盘扫描寻找仓库，不另建定位程序或长期安装清单。

#### Scenario: Installation or restoration fails

- **WHEN** 目标不可用、安装失败或恢复原来源失败
- **THEN** 工具保留准确状态和错误，明确已完成步骤与下一动作，不报告完整成功
- **THEN** 未完成项目更新或需要重启时明确列出，不删除源码、用户数据或无关安装
