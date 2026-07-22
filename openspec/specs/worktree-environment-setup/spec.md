# worktree-environment-setup Specification

## Purpose
TBD - created by archiving change configure-build-and-verify-init-script. Update Purpose after archive.
## Requirements
### Requirement: 工作树环境初始化入口
系统 MUST 提供 `scripts/setup-worktree.ps1`（工作树初始化脚本），用于为本仓库工作树准备本地 Python（Python 语言）开发环境。

#### Scenario: 缺失本地环境时初始化
- **WHEN** 开发者运行脚本且仓库 `.venv\Scripts\python.exe`（本地虚拟环境解释器）不存在
- **THEN** 脚本 MUST 使用 Python（Python 语言）3.12 创建 `.venv`（本地虚拟环境）
- **THEN** 脚本 MUST 使用该本地解释器升级 pip（包安装工具）并安装 `requirements-dev.txt`（开发依赖清单）

#### Scenario: 已有本地环境时复用
- **WHEN** 开发者运行脚本且仓库 `.venv\Scripts\python.exe`（本地虚拟环境解释器）已存在
- **THEN** 脚本 MUST 不重建或删除该环境
- **THEN** 脚本 MUST 使用该本地解释器升级 pip（包安装工具）并安装 `requirements-dev.txt`（开发依赖清单）

### Requirement: 初始化失败可见且不扩展职责
脚本 MUST 保留失败命令的非零退出码，且只能执行环境创建与依赖安装。

#### Scenario: 环境创建或依赖安装失败
- **WHEN** Python（Python 语言）环境创建、pip（包安装工具）升级或依赖安装返回非零退出码
- **THEN** 脚本 MUST 立即以非零退出码结束
- **THEN** 脚本 MUST 不运行后续初始化步骤、构建检查或验证

#### Scenario: 从仓库外调用
- **WHEN** 开发者从非仓库根目录调用脚本
- **THEN** 脚本 MUST 相对于脚本自身定位仓库根目录
- **THEN** 脚本 MUST 仍只在该仓库创建或使用 `.venv`（本地虚拟环境）
