---
comet_change: add-local-plugin-build-checks
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-21-add-local-plugin-build-checks
status: final
---

# Local Plugin Build Checks Design

## 背景

本仓库维护 Agent Plugin（代理插件）和 Skill（技能）源码，没有传统编译产物。Comet（双星流程）build guard（构建守卫）需要明确的构建或测试入口才能推进，因此本仓库需要符合自身形态的本地入口。

构建入口不表示“编译”，而表示“本地插件包是否成型”。完整行为回归仍由验证入口承担。

## 技术方案

新增 `scripts/check.py` 作为统一入口：

```bash
python scripts/check.py build
python scripts/check.py verify
```

`build` 做本地、可重复、无外部副作用的插件包检查：

- 运行 `claude plugin validate .` 校验 Claude marketplace（Claude 插件市场目录）。
- 从 `.claude-plugin/marketplace.json` 自动读取本地插件 `source`，逐个运行 `claude plugin validate <source>`。
- 检查 marketplace（插件市场目录）中的插件名称和 `.claude-plugin/plugin.json` 的 `name` 一致。
- 检查每个本地插件都有 `.claude-plugin/plugin.json` 和 `.codex-plugin/plugin.json`。
- 检查 Codex plugin manifest（Codex 插件清单）必填字段和声明路径存在。
- 检查 `.release-flow/projection.yaml` 中 codex-marketplace（Codex 插件市场）生成器列出的插件集合和本地 marketplace 插件集合一致，且无重复。
- 检查 Guard Profile（守卫画像）模板镜像目录字节级一致。

`verify` 只负责完整测试：

```bash
python -m pytest
```

测试发现范围由 `pyproject.toml` 中的 pytest（Python 测试框架）配置控制。

## 关键取舍

不启用 `claude plugin validate --strict`（严格校验）。当前仓库存在 Claude warning（警告），严格模式会失败；严格清理应作为后续独立工作。

不把完整 pytest 放进 build。build 保持轻量，验证阶段再跑完整测试。

不访问 GitHub（代码托管平台）远端，不发布，不安装，不写用户配置。build 必须可以在本地稳定重复运行。

不做深层文档语义判断。Guard Profile 模板检查只做镜像一致性，不判断内容含义。

## 错误处理

`scripts/check.py build` 收集本地检查错误并输出明确失败项。Claude CLI（Claude 命令行工具）不可用时，应给出清楚错误，提示缺少 `claude` 命令。

路径检查必须解析到仓库根目录内，禁止 `..` 或绝对路径把检查范围带出仓库。

## 配置

`.comet/config.yaml` 只保存项目级流程配置，不重复保存 `build_command` 或 `verify_command`。当前 Comet build guard（构建守卫）仍按其兼容入口读取根目录 `.comet.yaml`。

`.comet/build-check.sh` 不再作为正式入口。执行阶段先确认没有引用；无引用时删除，避免继续误导。

## Cross-Agent Review 输入快照

cross-agent-review（跨代理审查）仍通过 CLI（命令行接口）接收 diff、spec、design、tasks 和 tests 输入文件。运行时先把这些输入复制到 review output（审查输出）目录的 `inputs/` 子目录，再让 reviewer（审查代理）读取快照内容。

默认结构：

```text
.local/cross-agent-review/<change>/<short-head>/
  inputs/
    diff.patch
    spec.md
    design.md
    tasks.md
    tests.txt
  review-report.md
  review-results.json
  review-pass.json
```

这样输入快照与本次 review 输出、`review-pass.json` 共享同一个 change/head 目录，后续排障不依赖系统临时目录。

## 测试策略

先写测试再实现：

- 测试 `build` 会读取 `.claude-plugin/marketplace.json` 并调用 Claude 校验。
- 测试 marketplace source（来源路径）缺失或越界会失败。
- 测试 marketplace 名称和 plugin manifest（插件清单）名称不一致会失败。
- 测试 Codex manifest 必填字段或路径缺失会失败。
- 测试 release-flow projection（发布流程投影）插件集合不一致或重复会失败。
- 测试 Guard Profile 模板镜像不一致会失败。
- 测试 `verify` 会调用 `python -m pytest`。
- 测试 `.comet/config.yaml` 不重复保存构建/验证命令。

最终验证命令：

```bash
python scripts/check.py build
python scripts/check.py verify
```
