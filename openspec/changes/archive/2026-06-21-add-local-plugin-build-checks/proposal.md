## Why

Comet build guard（构建守卫）需要本仓库提供明确的构建或测试命令，否则没有传统编译入口时会在 build 阶段卡住。本仓库是 Agent Plugin（代理插件）和 Skill（技能）仓库，构建命令应表达“本地插件包是否成型”，而不是硬套传统编译。

## What Changes

- 新增仓库本地构建检查入口，用于检查插件市场目录、插件清单、路径引用和发布投影的一致性。
- 新增仓库本地 `verify_command`（验证命令），用于运行标准 Python（Python 语言）测试入口。
- 将 Claude plugin validate（Claude 插件本地校验）纳入构建命令，但第一版不启用 `--strict`（严格模式）。
- 在构建检查中覆盖 Claude marketplace（Claude 插件市场目录）、Codex plugin manifest（Codex 插件清单）、release-flow projection（发布流程投影）注册一致性和 Guard Profile（守卫画像）模板镜像一致性。
- 废弃 `.comet/build-check.sh` 作为正式构建入口；本次不修改 Comet 自身流程、脚本或产物。

## Capabilities

### New Capabilities

- `local-plugin-build-checks`: 定义本仓库本地插件构建检查与验证命令的行为边界。

### Modified Capabilities

- `cross-agent-review`: 保存审查输入快照到 review output（审查输出）目录。

## Impact

- 影响 `.comet/config.yaml` 的项目级配置边界。
- 影响新增的仓库检查入口，例如 `scripts/check.py`。
- 影响 Python 测试配置，例如 `pyproject.toml` 的 pytest（Python 测试框架）默认设置。
- 影响本地开发和 Comet 流程中的 build/verify（构建/验证）命令语义。
- 影响 `cross-agent-review`（跨代理审查）的输入快照保存位置。
