## Why

当前 `test-framework`（测试框架）Plugin（插件）的名称偏向测试框架初始化，但实际已经承担本仓库 `build`（构建检查）和 `verify`（验证）的统一入口职责。#70 需要把该入口语义稳定下来，避免流程在默认 fast verify（快速验证）和 full verify（完整验证）之间隐式切换。

## What Changes

- **BREAKING RENAME**: 将 `test-framework`（测试框架）Plugin（插件）和 Skill（技能）改名为 `build-and-verify`（构建与验证）。
- **BREAKING RENAME**: 将插件目录、Skill（技能）目录、脚本入口和配置目录改为 `build-and-verify`（构建与验证）命名，不保留旧 `test-framework`（测试框架）兼容入口。
- **BREAKING**: 删除根目录 `pyproject.toml`（Python 测试配置），不再保留多个测试行为入口或根目录测试配置来源。
- 将 `build-and-verify`（构建与验证）Skill（技能）说明明确为：所有需要运行 build（构建检查）或 verify（验证）命令的流程都必须使用该 Skill（技能）入口。
- 明确默认 `verify`（验证）就是 fast verify（快速验证）。
- 明确 full verify（完整验证）只允许用于 PR Flow（拉取请求流程）hotfix（热修复）直推验证命令和 PR CI（拉取请求持续集成）集成；其他场景不得自动使用 full verify（完整验证），必须说明原因并获得用户确认。
- 更新本仓库 Comet（双星流程）、PR Flow（拉取请求流程）、marketplace（市场目录）、release projection（发布投影）、OpenSpec（开放规格）和测试引用到新入口。

## Release Notes

- **Breaking change（破坏性变更）**: 根目录不再提供 `pyproject.toml`（Python 项目配置）作为 pytest（Python 测试运行器）入口。不要用裸 `pytest` 作为本仓库验证入口；请使用 `build-and-verify`（构建与验证）提供的 `build`（构建检查）和 `verify`（验证）命令。
- 本仓库不以 `pip install -e .`（可编辑安装）作为 Plugin（插件）/Skill（技能）开发入口；删除的 `pyproject.toml`（Python 项目配置）只承载 pytest（Python 测试运行器）参数，必要参数已迁移到 `.build-and-verify/config.json` 的显式命令。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `test-framework-plugin`: 同一 Plugin（插件）能力从 `test-framework`（测试框架）改名为 `build-and-verify`（构建与验证），不按新增/移除能力处理。
- `local-verification-modes`: 默认 fast verify（快速验证）和显式 full verify（完整验证）继续保留，但入口、配置目录和允许使用 full verify（完整验证）的边界改为新契约。
- `local-plugin-build-checks`: 本仓库 build（构建检查）和 verify（验证）命令改为 `build-and-verify`（构建与验证）入口，并删除根目录 Python（Python 语言）测试配置来源。
- `full-verification-runtime`: 本仓库完整验证的规范命令改为新的 `build-and-verify`（构建与验证）入口。
- `pr-flow-plugin`: hotfix（热修复）直推路径保留 full verify（完整验证）作为显式验证命令，其余 PR Flow（拉取请求流程）路径不得隐式升级到 full verify（完整验证）。

## Impact

- 影响 `plugins/test-framework/` 到 `plugins/build-and-verify/` 的目录与文件命名。
- 影响 `.test-framework/` 到 `.build-and-verify/` 的本仓库配置目录命名。
- 影响 `.comet.yaml`、`.comet/config.yaml`、`.pr-flow/config.yaml`、marketplace（市场目录）和 release projection（发布投影）中的插件与命令引用。
- 影响 `tests/test_test_framework_plugin.py`、`tests/test_local_plugin_build_checks.py`、`tests/test_pr_flow_cli.py`、插件 package（包）测试和相关 OpenSpec（开放规格）测试。
- 删除根目录 `pyproject.toml`（Python 测试配置），需要把 pytest（Python 测试运行器）发现范围和输出参数显式写入 `build-and-verify`（构建与验证）配置命令。
