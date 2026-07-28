## Why

当前 Agent Guard Plugin（代理守卫插件）的 `main` 与 `marketplace` 发布分支存在差异。后续如果继续手工维护发布分支，会让差异来源不透明，也会让 Codex/Claude marketplace subscription（市场订阅）的 latest channel（最新通道）长期依赖人工纪律。

已验证的前提是：Codex 与 Claude 的 marketplace source（市场来源）都可以指向 Git ref（Git 引用）。固定版本可以使用 tag（标签），但如果要保持现有订阅链接不变并自动更新 latest，就仍需要一个稳定可移动分支，例如 `marketplace`。

用户需要把这套发布模型沉淀成可复用 Plugin（插件），在所有项目中使用。该插件必须同时兼容 Codex 和 Claude，遵循双方官方插件结构标准，交付内容包括 Skill（技能）、脚本和模板。

## What Changes

- 新增通用 `release-flow` Plugin（发布流程插件）能力，用于跨项目复用发布流程。
- `release-flow` Plugin MUST 同时提供 Codex `.codex-plugin/plugin.json` 和 Claude `.claude-plugin/plugin.json` manifest（清单）。
- 插件 MUST 包含 `skills/`、确定性脚本和模板目录，避免只交付零散脚本。
- 项目通过 `.release-flow/config.yaml` 声明发布流程配置。
- 项目通过 `.release-flow/projection.yaml` 声明从 `main` 生成 `marketplace` 的发布投影规则。
- `.release-flow/projection.yaml` 只保存变量注册、说明和注入规则，不保存变量值。
- 发布变量值托管到 GitHub Actions Variables（GitHub Actions 变量）。
- 发布由 `workflow_dispatch` 触发的 GitHub Workflow（工作流）执行，本地插件只负责初始化、检查、触发和总结。
- `marketplace` 是远端 generated deployment branch（生成型发布分支），本地不需要存在，也不作为开发分支。
- 固定版本使用 tag 与 GitHub Release（GitHub 发布）；latest 自动更新使用 `marketplace` 分支。

## Capabilities

### New Capabilities

- `release-flow-plugin`: 定义可复用发布流程 Plugin 的官方结构、配置、变量注册表、GitHub 仓库设置、发布触发、发布投影和验证契约。

### Modified Capabilities

- `agent-guard-plugin-runtime`: 修改 Agent Guard 发布订阅要求，使 fixed release（固定版本发布）、latest channel（最新通道）和 `marketplace` 发布分支边界由 `release-flow` Plugin 配置和验证。

## Impact

- 影响 OpenSpec 规格：新增 `release-flow-plugin` capability，并修改 `agent-guard-plugin-runtime`。
- 影响插件结构：新增 `plugins/release-flow` Plugin 包，包含 Codex/Claude manifest、Skill、脚本和模板。
- 影响当前仓库发布配置：新增 `.release-flow/config.yaml`、`.release-flow/projection.yaml`、`.release-flow/.gitignore` 和由插件模板生成的薄 GitHub Workflow 入口。
- 发布脚本和模板属于 `release-flow` 插件包资产，不复制进目标项目仓库。
- 影响 GitHub 仓库配置：初始化阶段需要给出 Rulesets（规则集）、Actions 权限和 GitHub Actions Variables 的配置方案；用户授权后可直接修改 GitHub 仓库设置。
- 不影响 Agent Guard Runtime（代理守卫运行时）、Guard Profile（守卫画像）或 hooks（钩子）运行逻辑。
