## Why

本仓库的新工作树没有统一的本地 Python（Python 语言）环境准备入口；开发者可能依赖系统解释器或遗漏开发依赖，导致构建检查和验证结果不一致。量化研究实验室的工作树初始化脚本已验证“复用本地虚拟环境、安装声明依赖、失败即停止”的最小模式，适合在本仓库采用。

## What Changes

- 新增 PowerShell（命令行脚本）工作树初始化入口，创建或复用仓库 `.venv`（本地虚拟环境）。
- 固定使用 Python（Python 语言）3.12 创建缺失环境，更新 pip（包安装工具），并仅安装 `requirements-dev.txt`（开发依赖清单）声明的依赖。
- 保持失败退出码，且不运行构建检查、验证或修改 Build and Verify（构建与验证）配置。

## Capabilities

### New Capabilities

- `worktree-environment-setup`: 为本仓库工作树建立可重复的本地 Python（Python 语言）开发环境。

### Modified Capabilities

- 无。

## Impact

- 新增 `scripts/setup-worktree.ps1`。
- 新增或更新覆盖脚本行为的仓库测试。
- 不修改量化研究实验室，也不新增依赖或构建验证入口。
