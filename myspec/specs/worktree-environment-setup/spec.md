# worktree-environment-setup Specification

## Purpose

TBD - created by archiving change configure-build-and-verify-init-script. Update Purpose after archive.

## Requirements

### Requirement: 工作树环境初始化入口
系统 MUST 提供 `scripts/setup-worktree.ps1`（工作树初始化脚本），用于准备本仓库工作树的 Python（Python 语言）开发环境，并让依赖清单一致的工作树共享主仓库根目录的 Node.js（运行时）开发依赖。

#### Scenario: 主仓库初始化
- **WHEN** 开发者在主仓库运行脚本
- **THEN** 脚本 MUST 创建或复用 `.venv`（本地虚拟环境），并使用 Python（Python 语言）3.12 安装 `requirements-dev.txt`（开发依赖清单）
- **THEN** 脚本 MUST 使用根目录锁文件准备根目录 Node.js（运行时）开发依赖

#### Scenario: 工作树复用共享依赖
- **WHEN** 开发者在依赖清单与主仓库一致的链接工作树运行脚本，且主仓库共享依赖已存在
- **THEN** 脚本 MUST 让该工作树的根级 `node_modules`（依赖目录）指向主仓库根目录的共享依赖
- **THEN** 脚本 MUST 不在该工作树重复安装 Node.js（运行时）开发依赖

#### Scenario: 已有本地 Python 环境时复用
- **WHEN** 开发者运行脚本且当前工作树 `.venv\Scripts\python.exe`（本地虚拟环境解释器）已存在
- **THEN** 脚本 MUST 不重建或删除该环境
- **THEN** 脚本 MUST 使用该本地解释器升级 pip（包安装工具）并安装 `requirements-dev.txt`（开发依赖清单）
### Requirement: 初始化失败可见且不扩展职责
脚本 MUST 保留失败命令的非零退出码，并在共享依赖不可安全复用时停止；Build and Verify（构建与验证）不得承担依赖安装职责。

#### Scenario: 环境创建或依赖安装失败
- **WHEN** Python（Python 语言）环境创建、pip（包安装工具）升级或依赖安装返回非零退出码
- **THEN** 脚本 MUST 立即以非零退出码结束
- **THEN** 脚本 MUST 不运行后续初始化步骤、构建检查或验证

#### Scenario: 共享依赖缺失
- **WHEN** 开发者在链接工作树运行脚本，但主仓库根目录共享依赖不存在
- **THEN** 脚本 MUST 以非零退出码结束
- **THEN** 脚本 MUST 提示开发者先在主仓库根目录运行初始化

#### Scenario: 依赖清单不一致
- **WHEN** 链接工作树与主仓库的 Node.js（运行时）依赖清单不一致
- **THEN** 脚本 MUST 以非零退出码结束
- **THEN** 脚本 MUST 不修改主仓库共享依赖

#### Scenario: 从仓库外调用
- **WHEN** 开发者从非仓库根目录调用脚本
- **THEN** 脚本 MUST 相对于脚本自身定位当前工作树
- **THEN** 脚本 MUST 按当前工作树身份执行对应的主仓库初始化或共享依赖复用行为
