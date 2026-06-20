## Context

当前仓库同时维护 Agent Guard Plugin（代理守卫插件）源码、OpenSpec 规格、Codex marketplace catalog（市场目录）和 Claude marketplace catalog。`main` 与 `marketplace` 分支存在发布态差异，核心问题是：这些差异必须可解释、可复现、可验证，不能长期靠手工维护发布分支。

已确认前提：

- Codex 与 Claude 的 marketplace source（市场来源）可以指向 Git ref（Git 引用）。
- fixed release（固定版本发布）适合使用 tag（标签）和 GitHub Release（GitHub 发布）。
- latest channel（最新通道）如果要保持订阅链接不变并自动更新，必须使用稳定可移动 ref，本仓库继续使用 `marketplace` 分支。
- Codex/Claude 当前订阅链接保持不变时，`marketplace` 分支仍是必要的 latest channel。

用户进一步确认：本次变更产物是可复用 `release-flow` Plugin（发布流程插件），不是 Agent Guard 专用脚本。该插件必须兼容 Codex 和 Claude，并遵循双方官方插件结构标准。

## Goals / Non-Goals

**Goals:**

- 提供独立 `release-flow` Plugin，可在不同项目中复用。
- 插件结构同时满足 Codex 和 Claude：包含 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json`、`skills/`、脚本和模板。
- 让 `main` 成为唯一源码来源。
- 让 `marketplace` 成为远端 generated deployment branch（生成型发布分支），由 GitHub Workflow 从 `main` 生成。
- 本地不创建发布分支、不打 tag、不 push 发布内容。
- 通过 `.release-flow/config.yaml` 保存发布流程配置。
- 通过 `.release-flow/projection.yaml` 保存轻量发布投影变量注册表。
- 将发布变量值托管到 GitHub Actions Variables。
- 初始化阶段先输出 GitHub 仓库配置方案；首版通过 `github-plan` 和 `configure-github --dry-run` 给出手动步骤，不调用真实 GitHub 设置 API。
- 发布前检查必须阻断缺失变量快照、未声明投影差异、版本不一致和 manifest 不一致的情况；GitHub repository settings 远端回读后续再做。

**Non-Goals:**

- 不改变 Agent Guard Runtime（代理守卫运行时）行为。
- 不改变 Guard Profile（守卫画像）或 hooks（钩子）契约。
- 不接管项目日常开发和测试配置。
- 不引入 `.project-config`、dev/test/release profile（配置档）或完整文件覆盖机制。
- 不在 `projection.yaml` 中保存变量值或 secret（密钥）。
- 首版不做 Branch Protection（分支保护）兜底；GitHub 仓库保护模型只按 Rulesets（规则集）设计。

## Decisions

### Decision 1: 发布流程做成双端兼容 Plugin

`release-flow` 是跨项目发布工作流，必须作为独立 Plugin 发布。插件包必须包含：

- `.codex-plugin/plugin.json`
- `.claude-plugin/plugin.json`
- `skills/release-flow/SKILL.md`
- `skills/release-flow/scripts/`
- `skills/release-flow/assets/templates/`

Codex 侧遵循官方插件结构：插件 manifest 位于 `.codex-plugin/plugin.json`，技能位于 `skills/<skill>/SKILL.md`。Claude 侧遵循官方插件结构：插件 manifest 位于 `.claude-plugin/plugin.json`，插件可包含 `skills/`、脚本和其他组件。

### Decision 2: `main` 是源码，`marketplace` 是生成型发布分支

`main` 是唯一源码来源。`marketplace` 不作为开发分支，不本地维护，也不通过 PR 更新。发布 workflow 从 `main` checkout，应用发布投影变量，生成 `marketplace` 内容并推送远端分支。

这不是 merge（合并）或 cherry-pick（挑选提交），而是从 `main` 重新生成发布分支。

### Decision 3: 发布由 GitHub Workflow 触发和执行

发布使用 `workflow_dispatch`。本地 `release-flow` 只负责：

- 项目启用时生成 `.release-flow` 配置和薄 GitHub Workflow 入口。
- 单次发布初始化时生成 `.release-flow/releases/<tag>/release-plan.json`。
- 执行 preflight（发布前检查）。
- 调用 `gh workflow run` 触发 GitHub Workflow。
- 拉取 workflow run 结果并生成总结。

真正的发布写操作都在 GitHub Actions 中完成：

- 创建或更新远端 `marketplace` 分支。
- 创建 tag。
- 创建 GitHub Release。
- 输出发布结果。

### Decision 4: 发布流程配置和发布投影注册表解耦

`.release-flow/config.yaml` 只保存发布流程配置，例如 source ref、channel branch、workflow 文件、记录目录和 GitHub Rulesets 期望。

`.release-flow/projection.yaml` 只保存发布投影变量注册表，例如变量名、用途、是否必填、敏感性、注入文件和 JSON Pointer（JSON 指针）路径。

`projection.yaml` 禁止保存变量值，只允许保存 `description`、`example` 等说明字段。实际变量值托管到 GitHub Actions Variables。

### Decision 5: GitHub Variables 托管发布态变量值

处理 `main` 与 `marketplace` 差异的轻量方式是：Git 中保存投影规则，GitHub 保存变量值。

示例：

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

发布 workflow 读取 `.release-flow/projection.yaml` 和 GitHub Actions Variables，修改 JSON 文件后生成 `marketplace` 分支。

### Decision 6: Rulesets 优先，首版不做 Branch Protection 兜底

GitHub 仓库配置方案以 Rulesets 为准：

- `main` 仍通过 PR 进入。
- workflow 不允许绕过 `main` 的 PR 规则。
- `marketplace` 只允许发布 workflow 写入。
- tag 由 workflow 创建，发布后不可修改。

首版不设计 Branch Protection 兜底，避免实现分叉。

## Directory Contracts

目标项目初始化后：

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
- `.release-flow/.gitignore` 进 Git，并忽略 `/releases/`。
- `.release-flow/releases/<tag>/` 是本地发布记录，不进 Git。
- 发布目录名固定使用 tag，例如 `v0.1.2`。
- 目标项目不保存 release-flow 发布脚本；脚本和模板保留在插件包中。
- `.github/workflows/release.yml` 是从插件模板生成的薄 workflow 入口。

插件包结构：

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

## Lifecycle

发布流程分两层：

- Project setup（项目启用）：一次性接入 `release-flow`，生成项目配置和薄 workflow。
- Release lifecycle（单次发布生命周期）：每个版本执行 4 阶段，依次是 release init、preflight、publish、summarize。

### Project setup（项目启用）

`release-flow setup` 或等价初始化入口 MUST：

- 调研当前仓库。
- 生成 `.release-flow/config.yaml`。
- 生成 `.release-flow/projection.yaml`。
- 生成 `.release-flow/.gitignore`。
- 从插件模板生成目标项目的薄 GitHub Workflow 入口。
- 分析 `main` 与现有 `marketplace` 的差异，推断发布变量建议值。
- 输出 GitHub 仓库配置方案。
- 首版 `configure-github --authorize-github` 不写 GitHub 仓库设置，返回自动写入暂不可用。
- 用户不授权时，输出手动配置步骤。
- 不创建 `.release-flow/releases/<tag>/release-plan.json`。
- 不把插件内的发布脚本复制到目标项目。

### 1. 单次发布初始化阶段

`release-flow release-init` 或等价入口 MUST：

- 为本次发布创建 `.release-flow/releases/<tag>/release-plan.json`。
- release-plan MUST 包含 version、tag、sourceRef、channelBranch、workflow file、projection registry 和 dryRun 标记。
- release-plan 目录名 MUST 使用 tag。
- 本阶段 MUST NOT 创建本地发布分支、创建 tag 或 push。

### 2. 发布前检查阶段

`release-flow preflight` MUST：

- 检查 `.release-flow/config.yaml` 和 `.release-flow/projection.yaml` 存在且合法。
- 检查传入的 GitHub Actions Variables 快照存在且覆盖所有 required 变量。
- 检查 version、tag 和 manifest version 一致。
- 从 `main + projection` 生成发布投影。
- 对比远端 `marketplace`，拒绝未被 projection 描述的差异。

首版 preflight 不调用真实 GitHub API，不声称已回读验证 Rulesets 或 workflow 权限。GitHub repository settings 由 `github-plan` 和 `configure-github --dry-run` 输出 Actions 权限、Rulesets 和 Actions Variables 的配置方案与手动步骤。

### 3. 发布阶段

`release-flow publish` MUST：

- 读取已经存在的 `.release-flow/releases/<tag>/release-plan.json`。
- 通过 `workflow_dispatch` 触发 GitHub Workflow。
- 本地不创建发布分支、不打 tag、不 push。
- GitHub Workflow 从 `sourceRef` checkout，应用 projection，创建或更新 `marketplace`，创建 tag 和 GitHub Release。

### 4. 总结阶段

`release-flow summarize` MUST：

- 读取 workflow run 结果。
- 写入 `.release-flow/releases/<tag>/workflow-run.json`。
- 写入 `.release-flow/releases/<tag>/release-summary.md`。
- 输出 tag、GitHub Release URL、`marketplace` commit、变量检查结果和结论。

## Risks / Trade-offs

- 发布变量值不在 Git 中：Git 只能审计变量注册和注入规则。缓解方式是 init/preflight 强制检查 GitHub Actions Variables。
- GitHub Actions 写权限配置复杂：缓解方式是 init 阶段先给配置方案；首版只输出手动步骤，远端自动配置和回读验证后续再做。
- `marketplace` 分支仍可能被人工修改：缓解方式是 preflight 对比 `main + projection` 与远端 `marketplace`，发现未声明差异则失败。
- 双端插件结构可能漂移：缓解方式是测试必须同时检查 Codex 和 Claude manifest、Skill、脚本和模板存在。

## Migration Plan

1. 重写 `release-flow-plugin` delta spec，固化双端插件结构和发布生命周期。
2. 修改 `agent-guard-plugin-runtime` delta spec，明确 Agent Guard 使用 release-flow 管理 fixed release 与 latest channel。
3. 重写 Design Doc 和任务清单，旧 build plan 作废。
4. 后续 build 阶段新增 `plugins/release-flow` 插件包，脚本和模板保留在插件包内。
5. 为当前仓库新增 `.release-flow/config.yaml`、`.release-flow/projection.yaml`、`.release-flow/.gitignore` 和薄 GitHub Workflow 入口。
6. 用 Agent Guard 当前 `main`/`marketplace` 差异生成 projection 建议，并由用户确认变量值写入 GitHub Actions Variables。

Rollback（回滚）策略：如果新流程不可用，保留当前 `marketplace` 分支订阅入口不变；只暂停 release-flow 自动发布，不移动已发布 tag。

## Open Questions

- 首版 GitHub Workflow 是否只支持一个 plugin，还是支持 monorepo 多 plugin 发布，需要 build 计划阶段确认。
