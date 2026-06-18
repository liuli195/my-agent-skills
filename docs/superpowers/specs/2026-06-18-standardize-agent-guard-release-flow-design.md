---
comet_change: standardize-agent-guard-release-flow
role: technical-design
canonical_spec: openspec
---

# Release Flow Plugin 统一发布流程技术设计

## 背景

当前 Agent Guard Plugin（代理守卫插件）的 `main` 与 `marketplace` 发布分支存在差异。问题的核心不是“是否保留发布分支”，而是这些差异必须可解释、可复现、可验证。

已确认：

- fixed release（固定版本发布）使用 tag（标签）和 GitHub Release（GitHub 发布）。
- latest channel（最新通道）继续使用 `marketplace` 分支，以保持现有 Codex/Claude 订阅链接不变。
- `marketplace` 是远端 generated deployment branch（生成型发布分支），本地不维护。
- 发布由 GitHub Workflow（工作流）执行，本地只初始化、检查、触发和总结。
- 处理 `main` 与 `marketplace` 差异的轻量方案是：Git 里保存投影规则，GitHub Actions Variables（GitHub Actions 变量）保存变量值。

本次变更的产物是可复用 `release-flow` Plugin（发布流程插件），不是 Agent Guard 专用脚本。插件必须兼容 Codex 和 Claude，并遵循双方官方插件结构。

## 官方结构约束

Codex 官方插件结构要求插件 manifest 位于 `.codex-plugin/plugin.json`，插件可包含 `skills/`，Skill（技能）位于 `skills/<name>/SKILL.md`，并可带脚本和资源。Claude 官方插件结构要求插件 manifest 位于 `.claude-plugin/plugin.json`，插件是自包含目录，可包含 `skills/`、脚本、hooks、MCP 等组件；Skill 位于 `skills/<name>/SKILL.md`。

因此 `release-flow` 插件结构固定为：

```text
plugins/release-flow/
  .codex-plugin/plugin.json
  .claude-plugin/plugin.json
  skills/
    release-flow/
      SKILL.md
      scripts/
      assets/
        templates/
```

首版必须同时验证 Codex manifest、Claude manifest、Skill、脚本和模板存在。

## 目标

- 新增独立 `release-flow` Plugin，跨项目复用发布流程。
- 保持 `main` PR 流程不变。
- 保留 `marketplace` 作为 latest channel，但只由 workflow 生成。
- 本地不创建发布分支、不打 tag、不 push。
- 使用 `.release-flow/config.yaml` 保存发布流程配置。
- 使用 `.release-flow/projection.yaml` 保存轻量发布投影变量注册表。
- 使用 GitHub Actions Variables 保存变量值。
- 初始化阶段输出 GitHub 仓库配置方案；首版通过 `github-plan` 和 `configure-github --dry-run` 输出手动步骤，不调用真实 GitHub 设置 API。
- 发布前检查必须能解释 `main` 与 `marketplace` 的合法差异。

## 非目标

- 不改变 Agent Guard Runtime（代理守卫运行时）行为。
- 不改变 Guard Profile（守卫画像）或 hooks（钩子）契约。
- 不接管项目日常开发和测试配置。
- 不引入 `.project-config`、dev/test/release profile（配置档）或完整文件覆盖。
- 不把变量值或 secret（密钥）写入 `.release-flow/projection.yaml`。
- 首版不做 Branch Protection（分支保护）兜底，只设计 Rulesets（规则集）。

## 架构

`release-flow` 分为四层：

1. Plugin 层
   提供 Codex/Claude 双端 manifest、Skill、脚本和模板。

2. 项目配置层
   `.release-flow/config.yaml` 保存发布流程配置。
   `.release-flow/projection.yaml` 保存发布投影变量注册表。

3. GitHub 执行层
   GitHub Actions Variables 保存变量值。
   GitHub Workflow 读取 projection 和 variables，从 `main` 生成 `marketplace`。

4. 本地审计层
   `.release-flow/releases/<tag>/` 保存本地 release-plan、preflight-report、workflow-run 和 release-summary，不进 Git。

## 目录契约

目标项目：

```text
.release-flow/
  config.yaml
  projection.yaml
  .gitignore
  releases/
    v0.1.2/
      release-plan.json
      preflight-report.json
      workflow-run.json
      release-summary.md
```

规则：

- `.release-flow/config.yaml` 进 Git。
- `.release-flow/projection.yaml` 进 Git。
- `.release-flow/.gitignore` 进 Git，只忽略 `/releases/`。
- `.release-flow/releases/<tag>/` 不进 Git。
- 发布目录名固定为 tag。
- 目标项目不保存 release-flow 发布脚本；脚本和模板保留在插件包中。
- `.github/workflows/release.yml` 是从插件模板生成的薄 workflow 入口。

## 配置模型

`.release-flow/config.yaml` 只保存发布流程配置：

```yaml
version: 1

release:
  sourceRef: main
  channelBranch: marketplace
  branchMode: remote-only

workflow:
  file: .github/workflows/release.yml
  trigger: workflow_dispatch

projection:
  registry: .release-flow/projection.yaml

records:
  directory: .release-flow/releases
  directoryName: tag
  gitTracked: false
```

`.release-flow/projection.yaml` 保存变量注册和注入规则，不保存变量值：

```yaml
version: 1

variables:
  CODEX_MARKETPLACE_NAME:
    source: github-actions-variable
    required: true
    sensitive: false
    description: Codex marketplace catalog name

transforms:
  - path: .agents/plugins/marketplace.json
    type: json-env
    set:
      /name: CODEX_MARKETPLACE_NAME
```

GitHub Actions Variables 保存 `CODEX_MARKETPLACE_NAME` 等实际值。

## 发布流程

流程分两层：

- Project setup（项目启用）：一次性接入插件，生成配置和薄 workflow。
- Release lifecycle（单次发布生命周期）：每次发布执行 4 阶段。

### Project setup（项目启用）

`release-flow setup` 或等价初始化入口调研仓库，生成 `.release-flow` 配置，并从插件模板生成目标项目的薄 GitHub Workflow。它还会分析现有 `main` 与 `marketplace` 差异，生成 projection 和 GitHub Variables 建议值。

初始化阶段必须先输出 GitHub 仓库配置方案。首版 `configure-github --authorize-github` 不写 GitHub 仓库设置，返回自动写入暂不可用；`github-plan` 和 `configure-github --dry-run` 输出 Actions 权限、Rulesets 和 Actions Variables 的手动配置步骤。远端自动配置和回读验证后续再做。

项目启用阶段不创建 `release-plan.json`，也不把插件内发布脚本复制到目标项目。

### 1. 单次发布初始化

`release-flow release-init` 或等价入口在发布前创建 `.release-flow/releases/<tag>/release-plan.json`。release-plan 包含 version、tag、sourceRef、channelBranch、workflow file、projection registry 和 dryRun 标记。

本阶段不创建本地发布分支、不打 tag、不 push。

### 2. 发布前检查

`release-flow preflight` 检查：

- `.release-flow/config.yaml` 合法。
- `.release-flow/projection.yaml` 合法。
- 传入的 GitHub Actions Variables 快照覆盖 required 变量。
- tag 与 manifest version 一致。
- `main + projection` 能生成 expected marketplace tree。
- 远端 `marketplace` 不存在未被 projection 描述的差异。

首版 preflight 不调用真实 GitHub API，不声称已回读验证 Rulesets 或 workflow 权限。GitHub repository settings 由 `github-plan` 和 `configure-github --dry-run` 输出配置方案。

### 3. 发布

`release-flow publish` 读取已经存在的 `.release-flow/releases/<tag>/release-plan.json`，然后用 `workflow_dispatch` 触发 GitHub Workflow。

本地不创建发布分支、不打 tag、不 push。

GitHub Workflow 负责：

- checkout `sourceRef`
- 读取 `.release-flow/projection.yaml`
- 读取 GitHub Actions Variables
- 应用 `json-env` transforms
- 创建或更新远端 `marketplace`
- 创建 tag
- 创建 GitHub Release

### 4. 总结

`release-flow summarize` 写入：

- `.release-flow/releases/<tag>/workflow-run.json`
- `.release-flow/releases/<tag>/release-summary.md`

总结包含 tag、GitHub Release URL、`marketplace` commit、变量检查结果和发布结论。

## Agent Guard 适配

Agent Guard 是首个适配对象：

- `main` 保持开发态 catalog。
- `marketplace` 由 release workflow 生成发布态 catalog。
- Codex catalog 和 Claude catalog 的发布态差异通过 `.release-flow/projection.yaml` 注册变量解释。
- 变量值放在 GitHub Actions Variables。
- 现有 `liuli195/my-agent-skills@marketplace` latest 订阅链接保持不变。

## 测试策略

- 插件结构测试：检查 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json`、`skills/release-flow/SKILL.md`、脚本和模板。
- 配置解析测试：检查 `.release-flow/config.yaml` 和 `.release-flow/projection.yaml`。
- projection 测试：用变量生成 JSON 修改结果。
- preflight 测试：缺变量、未声明差异、版本不一致时失败。
- workflow dry-run 测试：验证 workflow inputs 和本地 release-plan。
- Agent Guard 适配测试：确认当前 `main` 与 `marketplace` 的合法差异能由 projection 解释。
- 端到端回归：project setup -> release init -> preflight -> workflow dry-run -> summary。

## 风险与缓解

- 发布变量值不在 Git：用 preflight 检查 GitHub Actions Variables，并在 summary 中记录检查结果。
- GitHub 权限复杂：init 先输出配置方案；首版只输出手动步骤，远端自动配置和回读验证后续再做。
- `marketplace` 被人工修改：preflight 对比 expected marketplace tree，发现未声明差异即失败。
- 双端插件结构漂移：测试同时覆盖 Codex 和 Claude manifest。

## Spec Patch

已回写 OpenSpec delta spec：

- 新增 `release-flow-plugin` capability。
- 修改 `agent-guard-plugin-runtime`，明确 Agent Guard 的 fixed release 和 latest channel 由 `release-flow` Plugin 配置和验证。
